from __future__ import annotations

import copy
import hashlib
import os
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    D02_DOWN_REVISION,
    DEMO_REVISION,
    _accepted_synthetic_source,
    _build_demo_row,
    _canonical_json,
    _digest,
    _insert_d02_question_bank,
    _insert_demo_row,
    _insert_full_demo_graph,
    _insert_local_d02_identity,
    _result_variant,
    _synthetic_admission_fields,
    _truncate_demo_authority,
)

from mirror_api.demo_models import (
    DemoPairScreeningReport,
    DemoQuestionBank,
    DemoQuestionPair,
    DemoSyntheticIdentity,
)
from mirror_api.models import new_id

_ROW_JSON_QUERIES = {
    "demo_synthetic_identities": text(
        "SELECT to_jsonb(authority_row)::text FROM "
        "(SELECT * FROM demo_synthetic_identities WHERE id=:row_id) AS authority_row"
    ),
    "demo_question_banks": text(
        "SELECT to_jsonb(authority_row)::text FROM "
        "(SELECT * FROM demo_question_banks WHERE id=:row_id) AS authority_row"
    ),
    "demo_question_pairs": text(
        "SELECT to_jsonb(authority_row)::text FROM "
        "(SELECT * FROM demo_question_pairs WHERE id=:row_id) AS authority_row"
    ),
}

_AUTHORITY_EXCLUDED_COLUMNS = {
    "id",
    "schema_version",
    "canonical_payload",
    "content_digest",
    "created_at",
    "closed_at",
    "tombstoned_at",
}


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


def _alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _formal_table_ddl_signature(connection: Connection) -> tuple[tuple[Any, ...], ...]:
    queries = (
        """
        SELECT c.relname, a.attnum, a.attname,
               format_type(a.atttypid, a.atttypmod), a.attnotnull,
               COALESCE(pg_get_expr(d.adbin, d.adrelid), '')
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        LEFT JOIN pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND c.relname NOT LIKE 'demo\_%' ESCAPE '\\'
          AND c.relname <> 'alembic_version'
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY c.relname, a.attnum
        """,
        """
        SELECT c.relname, con.conname, con.contype,
               pg_get_constraintdef(con.oid, true)
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND c.relname NOT LIKE 'demo\_%' ESCAPE '\\'
          AND c.relname <> 'alembic_version'
        ORDER BY c.relname, con.conname
        """,
        """
        SELECT c.relname, index_class.relname, pg_get_indexdef(index_class.oid)
        FROM pg_index idx
        JOIN pg_class c ON c.oid = idx.indrelid
        JOIN pg_class index_class ON index_class.oid = idx.indexrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND c.relname NOT LIKE 'demo\_%' ESCAPE '\\'
          AND c.relname <> 'alembic_version'
        ORDER BY c.relname, index_class.relname
        """,
        """
        SELECT c.relname, trigger_row.tgname, pg_get_triggerdef(trigger_row.oid, true)
        FROM pg_trigger trigger_row
        JOIN pg_class c ON c.oid = trigger_row.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND c.relname NOT LIKE 'demo\_%' ESCAPE '\\'
          AND c.relname <> 'alembic_version'
          AND NOT trigger_row.tgisinternal
        ORDER BY c.relname, trigger_row.tgname
        """,
    )
    signature: list[tuple[Any, ...]] = []
    for query_index, query in enumerate(queries):
        signature.extend(
            (query_index, *tuple(row)) for row in connection.execute(text(query)).all()
        )
    return tuple(signature)


def _row_json(connection: Connection, table_name: str, row_id: str) -> str:
    value = connection.scalar(
        _ROW_JSON_QUERIES[table_name],
        {"row_id": row_id},
    )
    assert isinstance(value, str)
    return value


def _authority_fields(authority_row: Any) -> dict[str, Any]:
    return {
        column.name: copy.deepcopy(getattr(authority_row, column.name))
        for column in authority_row.__table__.columns
        if column.name not in _AUTHORITY_EXCLUDED_COLUMNS
    }


def _redigest_d02_record(record: dict[str, Any], *, digest_key: str = "record_digest") -> None:
    record[digest_key] = _digest(
        str(record["schema_version"]),
        {key: value for key, value in record.items() if key not in {"schema_version", digest_key}},
    )


def _clone_d02_report(
    report: DemoPairScreeningReport,
    *,
    report_payload: dict[str, Any],
    field_overrides: dict[str, Any] | None = None,
) -> DemoPairScreeningReport:
    fields = _authority_fields(report)
    report_digest = _digest(report.schema_version, report_payload)
    fields.update(report_payload=report_payload, report_digest=report_digest)
    if field_overrides:
        fields.update(field_overrides)
    cloned_report = cast(
        DemoPairScreeningReport,
        _build_demo_row(
            DemoPairScreeningReport,
            row_id=_digest(
                "mirror.demo/D02PairScreeningReportId/v1",
                {"report_digest": report_digest},
            )[:32],
            authority_schema_version=report.schema_version,
            **fields,
        ),
    )
    if cloned_report.selected_pair_manifest_digest is None:
        cloned_report.canonical_payload.pop("selected_pair_manifest_digest", None)
        cloned_report.content_digest = _digest(
            cloned_report.schema_version, cloned_report.canonical_payload
        )
    return cloned_report


def _clone_v2_bank(
    bank: DemoQuestionBank,
    *,
    marker: str,
    dimension_manifest: dict[str, Any] | None = None,
) -> DemoQuestionBank:
    fields = _authority_fields(bank)
    if dimension_manifest is not None:
        fields["dimension_manifest"] = dimension_manifest
    fields["version"] = f"d02-neg-{marker[:16]}-{new_id()}"
    fields["algorithm_config_digest"] = hashlib.sha256(
        f"d02-negative-algorithm/{marker}".encode()
    ).hexdigest()
    bank_id = _digest(
        "mirror.demo/D02QuestionBankId/v1",
        {
            "algorithm_config_digest": fields["algorithm_config_digest"],
            "screening_report_digest": fields["screening_report_digest"],
            "screening_report_id": fields["screening_report_id"],
            "selected_pair_manifest_digest": fields["pair_manifest_digest"],
        },
    )[:32]
    return cast(
        DemoQuestionBank,
        _build_demo_row(
            DemoQuestionBank,
            row_id=bank_id,
            authority_schema_version="mirror.demo/DemoQuestionBank/v2",
            **fields,
        ),
    )


