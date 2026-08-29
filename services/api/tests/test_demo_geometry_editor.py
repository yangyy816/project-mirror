from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pytest

from mirror_api.demo_geometry_editor import (
    M4_QUALIFIED_ALGORITHM_VERSION,
    M4_QUALIFIED_CANDIDATE_ID,
    PENDING_INDEPENDENT_VERIFIER,
    STRUCTURAL_EVIDENCE_ONLY,
    GeometryAdapterRequest,
    GeometryAdapterResult,
    GeometryBackendIdentity,
    GeometryExecutionError,
    GeometryExecutionOutcome,
    GeometryExecutionRequest,
    GeometryExecutionState,
    execute_geometry_operation,
)
from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    PreserveKey,
)

_SOURCE = b"canonical-source-jpeg-bytes"
_RESULT = b"canonical-result-jpeg-bytes"
_RUNTIME_DIGEST = "1" * 64
_CONFIG_DIGEST = "2" * 64
_MEASUREMENT_DIGEST = "3" * 64


def _identity() -> GeometryBackendIdentity:
    return GeometryBackendIdentity(
        candidate_id=M4_QUALIFIED_CANDIDATE_ID,
        algorithm_version=M4_QUALIFIED_ALGORITHM_VERSION,
        runtime_manifest_digest=_RUNTIME_DIGEST,
        configuration_digest=_CONFIG_DIGEST,
    )


def _operation(*, dimension: str = "jaw_width", delta: int = 25_000) -> OperationSpec:
    return OperationSpec(
        engine=OperationEngine.GEOMETRY,
        operation_type=OperationType.GEOMETRY,
        parameters={"dimension_key": dimension, "delta_ppm": delta},
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME, PreserveKey.NON_TARGET_GEOMETRY),
        expected_effect={
            "effect_type": "GEOMETRY",
            "target_region": "FACE_REGION",
            "dimension_key": dimension,
            "delta_ppm": delta,
        },
    )


def _request(*, operation: OperationSpec | None = None) -> GeometryExecutionRequest:
    return GeometryExecutionRequest(
        operation=operation or _operation(),
        required_backend=_identity(),
        source_asset_id="a" * 32,
        source_asset_sha256=hashlib.sha256(_SOURCE).hexdigest(),
        source_bytes=_SOURCE,
        source_image_version_digest="b" * 64,
        source_image_version_id="c" * 32,
    )


def _result(
    *,
    content: bytes = _RESULT,
    content_sha256: str | None = None,
    identity: GeometryBackendIdentity | None = None,
    measured_delta_ppm: int = 20_000,
    artifact_status: str = "PASS",
    quarantined: bool = False,
    source_asset_sha256: str | None = None,
) -> GeometryAdapterResult:
    return GeometryAdapterResult(
        artifact_codes=(),
        artifact_status=artifact_status,
        content=content,
        content_sha256=content_sha256 or hashlib.sha256(content).hexdigest(),
        height=12,
        identity=identity or _identity(),
        measured_delta_ppm=measured_delta_ppm,
        measurement_config_digest=_MEASUREMENT_DIGEST,
        media_type="image/jpeg",
        non_target_drift_ppm=7_500,
        quarantined=quarantined,
        source_asset_sha256=source_asset_sha256 or hashlib.sha256(_SOURCE).hexdigest(),
        width=16,
    )


@dataclass
class _Backend:
    result: GeometryAdapterResult
    identity: GeometryBackendIdentity
    received: GeometryAdapterRequest | None = None

    def execute(self, *, request: GeometryAdapterRequest) -> GeometryAdapterResult:
        self.received = request
        return self.result


class _ExplodingBackend:
    @property
    def identity(self) -> GeometryBackendIdentity:
        return _identity()

    def execute(self, *, request: GeometryAdapterRequest) -> GeometryAdapterResult:
        del request
        raise RuntimeError("offline runtime failure")


def test_geometry_operation_becomes_qualified_adapter_request_and_evidence_envelope() -> None:
    request = _request()
    backend = _Backend(_result(), _identity())

    outcome = execute_geometry_operation(request, backend)

    assert outcome.state is GeometryExecutionState.MATERIALIZED
    assert outcome.publishable is False
    assert outcome.ready_for_verification is True
    assert outcome.reason_code == "GEOMETRY_MATERIALIZED_PENDING_VERIFIER"
    assert outcome.success is not None
    assert outcome.success.result_sha256 == hashlib.sha256(_RESULT).hexdigest()
    assert outcome.success.source_asset_sha256 == hashlib.sha256(_SOURCE).hexdigest()
    assert outcome.success.measured_delta_ppm == 20_000
    assert outcome.success.non_target_drift_ppm == 7_500
    assert backend.received is not None
    assert backend.received.requested_dimension_key == "jaw_width"
    assert backend.received.requested_delta_ppm == 25_000
    assert backend.received.source_bytes == _SOURCE
    payload = outcome.canonical_payload()
    assert payload["success"] is not None
    success = payload["success"]
    assert isinstance(success, dict)
    assert success["identity_claim_scope"] == STRUCTURAL_EVIDENCE_ONLY
    assert success["verification_state"] == PENDING_INDEPENDENT_VERIFIER


