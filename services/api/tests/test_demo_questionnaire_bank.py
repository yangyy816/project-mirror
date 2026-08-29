from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_demo_d02_r2_epoch2_admission import _bundle, _database, _digest

from mirror_api.demo_d02_r2_epoch2_admission import D02R2Epoch2AdmissionCoordinator
from mirror_api.demo_measurement_quality import mirror_demo_digest
from mirror_api.demo_questionnaire_bank import (
    PROJECTION_SCHEMA,
    QuestionBankProjectionError,
    _fisher,
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
