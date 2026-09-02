"""Pure, deterministic D07-B effect verification.

This module consumes only declared policy and independently measured facts.  It
does not decode bytes, invoke an editor, create an ImageVersion, or make a
biometric identity claim.  ``publishable`` is therefore only a verifier
decision for a later atomic publisher.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, cast

VERIFIER_VERSION: Final = "demo-tool-verifier-v1"
VERIFIER_SCHEMA_VERSION: Final = "mirror.demo/EffectVerifier/v1"
SUPPORTED_DIMENSIONS: Final = frozenset({"jaw_width", "chin_height", "eye_spacing"})
CATEGORY_ORDER: Final = (
    "STRUCTURAL_IDENTITY_CONSTRAINTS",
    "LOCK_PRESERVATION",
    "TARGET_DELTA",
    "NON_TARGET_DRIFT",
    "ARTIFACT",
    "ORIGINAL_IMMUTABILITY",
    "DECODE_VALIDITY",
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


class EffectVerifierError(ValueError):
    """A policy is not a usable deterministic verifier authority."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class VerificationStatus(StrEnum):
    PASS = "PASS"  # noqa: S105 - protocol status, not a secret
    FAIL = "FAIL"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class VerificationCategory(StrEnum):
    STRUCTURAL_IDENTITY_CONSTRAINTS = "STRUCTURAL_IDENTITY_CONSTRAINTS"
    LOCK_PRESERVATION = "LOCK_PRESERVATION"
    TARGET_DELTA = "TARGET_DELTA"
    NON_TARGET_DRIFT = "NON_TARGET_DRIFT"
    ARTIFACT = "ARTIFACT"
    ORIGINAL_IMMUTABILITY = "ORIGINAL_IMMUTABILITY"
    DECODE_VALIDITY = "DECODE_VALIDITY"


