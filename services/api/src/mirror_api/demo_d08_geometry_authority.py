"""Public PostgreSQL resolver for the frozen D08 geometry authority.

This module consumes only persisted public authority rows.  It intentionally
has no storage, private-runtime, or provider access.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api import demo_d02_generic_admission as d02_generic
from mirror_api import demo_d02_generic_screening as d02_screening
from mirror_api import demo_d02_r2_authority as d02_r2
from mirror_api import demo_d02_source_acquisition as d02_acquisition
from mirror_api.demo_d08_geometry_adapter import (
    D02FixedGeometryCase,
    GeometryAdapterAuthorityError,
    GeometryDirection,
    GeometryExecutionAuthority,
    GeometryJobAttemptBinding,
    operation_spec_digest,
)
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest
from mirror_api.demo_models import (
    D02SelectedSourceManifest,
    DemoD02R2Epoch2Admission,
    DemoD02R2SourceAuthority,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoImageVersion,
    DemoJobBinding,
    DemoPairScreeningReport,
)
from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    parse_operation_spec,
)
from mirror_api.models import Asset, AssetVariant, Job, JobAttempt
from mirror_api.providers.opencv_geometry import ALGORITHM_VERSION, CANDIDATE_ID


class GeometryAuthorityResolutionError(RuntimeError):
    """A public geometry authority cannot be replayed exactly."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