def _clone_v2_pair(
    pair: DemoQuestionPair,
    *,
    question_bank_id: str,
    qa_payload: dict[str, Any] | None = None,
    field_overrides: dict[str, Any] | None = None,
) -> DemoQuestionPair:
    fields = _authority_fields(pair)
    fields["question_bank_id"] = question_bank_id
    if qa_payload is not None:
        fields["qa_payload"] = qa_payload
    if field_overrides:
        fields.update(field_overrides)
    pair_id = _digest(
        "mirror.demo/D02QuestionPairId/v1",
        {
            "dimension_key": fields["dimension_key"],
            "magnitude_ppm": fields["magnitude_ppm"],
            "pair_screening_record_digest": fields["qa_payload"]["pair_screening_record_digest"],
            "question_bank_id": question_bank_id,
            "source_admission_event_id": fields["demo_synthetic_identity_id"],
        },
    )[:32]
    return cast(
        DemoQuestionPair,
        _build_demo_row(
            DemoQuestionPair,
            row_id=pair_id,
            authority_schema_version="mirror.demo/DemoQuestionPair/v2",
            **fields,
        ),
    )


def _failed_report_from(report: DemoPairScreeningReport) -> DemoPairScreeningReport:
    fields = _authority_fields(report)
    report_payload = copy.deepcopy(report.report_payload)

    def redigest_record(record: dict[str, Any], *, digest_key: str = "record_digest") -> None:
        record[digest_key] = _digest(
            str(record["schema_version"]),
            {
                key: value
                for key, value in record.items()
                if key not in {"schema_version", digest_key}
            },
        )

    pair_wrappers = report_payload["pair_quality_evidence"]
    manual_records = report_payload["manual_review_evidence"]
    for failed_dimension in ("chin_height", "eye_spacing"):
        wrapper = next(
            candidate
            for candidate in pair_wrappers
            if candidate["pair_screening_record_payload"]["dimension_key"] == failed_dimension
        )
        pair_payload = wrapper["pair_screening_record_payload"]
        failed_side = pair_payload["left"]
        manual_record = next(
            candidate
            for candidate in manual_records
            if candidate["case_id"] == failed_side["case_id"]
        )
        manual_record["background_seam"] = True
        manual_record["verdict"] = "FAIL"
        redigest_record(manual_record, digest_key="manual_decision_digest")

        failed_side["manual_decision_digest"] = manual_record["manual_decision_digest"]
        failed_side["manual_gate_passed"] = False
        failed_side["side_gate_passed"] = False
        failed_side["side_quality_state"] = "NOT_COMPUTED_GATE_FAILED"
        failed_side["side_quality_component_ppm"] = 0
        pair_payload["pair_side_gates_passed"] = False
        pair_payload["pair_gate_passed"] = False
        pair_payload["pair_quality_state"] = "NOT_COMPUTED_GATE_FAILED"
        pair_payload["pair_quality_ppm"] = 0
        wrapper["pair_screening_record_digest"] = _digest(
            "mirror.demo/D02PairScreeningRecord/v3", pair_payload
        )

    dimension_records = report_payload["dimension_eligibility"]
    dimension_by_key = {record["dimension_key"]: record for record in dimension_records}
    exact_sha_gate = bool(report_payload["exact_duplicate_evidence"]["exact_sha_gate_passed"])
    failure_reason_order = (
        ("ONE_OR_MORE_SIDE_GATES_FAILED", "all_sixteen_side_gates_passed"),
        ("ONE_OR_MORE_PAIR_GATES_FAILED", "all_eight_pair_gates_passed"),
        ("ONE_OR_MORE_MANUAL_GATES_FAILED", "all_manual_gates_passed"),
        ("GLOBAL_EXACT_SHA_GATE_FAILED", "global_exact_sha_gate_passed"),
        ("EMPTY_LOCK_POLICY_GATE_FAILED", "empty_lock_policy_gate_passed"),
    )
    for dimension_record in dimension_records:
        dimension_key = str(dimension_record["dimension_key"])
        priority_index = int(dimension_record["priority_index"])
        dimension_wrappers = [
            wrapper
            for wrapper in pair_wrappers
            if wrapper["pair_screening_record_payload"]["dimension_key"] == dimension_key
        ]
        side_entries: list[dict[str, Any]] = []
        pair_entries: list[dict[str, Any]] = []
        for wrapper in dimension_wrappers:
            pair_payload = wrapper["pair_screening_record_payload"]
            for side_label, side_key in (("LEFT", "left"), ("RIGHT", "right")):
                side = pair_payload[side_key]
                side_entries.append(
                    {
                        "schema_version": "mirror.demo/D02DimensionSideGateEntry/v1",
                        "source_ordinal": pair_payload["source_ordinal"],
                        "magnitude_ppm": pair_payload["magnitude_ppm"],
                        "side": side_label,
                        "case_id": side["case_id"],
                        "automated_gate_digest": side["automated_gate_digest"],
                        "manual_decision_digest": side["manual_decision_digest"],
                        "automated_gate_passed": side["automated_gate_passed"],
                        "manual_gate_passed": side["manual_gate_passed"],
                        "side_gate_passed": side["side_gate_passed"],
                    }
                )
            pair_entries.append(
                {
                    "schema_version": "mirror.demo/D02DimensionPairGateEntry/v1",
                    "source_ordinal": pair_payload["source_ordinal"],
                    "magnitude_ppm": pair_payload["magnitude_ppm"],
                    "pair_record_id": pair_payload["pair_record_id"],
                    "pair_screening_record_digest": wrapper["pair_screening_record_digest"],
                    "pair_gate_passed": pair_payload["pair_gate_passed"],
                }
            )

        all_side = all(bool(entry["side_gate_passed"]) for entry in side_entries)
        all_pair = all(bool(entry["pair_gate_passed"]) for entry in pair_entries)
        all_manual = all(bool(entry["manual_gate_passed"]) for entry in side_entries)
        all_lock = all(
            bool(wrapper["pair_screening_record_payload"]["empty_lock_policy_gate_passed"])
            for wrapper in dimension_wrappers
        )
        dimension_record.update(
            ordered_pair_screening_record_digests=[
                wrapper["pair_screening_record_digest"] for wrapper in dimension_wrappers
            ],
            ordered_side_automated_gate_digests=[
                entry["automated_gate_digest"] for entry in side_entries
            ],
            sixteen_side_gate_digest=_digest(
                "mirror.demo/D02SixteenSideGate/v1",
                {
                    "dimension_key": dimension_key,
                    "priority_index": priority_index,
                    "ordered_side_gate_entries": side_entries,
                },
            ),
            eight_pair_gate_digest=_digest(
                "mirror.demo/D02EightPairGate/v1",
                {
                    "dimension_key": dimension_key,
                    "priority_index": priority_index,
                    "ordered_pair_gate_entries": pair_entries,
                },
            ),
            all_sixteen_side_gates_passed=all_side,
            all_eight_pair_gates_passed=all_pair,
            all_manual_gates_passed=all_manual,
            global_exact_sha_gate_passed=exact_sha_gate,
            empty_lock_policy_gate_passed=all_lock,
        )
        dimension_record["eligible"] = all(
            (
                all_side,
                all_pair,
                all_manual,
                exact_sha_gate,
                all_lock,
            )
        )
        dimension_record["failure_reasons"] = [
            reason
            for reason, field_name in failure_reason_order
            if not bool(dimension_record[field_name])
        ]
        redigest_record(dimension_record)

    eligible_dimensions = [
        str(record["dimension_key"]) for record in dimension_records if bool(record["eligible"])
    ]
    eligible_rank = 0
    selection_trace = report_payload["fixed_priority_selection_trace"]
    for selection_step, trace_record in enumerate(selection_trace, start=1):
        dimension_record = dimension_by_key[str(trace_record["dimension_key"])]
        eligible = bool(dimension_record["eligible"])
        if eligible:
            eligible_rank += 1
            rank = eligible_rank
        else:
            rank = 0
        if not eligible:
            decision, slot, selected = "INELIGIBLE", 0, False
        elif len(eligible_dimensions) < 2:
            decision, slot, selected = (
                "ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET",
                0,
                False,
            )
        elif rank == 1:
            decision, slot, selected = "SELECTED_SLOT_1", 1, True
        elif rank == 2:
            decision, slot, selected = "SELECTED_SLOT_2", 2, True
        else:
            decision, slot, selected = "ELIGIBLE_NOT_SELECTED_CAPACITY", 0, False
        trace_record.update(
            selection_step=selection_step,
            priority_index=selection_step,
            dimension_eligibility_record_digest=dimension_record["record_digest"],
            eligible=eligible,
            eligible_rank=rank,
            selection_decision=decision,
            selection_slot=slot,
            selected=selected,
        )
        redigest_record(trace_record)

    report_payload["selected_pair_manifest"] = []
    report_digest = _digest(report.schema_version, report_payload)
    fields.update(
        report_payload=report_payload,
        report_digest=report_digest,
        status="FAILED",
        selected_pair_count=0,
        selected_result_side_count=0,
        eligible_dimension_keys=eligible_dimensions,
        selected_dimension_keys=[],
        selected_pair_manifest_digest=None,
    )
    report_id = _digest(
        "mirror.demo/D02PairScreeningReportId/v1",
        {"report_digest": report_digest},
    )[:32]
    failed_report = cast(
        DemoPairScreeningReport,
        _build_demo_row(
            DemoPairScreeningReport,
            row_id=report_id,
            authority_schema_version=report.schema_version,
            **fields,
        ),
    )
    failed_report.canonical_payload.pop("selected_pair_manifest_digest", None)
    failed_report.content_digest = _digest(
        failed_report.schema_version, failed_report.canonical_payload
    )
    return failed_report


