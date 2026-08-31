from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_d02_r2_authority import _report_input_template
from test_demo_d02_source_acquisition import _accept_candidate, _service

from mirror_api import demo_d02_generic_admission as generic
from mirror_api import demo_d02_generic_admission_coordinator as coordinator
from mirror_api import demo_d02_generic_screening as screening
from mirror_api import demo_d02_r2_authority as r2
from mirror_api.demo_measurement_quality import mirror_demo_digest
from mirror_api.demo_models import (
    D02CohortSpec,
    D02SelectedSourceManifest,
    D02SourceAcquisitionEvent,
    D02SourceAcquisitionRun,
    D02SourceCandidate,
    DemoD02R2Epoch2Admission,
    DemoD02R2SourceAuthority,
    DemoPairScreeningReport,
    DemoQuestionBank,
    DemoQuestionPair,
    DemoSyntheticIdentity,
)
from mirror_api.models import Asset, AssetVariant, new_id


def _digest(seed: str) -> str:
    return (seed.encode().hex() * 64)[:64]


def _source() -> generic.GenericSourceInput:
    return generic.GenericSourceInput(
        acquisition_run_id="d" * 32,
        cohort_spec_id="e" * 32,
        manifest_id="a" * 32,
        manifest_acquisition_run_id="d" * 32,
        manifest_cohort_spec_id="e" * 32,
        manifest_content_digest=_digest("manifest"),
        manifest_ordered_candidate_ids=("b" * 32, "f" * 32, "1" * 32, "2" * 32),
        candidate_id="b" * 32,
        candidate_acquisition_run_id="d" * 32,
        candidate_cohort_spec_id="e" * 32,
        candidate_content_digest=_digest("candidate"),
        position=1,
        spec_content_digest=_digest("spec"),
        generation_policy_digest=_digest("policy"),
        source_output_id="source-1",
        normalized_asset=generic.NormalizedAsset(
            asset_id="c" * 32,
            sha256=_digest("asset"),
            byte_size=100,
            width=64,
            height=64,
        ),
        formal_source_qa_digest=_digest("formal-qa"),
        candidate_m3_evidence_digest=_digest("candidate-m3"),
        candidate_qa_evidence_digest=_digest("candidate-qa"),
        formal_facts={
            "subject": "source-1",
            "source_p2_candidate_manifest_content_digest": _digest("source-p2"),
            "dimension_authority_manifest_content_digest": _digest("dimension-authority"),
        },
        formal_measurement_projection={"landmark_count": 1},
        formal_landmark_digest=_digest("landmark"),
    )


def test_source_and_identity_are_deterministic_and_generic() -> None:
    value = _source()
    source = generic.build_source_authority(value)
    assert source["schema_version"] == generic.SOURCE_SCHEMA
    assert source["execution_epoch"] == "D02_AUTONOMOUS_V1"
    assert source["source_asset_mime_type"] == "image/jpeg"
    assert "source_generation_receipt_digest" not in source
    assert "source_authority_kind" not in source["canonical_payload"]
    identity = generic.build_identity_row(value, source_row=source)
    assert identity["schema_version"] == generic.IDENTITY_SCHEMA
    assert identity["source_receipt_digest"] is None
    assert (
        identity["content_digest"]
        == generic.build_identity_row(value, source_row=source)["content_digest"]
    )


def test_provisional_qa_digest_cannot_be_formal() -> None:
    value = _source()
    with pytest.raises(generic.GenericAdmissionError):
        generic.build_source_authority(
            replace(value, formal_source_qa_digest=value.candidate_m3_evidence_digest)
        )


def test_manifest_position_and_non_jpeg_fail_closed() -> None:
    value = _source()
    with pytest.raises(generic.GenericAdmissionError):
        generic.build_source_provenance(replace(value, position=5))
    with pytest.raises(generic.GenericAdmissionError):
        generic.NormalizedAsset("c" * 32, _digest("a"), 1, 64, 64, "image/png")
    with pytest.raises(generic.GenericAdmissionError, match="run, and spec"):
        generic.build_source_provenance(replace(value, candidate_acquisition_run_id="9" * 32))
    with pytest.raises(generic.GenericAdmissionError, match="Manifest position"):
        generic.build_source_provenance(
            replace(
                value,
                manifest_ordered_candidate_ids=("f" * 32, "b" * 32, "1" * 32, "2" * 32),
            )
        )


