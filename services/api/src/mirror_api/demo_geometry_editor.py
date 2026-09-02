"""Fail-closed D08 original-source fixed-case geometry execution boundary.

The injected backend is trusted only for a fresh structural output. It cannot
make a verification, artifact, drift, or measured-delta decision. Every
materialization remains non-publishable until the independent verifier layer.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Final, Protocol

from mirror_api.demo_d08_geometry_adapter import (
    D08_VERIFIER_POLICY_VERSION,
    FIXED_GEOMETRY_DIMENSIONS,
    FIXED_GEOMETRY_MAGNITUDES_PPM,
    FIXED_RESULT_MEDIA_TYPE,
    GeometryAdapterAuthorityError,
    GeometryAttemptExecutionEvidence,
    GeometryExecutionAuthority,
    GeometryJobAttemptBinding,
    GeometryStableMaterializationCore,
    operation_spec_digest,
    stable_config_digest,
    stable_engine_digest,
)
from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    canonical_json_bytes,
)
from mirror_api.demo_tool_registry import GEOMETRY_ENGINE_VERSION
from mirror_api.providers.opencv_geometry import ALGORITHM_VERSION, CANDIDATE_ID

GEOMETRY_EXECUTION_SCHEMA_VERSION: Final = "mirror.demo/GeometryExecution/v2"
GEOMETRY_EXECUTION_ALGORITHM_VERSION: Final = "d08-fixed-case-geometry-boundary-v1"
M4_QUALIFIED_CANDIDATE_ID: Final = CANDIDATE_ID
M4_QUALIFIED_ALGORITHM_VERSION: Final = ALGORITHM_VERSION
M4_RESULT_MEDIA_TYPE: Final = FIXED_RESULT_MEDIA_TYPE
STRUCTURAL_EVIDENCE_ONLY: Final = "STRUCTURAL_EVIDENCE_ONLY_NOT_BIOMETRIC_IDENTITY_VERIFICATION"
PENDING_INDEPENDENT_VERIFIER: Final = "PENDING_INDEPENDENT_VERIFIER"

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class GeometryExecutionState(StrEnum):
    MATERIALIZED = "MATERIALIZED"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class GeometryExecutionError(ValueError):
    """A caller or backend violated this immutable D08 execution boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class GeometryBackendIdentity:
    candidate_id: str
    algorithm_version: str
    runtime_manifest_digest: str
    configuration_digest: str

    def __post_init__(self) -> None:
        _opaque(self.candidate_id, "candidate_id")
        _opaque(self.algorithm_version, "algorithm_version")
        _digest(self.runtime_manifest_digest, "runtime_manifest_digest")
        _digest(self.configuration_digest, "configuration_digest")

    def canonical_payload(self) -> dict[str, str]:
        return {
            "algorithm_version": self.algorithm_version,
            "candidate_id": self.candidate_id,
            "configuration_digest": self.configuration_digest,
            "runtime_manifest_digest": self.runtime_manifest_digest,
        }