def _insert_legacy_v1_graph(
    connection: Connection,
    *,
    source_identity_id: str,
    source_asset_id: str,
    source_asset_sha256: str,
    accepted_qa_run_id: str,
    accepted_qa_snapshot_digest: str,
    left_asset_id: str,
    left_asset_sha256: str,
    left_variant_id: str,
    right_asset_id: str,
    right_asset_sha256: str,
    right_variant_id: str,
) -> tuple[str, str, str]:
    created_at = datetime(2026, 8, 24, 2, 0, tzinfo=UTC)
    identity_id = new_id()
    identity_schema = "mirror.demo/DemoSyntheticIdentity/v1"
    identity_payload = {
        "formal_synthetic_identity_id": source_identity_id,
        "formal_canonical_asset_id": source_asset_id,
        "formal_canonical_asset_sha256": source_asset_sha256,
        "formal_accepted_qa_run_id": accepted_qa_run_id,
        "formal_accepted_qa_snapshot_digest": accepted_qa_snapshot_digest,
        "admission_sequence": 1,
        "admission_action": "ADMIT",
        "admission_config_digest": hashlib.sha256(b"legacy-v1-admission").hexdigest(),
        "supersedes_id": None,
    }
    connection.execute(
        text(
            """
            INSERT INTO demo_synthetic_identities (
                id, schema_version, canonical_payload, content_digest, created_at,
                formal_synthetic_identity_id, formal_canonical_asset_id,
                formal_canonical_asset_sha256, formal_accepted_qa_run_id,
                formal_accepted_qa_snapshot_digest, admission_sequence,
                admission_action, admission_config_digest, supersedes_id
            ) VALUES (
                :id, :schema_version, CAST(:canonical_payload AS jsonb), :content_digest,
                :created_at, :formal_synthetic_identity_id, :formal_canonical_asset_id,
                :formal_canonical_asset_sha256, :formal_accepted_qa_run_id,
                :formal_accepted_qa_snapshot_digest, 1, 'ADMIT',
                :admission_config_digest, NULL
            )
            """
        ),
        {
            "id": identity_id,
            "schema_version": identity_schema,
            "canonical_payload": _canonical_json(identity_payload),
            "content_digest": _digest(identity_schema, identity_payload),
            "created_at": created_at,
            **identity_payload,
        },
    )

    bank_id = new_id()
    bank_schema = "mirror.demo/DemoQuestionBank/v1"
    bank_payload = {
        "version": f"legacy-v1-{new_id()}",
        "algorithm_config_digest": hashlib.sha256(b"legacy-v1-algorithm").hexdigest(),
        "routing_version": "legacy-routing-v1",
        "stopping_version": "legacy-stopping-v1",
        "neighborhood_version": "legacy-neighborhood-v1",
        "pair_manifest_digest": hashlib.sha256(b"legacy-v1-pairs").hexdigest(),
        "dimension_manifest": [{"key": "jaw_width"}],
    }
    connection.execute(
        text(
            """
            INSERT INTO demo_question_banks (
                id, schema_version, canonical_payload, content_digest, created_at,
                version, algorithm_config_digest, routing_version, stopping_version,
                neighborhood_version, pair_manifest_digest, dimension_manifest
            ) VALUES (
                :id, :schema_version, CAST(:canonical_payload AS jsonb), :content_digest,
                :created_at, :version, :algorithm_config_digest, :routing_version,
                :stopping_version, :neighborhood_version, :pair_manifest_digest,
                CAST(:dimension_manifest AS jsonb)
            )
            """
        ),
        {
            "id": bank_id,
            "schema_version": bank_schema,
            "canonical_payload": _canonical_json(bank_payload),
            "content_digest": _digest(bank_schema, bank_payload),
            "created_at": created_at,
            **{
                key: _canonical_json(value) if key == "dimension_manifest" else value
                for key, value in bank_payload.items()
            },
        },
    )

    pair_id = new_id()
    pair_schema = "mirror.demo/DemoQuestionPair/v1"
    pair_payload = {
        "question_bank_id": bank_id,
        "demo_synthetic_identity_id": identity_id,
        "source_asset_id": source_asset_id,
        "source_asset_sha256": source_asset_sha256,
        "left_asset_id": left_asset_id,
        "left_asset_sha256": left_asset_sha256,
        "right_asset_id": right_asset_id,
        "right_asset_sha256": right_asset_sha256,
        "left_asset_variant_id": left_variant_id,
        "right_asset_variant_id": right_variant_id,
        "dimension_key": "jaw_width",
        "magnitude_ppm": 15_000,
        "left_delta_ppm": -15_000,
        "right_delta_ppm": 15_000,
        "pair_quality_ppm": 900_000,
        "qa_payload": {"passed": 1},
    }
    connection.execute(
        text(
            """
            INSERT INTO demo_question_pairs (
                id, schema_version, canonical_payload, content_digest, created_at,
                question_bank_id, demo_synthetic_identity_id, source_asset_id,
                source_asset_sha256, left_asset_id, left_asset_sha256, right_asset_id,
                right_asset_sha256, left_asset_variant_id, right_asset_variant_id,
                dimension_key, magnitude_ppm, left_delta_ppm, right_delta_ppm,
                pair_quality_ppm, qa_payload
            ) VALUES (
                :id, :schema_version, CAST(:canonical_payload AS jsonb), :content_digest,
                :created_at, :question_bank_id, :demo_synthetic_identity_id,
                :source_asset_id, :source_asset_sha256, :left_asset_id,
                :left_asset_sha256, :right_asset_id, :right_asset_sha256,
                :left_asset_variant_id, :right_asset_variant_id, :dimension_key,
                :magnitude_ppm, :left_delta_ppm, :right_delta_ppm,
                :pair_quality_ppm, CAST(:qa_payload AS jsonb)
            )
            """
        ),
        {
            "id": pair_id,
            "schema_version": pair_schema,
            "canonical_payload": _canonical_json(pair_payload),
            "content_digest": _digest(pair_schema, pair_payload),
            "created_at": created_at,
            **{
                key: _canonical_json(value) if key == "qa_payload" else value
                for key, value in pair_payload.items()
            },
        },
    )
    return identity_id, bank_id, pair_id


