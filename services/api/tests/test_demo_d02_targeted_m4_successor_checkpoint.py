from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from PIL import Image

import mirror_api.demo_d02_targeted_m4_successor_checkpoint as successor_checkpoint_module
from mirror_api.demo_d02_r2_runtime_forward import M4ExecutionOutput
from mirror_api.demo_d02_screening_adapters import PrincipalArtifactDecision
from mirror_api.demo_d02_targeted_m4_successor_checkpoint import (
    CHECKPOINT_RELATIVE,
    D02TargetedM4SuccessorCheckpoint,
    D02TargetedM4SuccessorCheckpointError,
    D02TargetedM4SuccessorStore,
    SuccessorBindings,
)
from mirror_api.demo_measurement_quality import mirror_demo_digest

CASE_ID = "25" * 16


def _output(replay_index: int) -> M4ExecutionOutput:
    image = Image.new("RGB", (96, 96), (90, 120, 180))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95, subsampling=0)
    content = buffer.getvalue()
    payload = {
        "schema_version": "mirror.demo/D02R2M4ExecutionOutput/v1",
        "case_id": CASE_ID,
        "replay_index": replay_index,
        "result_output_id": f"output-{replay_index:032x}",
        "result_sha256": hashlib.sha256(content).hexdigest(),
        "result_byte_size": len(content),
        "result_mime_type": "image/jpeg",
        "result_width": 96,
        "result_height": 96,
        "changed_pixel_count": 1,
        "execution_receipt_digest": hashlib.sha256(f"receipt-{replay_index}".encode()).hexdigest(),
        "execution_succeeded": True,
    }
    return M4ExecutionOutput(
        content=content,
        output_digest=mirror_demo_digest(payload["schema_version"], payload),
        **payload,
    )


def _bindings() -> SuccessorBindings:
    return SuccessorBindings(
        policy_digest="a" * 64,
        implementation_digest="b" * 64,
        config_digest="c" * 64,
        scope_digest="d" * 64,
        predecessor_checkpoint_digest="e" * 64,
        predecessor_report_digest="f" * 64,
        successor_case_id=CASE_ID,
        successor_admission_idempotency_key_hash="0" * 64,
    )


def _record(name: str, digest_key: str) -> dict[str, object]:
    return {
        "schema_version": f"test/{name}/v1",
        "subject_id": name,
        digest_key: hashlib.sha256(name.encode()).hexdigest(),
    }


def _decision(
    first: M4ExecutionOutput,
    *,
    case_id: str = CASE_ID,
    result_sha256: str | None = None,
    decision_sequence: int = 25,
) -> PrincipalArtifactDecision:
    return PrincipalArtifactDecision.seal(
        case_id=case_id,
        result_sha256=first.result_sha256 if result_sha256 is None else result_sha256,
        decision_sequence=decision_sequence,
        manual_review_version="manual-v1",
        manual_review_policy_digest="9" * 64,
        background_seam=False,
        disconnected_contour=False,
        duplicated_feature=False,
        warp_tear=False,
    )


