from __future__ import annotations

import base64
import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from mirror_api.synthetic_dataset import private_imagegen_capture as capture_module
from mirror_api.synthetic_dataset.private_execution_overlay import (
    GenesisBinding,
    consume_dispatch,
    initialize_overlay,
    prepare_dispatch,
    verify_overlay,
)
from mirror_api.synthetic_dataset.private_imagegen_capture import (
    PrivateImageGenCaptureError,
    capture_active_session,
    create_capture_session_handle,
    load_capture_session,
    no_echo_terminal_input,
    read_bounded_private_line,
)

CONTROLLER_SHA256 = "a" * 64
TIMESTAMP_0 = "2026-08-30T00:00:00Z"
TIMESTAMP_1 = "2026-08-30T00:00:01Z"
TIMESTAMP_2 = "2026-08-30T00:00:02Z"
TIMESTAMP_3 = "2026-08-30T00:00:03Z"
TIMESTAMP_4 = "2026-08-30T00:00:04Z"


def _binding() -> GenesisBinding:
    return GenesisBinding(
        genesis_output_id="GENESIS-R52-0001",
        genesis_bootstrap_sha256="1" * 64,
        genesis_receipt_sha256="2" * 64,
        private_registry_sha256="3" * 64,
        generation_specification_version="generation-v3",
        generation_specification_sha256="4" * 64,
        assignment_manifest_version="assignment-v3",
        assignment_manifest_sha256="5" * 64,
        prompt_template_version="prompt-v3",
        prompt_template_sha256="6" * 64,
        policy_digest="7" * 64,
    )


