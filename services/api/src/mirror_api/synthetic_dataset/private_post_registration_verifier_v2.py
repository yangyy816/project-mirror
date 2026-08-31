"""Independent, bounded authority for the CAL-REQ-004 post-registration hand-off.

This module deliberately does not interpret the legacy overlay state machine. It
only creates and verifies a small, append-only chain after the exact legacy
bridge validates. It never accepts image bytes, a Provider, a model, or an
executable capability.
"""

from __future__ import annotations

import ctypes
import hashlib
import importlib
import json
import os
import re
import stat
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from mirror_api.synthetic_dataset.legacy_overlay_bridge import (
    LegacyBridgeError,
    verify_bridge_for_cal_req_004,
)
from mirror_api.synthetic_dataset.post_registration_request_reference import (
    PostRegistrationRequestReference,
    RequestReferenceError,
)

VERIFIER_V2_VERSION: Final = "p2-m5-post-registration-verifier-v2"
VERIFIER_V2_SCHEMA: Final = "p2-m5-post-registration-verifier-v2-receipt/v1"
_CAL_REQ_004: Final = "CAL-REQ-004"
_ENTRY_PHASE: Final = "OUTPUT_REGISTERED_PRE_DECODE"
_BOUND_PHASE: Final = "POST_REGISTRATION_ATTEMPT_BOUND"
_ROOT_NAME: Final = "post-registration-v2-cal-req-004"
_MAX_RECEIPT_BYTES: Final = 1024 * 1024
_HEX = re.compile(r"^[0-9a-f]{64}$")


class _WindowsProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


@dataclass(frozen=True, slots=True)
class _WindowsNativeBinding:
    get_current_process: Any
    get_process_memory_info: Any


_WINDOWS_BINDING_LOCK = threading.Lock()
_WINDOWS_BINDING: _WindowsNativeBinding | None = None
_WINDOWS_BINDING_INITIALIZATIONS = 0
_VERIFIED_TIPS: OrderedDict[tuple[str, str, str, str, str], Mapping[str, object]] = OrderedDict()
_VERIFIED_TIPS_LOCK = threading.Lock()
_MAX_VERIFIED_TIPS: Final = 32


class PostRegistrationVerifierV2Error(RuntimeError):
    """Fail-closed v2 verifier state error."""


@dataclass(frozen=True, slots=True)
class PostRegistrationVerifierV2Handle:
    """Opaque durable tip. Its local path is never written into a receipt."""

    receipt_path: Path
    receipt_sha256: str
    state_sha256: str


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_digest(value: str, field: str) -> None:
    if not _HEX.fullmatch(value):
        raise PostRegistrationVerifierV2Error(f"V2_{field}_INVALID")


def _require_plain_directory(path: Path) -> None:
    try:
        details = path.lstat()
    except OSError as error:
        raise PostRegistrationVerifierV2Error("V2_DIRECTORY_UNAVAILABLE") from error
    if path.is_symlink() or not stat.S_ISDIR(details.st_mode):
        raise PostRegistrationVerifierV2Error("V2_DIRECTORY_INVALID")


def _require_plain_file(path: Path) -> None:
    try:
        details = path.lstat()
    except OSError as error:
        raise PostRegistrationVerifierV2Error("V2_FILE_UNAVAILABLE") from error
    if path.is_symlink() or not stat.S_ISREG(details.st_mode):
        raise PostRegistrationVerifierV2Error("V2_FILE_INVALID")


def _safe_child(root: Path, name: str) -> Path:
    if Path(name).name != name or name in {"", ".", ".."}:
        raise PostRegistrationVerifierV2Error("V2_CHILD_NAME_INVALID")
    return root / name


def _read_plain_bytes(path: Path) -> bytes:
    _require_plain_file(path)
    value = path.read_bytes()
    if len(value) > _MAX_RECEIPT_BYTES:
        raise PostRegistrationVerifierV2Error("V2_RECEIPT_BYTE_LIMIT_EXCEEDED")
    _require_plain_file(path)
    return value