async def require_geometry_plan_admission(
    session: AsyncSession,
    *,
    editing_session_id: str,
    image_version_id: str,
    operation: OperationSpec,
) -> None:
    """Fail closed before a geometry plan creates any immutable plan rows."""

    editing = await _one(session, DemoEditingSession, editing_session_id)
    image = await _one(session, DemoImageVersion, image_version_id)
    latest = await session.scalar(
        select(func.max(DemoImageVersion.sequence)).where(
            DemoImageVersion.editing_session_id == editing.id
        )
    )
    if (
        operation.engine is not OperationEngine.GEOMETRY
        or operation.operation_type is not OperationType.GEOMETRY
        or image.editing_session_id != editing.id
        or image.sequence != 0
        or latest != 0
        or image.parent_version_id is not None
        or image.source_asset_id != editing.source_asset_id
        or image.source_asset_sha256 != editing.source_asset_sha256
    ):
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_PLAN_ADMISSION_INVALID", "geometry plan input is unavailable"
        )
    root = await session.scalar(
        select(Asset).where(Asset.id == editing.source_asset_id).with_for_update()
    )
    variant = await session.scalar(
        select(AssetVariant)
        .where(AssetVariant.id == image.result_asset_variant_id)
        .with_for_update()
    )
    snapshot = await session.scalar(
        select(Asset).where(Asset.id == image.result_asset_id).with_for_update()
    )
    if (
        root is None
        or snapshot is None
        or variant is None
        or root.deleted_at is not None
        or snapshot.deleted_at is not None
        or not root.synthetic
        or not snapshot.synthetic
        or root.storage_key != f"internal-synthetic/v1/d02/source/{root.id}"
        or snapshot.id == root.id
        or snapshot.asset_role != "derived"
        or snapshot.storage_key != f"demo-original/v1/{editing.id}/{root.sha256}"
        or snapshot.sha256 != root.sha256
        or snapshot.byte_size != root.byte_size
        or snapshot.mime_type != root.mime_type
        or snapshot.width != root.width
        or snapshot.height != root.height
        or image.result_asset_id != snapshot.id
        or image.result_asset_sha256 != snapshot.sha256
        or variant.source_asset_id != root.id
        or variant.result_asset_id != snapshot.id
        or variant.variant_type != "demo_p3_p7_original_snapshot"
    ):
        raise GeometryAuthorityResolutionError(
            "D02_SOURCE_AUTHORITY_UNAVAILABLE", "D02 source is unavailable"
        )
    from mirror_api.demo_editing_repository import (
        DemoEditingRepositoryError,
        SqlAlchemyDemoEditingRepository,
        _canonical_authority_matches,
    )

    try:
        await SqlAlchemyDemoEditingRepository._require_generic_d02_source_authority(session, root)
    except DemoEditingRepositoryError as exc:
        raise GeometryAuthorityResolutionError(
            exc.code, "D02 source authority is unavailable"
        ) from exc
    authorities = list(
        await session.scalars(
            select(DemoD02R2SourceAuthority)
            .where(
                DemoD02R2SourceAuthority.source_asset_id == root.id,
                DemoD02R2SourceAuthority.source_asset_sha256 == root.sha256,
                DemoD02R2SourceAuthority.schema_version == d02_generic.SOURCE_SCHEMA,
            )
            .with_for_update()
        )
    )
    if len(authorities) != 1 or authorities[0].selected_source_manifest_id is None:
        raise GeometryAuthorityResolutionError(
            "D02_SOURCE_AUTHORITY_UNAVAILABLE", "D02 source is unavailable"
        )
    manifest = await session.scalar(
        select(D02SelectedSourceManifest)
        .where(
            D02SelectedSourceManifest.id == authorities[0].selected_source_manifest_id,
            D02SelectedSourceManifest.schema_version
            == d02_acquisition.SELECTED_SOURCE_MANIFEST_SCHEMA,
            D02SelectedSourceManifest.manifest_state == "FINALIZED",
        )
        .with_for_update()
    )
    admission = await session.scalar(
        select(DemoD02R2Epoch2Admission)
        .where(
            DemoD02R2Epoch2Admission.selected_source_manifest_id
            == authorities[0].selected_source_manifest_id,
            DemoD02R2Epoch2Admission.schema_version == d02_generic.ADMISSION_SCHEMA,
            DemoD02R2Epoch2Admission.admission_state == "COMPLETED",
        )
        .with_for_update()
    )
    report = (
        None
        if admission is None
        else await session.scalar(
            select(DemoPairScreeningReport)
            .where(
                DemoPairScreeningReport.id == admission.screening_report_id,
                DemoPairScreeningReport.schema_version == d02_screening.REPORT_SCHEMA,
                DemoPairScreeningReport.status == "PASSED",
                DemoPairScreeningReport.report_digest == admission.screening_report_digest,
            )
            .with_for_update()
        )
    )
    delta = operation.parameters.get("delta_ppm")
    dimension = operation.parameters.get("dimension_key")
    cases = (
        None
        if report is None or not isinstance(report.report_payload, Mapping)
        else report.report_payload.get("ordered_case_manifest")
    )
    if (
        manifest is None
        or not _canonical_authority_matches(
            manifest, d02_acquisition.SELECTED_SOURCE_MANIFEST_SCHEMA
        )
        or admission is None
        or not _canonical_authority_matches(admission, d02_generic.ADMISSION_SCHEMA)
        or report is None
        or not _canonical_authority_matches(report, d02_screening.REPORT_SCHEMA)
        or admission.admission_state != "COMPLETED"
        or report.status != "PASSED"
        or report.report_digest != admission.screening_report_digest
        or type(delta) is not int
        or not isinstance(dimension, str)
        or not isinstance(cases, list)
        or len(
            [
                case
                for case in cases
                if isinstance(case, Mapping)
                and case.get("source_asset_id") == root.id
                and case.get("source_asset_sha256") == root.sha256
                and case.get("dimension_key") == dimension
                and case.get("direction") == ("INCREASE" if delta > 0 else "DECREASE")
                and case.get("magnitude_ppm") == abs(delta)
            ]
        )
        != 1
    ):
        raise GeometryAuthorityResolutionError(
            "D02_FIXED_CASE_UNAVAILABLE", "D02 fixed case is unavailable"
        )