@dataclass(frozen=True, slots=True)
class GeometryExecutionRequest:
    """Typed repository authority plus current-attempt-only source bytes."""

    operation: OperationSpec
    authority: GeometryExecutionAuthority
    job_attempt: GeometryJobAttemptBinding
    source_bytes: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.operation, OperationSpec):
            raise GeometryExecutionError(
                "INVALID_OPERATION", "operation must be a frozen OperationSpec"
            )
        if not isinstance(self.authority, GeometryExecutionAuthority):
            raise GeometryExecutionError("INVALID_AUTHORITY", "geometry authority must be typed")
        if not isinstance(self.job_attempt, GeometryJobAttemptBinding):
            raise GeometryExecutionError("INVALID_JOB_ATTEMPT", "job attempt must be typed")
        _validate_geometry_operation(self.operation)
        if type(self.source_bytes) is not bytes or not self.source_bytes:
            raise GeometryExecutionError(
                "INVALID_SOURCE", "source bytes must be non-empty immutable bytes"
            )
        if hashlib.sha256(self.source_bytes).hexdigest() != self.authority.root_source_asset_sha256:
            raise GeometryExecutionError(
                "SOURCE_DIGEST_MISMATCH", "source bytes do not match authority root"
            )
        if operation_spec_digest(self.operation) != self.authority.operation_spec_digest:
            raise GeometryExecutionError(
                "OPERATION_SPEC_DIGEST_MISMATCH", "operation spec is not authority-bound"
            )
        parameters = self.operation.parameters
        if (
            parameters["dimension_key"] != self.authority.dimension_key
            or abs(int(parameters["delta_ppm"])) != self.authority.magnitude_ppm
            or (int(parameters["delta_ppm"]) > 0) != (self.authority.direction.value == "INCREASE")
        ):
            raise GeometryExecutionError(
                "CASE_OPERATION_MISMATCH", "operation does not match the fixed case"
            )
        case = self.authority.fixed_case
        if (
            case.backend_candidate_id != M4_QUALIFIED_CANDIDATE_ID
            or case.backend_algorithm_version != M4_QUALIFIED_ALGORITHM_VERSION
        ):
            raise GeometryExecutionError(
                "UNQUALIFIED_BACKEND", "authority is not bound to the frozen backend"
            )

    @property
    def required_backend(self) -> GeometryBackendIdentity:
        case = self.authority.fixed_case
        return GeometryBackendIdentity(
            candidate_id=case.backend_candidate_id,
            algorithm_version=case.backend_algorithm_version,
            runtime_manifest_digest=case.backend_runtime_manifest_digest,
            configuration_digest=case.backend_configuration_digest,
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "authority_digest": self.authority.authority_digest,
            "job_attempt": self.job_attempt.canonical_payload(),
            "operation_authority_digest": self.authority.operation_authority_digest,
            "operation_spec_digest": self.authority.operation_spec_digest,
            "schema_version": GEOMETRY_EXECUTION_SCHEMA_VERSION,
        }

    def content_digest(self) -> str:
        return _content_digest(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class GeometryAdapterRequest:
    """The only payload a fixed-case backend may receive."""

    authority: GeometryExecutionAuthority
    operation_authority_digest: str
    operation_spec_digest: str
    source_bytes: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.authority, GeometryExecutionAuthority):
            raise GeometryExecutionError("INVALID_AUTHORITY", "adapter authority must be typed")
        _digest(self.operation_authority_digest, "operation_authority_digest")
        _digest(self.operation_spec_digest, "operation_spec_digest")
        if (
            self.operation_authority_digest != self.authority.operation_authority_digest
            or self.operation_spec_digest != self.authority.operation_spec_digest
        ):
            raise GeometryExecutionError(
                "OPERATION_DIGEST_MISMATCH", "adapter operation is not authority-bound"
            )
        if type(self.source_bytes) is not bytes or not self.source_bytes:
            raise GeometryExecutionError("INVALID_SOURCE", "adapter source bytes are invalid")


@dataclass(frozen=True, slots=True)
class GeometryAdapterResult:
    """Fresh structural backend facts only; semantic verification is excluded."""

    content: bytes = field(repr=False)
    content_sha256: str
    byte_size: int
    media_type: str
    width: int
    height: int
    changed_pixel_count: int
    identity: GeometryBackendIdentity
    backend_execution_receipt: str
    authority_digest: str
    operation_authority_digest: str
    operation_spec_digest: str
    case_record_digest: str
    case_specification_digest: str
    case_binding_digest: str
    source_asset_sha256: str
    quarantined: bool = False


class GeometryExecutionBackend(Protocol):
    @property
    def identity(self) -> GeometryBackendIdentity: ...

    def execute(self, *, request: GeometryAdapterRequest) -> GeometryAdapterResult: ...


@dataclass(frozen=True, slots=True)
class GeometryExecutionSuccess:
    backend: GeometryBackendIdentity
    output_bytes: bytes = field(repr=False)
    stable_core: GeometryStableMaterializationCore
    attempt_evidence: GeometryAttemptExecutionEvidence

    @property
    def result_sha256(self) -> str:
        return self.stable_core.result_sha256

    def canonical_payload(self) -> dict[str, object]:
        return {
            "attempt_evidence": {
                **self.attempt_evidence.canonical_payload(),
                "attempt_receipt_digest": self.attempt_evidence.attempt_receipt_digest,
            },
            "backend": self.backend.canonical_payload(),
            "identity_claim_scope": STRUCTURAL_EVIDENCE_ONLY,
            "stable_core": {
                **self.stable_core.canonical_payload(),
                "stable_core_digest": self.stable_core.stable_core_digest,
            },
            "verification_state": PENDING_INDEPENDENT_VERIFIER,
        }


@dataclass(frozen=True, slots=True)
class GeometryExecutionOutcome:
    request_digest: str
    state: GeometryExecutionState
    reason_code: str
    success: GeometryExecutionSuccess | None = None

    def __post_init__(self) -> None:
        _digest(self.request_digest, "request_digest")
        _opaque(self.reason_code, "reason_code")
        if (self.state is GeometryExecutionState.MATERIALIZED) != (self.success is not None):
            raise GeometryExecutionError(
                "INVALID_OUTCOME", "output may exist only for materialization"
            )

    @property
    def publishable(self) -> bool:
        return False

    @property
    def ready_for_verification(self) -> bool:
        return self.state is GeometryExecutionState.MATERIALIZED

    def canonical_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "reason_code": self.reason_code,
            "request_digest": self.request_digest,
            "schema_version": GEOMETRY_EXECUTION_SCHEMA_VERSION,
            "state": self.state.value,
        }
        if self.success is not None:
            payload["success"] = self.success.canonical_payload()
        return payload

    def content_digest(self) -> str:
        return _content_digest(self.canonical_payload())


