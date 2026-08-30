from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib
import json
import os
import re
import stat
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, Final, Protocol, TextIO, cast

from mirror_api.synthetic_dataset.private_execution_overlay import (
    MAX_DATA_URL_ENCODED_BYTES,
    ExecutionOverlayError,
    _is_v2_successor_state,
    _validate_project_local_private_parent,
    _write_json_create_or_verify_exact,
    record_output_returned,
    register_imagegen_data_url_before_decode,
    v2_quiescence_lease_for_receipt,
    verify_overlay,
    verify_registration_before_decode,
)

CAPTURE_SESSION_SCHEMA: Final = "mirror.p2-m5/PrivateImageGenCaptureSession/v1"
CAPTURE_SESSION_SCHEMA_V2: Final = "mirror.p2-m5/PrivateImageGenCaptureSession/v2"
CAPTURE_COMPLETION_SCHEMA: Final = "mirror.p2-m5/PrivateImageGenCaptureCompletion/v1"
MAX_CAPTURE_HANDLE_BYTES: Final = 64 * 1024
MAX_DATA_URL_LINE_BYTES: Final = MAX_DATA_URL_ENCODED_BYTES + 64
_HANDLE_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
_EXPECTED_HANDLE_KEYS_V1: Final = frozenset(
    {
        "schema_version",
        "handle_id",
        "task_id",
        "ordinal",
        "action_id",
        "expected_output_opaque_id",
        "receipt_relative",
        "receipt_sha256",
        "controller_sha256",
        "returned_timestamp",
        "registration_timestamp",
        "allowed_use",
        "plaintext_persistence",
        "upload_to_github",
    }
)
_EXPECTED_HANDLE_KEYS_V2: Final = _EXPECTED_HANDLE_KEYS_V1 | {"state_sha256"}


class PrivateImageGenCaptureError(RuntimeError):
    pass


class _TermiosModule(Protocol):
    ECHO: int
    ECHONL: int
    TCSANOW: int

    def tcgetattr(self, file_descriptor: int) -> list[Any]: ...

    def tcsetattr(
        self,
        file_descriptor: int,
        when: int,
        attributes: list[Any],
    ) -> None: ...


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_plain_file(path: Path) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_FILE_UNAVAILABLE") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_FILE_INVALID")


