"""Canonical, authority-bound request reference for verifier v2."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from mirror_api.synthetic_dataset import private_execution_overlay as _legacy


class RequestReferenceError(RuntimeError):
    """Fail-closed request-reference authority error."""


@dataclass(frozen=True, slots=True)
class PostRegistrationRequestReference:
    reference: str
    sha256: str
    authority: Mapping[str, str]

    def __post_init__(self) -> None:
        """Snapshot authority once so digest and bridge checks share identical facts."""
        authority = dict(self.authority)
        if not all(
            isinstance(key, str) and isinstance(value, str) for key, value in authority.items()
        ):
            raise RequestReferenceError("REQUEST_REFERENCE_AUTHORITY_INVALID")
        object.__setattr__(self, "authority", MappingProxyType(authority))


def build_request_reference(
    *,
    ordinal: str,
    action_id: str,
    expected_output_id: str,
    source_output_sha256: str,
    registration_receipt_sha256: str,
    legacy_bridge_sha256: str,
    policy_version: str,
    policy_sha256: str,
    runtime_sha256: str,
    model_sha256: str,
) -> PostRegistrationRequestReference:
    """Return the only valid reference for an exact post-registration input."""
    values: Mapping[str, str] = {
        "ordinal": ordinal,
        "action_id": action_id,
        "expected_output_id": expected_output_id,
        "source_output_sha256": source_output_sha256,
        "registration_receipt_sha256": registration_receipt_sha256,
        "legacy_bridge_sha256": legacy_bridge_sha256,
        "policy_version": policy_version,
        "policy_sha256": policy_sha256,
        "runtime_sha256": runtime_sha256,
        "model_sha256": model_sha256,
    }
    if ordinal != "CAL-REQ-004" or any(not value for value in values.values()):
        raise RequestReferenceError("REQUEST_REFERENCE_AUTHORITY_INVALID")
    digest = _legacy.sha256_bytes(_legacy.canonical_json_bytes(values))
    return PostRegistrationRequestReference(
        reference=f"request-{digest[:48]}", sha256=digest, authority=dict(values)
    )
