"""Fail-closed D07-B geometry execution boundary.

This module intentionally does not load a geometry runtime or persist an image
version.  It converts one canonical D07-A geometry operation into a typed
adapter request, validates the qualified adapter's returned lineage/evidence,
and produces a deterministic envelope for the later application and verifier
layers.  A completed materialization is *not* a biometric identity claim and
is deliberately left ``PENDING_INDEPENDENT_VERIFIER``.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    canonical_json_bytes,
)
from mirror_api.providers.opencv_geometry import ALGORITHM_VERSION, CANDIDATE_ID

GEOMETRY_EXECUTION_SCHEMA_VERSION: Final = "mirror.demo/GeometryExecution/v1"
GEOMETRY_EXECUTION_ALGORITHM_VERSION: Final = "demo-geometry-execution-boundary-v1"
M4_QUALIFIED_CANDIDATE_ID: Final = CANDIDATE_ID
M4_QUALIFIED_ALGORITHM_VERSION: Final = ALGORITHM_VERSION
M4_RESULT_MEDIA_TYPE: Final = "image/jpeg"
STRUCTURAL_EVIDENCE_ONLY: Final = "STRUCTURAL_EVIDENCE_ONLY_NOT_BIOMETRIC_IDENTITY_VERIFICATION"
PENDING_INDEPENDENT_VERIFIER: Final = "PENDING_INDEPENDENT_VERIFIER"
SUPPORTED_DIMENSIONS: Final = frozenset({"jaw_width", "chin_height", "eye_spacing"})
MAX_DIMENSION_DELTA_PPM: Final = 100_000
MAX_NON_TARGET_DRIFT_PPM: Final = 1_000_000
MAX_IMAGE_DIMENSION: Final = 20_000

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[0-9a-f]{32}$")
_OPAQUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ARTIFACT_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")


class GeometryExecutionState(StrEnum):
    MATERIALIZED = "MATERIALIZED"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class GeometryExecutionError(ValueError):
    """A caller or adapter payload violates this immutable execution boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class GeometryBackendIdentity:
    """Exact M4 candidate/runtime/config facts required for one execution."""

    candidate_id: str
    algorithm_version: str
    runtime_manifest_digest: str
    configuration_digest: str

    def __post_init__(self) -> None:
        _require_opaque(self.candidate_id, "candidate_id")
        _require_opaque(self.algorithm_version, "algorithm_version")
        _require_digest(self.runtime_manifest_digest, "runtime_manifest_digest")
        _require_digest(self.configuration_digest, "configuration_digest")

    def canonical_payload(self) -> dict[str, str]:
        return {
            "algorithm_version": self.algorithm_version,
            "candidate_id": self.candidate_id,
            "configuration_digest": self.configuration_digest,
            "runtime_manifest_digest": self.runtime_manifest_digest,
        }


@dataclass(frozen=True, slots=True)
class GeometryExecutionRequest:
    """Immutable input facts for a single D07-A geometry materialization."""

    operation: OperationSpec
    required_backend: GeometryBackendIdentity
    source_asset_id: str
    source_asset_sha256: str
    source_bytes: bytes
    source_image_version_digest: str
    source_image_version_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.operation, OperationSpec):
            raise GeometryExecutionError(
                "INVALID_OPERATION", "operation must be a frozen OperationSpec"
            )
        _validate_geometry_operation(self.operation)
        if (
            self.required_backend.candidate_id != M4_QUALIFIED_CANDIDATE_ID
            or self.required_backend.algorithm_version != M4_QUALIFIED_ALGORITHM_VERSION
        ):
            raise GeometryExecutionError(
                "UNQUALIFIED_BACKEND", "request must bind the frozen P2-M4 candidate and algorithm"
            )
        _require_id(self.source_asset_id, "source_asset_id")
        _require_digest(self.source_asset_sha256, "source_asset_sha256")
        _require_id(self.source_image_version_id, "source_image_version_id")
        _require_digest(self.source_image_version_digest, "source_image_version_digest")
        if type(self.source_bytes) is not bytes or not self.source_bytes:
            raise GeometryExecutionError(
                "INVALID_SOURCE", "source bytes must be non-empty immutable bytes"
            )
        if hashlib.sha256(self.source_bytes).hexdigest() != self.source_asset_sha256:
            raise GeometryExecutionError(
                "SOURCE_DIGEST_MISMATCH", "source bytes do not match source asset digest"
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "algorithm_version": GEOMETRY_EXECUTION_ALGORITHM_VERSION,
            "operation": self.operation.canonical_payload(),
            "required_backend": self.required_backend.canonical_payload(),
            "schema_version": GEOMETRY_EXECUTION_SCHEMA_VERSION,
            "source_asset_id": self.source_asset_id,
            "source_asset_sha256": self.source_asset_sha256,
            "source_image_version_digest": self.source_image_version_digest,
            "source_image_version_id": self.source_image_version_id,
        }

    def content_digest(self) -> str:
        return _content_digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class GeometryAdapterRequest:
    """The only typed payload a qualified geometry adapter receives."""

    operation_digest: str
    requested_delta_ppm: int
    requested_dimension_key: str
    required_backend: GeometryBackendIdentity
    source_asset_id: str
    source_asset_sha256: str
    source_bytes: bytes
    source_image_version_digest: str
    source_image_version_id: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "operation_digest": self.operation_digest,
            "requested_delta_ppm": self.requested_delta_ppm,
            "requested_dimension_key": self.requested_dimension_key,
            "required_backend": self.required_backend.canonical_payload(),
            "source_asset_id": self.source_asset_id,
            "source_asset_sha256": self.source_asset_sha256,
            "source_image_version_digest": self.source_image_version_digest,
            "source_image_version_id": self.source_image_version_id,
        }


