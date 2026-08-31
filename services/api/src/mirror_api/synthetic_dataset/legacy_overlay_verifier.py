"""One-shot, exact-pinned verification of the immutable CAL-REQ-004 overlay."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from mirror_api.synthetic_dataset import private_execution_overlay as _legacy

LEGACY_VERIFIER_VERSION = "p2-m5-cal-req-004-legacy-overlay-verifier-v1"
LEGACY_ATTESTATION_SCHEMA = "p2-m5-legacy-overlay-attestation/v1"
_CAL_REQ_004 = "CAL-REQ-004"
_REGISTERED_PHASE = "OUTPUT_REGISTERED_PRE_DECODE"


class LegacyOverlayVerificationError(RuntimeError):
    """Fail-closed legacy receipt verification error."""


@dataclass(frozen=True, slots=True)
class LegacyOverlayAttestation:
    payload: Mapping[str, object]
    sha256: str


def verify_cal_req_004_once(
    *,
    receipt_path: Path,
    expected_legacy_controller_sha256: str,
    expected_receipt_sha256: str,
    expected_state_sha256: str,
    expected_registration_receipt_sha256: str,
    expected_output_id: str,
    expected_action_id: str,
    verification_timestamp: str,
) -> LegacyOverlayAttestation:
    """Verify one exact legacy receipt without decode, Provider, or mutation."""
    if _legacy.sha256_file(Path(_legacy.__file__)) != expected_legacy_controller_sha256:
        raise LegacyOverlayVerificationError("LEGACY_CONTROLLER_SHA_MISMATCH")
    if _legacy.sha256_file(receipt_path) != expected_receipt_sha256:
        raise LegacyOverlayVerificationError("LEGACY_RECEIPT_SHA_MISMATCH")
    verified = _legacy.verify_overlay(
        receipt_path, expected_controller_sha256=expected_legacy_controller_sha256
    )
    receipt = cast(dict[str, Any], verified["receipt"])
    state = cast(dict[str, Any], verified["state"])
    registration = state.get("output_registration")
    counters = state.get("counters")
    if (
        not isinstance(registration, dict)
        or not isinstance(counters, dict)
        or receipt.get("state_sha256") != expected_state_sha256
        or receipt.get("registration_receipt_sha256") != expected_registration_receipt_sha256
        or state.get("phase") != _REGISTERED_PHASE
        or state.get("current_ordinal") != _CAL_REQ_004
        or state.get("current_action_id") != expected_action_id
        or state.get("expected_output_opaque_id") != expected_output_id
        or registration.get("output_opaque_id") != expected_output_id
        or state.get("sequence") != 6
    ):
        raise LegacyOverlayVerificationError("LEGACY_RECEIPT_BINDING_MISMATCH")
    ledger_digest = _legacy.sha256_bytes(_legacy.canonical_json_bytes(counters))
    payload: dict[str, object] = {
        "schema_version": LEGACY_ATTESTATION_SCHEMA,
        "verifier_version": LEGACY_VERIFIER_VERSION,
        "legacy_controller_sha256": expected_legacy_controller_sha256,
        "legacy_receipt_sha256": expected_receipt_sha256,
        "legacy_state_sha256": expected_state_sha256,
        "request_ordinal": _CAL_REQ_004,
        "action_id_sha256": _legacy.sha256_bytes(expected_action_id.encode("utf-8")),
        "expected_output_id": expected_output_id,
        "phase": _REGISTERED_PHASE,
        "sequence": 6,
        "registration_receipt_sha256": expected_registration_receipt_sha256,
        "resource_ledger_sha256": ledger_digest,
        "verification_timestamp": verification_timestamp,
    }
    digest = _legacy.sha256_bytes(_legacy.canonical_json_bytes(payload))
    return LegacyOverlayAttestation(payload=payload, sha256=digest)