@pytest.mark.parametrize("dimension", ["jaw_width", "chin_height", "eye_spacing"])
def test_frozen_candidate_dimensions_are_supported(dimension: str) -> None:
    outcome = execute_geometry_operation(
        _request(operation=_operation(dimension=dimension)), _Backend(_result(), _identity())
    )
    assert outcome.state is GeometryExecutionState.MATERIALIZED


def test_unsupported_dimension_is_rejected_before_an_adapter_can_run() -> None:
    with pytest.raises(GeometryExecutionError, match="candidate set") as error:
        _request(operation=_operation(dimension="nose_width"))
    assert error.value.code == "UNSUPPORTED_DIMENSION"


def test_non_geometry_operation_is_rejected_before_an_adapter_can_run() -> None:
    raster = OperationSpec(
        engine=OperationEngine.RASTER,
        operation_type=OperationType.EXPOSURE,
        parameters={"exposure_ev_milli": 100},
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME,),
        expected_effect={
            "effect_type": "EXPOSURE",
            "target_region": "FULL_IMAGE",
            "exposure_ev_milli": 100,
        },
    )
    with pytest.raises(GeometryExecutionError, match="geometry operation") as error:
        _request(operation=raster)
    assert error.value.code == "UNSUPPORTED_OPERATION"


def test_missing_or_unqualified_backend_is_explicitly_non_publishable() -> None:
    request = _request()
    missing = execute_geometry_operation(request, None)
    mismatch = execute_geometry_operation(
        request,
        _Backend(
            _result(),
            GeometryBackendIdentity(
                candidate_id=M4_QUALIFIED_CANDIDATE_ID,
                algorithm_version=M4_QUALIFIED_ALGORITHM_VERSION,
                runtime_manifest_digest="4" * 64,
                configuration_digest=_CONFIG_DIGEST,
            ),
        ),
    )
    assert missing.state is GeometryExecutionState.CAPABILITY_UNAVAILABLE
    assert missing.reason_code == "BACKEND_MISSING"
    assert mismatch.state is GeometryExecutionState.CAPABILITY_UNAVAILABLE
    assert mismatch.reason_code == "QUALIFIED_BACKEND_UNAVAILABLE"
    assert missing.publishable is False
    assert missing.success is None


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        (_result(content_sha256="0" * 64), "RESULT_DIGEST_MISMATCH"),
        (_result(content=_SOURCE), "SOURCE_RESULT_IDENTICAL"),
        (_result(measured_delta_ppm=-20_000), "DIRECTION_MISMATCH"),
        (_result(artifact_status="FAIL"), "ARTIFACT_CHECK_FAILED"),
        (_result(quarantined=True), "RESULT_QUARANTINED"),
        (_result(source_asset_sha256="d" * 64), "SOURCE_LINEAGE_MISMATCH"),
        (
            _result(
                identity=GeometryBackendIdentity(
                    candidate_id=M4_QUALIFIED_CANDIDATE_ID,
                    algorithm_version=M4_QUALIFIED_ALGORITHM_VERSION,
                    runtime_manifest_digest="5" * 64,
                    configuration_digest=_CONFIG_DIGEST,
                )
            ),
            "BACKEND_IDENTITY_MISMATCH",
        ),
    ],
)
def test_invalid_result_evidence_never_publishes_success(
    result: GeometryAdapterResult, reason: str
) -> None:
    outcome = execute_geometry_operation(_request(), _Backend(result, _identity()))
    expected_state = (
        GeometryExecutionState.REJECTED
        if reason in {"DIRECTION_MISMATCH", "ARTIFACT_CHECK_FAILED", "RESULT_QUARANTINED"}
        else GeometryExecutionState.FAILED
    )
    assert outcome.state is expected_state
    assert outcome.reason_code == reason
    assert outcome.publishable is False
    assert outcome.ready_for_verification is False
    assert outcome.success is None


def test_backend_errors_do_not_publish_success() -> None:
    outcome = execute_geometry_operation(_request(), _ExplodingBackend())
    assert outcome.state is GeometryExecutionState.FAILED
    assert outcome.reason_code == "BACKEND_EXECUTION_FAILED"
    assert outcome.success is None


def test_source_bytes_are_unchanged_and_replay_digest_is_deterministic() -> None:
    source_before = bytes(_SOURCE)
    first = execute_geometry_operation(_request(), _Backend(_result(), _identity()))
    second = execute_geometry_operation(_request(), _Backend(_result(), _identity()))

    assert _SOURCE == source_before
    assert first == second
    assert first.content_digest() == second.content_digest()
    assert first.request_digest == _request().content_digest()


def test_outcome_does_not_allow_a_failed_result_to_carry_output() -> None:
    with pytest.raises(GeometryExecutionError, match="failed outcome") as error:
        GeometryExecutionOutcome(
            request_digest="f" * 64,
            state=GeometryExecutionState.REJECTED,
            reason_code="BAD",
            success=execute_geometry_operation(
                _request(), _Backend(_result(), _identity())
            ).success,
        )
    assert error.value.code == "INVALID_OUTCOME"