@pytest.mark.parametrize(
    ("fixed18_value", "expected_ppm"),
    (
        ("0.000000499999999999", 0),
        ("0.000000500000000000", 0),
        ("0.000000500000000001", 1),
        ("0.000001500000000000", 2),
        ("0.000002500000000000", 2),
        ("0.123456500000000000", 123_456),
        ("0.123457500000000000", 123_458),
        ("1.000000000000000000", 1_000_000),
    ),
)
def test_round_half_even_fixed18_boundaries(
    session: Session, fixed18_value: str, expected_ppm: int
) -> None:
    assert (
        session.scalar(
            text("SELECT mirror_demo_round_half_even_ppm(:fixed18_value)"),
            {"fixed18_value": fixed18_value},
        )
        == expected_ppm
    )


@pytest.mark.parametrize(
    "invalid_value",
    ("-0.000000000000000000", "0", "0.1", "1.000000000000000001"),
)
def test_round_half_even_rejects_noncanonical_fixed18(session: Session, invalid_value: str) -> None:
    with pytest.raises(DBAPIError, match="fixed18 value is not canonical"):
        session.scalar(
            text("SELECT mirror_demo_round_half_even_ppm(:fixed18_value)"),
            {"fixed18_value": invalid_value},
        )
    session.rollback()