def _resign_checkpoint(path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    digest_document = dict(document)
    digest_document.pop("document_digest", None)
    document["document_digest"] = hashlib.sha256(
        b"mirror.private/D02TargetedM4SuccessorCheckpoint/v1\n"
        + json.dumps(
            digest_document, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()
    path.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")


def _setup(
    tmp_path: Path,
) -> tuple[D02TargetedM4SuccessorCheckpoint, D02TargetedM4SuccessorStore]:
    (tmp_path / ".private-handoff").mkdir()
    bindings = _bindings()
    return (
        D02TargetedM4SuccessorCheckpoint(workspace_root=tmp_path, bindings=bindings),
        D02TargetedM4SuccessorStore(
            workspace_root=tmp_path, successor_case_id=bindings.successor_case_id
        ),
    )


def test_durable_crash_recovery_replays_same_bytes_without_backend(tmp_path: Path) -> None:
    checkpoint, store = _setup(tmp_path)
    first, second = _output(1), _output(2)
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
    store.persist(first, second)
    after_store = checkpoint.load(store=store)
    assert after_store.stage == "REPAIR_POLICY_VALIDATED"
    assert after_store.m4_outputs == (first, second)
    checkpoint.advance(stage="TARGET_M4_DURABLE", m4_outputs=(first, second))
    recovered = checkpoint.load(store=store)
    assert recovered.stage == "TARGET_M4_DURABLE"
    assert recovered.m4_outputs == (first, second)
    assert recovered.m4_outputs is not None and recovered.m4_outputs[0].content == first.content


def test_full_monotonic_successor_checkpoint_uses_exact_cardinalities(tmp_path: Path) -> None:
    checkpoint, store = _setup(tmp_path)
    first, second = _output(1), _output(2)
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
    store.persist(first, second)
    records = tuple(_record(f"m3-{index}", "record_digest") for index in range(3))
    decision = _decision(first)
    universe = {
        "schema_version": "test/universe/v1",
        "successor_universe_digest": "1" * 64,
    }
    envelope = {
        "schema_version": "test/envelope/v1",
        "provenance_envelope_digest": "2" * 64,
    }
    checkpoint.advance(stage="TARGET_M4_DURABLE", m4_outputs=(first, second))
    checkpoint.advance(
        stage="TARGET_RESULT_M3_COMPLETE", m4_outputs=(first, second), result_m3_records=records
    )
    checkpoint.advance(
        stage="TARGET_REVIEW_REQUIRED",
        m4_outputs=(first, second),
        result_m3_records=records,
    )
    checkpoint.advance(
        stage="SUCCESSOR_REVIEWED",
        m4_outputs=(first, second),
        result_m3_records=records,
        artifact_decision=decision,
    )
    checkpoint.advance(
        stage="SUCCESSOR_SCREENING_REPLAYED",
        m4_outputs=(first, second),
        result_m3_records=records,
        artifact_decision=decision,
        successor_universe=universe,
        provenance_envelope=envelope,
    )
    checkpoint.advance(
        stage="ADMISSION_READY",
        m4_outputs=(first, second),
        result_m3_records=records,
        artifact_decision=decision,
        successor_universe=universe,
        provenance_envelope=envelope,
    )
    checkpoint.advance(
        stage="ADMITTED",
        m4_outputs=(first, second),
        result_m3_records=records,
        artifact_decision=decision,
        successor_universe=universe,
        provenance_envelope=envelope,
    )
    assert checkpoint.load(store=store).stage == "ADMITTED"
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_STAGE_NOT_MONOTONIC"
    ):
        checkpoint.advance(
            stage="ADMITTED",
            m4_outputs=(first, second),
            result_m3_records=records,
            artifact_decision=decision,
            successor_universe=universe,
            provenance_envelope=envelope,
        )


def test_checkpoint_tamper_extra_field_and_duplicate_key_fail_closed(tmp_path: Path) -> None:
    checkpoint, store = _setup(tmp_path)
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    path = tmp_path / CHECKPOINT_RELATIVE
    path.write_text('{"schema_version":"x","schema_version":"x"}', encoding="utf-8")
    with pytest.raises(D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_CHECKPOINT_INVALID"):
        checkpoint.load(store=store)


def test_nonempty_store_without_checkpoint_and_store_collision_fail_closed(tmp_path: Path) -> None:
    checkpoint, store = _setup(tmp_path)
    first, second = _output(1), _output(2)
    store.persist(first, second)
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_STORE_WITHOUT_CHECKPOINT"
    ):
        checkpoint.load(store=store)
    modified_payload = first.payload()
    modified_payload["result_output_id"] = "output-ffffffffffffffffffffffffffffffff"
    modified_payload["execution_receipt_digest"] = "3" * 64
    modified = M4ExecutionOutput(
        content=first.content,
        output_digest=mirror_demo_digest(first.schema_version, modified_payload),
        **modified_payload,
    )
    with pytest.raises(D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_STORE_COLLISION"):
        store.persist(modified, second)


def test_private_payload_or_wrong_case_fails_closed(tmp_path: Path) -> None:
    checkpoint, store = _setup(tmp_path)
    first, second = _output(1), _output(2)
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
    store.persist(first, second)
    checkpoint.advance(stage="TARGET_M4_DURABLE", m4_outputs=(first, second))
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError,
        match="SUCCESSOR_PUBLIC_PAYLOAD_PRIVATE_FIELD",
    ):
        checkpoint.advance(
            stage="TARGET_RESULT_M3_COMPLETE",
            m4_outputs=(first, second),
            result_m3_records=(
                _record("one", "record_digest"),
                _record("two", "record_digest"),
                {"record_digest": "a" * 64, "path": "x"},
            ),
        )


@pytest.mark.parametrize(
    "name", ("index.json", "case25-primary.jpg", "case25-backup.jpg", ".index.incoming")
)
def test_orphan_store_files_are_nonempty_and_fail_closed(tmp_path: Path, name: str) -> None:
    _, store = _setup(tmp_path)
    directory = tmp_path / ".private-handoff" / "d02-targeted-m4-successor"
    directory.mkdir()
    (directory / name).write_bytes(b"orphan")
    assert store.exists is True
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_STORE_PARTIAL_STATE"
    ):
        store.load()
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_STORE_PARTIAL_STATE"
    ):
        store.persist(_output(1), _output(2))


