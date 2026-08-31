"""Append-only bridge from one legacy overlay attestation to verifier v2."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mirror_api.synthetic_dataset import private_execution_overlay as _legacy
from mirror_api.synthetic_dataset.legacy_overlay_verifier import (
    LEGACY_ATTESTATION_SCHEMA,
    LegacyOverlayVerificationError,
    verify_cal_req_004_once,
)

BRIDGE_RECEIPT_VERSION = "p2-m5-cal-req-004-legacy-to-v2-post-registration-bridge/v1"
_CAL_REQ_004 = "CAL-REQ-004"
_PHASE = "OUTPUT_REGISTERED_PRE_DECODE"


class LegacyBridgeError(RuntimeError):
    """Fail-closed bridge creation or verification error."""


@dataclass(frozen=True, slots=True)
class LegacyBridgeReceipt:
    path: Path
    sha256: str
    payload: Mapping[str, object]


def create_or_verify_cal_req_004_bridge_from_legacy_receipt(
    *,
    bridge_path: Path,
    legacy_receipt_path: Path,
    project_worktree_root: Path,
    expected_legacy_controller_sha256: str,
    expected_legacy_receipt_sha256: str,
    expected_legacy_state_sha256: str,
    expected_registration_receipt_sha256: str,
    expected_output_id: str,
    expected_action_id: str,
    verification_timestamp: str,
    expected_new_verifier_sha256: str,
    policy_version: str,
    policy_sha256: str,
) -> LegacyBridgeReceipt:
    """Verify the exact legacy receipt before creating its one bridge receipt."""
    try:
        attestation = verify_cal_req_004_once(
            receipt_path=legacy_receipt_path,
            expected_legacy_controller_sha256=expected_legacy_controller_sha256,
            expected_receipt_sha256=expected_legacy_receipt_sha256,
            expected_state_sha256=expected_legacy_state_sha256,
            expected_registration_receipt_sha256=expected_registration_receipt_sha256,
            expected_output_id=expected_output_id,
            expected_action_id=expected_action_id,
            verification_timestamp=verification_timestamp,
        )
    except LegacyOverlayVerificationError as error:
        raise LegacyBridgeError("LEGACY_RECEIPT_VERIFICATION_FAILED") from error
    try:
        registration = _legacy.verify_registration_before_decode(
            legacy_receipt_path,
            expected_controller_sha256=expected_legacy_controller_sha256,
            project_worktree_root=project_worktree_root,
        )
    except _legacy.ExecutionOverlayError as error:
        raise LegacyBridgeError("LEGACY_REGISTRATION_VERIFICATION_FAILED") from error
    registered_output_sha256 = registration.get("source_sha256")
    if not isinstance(registered_output_sha256, str):
        raise LegacyBridgeError("LEGACY_REGISTERED_OUTPUT_DIGEST_INVALID")
    # No bridge serializer receives caller-provided attestation data.  The
    # attestation below was just created by exact receipt verification above.
    source = dict(attestation.payload)
    required = {
        "schema_version",
        "verifier_version",
        "legacy_controller_sha256",
        "legacy_receipt_sha256",
        "legacy_state_sha256",
        "request_ordinal",
        "action_id_sha256",
        "expected_output_id",
        "resource_ledger_sha256",
        "phase",
        "sequence",
        "registration_receipt_sha256",
        "verification_timestamp",
    }
    if (
        set(source) != required
        or source.get("schema_version") != LEGACY_ATTESTATION_SCHEMA
        or source.get("legacy_controller_sha256") != expected_legacy_controller_sha256
        or source.get("request_ordinal") != _CAL_REQ_004
        or source.get("phase") != _PHASE
        or _legacy.sha256_bytes(_legacy.canonical_json_bytes(source)) != attestation.sha256
    ):
        raise LegacyBridgeError("LEGACY_ATTESTATION_BINDING_INVALID")
    payload: dict[str, object] = {
        "schema_version": BRIDGE_RECEIPT_VERSION,
        "scope": "CAL_REQ_004_POST_REGISTRATION_ONLY",
        "legacy_controller_sha256": expected_legacy_controller_sha256,
        "legacy_receipt_sha256": source["legacy_receipt_sha256"],
        "legacy_state_sha256": source["legacy_state_sha256"],
        "legacy_attestation_sha256": attestation.sha256,
        "new_verifier_sha256": expected_new_verifier_sha256,
        "policy_version": policy_version,
        "policy_sha256": policy_sha256,
        "resource_ledger_sha256": source["resource_ledger_sha256"],
        "registered_output_sha256": registered_output_sha256,
        "phase": _PHASE,
        "allowed_next_transition": "POST_REGISTRATION_ATTEMPT_BOUND",
    }
    receipt_digest, _ = _legacy._write_json_create_or_verify_exact(bridge_path, payload)
    if _legacy._read_plain_file_bytes(bridge_path) != _legacy.canonical_json_bytes(payload):
        raise LegacyBridgeError("BRIDGE_RECEIPT_NOT_CANONICAL")
    if _legacy.sha256_file(bridge_path) != receipt_digest:
        raise LegacyBridgeError("BRIDGE_RECEIPT_DIGEST_MISMATCH")
    return LegacyBridgeReceipt(path=bridge_path, sha256=receipt_digest, payload=payload)


def verify_bridge_for_cal_req_004(
    *,
    bridge_path: Path,
    expected_bridge_sha256: str,
    expected_legacy_controller_sha256: str,
    expected_legacy_receipt_sha256: str,
) -> Mapping[str, object]:
    """Verify exact bridge scope; never infer a legacy receipt from storage."""
    if _legacy.sha256_file(bridge_path) != expected_bridge_sha256:
        raise LegacyBridgeError("BRIDGE_RECEIPT_DIGEST_MISMATCH")
    payload: dict[str, Any] = _legacy._read_json(bridge_path)
    if (
        _legacy._read_plain_file_bytes(bridge_path) != _legacy.canonical_json_bytes(payload)
        or payload.get("schema_version") != BRIDGE_RECEIPT_VERSION
        or payload.get("scope") != "CAL_REQ_004_POST_REGISTRATION_ONLY"
        or payload.get("legacy_controller_sha256") != expected_legacy_controller_sha256
        or payload.get("legacy_receipt_sha256") != expected_legacy_receipt_sha256
        or payload.get("phase") != _PHASE
    ):
        raise LegacyBridgeError("BRIDGE_RECEIPT_BINDING_INVALID")
    return payload