def _read_json_exact(path: Path) -> dict[str, Any]:
    value = _read_plain_bytes(path)
    try:
        payload = json.loads(value)
    except (TypeError, ValueError) as error:
        raise PostRegistrationVerifierV2Error("V2_RECEIPT_JSON_INVALID") from error
    if not isinstance(payload, dict) or _canonical_json_bytes(payload) != value:
        raise PostRegistrationVerifierV2Error("V2_RECEIPT_NOT_CANONICAL")
    return cast(dict[str, Any], payload)


def _write_create_or_verify_exact(path: Path, payload: Mapping[str, Any]) -> str:
    expected = _canonical_json_bytes(payload)
    try:
        with path.open("xb") as file:
            file.write(expected)
            file.flush()
            os.fsync(file.fileno())
    except FileExistsError:
        actual = _read_plain_bytes(path)
        if actual != expected:
            raise PostRegistrationVerifierV2Error("V2_CREATE_NEW_CONFLICT") from None
    actual = _read_plain_bytes(path)
    if actual != expected:
        raise PostRegistrationVerifierV2Error("V2_CREATE_NEW_READBACK_MISMATCH")
    return _sha256_bytes(actual)


def _receipt_name(sequence: int) -> str:
    if sequence < 0 or sequence > 999_999:
        raise PostRegistrationVerifierV2Error("V2_SEQUENCE_INVALID")
    return f"receipt-{sequence:06d}.json"


def _root_identity_sha256(root: Path) -> str:
    _require_plain_directory(root)
    details = root.stat()
    return _sha256_bytes(_canonical_json_bytes({"device": details.st_dev, "inode": details.st_ino}))


def _windows_native_binding() -> _WindowsNativeBinding:
    """Bind Windows FFI once; no hot-path signature mutation is permitted."""
    global _WINDOWS_BINDING, _WINDOWS_BINDING_INITIALIZATIONS
    if os.name != "nt":
        raise PostRegistrationVerifierV2Error("V2_WINDOWS_FFI_UNAVAILABLE")
    with _WINDOWS_BINDING_LOCK:
        if _WINDOWS_BINDING is None:
            win_dll = getattr(ctypes, "WinDLL", None)
            if not callable(win_dll):
                raise PostRegistrationVerifierV2Error("V2_WINDOWS_FFI_UNAVAILABLE")
            kernel32 = win_dll("kernel32", use_last_error=True)
            psapi = win_dll("psapi", use_last_error=True)
            get_current_process = kernel32.GetCurrentProcess
            get_current_process.argtypes = ()
            get_current_process.restype = ctypes.c_void_p
            get_process_memory_info = psapi.GetProcessMemoryInfo
            get_process_memory_info.argtypes = (
                ctypes.c_void_p,
                ctypes.POINTER(_WindowsProcessMemoryCounters),
                ctypes.c_uint32,
            )
            get_process_memory_info.restype = ctypes.c_int
            _WINDOWS_BINDING = _WindowsNativeBinding(
                get_current_process=get_current_process,
                get_process_memory_info=get_process_memory_info,
            )
            _WINDOWS_BINDING_INITIALIZATIONS += 1
        return _WINDOWS_BINDING


def _windows_native_binding_initialization_count() -> int:
    with _WINDOWS_BINDING_LOCK:
        return _WINDOWS_BINDING_INITIALIZATIONS


def resource_profile() -> Mapping[str, int | None]:
    """Return only aggregate process facts; it never reads an image or receipt."""
    working_set: int | None = None
    if os.name == "nt":
        binding = _windows_native_binding()
        counters = _WindowsProcessMemoryCounters()
        counters.cb = ctypes.sizeof(_WindowsProcessMemoryCounters)
        if not binding.get_process_memory_info(
            binding.get_current_process(), ctypes.byref(counters), counters.cb
        ):
            raise PostRegistrationVerifierV2Error("V2_WINDOWS_RESOURCE_PROFILE_UNAVAILABLE")
        working_set = int(counters.WorkingSetSize)
    return {
        "windows_binding_initializations": _windows_native_binding_initialization_count(),
        "working_set_bytes": working_set,
        "verified_tip_cache_size": _verified_tip_cache_size(),
    }


