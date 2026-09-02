"""Long-lived operator for the Owner-approved ADR-053 targeted repair.

The operator recovers the immutable V1 reviewed checkpoint, executes only
Case 25 when no durable successor exists, and resumes every later stage from
the separate successor checkpoint.  It never calls a Provider or source M3.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Coroutine, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Final, NoReturn, TextIO, cast

from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from mirror_api import demo_d02_final_orchestrator as orchestrator
from mirror_api import demo_d02_targeted_m4_repair as repair
from mirror_api import demo_d02_targeted_m4_repair_execution as repair_execution
from mirror_api.demo_d02_acquisition_identity import MANUAL_REVIEW_POLICY_DIGEST
from mirror_api.demo_d02_acquisition_operator import (
    D02LocalDurableIndex,
    D02OperatorError,
    _database_url,
    _emit,
    _require_database_head,
    _validate_workspace_authority,
)
from mirror_api.demo_d02_candidate_qualification import D02CandidateNormalizer
from mirror_api.demo_d02_final_runtime_checkpoint import (
    D02FinalRuntimeCheckpoint,
    D02FinalRuntimeCheckpointError,
)
from mirror_api.demo_d02_final_runtime_operator import _run_advisory_lock
from mirror_api.demo_d02_generic_admission_coordinator import (
    D02GenericAdmissionCoordinator,
    GenericAdmissionBundle,
    GenericAdmissionCoordinatorError,
    GenericAdmissionResult,
)
from mirror_api.demo_d02_generic_runtime_admission import (
    D02GenericRuntimeAdmissionError,
    D02QuestionBankConfiguration,
    build_generic_runtime_admission_bundle,
)
from mirror_api.demo_d02_private_vision_backend import PrivateVisionBackendError
from mirror_api.demo_d02_r2_runtime_forward import M4ExecutionOutput, RuntimeForwardError
from mirror_api.demo_d02_runtime_composition import (
    D02RuntimeCompositionError,
    compose_accepted_m3_backend,
    load_runtime_locators,
)
from mirror_api.demo_d02_runtime_result_store import (
    D02RuntimeResultStore,
    D02RuntimeResultStoreError,
    runtime_result_binding_digest,
)
from mirror_api.demo_d02_screening_adapters import PrincipalArtifactDecision
from mirror_api.demo_d02_source_acquisition import D02SourceAcquisitionError
from mirror_api.demo_d02_targeted_m4_repair_backend import (
    D02TargetedM4RepairBackend,
    TargetedJawRepairConfig,
    TargetedM4RepairError,
)
from mirror_api.demo_d02_targeted_m4_successor_checkpoint import (
    D02TargetedM4SuccessorCheckpoint,
    D02TargetedM4SuccessorCheckpointError,
    D02TargetedM4SuccessorStore,
    RecoveredTargetedM4Successor,
    SuccessorBindings,
)
from mirror_api.demo_idempotency import idempotency_key_hash
from mirror_api.demo_models import (
    D02CohortSpec,
    D02SelectedSourceManifest,
    D02SourceAcquisitionRun,
    D02SourceCandidate,
)

TARGETED_ARTIFACT_REVIEW_COMMAND_SCHEMA: Final = (
    "mirror.private/D02TargetedM4ArtifactReviewCommand/v1"
)
_MAX_REVIEW_COMMAND_BYTES: Final = 64_000
_FORMAL_STAGES: Final = (
    "PREDECESSOR_REVIEWED_FAILED",
    "REPAIR_POLICY_VALIDATED",
    "TARGET_M4_DURABLE",
    "TARGET_RESULT_M3_COMPLETE",
    "TARGET_REVIEW_REQUIRED",
    "SUCCESSOR_REVIEWED",
    "SUCCESSOR_SCREENING_REPLAYED",
    "ADMISSION_READY",
    "ADMITTED",
)


class D02TargetedM4RepairOperatorError(RuntimeError):
    """Stable, redacted operator failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True, repr=False)
class _Predecessor:
    spec: D02CohortSpec
    manifest: D02SelectedSourceManifest
    candidates: tuple[
        D02SourceCandidate,
        D02SourceCandidate,
        D02SourceCandidate,
        D02SourceCandidate,
    ]
    prepared: orchestrator.PreparedRuntimeEvidence = field(repr=False)
    decisions: Mapping[str, PrincipalArtifactDecision]
    report: Mapping[str, object]
    checkpoint_payload_digest: str
    result_store: D02RuntimeResultStore = field(repr=False, compare=False)