async def resolve_geometry_execution_authority(
    session: AsyncSession,
    *,
    actor_id: str,
    session_id: str,
    editing_session_id: str,
    plan_id: str,
    operation_id: str,
    operation: OperationSpec,
    execution_job_binding_id: str,
    formal_job_attempt_id: str,
) -> tuple[GeometryExecutionAuthority, GeometryJobAttemptBinding]:
    """Lock and replay the one legal D02 SOURCE fixed case for an execution."""

    if (
        operation.engine is not OperationEngine.GEOMETRY
        or operation.operation_type is not OperationType.GEOMETRY
    ):
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_OPERATION_INVALID", "operation is not geometry"
        )
    editing = await _one(session, DemoEditingSession, editing_session_id)
    plan = await _one(session, DemoEditPlan, plan_id)
    row = await _one(session, DemoEditOperation, operation_id)
    binding = await _one(session, DemoJobBinding, execution_job_binding_id)
    job = await session.scalar(select(Job).where(Job.id == binding.job_id).with_for_update())
    if job is None:
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_JOB_UNAVAILABLE", "execution Job is unavailable"
        )
    attempt = await _one(session, JobAttempt, formal_job_attempt_id)
    if (
        editing.demo_actor_id != actor_id
        or editing.demo_session_id != session_id
        or plan.id != plan_id
        or plan.record_kind != "RESULT"
        or plan.editing_session_id != editing.id
        or row.edit_plan_id != plan.id
        or row.operation_index != 0
        or row.demo_actor_id != actor_id
        or row.demo_session_id != session_id
        or row.engine != operation.engine.value
        or row.operation_type != operation.operation_type.value
        or row.parameters != dict(operation.parameters)
        or row.preserve != [item.value for item in operation.preserve]
        or row.expected_effect != dict(operation.expected_effect)
        or binding.demo_actor_id != actor_id
        or binding.demo_session_id != session_id
        or binding.endpoint_operation != "edit_plan.execute"
        or binding.target_type != "EDIT_PLAN"
        or binding.target_id != plan.id
        or attempt.job_id != job.id
        or attempt.attempt != job.attempt_count
        or attempt.status != "RUNNING"
        or job.status != "RUNNING"
    ):
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_EXECUTION_AUTHORITY_MISMATCH", "execution rows do not agree"
        )
    from mirror_api.demo_editing_repository import (
        DemoEditingRepositoryError,
        SqlAlchemyDemoEditingRepository,
        _canonical_authority_matches,
    )

    try:
        persisted_spec = parse_operation_spec(
            {
                "engine": row.engine,
                "operation_type": row.operation_type,
                "parameters": row.parameters,
                "preserve": row.preserve,
                "expected_effect": row.expected_effect,
            }
        )
    except Exception as exc:
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_OPERATION_INVALID", "stored operation is invalid"
        ) from exc
    if persisted_spec != operation:
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_OPERATION_PROJECTION_MISMATCH", "operation projection changed"
        )
    image = await _one(session, DemoImageVersion, plan.input_image_version_id)
    latest = await session.scalar(
        select(func.max(DemoImageVersion.sequence)).where(
            DemoImageVersion.editing_session_id == editing.id
        )
    )
    source = await session.scalar(
        select(Asset).where(Asset.id == image.result_asset_id).with_for_update()
    )
    root = await session.scalar(
        select(Asset).where(Asset.id == editing.source_asset_id).with_for_update()
    )
    variant = await session.scalar(
        select(AssetVariant)
        .where(AssetVariant.id == image.result_asset_variant_id)
        .with_for_update()
    )
    if (
        image.demo_actor_id != actor_id
        or image.demo_session_id != session_id
        or image.editing_session_id != editing.id
        or image.sequence != 0
        or latest != 0
        or image.parent_version_id is not None
        or image.source_asset_id != editing.source_asset_id
        or image.source_asset_sha256 != editing.source_asset_sha256
        or image.result_asset_sha256 != editing.source_asset_sha256
        or source is None
        or root is None
        or variant is None
        or source.id == root.id
        or image.result_asset_id != source.id
        or source.sha256 != root.sha256
        or source.byte_size != root.byte_size
        or source.mime_type != root.mime_type
        or source.width != root.width
        or source.height != root.height
        or source.asset_role != "derived"
        or source.storage_key != f"demo-original/v1/{editing.id}/{root.sha256}"
        or variant.source_asset_id != root.id
        or variant.result_asset_id != source.id
        or variant.variant_type != "demo_p3_p7_original_snapshot"
        or root.storage_key != f"internal-synthetic/v1/d02/source/{root.id}"
        or source.deleted_at is not None
        or root.deleted_at is not None
        or not source.synthetic
        or not root.synthetic
    ):
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_SOURCE_LINEAGE_INVALID", "input is not current sequence-zero D02 source"
        )
    try:
        await SqlAlchemyDemoEditingRepository._require_generic_d02_source_authority(session, root)
    except DemoEditingRepositoryError as exc:
        raise GeometryAuthorityResolutionError(
            exc.code, "D02 source authority is unavailable"
        ) from exc
    source_authorities = list(
        await session.scalars(
            select(DemoD02R2SourceAuthority)
            .where(
                DemoD02R2SourceAuthority.source_asset_id == root.id,
                DemoD02R2SourceAuthority.source_asset_sha256 == root.sha256,
                DemoD02R2SourceAuthority.schema_version == d02_generic.SOURCE_SCHEMA,
            )
            .with_for_update()
        )
    )
    if len(source_authorities) != 1 or source_authorities[0].selected_source_manifest_id is None:
        raise GeometryAuthorityResolutionError(
            "D02_SOURCE_AUTHORITY_UNAVAILABLE", "D02 source authority is unavailable"
        )
    source_authority = source_authorities[0]
    manifest = await session.scalar(
        select(D02SelectedSourceManifest)
        .where(
            D02SelectedSourceManifest.id == source_authority.selected_source_manifest_id,
            D02SelectedSourceManifest.schema_version
            == d02_acquisition.SELECTED_SOURCE_MANIFEST_SCHEMA,
            D02SelectedSourceManifest.manifest_state == "FINALIZED",
        )
        .with_for_update()
    )
    if manifest is None or not _canonical_authority_matches(
        manifest, d02_acquisition.SELECTED_SOURCE_MANIFEST_SCHEMA
    ):
        raise GeometryAuthorityResolutionError(
            "D02_ADMISSION_UNAVAILABLE", "D02 manifest is unavailable"
        )
    admission = await session.scalar(
        select(DemoD02R2Epoch2Admission)
        .where(
            DemoD02R2Epoch2Admission.selected_source_manifest_id == manifest.id,
            DemoD02R2Epoch2Admission.schema_version == d02_generic.ADMISSION_SCHEMA,
            DemoD02R2Epoch2Admission.admission_state == "COMPLETED",
        )
        .with_for_update()
    )
    if admission is None or not _canonical_authority_matches(
        admission, d02_generic.ADMISSION_SCHEMA
    ):
        raise GeometryAuthorityResolutionError(
            "D02_ADMISSION_UNAVAILABLE", "D02 admission is unavailable"
        )
    report = await session.scalar(
        select(DemoPairScreeningReport)
        .where(
            DemoPairScreeningReport.id == admission.screening_report_id,
            DemoPairScreeningReport.schema_version == d02_screening.REPORT_SCHEMA,
            DemoPairScreeningReport.status == "PASSED",
            DemoPairScreeningReport.report_digest == admission.screening_report_digest,
        )
        .with_for_update()
    )
    if (
        report is None
        or report.schema_version != d02_screening.REPORT_SCHEMA
        or report.status != "PASSED"
        or report.report_digest != admission.screening_report_digest
        or not _canonical_authority_matches(report, report.schema_version)
    ):
        raise GeometryAuthorityResolutionError(
            "D02_REPORT_UNAVAILABLE", "D02 report is unavailable"
        )
    payload = report.report_payload
    if not isinstance(payload, Mapping):
        raise GeometryAuthorityResolutionError("D02_REPORT_REPLAY_FAILED", "D02 report is invalid")
    cases = payload.get("ordered_case_manifest")
    observations = payload.get("source_m3_repeat_evidence")
    if not isinstance(cases, list) or not isinstance(observations, list):
        raise GeometryAuthorityResolutionError(
            "D02_CASE_UNAVAILABLE", "D02 case authority is unavailable"
        )
    delta = operation.parameters.get("delta_ppm")
    dimension = operation.parameters.get("dimension_key")
    if type(delta) is not int or not isinstance(dimension, str):
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_OPERATION_INVALID", "operation parameters are invalid"
        )
    direction = "INCREASE" if delta > 0 else "DECREASE"
    matching = [
        item
        for item in cases
        if isinstance(item, Mapping)
        and item.get("source_asset_id") == root.id
        and item.get("source_asset_sha256") == root.sha256
        and item.get("dimension_key") == dimension
        and item.get("direction") == direction
        and item.get("magnitude_ppm") == abs(delta)
    ]
    if len(matching) != 1:
        raise GeometryAuthorityResolutionError(
            "D02_FIXED_CASE_UNAVAILABLE", "fixed D02 case is unavailable"
        )
    case = cast(Mapping[str, Any], matching[0])
    try:
        _validate_generic_case(case)
    except Exception as exc:
        raise GeometryAuthorityResolutionError(
            "D02_FIXED_CASE_INVALID", "fixed D02 case is invalid"
        ) from exc
    source_landmark_digest = _source_landmark_digest(
        observations,
        source_asset_id=root.id,
        source_asset_sha256=root.sha256,
    )
    try:
        fixed = D02FixedGeometryCase(
            case_id=cast(str, case["case_id"]),
            case_record_digest=cast(str, case["record_digest"]),
            case_specification_digest=cast(str, case["case_specification_digest"]),
            case_binding_digest="0" * 64,
            case_ordinal=cast(int, case["case_ordinal"]),
            source_ordinal=cast(int, case["source_ordinal"]),
            source_asset_id=root.id,
            source_asset_sha256=root.sha256,
            dimension_key=dimension,
            direction=GeometryDirection(direction),
            magnitude_ppm=abs(delta),
            warp_plan_digest=cast(str, case["warp_plan_digest"]),
            geometry_ontology_digest=cast(str, case["geometry_ontology_version_digest"]),
            source_landmark_digest=source_landmark_digest,
            output_policy_version=cast(str, case["output_policy_version"]),
            determinism_version=cast(str, case["determinism_level"]),
            backend_candidate_id=CANDIDATE_ID,
            backend_algorithm_version=cast(str, case["geometry_algorithm_version"]),
            backend_runtime_manifest_digest=cast(str, case["runtime_manifest_digest"]),
            backend_configuration_digest=cast(str, case["runtime_config_digest"]),
            output_width=cast(int, case["output_width"]),
            output_height=cast(int, case["output_height"]),
        )
        if fixed.backend_algorithm_version != ALGORITHM_VERSION:
            raise GeometryAuthorityResolutionError(
                "D02_BACKEND_UNQUALIFIED", "D02 case backend is not qualified"
            )
        fixed = replace(fixed, case_binding_digest=fixed.content_digest())
        authority = GeometryExecutionAuthority(
            editing_session_id=editing.id,
            editing_session_digest=editing.content_digest,
            plan_id=plan.id,
            plan_digest=plan.content_digest,
            operation_id=row.id,
            operation_authority_digest=row.content_digest,
            operation_spec_digest=operation_spec_digest(operation),
            input_image_version_id=image.id,
            input_image_version_digest=image.content_digest,
            input_sequence=image.sequence,
            input_asset_id=source.id,
            input_asset_sha256=source.sha256,
            root_source_asset_id=root.id,
            root_source_asset_sha256=root.sha256,
            d02_admission_id=admission.id,
            d02_admission_digest=admission.content_digest,
            d02_screening_report_id=report.id,
            d02_screening_report_digest=report.report_digest,
            fixed_case=fixed,
            authority_digest="0" * 64,
        )
        authority = replace(authority, authority_digest=authority.content_digest())
    except (KeyError, TypeError, GeometryAdapterAuthorityError) as exc:
        raise GeometryAuthorityResolutionError(
            "D02_FIXED_CASE_INVALID", "fixed D02 case is invalid"
        ) from exc
    attempt_payload = {
        "attempt": attempt.attempt,
        "attempt_id": attempt.id,
        "attempt_status": attempt.status,
        "execution_job_binding_id": binding.id,
        "job_attempt_count": job.attempt_count,
        "job_id": job.id,
        "job_binding_digest": binding.content_digest,
        "lease_acquired_at": _time(job.lease_acquired_at),
        "lease_expires_at": _time(job.lease_expires_at),
        "started_at": _time(attempt.started_at),
    }
    attempt_digest = hashlib.sha256(
        b"mirror.demo/D08GeometryJobAttempt/v1\n" + canonical_json_bytes(attempt_payload)
    ).hexdigest()
    return authority, GeometryJobAttemptBinding(
        job_id=job.id,
        execution_job_binding_id=binding.id,
        job_binding_digest=binding.content_digest,
        attempt_id=attempt.id,
        attempt_digest=attempt_digest,
    )