@dataclass(frozen=True, slots=True)
class GeometryAdapterResult:
    """Untrusted adapter result; every fact is revalidated before publication."""

    artifact_codes: tuple[str, ...]
    artifact_status: str
    content: bytes
    content_sha256: str
    height: int
    identity: GeometryBackendIdentity
    measured_delta_ppm: int
    measurement_config_digest: str
    media_type: str
    non_target_drift_ppm: int
    quarantined: bool
    source_asset_sha256: str
    width: int


class GeometryExecutionBackend(Protocol):
    """Injected adapter; production wiring remains outside this pure boundary."""

    @property
    def identity(self) -> GeometryBackendIdentity: ...

    def execute(self, *, request: GeometryAdapterRequest) -> GeometryAdapterResult: ...


@dataclass(frozen=True, slots=True)
class GeometryExecutionSuccess:
    artifact_codes: tuple[str, ...]
    backend: GeometryBackendIdentity
    height: int
    measured_delta_ppm: int
    measurement_config_digest: str
    non_target_drift_ppm: int
    output_bytes: bytes
    result_sha256: str
    source_asset_id: str
    source_asset_sha256: str
    source_image_version_digest: str
    source_image_version_id: str
    width: int

    def canonical_payload(self) -> dict[str, object]:
        return {
            "artifact_codes": list(self.artifact_codes),
            "backend": self.backend.canonical_payload(),
            "height": self.height,
            "identity_claim_scope": STRUCTURAL_EVIDENCE_ONLY,
            "measured_delta_ppm": self.measured_delta_ppm,
            "measurement_config_digest": self.measurement_config_digest,
            "non_target_drift_ppm": self.non_target_drift_ppm,
            "result_media_type": M4_RESULT_MEDIA_TYPE,
            "result_sha256": self.result_sha256,
            "source_asset_id": self.source_asset_id,
            "source_asset_sha256": self.source_asset_sha256,
            "source_image_version_digest": self.source_image_version_digest,
            "source_image_version_id": self.source_image_version_id,
            "verification_state": PENDING_INDEPENDENT_VERIFIER,
            "width": self.width,
        }


@dataclass(frozen=True, slots=True)
class GeometryExecutionOutcome:
    """A result envelope that makes failure non-publishable by construction."""

    request_digest: str
    state: GeometryExecutionState
    reason_code: str
    success: GeometryExecutionSuccess | None = None

    def __post_init__(self) -> None:
        _require_digest(self.request_digest, "request_digest")
        _require_opaque(self.reason_code, "reason_code")
        if self.state is GeometryExecutionState.MATERIALIZED:
            if self.success is None:
                raise GeometryExecutionError(
                    "INVALID_OUTCOME", "materialized outcome needs success facts"
                )
        elif self.success is not None:
            raise GeometryExecutionError(
                "INVALID_OUTCOME", "failed outcome must not publish output"
            )

    @property
    def publishable(self) -> bool:
        # This boundary deliberately stops before the independent Verifier.
        # Materialized bytes may be handed to that verifier, never published.
        return False

    @property
    def ready_for_verification(self) -> bool:
        return self.state is GeometryExecutionState.MATERIALIZED

    def canonical_payload(self) -> dict[str, object]:
        result: dict[str, object] = {
            "request_digest": self.request_digest,
            "schema_version": GEOMETRY_EXECUTION_SCHEMA_VERSION,
            "state": self.state.value,
            "reason_code": self.reason_code,
        }
        if self.success is not None:
            result["success"] = self.success.canonical_payload()
        return result

    def content_digest(self) -> str:
        return _content_digest(self.canonical_payload())