@dataclass(frozen=True, slots=True)
class EffectVerifierPolicy:
    """Explicit thresholds; all ppm values are exact Python ``int`` values."""

    target_tolerance_ppm: int
    structural_drift_thresholds_ppm: Mapping[str, int]
    locked_drift_thresholds_ppm: Mapping[str, int]
    non_target_drift_threshold_ppm: int
    allowed_media_types: tuple[str, ...]
    verifier_version: str = VERIFIER_VERSION

    def __post_init__(self) -> None:
        _require_int(self.target_tolerance_ppm, "target_tolerance_ppm", minimum=0)
        _require_int(
            self.non_target_drift_threshold_ppm,
            "non_target_drift_threshold_ppm",
            minimum=0,
        )
        if self.verifier_version != VERIFIER_VERSION:
            raise EffectVerifierError(
                "UNSUPPORTED_VERIFIER_VERSION", "unsupported verifier version"
            )
        object.__setattr__(
            self,
            "structural_drift_thresholds_ppm",
            _freeze_thresholds(
                self.structural_drift_thresholds_ppm, "structural", allow_empty=False
            ),
        )
        object.__setattr__(
            self,
            "locked_drift_thresholds_ppm",
            _freeze_thresholds(self.locked_drift_thresholds_ppm, "locked", allow_empty=True),
        )
        if not isinstance(self.allowed_media_types, tuple) or not self.allowed_media_types:
            raise EffectVerifierError(
                "INVALID_POLICY", "allowed media types must be a non-empty tuple"
            )
        if any(type(value) is not str or not value for value in self.allowed_media_types):
            raise EffectVerifierError("INVALID_POLICY", "allowed media types are invalid")
        if tuple(sorted(self.allowed_media_types)) != self.allowed_media_types:
            raise EffectVerifierError("INVALID_POLICY", "allowed media types are not canonical")
        if len(set(self.allowed_media_types)) != len(self.allowed_media_types):
            raise EffectVerifierError("INVALID_POLICY", "allowed media types are duplicated")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "allowed_media_types": list(self.allowed_media_types),
            "locked_drift_thresholds_ppm": dict(self.locked_drift_thresholds_ppm),
            "non_target_drift_threshold_ppm": self.non_target_drift_threshold_ppm,
            "schema_version": VERIFIER_SCHEMA_VERSION,
            "structural_drift_thresholds_ppm": dict(self.structural_drift_thresholds_ppm),
            "target_tolerance_ppm": self.target_tolerance_ppm,
            "verifier_version": self.verifier_version,
        }

    def content_digest(self) -> str:
        return _digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class EffectVerificationInput:
    """Untrusted, independently obtained facts for one already-materialized result."""

    source_asset_id: object
    result_asset_id: object
    target_dimension_key: object
    operation_digest: object
    requested_delta_ppm: object
    measured_delta_ppm: object
    structural_drifts_ppm: object
    locked_drifts_ppm: object
    non_target_drift_ppm: object
    artifact_status: object
    artifact_codes: object
    original_before_sha256: object
    original_after_sha256: object
    result_bytes: object
    declared_result_sha256: object
    decode_valid: object
    width: object
    height: object
    media_type: object

    def canonical_payload(self) -> dict[str, object]:
        # Bytes deliberately become their digest: raw image bytes never become authority payload.
        return _canonicalize_input(self)

    def content_digest(self) -> str:
        return _digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class CategoryVerificationResult:
    category: VerificationCategory
    status: VerificationStatus
    reason_codes: tuple[str, ...]
    evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        if tuple(sorted(self.reason_codes)) != self.reason_codes or not self.reason_codes:
            raise EffectVerifierError(
                "INVALID_RESULT", "reason codes must be a non-empty canonical tuple"
            )
        object.__setattr__(self, "evidence", MappingProxyType(_canonical_mapping(self.evidence)))

    def canonical_payload(self) -> dict[str, object]:
        return {
            "category": self.category.value,
            "evidence": dict(self.evidence),
            "reason_codes": list(self.reason_codes),
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class EffectVerificationResult:
    categories: tuple[CategoryVerificationResult, ...]
    policy_digest: str
    request_digest: str
    result_digest: str
    status: VerificationStatus
    publishable: bool
    identity_claim_scope: str = "STRUCTURAL_ONLY_NOT_BIOMETRIC_IDENTITY_VERIFICATION"
    authority_metrics: Mapping[str, object] | None = None
    authority_thresholds: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if tuple(item.category.value for item in self.categories) != CATEGORY_ORDER:
            raise EffectVerifierError("INVALID_RESULT", "categories must be complete and ordered")
        if self.publishable != (self.status is VerificationStatus.PASS):
            raise EffectVerifierError("INVALID_RESULT", "only PASS is publishable")
        if (self.authority_metrics is None) != (self.authority_thresholds is None):
            raise EffectVerifierError(
                "INVALID_RESULT",
                "extended authority metrics and thresholds must be a complete pair",
            )
        if self.authority_metrics is not None:
            if not self.authority_metrics or not self.authority_thresholds:
                raise EffectVerifierError(
                    "INVALID_RESULT", "extended authority evidence must be non-empty"
                )
            object.__setattr__(
                self,
                "authority_metrics",
                MappingProxyType(_canonical_extension_mapping(self.authority_metrics)),
            )
            object.__setattr__(
                self,
                "authority_thresholds",
                MappingProxyType(_canonical_extension_mapping(self.authority_thresholds)),
            )

    def canonical_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "categories": [item.canonical_payload() for item in self.categories],
            "identity_claim_scope": self.identity_claim_scope,
            "policy_digest": self.policy_digest,
            "publishable": self.publishable,
            "request_digest": self.request_digest,
            "result_digest": self.result_digest,
            "schema_version": VERIFIER_SCHEMA_VERSION,
            "status": self.status.value,
            "verifier_version": VERIFIER_VERSION,
        }
        if self.authority_metrics is not None:
            payload["authority_metrics"] = dict(self.authority_metrics)
            payload["authority_thresholds"] = dict(
                cast(Mapping[str, object], self.authority_thresholds)
            )
        return payload

    def content_digest(self) -> str:
        return _digest(self.canonical_payload())


