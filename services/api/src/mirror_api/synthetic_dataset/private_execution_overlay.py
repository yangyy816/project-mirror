from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import stat
import string
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO, Final, cast

OVERLAY_SCHEMA: Final = "mirror.p2-m5/Epoch3ExecutionOverlay/v1"
STATE_SCHEMA: Final = "mirror.p2-m5/Epoch3ExecutionOverlayState/v1"
EVENT_SCHEMA: Final = "mirror.p2-m5/Epoch3ExecutionEvent/v1"
RECEIPT_SCHEMA: Final = "mirror.p2-m5/Epoch3ExecutionReceipt/v1"
OUTPUT_RECORD_SCHEMA: Final = "mirror.p2-m5/PreDecodeOutputRecord/v1"
REGISTRATION_RECEIPT_SCHEMA: Final = "mirror.p2-m5/RegistrationCommitReceipt/v1"
IMAGEGEN_CAPTURE_SIDECAR_SCHEMA: Final = "mirror.p2-m5/ImageGenDataUrlCapture/v1"
ROLLOVER_INTENT_SCHEMA: Final = "mirror.p2-m5/TerminalOverlayRolloverIntent/v1"
MAX_RETURNED_BYTES: Final = 16 * 1024 * 1024
MAX_DATA_URL_ENCODED_BYTES: Final = ((MAX_RETURNED_BYTES + 2) // 3) * 4
MAX_PRIVATE_OVERLAY_FILE_BYTES: Final = MAX_RETURNED_BYTES + (1024 * 1024)
PROJECT_PRIVATE_NAMESPACE: Final = ".private-handoff"
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
_ORDINAL = re.compile(r"^CAL-REQ-(\d{3})$")
_STRICT_BASE64_PAYLOAD = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_IMAGEGEN_DATA_URL_PREFIXES: Final = {
    "data:image/png;base64,": "image/png",
    "data:image/jpeg;base64,": "image/jpeg",
    "data:image/webp;base64,": "image/webp",
}
_FILE_ATTRIBUTE_REPARSE_POINT: Final = 0x400
_FILE_ATTRIBUTE_DIRECTORY: Final = 0x10
_ALLOWED_PRIVATE_PROMPT_FIELDS: Final = frozenset(
    {
        "REQUEST_ORDINAL",
        "DECLARED_AGE_BAND",
        "MORPHOLOGY_DESCRIPTOR",
        "STYLE_DESCRIPTOR",
    }
)


class ExecutionOverlayError(RuntimeError):
    """Fail-closed error for the private execution overlay."""


@dataclass(frozen=True, slots=True)
class GenesisBinding:
    genesis_output_id: str
    genesis_bootstrap_sha256: str
    genesis_receipt_sha256: str
    private_registry_sha256: str
    generation_specification_version: str
    generation_specification_sha256: str
    assignment_manifest_version: str
    assignment_manifest_sha256: str
    prompt_template_version: str
    prompt_template_sha256: str
    policy_digest: str
    request_call_count: int = 1
    requested_output_count: int = 1
    returned_output_count: int = 1
    raw_output_count: int = 1
    failed_call_count: int = 0
    rejected_output_count: int = 0
    admitted_identity_count: int = 0
    formal_calls_remaining: int = 31
    formal_raw_capacity_remaining: int = 31
    global_native_output_capacity_remaining: int = 62
    global_native_output_consumed: int = 2
    next_unused_ordinal: str = "CAL-REQ-002"


@dataclass(frozen=True, slots=True)
class OverlayHandle:
    receipt_path: Path
    sequence: int
    phase: str


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(_read_plain_file_bytes(path))


def _is_reparse(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _require_plain_directory(path: Path) -> None:
    if not path.is_dir() or path.is_symlink() or _is_reparse(path):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_INVALID")


def _require_plain_file(path: Path) -> None:
    if not path.is_file() or path.is_symlink() or _is_reparse(path):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_INVALID")


def _validate_digest(value: str, field: str) -> None:
    if re.fullmatch(r"[0-9a-fA-F]{64}", value) is None:
        raise ExecutionOverlayError(f"{field}_INVALID")


def _validate_opaque_id(value: str, field: str) -> None:
    if _OPAQUE_ID.fullmatch(value) is None:
        raise ExecutionOverlayError(f"{field}_INVALID")


def _validate_timestamp(value: str) -> None:
    if not value or "T" not in value or not value.endswith("Z"):
        raise ExecutionOverlayError("TIMESTAMP_INVALID")


def _validate_ordinal(value: str) -> int:
    match = _ORDINAL.fullmatch(value)
    if match is None:
        raise ExecutionOverlayError("REQUEST_ORDINAL_INVALID")
    number = int(match.group(1))
    if not 1 <= number <= 32:
        raise ExecutionOverlayError("REQUEST_ORDINAL_OUT_OF_RANGE")
    return number


def _next_ordinal(value: str) -> str | None:
    number = _validate_ordinal(value)
    if number == 32:
        return None
    return f"CAL-REQ-{number + 1:03d}"


def _write_create_new(path: Path, payload: bytes) -> tuple[str, int]:
    if len(payload) > MAX_PRIVATE_OVERLAY_FILE_BYTES:
        raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_BYTE_BOUND_FAILED")
    actual = (
        _write_create_new_windows(path, payload)
        if os.name == "nt"
        else _write_create_new_posix(path, payload)
    )
    if actual != payload:
        raise ExecutionOverlayError("CREATE_NEW_REREAD_MISMATCH")
    return sha256_bytes(actual), len(actual)


def _write_json_create_new(path: Path, value: Mapping[str, Any]) -> tuple[str, int]:
    return _write_create_new(path, canonical_json_bytes(value))


def _write_json_create_or_verify_exact(path: Path, value: Mapping[str, Any]) -> tuple[str, int]:
    payload = canonical_json_bytes(value)
    try:
        return _write_create_new(path, payload)
    except ExecutionOverlayError as error:
        if str(error) != "CREATE_NEW_TARGET_PREEXISTS":
            raise
    actual = _read_plain_file_bytes(path)
    if actual != payload:
        raise ExecutionOverlayError("CREATE_NEW_EXISTING_CONTENT_CONFLICT")
    return sha256_bytes(actual), len(actual)


def _write_bytes_create_or_verify_exact(path: Path, payload: bytes) -> tuple[str, int]:
    try:
        return _write_create_new(path, payload)
    except ExecutionOverlayError as error:
        if str(error) != "CREATE_NEW_TARGET_PREEXISTS":
            raise
    actual = _read_plain_file_bytes(path)
    if actual != payload:
        raise ExecutionOverlayError("CREATE_NEW_EXISTING_CONTENT_CONFLICT")
    return sha256_bytes(actual), len(actual)


def _create_new_plain_directory(path: Path) -> None:
    if os.name == "nt":
        _create_plain_directory_windows(path, create_new=True)
    else:
        _create_plain_directory_posix(path, create_new=True)


def _create_or_verify_plain_directory(path: Path) -> None:
    if os.name == "nt":
        _create_plain_directory_windows(path, create_new=False)
    else:
        _create_plain_directory_posix(path, create_new=False)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(_read_plain_file_bytes(path).decode("utf-8"))
    if not isinstance(value, dict):
        raise ExecutionOverlayError("JSON_OBJECT_REQUIRED")
    return cast(dict[str, Any], value)


def _event_name(sequence: int) -> str:
    return f"event-{sequence:06d}.json"


def _state_name(sequence: int) -> str:
    return f"state-{sequence:06d}.json"


def _receipt_name(sequence: int) -> str:
    return f"receipt-{sequence:06d}.json"


def _safe_child(root: Path, file_name: str) -> Path:
    if Path(file_name).name != file_name or file_name in {"", ".", ".."}:
        raise ExecutionOverlayError("PRIVATE_OVERLAY_CHILD_NAME_INVALID")
    candidate = root / file_name
    if candidate.parent.resolve() != root.resolve():
        raise ExecutionOverlayError("PRIVATE_OVERLAY_CHILD_ESCAPES_ROOT")
    return candidate


def _normalized_path_value(path: Path) -> str:
    if not path.is_absolute():
        raise ExecutionOverlayError("PROJECT_WORKTREE_ABSOLUTE_PATH_REQUIRED")
    return os.path.normcase(os.path.abspath(str(path)))


def _validate_project_local_private_parent(
    *, project_worktree_root: Path, allowed_parent: Path
) -> str:
    project_value = _normalized_path_value(project_worktree_root)
    allowed_value = _normalized_path_value(allowed_parent)
    expected_parent = project_worktree_root / PROJECT_PRIVATE_NAMESPACE
    if allowed_value != _normalized_path_value(expected_parent):
        raise ExecutionOverlayError("PROJECT_PRIVATE_PARENT_AUTHORITY_MISMATCH")
    _require_plain_directory(project_worktree_root)
    _require_plain_directory(allowed_parent)
    git_marker = project_worktree_root / ".git"
    if git_marker.is_dir():
        _require_plain_directory(git_marker)
    elif git_marker.is_file():
        _require_plain_file(git_marker)
    else:
        raise ExecutionOverlayError("PROJECT_WORKTREE_GIT_MARKER_MISSING")
    gitignore_path = project_worktree_root / ".gitignore"
    try:
        ignore_lines = _read_plain_file_bytes(gitignore_path).decode("utf-8").splitlines()
    except (OSError, UnicodeError, ExecutionOverlayError) as error:
        raise ExecutionOverlayError("PROJECT_PRIVATE_GITIGNORE_AUTHORITY_INVALID") from error
    if PROJECT_PRIVATE_NAMESPACE + "/" not in {line.strip() for line in ignore_lines}:
        raise ExecutionOverlayError("PROJECT_PRIVATE_NAMESPACE_NOT_GIT_IGNORED")
    return _registration_binding_digest(project_value + "\n" + allowed_value)


def _initial_counters(binding: GenesisBinding) -> dict[str, int]:
    counters = {
        "request_call_count": binding.request_call_count,
        "requested_output_count": binding.requested_output_count,
        "returned_output_count": binding.returned_output_count,
        "raw_output_count": binding.raw_output_count,
        "failed_call_count": binding.failed_call_count,
        "rejected_output_count": binding.rejected_output_count,
        "admitted_identity_count": binding.admitted_identity_count,
        "formal_calls_remaining": binding.formal_calls_remaining,
        "formal_raw_capacity_remaining": binding.formal_raw_capacity_remaining,
        "global_native_output_capacity_remaining": (
            binding.global_native_output_capacity_remaining
        ),
        "global_native_output_consumed": binding.global_native_output_consumed,
        "active_calls": 0,
    }
    _validate_counters(counters)
    return counters


def _validate_counters(counters: Mapping[str, Any]) -> None:
    required = {
        "request_call_count",
        "requested_output_count",
        "returned_output_count",
        "raw_output_count",
        "failed_call_count",
        "rejected_output_count",
        "admitted_identity_count",
        "formal_calls_remaining",
        "formal_raw_capacity_remaining",
        "global_native_output_capacity_remaining",
        "global_native_output_consumed",
        "active_calls",
    }
    if set(counters) != required:
        raise ExecutionOverlayError("COUNTER_KEYSET_MISMATCH")
    if any(not isinstance(counters[key], int) or counters[key] < 0 for key in required):
        raise ExecutionOverlayError("COUNTER_VALUE_INVALID")
    if counters["requested_output_count"] != counters["request_call_count"]:
        raise ExecutionOverlayError("REQUESTED_OUTPUT_COUNTER_MISMATCH")
    if counters["raw_output_count"] != counters["returned_output_count"]:
        raise ExecutionOverlayError("RAW_OUTPUT_COUNTER_MISMATCH")
    if counters["returned_output_count"] > counters["requested_output_count"]:
        raise ExecutionOverlayError("RETURNED_OUTPUT_COUNTER_OVERFLOW")
    if counters["active_calls"] not in {0, 1}:
        raise ExecutionOverlayError("ACTIVE_CALL_COUNTER_INVALID")
    if counters["request_call_count"] + counters["formal_calls_remaining"] != 32:
        raise ExecutionOverlayError("FORMAL_REQUEST_CAPACITY_MISMATCH")
    if counters["raw_output_count"] + counters["formal_raw_capacity_remaining"] != 32:
        raise ExecutionOverlayError("FORMAL_RAW_CAPACITY_MISMATCH")
    if (
        counters["global_native_output_consumed"]
        + counters["global_native_output_capacity_remaining"]
        != 64
    ):
        raise ExecutionOverlayError("GLOBAL_NATIVE_OUTPUT_CAPACITY_MISMATCH")


def _binding_dict(binding: GenesisBinding) -> dict[str, Any]:
    value = asdict(binding)
    for field in (
        "genesis_bootstrap_sha256",
        "genesis_receipt_sha256",
        "private_registry_sha256",
        "generation_specification_sha256",
        "assignment_manifest_sha256",
        "prompt_template_sha256",
        "policy_digest",
    ):
        _validate_digest(cast(str, value[field]), field.upper())
    _validate_opaque_id(binding.genesis_output_id, "GENESIS_OUTPUT_ID")
    _validate_ordinal(binding.next_unused_ordinal)
    return value


def _commit_transition(
    *,
    root: Path,
    sequence: int,
    controller_sha256: str,
    event: dict[str, Any],
    state: dict[str, Any],
    previous_receipt: dict[str, Any] | None,
    registration_receipt: tuple[str, str] | None = None,
) -> OverlayHandle:
    _require_plain_directory(root)
    _validate_digest(controller_sha256, "CONTROLLER_SHA256")
    event_name = _event_name(sequence)
    state_name = _state_name(sequence)
    receipt_name = _receipt_name(sequence)
    event_path = _safe_child(root, event_name)
    state_path = _safe_child(root, state_name)
    receipt_path = _safe_child(root, receipt_name)

    event_digest, _ = _write_json_create_or_verify_exact(event_path, event)
    state_digest, _ = _write_json_create_or_verify_exact(state_path, state)
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "phase": state["phase"],
        "event_file": event_name,
        "event_sha256": event_digest,
        "state_file": state_name,
        "state_sha256": state_digest,
        "controller_sha256": controller_sha256,
        "previous_receipt_file": (
            previous_receipt["receipt_file"] if previous_receipt is not None else None
        ),
        "previous_receipt_sha256": (
            previous_receipt["receipt_sha256"] if previous_receipt is not None else None
        ),
        "registration_receipt_file": (
            registration_receipt[0] if registration_receipt is not None else None
        ),
        "registration_receipt_sha256": (
            registration_receipt[1] if registration_receipt is not None else None
        ),
    }
    _write_json_create_or_verify_exact(receipt_path, receipt)
    verified = verify_overlay(receipt_path, expected_controller_sha256=controller_sha256)
    return OverlayHandle(
        receipt_path=receipt_path,
        sequence=sequence,
        phase=cast(str, verified["state"]["phase"]),
    )


def initialize_overlay(
    *,
    allowed_parent: Path,
    root: Path,
    overlay_output_id: str,
    controller_sha256: str,
    binding: GenesisBinding,
    timestamp: str,
) -> OverlayHandle:
    _require_plain_directory(allowed_parent)
    if root.parent.resolve() != allowed_parent.resolve():
        raise ExecutionOverlayError("PRIVATE_OVERLAY_ROOT_OUTSIDE_ALLOWED_PARENT")
    if root.exists() or root.is_symlink():
        raise ExecutionOverlayError("PRIVATE_OVERLAY_ROOT_PREEXISTS")
    _validate_opaque_id(overlay_output_id, "OVERLAY_OUTPUT_ID")
    _validate_timestamp(timestamp)
    _validate_digest(controller_sha256, "CONTROLLER_SHA256")
    binding_value = _binding_dict(binding)

    root.mkdir()
    _require_plain_directory(root)
    (root / "staging").mkdir()
    (root / "records").mkdir()
    _require_plain_directory(root / "staging")
    _require_plain_directory(root / "records")

    event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": overlay_output_id,
        "sequence": 0,
        "event_type": "OVERLAY_MATERIALIZED",
        "timestamp": timestamp,
        "previous_event_sha256": None,
        "action_id": None,
        "request_ordinal": None,
        "reason_code": "FORWARD_EXECUTION_OVERLAY_CREATED_NO_GENERATION",
    }
    state = {
        "schema_version": STATE_SCHEMA,
        "overlay_schema_version": OVERLAY_SCHEMA,
        "overlay_output_id": overlay_output_id,
        "sequence": 0,
        "phase": "READY",
        "timestamp": timestamp,
        "previous_state_sha256": None,
        "last_event_sha256": sha256_bytes(canonical_json_bytes(event)),
        "binding": binding_value,
        "counters": _initial_counters(binding),
        "next_unused_ordinal": binding.next_unused_ordinal,
        "current_action_id": None,
        "current_ordinal": None,
        "expected_output_opaque_id": None,
        "returned_output_binding": None,
        "output_registration_attempt": None,
        "output_registration": None,
        "decode_authorized": False,
        "hard_stop": False,
    }
    return _commit_transition(
        root=root,
        sequence=0,
        controller_sha256=controller_sha256,
        event=event,
        state=state,
        previous_receipt=None,
    )


