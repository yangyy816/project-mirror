from __future__ import annotations

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
    register_output_before_decode,
    render_private_prompt,
    verify_overlay,
    verify_registration_before_decode,
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


def _initialized(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "overlay-task-owned-0001"
    handle = initialize_overlay(
        allowed_parent=tmp_path,
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
    assert record["registration_status"] == "COMMITTED"
    assert record["decode_performed"] is False
    assert record["dimensions_read"] is False
    assert "dimensions" not in record
    assert (root / "staging" / "OUTPUT-CAL-REQ-002.raw").read_bytes() == source.read_bytes()


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
    assert "with generated_artifact_path.open" not in source
    assert "generated_artifact_path.stat()" not in source
    assert "O_NOFOLLOW" in source
    assert "CreateFileW" in source