def execute_geometry_operation(
    request: GeometryExecutionRequest, backend: GeometryExecutionBackend | None
) -> GeometryExecutionOutcome:
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
    source_before = request.source_bytes
    try:
        result = backend.execute(request=_adapter_request(request))
    except Exception:
        return _failure(request_digest, GeometryExecutionState.FAILED, "BACKEND_EXECUTION_FAILED")
    if request.source_bytes != source_before:
        return _failure(request_digest, GeometryExecutionState.FAILED, "SOURCE_MUTATION_DETECTED")
    try:
        success = _validated_success(request, result)
    except (GeometryExecutionError, GeometryAdapterAuthorityError) as exc:
        return _failure(
            request_digest,
            GeometryExecutionState.REJECTED
            if exc.code == "RESULT_QUARANTINED"
            else GeometryExecutionState.FAILED,
            exc.code,
        )
    return GeometryExecutionOutcome(
        request_digest=request_digest,
        state=GeometryExecutionState.MATERIALIZED,
        reason_code="GEOMETRY_MATERIALIZED_PENDING_VERIFIER",
        success=success,
    )


def _adapter_request(request: GeometryExecutionRequest) -> GeometryAdapterRequest:
    return GeometryAdapterRequest(
        authority=request.authority,
        operation_authority_digest=request.authority.operation_authority_digest,
        operation_spec_digest=request.authority.operation_spec_digest,
        source_bytes=request.source_bytes,
    )