def initialize_from_legacy_bridge(
    *,
    root: Path,
    bridge_path: Path,
    expected_bridge_sha256: str,
    expected_legacy_controller_sha256: str,
    expected_legacy_receipt_sha256: str,
    expected_verifier_sha256: str,
    timestamp: str,
) -> PostRegistrationVerifierV2Handle:
    """Create or verify the only v2 genesis record for the exact legacy bridge."""
    _validate_digest(expected_bridge_sha256, "BRIDGE_SHA256")
    _validate_digest(expected_legacy_controller_sha256, "LEGACY_CONTROLLER_SHA256")
    _validate_digest(expected_legacy_receipt_sha256, "LEGACY_RECEIPT_SHA256")
    _validate_digest(expected_verifier_sha256, "VERIFIER_SHA256")
    if _sha256_bytes(_read_plain_bytes(Path(__file__))) != expected_verifier_sha256:
        raise PostRegistrationVerifierV2Error("V2_VERIFIER_SHA_MISMATCH")
    try:
        bridge = verify_bridge_for_cal_req_004(
            bridge_path=bridge_path,
            expected_bridge_sha256=expected_bridge_sha256,
            expected_legacy_controller_sha256=expected_legacy_controller_sha256,
            expected_legacy_receipt_sha256=expected_legacy_receipt_sha256,
        )
    except LegacyBridgeError as error:
        raise PostRegistrationVerifierV2Error("V2_LEGACY_BRIDGE_INVALID") from error
    if bridge.get("new_verifier_sha256") != expected_verifier_sha256:
        raise PostRegistrationVerifierV2Error("V2_LEGACY_BRIDGE_VERIFIER_MISMATCH")
    if root.name != _ROOT_NAME:
        raise PostRegistrationVerifierV2Error("V2_ROOT_NAME_INVALID")
    _require_plain_directory(root.parent)
    with _r64_exclusive_lease(root.parent):
        if root.exists() or root.is_symlink():
            _require_plain_directory(root)
        else:
            root.mkdir(mode=0o700)
            _require_plain_directory(root)
        root_identity_sha256 = _root_identity_sha256(root)
        state: dict[str, Any] = {
            "schema_version": VERIFIER_V2_SCHEMA,
            "verifier_version": VERIFIER_V2_VERSION,
            "sequence": 0,
            "phase": _ENTRY_PHASE,
            "allowed_next_transition": _BOUND_PHASE,
            "root_identity_sha256": root_identity_sha256,
            "legacy_bridge_sha256": expected_bridge_sha256,
            "legacy_controller_sha256": expected_legacy_controller_sha256,
            "legacy_receipt_sha256": expected_legacy_receipt_sha256,
            "timestamp": timestamp,
            "bridge": dict(bridge),
            "previous_receipt_sha256": None,
            "previous_state_sha256": None,
            "request_reference_sha256": None,
        }
        return _commit_state(root=root, state=state, verifier_sha256=expected_verifier_sha256)