def _verify_receipt(
    receipt_path: Path,
    *,
    expected_controller_sha256: str | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _require_plain_file(receipt_path)
    root = receipt_path.parent
    _require_plain_directory(root)
    receipt = _read_json(receipt_path)
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise ExecutionOverlayError("OVERLAY_RECEIPT_SCHEMA_MISMATCH")
    sequence = receipt.get("sequence")
    if not isinstance(sequence, int) or sequence < 0:
        raise ExecutionOverlayError("OVERLAY_RECEIPT_SEQUENCE_INVALID")
    if receipt_path.name != _receipt_name(sequence):
        raise ExecutionOverlayError("OVERLAY_RECEIPT_FILENAME_MISMATCH")
    controller_sha256 = receipt.get("controller_sha256")
    if not isinstance(controller_sha256, str):
        raise ExecutionOverlayError("OVERLAY_CONTROLLER_DIGEST_MISSING")
    _validate_digest(controller_sha256, "CONTROLLER_SHA256")
    if expected_controller_sha256 is not None and controller_sha256 != expected_controller_sha256:
        raise ExecutionOverlayError("OVERLAY_CONTROLLER_DIGEST_MISMATCH")

    event_name = receipt.get("event_file")
    state_name = receipt.get("state_file")
    if not isinstance(event_name, str) or not isinstance(state_name, str):
        raise ExecutionOverlayError("OVERLAY_RECEIPT_FILE_BINDING_INVALID")
    event_path = _safe_child(root, event_name)
    state_path = _safe_child(root, state_name)
    if event_name != _event_name(sequence) or state_name != _state_name(sequence):
        raise ExecutionOverlayError("OVERLAY_RECEIPT_SEQUENCE_BINDING_MISMATCH")
    if sha256_file(event_path) != receipt.get("event_sha256"):
        raise ExecutionOverlayError("OVERLAY_EVENT_DIGEST_MISMATCH")
    if sha256_file(state_path) != receipt.get("state_sha256"):
        raise ExecutionOverlayError("OVERLAY_STATE_DIGEST_MISMATCH")
    event = _read_json(event_path)
    state = _read_json(state_path)
    if event.get("schema_version") != EVENT_SCHEMA or state.get("schema_version") != STATE_SCHEMA:
        raise ExecutionOverlayError("OVERLAY_STATE_OR_EVENT_SCHEMA_MISMATCH")
    if event.get("sequence") != sequence or state.get("sequence") != sequence:
        raise ExecutionOverlayError("OVERLAY_STATE_OR_EVENT_SEQUENCE_MISMATCH")
    if state.get("last_event_sha256") != receipt.get("event_sha256"):
        raise ExecutionOverlayError("OVERLAY_STATE_EVENT_BINDING_MISMATCH")
    if state.get("overlay_output_id") != receipt.get("overlay_output_id"):
        raise ExecutionOverlayError("OVERLAY_OUTPUT_ID_MISMATCH")
    counters = state.get("counters")
    if not isinstance(counters, dict):
        raise ExecutionOverlayError("OVERLAY_COUNTERS_MISSING")
    _validate_counters(counters)
    return receipt, event, state


def verify_overlay(
    receipt_path: Path,
    *,
    expected_controller_sha256: str | None = None,
) -> dict[str, Any]:
    receipt, event, state = _verify_receipt(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    root = receipt_path.parent
    current_receipt = receipt
    current_event = event
    current_state = state
    sequence = cast(int, receipt["sequence"])
    while sequence > 0:
        previous_name = current_receipt.get("previous_receipt_file")
        previous_digest = current_receipt.get("previous_receipt_sha256")
        if previous_name != _receipt_name(sequence - 1) or not isinstance(previous_digest, str):
            raise ExecutionOverlayError("OVERLAY_PREVIOUS_RECEIPT_BINDING_INVALID")
        previous_path = _safe_child(root, previous_name)
        if sha256_file(previous_path) != previous_digest:
            raise ExecutionOverlayError("OVERLAY_PREVIOUS_RECEIPT_DIGEST_MISMATCH")
        previous_receipt, previous_event, previous_state = _verify_receipt(
            previous_path,
            expected_controller_sha256=expected_controller_sha256,
        )
        if current_event.get("previous_event_sha256") != previous_receipt.get("event_sha256"):
            raise ExecutionOverlayError("OVERLAY_PREVIOUS_EVENT_DIGEST_MISMATCH")
        if current_state.get("previous_state_sha256") != previous_receipt.get("state_sha256"):
            raise ExecutionOverlayError("OVERLAY_PREVIOUS_STATE_DIGEST_MISMATCH")
        current_receipt = previous_receipt
        current_event = previous_event
        current_state = previous_state
        sequence -= 1
    if (
        current_receipt.get("previous_receipt_file") is not None
        or current_receipt.get("previous_receipt_sha256") is not None
    ):
        raise ExecutionOverlayError("OVERLAY_GENESIS_RECEIPT_PREDECESSOR_INVALID")
    if (
        current_event.get("previous_event_sha256") is not None
        or current_state.get("previous_state_sha256") is not None
    ):
        raise ExecutionOverlayError("OVERLAY_GENESIS_CHAIN_INVALID")
    return {"receipt": receipt, "event": event, "state": state}


def _transition_context(
    receipt_path: Path,
    *,
    expected_controller_sha256: str,
) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    verified = verify_overlay(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    return (
        receipt_path.parent,
        cast(dict[str, Any], verified["receipt"]),
        cast(dict[str, Any], verified["event"]),
        cast(dict[str, Any], verified["state"]),
    )


def _previous_receipt_binding(receipt_path: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "receipt_file": receipt_path.name,
        "receipt_sha256": sha256_file(receipt_path),
    }


def prepare_dispatch(
    *,
    receipt_path: Path,
    expected_controller_sha256: str,
    ordinal: str,
    action_id: str,
    expected_output_opaque_id: str,
    timestamp: str,
) -> OverlayHandle:
    _validate_opaque_id(action_id, "ACTION_ID")
    _validate_opaque_id(expected_output_opaque_id, "EXPECTED_OUTPUT_OPAQUE_ID")
    _validate_timestamp(timestamp)
    _validate_ordinal(ordinal)
    root, receipt, _event, state = _transition_context(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    if state["phase"] != "READY" or state["hard_stop"] is not False:
        raise ExecutionOverlayError("DISPATCH_PREPARE_STATE_INVALID")
    if state["next_unused_ordinal"] != ordinal:
        raise ExecutionOverlayError("DISPATCH_PREPARE_ORDINAL_MISMATCH")
    counters = cast(dict[str, int], state["counters"])
    if counters["active_calls"] != 0:
        raise ExecutionOverlayError("DISPATCH_PREPARE_ACTIVE_CALL_EXISTS")
    if (
        counters["formal_calls_remaining"] < 1
        or counters["formal_raw_capacity_remaining"] < 1
        or counters["global_native_output_capacity_remaining"] < 1
    ):
        raise ExecutionOverlayError("DISPATCH_PREPARE_RESOURCE_EXHAUSTED")

    sequence = cast(int, receipt["sequence"]) + 1
    new_event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": "DISPATCH_PREPARED",
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": action_id,
        "request_ordinal": ordinal,
        "expected_output_opaque_id": expected_output_opaque_id,
        "reason_code": "EXACT_ORDINAL_DURABLY_PREPARED_ZERO_RETRY",
    }
    new_state = dict(state)
    new_state.update(
        {
            "sequence": sequence,
            "phase": "DISPATCH_PREPARED",
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": sha256_bytes(canonical_json_bytes(new_event)),
            "current_action_id": action_id,
            "current_ordinal": ordinal,
            "expected_output_opaque_id": expected_output_opaque_id,
        }
    )
    return _commit_transition(
        root=root,
        sequence=sequence,
        controller_sha256=expected_controller_sha256,
        event=new_event,
        state=new_state,
        previous_receipt=_previous_receipt_binding(receipt_path, receipt),
    )


def consume_dispatch(
    *,
    receipt_path: Path,
    expected_controller_sha256: str,
    action_id: str,
    timestamp: str,
) -> OverlayHandle:
    _validate_timestamp(timestamp)
    root, receipt, _event, state = _transition_context(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    if state["phase"] != "DISPATCH_PREPARED" or state["current_action_id"] != action_id:
        raise ExecutionOverlayError("DISPATCH_CONSUME_STATE_OR_ACTION_INVALID")
    ordinal = cast(str, state["current_ordinal"])
    counters = dict(cast(dict[str, int], state["counters"]))
    if counters["active_calls"] != 0:
        raise ExecutionOverlayError("DISPATCH_CONSUME_ACTIVE_CALL_EXISTS")
    counters["request_call_count"] += 1
    counters["requested_output_count"] += 1
    counters["formal_calls_remaining"] -= 1
    counters["global_native_output_capacity_remaining"] -= 1
    counters["global_native_output_consumed"] += 1
    counters["active_calls"] = 1
    _validate_counters(counters)

    sequence = cast(int, receipt["sequence"]) + 1
    new_event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": "DISPATCH_STARTED_CONSUMED",
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": action_id,
        "request_ordinal": ordinal,
        "reason_code": "NATIVE_DISPATCH_IRREVERSIBLY_CONSUMED",
    }
    new_state = dict(state)
    new_state.update(
        {
            "sequence": sequence,
            "phase": "DISPATCH_STARTED_CONSUMED",
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": sha256_bytes(canonical_json_bytes(new_event)),
            "counters": counters,
            "next_unused_ordinal": _next_ordinal(ordinal),
        }
    )
    return _commit_transition(
        root=root,
        sequence=sequence,
        controller_sha256=expected_controller_sha256,
        event=new_event,
        state=new_state,
        previous_receipt=_previous_receipt_binding(receipt_path, receipt),
    )


def mark_dispatch_failed(
    *,
    receipt_path: Path,
    expected_controller_sha256: str,
    action_id: str,
    timestamp: str,
    reason_code: str,
) -> OverlayHandle:
    _validate_timestamp(timestamp)
    root, receipt, _event, state = _transition_context(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    if state["phase"] != "DISPATCH_STARTED_CONSUMED" or state["current_action_id"] != action_id:
        raise ExecutionOverlayError("DISPATCH_FAILURE_STATE_OR_ACTION_INVALID")
    if not reason_code or not reason_code.isupper():
        raise ExecutionOverlayError("DISPATCH_FAILURE_REASON_INVALID")
    counters = dict(cast(dict[str, int], state["counters"]))
    counters["failed_call_count"] += 1
    counters["active_calls"] = 0
    _validate_counters(counters)
    sequence = cast(int, receipt["sequence"]) + 1
    new_event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": "DISPATCH_FAILED_FINAL",
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": action_id,
        "request_ordinal": state["current_ordinal"],
        "reason_code": reason_code,
    }
    new_state = dict(state)
    new_state.update(
        {
            "sequence": sequence,
            "phase": "DISPATCH_FAILED_FINAL",
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": sha256_bytes(canonical_json_bytes(new_event)),
            "counters": counters,
            "hard_stop": True,
            "decode_authorized": False,
        }
    )
    return _commit_transition(
        root=root,
        sequence=sequence,
        controller_sha256=expected_controller_sha256,
        event=new_event,
        state=new_state,
        previous_receipt=_previous_receipt_binding(receipt_path, receipt),
    )


def record_output_returned(
    *,
    receipt_path: Path,
    expected_controller_sha256: str,
    action_id: str,
    timestamp: str,
    returned_output_count: int,
    exact_generated_artifact_receipt: str,
) -> OverlayHandle:
    _validate_timestamp(timestamp)
    root, receipt, _event, state = _transition_context(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    if state["phase"] != "DISPATCH_STARTED_CONSUMED" or state["current_action_id"] != action_id:
        raise ExecutionOverlayError("OUTPUT_RETURN_STATE_OR_ACTION_INVALID")
    if returned_output_count != 1:
        raise ExecutionOverlayError("OUTPUT_CARDINALITY_MISMATCH_HARD_STOP")
    counters = dict(cast(dict[str, int], state["counters"]))
    if counters["formal_raw_capacity_remaining"] < 1:
        raise ExecutionOverlayError("FORMAL_RAW_CAPACITY_EXHAUSTED")
    counters["returned_output_count"] += 1
    counters["raw_output_count"] += 1
    counters["formal_raw_capacity_remaining"] -= 1
    _validate_counters(counters)
    sequence = cast(int, receipt["sequence"]) + 1
    new_event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": "OUTPUT_RETURNED_UNREGISTERED",
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": action_id,
        "request_ordinal": state["current_ordinal"],
        "reason_code": "ONE_RETURNED_OUTPUT_COUNTED_BEFORE_BYTE_INSPECTION",
        "returned_output_count_for_action": returned_output_count,
    }
    new_state = dict(state)
    new_state.update(
        {
            "sequence": sequence,
            "phase": "OUTPUT_RETURNED_UNREGISTERED",
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": sha256_bytes(canonical_json_bytes(new_event)),
            "counters": counters,
            "decode_authorized": False,
        }
    )
    returned_handle = _commit_transition(
        root=root,
        sequence=sequence,
        controller_sha256=expected_controller_sha256,
        event=new_event,
        state=new_state,
        previous_receipt=_previous_receipt_binding(receipt_path, receipt),
    )
    root, receipt, _event, state = _transition_context(
        returned_handle.receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    expected_output_opaque_id = state.get("expected_output_opaque_id")
    if not isinstance(expected_output_opaque_id, str):
        raise ExecutionOverlayError("EXPECTED_OUTPUT_OPAQUE_ID_MISSING")
    receipt_digest = _registration_binding_digest(exact_generated_artifact_receipt)
    sequence = cast(int, receipt["sequence"]) + 1
    binding_event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": "OUTPUT_RETURNED_RECEIPT_BOUND",
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": action_id,
        "request_ordinal": state["current_ordinal"],
        "reason_code": "EXACT_IMAGEGEN_OUTPUT_HINT_DIGEST_BOUND_AFTER_COUNTER_COMMIT",
        "output_opaque_id": expected_output_opaque_id,
        "exact_generated_artifact_receipt_sha256": receipt_digest,
    }
    binding_state = dict(state)
    binding_state.update(
        {
            "sequence": sequence,
            "phase": "OUTPUT_RETURNED_RECEIPT_BOUND",
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": sha256_bytes(canonical_json_bytes(binding_event)),
            "returned_output_binding": {
                "output_opaque_id": expected_output_opaque_id,
                "request_ordinal": state["current_ordinal"],
                "action_id": action_id,
                "exact_generated_artifact_receipt_sha256": receipt_digest,
            },
            "decode_authorized": False,
        }
    )
    return _commit_transition(
        root=root,
        sequence=sequence,
        controller_sha256=expected_controller_sha256,
        event=binding_event,
        state=binding_state,
        previous_receipt=_previous_receipt_binding(returned_handle.receipt_path, receipt),
    )


def mark_registration_failed(
    *,
    receipt_path: Path,
    expected_controller_sha256: str,
    action_id: str,
    timestamp: str,
    reason_code: str,
) -> OverlayHandle:
    _validate_timestamp(timestamp)
    root, receipt, _event, state = _transition_context(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    if (
        state["phase"] != "OUTPUT_REGISTRATION_ATTEMPT_BOUND"
        or state["current_action_id"] != action_id
    ):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_FAILURE_STATE_OR_ACTION_INVALID")
    if not reason_code or not reason_code.isupper():
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_FAILURE_REASON_INVALID")
    counters = dict(cast(dict[str, int], state["counters"]))
    counters["active_calls"] = 0
    _validate_counters(counters)
    sequence = cast(int, receipt["sequence"]) + 1
    new_event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE",
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": action_id,
        "request_ordinal": state["current_ordinal"],
        "reason_code": reason_code,
    }
    new_state = dict(state)
    new_state.update(
        {
            "sequence": sequence,
            "phase": "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE",
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": sha256_bytes(canonical_json_bytes(new_event)),
            "counters": counters,
            "decode_authorized": False,
            "hard_stop": True,
        }
    )
    return _commit_transition(
        root=root,
        sequence=sequence,
        controller_sha256=expected_controller_sha256,
        event=new_event,
        state=new_state,
        previous_receipt=_previous_receipt_binding(receipt_path, receipt),
    )


def _classify_magic(first_bytes: bytes) -> tuple[str, str]:
    if first_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "PNG_89504E470D0A1A0A"
    if first_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "JPEG_FFD8FF"
    if len(first_bytes) >= 12 and first_bytes[:4] == b"RIFF" and first_bytes[8:12] == b"WEBP":
        return "image/webp", "WEBP_RIFF"
    return "application/octet-stream", "UNKNOWN"


def _registration_binding_digest(value: str) -> str:
    if not isinstance(value, str):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_RECEIPT_TYPE_INVALID")
    return sha256_bytes(value.encode("utf-8", errors="surrogatepass"))


def _parse_imagegen_data_url(value: str) -> tuple[bytes, str, str, str, int]:
    if not isinstance(value, str):
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_TYPE_INVALID")
    declared_media_type: str | None = None
    encoded_payload = ""
    for prefix, media_type in _IMAGEGEN_DATA_URL_PREFIXES.items():
        if value.startswith(prefix):
            declared_media_type = media_type
            encoded_payload = value[len(prefix) :]
            break
    if declared_media_type is None:
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_HEADER_INVALID")
    if not encoded_payload:
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_PAYLOAD_EMPTY")
    if len(encoded_payload) > MAX_DATA_URL_ENCODED_BYTES:
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_ENCODED_BYTE_BOUND_FAILED")
    if (
        not encoded_payload.isascii()
        or len(encoded_payload) % 4 != 0
        or _STRICT_BASE64_PAYLOAD.fullmatch(encoded_payload) is None
    ):
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_BASE64_INVALID")
    try:
        decoded = base64.b64decode(encoded_payload, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_BASE64_INVALID") from error
    if base64.b64encode(decoded).decode("ascii") != encoded_payload:
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_BASE64_INVALID")
    if not decoded or len(decoded) > MAX_RETURNED_BYTES:
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_DECODED_BYTE_BOUND_FAILED")
    actual_media_type, magic_class = _classify_magic(decoded[:16])
    if actual_media_type == "application/octet-stream":
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_MAGIC_UNSUPPORTED")
    if actual_media_type != declared_media_type:
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_MIME_MAGIC_MISMATCH")
    return (
        decoded,
        declared_media_type,
        magic_class,
        sha256_bytes(value.encode("ascii")),
        len(encoded_payload),
    )


def _begin_imagegen_data_url_registration_attempt(
    *,
    receipt_path: Path,
    expected_controller_sha256: str,
    action_id: str,
    project_worktree_root: Path,
    imagegen_data_url: str,
    timestamp: str,
) -> OverlayHandle:
    root, receipt, _event, state = _transition_context(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    private_parent_sha256 = _validate_project_local_private_parent(
        project_worktree_root=project_worktree_root,
        allowed_parent=root.parent,
    )
    if state["phase"] != "OUTPUT_RETURNED_RECEIPT_BOUND" or state["current_action_id"] != action_id:
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_STATE_OR_ACTION_INVALID")
    returned_binding = state.get("returned_output_binding")
    if not isinstance(returned_binding, dict):
        raise ExecutionOverlayError("RETURNED_OUTPUT_BINDING_MISSING")
    output_opaque_id = returned_binding.get("output_opaque_id")
    bound_digest = returned_binding.get("exact_generated_artifact_receipt_sha256")
    if not isinstance(output_opaque_id, str) or not isinstance(bound_digest, str):
        raise ExecutionOverlayError("RETURNED_OUTPUT_BINDING_INVALID")
    _validate_opaque_id(output_opaque_id, "OUTPUT_OPAQUE_ID")
    _validate_digest(bound_digest, "GENERATED_ARTIFACT_RECEIPT_SHA256")
    actual_digest = _registration_binding_digest(imagegen_data_url)
    if actual_digest != bound_digest:
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_BINDING_MISMATCH")

    sequence = cast(int, receipt["sequence"]) + 1
    new_event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": "OUTPUT_REGISTRATION_ATTEMPT_BOUND",
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": action_id,
        "request_ordinal": state["current_ordinal"],
        "reason_code": "EXACT_IMAGEGEN_DATA_URL_DIGEST_BOUND_BEFORE_BASE64_PARSE",
        "output_opaque_id": output_opaque_id,
        "exact_generated_artifact_receipt_sha256": bound_digest,
        "source_delivery_class": "CODEX_NATIVE_IMAGEGEN_DATA_URL",
        "project_private_parent_sha256": private_parent_sha256,
    }
    new_state = dict(state)
    new_state.update(
        {
            "sequence": sequence,
            "phase": "OUTPUT_REGISTRATION_ATTEMPT_BOUND",
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": sha256_bytes(canonical_json_bytes(new_event)),
            "output_registration_attempt": {
                "output_opaque_id": output_opaque_id,
                "request_ordinal": state["current_ordinal"],
                "action_id": action_id,
                "source_kind": "CODEX_NATIVE_IMAGEGEN",
                "source_delivery_class": "CODEX_NATIVE_IMAGEGEN_DATA_URL",
                "exact_generated_artifact_receipt_sha256": bound_digest,
                "project_private_parent_sha256": private_parent_sha256,
            },
            "decode_authorized": False,
        }
    )
    return _commit_transition(
        root=root,
        sequence=sequence,
        controller_sha256=expected_controller_sha256,
        event=new_event,
        state=new_state,
        previous_receipt=_previous_receipt_binding(receipt_path, receipt),
    )


def _begin_output_registration_attempt(
    *,
    receipt_path: Path,
    expected_controller_sha256: str,
    action_id: str,
    allowed_generated_artifact_root: Path,
    timestamp: str,
) -> OverlayHandle:
    root, receipt, _event, state = _transition_context(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    if state["phase"] != "OUTPUT_RETURNED_RECEIPT_BOUND" or state["current_action_id"] != action_id:
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_STATE_OR_ACTION_INVALID")
    returned_binding = state.get("returned_output_binding")
    if not isinstance(returned_binding, dict):
        raise ExecutionOverlayError("RETURNED_OUTPUT_BINDING_MISSING")
    expected_output_opaque_id = returned_binding.get("output_opaque_id")
    receipt_digest = returned_binding.get("exact_generated_artifact_receipt_sha256")
    if not isinstance(expected_output_opaque_id, str) or not isinstance(receipt_digest, str):
        raise ExecutionOverlayError("RETURNED_OUTPUT_BINDING_INVALID")
    _validate_digest(receipt_digest, "GENERATED_ARTIFACT_RECEIPT_SHA256")
    allowed_root_value = str(allowed_generated_artifact_root)
    allowed_root_digest = _registration_binding_digest(allowed_root_value)
    sequence = cast(int, receipt["sequence"]) + 1
    new_event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": "OUTPUT_REGISTRATION_ATTEMPT_BOUND",
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": action_id,
        "request_ordinal": state["current_ordinal"],
        "reason_code": "EXACT_PRINCIPAL_IMAGEGEN_OUTPUT_HINT_BOUND_BEFORE_SOURCE_ACCESS",
        "output_opaque_id": expected_output_opaque_id,
        "exact_generated_artifact_receipt_sha256": receipt_digest,
        "allowed_generated_artifact_root_sha256": allowed_root_digest,
    }
    new_state = dict(state)
    new_state.update(
        {
            "sequence": sequence,
            "phase": "OUTPUT_REGISTRATION_ATTEMPT_BOUND",
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": sha256_bytes(canonical_json_bytes(new_event)),
            "output_registration_attempt": {
                "output_opaque_id": expected_output_opaque_id,
                "request_ordinal": state["current_ordinal"],
                "action_id": action_id,
                "source_kind": "CODEX_NATIVE_IMAGEGEN",
                "source_delivery_class": ("TRUSTED_PRINCIPAL_EXACT_IMAGEGEN_OUTPUT_HINT_PATH"),
                "exact_generated_artifact_receipt_sha256": receipt_digest,
                "allowed_generated_artifact_root_sha256": allowed_root_digest,
            },
            "decode_authorized": False,
        }
    )
    return _commit_transition(
        root=root,
        sequence=sequence,
        controller_sha256=expected_controller_sha256,
        event=new_event,
        state=new_state,
        previous_receipt=_previous_receipt_binding(receipt_path, receipt),
    )


def _validated_generated_artifact_path(
    *,
    state: Mapping[str, Any],
    exact_generated_artifact_receipt: str,
    allowed_generated_artifact_root: Path,
) -> Path:
    attempt = state.get("output_registration_attempt")
    if not isinstance(attempt, dict):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_MISSING")
    returned_binding = state.get("returned_output_binding")
    if not isinstance(returned_binding, dict):
        raise ExecutionOverlayError("RETURNED_OUTPUT_BINDING_MISSING")
    for field in (
        "output_opaque_id",
        "request_ordinal",
        "action_id",
        "exact_generated_artifact_receipt_sha256",
    ):
        if attempt.get(field) != returned_binding.get(field):
            raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_BINDING_MISMATCH")
    receipt_digest = _registration_binding_digest(exact_generated_artifact_receipt)
    allowed_root_digest = _registration_binding_digest(str(allowed_generated_artifact_root))
    if attempt.get("exact_generated_artifact_receipt_sha256") != receipt_digest:
        raise ExecutionOverlayError("GENERATED_ARTIFACT_RECEIPT_BINDING_MISMATCH")
    if attempt.get("allowed_generated_artifact_root_sha256") != allowed_root_digest:
        raise ExecutionOverlayError("GENERATED_ARTIFACT_ROOT_BINDING_MISMATCH")
    if (
        not exact_generated_artifact_receipt
        or len(exact_generated_artifact_receipt) > 4096
        or "\x00" in exact_generated_artifact_receipt
        or "\n" in exact_generated_artifact_receipt
        or "\r" in exact_generated_artifact_receipt
        or "data:" in exact_generated_artifact_receipt.lower()
        or "://" in exact_generated_artifact_receipt
    ):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_RECEIPT_INVALID")
    generated_artifact_path = Path(exact_generated_artifact_receipt)
    if (
        not generated_artifact_path.is_absolute()
        or not allowed_generated_artifact_root.is_absolute()
    ):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_ABSOLUTE_PATH_REQUIRED")
    try:
        relative_parts = generated_artifact_path.relative_to(allowed_generated_artifact_root).parts
    except ValueError as error:
        raise ExecutionOverlayError("GENERATED_ARTIFACT_OUTSIDE_ALLOWED_ROOT") from error
    if not relative_parts or any(part in {"", ".", ".."} for part in relative_parts):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_OUTSIDE_ALLOWED_ROOT")
    return generated_artifact_path


def _relative_artifact_parts(
    *,
    generated_artifact_path: Path,
    allowed_generated_artifact_root: Path,
) -> tuple[str, ...]:
    try:
        relative_parts = generated_artifact_path.relative_to(allowed_generated_artifact_root).parts
    except ValueError as error:
        raise ExecutionOverlayError("GENERATED_ARTIFACT_OUTSIDE_ALLOWED_ROOT") from error
    if not relative_parts or any(part in {"", ".", ".."} for part in relative_parts):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_OUTSIDE_ALLOWED_ROOT")
    return relative_parts


def _posix_safe_open_flags() -> tuple[int, int]:
    directory_flag = getattr(os, "O_DIRECTORY", None)
    no_follow_flag = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(directory_flag, int) or not isinstance(no_follow_flag, int):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_SAFE_OPEN_UNAVAILABLE")
    return directory_flag, no_follow_flag


def _open_posix_directory_chain(path: Path) -> list[int]:
    directory_flag, no_follow_flag = _posix_safe_open_flags()
    flags = os.O_RDONLY | directory_flag | no_follow_flag
    anchor = Path(path.anchor)
    descriptors = [os.open(str(anchor), flags)]
    try:
        for part in path.parts[1:]:
            descriptor = os.open(part, flags, dir_fd=descriptors[-1])
            try:
                if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    raise ExecutionOverlayError("GENERATED_ARTIFACT_DIRECTORY_INVALID")
            except Exception:
                os.close(descriptor)
                raise
            descriptors.append(descriptor)
        return descriptors
    except Exception:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise


def _assert_posix_root_identity(path: Path, descriptor: int) -> None:
    path_stat = os.lstat(path)
    opened_stat = os.fstat(descriptor)
    if not stat.S_ISDIR(path_stat.st_mode) or (path_stat.st_dev, path_stat.st_ino) != (
        opened_stat.st_dev,
        opened_stat.st_ino,
    ):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_ROOT_CHANGED_BEFORE_READ")


def _assert_posix_named_file_identity(
    file_descriptor: int, parent_descriptor: int, name: str
) -> None:
    opened_stat = os.fstat(file_descriptor)
    named_stat = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    if not stat.S_ISREG(opened_stat.st_mode) or not stat.S_ISREG(named_stat.st_mode):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_INVALID")
    if (opened_stat.st_dev, opened_stat.st_ino) != (named_stat.st_dev, named_stat.st_ino):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_BINDING_CHANGED")


def _read_plain_file_bytes_posix(path: Path) -> bytes:
    if not path.is_absolute():
        raise ExecutionOverlayError("PRIVATE_OVERLAY_ABSOLUTE_PATH_REQUIRED")
    _directory_flag, no_follow_flag = _posix_safe_open_flags()
    descriptors = _open_posix_directory_chain(path.parent)
    file_descriptor: int | None = None
    try:
        _assert_posix_root_identity(path.parent, descriptors[-1])
        file_descriptor = os.open(
            path.name,
            os.O_RDONLY | no_follow_flag | getattr(os, "O_CLOEXEC", 0),
            dir_fd=descriptors[-1],
        )
        opened_stat = os.fstat(file_descriptor)
        if (
            not stat.S_ISREG(opened_stat.st_mode)
            or opened_stat.st_size < 0
            or opened_stat.st_size > MAX_PRIVATE_OVERLAY_FILE_BYTES
        ):
            raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_INVALID")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(
                file_descriptor, min(1024 * 1024, MAX_PRIVATE_OVERLAY_FILE_BYTES + 1 - total)
            )
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_PRIVATE_OVERLAY_FILE_BYTES:
                raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_BYTE_BOUND_FAILED")
            chunks.append(chunk)
        _assert_posix_named_file_identity(file_descriptor, descriptors[-1], path.name)
        _assert_posix_root_identity(path.parent, descriptors[-1])
        return b"".join(chunks)
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _write_create_new_posix(path: Path, payload: bytes) -> bytes:
    if not path.is_absolute():
        raise ExecutionOverlayError("PRIVATE_OVERLAY_ABSOLUTE_PATH_REQUIRED")
    _directory_flag, no_follow_flag = _posix_safe_open_flags()
    descriptors = _open_posix_directory_chain(path.parent)
    file_descriptor: int | None = None
    try:
        _assert_posix_root_identity(path.parent, descriptors[-1])
        try:
            file_descriptor = os.open(
                path.name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | no_follow_flag | getattr(os, "O_CLOEXEC", 0),
                0o600,
                dir_fd=descriptors[-1],
            )
        except FileExistsError as error:
            raise ExecutionOverlayError("CREATE_NEW_TARGET_PREEXISTS") from error
        if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
            raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_INVALID")
        offset = 0
        while offset < len(payload):
            written = os.write(file_descriptor, payload[offset:])
            if written <= 0:
                raise ExecutionOverlayError("CREATE_NEW_SHORT_WRITE")
            offset += written
        os.fsync(file_descriptor)
        os.lseek(file_descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = len(payload)
        while remaining:
            chunk = os.read(file_descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise ExecutionOverlayError("CREATE_NEW_SHORT_READBACK")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(file_descriptor, 1):
            raise ExecutionOverlayError("CREATE_NEW_READBACK_OVERFLOW")
        _assert_posix_named_file_identity(file_descriptor, descriptors[-1], path.name)
        _assert_posix_root_identity(path.parent, descriptors[-1])
        return b"".join(chunks)
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _assert_posix_plain_directory_identity(path: Path, descriptor: int) -> None:
    path_stat = os.lstat(path)
    opened_stat = os.fstat(descriptor)
    if not stat.S_ISDIR(path_stat.st_mode) or not stat.S_ISDIR(opened_stat.st_mode):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_INVALID")
    if (path_stat.st_dev, path_stat.st_ino) != (opened_stat.st_dev, opened_stat.st_ino):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_BINDING_CHANGED")


def _create_plain_directory_posix(path: Path, *, create_new: bool) -> None:
    if not path.is_absolute() or Path(path.name).name != path.name or path.name in {"", ".", ".."}:
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_PATH_INVALID")
    directory_flag, no_follow_flag = _posix_safe_open_flags()
    try:
        descriptors = _open_posix_directory_chain(path.parent)
    except OSError as error:
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_INVALID") from error
    child_descriptor: int | None = None
    try:
        _assert_posix_plain_directory_identity(path.parent, descriptors[-1])
        try:
            os.mkdir(path.name, 0o700, dir_fd=descriptors[-1])
        except FileExistsError as error:
            if create_new:
                raise ExecutionOverlayError("CREATE_NEW_TARGET_PREEXISTS") from error
        child_descriptor = os.open(
            path.name,
            os.O_RDONLY | directory_flag | no_follow_flag | getattr(os, "O_CLOEXEC", 0),
            dir_fd=descriptors[-1],
        )
        _assert_posix_plain_directory_identity(path.parent, descriptors[-1])
        _assert_posix_plain_directory_identity(path, child_descriptor)
    except OSError as error:
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_INVALID") from error
    finally:
        if child_descriptor is not None:
            os.close(child_descriptor)
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _open_posix_generated_artifact(
    *,
    generated_artifact_path: Path,
    allowed_generated_artifact_root: Path,
) -> tuple[int, list[int]]:
    directory_flag, no_follow_flag = _posix_safe_open_flags()
    descriptors = _open_posix_directory_chain(allowed_generated_artifact_root)
    root_descriptor = descriptors[-1]
    file_descriptor: int | None = None
    try:
        relative_parts = _relative_artifact_parts(
            generated_artifact_path=generated_artifact_path,
            allowed_generated_artifact_root=allowed_generated_artifact_root,
        )
        directory_flags = os.O_RDONLY | directory_flag | no_follow_flag
        for part in relative_parts[:-1]:
            descriptor = os.open(part, directory_flags, dir_fd=descriptors[-1])
            try:
                if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    raise ExecutionOverlayError("GENERATED_ARTIFACT_DIRECTORY_INVALID")
            except Exception:
                os.close(descriptor)
                raise
            descriptors.append(descriptor)
        file_descriptor = os.open(
            relative_parts[-1],
            os.O_RDONLY | no_follow_flag,
            dir_fd=descriptors[-1],
        )
        if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
            os.close(file_descriptor)
            file_descriptor = None
            raise ExecutionOverlayError("GENERATED_ARTIFACT_FILE_INVALID")
        _assert_posix_root_identity(allowed_generated_artifact_root, root_descriptor)
        return file_descriptor, descriptors
    except Exception:
        if file_descriptor is not None:
            os.close(file_descriptor)
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise


def _windows_final_path(handle: int) -> str:
    import ctypes

    win_dll = getattr(ctypes, "WinDLL", None)
    if not callable(win_dll):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_SAFE_OPEN_UNAVAILABLE")
    kernel32 = win_dll("kernel32", use_last_error=True)
    get_final_path = kernel32.GetFinalPathNameByHandleW
    get_final_path.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
    get_final_path.restype = ctypes.c_uint32
    buffer_size = 512
    while buffer_size <= 32768:
        buffer = ctypes.create_unicode_buffer(buffer_size)
        result = get_final_path(handle, buffer, buffer_size, 0)
        if result == 0:
            raise ExecutionOverlayError("GENERATED_ARTIFACT_HANDLE_PATH_UNAVAILABLE")
        if result < buffer_size:
            value = buffer.value
            if value.startswith("\\\\?\\UNC\\"):
                value = "\\\\" + value[8:]
            elif value.startswith("\\\\?\\"):
                value = value[4:]
            return os.path.normcase(os.path.normpath(value))
        buffer_size = result + 1
    raise ExecutionOverlayError("GENERATED_ARTIFACT_HANDLE_PATH_UNAVAILABLE")


def _windows_open_path(path: Path, *, expect_directory: bool) -> int:
    import ctypes

    win_dll = getattr(ctypes, "WinDLL", None)
    if not callable(win_dll):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_SAFE_OPEN_UNAVAILABLE")
    kernel32 = win_dll("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    get_file_information = kernel32.GetFileInformationByHandle
    get_file_information.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    get_file_information.restype = ctypes.c_int
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_int

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", ctypes.c_uint32),
            ("ftCreationTimeLow", ctypes.c_uint32),
            ("ftCreationTimeHigh", ctypes.c_uint32),
            ("ftLastAccessTimeLow", ctypes.c_uint32),
            ("ftLastAccessTimeHigh", ctypes.c_uint32),
            ("ftLastWriteTimeLow", ctypes.c_uint32),
            ("ftLastWriteTimeHigh", ctypes.c_uint32),
            ("dwVolumeSerialNumber", ctypes.c_uint32),
            ("nFileSizeHigh", ctypes.c_uint32),
            ("nFileSizeLow", ctypes.c_uint32),
            ("nNumberOfLinks", ctypes.c_uint32),
            ("nFileIndexHigh", ctypes.c_uint32),
            ("nFileIndexLow", ctypes.c_uint32),
        ]

    flags = 0x00200000
    if expect_directory:
        flags |= 0x02000000
    handle = create_file(str(path), 0x80000000, 0x00000001, None, 3, flags, None)
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle or handle is None:
        raise ExecutionOverlayError("GENERATED_ARTIFACT_SAFE_OPEN_FAILED")
    information = ByHandleFileInformation()
    try:
        if not get_file_information(handle, ctypes.byref(information)):
            raise ExecutionOverlayError("GENERATED_ARTIFACT_HANDLE_INFO_UNAVAILABLE")
        is_directory = bool(information.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY)
        if (
            bool(information.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT)
            or is_directory != expect_directory
            or _windows_final_path(handle) != os.path.normcase(os.path.normpath(str(path)))
        ):
            raise ExecutionOverlayError("GENERATED_ARTIFACT_HANDLE_BINDING_INVALID")
        return cast(int, handle)
    except Exception:
        close_handle(handle)
        raise


def _close_windows_handles(handles: list[int]) -> None:
    import ctypes

    win_dll = getattr(ctypes, "WinDLL", None)
    if not callable(win_dll):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_SAFE_OPEN_UNAVAILABLE")
    close_handle = win_dll("kernel32", use_last_error=True).CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_int
    for handle in reversed(handles):
        close_handle(handle)


def _open_windows_directory_chain(path: Path) -> list[int]:
    if not path.is_absolute():
        raise ExecutionOverlayError("PRIVATE_OVERLAY_ABSOLUTE_PATH_REQUIRED")
    current_path = Path(path.anchor)
    handles = [_windows_open_path(current_path, expect_directory=True)]
    expected_paths = [current_path]
    try:
        for part in path.parts[1:]:
            current_path /= part
            handles.append(_windows_open_path(current_path, expect_directory=True))
            expected_paths.append(current_path)
        if any(
            _windows_final_path(handle) != os.path.normcase(os.path.normpath(str(expected)))
            for handle, expected in zip(handles, expected_paths, strict=True)
        ):
            raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_BINDING_CHANGED")
        return handles
    except Exception:
        _close_windows_handles(handles)
        raise


def _assert_windows_plain_file_handle(handle: int, expected_path: Path) -> None:
    import ctypes

    win_dll = getattr(ctypes, "WinDLL", None)
    if not callable(win_dll):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_SAFE_OPEN_UNAVAILABLE")
    kernel32 = win_dll("kernel32", use_last_error=True)
    get_file_information = kernel32.GetFileInformationByHandle
    get_file_information.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    get_file_information.restype = ctypes.c_int

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", ctypes.c_uint32),
            ("ftCreationTimeLow", ctypes.c_uint32),
            ("ftCreationTimeHigh", ctypes.c_uint32),
            ("ftLastAccessTimeLow", ctypes.c_uint32),
            ("ftLastAccessTimeHigh", ctypes.c_uint32),
            ("ftLastWriteTimeLow", ctypes.c_uint32),
            ("ftLastWriteTimeHigh", ctypes.c_uint32),
            ("dwVolumeSerialNumber", ctypes.c_uint32),
            ("nFileSizeHigh", ctypes.c_uint32),
            ("nFileSizeLow", ctypes.c_uint32),
            ("nNumberOfLinks", ctypes.c_uint32),
            ("nFileIndexHigh", ctypes.c_uint32),
            ("nFileIndexLow", ctypes.c_uint32),
        ]

    information = ByHandleFileInformation()
    if not get_file_information(handle, ctypes.byref(information)):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_HANDLE_INFO_UNAVAILABLE")
    if (
        information.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT
        or information.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY
        or _windows_final_path(handle) != os.path.normcase(os.path.normpath(str(expected_path)))
    ):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_HANDLE_BINDING_INVALID")


def _assert_windows_plain_directory_handle(handle: int, expected_path: Path) -> None:
    import ctypes

    win_dll = getattr(ctypes, "WinDLL", None)
    if not callable(win_dll):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_SAFE_OPEN_UNAVAILABLE")
    kernel32 = win_dll("kernel32", use_last_error=True)
    get_file_information = kernel32.GetFileInformationByHandle
    get_file_information.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    get_file_information.restype = ctypes.c_int

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", ctypes.c_uint32),
            ("ftCreationTimeLow", ctypes.c_uint32),
            ("ftCreationTimeHigh", ctypes.c_uint32),
            ("ftLastAccessTimeLow", ctypes.c_uint32),
            ("ftLastAccessTimeHigh", ctypes.c_uint32),
            ("ftLastWriteTimeLow", ctypes.c_uint32),
            ("ftLastWriteTimeHigh", ctypes.c_uint32),
            ("dwVolumeSerialNumber", ctypes.c_uint32),
            ("nFileSizeHigh", ctypes.c_uint32),
            ("nFileSizeLow", ctypes.c_uint32),
            ("nNumberOfLinks", ctypes.c_uint32),
            ("nFileIndexHigh", ctypes.c_uint32),
            ("nFileIndexLow", ctypes.c_uint32),
        ]

    information = ByHandleFileInformation()
    if not get_file_information(handle, ctypes.byref(information)):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_HANDLE_INFO_UNAVAILABLE")
    if (
        information.dwFileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT
        or not information.dwFileAttributes & _FILE_ATTRIBUTE_DIRECTORY
        or _windows_final_path(handle) != os.path.normcase(os.path.normpath(str(expected_path)))
    ):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_BINDING_CHANGED")


def _open_windows_relative_plain_file(
    *, parent_handle: int, file_name: str, expected_path: Path, create_new: bool
) -> int:
    import ctypes

    if Path(file_name).name != file_name or file_name in {"", ".", ".."}:
        raise ExecutionOverlayError("PRIVATE_OVERLAY_CHILD_NAME_INVALID")
    win_dll = getattr(ctypes, "WinDLL", None)
    if not callable(win_dll):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_SAFE_OPEN_UNAVAILABLE")
    ntdll = win_dll("ntdll", use_last_error=True)

    class UnicodeString(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ushort),
            ("MaximumLength", ctypes.c_ushort),
            ("Buffer", ctypes.c_wchar_p),
        ]

    class ObjectAttributes(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ulong),
            ("RootDirectory", ctypes.c_void_p),
            ("ObjectName", ctypes.POINTER(UnicodeString)),
            ("Attributes", ctypes.c_ulong),
            ("SecurityDescriptor", ctypes.c_void_p),
            ("SecurityQualityOfService", ctypes.c_void_p),
        ]

    class IoStatusValue(ctypes.Union):
        _fields_ = (("Status", ctypes.c_long), ("Pointer", ctypes.c_void_p))

    class IoStatusBlock(ctypes.Structure):
        _fields_ = (("Value", IoStatusValue), ("Information", ctypes.c_size_t))

    relative_buffer = ctypes.create_unicode_buffer(file_name)
    encoded_name = file_name.encode("utf-16-le")
    unicode_name = UnicodeString(
        len(encoded_name),
        len(encoded_name) + 2,
        ctypes.cast(relative_buffer, ctypes.c_wchar_p),
    )
    object_attributes = ObjectAttributes(
        ctypes.sizeof(ObjectAttributes),
        ctypes.c_void_p(parent_handle),
        ctypes.pointer(unicode_name),
        0x00000040,
        None,
        None,
    )
    io_status = IoStatusBlock()
    output_handle = ctypes.c_void_p()
    nt_create_file = ntdll.NtCreateFile
    nt_create_file.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_ulong,
        ctypes.POINTER(ObjectAttributes),
        ctypes.POINTER(IoStatusBlock),
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    nt_create_file.restype = ctypes.c_long
    desired_access = (0xC0000000 if create_new else 0x80000000) | 0x00100000
    status = nt_create_file(
        ctypes.byref(output_handle),
        desired_access,
        ctypes.byref(object_attributes),
        ctypes.byref(io_status),
        None,
        0x00000080,
        0x00000001,
        2 if create_new else 1,
        0x00200000 | 0x00000040 | 0x00000020,
        None,
        0,
    )
    status_code = ctypes.c_uint32(status).value
    if status < 0 or output_handle.value is None:
        if create_new and status_code == 0xC0000035:
            raise ExecutionOverlayError("CREATE_NEW_TARGET_PREEXISTS")
        raise ExecutionOverlayError("PRIVATE_OVERLAY_SAFE_OPEN_FAILED")
    handle = output_handle.value
    try:
        _assert_windows_plain_file_handle(handle, expected_path)
        return handle
    except Exception:
        _close_windows_handles([handle])
        raise


def _open_windows_relative_plain_directory(
    *, parent_handle: int, directory_name: str, expected_path: Path, create_new: bool
) -> int:
    import ctypes

    if Path(directory_name).name != directory_name or directory_name in {"", ".", ".."}:
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_PATH_INVALID")
    win_dll = getattr(ctypes, "WinDLL", None)
    if not callable(win_dll):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_SAFE_OPEN_UNAVAILABLE")
    ntdll = win_dll("ntdll", use_last_error=True)

    class UnicodeString(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ushort),
            ("MaximumLength", ctypes.c_ushort),
            ("Buffer", ctypes.c_wchar_p),
        ]

    class ObjectAttributes(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ulong),
            ("RootDirectory", ctypes.c_void_p),
            ("ObjectName", ctypes.POINTER(UnicodeString)),
            ("Attributes", ctypes.c_ulong),
            ("SecurityDescriptor", ctypes.c_void_p),
            ("SecurityQualityOfService", ctypes.c_void_p),
        ]

    class IoStatusValue(ctypes.Union):
        _fields_ = (("Status", ctypes.c_long), ("Pointer", ctypes.c_void_p))

    class IoStatusBlock(ctypes.Structure):
        _fields_ = (("Value", IoStatusValue), ("Information", ctypes.c_size_t))

    relative_buffer = ctypes.create_unicode_buffer(directory_name)
    encoded_name = directory_name.encode("utf-16-le")
    unicode_name = UnicodeString(
        len(encoded_name),
        len(encoded_name) + 2,
        ctypes.cast(relative_buffer, ctypes.c_wchar_p),
    )
    object_attributes = ObjectAttributes(
        ctypes.sizeof(ObjectAttributes),
        ctypes.c_void_p(parent_handle),
        ctypes.pointer(unicode_name),
        0x00000040,
        None,
        None,
    )
    io_status = IoStatusBlock()
    output_handle = ctypes.c_void_p()
    nt_create_file = ntdll.NtCreateFile
    nt_create_file.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_ulong,
        ctypes.POINTER(ObjectAttributes),
        ctypes.POINTER(IoStatusBlock),
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
    ]
    nt_create_file.restype = ctypes.c_long
    status = nt_create_file(
        ctypes.byref(output_handle),
        0x00100081,
        ctypes.byref(object_attributes),
        ctypes.byref(io_status),
        None,
        _FILE_ATTRIBUTE_DIRECTORY,
        0x00000007,
        2 if create_new else 3,
        0x00200000 | 0x00000020 | 0x00000001,
        None,
        0,
    )
    status_code = ctypes.c_uint32(status).value
    if status < 0 or output_handle.value is None:
        if create_new and status_code == 0xC0000035:
            raise ExecutionOverlayError("CREATE_NEW_TARGET_PREEXISTS")
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_INVALID")
    handle = output_handle.value
    try:
        _assert_windows_plain_directory_handle(handle, expected_path)
        return handle
    except Exception:
        _close_windows_handles([handle])
        raise