def test_source_key_helpers_and_generated_expressions_are_frozen(session: Session) -> None:
    helper_rows = [
        tuple(row)
        for row in session.execute(
            text(
                """
                SELECT proname, provolatile, proisstrict
                FROM pg_proc
                WHERE proname IN (
                    'mirror_demo_formal_source_authority_key',
                    'mirror_demo_local_source_authority_key'
                )
                ORDER BY proname
                """
            )
        )
    ]
    assert helper_rows == [
        ("mirror_demo_formal_source_authority_key", "i", True),
        ("mirror_demo_local_source_authority_key", "i", True),
    ]

    generated_rows = session.execute(
        text(
            """
            SELECT attribute_row.attname,
                   pg_get_expr(default_row.adbin, default_row.adrelid),
                   attribute_row.attgenerated
            FROM pg_attribute attribute_row
            JOIN pg_attrdef default_row
              ON default_row.adrelid = attribute_row.attrelid
             AND default_row.adnum = attribute_row.attnum
            WHERE attribute_row.attrelid = 'demo_synthetic_identities'::regclass
              AND attribute_row.attname IN ('source_authority_kind','source_authority_key')
            ORDER BY attribute_row.attname
            """
        )
    ).all()
    assert len(generated_rows) == 2
    expressions = {
        name: expression for name, expression, generated in generated_rows if generated == "s"
    }
    assert set(expressions) == {"source_authority_kind", "source_authority_key"}
    assert "source_authority_key" not in expressions["source_authority_kind"]
    assert "source_authority_kind" not in expressions["source_authority_key"]
    assert "formal_synthetic_identity_id" in expressions["source_authority_kind"]
    for base_column in (
        "formal_synthetic_identity_id",
        "source_output_id",
        "formal_canonical_asset_id",
        "formal_canonical_asset_sha256",
        "source_receipt_digest",
    ):
        assert base_column in expressions["source_authority_key"]


def test_new_v1_identity_bank_and_pair_inserts_fail_closed(session: Session) -> None:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    identity = _build_demo_row(
        DemoSyntheticIdentity,
        authority_schema_version="mirror.demo/DemoSyntheticIdentity/v1",
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=1,
            action="ADMIT",
            supersedes_id=None,
            config_marker="new-v1-rejected",
        ),
    )
    identity.canonical_payload["source_authority_kind"] = "FORMAL_REFERENCE"
    identity.canonical_payload["source_authority_key"] = _digest(
        "mirror.demo/SourceAuthorityKey/v1",
        {
            "formal_synthetic_identity_id": formal_identity.id,
            "source_authority_kind": "FORMAL_REFERENCE",
        },
    )
    identity.content_digest = _digest(identity.schema_version, identity.canonical_payload)
    session.add(identity)
    with pytest.raises(
        DBAPIError,
        match=r"canonical payload disagrees|identity events must use v2 authority",
    ):
        session.commit()
    session.rollback()

    bank = _build_demo_row(
        DemoQuestionBank,
        authority_schema_version="mirror.demo/DemoQuestionBank/v1",
        version=f"new-v1-rejected-{new_id()}",
        algorithm_config_digest="1" * 64,
        routing_version="legacy-v1",
        stopping_version="legacy-v1",
        neighborhood_version="legacy-v1",
        pair_manifest_digest="2" * 64,
        dimension_manifest=[{"key": "jaw_width"}],
        screening_report_id=None,
        screening_report_digest=None,
    )
    session.add(bank)
    with pytest.raises(DBAPIError, match="question banks must use v2 authority"):
        session.commit()
    session.rollback()

    pair = _build_demo_row(
        DemoQuestionPair,
        authority_schema_version="mirror.demo/DemoQuestionPair/v1",
        question_bank_id="1" * 32,
        demo_synthetic_identity_id="2" * 32,
        source_asset_id="3" * 32,
        source_asset_sha256="4" * 64,
        left_asset_id="5" * 32,
        left_asset_sha256="6" * 64,
        right_asset_id="7" * 32,
        right_asset_sha256="8" * 64,
        left_asset_variant_id="9" * 32,
        right_asset_variant_id="a" * 32,
        dimension_key="jaw_width",
        magnitude_ppm=15_000,
        left_delta_ppm=-15_000,
        right_delta_ppm=15_000,
        pair_quality_ppm=900_000,
        qa_payload={"passed": 1},
        screening_report_id=None,
        screening_report_digest=None,
    )
    session.add(pair)
    with pytest.raises(DBAPIError, match="question pairs must use v2 authority"):
        session.commit()
    session.rollback()


@pytest.mark.parametrize("source_kind", ("FORMAL_REFERENCE", "DEMO_LOCAL_IMPORTED_COPY"))
def test_populated_v2_identity_blocks_demo_0003_downgrade_before_ddl(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    source_kind: str,
) -> None:
    if source_kind == "FORMAL_REFERENCE":
        source_asset, formal_identity = _accepted_synthetic_source(session)
        authority_row = _insert_demo_row(
            session,
            DemoSyntheticIdentity,
            **_synthetic_admission_fields(
                session,
                source_asset,
                formal_identity,
                sequence=1,
                action="ADMIT",
                supersedes_id=None,
                config_marker="v2-downgrade-blocker",
            ),
        )
    else:
        _, authority_row = _insert_local_d02_identity(session, marker=f"local-downgrade-{new_id()}")
    authority_id = authority_row.id
    authority_digest = authority_row.content_digest
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _alembic_config(database_url)
    session.close()

    try:
        with pytest.raises(
            DBAPIError,
            match=(r"incompatible authority: identity=1, report=0, bank=0, pair=0"),
        ):
            command.downgrade(config, D02_DOWN_REVISION)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                DEMO_REVISION
            )
            assert connection.execute(
                text(
                    "SELECT content_digest, source_authority_kind "
                    "FROM demo_synthetic_identities WHERE id=:authority_id"
                ),
                {"authority_id": authority_id},
            ).one() == (authority_digest, source_kind)
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.columns "
                        "WHERE table_schema='public' "
                        "AND table_name='demo_synthetic_identities' "
                        "AND column_name='source_authority_key'"
                    )
                )
                == 1
            )
        engine.dispose()
    finally:
        command.upgrade(config, DEMO_REVISION)