def test_admission_has_fixed_cardinality_and_replays() -> None:
    kwargs = dict(
        idempotency_key_hash=_digest("key"),
        request_payload={"policy_digest": _digest("policy")},
        selected_source_manifest_id="a" * 32,
        selected_source_manifest_digest=_digest("selected-manifest"),
        formal_source_manifest_digest=_digest("formal-manifest"),
        screening_report_id="b" * 32,
        screening_report_digest=_digest("report"),
        question_bank_id="c" * 32,
        question_bank_content_digest=_digest("bank"),
        question_bank_version="v1",
        selected_pair_manifest_digest=_digest("pairs"),
    )
    first = generic.build_generic_admission(**kwargs)
    second = generic.build_generic_admission(**kwargs)
    assert first == second
    assert first["execution_epoch"] == "D02_AUTONOMOUS_V1"
    assert first["source_authority_count"] == 4
    assert first["synthetic_identity_count"] == 4
    assert first["question_pair_count"] == 16
    assert first["selected_result_side_count"] == 32
    assert first["source_manifest_digest"] == _digest("formal-manifest")
    assert (
        first["request_digest"]
        != generic.build_generic_admission(
            **{**kwargs, "selected_source_manifest_digest": _digest("other-selected-manifest")}
        )["request_digest"]
    )
    assert first["evidence_root_id"] is None
    assert "evidence_root_id" not in first["canonical_payload"]


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy() -> Any:
    if os.name == "nt":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def session() -> Session:
    database_url = pytest.importorskip("os").environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    db_session = Session(engine, expire_on_commit=False)
    db_session.execute(
        text(
            "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, demo_question_pairs, "
            "demo_question_banks, demo_pair_screening_reports, asset_variants, "
            "demo_synthetic_identities, demo_d02_r2_source_authorities, "
            "demo_d02_selected_source_manifests, "
            "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
            "demo_d02_source_acquisition_runs, demo_d02_cohort_specs, assets CASCADE"
        )
    )
    db_session.commit()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.execute(
            text(
                "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, demo_question_pairs, "
                "demo_question_banks, demo_pair_screening_reports, asset_variants, "
                "demo_synthetic_identities, demo_d02_r2_source_authorities, "
                "demo_d02_selected_source_manifests, "
                "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
                "demo_d02_source_acquisition_runs, demo_d02_cohort_specs, assets CASCADE"
            )
        )
        db_session.commit()
        db_session.close()
        engine.dispose()


def _generic_sources(
    session: Session, tmp_path: Path
) -> tuple[D02SelectedSourceManifest, list[generic.GenericSourceInput], list[dict[str, object]]]:
    service, run_id = _service(session, "generic-pg")
    manifest: D02SelectedSourceManifest | None = None
    for marker in range(1, 5):
        manifest = _accept_candidate(service=service, run_id=run_id, parent=tmp_path, marker=marker)
    assert manifest is not None
    candidates = list(
        session.scalars(
            select(D02SourceCandidate)
            .where(D02SourceCandidate.acquisition_run_id == run_id)
            .order_by(D02SourceCandidate.provider_ordinal)
        )
    )
    assert len(candidates) == 4
    ordered_ids = tuple(cast(str, item) for item in manifest.ordered_candidate_ids)
    assert len(ordered_ids) == 4
    run = session.get(D02SourceAcquisitionRun, run_id)
    assert run is not None
    spec = session.get(D02CohortSpec, run.cohort_spec_id)
    assert spec is not None
    inputs: list[generic.GenericSourceInput] = []
    rows: list[dict[str, object]] = []
    for position, candidate in enumerate(candidates, start=1):
        asset = Asset(
            id=new_id(),
            owner_user_id=None,
            asset_role="synthetic",
            internal_purpose="synthetic_dataset",
            storage_key=f"d02-generic-pg/{position}",
            mime_type="image/jpeg",
            byte_size=100 + position,
            width=64,
            height=64,
            sha256=_digest(f"generic-asset-{position}"),
            synthetic=True,
            is_ai_generated=True,
            is_ai_modified=False,
        )
        session.add(asset)
        value = generic.GenericSourceInput(
            acquisition_run_id=run_id,
            cohort_spec_id=manifest.cohort_spec_id,
            manifest_id=manifest.id,
            manifest_acquisition_run_id=manifest.acquisition_run_id,
            manifest_cohort_spec_id=manifest.cohort_spec_id,
            manifest_content_digest=manifest.content_digest,
            manifest_ordered_candidate_ids=cast(tuple[str, str, str, str], ordered_ids),
            candidate_id=candidate.id,
            candidate_acquisition_run_id=candidate.acquisition_run_id,
            candidate_cohort_spec_id=candidate.cohort_spec_id,
            candidate_content_digest=candidate.content_digest,
            position=position,
            spec_content_digest=spec.content_digest,
            generation_policy_digest=manifest.generation_policy_digest,
            source_output_id=candidate.output_id,
            normalized_asset=generic.NormalizedAsset(
                asset_id=asset.id,
                sha256=asset.sha256,
                byte_size=asset.byte_size,
                width=asset.width,
                height=asset.height,
            ),
            formal_source_qa_digest=_digest(f"formal-source-qa-{position}"),
            candidate_m3_evidence_digest=cast(str, candidate.m3_evidence_digest),
            candidate_qa_evidence_digest=cast(str, candidate.qa_evidence_digest),
            formal_facts={
                "fixture": f"source-{position}",
                "source_p2_candidate_manifest_content_digest": _digest(f"source-p2-{position}"),
                "dimension_authority_manifest_content_digest": _digest(
                    f"dimension-authority-{position}"
                ),
            },
            formal_measurement_projection={"fixture_measurement": position},
            formal_landmark_digest=_digest(f"formal-landmark-{position}"),
        )
        inputs.append(value)
        rows.append(generic.build_source_authority(value))
    session.flush()
    return manifest, inputs, rows