def _create_plain_directory_windows(path: Path, *, create_new: bool) -> None:
    if not path.is_absolute() or Path(path.name).name != path.name or path.name in {"", ".", ".."}:
        raise ExecutionOverlayError("PRIVATE_OVERLAY_DIRECTORY_PATH_INVALID")
    handles = _open_windows_directory_chain(path.parent)
    directory_handle: int | None = None
    try:
        _assert_windows_plain_directory_handle(handles[-1], path.parent)
        directory_handle = _open_windows_relative_plain_directory(
            parent_handle=handles[-1],
            directory_name=path.name,
            expected_path=path,
            create_new=create_new,
        )
        _assert_windows_plain_directory_handle(handles[-1], path.parent)
        _assert_windows_plain_directory_handle(directory_handle, path)
    finally:
        if directory_handle is not None:
            _close_windows_handles([directory_handle])
        _close_windows_handles(handles)


def _read_windows_file_handle(handle: int) -> bytes:
    import ctypes

    win_dll = getattr(ctypes, "WinDLL", None)
    if not callable(win_dll):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_SAFE_OPEN_UNAVAILABLE")
    kernel32 = win_dll("kernel32", use_last_error=True)
    get_file_size = kernel32.GetFileSizeEx
    get_file_size.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_longlong)]
    get_file_size.restype = ctypes.c_int
    set_pointer = kernel32.SetFilePointerEx
    set_pointer.argtypes = [
        ctypes.c_void_p,
        ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong),
        ctypes.c_uint32,
    ]
    set_pointer.restype = ctypes.c_int
    read_file = kernel32.ReadFile
    read_file.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    ]
    read_file.restype = ctypes.c_int
    size = ctypes.c_longlong()
    if not get_file_size(handle, ctypes.byref(size)):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_SIZE_UNAVAILABLE")
    if size.value < 0 or size.value > MAX_PRIVATE_OVERLAY_FILE_BYTES:
        raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_BYTE_BOUND_FAILED")
    if not set_pointer(handle, 0, None, 0):
        raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_SEEK_FAILED")
    chunks: list[bytes] = []
    remaining = size.value
    while remaining:
        chunk_size = min(1024 * 1024, remaining)
        buffer = ctypes.create_string_buffer(chunk_size)
        bytes_read = ctypes.c_uint32()
        if not read_file(handle, buffer, chunk_size, ctypes.byref(bytes_read), None):
            raise ExecutionOverlayError("PRIVATE_OVERLAY_FILE_READ_FAILED")
        if bytes_read.value == 0:
            raise ExecutionOverlayError("CREATE_NEW_SHORT_READBACK")
        chunks.append(buffer.raw[: bytes_read.value])
        remaining -= bytes_read.value
    return b"".join(chunks)