def test_recovered_checkpoint_evidence_is_complete_and_immutable(tmp_path: Path) -> None:
    checkpoint, store = _setup(tmp_path)
    first, second = _output(1), _output(2)
    records = tuple(_record(f"m3-{index}", "record_digest") for index in range(3))
    decision = _decision(first)
    universe = {"schema_version": "test/universe/v1", "successor_universe_digest": "1" * 64}
    envelope = {"schema_version": "test/envelope/v1", "provenance_envelope_digest": "2" * 64}
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
    store.persist(first, second)
    checkpoint.advance(stage="TARGET_M4_DURABLE", m4_outputs=(first, second))
    checkpoint.advance(
        stage="TARGET_RESULT_M3_COMPLETE", m4_outputs=(first, second), result_m3_records=records
    )
    checkpoint.advance(
        stage="TARGET_REVIEW_REQUIRED", m4_outputs=(first, second), result_m3_records=records
    )
    checkpoint.advance(
        stage="SUCCESSOR_REVIEWED",
        m4_outputs=(first, second),
        result_m3_records=records,
        artifact_decision=decision,
    )
    checkpoint.advance(
        stage="SUCCESSOR_SCREENING_REPLAYED",
        m4_outputs=(first, second),
        result_m3_records=records,
        artifact_decision=decision,
        successor_universe=universe,
        provenance_envelope=envelope,
    )
    recovered = checkpoint.load(store=store)
    assert recovered.result_m3_records == records
    assert recovered.artifact_decision == decision
    assert recovered.successor_universe == universe
    assert recovered.provenance_envelope == envelope
    with pytest.raises(TypeError):
        recovered.result_m3_records[0]["subject_id"] = "mutated"  # type: ignore[index]
    assert recovered.successor_universe is not None
    with pytest.raises(TypeError):
        recovered.successor_universe["schema_version"] = "mutated"  # type: ignore[index]


@pytest.mark.parametrize(
    ("mutate", "code"),
    (
        (
            lambda document: document.__setitem__("schema_version", []),
            "SUCCESSOR_CHECKPOINT_INVALID",
        ),
        (
            lambda document: cast(list[dict[str, object]], document["m4_outputs"])[0].__setitem__(
                "schema_version", []
            ),
            "SUCCESSOR_M4_PAYLOAD_INVALID",
        ),
        (
            lambda document: cast(list[dict[str, object]], document["m4_outputs"])[0].__setitem__(
                "replay_index", []
            ),
            "SUCCESSOR_M4_PAYLOAD_INVALID",
        ),
    ),
)
def test_malformed_json_field_types_are_redacted_and_stable(
    tmp_path: Path, mutate: Callable[[dict[str, object]], None], code: str
) -> None:
    checkpoint, store = _setup(tmp_path)
    first, second = _output(1), _output(2)
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
    store.persist(first, second)
    checkpoint.advance(stage="TARGET_M4_DURABLE", m4_outputs=(first, second))
    _resign_checkpoint(tmp_path / CHECKPOINT_RELATIVE, mutate)
    with pytest.raises(D02TargetedM4SuccessorCheckpointError) as raised:
        checkpoint.load(store=store)
    assert raised.value.code == code
    assert "[" not in str(raised.value)