def verify_effect(
    policy: EffectVerifierPolicy, facts: EffectVerificationInput
) -> EffectVerificationResult:
    """Verify seven fixed categories without side effects; malformed facts fail closed."""

    if not isinstance(policy, EffectVerifierPolicy):
        raise EffectVerifierError("INVALID_POLICY", "policy must be EffectVerifierPolicy")
    if not isinstance(facts, EffectVerificationInput):
        raise EffectVerifierError("INVALID_INPUT", "facts must be EffectVerificationInput")
    policy_digest = policy.content_digest()
    request_payload = facts.canonical_payload()
    request_digest = _digest(request_payload)
    categories = (
        _drift_category(
            VerificationCategory.STRUCTURAL_IDENTITY_CONSTRAINTS,
            facts.structural_drifts_ppm,
            policy.structural_drift_thresholds_ppm,
        ),
        _drift_category(
            VerificationCategory.LOCK_PRESERVATION,
            facts.locked_drifts_ppm,
            policy.locked_drift_thresholds_ppm,
        ),
        _target_category(facts, policy),
        _non_target_category(facts, policy),
        _artifact_category(facts),
        _original_category(facts),
        _decode_category(facts, policy),
    )
    status = _overall_status(categories)
    result_digest = _result_bytes_digest(facts.result_bytes) or ""
    return EffectVerificationResult(
        categories=categories,
        policy_digest=policy_digest,
        request_digest=request_digest,
        result_digest=result_digest,
        status=status,
        publishable=status is VerificationStatus.PASS,
    )


def verify_effects(
    policy: EffectVerifierPolicy, facts: EffectVerificationInput
) -> EffectVerificationResult:
    """Compatibility spelling for callers; identical pure verification."""
    return verify_effect(policy, facts)


def _drift_category(
    category: VerificationCategory, supplied: object, thresholds: Mapping[str, int]
) -> CategoryVerificationResult:
    measured = _valid_drift_mapping(supplied)
    if measured is None:
        return _fail(category, "INVALID_REQUIRED_FACT", {"thresholds_ppm": dict(thresholds)})
    missing = sorted(set(thresholds) - set(measured))
    extra = sorted(set(measured) - set(thresholds))
    exceeded = sorted(key for key in thresholds if abs(measured.get(key, 0)) > thresholds[key])
    evidence = {"drifts_ppm": measured, "thresholds_ppm": dict(thresholds)}
    if missing or extra:
        return _fail(category, "DRIFT_KEYS_MISMATCH", evidence)
    if exceeded:
        return _fail(category, "DRIFT_THRESHOLD_EXCEEDED", evidence)
    return _pass(category, evidence)


def _target_category(
    facts: EffectVerificationInput, policy: EffectVerifierPolicy
) -> CategoryVerificationResult:
    requested, measured = facts.requested_delta_ppm, facts.measured_delta_ppm
    evidence = {
        "measured_delta_ppm": measured,
        "operation_digest": facts.operation_digest,
        "requested_delta_ppm": requested,
        "target_dimension_key": facts.target_dimension_key,
        "tolerance_ppm": policy.target_tolerance_ppm,
    }
    if (
        facts.target_dimension_key not in SUPPORTED_DIMENSIONS
        or not _valid_digest(facts.operation_digest)
        or not _is_int(requested)
        or not _is_int(measured)
    ):
        return _fail(VerificationCategory.TARGET_DELTA, "INVALID_REQUIRED_FACT", evidence)
    requested_int = cast(int, requested)
    measured_int = cast(int, measured)
    if requested_int == 0:
        ok = abs(measured_int) <= policy.target_tolerance_ppm
    else:
        ok = (measured_int > 0) == (requested_int > 0) and abs(
            measured_int - requested_int
        ) <= policy.target_tolerance_ppm
    return (
        _pass(VerificationCategory.TARGET_DELTA, evidence)
        if ok
        else _fail(
            VerificationCategory.TARGET_DELTA, "TARGET_DIRECTION_OR_TOLERANCE_FAILED", evidence
        )
    )


def _non_target_category(
    facts: EffectVerificationInput, policy: EffectVerifierPolicy
) -> CategoryVerificationResult:
    evidence = {
        "drift_ppm": facts.non_target_drift_ppm,
        "threshold_ppm": policy.non_target_drift_threshold_ppm,
    }
    if not _is_int(facts.non_target_drift_ppm):
        return _fail(VerificationCategory.NON_TARGET_DRIFT, "INVALID_REQUIRED_FACT", evidence)
    drift = cast(int, facts.non_target_drift_ppm)
    return (
        _pass(VerificationCategory.NON_TARGET_DRIFT, evidence)
        if abs(drift) <= policy.non_target_drift_threshold_ppm
        else _fail(VerificationCategory.NON_TARGET_DRIFT, "NON_TARGET_DRIFT_EXCEEDED", evidence)
    )