def _read_plain_file_bytes_windows(path: Path) -> bytes:
    handles = _open_windows_directory_chain(path.parent)
    file_handle: int | None = None
    try:
        file_handle = _open_windows_relative_plain_file(
            parent_handle=handles[-1],
            file_name=path.name,
            expected_path=path,
            create_new=False,
        )
        result = _read_windows_file_handle(file_handle)
        _assert_windows_plain_file_handle(file_handle, path)
        return result
    finally:
        if file_handle is not None:
            _close_windows_handles([file_handle])
        _close_windows_handles(handles)


def _write_create_new_windows(path: Path, payload: bytes) -> bytes:
    import ctypes

    handles = _open_windows_directory_chain(path.parent)
    file_handle: int | None = None
    try:
        file_handle = _open_windows_relative_plain_file(
            parent_handle=handles[-1],
            file_name=path.name,
            expected_path=path,
            create_new=True,
        )
        win_dll = getattr(ctypes, "WinDLL", None)
        if not callable(win_dll):
            raise ExecutionOverlayError("PRIVATE_OVERLAY_SAFE_OPEN_UNAVAILABLE")
        kernel32 = win_dll("kernel32", use_last_error=True)
        write_file = kernel32.WriteFile
        write_file.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_void_p,
        ]
        write_file.restype = ctypes.c_int
        flush_file = kernel32.FlushFileBuffers
        flush_file.argtypes = [ctypes.c_void_p]
        flush_file.restype = ctypes.c_int
        offset = 0
        while offset < len(payload):
            chunk = payload[offset : offset + (1024 * 1024)]
            buffer = ctypes.create_string_buffer(chunk)
            written = ctypes.c_uint32()
            if not write_file(
                file_handle,
                buffer,
                len(chunk),
                ctypes.byref(written),
                None,
            ):
                raise ExecutionOverlayError("CREATE_NEW_WRITE_FAILED")
            if written.value == 0:
                raise ExecutionOverlayError("CREATE_NEW_SHORT_WRITE")
            offset += written.value
        if not flush_file(file_handle):
            raise ExecutionOverlayError("CREATE_NEW_FLUSH_FAILED")
        actual = _read_windows_file_handle(file_handle)
        _assert_windows_plain_file_handle(file_handle, path)
        return actual
    finally:
        if file_handle is not None:
            _close_windows_handles([file_handle])
        _close_windows_handles(handles)