async def _one(session: AsyncSession, model: type[Any], identifier: str) -> Any:
    row = await session.scalar(select(model).where(model.id == identifier).with_for_update())
    if row is None:
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_AUTHORITY_UNAVAILABLE", "authority row is unavailable"
        )
    return row


def _time(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise GeometryAuthorityResolutionError(
            "GEOMETRY_ATTEMPT_TIME_INVALID", "Job Attempt time authority is invalid"
        )
    return value.astimezone(UTC).isoformat()


def _source_landmark_digest(
    observations: list[object],
    *,
    source_asset_id: str,
    source_asset_sha256: str,
) -> str:
    matches = [
        item
        for item in observations
        if isinstance(item, Mapping)
        and item.get("source_asset_id") == source_asset_id
        and item.get("source_asset_sha256") == source_asset_sha256
    ]
    if len(matches) != 3:
        raise GeometryAuthorityResolutionError(
            "D02_SOURCE_LANDMARK_UNAVAILABLE", "source landmark authority is unavailable"
        )
    repeats: set[int] = set()
    digests: set[str] = set()
    for item in matches:
        repeat = item.get("repeat_index")
        digest = item.get("landmark_digest")
        if (
            type(repeat) is not int
            or repeat not in {1, 2, 3}
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise GeometryAuthorityResolutionError(
                "D02_SOURCE_LANDMARK_UNAVAILABLE",
                "source landmark authority is unavailable",
            )
        repeats.add(repeat)
        digests.add(digest)
    if repeats != {1, 2, 3} or len(digests) != 1:
        raise GeometryAuthorityResolutionError(
            "D02_SOURCE_LANDMARK_UNAVAILABLE", "source landmark authority is unavailable"
        )
    return next(iter(digests))


def _validate_generic_case(case: Mapping[str, Any]) -> None:
    """Replay the generic admitted case record without legacy private-ID derivation."""

    required = {
        "case_id",
        "case_ordinal",
        "case_specification_digest",
        "determinism_level",
        "dimension_key",
        "direction",
        "geometry_algorithm_version",
        "geometry_ontology_version_digest",
        "magnitude_ppm",
        "output_height",
        "output_policy_version",
        "output_width",
        "record_digest",
        "runtime_config_digest",
        "runtime_manifest_digest",
        "schema_version",
        "source_asset_id",
        "source_asset_sha256",
        "source_ordinal",
        "warp_plan_digest",
    }
    if not required.issubset(case) or case.get("schema_version") != d02_r2.R2_CASE_SCHEMA:
        raise ValueError("case shape is invalid")
    for key in (
        "case_specification_digest",
        "geometry_ontology_version_digest",
        "record_digest",
        "runtime_config_digest",
        "runtime_manifest_digest",
        "source_asset_sha256",
        "warp_plan_digest",
    ):
        value = case.get(key)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError("case digest is invalid")
    for key in ("case_id", "source_asset_id"):
        value = case.get(key)
        if (
            not isinstance(value, str)
            or len(value) != 32
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError("case identifier is invalid")
    if (
        type(case.get("case_ordinal")) is not int
        or not 1 <= cast(int, case["case_ordinal"]) <= 48
        or type(case.get("source_ordinal")) is not int
        or not 1 <= cast(int, case["source_ordinal"]) <= 4
        or case.get("dimension_key") not in {"jaw_width", "chin_height", "eye_spacing"}
        or case.get("direction") not in {"INCREASE", "DECREASE"}
        or case.get("magnitude_ppm") not in {15_000, 30_000}
        or type(case.get("output_width")) is not int
        or cast(int, case["output_width"]) <= 0
        or type(case.get("output_height")) is not int
        or cast(int, case["output_height"]) <= 0
    ):
        raise ValueError("case values are invalid")
    for key in ("determinism_level", "geometry_algorithm_version", "output_policy_version"):
        if not isinstance(case.get(key), str) or not cast(str, case[key]):
            raise ValueError("case version is invalid")
    canonical = cast(
        Mapping[str, JsonValue],
        {
            key: value
            for key, value in case.items()
            if key not in {"schema_version", "record_digest"}
        },
    )
    if case["record_digest"] != mirror_demo_digest(d02_r2.R2_CASE_SCHEMA, canonical):
        raise ValueError("case record digest does not replay")
