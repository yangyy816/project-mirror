from __future__ import annotations

import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_demo_d02_r2_authority import (
    _R2_MANDATORY_DIGEST_ATTACK_CASES,
    _build_fully_resigned_mandatory_digest_attack,
    _packet,
    _report,
    _resign_legacy_typed,
    _resign_r2_image_record,
    _resign_r2_phash_matrix,
    _resign_r2_record,
    _resign_r2_report_envelope,
)
from test_demo_schema_authority_invariants import _truncate_demo_authority

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as r2
from mirror_api.config import get_settings
from mirror_api.demo_measurement_quality import mirror_demo_digest
from mirror_api.demo_models import (
    DemoD02R2SourceAuthority,
    DemoPairScreeningReport,
    DemoQuestionBank,
    DemoQuestionPair,
    DemoSyntheticIdentity,
)
from mirror_api.models import Asset, AssetVariant, new_id

_HEAD = "demo_0019_d06_stepped_transfer"
_DOWN = "demo_0007_d02_recovered_qa"
_R2_TOUCHED_TABLES = (
    "demo_synthetic_identities",
    "demo_pair_screening_reports",
    "demo_question_banks",
    "demo_question_pairs",
)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with Session(engine) as db_session:
        _truncate_demo_authority(db_session)
        yield db_session
        db_session.rollback()
        _truncate_demo_authority(db_session)
    engine.dispose()


def _persist_packet_asset(session: Session, packet: dict[str, object]) -> None:
    row = packet["supporting_row"]
    assert isinstance(row, dict)
    asset_id = row["source_asset_id"]
    assert isinstance(asset_id, str)
    existing = session.get(Asset, asset_id)
    if existing is not None:
        assert existing.sha256 == row["source_asset_sha256"]
        return
    session.add(
        Asset(
            id=asset_id,
            owner_user_id=None,
            asset_role="synthetic",
            internal_purpose="synthetic_dataset",
            storage_key=f"demo-r2-schema/{new_id()}",
            mime_type=row["source_asset_mime_type"],
            byte_size=row["source_asset_byte_size"],
            width=row["source_asset_width"],
            height=row["source_asset_height"],
            sha256=row["source_asset_sha256"],
            synthetic=True,
            is_ai_generated=True,
            is_ai_modified=False,
        )
    )
    session.commit()


def _persist_packet_supporting_row(
    session: Session, packet: dict[str, object]
) -> DemoD02R2SourceAuthority:
    _persist_packet_asset(session, packet)
    fields = dict(packet["supporting_row"])
    fields["created_at"] = datetime(2026, 8, 26, tzinfo=UTC)
    row = DemoD02R2SourceAuthority(**fields)
    session.add(row)
    session.commit()
    return row


def _supporting_row_values(packet: dict[str, object]) -> dict[str, object]:
    """Return a detached, database-ready supporting-row replay payload."""
    fields = dict(packet["supporting_row"])
    fields["created_at"] = datetime(2026, 8, 26, tzinfo=UTC)
    return fields


def _persist_packet_identity(session: Session, packet: dict[str, object]) -> DemoSyntheticIdentity:
    fields = dict(packet["identity_row"])
    fields["created_at"] = datetime(2026, 8, 26, tzinfo=UTC)
    fields.pop("source_authority_kind")
    fields.pop("source_authority_key")
    identity = DemoSyntheticIdentity(**fields)
    session.add(identity)
    session.commit()
    return identity


def _identity_values(identity_row: dict[str, Any]) -> dict[str, Any]:
    fields = deepcopy(identity_row)
    fields["created_at"] = datetime(2026, 8, 26, tzinfo=UTC)
    fields.pop("source_authority_kind")
    fields.pop("source_authority_key")
    return fields