def append_v2_transition(
    *,
    handle: PostRegistrationVerifierV2Handle,
    expected_verifier_sha256: str,
    request_reference: PostRegistrationRequestReference,
    timestamp: str,
) -> PostRegistrationVerifierV2Handle:
    """Durably bind the exact request reference once, without performing work."""
    root = handle.receipt_path.parent
    with _r64_exclusive_lease(root.parent):
        request_reference = _materialize_request_reference(request_reference)
        _validate_digest(request_reference.sha256, "REQUEST_REFERENCE_SHA256")
        successor_path = _safe_child(root, _receipt_name(1))
        if handle.receipt_path.name == _receipt_name(0) and successor_path.exists():
            successor_payload = _read_json_exact(successor_path)
            successor_receipt = successor_payload.get("receipt")
            successor_state = successor_payload.get("state")
            if not isinstance(successor_receipt, dict) or not isinstance(successor_state, dict):
                raise PostRegistrationVerifierV2Error("V2_SUCCESSOR_SHAPE_INVALID")
            successor = PostRegistrationVerifierV2Handle(
                successor_path,
                _sha256_bytes(_read_plain_bytes(successor_path)),
                cast(str, successor_receipt.get("state_sha256")),
            )
            _verify_v2_chain_unleased(
                handle=successor, expected_verifier_sha256=expected_verifier_sha256
            )
            if (
                request_reference.reference == f"request-{request_reference.sha256[:48]}"
                and _request_reference_digest_is_canonical(request_reference)
                and _request_reference_matches_bridge(request_reference, successor_state)
                and successor_state.get("request_reference_sha256") == request_reference.sha256
            ):
                return successor
            raise PostRegistrationVerifierV2Error("V2_REQUEST_REFERENCE_BINDING_INVALID")
        verified = _verify_v2_chain_unleased(
            handle=handle, expected_verifier_sha256=expected_verifier_sha256
        )
        state = cast(Mapping[str, Any], verified["state"])
        sequence = cast(int, state["sequence"])
        expected_tip = _safe_child(root, _receipt_name(sequence))
        if (
            handle.receipt_path != expected_tip
            or _safe_child(root, _receipt_name(sequence + 1)).exists()
        ):
            raise PostRegistrationVerifierV2Error("V2_STALE_HANDLE_OR_BRANCH_FORK")
        if (
            state.get("phase") != _ENTRY_PHASE
            or state.get("allowed_next_transition") != _BOUND_PHASE
            or state.get("request_reference_sha256") is not None
            or request_reference.reference != f"request-{request_reference.sha256[:48]}"
            or not _request_reference_digest_is_canonical(request_reference)
            or not _request_reference_matches_bridge(request_reference, state)
        ):
            raise PostRegistrationVerifierV2Error("V2_REQUEST_REFERENCE_BINDING_INVALID")
        next_state = dict(state)
        next_state.update(
            {
                "sequence": sequence + 1,
                "phase": _BOUND_PHASE,
                "allowed_next_transition": None,
                "timestamp": timestamp,
                "previous_receipt_sha256": handle.receipt_sha256,
                "previous_state_sha256": handle.state_sha256,
                "request_reference_sha256": request_reference.sha256,
            }
        )
        return _commit_state(root=root, state=next_state, verifier_sha256=expected_verifier_sha256)


def _materialize_request_reference(
    request_reference: PostRegistrationRequestReference,
) -> PostRegistrationRequestReference:
    """Consume an authority mapping exactly once before any security decision."""
    try:
        return PostRegistrationRequestReference(
            reference=request_reference.reference,
            sha256=request_reference.sha256,
            authority=dict(request_reference.authority),
        )
    except (RequestReferenceError, TypeError, ValueError) as error:
        raise PostRegistrationVerifierV2Error("V2_REQUEST_REFERENCE_BINDING_INVALID") from error


def _request_reference_digest_is_canonical(
    request_reference: PostRegistrationRequestReference,
) -> bool:
    authority = request_reference.authority
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in authority.items()):
        return False
    return request_reference.sha256 == _sha256_bytes(_canonical_json_bytes(dict(authority)))


