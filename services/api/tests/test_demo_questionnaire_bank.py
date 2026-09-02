from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_demo_d02_generic_admission import _digest as _generic_digest
from test_demo_d02_generic_admission import _generic_screening_graph, _source
from test_demo_d02_r2_epoch2_admission import _bundle, _database, _digest

from mirror_api import demo_d02_generic_admission as generic
from mirror_api.demo_d02_r2_epoch2_admission import D02R2Epoch2AdmissionCoordinator
from mirror_api.demo_measurement_quality import mirror_demo_digest
from mirror_api.demo_questionnaire_bank import (
    PROJECTION_SCHEMA,
    QuestionBankProjectionError,
    _fisher,
    _generic_source_anchors,
    _mad_scale,
    load_admitted_question_bank,
    project_admitted_question_bank,
)

_ADMISSION_SCHEMA = "mirror.demo/D02R2Epoch2Admission/v1"


def _graph() -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace, list[SimpleNamespace]]:
    bundle = _bundle()
    report = SimpleNamespace(**deepcopy(dict(bundle.report_row)))
    bank = SimpleNamespace(**deepcopy(dict(bundle.question_bank_row)))
    pairs = [SimpleNamespace(**deepcopy(dict(row))) for row in bundle.question_pair_rows]
    canonical: dict[str, object] = {
        "idempotency_key_hash": _digest("d04b-projection-idempotency"),
        "request_digest": _digest("d04b-projection-request"),
        "execution_epoch": "D02_R2_EPOCH_02",
        "evidence_root_id": "P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT",
        "source_manifest_digest": report.source_manifest_digest,
        "screening_report_id": report.id,
        "screening_report_digest": report.report_digest,
        "question_bank_id": bank.id,
        "question_bank_content_digest": bank.content_digest,
        "question_bank_version": bank.version,
        "selected_pair_manifest_digest": report.selected_pair_manifest_digest,
        "source_authority_count": 4,
        "synthetic_identity_count": 4,
        "question_pair_count": 16,
        "selected_result_side_count": 32,
        "admission_state": "COMPLETED",
    }
    admission = SimpleNamespace(
        id="a" * 32,
        schema_version=_ADMISSION_SCHEMA,
        canonical_payload=canonical,
        content_digest=mirror_demo_digest(_ADMISSION_SCHEMA, canonical),
        **canonical,
    )
    return admission, bank, report, pairs


def _generic_graph() -> tuple[
    SimpleNamespace, SimpleNamespace, SimpleNamespace, list[SimpleNamespace]
]:
    inputs: list[generic.GenericSourceInput] = []
    source_rows: list[dict[str, object]] = []
    identity_rows: list[dict[str, object]] = []
    candidate_ids = tuple(char * 32 for char in "abcd")
    dimensions = (
        "eye_spacing",
        "jaw_width",
        "nose_width",
        "mouth_width",
        "face_width",
        "chin_height",
    )
    for position, char in enumerate("abcd", start=1):
        entries = [
            {
                "dimension_key": dimension,
                "support_state": "SUPPORTED",
                "unit": "FACE_HEIGHT_PPM",
                "unsupported_reason": None,
                "value_ppm": position * 10_000 + ordinal,
                "reliability_ppm": 900_000,
                "confidence_ppm": 800_000,
            }
            for ordinal, dimension in enumerate(dimensions, start=1)
        ]
        value = replace(
            _source(),
            candidate_id=char * 32,
            manifest_ordered_candidate_ids=cast(tuple[str, str, str, str], candidate_ids),
            position=position,
            source_output_id=f"generic-source-{position}",
            normalized_asset=generic.NormalizedAsset(
                asset_id=str(position) * 32,
                sha256=_generic_digest(f"generic-source-{position}"),
                byte_size=100 + position,
                width=64,
                height=64,
            ),
            formal_source_qa_digest=_generic_digest(f"formal-qa-{position}"),
            formal_landmark_digest=_generic_digest(f"landmark-{position}"),
            formal_measurement_projection={"ordered_entries": entries},
        )
        source = generic.build_source_authority(value)
        inputs.append(value)
        source_rows.append(source)
        identity_rows.append(generic.build_identity_row(value, source_row=source))
    manifest = SimpleNamespace(id="a" * 32, content_digest=_generic_digest("generic-manifest"))
    report_row, bank_row, pair_rows, _, _ = _generic_screening_graph(
        inputs, source_rows, identity_rows, manifest
    )
    admission_row = generic.build_generic_admission(
        idempotency_key_hash=_generic_digest("generic-admission-key"),
        request_payload={"policy_digest": _generic_digest("generic-policy")},
        selected_source_manifest_id=manifest.id,
        selected_source_manifest_digest=manifest.content_digest,
        formal_source_manifest_digest=cast(str, report_row["source_manifest_digest"]),
        screening_report_id=cast(str, report_row["id"]),
        screening_report_digest=cast(str, report_row["report_digest"]),
        question_bank_id=cast(str, bank_row["id"]),
        question_bank_content_digest=cast(str, bank_row["content_digest"]),
        question_bank_version=cast(str, bank_row["version"]),
        selected_pair_manifest_digest=cast(str, report_row["selected_pair_manifest_digest"]),
    )
    return (
        SimpleNamespace(**admission_row),
        SimpleNamespace(**bank_row),
        SimpleNamespace(**report_row),
        [SimpleNamespace(**row) for row in pair_rows],
    )