def execute_geometry_operation(
    request: GeometryExecutionRequest, backend: GeometryExecutionBackend | None
) -> GeometryExecutionOutcome:
    """Execute one qualified geometry request without silently falling back.

    A materialized success may be handed only to the independent Verifier; it
    is not publishable at this adapter boundary. Adapter failures, mismatched
    runtime identity, invalid output, artifact failures, and quarantine all
    return a non-publishable outcome that is not verifier-ready.
    """

    if not isinstance(request, GeometryExecutionRequest):
        raise GeometryExecutionError(
            "INVALID_REQUEST", "request must be a GeometryExecutionRequest"
        )
    request_digest = request.content_digest()
    if backend is None:
        return _failure(
            request_digest, GeometryExecutionState.CAPABILITY_UNAVAILABLE, "BACKEND_MISSING"
        )
    try:
        if backend.identity != request.required_backend:
            return _failure(
                request_digest,
                GeometryExecutionState.CAPABILITY_UNAVAILABLE,
                "QUALIFIED_BACKEND_UNAVAILABLE",
            )
    except Exception:
        return _failure(request_digest, GeometryExecutionState.FAILED, "BACKEND_IDENTITY_INVALID")

    adapter_request = _adapter_request(request)
    source_before = request.source_bytes
    try:
        adapter_result = backend.execute(request=adapter_request)
    except Exception:
        return _failure(request_digest, GeometryExecutionState.FAILED, "BACKEND_EXECUTION_FAILED")
    if request.source_bytes != source_before:
        return _failure(request_digest, GeometryExecutionState.FAILED, "SOURCE_MUTATION_DETECTED")
    try:
        success = _validated_success(request, adapter_result)
    except GeometryExecutionError as exc:
        state = (
            GeometryExecutionState.REJECTED
            if exc.code in {"ARTIFACT_CHECK_FAILED", "DIRECTION_MISMATCH", "RESULT_QUARANTINED"}
            else GeometryExecutionState.FAILED
        )
        return _failure(request_digest, state, exc.code)
    return GeometryExecutionOutcome(
        request_digest=request_digest,
        state=GeometryExecutionState.MATERIALIZED,
        reason_code="GEOMETRY_MATERIALIZED_PENDING_VERIFIER",
        success=success,
    )


def _adapter_request(request: GeometryExecutionRequest) -> GeometryAdapterRequest:
    parameters = request.operation.parameters
    return GeometryAdapterRequest(
        operation_digest=_content_digest(request.operation.canonical_payload()),
        requested_delta_ppm=int(parameters["delta_ppm"]),
        requested_dimension_key=str(parameters["dimension_key"]),
        required_backend=request.required_backend,
        source_asset_id=request.source_asset_id,
        source_asset_sha256=request.source_asset_sha256,
        source_bytes=request.source_bytes,
        source_image_version_digest=request.source_image_version_digest,
        source_image_version_id=request.source_image_version_id,
    )