def _validate_digest(value: object, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise PrivateImageGenCaptureError(f"{field}_INVALID")
    return value


def _sanitized_reason_code(
    error: PrivateImageGenCaptureError | ExecutionOverlayError | OSError,
) -> str:
    if isinstance(error, PrivateImageGenCaptureError):
        reason_code = str(error)
        if re.fullmatch(r"[A-Z0-9_]{3,128}", reason_code) is not None:
            return reason_code
        return "PRIVATE_CAPTURE_FAILURE"
    if isinstance(error, OSError):
        return "PRIVATE_CAPTURE_IO_FAILURE"
    return "PRIVATE_CAPTURE_EXECUTION_OVERLAY_FAILURE"


def _private_parent(project_worktree_root: Path) -> Path:
    private_parent = project_worktree_root / ".private-handoff"
    try:
        _validate_project_local_private_parent(
            project_worktree_root=project_worktree_root,
            allowed_parent=private_parent,
        )
    except ExecutionOverlayError as error:
        raise PrivateImageGenCaptureError("PROJECT_PRIVATE_PARENT_INVALID") from error
    return private_parent


def _verified_consumed_state(
    receipt_path: Path,
    *,
    controller_sha256: str,
    ordinal: str,
    action_id: str,
    expected_output_opaque_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        verified = verify_overlay(
            receipt_path,
            expected_controller_sha256=controller_sha256,
        )
    except ExecutionOverlayError as error:
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_OVERLAY_INVALID") from error
    receipt = cast(dict[str, Any], verified["receipt"])
    state = cast(dict[str, Any], verified["state"])
    if (
        state.get("phase") != "DISPATCH_STARTED_CONSUMED"
        or state.get("hard_stop") is not False
        or state.get("decode_authorized") is not False
        or state.get("current_ordinal") != ordinal
        or state.get("current_action_id") != action_id
        or state.get("expected_output_opaque_id") != expected_output_opaque_id
        or state.get("returned_output_binding") is not None
        or state.get("output_registration_attempt") is not None
        or state.get("output_registration") is not None
    ):
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_OVERLAY_NOT_CONSUMED")
    sequence = receipt.get("sequence")
    if not isinstance(sequence, int) or sequence < 0 or state.get("sequence") != sequence:
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_OVERLAY_INVALID")
    for prefix in ("event", "state", "receipt"):
        successor_path = receipt_path.parent / f"{prefix}-{sequence + 1:06d}.json"
        try:
            successor_path.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise PrivateImageGenCaptureError("CAPTURE_SESSION_TIP_CHECK_FAILED") from error
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_STALE_RECEIPT")
    return state, receipt


def create_capture_session_handle(
    *,
    project_worktree_root: Path,
    handle_id: str,
    task_id: str,
    receipt_path: Path,
    controller_sha256: str,
    ordinal: str,
    action_id: str,
    expected_output_opaque_id: str,
    returned_timestamp: str,
    registration_timestamp: str,
) -> Path:
    with v2_quiescence_lease_for_receipt(
        receipt_path=receipt_path, expected_controller_sha256=controller_sha256
    ):
        return _create_capture_session_handle_unleased(
            project_worktree_root=project_worktree_root,
            handle_id=handle_id,
            task_id=task_id,
            receipt_path=receipt_path,
            controller_sha256=controller_sha256,
            ordinal=ordinal,
            action_id=action_id,
            expected_output_opaque_id=expected_output_opaque_id,
            returned_timestamp=returned_timestamp,
            registration_timestamp=registration_timestamp,
        )


def _create_capture_session_handle_unleased(
    *,
    project_worktree_root: Path,
    handle_id: str,
    task_id: str,
    receipt_path: Path,
    controller_sha256: str,
    ordinal: str,
    action_id: str,
    expected_output_opaque_id: str,
    returned_timestamp: str,
    registration_timestamp: str,
) -> Path:
    if _HANDLE_ID.fullmatch(handle_id) is None:
        raise PrivateImageGenCaptureError("CAPTURE_HANDLE_ID_INVALID")
    private_parent = _private_parent(project_worktree_root)
    _validate_digest(controller_sha256, "CONTROLLER_SHA256")
    resolved_receipt = receipt_path.resolve()
    try:
        relative_receipt = resolved_receipt.relative_to(private_parent.resolve())
    except ValueError as error:
        raise PrivateImageGenCaptureError("CAPTURE_RECEIPT_OUTSIDE_PRIVATE_PARENT") from error
    _require_plain_file(resolved_receipt)
    state, receipt = _verified_consumed_state(
        resolved_receipt,
        controller_sha256=controller_sha256,
        ordinal=ordinal,
        action_id=action_id,
        expected_output_opaque_id=expected_output_opaque_id,
    )
    is_v2 = _is_v2_successor_state(state)
    handle: dict[str, Any] = {
        "schema_version": CAPTURE_SESSION_SCHEMA_V2 if is_v2 else CAPTURE_SESSION_SCHEMA,
        "handle_id": handle_id,
        "task_id": task_id,
        "ordinal": ordinal,
        "action_id": action_id,
        "expected_output_opaque_id": expected_output_opaque_id,
        "receipt_relative": relative_receipt.as_posix(),
        "receipt_sha256": _sha256_file(resolved_receipt),
        "controller_sha256": controller_sha256,
        "returned_timestamp": returned_timestamp,
        "registration_timestamp": registration_timestamp,
        "allowed_use": "ONE_EXACT_CODEX_NATIVE_IMAGEGEN_DATA_URL_CAPTURE",
        "plaintext_persistence": "PROHIBITED",
        "upload_to_github": False,
    }
    if is_v2:
        handle["state_sha256"] = _validate_digest(receipt.get("state_sha256"), "STATE_SHA256")
    handle_path = private_parent / f"{handle_id}.json"
    try:
        _write_json_create_or_verify_exact(handle_path, handle)
    except ExecutionOverlayError as error:
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_WRITE_FAILED") from error
    if handle_path.read_bytes() != _canonical_json_bytes(handle):
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_CANONICALIZATION_FAILED")
    return handle_path


def load_capture_session(
    *, project_worktree_root: Path, handle_id: str
) -> tuple[dict[str, Any], Path]:
    if _HANDLE_ID.fullmatch(handle_id) is None:
        raise PrivateImageGenCaptureError("CAPTURE_HANDLE_ID_INVALID")
    private_parent = _private_parent(project_worktree_root)
    handle_path = private_parent / f"{handle_id}.json"
    _require_plain_file(handle_path)
    try:
        handle_bytes = handle_path.read_bytes()
    except OSError as error:
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_READ_FAILED") from error
    if len(handle_bytes) > MAX_CAPTURE_HANDLE_BYTES:
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_SIZE_INVALID")
    try:
        handle = json.loads(handle_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_JSON_INVALID") from error
    if not isinstance(handle, dict):
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_SHAPE_INVALID")
    schema_version = handle.get("schema_version")
    if schema_version == CAPTURE_SESSION_SCHEMA:
        expected_handle_keys = _EXPECTED_HANDLE_KEYS_V1
    elif schema_version == CAPTURE_SESSION_SCHEMA_V2:
        expected_handle_keys = _EXPECTED_HANDLE_KEYS_V2
    else:
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_AUTHORITY_INVALID")
    if frozenset(handle) != expected_handle_keys:
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_SHAPE_INVALID")
    if handle_bytes != _canonical_json_bytes(handle):
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_NOT_CANONICAL")
    if (
        handle.get("handle_id") != handle_id
        or handle.get("allowed_use") != "ONE_EXACT_CODEX_NATIVE_IMAGEGEN_DATA_URL_CAPTURE"
        or handle.get("plaintext_persistence") != "PROHIBITED"
        or handle.get("upload_to_github") is not False
    ):
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_AUTHORITY_INVALID")
    completion_path = private_parent / f"{handle_id}.completed.json"
    if completion_path.exists() or completion_path.is_symlink():
        _require_plain_file(completion_path)
        try:
            completion_bytes = completion_path.read_bytes()
            completion = json.loads(completion_bytes.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise PrivateImageGenCaptureError("CAPTURE_COMPLETION_INVALID") from error
        common_valid = (
            isinstance(completion, dict)
            and completion_bytes == _canonical_json_bytes(completion)
            and completion.get("schema_version") == CAPTURE_COMPLETION_SCHEMA
            and completion.get("handle_id") == handle_id
            and completion.get("session_handle_sha256") == hashlib.sha256(handle_bytes).hexdigest()
            and completion.get("decode_performed") is False
            and completion.get("dimensions_read") is False
            and completion.get("upload_to_github") is False
        )
        success_valid = common_valid and completion.get("status") == "REGISTER_BEFORE_DECODE_PASS"
        failure_reason = completion.get("reason_code")
        failure_valid = (
            common_valid
            and completion.get("status") == "FAIL_CLOSED"
            and isinstance(completion.get("failure_phase"), str)
            and isinstance(failure_reason, str)
            and re.fullmatch(r"[A-Z0-9_]{3,128}", failure_reason) is not None
            and isinstance(completion.get("last_receipt_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", completion["last_receipt_sha256"]) is not None
        )
        if not success_valid and not failure_valid:
            raise PrivateImageGenCaptureError("CAPTURE_COMPLETION_INVALID")
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_ALREADY_COMPLETED")
    controller_sha256 = _validate_digest(handle.get("controller_sha256"), "CONTROLLER_SHA256")
    receipt_sha256 = _validate_digest(handle.get("receipt_sha256"), "RECEIPT_SHA256")
    receipt_relative = handle.get("receipt_relative")
    if not isinstance(receipt_relative, str):
        raise PrivateImageGenCaptureError("CAPTURE_RECEIPT_RELATIVE_INVALID")
    relative_path = Path(receipt_relative)
    if relative_path.is_absolute() or ".." in relative_path.parts or not relative_path.parts:
        raise PrivateImageGenCaptureError("CAPTURE_RECEIPT_RELATIVE_INVALID")
    receipt_path = private_parent.joinpath(*relative_path.parts)
    try:
        receipt_path.resolve().relative_to(private_parent.resolve())
    except ValueError as error:
        raise PrivateImageGenCaptureError("CAPTURE_RECEIPT_OUTSIDE_PRIVATE_PARENT") from error
    _require_plain_file(receipt_path)
    if _sha256_file(receipt_path) != receipt_sha256:
        raise PrivateImageGenCaptureError("CAPTURE_RECEIPT_DIGEST_MISMATCH")
    for field in ("task_id", "ordinal", "action_id", "expected_output_opaque_id"):
        if not isinstance(handle.get(field), str) or not handle[field]:
            raise PrivateImageGenCaptureError(f"CAPTURE_{field.upper()}_INVALID")
    state, receipt = _verified_consumed_state(
        receipt_path,
        controller_sha256=controller_sha256,
        ordinal=cast(str, handle["ordinal"]),
        action_id=cast(str, handle["action_id"]),
        expected_output_opaque_id=cast(str, handle["expected_output_opaque_id"]),
    )
    state_is_v2 = _is_v2_successor_state(state)
    if state_is_v2 != (schema_version == CAPTURE_SESSION_SCHEMA_V2):
        raise PrivateImageGenCaptureError("CAPTURE_SESSION_HANDLE_VERSION_MISMATCH")
    if state_is_v2:
        state_sha256 = _validate_digest(handle.get("state_sha256"), "STATE_SHA256")
        if receipt.get("state_sha256") != state_sha256:
            raise PrivateImageGenCaptureError("CAPTURE_STATE_DIGEST_MISMATCH")
    return cast(dict[str, Any], handle), receipt_path


def read_bounded_private_line(stream: BinaryIO) -> str:
    line = stream.readline(MAX_DATA_URL_LINE_BYTES + 2)
    if not line.endswith(b"\n"):
        if len(line) > MAX_DATA_URL_LINE_BYTES:
            raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_INPUT_BOUND_EXCEEDED")
        raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_INPUT_INCOMPLETE")
    line = line[:-1]
    if line.endswith(b"\r"):
        line = line[:-1]
    if not line or len(line) > MAX_DATA_URL_LINE_BYTES:
        raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_INPUT_BOUND_EXCEEDED")
    try:
        return line.decode("ascii")
    except UnicodeError as error:
        raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_INPUT_NOT_ASCII") from error


@contextmanager
def no_echo_terminal_input(stream: BinaryIO) -> Iterator[None]:
    if not stream.isatty():
        raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_TTY_REQUIRED")
    file_descriptor = stream.fileno()
    if os.name == "nt":
        ctypes_module = cast(Any, ctypes)
        kernel32 = ctypes_module.windll.kernel32
        std_input_handle = kernel32.GetStdHandle(-10)
        mode = ctypes.c_uint()
        if not kernel32.GetConsoleMode(std_input_handle, ctypes.byref(mode)):
            raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_CONSOLE_MODE_READ_FAILED")
        original_mode = mode.value
        if not kernel32.SetConsoleMode(std_input_handle, original_mode & ~0x0004):
            raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_CONSOLE_ECHO_DISABLE_FAILED")
        try:
            yield
        finally:
            if not kernel32.SetConsoleMode(std_input_handle, original_mode):
                raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_CONSOLE_MODE_RESTORE_FAILED")
        return

    try:
        termios = cast(_TermiosModule, importlib.import_module("termios"))
        original_attributes = termios.tcgetattr(file_descriptor)
        private_attributes = list(original_attributes)
        private_attributes[3] &= ~(termios.ECHO | termios.ECHONL)
        termios.tcsetattr(file_descriptor, termios.TCSANOW, private_attributes)
    except OSError as error:
        raise PrivateImageGenCaptureError("PRIVATE_CAPTURE_TERMINAL_ECHO_DISABLE_FAILED") from error
    try:
        yield
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSANOW, original_attributes)


def capture_active_session(
    *,
    project_worktree_root: Path,
    handle_id: str,
    input_stream: BinaryIO,
    ready_stream: TextIO,
) -> dict[str, Any]:
    _handle, receipt_path = load_capture_session(
        project_worktree_root=project_worktree_root, handle_id=handle_id
    )
    with v2_quiescence_lease_for_receipt(
        receipt_path=receipt_path,
        expected_controller_sha256=cast(str, _handle["controller_sha256"]),
    ):
        return _capture_active_session_unleased(
            project_worktree_root=project_worktree_root,
            handle_id=handle_id,
            input_stream=input_stream,
            ready_stream=ready_stream,
        )


def _capture_active_session_unleased(
    *,
    project_worktree_root: Path,
    handle_id: str,
    input_stream: BinaryIO,
    ready_stream: TextIO,
) -> dict[str, Any]:
    handle, receipt_path = load_capture_session(
        project_worktree_root=project_worktree_root,
        handle_id=handle_id,
    )
    private_parent = _private_parent(project_worktree_root)
    handle_path = private_parent / f"{handle_id}.json"
    completion_path = private_parent / f"{handle_id}.completed.json"
    failure_phase = "READY_NOT_EMITTED"
    last_receipt_path = receipt_path
    ready_emitted = False
    try:
        with no_echo_terminal_input(input_stream):
            ready_stream.write("READY_NO_ECHO\n")
            ready_stream.flush()
            ready_emitted = True
            failure_phase = "INPUT_PENDING"
            data_url = read_bounded_private_line(input_stream)
        failure_phase = "OUTPUT_RETURN_PENDING"
        returned = record_output_returned(
            receipt_path=receipt_path,
            expected_controller_sha256=cast(str, handle["controller_sha256"]),
            action_id=cast(str, handle["action_id"]),
            timestamp=cast(str, handle["returned_timestamp"]),
            returned_output_count=1,
            exact_generated_artifact_receipt=data_url,
        )
        last_receipt_path = returned.receipt_path
        failure_phase = "REGISTRATION_PENDING"
        registered = register_imagegen_data_url_before_decode(
            receipt_path=returned.receipt_path,
            expected_controller_sha256=cast(str, handle["controller_sha256"]),
            action_id=cast(str, handle["action_id"]),
            project_worktree_root=project_worktree_root,
            imagegen_data_url=data_url,
            timestamp=cast(str, handle["registration_timestamp"]),
        )
        last_receipt_path = registered.receipt_path
        failure_phase = "VERIFICATION_PENDING"
        verified = verify_registration_before_decode(
            registered.receipt_path,
            expected_controller_sha256=cast(str, handle["controller_sha256"]),
            project_worktree_root=project_worktree_root,
        )
    except (PrivateImageGenCaptureError, ExecutionOverlayError, OSError) as error:
        if ready_emitted:
            reason_code = _sanitized_reason_code(error)
            failure_completion = {
                "schema_version": CAPTURE_COMPLETION_SCHEMA,
                "handle_id": handle_id,
                "session_handle_sha256": _sha256_file(handle_path),
                "status": "FAIL_CLOSED",
                "failure_phase": failure_phase,
                "reason_code": reason_code,
                "last_receipt_sha256": _sha256_file(last_receipt_path),
                "decode_performed": False,
                "dimensions_read": False,
                "upload_to_github": False,
            }
            try:
                _write_json_create_or_verify_exact(completion_path, failure_completion)
            except ExecutionOverlayError as completion_error:
                raise PrivateImageGenCaptureError(
                    "CAPTURE_COMPLETION_WRITE_FAILED"
                ) from completion_error
        raise
    result = {
        "status": verified["status"],
        "phase": verified["phase"],
        "sequence": verified["sequence"],
        "output_opaque_id": verified["output_opaque_id"],
        "source_sha256": verified["source_sha256"],
        "byte_size": verified["byte_size"],
        "media_type": verified["media_type"],
        "decode_performed": verified["decode_performed"],
        "dimensions_read": verified["dimensions_read"],
        "decode_authorized": verified.get("decode_authorized", False),
        "receipt_sha256": _sha256_file(registered.receipt_path),
    }
    completion = {
        "schema_version": CAPTURE_COMPLETION_SCHEMA,
        "handle_id": handle_id,
        "session_handle_sha256": _sha256_file(handle_path),
        "status": result["status"],
        "output_opaque_id": result["output_opaque_id"],
        "source_sha256": result["source_sha256"],
        "byte_size": result["byte_size"],
        "media_type": result["media_type"],
        "registered_receipt_sha256": result["receipt_sha256"],
        "decode_performed": False,
        "dimensions_read": False,
        "upload_to_github": False,
    }
    try:
        _write_json_create_or_verify_exact(
            completion_path,
            completion,
        )
    except ExecutionOverlayError as error:
        raise PrivateImageGenCaptureError("CAPTURE_COMPLETION_WRITE_FAILED") from error
    return result


def run() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("handle_id")
    arguments = parser.parse_args()
    try:
        result = capture_active_session(
            project_worktree_root=Path.cwd(),
            handle_id=arguments.handle_id,
            input_stream=sys.stdin.buffer,
            ready_stream=sys.stdout,
        )
    except (PrivateImageGenCaptureError, ExecutionOverlayError, OSError) as error:
        print(
            json.dumps(
                {"status": "FAIL_CLOSED", "reason_code": _sanitized_reason_code(error)},
                separators=(",", ":"),
            ),
            flush=True,
        )
        raise SystemExit(1) from error
    print(json.dumps(result, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    run()