def _resign_r2_identity_event(identity_row: dict[str, Any]) -> None:
    canonical = {
        key: value
        for key, value in identity_row.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    identity_row["canonical_payload"] = canonical
    identity_row["content_digest"] = mirror_demo_digest(r2.R2_IDENTITY_SCHEMA, canonical)
    identity_row["id"] = mirror_demo_digest(
        r2.R2_IDENTITY_ID_DOMAIN,
        {
            "source_authority_kind": identity_row["source_authority_kind"],
            "source_authority_key": identity_row["source_authority_key"],
            "r2_source_authority_record_id": identity_row["r2_source_authority_record_id"],
            "admission_sequence": identity_row["admission_sequence"],
            "admission_action": identity_row["admission_action"],
            "supersedes_id": identity_row["supersedes_id"],
            "admission_config_digest": identity_row["admission_config_digest"],
            "canonical_payload_digest": identity_row["content_digest"],
        },
    )[:32]


def _timestamp(value: object) -> datetime:
    assert isinstance(value, str)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _build_r2_bank_and_pairs(
    report: dict[str, object], packets: list[dict[str, object]]
) -> tuple[dict[str, object], list[dict[str, object]]]:
    payload = cast(dict[str, object], report["report_payload"])
    selected_entries = cast(list[dict[str, object]], payload["selected_pair_manifest"])
    dimension_records = cast(list[dict[str, object]], payload["dimension_eligibility"])
    source_entries = cast(list[dict[str, object]], payload["ordered_source_manifest"])
    pair_records = cast(list[dict[str, object]], payload["pair_quality_evidence"])
    selected_dimensions = cast(list[str], report["selected_dimension_keys"])
    first_source = source_entries[0]
    dimension_manifest = {
        "schema_version": r2.R2_DIMENSION_MANIFEST_SCHEMA,
        "screening_report_id": report["id"],
        "screening_report_digest": report["report_digest"],
        "source_manifest_digest": report["source_manifest_digest"],
        "source_p2_candidate_manifest_content_digest": first_source[
            "source_p2_candidate_manifest_content_digest"
        ],
        "dimension_authority_manifest_content_digest": first_source[
            "dimension_authority_manifest_content_digest"
        ],
        "selected_pair_manifest_digest": report["selected_pair_manifest_digest"],
        "selected_dimensions": [
            {
                "dimension_key": dimension_key,
                "priority_index": next(
                    item["priority_index"]
                    for item in dimension_records
                    if item["dimension_key"] == dimension_key
                ),
                "sixteen_side_gate_digest": next(
                    item["sixteen_side_gate_digest"]
                    for item in dimension_records
                    if item["dimension_key"] == dimension_key
                ),
                "eight_pair_gate_digest": next(
                    item["eight_pair_gate_digest"]
                    for item in dimension_records
                    if item["dimension_key"] == dimension_key
                ),
                "ordered_selected_pair_entry_digests": [
                    item["entry_digest"]
                    for item in selected_entries
                    if item["dimension_key"] == dimension_key
                ],
            }
            for dimension_key in selected_dimensions
        ],
    }
    bank = r2.build_r2_question_bank_row(
        {
            "created_at": "2026-08-26T00:00:00Z",
            "version": "d02-r2-v3",
            "algorithm_config_digest": mirror_demo_digest(
                "mirror.demo/TestOnlyR2AlgorithmConfig/v1", {"version": 1}
            ),
            "routing_version": "routing-v3",
            "stopping_version": "stopping-v3",
            "neighborhood_version": "neighborhood-v3",
            "pair_manifest_digest": report["selected_pair_manifest_digest"],
            "dimension_manifest": dimension_manifest,
            "screening_report_id": report["id"],
            "screening_report_digest": report["report_digest"],
        },
        report=report,
        source_packets=packets,
    )
    pairs: list[dict[str, object]] = []
    for selected in selected_entries:
        record = next(
            item
            for item in pair_records
            if item["pair_screening_record_digest"] == selected["pair_screening_record_digest"]
        )
        pair_payload = cast(dict[str, object], record["pair_screening_record_payload"])
        source = next(
            item
            for item in source_entries
            if item["source_admission_event_id"] == selected["source_admission_event_id"]
        )
        left = cast(dict[str, object], pair_payload["left"])
        right = cast(dict[str, object], pair_payload["right"])
        magnitude = cast(int, pair_payload["magnitude_ppm"])
        qa_payload = {
            "schema_version": r2.R2_PAIR_QA_SCHEMA,
            "screening_report_id": report["id"],
            "screening_report_digest": report["report_digest"],
            "source_manifest_digest": report["source_manifest_digest"],
            "source_manifest_entry_schema_version": source["schema_version"],
            "source_manifest_entry_digest": source["record_digest"],
            "pair_screening_record_schema_version": record["schema_version"],
            "pair_screening_record_digest": record["pair_screening_record_digest"],
            "pair_screening_record_payload": record,
            "selected_pair_manifest_digest": report["selected_pair_manifest_digest"],
            "selected_pair_entry_schema_version": selected["schema_version"],
            "selected_pair_entry_digest": selected["entry_digest"],
            "selected_pair_entry_payload": selected,
        }
        pairs.append(
            r2.build_r2_question_pair_row(
                {
                    "created_at": "2026-08-26T00:00:00Z",
                    "question_bank_id": bank["id"],
                    "demo_synthetic_identity_id": source["source_admission_event_id"],
                    "source_asset_id": pair_payload["source_asset_id"],
                    "source_asset_sha256": pair_payload["source_asset_sha256"],
                    "left_asset_id": left["result_asset_id"],
                    "left_asset_sha256": left["result_asset_sha256"],
                    "right_asset_id": right["result_asset_id"],
                    "right_asset_sha256": right["result_asset_sha256"],
                    "left_asset_variant_id": left["asset_variant_id"],
                    "right_asset_variant_id": right["asset_variant_id"],
                    "dimension_key": pair_payload["dimension_key"],
                    "magnitude_ppm": magnitude,
                    "left_delta_ppm": left["measured_signed_delta_ppm"],
                    "right_delta_ppm": right["measured_signed_delta_ppm"],
                    "pair_quality_ppm": pair_payload["pair_quality_ppm"],
                    "qa_payload": qa_payload,
                    "screening_report_id": report["id"],
                    "screening_report_digest": report["report_digest"],
                },
                report=report,
                bank=bank,
                source_packets=packets,
            )
        )
    return bank, pairs


def _persist_r2_report_prerequisites(
    session: Session, report: dict[str, object], packets: list[dict[str, object]]
) -> None:
    for packet in packets:
        _persist_packet_supporting_row(session, packet)
        _persist_packet_identity(session, packet)
    payload = cast(dict[str, object], report["report_payload"])
    exact = cast(dict[str, object], payload["exact_duplicate_evidence"])
    for image_record in cast(list[dict[str, object]], exact["image_records"]):
        if image_record["authority_role"] == "SOURCE":
            continue
        asset_id = cast(str, image_record["deterministic_result_asset_id"])
        if session.get(Asset, asset_id) is not None:
            continue
        session.add(
            Asset(
                id=asset_id,
                owner_user_id=None,
                asset_role="synthetic",
                internal_purpose="synthetic_dataset",
                storage_key=f"demo-r2-schema/result/{new_id()}",
                mime_type=image_record["mime_type"],
                byte_size=image_record["byte_size"],
                width=image_record["width"],
                height=image_record["height"],
                sha256=image_record["sha256"],
                synthetic=True,
                is_ai_generated=False,
                is_ai_modified=True,
            )
        )
    session.flush()
    for wrapper in cast(list[dict[str, object]], payload["pair_quality_evidence"]):
        pair_payload = cast(dict[str, object], wrapper["pair_screening_record_payload"])
        for side_name in ("left", "right"):
            side = cast(dict[str, object], pair_payload[side_name])
            variant_id = cast(str, side["asset_variant_id"])
            if session.get(AssetVariant, variant_id) is not None:
                continue
            session.add(
                AssetVariant(
                    id=variant_id,
                    source_asset_id=pair_payload["source_asset_id"],
                    result_asset_id=side["result_asset_id"],
                    variant_type=side["asset_variant_type"],
                    created_at=datetime(2026, 8, 26, tzinfo=UTC),
                )
            )
    session.commit()


def _report_model(report: dict[str, object]) -> DemoPairScreeningReport:
    fields = deepcopy(report)
    fields["created_at"] = _timestamp(fields["created_at"])
    return DemoPairScreeningReport(**fields)


def _resigned_report_attack(
    report: dict[str, object], attack: str
) -> tuple[dict[str, object], str]:
    forged = deepcopy(report)
    payload = cast(dict[str, object], forged["report_payload"])
    attack_digest = mirror_demo_digest(
        "mirror.demo/TestOnlyD02R2PostgreSQLAttack/v1", {"attack": attack}
    )

    if attack == "case-execution-config":
        case = cast(list[dict[str, object]], payload["ordered_case_manifest"])[0]
        case["execution_config_digest"] = attack_digest
        _resign_r2_record(case, r2.R2_CASE_SCHEMA)
        expected = "Case projection"
    elif attack == "source-m3-observation":
        source_m3 = cast(list[dict[str, object]], payload["source_m3_repeat_evidence"])[0]
        source_m3["face_count"] = 2
        _resign_r2_record(source_m3, r2.R2_SOURCE_M3_SCHEMA)
        expected = "D02"
    elif attack == "m4-replay":
        m4 = cast(list[dict[str, object]], payload["m4_repeat_evidence"])[1]
        m4["changed_pixel_count"] = cast(int, m4["changed_pixel_count"]) + 1
        _resign_r2_record(m4, r2.R2_M4_SCHEMA)
        expected = "M4 replay pair is not deterministic"
    elif attack == "result-m3-observation":
        result_m3 = cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])[0]
        result_m3["face_count"] = 2
        _resign_r2_record(result_m3, r2.R2_RESULT_M3_SCHEMA)
        expected = "D02"
    elif attack == "measurement-gate":
        gate = cast(list[dict[str, object]], payload["measurement_gate_evidence"])[0]
        evaluation = cast(dict[str, object], gate["gate_evaluation"])
        evaluation["target_direction_passed"] = False
        _resign_r2_record(gate, r2.R2_GATE_SCHEMA)
        expected = "D02"
    elif attack == "structure-false-green":
        structure = cast(
            list[dict[str, object]], payload["decode_structure_immutability_evidence"]
        )[0]
        structure["m4_replay_bytes_equal"] = False
        _resign_r2_record(structure, r2.R2_STRUCTURE_SCHEMA)
        expected = "D02"
    elif attack == "manual-false-green":
        manual = cast(list[dict[str, object]], payload["manual_review_evidence"])[0]
        manual["background_seam"] = True
        _resign_legacy_typed(manual, r2.R2_MANUAL_SCHEMA, "manual_decision_digest")
        expected = "manual review verdict"
    elif attack == "source-image-asset-projection":
        exact = cast(dict[str, object], payload["exact_duplicate_evidence"])
        source_image = next(
            image
            for image in cast(list[dict[str, object]], exact["image_records"])
            if image["authority_role"] == "SOURCE"
        )
        source_image["byte_size"] = cast(int, source_image["byte_size"]) + 1
        _resign_r2_image_record(source_image)
        expected = "source image authority"
    elif attack == "phash-signature-order":
        phash = cast(dict[str, object], payload["phash_observation_evidence"])
        signatures = cast(list[dict[str, object]], phash["ordered_record_signatures"])
        signatures[0], signatures[1] = signatures[1], signatures[0]
        _resign_r2_phash_matrix(phash)
        expected = "pHash signature projection"
    elif attack == "phash-hamming":
        phash = cast(dict[str, object], payload["phash_observation_evidence"])
        comparison = cast(list[dict[str, object]], phash["comparisons"])[0]
        comparison["hamming_distance"] = (cast(int, comparison["hamming_distance"]) + 1) % 65
        comparison["comparison_digest"] = r2._r2_phash_comparison_digest(comparison)
        expected = "pHash comparison projection"
    elif attack == "pair-side-variant":
        wrappers = cast(list[dict[str, object]], payload["pair_quality_evidence"])
        pair = cast(dict[str, object], wrappers[0]["pair_screening_record_payload"])
        other_pair = cast(dict[str, object], wrappers[2]["pair_screening_record_payload"])
        left = cast(dict[str, object], pair["left"])
        other_left = cast(dict[str, object], other_pair["left"])
        left["asset_variant_id"] = other_left["asset_variant_id"]
        wrappers[0]["pair_screening_record_digest"] = mirror_demo_digest(
            r2.R2_PAIR_SCREENING_SCHEMA, pair
        )
        expected = "dimension eligibility"
    elif attack == "dimension-eligibility":
        dimension = cast(list[dict[str, object]], payload["dimension_eligibility"])[0]
        dimension["eligible"] = False
        _resign_r2_record(dimension, r2.R2_DIMENSION_SCHEMA)
        expected = "dimension eligibility"
    elif attack == "selection-trace":
        selection = cast(list[dict[str, object]], payload["fixed_priority_selection_trace"])[0]
        selection["selection_decision"] = "INELIGIBLE"
        _resign_r2_record(selection, r2.R2_SELECTION_SCHEMA)
        expected = "selection trace"
    elif attack == "selected-manifest":
        selected = cast(list[dict[str, object]], payload["selected_pair_manifest"])
        selected[0]["left_result_asset_id"] = attack_digest[:32]
        selected[0]["entry_digest"] = mirror_demo_digest(
            r2.R2_SELECTED_ENTRY_SCHEMA,
            {
                key: value
                for key, value in selected[0].items()
                if key not in {"schema_version", "entry_digest"}
            },
        )
        forged["selected_pair_manifest_digest"] = legacy._sequence_digest(
            r2.R2_SELECTED_MANIFEST_SCHEMA, selected
        )
        expected = "selected manifest projection"
    else:
        raise AssertionError(f"unhandled attack: {attack}")

    _resign_r2_report_envelope(forged)
    return forged, expected