class _SuccessorResultPersistence:
    """Read-only 47+1 availability view for generic admission assembly."""

    def __init__(
        self,
        *,
        predecessor: D02RuntimeResultStore,
        successor: D02TargetedM4SuccessorStore,
    ) -> None:
        self._predecessor = predecessor
        self._successor = successor

    def persist(self, output: M4ExecutionOutput, case_ordinal: int) -> object:
        del output, case_ordinal
        _fail("SUCCESSOR_PERSISTENCE_IS_READ_ONLY")

    def verify_complete(self, *, outputs: Sequence[M4ExecutionOutput]) -> None:
        if len(outputs) != 48:
            _fail("SUCCESSOR_RESULT_CARDINALITY_INVALID")
        replacement = self._successor.load()[0]
        for ordinal, output in enumerate(outputs, start=1):
            expected = (
                replacement
                if ordinal == repair.TARGET_CASE_ORDINAL
                else self._predecessor.load(case_ordinal=ordinal)
            )
            if output != expected:
                _fail("SUCCESSOR_RESULT_AVAILABILITY_MISMATCH")


class D02TargetedM4RepairOperator:
    def __init__(
        self,
        *,
        sessions: sessionmaker[Session],
        database_url: str,
        workspace_root: Path,
        durable_index: D02LocalDurableIndex,
    ) -> None:
        self._sessions = sessions
        self._database_url = database_url
        self._workspace_root = workspace_root
        self._index = durable_index

    def diagnose(
        self,
        *,
        run_id: str,
        predecessor_idempotency_key_hash: str,
        strength_ppm: int,
    ) -> dict[str, object]:
        """Execute an unpersisted, redacted calibration attempt for Case 25 only."""

        predecessor = self._recover_predecessor(
            run_id=run_id,
            predecessor_idempotency_key_hash=predecessor_idempotency_key_hash,
        )
        config = TargetedJawRepairConfig(strength_ppm=strength_ppm)
        m4_backend = D02TargetedM4RepairBackend(
            material=predecessor.prepared.source_materials[repair.TARGET_SOURCE_ORDINAL - 1],
            config=config,
        )
        context = self._execution_context(
            predecessor=predecessor,
            m4_backend=m4_backend,
        )
        first, second = repair_execution.execute_target_m4(context)
        _, records = repair_execution.inspect_target_result_m3(
            context=context,
            first_output=first,
        )
        outcome = repair_execution.evaluate_target_measurement(
            predecessor_report=predecessor.report,
            predecessor=predecessor.prepared,
            replacement_case=context.replacement_case,
            result_m3_records=records,
        )
        return {
            "status": "TARGETED_M4_DIAGNOSTIC_COMPLETE",
            "persisted": False,
            "backend_reexecution_case_ordinals": [repair.TARGET_CASE_ORDINAL],
            "provider_calls": 0,
            "source_m3_calls": 0,
            "m4_calls": 2,
            "result_m3_calls": 3,
            "config_digest": config.digest,
            "implementation_digest": m4_backend.implementation_digest,
            "repair_policy_digest": m4_backend.repair_policy_digest,
            "warp_plan_digest": m4_backend.warp_plan_digest,
            "strength_ppm": strength_ppm,
            "successor_case_id": context.replacement_case["case_id"],
            "measured_signed_delta_ppm": list(outcome.measured_signed_delta_ppm),
            "predecessor_case_26_absolute_delta_ppm": list(
                outcome.predecessor_case_26_absolute_delta_ppm
            ),
            "repeat_consistent": outcome.repeat_consistent,
            "direction_and_margin_passed": outcome.direction_and_margin_passed,
            "predecessor_bound_passed": outcome.predecessor_bound_passed,
            "measurement_gate_passed": outcome.measurement_gate_passed,
            "targeted_gate_passed": outcome.passed,
            "m4_repeat_digest_equal": first.result_sha256 == second.result_sha256,
        }

    def execute(
        self,
        *,
        run_id: str,
        predecessor_idempotency_key_hash: str,
        successor_idempotency_key: str,
        input_stream: IO[bytes],
        output: TextIO,
    ) -> dict[str, object]:
        """Resume or complete the formal successor and one admission transaction."""

        predecessor = self._recover_predecessor(
            run_id=run_id,
            predecessor_idempotency_key_hash=predecessor_idempotency_key_hash,
        )
        policy = repair.build_repair_policy()
        config = TargetedJawRepairConfig()
        m4_backend = D02TargetedM4RepairBackend(
            material=predecessor.prepared.source_materials[repair.TARGET_SOURCE_ORDINAL - 1],
            config=config,
        )
        implementation = repair.build_repair_implementation(
            algorithm_version=m4_backend.algorithm_version,
            implementation_digest=m4_backend.implementation_digest,
            configuration_digest=m4_backend.config_digest,
        )
        case_plan = self._case_plan(
            predecessor=predecessor,
            m4_backend=m4_backend,
        )
        scope = repair.build_repair_scope()
        bindings = SuccessorBindings(
            policy_digest=cast(str, policy["repair_policy_digest"]),
            implementation_digest=cast(str, implementation["repair_implementation_binding_digest"]),
            config_digest=config.digest,
            scope_digest=cast(str, scope["repair_scope_digest"]),
            predecessor_checkpoint_digest=predecessor.checkpoint_payload_digest,
            predecessor_report_digest=cast(str, predecessor.report["report_digest"]),
            successor_case_id=cast(str, case_plan.replacement_case["case_id"]),
            successor_admission_idempotency_key_hash=idempotency_key_hash(
                successor_idempotency_key
            ),
        )
        store = D02TargetedM4SuccessorStore(
            workspace_root=self._workspace_root,
            successor_case_id=bindings.successor_case_id,
        )
        checkpoint = D02TargetedM4SuccessorCheckpoint(
            workspace_root=self._workspace_root,
            bindings=bindings,
        )
        recovered = self._initialize_or_recover(checkpoint=checkpoint, store=store)
        recovered = self._advance_policy(
            checkpoint=checkpoint,
            store=store,
            recovered=recovered,
        )
        recovered = self._ensure_m4_durable(
            checkpoint=checkpoint,
            store=store,
            recovered=recovered,
            predecessor=predecessor,
            m4_backend=m4_backend,
        )
        recovered = self._ensure_result_m3(
            checkpoint=checkpoint,
            store=store,
            recovered=recovered,
            predecessor=predecessor,
            m4_backend=m4_backend,
        )
        records = recovered.result_m3_records
        if recovered.m4_outputs is None or records is None:
            _fail("SUCCESSOR_DURABLE_EVIDENCE_MISSING")
        outcome = repair_execution.evaluate_target_measurement(
            predecessor_report=predecessor.report,
            predecessor=predecessor.prepared,
            replacement_case=case_plan.replacement_case,
            result_m3_records=records,
        )
        if not outcome.passed:
            _fail("TARGETED_MEASUREMENT_GATE_FAILED")
        recovered = self._ensure_review(
            checkpoint=checkpoint,
            store=store,
            recovered=recovered,
            input_stream=input_stream,
            output=output,
        )
        decision = recovered.artifact_decision
        replacement_outputs = recovered.m4_outputs
        if decision is None or replacement_outputs is None:
            _fail("SUCCESSOR_REVIEW_MISSING")
        successor = repair.compose_targeted_m4_successor(
            predecessor=predecessor.prepared,
            predecessor_report=predecessor.report,
            predecessor_checkpoint_payload_digest=predecessor.checkpoint_payload_digest,
            predecessor_artifact_decisions=predecessor.decisions,
            replacement_case_fields=case_plan.replacement_case_fields,
            replacement_m4_outputs=replacement_outputs,
            replacement_result_m3_fields=repair_execution.adapter_fields_from_records(records),
            replacement_artifact_decision=decision,
            repair_policy=policy,
            repair_implementation=implementation,
        )
        runtime_result = orchestrator.finalize_runtime_evidence(
            prepared=successor.prepared,
            artifact_decisions=successor.artifact_decisions,
        )
        self._require_successor_pass(runtime_result.report_row)
        recovered = self._ensure_screening_checkpoint(
            checkpoint=checkpoint,
            store=store,
            recovered=recovered,
            successor=successor,
        )
        availability = _SuccessorResultPersistence(
            predecessor=predecessor.result_store,
            successor=store,
        )
        bundle = build_generic_runtime_admission_bundle(
            runtime_result=runtime_result,
            formal_bundle=successor.prepared.formal_bundle,
            selected_manifest=predecessor.manifest,
            result_persistence=availability,
            configuration=D02QuestionBankConfiguration(created_at=successor.prepared.created_at),
        )
        recovered = self._ensure_admission_ready(
            checkpoint=checkpoint,
            store=store,
            recovered=recovered,
        )
        admitted = _run_async(self._admit(idempotency_key=successor_idempotency_key, bundle=bundle))
        if recovered.stage != "ADMITTED":
            self._advance(
                checkpoint=checkpoint,
                stage="ADMITTED",
                recovered=recovered,
            )
        return {
            "status": "ADMITTED",
            "admission_id": admitted.admission_id,
            "acquisition_run_id": admitted.acquisition_run_id,
            "screening_report_id": admitted.screening_report_id,
            "question_bank_id": admitted.question_bank_id,
            "replayed": admitted.replayed,
            "backend_reexecution_case_ordinals": [repair.TARGET_CASE_ORDINAL],
            "provider_calls": 0,
            "source_m3_calls": 0,
            "m4_calls": 2,
            "result_m3_calls": 3,
            "source_count": 4,
            "asset_count": 52,
            "asset_variant_count": 48,
            "question_pair_count": 16,
            "selected_result_side_count": 32,
            "predecessor_status": "FAILED",
            "successor_status": "PASSED",
            "successor_universe_digest": successor.successor_universe_digest,
            "provenance_envelope_digest": successor.provenance_envelope[
                "provenance_envelope_digest"
            ],
        }

    def _recover_predecessor(
        self,
        *,
        run_id: str,
        predecessor_idempotency_key_hash: str,
    ) -> _Predecessor:
        spec, manifest, candidates = self._load_selection(run_id)
        normalizer = D02CandidateNormalizer(durable_index=self._index)
        materials = [normalizer.recover(candidate) for candidate in candidates]
        availability_binding = runtime_result_binding_digest(
            acquisition_run_id=manifest.acquisition_run_id,
            selected_manifest_digest=manifest.content_digest,
            cohort_spec_digest=spec.content_digest,
            runtime_identity_digest=spec.runtime_identity_digest,
            model_identity_digest=spec.model_identity_digest,
        )
        result_store = D02RuntimeResultStore(
            workspace_root=self._workspace_root,
            availability_binding_digest=availability_binding,
        )
        checkpoint = D02FinalRuntimeCheckpoint(
            workspace_root=self._workspace_root,
            availability_binding_digest=availability_binding,
            acquisition_run_id=manifest.acquisition_run_id,
            selected_manifest_digest=manifest.content_digest,
            admission_idempotency_key_hash=predecessor_idempotency_key_hash,
            result_store=result_store,
        )
        if not checkpoint.exists or result_store.count() != 48:
            _fail("PREDECESSOR_REVIEWED_CHECKPOINT_MISSING")
        recovered = checkpoint.load(materials=materials)
        if recovered.stage != "REVIEWED" or recovered.artifact_decisions is None:
            _fail("PREDECESSOR_REVIEWED_CHECKPOINT_MISSING")
        report_result = orchestrator.finalize_runtime_evidence(
            prepared=recovered.prepared,
            artifact_decisions=recovered.artifact_decisions,
        )
        repair_execution.validate_accurate_failure_report(report_result.report_row)
        return _Predecessor(
            spec=spec,
            manifest=manifest,
            candidates=candidates,
            prepared=recovered.prepared,
            decisions=recovered.artifact_decisions,
            report=report_result.report_row,
            checkpoint_payload_digest=recovered.checkpoint_payload_digest,
            result_store=result_store,
        )

    def _load_selection(
        self, run_id: str
    ) -> tuple[
        D02CohortSpec,
        D02SelectedSourceManifest,
        tuple[
            D02SourceCandidate,
            D02SourceCandidate,
            D02SourceCandidate,
            D02SourceCandidate,
        ],
    ]:
        with self._sessions() as session:
            _require_database_head(session)
            run = session.get(D02SourceAcquisitionRun, run_id)
            manifest = session.scalar(
                select(D02SelectedSourceManifest).where(
                    D02SelectedSourceManifest.acquisition_run_id == run_id
                )
            )
            if (
                run is None
                or manifest is None
                or run.run_state not in {"MANIFEST_FINALIZED", "ADMITTED"}
                or manifest.manifest_state != "FINALIZED"
            ):
                _fail("FINAL_MANIFEST_NOT_READY")
            spec = session.get(D02CohortSpec, manifest.cohort_spec_id)
            if spec is None:
                _fail("FINAL_MANIFEST_NOT_READY")
            values = [
                session.get(D02SourceCandidate, value) for value in manifest.ordered_candidate_ids
            ]
            if len(values) != 4 or any(value is None for value in values):
                _fail("FINAL_MANIFEST_NOT_READY")
            return (
                spec,
                manifest,
                cast(
                    tuple[
                        D02SourceCandidate,
                        D02SourceCandidate,
                        D02SourceCandidate,
                        D02SourceCandidate,
                    ],
                    tuple(values),
                ),
            )

    def _case_plan(
        self,
        *,
        predecessor: _Predecessor,
        m4_backend: D02TargetedM4RepairBackend,
    ) -> _CaseOnlyContext:
        """Build public case identity without loading private M3 runtime artifacts."""
        packet = predecessor.prepared.formal_bundle.runtime_packets[
            repair.TARGET_SOURCE_ORDINAL - 1
        ]
        entry = packet.get("source_manifest_entry")
        if not isinstance(entry, Mapping):
            _fail("TARGETED_SOURCE_BINDING_INVALID")
        fields = dict(
            m4_backend.case_fields(
                source_packet=packet,
                source_entry=entry,
                case_ordinal=repair.TARGET_CASE_ORDINAL,
                dimension_key=cast(str, repair.TARGET_SELECTOR["dimension_key"]),
                direction=cast(str, repair.TARGET_SELECTOR["direction"]),
                magnitude_ppm=cast(int, repair.TARGET_SELECTOR["magnitude_ppm"]),
            )
        )
        case = repair.build_targeted_replacement_case(
            predecessor=predecessor.prepared,
            replacement_case_fields=fields,
        )
        recipe = repair_execution.build_targeted_runtime_recipe(
            predecessor_recipe=predecessor.prepared.recipe,
            algorithm_version=m4_backend.algorithm_version,
        )
        return _CaseOnlyContext(
            replacement_case_fields=fields,
            replacement_case=case,
            recipe=recipe,
        )

    def _execution_context(
        self,
        *,
        predecessor: _Predecessor,
        m4_backend: D02TargetedM4RepairBackend,
    ) -> repair_execution.TargetedM4ExecutionContext:
        locators = load_runtime_locators(workspace_root=self._workspace_root)
        m3_backend = compose_accepted_m3_backend(
            locators=locators,
            staging_root=self._index.objects_parent.parent / "runtime-staging",
        )
        return repair_execution.prepare_targeted_execution(
            predecessor=predecessor.prepared,
            m3_backend=m3_backend,
            m4_backend=m4_backend,
        )

    def _initialize_or_recover(
        self,
        *,
        checkpoint: D02TargetedM4SuccessorCheckpoint,
        store: D02TargetedM4SuccessorStore,
    ) -> RecoveredTargetedM4Successor:
        if checkpoint.exists:
            return checkpoint.load(store=store)
        if store.exists:
            _fail("SUCCESSOR_STORE_WITHOUT_CHECKPOINT")
        checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
        return checkpoint.load(store=store)

    def _advance_policy(
        self,
        *,
        checkpoint: D02TargetedM4SuccessorCheckpoint,
        store: D02TargetedM4SuccessorStore,
        recovered: RecoveredTargetedM4Successor,
    ) -> RecoveredTargetedM4Successor:
        if recovered.stage == "PREDECESSOR_REVIEWED_FAILED":
            checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
            return checkpoint.load(store=store)
        return recovered

    def _ensure_m4_durable(
        self,
        *,
        checkpoint: D02TargetedM4SuccessorCheckpoint,
        store: D02TargetedM4SuccessorStore,
        recovered: RecoveredTargetedM4Successor,
        predecessor: _Predecessor,
        m4_backend: D02TargetedM4RepairBackend,
    ) -> RecoveredTargetedM4Successor:
        if _stage_at_least(recovered.stage, "TARGET_M4_DURABLE"):
            return recovered
        outputs = recovered.m4_outputs
        if outputs is None:
            context = self._execution_context(
                predecessor=predecessor,
                m4_backend=m4_backend,
            )
            outputs = repair_execution.execute_target_m4(context)
            store.persist(*outputs)
        checkpoint.advance(stage="TARGET_M4_DURABLE", m4_outputs=outputs)
        return checkpoint.load(store=store)

    def _ensure_result_m3(
        self,
        *,
        checkpoint: D02TargetedM4SuccessorCheckpoint,
        store: D02TargetedM4SuccessorStore,
        recovered: RecoveredTargetedM4Successor,
        predecessor: _Predecessor,
        m4_backend: D02TargetedM4RepairBackend,
    ) -> RecoveredTargetedM4Successor:
        if _stage_at_least(recovered.stage, "TARGET_RESULT_M3_COMPLETE"):
            return recovered
        if recovered.m4_outputs is None:
            _fail("SUCCESSOR_DURABLE_EVIDENCE_MISSING")
        context = self._execution_context(
            predecessor=predecessor,
            m4_backend=m4_backend,
        )
        _, records = repair_execution.inspect_target_result_m3(
            context=context,
            first_output=recovered.m4_outputs[0],
        )
        checkpoint.advance(
            stage="TARGET_RESULT_M3_COMPLETE",
            m4_outputs=recovered.m4_outputs,
            result_m3_records=records,
        )
        return checkpoint.load(store=store)

    def _ensure_review(
        self,
        *,
        checkpoint: D02TargetedM4SuccessorCheckpoint,
        store: D02TargetedM4SuccessorStore,
        recovered: RecoveredTargetedM4Successor,
        input_stream: IO[bytes],
        output: TextIO,
    ) -> RecoveredTargetedM4Successor:
        if recovered.m4_outputs is None or len(recovered.result_m3_records) != 3:
            _fail("SUCCESSOR_DURABLE_EVIDENCE_MISSING")
        if recovered.stage == "TARGET_RESULT_M3_COMPLETE":
            checkpoint.advance(
                stage="TARGET_REVIEW_REQUIRED",
                m4_outputs=recovered.m4_outputs,
                result_m3_records=recovered.result_m3_records,
            )
            recovered = checkpoint.load(store=store)
        if recovered.stage == "TARGET_REVIEW_REQUIRED":
            replacement_outputs = recovered.m4_outputs
            if replacement_outputs is None:
                _fail("SUCCESSOR_DURABLE_EVIDENCE_MISSING")
            first = replacement_outputs[0]
            _emit(
                output,
                {
                    "status": "TARGETED_ARTIFACT_REVIEW_REQUIRED",
                    "decision_count": 1,
                    "case_id": first.case_id,
                    "result_sha256": first.result_sha256,
                    "decision_sequence": repair.TARGET_CASE_ORDINAL,
                    "manual_review_policy_digest": MANUAL_REVIEW_POLICY_DIGEST,
                },
            )
            command = _read_json_line(
                input_stream,
                code="TARGETED_ARTIFACT_REVIEW_COMMAND_INVALID",
            )
            decision = _targeted_artifact_decision(command, output=first)
            checkpoint.advance(
                stage="SUCCESSOR_REVIEWED",
                m4_outputs=replacement_outputs,
                result_m3_records=recovered.result_m3_records,
                artifact_decision=decision,
            )
            recovered = checkpoint.load(store=store)
        return recovered

    def _ensure_screening_checkpoint(
        self,
        *,
        checkpoint: D02TargetedM4SuccessorCheckpoint,
        store: D02TargetedM4SuccessorStore,
        recovered: RecoveredTargetedM4Successor,
        successor: repair.TargetedM4RepairSuccessor,
    ) -> RecoveredTargetedM4Successor:
        if recovered.artifact_decision is None:
            _fail("SUCCESSOR_REVIEW_MISSING")
        if _stage_at_least(recovered.stage, "SUCCESSOR_SCREENING_REPLAYED"):
            if repair_execution.normalize_public_tree(
                recovered.successor_universe
            ) != repair_execution.normalize_public_tree(
                successor.successor_universe
            ) or repair_execution.normalize_public_tree(
                recovered.provenance_envelope
            ) != repair_execution.normalize_public_tree(successor.provenance_envelope):
                _fail("SUCCESSOR_SCREENING_CHECKPOINT_MISMATCH")
            return recovered
        checkpoint.advance(
            stage="SUCCESSOR_SCREENING_REPLAYED",
            m4_outputs=cast(tuple[M4ExecutionOutput, M4ExecutionOutput], recovered.m4_outputs),
            result_m3_records=cast(Sequence[Mapping[str, object]], recovered.result_m3_records),
            artifact_decision=recovered.artifact_decision,
            successor_universe=successor.successor_universe,
            provenance_envelope=successor.provenance_envelope,
        )
        return checkpoint.load(store=store)

    def _ensure_admission_ready(
        self,
        *,
        checkpoint: D02TargetedM4SuccessorCheckpoint,
        store: D02TargetedM4SuccessorStore,
        recovered: RecoveredTargetedM4Successor,
    ) -> RecoveredTargetedM4Successor:
        if _stage_at_least(recovered.stage, "ADMISSION_READY"):
            return recovered
        self._advance(checkpoint=checkpoint, stage="ADMISSION_READY", recovered=recovered)
        return checkpoint.load(store=store)

    def _advance(
        self,
        *,
        checkpoint: D02TargetedM4SuccessorCheckpoint,
        stage: str,
        recovered: RecoveredTargetedM4Successor,
    ) -> None:
        if (
            recovered.m4_outputs is None
            or recovered.result_m3_records is None
            or recovered.artifact_decision is None
            or recovered.successor_universe is None
            or recovered.provenance_envelope is None
        ):
            _fail("SUCCESSOR_CHECKPOINT_PAYLOAD_INCOMPLETE")
        checkpoint.advance(
            stage=stage,
            m4_outputs=recovered.m4_outputs,
            result_m3_records=recovered.result_m3_records,
            artifact_decision=recovered.artifact_decision,
            successor_universe=recovered.successor_universe,
            provenance_envelope=recovered.provenance_envelope,
        )

    def _require_successor_pass(self, report: Mapping[str, object]) -> None:
        if (
            report.get("status") != "PASSED"
            or report.get("eligible_dimension_keys") != ["jaw_width", "eye_spacing"]
            or report.get("selected_dimension_keys") != ["jaw_width", "eye_spacing"]
            or report.get("selected_pair_count") != 16
            or report.get("selected_result_side_count") != 32
        ):
            _fail("SUCCESSOR_SCREENING_FAILED")

    async def _admit(
        self,
        *,
        idempotency_key: str,
        bundle: GenericAdmissionBundle,
    ) -> GenericAdmissionResult:
        engine = create_async_engine(self._database_url, pool_pre_ping=True)
        try:
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            return await D02GenericAdmissionCoordinator(session_factory=sessions).admit(
                idempotency_key=idempotency_key,
                bundle=bundle,
            )
        finally:
            await engine.dispose()