def _validated_success(
    request: GeometryExecutionRequest, result: GeometryAdapterResult
) -> GeometryExecutionSuccess:
    if not isinstance(result, GeometryAdapterResult):
        raise GeometryExecutionError(
            "INVALID_ADAPTER_RESULT", "adapter must return GeometryAdapterResult"
        )
    if result.identity != request.required_backend:
        raise GeometryExecutionError("BACKEND_IDENTITY_MISMATCH", "result backend identity changed")
    if result.source_asset_sha256 != request.source_asset_sha256:
        raise GeometryExecutionError(
            "SOURCE_LINEAGE_MISMATCH", "result does not bind request source"
        )
    if result.quarantined:
        raise GeometryExecutionError("RESULT_QUARANTINED", "quarantined output cannot be published")
    if result.media_type != M4_RESULT_MEDIA_TYPE:
        raise GeometryExecutionError(
            "INVALID_RESULT_MEDIA_TYPE", "result media type is not frozen M4 JPEG"
        )
    if type(result.content) is not bytes or not result.content:
        raise GeometryExecutionError(
            "INVALID_RESULT_CONTENT", "result content must be non-empty bytes"
        )
    _require_digest(result.content_sha256, "content_sha256")
    if hashlib.sha256(result.content).hexdigest() != result.content_sha256:
        raise GeometryExecutionError(
            "RESULT_DIGEST_MISMATCH", "result bytes do not match result digest"
        )
    if (
        result.content == request.source_bytes
        or result.content_sha256 == request.source_asset_sha256
    ):
        raise GeometryExecutionError(
            "SOURCE_RESULT_IDENTICAL", "geometry result must differ from source"
        )
    _require_positive_dimension(result.width, "width")
    _require_positive_dimension(result.height, "height")
    _require_digest(result.measurement_config_digest, "measurement_config_digest")
    _require_integer(
        result.measured_delta_ppm,
        "measured_delta_ppm",
        -MAX_DIMENSION_DELTA_PPM,
        MAX_DIMENSION_DELTA_PPM,
        nonzero=True,
    )
    _require_integer(
        result.non_target_drift_ppm,
        "non_target_drift_ppm",
        0,
        MAX_NON_TARGET_DRIFT_PPM,
    )
    requested_delta = int(request.operation.parameters["delta_ppm"])
    if (result.measured_delta_ppm > 0) != (requested_delta > 0):
        raise GeometryExecutionError(
            "DIRECTION_MISMATCH", "measured direction differs from request"
        )
    if result.artifact_status != "PASS":
        raise GeometryExecutionError("ARTIFACT_CHECK_FAILED", "artifact evidence is not pass")
    _validate_artifact_codes(result.artifact_codes)
    return GeometryExecutionSuccess(
        artifact_codes=result.artifact_codes,
        backend=result.identity,
        height=result.height,
        measured_delta_ppm=result.measured_delta_ppm,
        measurement_config_digest=result.measurement_config_digest,
        non_target_drift_ppm=result.non_target_drift_ppm,
        output_bytes=result.content,
        result_sha256=result.content_sha256,
        source_asset_id=request.source_asset_id,
        source_asset_sha256=request.source_asset_sha256,
        source_image_version_digest=request.source_image_version_digest,
        source_image_version_id=request.source_image_version_id,
        width=result.width,
    )


def _validate_geometry_operation(operation: OperationSpec) -> None:
    if (
        operation.engine is not OperationEngine.GEOMETRY
        or operation.operation_type is not OperationType.GEOMETRY
    ):
        raise GeometryExecutionError(
            "UNSUPPORTED_OPERATION", "only a D07-A geometry operation is accepted"
        )
    parameters = operation.parameters
    dimension = parameters.get("dimension_key")
    delta = parameters.get("delta_ppm")
    if dimension not in SUPPORTED_DIMENSIONS:
        raise GeometryExecutionError(
            "UNSUPPORTED_DIMENSION", "dimension is not in the frozen Demo candidate set"
        )
    _require_integer(
        delta, "delta_ppm", -MAX_DIMENSION_DELTA_PPM, MAX_DIMENSION_DELTA_PPM, nonzero=True
    )


def _failure(
    request_digest: str, state: GeometryExecutionState, reason_code: str
) -> GeometryExecutionOutcome:
    return GeometryExecutionOutcome(
        request_digest=request_digest,
        state=state,
        reason_code=reason_code,
    )


def _content_digest(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        GEOMETRY_EXECUTION_SCHEMA_VERSION.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _validate_artifact_codes(codes: tuple[str, ...]) -> None:
    if not isinstance(codes, tuple) or any(
        not isinstance(code, str) or _ARTIFACT_CODE.fullmatch(code) is None for code in codes
    ):
        raise GeometryExecutionError("INVALID_ARTIFACT_EVIDENCE", "artifact codes are invalid")
    if tuple(sorted(codes, key=lambda item: item.encode("utf-8"))) != codes:
        raise GeometryExecutionError(
            "INVALID_ARTIFACT_EVIDENCE", "artifact codes are not canonical"
        )
    if len(set(codes)) != len(codes):
        raise GeometryExecutionError("INVALID_ARTIFACT_EVIDENCE", "artifact codes are duplicated")


def _require_positive_dimension(value: object, name: str) -> None:
    _require_integer(value, name, 1, MAX_IMAGE_DIMENSION)


def _require_integer(
    value: object, name: str, minimum: int, maximum: int, *, nonzero: bool = False
) -> None:
    if (
        type(value) is not int
        or int(value) < minimum
        or int(value) > maximum
        or (nonzero and int(value) == 0)
    ):
        raise GeometryExecutionError(
            "INVALID_RESULT_EVIDENCE", f"{name} is outside the allowed range"
        )


def _require_digest(value: object, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise GeometryExecutionError("INVALID_DIGEST", f"{name} must be a lowercase SHA-256 digest")


def _require_id(value: object, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise GeometryExecutionError(
            "INVALID_ID", f"{name} must be a 32-character lowercase identifier"
        )


def _require_opaque(value: object, name: str) -> None:
    if not isinstance(value, str) or _OPAQUE.fullmatch(value) is None:
        raise GeometryExecutionError("INVALID_OPAQUE_VALUE", f"{name} is invalid")