def test_projects_real_r2_authority_deterministically() -> None:
    admission, bank, report, pairs = _graph()

    first = project_admitted_question_bank(admission, bank, report, pairs)
    second = project_admitted_question_bank(admission, bank, report, list(reversed(pairs)))

    assert len(first.pairs) == 16
    assert len({pair.source_identity_id for pair in first.pairs}) == 4
    assert len({pair.dimension_id for pair in first.pairs}) == 2
    assert first.projection_digest == second.projection_digest
    assert first.canonical_payload == second.canonical_payload
    assert first.projection_digest == mirror_demo_digest(PROJECTION_SCHEMA, first.canonical_payload)
    assert set(report.selected_dimension_keys).issubset(first.morphology_scale_ppm)
    assert {pair.expected_fisher_information_ppm for pair in first.pairs} == {
        250_000,
        1_000_000,
    }
    with pytest.raises(TypeError):
        cast(Any, first.morphology_scale_ppm)["jaw_width"] = 0


def test_fixed_point_scale_and_fisher_rules() -> None:
    assert _fisher(15_000) == 250_000
    assert _fisher(30_000) == 1_000_000
    assert _mad_scale([10_000, 10_000, 10_000, 10_000]) == 1_000
    assert _mad_scale([0, 10_000, 20_000, 30_000]) == 14_826


def test_extracts_generic_public_projection_anchors() -> None:
    _, _, report, _ = _generic_graph()
    anchors = _generic_source_anchors(report.report_payload, ("eye_spacing", "jaw_width"))

    assert len(anchors) == 4
    assert {tuple(values) for values in anchors.values()} == {("eye_spacing", "jaw_width")}
    assert {values["eye_spacing"] % 10_000 for values in anchors.values()} == {1}


def test_generic_public_projection_fails_closed_for_tampering() -> None:
    _, _, report, _ = _generic_graph()
    report.report_payload["ordered_source_manifest"][0]["source_measurement_projection"][
        "projection"
    ]["ordered_entries"][0]["value_ppm"] = 1
    with pytest.raises(QuestionBankProjectionError):
        _generic_source_anchors(report.report_payload, ("eye_spacing", "jaw_width"))


@pytest.mark.parametrize(
    "mutation",
    ["repeat", "support", "pair", "screening_digest", "report_status"],
)
def test_projection_fails_closed_for_invalid_authority(mutation: str) -> None:
    admission, bank, report, pairs = _graph()
    if mutation == "repeat":
        report.report_payload["source_m3_repeat_evidence"][0]["face_count"] = 2
    elif mutation == "support":
        report.report_payload["ordered_source_manifest"][0]["ordered_supported_measurements"][0][
            "reliability_ppm"
        ] = 0
    elif mutation == "pair":
        pairs.pop()
    elif mutation == "screening_digest":
        pairs[0].screening_report_digest = _digest("wrong-report")
    else:
        report.status = "FAILED"
    with pytest.raises(QuestionBankProjectionError):
        project_admitted_question_bank(admission, bank, report, pairs)


@pytest.mark.asyncio
async def test_loads_complete_bank_from_real_postgresql_without_writes() -> None:
    bundle = _bundle()
    async with _database() as sessions:
        coordinator = D02R2Epoch2AdmissionCoordinator(session_factory=sessions)
        await coordinator.admit(
            idempotency_key=_digest("d04b-real-postgresql-admission"),
            bundle=bundle,
        )
        async with sessions() as session:
            projected = await load_admitted_question_bank(
                session, cast(str, bundle.question_bank_row["id"])
            )
            assert len(projected.pairs) == 16
            assert not session.new
            assert not session.dirty
            assert not session.deleted
