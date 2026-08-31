"""Long-lived non-HTTP operator for the post-Manifest D02 runtime Gate."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Final, NoReturn, TextIO, cast

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

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
from mirror_api.demo_d02_final_orchestrator import (
    D02CaseM4Backend,
    D02FinalOrchestratorError,
    assemble_formal_runtime,
    build_execution_authority,
    finalize_runtime_evidence,
    load_measurement_execution_config,
    prepare_runtime_evidence,
)
from mirror_api.demo_d02_final_runtime_checkpoint import (
    D02FinalRuntimeCheckpoint,
    D02FinalRuntimeCheckpointError,
)
from mirror_api.demo_d02_formal_source_builder import FormalSourceManualReview
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
from mirror_api.demo_d02_r2_runtime_forward import SourceMaterial
from mirror_api.demo_d02_runtime_composition import (
    D02RuntimeCompositionError,
    compose_accepted_m3_backend,
    compose_accepted_m4_backend,
    load_runtime_locators,
)
from mirror_api.demo_d02_runtime_result_store import (
    D02RuntimeResultStore,
    D02RuntimeResultStoreError,
    runtime_result_binding_digest,
)
from mirror_api.demo_d02_screening_adapters import PrincipalArtifactDecision
from mirror_api.demo_d02_source_acquisition import D02SourceAcquisitionError
from mirror_api.demo_idempotency import idempotency_key_hash
from mirror_api.demo_models import (
    D02CohortSpec,
    D02SelectedSourceManifest,
    D02SourceAcquisitionRun,
    D02SourceCandidate,
)

SOURCE_REVIEW_COMMAND_SCHEMA: Final = "mirror.private/D02FormalSourceReviewCommand/v1"
ARTIFACT_REVIEW_COMMAND_SCHEMA: Final = "mirror.private/D02ArtifactReviewCommand/v1"
_MAX_REVIEW_COMMAND_BYTES: Final = 1_000_000


class _DuplicateJsonKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey()
        value[key] = item
    return value


class D02FinalRuntimeOperatorError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class D02FinalRuntimeOperator:
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

    def execute(
        self,
        *,
        run_id: str,
        created_at: str,
        idempotency_key: str,
        input_stream: IO[bytes],
        output: TextIO,
    ) -> dict[str, object]:
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
            admission_idempotency_key_hash=idempotency_key_hash(idempotency_key),
            result_store=result_store,
        )
        if not checkpoint.exists and result_store.count() != 0:
            _fail("FINAL_RUNTIME_PARTIAL_WITHOUT_CHECKPOINT")
        decisions: Mapping[str, PrincipalArtifactDecision] | None = None
        if checkpoint.exists:
            recovered = checkpoint.load(materials=materials)
            prepared = recovered.prepared
            decisions = recovered.artifact_decisions
            if prepared.created_at != created_at:
                _fail("FINAL_RUNTIME_CREATED_AT_COLLISION")
            _emit(
                output,
                {
                    "status": "FINAL_RUNTIME_RECOVERED",
                    "stage": recovered.stage,
                    "backend_reexecution": False,
                    "result_count": 48,
                },
            )
        else:
            source_command = _read_json_line(input_stream, code="SOURCE_REVIEW_COMMAND_INVALID")
            source_reviews = _source_reviews(
                source_command,
                manifest=manifest,
                candidates=candidates,
                normalized_sha256=[item.sha256 for item in materials],
            )
            locators = load_runtime_locators(workspace_root=self._workspace_root)
            m3_backend = compose_accepted_m3_backend(
                locators=locators,
                staging_root=self._index.objects_parent.parent / "runtime-staging",
            )

            def m4_factory(
                source_materials: tuple[
                    SourceMaterial,
                    SourceMaterial,
                    SourceMaterial,
                    SourceMaterial,
                ],
                landmarks: dict[str, tuple[tuple[float, float, float], ...]],
            ) -> D02CaseM4Backend:
                return cast(
                    D02CaseM4Backend,
                    compose_accepted_m4_backend(
                        locators=locators,
                        materials=source_materials,
                        landmarks_by_source=landmarks,
                    ),
                )

            assembly = assemble_formal_runtime(
                spec=spec,
                manifest=manifest,
                candidates=candidates,
                materials=materials,
                formal_reviews=source_reviews,
                m3_backend=m3_backend,
                m4_backend_factory=m4_factory,
            )
            execution_authority = build_execution_authority(
                source_manifest_digest=assembly.bundle.runtime_source_manifest_digest,
                measurement_execution_config=load_measurement_execution_config(
                    workspace_root=self._workspace_root
                ),
                manual_review_policy_digest=MANUAL_REVIEW_POLICY_DIGEST,
                recipe=assembly.recipe,
                model_identity=assembly.model_identity,
            )
            prepared = prepare_runtime_evidence(
                assembly=assembly,
                created_at=created_at,
                execution_authority=execution_authority,
                result_persistence=result_store,
            )
            checkpoint.save_prepared(prepared)
        if decisions is None:
            _emit(
                output,
                {
                    "status": "ARTIFACT_REVIEW_REQUIRED",
                    "decision_count": 48,
                    "manual_review_policy_digest": MANUAL_REVIEW_POLICY_DIGEST,
                    "subjects": [
                        {
                            "case_id": item.case_id,
                            "result_sha256": item.result_sha256,
                            "decision_sequence": item.decision_sequence,
                        }
                        for item in prepared.review_subjects
                    ],
                },
            )
            artifact_command = _read_json_line(input_stream, code="ARTIFACT_REVIEW_COMMAND_INVALID")
            decisions = _artifact_decisions(artifact_command, prepared.review_subjects)
            checkpoint.save_reviewed(prepared=prepared, decisions=decisions)
        runtime_result = finalize_runtime_evidence(
            prepared=prepared,
            artifact_decisions=decisions,
        )
        bundle = build_generic_runtime_admission_bundle(
            runtime_result=runtime_result,
            formal_bundle=prepared.formal_bundle,
            selected_manifest=manifest,
            result_persistence=result_store,
            configuration=D02QuestionBankConfiguration(created_at=created_at),
        )
        admitted = asyncio.run(self._admit(idempotency_key=idempotency_key, bundle=bundle))
        return {
            "status": "ADMITTED",
            "admission_id": admitted.admission_id,
            "acquisition_run_id": admitted.acquisition_run_id,
            "screening_report_id": admitted.screening_report_id,
            "question_bank_id": admitted.question_bank_id,
            "replayed": admitted.replayed,
            "source_count": 4,
            "asset_count": 52,
            "asset_variant_count": 48,
            "question_pair_count": 16,
        }

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
                or run.run_state != "MANIFEST_FINALIZED"
                or manifest.manifest_state != "FINALIZED"
            ):
                _fail("FINAL_MANIFEST_NOT_READY")
            spec = session.get(D02CohortSpec, manifest.cohort_spec_id)
            if spec is None:
                _fail("FINAL_MANIFEST_NOT_READY")
            candidate_values: list[D02SourceCandidate] = []
            for candidate_id in manifest.ordered_candidate_ids:
                candidate = session.get(D02SourceCandidate, candidate_id)
                if candidate is None:
                    _fail("FINAL_MANIFEST_NOT_READY")
                candidate_values.append(candidate)
            if len(candidate_values) != 4:
                _fail("FINAL_MANIFEST_NOT_READY")
            candidates = cast(
                tuple[
                    D02SourceCandidate,
                    D02SourceCandidate,
                    D02SourceCandidate,
                    D02SourceCandidate,
                ],
                tuple(candidate_values),
            )
            return (
                spec,
                manifest,
                candidates,
            )

    async def _admit(
        self, *, idempotency_key: str, bundle: GenericAdmissionBundle
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


def _source_reviews(
    command: Mapping[str, object],
    *,
    manifest: D02SelectedSourceManifest,
    candidates: Sequence[D02SourceCandidate],
    normalized_sha256: Sequence[str],
) -> tuple[
    FormalSourceManualReview,
    FormalSourceManualReview,
    FormalSourceManualReview,
    FormalSourceManualReview,
]:
    if (
        set(command) != {"schema_version", "reviews"}
        or command.get("schema_version") != SOURCE_REVIEW_COMMAND_SCHEMA
    ):
        _fail("SOURCE_REVIEW_COMMAND_INVALID")
    values = command.get("reviews")
    if not isinstance(values, list) or len(values) != 4:
        _fail("SOURCE_REVIEW_COMMAND_INVALID")
    reviews: list[FormalSourceManualReview] = []
    expected_keys = {
        "position",
        "candidate_id",
        "normalized_sha256",
        "synthetic_adult_attested",
        "suspected_minor",
        "real_person_reference_used",
        "celebrity_imitation_suspected",
        "style_context_match",
        "anti_homogenization_passed",
    }
    for position, (raw, candidate, sha256) in enumerate(
        zip(values, candidates, normalized_sha256, strict=True), start=1
    ):
        if not isinstance(raw, Mapping) or set(raw) != expected_keys:
            _fail("SOURCE_REVIEW_COMMAND_INVALID")
        boolean_keys = expected_keys - {"position", "candidate_id", "normalized_sha256"}
        if (
            raw.get("position") != position
            or raw.get("candidate_id") != candidate.id
            or raw.get("normalized_sha256") != sha256
            or any(type(raw.get(key)) is not bool for key in boolean_keys)
        ):
            _fail("SOURCE_REVIEW_COMMAND_INVALID")
        reviews.append(
            FormalSourceManualReview(
                manifest_id=manifest.id,
                manifest_content_digest=manifest.content_digest,
                position=position,
                candidate_id=candidate.id,
                normalized_sha256=sha256,
                reviewer_role="D02_SUBSYSTEM_PRINCIPAL",
                synthetic_adult_attested=cast(bool, raw["synthetic_adult_attested"]),
                suspected_minor=cast(bool, raw["suspected_minor"]),
                real_person_reference_used=cast(bool, raw["real_person_reference_used"]),
                celebrity_imitation_suspected=cast(bool, raw["celebrity_imitation_suspected"]),
                style_context_match=cast(bool, raw["style_context_match"]),
                anti_homogenization_passed=cast(bool, raw["anti_homogenization_passed"]),
            )
        )
    return cast(
        tuple[
            FormalSourceManualReview,
            FormalSourceManualReview,
            FormalSourceManualReview,
            FormalSourceManualReview,
        ],
        tuple(reviews),
    )


def _artifact_decisions(
    command: Mapping[str, object], subjects: Sequence[object]
) -> dict[str, PrincipalArtifactDecision]:
    from mirror_api.demo_d02_final_orchestrator import RuntimeReviewSubject

    if (
        set(command) != {"schema_version", "decisions"}
        or command.get("schema_version") != ARTIFACT_REVIEW_COMMAND_SCHEMA
    ):
        _fail("ARTIFACT_REVIEW_COMMAND_INVALID")
    values = command.get("decisions")
    typed_subjects = cast(Sequence[RuntimeReviewSubject], subjects)
    if not isinstance(values, list) or len(values) != 48 or len(typed_subjects) != 48:
        _fail("ARTIFACT_REVIEW_COMMAND_INVALID")
    expected_keys = {
        "case_id",
        "result_sha256",
        "decision_sequence",
        "manual_review_version",
        "background_seam",
        "disconnected_contour",
        "duplicated_feature",
        "warp_tear",
    }
    result: dict[str, PrincipalArtifactDecision] = {}
    for raw, subject in zip(values, typed_subjects, strict=True):
        if not isinstance(raw, Mapping) or set(raw) != expected_keys:
            _fail("ARTIFACT_REVIEW_COMMAND_INVALID")
        boolean_keys = expected_keys - {
            "case_id",
            "result_sha256",
            "decision_sequence",
            "manual_review_version",
        }
        if (
            raw.get("case_id") != subject.case_id
            or raw.get("result_sha256") != subject.result_sha256
            or raw.get("decision_sequence") != subject.decision_sequence
            or any(type(raw.get(key)) is not bool for key in boolean_keys)
            or not isinstance(raw.get("manual_review_version"), str)
            or re.fullmatch(r"[A-Za-z0-9._-]{1,64}", cast(str, raw["manual_review_version"]))
            is None
        ):
            _fail("ARTIFACT_REVIEW_COMMAND_INVALID")
        decision = PrincipalArtifactDecision.seal(
            case_id=subject.case_id,
            result_sha256=subject.result_sha256,
            decision_sequence=subject.decision_sequence,
            manual_review_version=cast(str, raw["manual_review_version"]),
            manual_review_policy_digest=MANUAL_REVIEW_POLICY_DIGEST,
            background_seam=cast(bool, raw["background_seam"]),
            disconnected_contour=cast(bool, raw["disconnected_contour"]),
            duplicated_feature=cast(bool, raw["duplicated_feature"]),
            warp_tear=cast(bool, raw["warp_tear"]),
        )
        result[subject.case_id] = decision
    return result


def _read_json_line(stream: IO[bytes], *, code: str) -> Mapping[str, object]:
    if stream.isatty():
        _fail("TTY_INPUT_FORBIDDEN")
    line = stream.readline(_MAX_REVIEW_COMMAND_BYTES + 1)
    if not line or len(line) > _MAX_REVIEW_COMMAND_BYTES or not line.endswith(b"\n"):
        _fail(code)
    try:
        value = json.loads(line[:-1].decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey) as error:
        raise D02FinalRuntimeOperatorError(code) from error
    if not isinstance(value, Mapping):
        _fail(code)
    return cast(Mapping[str, object], value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal D02 final runtime operator")
    parser.add_argument("--database-env", default="D02_DATABASE_URL")
    parser.add_argument("--environment", required=True, choices=("development", "test", "ci"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--idempotency-key", required=True)
    return parser


@contextmanager
def _run_advisory_lock(engine: Engine, run_id: str) -> Iterator[None]:
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        _fail("FINAL_RUNTIME_RUN_ID_INVALID")
    lock_key = int.from_bytes(
        hashlib.sha256(b"mirror.demo/D02FinalRuntimeLock/v1\n" + run_id.encode("ascii")).digest()[
            :8
        ],
        byteorder="big",
        signed=True,
    )
    connection = engine.connect()
    acquired = False
    try:
        acquired = (
            connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": lock_key}
            )
            is True
        )
        connection.commit()
        if not acquired:
            _fail("FINAL_RUNTIME_ALREADY_ACTIVE")
        yield
    finally:
        if acquired:
            try:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": lock_key}
                )
                connection.commit()
            except SQLAlchemyError:
                connection.rollback()
        connection.close()


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
        with _run_advisory_lock(engine, run_id):
            result = D02FinalRuntimeOperator(
                sessions=sessionmaker(engine, expire_on_commit=False),
                database_url=database_url,
                workspace_root=workspace_root,
                durable_index=D02LocalDurableIndex(workspace_root=workspace_root),
            ).execute(
                run_id=run_id,
                created_at=cast(str, args.created_at),
                idempotency_key=cast(str, args.idempotency_key),
                input_stream=input_stream or sys.stdin.buffer,
                output=stream,
            )
        _emit(stream, result)
        return 0
    except (
        D02FinalRuntimeOperatorError,
        D02FinalRuntimeCheckpointError,
        D02FinalOrchestratorError,
        D02GenericRuntimeAdmissionError,
        D02OperatorError,
        D02RuntimeCompositionError,
        D02RuntimeResultStoreError,
        D02SourceAcquisitionError,
        GenericAdmissionCoordinatorError,
        PrivateVisionBackendError,
    ) as error:
        _emit(errors, {"status": "FAILED", "code": getattr(error, "code", "RUNTIME_FAILED")})
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
    raise D02FinalRuntimeOperatorError(code)


if __name__ == "__main__":
    raise SystemExit(run())
