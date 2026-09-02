from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
import test_demo_d02_formal_source_builder as formal_test
from test_demo_d02_formal_source_builder import (
    _accepted_review,
    _accepted_selection,
    _runner,
)
from test_demo_d02_generic_runtime_admission import _runtime_result
from test_demo_d02_generic_runtime_bridge import _generic_runtime_packets
from test_demo_d02_r2_runtime_forward import _Adapters

from mirror_api import demo_d02_final_orchestrator as orchestrator
from mirror_api import demo_d02_private_vision_backend as private_backend
from mirror_api import demo_d02_r2_authority as r2
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_r2_screening_execution as screening_execution
from mirror_api.demo_d02_formal_source_builder import FormalSourceRuntimeBundle
from mirror_api.demo_d02_private_vision_backend import WindowsFaceLandmarkerOfflineM3Backend
from mirror_api.demo_d02_screening_adapters import PrincipalArtifactDecision

_SOURCE_M3_FIELDS = {
    "execution_receipt_digest",
    "vision_model_manifest_digest",
    "runtime_manifest_digest",
    "topology_digest",
    "canonical_output_digest",
    "landmark_digest",
    "measurement_observation",
    "measurement_observation_digest",
    "face_count",
    "landmark_count",
    "coordinates_finite",
    "coordinates_in_bounds",
    "repeat_gate_passed",
}
_RESULT_M3_FIELDS = (_SOURCE_M3_FIELDS - {"runtime_manifest_digest"}) | {"observation_state"}
_M4_FIELDS = {
    "case_id",
    "replay_index",
    "source_output_id",
    "result_output_id",
    "result_sha256",
    "result_byte_size",
    "result_mime_type",
    "result_width",
    "result_height",
    "changed_pixel_count",
    "execution_receipt_digest",
    "execution_succeeded",
}


@pytest.fixture(autouse=True)
def _synthetic_diagnostic_grammar(monkeypatch: pytest.MonkeyPatch) -> None:
    digests = tuple(
        hashlib.sha256(
            private_backend._ABSL_DIAGNOSTIC_PREFIX_RE.sub(b"<ABSL> ", line, count=1)
        ).hexdigest()
        for line in formal_test._m3_stderr().splitlines()
    )
    monkeypatch.setattr(private_backend, "_EXPECTED_DIAGNOSTIC_LINE_DIGESTS", digests)


class _AssemblyOnlyM4:
    execution_runtime_set_digest = runtime.build_default_runtime_recipe().runtime_manifest_digest
    algorithm_version = runtime.build_default_runtime_recipe().m4_algorithm_version
    network_policy = runtime.build_default_runtime_recipe().network_policy

    def case_fields(self, **_: object) -> dict[str, object]:
        raise AssertionError("M4 case execution is not part of formal source assembly")

    def transform(self, **_: object) -> runtime.BackendM4Result:
        raise AssertionError("M4 execution is not part of formal source assembly")


def _measurement_config() -> dict[str, object]:
    root = Path(__file__).resolve().parents[3]
    document = json.loads(
        (root / "docs/research/P3_P7_D02_MEASUREMENT_QUALITY_AUTHORITY_MANIFEST.json").read_text(
            encoding="utf-8"
        )
    )
    return cast(dict[str, object], document["measurement_execution_config"])


def test_execution_authority_replays_tracked_measurement_configuration() -> None:
    workspace_root = Path(__file__).resolve().parents[3]
    assert (
        orchestrator.load_measurement_execution_config(workspace_root=workspace_root)
        == _measurement_config()
    )
    authority = orchestrator.build_execution_authority(
        source_manifest_digest="a" * 64,
        measurement_execution_config=_measurement_config(),
        manual_review_policy_digest="b" * 64,
    )
    assert authority["schema_version"] == r2.R2_SCHEMA_POLICY_SCHEMA
    assert (
        authority["runtime_manifest_digest"]
        == runtime.build_default_runtime_recipe().runtime_manifest_digest
    )
    assert r2._r2_execution_authority(authority) == authority