def _artifact_category(facts: EffectVerificationInput) -> CategoryVerificationResult:
    evidence = {"artifact_codes": facts.artifact_codes, "artifact_status": facts.artifact_status}
    if facts.artifact_status not in {"PASS", "FAIL", "HUMAN_REVIEW"} or not _valid_codes(
        facts.artifact_codes
    ):
        return _fail(VerificationCategory.ARTIFACT, "INVALID_REQUIRED_FACT", evidence)
    if facts.artifact_codes:
        return _fail(VerificationCategory.ARTIFACT, "ARTIFACT_CHECK_FAILED", evidence)
    if facts.artifact_status == "HUMAN_REVIEW":
        return _review(VerificationCategory.ARTIFACT, "ARTIFACT_REQUIRES_HUMAN_REVIEW", evidence)
    if facts.artifact_status != "PASS":
        return _fail(VerificationCategory.ARTIFACT, "ARTIFACT_CHECK_FAILED", evidence)
    return _pass(VerificationCategory.ARTIFACT, evidence)


def _original_category(facts: EffectVerificationInput) -> CategoryVerificationResult:
    bytes_digest = _result_bytes_digest(facts.result_bytes)
    evidence = {
        "declared_result_sha256": facts.declared_result_sha256,
        "original_after_sha256": facts.original_after_sha256,
        "original_before_sha256": facts.original_before_sha256,
        "result_bytes_sha256": bytes_digest,
        "result_asset_id": facts.result_asset_id,
        "source_asset_id": facts.source_asset_id,
    }
    required = (
        facts.source_asset_id,
        facts.result_asset_id,
        facts.original_before_sha256,
        facts.original_after_sha256,
        facts.declared_result_sha256,
    )
    if (
        type(facts.source_asset_id) is not str
        or _ID.fullmatch(facts.source_asset_id) is None
        or type(facts.result_asset_id) is not str
        or _ID.fullmatch(facts.result_asset_id) is None
        or not all(_valid_digest(item) for item in required[2:])
        or bytes_digest is None
    ):
        return _fail(VerificationCategory.ORIGINAL_IMMUTABILITY, "INVALID_REQUIRED_FACT", evidence)
    if facts.source_asset_id == facts.result_asset_id:
        return _fail(
            VerificationCategory.ORIGINAL_IMMUTABILITY, "SOURCE_RESULT_ASSET_NOT_DISTINCT", evidence
        )
    if facts.original_before_sha256 != facts.original_after_sha256:
        return _fail(VerificationCategory.ORIGINAL_IMMUTABILITY, "ORIGINAL_MUTATED", evidence)
    if bytes_digest != facts.declared_result_sha256:
        return _fail(VerificationCategory.ORIGINAL_IMMUTABILITY, "RESULT_DIGEST_MISMATCH", evidence)
    return _pass(VerificationCategory.ORIGINAL_IMMUTABILITY, evidence)


def _decode_category(
    facts: EffectVerificationInput, policy: EffectVerifierPolicy
) -> CategoryVerificationResult:
    evidence = {
        "decode_valid": facts.decode_valid,
        "height": facts.height,
        "media_type": facts.media_type,
        "width": facts.width,
    }
    ok = (
        facts.decode_valid is True
        and _is_int(facts.width)
        and cast(int, facts.width) > 0
        and _is_int(facts.height)
        and cast(int, facts.height) > 0
        and facts.media_type in policy.allowed_media_types
    )
    return (
        _pass(VerificationCategory.DECODE_VALIDITY, evidence)
        if ok
        else _fail(VerificationCategory.DECODE_VALIDITY, "DECODE_OR_MEDIA_INVALID", evidence)
    )


def _pass(
    category: VerificationCategory, evidence: Mapping[str, object]
) -> CategoryVerificationResult:
    return CategoryVerificationResult(category, VerificationStatus.PASS, ("VERIFIED",), evidence)


def _fail(
    category: VerificationCategory, code: str, evidence: Mapping[str, object]
) -> CategoryVerificationResult:
    return CategoryVerificationResult(category, VerificationStatus.FAIL, (code,), evidence)


def _review(
    category: VerificationCategory, code: str, evidence: Mapping[str, object]
) -> CategoryVerificationResult:
    return CategoryVerificationResult(category, VerificationStatus.HUMAN_REVIEW, (code,), evidence)