def _request_reference_matches_bridge(
    request_reference: PostRegistrationRequestReference, state: Mapping[str, Any]
) -> bool:
    authority = request_reference.authority
    bridge = state.get("bridge")
    if not isinstance(bridge, Mapping) or set(authority) != {
        "ordinal",
        "action_id",
        "expected_output_id",
        "source_output_sha256",
        "registration_receipt_sha256",
        "legacy_bridge_sha256",
        "policy_version",
        "policy_sha256",
        "runtime_sha256",
        "model_sha256",
    }:
        return False
    runtime_model_authority = bridge.get("runtime_model_authority")
    if (
        not isinstance(runtime_model_authority, Mapping)
        or set(runtime_model_authority)
        != {
            "post_registration_controller_sha256",
            "runtime_sha256_by_platform",
            "model_sha256",
        }
        or not isinstance(runtime_model_authority.get("runtime_sha256_by_platform"), Mapping)
    ):
        return False
    runtime_sha256_by_platform = cast(
        Mapping[str, object], runtime_model_authority["runtime_sha256_by_platform"]
    )
    return (
        authority["ordinal"] == _CAL_REQ_004
        and authority["legacy_bridge_sha256"] == state.get("legacy_bridge_sha256")
        and _sha256_bytes(authority["action_id"].encode("utf-8")) == bridge.get("action_id_sha256")
        and authority["expected_output_id"] == bridge.get("expected_output_id")
        and authority["source_output_sha256"] == bridge.get("registered_output_sha256")
        and authority["registration_receipt_sha256"] == bridge.get("registration_receipt_sha256")
        and authority["policy_version"] == bridge.get("policy_version")
        and authority["policy_sha256"] == bridge.get("policy_sha256")
        and authority["runtime_sha256"] in runtime_sha256_by_platform.values()
        and authority["model_sha256"] == runtime_model_authority.get("model_sha256")
    )


def verify_v2_entry(
    *, handle: PostRegistrationVerifierV2Handle, expected_verifier_sha256: str
) -> Mapping[str, object]:
    """Backward-compatible entry verifier, rejecting an already transitioned tip."""
    verified = _verify_v2_chain(handle=handle, expected_verifier_sha256=expected_verifier_sha256)
    if cast(Mapping[str, object], verified["state"]).get("sequence") != 0:
        raise PostRegistrationVerifierV2Error("V2_ENTRY_NO_LONGER_TIP")
    return verified


def recover_v2_chain(
    *, handle: PostRegistrationVerifierV2Handle, expected_verifier_sha256: str
) -> Mapping[str, object]:
    """Recover from only a durable v2 tip and deterministic predecessor names."""
    return _verify_v2_chain(handle=handle, expected_verifier_sha256=expected_verifier_sha256)


def recover_v2_chain_with_bridge(
    *,
    handle: PostRegistrationVerifierV2Handle,
    bridge_path: Path,
    expected_verifier_sha256: str,
) -> Mapping[str, object]:
    """Recover only when the durable bridge is still byte-identical and exact."""
    verified = _verify_v2_chain(handle=handle, expected_verifier_sha256=expected_verifier_sha256)
    state = cast(Mapping[str, Any], verified["state"])
    try:
        bridge = verify_bridge_for_cal_req_004(
            bridge_path=bridge_path,
            expected_bridge_sha256=cast(str, state["legacy_bridge_sha256"]),
            expected_legacy_controller_sha256=cast(str, state["legacy_controller_sha256"]),
            expected_legacy_receipt_sha256=cast(str, state["legacy_receipt_sha256"]),
        )
    except (KeyError, LegacyBridgeError) as error:
        raise PostRegistrationVerifierV2Error("V2_DURABLE_BRIDGE_RECOVERY_INVALID") from error
    if (
        dict(bridge) != state.get("bridge")
        or bridge.get("new_verifier_sha256") != expected_verifier_sha256
        or bridge.get("scope") != "CAL_REQ_004_POST_REGISTRATION_ONLY"
    ):
        raise PostRegistrationVerifierV2Error("V2_DURABLE_BRIDGE_BINDING_INVALID")
    return verified


