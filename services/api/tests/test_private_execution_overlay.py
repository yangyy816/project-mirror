from __future__ import annotations

import base64
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from mirror_api.synthetic_dataset import private_execution_overlay as overlay_module
from mirror_api.synthetic_dataset.private_execution_overlay import (
    ExecutionOverlayError,
    GenesisBinding,
    consume_dispatch,
    initialize_overlay,
    mark_dispatch_failed,
    prepare_dispatch,
    record_output_returned,
    register_imagegen_data_url_before_decode,
    register_output_before_decode,
    render_private_prompt,
    rollover_terminal_overlay,
    rollover_terminal_overlay_v2,
    verify_overlay,
    verify_registration_before_decode,
    verify_rollover_successor,
    verify_rollover_successor_v2,
)

CONTROLLER_SHA256 = "a" * 64
POLICY_DIGEST = "7" * 64
TIMESTAMP_0 = "2026-08-29T00:00:00Z"
TIMESTAMP_1 = "2026-08-29T00:00:01Z"
TIMESTAMP_2 = "2026-08-29T00:00:02Z"
TIMESTAMP_3 = "2026-08-29T00:00:03Z"


def _binding() -> GenesisBinding:
    return GenesisBinding(
        genesis_output_id="GENESIS-EPOCH3-0001",
        genesis_bootstrap_sha256="1" * 64,
        genesis_receipt_sha256="2" * 64,
        private_registry_sha256="3" * 64,
        generation_specification_version="generation-v3",
        generation_specification_sha256="4" * 64,
        assignment_manifest_version="assignment-v3",
        assignment_manifest_sha256="5" * 64,
        prompt_template_version="prompt-v3",
        prompt_template_sha256="6" * 64,
        policy_digest=POLICY_DIGEST,
    )


def _binding_v2() -> GenesisBinding:
    return GenesisBinding(
        genesis_output_id="GENESIS-EPOCH4-0001",
        genesis_bootstrap_sha256="1" * 64,
        genesis_receipt_sha256="2" * 64,
        private_registry_sha256="3" * 64,
        generation_specification_version="generation-v3",
        generation_specification_sha256="4" * 64,
        assignment_manifest_version="assignment-v3",
        assignment_manifest_sha256="5" * 64,
        prompt_template_version="prompt-v3",
        prompt_template_sha256="6" * 64,
        policy_digest=POLICY_DIGEST,
        request_call_count=2,
        requested_output_count=2,
        returned_output_count=2,
        raw_output_count=2,
        formal_calls_remaining=30,
        formal_raw_capacity_remaining=30,
        global_native_output_capacity_remaining=61,
        global_native_output_consumed=3,
        next_unused_ordinal="CAL-REQ-003",
    )


def _project_private_parent(project_root: Path) -> Path:
    git_marker = project_root / ".git"
    if not git_marker.exists():
        git_marker.write_text("gitdir: synthetic-test-worktree\n", encoding="utf-8")
    gitignore = project_root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".private-handoff/\n", encoding="utf-8")
    private_parent = project_root / ".private-handoff"
    private_parent.mkdir(exist_ok=True)
    return private_parent


def _initialized(tmp_path: Path) -> tuple[Path, Path]:
    private_parent = _project_private_parent(tmp_path)
    root = private_parent / "overlay-task-owned-0001"
    handle = initialize_overlay(
        allowed_parent=private_parent,
        root=root,
        overlay_output_id="OVERLAY-EPOCH3-0001",
        controller_sha256=CONTROLLER_SHA256,
        binding=_binding(),
        timestamp=TIMESTAMP_0,
    )
    return root, handle.receipt_path


def _consumed(tmp_path: Path) -> tuple[Path, Path]:
    root, receipt = _initialized(tmp_path)
    prepared = prepare_dispatch(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        ordinal="CAL-REQ-002",
        action_id="ACTION-CAL-REQ-002",
        expected_output_opaque_id="OUTPUT-CAL-REQ-002",
        timestamp=TIMESTAMP_1,
    )
    consumed = consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_2,
    )
    return root, consumed.receipt_path


def _imagegen_data_url(payload: bytes, media_type: str = "image/png") -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _returned_data_url(tmp_path: Path, data_url: str) -> tuple[Path, Path]:
    root, receipt = _consumed(tmp_path)
    returned = record_output_returned(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
        exact_generated_artifact_receipt=data_url,
    )
    return root, returned.receipt_path


def _terminal_registration_failure(tmp_path: Path) -> tuple[Path, Path]:
    root, receipt = _consumed(tmp_path)
    invalid_output_hint = "data:image/png;base64,invalid-path-receipt"
    returned = record_output_returned(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
        exact_generated_artifact_receipt=invalid_output_hint,
    )
    allowed_root = tmp_path / "allowed-generated-artifacts"
    allowed_root.mkdir()
    failed = register_output_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        allowed_generated_artifact_root=allowed_root.resolve(),
        exact_generated_artifact_receipt=invalid_output_hint,
        timestamp="2026-08-29T00:00:04Z",
    )
    return root, failed.receipt_path


def _terminal_registration_failure_v2(tmp_path: Path) -> tuple[Path, Path]:
    private_parent = _project_private_parent(tmp_path)
    root = private_parent / "overlay-task-owned-0103"
    initial = initialize_overlay(
        allowed_parent=private_parent,
        root=root,
        overlay_output_id="OVERLAY-EPOCH4-0103",
        controller_sha256=CONTROLLER_SHA256,
        binding=_binding_v2(),
        timestamp=TIMESTAMP_0,
    )
    prepared = prepare_dispatch(
        receipt_path=initial.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        ordinal="CAL-REQ-003",
        action_id="ACTION-CAL-REQ-003",
        expected_output_opaque_id="OUTPUT-CAL-REQ-003",
        timestamp=TIMESTAMP_1,
    )
    consumed = consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-003",
        timestamp=TIMESTAMP_2,
    )
    returned = record_output_returned(
        receipt_path=consumed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-003",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
        exact_generated_artifact_receipt="not-a-data-url",
    )
    failed = register_imagegen_data_url_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-003",
        project_worktree_root=tmp_path,
        imagegen_data_url="not-a-data-url",
        timestamp=TIMESTAMP_3,
    )
    return root, failed.receipt_path


def _rollover_v2_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    predecessor_root, predecessor_receipt = _terminal_registration_failure_v2(tmp_path)
    predecessor = verify_overlay(
        predecessor_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    receipt = cast(dict[str, Any], predecessor["receipt"])
    private_parent = predecessor_root.parent
    return (
        predecessor_root,
        predecessor_receipt,
        {
            "predecessor_receipt_path": predecessor_receipt,
            "expected_predecessor_receipt_sha256": overlay_module.sha256_file(predecessor_receipt),
            "expected_predecessor_state_sha256": receipt["state_sha256"],
            "expected_predecessor_event_sha256": receipt["event_sha256"],
            "expected_controller_sha256": CONTROLLER_SHA256,
            "project_worktree_root": tmp_path,
            "allowed_parent": private_parent,
            "successor_root": private_parent / "overlay-task-owned-0104",
            "successor_overlay_output_id": "OVERLAY-EPOCH4-0104",
            "timestamp": "2026-08-30T00:00:00Z",
        },
    )


def _fresh_process_environment() -> tuple[Path, dict[str, str]]:
    api_src = Path(__file__).resolve().parents[1] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(api_src), environment.get("PYTHONPATH", "")) if value
    )
    return api_src, environment