def test_formal_runtime_assembly_executes_source_m3_once(tmp_path: Path) -> None:
    context = formal_test.formal_context.__wrapped__(tmp_path)
    operator, normalizer, sessions, root = next(context)
    try:
        spec, manifest, candidates, materials = _accepted_selection(operator, normalizer, sessions)
        calls: list[tuple[str, ...]] = []
        staging = root / ".private-handoff" / "final-runtime-staging"
        staging.mkdir()
        m3 = WindowsFaceLandmarkerOfflineM3Backend.for_testing(
            staging_root=staging, runner=_runner(calls)
        )
        received: list[object] = []

        def m4_factory(
            source_materials: tuple[
                runtime.SourceMaterial,
                runtime.SourceMaterial,
                runtime.SourceMaterial,
                runtime.SourceMaterial,
            ],
            landmarks: dict[str, tuple[tuple[float, float, float], ...]],
        ) -> orchestrator.D02CaseM4Backend:
            received.extend((source_materials, landmarks))
            return cast(orchestrator.D02CaseM4Backend, _AssemblyOnlyM4())

        assembled = orchestrator.assemble_formal_runtime(
            spec=spec,
            manifest=manifest,
            candidates=candidates,
            materials=materials,
            formal_reviews=[
                _accepted_review(manifest, candidate, material.sha256, position)
                for position, (candidate, material) in enumerate(
                    zip(candidates, materials, strict=True), start=1
                )
            ],
            m3_backend=m3,
            m4_backend_factory=m4_factory,
        )

        assert len(calls) == 12
        assert len(received) == 2
        assert len(assembled.bundle.runtime_packets) == 4
        assert (
            assembled.bundle.runtime_source_manifest_digest
            != assembled.bundle.formal_source_manifest_digest
        )
    finally:
        context.close()


def _prepared_runtime() -> tuple[
    orchestrator.PreparedRuntimeEvidence,
    FormalSourceRuntimeBundle,
    dict[str, object],
]:
    original, formal, _ = _runtime_result()
    payload = cast(dict[str, object], original.report_row["report_payload"])
    source_records = cast(list[dict[str, object]], payload["source_m3_repeat_evidence"])
    source_outputs = []
    for source_ordinal in range(1, 5):
        records = [
            record for record in source_records if record["source_ordinal"] == source_ordinal
        ]
        source_outputs.append(
            tuple(
                runtime.M3ExecutionOutput.create(
                    runtime.BackendM3Result(
                        payload_schema=r2.R2_SOURCE_M3_SCHEMA,
                        fields={key: record[key] for key in _SOURCE_M3_FIELDS},
                    )
                )
                for record in records
            )
        )
    augmented_sources = tuple(
        SimpleNamespace(
            source_input=source.source_input,
            source_row=source.source_row,
            identity_row=source.identity_row,
            position=source.position,
            source_m3_outputs=outputs,
        )
        for source, outputs in zip(formal.sources, source_outputs, strict=True)
    )
    bundle_values = vars(formal).copy()
    bundle_values["sources"] = augmented_sources
    bundle = cast(FormalSourceRuntimeBundle, SimpleNamespace(**bundle_values))
    packets, materials, fields = _generic_runtime_packets()
    del packets
    recipe = runtime.build_default_runtime_recipe()
    model = runtime.build_default_model_identity()
    m4_records = cast(list[dict[str, object]], payload["m4_repeat_evidence"])
    result_records = cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])
    prepared = orchestrator.PreparedRuntimeEvidence(
        formal_bundle=bundle,
        source_materials=materials,
        recipe=recipe,
        model_identity=model,
        created_at=cast(str, fields["created_at"]),
        execution_authority=cast(dict[str, object], payload["schema_and_policy"]),
        cases=tuple(cast(list[dict[str, object]], payload["ordered_case_manifest"])),
        m4_adapter_fields=tuple({key: record[key] for key in _M4_FIELDS} for record in m4_records),
        result_m3_adapter_fields=tuple(
            {key: record[key] for key in _RESULT_M3_FIELDS} for record in result_records
        ),
        result_outputs=original.result_outputs,
        _factory_token=orchestrator._PREPARED_TOKEN,
    )
    return prepared, bundle, fields