def _commit_state(
    *, root: Path, state: Mapping[str, Any], verifier_sha256: str
) -> PostRegistrationVerifierV2Handle:
    sequence = state.get("sequence")
    if not isinstance(sequence, int):
        raise PostRegistrationVerifierV2Error("V2_SEQUENCE_INVALID")
    state_sha256 = _sha256_bytes(_canonical_json_bytes(state))
    receipt = {
        "schema_version": VERIFIER_V2_SCHEMA,
        "sequence": sequence,
        "state_sha256": state_sha256,
        "verifier_sha256": verifier_sha256,
        "legacy_bridge_sha256": state["legacy_bridge_sha256"],
        "root_identity_sha256": state["root_identity_sha256"],
    }
    path = _safe_child(root, _receipt_name(sequence))
    digest = _write_create_or_verify_exact(path, {"receipt": receipt, "state": dict(state)})
    handle = PostRegistrationVerifierV2Handle(path, digest, state_sha256)
    _verify_v2_chain_unleased(handle=handle, expected_verifier_sha256=verifier_sha256)
    return handle


def _verify_v2_chain(
    *, handle: PostRegistrationVerifierV2Handle, expected_verifier_sha256: str
) -> Mapping[str, object]:
    root = handle.receipt_path.parent
    with _r64_exclusive_lease(root.parent):
        return _verify_v2_chain_unleased(
            handle=handle, expected_verifier_sha256=expected_verifier_sha256
        )


def _verify_v2_chain_unleased(
    *, handle: PostRegistrationVerifierV2Handle, expected_verifier_sha256: str
) -> Mapping[str, object]:
    _validate_digest(handle.receipt_sha256, "HANDLE_RECEIPT_SHA256")
    _validate_digest(handle.state_sha256, "HANDLE_STATE_SHA256")
    _validate_digest(expected_verifier_sha256, "VERIFIER_SHA256")
    root = handle.receipt_path.parent
    if root.name != _ROOT_NAME:
        raise PostRegistrationVerifierV2Error("V2_ROOT_NAME_INVALID")
    _require_plain_directory(root)
    payload = _read_json_exact(handle.receipt_path)
    receipt = payload.get("receipt")
    state = payload.get("state")
    if not isinstance(receipt, dict) or not isinstance(state, dict):
        raise PostRegistrationVerifierV2Error("V2_RECEIPT_SHAPE_INVALID")
    sequence = state.get("sequence")
    if (
        not isinstance(sequence, int)
        or handle.receipt_path.name != _receipt_name(sequence)
        or _sha256_bytes(_read_plain_bytes(handle.receipt_path)) != handle.receipt_sha256
        or receipt.get("schema_version") != VERIFIER_V2_SCHEMA
        or receipt.get("sequence") != sequence
        or receipt.get("state_sha256") != handle.state_sha256
        or receipt.get("verifier_sha256") != expected_verifier_sha256
        or _sha256_bytes(_canonical_json_bytes(state)) != handle.state_sha256
        or state.get("schema_version") != VERIFIER_V2_SCHEMA
        or state.get("verifier_version") != VERIFIER_V2_VERSION
        or state.get("root_identity_sha256") != _root_identity_sha256(root)
        or receipt.get("root_identity_sha256") != state.get("root_identity_sha256")
    ):
        raise PostRegistrationVerifierV2Error("V2_ENTRY_BINDING_INVALID")
    if _sha256_bytes(_read_plain_bytes(Path(__file__))) != expected_verifier_sha256:
        raise PostRegistrationVerifierV2Error("V2_VERIFIER_SHA_MISMATCH")
    _validate_state_chain(root=root, tip_receipt=receipt, tip_state=state, sequence=sequence)
    key = (
        cast(str, state["root_identity_sha256"]),
        handle.receipt_sha256,
        handle.state_sha256,
        expected_verifier_sha256,
        _CAL_REQ_004,
    )
    result: Mapping[str, object] = {"receipt": receipt, "state": state}
    with _VERIFIED_TIPS_LOCK:
        _VERIFIED_TIPS[key] = result
        _VERIFIED_TIPS.move_to_end(key)
        while len(_VERIFIED_TIPS) > _MAX_VERIFIED_TIPS:
            _VERIFIED_TIPS.popitem(last=False)
    return result