@dataclass(frozen=True, slots=True, repr=False)
class _CaseOnlyContext:
    replacement_case_fields: Mapping[str, object]
    replacement_case: Mapping[str, object]
    recipe: object


def _targeted_artifact_decision(
    command: Mapping[str, object],
    *,
    output: M4ExecutionOutput,
) -> PrincipalArtifactDecision:
    if (
        set(command) != {"schema_version", "decision"}
        or command.get("schema_version") != TARGETED_ARTIFACT_REVIEW_COMMAND_SCHEMA
        or not isinstance(command.get("decision"), Mapping)
    ):
        _fail("TARGETED_ARTIFACT_REVIEW_COMMAND_INVALID")
    raw = cast(Mapping[str, object], command["decision"])
    expected = {
        "case_id",
        "result_sha256",
        "decision_sequence",
        "manual_review_version",
        "background_seam",
        "disconnected_contour",
        "duplicated_feature",
        "warp_tear",
    }
    boolean_keys = {
        "background_seam",
        "disconnected_contour",
        "duplicated_feature",
        "warp_tear",
    }
    version = raw.get("manual_review_version")
    if (
        set(raw) != expected
        or raw.get("case_id") != output.case_id
        or raw.get("result_sha256") != output.result_sha256
        or raw.get("decision_sequence") != repair.TARGET_CASE_ORDINAL
        or not isinstance(version, str)
        or re.fullmatch(r"[A-Za-z0-9._-]{1,64}", version) is None
        or any(type(raw.get(key)) is not bool for key in boolean_keys)
    ):
        _fail("TARGETED_ARTIFACT_REVIEW_COMMAND_INVALID")
    return PrincipalArtifactDecision.seal(
        case_id=output.case_id,
        result_sha256=output.result_sha256,
        decision_sequence=repair.TARGET_CASE_ORDINAL,
        manual_review_version=version,
        manual_review_policy_digest=MANUAL_REVIEW_POLICY_DIGEST,
        background_seam=cast(bool, raw["background_seam"]),
        disconnected_contour=cast(bool, raw["disconnected_contour"]),
        duplicated_feature=cast(bool, raw["duplicated_feature"]),
        warp_tear=cast(bool, raw["warp_tear"]),
    )