def _overall_status(categories: tuple[CategoryVerificationResult, ...]) -> VerificationStatus:
    if any(item.status is VerificationStatus.FAIL for item in categories):
        return VerificationStatus.FAIL
    if any(item.status is VerificationStatus.HUMAN_REVIEW for item in categories):
        return VerificationStatus.HUMAN_REVIEW
    return VerificationStatus.PASS


def _freeze_thresholds(
    value: Mapping[str, int], kind: str, *, allow_empty: bool
) -> Mapping[str, int]:
    if not isinstance(value, Mapping) or (not value and not allow_empty):
        raise EffectVerifierError(
            "INVALID_POLICY", f"{kind} thresholds must be a non-empty mapping"
        )
    result: dict[str, int] = {}
    for key, threshold in value.items():
        if type(key) is not str or key not in SUPPORTED_DIMENSIONS:
            raise EffectVerifierError(
                "INVALID_POLICY", f"{kind} threshold dimension is unsupported"
            )
        _require_int(threshold, f"{kind} threshold", minimum=0)
        result[key] = threshold
    return MappingProxyType(dict(sorted(result.items())))


def _valid_drift_mapping(value: object) -> dict[str, int] | None:
    if not isinstance(value, Mapping):
        return None
    result: dict[str, int] = {}
    for key, drift in value.items():
        if type(key) is not str or key not in SUPPORTED_DIMENSIONS or not _is_int(drift):
            return None
        result[key] = drift
    return dict(sorted(result.items()))


def _valid_codes(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and all(type(item) is str and _CODE.fullmatch(item) for item in value)
        and tuple(sorted(value)) == value
        and len(set(value)) == len(value)
    )


def _canonicalize_input(facts: EffectVerificationInput) -> dict[str, object]:
    raw = {
        "artifact_codes": facts.artifact_codes,
        "artifact_status": facts.artifact_status,
        "declared_result_sha256": facts.declared_result_sha256,
        "decode_valid": facts.decode_valid,
        "height": facts.height,
        "locked_drifts_ppm": facts.locked_drifts_ppm,
        "media_type": facts.media_type,
        "measured_delta_ppm": facts.measured_delta_ppm,
        "non_target_drift_ppm": facts.non_target_drift_ppm,
        "operation_digest": facts.operation_digest,
        "original_after_sha256": facts.original_after_sha256,
        "original_before_sha256": facts.original_before_sha256,
        "requested_delta_ppm": facts.requested_delta_ppm,
        "result_asset_id": facts.result_asset_id,
        "result_bytes_sha256": _result_bytes_digest(facts.result_bytes),
        "source_asset_id": facts.source_asset_id,
        "structural_drifts_ppm": facts.structural_drifts_ppm,
        "target_dimension_key": facts.target_dimension_key,
        "width": facts.width,
    }
    return _canonical_mapping(raw)


def _canonical_mapping(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in sorted(value):
        item = value[key]
        if isinstance(item, Mapping):
            result[key] = _canonical_mapping(item)
        elif isinstance(item, tuple):
            result[key] = [_canonical_value(part) for part in item]
        else:
            result[key] = _canonical_value(item)
    return result


def _canonical_extension_mapping(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in sorted(value):
        if type(key) is not str or not key:
            raise EffectVerifierError("INVALID_RESULT", "extended authority key is invalid")
        result[key] = _canonical_extension_value(value[key])
    return result


def _canonical_extension_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _canonical_extension_mapping(cast(Mapping[str, object], value))
    if isinstance(value, (tuple, list)):
        return [_canonical_extension_value(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise EffectVerifierError("INVALID_RESULT", "extended authority value is invalid")


def _canonical_value(value: object) -> object:
    if isinstance(value, float):
        return "INVALID_FLOAT"
    if isinstance(value, Mapping):
        return _canonical_mapping(value)
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return "INVALID_TYPE"


def _digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        VERIFIER_SCHEMA_VERSION.encode("utf-8")
        + b"\n"
        + json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()


def _result_bytes_digest(value: object) -> str | None:
    return hashlib.sha256(value).hexdigest() if type(value) is bytes and value else None


def _valid_digest(value: object) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _is_int(value: object) -> bool:
    return type(value) is int


def _require_int(value: object, name: str, *, minimum: int) -> None:
    if not _is_int(value) or cast(int, value) < minimum:
        raise EffectVerifierError("INVALID_POLICY", f"{name} must be an integer at least {minimum}")