def test_populated_report_authority_is_counted_before_any_downgrade_ddl(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_asset, admission = _insert_local_d02_identity(
        session, marker=f"report-only-downgrade-{new_id()}"
    )
    bank, _ = _insert_d02_question_bank(session, source_asset, admission)
    report_id = bank.screening_report_id
    report_digest = bank.screening_report_digest
    assert report_id is not None
    assert report_digest is not None

    session.execute(text("TRUNCATE demo_question_pairs, demo_question_banks CASCADE"))
    session.commit()
    assert session.scalar(text("SELECT count(*) FROM demo_pair_screening_reports")) == 1
    assert session.scalar(text("SELECT count(*) FROM demo_question_banks")) == 0
    assert session.scalar(text("SELECT count(*) FROM demo_question_pairs")) == 0

    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _alembic_config(database_url)
    session.close()

    try:
        with pytest.raises(
            DBAPIError,
            match=(r"incompatible authority: identity=5, report=1, bank=0, pair=0"),
        ):
            command.downgrade(config, D02_DOWN_REVISION)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                DEMO_REVISION
            )
            assert connection.execute(
                text(
                    "SELECT report_digest, status FROM demo_pair_screening_reports "
                    "WHERE id=:report_id"
                ),
                {"report_id": report_id},
            ).one() == (report_digest, "PASSED")
            assert (
                connection.scalar(text("SELECT to_regclass('public.demo_pair_screening_reports')"))
                == "demo_pair_screening_reports"
            )
        engine.dispose()
    finally:
        command.upgrade(config, DEMO_REVISION)


def test_populated_v2_bank_and_pairs_are_all_counted_before_any_downgrade_ddl(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_asset, admission = _insert_local_d02_identity(
        session, marker=f"bank-pair-downgrade-{new_id()}"
    )
    bank, pair = _insert_d02_question_bank(session, source_asset, admission)
    bank_id = bank.id
    bank_digest = bank.content_digest
    pair_id = pair.id
    pair_digest = pair.content_digest
    assert session.scalar(text("SELECT count(*) FROM demo_pair_screening_reports")) == 1
    assert session.scalar(text("SELECT count(*) FROM demo_question_banks")) == 1
    assert session.scalar(text("SELECT count(*) FROM demo_question_pairs")) == 16

    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _alembic_config(database_url)
    session.close()

    try:
        with pytest.raises(
            DBAPIError,
            match=(r"incompatible authority: identity=5, report=1, bank=1, pair=16"),
        ):
            command.downgrade(config, D02_DOWN_REVISION)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                DEMO_REVISION
            )
            assert (
                connection.scalar(
                    text("SELECT content_digest FROM demo_question_banks WHERE id=:bank_id"),
                    {"bank_id": bank_id},
                )
                == bank_digest
            )
            assert (
                connection.scalar(
                    text("SELECT content_digest FROM demo_question_pairs WHERE id=:pair_id"),
                    {"pair_id": pair_id},
                )
                == pair_digest
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_trigger "
                        "WHERE tgname IN ("
                        "'trg_demo_d02_question_bank_insert',"
                        "'trg_demo_d02_question_pair_insert',"
                        "'trg_demo_d02_complete_bank_demo_question_banks',"
                        "'trg_demo_d02_complete_bank_demo_question_pairs'"
                        ") AND NOT tgisinternal"
                    )
                )
                == 4
            )
        engine.dispose()
    finally:
        command.upgrade(config, DEMO_REVISION)