@pytest.mark.parametrize(
    "decision",
    (
        lambda first: _decision(first, case_id="ab" * 16),
        lambda first: _decision(first, result_sha256="a" * 64),
        lambda first: _decision(first, decision_sequence=24),
    ),
)
def test_artifact_decision_binding_drift_fails_closed(
    tmp_path: Path, decision: Callable[[M4ExecutionOutput], PrincipalArtifactDecision]
) -> None:
    checkpoint, store = _setup(tmp_path)
    first, second = _output(1), _output(2)
    records = tuple(_record(f"m3-{index}", "record_digest") for index in range(3))
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
    store.persist(first, second)
    checkpoint.advance(stage="TARGET_M4_DURABLE", m4_outputs=(first, second))
    checkpoint.advance(
        stage="TARGET_RESULT_M3_COMPLETE", m4_outputs=(first, second), result_m3_records=records
    )
    checkpoint.advance(
        stage="TARGET_REVIEW_REQUIRED", m4_outputs=(first, second), result_m3_records=records
    )
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_REVIEW_BINDING_INVALID"
    ):
        checkpoint.advance(
            stage="SUCCESSOR_REVIEWED",
            m4_outputs=(first, second),
            result_m3_records=records,
            artifact_decision=decision(first),
        )


def test_artifact_decision_digest_tamper_fails_closed(tmp_path: Path) -> None:
    checkpoint, store = _setup(tmp_path)
    first, second = _output(1), _output(2)
    records = tuple(_record(f"m3-{index}", "record_digest") for index in range(3))
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
    store.persist(first, second)
    checkpoint.advance(stage="TARGET_M4_DURABLE", m4_outputs=(first, second))
    checkpoint.advance(
        stage="TARGET_RESULT_M3_COMPLETE",
        m4_outputs=(first, second),
        result_m3_records=records,
    )
    checkpoint.advance(
        stage="TARGET_REVIEW_REQUIRED",
        m4_outputs=(first, second),
        result_m3_records=records,
    )
    checkpoint.advance(
        stage="SUCCESSOR_REVIEWED",
        m4_outputs=(first, second),
        result_m3_records=records,
        artifact_decision=_decision(first),
    )
    _resign_checkpoint(
        tmp_path / CHECKPOINT_RELATIVE,
        lambda document: cast(dict[str, object], document["artifact_decision"]).__setitem__(
            "review_authority_digest", "0" * 64
        ),
    )
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError,
        match="SUCCESSOR_REVIEW_BINDING_INVALID",
    ):
        checkpoint.load(store=store)


def test_workspace_parent_reparse_is_rejected_before_checkpoint_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint, _ = _setup(tmp_path)
    parent = tmp_path / ".private-handoff"
    original = successor_checkpoint_module._is_link_or_reparse
    parent_inode = parent.lstat().st_ino
    monkeypatch.setattr(
        successor_checkpoint_module,
        "_is_link_or_reparse",
        lambda details: original(details) or details.st_ino == parent_inode,
    )
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_CHECKPOINT_PATH_INVALID"
    ):
        checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")


def test_workspace_root_reparse_is_rejected_on_windows_and_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(successor_checkpoint_module, "_is_link_or_reparse", lambda _: True)
    with pytest.raises(D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_WORKSPACE_INVALID"):
        D02TargetedM4SuccessorStore(workspace_root=tmp_path, successor_case_id=CASE_ID)


def test_successor_admission_key_hash_drift_and_collision_fail_closed(tmp_path: Path) -> None:
    checkpoint, store = _setup(tmp_path)
    checkpoint.advance(stage="PREDECESSOR_REVIEWED_FAILED")
    checkpoint.advance(stage="REPAIR_POLICY_VALIDATED")
    first, second = _output(1), _output(2)
    store.persist(first, second)
    altered_hash = replace(_bindings(), successor_admission_idempotency_key_hash="1" * 64)
    drifted = D02TargetedM4SuccessorCheckpoint(workspace_root=tmp_path, bindings=altered_hash)
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_CHECKPOINT_BINDING_INVALID"
    ):
        drifted.load(store=store)
    colliding_hash = replace(_bindings(), policy_digest="2" * 64)
    collision = D02TargetedM4SuccessorCheckpoint(workspace_root=tmp_path, bindings=colliding_hash)
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_CHECKPOINT_BINDING_INVALID"
    ):
        collision.load(store=store)
    with pytest.raises(
        D02TargetedM4SuccessorCheckpointError, match="SUCCESSOR_CHECKPOINT_BINDING_INVALID"
    ):
        D02TargetedM4SuccessorCheckpoint(
            workspace_root=tmp_path,
            bindings=replace(_bindings(), successor_admission_idempotency_key_hash="invalid"),
        )