def _consumed(tmp_path: Path) -> Path:
    (tmp_path / ".git").write_text("gitdir: synthetic-test-worktree\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".private-handoff/\n", encoding="utf-8")
    private_parent = tmp_path / ".private-handoff"
    private_parent.mkdir()
    initialized = initialize_overlay(
        allowed_parent=private_parent,
        root=private_parent / "overlay-r52-task-owned-0001",
        overlay_output_id="OVERLAY-R52-0001",
        controller_sha256=CONTROLLER_SHA256,
        binding=_binding(),
        timestamp=TIMESTAMP_0,
    )
    prepared = prepare_dispatch(
        receipt_path=initialized.receipt_path,
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
    return consumed.receipt_path


def _create_handle(tmp_path: Path) -> Path:
    receipt_path = _consumed(tmp_path)
    return create_capture_session_handle(
        project_worktree_root=tmp_path,
        handle_id="capture-session-r52-0001",
        task_id="P2-M5-R52-TEST",
        receipt_path=receipt_path,
        controller_sha256=CONTROLLER_SHA256,
        ordinal="CAL-REQ-002",
        action_id="ACTION-CAL-REQ-002",
        expected_output_opaque_id="OUTPUT-CAL-REQ-002",
        returned_timestamp=TIMESTAMP_3,
        registration_timestamp=TIMESTAMP_4,
    )


@contextmanager
def _no_echo_fixture(_stream: object) -> Iterator[None]:
    yield


def _data_url(payload: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(payload).decode("ascii")


def test_capture_session_registers_data_url_before_decode_without_plaintext_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle_path = _create_handle(tmp_path)
    handle, receipt_path = load_capture_session(
        project_worktree_root=tmp_path,
        handle_id="capture-session-r52-0001",
    )
    assert handle_path == tmp_path / ".private-handoff" / "capture-session-r52-0001.json"
    assert handle["receipt_sha256"]
    assert receipt_path.name == "receipt-000002.json"

    data_url = _data_url(b"\x89PNG\r\n\x1a\nprivate-r52-transport-fixture")
    monkeypatch.setattr(capture_module, "no_echo_terminal_input", _no_echo_fixture)
    ready_stream = io.StringIO()
    result = capture_active_session(
        project_worktree_root=tmp_path,
        handle_id="capture-session-r52-0001",
        input_stream=io.BytesIO((data_url + "\n").encode("ascii")),
        ready_stream=ready_stream,
    )

    assert ready_stream.getvalue() == "READY_NO_ECHO\n"
    assert result["status"] == "REGISTER_BEFORE_DECODE_PASS"
    assert result["phase"] == "OUTPUT_REGISTERED_PRE_DECODE"
    assert result["output_opaque_id"] == "OUTPUT-CAL-REQ-002"
    assert result["decode_performed"] is False
    assert result["dimensions_read"] is False
    assert result["decode_authorized"] is True
    assert result["byte_size"] == len(b"\x89PNG\r\n\x1a\nprivate-r52-transport-fixture")

    tracked_private_json = b"".join(
        path.read_bytes() for path in (tmp_path / ".private-handoff").rglob("*.json")
    )
    assert data_url.encode("ascii") not in tracked_private_json
    with pytest.raises(
        PrivateImageGenCaptureError,
        match="CAPTURE_SESSION_ALREADY_COMPLETED",
    ):
        load_capture_session(
            project_worktree_root=tmp_path,
            handle_id="capture-session-r52-0001",
        )


def test_capture_session_handle_is_create_or_verify_exact(tmp_path: Path) -> None:
    first = _create_handle(tmp_path)
    first_bytes = first.read_bytes()
    receipt_path = (
        tmp_path / ".private-handoff" / "overlay-r52-task-owned-0001" / ("receipt-000002.json")
    )
    replayed = create_capture_session_handle(
        project_worktree_root=tmp_path,
        handle_id="capture-session-r52-0001",
        task_id="P2-M5-R52-TEST",
        receipt_path=receipt_path,
        controller_sha256=CONTROLLER_SHA256,
        ordinal="CAL-REQ-002",
        action_id="ACTION-CAL-REQ-002",
        expected_output_opaque_id="OUTPUT-CAL-REQ-002",
        returned_timestamp=TIMESTAMP_3,
        registration_timestamp=TIMESTAMP_4,
    )
    assert replayed == first
    assert replayed.read_bytes() == first_bytes


@pytest.mark.parametrize(
    ("payload", "reason_code", "failure_phase"),
    (
        (b"data:image/png;base64,AA==", "PRIVATE_CAPTURE_INPUT_INCOMPLETE", "INPUT_PENDING"),
        (
            b"not-a-data-url\n",
            "PRIVATE_CAPTURE_EXECUTION_OVERLAY_FAILURE",
            "VERIFICATION_PENDING",
        ),
    ),
)
def test_post_ready_failure_is_sanitized_terminal_evidence_and_rejects_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    reason_code: str,
    failure_phase: str,
) -> None:
    _create_handle(tmp_path)
    monkeypatch.setattr(capture_module, "no_echo_terminal_input", _no_echo_fixture)
    ready_stream = io.StringIO()

    with pytest.raises((PrivateImageGenCaptureError, capture_module.ExecutionOverlayError)):
        capture_active_session(
            project_worktree_root=tmp_path,
            handle_id="capture-session-r52-0001",
            input_stream=io.BytesIO(payload),
            ready_stream=ready_stream,
        )

    assert ready_stream.getvalue() == "READY_NO_ECHO\n"
    completion_path = tmp_path / ".private-handoff" / "capture-session-r52-0001.completed.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    assert completion["status"] == "FAIL_CLOSED"
    assert completion["failure_phase"] == failure_phase
    assert completion["reason_code"] == reason_code
    assert completion["decode_performed"] is False
    assert completion["dimensions_read"] is False
    assert payload.rstrip(b"\n") not in completion_path.read_bytes()
    with pytest.raises(PrivateImageGenCaptureError, match="CAPTURE_SESSION_ALREADY_COMPLETED"):
        load_capture_session(
            project_worktree_root=tmp_path,
            handle_id="capture-session-r52-0001",
        )


def test_capture_session_rejects_relative_escape_and_digest_tampering(tmp_path: Path) -> None:
    handle_path = _create_handle(tmp_path)
    handle = json.loads(handle_path.read_text(encoding="utf-8"))
    handle["receipt_relative"] = "../outside/receipt.json"
    handle_path.write_bytes(
        (json.dumps(handle, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    )
    with pytest.raises(PrivateImageGenCaptureError, match="CAPTURE_RECEIPT_RELATIVE_INVALID"):
        load_capture_session(
            project_worktree_root=tmp_path,
            handle_id="capture-session-r52-0001",
        )


def test_private_line_reader_is_bounded_complete_and_ascii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(capture_module, "MAX_DATA_URL_LINE_BYTES", 32)
    assert read_bounded_private_line(io.BytesIO(b"data:image/png;base64,AA==\r\n")) == (
        "data:image/png;base64,AA=="
    )
    with pytest.raises(PrivateImageGenCaptureError, match="PRIVATE_CAPTURE_INPUT_INCOMPLETE"):
        read_bounded_private_line(io.BytesIO(b"data:image/png;base64,AA=="))
    with pytest.raises(PrivateImageGenCaptureError, match="PRIVATE_CAPTURE_INPUT_BOUND_EXCEEDED"):
        read_bounded_private_line(io.BytesIO(b"A" * 34 + b"\n"))
    with pytest.raises(PrivateImageGenCaptureError, match="PRIVATE_CAPTURE_INPUT_NOT_ASCII"):
        read_bounded_private_line(io.BytesIO(b"data:image/png;base64,\xff\n"))


def test_no_echo_transport_requires_a_real_tty() -> None:
    with pytest.raises(PrivateImageGenCaptureError, match="PRIVATE_CAPTURE_TTY_REQUIRED"):
        with no_echo_terminal_input(io.BytesIO(b"")):
            pass


def test_cli_failure_output_never_echoes_private_oserror_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private_locator = r"D:\private-custody\secret-session\payload.bin"

    def _raise_private_oserror(**_kwargs: object) -> dict[str, object]:
        raise OSError(f"cannot read {private_locator}")

    monkeypatch.setattr(capture_module, "capture_active_session", _raise_private_oserror)
    monkeypatch.setattr(capture_module.sys, "argv", ["private-imagegen-capture", "handle-0001"])
    with pytest.raises(SystemExit) as exit_info:
        capture_module.run()

    assert exit_info.value.code == 1
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "status": "FAIL_CLOSED",
        "reason_code": "PRIVATE_CAPTURE_IO_FAILURE",
    }
    assert private_locator not in output


def test_capture_handle_rejects_non_consumed_overlay(tmp_path: Path) -> None:
    receipt_path = _consumed(tmp_path)
    state = verify_overlay(
        receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )["state"]
    assert state["phase"] == "DISPATCH_STARTED_CONSUMED"
    with pytest.raises(PrivateImageGenCaptureError, match="CAPTURE_SESSION_OVERLAY_NOT_CONSUMED"):
        create_capture_session_handle(
            project_worktree_root=tmp_path,
            handle_id="capture-session-r52-wrong-action",
            task_id="P2-M5-R52-TEST",
            receipt_path=receipt_path,
            controller_sha256=CONTROLLER_SHA256,
            ordinal="CAL-REQ-002",
            action_id="ACTION-CAL-REQ-WRONG",
            expected_output_opaque_id="OUTPUT-CAL-REQ-002",
            returned_timestamp=TIMESTAMP_3,
            registration_timestamp=TIMESTAMP_4,
        )
