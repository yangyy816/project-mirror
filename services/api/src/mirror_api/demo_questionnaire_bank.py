"""Read-only, fail-closed D02-R2 bank projection for the P4 scheduler."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from types import MappingProxyType
from typing import Any, Final, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    """Load the sole completed E2 admission graph without mutating the database."""
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