def test_screening_report_forgery_and_failed_report_bank_binding_fail_closed(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    report = graph["pair_screening_report"]
    bank = graph["bank"]

    forged_fields = _authority_fields(report)
    forged_fields["report_digest"] = hashlib.sha256(b"forged-report-digest").hexdigest()
    forged_report = _build_demo_row(
        DemoPairScreeningReport,
        row_id=_digest(
            "mirror.demo/D02PairScreeningReportId/v1",
            {"report_digest": forged_fields["report_digest"]},
        )[:32],
        authority_schema_version=report.schema_version,
        **forged_fields,
    )
    session.add(forged_report)
    with pytest.raises(DBAPIError, match="report fixed counts or digest are invalid"):
        session.commit()
    session.rollback()

    failed_report = _failed_report_from(report)
    session.add(failed_report)
    session.commit()
    assert failed_report.status == "FAILED"
    assert failed_report.selected_pair_count == 0

    failed_bank_fields = _authority_fields(bank)
    failed_bank_fields["version"] = f"failed-report-bank-{new_id()}"
    failed_bank_fields["algorithm_config_digest"] = hashlib.sha256(
        b"failed-report-bank"
    ).hexdigest()
    failed_bank_fields["screening_report_id"] = failed_report.id
    failed_bank_fields["screening_report_digest"] = failed_report.report_digest
    failed_bank_fields["pair_manifest_digest"] = "e" * 64
    failed_dimension_manifest = copy.deepcopy(bank.dimension_manifest)
    assert isinstance(failed_dimension_manifest, dict)
    failed_dimension_manifest["screening_report_id"] = failed_report.id
    failed_dimension_manifest["screening_report_digest"] = failed_report.report_digest
    failed_dimension_manifest["selected_pair_manifest_digest"] = "e" * 64
    failed_bank_fields["dimension_manifest"] = failed_dimension_manifest
    failed_bank_id = _digest(
        "mirror.demo/D02QuestionBankId/v1",
        {
            "algorithm_config_digest": failed_bank_fields["algorithm_config_digest"],
            "screening_report_digest": failed_report.report_digest,
            "screening_report_id": failed_report.id,
            "selected_pair_manifest_digest": "e" * 64,
        },
    )[:32]
    failed_bank = _build_demo_row(
        DemoQuestionBank,
        row_id=failed_bank_id,
        authority_schema_version="mirror.demo/DemoQuestionBank/v2",
        **failed_bank_fields,
    )
    session.add(failed_bank)
    with pytest.raises(DBAPIError, match="requires a PASSED screening report"):
        session.commit()
    session.rollback()


@pytest.mark.parametrize(
    ("attack", "expected_error"),
    (
        ("SCREENING_POLICY_ROOT", "screening policy root is not the accepted Revision 9 root"),
        ("NETWORK_BOOLEAN", "Revision 9 network boundary is invalid"),
        ("EXECUTION_FALSE", "M4 record or execution precondition is invalid"),
        ("MANUAL_BOOLEAN", "manual decision authority is invalid"),
        ("RAW_MEASUREMENT_BINDING", "source manifest does not match current local authority"),
    ),
)
def test_revision9_recanonicalized_report_attacks_fail_closed(
    session: Session,
    attack: str,
    expected_error: str,
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    report = graph["pair_screening_report"]
    report_payload = copy.deepcopy(report.report_payload)
    field_overrides: dict[str, Any] = {}

    if attack == "SCREENING_POLICY_ROOT":
        forged_root = hashlib.sha256(b"d02-forged-screening-policy-root").hexdigest()
        report_payload["schema_and_policy"]["screening_policy_digest"] = forged_root
        field_overrides["screening_policy_digest"] = forged_root
    elif attack == "NETWORK_BOOLEAN":
        report_payload["network_and_runtime_boundary"]["localhost_and_docker_internal_network"] = (
            "true"
        )
    elif attack == "EXECUTION_FALSE":
        execution_record = report_payload["m4_repeat_evidence"][0]
        execution_record["execution_succeeded"] = False
        _redigest_d02_record(execution_record)
    elif attack == "MANUAL_BOOLEAN":
        manual_record = report_payload["manual_review_evidence"][0]
        manual_record["background_seam"] = "false"
        _redigest_d02_record(manual_record, digest_key="manual_decision_digest")
    else:
        source_entry = report_payload["ordered_source_manifest"][0]
        source_entry["raw_measurement_authority_digest"] = hashlib.sha256(
            b"d02-forged-raw-measurement-authority"
        ).hexdigest()
        _redigest_d02_record(source_entry)
        source_manifest_digest = _digest(
            "mirror.demo/D02SourceAuthorityManifest/v1",
            report_payload["ordered_source_manifest"],
        )
        report_payload["schema_and_policy"]["source_manifest_digest"] = source_manifest_digest
        field_overrides["source_manifest_digest"] = source_manifest_digest

    attacked_report = _clone_d02_report(
        report,
        report_payload=report_payload,
        field_overrides=field_overrides,
    )
    session.add(attacked_report)
    with pytest.raises(DBAPIError, match=expected_error):
        session.commit()
    session.rollback()


def test_question_bank_rejects_recanonicalized_dimension_summary_forgery(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    original_bank = graph["bank"]
    dimension_manifest = copy.deepcopy(original_bank.dimension_manifest)
    dimension_manifest["selected_dimensions"][0]["sixteen_side_gate_digest"] = hashlib.sha256(
        b"d02-forged-sixteen-side-summary"
    ).hexdigest()
    forged_bank = _clone_v2_bank(
        original_bank,
        marker="dimension-summary-forgery",
        dimension_manifest=dimension_manifest,
    )
    session.add(forged_bank)
    with pytest.raises(DBAPIError, match="selected dimension authority is invalid"):
        session.flush()
    session.rollback()


def test_question_pair_rejects_recanonicalized_payload_not_in_report(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    original_bank = graph["bank"]
    original_pair = session.scalars(
        select(DemoQuestionPair)
        .where(DemoQuestionPair.question_bank_id == original_bank.id)
        .order_by(DemoQuestionPair.id)
    ).first()
    assert original_pair is not None

    cloned_bank = _clone_v2_bank(original_bank, marker="qa-structural-forgery")
    qa_payload = copy.deepcopy(original_pair.qa_payload)
    pair_payload = qa_payload["pair_screening_record_payload"]
    pair_payload["pair_quality_ppm"] = 999_999
    qa_payload["pair_screening_record_digest"] = _digest(
        "mirror.demo/D02PairScreeningRecord/v3", pair_payload
    )
    forged_pair = _clone_v2_pair(
        original_pair,
        question_bank_id=cloned_bank.id,
        qa_payload=qa_payload,
        field_overrides={"pair_quality_ppm": 999_999},
    )

    session.add(cloned_bank)
    session.flush()
    session.add(forged_pair)
    with pytest.raises(
        DBAPIError,
        match="question pair QA does not resolve one exact report record",
    ):
        session.flush()
    session.rollback()


@pytest.mark.parametrize(
    "failure_mode",
    ("MISSING_PAIR", "DUPLICATE_SIDE", "SWAPPED_SELECTED_RECORD"),
)
def test_complete_bank_rejects_incomplete_or_mismatched_selected_authority(
    session: Session, failure_mode: str
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    original_bank = graph["bank"]
    original_pairs = list(
        session.scalars(
            select(DemoQuestionPair)
            .where(DemoQuestionPair.question_bank_id == original_bank.id)
            .order_by(DemoQuestionPair.id)
        )
    )
    assert len(original_pairs) == 16
    bank = _clone_v2_bank(original_bank, marker=failure_mode.lower())

    pair_payloads = [copy.deepcopy(pair.qa_payload) for pair in original_pairs]
    pair_overrides: list[dict[str, Any]] = [{} for _ in original_pairs]
    selected_pairs = original_pairs
    if failure_mode == "MISSING_PAIR":
        selected_pairs = original_pairs[:-1]
        pair_payloads = pair_payloads[:-1]
        pair_overrides = pair_overrides[:-1]
    elif failure_mode == "DUPLICATE_SIDE":
        source_index = next(
            index
            for index in range(1, len(original_pairs))
            if original_pairs[index].demo_synthetic_identity_id
            == original_pairs[0].demo_synthetic_identity_id
        )
        duplicate_source = original_pairs[0]
        duplicate_side = pair_payloads[source_index]["pair_screening_record_payload"]["left"]
        source_side = duplicate_source.qa_payload["pair_screening_record_payload"]["left"]
        for key in (
            "result_asset_id",
            "result_asset_sha256",
            "asset_variant_id",
            "asset_variant_type",
            "lineage_digest",
        ):
            duplicate_side[key] = source_side[key]
        pair_overrides[source_index] = {
            "left_asset_id": duplicate_source.left_asset_id,
            "left_asset_sha256": duplicate_source.left_asset_sha256,
            "left_asset_variant_id": duplicate_source.left_asset_variant_id,
        }
    else:
        (
            pair_payloads[0]["pair_screening_record_digest"],
            pair_payloads[1]["pair_screening_record_digest"],
        ) = (
            pair_payloads[1]["pair_screening_record_digest"],
            pair_payloads[0]["pair_screening_record_digest"],
        )

    cloned_pairs = [
        _clone_v2_pair(
            pair,
            question_bank_id=bank.id,
            qa_payload=qa_payload,
            field_overrides=overrides,
        )
        for pair, qa_payload, overrides in zip(
            selected_pairs, pair_payloads, pair_overrides, strict=True
        )
    ]
    session.add(bank)
    session.add_all(cloned_pairs)
    expected_failure = (
        "not the complete selected 16-pair authority"
        if failure_mode == "MISSING_PAIR"
        else "question pair QA does not resolve one exact report record"
    )
    with pytest.raises(DBAPIError, match=expected_failure):
        session.commit()
    session.rollback()


def test_populated_legacy_v1_round_trip_is_byte_exact_and_formal_ddl_is_unchanged(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    assert formal_identity.accepted_qa_run_id is not None
    accepted_qa_snapshot_digest = session.scalar(
        text("SELECT mirror_demo_formal_qa_snapshot_digest(:qa_run_id)"),
        {"qa_run_id": formal_identity.accepted_qa_run_id},
    )
    assert isinstance(accepted_qa_snapshot_digest, str)
    left_asset, left_variant = _result_variant(
        session,
        source_asset,
        sha=hashlib.sha256(b"legacy-v1-left").hexdigest(),
        variant_type="demo_p3_p7_question_left",
    )
    right_asset, right_variant = _result_variant(
        session,
        source_asset,
        sha=hashlib.sha256(b"legacy-v1-right").hexdigest(),
        variant_type="demo_p3_p7_question_right",
    )
    source_identity_id = formal_identity.id
    source_asset_id = source_asset.id
    source_asset_sha256 = source_asset.sha256
    accepted_qa_run_id = formal_identity.accepted_qa_run_id
    left_asset_id = left_asset.id
    left_asset_sha256 = left_asset.sha256
    left_variant_id = left_variant.id
    right_asset_id = right_asset.id
    right_asset_sha256 = right_asset.sha256
    right_variant_id = right_variant.id
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _alembic_config(database_url)
    session.close()

    try:
        command.downgrade(config, D02_DOWN_REVISION)
        engine = create_engine(database_url)
        with engine.begin() as connection:
            formal_ddl_before = _formal_table_ddl_signature(connection)
            identity_id, bank_id, pair_id = _insert_legacy_v1_graph(
                connection,
                source_identity_id=source_identity_id,
                source_asset_id=source_asset_id,
                source_asset_sha256=source_asset_sha256,
                accepted_qa_run_id=accepted_qa_run_id,
                accepted_qa_snapshot_digest=accepted_qa_snapshot_digest,
                left_asset_id=left_asset_id,
                left_asset_sha256=left_asset_sha256,
                left_variant_id=left_variant_id,
                right_asset_id=right_asset_id,
                right_asset_sha256=right_asset_sha256,
                right_variant_id=right_variant_id,
            )
            before_rows = {
                "identity": _row_json(connection, "demo_synthetic_identities", identity_id),
                "bank": _row_json(connection, "demo_question_banks", bank_id),
                "pair": _row_json(connection, "demo_question_pairs", pair_id),
            }
        engine.dispose()

        command.upgrade(config, DEMO_REVISION)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            first_source_key = connection.scalar(
                text(
                    "SELECT source_authority_key FROM demo_synthetic_identities "
                    "WHERE id=:identity_id"
                ),
                {"identity_id": identity_id},
            )
            formal_ddl_after_upgrade = _formal_table_ddl_signature(connection)
        engine.dispose()
        assert isinstance(first_source_key, str)
        assert formal_ddl_after_upgrade == formal_ddl_before

        command.downgrade(config, D02_DOWN_REVISION)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            after_rows = {
                "identity": _row_json(connection, "demo_synthetic_identities", identity_id),
                "bank": _row_json(connection, "demo_question_banks", bank_id),
                "pair": _row_json(connection, "demo_question_pairs", pair_id),
            }
            formal_ddl_after_downgrade = _formal_table_ddl_signature(connection)
        engine.dispose()
        assert after_rows == before_rows
        assert formal_ddl_after_downgrade == formal_ddl_before

        command.upgrade(config, DEMO_REVISION)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            second_source_key = connection.scalar(
                text(
                    "SELECT source_authority_key FROM demo_synthetic_identities "
                    "WHERE id=:identity_id"
                ),
                {"identity_id": identity_id},
            )
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                DEMO_REVISION
            )
        engine.dispose()
        assert second_source_key == first_source_key
    finally:
        command.upgrade(config, DEMO_REVISION)