def test_generic_sources_and_identities_insert_with_trigger_parity(
    session: Session, tmp_path: Path
) -> None:
    _, inputs, source_rows = _generic_sources(session, tmp_path)
    for source in source_rows:
        session.add(DemoD02R2SourceAuthority(**source))
    session.commit()
    assert session.scalar(select(func.count()).select_from(DemoD02R2SourceAuthority)) == 4
    identities: list[DemoSyntheticIdentity] = []
    for value, source in zip(inputs, source_rows, strict=True):
        identity_row = generic.build_identity_row(value, source_row=source)
        identity_row.pop("source_authority_kind")
        identity_row.pop("source_authority_key")
        identity = DemoSyntheticIdentity(**identity_row)
        session.add(identity)
        identities.append(identity)
    session.commit()
    assert len(identities) == 4


def _resign(row: dict[str, object], schema: str, field: str = "record_digest") -> None:
    row[field] = mirror_demo_digest(
        schema, {key: value for key, value in row.items() if key not in {"schema_version", field}}
    )


def _generic_screening_graph(
    inputs: list[generic.GenericSourceInput],
    source_rows: list[dict[str, object]],
    identity_rows: list[dict[str, object]],
    manifest: D02SelectedSourceManifest,
) -> tuple[
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Rebind a deterministic, in-memory R2 graph to generic formal sources."""
    # The authority helper is cached for its own module; generic rebinding must
    # always start from a fresh graph because several runtime tests deliberately
    # mutate their local fixture copy.
    report_template, _ = _report_input_template.__wrapped__()
    source_entries, formal_digest = screening.build_formal_source_manifest(
        source_inputs=inputs,
        source_rows=source_rows,
        identity_rows=identity_rows,
        selected_source_manifest_id=manifest.id,
        selected_source_manifest_digest=manifest.content_digest,
    )
    source_by_ordinal = {entry["source_ordinal"]: entry for entry in source_entries}
    payload = deepcopy(cast(dict[str, object], report_template["report_payload"]))

    def bind_source(row: dict[str, object]) -> None:
        entry = source_by_ordinal[cast(int, row["source_ordinal"])]
        for key in (
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "source_asset_sha256",
            "r2_source_authority_record_id",
        ):
            if key in row:
                row[key] = entry[key]

    for case in cast(list[dict[str, object]], payload["ordered_case_manifest"]):
        bind_source(case)
        _resign(case, r2.R2_CASE_SCHEMA)
    for observation in cast(list[dict[str, object]], payload["source_m3_repeat_evidence"]):
        bind_source(observation)
        _resign(observation, r2.R2_SOURCE_M3_SCHEMA)
    pair_digest_rebindings: dict[str, str] = {}
    for wrapper in cast(list[dict[str, object]], payload["pair_quality_evidence"]):
        pair_payload = cast(dict[str, object], wrapper["pair_screening_record_payload"])
        bind_source(pair_payload)
        previous_digest = cast(str, wrapper["pair_screening_record_digest"])
        wrapper["pair_screening_record_digest"] = mirror_demo_digest(
            r2.R2_PAIR_SCREENING_SCHEMA, pair_payload
        )
        pair_digest_rebindings[previous_digest] = cast(str, wrapper["pair_screening_record_digest"])
        # The generic envelope requires an explicit fixture binding in addition
        # to the legacy three-field wrapper; the record digest remains bound to
        # the unchanged canonical pair payload.
        wrapper["fixture_binding"] = "generic-formal-source-v1"
    for selected in cast(list[dict[str, object]], payload["selected_pair_manifest"]):
        bind_source(selected)
        selected["pair_screening_record_digest"] = pair_digest_rebindings[
            cast(str, selected["pair_screening_record_digest"])
        ]
        _resign(selected, r2.R2_SELECTED_ENTRY_SCHEMA, "entry_digest")
    payload["ordered_source_manifest"] = source_entries
    payload["selected_source_manifest_binding"] = {
        "schema_version": screening.SELECTED_SOURCE_BINDING_SCHEMA,
        "selected_source_manifest_id": manifest.id,
        "selected_source_manifest_digest": manifest.content_digest,
        "formal_source_manifest_digest": formal_digest,
        "source_count": 4,
        "binding_digest": mirror_demo_digest(
            screening.SELECTED_SOURCE_BINDING_SCHEMA,
            {
                "selected_source_manifest_id": manifest.id,
                "selected_source_manifest_digest": manifest.content_digest,
                "formal_source_manifest_digest": formal_digest,
                "source_count": 4,
            },
        ),
    }
    asset_rows: list[dict[str, object]] = []
    asset_entries: list[dict[str, object]] = []
    for index, value in enumerate(inputs, start=1):
        asset = value.normalized_asset
        asset_rows.append(
            {
                "id": asset.asset_id,
                "owner_user_id": None,
                "asset_role": "synthetic",
                "storage_key": f"d02-generic-screening/source/{index}",
                "mime_type": asset.mime_type,
                "byte_size": asset.byte_size,
                "width": asset.width,
                "height": asset.height,
                "sha256": asset.sha256,
                "synthetic": True,
                "is_ai_generated": True,
                "is_ai_modified": False,
                "internal_purpose": "synthetic_dataset",
            }
        )
        asset_entries.append(
            screening.build_asset_manifest_entry(
                asset_id=asset.asset_id,
                sha256=asset.sha256,
                byte_size=asset.byte_size,
                mime_type=asset.mime_type,
                width=asset.width,
                height=asset.height,
                asset_kind="SOURCE",
                source_ordinal=index,
                case_ordinal=None,
            )
        )
    image_records = cast(
        list[dict[str, object]],
        cast(dict[str, object], payload["exact_duplicate_evidence"])["image_records"],
    )
    case_ordinal_by_id = {
        cast(str, case["case_id"]): index
        for index, case in enumerate(payload["ordered_case_manifest"], start=1)
    }
    for image in (item for item in image_records if item["authority_role"] == "RESULT"):
        case_ordinal = case_ordinal_by_id[cast(str, image["case_id"])]
        source_ordinal = cast(int, image["source_ordinal"])
        result = {
            "id": image["deterministic_result_asset_id"],
            "owner_user_id": None,
            "asset_role": "synthetic",
            "storage_key": f"d02-generic-screening/result/{case_ordinal}",
            "mime_type": image["mime_type"],
            "byte_size": image["byte_size"],
            "width": image["width"],
            "height": image["height"],
            "sha256": image["sha256"],
            "synthetic": True,
            "is_ai_generated": False,
            "is_ai_modified": True,
            "internal_purpose": "synthetic_dataset",
        }
        asset_rows.append(result)
        asset_entries.append(
            screening.build_asset_manifest_entry(
                asset_id=cast(str, result["id"]),
                sha256=cast(str, result["sha256"]),
                byte_size=cast(int, result["byte_size"]),
                mime_type=cast(str, result["mime_type"]),
                width=cast(int, result["width"]),
                height=cast(int, result["height"]),
                asset_kind="RESULT",
                source_ordinal=source_ordinal,
                case_ordinal=case_ordinal,
            )
        )
    variant_rows: list[dict[str, object]] = []
    variant_entries: list[dict[str, object]] = []
    for wrapper in cast(list[dict[str, object]], payload["pair_quality_evidence"]):
        pair_payload = cast(dict[str, object], wrapper["pair_screening_record_payload"])
        source_ordinal = cast(int, pair_payload["source_ordinal"])
        for side in ("left", "right"):
            side_payload = cast(dict[str, object], pair_payload[side])
            case_ordinal = next(
                index
                for index, case in enumerate(payload["ordered_case_manifest"], start=1)
                if cast(dict[str, object], case)["case_id"] == side_payload["case_id"]
            )
            variant = {
                "id": side_payload["asset_variant_id"],
                "source_asset_id": source_by_ordinal[source_ordinal]["source_asset_id"],
                "result_asset_id": side_payload["result_asset_id"],
                "variant_type": side_payload["asset_variant_type"],
                "created_at": "2026-08-31T00:00:00Z",
            }
            variant_rows.append(variant)
            variant_entries.append(
                screening.build_variant_manifest_entry(
                    variant_id=cast(str, variant["id"]),
                    source_asset_id=cast(str, variant["source_asset_id"]),
                    result_asset_id=cast(str, variant["result_asset_id"]),
                    source_ordinal=source_ordinal,
                    case_ordinal=case_ordinal,
                )
            )
    payload["asset_authority_manifest"] = asset_entries
    payload["asset_variant_manifest"] = variant_entries
    exact_duplicate = cast(dict[str, object], payload["exact_duplicate_evidence"])
    _resign(exact_duplicate, "mirror.demo/D02ExactDuplicateEvidence/v2")
    selected = cast(list[dict[str, object]], payload["selected_pair_manifest"])
    selected_digest = mirror_demo_digest(
        screening.SELECTED_PAIR_MANIFEST_SCHEMA, {"ordered_entries": selected}
    )
    report_fields = {
        key: deepcopy(value) for key, value in report_template.items() if key in r2.R2_REPORT_FIELDS
    }
    report_fields.update(
        report_payload=payload,
        source_manifest_digest=formal_digest,
        selected_pair_manifest_digest=selected_digest,
    )
    report = screening.build_report_row(
        report_fields,
        source_inputs=inputs,
        source_rows=source_rows,
        identity_rows=identity_rows,
        selected_source_manifest_id=manifest.id,
        selected_source_manifest_digest=manifest.content_digest,
    )
    selected_dimensions = cast(list[str], report["selected_dimension_keys"])
    dimension_manifest = {
        "schema_version": screening.DIMENSION_MANIFEST_SCHEMA,
        "screening_report_id": report["id"],
        "screening_report_digest": report["report_digest"],
        "selected_source_manifest_id": manifest.id,
        "selected_source_manifest_digest": manifest.content_digest,
        "formal_source_manifest_digest": formal_digest,
        "selected_pair_manifest_digest": selected_digest,
        "selected_dimensions": [
            {
                "dimension_key": dimension,
                "ordered_selected_pair_entry_digests": [
                    item["entry_digest"] for item in selected if item["dimension_key"] == dimension
                ],
            }
            for dimension in selected_dimensions
        ],
    }
    bank_fields = {
        "created_at": "2026-08-31T00:00:00Z",
        "version": "d02-generic-test-v1",
        "algorithm_config_digest": _digest("generic-bank-config"),
        "routing_version": "generic-routing-v1",
        "stopping_version": "generic-stopping-v1",
        "neighborhood_version": "generic-neighborhood-v1",
        "pair_manifest_digest": selected_digest,
        "dimension_manifest": dimension_manifest,
        "screening_report_id": report["id"],
        "screening_report_digest": report["report_digest"],
    }
    bank = screening.build_question_bank_row(
        bank_fields,
        report=report,
        selected_source_manifest_id=manifest.id,
        selected_source_manifest_digest=manifest.content_digest,
    )
    pair_rows: list[dict[str, object]] = []
    wrappers = cast(list[dict[str, object]], payload["pair_quality_evidence"])
    for selected_entry in selected:
        wrapper = next(
            item
            for item in wrappers
            if item["pair_screening_record_digest"]
            == selected_entry["pair_screening_record_digest"]
        )
        pair_payload = cast(dict[str, object], wrapper["pair_screening_record_payload"])
        source = source_by_ordinal[cast(int, pair_payload["source_ordinal"])]
        qa = {
            "schema_version": screening.PAIR_QA_SCHEMA,
            "screening_report_id": report["id"],
            "screening_report_digest": report["report_digest"],
            "selected_source_manifest_id": manifest.id,
            "selected_source_manifest_digest": manifest.content_digest,
            "formal_source_manifest_digest": formal_digest,
            "source_manifest_entry_schema_version": screening.SOURCE_ENTRY_SCHEMA,
            "source_manifest_entry_digest": source["record_digest"],
            "pair_screening_record_schema_version": r2.R2_PAIR_SCREENING_SCHEMA,
            "pair_screening_record_digest": wrapper["pair_screening_record_digest"],
            "pair_screening_record_payload": wrapper,
            "selected_pair_manifest_digest": selected_digest,
            "selected_pair_entry_schema_version": r2.R2_SELECTED_ENTRY_SCHEMA,
            "selected_pair_entry_digest": selected_entry["entry_digest"],
            "selected_pair_entry_payload": selected_entry,
        }
        left = cast(dict[str, object], pair_payload["left"])
        right = cast(dict[str, object], pair_payload["right"])
        pair_rows.append(
            screening.build_question_pair_row(
                {
                    "created_at": "2026-08-31T00:00:00Z",
                    "question_bank_id": bank["id"],
                    "demo_synthetic_identity_id": source["source_admission_event_id"],
                    "source_asset_id": source["source_asset_id"],
                    "source_asset_sha256": source["source_asset_sha256"],
                    "left_asset_id": left["result_asset_id"],
                    "left_asset_sha256": left["result_asset_sha256"],
                    "right_asset_id": right["result_asset_id"],
                    "right_asset_sha256": right["result_asset_sha256"],
                    "left_asset_variant_id": left["asset_variant_id"],
                    "right_asset_variant_id": right["asset_variant_id"],
                    "dimension_key": pair_payload["dimension_key"],
                    "magnitude_ppm": pair_payload["magnitude_ppm"],
                    "left_delta_ppm": left["measured_signed_delta_ppm"],
                    "right_delta_ppm": right["measured_signed_delta_ppm"],
                    "pair_quality_ppm": pair_payload["pair_quality_ppm"],
                    "qa_payload": qa,
                    "screening_report_id": report["id"],
                    "screening_report_digest": report["report_digest"],
                },
                report=report,
                bank=bank,
            )
        )
    screening.validate_complete_question_bank(report=report, bank=bank, pair_rows=pair_rows)
    return report, bank, pair_rows, asset_rows, variant_rows


def test_generic_screening_graph_replays_and_keeps_selected_and_formal_digests_distinct() -> None:
    values: list[generic.GenericSourceInput] = []
    source_rows: list[dict[str, object]] = []
    identity_rows: list[dict[str, object]] = []
    candidate_ids = tuple(char * 32 for char in "abcd")
    for position, char in enumerate("abcd", start=1):
        value = replace(
            _source(),
            candidate_id=char * 32,
            manifest_ordered_candidate_ids=cast(tuple[str, str, str, str], candidate_ids),
            position=position,
            source_output_id=f"generic-source-{position}",
            normalized_asset=generic.NormalizedAsset(
                asset_id=str(position) * 32,
                sha256=_digest(f"generic-source-{position}"),
                byte_size=100 + position,
                width=64,
                height=64,
            ),
            formal_source_qa_digest=_digest(f"formal-qa-{position}"),
            formal_landmark_digest=_digest(f"landmark-{position}"),
        )
        source = generic.build_source_authority(value)
        values.append(value)
        source_rows.append(source)
        identity_rows.append(generic.build_identity_row(value, source_row=source))
    manifest = type("Manifest", (), {"id": "a" * 32, "content_digest": _digest("manifest")})()
    report, bank, pairs, assets, variants = _generic_screening_graph(
        values, source_rows, identity_rows, cast(D02SelectedSourceManifest, manifest)
    )
    assert len(assets) == 52
    assert len(variants) == 48
    assert len(pairs) == 16
    assert len({pair[key] for pair in pairs for key in ("left_asset_id", "right_asset_id")}) == 32
    assert report["source_manifest_digest"] != manifest.content_digest
    assert bank["pair_manifest_digest"] == report["selected_pair_manifest_digest"]
    screening.validate_report_row(
        report,
        source_inputs=values,
        source_rows=source_rows,
        identity_rows=identity_rows,
        selected_source_manifest_id=manifest.id,
        selected_source_manifest_digest=manifest.content_digest,
    )
    substituted = deepcopy(report)
    substituted["source_manifest_digest"] = manifest.content_digest
    with pytest.raises(generic.GenericAdmissionError, match="formal source manifest digest"):
        screening.validate_report_row(
            substituted,
            source_inputs=values,
            source_rows=source_rows,
            identity_rows=identity_rows,
            selected_source_manifest_id=manifest.id,
            selected_source_manifest_digest=manifest.content_digest,
        )
    tampered = deepcopy(report)
    asset_manifest = cast(
        list[dict[str, object]],
        cast(dict[str, object], tampered["report_payload"])["asset_authority_manifest"],
    )
    asset_manifest[0]["sha256"] = _digest("tampered-source-asset")
    with pytest.raises(generic.GenericAdmissionError, match="record digest does not replay"):
        screening.validate_report_row(
            tampered,
            source_inputs=values,
            source_rows=source_rows,
            identity_rows=identity_rows,
            selected_source_manifest_id=manifest.id,
            selected_source_manifest_digest=manifest.content_digest,
        )


def _selected_manifest_row(manifest: D02SelectedSourceManifest) -> dict[str, object]:
    return {
        "id": manifest.id,
        "schema_version": manifest.schema_version,
        "canonical_payload": manifest.canonical_payload,
        "content_digest": manifest.content_digest,
        "acquisition_run_id": manifest.acquisition_run_id,
        "cohort_spec_id": manifest.cohort_spec_id,
        "generation_policy_digest": manifest.generation_policy_digest,
        "ordered_candidate_ids": list(manifest.ordered_candidate_ids),
        "source_count": manifest.source_count,
        "manifest_state": manifest.manifest_state,
    }


def _generic_admission_bundle(
    session: Session, tmp_path: Path
) -> coordinator.GenericAdmissionBundle:
    manifest, inputs, source_rows = _generic_sources(session, tmp_path)
    identity_rows = [
        generic.build_identity_row(value, source_row=source)
        for value, source in zip(inputs, source_rows, strict=True)
    ]
    report, bank, pairs, assets, variants = _generic_screening_graph(
        inputs, source_rows, identity_rows, manifest
    )
    return coordinator.GenericAdmissionBundle(
        request_payload={
            "operation": "D02_GENERIC_ADMISSION",
            "policy_digest": _digest("generic-admission-policy"),
        },
        selected_manifest=_selected_manifest_row(manifest),
        source_inputs=tuple(inputs),
        source_rows=tuple(source_rows),
        identity_rows=tuple(identity_rows),
        asset_rows=tuple(assets),
        asset_variant_rows=tuple(variants),
        report_row=report,
        question_bank_row=bank,
        question_pair_rows=tuple(pairs),
    )


@asynccontextmanager
async def _async_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for the generic PostgreSQL gate")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield sessions
    finally:
        await engine.dispose()


async def _count(sessions: async_sessionmaker[AsyncSession], model: type[Any]) -> int:
    async with sessions() as async_session:
        value = await async_session.scalar(select(func.count()).select_from(model))
    assert isinstance(value, int)
    return value


@pytest.mark.asyncio
async def test_generic_atomic_admission_replay_conflict_and_cardinality(
    session: Session, tmp_path: Path
) -> None:
    bundle = _generic_admission_bundle(session, tmp_path)
    admission_key = "d02-generic-concurrent-winner"
    expected = coordinator.validate_generic_admission_bundle(
        idempotency_key=admission_key, bundle=bundle
    )
    session.commit()

    async with _async_sessions() as sessions:
        admission = coordinator.D02GenericAdmissionCoordinator(session_factory=sessions)
        first, replay = await asyncio.gather(
            admission.admit(idempotency_key=admission_key, bundle=bundle),
            admission.admit(idempotency_key=admission_key, bundle=bundle),
        )
        assert {first.replayed, replay.replayed} == {False, True}
        assert first.admission_id == replay.admission_id == expected["id"]
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 1
        assert await _count(sessions, DemoD02R2SourceAuthority) == 4
        assert await _count(sessions, DemoSyntheticIdentity) == 4
        assert await _count(sessions, DemoPairScreeningReport) == 1
        assert await _count(sessions, DemoQuestionBank) == 1
        assert await _count(sessions, DemoQuestionPair) == 16
        assert await _count(sessions, Asset) == 52
        assert await _count(sessions, AssetVariant) == 48

        async with sessions() as async_session:
            run = await async_session.get(
                D02SourceAcquisitionRun, bundle.selected_manifest["acquisition_run_id"]
            )
            assert run is not None
            assert run.run_state == "ADMITTED"
            assert run.budget_consumed == 4
            assert run.next_ordinal == 5
            call_count = await async_session.scalar(
                select(func.count())
                .select_from(D02SourceAcquisitionEvent)
                .where(
                    D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                    D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
                )
            )
            terminal_events = list(
                await async_session.scalars(
                    select(D02SourceAcquisitionEvent)
                    .where(
                        D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                        D02SourceAcquisitionEvent.event_kind.in_(
                            {"FORMAL_SOURCES_READY", "ADMISSION_COMPLETED"}
                        ),
                    )
                    .order_by(D02SourceAcquisitionEvent.event_sequence)
                )
            )
        assert call_count == 4
        assert [event.event_kind for event in terminal_events] == [
            "FORMAL_SOURCES_READY",
            "ADMISSION_COMPLETED",
        ]

        conflicting = replace(
            bundle,
            request_payload={
                **bundle.request_payload,
                "policy_digest": _digest("different-admission-policy"),
            },
        )
        with pytest.raises(coordinator.GenericPayloadConflict):
            await admission.admit(idempotency_key=admission_key, bundle=conflicting)
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 1


@pytest.mark.asyncio
async def test_generic_mid_transaction_failure_has_zero_partial_graph_rows(
    session: Session, tmp_path: Path
) -> None:
    bundle = _generic_admission_bundle(session, tmp_path)
    broken_assets = [dict(row) for row in bundle.asset_rows]
    broken_assets[5]["storage_key"] = broken_assets[4]["storage_key"]
    broken = replace(bundle, asset_rows=tuple(broken_assets))
    session.commit()

    async with _async_sessions() as sessions:
        admission = coordinator.D02GenericAdmissionCoordinator(session_factory=sessions)
        with pytest.raises(coordinator.GenericAuthorityCorruption):
            await admission.admit(idempotency_key="d02-generic-rollback", bundle=broken)
        assert await _count(sessions, DemoD02R2Epoch2Admission) == 0
        assert await _count(sessions, DemoD02R2SourceAuthority) == 0
        assert await _count(sessions, DemoSyntheticIdentity) == 0
        assert await _count(sessions, DemoPairScreeningReport) == 0
        assert await _count(sessions, DemoQuestionBank) == 0
        assert await _count(sessions, DemoQuestionPair) == 0
        assert await _count(sessions, AssetVariant) == 0
        # Four normalized source Assets predate admission; no result Asset survives.
        assert await _count(sessions, Asset) == 4
        async with sessions() as async_session:
            run = await async_session.get(
                D02SourceAcquisitionRun, bundle.selected_manifest["acquisition_run_id"]
            )
            assert run is not None
            assert run.run_state == "MANIFEST_FINALIZED"
            assert run.budget_consumed == 4
            assert run.next_ordinal == 5
            call_count = await async_session.scalar(
                select(func.count())
                .select_from(D02SourceAcquisitionEvent)
                .where(
                    D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                    D02SourceAcquisitionEvent.event_kind == "CALL_STARTED",
                )
            )
            terminal_count = await async_session.scalar(
                select(func.count())
                .select_from(D02SourceAcquisitionEvent)
                .where(
                    D02SourceAcquisitionEvent.acquisition_run_id == run.id,
                    D02SourceAcquisitionEvent.event_kind.in_(
                        {"FORMAL_SOURCES_READY", "ADMISSION_COMPLETED"}
                    ),
                )
            )
            assert call_count == 4
            assert terminal_count == 0