def _read_plain_file_bytes(path: Path) -> bytes:
    return (
        _read_plain_file_bytes_windows(path)
        if os.name == "nt"
        else _read_plain_file_bytes_posix(path)
    )


def _open_windows_generated_artifact(
    *,
    generated_artifact_path: Path,
    allowed_generated_artifact_root: Path,
) -> tuple[int, list[int]]:
    root_parts = allowed_generated_artifact_root.parts
    if not root_parts:
        raise ExecutionOverlayError("GENERATED_ARTIFACT_SAFE_OPEN_UNAVAILABLE")
    current_path = Path(allowed_generated_artifact_root.anchor)
    handles = [_windows_open_path(current_path, expect_directory=True)]
    expected_paths = [current_path]
    file_handle: int | None = None
    try:
        for part in root_parts[1:]:
            current_path /= part
            handles.append(_windows_open_path(current_path, expect_directory=True))
            expected_paths.append(current_path)
        relative_parts = _relative_artifact_parts(
            generated_artifact_path=generated_artifact_path,
            allowed_generated_artifact_root=allowed_generated_artifact_root,
        )
        for part in relative_parts[:-1]:
            current_path /= part
            handles.append(_windows_open_path(current_path, expect_directory=True))
            expected_paths.append(current_path)
        file_path = current_path / relative_parts[-1]
        file_handle = _windows_open_path(file_path, expect_directory=False)
        if any(
            _windows_final_path(handle) != os.path.normcase(os.path.normpath(str(path)))
            for handle, path in zip(handles, expected_paths, strict=True)
        ):
            raise ExecutionOverlayError("GENERATED_ARTIFACT_ROOT_CHANGED_BEFORE_READ")
        return file_handle, handles
    except Exception:
        if file_handle is not None:
            _close_windows_handles([file_handle])
        _close_windows_handles(handles)
        raise


@contextmanager
def _open_bound_generated_artifact(
    *,
    generated_artifact_path: Path,
    allowed_generated_artifact_root: Path,
) -> Iterator[BinaryIO]:
    if os.name == "nt":
        import msvcrt

        file_handle, ancestor_handles = _open_windows_generated_artifact(
            generated_artifact_path=generated_artifact_path,
            allowed_generated_artifact_root=allowed_generated_artifact_root,
        )
        descriptor: int | None = None
        source: BinaryIO | None = None
        file_handle_owned = True
        try:
            open_osfhandle = getattr(msvcrt, "open_osfhandle", None)
            binary_flag = getattr(os, "O_BINARY", None)
            if not callable(open_osfhandle) or not isinstance(binary_flag, int):
                raise ExecutionOverlayError("GENERATED_ARTIFACT_SAFE_OPEN_UNAVAILABLE")
            descriptor_value = open_osfhandle(file_handle, os.O_RDONLY | binary_flag)
            if not isinstance(descriptor_value, int):
                raise ExecutionOverlayError("GENERATED_ARTIFACT_SAFE_OPEN_UNAVAILABLE")
            descriptor = descriptor_value
            file_handle_owned = False
            source = cast(BinaryIO, os.fdopen(descriptor, "rb"))
            descriptor = None
            yield source
        finally:
            try:
                if source is not None:
                    source.close()
                elif descriptor is not None:
                    os.close(descriptor)
                elif file_handle_owned:
                    _close_windows_handles([file_handle])
            finally:
                _close_windows_handles(ancestor_handles)
        return

    file_descriptor, ancestor_descriptors = _open_posix_generated_artifact(
        generated_artifact_path=generated_artifact_path,
        allowed_generated_artifact_root=allowed_generated_artifact_root,
    )
    source = None
    try:
        source = cast(BinaryIO, os.fdopen(file_descriptor, "rb"))
        yield source
    finally:
        try:
            if source is not None:
                source.close()
            else:
                os.close(file_descriptor)
        finally:
            for descriptor in reversed(ancestor_descriptors):
                os.close(descriptor)


def _copy_or_verify_generated_artifact(
    *,
    generated_artifact_path: Path,
    allowed_generated_artifact_root: Path,
    staging_path: Path,
) -> tuple[str, int, bytes]:
    source_digest = hashlib.sha256()
    first_bytes = b""
    with _open_bound_generated_artifact(
        generated_artifact_path=generated_artifact_path,
        allowed_generated_artifact_root=allowed_generated_artifact_root,
    ) as source:
        opened_before = os.fstat(source.fileno())
        source_size = opened_before.st_size
        if source_size <= 0 or source_size > MAX_RETURNED_BYTES:
            raise ExecutionOverlayError("OUTPUT_REGISTRATION_BYTE_BOUND_FAILED")
        chunks: list[bytes] = []
        copied = 0
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            if not first_bytes:
                first_bytes = chunk[:16]
            copied += len(chunk)
            if copied > MAX_RETURNED_BYTES:
                raise ExecutionOverlayError("OUTPUT_REGISTRATION_BYTE_BOUND_FAILED")
            source_digest.update(chunk)
            chunks.append(chunk)
        opened_after = os.fstat(source.fileno())
    if (
        copied != source_size
        or opened_after.st_size != opened_before.st_size
        or opened_after.st_mtime_ns != opened_before.st_mtime_ns
    ):
        raise ExecutionOverlayError("GENERATED_ARTIFACT_CHANGED_DURING_READ")
    source_sha256 = source_digest.hexdigest()
    payload = b"".join(chunks)
    try:
        staging_sha256, staging_size = _write_bytes_create_or_verify_exact(staging_path, payload)
    except ExecutionOverlayError as error:
        if str(error) == "CREATE_NEW_EXISTING_CONTENT_CONFLICT":
            raise ExecutionOverlayError("OUTPUT_REGISTRATION_STAGING_CONFLICT") from error
        raise
    if staging_size != source_size or staging_sha256 != source_sha256:
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_COPY_DIGEST_MISMATCH")
    return source_sha256, source_size, first_bytes


def _registration_failure_reason(error: Exception) -> str:
    if isinstance(error, ExecutionOverlayError) and re.fullmatch(
        r"[A-Z][A-Z0-9_]{2,127}", str(error)
    ):
        return str(error)
    return "OUTPUT_REGISTRATION_INTERNAL_IO_FAILURE"


def _registration_file_bindings(
    *, root: Path, output_opaque_id: str
) -> tuple[Path, str, Path, str, Path, str]:
    staging_root = root / "staging"
    records_root = root / "records"
    _require_plain_directory(staging_root)
    _require_plain_directory(records_root)
    staging_name = f"{output_opaque_id}.raw"
    record_name = f"output-{output_opaque_id}.json"
    registration_receipt_name = f"registration-{output_opaque_id}.json"
    return (
        _safe_child(staging_root, staging_name),
        record_name,
        _safe_child(records_root, record_name),
        registration_receipt_name,
        _safe_child(records_root, registration_receipt_name),
        staging_name,
    )


