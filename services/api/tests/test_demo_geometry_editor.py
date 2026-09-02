from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields, replace

import pytest

from mirror_api.demo_d08_geometry_adapter import (
    D02FixedGeometryCase,
    GeometryAdapterAuthorityError,
    GeometryDirection,
    GeometryExecutionAuthority,
    GeometryJobAttemptBinding,
    operation_spec_digest,
)
from mirror_api.demo_geometry_editor import (
    M4_QUALIFIED_ALGORITHM_VERSION,
    M4_QUALIFIED_CANDIDATE_ID,
    PENDING_INDEPENDENT_VERIFIER,
    GeometryAdapterRequest,
    GeometryAdapterResult,
    GeometryBackendIdentity,
    GeometryExecutionError,
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
_RESULT = b"fresh-canonical-result-jpeg-bytes"
_RUNTIME_DIGEST = "1" * 64
_CONFIG_DIGEST = "2" * 64


def _identity() -> GeometryBackendIdentity:
    return GeometryBackendIdentity(
        candidate_id=M4_QUALIFIED_CANDIDATE_ID,
        algorithm_version=M4_QUALIFIED_ALGORITHM_VERSION,
        runtime_manifest_digest=_RUNTIME_DIGEST,
        configuration_digest=_CONFIG_DIGEST,
    )


def _operation(*, dimension: str = "jaw_width", delta: int = 15_000) -> OperationSpec:
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


def _authority(operation: OperationSpec | None = None) -> GeometryExecutionAuthority:
    operation = operation or _operation()
    case = D02FixedGeometryCase(
        case_id="1" * 32,
        case_record_digest="3" * 64,
        case_specification_digest="4" * 64,
        case_binding_digest="0" * 64,
        case_ordinal=1,
        source_ordinal=1,
        source_asset_id="2" * 32,
        source_asset_sha256=hashlib.sha256(_SOURCE).hexdigest(),
        dimension_key=str(operation.parameters["dimension_key"]),
        direction=GeometryDirection.INCREASE
        if int(operation.parameters["delta_ppm"]) > 0
        else GeometryDirection.DECREASE,
        magnitude_ppm=abs(int(operation.parameters["delta_ppm"])),
        warp_plan_digest="5" * 64,
        geometry_ontology_digest="6" * 64,
        source_landmark_digest="7" * 64,
        output_policy_version="output-policy-v1",
        determinism_version="determinism-v1",
        backend_candidate_id=M4_QUALIFIED_CANDIDATE_ID,
        backend_algorithm_version=M4_QUALIFIED_ALGORITHM_VERSION,
        backend_runtime_manifest_digest=_RUNTIME_DIGEST,
        backend_configuration_digest=_CONFIG_DIGEST,
        output_width=16,
        output_height=12,
    )
    return GeometryExecutionAuthority(
        editing_session_id="6" * 32,
        editing_session_digest="7" * 64,
        plan_id="8" * 32,
        plan_digest="9" * 64,
        operation_id="a" * 32,
        operation_authority_digest="a" * 64,
        operation_spec_digest=operation_spec_digest(operation),
        input_image_version_id="b" * 32,
        input_image_version_digest="c" * 64,
        input_sequence=0,
        input_asset_id="0" * 32,
        input_asset_sha256=case.source_asset_sha256,
        root_source_asset_id=case.source_asset_id,
        root_source_asset_sha256=case.source_asset_sha256,
        d02_admission_id="d" * 32,
        d02_admission_digest="e" * 64,
        d02_screening_report_id="f" * 32,
        d02_screening_report_digest="0" * 64,
        fixed_case=case,
        authority_digest="0" * 64,
    )


def _request(
    *, operation: OperationSpec | None = None, attempt: str = "3" * 32
) -> GeometryExecutionRequest:
    operation = operation or _operation()
    return GeometryExecutionRequest(
        operation=operation,
        authority=_authority(operation),
        job_attempt=GeometryJobAttemptBinding(
            job_id="4" * 32,
            execution_job_binding_id="5" * 32,
            job_binding_digest="5" * 64,
            attempt_id=attempt,
            attempt_digest="6" * 64,
        ),
        source_bytes=_SOURCE,
    )


def _result(
    request: GeometryExecutionRequest,
    *,
    content: bytes = _RESULT,
    receipt: str = "a" * 64,
) -> GeometryAdapterResult:
    return GeometryAdapterResult(
        content=content,
        content_sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        media_type="image/jpeg",
        width=16,
        height=12,
        changed_pixel_count=4,
        identity=_identity(),
        backend_execution_receipt=receipt,
        authority_digest=request.authority.authority_digest,
        operation_authority_digest=request.authority.operation_authority_digest,
        operation_spec_digest=request.authority.operation_spec_digest,
        case_record_digest=request.authority.fixed_case.case_record_digest,
        case_specification_digest=request.authority.fixed_case.case_specification_digest,
        case_binding_digest=request.authority.fixed_case.case_binding_digest,
        source_asset_sha256=request.authority.root_source_asset_sha256,
    )


@dataclass
class _Backend:
    result: GeometryAdapterResult
    identity: GeometryBackendIdentity
    received: GeometryAdapterRequest | None = None

    def execute(self, *, request: GeometryAdapterRequest) -> GeometryAdapterResult:
        self.received = request
        return self.result


def test_fixed_case_execution_is_pending_verifier_and_never_publishable() -> None:
    request = _request()
    backend = _Backend(_result(request), _identity())

    outcome = execute_geometry_operation(request, backend)

    assert outcome.state is GeometryExecutionState.MATERIALIZED
    assert outcome.publishable is False
    assert outcome.ready_for_verification is True
    assert outcome.success is not None
    assert request.authority.operation_authority_digest != request.authority.operation_spec_digest
    assert outcome.success.result_sha256 == hashlib.sha256(_RESULT).hexdigest()
    assert outcome.success.stable_core.authority_digest == request.authority.authority_digest
    assert (
        outcome.success.stable_core.case_record_digest
        == request.authority.fixed_case.case_record_digest
    )
    assert (
        outcome.success.stable_core.case_specification_digest
        == request.authority.fixed_case.case_specification_digest
    )
    assert (
        outcome.success.stable_core.case_binding_digest
        == request.authority.fixed_case.case_binding_digest
    )
    assert (
        outcome.success.stable_core.operation_authority_digest
        == request.authority.operation_authority_digest
    )
    assert (
        outcome.success.stable_core.operation_spec_digest == request.authority.operation_spec_digest
    )
    assert outcome.success.attempt_evidence.job_attempt == request.job_attempt
    assert backend.received is not None
    assert backend.received.authority is request.authority
    assert outcome.success.canonical_payload()["verification_state"] == PENDING_INDEPENDENT_VERIFIER
    assert (
        outcome.success.attempt_evidence.canonical_payload()["job_attempt"][
            "execution_job_binding_id"
        ]
        == request.job_attempt.execution_job_binding_id
    )
    assert (
        outcome.success.attempt_evidence.operation_authority_digest
        == request.authority.operation_authority_digest
    )
    assert (
        outcome.success.attempt_evidence.operation_spec_digest
        == request.authority.operation_spec_digest
    )
    assert {"measured_delta_ppm", "non_target_drift_ppm", "artifact_status"}.isdisjoint(
        {field.name for field in fields(GeometryAdapterResult)}
    )
    assert _SOURCE.decode() not in repr(request)
    assert _SOURCE.decode() not in repr(backend.received)
    assert _RESULT.decode() not in repr(backend.result)
    assert _RESULT.decode() not in repr(outcome.success)


def test_stable_core_replays_across_attempts_but_receipts_are_attempt_specific() -> None:
    first_request = _request(attempt="3" * 32)
    second_request = _request(attempt="7" * 32)
    first = execute_geometry_operation(
        first_request, _Backend(_result(first_request, receipt="a" * 64), _identity())
    )
    second = execute_geometry_operation(
        second_request, _Backend(_result(second_request, receipt="b" * 64), _identity())
    )

    assert first.success is not None and second.success is not None
    assert first.success.stable_core == second.success.stable_core
    assert (
        first.success.attempt_evidence.attempt_receipt_digest
        != second.success.attempt_evidence.attempt_receipt_digest
    )


@pytest.mark.parametrize(
    ("result_update", "reason"),
    [
        ({"content_sha256": "0" * 64}, "RESULT_DIGEST_MISMATCH"),
        ({"byte_size": 1}, "RESULT_SIZE_MISMATCH"),
        ({"media_type": "image/png"}, "INVALID_RESULT_MEDIA_TYPE"),
        ({"width": 0}, "INVALID_RESULT_EVIDENCE"),
        ({"width": 15}, "RESULT_DIMENSION_MISMATCH"),
        ({"changed_pixel_count": 0}, "INVALID_CHANGED_PIXEL_COUNT"),
        ({"changed_pixel_count": 193}, "INVALID_CHANGED_PIXEL_COUNT"),
        ({"backend_execution_receipt": "receipt-not-a-digest"}, "INVALID_DIGEST"),
        ({"source_asset_sha256": "a" * 64}, "SOURCE_LINEAGE_MISMATCH"),
        ({"authority_digest": "b" * 64}, "AUTHORITY_MISMATCH"),
        ({"operation_authority_digest": "b" * 64}, "OPERATION_DIGEST_MISMATCH"),
        ({"operation_spec_digest": "b" * 64}, "OPERATION_DIGEST_MISMATCH"),
        ({"case_binding_digest": "c" * 64}, "CASE_MISMATCH"),
        (
            {
                "content": _SOURCE,
                "content_sha256": hashlib.sha256(_SOURCE).hexdigest(),
                "byte_size": len(_SOURCE),
            },
            "SOURCE_RESULT_IDENTICAL",
        ),
    ],
)
def test_structural_mismatch_is_non_publishable(
    result_update: dict[str, object], reason: str
) -> None:
    request = _request()
    result = replace(_result(request), **result_update)
    outcome = execute_geometry_operation(request, _Backend(result, _identity()))
    assert outcome.state is GeometryExecutionState.FAILED
    assert outcome.reason_code == reason
    assert outcome.publishable is False


def test_forged_authority_or_case_is_rejected_before_backend_runs() -> None:
    request = _request()
    with pytest.raises(GeometryAdapterAuthorityError):
        replace(request.authority, authority_digest="f" * 64)
    with pytest.raises(GeometryAdapterAuthorityError):
        replace(request.authority.fixed_case, case_binding_digest="e" * 64)


def test_mismatched_operation_and_missing_or_wrong_backend_fail_closed() -> None:
    with pytest.raises((GeometryExecutionError, GeometryAdapterAuthorityError)) as error:
        _request(operation=_operation(delta=30_000)).__class__(
            operation=_operation(delta=15_000),
            authority=_authority(_operation(delta=30_000)),
            job_attempt=GeometryJobAttemptBinding("4" * 32, "5" * 32, "5" * 64, "3" * 32, "6" * 64),
            source_bytes=_SOURCE,
        )
    assert error.value.code == "OPERATION_SPEC_DIGEST_MISMATCH"
    request = _request()
    assert (
        execute_geometry_operation(request, None).state
        is GeometryExecutionState.CAPABILITY_UNAVAILABLE
    )
    wrong = GeometryBackendIdentity(
        M4_QUALIFIED_CANDIDATE_ID, M4_QUALIFIED_ALGORITHM_VERSION, "8" * 64, _CONFIG_DIGEST
    )
    outcome = execute_geometry_operation(request, _Backend(_result(request), wrong))
    assert outcome.reason_code == "QUALIFIED_BACKEND_UNAVAILABLE"


@pytest.mark.parametrize(
    ("dimension", "delta", "code"),
    [
        ("nose_width", 15_000, "UNSUPPORTED_DIMENSION"),
        ("jaw_width", 20_000, "INVALID_MAGNITUDE"),
    ],
)
def test_only_fixed_case_dimensions_and_magnitudes_reach_a_backend(
    dimension: str, delta: int, code: str
) -> None:
    with pytest.raises((GeometryExecutionError, GeometryAdapterAuthorityError)) as error:
        _request(operation=_operation(dimension=dimension, delta=delta))
    assert error.value.code == code