def test_overlay_prepare_and_consume_are_append_only_and_recoverable(tmp_path: Path) -> None:
    root, receipt = _initialized(tmp_path)
    initial = verify_overlay(receipt, expected_controller_sha256=CONTROLLER_SHA256)
    initial_state = cast(dict[str, Any], initial["state"])
    assert initial_state["phase"] == "READY"
    assert initial_state["next_unused_ordinal"] == "CAL-REQ-002"
    assert initial_state["counters"] == {
        "active_calls": 0,
        "admitted_identity_count": 0,
        "failed_call_count": 0,
        "formal_calls_remaining": 31,
        "formal_raw_capacity_remaining": 31,
        "global_native_output_capacity_remaining": 62,
        "global_native_output_consumed": 2,
        "raw_output_count": 1,
        "rejected_output_count": 0,
        "request_call_count": 1,
        "requested_output_count": 1,
        "returned_output_count": 1,
    }

    prepared = prepare_dispatch(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        ordinal="CAL-REQ-002",
        action_id="ACTION-CAL-REQ-002",
        expected_output_opaque_id="OUTPUT-CAL-REQ-002",
        timestamp=TIMESTAMP_1,
    )
    prepared_state = cast(
        dict[str, Any],
        verify_overlay(
            prepared.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert prepared.sequence == 1
    assert prepared_state["phase"] == "DISPATCH_PREPARED"
    assert prepared_state["counters"] == initial_state["counters"]

    consumed = consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_2,
    )
    consumed_state = cast(
        dict[str, Any],
        verify_overlay(
            consumed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert consumed.sequence == 2
    assert consumed_state["phase"] == "DISPATCH_STARTED_CONSUMED"
    assert consumed_state["next_unused_ordinal"] == "CAL-REQ-003"
    assert consumed_state["counters"]["request_call_count"] == 2
    assert consumed_state["counters"]["requested_output_count"] == 2
    assert consumed_state["counters"]["formal_calls_remaining"] == 30
    assert consumed_state["counters"]["global_native_output_capacity_remaining"] == 61
    assert consumed_state["counters"]["global_native_output_consumed"] == 3
    assert consumed_state["counters"]["active_calls"] == 1
    assert sorted(path.name for path in root.glob("event-*.json")) == [
        "event-000000.json",
        "event-000001.json",
        "event-000002.json",
    ]


def test_output_is_registered_and_receipted_before_any_decode(tmp_path: Path) -> None:
    root, receipt = _consumed(tmp_path)
    artifact_root = tmp_path / "generated-artifacts"
    source = artifact_root / "native-generated-artifact.bin"
    exact_output_hint = str(source.resolve())
    returned = record_output_returned(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
        exact_generated_artifact_receipt=exact_output_hint,
    )
    returned_state = cast(
        dict[str, Any],
        verify_overlay(
            returned.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert returned_state["phase"] == "OUTPUT_RETURNED_RECEIPT_BOUND"
    assert returned_state["decode_authorized"] is False
    assert returned_state["counters"]["returned_output_count"] == 2
    assert returned_state["counters"]["raw_output_count"] == 2
    assert returned_state["counters"]["formal_raw_capacity_remaining"] == 30
    assert returned_state["counters"]["active_calls"] == 1

    artifact_root.mkdir()
    source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"non-human-synthetic-fixture")

    registered = register_output_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        allowed_generated_artifact_root=artifact_root.resolve(),
        exact_generated_artifact_receipt=exact_output_hint,
        timestamp="2026-08-29T00:00:04Z",
    )
    result = verify_registration_before_decode(
        registered.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert result == {
        "status": "REGISTER_BEFORE_DECODE_PASS",
        "phase": "OUTPUT_REGISTERED_PRE_DECODE",
        "sequence": 6,
        "output_opaque_id": "OUTPUT-CAL-REQ-002",
        "source_sha256": result["source_sha256"],
        "staging_sha256": result["source_sha256"],
        "byte_size": len(source.read_bytes()),
        "media_type": "image/png",
        "magic_byte_class": "PNG_89504E470D0A1A0A",
        "decode_performed": False,
        "dimensions_read": False,
    }
    state = cast(
        dict[str, Any],
        verify_overlay(
            registered.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert state["decode_authorized"] is True
    assert state["counters"]["returned_output_count"] == 2
    assert state["counters"]["raw_output_count"] == 2
    assert state["counters"]["formal_raw_capacity_remaining"] == 30
    assert state["counters"]["active_calls"] == 0

    registration = cast(dict[str, Any], state["output_registration"])
    attempt = cast(dict[str, Any], state["output_registration_attempt"])
    assert attempt["output_opaque_id"] == "OUTPUT-CAL-REQ-002"
    assert exact_output_hint not in json.dumps(state)
    record = json.loads((root / "records" / registration["record_file"]).read_text())
    registration_receipt = json.loads(
        (root / "records" / registration["registration_receipt_file"]).read_text()
    )
    assert set(registration) == {
        "output_opaque_id",
        "record_file",
        "record_sha256",
        "registration_receipt_file",
        "registration_receipt_sha256",
        "registration_status",
        "receipt_status",
    }
    assert set(record) == {
        "schema_version",
        "output_opaque_id",
        "request_ordinal",
        "source_kind",
        "source_delivery_class",
        "exact_generated_artifact_receipt_sha256",
        "source_sha256",
        "staging_sha256",
        "byte_size",
        "media_type",
        "magic_byte_class",
        "generation_specification_version",
        "generation_specification_digest",
        "assignment_manifest_version",
        "assignment_manifest_digest",
        "request_ledger_status",
        "output_ledger_status",
        "custody_status",
        "retention_class",
        "cleanup_policy",
        "registration_timestamp",
        "registration_status",
        "registration_commit_receipt",
        "decode_performed",
        "dimensions_read",
    }
    assert set(registration_receipt) == {
        "schema_version",
        "registration_receipt_id",
        "output_opaque_id",
        "request_ordinal",
        "output_record_file",
        "output_record_sha256",
        "output_record_bytes",
        "exact_generated_artifact_receipt_sha256",
        "source_sha256",
        "staging_sha256",
        "registration_status",
        "receipt_status",
        "decode_performed",
        "dimensions_read",
        "timestamp",
    }
    assert record["registration_status"] == "COMMITTED"
    assert record["decode_performed"] is False
    assert record["dimensions_read"] is False
    assert "dimensions" not in record
    assert (root / "staging" / "OUTPUT-CAL-REQ-002.raw").read_bytes() == source.read_bytes()


@pytest.mark.parametrize(
    ("media_type", "payload", "magic_class"),
    [
        ("image/png", b"\x89PNG\r\n\x1a\nsynthetic-non-face-png", "PNG_89504E470D0A1A0A"),
        ("image/jpeg", b"\xff\xd8\xff\xe0synthetic-non-face-jpeg", "JPEG_FFD8FF"),
        (
            "image/webp",
            b"RIFF\x10\x00\x00\x00WEBPsynthetic-non-face-webp",
            "WEBP_RIFF",
        ),
    ],
)
def test_imagegen_data_url_is_captured_before_decode_without_plaintext_persistence(
    tmp_path: Path,
    media_type: str,
    payload: bytes,
    magic_class: str,
) -> None:
    data_url = _imagegen_data_url(payload, media_type)
    root, returned_receipt = _returned_data_url(tmp_path, data_url)
    registered = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    result = verify_registration_before_decode(
        registered.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=tmp_path,
    )
    assert result["phase"] == "OUTPUT_REGISTERED_PRE_DECODE"
    assert result["sequence"] == 6
    assert result["source_delivery_class"] == "CODEX_NATIVE_IMAGEGEN_DATA_URL"
    assert result["media_type"] == media_type
    assert result["magic_byte_class"] == magic_class
    assert result["byte_size"] == len(payload)
    assert result["source_sha256"] == result["staging_sha256"]
    assert result["decode_performed"] is False
    assert result["dimensions_read"] is False
    assert (root / "staging" / "OUTPUT-CAL-REQ-002.raw").read_bytes() == payload

    state = cast(
        dict[str, Any],
        verify_overlay(
            registered.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert state["decode_authorized"] is False
    assert result["decode_authorized"] is True
    registration = cast(dict[str, Any], state["output_registration"])
    capture = json.loads(
        (root / "records" / registration["capture_sidecar_file"]).read_text(encoding="utf-8")
    )
    assert capture["capture_status"] == "COMMITTED_PRE_DECODE"
    assert capture["decode_performed"] is False
    assert capture["dimensions_read"] is False
    assert capture["source_sha256"] == result["source_sha256"]
    assert capture["staging_sha256"] == result["staging_sha256"]
    persisted_json = "".join(
        path.read_text(encoding="utf-8")
        for path in [
            *sorted(root.glob("event-*.json")),
            *sorted(root.glob("state-*.json")),
            *sorted(root.glob("receipt-*.json")),
            *sorted((root / "records").glob("*.json")),
        ]
    )
    assert data_url not in persisted_json
    assert base64.b64encode(payload).decode("ascii") not in persisted_json


def test_imagegen_data_url_requires_exact_project_local_git_ignored_custody(
    tmp_path: Path,
) -> None:
    data_url = _imagegen_data_url(b"\x89PNG\r\n\x1a\nproject-authority")
    root, returned_receipt = _returned_data_url(tmp_path, data_url)
    wrong_project_root = tmp_path / "wrong-project"
    wrong_project_root.mkdir()
    with pytest.raises(
        ExecutionOverlayError,
        match="PROJECT_PRIVATE_PARENT_AUTHORITY_MISMATCH",
    ):
        register_imagegen_data_url_before_decode(
            receipt_path=returned_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            project_worktree_root=wrong_project_root,
            imagegen_data_url=data_url,
            timestamp="2026-08-29T00:00:04Z",
        )
    (tmp_path / ".gitignore").write_text(".unrelated/\n", encoding="utf-8")
    with pytest.raises(
        ExecutionOverlayError,
        match="PROJECT_PRIVATE_NAMESPACE_NOT_GIT_IGNORED",
    ):
        register_imagegen_data_url_before_decode(
            receipt_path=returned_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            project_worktree_root=tmp_path,
            imagegen_data_url=data_url,
            timestamp="2026-08-29T00:00:04Z",
        )
    assert (
        verify_overlay(
            returned_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"]["phase"]
        == "OUTPUT_RETURNED_RECEIPT_BOUND"
    )
    assert not (root / "receipt-000005.json").exists()


def test_imagegen_capture_is_reverified_before_final_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_url = _imagegen_data_url(b"\x89PNG\r\n\x1a\nfinal-gate-race")
    _root, returned_receipt = _returned_data_url(tmp_path, data_url)
    original_verify = overlay_module._verify_imagegen_capture_binding
    calls = 0

    def tamper_before_second_verification(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            capture_name = cast(dict[str, Any], kwargs["capture_binding"])["capture_sidecar_file"]
            capture_path = cast(Path, kwargs["root"]) / "records" / capture_name
            capture_path.write_bytes(capture_path.read_bytes() + b" ")
        original_verify(**kwargs)

    monkeypatch.setattr(
        overlay_module,
        "_verify_imagegen_capture_binding",
        tamper_before_second_verification,
    )
    failed = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    verified = verify_overlay(
        failed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert calls == 2
    assert verified["state"]["phase"] == "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
    assert verified["state"]["decode_authorized"] is False
    assert verified["event"]["reason_code"] == "IMAGEGEN_CAPTURE_SIDECAR_NOT_VALID_PRE_DECODE"


@pytest.mark.skipif(os.name == "nt", reason="POSIX dirfd binding probe")
def test_private_write_uses_bound_parent_descriptor_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "private-parent"
    parent.mkdir()
    held_parent = tmp_path / "private-parent-held"
    outside = tmp_path / "outside"
    outside.mkdir()
    target = parent / "capture.raw"
    original_open_chain = overlay_module._open_posix_directory_chain

    def replace_parent_after_open(path: Path) -> list[int]:
        descriptors = original_open_chain(path)
        parent.rename(held_parent)
        parent.symlink_to(outside, target_is_directory=True)
        return descriptors

    monkeypatch.setattr(
        overlay_module,
        "_open_posix_directory_chain",
        replace_parent_after_open,
    )
    with pytest.raises(
        ExecutionOverlayError,
        match="GENERATED_ARTIFACT_ROOT_CHANGED_BEFORE_READ",
    ):
        overlay_module._write_bytes_create_or_verify_exact(target, b"private-bytes")
    assert not (outside / target.name).exists()
    assert not (held_parent / target.name).exists()


def test_private_directory_create_uses_bound_parent_handle_before_creating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "private-parent"
    parent.mkdir()
    held_parent = tmp_path / "private-parent-held"
    replacement_parent = tmp_path / "private-parent-replacement"
    target = parent / "successor-root"
    if os.name == "nt":
        handles = overlay_module._open_windows_directory_chain(parent)
        try:
            with pytest.raises(PermissionError):
                parent.rename(held_parent)
        finally:
            overlay_module._close_windows_handles(handles)
        overlay_module._create_new_plain_directory(target)
        assert target.is_dir()
        return

    original_open_chain = overlay_module._open_posix_directory_chain

    def replace_parent_after_open(path: Path) -> list[int]:
        descriptors = original_open_chain(path)
        parent.rename(held_parent)
        replacement_parent.mkdir()
        replacement_parent.rename(parent)
        return descriptors

    monkeypatch.setattr(
        overlay_module,
        "_open_posix_directory_chain",
        replace_parent_after_open,
    )

    with pytest.raises(
        ExecutionOverlayError,
        match="PRIVATE_OVERLAY_DIRECTORY_BINDING_CHANGED",
    ):
        overlay_module._create_new_plain_directory(target)
    assert not target.exists()
    held_target = held_parent / target.name
    assert not held_target.exists() or not any(held_target.iterdir())


@pytest.mark.parametrize(
    ("data_url", "expected_reason"),
    [
        ("https://invalid.example/image.png", "IMAGEGEN_DATA_URL_HEADER_INVALID"),
        ("data:image/gif;base64,AAAA", "IMAGEGEN_DATA_URL_HEADER_INVALID"),
        (
            "data:image/png;charset=utf-8;base64,AAAA",
            "IMAGEGEN_DATA_URL_HEADER_INVALID",
        ),
        ("data:image/png;base64,", "IMAGEGEN_DATA_URL_PAYLOAD_EMPTY"),
        ("data:image/png;base64,AAAA AAAA", "IMAGEGEN_DATA_URL_BASE64_INVALID"),
        ("data:image/png;base64,AAAA\nAAAA", "IMAGEGEN_DATA_URL_BASE64_INVALID"),
        ("data:image/png;base64,AAAA===", "IMAGEGEN_DATA_URL_BASE64_INVALID"),
        ("data:image/png;base64,AAAA-_==", "IMAGEGEN_DATA_URL_BASE64_INVALID"),
        ("data:image/png;base64,AAAA%3D%3D", "IMAGEGEN_DATA_URL_BASE64_INVALID"),
        ("data:image/png;base64,AB==", "IMAGEGEN_DATA_URL_BASE64_INVALID"),
    ],
)
def test_imagegen_data_url_strict_grammar_failures_are_terminal_without_leakage(
    tmp_path: Path,
    data_url: str,
    expected_reason: str,
) -> None:
    root, returned_receipt = _returned_data_url(tmp_path, data_url)
    failed = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    verified = verify_overlay(
        failed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert verified["state"]["phase"] == "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
    assert verified["state"]["hard_stop"] is True
    assert verified["state"]["decode_authorized"] is False
    assert verified["event"]["reason_code"] == expected_reason
    persisted_json = "".join(
        path.read_text(encoding="utf-8")
        for path in [
            *sorted(root.glob("event-*.json")),
            *sorted(root.glob("state-*.json")),
            *sorted(root.glob("receipt-*.json")),
        ]
    )
    assert data_url not in persisted_json


def test_imagegen_data_url_encoded_bound_is_checked_before_base64_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_url = "data:image/png;base64," + "A" * 12
    _root, returned_receipt = _returned_data_url(tmp_path, data_url)
    monkeypatch.setattr(overlay_module, "MAX_DATA_URL_ENCODED_BYTES", 8)

    def forbidden_decode(*_args: Any, **_kwargs: Any) -> bytes:
        pytest.fail("encoded overflow must be rejected before Base64 decode")

    monkeypatch.setattr(base64, "b64decode", forbidden_decode)
    failed = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    verified = verify_overlay(
        failed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert verified["event"]["reason_code"] == "IMAGEGEN_DATA_URL_ENCODED_BYTE_BOUND_FAILED"
    assert verified["state"]["decode_authorized"] is False


def test_imagegen_data_url_decoded_bound_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"\x89PNG\r\n\x1a\nX"
    data_url = _imagegen_data_url(payload)
    _root, returned_receipt = _returned_data_url(tmp_path, data_url)
    monkeypatch.setattr(overlay_module, "MAX_RETURNED_BYTES", len(payload) - 1)
    failed = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    verified = verify_overlay(
        failed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert verified["event"]["reason_code"] == "IMAGEGEN_DATA_URL_DECODED_BYTE_BOUND_FAILED"
    assert verified["state"]["decode_authorized"] is False


@pytest.mark.parametrize(
    ("data_url", "expected_reason"),
    [
        (
            _imagegen_data_url(b"\x89PNG\r\n\x1a\nsynthetic", "image/jpeg"),
            "IMAGEGEN_DATA_URL_MIME_MAGIC_MISMATCH",
        ),
        (
            _imagegen_data_url(b"not-a-supported-image-magic", "image/png"),
            "IMAGEGEN_DATA_URL_MAGIC_UNSUPPORTED",
        ),
    ],
)
def test_imagegen_data_url_mime_and_magic_must_agree(
    tmp_path: Path,
    data_url: str,
    expected_reason: str,
) -> None:
    _root, returned_receipt = _returned_data_url(tmp_path, data_url)
    failed = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    verified = verify_overlay(
        failed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert verified["event"]["reason_code"] == expected_reason
    assert verified["state"]["decode_authorized"] is False


def test_imagegen_data_url_binding_mismatch_rejects_before_attempt_without_plaintext_error(
    tmp_path: Path,
) -> None:
    bound = _imagegen_data_url(b"\x89PNG\r\n\x1a\nbound")
    different = _imagegen_data_url(b"\x89PNG\r\n\x1a\ndifferent")
    _root, returned_receipt = _returned_data_url(tmp_path, bound)
    with pytest.raises(ExecutionOverlayError, match="IMAGEGEN_DATA_URL_BINDING_MISMATCH") as caught:
        register_imagegen_data_url_before_decode(
            receipt_path=returned_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            project_worktree_root=tmp_path,
            imagegen_data_url=different,
            timestamp="2026-08-29T00:00:04Z",
        )
    assert different not in str(caught.value)
    with pytest.raises(ExecutionOverlayError, match="STATE_OR_ACTION_INVALID"):
        register_imagegen_data_url_before_decode(
            receipt_path=returned_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-003",
            project_worktree_root=tmp_path,
            imagegen_data_url=bound,
            timestamp="2026-08-29T00:00:04Z",
        )
    with pytest.raises(ExecutionOverlayError, match="CONTROLLER_DIGEST_MISMATCH"):
        register_imagegen_data_url_before_decode(
            receipt_path=returned_receipt,
            expected_controller_sha256="b" * 64,
            action_id="ACTION-CAL-REQ-002",
            project_worktree_root=tmp_path,
            imagegen_data_url=bound,
            timestamp="2026-08-29T00:00:04Z",
        )
    state = verify_overlay(
        returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
    )["state"]
    assert state["phase"] == "OUTPUT_RETURNED_RECEIPT_BOUND"
    assert state["counters"]["returned_output_count"] == 2


def test_imagegen_data_url_exact_existing_staging_and_complete_replay_are_idempotent(
    tmp_path: Path,
) -> None:
    payload = b"\x89PNG\r\n\x1a\nsynthetic-existing-staging"
    data_url = _imagegen_data_url(payload)
    root, returned_receipt = _returned_data_url(tmp_path, data_url)
    staging = root / "staging" / "OUTPUT-CAL-REQ-002.raw"
    staging.write_bytes(payload)
    first = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    replayed = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    assert replayed == first
    verified = verify_registration_before_decode(
        replayed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=tmp_path,
    )
    assert verified["source_sha256"] == verified["staging_sha256"]
    assert staging.read_bytes() == payload


def test_imagegen_data_url_different_existing_staging_fails_closed(tmp_path: Path) -> None:
    data_url = _imagegen_data_url(b"\x89PNG\r\n\x1a\nexpected")
    root, returned_receipt = _returned_data_url(tmp_path, data_url)
    (root / "staging" / "OUTPUT-CAL-REQ-002.raw").write_bytes(b"\x89PNG\r\n\x1a\ndifferent")
    failed = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    verified = verify_overlay(
        failed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert verified["state"]["phase"] == "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
    assert verified["state"]["hard_stop"] is True
    assert verified["state"]["decode_authorized"] is False


def test_imagegen_capture_sidecar_preexisting_conflict_fails_closed(
    tmp_path: Path,
) -> None:
    data_url = _imagegen_data_url(b"\x89PNG\r\n\x1a\nsidecar-conflict")
    root, returned_receipt = _returned_data_url(tmp_path, data_url)
    (root / "records" / "capture-OUTPUT-CAL-REQ-002.json").write_text(
        '{"conflict":true}\n', encoding="utf-8"
    )
    failed = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    verified = verify_overlay(
        failed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert verified["state"]["hard_stop"] is True
    assert verified["state"]["decode_authorized"] is False


@pytest.mark.parametrize("mutation", ["missing", "tampered"])
def test_imagegen_capture_sidecar_is_mandatory_for_decode_gate(
    tmp_path: Path,
    mutation: str,
) -> None:
    data_url = _imagegen_data_url(b"\x89PNG\r\n\x1a\nmandatory-sidecar")
    root, returned_receipt = _returned_data_url(tmp_path, data_url)
    registered = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    state = verify_overlay(
        registered.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )["state"]
    capture_path = root / "records" / state["output_registration"]["capture_sidecar_file"]
    if mutation == "missing":
        capture_path.unlink()
    else:
        capture_path.write_bytes(capture_path.read_bytes() + b" ")
    with pytest.raises(ExecutionOverlayError):
        verify_registration_before_decode(
            registered.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
        )


def test_imagegen_capture_rejects_reparse_staging_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_url = _imagegen_data_url(b"\x89PNG\r\n\x1a\nreparse-staging")
    root, returned_receipt = _returned_data_url(tmp_path, data_url)
    original_is_reparse = overlay_module._is_reparse

    def mark_staging_as_reparse(path: Path) -> bool:
        return path == root / "staging" or original_is_reparse(path)

    monkeypatch.setattr(overlay_module, "_is_reparse", mark_staging_as_reparse)
    failed = register_imagegen_data_url_before_decode(
        receipt_path=returned_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp="2026-08-29T00:00:04Z",
    )
    monkeypatch.setattr(overlay_module, "_is_reparse", original_is_reparse)
    verified = verify_overlay(
        failed.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert verified["state"]["hard_stop"] is True
    assert verified["state"]["decode_authorized"] is False


def test_duplicate_dispatch_and_wrong_ordinal_fail_closed(tmp_path: Path) -> None:
    _root, receipt = _initialized(tmp_path)
    with pytest.raises(ExecutionOverlayError, match="ORDINAL_MISMATCH"):
        prepare_dispatch(
            receipt_path=receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            ordinal="CAL-REQ-003",
            action_id="ACTION-CAL-REQ-003",
            expected_output_opaque_id="OUTPUT-CAL-REQ-003",
            timestamp=TIMESTAMP_1,
        )
    prepared = prepare_dispatch(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        ordinal="CAL-REQ-002",
        action_id="ACTION-CAL-REQ-002",
        expected_output_opaque_id="OUTPUT-CAL-REQ-002",
        timestamp=TIMESTAMP_1,
    )
    with pytest.raises(ExecutionOverlayError, match="PREPARE_STATE_INVALID"):
        prepare_dispatch(
            receipt_path=prepared.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            ordinal="CAL-REQ-002",
            action_id="ACTION-CAL-REQ-002-B",
            expected_output_opaque_id="OUTPUT-CAL-REQ-002-B",
            timestamp=TIMESTAMP_2,
        )
    consumed = consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_2,
    )
    replayed = consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_2,
    )
    assert replayed.receipt_path == consumed.receipt_path
    assert replayed.sequence == consumed.sequence == 2


def test_dispatch_failure_is_final_and_preserves_consumed_counters(tmp_path: Path) -> None:
    _root, receipt = _consumed(tmp_path)
    failed = mark_dispatch_failed(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        reason_code="NATIVE_TOOL_FAILED_ZERO_RETRY",
    )
    state = cast(
        dict[str, Any],
        verify_overlay(
            failed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert state["phase"] == "DISPATCH_FAILED_FINAL"
    assert state["hard_stop"] is True
    assert state["decode_authorized"] is False
    assert state["counters"]["request_call_count"] == 2
    assert state["counters"]["formal_calls_remaining"] == 30
    assert state["counters"]["failed_call_count"] == 1
    assert state["counters"]["active_calls"] == 0


def test_registration_failure_after_return_is_a_no_decode_hard_stop(tmp_path: Path) -> None:
    _root, receipt = _consumed(tmp_path)
    invalid_output_hint = "data:image/png;base64,ignored"
    returned = record_output_returned(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
        exact_generated_artifact_receipt=invalid_output_hint,
    )
    allowed_root = tmp_path / "allowed-generated-artifacts"
    allowed_root.mkdir()
    failed = register_output_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        allowed_generated_artifact_root=allowed_root.resolve(),
        exact_generated_artifact_receipt=invalid_output_hint,
        timestamp="2026-08-29T00:00:04Z",
    )
    state = cast(
        dict[str, Any],
        verify_overlay(
            failed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert state["phase"] == "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
    assert state["hard_stop"] is True
    assert state["decode_authorized"] is False
    assert state["counters"]["request_call_count"] == 2
    assert state["counters"]["returned_output_count"] == 2
    assert state["counters"]["raw_output_count"] == 2
    assert state["counters"]["active_calls"] == 0

    replayed = register_output_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        allowed_generated_artifact_root=allowed_root.resolve(),
        exact_generated_artifact_receipt=invalid_output_hint,
        timestamp="2026-08-29T00:00:04Z",
    )
    assert replayed.receipt_path == failed.receipt_path
    with pytest.raises(ExecutionOverlayError, match="STATE_OR_ACTION_INVALID"):
        register_output_before_decode(
            receipt_path=failed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            allowed_generated_artifact_root=allowed_root.resolve(),
            exact_generated_artifact_receipt=invalid_output_hint,
            timestamp="2026-08-29T00:00:04Z",
        )


def test_registration_rejects_out_of_scope_paths_and_data_urls(tmp_path: Path) -> None:
    _root, receipt = _consumed(tmp_path)
    allowed_root = tmp_path / "allowed-generated-artifacts"
    allowed_root.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    exact_outside_hint = str(outside.resolve())
    returned = record_output_returned(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
        exact_generated_artifact_receipt=exact_outside_hint,
    )
    failed = register_output_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        allowed_generated_artifact_root=allowed_root.resolve(),
        exact_generated_artifact_receipt=exact_outside_hint,
        timestamp="2026-08-29T00:00:04Z",
    )
    failed_state = cast(
        dict[str, Any],
        verify_overlay(
            failed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert failed_state["phase"] == "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
    assert failed_state["decode_authorized"] is False

    inside = allowed_root / "inside.bin"
    inside.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    with pytest.raises(ExecutionOverlayError, match="HARD_STOP"):
        register_output_before_decode(
            receipt_path=returned.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            allowed_generated_artifact_root=allowed_root.resolve(),
            exact_generated_artifact_receipt=str(inside.resolve()),
            timestamp="2026-08-29T00:00:04Z",
        )


@pytest.mark.parametrize("replacement", ["source", "root"])
def test_registration_rejects_validate_open_reparse_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement: str,
) -> None:
    root, receipt = _consumed(tmp_path)
    artifact_root = tmp_path / "allowed-generated-artifacts"
    artifact_root.mkdir()
    source = artifact_root / "native-generated-artifact.bin"
    source.write_bytes(b"\x89PNG\r\n\x1a\ntrusted-fixture")
    outside_root = tmp_path / "outside-generated-artifacts"
    outside_root.mkdir()
    outside_source = outside_root / source.name
    outside_source.write_bytes(b"outside-fixture-must-not-be-read")
    returned = record_output_returned(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
        exact_generated_artifact_receipt=str(source.resolve()),
    )

    if os.name == "nt":
        original_windows_open = overlay_module._windows_open_path

        def replace_before_final_open_windows(path: Path, *, expect_directory: bool) -> int:
            if path == source and not expect_directory:
                if replacement == "source":
                    source.unlink()
                    source.symlink_to(outside_source)
                else:
                    artifact_root.rename(tmp_path / "displaced-allowed-generated-artifacts")
                    artifact_root.symlink_to(outside_root, target_is_directory=True)
            return original_windows_open(path, expect_directory=expect_directory)

        monkeypatch.setattr(
            overlay_module,
            "_windows_open_path",
            replace_before_final_open_windows,
        )
    else:
        original_posix_open = os.open

        def replace_before_final_open_posix(
            path: str,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            directory_flag = cast(int, getattr(os, "O_DIRECTORY", 0))
            if path == source.name and dir_fd is not None and not flags & directory_flag:
                if replacement == "source":
                    source.unlink()
                    source.symlink_to(outside_source)
                else:
                    artifact_root.rename(tmp_path / "displaced-allowed-generated-artifacts")
                    artifact_root.symlink_to(outside_root, target_is_directory=True)
            return original_posix_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(os, "open", replace_before_final_open_posix)

    failed = register_output_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        allowed_generated_artifact_root=artifact_root.resolve(),
        exact_generated_artifact_receipt=str(source.resolve()),
        timestamp="2026-08-29T00:00:04Z",
    )
    state = cast(
        dict[str, Any],
        verify_overlay(
            failed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert state["phase"] == "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
    assert state["decode_authorized"] is False
    assert state["hard_stop"] is True
    assert not (root / "staging" / "OUTPUT-CAL-REQ-002.raw").exists()
    with pytest.raises(ExecutionOverlayError, match="STATE_OR_ACTION_INVALID"):
        register_output_before_decode(
            receipt_path=failed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            allowed_generated_artifact_root=artifact_root.resolve(),
            exact_generated_artifact_receipt=str(source.resolve()),
            timestamp="2026-08-29T00:00:04Z",
        )


def test_bound_source_open_closes_all_resources_if_fdopen_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "allowed-generated-artifacts"
    artifact_root.mkdir()
    source = artifact_root / "native-generated-artifact.bin"
    source.write_bytes(b"synthetic-non-image-fixture")
    opened_resources: list[int] = []

    if os.name == "nt":
        original_open = overlay_module._open_windows_generated_artifact

        def capture_windows_resources(
            *,
            generated_artifact_path: Path,
            allowed_generated_artifact_root: Path,
        ) -> tuple[int, list[int]]:
            file_handle, ancestor_handles = original_open(
                generated_artifact_path=generated_artifact_path,
                allowed_generated_artifact_root=allowed_generated_artifact_root,
            )
            opened_resources.extend([file_handle, *ancestor_handles])
            return file_handle, ancestor_handles

        monkeypatch.setattr(
            overlay_module,
            "_open_windows_generated_artifact",
            capture_windows_resources,
        )
    else:
        original_open = overlay_module._open_posix_generated_artifact

        def capture_posix_resources(
            *,
            generated_artifact_path: Path,
            allowed_generated_artifact_root: Path,
        ) -> tuple[int, list[int]]:
            file_descriptor, ancestor_descriptors = original_open(
                generated_artifact_path=generated_artifact_path,
                allowed_generated_artifact_root=allowed_generated_artifact_root,
            )
            opened_resources.extend([file_descriptor, *ancestor_descriptors])
            return file_descriptor, ancestor_descriptors

        monkeypatch.setattr(
            overlay_module,
            "_open_posix_generated_artifact",
            capture_posix_resources,
        )

    def fail_fdopen(_descriptor: int, _mode: str) -> Any:
        raise OSError("INJECTED_FDOPEN_FAILURE")

    monkeypatch.setattr(os, "fdopen", fail_fdopen)
    with pytest.raises(OSError, match="INJECTED_FDOPEN_FAILURE"):
        with overlay_module._open_bound_generated_artifact(
            generated_artifact_path=source,
            allowed_generated_artifact_root=artifact_root,
        ):
            pytest.fail("fdopen failure must prevent the source context from opening")

    assert opened_resources
    if os.name == "nt":
        import ctypes

        get_handle_information = ctypes.WinDLL("kernel32", use_last_error=True).GetHandleInformation
        get_handle_information.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        get_handle_information.restype = ctypes.c_int
        flags = ctypes.c_uint32()
        assert all(
            not get_handle_information(ctypes.c_void_p(handle), ctypes.byref(flags))
            for handle in opened_resources
        )
    else:
        for descriptor in opened_resources:
            with pytest.raises(OSError):
                os.fstat(descriptor)


def test_hash_chain_detects_prior_event_tampering(tmp_path: Path) -> None:
    root, receipt = _consumed(tmp_path)
    event = root / "event-000000.json"
    event.write_bytes(event.read_bytes() + b" ")
    with pytest.raises(ExecutionOverlayError, match="EVENT_DIGEST_MISMATCH"):
        verify_overlay(receipt, expected_controller_sha256=CONTROLLER_SHA256)


@pytest.mark.parametrize("crash_after_write", [1, 2, 3])
def test_transition_rolls_forward_from_exact_predecessor_in_fresh_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_after_write: int,
) -> None:
    root, receipt = _initialized(tmp_path)
    original_write = overlay_module._write_json_create_or_verify_exact
    write_count = 0

    def injected_crash(path: Path, value: dict[str, Any]) -> tuple[str, int]:
        nonlocal write_count
        result = original_write(path, value)
        write_count += 1
        if write_count == crash_after_write:
            raise RuntimeError("INJECTED_TRANSITION_CRASH")
        return result

    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        injected_crash,
    )
    with pytest.raises(RuntimeError, match="INJECTED_TRANSITION_CRASH"):
        prepare_dispatch(
            receipt_path=receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            ordinal="CAL-REQ-002",
            action_id="ACTION-CAL-REQ-002",
            expected_output_opaque_id="OUTPUT-CAL-REQ-002",
            timestamp=TIMESTAMP_1,
        )
    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        original_write,
    )

    api_src = Path(__file__).resolve().parents[1] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(api_src), environment.get("PYTHONPATH", "")) if value
    )
    script = """
import sys
from pathlib import Path
from mirror_api.synthetic_dataset.private_execution_overlay import prepare_dispatch

handle = prepare_dispatch(
    receipt_path=Path(sys.argv[1]),
    expected_controller_sha256=sys.argv[2],
    ordinal="CAL-REQ-002",
    action_id="ACTION-CAL-REQ-002",
    expected_output_opaque_id="OUTPUT-CAL-REQ-002",
    timestamp="2026-08-29T00:00:01Z",
)
print(handle.receipt_path)
"""
    recovered = subprocess.run(  # noqa: S603 - fixed interpreter and inline test probe
        [sys.executable, "-c", script, str(receipt), CONTROLLER_SHA256],
        cwd=api_src.parent,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert recovered.returncode == 0, recovered.stderr
    recovered_receipt = Path(recovered.stdout.strip())
    verified = verify_overlay(
        recovered_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert verified["state"]["phase"] == "DISPATCH_PREPARED"
    assert recovered_receipt == root / "receipt-000001.json"


@pytest.mark.parametrize("crash_after_write", [1, 2, 3, 4, 5, 6])
def test_output_return_counter_and_binding_recover_once_in_fresh_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_after_write: int,
) -> None:
    _root, consumed_receipt = _consumed(tmp_path)
    data_url = _imagegen_data_url(b"\x89PNG\r\n\x1a\nreturned-crash-recovery")
    original_write = overlay_module._write_json_create_or_verify_exact
    write_count = 0

    def injected_crash(path: Path, value: dict[str, Any]) -> tuple[str, int]:
        nonlocal write_count
        result = original_write(path, value)
        write_count += 1
        if write_count == crash_after_write:
            raise RuntimeError("INJECTED_OUTPUT_RETURN_CRASH")
        return result

    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        injected_crash,
    )
    with pytest.raises(RuntimeError, match="INJECTED_OUTPUT_RETURN_CRASH"):
        record_output_returned(
            receipt_path=consumed_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            timestamp=TIMESTAMP_3,
            returned_output_count=1,
            exact_generated_artifact_receipt=data_url,
        )
    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        original_write,
    )

    api_src, environment = _fresh_process_environment()
    script = """
import base64
import sys
from pathlib import Path
from mirror_api.synthetic_dataset.private_execution_overlay import record_output_returned

payload = b"\\x89PNG\\r\\n\\x1a\\nreturned-crash-recovery"
data_url = "data:image/png;base64," + base64.b64encode(payload).decode("ascii")
handle = record_output_returned(
    receipt_path=Path(sys.argv[1]),
    expected_controller_sha256=sys.argv[2],
    action_id="ACTION-CAL-REQ-002",
    timestamp="2026-08-29T00:00:03Z",
    returned_output_count=1,
    exact_generated_artifact_receipt=data_url,
)
print(handle.receipt_path)
"""
    recovered = subprocess.run(  # noqa: S603 - fixed interpreter and inline test probe
        [sys.executable, "-c", script, str(consumed_receipt), CONTROLLER_SHA256],
        cwd=api_src.parent,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert recovered.returncode == 0, recovered.stderr
    recovered_receipt = Path(recovered.stdout.strip())
    state = verify_overlay(
        recovered_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
    )["state"]
    assert recovered_receipt.name == "receipt-000004.json"
    assert state["phase"] == "OUTPUT_RETURNED_RECEIPT_BOUND"
    assert state["counters"]["returned_output_count"] == 2
    assert state["counters"]["raw_output_count"] == 2
    assert state["counters"]["formal_raw_capacity_remaining"] == 30


@pytest.mark.parametrize(
    "crash_point",
    [
        "attempt-event",
        "attempt-state",
        "attempt-receipt",
        "staging",
        "capture",
        "record",
        "registration",
        "final-event",
        "final-state",
        "final-receipt",
    ],
)
def test_imagegen_registration_crash_windows_recover_in_fresh_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_point: str,
) -> None:
    payload = b"\x89PNG\r\n\x1a\nregistration-crash-recovery"
    data_url = _imagegen_data_url(payload)
    root, returned_receipt = _returned_data_url(tmp_path, data_url)
    original_json_write = overlay_module._write_json_create_or_verify_exact
    original_bytes_write = overlay_module._write_bytes_create_or_verify_exact
    json_targets = {
        "attempt-event": "event-000005.json",
        "attempt-state": "state-000005.json",
        "attempt-receipt": "receipt-000005.json",
        "capture": "capture-OUTPUT-CAL-REQ-002.json",
        "record": "output-OUTPUT-CAL-REQ-002.json",
        "registration": "registration-OUTPUT-CAL-REQ-002.json",
        "final-event": "event-000006.json",
        "final-state": "state-000006.json",
        "final-receipt": "receipt-000006.json",
    }

    def injected_json_crash(path: Path, value: dict[str, Any]) -> tuple[str, int]:
        result = original_json_write(path, value)
        if json_targets.get(crash_point) == path.name:
            raise RuntimeError(f"INJECTED_{crash_point.upper()}_CRASH")
        return result

    def injected_bytes_crash(path: Path, value: bytes) -> tuple[str, int]:
        result = original_bytes_write(path, value)
        if crash_point == "staging":
            raise RuntimeError("INJECTED_STAGING_CRASH")
        return result

    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        injected_json_crash,
    )
    monkeypatch.setattr(
        overlay_module,
        "_write_bytes_create_or_verify_exact",
        injected_bytes_crash,
    )
    with pytest.raises(RuntimeError, match="INJECTED_"):
        register_imagegen_data_url_before_decode(
            receipt_path=returned_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            project_worktree_root=tmp_path,
            imagegen_data_url=data_url,
            timestamp="2026-08-29T00:00:04Z",
        )
    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        original_json_write,
    )
    monkeypatch.setattr(
        overlay_module,
        "_write_bytes_create_or_verify_exact",
        original_bytes_write,
    )

    api_src, environment = _fresh_process_environment()
    script = """
import base64
import sys
from pathlib import Path
from mirror_api.synthetic_dataset.private_execution_overlay import (
    register_imagegen_data_url_before_decode,
)

payload = b"\\x89PNG\\r\\n\\x1a\\nregistration-crash-recovery"
data_url = "data:image/png;base64," + base64.b64encode(payload).decode("ascii")
handle = register_imagegen_data_url_before_decode(
    receipt_path=Path(sys.argv[1]),
    expected_controller_sha256=sys.argv[2],
    action_id="ACTION-CAL-REQ-002",
    project_worktree_root=Path(sys.argv[3]),
    imagegen_data_url=data_url,
    timestamp="2026-08-29T00:00:04Z",
)
print(handle.receipt_path)
"""
    recovered = subprocess.run(  # noqa: S603 - fixed interpreter and inline test probe
        [
            sys.executable,
            "-c",
            script,
            str(returned_receipt),
            CONTROLLER_SHA256,
            str(tmp_path),
        ],
        cwd=api_src.parent,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert recovered.returncode == 0, recovered.stderr
    recovered_receipt = Path(recovered.stdout.strip())
    result = verify_registration_before_decode(
        recovered_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=tmp_path,
    )
    assert recovered_receipt == root / "receipt-000006.json"
    assert result["source_delivery_class"] == "CODEX_NATIVE_IMAGEGEN_DATA_URL"
    state = verify_overlay(
        recovered_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
    )["state"]
    assert state["counters"]["returned_output_count"] == 2
    assert state["counters"]["raw_output_count"] == 2
    assert state["counters"]["formal_raw_capacity_remaining"] == 30
    assert state["counters"]["active_calls"] == 0


def test_terminal_overlay_rollover_derives_exact_ledger_and_preserves_predecessor(
    tmp_path: Path,
) -> None:
    predecessor_root, predecessor_receipt = _terminal_registration_failure(tmp_path)
    private_parent = predecessor_root.parent
    predecessor_bytes = {
        path.name: path.read_bytes()
        for path in [
            predecessor_root / "event-000006.json",
            predecessor_root / "state-000006.json",
            predecessor_root / "receipt-000006.json",
        ]
    }
    with pytest.raises(
        ExecutionOverlayError,
        match="PROJECT_PRIVATE_PARENT_AUTHORITY_MISMATCH",
    ):
        rollover_terminal_overlay(
            predecessor_receipt_path=predecessor_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
            allowed_parent=tmp_path,
            successor_root=tmp_path / "overlay-task-owned-0002",
            successor_overlay_output_id="OVERLAY-EPOCH4-0002",
            timestamp="2026-08-29T00:00:05Z",
        )
    with pytest.raises(ExecutionOverlayError, match="ROLLOVER_SUCCESSOR_ROOT_NAME_INVALID"):
        rollover_terminal_overlay(
            predecessor_receipt_path=predecessor_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
            allowed_parent=private_parent,
            successor_root=private_parent / "..",
            successor_overlay_output_id="OVERLAY-EPOCH4-0002",
            timestamp="2026-08-29T00:00:05Z",
        )
    successor_root = private_parent / "overlay-task-owned-0002"
    successor = rollover_terminal_overlay(
        predecessor_receipt_path=predecessor_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=tmp_path,
        allowed_parent=private_parent,
        successor_root=successor_root,
        successor_overlay_output_id="OVERLAY-EPOCH4-0002",
        timestamp="2026-08-29T00:00:05Z",
    )
    result = verify_rollover_successor(
        successor.receipt_path,
        predecessor_receipt_path=predecessor_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=tmp_path,
    )
    assert result == {
        "status": "TERMINAL_OVERLAY_ROLLOVER_PASS",
        "successor_overlay_output_id": "OVERLAY-EPOCH4-0002",
        "predecessor_overlay_output_id": "OVERLAY-EPOCH3-0001",
        "next_unused_ordinal": "CAL-REQ-003",
        "formal_calls_remaining": 30,
        "formal_raw_capacity_remaining": 30,
        "global_native_output_capacity_remaining": 61,
        "global_native_output_consumed": 3,
        "decode_authorized": False,
    }
    replayed = rollover_terminal_overlay(
        predecessor_receipt_path=predecessor_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=tmp_path,
        allowed_parent=private_parent,
        successor_root=successor_root,
        successor_overlay_output_id="OVERLAY-EPOCH4-0002",
        timestamp="2026-08-29T00:00:05Z",
    )
    assert replayed == successor
    fork_root = private_parent / "overlay-task-owned-0003"
    with pytest.raises(ExecutionOverlayError, match="CREATE_NEW_EXISTING_CONTENT_CONFLICT"):
        rollover_terminal_overlay(
            predecessor_receipt_path=predecessor_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
            allowed_parent=private_parent,
            successor_root=fork_root,
            successor_overlay_output_id="OVERLAY-EPOCH4-0003",
            timestamp="2026-08-29T00:00:05Z",
        )
    assert not fork_root.exists()
    predecessor_state = verify_overlay(
        predecessor_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
    )["state"]
    assert predecessor_state["phase"] == "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
    assert predecessor_state["hard_stop"] is True
    assert predecessor_state["decode_authorized"] is False
    assert {
        path.name: path.read_bytes()
        for path in [
            predecessor_root / "event-000006.json",
            predecessor_root / "state-000006.json",
            predecessor_root / "receipt-000006.json",
        ]
    } == predecessor_bytes
    with pytest.raises(ExecutionOverlayError, match="ORDINAL_MISMATCH"):
        prepare_dispatch(
            receipt_path=successor.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            ordinal="CAL-REQ-002",
            action_id="ACTION-CAL-REQ-002-RETRY",
            expected_output_opaque_id="OUTPUT-CAL-REQ-002-RETRY",
            timestamp="2026-08-29T00:00:06Z",
        )
    rollover_parameters = inspect.signature(rollover_terminal_overlay).parameters
    assert "next_unused_ordinal" not in rollover_parameters
    assert "counters" not in rollover_parameters
    assert "rollover_intent_id" not in rollover_parameters
    assert "project_worktree_root" in rollover_parameters


@pytest.mark.skipif(os.name == "nt", reason="POSIX rollover reparse race probe")
def test_terminal_rollover_rejects_private_parent_reparse_after_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    predecessor_root, predecessor_receipt = _terminal_registration_failure(tmp_path)
    private_parent = predecessor_root.parent
    held_parent = tmp_path / ".private-handoff-held"
    outside = tmp_path / "outside"
    outside.mkdir()
    successor_root = private_parent / "overlay-task-owned-race"
    original_create = overlay_module._create_new_plain_directory

    def replace_parent_before_directory_create(path: Path) -> None:
        private_parent.rename(held_parent)
        private_parent.symlink_to(outside, target_is_directory=True)
        original_create(path)

    monkeypatch.setattr(
        overlay_module,
        "_create_new_plain_directory",
        replace_parent_before_directory_create,
    )
    with pytest.raises(
        ExecutionOverlayError,
        match="PRIVATE_OVERLAY_DIRECTORY_INVALID",
    ):
        rollover_terminal_overlay(
            predecessor_receipt_path=predecessor_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
            allowed_parent=private_parent,
            successor_root=successor_root,
            successor_overlay_output_id="OVERLAY-EPOCH4-RACE",
            timestamp="2026-08-29T00:00:05Z",
        )
    assert not any(outside.iterdir())
    assert not (held_parent / successor_root.name).exists()


@pytest.mark.parametrize(
    "crash_point",
    ["intent", "directories", "event", "state", "receipt"],
)
def test_terminal_rollover_partial_root_recovers_in_fresh_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_point: str,
) -> None:
    predecessor_root, predecessor_receipt = _terminal_registration_failure(tmp_path)
    private_parent = predecessor_root.parent
    successor_root = private_parent / "overlay-task-owned-0002"
    original_json_write = overlay_module._write_json_create_or_verify_exact
    original_directory = overlay_module._create_or_verify_plain_directory

    def injected_json_crash(path: Path, value: dict[str, Any]) -> tuple[str, int]:
        result = original_json_write(path, value)
        targets = {
            "event": "event-000000.json",
            "state": "state-000000.json",
            "receipt": "receipt-000000.json",
        }
        if targets.get(crash_point) == path.name or (
            crash_point == "intent" and path.name.startswith("rollover-intent-")
        ):
            raise RuntimeError(f"INJECTED_ROLLOVER_{crash_point.upper()}_CRASH")
        return result

    def injected_directory_crash(path: Path) -> None:
        original_directory(path)
        if crash_point == "directories" and path.name == "records":
            raise RuntimeError("INJECTED_ROLLOVER_DIRECTORIES_CRASH")

    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        injected_json_crash,
    )
    monkeypatch.setattr(
        overlay_module,
        "_create_or_verify_plain_directory",
        injected_directory_crash,
    )
    with pytest.raises(RuntimeError, match="INJECTED_ROLLOVER_"):
        rollover_terminal_overlay(
            predecessor_receipt_path=predecessor_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
            allowed_parent=private_parent,
            successor_root=successor_root,
            successor_overlay_output_id="OVERLAY-EPOCH4-0002",
            timestamp="2026-08-29T00:00:05Z",
        )
    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        original_json_write,
    )
    monkeypatch.setattr(
        overlay_module,
        "_create_or_verify_plain_directory",
        original_directory,
    )

    api_src, environment = _fresh_process_environment()
    script = """
import sys
from pathlib import Path
from mirror_api.synthetic_dataset.private_execution_overlay import rollover_terminal_overlay

handle = rollover_terminal_overlay(
    predecessor_receipt_path=Path(sys.argv[1]),
    expected_controller_sha256=sys.argv[2],
    project_worktree_root=Path(sys.argv[3]),
    allowed_parent=Path(sys.argv[4]),
    successor_root=Path(sys.argv[5]),
    successor_overlay_output_id="OVERLAY-EPOCH4-0002",
    timestamp="2026-08-29T00:00:05Z",
)
print(handle.receipt_path)
"""
    recovered = subprocess.run(  # noqa: S603 - fixed interpreter and inline test probe
        [
            sys.executable,
            "-c",
            script,
            str(predecessor_receipt),
            CONTROLLER_SHA256,
            str(tmp_path),
            str(private_parent),
            str(successor_root),
        ],
        cwd=api_src.parent,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert recovered.returncode == 0, recovered.stderr
    recovered_receipt = Path(recovered.stdout.strip())
    result = verify_rollover_successor(
        recovered_receipt,
        predecessor_receipt_path=predecessor_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=tmp_path,
    )
    assert recovered_receipt == successor_root / "receipt-000000.json"
    assert result["next_unused_ordinal"] == "CAL-REQ-003"
    assert result["formal_calls_remaining"] == 30
    assert result["formal_raw_capacity_remaining"] == 30
    assert result["global_native_output_capacity_remaining"] == 61
    assert result["global_native_output_consumed"] == 3


def test_terminal_rollover_rejects_nonterminal_wrong_controller_and_tampering(
    tmp_path: Path,
) -> None:
    nonterminal_parent = tmp_path / "nonterminal"
    nonterminal_parent.mkdir()
    nonterminal_root, nonterminal_receipt = _consumed(nonterminal_parent)
    nonterminal_private_parent = nonterminal_root.parent
    with pytest.raises(ExecutionOverlayError, match="ROLLOVER_TERMINAL_PREDECESSOR_INVALID"):
        rollover_terminal_overlay(
            predecessor_receipt_path=nonterminal_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=nonterminal_parent,
            allowed_parent=nonterminal_private_parent,
            successor_root=nonterminal_private_parent / "overlay-task-owned-0002",
            successor_overlay_output_id="OVERLAY-EPOCH4-0002",
            timestamp="2026-08-29T00:00:05Z",
        )

    terminal_parent = tmp_path / "terminal"
    terminal_parent.mkdir()
    predecessor_root, predecessor_receipt = _terminal_registration_failure(terminal_parent)
    terminal_private_parent = predecessor_root.parent
    with pytest.raises(ExecutionOverlayError, match="CONTROLLER_DIGEST_MISMATCH"):
        rollover_terminal_overlay(
            predecessor_receipt_path=predecessor_receipt,
            expected_controller_sha256="b" * 64,
            project_worktree_root=terminal_parent,
            allowed_parent=terminal_private_parent,
            successor_root=terminal_private_parent / "overlay-task-owned-0002",
            successor_overlay_output_id="OVERLAY-EPOCH4-0002",
            timestamp="2026-08-29T00:00:05Z",
        )
    successor = rollover_terminal_overlay(
        predecessor_receipt_path=predecessor_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=terminal_parent,
        allowed_parent=terminal_private_parent,
        successor_root=terminal_private_parent / "overlay-task-owned-0002",
        successor_overlay_output_id="OVERLAY-EPOCH4-0002",
        timestamp="2026-08-29T00:00:05Z",
    )
    (predecessor_root / "event-000006.json").write_bytes(
        (predecessor_root / "event-000006.json").read_bytes() + b" "
    )
    with pytest.raises(ExecutionOverlayError, match="EVENT_DIGEST_MISMATCH"):
        verify_rollover_successor(
            successor.receipt_path,
            predecessor_receipt_path=predecessor_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=terminal_parent,
        )

    intent_parent = tmp_path / "intent-tamper"
    intent_parent.mkdir()
    intent_predecessor_root, intent_predecessor_receipt = _terminal_registration_failure(
        intent_parent
    )
    intent_private_parent = intent_predecessor_root.parent
    intent_successor = rollover_terminal_overlay(
        predecessor_receipt_path=intent_predecessor_receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=intent_parent,
        allowed_parent=intent_private_parent,
        successor_root=intent_private_parent / "overlay-task-owned-0002",
        successor_overlay_output_id="OVERLAY-EPOCH4-0002",
        timestamp="2026-08-29T00:00:05Z",
    )
    intent_state = verify_overlay(
        intent_successor.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )["state"]
    intent_path = (
        intent_private_parent / intent_state["rollover_predecessor"]["rollover_intent_file"]
    )
    intent_path.write_bytes(intent_path.read_bytes() + b" ")
    with pytest.raises(ExecutionOverlayError, match="ROLLOVER_INTENT_DIGEST_MISMATCH"):
        verify_rollover_successor(
            intent_successor.receipt_path,
            predecessor_receipt_path=intent_predecessor_receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=intent_parent,
        )


def test_terminal_rollover_v2_pins_cal_req_003_and_recovers_one_ready_successor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    predecessor_root, predecessor_receipt, kwargs = _rollover_v2_fixture(tmp_path)
    private_parent = predecessor_root.parent
    predecessor_bytes = {
        path.name: path.read_bytes()
        for path in (
            predecessor_root / "event-000006.json",
            predecessor_root / "state-000006.json",
            predecessor_root / "receipt-000006.json",
        )
    }
    with monkeypatch.context() as patch_context:
        patch_context.setattr(
            overlay_module,
            "sha256_file",
            lambda _path: pytest.fail("out-of-scope predecessor was read"),
        )
        with pytest.raises(
            ExecutionOverlayError,
            match="V2_ROLLOVER_PREDECESSOR_ROOT_OUTSIDE_ALLOWED_PARENT",
        ):
            verify_rollover_successor_v2(
                private_parent / "not-created" / "receipt-000000.json",
                predecessor_receipt_path=(
                    tmp_path / "outside-private-parent" / "receipt-000006.json"
                ),
                expected_predecessor_receipt_sha256=kwargs["expected_predecessor_receipt_sha256"],
                expected_predecessor_state_sha256=kwargs["expected_predecessor_state_sha256"],
                expected_predecessor_event_sha256=kwargs["expected_predecessor_event_sha256"],
                expected_controller_sha256=CONTROLLER_SHA256,
                project_worktree_root=tmp_path,
            )
    for pin_name, expected_error in (
        ("expected_predecessor_receipt_sha256", "V2_PREDECESSOR_RECEIPT_DIGEST_MISMATCH"),
        ("expected_predecessor_state_sha256", "V2_PREDECESSOR_CHILD_DIGEST_MISMATCH"),
        ("expected_predecessor_event_sha256", "V2_PREDECESSOR_CHILD_DIGEST_MISMATCH"),
        ("expected_controller_sha256", "CONTROLLER_DIGEST_MISMATCH"),
    ):
        with pytest.raises(ExecutionOverlayError, match=expected_error):
            rollover_terminal_overlay_v2(**{**kwargs, pin_name: "b" * 64})
        assert not kwargs["successor_root"].exists()
        assert not list(private_parent.glob("rollover-v2-intent-*.json"))
    successor = rollover_terminal_overlay_v2(**kwargs)
    assert verify_rollover_successor_v2(
        successor.receipt_path,
        predecessor_receipt_path=predecessor_receipt,
        expected_predecessor_receipt_sha256=kwargs["expected_predecessor_receipt_sha256"],
        expected_predecessor_state_sha256=kwargs["expected_predecessor_state_sha256"],
        expected_predecessor_event_sha256=kwargs["expected_predecessor_event_sha256"],
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=tmp_path,
    ) == {
        "status": "TERMINAL_OVERLAY_ROLLOVER_V2_PASS",
        "successor_overlay_output_id": "OVERLAY-EPOCH4-0104",
        "predecessor_overlay_output_id": "OVERLAY-EPOCH4-0103",
        "next_unused_ordinal": "CAL-REQ-004",
        "formal_calls_remaining": 29,
        "formal_raw_capacity_remaining": 29,
        "global_native_output_capacity_remaining": 60,
        "global_native_output_consumed": 4,
        "decode_authorized": False,
    }
    assert rollover_terminal_overlay_v2(**kwargs) == successor
    with pytest.raises(ExecutionOverlayError, match="CREATE_NEW_EXISTING_CONTENT_CONFLICT"):
        rollover_terminal_overlay_v2(
            **{**kwargs, "successor_root": private_parent / "overlay-task-owned-0105"}
        )
    for changed in (
        {"successor_overlay_output_id": "OVERLAY-EPOCH4-0105"},
        {"timestamp": "2026-08-30T00:00:01Z"},
    ):
        with pytest.raises(ExecutionOverlayError, match="CREATE_NEW_EXISTING_CONTENT_CONFLICT"):
            rollover_terminal_overlay_v2(**{**kwargs, **changed})
    parameters = inspect.signature(rollover_terminal_overlay_v2).parameters
    for forbidden in (
        "counters",
        "next_unused_ordinal",
        "rollover_intent_id",
        "phase",
        "reason_code",
    ):
        assert forbidden not in parameters
    state = cast(
        dict[str, Any],
        verify_overlay(successor.receipt_path, expected_controller_sha256=CONTROLLER_SHA256)[
            "state"
        ],
    )
    assert state["phase"] == "READY"
    assert state["next_unused_ordinal"] == "CAL-REQ-004"
    assert state["output_registration"] is None
    assert not (successor.receipt_path.parent / "receipt-000001.json").exists()
    assert not any((successor.receipt_path.parent / "staging").iterdir())
    assert not any((successor.receipt_path.parent / "records").iterdir())
    assert {
        path.name: path.read_bytes()
        for path in (
            predecessor_root / "event-000006.json",
            predecessor_root / "state-000006.json",
            predecessor_root / "receipt-000006.json",
        )
    } == predecessor_bytes


@pytest.mark.parametrize(
    ("directory_name", "entry_kind"),
    [("staging", "file"), ("records", "directory")],
)
def test_terminal_rollover_v2_verification_rejects_any_successor_work_entry_without_echo(
    tmp_path: Path,
    directory_name: str,
    entry_kind: str,
) -> None:
    _predecessor_root, predecessor_receipt, kwargs = _rollover_v2_fixture(tmp_path)
    successor = rollover_terminal_overlay_v2(**kwargs)
    injected = successor.receipt_path.parent / directory_name / "untrusted-entry-token.bin"
    if entry_kind == "file":
        injected.write_bytes(b"synthetic-private-placeholder")
    else:
        injected.mkdir()

    with pytest.raises(
        ExecutionOverlayError,
        match="V2_ROLLOVER_SUCCESSOR_DIRECTORY_NOT_EMPTY",
    ) as error:
        verify_rollover_successor_v2(
            successor.receipt_path,
            predecessor_receipt_path=predecessor_receipt,
            expected_predecessor_receipt_sha256=cast(
                str, kwargs["expected_predecessor_receipt_sha256"]
            ),
            expected_predecessor_state_sha256=cast(
                str, kwargs["expected_predecessor_state_sha256"]
            ),
            expected_predecessor_event_sha256=cast(
                str, kwargs["expected_predecessor_event_sha256"]
            ),
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
        )
    assert injected.name not in str(error.value)


def test_terminal_rollover_v2_partial_recovery_rejects_prepopulated_work_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _predecessor_root, _predecessor_receipt, kwargs = _rollover_v2_fixture(tmp_path)
    original_directory = overlay_module._create_or_verify_plain_directory

    def crash_after_directories(path: Path) -> None:
        original_directory(path)
        if path.name == "records":
            raise RuntimeError("INJECTED_V2_ROLLOVER_DIRECTORIES_CRASH")

    monkeypatch.setattr(
        overlay_module,
        "_create_or_verify_plain_directory",
        crash_after_directories,
    )
    with pytest.raises(RuntimeError, match="INJECTED_V2_ROLLOVER_DIRECTORIES_CRASH"):
        rollover_terminal_overlay_v2(**kwargs)
    monkeypatch.setattr(
        overlay_module,
        "_create_or_verify_plain_directory",
        original_directory,
    )
    successor_root = cast(Path, kwargs["successor_root"])
    injected = successor_root / "staging" / "untrusted-partial-recovery.bin"
    injected.write_bytes(b"synthetic-private-placeholder")

    with pytest.raises(
        ExecutionOverlayError,
        match="V2_ROLLOVER_SUCCESSOR_DIRECTORY_NOT_EMPTY",
    ) as error:
        rollover_terminal_overlay_v2(**kwargs)
    assert injected.name not in str(error.value)
    assert not (successor_root / "event-000000.json").exists()
    assert not (successor_root / "state-000000.json").exists()
    assert not (successor_root / "receipt-000000.json").exists()


def test_terminal_rollover_v2_rejects_entry_race_before_initial_empty_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _predecessor_root, _predecessor_receipt, kwargs = _rollover_v2_fixture(tmp_path)
    successor_root = cast(Path, kwargs["successor_root"])
    original_scandir = overlay_module.os.scandir
    injected = False

    def inject_before_scan(path: str | bytes | int | os.PathLike[str] | os.PathLike[bytes]):
        nonlocal injected
        if not injected:
            (successor_root / "records" / "untrusted-race-entry.bin").write_bytes(
                b"synthetic-private-placeholder"
            )
            injected = True
        return original_scandir(path)

    monkeypatch.setattr(overlay_module.os, "scandir", inject_before_scan)
    with pytest.raises(
        ExecutionOverlayError,
        match="V2_ROLLOVER_SUCCESSOR_DIRECTORY_NOT_EMPTY",
    ):
        rollover_terminal_overlay_v2(**kwargs)
    assert not (successor_root / "event-000000.json").exists()
    assert not (successor_root / "state-000000.json").exists()
    assert not (successor_root / "receipt-000000.json").exists()


def test_terminal_rollover_v2_rechecks_empty_directories_before_verification_returns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _predecessor_root, predecessor_receipt, kwargs = _rollover_v2_fixture(tmp_path)
    successor = rollover_terminal_overlay_v2(**kwargs)
    original_read_json = overlay_module._read_json
    injected = False

    def inject_after_initial_empty_proof(path: Path) -> dict[str, Any]:
        nonlocal injected
        value = original_read_json(path)
        if not injected and path.name.startswith("rollover-v2-intent-"):
            (successor.receipt_path.parent / "records" / "untrusted-verify-race.bin").write_bytes(
                b"synthetic-private-placeholder"
            )
            injected = True
        return value

    monkeypatch.setattr(overlay_module, "_read_json", inject_after_initial_empty_proof)
    with pytest.raises(
        ExecutionOverlayError,
        match="V2_ROLLOVER_SUCCESSOR_DIRECTORY_NOT_EMPTY",
    ):
        verify_rollover_successor_v2(
            successor.receipt_path,
            predecessor_receipt_path=predecessor_receipt,
            expected_predecessor_receipt_sha256=cast(
                str, kwargs["expected_predecessor_receipt_sha256"]
            ),
            expected_predecessor_state_sha256=cast(
                str, kwargs["expected_predecessor_state_sha256"]
            ),
            expected_predecessor_event_sha256=cast(
                str, kwargs["expected_predecessor_event_sha256"]
            ),
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
        )


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        (("event", "reason_code", "OTHER"), "reason"),
        (("state", "current_ordinal", "CAL-REQ-004"), "ordinal"),
        (("state", "counters", {}), "counters"),
        (("state", "output_registration_attempt", {"source_kind": "OTHER"}), "native"),
    ],
)
def test_terminal_rollover_v2_rejects_semantic_predecessor_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: tuple[str, str, Any],
    field: str,
) -> None:
    root, predecessor_receipt = _terminal_registration_failure_v2(tmp_path)
    verified = verify_overlay(predecessor_receipt, expected_controller_sha256=CONTROLLER_SHA256)
    forged = json.loads(json.dumps(verified))
    forged[mutation[0]][mutation[1]] = mutation[2]
    monkeypatch.setattr(overlay_module, "verify_overlay", lambda *_args, **_kwargs: forged)
    receipt = cast(dict[str, Any], verified["receipt"])
    with pytest.raises(ExecutionOverlayError, match="V2_ROLLOVER_TERMINAL_PREDECESSOR_INVALID"):
        overlay_module._verified_terminal_rollover_predecessor_v2(
            predecessor_receipt,
            expected_predecessor_receipt_sha256=overlay_module.sha256_file(predecessor_receipt),
            expected_predecessor_state_sha256=receipt["state_sha256"],
            expected_predecessor_event_sha256=receipt["event_sha256"],
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
            allowed_parent=root.parent,
        )
    assert field in {"reason", "ordinal", "counters", "native"}


@pytest.mark.parametrize(
    "crash_point",
    ["intent", "directories", "event", "state", "receipt"],
)
def test_terminal_rollover_v2_partial_root_recovers_in_fresh_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_point: str,
) -> None:
    _predecessor_root, predecessor_receipt, kwargs = _rollover_v2_fixture(tmp_path)
    original_json_write = overlay_module._write_json_create_or_verify_exact
    original_directory = overlay_module._create_or_verify_plain_directory

    def injected_json_crash(path: Path, value: dict[str, Any]) -> tuple[str, int]:
        result = original_json_write(path, value)
        targets = {
            "event": "event-000000.json",
            "state": "state-000000.json",
            "receipt": "receipt-000000.json",
        }
        if targets.get(crash_point) == path.name or (
            crash_point == "intent" and path.name.startswith("rollover-v2-intent-")
        ):
            raise RuntimeError(f"INJECTED_V2_ROLLOVER_{crash_point.upper()}_CRASH")
        return result

    def injected_directory_crash(path: Path) -> None:
        original_directory(path)
        if crash_point == "directories" and path.name == "records":
            raise RuntimeError("INJECTED_V2_ROLLOVER_DIRECTORIES_CRASH")

    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        injected_json_crash,
    )
    monkeypatch.setattr(
        overlay_module,
        "_create_or_verify_plain_directory",
        injected_directory_crash,
    )
    with pytest.raises(RuntimeError, match="INJECTED_V2_ROLLOVER_"):
        rollover_terminal_overlay_v2(**kwargs)
    monkeypatch.setattr(
        overlay_module,
        "_write_json_create_or_verify_exact",
        original_json_write,
    )
    monkeypatch.setattr(
        overlay_module,
        "_create_or_verify_plain_directory",
        original_directory,
    )

    api_src, environment = _fresh_process_environment()
    script = """
import sys
from pathlib import Path
from mirror_api.synthetic_dataset.private_execution_overlay import rollover_terminal_overlay_v2

handle = rollover_terminal_overlay_v2(
    predecessor_receipt_path=Path(sys.argv[1]),
    expected_predecessor_receipt_sha256=sys.argv[2],
    expected_predecessor_state_sha256=sys.argv[3],
    expected_predecessor_event_sha256=sys.argv[4],
    expected_controller_sha256=sys.argv[5],
    project_worktree_root=Path(sys.argv[6]),
    allowed_parent=Path(sys.argv[7]),
    successor_root=Path(sys.argv[8]),
    successor_overlay_output_id=sys.argv[9],
    timestamp=sys.argv[10],
)
print(handle.receipt_path)
"""
    recovered = subprocess.run(  # noqa: S603 - fixed interpreter and inline test probe
        [
            sys.executable,
            "-c",
            script,
            str(predecessor_receipt),
            cast(str, kwargs["expected_predecessor_receipt_sha256"]),
            cast(str, kwargs["expected_predecessor_state_sha256"]),
            cast(str, kwargs["expected_predecessor_event_sha256"]),
            CONTROLLER_SHA256,
            str(tmp_path),
            str(kwargs["allowed_parent"]),
            str(kwargs["successor_root"]),
            cast(str, kwargs["successor_overlay_output_id"]),
            cast(str, kwargs["timestamp"]),
        ],
        cwd=api_src.parent,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert recovered.returncode == 0, recovered.stderr
    recovered_receipt = Path(recovered.stdout.strip())
    result = verify_rollover_successor_v2(
        recovered_receipt,
        predecessor_receipt_path=predecessor_receipt,
        expected_predecessor_receipt_sha256=cast(
            str, kwargs["expected_predecessor_receipt_sha256"]
        ),
        expected_predecessor_state_sha256=cast(str, kwargs["expected_predecessor_state_sha256"]),
        expected_predecessor_event_sha256=cast(str, kwargs["expected_predecessor_event_sha256"]),
        expected_controller_sha256=CONTROLLER_SHA256,
        project_worktree_root=tmp_path,
    )
    assert recovered_receipt == cast(Path, kwargs["successor_root"]) / "receipt-000000.json"
    assert result["next_unused_ordinal"] == "CAL-REQ-004"
    assert result["formal_calls_remaining"] == 29


@pytest.mark.parametrize(
    ("target", "expected_error"),
    [
        ("predecessor-event", "OVERLAY_EVENT_DIGEST_MISMATCH"),
        ("intent", "V2_ROLLOVER_INTENT_DIGEST_MISMATCH"),
        ("successor-event", "OVERLAY_EVENT_DIGEST_MISMATCH"),
        ("successor-state", "OVERLAY_STATE_DIGEST_MISMATCH"),
        ("successor-receipt", "V2_ROLLOVER_SUCCESSOR_RECEIPT_NOT_CANONICAL"),
    ],
)
def test_terminal_rollover_v2_rejects_predecessor_intent_and_successor_tamper(
    tmp_path: Path,
    target: str,
    expected_error: str,
) -> None:
    predecessor_root, predecessor_receipt, kwargs = _rollover_v2_fixture(tmp_path)
    successor = rollover_terminal_overlay_v2(**kwargs)
    successor_state = verify_overlay(
        successor.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )["state"]
    paths = {
        "predecessor-event": predecessor_root / "event-000006.json",
        "intent": predecessor_root.parent
        / cast(dict[str, Any], successor_state["rollover_predecessor"])["rollover_intent_file"],
        "successor-event": successor.receipt_path.parent / "event-000000.json",
        "successor-state": successor.receipt_path.parent / "state-000000.json",
        "successor-receipt": successor.receipt_path,
    }
    paths[target].write_bytes(paths[target].read_bytes() + b" ")
    with pytest.raises(ExecutionOverlayError, match=expected_error):
        verify_rollover_successor_v2(
            successor.receipt_path,
            predecessor_receipt_path=predecessor_receipt,
            expected_predecessor_receipt_sha256=cast(
                str, kwargs["expected_predecessor_receipt_sha256"]
            ),
            expected_predecessor_state_sha256=cast(
                str, kwargs["expected_predecessor_state_sha256"]
            ),
            expected_predecessor_event_sha256=cast(
                str, kwargs["expected_predecessor_event_sha256"]
            ),
            expected_controller_sha256=CONTROLLER_SHA256,
            project_worktree_root=tmp_path,
        )


@pytest.mark.skipif(os.name == "nt", reason="POSIX v2 rollover reparse race probe")
def test_terminal_rollover_v2_rejects_private_parent_reparse_after_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    predecessor_root, _predecessor_receipt, kwargs = _rollover_v2_fixture(tmp_path)
    private_parent = predecessor_root.parent
    held_parent = tmp_path / ".private-handoff-held-v2"
    outside = tmp_path / "outside-v2"
    outside.mkdir()
    original_create = overlay_module._create_new_plain_directory

    def replace_parent_before_directory_create(path: Path) -> None:
        private_parent.rename(held_parent)
        private_parent.symlink_to(outside, target_is_directory=True)
        original_create(path)

    monkeypatch.setattr(
        overlay_module,
        "_create_new_plain_directory",
        replace_parent_before_directory_create,
    )
    with pytest.raises(ExecutionOverlayError, match="PRIVATE_OVERLAY_DIRECTORY_INVALID"):
        rollover_terminal_overlay_v2(**kwargs)
    assert not any(outside.iterdir())
    assert not (held_parent / cast(Path, kwargs["successor_root"]).name).exists()


def test_private_prompt_rendering_is_deterministic_and_requires_prohibition() -> None:
    template = {
        "plaintext_export": "PROHIBITED",
        "status": "MATERIALIZED_NOT_RENDERED_NOT_DISPATCHED",
        "policy_digest": POLICY_DIGEST,
        "render_placeholders": [
            "REQUEST_ORDINAL",
            "DECLARED_AGE_BAND",
            "MORPHOLOGY_DESCRIPTOR",
            "STYLE_DESCRIPTOR",
        ],
        "positive_segments": [
            [
                "synthetic non-real subject",
                "ordinal {REQUEST_ORDINAL}",
                "{DECLARED_AGE_BAND}",
            ],
            ["morphology {MORPHOLOGY_DESCRIPTOR}", "style {STYLE_DESCRIPTOR}"],
        ],
        "negative_segments": [["no real person", "no text"]],
    }
    assignment = {
        "ordinal": "CAL-REQ-002",
        "declared_age_band": "ADULT_20_25",
        "morphology": "UPPER_HIGH",
        "style_family": "GENTLE_SOFT",
        "status": "NOT_CONSUMED",
        "retryable": False,
        "policy_binding": POLICY_DIGEST,
    }
    rendered = render_private_prompt(
        prompt_template=template,
        assignment_entry=assignment,
        ordinal="CAL-REQ-002",
        expected_policy_digest=POLICY_DIGEST,
    )
    assert rendered == (
        "REQUEST_ORDINAL: CAL-REQ-002\n"
        "POSITIVE_CONSTRAINT_GROUPS:\n"
        "1. synthetic non-real subject; ordinal CAL-REQ-002; ADULT_20_25\n"
        "2. morphology UPPER_HIGH; style GENTLE_SOFT\n"
        "NEGATIVE_CONSTRAINT_GROUPS:\n"
        "1. no real person; no text"
    )
    with pytest.raises(ExecutionOverlayError, match="EXPORT_POLICY_INVALID"):
        render_private_prompt(
            prompt_template={**template, "plaintext_export": "ALLOWED"},
            assignment_entry=assignment,
            ordinal="CAL-REQ-002",
            expected_policy_digest=POLICY_DIGEST,
        )

    escaped = render_private_prompt(
        prompt_template={
            **template,
            "positive_segments": [["literal {{braces}} and {REQUEST_ORDINAL}"]],
        },
        assignment_entry=assignment,
        ordinal="CAL-REQ-002",
        expected_policy_digest=POLICY_DIGEST,
    )
    assert "literal {braces} and CAL-REQ-002" in escaped

    for invalid_segment in (
        "{UNKNOWN_PLACEHOLDER}",
        "{REQUEST_ORDINAL[invalid]}",
        "{REQUEST_ORDINAL[0]}",
        "{REQUEST_ORDINAL.__class__.__name__}",
        "{0}",
        "{REQUEST_ORDINAL!r}",
        "{REQUEST_ORDINAL:>10}",
    ):
        with pytest.raises(
            ExecutionOverlayError,
            match="PRIVATE_PROMPT_PLACEHOLDER_RENDER_FAILED",
        ):
            render_private_prompt(
                prompt_template={
                    **template,
                    "positive_segments": [[invalid_segment]],
                },
                assignment_entry=assignment,
                ordinal="CAL-REQ-002",
                expected_policy_digest=POLICY_DIGEST,
            )


def test_controller_uses_no_directory_discovery_primitive() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "mirror_api"
        / "synthetic_dataset"
        / "private_execution_overlay.py"
    )
    source = module_path.read_text(encoding="utf-8")
    assert ".iterdir(" not in source
    assert ".glob(" not in source
    assert ".rglob(" not in source
    assert "os.walk(" not in source
    assert "import requests" not in source
    assert "import urllib" not in source
    assert "import socket" not in source
    assert "import subprocess" not in source
    assert "from PIL" not in source
    assert "import PIL" not in source
    assert "Image.open(" not in source
    assert "imagegen__" not in source
    assert "with generated_artifact_path.open" not in source
    assert "generated_artifact_path.stat()" not in source
    assert "O_NOFOLLOW" in source
    assert "CreateFileW" in source