def _validated_success(
    request: GeometryExecutionRequest, result: GeometryAdapterResult
) -> GeometryExecutionSuccess:
    if not isinstance(result, GeometryAdapterResult):
        raise GeometryExecutionError("INVALID_ADAPTER_RESULT", "backend returned an invalid result")
    authority = request.authority
    if result.identity != request.required_backend:
        raise GeometryExecutionError("BACKEND_IDENTITY_MISMATCH", "result backend identity changed")
    if result.authority_digest != authority.authority_digest:
        raise GeometryExecutionError("AUTHORITY_MISMATCH", "result authority binding changed")
    if (
        result.operation_authority_digest != authority.operation_authority_digest
        or result.operation_spec_digest != authority.operation_spec_digest
    ):
        raise GeometryExecutionError(
            "OPERATION_DIGEST_MISMATCH", "result operation binding changed"
        )
    case = authority.fixed_case
    if (
        result.case_record_digest != case.case_record_digest
        or result.case_specification_digest != case.case_specification_digest
        or result.case_binding_digest != case.case_binding_digest
    ):
        raise GeometryExecutionError("CASE_MISMATCH", "result case binding changed")
    if result.source_asset_sha256 != authority.root_source_asset_sha256:
        raise GeometryExecutionError("SOURCE_LINEAGE_MISMATCH", "result source binding changed")
    if result.quarantined:
        raise GeometryExecutionError("RESULT_QUARANTINED", "quarantined output cannot proceed")
    if result.media_type != M4_RESULT_MEDIA_TYPE:
        raise GeometryExecutionError(
            "INVALID_RESULT_MEDIA_TYPE", "result MIME is not the frozen JPEG"
        )
    if type(result.content) is not bytes or not result.content:
        raise GeometryExecutionError(
            "INVALID_RESULT_CONTENT", "result content must be immutable bytes"
        )
    _digest(result.content_sha256, "content_sha256")
    if result.byte_size != len(result.content):
        raise GeometryExecutionError(
            "RESULT_SIZE_MISMATCH", "result byte size does not match bytes"
        )
    if hashlib.sha256(result.content).hexdigest() != result.content_sha256:
        raise GeometryExecutionError("RESULT_DIGEST_MISMATCH", "result bytes do not match digest")
    if (
        result.content == request.source_bytes
        or result.content_sha256 == authority.root_source_asset_sha256
    ):
        raise GeometryExecutionError(
            "SOURCE_RESULT_IDENTICAL", "result must differ from immutable source"
        )
    _positive_image_scalar(result.width, "width")
    _positive_image_scalar(result.height, "height")
    if result.width != case.output_width or result.height != case.output_height:
        raise GeometryExecutionError(
            "RESULT_DIMENSION_MISMATCH", "result dimensions differ from fixed case"
        )
    if (
        type(result.changed_pixel_count) is not int
        or result.changed_pixel_count < 1
        or result.changed_pixel_count > result.width * result.height
    ):
        raise GeometryExecutionError(
            "INVALID_CHANGED_PIXEL_COUNT", "changed pixels must be positive"
        )
    _digest(result.backend_execution_receipt, "backend_execution_receipt")
    engine_digest = stable_engine_digest(authority, GEOMETRY_ENGINE_VERSION)
    config_digest = stable_config_digest(authority, D08_VERIFIER_POLICY_VERSION)
    core = GeometryStableMaterializationCore(
        operation_id=authority.operation_id,
        operation_authority_digest=authority.operation_authority_digest,
        operation_spec_digest=authority.operation_spec_digest,
        authority_digest=authority.authority_digest,
        case_id=case.case_id,
        case_record_digest=case.case_record_digest,
        case_specification_digest=case.case_specification_digest,
        case_binding_digest=case.case_binding_digest,
        backend_candidate_id=result.identity.candidate_id,
        backend_algorithm_version=result.identity.algorithm_version,
        backend_runtime_manifest_digest=result.identity.runtime_manifest_digest,
        backend_configuration_digest=result.identity.configuration_digest,
        warp_plan_digest=case.warp_plan_digest,
        input_image_version_id=authority.input_image_version_id,
        input_image_version_digest=authority.input_image_version_digest,
        input_asset_id=authority.input_asset_id,
        input_asset_sha256=authority.input_asset_sha256,
        root_source_asset_id=authority.root_source_asset_id,
        root_source_asset_sha256=authority.root_source_asset_sha256,
        result_sha256=result.content_sha256,
        result_byte_size=result.byte_size,
        result_media_type=result.media_type,
        result_width=result.width,
        result_height=result.height,
        changed_pixel_count=result.changed_pixel_count,
        engine_digest=engine_digest,
        config_digest=config_digest,
        stable_core_digest="0" * 64,
    )
    core = replace(core, stable_core_digest=core.content_digest())
    evidence = GeometryAttemptExecutionEvidence(
        job_attempt=request.job_attempt,
        operation_id=authority.operation_id,
        operation_authority_digest=authority.operation_authority_digest,
        operation_spec_digest=authority.operation_spec_digest,
        authority_digest=authority.authority_digest,
        stable_core_digest=core.stable_core_digest,
        backend_execution_receipt=result.backend_execution_receipt,
        attempt_receipt_digest="0" * 64,
    )
    evidence = replace(evidence, attempt_receipt_digest=evidence.content_digest())
    return GeometryExecutionSuccess(
        backend=result.identity,
        output_bytes=result.content,
        stable_core=core,
        attempt_evidence=evidence,
    )


def _validate_geometry_operation(operation: OperationSpec) -> None:
    if (
        operation.engine is not OperationEngine.GEOMETRY
        or operation.operation_type is not OperationType.GEOMETRY
    ):
        raise GeometryExecutionError(
            "UNSUPPORTED_OPERATION", "only a geometry operation is accepted"
        )
    dimension = operation.parameters.get("dimension_key")
    delta = operation.parameters.get("delta_ppm")
    if dimension not in FIXED_GEOMETRY_DIMENSIONS:
        raise GeometryExecutionError(
            "UNSUPPORTED_DIMENSION", "dimension is not a fixed D08 dimension"
        )
    if type(delta) is not int or abs(delta) not in FIXED_GEOMETRY_MAGNITUDES_PPM:
        raise GeometryExecutionError(
            "INVALID_MAGNITUDE", "delta must be exactly plus or minus 15000 or 30000"
        )


def _failure(
    request_digest: str, state: GeometryExecutionState, reason_code: str
) -> GeometryExecutionOutcome:
    return GeometryExecutionOutcome(
        request_digest=request_digest, state=state, reason_code=reason_code
    )


def _content_digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        GEOMETRY_EXECUTION_SCHEMA_VERSION.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _digest(value: object, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise GeometryExecutionError("INVALID_DIGEST", f"{name} must be a lowercase SHA-256 digest")


def _opaque(value: object, name: str) -> None:
    if not isinstance(value, str) or _OPAQUE.fullmatch(value) is None:
        raise GeometryExecutionError("INVALID_OPAQUE_VALUE", f"{name} is invalid")


def _positive_image_scalar(value: object, name: str) -> None:
    if type(value) is not int or value < 1 or value > 20_000:
        raise GeometryExecutionError(
            "INVALID_RESULT_EVIDENCE", f"{name} is outside the allowed range"
        )