def _resign_bank_row(bank: dict[str, object], *, schema: str = r2.R2_BANK_SCHEMA) -> None:
    canonical = {
        key: value
        for key, value in bank.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    bank["schema_version"] = schema
    bank["canonical_payload"] = canonical
    bank["content_digest"] = mirror_demo_digest(schema, canonical)


def _resign_pair_row(pair: dict[str, object], *, schema: str = r2.R2_PAIR_SCHEMA) -> None:
    canonical = {
        key: value
        for key, value in pair.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    pair["schema_version"] = schema
    pair["canonical_payload"] = canonical
    pair["content_digest"] = mirror_demo_digest(schema, canonical)


def _bank_model(bank: dict[str, object]) -> DemoQuestionBank:
    fields = deepcopy(bank)
    fields["created_at"] = _timestamp(fields["created_at"])
    return DemoQuestionBank(**fields)


def _pair_model(pair: dict[str, object]) -> DemoQuestionPair:
    fields = deepcopy(pair)
    fields["created_at"] = _timestamp(fields["created_at"])
    return DemoQuestionPair(**fields)


def _legacy_d02_fingerprint(session: Session) -> tuple[tuple[object, ...], ...]:
    table_names = ", ".join(f"'{table_name}'" for table_name in _R2_TOUCHED_TABLES)
    queries = (
        "SELECT pg_get_functiondef("
        "to_regprocedure('mirror_demo_authority_projection(jsonb,text)'))",
        "SELECT pg_get_functiondef(to_regprocedure('mirror_demo_guard_authority()'))",
        "SELECT pg_get_functiondef("
        "to_regprocedure('mirror_demo_validate_d02_write_version_v10()'))",
        "SELECT class_row.relname, attribute_row.attname, "
        "format_type(attribute_row.atttypid, attribute_row.atttypmod), "
        "attribute_row.attnotnull, attribute_row.attgenerated, "
        "COALESCE(pg_get_expr(default_row.adbin, default_row.adrelid), '') "
        "FROM pg_attribute AS attribute_row "
        "JOIN pg_class AS class_row ON class_row.oid = attribute_row.attrelid "
        "LEFT JOIN pg_attrdef AS default_row ON default_row.adrelid = attribute_row.attrelid "
        "AND default_row.adnum = attribute_row.attnum "
        "WHERE class_row.relname IN ("
        + table_names
        + ") AND attribute_row.attnum > 0 AND NOT attribute_row.attisdropped "
        "ORDER BY class_row.relname, attribute_row.attnum",
        "SELECT class_row.relname, constraint_row.conname, constraint_row.contype, "
        "pg_get_constraintdef(constraint_row.oid, true) "
        "FROM pg_constraint AS constraint_row "
        "JOIN pg_class AS class_row ON class_row.oid = constraint_row.conrelid "
        "WHERE class_row.relname IN ("
        + table_names
        + ") ORDER BY class_row.relname, constraint_row.conname",
        "SELECT class_row.relname, trigger_row.tgname, "
        "pg_get_triggerdef(trigger_row.oid, true) "
        "FROM pg_trigger AS trigger_row "
        "JOIN pg_class AS class_row ON class_row.oid = trigger_row.tgrelid "
        "WHERE class_row.relname IN (" + table_names + ") AND NOT trigger_row.tgisinternal "
        "ORDER BY class_row.relname, trigger_row.tgname",
    )
    return tuple(
        (query_index, *tuple(row))
        for query_index, query in enumerate(queries)
        for row in session.execute(text(query)).all()
    )


def test_r2_supporting_row_replays_asset_fk_and_is_append_only(session: Session) -> None:
    packet = _packet("a")
    supporting = _persist_packet_supporting_row(session, packet)
    assert supporting.id == packet["supporting_row"]["id"]
    assert (
        session.scalar(
            select(DemoD02R2SourceAuthority.id).where(DemoD02R2SourceAuthority.id == supporting.id)
        )
        == supporting.id
    )

    with pytest.raises((DBAPIError, IntegrityError), match="supporting row is append-only"):
        session.execute(
            text(
                "UPDATE demo_d02_r2_source_authorities "
                "SET created_at = created_at + interval '1 second' WHERE id=:row_id"
            ),
            {"row_id": supporting.id},
        )
        session.commit()
    session.rollback()

    supporting_fields = dict(packet["supporting_row"])
    resigned_payload = dict(supporting_fields["canonical_payload"])
    resigned_payload["generation_request_policy_digest"] = mirror_demo_digest(
        "mirror.demo/TestOnlyResignedSupportingField/v1",
        {"row_id": supporting.id},
    )
    resigned_digest = mirror_demo_digest(
        "mirror.demo/D02R2SourceAuthorityRecord/v1",
        resigned_payload,
    )
    resigned_id = mirror_demo_digest(
        "mirror.demo/D02R2SourceAuthorityRecordId/v1",
        {
            **{
                key: resigned_payload[key]
                for key in (
                    "execution_contract_digest",
                    "evidence_root_id",
                    "root_name_receipt_digest",
                    "generation_preregistration_digest",
                    "source_allocation_manifest_digest",
                    "source_producer_dispatch_digest",
                    "source_ordinal",
                    "source_output_id",
                    "source_authority_key",
                    "source_authority_digest",
                    "source_qa_snapshot_digest",
                )
            },
            "content_digest": resigned_digest,
        },
    )[:32]
    with pytest.raises((DBAPIError, IntegrityError), match="supporting row is append-only"):
        session.execute(
            DemoD02R2SourceAuthority.__table__.update()
            .where(DemoD02R2SourceAuthority.id == supporting.id)
            .values(
                id=resigned_id,
                generation_request_policy_digest=resigned_payload[
                    "generation_request_policy_digest"
                ],
                canonical_payload=resigned_payload,
                content_digest=resigned_digest,
            )
        )
        session.commit()
    session.rollback()

    with pytest.raises((DBAPIError, IntegrityError), match="supporting row is append-only"):
        session.execute(
            text("DELETE FROM demo_d02_r2_source_authorities WHERE id=:row_id"),
            {"row_id": supporting.id},
        )
        session.commit()
    session.rollback()

    with pytest.raises((DBAPIError, IntegrityError)):
        session.execute(
            text("DELETE FROM assets WHERE id=:asset_id"), {"asset_id": supporting.source_asset_id}
        )
        session.commit()
    session.rollback()


def test_r2_identity_v4_binds_supporting_row_and_replay_is_idempotent(session: Session) -> None:
    packet = _packet("a")
    supporting = _persist_packet_supporting_row(session, packet)
    identity = _persist_packet_identity(session, packet)
    assert identity.r2_source_authority_record_id == supporting.id
    assert identity.source_authority_kind == "DEMO_R2_GENERATED_SOURCE"

    with pytest.raises((DBAPIError, IntegrityError)):
        _persist_packet_identity(session, packet)
    session.rollback()


@pytest.mark.parametrize(
    ("sequence", "action", "supersedes_id"),
    (
        (1, "REVOKE", None),
        (2, "ADMIT", None),
        (1, "ADMIT", "0" * 32),
    ),
)
def test_r2_identity_v4_rejects_fully_resigned_invalid_first_events(
    session: Session,
    sequence: int,
    action: str,
    supersedes_id: str | None,
) -> None:
    packet = _packet("a")
    _persist_packet_supporting_row(session, packet)
    forged = deepcopy(cast(dict[str, Any], packet["identity_row"]))
    forged["admission_sequence"] = sequence
    forged["admission_action"] = action
    forged["supersedes_id"] = supersedes_id
    _resign_r2_identity_event(forged)

    with pytest.raises(
        (DBAPIError, IntegrityError), match="First D02 R2 source event must be ADMIT"
    ):
        session.execute(DemoSyntheticIdentity.__table__.insert().values(**_identity_values(forged)))
        session.commit()
    session.rollback()


@pytest.mark.parametrize("config_field", ("admission_config_digest", "import_config_digest"))
def test_r2_identity_v4_rejects_fully_resigned_unfrozen_config(
    session: Session,
    config_field: str,
) -> None:
    packet = _packet("a")
    _persist_packet_supporting_row(session, packet)
    forged = deepcopy(cast(dict[str, Any], packet["identity_row"]))
    forged[config_field] = mirror_demo_digest(
        "mirror.demo/TestOnlyR2UnfrozenAdmissionConfig/v1", {"field": config_field}
    )
    _resign_r2_identity_event(forged)

    with pytest.raises(
        (DBAPIError, IntegrityError), match="D02 R2 identity admission config is invalid"
    ):
        session.execute(DemoSyntheticIdentity.__table__.insert().values(**_identity_values(forged)))
        session.commit()
    session.rollback()


@pytest.mark.parametrize(
    ("sequence", "action", "supersedes_mode"),
    (
        (3, "REVOKE", "latest"),
        (2, "REVOKE", "missing"),
        (2, "REVOKE", "wrong"),
        (2, "ADMIT", "latest"),
    ),
)
def test_r2_identity_v4_rejects_fully_resigned_invalid_successors(
    session: Session,
    sequence: int,
    action: str,
    supersedes_mode: str,
) -> None:
    packet = _packet("a")
    _persist_packet_supporting_row(session, packet)
    first = _persist_packet_identity(session, packet)
    forged = deepcopy(cast(dict[str, Any], packet["identity_row"]))
    forged["admission_sequence"] = sequence
    forged["admission_action"] = action
    forged["supersedes_id"] = {
        "latest": first.id,
        "missing": None,
        "wrong": "0" * 32,
    }[supersedes_mode]
    _resign_r2_identity_event(forged)

    with pytest.raises(
        (DBAPIError, IntegrityError),
        match="D02 R2 source admission chain is invalid or mixed-version",
    ):
        session.execute(DemoSyntheticIdentity.__table__.insert().values(**_identity_values(forged)))
        session.commit()
    session.rollback()


def test_r2_identity_v4_accepts_only_contiguous_alternating_chain(session: Session) -> None:
    packet = _packet("a")
    _persist_packet_supporting_row(session, packet)
    first = _persist_packet_identity(session, packet)

    revoke = deepcopy(cast(dict[str, Any], packet["identity_row"]))
    revoke["admission_sequence"] = 2
    revoke["admission_action"] = "REVOKE"
    revoke["supersedes_id"] = first.id
    _resign_r2_identity_event(revoke)
    session.execute(DemoSyntheticIdentity.__table__.insert().values(**_identity_values(revoke)))
    session.commit()

    readmit = deepcopy(cast(dict[str, Any], packet["identity_row"]))
    readmit["admission_sequence"] = 3
    readmit["admission_action"] = "ADMIT"
    readmit["supersedes_id"] = revoke["id"]
    _resign_r2_identity_event(readmit)
    session.execute(DemoSyntheticIdentity.__table__.insert().values(**_identity_values(readmit)))
    session.commit()

    assert session.scalars(
        select(DemoSyntheticIdentity.admission_action)
        .where(DemoSyntheticIdentity.source_authority_key == first.source_authority_key)
        .order_by(DemoSyntheticIdentity.admission_sequence)
    ).all() == ["ADMIT", "REVOKE", "ADMIT"]


def test_r2_identity_v4_rejects_fully_resigned_successor_evidence_drift(
    session: Session,
) -> None:
    packet = _packet("a")
    _persist_packet_supporting_row(session, packet)
    first = _persist_packet_identity(session, packet)
    forged = deepcopy(cast(dict[str, Any], packet["identity_row"]))
    forged["admission_sequence"] = 2
    forged["admission_action"] = "REVOKE"
    forged["supersedes_id"] = first.id
    facts = cast(dict[str, Any], forged["source_fact_snapshot"])
    facts["qa_policy_digest"] = mirror_demo_digest(
        "mirror.demo/TestOnlyR2IdentityQaPolicyDrift/v1", {"candidate": 2}
    )
    forged["source_fact_snapshot_digest"] = r2.digest_r2_facts(facts)
    _resign_r2_identity_event(forged)

    with pytest.raises(
        (DBAPIError, IntegrityError), match="D02 R2 ADMIT/REVOKE evidence copy differs"
    ):
        session.execute(DemoSyntheticIdentity.__table__.insert().values(**_identity_values(forged)))
        session.commit()
    session.rollback()


def test_r2_concurrent_identity_v4_first_admit_has_one_chain_winner(session: Session) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    packet = _packet("a")
    supporting = _persist_packet_supporting_row(session, packet)
    first = deepcopy(cast(dict[str, Any], packet["identity_row"]))
    second = deepcopy(first)
    second_facts = cast(dict[str, Any], second["source_fact_snapshot"])
    second_facts["qa_policy_digest"] = mirror_demo_digest(
        "mirror.demo/TestOnlyR2ConcurrentIdentity/v1", {"candidate": 2}
    )
    second["source_fact_snapshot_digest"] = r2.digest_r2_facts(second_facts)
    _resign_r2_identity_event(second)
    r2.validate_r2_identity_row(
        second,
        facts=second_facts,
        supporting_row=cast(dict[str, object], packet["supporting_row"]),
    )
    assert first["id"] != second["id"]
    start = Barrier(2)

    def attempt(candidate: dict[str, Any]) -> bool:
        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                start.wait()
                connection.execute(
                    DemoSyntheticIdentity.__table__.insert().values(**_identity_values(candidate))
                )
            return True
        except (DBAPIError, IntegrityError):
            return False
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, (first, second)))

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 1
    winners = session.scalars(
        select(DemoSyntheticIdentity).where(
            DemoSyntheticIdentity.r2_source_authority_record_id == supporting.id,
            DemoSyntheticIdentity.admission_sequence == 1,
        )
    ).all()
    assert len(winners) == 1
    assert winners[0].id in {first["id"], second["id"]}


