from __future__ import annotations

import hashlib
from dataclasses import fields, replace

import pytest

from mirror_api.demo_d08_geometry_adapter import (
    TARGETED_REPAIR_ALGORITHM_VERSION,
    TARGETED_REPAIR_CANDIDATE_ID,
    D02FixedGeometryCase,
    GeometryAdapterAuthorityError,
    GeometryAttemptExecutionEvidence,
    GeometryDirection,
    GeometryExecutionAuthority,
    GeometryJobAttemptBinding,
    GeometryStableMaterializationCore,
)
from mirror_api.providers.opencv_geometry import ALGORITHM_VERSION, CANDIDATE_ID


def _case() -> D02FixedGeometryCase:
    return D02FixedGeometryCase(
        case_id="1" * 32,
        case_record_digest="3" * 64,
        case_specification_digest="4" * 64,
        case_binding_digest="0" * 64,
        case_ordinal=1,
        source_ordinal=1,
        source_asset_id="2" * 32,
        source_asset_sha256=hashlib.sha256(b"source").hexdigest(),
        dimension_key="jaw_width",
        direction=GeometryDirection.INCREASE,
        magnitude_ppm=15_000,
        warp_plan_digest="5" * 64,
        geometry_ontology_digest="6" * 64,
        source_landmark_digest="7" * 64,
        output_policy_version="output-policy-v1",
        determinism_version="determinism-v1",
        backend_candidate_id=CANDIDATE_ID,
        backend_algorithm_version=ALGORITHM_VERSION,
        backend_runtime_manifest_digest="8" * 64,
        backend_configuration_digest="9" * 64,
        output_width=10,
        output_height=10,
    )


def _authority() -> GeometryExecutionAuthority:
    case = _case()
    return GeometryExecutionAuthority(
        editing_session_id="8" * 32,
        editing_session_digest="9" * 64,
        plan_id="a" * 32,
        plan_digest="b" * 64,
        operation_id="c" * 32,
        operation_authority_digest="d" * 64,
        operation_spec_digest="e" * 64,
        input_image_version_id="e" * 32,
        input_image_version_digest="f" * 64,
        input_sequence=0,
        input_asset_id="4" * 32,
        input_asset_sha256=case.source_asset_sha256,
        root_source_asset_id=case.source_asset_id,
        root_source_asset_sha256=case.source_asset_sha256,
        d02_admission_id="0" * 32,
        d02_admission_digest="1" * 64,
        d02_screening_report_id="2" * 32,
        d02_screening_report_digest="3" * 64,
        fixed_case=case,
        authority_digest="0" * 64,
    )


def test_typed_authority_replays_and_rejects_forged_case_or_source_lineage() -> None:
    authority = _authority()
    assert authority.authority_digest == authority.content_digest()
    assert authority.fixed_case.case_binding_digest == authority.fixed_case.content_digest()
    with pytest.raises(GeometryAdapterAuthorityError, match="source"):
        replace(
            authority,
            input_asset_id=authority.root_source_asset_id,
            authority_digest="0" * 64,
        )
    with pytest.raises(GeometryAdapterAuthorityError, match="sequence"):
        replace(authority, input_sequence=1)
    with pytest.raises(GeometryAdapterAuthorityError, match="case binding"):
        replace(authority.fixed_case, case_binding_digest="f" * 64)
    with pytest.raises(GeometryAdapterAuthorityError):
        replace(authority.fixed_case, case_ordinal=49)
    with pytest.raises(GeometryAdapterAuthorityError):
        replace(authority.fixed_case, source_ordinal=5)


def test_targeted_backend_is_allowed_only_for_the_exact_case_25_selector() -> None:
    targeted = replace(
        _case(),
        case_ordinal=25,
        source_ordinal=3,
        direction=GeometryDirection.DECREASE,
        backend_candidate_id=TARGETED_REPAIR_CANDIDATE_ID,
        backend_algorithm_version=TARGETED_REPAIR_ALGORITHM_VERSION,
        case_binding_digest="0" * 64,
    )
    assert targeted.case_binding_digest == targeted.content_digest()
    with pytest.raises(GeometryAdapterAuthorityError, match="exact D08 allowlist"):
        replace(
            targeted,
            source_ordinal=2,
            case_binding_digest="0" * 64,
        )


def test_stable_and_attempt_surfaces_are_separate_and_canonical() -> None:
    authority = _authority()
    core = GeometryStableMaterializationCore(
        operation_id=authority.operation_id,
        operation_authority_digest=authority.operation_authority_digest,
        operation_spec_digest=authority.operation_spec_digest,
        authority_digest=authority.authority_digest,
        case_id=authority.fixed_case.case_id,
        case_record_digest=authority.fixed_case.case_record_digest,
        case_specification_digest=authority.fixed_case.case_specification_digest,
        case_binding_digest=authority.fixed_case.case_binding_digest,
        backend_candidate_id=authority.fixed_case.backend_candidate_id,
        backend_algorithm_version=authority.fixed_case.backend_algorithm_version,
        backend_runtime_manifest_digest=authority.fixed_case.backend_runtime_manifest_digest,
        backend_configuration_digest=authority.fixed_case.backend_configuration_digest,
        warp_plan_digest=authority.fixed_case.warp_plan_digest,
        input_image_version_id=authority.input_image_version_id,
        input_image_version_digest=authority.input_image_version_digest,
        input_asset_id=authority.input_asset_id,
        input_asset_sha256=authority.input_asset_sha256,
        root_source_asset_id=authority.root_source_asset_id,
        root_source_asset_sha256=authority.root_source_asset_sha256,
        result_sha256=hashlib.sha256(b"result").hexdigest(),
        result_byte_size=6,
        result_media_type="image/jpeg",
        result_width=10,
        result_height=10,
        changed_pixel_count=1,
        engine_digest="4" * 64,
        config_digest="5" * 64,
        stable_core_digest="0" * 64,
    )
    first = GeometryAttemptExecutionEvidence(
        GeometryJobAttemptBinding("6" * 32, "7" * 32, "7" * 64, "8" * 32, "9" * 64),
        authority.operation_id,
        authority.operation_authority_digest,
        authority.operation_spec_digest,
        authority.authority_digest,
        core.stable_core_digest,
        "a" * 64,
        "0" * 64,
    )
    second = GeometryAttemptExecutionEvidence(
        GeometryJobAttemptBinding("6" * 32, "7" * 32, "7" * 64, "a" * 32, "b" * 64),
        authority.operation_id,
        authority.operation_authority_digest,
        authority.operation_spec_digest,
        authority.authority_digest,
        core.stable_core_digest,
        "b" * 64,
        "0" * 64,
    )
    assert core.stable_core_digest == core.content_digest()
    assert first.attempt_receipt_digest != second.attempt_receipt_digest
    assert "job_attempt" not in {field.name for field in fields(GeometryStableMaterializationCore)}


def test_fixed_case_has_no_historical_result_or_measurement_input() -> None:
    forbidden = {"historical_result", "result_m3", "measured_delta_ppm", "artifact_status"}
    fixed_case_fields = {field.name for field in fields(D02FixedGeometryCase)}
    assert forbidden.isdisjoint(fixed_case_fields)
