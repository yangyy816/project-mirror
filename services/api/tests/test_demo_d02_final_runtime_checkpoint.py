from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from test_demo_d02_final_orchestrator import _prepared_runtime

from mirror_api.demo_d02_final_orchestrator import PreparedRuntimeEvidence
from mirror_api.demo_d02_final_runtime_checkpoint import (
    CHECKPOINT_RELATIVE,
    D02FinalRuntimeCheckpoint,
    D02FinalRuntimeCheckpointError,
)
from mirror_api.demo_d02_runtime_result_store import D02RuntimeResultStore
from mirror_api.demo_d02_screening_adapters import PrincipalArtifactDecision


class _MemoryResultStore:
    def __init__(self, outputs: tuple[object, ...]) -> None:
        self._outputs = outputs

    def finalize(self) -> tuple[object, ...]:
        return self._outputs


def _checkpoint(
    tmp_path: Path,
) -> tuple[D02FinalRuntimeCheckpoint, PreparedRuntimeEvidence]:
    (tmp_path / ".private-handoff").mkdir()
    prepared, _, _ = _prepared_runtime()
    binding = "a" * 64
    store = cast(D02RuntimeResultStore, _MemoryResultStore(prepared.result_outputs))
    first = prepared.formal_bundle.sources[0].source_input
    checkpoint = D02FinalRuntimeCheckpoint(
        workspace_root=tmp_path,
        availability_binding_digest=binding,
        acquisition_run_id=first.acquisition_run_id,
        selected_manifest_digest=first.manifest_content_digest,
        admission_idempotency_key_hash="b" * 64,
        result_store=store,
    )
    return checkpoint, prepared


def test_prepared_and_reviewed_runtime_recover_without_backend(tmp_path: Path) -> None:
    checkpoint, prepared = _checkpoint(tmp_path)
    checkpoint.save_prepared(prepared)
    recovered = checkpoint.load(materials=prepared.source_materials)
    assert recovered.stage == "PREPARED"
    assert recovered.artifact_decisions is None
    assert recovered.prepared.result_outputs == prepared.result_outputs
    assert recovered.prepared.cases == prepared.cases

    policy = cast(str, prepared.execution_authority["manual_review_policy_digest"])
    decisions = {
        subject.case_id: PrincipalArtifactDecision.seal(
            case_id=subject.case_id,
            result_sha256=subject.result_sha256,
            decision_sequence=subject.decision_sequence,
            manual_review_version="d02-artifact-review-v1",
            manual_review_policy_digest=policy,
            background_seam=False,
            disconnected_contour=False,
            duplicated_feature=False,
            warp_tear=False,
        )
        for subject in prepared.review_subjects
    }
    checkpoint.save_reviewed(prepared=prepared, decisions=decisions)
    reviewed = checkpoint.load(materials=prepared.source_materials)
    assert reviewed.stage == "REVIEWED"
    assert reviewed.artifact_decisions == decisions


def test_checkpoint_tamper_and_binding_substitution_fail_closed(tmp_path: Path) -> None:
    checkpoint, prepared = _checkpoint(tmp_path)
    checkpoint.save_prepared(prepared)
    path = tmp_path / CHECKPOINT_RELATIVE
    content = path.read_text(encoding="utf-8")
    path.write_text(content.replace('"stage":"PREPARED"', '"stage":"REVIEWED"'), encoding="utf-8")
    with pytest.raises(D02FinalRuntimeCheckpointError, match="FINAL_RUNTIME_CHECKPOINT_INVALID"):
        checkpoint.load(materials=prepared.source_materials)