def test_r2_populated_downgrade_fails_closed_then_clean_round_trip(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config(database_url)
    _persist_packet_supporting_row(session, _packet("a"))
    session.close()
    with pytest.raises(Exception, match="Cannot downgrade populated D02 R2 source authority"):
        command.downgrade(config, _DOWN)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE demo_d02_r2_source_authorities CASCADE"))
    command.downgrade(config, _DOWN)
    command.upgrade(config, _HEAD)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == _HEAD
        assert connection.scalar(text("SELECT to_regclass('demo_d02_r2_source_authorities')")) == (
            "demo_d02_r2_source_authorities"
        )
    engine.dispose()


def test_r2_clean_lifecycle_restores_demo_0007_fingerprint(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config(database_url)
    session.close()
    command.downgrade(config, _DOWN)
    try:
        before = _legacy_d02_fingerprint(session)
        command.upgrade(config, _HEAD)
        command.downgrade(config, _DOWN)
        assert _legacy_d02_fingerprint(session) == before
    finally:
        command.upgrade(config, _HEAD)


def test_r2_uses_existing_write_version_dispatch_without_parallel_write_triggers(
    session: Session,
) -> None:
    """Addendum 01 permits dispatch replacement, not a second R2 write path."""
    trigger_names = set(
        session.scalars(
            text(
                "SELECT tgname FROM pg_trigger "
                "WHERE tgname LIKE 'trg_demo_d02_r2_write_%' AND NOT tgisinternal"
            )
        )
    )
    assert trigger_names == set()


def test_r2_complete_bank_constraint_triggers_are_deferred_and_cover_both_sides(
    session: Session,
) -> None:
    """The 16-pair completeness gate must run after either bank or pair insert."""
    rows = session.execute(
        text(
            "SELECT trigger_row.tgname, class_row.relname, trigger_row.tgdeferrable, "
            "trigger_row.tginitdeferred "
            "FROM pg_trigger AS trigger_row "
            "JOIN pg_class AS class_row ON class_row.oid = trigger_row.tgrelid "
            "WHERE trigger_row.tgname LIKE 'trg_demo_d02_r2_complete_bank_v3_%' "
            "AND NOT trigger_row.tgisinternal "
            "ORDER BY trigger_row.tgname"
        )
    ).all()
    assert {
        (name, table, deferred, initially_deferred)
        for name, table, deferred, initially_deferred in rows
    } == {
        ("trg_demo_d02_r2_complete_bank_v3_bank", "demo_question_banks", True, True),
        ("trg_demo_d02_r2_complete_bank_v3_pair", "demo_question_pairs", True, True),
    }


def test_r2_report_and_complete_bank_v3_persist(session: Session) -> None:
    report, packets = _report()
    _persist_r2_report_prerequisites(session, report, packets)
    session.add(_report_model(report))
    session.commit()

    bank, pairs = _build_r2_bank_and_pairs(report, packets)
    session.add(_bank_model(bank))
    session.add_all(_pair_model(pair) for pair in pairs)
    session.commit()

    assert (
        session.scalar(
            select(DemoPairScreeningReport.id).where(DemoPairScreeningReport.id == report["id"])
        )
        == report["id"]
    )
    assert (
        session.scalar(select(DemoQuestionBank.id).where(DemoQuestionBank.id == bank["id"]))
        == bank["id"]
    )
    assert (
        len(
            session.scalars(
                select(DemoQuestionPair.id).where(DemoQuestionPair.question_bank_id == bank["id"])
            ).all()
        )
        == 16
    )


def test_r2_postgresql_rejects_resigned_report_graph_attacks(session: Session) -> None:
    report, packets = _report()
    _persist_r2_report_prerequisites(session, report, packets)
    attacks = (
        "case-execution-config",
        "source-m3-observation",
        "m4-replay",
        "result-m3-observation",
        "measurement-gate",
        "structure-false-green",
        "manual-false-green",
        "source-image-asset-projection",
        "phash-signature-order",
        "phash-hamming",
        "pair-side-variant",
        "dimension-eligibility",
        "selection-trace",
        "selected-manifest",
    )

    for attack in attacks:
        forged, expected = _resigned_report_attack(report, attack)
        session.add(_report_model(forged))
        try:
            session.commit()
        except (DBAPIError, IntegrityError) as error:
            session.rollback()
            assert expected in str(error), attack
        else:
            pytest.fail(f"resigned PostgreSQL attack was admitted: {attack}")
        assert session.get(DemoPairScreeningReport, forged["id"]) is None, attack


def test_r2_deferred_complete_bank_rejects_fifteen_pair_commit_and_rolls_back(
    session: Session,
) -> None:
    """The deferred R2 completeness trigger must leave no partial Bank authority."""
    report, packets = _report()
    _persist_r2_report_prerequisites(session, report, packets)
    session.add(_report_model(report))
    session.commit()

    bank, pairs = _build_r2_bank_and_pairs(report, packets)
    session.add(_bank_model(bank))
    session.add_all(_pair_model(pair) for pair in pairs[:-1])
    with pytest.raises((DBAPIError, IntegrityError), match="complete selected 16-pair authority"):
        session.commit()
    session.rollback()

    assert session.get(DemoQuestionBank, bank["id"]) is None
    assert not session.scalars(
        select(DemoQuestionPair.id).where(DemoQuestionPair.question_bank_id == bank["id"])
    ).all()


def test_r2_postgresql_rejects_fully_resigned_bank_selected_member_attack(
    session: Session,
) -> None:
    report, packets = _report()
    _persist_r2_report_prerequisites(session, report, packets)
    session.add(_report_model(report))
    session.commit()

    bank, _ = _build_r2_bank_and_pairs(report, packets)
    manifest = cast(dict[str, object], bank["dimension_manifest"])
    selected = cast(list[dict[str, object]], manifest["selected_dimensions"])
    digests = cast(list[str], selected[0]["ordered_selected_pair_entry_digests"])
    digests[0], digests[1] = digests[1], digests[0]
    _resign_bank_row(bank)

    session.add(_bank_model(bank))
    with pytest.raises((DBAPIError, IntegrityError), match="selected entry ordering"):
        session.flush()
    session.rollback()
    assert session.get(DemoQuestionBank, bank["id"]) is None


def test_r2_postgresql_rejects_fully_resigned_pair_physical_variant_attack(
    session: Session,
) -> None:
    report, packets = _report()
    _persist_r2_report_prerequisites(session, report, packets)
    session.add(_report_model(report))
    session.commit()

    bank, pairs = _build_r2_bank_and_pairs(report, packets)
    session.add(_bank_model(bank))
    session.flush()
    forged = deepcopy(pairs[0])
    donor = pairs[2]
    for field in ("left_asset_id", "left_asset_sha256", "left_asset_variant_id"):
        forged[field] = donor[field]
    _resign_pair_row(forged)

    session.add(_pair_model(forged))
    with pytest.raises((DBAPIError, IntegrityError), match=r"selected member|side authority"):
        session.flush()
    session.rollback()
    assert session.get(DemoQuestionPair, forged["id"]) is None


@pytest.mark.parametrize("target", ("report", "bank", "pair"))
def test_r2_postgresql_rejects_mixed_report_bank_pair_authority_versions(
    session: Session, target: str
) -> None:
    """A complete re-sign cannot route an R2 authority graph through a v2 gate."""
    report, packets = _report()
    _persist_r2_report_prerequisites(session, report, packets)
    bank, pairs = _build_r2_bank_and_pairs(report, packets)

    if target == "report":
        report["schema_version"] = "mirror.demo/D02PairScreeningReport/v2"
        _resign_r2_report_envelope(report)
        report["schema_version"] = "mirror.demo/D02PairScreeningReport/v2"
        report["content_digest"] = mirror_demo_digest(
            cast(str, report["schema_version"]),
            cast(dict[str, object], report["canonical_payload"]),
        )
        session.add(_report_model(report))
    else:
        session.add(_report_model(report))
        session.commit()
        if target == "bank":
            bank["schema_version"] = "mirror.demo/DemoQuestionBank/v2"
            _resign_bank_row(bank, schema="mirror.demo/DemoQuestionBank/v2")
            session.add(_bank_model(bank))
        else:
            session.add(_bank_model(bank))
            session.flush()
            pair = pairs[0]
            pair["schema_version"] = "mirror.demo/DemoQuestionPair/v2"
            _resign_pair_row(pair, schema="mirror.demo/DemoQuestionPair/v2")
            session.add(_pair_model(pair))

    with pytest.raises((DBAPIError, IntegrityError)):
        session.flush()
    session.rollback()


def test_r2_source_replay_is_idempotent_but_conflicting_ordinal_fails_closed(
    session: Session,
) -> None:
    packet = _packet("a", source_ordinal=1)
    persisted = _persist_packet_supporting_row(session, packet)
    replay = _supporting_row_values(packet)
    replay_id = session.scalar(
        pg_insert(DemoD02R2SourceAuthority)
        .values(**replay)
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(DemoD02R2SourceAuthority.id)
    )
    session.commit()
    assert replay_id is None
    assert session.get(DemoD02R2SourceAuthority, persisted.id) is not None

    conflicting = _packet("b", source_ordinal=1)
    _persist_packet_asset(session, conflicting)
    session.add(DemoD02R2SourceAuthority(**_supporting_row_values(conflicting)))
    with pytest.raises((DBAPIError, IntegrityError), match="execution_ordinal"):
        session.commit()
    session.rollback()
    assert (
        session.scalar(
            select(DemoD02R2SourceAuthority.id).where(
                DemoD02R2SourceAuthority.execution_contract_digest
                == persisted.execution_contract_digest,
                DemoD02R2SourceAuthority.source_ordinal == 1,
            )
        )
        == persisted.id
    )


def test_r2_concurrent_source_ordinal_admit_has_one_canonical_winner(session: Session) -> None:
    """Two distinct first admits for an execution ordinal must never both commit."""
    database_url = os.environ["TEST_DATABASE_URL"]
    first = _packet("a", source_ordinal=1)
    second = _packet("b", source_ordinal=1)
    _persist_packet_asset(session, first)
    _persist_packet_asset(session, second)
    start = Barrier(2)

    def attempt(packet: dict[str, object]) -> bool:
        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                start.wait()
                connection.execute(
                    DemoD02R2SourceAuthority.__table__.insert().values(
                        **_supporting_row_values(packet)
                    )
                )
            return True
        except (DBAPIError, IntegrityError):
            return False
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, (first, second)))

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 1
    first_supporting = cast(dict[str, object], first["supporting_row"])
    second_supporting = cast(dict[str, object], second["supporting_row"])
    winners = session.scalars(
        select(DemoD02R2SourceAuthority).where(
            DemoD02R2SourceAuthority.execution_contract_digest
            == first_supporting["execution_contract_digest"],
            DemoD02R2SourceAuthority.source_ordinal == 1,
        )
    ).all()
    assert len(winners) == 1
    assert winners[0].id in {
        first_supporting["id"],
        second_supporting["id"],
    }