def _validate_state_chain(
    *, root: Path, tip_receipt: Mapping[str, Any], tip_state: Mapping[str, Any], sequence: int
) -> None:
    expected_names = {_receipt_name(index) for index in range(sequence + 1)}
    actual_names = {child.name for child in root.iterdir()}
    if actual_names != expected_names:
        raise PostRegistrationVerifierV2Error("V2_BRANCH_FORK_OR_ROOT_CONTENT_INVALID")
    current_receipt = dict(tip_receipt)
    current_state = dict(tip_state)
    for index in range(sequence, -1, -1):
        if current_state.get("sequence") != index or current_receipt.get("sequence") != index:
            raise PostRegistrationVerifierV2Error("V2_CHAIN_SEQUENCE_INVALID")
        if current_state.get("legacy_bridge_sha256") != current_receipt.get("legacy_bridge_sha256"):
            raise PostRegistrationVerifierV2Error("V2_CHAIN_BRIDGE_MISMATCH")
        if index == 0:
            if (
                current_state.get("phase") != _ENTRY_PHASE
                or current_state.get("previous_receipt_sha256") is not None
                or current_state.get("previous_state_sha256") is not None
                or current_state.get("request_reference_sha256") is not None
                or not isinstance(current_state.get("bridge"), dict)
                or _sha256_bytes(
                    _canonical_json_bytes(cast(Mapping[str, Any], current_state["bridge"]))
                )
                != current_state.get("legacy_bridge_sha256")
                or current_state["bridge"].get("new_verifier_sha256")
                != current_receipt.get("verifier_sha256")
            ):
                raise PostRegistrationVerifierV2Error("V2_GENESIS_INVALID")
            return
        previous_path = _safe_child(root, _receipt_name(index - 1))
        previous_payload = _read_json_exact(previous_path)
        previous_receipt = previous_payload.get("receipt")
        previous_state = previous_payload.get("state")
        if not isinstance(previous_receipt, dict) or not isinstance(previous_state, dict):
            raise PostRegistrationVerifierV2Error("V2_PREDECESSOR_SHAPE_INVALID")
        previous_digest = _sha256_bytes(_read_plain_bytes(previous_path))
        previous_state_sha256 = _sha256_bytes(_canonical_json_bytes(previous_state))
        if (
            current_state.get("previous_receipt_sha256") != previous_digest
            or current_state.get("previous_state_sha256") != previous_state_sha256
            or previous_receipt.get("state_sha256") != previous_state_sha256
            or current_state.get("phase") != _BOUND_PHASE
            or current_state.get("request_reference_sha256") is None
        ):
            raise PostRegistrationVerifierV2Error("V2_PREDECESSOR_BINDING_INVALID")
        current_receipt = previous_receipt
        current_state = previous_state
    raise PostRegistrationVerifierV2Error("V2_CHAIN_UNREACHABLE")


def _verified_tip_cache_size() -> int:
    with _VERIFIED_TIPS_LOCK:
        return len(_VERIFIED_TIPS)


@contextmanager
def _r64_exclusive_lease(parent: Path) -> Iterator[None]:
    """Bounded lease covering v2 verification, aggregation and durable commits."""
    _require_plain_directory(parent)
    lease_path = _safe_child(parent, ".r64-post-registration-v2.lock")
    descriptor = os.open(lease_path, os.O_RDWR | os.O_CREAT, 0o600)
    locked = False
    deadline = time.monotonic() + 1.0
    try:
        while not locked:
            try:
                if os.name == "nt":
                    msvcrt = cast(Any, importlib.import_module("msvcrt"))

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    fcntl = cast(Any, importlib.import_module("fcntl"))
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise PostRegistrationVerifierV2Error("V2_LEASE_TIMEOUT") from None
                time.sleep(0.025)
        yield
    finally:
        if locked:
            if os.name == "nt":
                msvcrt = cast(Any, importlib.import_module("msvcrt"))

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl = cast(Any, importlib.import_module("fcntl"))
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