def test_prepared_runtime_replay_finalizes_without_backend_reexecution() -> None:
    prepared, bundle, fields = _prepared_runtime()
    try:
        orchestrator.finalize_runtime_evidence(prepared=prepared, artifact_decisions={})
    except orchestrator.D02FinalOrchestratorError as error:
        assert error.code == "ARTIFACT_REVIEW_CARDINALITY_INVALID"
    else:
        raise AssertionError("missing artifact decisions were accepted")

    # Fixture JPEGs are intentionally smaller than the production pHash Gate.
    # Use their accepted fixture-only quality adapters while exercising the
    # prepared M3/M4 replay (which has no backend object to call).
    replay = orchestrator._PreparedRuntimeReplayAdapter(prepared)
    fixture_adapters = _Adapters(deepcopy(fields))
    report = screening_execution.run_offline_screening(
        screening_execution.OfflineScreeningRequest(
            created_at=prepared.created_at,
            source_packets=bundle.runtime_packets,
            execution_authority=prepared.execution_authority,
            case_fields=replay,
            vision_m3=replay,
            m4=replay,
            measurement_gate=fixture_adapters,
            manual_review=fixture_adapters,
            phash=fixture_adapters,
        )
    )
    replay.assert_complete()

    assert report["status"] == "PASSED"
    assert report["source_m3_repeat_count"] == 12
    assert report["m4_execution_count"] == 96
    assert report["result_m3_repeat_count"] == 144


def test_review_decisions_project_to_screening_case_order() -> None:
    prepared, _, _ = _prepared_runtime()
    decisions = {
        subject.case_id: PrincipalArtifactDecision.seal(
            case_id=subject.case_id,
            result_sha256=subject.result_sha256,
            decision_sequence=subject.decision_sequence,
            manual_review_version="test-review-v1",
            manual_review_policy_digest="a" * 64,
            background_seam=subject.decision_sequence == 1,
            disconnected_contour=False,
            duplicated_feature=False,
            warp_tear=False,
        )
        for subject in prepared.review_subjects
    }

    projected = orchestrator._screening_artifact_decisions(
        prepared=prepared,
        artifact_decisions=decisions,
    )

    assert list(projected) == sorted(decisions)
    for decision_sequence, case_id in enumerate(sorted(decisions), start=1):
        original = decisions[case_id]
        current = projected[case_id]
        assert current.case_id == original.case_id
        assert current.result_sha256 == original.result_sha256
        assert current.decision_sequence == decision_sequence
        assert current.background_seam == original.background_seam
        assert current.disconnected_contour == original.disconnected_contour
        assert current.duplicated_feature == original.duplicated_feature
        assert current.warp_tear == original.warp_tear


def test_finalize_projects_review_order_without_backend_reexecution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, _, fields = _prepared_runtime()
    decisions = {
        subject.case_id: PrincipalArtifactDecision.seal(
            case_id=subject.case_id,
            result_sha256=subject.result_sha256,
            decision_sequence=subject.decision_sequence,
            manual_review_version="test-review-v1",
            manual_review_policy_digest=cast(
                str, prepared.execution_authority["manual_review_policy_digest"]
            ),
            background_seam=False,
            disconnected_contour=False,
            duplicated_feature=False,
            warp_tear=False,
        )
        for subject in prepared.review_subjects
    }
    fixture_adapters = _Adapters(deepcopy(fields))
    monkeypatch.setattr(orchestrator, "PHashAdapter", lambda _: fixture_adapters)

    result = orchestrator.finalize_runtime_evidence(
        prepared=prepared,
        artifact_decisions=decisions,
    )

    assert result.admission_ready
    assert len(result.result_outputs) == 48