def test_r2_rejects_null_json_digest_and_resigned_nullable_report_count(
    session: Session,
) -> None:
    report, packets = _report()
    _persist_r2_report_prerequisites(session, report, packets)

    null_digest_attack = deepcopy(report)
    null_digest_payload = cast(dict[str, object], null_digest_attack["report_payload"])
    source_m3_records = cast(
        list[dict[str, object]], null_digest_payload["source_m3_repeat_evidence"]
    )
    source_m3_records[0]["record_digest"] = None
    _resign_r2_report_envelope(null_digest_attack)
    session.add(_report_model(null_digest_attack))
    with pytest.raises((DBAPIError, IntegrityError), match="mandatory digest leaf"):
        session.flush()
    session.rollback()
    assert session.get(DemoPairScreeningReport, null_digest_attack["id"]) is None

    session.add(_report_model(report))
    session.commit()
    bank, _ = _build_r2_bank_and_pairs(report, packets)
    manifest = cast(dict[str, object], bank["dimension_manifest"])
    manifest["source_p2_candidate_manifest_content_digest"] = None
    _resign_bank_row(bank)
    session.add(_bank_model(bank))
    with pytest.raises((DBAPIError, IntegrityError), match="Report or manifest binding"):
        session.flush()
    session.rollback()

    nullable_attack, _ = _report()
    nullable_attack["measurement_gate_count"] = None
    _resign_r2_report_envelope(nullable_attack)
    session.add(_report_model(nullable_attack))
    with pytest.raises((DBAPIError, IntegrityError)):
        session.flush()
    session.rollback()


def test_r2_postgresql_negative_input_validation_matches_python_for_all_mandatory_digest_leaves(
    session: Session,
) -> None:
    """DATA_INTEGRITY_INVARIANTS: PostgreSQL rejects the full fully-resigned matrix."""

    report, packets = _report()
    _persist_r2_report_prerequisites(session, report, packets)

    for record_group, leaf, mutation in _R2_MANDATORY_DIGEST_ATTACK_CASES:
        forged, _ = _build_fully_resigned_mandatory_digest_attack(
            record_group=record_group,
            leaf=leaf,
            mutation=mutation,
        )
        try:
            with pytest.raises((DBAPIError, IntegrityError)) as error:
                session.add(_report_model(forged))
                session.flush()
            if mutation not in {"wrong_well_formed_digest", "cross_source_substitution"}:
                assert "mandatory digest leaf" in str(error.value)
            else:
                assert "mandatory digest leaf" not in str(error.value)
        except AssertionError as error:
            pytest.fail(
                "PostgreSQL MALFORMED_AUTHORITY_REJECTION parity failed for "
                f"{record_group}.{leaf}/{mutation}: {error}"
            )
        finally:
            session.rollback()

    assert session.scalar(select(DemoPairScreeningReport.id)) is None