class _DuplicateJsonKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey()
        result[key] = value
    return result


def _read_json_line(stream: IO[bytes], *, code: str) -> Mapping[str, object]:
    if stream.isatty():
        _fail("TTY_INPUT_FORBIDDEN")
    line = stream.readline(_MAX_REVIEW_COMMAND_BYTES + 1)
    if not line or len(line) > _MAX_REVIEW_COMMAND_BYTES or not line.endswith(b"\n"):
        _fail(code)
    try:
        value = json.loads(
            line[:-1].decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey) as error:
        raise D02TargetedM4RepairOperatorError(code) from error
    if not isinstance(value, Mapping):
        _fail(code)
    return cast(Mapping[str, object], value)


def _stage_at_least(stage: str, expected: str) -> bool:
    if stage not in _FORMAL_STAGES or expected not in _FORMAL_STAGES:
        _fail("SUCCESSOR_STAGE_INVALID")
    return _FORMAL_STAGES.index(stage) >= _FORMAL_STAGES.index(expected)


def _run_async[T](value: Coroutine[Any, Any, T]) -> T:
    """Use psycopg-compatible selector I/O on Windows only."""

    if os.name == "nt":
        return asyncio.run(value, loop_factory=asyncio.SelectorEventLoop)
    return asyncio.run(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal D02 targeted M4 repair operator")
    parser.add_argument("--database-env", default="D02_DATABASE_URL")
    parser.add_argument("--environment", required=True, choices=("development", "test", "ci"))
    parser.add_argument("--mode", required=True, choices=("diagnostic", "formal"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--predecessor-idempotency-key-hash", required=True)
    parser.add_argument("--successor-idempotency-key")
    parser.add_argument("--strength-ppm", type=int)
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    input_stream: IO[bytes] | None = None,
    output: TextIO | None = None,
    error_output: TextIO | None = None,
) -> int:
    stream = output or sys.stdout
    errors = error_output or sys.stderr
    engine = None
    try:
        args = build_parser().parse_args(argv)
        workspace_root = Path.cwd()
        _validate_workspace_authority(
            workspace_root=workspace_root,
            environment=cast(str, args.environment),
        )
        database_url = _database_url(cast(str, args.database_env))
        engine = create_engine(database_url, pool_pre_ping=True)
        run_id = cast(str, args.run_id)
        operator = D02TargetedM4RepairOperator(
            sessions=sessionmaker(engine, expire_on_commit=False),
            database_url=database_url,
            workspace_root=workspace_root,
            durable_index=D02LocalDurableIndex(workspace_root=workspace_root),
        )
        with _run_advisory_lock(engine, run_id):
            if args.mode == "diagnostic":
                if args.strength_ppm is None or args.successor_idempotency_key is not None:
                    _fail("TARGETED_DIAGNOSTIC_ARGUMENTS_INVALID")
                result = operator.diagnose(
                    run_id=run_id,
                    predecessor_idempotency_key_hash=cast(
                        str, args.predecessor_idempotency_key_hash
                    ),
                    strength_ppm=cast(int, args.strength_ppm),
                )
            else:
                if args.strength_ppm is not None or not isinstance(
                    args.successor_idempotency_key, str
                ):
                    _fail("TARGETED_FORMAL_ARGUMENTS_INVALID")
                result = operator.execute(
                    run_id=run_id,
                    predecessor_idempotency_key_hash=cast(
                        str, args.predecessor_idempotency_key_hash
                    ),
                    successor_idempotency_key=args.successor_idempotency_key,
                    input_stream=input_stream or sys.stdin.buffer,
                    output=stream,
                )
        _emit(stream, result)
        return 0
    except (
        D02TargetedM4RepairOperatorError,
        repair_execution.D02TargetedM4RepairExecutionError,
        D02TargetedM4SuccessorCheckpointError,
        D02FinalRuntimeCheckpointError,
        orchestrator.D02FinalOrchestratorError,
        repair.D02TargetedM4RepairError,
        D02GenericRuntimeAdmissionError,
        D02OperatorError,
        D02RuntimeCompositionError,
        D02RuntimeResultStoreError,
        D02SourceAcquisitionError,
        GenericAdmissionCoordinatorError,
        PrivateVisionBackendError,
        TargetedM4RepairError,
        RuntimeForwardError,
    ) as error:
        _emit(errors, {"status": "FAILED", "code": getattr(error, "code", "REPAIR_FAILED")})
        return 2
    except SQLAlchemyError:
        _emit(errors, {"status": "FAILED", "code": "DATABASE_OPERATION_FAILED"})
        return 2
    except Exception:
        _emit(errors, {"status": "FAILED", "code": "INTERNAL_OPERATOR_FAILURE"})
        return 2
    finally:
        if engine is not None:
            engine.dispose()


def _fail(code: str) -> NoReturn:
    raise D02TargetedM4RepairOperatorError(code)


if __name__ == "__main__":
    raise SystemExit(run())