def _capture_imagegen_data_url(
    *,
    attempt_handle: OverlayHandle,
    expected_controller_sha256: str,
    action_id: str,
    project_worktree_root: Path,
    imagegen_data_url: str,
    timestamp: str,
) -> dict[str, Any]:
    root, _receipt, _event, state = _transition_context(
        attempt_handle.receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    if (
        state["phase"] != "OUTPUT_REGISTRATION_ATTEMPT_BOUND"
        or state["current_action_id"] != action_id
    ):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_STATE_INVALID")
    attempt = state.get("output_registration_attempt")
    if not isinstance(attempt, dict):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_MISSING")
    if attempt.get("source_delivery_class") != "CODEX_NATIVE_IMAGEGEN_DATA_URL":
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_ATTEMPT_CLASS_MISMATCH")
    private_parent_sha256 = _validate_project_local_private_parent(
        project_worktree_root=project_worktree_root,
        allowed_parent=root.parent,
    )
    if attempt.get("project_private_parent_sha256") != private_parent_sha256:
        raise ExecutionOverlayError("PROJECT_PRIVATE_PARENT_BINDING_MISMATCH")
    output_opaque_id = attempt.get("output_opaque_id")
    if not isinstance(output_opaque_id, str):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_OUTPUT_ID_INVALID")
    _validate_opaque_id(output_opaque_id, "OUTPUT_OPAQUE_ID")

    decoded, media_type, magic_class, data_url_sha256, encoded_payload_bytes = (
        _parse_imagegen_data_url(imagegen_data_url)
    )
    if data_url_sha256 != attempt.get("exact_generated_artifact_receipt_sha256"):
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_BINDING_MISMATCH")
    (
        staging_path,
        _record_name,
        _record_path,
        _registration_receipt_name,
        _registration_receipt_path,
        staging_name,
    ) = _registration_file_bindings(root=root, output_opaque_id=output_opaque_id)
    staging_sha256, byte_size = _write_bytes_create_or_verify_exact(staging_path, decoded)
    source_sha256 = sha256_bytes(decoded)
    if staging_sha256 != source_sha256 or byte_size != len(decoded):
        raise ExecutionOverlayError("IMAGEGEN_DATA_URL_STAGING_VERIFICATION_FAILED")

    capture_sidecar_name = f"capture-{output_opaque_id}.json"
    capture_sidecar_path = _safe_child(root / "records", capture_sidecar_name)
    capture_sidecar = {
        "schema_version": IMAGEGEN_CAPTURE_SIDECAR_SCHEMA,
        "capture_sidecar_id": f"{output_opaque_id}-IMAGEGEN-CAPTURE",
        "output_opaque_id": output_opaque_id,
        "request_ordinal": state["current_ordinal"],
        "action_id": action_id,
        "source_kind": "CODEX_NATIVE_IMAGEGEN",
        "source_delivery_class": "CODEX_NATIVE_IMAGEGEN_DATA_URL",
        "project_private_parent_sha256": private_parent_sha256,
        "data_url_sha256": data_url_sha256,
        "encoded_payload_byte_length": encoded_payload_bytes,
        "staging_file": staging_name,
        "source_sha256": source_sha256,
        "staging_sha256": staging_sha256,
        "byte_size": byte_size,
        "media_type": media_type,
        "magic_byte_class": magic_class,
        "capture_status": "COMMITTED_PRE_DECODE",
        "decode_performed": False,
        "dimensions_read": False,
        "timestamp": timestamp,
    }
    capture_sidecar_sha256, capture_sidecar_bytes = _write_json_create_or_verify_exact(
        capture_sidecar_path, capture_sidecar
    )
    return {
        "source_sha256": source_sha256,
        "staging_sha256": staging_sha256,
        "byte_size": byte_size,
        "media_type": media_type,
        "magic_byte_class": magic_class,
        "capture_sidecar_file": capture_sidecar_name,
        "capture_sidecar_sha256": capture_sidecar_sha256,
        "capture_sidecar_bytes": capture_sidecar_bytes,
        "data_url_sha256": data_url_sha256,
        "encoded_payload_byte_length": encoded_payload_bytes,
        "project_private_parent_sha256": private_parent_sha256,
    }


def _verify_imagegen_capture_binding(
    *,
    root: Path,
    state: Mapping[str, Any],
    action_id: str,
    capture_binding: Mapping[str, Any],
) -> None:
    attempt = state.get("output_registration_attempt")
    if not isinstance(attempt, dict):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_MISSING")
    output_opaque_id = attempt.get("output_opaque_id")
    if not isinstance(output_opaque_id, str):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_OUTPUT_ID_INVALID")
    capture_name = f"capture-{output_opaque_id}.json"
    staging_name = f"{output_opaque_id}.raw"
    if capture_binding.get("capture_sidecar_file") != capture_name:
        raise ExecutionOverlayError("IMAGEGEN_CAPTURE_SIDECAR_BINDING_MISSING")
    capture_path = _safe_child(root / "records", capture_name)
    staging_path = _safe_child(root / "staging", staging_name)
    try:
        capture_bytes = _read_plain_file_bytes(capture_path)
        staging_bytes = _read_plain_file_bytes(staging_path)
    except (ExecutionOverlayError, OSError) as error:
        raise ExecutionOverlayError("IMAGEGEN_CAPTURE_SIDECAR_NOT_VALID_PRE_DECODE") from error
    try:
        capture = json.loads(capture_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ExecutionOverlayError("IMAGEGEN_CAPTURE_SIDECAR_JSON_INVALID") from error
    if not isinstance(capture, dict):
        raise ExecutionOverlayError("IMAGEGEN_CAPTURE_SIDECAR_JSON_INVALID")
    staging_digest = sha256_bytes(staging_bytes)
    media_type, magic_class = _classify_magic(staging_bytes[:16])
    expected_capture_digest = capture_binding.get("capture_sidecar_sha256")
    expected_project_parent = attempt.get("project_private_parent_sha256")
    if (
        not isinstance(expected_capture_digest, str)
        or sha256_bytes(capture_bytes) != expected_capture_digest
        or capture_binding.get("capture_sidecar_bytes") != len(capture_bytes)
        or capture_binding.get("source_sha256") != staging_digest
        or capture_binding.get("staging_sha256") != staging_digest
        or capture_binding.get("byte_size") != len(staging_bytes)
        or capture_binding.get("media_type") != media_type
        or capture_binding.get("magic_byte_class") != magic_class
        or capture_binding.get("data_url_sha256")
        != attempt.get("exact_generated_artifact_receipt_sha256")
        or capture_binding.get("project_private_parent_sha256") != expected_project_parent
        or not isinstance(capture_binding.get("encoded_payload_byte_length"), int)
        or not 1
        <= cast(int, capture_binding.get("encoded_payload_byte_length"))
        <= MAX_DATA_URL_ENCODED_BYTES
        or capture.get("schema_version") != IMAGEGEN_CAPTURE_SIDECAR_SCHEMA
        or capture.get("capture_sidecar_id") != f"{output_opaque_id}-IMAGEGEN-CAPTURE"
        or capture.get("output_opaque_id") != output_opaque_id
        or capture.get("request_ordinal") != state.get("current_ordinal")
        or capture.get("action_id") != action_id
        or capture.get("source_kind") != "CODEX_NATIVE_IMAGEGEN"
        or capture.get("source_delivery_class") != "CODEX_NATIVE_IMAGEGEN_DATA_URL"
        or capture.get("project_private_parent_sha256") != expected_project_parent
        or capture.get("data_url_sha256") != attempt.get("exact_generated_artifact_receipt_sha256")
        or capture.get("encoded_payload_byte_length")
        != capture_binding.get("encoded_payload_byte_length")
        or capture.get("staging_file") != staging_name
        or capture.get("source_sha256") != staging_digest
        or capture.get("staging_sha256") != staging_digest
        or capture.get("byte_size") != len(staging_bytes)
        or capture.get("media_type") != media_type
        or capture.get("magic_byte_class") != magic_class
        or capture.get("capture_status") != "COMMITTED_PRE_DECODE"
        or capture.get("decode_performed") is not False
        or capture.get("dimensions_read") is not False
    ):
        raise ExecutionOverlayError("IMAGEGEN_CAPTURE_SIDECAR_NOT_VALID_PRE_DECODE")


def _commit_output_registration(
    *,
    attempt_handle: OverlayHandle,
    expected_controller_sha256: str,
    action_id: str,
    timestamp: str,
    source_sha256: str,
    staging_sha256: str,
    byte_size: int,
    media_type: str,
    magic_class: str,
    capture_binding: Mapping[str, Any] | None = None,
) -> OverlayHandle:
    _validate_digest(source_sha256, "SOURCE_SHA256")
    _validate_digest(staging_sha256, "STAGING_SHA256")
    if source_sha256 != staging_sha256:
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_SOURCE_STAGING_DIGEST_MISMATCH")
    if not isinstance(byte_size, int) or not 1 <= byte_size <= MAX_RETURNED_BYTES:
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_BYTE_BOUND_FAILED")
    if media_type not in {"image/png", "image/jpeg", "image/webp", "application/octet-stream"}:
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_MEDIA_TYPE_INVALID")
    if not isinstance(magic_class, str) or not magic_class:
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_MAGIC_CLASS_INVALID")

    root, receipt, _event, state = _transition_context(
        attempt_handle.receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    if (
        state["phase"] != "OUTPUT_REGISTRATION_ATTEMPT_BOUND"
        or state["current_action_id"] != action_id
    ):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_STATE_INVALID")
    attempt = state.get("output_registration_attempt")
    if not isinstance(attempt, dict):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_MISSING")
    output_opaque_id = attempt.get("output_opaque_id")
    if not isinstance(output_opaque_id, str):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_OUTPUT_ID_INVALID")
    _validate_opaque_id(output_opaque_id, "OUTPUT_OPAQUE_ID")
    source_delivery_class = attempt.get("source_delivery_class")
    if source_delivery_class not in {
        "TRUSTED_PRINCIPAL_EXACT_IMAGEGEN_OUTPUT_HINT_PATH",
        "CODEX_NATIVE_IMAGEGEN_DATA_URL",
    }:
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_DELIVERY_CLASS_INVALID")
    if (source_delivery_class == "CODEX_NATIVE_IMAGEGEN_DATA_URL") != (capture_binding is not None):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_CAPTURE_BINDING_MISMATCH")
    if capture_binding is not None:
        _verify_imagegen_capture_binding(
            root=root,
            state=state,
            action_id=action_id,
            capture_binding=capture_binding,
        )

    (
        _staging_path,
        record_name,
        record_path,
        registration_receipt_name,
        registration_receipt_path,
        _staging_name,
    ) = _registration_file_bindings(root=root, output_opaque_id=output_opaque_id)
    binding = cast(dict[str, Any], state["binding"])
    registration_receipt_id = f"{output_opaque_id}-REGISTRATION"
    output_record: dict[str, Any] = {
        "schema_version": OUTPUT_RECORD_SCHEMA,
        "output_opaque_id": output_opaque_id,
        "request_ordinal": state["current_ordinal"],
        "source_kind": "CODEX_NATIVE_IMAGEGEN",
        "source_delivery_class": source_delivery_class,
        "exact_generated_artifact_receipt_sha256": attempt[
            "exact_generated_artifact_receipt_sha256"
        ],
        "source_sha256": source_sha256,
        "staging_sha256": staging_sha256,
        "byte_size": byte_size,
        "media_type": media_type,
        "magic_byte_class": magic_class,
        "generation_specification_version": binding["generation_specification_version"],
        "generation_specification_digest": binding["generation_specification_sha256"],
        "assignment_manifest_version": binding["assignment_manifest_version"],
        "assignment_manifest_digest": binding["assignment_manifest_sha256"],
        "request_ledger_status": "DISPATCHED_RETURNED_ONE",
        "output_ledger_status": "RAW_REGISTERED_PRE_DECODE",
        "custody_status": "PRIVATE_STAGING_CREATE_NEW",
        "retention_class": "AUTHORIZED_P2_M5_CALIBRATION_RESEARCH_AND_AUDIT_ONLY",
        "cleanup_policy": "EXACT_REGISTERED_OUTPUT_ID_ONLY",
        "registration_timestamp": timestamp,
        "registration_status": "COMMITTED",
        "registration_commit_receipt": registration_receipt_id,
        "decode_performed": False,
        "dimensions_read": False,
    }
    if capture_binding is not None:
        output_record.update(
            {
                "capture_sidecar_file": capture_binding["capture_sidecar_file"],
                "capture_sidecar_sha256": capture_binding["capture_sidecar_sha256"],
                "data_url_sha256": capture_binding["data_url_sha256"],
                "encoded_payload_byte_length": capture_binding["encoded_payload_byte_length"],
            }
        )
    record_digest, record_size = _write_json_create_or_verify_exact(record_path, output_record)
    registration_receipt: dict[str, Any] = {
        "schema_version": REGISTRATION_RECEIPT_SCHEMA,
        "registration_receipt_id": registration_receipt_id,
        "output_opaque_id": output_opaque_id,
        "request_ordinal": state["current_ordinal"],
        "output_record_file": record_name,
        "output_record_sha256": record_digest,
        "output_record_bytes": record_size,
        "exact_generated_artifact_receipt_sha256": attempt[
            "exact_generated_artifact_receipt_sha256"
        ],
        "source_sha256": source_sha256,
        "staging_sha256": staging_sha256,
        "registration_status": "COMMITTED",
        "receipt_status": "VALID",
        "decode_performed": False,
        "dimensions_read": False,
        "timestamp": timestamp,
    }
    if capture_binding is not None:
        registration_receipt.update(
            {
                "byte_size": byte_size,
                "media_type": media_type,
                "magic_byte_class": magic_class,
                "capture_sidecar_file": capture_binding["capture_sidecar_file"],
                "capture_sidecar_sha256": capture_binding["capture_sidecar_sha256"],
                "capture_sidecar_bytes": capture_binding["capture_sidecar_bytes"],
                "data_url_sha256": capture_binding["data_url_sha256"],
                "encoded_payload_byte_length": capture_binding["encoded_payload_byte_length"],
            }
        )
    registration_digest, _ = _write_json_create_or_verify_exact(
        registration_receipt_path, registration_receipt
    )
    if capture_binding is not None:
        _verify_imagegen_capture_binding(
            root=root,
            state=state,
            action_id=action_id,
            capture_binding=capture_binding,
        )

    counters = dict(cast(dict[str, int], state["counters"]))
    counters["active_calls"] = 0
    _validate_counters(counters)
    sequence = cast(int, receipt["sequence"]) + 1
    new_event: dict[str, Any] = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": "OUTPUT_REGISTRATION_COMMITTED_PRE_DECODE",
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": action_id,
        "request_ordinal": state["current_ordinal"],
        "reason_code": "REGISTER_BEFORE_DECODE_PASS",
        "output_opaque_id": output_opaque_id,
        "output_record_file": record_name,
        "output_record_sha256": record_digest,
        "registration_receipt_file": registration_receipt_name,
        "registration_receipt_sha256": registration_digest,
    }
    if capture_binding is not None:
        new_event.update(
            {
                "capture_sidecar_file": capture_binding["capture_sidecar_file"],
                "capture_sidecar_sha256": capture_binding["capture_sidecar_sha256"],
            }
        )
    output_registration: dict[str, Any] = {
        "output_opaque_id": output_opaque_id,
        "record_file": record_name,
        "record_sha256": record_digest,
        "registration_receipt_file": registration_receipt_name,
        "registration_receipt_sha256": registration_digest,
        "registration_status": "COMMITTED",
        "receipt_status": "VALID",
    }
    if capture_binding is not None:
        output_registration.update(
            {
                "source_delivery_class": source_delivery_class,
                "capture_sidecar_file": capture_binding["capture_sidecar_file"],
                "capture_sidecar_sha256": capture_binding["capture_sidecar_sha256"],
            }
        )
    new_state = dict(state)
    new_state.update(
        {
            "sequence": sequence,
            "phase": "OUTPUT_REGISTERED_PRE_DECODE",
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": sha256_bytes(canonical_json_bytes(new_event)),
            "counters": counters,
            "output_registration": output_registration,
            "decode_authorized": capture_binding is None,
            "hard_stop": False,
        }
    )
    return _commit_transition(
        root=root,
        sequence=sequence,
        controller_sha256=expected_controller_sha256,
        event=new_event,
        state=new_state,
        previous_receipt=_previous_receipt_binding(attempt_handle.receipt_path, receipt),
        registration_receipt=(registration_receipt_name, registration_digest),
    )


def register_output_before_decode(
    *,
    receipt_path: Path,
    expected_controller_sha256: str,
    action_id: str,
    allowed_generated_artifact_root: Path,
    exact_generated_artifact_receipt: str,
    timestamp: str,
) -> OverlayHandle:
    _validate_timestamp(timestamp)
    attempt_handle = _begin_output_registration_attempt(
        receipt_path=receipt_path,
        expected_controller_sha256=expected_controller_sha256,
        action_id=action_id,
        allowed_generated_artifact_root=allowed_generated_artifact_root,
        timestamp=timestamp,
    )
    try:
        root, _receipt, _event, state = _transition_context(
            attempt_handle.receipt_path,
            expected_controller_sha256=expected_controller_sha256,
        )
        if state["phase"] != "OUTPUT_REGISTRATION_ATTEMPT_BOUND":
            raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_STATE_INVALID")
        attempt = cast(dict[str, Any], state["output_registration_attempt"])
        output_opaque_id = cast(str, attempt["output_opaque_id"])
        generated_artifact_path = _validated_generated_artifact_path(
            state=state,
            exact_generated_artifact_receipt=exact_generated_artifact_receipt,
            allowed_generated_artifact_root=allowed_generated_artifact_root,
        )
        if generated_artifact_path.resolve().is_relative_to(root.resolve()):
            raise ExecutionOverlayError("GENERATED_ARTIFACT_INSIDE_OVERLAY_PROHIBITED")

        staging_path, _record_name, _record_path, _registration_name, _registration_path, _ = (
            _registration_file_bindings(root=root, output_opaque_id=output_opaque_id)
        )
        source_sha256, source_size, first_bytes = _copy_or_verify_generated_artifact(
            generated_artifact_path=generated_artifact_path,
            allowed_generated_artifact_root=allowed_generated_artifact_root,
            staging_path=staging_path,
        )
        staging_sha256 = sha256_file(staging_path)
        media_type, magic_class = _classify_magic(first_bytes)
        return _commit_output_registration(
            attempt_handle=attempt_handle,
            expected_controller_sha256=expected_controller_sha256,
            action_id=action_id,
            timestamp=timestamp,
            source_sha256=source_sha256,
            staging_sha256=staging_sha256,
            byte_size=source_size,
            media_type=media_type,
            magic_class=magic_class,
        )
    except (ExecutionOverlayError, OSError, UnicodeError) as error:
        reason_code = _registration_failure_reason(error)
        try:
            return mark_registration_failed(
                receipt_path=attempt_handle.receipt_path,
                expected_controller_sha256=expected_controller_sha256,
                action_id=action_id,
                timestamp=timestamp,
                reason_code=reason_code,
            )
        except ExecutionOverlayError as terminal_error:
            raise ExecutionOverlayError(
                "OUTPUT_REGISTRATION_FAILURE_EVIDENCE_UNCOMMITTED_HARD_STOP"
            ) from terminal_error


def register_imagegen_data_url_before_decode(
    *,
    receipt_path: Path,
    expected_controller_sha256: str,
    action_id: str,
    project_worktree_root: Path,
    imagegen_data_url: str,
    timestamp: str,
) -> OverlayHandle:
    _validate_timestamp(timestamp)
    attempt_handle = _begin_imagegen_data_url_registration_attempt(
        receipt_path=receipt_path,
        expected_controller_sha256=expected_controller_sha256,
        action_id=action_id,
        project_worktree_root=project_worktree_root,
        imagegen_data_url=imagegen_data_url,
        timestamp=timestamp,
    )
    try:
        capture_binding = _capture_imagegen_data_url(
            attempt_handle=attempt_handle,
            expected_controller_sha256=expected_controller_sha256,
            action_id=action_id,
            project_worktree_root=project_worktree_root,
            imagegen_data_url=imagegen_data_url,
            timestamp=timestamp,
        )
        return _commit_output_registration(
            attempt_handle=attempt_handle,
            expected_controller_sha256=expected_controller_sha256,
            action_id=action_id,
            timestamp=timestamp,
            source_sha256=cast(str, capture_binding["source_sha256"]),
            staging_sha256=cast(str, capture_binding["staging_sha256"]),
            byte_size=cast(int, capture_binding["byte_size"]),
            media_type=cast(str, capture_binding["media_type"]),
            magic_class=cast(str, capture_binding["magic_byte_class"]),
            capture_binding=capture_binding,
        )
    except (ExecutionOverlayError, OSError, UnicodeError) as error:
        reason_code = _registration_failure_reason(error)
        try:
            return mark_registration_failed(
                receipt_path=attempt_handle.receipt_path,
                expected_controller_sha256=expected_controller_sha256,
                action_id=action_id,
                timestamp=timestamp,
                reason_code=reason_code,
            )
        except ExecutionOverlayError as terminal_error:
            raise ExecutionOverlayError(
                "OUTPUT_REGISTRATION_FAILURE_EVIDENCE_UNCOMMITTED_HARD_STOP"
            ) from terminal_error


def verify_registration_before_decode(
    receipt_path: Path,
    *,
    expected_controller_sha256: str,
    project_worktree_root: Path | None = None,
) -> dict[str, Any]:
    verified = verify_overlay(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    receipt = cast(dict[str, Any], verified["receipt"])
    state = cast(dict[str, Any], verified["state"])
    if state["phase"] != "OUTPUT_REGISTERED_PRE_DECODE":
        raise ExecutionOverlayError("DECODE_GATE_NOT_OPEN")
    attempt = state.get("output_registration_attempt")
    if not isinstance(attempt, dict):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_ATTEMPT_MISSING")
    source_delivery_class = attempt.get("source_delivery_class")
    if source_delivery_class == "TRUSTED_PRINCIPAL_EXACT_IMAGEGEN_OUTPUT_HINT_PATH":
        if state.get("decode_authorized") is not True:
            raise ExecutionOverlayError("DECODE_GATE_NOT_OPEN")
    elif source_delivery_class == "CODEX_NATIVE_IMAGEGEN_DATA_URL":
        if state.get("decode_authorized") is not False or project_worktree_root is None:
            raise ExecutionOverlayError("IMAGEGEN_CAPTURE_VERIFIER_AUTHORITY_REQUIRED")
    else:
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_DELIVERY_CLASS_INVALID")
    registration = state.get("output_registration")
    if not isinstance(registration, dict):
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_STATE_MISSING")
    root = receipt_path.parent
    _require_plain_directory(root / "records")
    registration_path = _safe_child(
        root / "records", cast(str, registration["registration_receipt_file"])
    )
    record_path = _safe_child(root / "records", cast(str, registration["record_file"]))
    registration_bytes = _read_plain_file_bytes(registration_path)
    record_bytes = _read_plain_file_bytes(record_path)
    if sha256_bytes(registration_bytes) != registration["registration_receipt_sha256"]:
        raise ExecutionOverlayError("REGISTRATION_RECEIPT_DIGEST_MISMATCH")
    if sha256_bytes(record_bytes) != registration["record_sha256"]:
        raise ExecutionOverlayError("OUTPUT_RECORD_DIGEST_MISMATCH")
    try:
        registration_receipt = json.loads(registration_bytes.decode("utf-8"))
        output_record = json.loads(record_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ExecutionOverlayError("REGISTRATION_JSON_INVALID") from error
    if not isinstance(registration_receipt, dict) or not isinstance(output_record, dict):
        raise ExecutionOverlayError("REGISTRATION_JSON_INVALID")
    if (
        registration_receipt.get("receipt_status") != "VALID"
        or registration_receipt.get("registration_status") != "COMMITTED"
        or output_record.get("registration_status") != "COMMITTED"
        or registration_receipt.get("output_record_sha256") != registration["record_sha256"]
        or registration_receipt.get("exact_generated_artifact_receipt_sha256")
        != attempt.get("exact_generated_artifact_receipt_sha256")
        or output_record.get("exact_generated_artifact_receipt_sha256")
        != attempt.get("exact_generated_artifact_receipt_sha256")
        or registration_receipt.get("decode_performed") is not False
        or output_record.get("decode_performed") is not False
        or registration_receipt.get("dimensions_read") is not False
        or output_record.get("dimensions_read") is not False
    ):
        raise ExecutionOverlayError("REGISTRATION_RECEIPT_NOT_VALID_PRE_DECODE")
    if receipt.get("registration_receipt_sha256") != registration["registration_receipt_sha256"]:
        raise ExecutionOverlayError("OVERLAY_RECEIPT_REGISTRATION_BINDING_MISMATCH")
    result = {
        "status": "REGISTER_BEFORE_DECODE_PASS",
        "phase": state["phase"],
        "sequence": state["sequence"],
        "output_opaque_id": registration["output_opaque_id"],
        "source_sha256": output_record["source_sha256"],
        "staging_sha256": output_record["staging_sha256"],
        "byte_size": output_record["byte_size"],
        "media_type": output_record["media_type"],
        "magic_byte_class": output_record["magic_byte_class"],
        "decode_performed": False,
        "dimensions_read": False,
    }
    if source_delivery_class == "CODEX_NATIVE_IMAGEGEN_DATA_URL":
        capture_sidecar_file = registration.get("capture_sidecar_file")
        capture_sidecar_sha256 = registration.get("capture_sidecar_sha256")
        output_opaque_id = registration.get("output_opaque_id")
        if (
            not isinstance(capture_sidecar_file, str)
            or not isinstance(capture_sidecar_sha256, str)
            or not isinstance(output_opaque_id, str)
            or capture_sidecar_file != f"capture-{output_opaque_id}.json"
        ):
            raise ExecutionOverlayError("IMAGEGEN_CAPTURE_SIDECAR_BINDING_MISSING")
        _validate_digest(capture_sidecar_sha256, "CAPTURE_SIDECAR_SHA256")
        private_parent_sha256 = _validate_project_local_private_parent(
            project_worktree_root=cast(Path, project_worktree_root),
            allowed_parent=root.parent,
        )
        encoded_payload_bytes = registration_receipt.get("encoded_payload_byte_length")
        if (
            attempt.get("project_private_parent_sha256") != private_parent_sha256
            or output_record.get("source_delivery_class") != "CODEX_NATIVE_IMAGEGEN_DATA_URL"
            or output_record.get("capture_sidecar_file") != capture_sidecar_file
            or output_record.get("capture_sidecar_sha256") != capture_sidecar_sha256
            or output_record.get("data_url_sha256")
            != attempt.get("exact_generated_artifact_receipt_sha256")
            or output_record.get("encoded_payload_byte_length") != encoded_payload_bytes
            or registration_receipt.get("capture_sidecar_file") != capture_sidecar_file
            or registration_receipt.get("capture_sidecar_sha256") != capture_sidecar_sha256
            or registration_receipt.get("data_url_sha256")
            != attempt.get("exact_generated_artifact_receipt_sha256")
            or registration_receipt.get("source_sha256") != output_record.get("source_sha256")
            or registration_receipt.get("staging_sha256") != output_record.get("staging_sha256")
            or registration_receipt.get("byte_size") != output_record.get("byte_size")
            or registration_receipt.get("media_type") != output_record.get("media_type")
            or registration_receipt.get("magic_byte_class") != output_record.get("magic_byte_class")
        ):
            raise ExecutionOverlayError("IMAGEGEN_CAPTURE_SIDECAR_NOT_VALID_PRE_DECODE")
        capture_binding = {
            "source_sha256": output_record.get("source_sha256"),
            "staging_sha256": output_record.get("staging_sha256"),
            "byte_size": output_record.get("byte_size"),
            "media_type": output_record.get("media_type"),
            "magic_byte_class": output_record.get("magic_byte_class"),
            "capture_sidecar_file": capture_sidecar_file,
            "capture_sidecar_sha256": capture_sidecar_sha256,
            "capture_sidecar_bytes": registration_receipt.get("capture_sidecar_bytes"),
            "data_url_sha256": attempt.get("exact_generated_artifact_receipt_sha256"),
            "encoded_payload_byte_length": encoded_payload_bytes,
            "project_private_parent_sha256": private_parent_sha256,
        }
        _verify_imagegen_capture_binding(
            root=root,
            state=state,
            action_id=cast(str, state["current_action_id"]),
            capture_binding=capture_binding,
        )
        result.update(
            {
                "source_delivery_class": source_delivery_class,
                "capture_sidecar_sha256": capture_sidecar_sha256,
                "decode_authorized": True,
            }
        )
    elif source_delivery_class != "TRUSTED_PRINCIPAL_EXACT_IMAGEGEN_OUTPUT_HINT_PATH":
        raise ExecutionOverlayError("OUTPUT_REGISTRATION_DELIVERY_CLASS_INVALID")
    return result


def _verified_terminal_rollover_predecessor(
    receipt_path: Path,
    *,
    expected_controller_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    verified = verify_overlay(
        receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    receipt = cast(dict[str, Any], verified["receipt"])
    event = cast(dict[str, Any], verified["event"])
    state = cast(dict[str, Any], verified["state"])
    expected_counters = {
        "request_call_count": 2,
        "requested_output_count": 2,
        "returned_output_count": 2,
        "raw_output_count": 2,
        "failed_call_count": 0,
        "rejected_output_count": 0,
        "admitted_identity_count": 0,
        "formal_calls_remaining": 30,
        "formal_raw_capacity_remaining": 30,
        "global_native_output_capacity_remaining": 61,
        "global_native_output_consumed": 3,
        "active_calls": 0,
    }
    attempt = state.get("output_registration_attempt")
    returned_binding = state.get("returned_output_binding")
    if (
        state.get("phase") != "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
        or event.get("event_type") != "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
        or event.get("reason_code") != "GENERATED_ARTIFACT_RECEIPT_INVALID"
        or state.get("hard_stop") is not True
        or state.get("decode_authorized") is not False
        or state.get("current_ordinal") != "CAL-REQ-002"
        or state.get("next_unused_ordinal") != "CAL-REQ-003"
        or state.get("counters") != expected_counters
        or state.get("output_registration") is not None
        or not isinstance(attempt, dict)
        or not isinstance(returned_binding, dict)
        or attempt.get("request_ordinal") != "CAL-REQ-002"
        or returned_binding.get("request_ordinal") != "CAL-REQ-002"
        or attempt.get("action_id") != state.get("current_action_id")
        or returned_binding.get("action_id") != state.get("current_action_id")
        or event.get("action_id") != state.get("current_action_id")
        or event.get("request_ordinal") != "CAL-REQ-002"
    ):
        raise ExecutionOverlayError("ROLLOVER_TERMINAL_PREDECESSOR_INVALID")
    predecessor_binding = {
        "predecessor_overlay_output_id": state["overlay_output_id"],
        "predecessor_terminal_receipt_sha256": sha256_file(receipt_path),
        "predecessor_terminal_state_sha256": receipt["state_sha256"],
        "predecessor_terminal_event_sha256": receipt["event_sha256"],
        "predecessor_terminal_sequence": receipt["sequence"],
        "predecessor_terminal_phase": state["phase"],
        "predecessor_terminal_reason_code": event["reason_code"],
    }
    return receipt, event, state, predecessor_binding


def _rollover_derived_ledger(state: Mapping[str, Any]) -> dict[str, Any]:
    counters = state.get("counters")
    if not isinstance(counters, dict):
        raise ExecutionOverlayError("ROLLOVER_PREDECESSOR_COUNTERS_MISSING")
    _validate_counters(counters)
    return {
        "next_unused_ordinal": state["next_unused_ordinal"],
        "counters": dict(cast(dict[str, int], counters)),
        "cal_req_002_status": "CONSUMED_FAILED_NO_RETRY",
    }


def rollover_terminal_overlay(
    *,
    predecessor_receipt_path: Path,
    expected_controller_sha256: str,
    project_worktree_root: Path,
    allowed_parent: Path,
    successor_root: Path,
    successor_overlay_output_id: str,
    timestamp: str,
) -> OverlayHandle:
    _validate_timestamp(timestamp)
    _validate_opaque_id(successor_overlay_output_id, "SUCCESSOR_OVERLAY_OUTPUT_ID")
    project_private_parent_sha256 = _validate_project_local_private_parent(
        project_worktree_root=project_worktree_root,
        allowed_parent=allowed_parent,
    )
    if not allowed_parent.is_absolute() or not successor_root.is_absolute():
        raise ExecutionOverlayError("ROLLOVER_ABSOLUTE_PATH_REQUIRED")
    if successor_root.parent.resolve() != allowed_parent.resolve():
        raise ExecutionOverlayError("ROLLOVER_SUCCESSOR_ROOT_OUTSIDE_ALLOWED_PARENT")
    if predecessor_receipt_path.parent.parent.resolve() != allowed_parent.resolve():
        raise ExecutionOverlayError("ROLLOVER_PREDECESSOR_ROOT_OUTSIDE_ALLOWED_PARENT")
    if predecessor_receipt_path.parent.resolve() == successor_root.resolve():
        raise ExecutionOverlayError("ROLLOVER_SUCCESSOR_MUST_BE_NEW_ROOT")
    _validate_opaque_id(successor_root.name, "ROLLOVER_SUCCESSOR_ROOT_NAME")

    _receipt, _event, predecessor_state, predecessor_binding = (
        _verified_terminal_rollover_predecessor(
            predecessor_receipt_path,
            expected_controller_sha256=expected_controller_sha256,
        )
    )
    if successor_overlay_output_id == predecessor_state["overlay_output_id"]:
        raise ExecutionOverlayError("ROLLOVER_SUCCESSOR_OVERLAY_ID_MUST_BE_NEW")
    derived_ledger = _rollover_derived_ledger(predecessor_state)
    rollover_intent_id = (
        "ROLLOVER-" + cast(str, predecessor_binding["predecessor_terminal_receipt_sha256"]).upper()
    )
    _validate_opaque_id(rollover_intent_id, "ROLLOVER_INTENT_ID")
    intent_name = f"rollover-intent-{rollover_intent_id}.json"
    intent_path = _safe_child(allowed_parent, intent_name)
    intent = {
        "schema_version": ROLLOVER_INTENT_SCHEMA,
        "rollover_intent_id": rollover_intent_id,
        "controller_sha256": expected_controller_sha256,
        "successor_overlay_output_id": successor_overlay_output_id,
        "successor_root_name": successor_root.name,
        "predecessor": predecessor_binding,
        "derived_ledger": derived_ledger,
        "project_private_parent_sha256": project_private_parent_sha256,
        "create_mode": "CREATE_NEW_OR_RECOVER_EXACT_PARTIAL_ROOT",
        "generation_calls": 0,
        "decode_performed": False,
        "timestamp": timestamp,
    }
    intent_preexisted = intent_path.exists() or intent_path.is_symlink()
    if not intent_preexisted and (successor_root.exists() or successor_root.is_symlink()):
        raise ExecutionOverlayError("ROLLOVER_SUCCESSOR_ROOT_PREEXISTS_WITHOUT_INTENT")
    intent_sha256, _ = _write_json_create_or_verify_exact(intent_path, intent)

    if intent_preexisted:
        _create_or_verify_plain_directory(successor_root)
    else:
        try:
            _create_new_plain_directory(successor_root)
        except ExecutionOverlayError as error:
            if str(error) == "CREATE_NEW_TARGET_PREEXISTS":
                raise ExecutionOverlayError("ROLLOVER_SUCCESSOR_ROOT_CREATE_RACE") from error
            raise
    _create_or_verify_plain_directory(successor_root / "staging")
    _create_or_verify_plain_directory(successor_root / "records")
    if (
        _validate_project_local_private_parent(
            project_worktree_root=project_worktree_root,
            allowed_parent=allowed_parent,
        )
        != project_private_parent_sha256
        or sha256_file(intent_path) != intent_sha256
    ):
        raise ExecutionOverlayError("ROLLOVER_INTENT_PARENT_BINDING_CHANGED")

    cross_root_binding = {
        **predecessor_binding,
        "rollover_intent_id": rollover_intent_id,
        "rollover_intent_file": intent_name,
        "rollover_intent_sha256": intent_sha256,
        "project_private_parent_sha256": project_private_parent_sha256,
    }
    event = {
        "schema_version": EVENT_SCHEMA,
        "overlay_output_id": successor_overlay_output_id,
        "sequence": 0,
        "event_type": "TERMINAL_OVERLAY_ROLLED_FORWARD",
        "timestamp": timestamp,
        "previous_event_sha256": None,
        "action_id": None,
        "request_ordinal": None,
        "reason_code": "TERMINAL_OVERLAY_ROLLED_FORWARD_NO_GENERATION",
        "rollover_predecessor": cross_root_binding,
    }
    state = {
        "schema_version": STATE_SCHEMA,
        "overlay_schema_version": OVERLAY_SCHEMA,
        "overlay_output_id": successor_overlay_output_id,
        "sequence": 0,
        "phase": "READY",
        "timestamp": timestamp,
        "previous_state_sha256": None,
        "last_event_sha256": sha256_bytes(canonical_json_bytes(event)),
        "binding": dict(cast(dict[str, Any], predecessor_state["binding"])),
        "rollover_predecessor": cross_root_binding,
        "counters": dict(cast(dict[str, int], predecessor_state["counters"])),
        "next_unused_ordinal": predecessor_state["next_unused_ordinal"],
        "current_action_id": None,
        "current_ordinal": None,
        "expected_output_opaque_id": None,
        "returned_output_binding": None,
        "output_registration_attempt": None,
        "output_registration": None,
        "decode_authorized": False,
        "hard_stop": False,
    }
    handle = _commit_transition(
        root=successor_root,
        sequence=0,
        controller_sha256=expected_controller_sha256,
        event=event,
        state=state,
        previous_receipt=None,
    )
    verify_rollover_successor(
        handle.receipt_path,
        predecessor_receipt_path=predecessor_receipt_path,
        expected_controller_sha256=expected_controller_sha256,
        project_worktree_root=project_worktree_root,
    )
    return handle


def verify_rollover_successor(
    successor_receipt_path: Path,
    *,
    predecessor_receipt_path: Path,
    expected_controller_sha256: str,
    project_worktree_root: Path,
) -> dict[str, Any]:
    _predecessor_receipt, _predecessor_event, predecessor_state, predecessor_binding = (
        _verified_terminal_rollover_predecessor(
            predecessor_receipt_path,
            expected_controller_sha256=expected_controller_sha256,
        )
    )
    successor_verified = verify_overlay(
        successor_receipt_path,
        expected_controller_sha256=expected_controller_sha256,
    )
    successor_receipt = cast(dict[str, Any], successor_verified["receipt"])
    successor_event = cast(dict[str, Any], successor_verified["event"])
    successor_state = cast(dict[str, Any], successor_verified["state"])
    if (
        successor_receipt_path.parent.parent.resolve()
        != predecessor_receipt_path.parent.parent.resolve()
    ):
        raise ExecutionOverlayError("ROLLOVER_ROOT_PARENT_MISMATCH")
    if successor_receipt_path.parent.resolve() == predecessor_receipt_path.parent.resolve():
        raise ExecutionOverlayError("ROLLOVER_SUCCESSOR_MUST_BE_NEW_ROOT")
    cross_root_binding = successor_state.get("rollover_predecessor")
    event_binding = successor_event.get("rollover_predecessor")
    if not isinstance(cross_root_binding, dict) or event_binding != cross_root_binding:
        raise ExecutionOverlayError("ROLLOVER_CROSS_ROOT_BINDING_MISSING")
    intent_id = cross_root_binding.get("rollover_intent_id")
    intent_name = cross_root_binding.get("rollover_intent_file")
    intent_sha256 = cross_root_binding.get("rollover_intent_sha256")
    if (
        not isinstance(intent_id, str)
        or not isinstance(intent_name, str)
        or not isinstance(intent_sha256, str)
        or intent_name != f"rollover-intent-{intent_id}.json"
    ):
        raise ExecutionOverlayError("ROLLOVER_INTENT_BINDING_INVALID")
    _validate_opaque_id(intent_id, "ROLLOVER_INTENT_ID")
    _validate_digest(intent_sha256, "ROLLOVER_INTENT_SHA256")
    allowed_parent = successor_receipt_path.parent.parent
    project_private_parent_sha256 = _validate_project_local_private_parent(
        project_worktree_root=project_worktree_root,
        allowed_parent=allowed_parent,
    )
    _require_plain_directory(successor_receipt_path.parent / "staging")
    _require_plain_directory(successor_receipt_path.parent / "records")
    intent_path = _safe_child(allowed_parent, intent_name)
    if sha256_file(intent_path) != intent_sha256:
        raise ExecutionOverlayError("ROLLOVER_INTENT_DIGEST_MISMATCH")
    intent = _read_json(intent_path)
    expected_cross_root_binding = {
        **predecessor_binding,
        "rollover_intent_id": intent_id,
        "rollover_intent_file": intent_name,
        "rollover_intent_sha256": intent_sha256,
        "project_private_parent_sha256": project_private_parent_sha256,
    }
    derived_ledger = _rollover_derived_ledger(predecessor_state)
    if (
        cross_root_binding != expected_cross_root_binding
        or intent.get("schema_version") != ROLLOVER_INTENT_SCHEMA
        or intent.get("rollover_intent_id") != intent_id
        or intent.get("controller_sha256") != expected_controller_sha256
        or intent.get("successor_overlay_output_id") != successor_state.get("overlay_output_id")
        or intent.get("successor_root_name") != successor_receipt_path.parent.name
        or intent.get("predecessor") != predecessor_binding
        or intent.get("derived_ledger") != derived_ledger
        or intent.get("project_private_parent_sha256") != project_private_parent_sha256
        or intent.get("create_mode") != "CREATE_NEW_OR_RECOVER_EXACT_PARTIAL_ROOT"
        or intent.get("generation_calls") != 0
        or intent.get("decode_performed") is not False
        or intent.get("timestamp") != successor_state.get("timestamp")
        or successor_event.get("timestamp") != successor_state.get("timestamp")
        or successor_receipt.get("sequence") != 0
        or successor_state.get("phase") != "READY"
        or successor_event.get("event_type") != "TERMINAL_OVERLAY_ROLLED_FORWARD"
        or successor_event.get("reason_code") != "TERMINAL_OVERLAY_ROLLED_FORWARD_NO_GENERATION"
        or successor_state.get("binding") != predecessor_state.get("binding")
        or successor_state.get("counters") != predecessor_state.get("counters")
        or successor_state.get("next_unused_ordinal") != "CAL-REQ-003"
        or successor_state.get("current_action_id") is not None
        or successor_state.get("current_ordinal") is not None
        or successor_state.get("expected_output_opaque_id") is not None
        or successor_state.get("returned_output_binding") is not None
        or successor_state.get("output_registration_attempt") is not None
        or successor_state.get("output_registration") is not None
        or successor_state.get("decode_authorized") is not False
        or successor_state.get("hard_stop") is not False
    ):
        raise ExecutionOverlayError("ROLLOVER_SUCCESSOR_BINDING_INVALID")
    counters = cast(dict[str, int], successor_state["counters"])
    return {
        "status": "TERMINAL_OVERLAY_ROLLOVER_PASS",
        "successor_overlay_output_id": successor_state["overlay_output_id"],
        "predecessor_overlay_output_id": predecessor_binding["predecessor_overlay_output_id"],
        "next_unused_ordinal": successor_state["next_unused_ordinal"],
        "formal_calls_remaining": counters["formal_calls_remaining"],
        "formal_raw_capacity_remaining": counters["formal_raw_capacity_remaining"],
        "global_native_output_capacity_remaining": counters[
            "global_native_output_capacity_remaining"
        ],
        "global_native_output_consumed": counters["global_native_output_consumed"],
        "decode_authorized": False,
    }


def render_private_prompt(
    *,
    prompt_template: Mapping[str, Any],
    assignment_entry: Mapping[str, Any],
    ordinal: str,
    expected_policy_digest: str,
) -> str:
    _validate_digest(expected_policy_digest, "EXPECTED_POLICY_DIGEST")
    if prompt_template.get("plaintext_export") != "PROHIBITED":
        raise ExecutionOverlayError("PRIVATE_PROMPT_EXPORT_POLICY_INVALID")
    if prompt_template.get("status") != "MATERIALIZED_NOT_RENDERED_NOT_DISPATCHED":
        raise ExecutionOverlayError("PRIVATE_PROMPT_TEMPLATE_STATUS_INVALID")
    if prompt_template.get("policy_digest") != expected_policy_digest:
        raise ExecutionOverlayError("PRIVATE_PROMPT_POLICY_DIGEST_MISMATCH")
    if prompt_template.get("render_placeholders") != [
        "REQUEST_ORDINAL",
        "DECLARED_AGE_BAND",
        "MORPHOLOGY_DESCRIPTOR",
        "STYLE_DESCRIPTOR",
    ]:
        raise ExecutionOverlayError("PRIVATE_PROMPT_PLACEHOLDER_CONTRACT_MISMATCH")
    if assignment_entry.get("ordinal") != ordinal:
        raise ExecutionOverlayError("PRIVATE_PROMPT_ASSIGNMENT_ORDINAL_MISMATCH")
    if (
        assignment_entry.get("status") != "NOT_CONSUMED"
        or assignment_entry.get("retryable") is not False
        or assignment_entry.get("policy_binding") != expected_policy_digest
    ):
        raise ExecutionOverlayError("PRIVATE_PROMPT_ASSIGNMENT_AUTHORITY_INVALID")
    declared_age_band = assignment_entry.get("declared_age_band")
    morphology = assignment_entry.get("morphology")
    style_descriptor = assignment_entry.get("style_family")
    if not all(
        isinstance(value, str) and value
        for value in (declared_age_band, morphology, style_descriptor)
    ):
        raise ExecutionOverlayError("PRIVATE_PROMPT_ASSIGNMENT_INCOMPLETE")
    values = {
        "REQUEST_ORDINAL": ordinal,
        "DECLARED_AGE_BAND": declared_age_band,
        "MORPHOLOGY_DESCRIPTOR": morphology,
        "STYLE_DESCRIPTOR": style_descriptor,
    }
    positive = prompt_template.get("positive_segments")
    negative = prompt_template.get("negative_segments")
    if not isinstance(positive, list) or not isinstance(negative, list):
        raise ExecutionOverlayError("PRIVATE_PROMPT_SEGMENTS_INVALID")

    formatter = string.Formatter()

    def render_segment(segment: str) -> str:
        try:
            fields = tuple(formatter.parse(segment))
        except ValueError as error:
            raise ExecutionOverlayError("PRIVATE_PROMPT_PLACEHOLDER_RENDER_FAILED") from error
        for _literal, field_name, format_spec, conversion in fields:
            if field_name is None:
                continue
            if (
                field_name not in _ALLOWED_PRIVATE_PROMPT_FIELDS
                or conversion is not None
                or format_spec
            ):
                raise ExecutionOverlayError("PRIVATE_PROMPT_PLACEHOLDER_RENDER_FAILED")
        try:
            return segment.format_map(values)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
            raise ExecutionOverlayError("PRIVATE_PROMPT_PLACEHOLDER_RENDER_FAILED") from error

    def render_groups(groups: list[Any]) -> list[str]:
        rendered: list[str] = []
        for group in groups:
            if (
                not isinstance(group, list)
                or not group
                or not all(isinstance(item, str) for item in group)
            ):
                raise ExecutionOverlayError("PRIVATE_PROMPT_GROUP_INVALID")
            rendered.append("; ".join(render_segment(item) for item in group))
        return rendered

    positive_lines = render_groups(positive)
    negative_lines = render_groups(negative)
    return "\n".join(
        [
            f"REQUEST_ORDINAL: {ordinal}",
            "POSITIVE_CONSTRAINT_GROUPS:",
            *(f"{index}. {value}" for index, value in enumerate(positive_lines, start=1)),
            "NEGATIVE_CONSTRAINT_GROUPS:",
            *(f"{index}. {value}" for index, value in enumerate(negative_lines, start=1)),
        ]
    )
