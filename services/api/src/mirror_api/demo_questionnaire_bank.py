"""Read-only, fail-closed D02-R2 bank projection for the P4 scheduler."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from types import MappingProxyType
from typing import Any, Final, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api import demo_d02_generic_screening as generic_screening
from mirror_api.demo_d02_generic_admission import GenericAdmissionError
from mirror_api.demo_d02_r2_authority import (
    R2_BANK_FIELDS,
    R2_BANK_SCHEMA,
    R2_PAIR_FIELDS,
    R2_PAIR_SCHEMA,
    R2_REPORT_FIELDS,
    R2_REPORT_SCHEMA,
    D02R2AuthorityError,
    validate_r2_pair_qa_payload,
    validate_r2_report_payload,
)
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest
from mirror_api.demo_models import (
    DemoD02R2Epoch2Admission,
    DemoPairScreeningReport,
    DemoQuestionBank,
    DemoQuestionPair,
)
from mirror_api.demo_questionnaire_routing import QuestionPair

PROJECTION_SCHEMA: Final = "mirror.demo/D04BQuestionBankProjection/v1"
PROJECTION_CONFIG_SCHEMA: Final = "mirror.demo/D04BQuestionBankProjectionConfig/v1"
_FISHER_VERSION: Final = "demo-symmetric-pair-fisher-normalized-v1"
_SCALE_VERSION: Final = "demo-robust-mad-scale-v1"
_SCALE_FLOOR: Final = 1_000
_SCALE_MULTIPLIER_PPM: Final = 1_482_600
_MAX_MAGNITUDE: Final = 30_000
_PAIR_MAGNITUDES: Final = frozenset({15_000, 30_000})
_POSTERIOR_TAU_PPM: Final = 15_000
_ADMISSION_CANONICAL_FIELDS: Final = {
    "idempotency_key_hash",
    "request_digest",
    "execution_epoch",
    "evidence_root_id",
    "source_manifest_digest",
    "screening_report_id",
    "screening_report_digest",
    "question_bank_id",
    "question_bank_content_digest",
    "question_bank_version",
    "selected_pair_manifest_digest",
    "source_authority_count",
    "synthetic_identity_count",
    "question_pair_count",
    "selected_result_side_count",
    "admission_state",
}
_GENERIC_ADMISSION_SCHEMA: Final = "mirror.demo/D02GenericAdmission/v1"
_GENERIC_REPORT_SCHEMA: Final = "mirror.demo/D02GenericPairScreeningReport/v1"
_GENERIC_BANK_SCHEMA: Final = "mirror.demo/D02GenericQuestionBank/v1"
_GENERIC_PAIR_SCHEMA: Final = "mirror.demo/D02GenericQuestionPair/v1"
_GENERIC_SOURCE_ENTRY_SCHEMA: Final = "mirror.demo/D02GenericSourceManifestEntry/v1"
_GENERIC_SOURCE_MEASUREMENT_SCHEMA: Final = "mirror.demo/D02GenericSourceMeasurement/v1"
_GENERIC_SOURCE_PROJECTION_SCHEMA: Final = "mirror.demo/D02GenericSourceProjection/v1"
_GENERIC_DIMENSIONS: Final = ("eye_spacing", "jaw_width")
_GENERIC_ADMISSION_CANONICAL_FIELDS: Final = _ADMISSION_CANONICAL_FIELDS - {"evidence_root_id"} | {
    "selected_source_manifest_id"
}


class QuestionBankProjectionError(ValueError):
    pass


@dataclass(frozen=True)
class QuestionSidePresentation:
    result_asset_id: str
    result_checksum: str
    result_lineage_digest: str
    requested_direction: str
    measured_delta_ppm: int


@dataclass(frozen=True)
class QuestionPairPresentation:
    question_pair_digest: str
    source_asset_id: str
    source_checksum: str
    left: QuestionSidePresentation
    right: QuestionSidePresentation


@dataclass(frozen=True)
class AdmittedQuestionBank:
    pairs: tuple[QuestionPair, ...]
    morphology_scale_ppm: Mapping[str, int]
    morphology_scale_floor_ppm: int
    config_digest: str
    projection_digest: str
    canonical_payload: Mapping[str, object]
    presentations: Mapping[str, QuestionPairPresentation]


async def load_admitted_question_bank(
    session: AsyncSession, question_bank_id: str
) -> AdmittedQuestionBank:
    """Load one completed, schema-recognized D02 graph without database writes."""
    with session.no_autoflush:
        admission = await session.scalar(
            select(DemoD02R2Epoch2Admission).where(
                DemoD02R2Epoch2Admission.question_bank_id == question_bank_id
            )
        )
        if admission is None or admission.admission_state != "COMPLETED":
            raise QuestionBankProjectionError("question bank is not admitted")
        bank = await session.get(DemoQuestionBank, question_bank_id)
        report = await session.get(DemoPairScreeningReport, admission.screening_report_id)
        pairs = list(
            (
                await session.scalars(
                    select(DemoQuestionPair)
                    .where(DemoQuestionPair.question_bank_id == question_bank_id)
                    .order_by(DemoQuestionPair.id)
                )
            ).all()
        )
    if bank is None or report is None:
        raise QuestionBankProjectionError("admission graph is incomplete")
    return project_admitted_question_bank(admission, bank, report, pairs)


def project_admitted_question_bank(
    admission: DemoD02R2Epoch2Admission,
    bank: DemoQuestionBank,
    report: DemoPairScreeningReport,
    pairs: Sequence[DemoQuestionPair],
) -> AdmittedQuestionBank:
    if admission.schema_version == _GENERIC_ADMISSION_SCHEMA:
        return _project_generic_admitted_question_bank(admission, bank, report, pairs)
    if admission.schema_version != "mirror.demo/D02R2Epoch2Admission/v1":
        raise QuestionBankProjectionError("admission schema is unsupported")
    try:
        report_payload = validate_r2_report_payload(report.report_payload)
    except D02R2AuthorityError as exc:
        raise QuestionBankProjectionError("screening Report authority is invalid") from exc
    if (
        admission.schema_version != "mirror.demo/D02R2Epoch2Admission/v1"
        or admission.admission_state != "COMPLETED"
        or admission.execution_epoch != "D02_R2_EPOCH_02"
        or admission.question_bank_id != bank.id
        or report.schema_version != R2_REPORT_SCHEMA
        or report.status != "PASSED"
        or report.report_digest != mirror_demo_digest(R2_REPORT_SCHEMA, report_payload)
        or report.source_count != 4
        or report.source_m3_repeat_count != 12
        or report.selected_pair_count != 16
        or report.selected_result_side_count != 32
        or bank.schema_version != R2_BANK_SCHEMA
    ):
        raise QuestionBankProjectionError("admitted authority state is invalid")
    _validate_canonical_row(
        admission,
        "mirror.demo/D02R2Epoch2Admission/v1",
        _ADMISSION_CANONICAL_FIELDS,
    )
    _validate_canonical_row(report, R2_REPORT_SCHEMA, R2_REPORT_FIELDS)
    _validate_canonical_row(bank, R2_BANK_SCHEMA, R2_BANK_FIELDS)
    if (
        admission.question_bank_content_digest != bank.content_digest
        or admission.question_bank_version != bank.version
        or admission.screening_report_id != report.id
        or admission.screening_report_digest != report.report_digest
        or bank.screening_report_id != report.id
        or bank.screening_report_digest != report.report_digest
        or bank.pair_manifest_digest != admission.selected_pair_manifest_digest
        or report.selected_pair_manifest_digest != admission.selected_pair_manifest_digest
        or len(pairs) != 16
        or admission.question_pair_count != 16
        or admission.selected_result_side_count != 32
        or admission.source_authority_count != 4
        or admission.synthetic_identity_count != 4
    ):
        raise QuestionBankProjectionError("admission bindings or cardinality are invalid")
    dimensions = _dimensions(bank.dimension_manifest)
    if tuple(sorted(report.selected_dimension_keys)) != dimensions:
        raise QuestionBankProjectionError("bank and Report selected dimensions disagree")
    anchors = _source_anchors(report_payload, dimensions)
    if len(anchors) != 4:
        raise QuestionBankProjectionError("four source anchors are required")
    report_view: dict[str, object] = {
        "id": report.id,
        "report_digest": report.report_digest,
        "source_manifest_digest": report.source_manifest_digest,
        "selected_pair_manifest_digest": report.selected_pair_manifest_digest,
        "report_payload": report_payload,
    }
    projected: list[QuestionPair] = []
    presentations: dict[str, QuestionPairPresentation] = {}
    for pair in sorted(pairs, key=lambda row: row.id):
        if (
            pair.schema_version != R2_PAIR_SCHEMA
            or pair.screening_report_id != report.id
            or pair.screening_report_digest != report.report_digest
            or pair.question_bank_id != bank.id
            or pair.dimension_key not in dimensions
            or pair.magnitude_ppm not in _PAIR_MAGNITUDES
            or pair.pair_quality_ppm <= 0
        ):
            raise QuestionBankProjectionError("question pair report binding is invalid")
        _validate_canonical_row(pair, R2_PAIR_SCHEMA, R2_PAIR_FIELDS)
        try:
            qa = validate_r2_pair_qa_payload(pair.qa_payload, report=report_view)
        except D02R2AuthorityError as exc:
            raise QuestionBankProjectionError("question pair QA authority is invalid") from exc
        source_anchor = anchors.get(pair.demo_synthetic_identity_id)
        if source_anchor is None or pair.dimension_key not in source_anchor:
            raise QuestionBankProjectionError("pair source identity or target anchor is invalid")
        projected_pair = QuestionPair(
            pair.id,
            pair.dimension_key,
            pair.magnitude_ppm,
            pair.demo_synthetic_identity_id,
            MappingProxyType(dict(source_anchor)),
            _fisher(pair.magnitude_ppm),
            pair.pair_quality_ppm,
        )
        projected.append(projected_pair)
        record = cast(Mapping[str, Any], qa["pair_screening_record_payload"])
        record_payload = cast(Mapping[str, Any], record["pair_screening_record_payload"])
        left = cast(Mapping[str, Any], record_payload["left"])
        right = cast(Mapping[str, Any], record_payload["right"])
        presentations[pair.id] = QuestionPairPresentation(
            question_pair_digest=pair.content_digest,
            source_asset_id=pair.source_asset_id,
            source_checksum=pair.source_asset_sha256,
            left=QuestionSidePresentation(
                result_asset_id=pair.left_asset_id,
                result_checksum=pair.left_asset_sha256,
                result_lineage_digest=cast(str, left["lineage_digest"]),
                requested_direction="NEGATIVE",
                measured_delta_ppm=pair.left_delta_ppm,
            ),
            right=QuestionSidePresentation(
                result_asset_id=pair.right_asset_id,
                result_checksum=pair.right_asset_sha256,
                result_lineage_digest=cast(str, right["lineage_digest"]),
                requested_direction="POSITIVE",
                measured_delta_ppm=pair.right_delta_ppm,
            ),
        )
    expected_slots = {
        (source_id, dimension, magnitude)
        for source_id in anchors
        for dimension in dimensions
        for magnitude in _PAIR_MAGNITUDES
    }
    actual_slots = {
        (pair.source_identity_id, pair.dimension_id, pair.magnitude_ppm) for pair in projected
    }
    if actual_slots != expected_slots:
        raise QuestionBankProjectionError("projected pair coverage is invalid")
    anchor_dimensions = tuple(sorted(next(iter(anchors.values()))))
    scales = {
        key: _mad_scale([anchor[key] for anchor in anchors.values()]) for key in anchor_dimensions
    }
    config_payload: dict[str, object] = {
        "scale_algorithm_version": _SCALE_VERSION,
        "scale_floor_ppm": _SCALE_FLOOR,
        "scale_multiplier_ppm": _SCALE_MULTIPLIER_PPM,
        "fisher_algorithm_version": _FISHER_VERSION,
        "posterior_tau_ppm": _POSTERIOR_TAU_PPM,
        "fisher_evaluation_delta_ppm": 0,
        "max_magnitude_ppm": _MAX_MAGNITUDE,
        "questionnaire_runtime_generation_calls": 0,
        "bank_algorithm_config_digest": bank.algorithm_config_digest,
        "bank_routing_version": bank.routing_version,
        "bank_stopping_version": bank.stopping_version,
        "bank_neighborhood_version": bank.neighborhood_version,
    }
    config_digest = mirror_demo_digest(
        PROJECTION_CONFIG_SCHEMA, cast(Mapping[str, JsonValue], config_payload)
    )
    projection_payload: dict[str, object] = {
        "config": config_payload,
        "config_digest": config_digest,
        "admission_id": admission.id,
        "admission_content_digest": admission.content_digest,
        "bank_id": bank.id,
        "bank_content_digest": bank.content_digest,
        "report_id": report.id,
        "report_digest": report.report_digest,
        "report_content_digest": report.content_digest,
        "dimensions": list(dimensions),
        "scales": dict(sorted(scales.items())),
        "pairs": [
            {
                "pair_id": p.pair_id,
                "question_pair_digest": presentations[p.pair_id].question_pair_digest,
                "dimension_id": p.dimension_id,
                "source_identity_id": p.source_identity_id,
                "source_asset_id": presentations[p.pair_id].source_asset_id,
                "source_checksum": presentations[p.pair_id].source_checksum,
                "magnitude_ppm": p.magnitude_ppm,
                "morphology_anchor_ppm": dict(sorted(p.morphology_anchor_ppm.items())),
                "expected_fisher_information_ppm": p.expected_fisher_information_ppm,
                "pair_quality_ppm": p.pair_quality_ppm,
                "left": {
                    "result_asset_id": presentations[p.pair_id].left.result_asset_id,
                    "result_checksum": presentations[p.pair_id].left.result_checksum,
                    "result_lineage_digest": presentations[p.pair_id].left.result_lineage_digest,
                    "requested_direction": presentations[p.pair_id].left.requested_direction,
                    "measured_delta_ppm": presentations[p.pair_id].left.measured_delta_ppm,
                },
                "right": {
                    "result_asset_id": presentations[p.pair_id].right.result_asset_id,
                    "result_checksum": presentations[p.pair_id].right.result_checksum,
                    "result_lineage_digest": presentations[p.pair_id].right.result_lineage_digest,
                    "requested_direction": presentations[p.pair_id].right.requested_direction,
                    "measured_delta_ppm": presentations[p.pair_id].right.measured_delta_ppm,
                },
            }
            for p in projected
        ],
    }
    digest = mirror_demo_digest(
        PROJECTION_SCHEMA, cast(Mapping[str, JsonValue], projection_payload)
    )
    frozen_payload = _freeze_mapping(projection_payload)
    return AdmittedQuestionBank(
        tuple(projected),
        MappingProxyType(dict(scales)),
        _SCALE_FLOOR,
        config_digest,
        digest,
        frozen_payload,
        MappingProxyType(dict(presentations)),
    )


def _project_generic_admitted_question_bank(
    admission: DemoD02R2Epoch2Admission,
    bank: DemoQuestionBank,
    report: DemoPairScreeningReport,
    pairs: Sequence[DemoQuestionPair],
) -> AdmittedQuestionBank:
    """Project the autonomous D02 graph without treating it as an E2 record."""

    if (
        admission.admission_state != "COMPLETED"
        or admission.execution_epoch != "D02_AUTONOMOUS_V1"
        or admission.evidence_root_id is not None
        or admission.selected_source_manifest_id is None
        or admission.question_bank_id != bank.id
        or report.schema_version != _GENERIC_REPORT_SCHEMA
        or report.status != "PASSED"
        or bank.schema_version != _GENERIC_BANK_SCHEMA
    ):
        raise QuestionBankProjectionError("generic admitted authority state is invalid")
    _validate_canonical_row(
        admission, _GENERIC_ADMISSION_SCHEMA, _GENERIC_ADMISSION_CANONICAL_FIELDS
    )
    _validate_canonical_row(report, _GENERIC_REPORT_SCHEMA, R2_REPORT_FIELDS)
    _validate_canonical_row(bank, _GENERIC_BANK_SCHEMA, R2_BANK_FIELDS)
    report_payload = _generic_report_payload(report)
    binding = _generic_source_binding(report_payload, admission)
    formal_sources = report_payload.get("ordered_source_manifest")
    if not isinstance(formal_sources, list) or report.source_manifest_digest != mirror_demo_digest(
        generic_screening.FORMAL_SOURCE_MANIFEST_SCHEMA,
        cast(Mapping[str, JsonValue], {"ordered_entries": formal_sources}),
    ):
        raise QuestionBankProjectionError("generic formal source manifest does not replay")
    if (
        admission.question_bank_content_digest != bank.content_digest
        or admission.question_bank_version != bank.version
        or admission.screening_report_id != report.id
        or admission.screening_report_digest != report.report_digest
        or admission.source_manifest_digest != report.source_manifest_digest
        or admission.selected_pair_manifest_digest != report.selected_pair_manifest_digest
        or bank.screening_report_id != report.id
        or bank.screening_report_digest != report.report_digest
        or bank.pair_manifest_digest != report.selected_pair_manifest_digest
        or len(pairs) != 16
        or admission.question_pair_count != 16
        or admission.selected_result_side_count != 32
        or admission.source_authority_count != 4
        or admission.synthetic_identity_count != 4
    ):
        raise QuestionBankProjectionError("generic admission bindings or cardinality are invalid")
    try:
        generic_screening.validate_question_bank_row(
            _row_mapping(bank),
            report=_row_mapping(report),
            selected_source_manifest_id=admission.selected_source_manifest_id,
            selected_source_manifest_digest=cast(str, binding["selected_source_manifest_digest"]),
        )
    except GenericAdmissionError as exc:
        raise QuestionBankProjectionError("generic QuestionBank authority is invalid") from exc
    dimensions = _generic_dimensions(bank.dimension_manifest)
    if tuple(sorted(report.selected_dimension_keys)) != dimensions:
        raise QuestionBankProjectionError("generic selected dimensions disagree")
    anchors = _generic_source_anchors(report_payload, dimensions)
    report_view = _row_mapping(report)
    bank_view = _row_mapping(bank)
    projected: list[QuestionPair] = []
    presentations: dict[str, QuestionPairPresentation] = {}
    for pair in sorted(pairs, key=lambda row: row.id):
        if (
            pair.schema_version != _GENERIC_PAIR_SCHEMA
            or pair.question_bank_id != bank.id
            or pair.screening_report_id != report.id
            or pair.screening_report_digest != report.report_digest
            or pair.dimension_key not in dimensions
            or pair.magnitude_ppm not in _PAIR_MAGNITUDES
            or pair.pair_quality_ppm <= 0
        ):
            raise QuestionBankProjectionError("generic QuestionPair binding is invalid")
        _validate_canonical_row(pair, _GENERIC_PAIR_SCHEMA, R2_PAIR_FIELDS)
        try:
            generic_screening.validate_question_pair_row(
                _row_mapping(pair), report=report_view, bank=bank_view
            )
        except GenericAdmissionError as exc:
            raise QuestionBankProjectionError("generic QuestionPair authority is invalid") from exc
        source_anchor = anchors.get(pair.demo_synthetic_identity_id)
        if source_anchor is None:
            raise QuestionBankProjectionError("generic QuestionPair source anchor is invalid")
        projected_pair = QuestionPair(
            pair.id,
            pair.dimension_key,
            pair.magnitude_ppm,
            pair.demo_synthetic_identity_id,
            MappingProxyType(dict(source_anchor)),
            _fisher(pair.magnitude_ppm),
            pair.pair_quality_ppm,
        )
        projected.append(projected_pair)
        qa = cast(Mapping[str, Any], pair.qa_payload)
        wrapper = cast(Mapping[str, Any], qa["pair_screening_record_payload"])
        record = cast(Mapping[str, Any], wrapper["pair_screening_record_payload"])
        left = cast(Mapping[str, Any], record["left"])
        right = cast(Mapping[str, Any], record["right"])
        presentations[pair.id] = QuestionPairPresentation(
            question_pair_digest=pair.content_digest,
            source_asset_id=pair.source_asset_id,
            source_checksum=pair.source_asset_sha256,
            left=QuestionSidePresentation(
                result_asset_id=pair.left_asset_id,
                result_checksum=pair.left_asset_sha256,
                result_lineage_digest=cast(str, left["lineage_digest"]),
                requested_direction=_generic_direction(left.get("requested_direction")),
                measured_delta_ppm=pair.left_delta_ppm,
            ),
            right=QuestionSidePresentation(
                result_asset_id=pair.right_asset_id,
                result_checksum=pair.right_asset_sha256,
                result_lineage_digest=cast(str, right["lineage_digest"]),
                requested_direction=_generic_direction(right.get("requested_direction")),
                measured_delta_ppm=pair.right_delta_ppm,
            ),
        )
    expected_slots = {
        (source_id, dimension, magnitude)
        for source_id in anchors
        for dimension in dimensions
        for magnitude in _PAIR_MAGNITUDES
    }
    if {
        (pair.source_identity_id, pair.dimension_id, pair.magnitude_ppm) for pair in projected
    } != expected_slots:
        raise QuestionBankProjectionError("generic QuestionPair coverage is invalid")
    return _finalize_projection(
        admission, bank, report, projected, presentations, dimensions, anchors
    )


def _generic_report_payload(report: DemoPairScreeningReport) -> Mapping[str, Any]:
    payload = report.report_payload
    if not isinstance(payload, Mapping) or report.report_digest != mirror_demo_digest(
        _GENERIC_REPORT_SCHEMA, cast(Mapping[str, JsonValue], payload)
    ):
        raise QuestionBankProjectionError("generic Report payload does not replay")
    return cast(Mapping[str, Any], payload)


def _generic_source_binding(
    payload: Mapping[str, Any], admission: DemoD02R2Epoch2Admission
) -> Mapping[str, Any]:
    binding = payload.get("selected_source_manifest_binding")
    if (
        not isinstance(binding, Mapping)
        or binding.get("schema_version") != generic_screening.SELECTED_SOURCE_BINDING_SCHEMA
        or binding.get("selected_source_manifest_id") != admission.selected_source_manifest_id
        or binding.get("formal_source_manifest_digest") != admission.source_manifest_digest
        or binding.get("source_count") != 4
    ):
        raise QuestionBankProjectionError("generic selected source binding is invalid")
    digest_payload = {
        key: binding.get(key)
        for key in (
            "selected_source_manifest_id",
            "selected_source_manifest_digest",
            "formal_source_manifest_digest",
            "source_count",
        )
    }
    if binding.get("binding_digest") != mirror_demo_digest(
        generic_screening.SELECTED_SOURCE_BINDING_SCHEMA,
        cast(Mapping[str, JsonValue], digest_payload),
    ):
        raise QuestionBankProjectionError("generic selected source binding does not replay")
    return cast(Mapping[str, Any], binding)


def _generic_dimensions(value: object) -> tuple[str, str]:
    if (
        not isinstance(value, Mapping)
        or value.get("schema_version") != generic_screening.DIMENSION_MANIFEST_SCHEMA
    ):
        raise QuestionBankProjectionError("generic dimension manifest is invalid")
    rows = value.get("selected_dimensions")
    if not isinstance(rows, list) or len(rows) != 2:
        raise QuestionBankProjectionError("generic dimension manifest is invalid")
    dimensions = tuple(
        cast(str, row.get("dimension_key")) for row in rows if isinstance(row, Mapping)
    )
    if tuple(sorted(dimensions)) != _GENERIC_DIMENSIONS:
        raise QuestionBankProjectionError("generic dimensions are unsupported")
    return cast(tuple[str, str], tuple(sorted(dimensions)))


def _generic_source_anchors(
    payload: Mapping[str, Any], dimensions: Sequence[str]
) -> dict[str, dict[str, int]]:
    rows = payload.get("ordered_source_manifest")
    if not isinstance(rows, list) or len(rows) != 4:
        raise QuestionBankProjectionError("generic formal source manifest is invalid")
    anchors: dict[str, dict[str, int]] = {}
    for ordinal, raw in enumerate(rows, start=1):
        if not isinstance(raw, Mapping):
            raise QuestionBankProjectionError("generic formal source entry is invalid")
        source = cast(Mapping[str, Any], raw)
        projection = source.get("source_measurement_projection")
        identity = source.get("source_admission_event_id")
        if (
            source.get("schema_version") != _GENERIC_SOURCE_ENTRY_SCHEMA
            or source.get("source_ordinal") != ordinal
            or not isinstance(identity, str)
            or identity in anchors
            or not isinstance(projection, Mapping)
            or source.get("source_measurement_digest")
            != mirror_demo_digest(
                _GENERIC_SOURCE_MEASUREMENT_SCHEMA, cast(Mapping[str, JsonValue], projection)
            )
            or source.get("source_measurement_projection_digest")
            != mirror_demo_digest(
                _GENERIC_SOURCE_PROJECTION_SCHEMA, cast(Mapping[str, JsonValue], projection)
            )
            or source.get("record_digest")
            != mirror_demo_digest(
                _GENERIC_SOURCE_ENTRY_SCHEMA,
                cast(
                    Mapping[str, JsonValue],
                    {
                        key: value
                        for key, value in source.items()
                        if key not in {"schema_version", "record_digest"}
                    },
                ),
            )
        ):
            raise QuestionBankProjectionError("generic source measurement authority is invalid")
        nested_projection = projection.get("projection")
        entries = (
            nested_projection.get("ordered_entries")
            if isinstance(nested_projection, Mapping)
            else None
        )
        if not isinstance(entries, list) or len(entries) != 6:
            raise QuestionBankProjectionError("generic source measurement projection is invalid")
        values: dict[str, int] = {}
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise QuestionBankProjectionError("generic source measurement entry is invalid")
            dimension = entry.get("dimension_key")
            if (
                not isinstance(dimension, str)
                or dimension in values
                or entry.get("support_state") != "SUPPORTED"
                or entry.get("unit") != "FACE_HEIGHT_PPM"
                or type(entry.get("value_ppm")) is not int
                or type(entry.get("reliability_ppm")) is not int
                or type(entry.get("confidence_ppm")) is not int
                or cast(int, entry["reliability_ppm"]) <= 0
                or cast(int, entry["confidence_ppm"]) <= 0
                or entry.get("unsupported_reason") is not None
            ):
                raise QuestionBankProjectionError("generic source measurement entry is invalid")
            values[dimension] = cast(int, entry["value_ppm"])
        if not set(dimensions).issubset(values):
            raise QuestionBankProjectionError("generic source lacks selected measurement")
        anchors[identity] = {dimension: values[dimension] for dimension in dimensions}
    return anchors


def _generic_direction(value: object) -> str:
    if value == "DECREASE":
        return "NEGATIVE"
    if value == "INCREASE":
        return "POSITIVE"
    raise QuestionBankProjectionError("generic pair direction is invalid")


def _row_mapping(row: object) -> Mapping[str, object]:
    values = getattr(row, "__dict__", None)
    if not isinstance(values, Mapping):
        raise QuestionBankProjectionError("generic authority row cannot be replayed")
    return {key: value for key, value in values.items() if not key.startswith("_")}


def _finalize_projection(
    admission: DemoD02R2Epoch2Admission,
    bank: DemoQuestionBank,
    report: DemoPairScreeningReport,
    projected: Sequence[QuestionPair],
    presentations: Mapping[str, QuestionPairPresentation],
    dimensions: Sequence[str],
    anchors: Mapping[str, Mapping[str, int]],
) -> AdmittedQuestionBank:
    scales = {
        dimension: _mad_scale([anchor[dimension] for anchor in anchors.values()])
        for dimension in dimensions
    }
    config_payload: dict[str, object] = {
        "scale_algorithm_version": _SCALE_VERSION,
        "scale_floor_ppm": _SCALE_FLOOR,
        "scale_multiplier_ppm": _SCALE_MULTIPLIER_PPM,
        "fisher_algorithm_version": _FISHER_VERSION,
        "posterior_tau_ppm": _POSTERIOR_TAU_PPM,
        "fisher_evaluation_delta_ppm": 0,
        "max_magnitude_ppm": _MAX_MAGNITUDE,
        "questionnaire_runtime_generation_calls": 0,
        "bank_algorithm_config_digest": bank.algorithm_config_digest,
        "bank_routing_version": bank.routing_version,
        "bank_stopping_version": bank.stopping_version,
        "bank_neighborhood_version": bank.neighborhood_version,
    }
    config_digest = mirror_demo_digest(
        PROJECTION_CONFIG_SCHEMA, cast(Mapping[str, JsonValue], config_payload)
    )
    projection_payload: dict[str, object] = {
        "config": config_payload,
        "config_digest": config_digest,
        "admission_id": admission.id,
        "admission_content_digest": admission.content_digest,
        "bank_id": bank.id,
        "bank_content_digest": bank.content_digest,
        "report_id": report.id,
        "report_digest": report.report_digest,
        "report_content_digest": report.content_digest,
        "dimensions": list(dimensions),
        "scales": dict(sorted(scales.items())),
        "pairs": [
            {
                "pair_id": pair.pair_id,
                "question_pair_digest": presentations[pair.pair_id].question_pair_digest,
                "dimension_id": pair.dimension_id,
                "source_identity_id": pair.source_identity_id,
                "source_asset_id": presentations[pair.pair_id].source_asset_id,
                "source_checksum": presentations[pair.pair_id].source_checksum,
                "magnitude_ppm": pair.magnitude_ppm,
                "morphology_anchor_ppm": dict(sorted(pair.morphology_anchor_ppm.items())),
                "expected_fisher_information_ppm": pair.expected_fisher_information_ppm,
                "pair_quality_ppm": pair.pair_quality_ppm,
                "left": {
                    "result_asset_id": presentations[pair.pair_id].left.result_asset_id,
                    "result_checksum": presentations[pair.pair_id].left.result_checksum,
                    "result_lineage_digest": presentations[pair.pair_id].left.result_lineage_digest,
                    "requested_direction": presentations[pair.pair_id].left.requested_direction,
                    "measured_delta_ppm": presentations[pair.pair_id].left.measured_delta_ppm,
                },
                "right": {
                    "result_asset_id": presentations[pair.pair_id].right.result_asset_id,
                    "result_checksum": presentations[pair.pair_id].right.result_checksum,
                    "result_lineage_digest": presentations[
                        pair.pair_id
                    ].right.result_lineage_digest,
                    "requested_direction": presentations[pair.pair_id].right.requested_direction,
                    "measured_delta_ppm": presentations[pair.pair_id].right.measured_delta_ppm,
                },
            }
            for pair in projected
        ],
    }
    digest = mirror_demo_digest(
        PROJECTION_SCHEMA, cast(Mapping[str, JsonValue], projection_payload)
    )
    return AdmittedQuestionBank(
        tuple(projected),
        MappingProxyType(dict(scales)),
        _SCALE_FLOOR,
        config_digest,
        digest,
        _freeze_mapping(projection_payload),
        MappingProxyType(dict(presentations)),
    )


def _dimensions(value: object) -> tuple[str, ...]:
    if (
        not isinstance(value, Mapping)
        or value.get("schema_version") != "mirror.demo/D02QuestionBankDimensionManifest/v2"
    ):
        raise QuestionBankProjectionError("dimension manifest is invalid")
    rows = value.get("selected_dimensions")
    if not isinstance(rows, list) or len(rows) != 2:
        raise QuestionBankProjectionError("exactly two selected dimensions are required")
    values = tuple(cast(str, row.get("dimension_key")) for row in rows if isinstance(row, Mapping))
    if len(values) != 2 or len(set(values)) != 2:
        raise QuestionBankProjectionError("selected dimensions are invalid")
    return tuple(sorted(values))


def _validate_canonical_row(row: object, schema_version: str, canonical_fields: set[str]) -> None:
    canonical = getattr(row, "canonical_payload", None)
    content_digest = getattr(row, "content_digest", None)
    if not isinstance(canonical, Mapping) or not isinstance(content_digest, str):
        raise QuestionBankProjectionError("authority canonical payload is missing")
    expected = {field: getattr(row, field) for field in canonical_fields if field != "created_at"}
    if (
        dict(canonical) != expected
        or mirror_demo_digest(schema_version, cast(Mapping[str, JsonValue], expected))
        != content_digest
    ):
        raise QuestionBankProjectionError("authority canonical payload does not replay")


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_mapping(cast(Mapping[str, object], value))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _source_anchors(payload: object, dimensions: Sequence[str]) -> dict[str, dict[str, int]]:
    if not isinstance(payload, Mapping):
        raise QuestionBankProjectionError("report payload is invalid")
    manifest_rows = payload.get("ordered_source_manifest")
    repeat_rows = payload.get("source_m3_repeat_evidence")
    if not isinstance(manifest_rows, list) or len(manifest_rows) != 4:
        raise QuestionBankProjectionError("source manifest is invalid")
    if not isinstance(repeat_rows, list) or len(repeat_rows) != 12:
        raise QuestionBankProjectionError("source repeat evidence is invalid")
    manifests: dict[str, Mapping[str, Any]] = {}
    result: dict[str, dict[str, int]] = {}
    for raw_manifest in manifest_rows:
        if not isinstance(raw_manifest, Mapping):
            raise QuestionBankProjectionError("source manifest entry is invalid")
        manifest = cast(Mapping[str, Any], raw_manifest)
        identity = manifest.get("source_admission_event_id")
        measurements = manifest.get("ordered_supported_measurements")
        if (
            not isinstance(identity, str)
            or not identity
            or identity in manifests
            or not isinstance(measurements, list)
        ):
            raise QuestionBankProjectionError("source manifest identity is invalid")
        values: dict[str, int] = {}
        for raw_measurement in measurements:
            if not isinstance(raw_measurement, Mapping):
                raise QuestionBankProjectionError("source measurement projection is invalid")
            measurement = cast(Mapping[str, Any], raw_measurement)
            dimension = measurement.get("dimension_key")
            if (
                measurement.get("schema_version") != "mirror.demo/D02SupportedSourceMeasurement/v1"
                or measurement.get("unit") != "FACE_HEIGHT_PPM"
                or not isinstance(dimension, str)
                or not dimension
                or dimension in values
                or type(measurement.get("value_ppm")) is not int
                or type(measurement.get("reliability_ppm")) is not int
                or type(measurement.get("confidence_ppm")) is not int
                or measurement["reliability_ppm"] <= 0
                or measurement["confidence_ppm"] <= 0
            ):
                raise QuestionBankProjectionError("source measurement projection is invalid")
            values[dimension] = cast(int, measurement["value_ppm"])
        manifests[identity] = manifest
        result[identity] = values

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in repeat_rows:
        if not isinstance(row, Mapping):
            raise QuestionBankProjectionError("source repeat record is invalid")
        identity = row.get("source_admission_event_id")
        if not isinstance(identity, str) or not identity:
            raise QuestionBankProjectionError("source repeat identity is invalid")
        grouped.setdefault(identity, []).append(cast(Mapping[str, Any], row))
    for identity, repeats in grouped.items():
        if (
            len(repeats) != 3
            or {item.get("repeat_index") for item in repeats} != {1, 2, 3}
            or any(
                item.get("face_count") != 1
                or item.get("landmark_count") != 478
                or item.get("repeat_gate_passed") is not True
                for item in repeats
            )
        ):
            raise QuestionBankProjectionError("source repeats are not admitted")
        obs = [item.get("measurement_observation") for item in repeats]
        digests = {item.get("measurement_observation_digest") for item in repeats}
        if (
            len(digests) != 1
            or any(value != obs[0] for value in obs[1:])
            or not isinstance(obs[0], Mapping)
        ):
            raise QuestionBankProjectionError("source repeats disagree")
        source_manifest = manifests.get(identity)
        if source_manifest is None or next(iter(digests)) != source_manifest.get(
            "source_measurement_digest"
        ):
            raise QuestionBankProjectionError("source repeat and manifest digests disagree")
        entries = obs[0].get("ordered_measurements")
        if not isinstance(entries, list):
            raise QuestionBankProjectionError("measurement observation is invalid")
        raw_by_dimension: dict[str, Mapping[str, Any]] = {}
        for raw_entry in entries:
            if not isinstance(raw_entry, Mapping):
                raise QuestionBankProjectionError("measurement observation entry is invalid")
            entry = cast(Mapping[str, Any], raw_entry)
            dimension = entry.get("dimension_key")
            if not isinstance(dimension, str) or not dimension or dimension in raw_by_dimension:
                raise QuestionBankProjectionError("measurement observation entry is invalid")
            raw_by_dimension[dimension] = entry
        for supported in cast(
            list[Mapping[str, Any]], source_manifest["ordered_supported_measurements"]
        ):
            raw = raw_by_dimension.get(cast(str, supported["dimension_key"]))
            if (
                raw is None
                or raw.get("support_state") != "SUPPORTED"
                or raw.get("raw_value_fixed18") != supported.get("raw_value_fixed18")
                or raw.get("raw_observability_fixed18") != supported.get("raw_confidence_fixed18")
            ):
                raise QuestionBankProjectionError("source measurement projection disagrees")
        for repeat in repeats:
            if any(
                repeat.get(key) != source_manifest.get(key)
                for key in (
                    "source_ordinal",
                    "source_admission_event_id",
                    "source_asset_id",
                    "source_asset_sha256",
                    "runtime_manifest_digest",
                    "vision_model_manifest_digest",
                    "topology_digest",
                )
            ):
                raise QuestionBankProjectionError("source repeat lineage disagrees")
    if len(result) != 4 or set(grouped) != set(manifests):
        raise QuestionBankProjectionError("four source observations are required")
    common_dimensions = set.intersection(*(set(values) for values in result.values()))
    if not set(dimensions).issubset(common_dimensions):
        raise QuestionBankProjectionError("source lacks selected measurement")
    return {
        identity: {key: values[key] for key in sorted(common_dimensions)}
        for identity, values in result.items()
    }


def _fisher(magnitude: int) -> int:
    if type(magnitude) is not int or not 0 < magnitude <= _MAX_MAGNITUDE:
        raise QuestionBankProjectionError("magnitude is invalid")
    return int(
        (
            Decimal(1_000_000)
            * Decimal(magnitude * magnitude)
            / Decimal(_MAX_MAGNITUDE * _MAX_MAGNITUDE)
        ).to_integral_value(rounding=ROUND_HALF_EVEN)
    )


def _mad_scale(values: Sequence[int]) -> int:
    if len(values) != 4 or any(type(value) is not int for value in values):
        raise QuestionBankProjectionError("four integer source values are required")
    ordered = sorted(values)
    median = (Decimal(ordered[1]) + Decimal(ordered[2])) / Decimal(2)
    deviations = sorted(abs(Decimal(value) - median) for value in values)
    mad = (deviations[1] + deviations[2]) / Decimal(2)
    scale = int(
        (mad * Decimal(_SCALE_MULTIPLIER_PPM) / Decimal(1_000_000)).to_integral_value(
            rounding=ROUND_HALF_EVEN
        )
    )
    return max(_SCALE_FLOOR, scale)
