"""Add the D02 autonomous source acquisition budget pool.

Revision ID: demo_0015_d02_source_acq_pool
Revises: demo_0014_d02_r2_e3_versioning
Create Date: 2026-08-31

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
FORWARD_REPAIR_ONLY: TRUE
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0015_d02_source_acq_pool"
down_revision: str | None = "demo_0014_d02_r2_e3_versioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
FORWARD_REPAIR_ONLY = True

_GENERIC_SOURCE = "mirror.demo/D02GenericSourceAuthorityRecord/v1"
_GENERIC_IDENTITY = "mirror.demo/DemoSyntheticIdentity/v5"
_GENERIC_ADMISSION = "mirror.demo/D02GenericAdmission/v1"

_R2_SOURCE_KEY_CALLED_ON_NULL_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_r2_source_authority_key(
    source_output_id text, source_asset_id text, source_asset_sha256 text,
    source_generation_receipt_digest text, source_authority_digest text
) RETURNS text LANGUAGE sql IMMUTABLE CALLED ON NULL INPUT PARALLEL SAFE AS $function$
    SELECT mirror_demo_digest('mirror.demo/D02R2SourceAuthorityKey/v1', jsonb_build_object(
        'authority_kind', 'DEMO_R2_GENERATED_SOURCE',
        'source_output_id', source_output_id, 'source_asset_id', source_asset_id,
        'source_asset_sha256', source_asset_sha256,
        'source_generation_receipt_digest', source_generation_receipt_digest,
        'authority_digest', source_authority_digest));
$function$;
"""

_R2_SOURCE_KEY_STRICT_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_r2_source_authority_key(
    source_output_id text, source_asset_id text, source_asset_sha256 text,
    source_generation_receipt_digest text, source_authority_digest text
) RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $function$
    SELECT mirror_demo_digest('mirror.demo/D02R2SourceAuthorityKey/v1', jsonb_build_object(
        'authority_kind', 'DEMO_R2_GENERATED_SOURCE',
        'source_output_id', source_output_id, 'source_asset_id', source_asset_id,
        'source_asset_sha256', source_asset_sha256,
        'source_generation_receipt_digest', source_generation_receipt_digest,
        'authority_digest', source_authority_digest));
$function$;
"""


def _authority_projection_sql(*, include_generic_identity: bool) -> str:
    generic_identity_projection = (
        r"""
    IF authority_table = 'demo_synthetic_identities'
       AND row_data ->> 'schema_version' =
           'mirror.demo/DemoSyntheticIdentity/v5' THEN
        projected := projected || jsonb_build_object(
            'source_authority_kind', 'DEMO_R2_GENERATED_SOURCE',
            'source_authority_key', mirror_demo_r2_source_authority_key(
                row_data ->> 'source_output_id',
                row_data ->> 'formal_canonical_asset_id',
                row_data ->> 'formal_canonical_asset_sha256',
                row_data ->> 'source_receipt_digest',
                row_data ->> 'source_authority_digest'
            )
        );
    END IF;
"""
        if include_generic_identity
        else ""
    )
    return rf"""
CREATE OR REPLACE FUNCTION mirror_demo_authority_projection(
    row_data jsonb,
    authority_table text
)
RETURNS jsonb
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    projected jsonb;
    timestamp_key text;
BEGIN
    projected := row_data - ARRAY[
        'id',
        'schema_version',
        'canonical_payload',
        'content_digest',
        'created_at',
        'closed_at',
        'tombstoned_at'
    ]::text[];

    FOREACH timestamp_key IN ARRAY ARRAY[
        'authority_at',
        'expires_at',
        'occurred_at',
        'context_as_of_time'
    ]::text[] LOOP
        IF projected ? timestamp_key AND projected -> timestamp_key <> 'null'::jsonb THEN
            projected := jsonb_set(
                projected,
                ARRAY[timestamp_key],
                to_jsonb(
                    to_char(
                        (projected ->> timestamp_key)::timestamptz AT TIME ZONE 'UTC',
                        'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                    )
                ),
                false
            );
        END IF;
    END LOOP;
    IF authority_table = 'demo_synthetic_identities'
       AND row_data ->> 'schema_version' IN (
           'mirror.demo/DemoSyntheticIdentity/v1',
           'mirror.demo/DemoSyntheticIdentity/v2',
           'mirror.demo/DemoSyntheticIdentity/v3'
       ) THEN
        projected := projected - 'r2_source_authority_record_id';
    END IF;
    IF authority_table = 'demo_pair_screening_reports'
       AND row_data ->> 'schema_version' IN (
           'mirror.demo/D02PairScreeningReport/v1',
           'mirror.demo/D02PairScreeningReport/v2'
       ) THEN
        projected := projected - ARRAY[
            'measurement_gate_count',
            'decode_structure_record_count'
        ]::text[];
    END IF;
    IF authority_table = 'demo_pair_screening_reports'
       AND row_data ->> 'schema_version' IN (
           'mirror.demo/D02PairScreeningReport/v3',
           'mirror.demo/D02GenericPairScreeningReport/v1'
       ) THEN
        projected := projected - 'report_digest';
    END IF;
    IF authority_table = 'demo_face_observations'
       AND row_data ->> 'schema_version' = 'mirror.demo/DemoFaceObservation/v1' THEN
        projected := projected - 'analysis_run_id';
    END IF;
{generic_identity_projection}
    IF authority_table NOT LIKE 'demo\_%' ESCAPE E'\\' THEN
        RAISE EXCEPTION 'Demo authority projection rejected unexpected table %', authority_table;
    END IF;
    RETURN projected;
END;
$function$;
"""


_GENERIC_WRITE_VERSION_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_write_version_v11()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE report_schema text; identity_schema text;
BEGIN
    IF TG_TABLE_NAME = 'demo_synthetic_identities' THEN
      IF NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v5'
       AND NEW.r2_source_authority_record_id IS NOT NULL
       AND NEW.formal_synthetic_identity_id IS NULL THEN
        RETURN NEW; END IF;
      IF NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v4' THEN RETURN NEW; END IF;
      IF NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v3'
       AND NEW.formal_synthetic_identity_id IS NULL THEN
        RETURN NEW; END IF;
      IF NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v2'
       AND NEW.formal_synthetic_identity_id IS NOT NULL THEN
        RETURN NEW; END IF;
      RAISE EXCEPTION 'New Demo synthetic identity event uses an unsupported authority version';
    ELSIF TG_TABLE_NAME = 'demo_pair_screening_reports' THEN
      IF NEW.schema_version = 'mirror.demo/D02GenericPairScreeningReport/v1' THEN RETURN NEW; END IF;
      IF NEW.schema_version = 'mirror.demo/D02PairScreeningReport/v3' THEN
        IF NEW.measurement_gate_count IS DISTINCT FROM 48 OR NEW.decode_structure_record_count IS DISTINCT FROM 48 THEN RAISE EXCEPTION 'D02 R2 Report v3 counts are invalid'; END IF;
        RETURN NEW;
      END IF;
      IF NEW.schema_version = 'mirror.demo/D02PairScreeningReport/v2' THEN RETURN NEW; END IF;
      RAISE EXCEPTION 'New D02 screening reports use an unsupported authority version';
    ELSIF TG_TABLE_NAME = 'demo_question_banks' THEN
      IF NEW.schema_version = 'mirror.demo/D02GenericQuestionBank/v1' THEN
        SELECT schema_version INTO report_schema FROM demo_pair_screening_reports WHERE id = NEW.screening_report_id AND report_digest = NEW.screening_report_digest;
        IF report_schema = 'mirror.demo/D02GenericPairScreeningReport/v1' THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'Generic question bank must bind generic Report authority';
      END IF;
      IF NEW.schema_version NOT IN ('mirror.demo/DemoQuestionBank/v2','mirror.demo/DemoQuestionBank/v3') THEN RAISE EXCEPTION 'New Demo question banks use an unsupported authority version'; END IF;
      SELECT schema_version INTO report_schema FROM demo_pair_screening_reports WHERE id = NEW.screening_report_id AND report_digest = NEW.screening_report_digest;
      IF report_schema IS DISTINCT FROM (CASE WHEN NEW.schema_version = 'mirror.demo/DemoQuestionBank/v3' THEN 'mirror.demo/D02PairScreeningReport/v3' ELSE 'mirror.demo/D02PairScreeningReport/v2' END) THEN RAISE EXCEPTION 'D02 v10 question bank must bind matching Report authority'; END IF;
      RETURN NEW;
    ELSIF TG_TABLE_NAME = 'demo_question_pairs' THEN
      IF NEW.schema_version = 'mirror.demo/D02GenericQuestionPair/v1' THEN
        SELECT schema_version INTO report_schema FROM demo_pair_screening_reports WHERE id = NEW.screening_report_id AND report_digest = NEW.screening_report_digest;
        SELECT schema_version INTO identity_schema FROM demo_synthetic_identities WHERE id = NEW.demo_synthetic_identity_id;
        IF report_schema = 'mirror.demo/D02GenericPairScreeningReport/v1' AND identity_schema = 'mirror.demo/DemoSyntheticIdentity/v5' THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'Generic question pair requires generic Report and Identity authority';
      END IF;
      IF NEW.schema_version NOT IN ('mirror.demo/DemoQuestionPair/v2','mirror.demo/DemoQuestionPair/v3') THEN RAISE EXCEPTION 'New Demo question pairs use an unsupported authority version'; END IF;
      SELECT schema_version INTO report_schema FROM demo_pair_screening_reports WHERE id = NEW.screening_report_id AND report_digest = NEW.screening_report_digest;
      SELECT schema_version INTO identity_schema FROM demo_synthetic_identities WHERE id = NEW.demo_synthetic_identity_id;
      IF report_schema IS DISTINCT FROM (CASE WHEN NEW.schema_version = 'mirror.demo/DemoQuestionPair/v3' THEN 'mirror.demo/D02PairScreeningReport/v3' ELSE 'mirror.demo/D02PairScreeningReport/v2' END) OR identity_schema IS DISTINCT FROM (CASE WHEN NEW.schema_version = 'mirror.demo/DemoQuestionPair/v3' THEN 'mirror.demo/DemoSyntheticIdentity/v4' ELSE 'mirror.demo/DemoSyntheticIdentity/v3' END) THEN RAISE EXCEPTION 'D02 v10 pair requires matching Report and Identity authority'; END IF;
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'D02 v11 write-version guard attached to unknown table';
END;
$function$;
"""


def _install_generic_write_guard() -> None:
    op.execute("DROP TRIGGER trg_demo_d02_write_version_v10_identity ON demo_synthetic_identities")
    for table, suffix in (
        ("demo_pair_screening_reports", "report"),
        ("demo_question_banks", "bank"),
        ("demo_question_pairs", "pair"),
    ):
        op.execute(f"DROP TRIGGER trg_demo_d02_write_version_v10_{suffix} ON {table}")
    op.execute(_GENERIC_WRITE_VERSION_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_d02_write_version_v11_identity "
        "BEFORE INSERT ON demo_synthetic_identities FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_write_version_v11()"
    )
    for table, suffix in (
        ("demo_pair_screening_reports", "report"),
        ("demo_question_banks", "bank"),
        ("demo_question_pairs", "pair"),
    ):
        op.execute(
            f"CREATE TRIGGER trg_demo_d02_write_version_v11_{suffix} BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_write_version_v11()"
        )


def _restore_write_guard_v10() -> None:
    op.execute("DROP TRIGGER trg_demo_d02_write_version_v11_identity ON demo_synthetic_identities")
    for table, suffix in (
        ("demo_pair_screening_reports", "report"),
        ("demo_question_banks", "bank"),
        ("demo_question_pairs", "pair"),
    ):
        op.execute(f"DROP TRIGGER trg_demo_d02_write_version_v11_{suffix} ON {table}")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_write_version_v11()")
    op.execute(
        "CREATE TRIGGER trg_demo_d02_write_version_v10_identity "
        "BEFORE INSERT ON demo_synthetic_identities FOR EACH ROW EXECUTE FUNCTION "
        "mirror_demo_validate_d02_write_version_v10()"
    )
    for table, suffix in (
        ("demo_pair_screening_reports", "report"),
        ("demo_question_banks", "bank"),
        ("demo_question_pairs", "pair"),
    ):
        op.execute(
            f"CREATE TRIGGER trg_demo_d02_write_version_v10_{suffix} BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_write_version_v10()"
        )


_BUDGET_CONSISTENCY_TRIGGER_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_budget_consistency()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    run_id text;
    expected_budget integer;
BEGIN
    IF TG_TABLE_NAME = 'demo_d02_source_acquisition_runs' THEN
        run_id := NEW.id;
    ELSE
        run_id := NEW.acquisition_run_id;
    END IF;
    SELECT count(*) INTO expected_budget
      FROM demo_d02_source_acquisition_events
     WHERE acquisition_run_id = run_id AND event_kind = 'CALL_STARTED';
    IF (SELECT budget_consumed FROM demo_d02_source_acquisition_runs WHERE id = run_id)
       IS DISTINCT FROM expected_budget THEN
        RAISE EXCEPTION 'D02 budget projection disagrees with CALL_STARTED authority';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM demo_d02_source_acquisition_runs run
        WHERE run.id = run_id
          AND run.run_state IN ('MANIFEST_FINALIZED','ADMITTED')
          AND NOT EXISTS (
              SELECT 1
              FROM demo_d02_selected_source_manifests manifest
              WHERE manifest.acquisition_run_id = run.id
                AND manifest.cohort_spec_id = run.cohort_spec_id
                AND manifest.manifest_state = 'FINALIZED'
          )
    ) THEN
        RAISE EXCEPTION 'D02 finalized run is missing its selected manifest';
    END IF;
    RETURN NULL;
END;
$function$;
"""

_GENERIC_IDENTITY_TRIGGER_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_generic_identity()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    source_row demo_d02_r2_source_authorities%ROWTYPE;
    manifest_row demo_d02_selected_source_manifests%ROWTYPE;
    expected_key text;
    expected_payload jsonb;
BEGIN
    IF NEW.schema_version IS DISTINCT FROM 'mirror.demo/DemoSyntheticIdentity/v5' THEN
        RETURN NEW;
    END IF;
    SELECT * INTO source_row FROM demo_d02_r2_source_authorities
     WHERE id = NEW.r2_source_authority_record_id;
    SELECT * INTO manifest_row FROM demo_d02_selected_source_manifests
     WHERE id = source_row.selected_source_manifest_id;
    expected_key := mirror_demo_r2_source_authority_key(
        NEW.source_output_id, NEW.formal_canonical_asset_id,
        NEW.formal_canonical_asset_sha256, NEW.source_receipt_digest,
        NEW.source_authority_digest
    );
    IF NOT FOUND
       OR source_row.schema_version IS DISTINCT FROM 'mirror.demo/D02GenericSourceAuthorityRecord/v1'
       OR manifest_row.manifest_state IS DISTINCT FROM 'FINALIZED'
       OR NEW.source_output_id IS DISTINCT FROM source_row.source_output_id
       OR NEW.formal_canonical_asset_id IS DISTINCT FROM source_row.source_asset_id
       OR NEW.formal_canonical_asset_sha256 IS DISTINCT FROM source_row.source_asset_sha256
       OR NEW.source_receipt_digest IS NOT NULL
       OR NEW.source_authority_digest IS DISTINCT FROM source_row.source_authority_digest
       OR NEW.source_qa_snapshot_digest IS DISTINCT FROM source_row.source_qa_snapshot_digest
       OR NEW.source_provenance_digest IS DISTINCT FROM source_row.source_provenance_digest
       OR NEW.adult_synthetic_attested IS DISTINCT FROM source_row.adult_synthetic_attested
       OR NEW.admission_config_digest IS DISTINCT FROM source_row.execution_contract_digest
       OR NEW.import_config_digest IS DISTINCT FROM source_row.execution_contract_digest
       OR expected_key IS DISTINCT FROM source_row.source_authority_key THEN
        RAISE EXCEPTION 'D02 generic identity/source binding is invalid';
    END IF;
    PERFORM pg_advisory_xact_lock(
        hashtextextended('mirror.demo.synthetic-admission-v5/' || expected_key, 0)
    );
    IF NEW.admission_sequence IS DISTINCT FROM 1 OR NEW.admission_action IS DISTINCT FROM 'ADMIT'
       OR NEW.supersedes_id IS NOT NULL OR EXISTS (
           SELECT 1 FROM demo_synthetic_identities
           WHERE source_authority_key = expected_key
       ) THEN
        RAISE EXCEPTION 'First D02 generic source event must be ADMIT';
    END IF;
    expected_payload := mirror_demo_authority_projection(
        to_jsonb(NEW) || jsonb_build_object(
            'source_authority_kind', 'DEMO_R2_GENERATED_SOURCE',
            'source_authority_key', expected_key
        ), TG_TABLE_NAME
    );
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload
       OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected_payload)
       OR NEW.id IS DISTINCT FROM substring(mirror_demo_digest(
           'mirror.demo/DemoSyntheticIdentityAdmissionEventId/v4',
           jsonb_build_object(
               'source_authority_kind', 'DEMO_R2_GENERATED_SOURCE',
               'source_authority_key', expected_key,
               'r2_source_authority_record_id', NEW.r2_source_authority_record_id,
               'admission_sequence', NEW.admission_sequence,
               'admission_action', NEW.admission_action,
               'supersedes_id', NEW.supersedes_id,
               'admission_config_digest', NEW.admission_config_digest,
               'canonical_payload_digest', NEW.content_digest
           )) FROM 1 FOR 32) THEN
        RAISE EXCEPTION 'D02 generic identity canonical authority is invalid';
    END IF;
    RETURN NEW;
END;
$function$;
"""

_ACQUISITION_TRIGGER_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_acquisition_row()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    expected_schema text;
    expected_payload jsonb;
    spec_row demo_d02_cohort_specs%ROWTYPE;
    run_row demo_d02_source_acquisition_runs%ROWTYPE;
    candidate_count integer;
    distinct_candidate_count integer;
    distinct_slot_count integer;
    distinct_family_count integer;
    started_count integer;
    terminal_count integer;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'D02 acquisition authority is not deletable';
    END IF;
    expected_schema := CASE TG_TABLE_NAME
        WHEN 'demo_d02_cohort_specs' THEN 'mirror.demo/D02CohortSpec/v1'
        WHEN 'demo_d02_source_acquisition_runs' THEN
            'mirror.demo/D02SourceAcquisitionRun/v1'
        WHEN 'demo_d02_source_acquisition_events' THEN
            'mirror.demo/D02SourceAcquisitionEvent/v1'
        WHEN 'demo_d02_source_candidates' THEN 'mirror.demo/D02SourceCandidate/v1'
        WHEN 'demo_d02_selected_source_manifests' THEN
            'mirror.demo/D02SelectedSourceManifest/v1'
        ELSE NULL
    END;
    IF expected_schema IS NULL OR NEW.schema_version IS DISTINCT FROM expected_schema THEN
        RAISE EXCEPTION 'D02 acquisition schema is unsupported';
    END IF;
    expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload
       OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected_payload)
    THEN
        RAISE EXCEPTION 'D02 acquisition canonical authority is invalid';
    END IF;

    IF TG_TABLE_NAME IN (
        'demo_d02_cohort_specs',
        'demo_d02_source_acquisition_events',
        'demo_d02_selected_source_manifests'
    ) AND TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'D02 acquisition authority row is append-only';
    END IF;

    IF TG_TABLE_NAME = 'demo_d02_cohort_specs' THEN
        RETURN NEW;
    END IF;

    SELECT * INTO spec_row FROM demo_d02_cohort_specs WHERE id = NEW.cohort_spec_id;
    IF NOT FOUND OR spec_row.schema_version IS DISTINCT FROM 'mirror.demo/D02CohortSpec/v1'
       OR spec_row.spec_state IS DISTINCT FROM 'REGISTERED' THEN
        RAISE EXCEPTION 'D02 acquisition spec is not registered';
    END IF;

    IF TG_TABLE_NAME = 'demo_d02_source_acquisition_runs' THEN
        IF TG_OP = 'UPDATE' THEN
            IF NEW.id IS DISTINCT FROM OLD.id
               OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
               OR NEW.cohort_spec_id IS DISTINCT FROM OLD.cohort_spec_id
               OR NEW.run_key_digest IS DISTINCT FROM OLD.run_key_digest
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.budget_consumed < OLD.budget_consumed
               OR NEW.budget_consumed > OLD.budget_consumed + 1
               OR NEW.accepted_count < OLD.accepted_count
               OR NEW.content_review_epoch < OLD.content_review_epoch THEN
                RAISE EXCEPTION 'D02 acquisition run projection regressed';
            END IF;
            IF NOT (
                (OLD.run_state = 'ACTIVE' AND NEW.run_state IN (
                    'ACTIVE','PAUSED_INFRASTRUCTURE','PAUSED_CONTENT_REVIEW',
                    'MANIFEST_FINALIZED','FAILED_CLOSED'
                )) OR
                (OLD.run_state = 'PAUSED_INFRASTRUCTURE' AND NEW.run_state IN (
                    'ACTIVE','PAUSED_CONTENT_REVIEW','FAILED_CLOSED'
                )) OR
                (OLD.run_state = 'PAUSED_CONTENT_REVIEW' AND NEW.run_state IN (
                    'ACTIVE','FAILED_CLOSED'
                )) OR
                (OLD.run_state = 'MANIFEST_FINALIZED' AND NEW.run_state IN (
                    'MANIFEST_FINALIZED','ADMITTED'
                )) OR
                (OLD.run_state = NEW.run_state AND OLD.run_state IN ('ADMITTED','FAILED_CLOSED'))
            ) THEN
                RAISE EXCEPTION 'D02 acquisition run state transition is invalid';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO run_row FROM demo_d02_source_acquisition_runs
    WHERE id = NEW.acquisition_run_id FOR UPDATE;
    IF NOT FOUND OR run_row.cohort_spec_id IS DISTINCT FROM NEW.cohort_spec_id THEN
        RAISE EXCEPTION 'D02 acquisition run/spec binding is invalid';
    END IF;

    IF TG_TABLE_NAME = 'demo_d02_source_acquisition_events' THEN
        IF run_row.run_state = 'FAILED_CLOSED' AND (
            NEW.event_kind IS DISTINCT FROM 'RUN_FAILED_CLOSED' OR EXISTS (
                SELECT 1 FROM demo_d02_source_acquisition_events terminal
                WHERE terminal.acquisition_run_id = NEW.acquisition_run_id
                  AND terminal.event_kind = 'RUN_FAILED_CLOSED'
            )
        ) THEN
            RAISE EXCEPTION 'D02 failed run is terminal';
        END IF;
        IF run_row.run_state = 'ADMITTED' AND (
            NEW.event_kind IS DISTINCT FROM 'ADMISSION_COMPLETED' OR EXISTS (
                SELECT 1 FROM demo_d02_source_acquisition_events terminal
                WHERE terminal.acquisition_run_id = NEW.acquisition_run_id
                  AND terminal.event_kind = 'ADMISSION_COMPLETED'
            )
        ) THEN
            RAISE EXCEPTION 'D02 admitted run is terminal';
        END IF;
        IF NEW.event_sequence IS DISTINCT FROM COALESCE((
            SELECT max(event_sequence) + 1
            FROM demo_d02_source_acquisition_events
            WHERE acquisition_run_id = NEW.acquisition_run_id
        ), 1) THEN
            RAISE EXCEPTION 'D02 acquisition event sequence is not contiguous';
        END IF;
        IF NEW.event_kind = 'CALL_STARTED' AND (
            run_row.run_state IS DISTINCT FROM 'ACTIVE'
            OR run_row.open_call_ordinal IS DISTINCT FROM NEW.provider_ordinal
            OR run_row.open_selector_slot_id IS DISTINCT FROM NEW.selector_slot_id
            OR run_row.budget_consumed IS DISTINCT FROM NEW.provider_ordinal
            OR EXISTS (
                SELECT 1 FROM demo_d02_source_candidates candidate
                WHERE candidate.acquisition_run_id = NEW.acquisition_run_id
                  AND candidate.candidate_state IN (
                      'PRIMARY_DURABLE','DURABLE','M3_SUPPORTED'
                  )
            )
            OR NEW.provider_ordinal IS DISTINCT FROM COALESCE((
                SELECT count(*) + 1
                FROM demo_d02_source_acquisition_events started
                WHERE started.acquisition_run_id = NEW.acquisition_run_id
                  AND started.event_kind = 'CALL_STARTED'
            ), 1)
        ) THEN
            RAISE EXCEPTION 'D02 CALL_STARTED does not bind the locked run projection';
        END IF;
        IF NEW.provider_ordinal IS NOT NULL AND NEW.event_kind <> 'CALL_STARTED'
           AND NOT EXISTS (
               SELECT 1 FROM demo_d02_source_acquisition_events started
               WHERE started.acquisition_run_id = NEW.acquisition_run_id
                 AND started.provider_ordinal = NEW.provider_ordinal
                 AND started.event_kind = 'CALL_STARTED'
                 AND started.content_digest = NEW.call_started_event_digest
           ) THEN
            RAISE EXCEPTION 'D02 event does not have a CALL_STARTED authority';
        END IF;
        IF NEW.event_kind = 'TRANCHE_RECONCILED' THEN
            SELECT count(*), count(DISTINCT terminal.provider_ordinal)
              INTO started_count, terminal_count
            FROM demo_d02_source_acquisition_events started
            LEFT JOIN demo_d02_source_acquisition_events terminal
              ON terminal.acquisition_run_id = started.acquisition_run_id
             AND terminal.provider_ordinal = started.provider_ordinal
             AND terminal.event_kind IN (
                 'CALL_CONSUMED_NO_RESULT','PROVIDER_OUTCOME_UNCERTAIN',
                 'MATERIALIZATION_FAILED','M3_UNSUPPORTED','QA_ACCEPTED','QA_REJECTED'
             )
            WHERE started.acquisition_run_id = NEW.acquisition_run_id
              AND started.event_kind = 'CALL_STARTED'
              AND started.provider_ordinal BETWEEN ((NEW.tranche_number - 1) * 10 + 1)
                                               AND (NEW.tranche_number * 10);
            IF started_count IS DISTINCT FROM 10 OR terminal_count IS DISTINCT FROM 10 THEN
                RAISE EXCEPTION 'D02 tranche is missing terminal outcomes';
            END IF;
        END IF;
        IF NEW.candidate_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM demo_d02_source_candidates candidate
            WHERE candidate.id = NEW.candidate_id
              AND candidate.acquisition_run_id = NEW.acquisition_run_id
              AND candidate.cohort_spec_id = NEW.cohort_spec_id
              AND candidate.provider_ordinal = NEW.provider_ordinal
              AND candidate.selector_slot_id = NEW.selector_slot_id
        ) THEN
            RAISE EXCEPTION 'D02 event candidate binding is invalid';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_TABLE_NAME = 'demo_d02_source_candidates' THEN
        IF NOT EXISTS (
            SELECT 1 FROM demo_d02_source_acquisition_events started
            WHERE started.acquisition_run_id = NEW.acquisition_run_id
              AND started.provider_ordinal = NEW.provider_ordinal
              AND started.selector_slot_id = NEW.selector_slot_id
              AND started.event_kind = 'CALL_STARTED'
              AND started.content_digest = NEW.call_started_event_digest
        ) THEN
            RAISE EXCEPTION 'D02 candidate does not bind a consumed call';
        END IF;
        IF TG_OP = 'UPDATE' THEN
            IF NEW.id IS DISTINCT FROM OLD.id
               OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
               OR NEW.acquisition_run_id IS DISTINCT FROM OLD.acquisition_run_id
               OR NEW.cohort_spec_id IS DISTINCT FROM OLD.cohort_spec_id
               OR NEW.provider_ordinal IS DISTINCT FROM OLD.provider_ordinal
               OR NEW.selector_slot_id IS DISTINCT FROM OLD.selector_slot_id
               OR NEW.call_started_event_digest IS DISTINCT FROM OLD.call_started_event_digest
               OR NEW.output_id IS DISTINCT FROM OLD.output_id
               OR NEW.provider_result_digest IS DISTINCT FROM OLD.provider_result_digest
               OR NEW.durable_primary_sha256 IS DISTINCT FROM OLD.durable_primary_sha256
               OR (NEW.durable_backup_sha256 IS DISTINCT FROM OLD.durable_backup_sha256
                   AND NOT (OLD.candidate_state = 'PRIMARY_DURABLE'
                            AND NEW.candidate_state = 'DURABLE'
                            AND OLD.durable_backup_sha256 IS NULL
                            AND NEW.durable_backup_sha256 = NEW.durable_primary_sha256))
               OR NEW.durable_byte_size IS DISTINCT FROM OLD.durable_byte_size
               OR NEW.durable_media_type IS DISTINCT FROM OLD.durable_media_type
               OR NEW.durable_width IS DISTINCT FROM OLD.durable_width
               OR NEW.durable_height IS DISTINCT FROM OLD.durable_height
               OR NEW.declared_age_band IS DISTINCT FROM OLD.declared_age_band
               OR NEW.synthetic_only_attested IS DISTINCT FROM OLD.synthetic_only_attested
               OR NEW.real_person_reference_used IS DISTINCT FROM OLD.real_person_reference_used
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'D02 candidate immutable authority changed';
            END IF;
            IF NOT (
                (OLD.candidate_state = 'PRIMARY_DURABLE' AND NEW.candidate_state = 'DURABLE') OR
                (OLD.candidate_state = 'DURABLE' AND NEW.candidate_state IN (
                    'M3_SUPPORTED','QA_REJECTED'
                )) OR
                (OLD.candidate_state = 'M3_SUPPORTED' AND NEW.candidate_state IN (
                    'QA_ACCEPTED','QA_REJECTED'
                ))
            ) THEN
                RAISE EXCEPTION 'D02 candidate state transition is invalid';
            END IF;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_TABLE_NAME = 'demo_d02_selected_source_manifests' THEN
        IF run_row.run_state NOT IN ('MANIFEST_FINALIZED','ADMITTED')
           OR run_row.accepted_count IS DISTINCT FROM 4 THEN
            RAISE EXCEPTION 'D02 selected manifest run is not finalized';
        END IF;
        IF NEW.generation_policy_digest IS DISTINCT FROM spec_row.generation_policy_digest THEN
            RAISE EXCEPTION 'D02 selected manifest policy is unregistered';
        END IF;
        SELECT count(*), count(DISTINCT candidate.id),
               count(DISTINCT candidate.selector_slot_id),
               count(DISTINCT candidate.identity_family_digest)
          INTO candidate_count, distinct_candidate_count, distinct_slot_count,
               distinct_family_count
        FROM jsonb_array_elements_text(NEW.ordered_candidate_ids) WITH ORDINALITY entry(id, position)
        JOIN demo_d02_source_candidates candidate ON candidate.id = entry.id
        WHERE candidate.acquisition_run_id = NEW.acquisition_run_id
          AND candidate.cohort_spec_id = NEW.cohort_spec_id
          AND candidate.qa_state = 'ACCEPTED'
          AND candidate.candidate_state = 'QA_ACCEPTED';
        IF candidate_count IS DISTINCT FROM 4
           OR distinct_candidate_count IS DISTINCT FROM 4
           OR distinct_slot_count IS DISTINCT FROM 4
           OR distinct_family_count IS DISTINCT FROM 4 THEN
            RAISE EXCEPTION 'D02 selected manifest candidates are invalid';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'D02 acquisition trigger routing failed';
END;
$function$;
"""

_SOURCE_TRIGGER_V4_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_source_authority()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    expected_id text;
    source_asset assets%ROWTYPE;
    expected_payload jsonb;
    id_preimage jsonb;
    candidate_row demo_d02_source_candidates%ROWTYPE;
    manifest_row demo_d02_selected_source_manifests%ROWTYPE;
    spec_row demo_d02_cohort_specs%ROWTYPE;
BEGIN
    IF TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'D02 R2 supporting row is append-only';
    END IF;
    IF NEW.schema_version NOT IN (
        'mirror.demo/D02R2SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1',
        'mirror.demo/D02GenericSourceAuthorityRecord/v1'
    ) THEN
        RAISE EXCEPTION 'D02 supporting row schema is unsupported';
    END IF;
    expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
    IF NEW.schema_version = 'mirror.demo/D02R2SourceAuthorityRecord/v1' THEN
        expected_payload := expected_payload - ARRAY[
            'generation_request_digest','execution_epoch','producer_task_id','dispatch_epoch',
            'generation_source_asset_sha256','generation_source_asset_byte_size',
            'generation_source_asset_mime_type','generation_source_asset_width',
            'generation_source_asset_height','source_normalization_receipt_digest'
        ]::text[];
    END IF;
    IF NEW.schema_version NOT IN (
       'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',
       'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1'
    ) THEN
        expected_payload := expected_payload - 'generation_policy_metadata';
    END IF;
    IF NEW.schema_version <> 'mirror.demo/D02GenericSourceAuthorityRecord/v1' THEN
        expected_payload := expected_payload - ARRAY[
            'acquisition_candidate_id','selected_source_manifest_id','manifest_position'
        ]::text[];
    ELSE
        expected_payload := expected_payload - ARRAY[
            'evidence_root_id','root_name_receipt_digest','generation_preregistration_digest',
            'source_allocation_manifest_digest','source_producer_dispatch_digest',
            'source_generation_receipt_digest','output_name_receipt_digest',
            'output_seal_receipt_digest','registry_commit_receipt_digest',
            'generation_capability_authority_digest','generation_request_digest',
            'producer_task_id','dispatch_epoch','generation_source_asset_sha256',
            'generation_source_asset_byte_size','generation_source_asset_mime_type',
            'generation_source_asset_width','generation_source_asset_height',
            'source_normalization_receipt_digest','source_provenance_output_id',
            'source_provenance_name_receipt_digest','source_provenance_seal_receipt_digest',
            'source_provenance_registry_commit_receipt_digest'
        ]::text[];
    END IF;
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload
       OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected_payload) THEN
        RAISE EXCEPTION 'D02 supporting row canonical authority is invalid';
    END IF;
    id_preimage := jsonb_build_object(
        'execution_contract_digest', NEW.execution_contract_digest,
        'evidence_root_id', NEW.evidence_root_id,
        'root_name_receipt_digest', NEW.root_name_receipt_digest,
        'generation_preregistration_digest', NEW.generation_preregistration_digest,
        'source_allocation_manifest_digest', NEW.source_allocation_manifest_digest,
        'source_producer_dispatch_digest', NEW.source_producer_dispatch_digest,
        'source_ordinal', NEW.source_ordinal,
        'source_output_id', NEW.source_output_id,
        'source_authority_key', NEW.source_authority_key,
        'source_authority_digest', NEW.source_authority_digest,
        'source_qa_snapshot_digest', NEW.source_qa_snapshot_digest,
        'content_digest', NEW.content_digest
    );
    IF NEW.schema_version = 'mirror.demo/D02GenericSourceAuthorityRecord/v1' THEN
        id_preimage := jsonb_build_object(
            'acquisition_candidate_id', NEW.acquisition_candidate_id,
            'selected_source_manifest_id', NEW.selected_source_manifest_id,
            'manifest_position', NEW.manifest_position,
            'source_asset_id', NEW.source_asset_id,
            'content_digest', NEW.content_digest
        );
        expected_id := substring(mirror_demo_digest(
            'mirror.demo/D02GenericSourceAuthorityRecordId/v1', id_preimage
        ) FROM 1 FOR 32);
    ELSIF NEW.schema_version IN (
        'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1'
    ) THEN
        id_preimage := id_preimage || jsonb_build_object(
            'generation_request_digest', NEW.generation_request_digest,
            'execution_epoch', NEW.execution_epoch,
            'producer_task_id', NEW.producer_task_id,
            'dispatch_epoch', NEW.dispatch_epoch,
            'generation_source_asset_sha256', NEW.generation_source_asset_sha256,
            'generation_source_asset_byte_size', NEW.generation_source_asset_byte_size,
            'generation_source_asset_mime_type', NEW.generation_source_asset_mime_type,
            'generation_source_asset_width', NEW.generation_source_asset_width,
            'generation_source_asset_height', NEW.generation_source_asset_height,
            'source_normalization_receipt_digest', NEW.source_normalization_receipt_digest
        );
        expected_id := substring(mirror_demo_digest(
            CASE NEW.schema_version
                WHEN 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1'
                    THEN 'mirror.demo/D02R2Epoch2SourceAuthorityRecordId/v1'
                WHEN 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1'
                    THEN 'mirror.demo/D02R2Epoch3SourceAuthorityRecordId/v1'
                ELSE 'mirror.demo/D02R2Epoch4SourceAuthorityRecordId/v1'
            END,
            id_preimage
        ) FROM 1 FOR 32);
    ELSE
        expected_id := substring(mirror_demo_digest(
            'mirror.demo/D02R2SourceAuthorityRecordId/v1', id_preimage
        ) FROM 1 FOR 32);
    END IF;
    IF NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 supporting row ID is invalid';
    END IF;
    IF NEW.source_authority_key IS DISTINCT FROM mirror_demo_r2_source_authority_key(
        NEW.source_output_id, NEW.source_asset_id, NEW.source_asset_sha256,
        NEW.source_generation_receipt_digest, NEW.source_authority_digest
    ) THEN
        RAISE EXCEPTION 'D02 supporting row source key is invalid';
    END IF;
    IF NEW.schema_version = 'mirror.demo/D02GenericSourceAuthorityRecord/v1' THEN
        SELECT * INTO candidate_row FROM demo_d02_source_candidates
        WHERE id = NEW.acquisition_candidate_id;
        SELECT * INTO manifest_row FROM demo_d02_selected_source_manifests
        WHERE id = NEW.selected_source_manifest_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'D02 generic source manifest is missing';
        END IF;
        SELECT * INTO spec_row FROM demo_d02_cohort_specs WHERE id = candidate_row.cohort_spec_id;
        IF candidate_row.id IS NULL
           OR candidate_row.candidate_state IS DISTINCT FROM 'QA_ACCEPTED'
           OR candidate_row.qa_state IS DISTINCT FROM 'ACCEPTED'
           OR candidate_row.adult_status IS DISTINCT FROM 'VERIFIED_SYNTHETIC_ADULT'
           OR candidate_row.suspected_minor IS DISTINCT FROM FALSE
           OR manifest_row.acquisition_run_id IS DISTINCT FROM candidate_row.acquisition_run_id
           OR manifest_row.cohort_spec_id IS DISTINCT FROM candidate_row.cohort_spec_id
           OR manifest_row.ordered_candidate_ids ->> (NEW.manifest_position - 1)
                IS DISTINCT FROM candidate_row.id
           OR NEW.source_ordinal IS DISTINCT FROM NEW.manifest_position
           OR NEW.execution_contract_digest IS DISTINCT FROM spec_row.content_digest
           OR NEW.generation_request_policy_digest IS DISTINCT FROM spec_row.generation_policy_digest
           OR NEW.source_output_id IS DISTINCT FROM candidate_row.output_id
           OR NEW.source_provenance_digest IS NOT DISTINCT FROM candidate_row.content_digest
           OR NEW.source_qa_snapshot_digest IS NOT DISTINCT FROM candidate_row.m3_evidence_digest
           OR NEW.source_qa_snapshot_digest IS NOT DISTINCT FROM candidate_row.qa_evidence_digest THEN
            RAISE EXCEPTION 'D02 generic source candidate/manifest binding is invalid';
        END IF;
    ELSIF NEW.schema_version IN (
        'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',
        'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1'
    ) AND (
        NEW.generation_policy_metadata IS NULL
        OR NEW.generation_policy_metadata ->> 'source_digest' IS DISTINCT FROM NEW.source_asset_sha256
        OR NEW.generation_policy_metadata ->> 'adult_status' IS DISTINCT FROM 'VERIFIED_SYNTHETIC_ADULT'
        OR NEW.generation_policy_metadata ->> 'suspected_minor' IS DISTINCT FROM 'false'
        OR NEW.generation_policy_metadata ->> 'real_person_reference' IS DISTINCT FROM 'false'
        OR NEW.generation_policy_metadata ->> 'celebrity_resemblance' IS DISTINCT FROM 'false'
        OR NEW.generation_policy_metadata ->> 'metadata_digest' IS DISTINCT FROM mirror_demo_digest(
            CASE WHEN NEW.schema_version = 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1'
                 THEN 'mirror.demo/D02R2Epoch3GenerationPolicyMetadata/v1'
                 ELSE 'mirror.demo/D02R2Epoch4GenerationPolicyMetadata/v1' END,
            NEW.generation_policy_metadata - 'metadata_digest'
        )
        OR NEW.generation_policy_metadata -> 'source_policy_profile' ->> 'profile_digest'
           IS DISTINCT FROM NEW.generation_policy_metadata ->> 'source_policy_profile_digest'
        OR NEW.generation_policy_metadata -> 'source_policy_profile' ->> 'profile_digest'
           IS DISTINCT FROM mirror_demo_digest(
               CASE WHEN NEW.schema_version = 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1'
                    THEN 'mirror.demo/D02R2Epoch3SourcePolicyProfile/v1'
                    ELSE 'mirror.demo/D02R2Epoch4SourcePolicyProfile/v1' END,
               (NEW.generation_policy_metadata -> 'source_policy_profile') - 'profile_digest'::text
           )
        OR (NEW.generation_policy_metadata -> 'source_policy_profile' ->> 'source_ordinal')::integer
           IS DISTINCT FROM NEW.source_ordinal
    ) THEN
        RAISE EXCEPTION 'D02 legacy generation policy metadata is invalid';
    END IF;
    SELECT * INTO source_asset FROM assets WHERE id = NEW.source_asset_id;
    IF NOT FOUND OR source_asset.sha256 IS DISTINCT FROM NEW.source_asset_sha256
       OR source_asset.byte_size IS DISTINCT FROM NEW.source_asset_byte_size
       OR source_asset.mime_type IS DISTINCT FROM NEW.source_asset_mime_type
       OR source_asset.width IS DISTINCT FROM NEW.source_asset_width
       OR source_asset.height IS DISTINCT FROM NEW.source_asset_height
       OR source_asset.asset_role IS DISTINCT FROM 'synthetic'
       OR source_asset.owner_user_id IS NOT NULL
       OR source_asset.internal_purpose IS DISTINCT FROM 'synthetic_dataset'
       OR source_asset.synthetic IS NOT TRUE OR source_asset.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'D02 supporting row Asset authority is invalid';
    END IF;
    RETURN NEW;
END;
$function$;
"""

_ADMISSION_AUTHORITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_guard_d02_admission()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    expected_payload jsonb;
BEGIN
    IF TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'D02 admission authority is append-only';
    END IF;
    expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
    IF NEW.schema_version <> 'mirror.demo/D02GenericAdmission/v1' THEN
        expected_payload := expected_payload - 'selected_source_manifest_id';
    ELSE
        expected_payload := expected_payload - 'evidence_root_id';
    END IF;
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload
       OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected_payload)
    THEN
        RAISE EXCEPTION 'D02 admission canonical authority is invalid';
    END IF;
    RETURN NEW;
END;
$function$;
"""

_GENERIC_SCREENING_TRIGGER_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_generic_report()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE binding jsonb; manifest demo_d02_selected_source_manifests%ROWTYPE; expected jsonb;
BEGIN
  IF NEW.schema_version IS DISTINCT FROM 'mirror.demo/D02GenericPairScreeningReport/v1' THEN RETURN NEW; END IF;
  binding := NEW.report_payload -> 'selected_source_manifest_binding';
  SELECT * INTO manifest FROM demo_d02_selected_source_manifests WHERE id = binding ->> 'selected_source_manifest_id';
  expected := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
  IF NOT FOUND OR manifest.manifest_state IS DISTINCT FROM 'FINALIZED'
     OR jsonb_typeof(binding) IS DISTINCT FROM 'object'
     OR binding ->> 'selected_source_manifest_digest' IS DISTINCT FROM manifest.content_digest
     OR binding ->> 'formal_source_manifest_digest' IS DISTINCT FROM NEW.source_manifest_digest
     OR NEW.source_manifest_digest IS NOT DISTINCT FROM manifest.content_digest
     OR NEW.report_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, NEW.report_payload)
     OR NEW.canonical_payload IS DISTINCT FROM expected
     OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected)
     OR (SELECT count(*) FROM demo_d02_r2_source_authorities source_row
         WHERE source_row.schema_version = 'mirror.demo/D02GenericSourceAuthorityRecord/v1'
           AND source_row.selected_source_manifest_id = manifest.id) IS DISTINCT FROM 4
  THEN RAISE EXCEPTION 'D02 generic Report authority is invalid'; END IF;
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_generic_bank()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE report demo_pair_screening_reports%ROWTYPE; expected jsonb;
BEGIN
  IF NEW.schema_version IS DISTINCT FROM 'mirror.demo/D02GenericQuestionBank/v1' THEN RETURN NEW; END IF;
  SELECT * INTO report FROM demo_pair_screening_reports WHERE id = NEW.screening_report_id;
  expected := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
  IF NOT FOUND OR report.schema_version IS DISTINCT FROM 'mirror.demo/D02GenericPairScreeningReport/v1'
     OR report.status IS DISTINCT FROM 'PASSED'
     OR NEW.screening_report_digest IS DISTINCT FROM report.report_digest
     OR NEW.pair_manifest_digest IS DISTINCT FROM report.selected_pair_manifest_digest
     OR NEW.canonical_payload IS DISTINCT FROM expected
     OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected)
  THEN RAISE EXCEPTION 'D02 generic QuestionBank authority is invalid'; END IF;
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_generic_pair()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE report demo_pair_screening_reports%ROWTYPE; bank demo_question_banks%ROWTYPE; expected jsonb; qa jsonb;
BEGIN
  IF NEW.schema_version IS DISTINCT FROM 'mirror.demo/D02GenericQuestionPair/v1' THEN RETURN NEW; END IF;
  SELECT * INTO report FROM demo_pair_screening_reports WHERE id = NEW.screening_report_id;
  SELECT * INTO bank FROM demo_question_banks WHERE id = NEW.question_bank_id;
  expected := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME); qa := NEW.qa_payload;
  IF NOT FOUND OR report.schema_version IS DISTINCT FROM 'mirror.demo/D02GenericPairScreeningReport/v1'
     OR bank.schema_version IS DISTINCT FROM 'mirror.demo/D02GenericQuestionBank/v1'
     OR bank.screening_report_id IS DISTINCT FROM report.id
     OR NEW.screening_report_digest IS DISTINCT FROM report.report_digest
     OR jsonb_typeof(qa) IS DISTINCT FROM 'object'
     OR qa ->> 'schema_version' IS DISTINCT FROM 'mirror.demo/D02GenericQuestionPairQAPayload/v1'
     OR qa ->> 'screening_report_id' IS DISTINCT FROM report.id
     OR qa ->> 'screening_report_digest' IS DISTINCT FROM report.report_digest
     OR qa ->> 'formal_source_manifest_digest' IS DISTINCT FROM report.source_manifest_digest
     OR qa ->> 'selected_pair_manifest_digest' IS DISTINCT FROM report.selected_pair_manifest_digest
     OR NEW.canonical_payload IS DISTINCT FROM expected
     OR NEW.content_digest IS DISTINCT FROM mirror_demo_digest(NEW.schema_version, expected)
  THEN RAISE EXCEPTION 'D02 generic QuestionPair authority is invalid'; END IF;
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_generic_complete_bank()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE bank_id text; pair_count integer; identity_count integer; dimension_count integer; magnitude_count integer; side_count integer;
BEGIN
  IF TG_TABLE_NAME = 'demo_question_banks' THEN
    bank_id := NEW.id;
  ELSIF TG_TABLE_NAME = 'demo_question_pairs' THEN
    bank_id := NEW.question_bank_id;
  ELSE
    RAISE EXCEPTION 'D02 generic complete-bank trigger routing failed';
  END IF;
  IF (SELECT schema_version FROM demo_question_banks WHERE id = bank_id) IS DISTINCT FROM 'mirror.demo/D02GenericQuestionBank/v1' THEN RETURN NULL; END IF;
  SELECT count(*), count(DISTINCT demo_synthetic_identity_id), count(DISTINCT dimension_key), count(DISTINCT magnitude_ppm), count(DISTINCT side.asset_id)
    INTO pair_count, identity_count, dimension_count, magnitude_count, side_count
    FROM demo_question_pairs pair_row CROSS JOIN LATERAL (VALUES (pair_row.left_asset_id), (pair_row.right_asset_id)) side(asset_id)
   WHERE pair_row.question_bank_id = bank_id AND pair_row.schema_version = 'mirror.demo/D02GenericQuestionPair/v1';
  IF pair_count / 2 IS DISTINCT FROM 16 OR identity_count IS DISTINCT FROM 4 OR dimension_count IS DISTINCT FROM 2 OR magnitude_count IS DISTINCT FROM 2 OR side_count IS DISTINCT FROM 32 THEN
    RAISE EXCEPTION 'D02 generic QuestionBank is incomplete';
  END IF;
  RETURN NULL;
END;
$function$;
"""

_ADMISSION_TRIGGER_V4_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_d02_r2_epoch2_admission()
RETURNS trigger LANGUAGE plpgsql AS $function$
DECLARE
    report_row demo_pair_screening_reports%ROWTYPE;
    bank_row demo_question_banks%ROWTYPE;
    manifest_row demo_d02_selected_source_manifests%ROWTYPE;
    source_count integer;
    identity_count integer;
    source_position_count integer;
    pair_count integer;
    side_count integer;
    expected_id text;
    expected_source_schema text;
    expected_identity_schema text;
    expected_root text;
    expected_epoch text;
    expected_dispatch smallint;
    expected_id_schema text;
    selected_binding jsonb;
BEGIN
    IF TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'D02 admission is append-only';
    END IF;
    IF NEW.schema_version = 'mirror.demo/D02GenericAdmission/v1' THEN
        expected_source_schema := 'mirror.demo/D02GenericSourceAuthorityRecord/v1';
        expected_identity_schema := 'mirror.demo/DemoSyntheticIdentity/v5';
        expected_root := NULL;
        expected_epoch := 'D02_AUTONOMOUS_V1';
        expected_dispatch := NULL;
        expected_id_schema := 'mirror.demo/D02GenericAdmissionId/v1';
        SELECT * INTO manifest_row FROM demo_d02_selected_source_manifests
        WHERE id = NEW.selected_source_manifest_id;
        IF NOT FOUND OR manifest_row.manifest_state IS DISTINCT FROM 'FINALIZED' THEN
            RAISE EXCEPTION 'D02 generic admission manifest is missing';
        END IF;
    ELSIF NEW.schema_version = 'mirror.demo/D02R2Epoch2Admission/v1' THEN
        expected_source_schema := 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1';
        expected_identity_schema := 'mirror.demo/DemoSyntheticIdentity/v4';
        expected_root := 'P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT';
        expected_epoch := 'D02_R2_EPOCH_02'; expected_dispatch := 2;
        expected_id_schema := 'mirror.demo/D02R2Epoch2AdmissionId/v1';
    ELSIF NEW.schema_version = 'mirror.demo/D02R2Epoch3Admission/v1' THEN
        expected_source_schema := 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1';
        expected_identity_schema := 'mirror.demo/DemoSyntheticIdentity/v4';
        expected_root := 'P3_P7_D02_R2_E3_EVIDENCE_ROOT';
        expected_epoch := 'D02_R2_EPOCH_03'; expected_dispatch := 3;
        expected_id_schema := 'mirror.demo/D02R2Epoch3AdmissionId/v1';
    ELSIF NEW.schema_version = 'mirror.demo/D02R2Epoch4Admission/v1' THEN
        expected_source_schema := 'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1';
        expected_identity_schema := 'mirror.demo/DemoSyntheticIdentity/v4';
        expected_root := 'P3_P7_D02_R2_E4_EVIDENCE_ROOT';
        expected_epoch := 'D02_R2_EPOCH_04'; expected_dispatch := 4;
        expected_id_schema := 'mirror.demo/D02R2Epoch4AdmissionId/v1';
    ELSE
        RAISE EXCEPTION 'D02 admission schema is unsupported';
    END IF;
    SELECT * INTO report_row FROM demo_pair_screening_reports WHERE id = NEW.screening_report_id;
    SELECT * INTO bank_row FROM demo_question_banks WHERE id = NEW.question_bank_id;
    IF NOT FOUND OR report_row.schema_version IS DISTINCT FROM (CASE
           WHEN NEW.schema_version = 'mirror.demo/D02GenericAdmission/v1'
           THEN 'mirror.demo/D02GenericPairScreeningReport/v1'
           ELSE 'mirror.demo/D02PairScreeningReport/v3' END)
       OR report_row.status IS DISTINCT FROM 'PASSED'
       OR report_row.report_digest IS DISTINCT FROM NEW.screening_report_digest
       OR report_row.source_manifest_digest IS DISTINCT FROM NEW.source_manifest_digest
       OR report_row.selected_pair_manifest_digest IS DISTINCT FROM NEW.selected_pair_manifest_digest
       OR report_row.source_count IS DISTINCT FROM 4
       OR report_row.selected_pair_count IS DISTINCT FROM 16
       OR report_row.selected_result_side_count IS DISTINCT FROM 32
       OR bank_row.schema_version IS DISTINCT FROM (CASE
           WHEN NEW.schema_version = 'mirror.demo/D02GenericAdmission/v1'
           THEN 'mirror.demo/D02GenericQuestionBank/v1'
           ELSE 'mirror.demo/DemoQuestionBank/v3' END)
       OR bank_row.screening_report_id IS DISTINCT FROM report_row.id
       OR bank_row.screening_report_digest IS DISTINCT FROM report_row.report_digest
       OR bank_row.content_digest IS DISTINCT FROM NEW.question_bank_content_digest
       OR bank_row.version IS DISTINCT FROM NEW.question_bank_version
       OR bank_row.pair_manifest_digest IS DISTINCT FROM NEW.selected_pair_manifest_digest THEN
        RAISE EXCEPTION 'D02 admission graph binding is invalid';
    END IF;
    IF NEW.schema_version = 'mirror.demo/D02GenericAdmission/v1' THEN
        selected_binding := report_row.report_payload -> 'selected_source_manifest_binding';
        IF jsonb_typeof(selected_binding) IS DISTINCT FROM 'object'
           OR selected_binding ->> 'selected_source_manifest_id' IS DISTINCT FROM NEW.selected_source_manifest_id
           OR selected_binding ->> 'selected_source_manifest_digest' IS DISTINCT FROM manifest_row.content_digest
           OR selected_binding ->> 'formal_source_manifest_digest' IS DISTINCT FROM NEW.source_manifest_digest
           OR report_row.source_manifest_digest IS DISTINCT FROM NEW.source_manifest_digest
           OR NEW.source_manifest_digest IS NOT DISTINCT FROM manifest_row.content_digest
           OR jsonb_array_length(report_row.report_payload -> 'asset_authority_manifest') IS DISTINCT FROM 52
           OR jsonb_array_length(report_row.report_payload -> 'asset_variant_manifest') IS DISTINCT FROM 48 THEN
            RAISE EXCEPTION 'D02 generic admission selected/formal manifest binding is invalid';
        END IF;
    END IF;
    SELECT count(DISTINCT source_row.id), count(DISTINCT source_row.manifest_position)
      INTO source_count, source_position_count
    FROM jsonb_array_elements(report_row.report_payload -> 'ordered_source_manifest') entry
    JOIN demo_d02_r2_source_authorities source_row
      ON source_row.id = entry ->> 'r2_source_authority_record_id'
    WHERE source_row.schema_version = expected_source_schema
      AND source_row.evidence_root_id IS NOT DISTINCT FROM expected_root
      AND source_row.execution_epoch = expected_epoch
      AND source_row.dispatch_epoch IS NOT DISTINCT FROM expected_dispatch
      AND (
          NEW.schema_version <> 'mirror.demo/D02GenericAdmission/v1'
          OR source_row.selected_source_manifest_id = NEW.selected_source_manifest_id
      );
    SELECT count(DISTINCT identity_row.id) INTO identity_count
    FROM jsonb_array_elements(report_row.report_payload -> 'ordered_source_manifest') entry
    JOIN demo_synthetic_identities identity_row
      ON identity_row.id = entry ->> 'source_admission_event_id'
    WHERE identity_row.schema_version = expected_identity_schema
      AND identity_row.admission_action = 'ADMIT'
      AND identity_row.r2_source_authority_record_id = entry ->> 'r2_source_authority_record_id';
    SELECT count(*), count(DISTINCT side.asset_id) INTO pair_count, side_count
    FROM demo_question_pairs pair_row
    CROSS JOIN LATERAL (VALUES (pair_row.left_asset_id), (pair_row.right_asset_id)) side(asset_id)
    WHERE pair_row.question_bank_id = bank_row.id
      AND pair_row.schema_version = CASE WHEN NEW.schema_version = 'mirror.demo/D02GenericAdmission/v1'
                                         THEN 'mirror.demo/D02GenericQuestionPair/v1'
                                         ELSE 'mirror.demo/DemoQuestionPair/v3' END
      AND pair_row.screening_report_id = report_row.id
      AND pair_row.screening_report_digest = report_row.report_digest;
    pair_count := pair_count / 2;
    IF source_count IS DISTINCT FROM 4 OR identity_count IS DISTINCT FROM 4
       OR (NEW.schema_version = 'mirror.demo/D02GenericAdmission/v1'
           AND source_position_count IS DISTINCT FROM 4)
       OR pair_count IS DISTINCT FROM 16 OR side_count IS DISTINCT FROM 32 THEN
        RAISE EXCEPTION 'D02 admission cardinality is invalid';
    END IF;
    expected_id := substring(mirror_demo_digest(
        expected_id_schema,
        jsonb_build_object(
            'idempotency_key_hash', NEW.idempotency_key_hash,
            'request_digest', NEW.request_digest,
            'screening_report_id', NEW.screening_report_id,
            'question_bank_id', NEW.question_bank_id
        )
    ) FROM 1 FOR 32);
    IF NEW.id IS DISTINCT FROM expected_id THEN
        RAISE EXCEPTION 'D02 admission ID is invalid';
    END IF;
    RETURN NULL;
END;
$function$;
"""


def _authority_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _authority_constraints(table: str, schema: str) -> list[sa.Constraint]:
    return [
        sa.CheckConstraint("id ~ '^[0-9a-f]{32}$'", name="id_shape"),
        sa.CheckConstraint(f"schema_version = '{schema}'", name="schema_version_shape"),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'", name="canonical_payload_object"
        ),
        sa.CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="content_digest_shape"),
        sa.UniqueConstraint("content_digest", name=f"uq_{table}_content_digest"),
    ]


def _create_acquisition_tables() -> None:
    op.create_table(
        "demo_d02_cohort_specs",
        *_authority_columns(),
        sa.Column("generation_policy_version", sa.String(length=64), nullable=False),
        sa.Column("generation_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("provider_interface", sa.String(length=64), nullable=False),
        sa.Column("provider_identity_digest", sa.String(length=64), nullable=False),
        sa.Column("runtime_identity_digest", sa.String(length=64), nullable=False),
        sa.Column("model_identity_digest", sa.String(length=64), nullable=False),
        sa.Column("materializer_version", sa.String(length=64), nullable=False),
        sa.Column("materializer_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("m3_prescreen_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("qa_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("total_budget", sa.SmallInteger(), nullable=False),
        sa.Column("tranche_size", sa.SmallInteger(), nullable=False),
        sa.Column("concurrency", sa.SmallInteger(), nullable=False),
        sa.Column("same_ordinal_retry", sa.SmallInteger(), nullable=False),
        sa.Column("target_source_count", sa.SmallInteger(), nullable=False),
        sa.Column("outputs_per_call", sa.SmallInteger(), nullable=False),
        sa.Column("spec_state", sa.String(length=16), nullable=False),
        *_authority_constraints("demo_d02_cohort_specs", "mirror.demo/D02CohortSpec/v1"),
        sa.UniqueConstraint(
            "generation_policy_digest",
            "provider_identity_digest",
            "runtime_identity_digest",
            "model_identity_digest",
            "materializer_policy_digest",
            name="registered_identity",
        ),
        sa.UniqueConstraint(
            "spec_state",
            name="uq_demo_d02_cohort_specs_bootstrap_singleton",
        ),
        sa.CheckConstraint(
            "generation_policy_digest ~ '^[0-9a-f]{64}$' AND provider_identity_digest ~ '^[0-9a-f]{64}$' "
            "AND runtime_identity_digest ~ '^[0-9a-f]{64}$' AND model_identity_digest ~ '^[0-9a-f]{64}$' "
            "AND materializer_policy_digest ~ '^[0-9a-f]{64}$' AND m3_prescreen_policy_digest ~ '^[0-9a-f]{64}$' "
            "AND qa_policy_digest ~ '^[0-9a-f]{64}$'",
            name="digest_shapes",
        ),
        sa.CheckConstraint(
            "total_budget = 50 AND tranche_size = 10 AND concurrency = 1 AND same_ordinal_retry = 0 "
            "AND target_source_count = 4 AND outputs_per_call = 1",
            name="fixed_budget",
        ),
        sa.CheckConstraint("spec_state = 'REGISTERED'", name="registered_state"),
    )
    op.create_table(
        "demo_d02_source_acquisition_runs",
        *_authority_columns(),
        sa.Column("cohort_spec_id", sa.String(length=32), nullable=False),
        sa.Column("run_key_digest", sa.String(length=64), nullable=False),
        sa.Column("run_state", sa.String(length=32), nullable=False),
        sa.Column("budget_consumed", sa.SmallInteger(), nullable=False),
        sa.Column("next_ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("open_call_ordinal", sa.SmallInteger()),
        sa.Column("open_selector_slot_id", sa.String(length=32)),
        sa.Column("accepted_count", sa.SmallInteger(), nullable=False),
        sa.Column("consecutive_content_rejects", sa.SmallInteger(), nullable=False),
        sa.Column("calls_without_accept", sa.SmallInteger(), nullable=False),
        sa.Column("content_review_epoch", sa.SmallInteger(), nullable=False),
        sa.Column("terminal_reason", sa.String(length=64)),
        *_authority_constraints(
            "demo_d02_source_acquisition_runs", "mirror.demo/D02SourceAcquisitionRun/v1"
        ),
        sa.ForeignKeyConstraint(
            ["cohort_spec_id"], ["demo_d02_cohort_specs.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "run_key_digest",
            name="uq_demo_d02_source_acquisition_runs_run_key_digest",
        ),
        sa.UniqueConstraint(
            "cohort_spec_id",
            name="uq_demo_d02_source_acquisition_runs_bootstrap_singleton",
        ),
        sa.UniqueConstraint(
            "id",
            "cohort_spec_id",
            name="uq_demo_d02_source_acquisition_runs_id_spec",
        ),
        sa.CheckConstraint("run_key_digest ~ '^[0-9a-f]{64}$'", name="run_key_digest_shape"),
        sa.CheckConstraint(
            "run_state IN ('ACTIVE','PAUSED_INFRASTRUCTURE','PAUSED_CONTENT_REVIEW',"
            "'MANIFEST_FINALIZED','ADMITTED','FAILED_CLOSED')",
            name="run_state",
        ),
        sa.CheckConstraint(
            "budget_consumed BETWEEN 0 AND 50 AND next_ordinal = budget_consumed + 1 "
            "AND next_ordinal BETWEEN 1 AND 51",
            name="budget_projection",
        ),
        sa.CheckConstraint(
            "accepted_count BETWEEN 0 AND 4 AND consecutive_content_rejects BETWEEN 0 AND 50 "
            "AND calls_without_accept BETWEEN 0 AND 50 AND content_review_epoch BETWEEN 0 AND 50",
            name="counter_ranges",
        ),
        sa.CheckConstraint(
            "(open_call_ordinal IS NULL AND open_selector_slot_id IS NULL) OR "
            "(run_state = 'ACTIVE' AND open_call_ordinal = budget_consumed "
            "AND open_call_ordinal BETWEEN 1 AND 50 "
            "AND open_selector_slot_id ~ '^[A-Z][A-Z0-9_]{0,31}$')",
            name="single_open_call",
        ),
        sa.CheckConstraint(
            "run_state = 'ACTIVE' OR open_call_ordinal IS NULL", name="paused_has_no_open_call"
        ),
        sa.CheckConstraint(
            "(run_state IN ('MANIFEST_FINALIZED','ADMITTED') AND accepted_count = 4 AND terminal_reason IS NULL) OR "
            "(run_state = 'FAILED_CLOSED' AND terminal_reason IS NOT NULL) OR "
            "(run_state NOT IN ('MANIFEST_FINALIZED','ADMITTED','FAILED_CLOSED') "
            "AND accepted_count < 4 AND terminal_reason IS NULL)",
            name="terminal_matrix",
        ),
    )
    op.create_index(
        op.f("ix_demo_d02_source_acquisition_runs_cohort_spec_id"),
        "demo_d02_source_acquisition_runs",
        ["cohort_spec_id"],
    )

    op.create_table(
        "demo_d02_source_candidates",
        *_authority_columns(),
        sa.Column("acquisition_run_id", sa.String(length=32), nullable=False),
        sa.Column("cohort_spec_id", sa.String(length=32), nullable=False),
        sa.Column("provider_ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("selector_slot_id", sa.String(length=32), nullable=False),
        sa.Column("call_started_event_digest", sa.String(length=64), nullable=False),
        sa.Column("output_id", sa.String(length=128), nullable=False),
        sa.Column("provider_result_digest", sa.String(length=64), nullable=False),
        sa.Column("durable_primary_sha256", sa.String(length=64), nullable=False),
        sa.Column("durable_backup_sha256", sa.String(length=64)),
        sa.Column("durable_byte_size", sa.BigInteger(), nullable=False),
        sa.Column("durable_media_type", sa.String(length=64), nullable=False),
        sa.Column("durable_width", sa.Integer(), nullable=False),
        sa.Column("durable_height", sa.Integer(), nullable=False),
        sa.Column("candidate_state", sa.String(length=24), nullable=False),
        sa.Column("m3_state", sa.String(length=16), nullable=False),
        sa.Column("m3_evidence_digest", sa.String(length=64)),
        sa.Column("qa_state", sa.String(length=16), nullable=False),
        sa.Column("qa_evidence_digest", sa.String(length=64)),
        sa.Column("adult_status", sa.String(length=32), nullable=False),
        sa.Column("declared_age_band", sa.String(length=16), nullable=False),
        sa.Column("suspected_minor", sa.Boolean()),
        sa.Column("synthetic_only_attested", sa.Boolean(), nullable=False),
        sa.Column("real_person_reference_used", sa.Boolean(), nullable=False),
        sa.Column("identity_family_digest", sa.String(length=64)),
        sa.Column("rejection_code", sa.String(length=64)),
        *_authority_constraints("demo_d02_source_candidates", "mirror.demo/D02SourceCandidate/v1"),
        sa.ForeignKeyConstraint(
            ["acquisition_run_id"], ["demo_d02_source_acquisition_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["cohort_spec_id"], ["demo_d02_cohort_specs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_run_id", "cohort_spec_id"],
            [
                "demo_d02_source_acquisition_runs.id",
                "demo_d02_source_acquisition_runs.cohort_spec_id",
            ],
            name="fk_demo_d02_source_candidates_run_spec",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "acquisition_run_id",
            "provider_ordinal",
            name="uq_demo_d02_source_candidates_run_ordinal",
        ),
        sa.UniqueConstraint(
            "output_id",
            name="uq_demo_d02_source_candidates_output_id",
        ),
        sa.UniqueConstraint(
            "id",
            "acquisition_run_id",
            "cohort_spec_id",
            name="uq_demo_d02_source_candidates_id_run_spec",
        ),
        sa.CheckConstraint("provider_ordinal BETWEEN 1 AND 50", name="provider_ordinal"),
        sa.CheckConstraint("selector_slot_id ~ '^[A-Z][A-Z0-9_]{0,31}$'", name="selector_slot_id"),
        sa.CheckConstraint(
            "output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'", name="output_id_shape"
        ),
        sa.CheckConstraint(
            "provider_result_digest ~ '^[0-9a-f]{64}$' AND call_started_event_digest ~ '^[0-9a-f]{64}$' "
            "AND durable_primary_sha256 ~ '^[0-9a-f]{64}$' "
            "AND (durable_backup_sha256 IS NULL OR durable_backup_sha256 = durable_primary_sha256) "
            "AND (m3_evidence_digest IS NULL OR m3_evidence_digest ~ '^[0-9a-f]{64}$') "
            "AND (qa_evidence_digest IS NULL OR qa_evidence_digest ~ '^[0-9a-f]{64}$') "
            "AND (identity_family_digest IS NULL OR identity_family_digest ~ '^[0-9a-f]{64}$')",
            name="digest_shapes",
        ),
        sa.CheckConstraint(
            "durable_byte_size > 0 AND durable_width > 0 AND durable_height > 0 "
            "AND durable_media_type IN ('image/png','image/jpeg')",
            name="durable_image",
        ),
        sa.CheckConstraint(
            "declared_age_band IN ('ADULT_18_19','ADULT_20_25') AND synthetic_only_attested IS TRUE "
            "AND real_person_reference_used IS FALSE",
            name="synthetic_adult_scope",
        ),
        sa.CheckConstraint(
            "candidate_state IN ('PRIMARY_DURABLE','DURABLE','M3_SUPPORTED','QA_ACCEPTED','QA_REJECTED') "
            "AND m3_state IN ('PENDING','SUPPORTED','UNSUPPORTED') "
            "AND qa_state IN ('PENDING','ACCEPTED','REJECTED')",
            name="states",
        ),
        sa.CheckConstraint(
            "(candidate_state = 'PRIMARY_DURABLE' AND durable_backup_sha256 IS NULL "
            "AND m3_state = 'PENDING' AND m3_evidence_digest IS NULL "
            "AND qa_state = 'PENDING' AND qa_evidence_digest IS NULL AND adult_status = 'UNVERIFIED' "
            "AND suspected_minor IS NULL AND identity_family_digest IS NULL AND rejection_code IS NULL) OR "
            "(candidate_state = 'DURABLE' AND durable_backup_sha256 = durable_primary_sha256 "
            "AND m3_state = 'PENDING' AND m3_evidence_digest IS NULL "
            "AND qa_state = 'PENDING' AND qa_evidence_digest IS NULL AND adult_status = 'UNVERIFIED' "
            "AND identity_family_digest IS NULL AND rejection_code IS NULL) OR "
            "(candidate_state = 'M3_SUPPORTED' AND durable_backup_sha256 = durable_primary_sha256 "
            "AND m3_state = 'SUPPORTED' AND m3_evidence_digest IS NOT NULL "
            "AND qa_state = 'PENDING' AND qa_evidence_digest IS NULL AND adult_status = 'UNVERIFIED' "
            "AND identity_family_digest IS NULL AND rejection_code IS NULL) OR "
            "(candidate_state = 'QA_ACCEPTED' AND durable_backup_sha256 = durable_primary_sha256 "
            "AND m3_state = 'SUPPORTED' AND m3_evidence_digest IS NOT NULL "
            "AND qa_state = 'ACCEPTED' AND qa_evidence_digest IS NOT NULL "
            "AND adult_status = 'VERIFIED_SYNTHETIC_ADULT' AND suspected_minor IS FALSE "
            "AND identity_family_digest IS NOT NULL AND rejection_code IS NULL) OR "
            "(candidate_state = 'QA_REJECTED' AND durable_backup_sha256 = durable_primary_sha256 "
            "AND m3_state IN ('SUPPORTED','UNSUPPORTED') "
            "AND m3_evidence_digest IS NOT NULL AND qa_state = 'REJECTED' "
            "AND qa_evidence_digest IS NOT NULL AND rejection_code IS NOT NULL)",
            name="state_matrix",
        ),
    )
    op.create_index(
        op.f("ix_demo_d02_source_candidates_acquisition_run_id"),
        "demo_d02_source_candidates",
        ["acquisition_run_id"],
    )
    op.create_index(
        op.f("ix_demo_d02_source_candidates_cohort_spec_id"),
        "demo_d02_source_candidates",
        ["cohort_spec_id"],
    )
    op.create_index(
        "uq_demo_d02_source_candidates_accepted_slot",
        "demo_d02_source_candidates",
        ["acquisition_run_id", "selector_slot_id"],
        unique=True,
        postgresql_where=sa.text("qa_state = 'ACCEPTED'"),
    )

    op.create_table(
        "demo_d02_source_acquisition_events",
        *_authority_columns(),
        sa.Column("acquisition_run_id", sa.String(length=32), nullable=False),
        sa.Column("cohort_spec_id", sa.String(length=32), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("event_kind", sa.String(length=40), nullable=False),
        sa.Column("provider_ordinal", sa.SmallInteger()),
        sa.Column("selector_slot_id", sa.String(length=32)),
        sa.Column("tranche_number", sa.SmallInteger()),
        sa.Column("candidate_id", sa.String(length=32)),
        sa.Column("detail_code", sa.String(length=64)),
        sa.Column("evidence_digest", sa.String(length=64)),
        sa.Column("call_started_event_digest", sa.String(length=64)),
        *_authority_constraints(
            "demo_d02_source_acquisition_events", "mirror.demo/D02SourceAcquisitionEvent/v1"
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_run_id"], ["demo_d02_source_acquisition_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["cohort_spec_id"], ["demo_d02_cohort_specs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["demo_d02_source_candidates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_run_id", "cohort_spec_id"],
            [
                "demo_d02_source_acquisition_runs.id",
                "demo_d02_source_acquisition_runs.cohort_spec_id",
            ],
            name="fk_demo_d02_source_acquisition_events_run_spec",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "acquisition_run_id",
            "event_sequence",
            name="uq_demo_d02_source_acquisition_events_run_sequence",
        ),
        sa.CheckConstraint("event_sequence > 0", name="positive_sequence"),
        sa.CheckConstraint(
            "event_kind IN ('RUN_CREATED','CALL_STARTED','CALL_CONSUMED_NO_RESULT','PROVIDER_OUTCOME_UNCERTAIN',"
            "'MATERIALIZATION_FAILED','CANDIDATE_PRIMARY_DURABLE','CANDIDATE_DURABLE','M3_SUPPORTED',"
            "'M3_UNSUPPORTED','QA_ACCEPTED','QA_REJECTED','INFRASTRUCTURE_PAUSED','INFRASTRUCTURE_RESUMED',"
            "'CONTENT_REVIEW_PAUSED','CONTENT_REVIEW_RESUMED','TRANCHE_RECONCILED','MANIFEST_FINALIZED',"
            "'FORMAL_SOURCES_READY','FINAL_GATE_PAUSED','ADMISSION_COMPLETED','RUN_FAILED_CLOSED')",
            name="event_kind",
        ),
        sa.CheckConstraint(
            "(provider_ordinal IS NULL AND selector_slot_id IS NULL) OR "
            "(provider_ordinal BETWEEN 1 AND 50 AND selector_slot_id ~ '^[A-Z][A-Z0-9_]{0,31}$')",
            name="ordinal_slot_pair",
        ),
        sa.CheckConstraint(
            "(event_kind = 'TRANCHE_RECONCILED' AND tranche_number BETWEEN 1 AND 5 "
            "AND provider_ordinal IS NULL AND selector_slot_id IS NULL) OR "
            "(event_kind <> 'TRANCHE_RECONCILED' AND tranche_number IS NULL)",
            name="tranche_binding",
        ),
        sa.CheckConstraint(
            "(detail_code IS NULL OR detail_code ~ '^[A-Z][A-Z0-9_]{0,63}$') "
            "AND (evidence_digest IS NULL OR evidence_digest ~ '^[0-9a-f]{64}$') "
            "AND (call_started_event_digest IS NULL OR call_started_event_digest ~ '^[0-9a-f]{64}$')",
            name="detail_shapes",
        ),
        sa.CheckConstraint(
            "(provider_ordinal IS NULL AND call_started_event_digest IS NULL) OR "
            "(event_kind = 'CALL_STARTED' AND call_started_event_digest IS NULL) OR "
            "(provider_ordinal IS NOT NULL AND event_kind <> 'CALL_STARTED' "
            "AND call_started_event_digest IS NOT NULL)",
            name="call_started_binding",
        ),
    )
    op.create_index(
        op.f("ix_demo_d02_source_acquisition_events_acquisition_run_id"),
        "demo_d02_source_acquisition_events",
        ["acquisition_run_id"],
    )
    op.create_index(
        op.f("ix_demo_d02_source_acquisition_events_cohort_spec_id"),
        "demo_d02_source_acquisition_events",
        ["cohort_spec_id"],
    )
    op.create_index(
        op.f("ix_demo_d02_source_acquisition_events_candidate_id"),
        "demo_d02_source_acquisition_events",
        ["candidate_id"],
    )
    op.create_index(
        "uq_demo_d02_source_acquisition_events_call_started",
        "demo_d02_source_acquisition_events",
        ["acquisition_run_id", "provider_ordinal"],
        unique=True,
        postgresql_where=sa.text("event_kind = 'CALL_STARTED'"),
    )
    op.create_index(
        "uq_demo_d02_source_acquisition_events_tranche_reconciled",
        "demo_d02_source_acquisition_events",
        ["acquisition_run_id", "tranche_number"],
        unique=True,
        postgresql_where=sa.text("event_kind = 'TRANCHE_RECONCILED'"),
    )
    op.create_index(
        "uq_demo_d02_source_acquisition_events_formal_sources_ready",
        "demo_d02_source_acquisition_events",
        ["acquisition_run_id"],
        unique=True,
        postgresql_where=sa.text("event_kind = 'FORMAL_SOURCES_READY'"),
    )

    op.create_table(
        "demo_d02_selected_source_manifests",
        *_authority_columns(),
        sa.Column("acquisition_run_id", sa.String(length=32), nullable=False),
        sa.Column("cohort_spec_id", sa.String(length=32), nullable=False),
        sa.Column("generation_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("ordered_candidate_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_count", sa.SmallInteger(), nullable=False),
        sa.Column("manifest_state", sa.String(length=16), nullable=False),
        *_authority_constraints(
            "demo_d02_selected_source_manifests", "mirror.demo/D02SelectedSourceManifest/v1"
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_run_id"], ["demo_d02_source_acquisition_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["cohort_spec_id"], ["demo_d02_cohort_specs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_run_id", "cohort_spec_id"],
            [
                "demo_d02_source_acquisition_runs.id",
                "demo_d02_source_acquisition_runs.cohort_spec_id",
            ],
            name="fk_demo_d02_selected_source_manifests_run_spec",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "acquisition_run_id",
            name="uq_demo_d02_selected_source_manifests_acquisition_run_id",
        ),
        sa.UniqueConstraint(
            "id",
            "acquisition_run_id",
            "cohort_spec_id",
            name="uq_demo_d02_selected_source_manifests_id_run_spec",
        ),
        sa.CheckConstraint(
            "generation_policy_digest ~ '^[0-9a-f]{64}$'",
            name="gen_policy_digest",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(ordered_candidate_ids) = 'array' AND jsonb_array_length(ordered_candidate_ids) = 4 "
            "AND source_count = 4",
            name="four_candidates",
        ),
        sa.CheckConstraint("manifest_state = 'FINALIZED'", name="finalized_state"),
    )
    op.create_index(
        op.f("ix_demo_d02_selected_source_manifests_acquisition_run_id"),
        "demo_d02_selected_source_manifests",
        ["acquisition_run_id"],
    )
    op.create_index(
        op.f("ix_demo_d02_selected_source_manifests_cohort_spec_id"),
        "demo_d02_selected_source_manifests",
        ["cohort_spec_id"],
    )

    op.execute(_ACQUISITION_TRIGGER_SQL)
    op.execute(_BUDGET_CONSISTENCY_TRIGGER_SQL)
    for table in (
        "demo_d02_cohort_specs",
        "demo_d02_source_acquisition_runs",
        "demo_d02_source_candidates",
        "demo_d02_source_acquisition_events",
        "demo_d02_selected_source_manifests",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_authority BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_acquisition_row()"
        )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d02_runs_budget_consistency "
        "AFTER INSERT OR UPDATE ON demo_d02_source_acquisition_runs DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_budget_consistency()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d02_events_budget_consistency "
        "AFTER INSERT ON demo_d02_source_acquisition_events DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_budget_consistency()"
    )


def _drop_source_version_constraints() -> None:
    for name in ("schema_version_shape", "evidence_root", "opaque_output_ids", "digest_shapes"):
        op.drop_constraint(
            op.f(f"ck_demo_d02_r2_source_authorities_{name}"),
            "demo_d02_r2_source_authorities",
            type_="check",
        )


def _create_source_v4_constraints() -> None:
    table = "demo_d02_r2_source_authorities"
    op.create_check_constraint(
        op.f(f"ck_{table}_schema_version_shape"),
        table,
        "schema_version IN ('mirror.demo/D02R2SourceAuthorityRecord/v1',"
        "'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1',"
        "'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',"
        "'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1',"
        "'mirror.demo/D02GenericSourceAuthorityRecord/v1')",
    )
    legacy_null = (
        "acquisition_candidate_id IS NULL AND selected_source_manifest_id IS NULL "
        "AND manifest_position IS NULL"
    )
    generic = (
        "schema_version = 'mirror.demo/D02GenericSourceAuthorityRecord/v1' "
        "AND evidence_root_id IS NULL AND root_name_receipt_digest IS NULL "
        "AND generation_preregistration_digest IS NULL AND source_allocation_manifest_digest IS NULL "
        "AND source_producer_dispatch_digest IS NULL AND source_generation_receipt_digest IS NULL "
        "AND output_name_receipt_digest IS NULL AND output_seal_receipt_digest IS NULL "
        "AND registry_commit_receipt_digest IS NULL AND generation_capability_authority_digest IS NULL "
        "AND generation_request_digest IS NULL AND execution_epoch = 'D02_AUTONOMOUS_V1' "
        "AND producer_task_id IS NULL AND dispatch_epoch IS NULL "
        "AND generation_source_asset_sha256 IS NULL AND generation_source_asset_byte_size IS NULL "
        "AND generation_source_asset_mime_type IS NULL AND generation_source_asset_width IS NULL "
        "AND generation_source_asset_height IS NULL AND source_normalization_receipt_digest IS NULL "
        "AND generation_policy_metadata IS NULL AND source_provenance_output_id IS NULL "
        "AND source_provenance_name_receipt_digest IS NULL "
        "AND source_provenance_seal_receipt_digest IS NULL "
        "AND source_provenance_registry_commit_receipt_digest IS NULL "
        "AND acquisition_candidate_id IS NOT NULL AND selected_source_manifest_id IS NOT NULL "
        "AND manifest_position BETWEEN 1 AND 4"
    )
    legacy_root = (
        "(schema_version = 'mirror.demo/D02R2SourceAuthorityRecord/v1' "
        "AND evidence_root_id = 'P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT' "
        "AND generation_request_digest IS NULL AND execution_epoch IS NULL AND producer_task_id IS NULL "
        "AND dispatch_epoch IS NULL AND generation_source_asset_sha256 IS NULL "
        "AND generation_source_asset_byte_size IS NULL AND generation_source_asset_mime_type IS NULL "
        "AND generation_source_asset_width IS NULL AND generation_source_asset_height IS NULL "
        "AND source_normalization_receipt_digest IS NULL AND generation_policy_metadata IS NULL) OR "
        "(schema_version = 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1' "
        "AND evidence_root_id = 'P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_02' AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_02' "
        "AND dispatch_epoch = 2 AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$' AND generation_policy_metadata IS NULL) OR "
        "(schema_version = 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1' "
        "AND evidence_root_id = 'P3_P7_D02_R2_E3_EVIDENCE_ROOT' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_03' AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_03' "
        "AND dispatch_epoch = 3 AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND jsonb_typeof(generation_policy_metadata) = 'object') OR "
        "(schema_version = 'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1' "
        "AND evidence_root_id = 'P3_P7_D02_R2_E4_EVIDENCE_ROOT' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_04' AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_04' "
        "AND dispatch_epoch = 4 AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND jsonb_typeof(generation_policy_metadata) = 'object')"
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_evidence_root"),
        table,
        f"(({legacy_root}) AND {legacy_null}) OR ({generic})",
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_opaque_output_ids"),
        table,
        "source_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$' AND "
        "(source_provenance_output_id IS NULL OR source_provenance_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')",
    )
    nullable_digests = (
        "root_name_receipt_digest",
        "generation_preregistration_digest",
        "source_allocation_manifest_digest",
        "source_producer_dispatch_digest",
        "source_generation_receipt_digest",
        "output_name_receipt_digest",
        "output_seal_receipt_digest",
        "registry_commit_receipt_digest",
        "generation_capability_authority_digest",
        "generation_request_digest",
        "generation_source_asset_sha256",
        "source_normalization_receipt_digest",
        "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest",
    )
    mandatory_digests = (
        "source_asset_sha256",
        "source_authority_key",
        "execution_contract_digest",
        "generation_request_policy_digest",
        "source_provenance_digest",
        "source_authority_digest",
        "source_qa_snapshot_digest",
    )
    digest_expression = " AND ".join(
        [f"{name} ~ '^[0-9a-f]{{64}}$'" for name in mandatory_digests]
        + [f"({name} IS NULL OR {name} ~ '^[0-9a-f]{{64}}$')" for name in nullable_digests]
    )
    op.create_check_constraint(op.f(f"ck_{table}_digest_shapes"), table, digest_expression)
    op.create_check_constraint(
        op.f(f"ck_{table}_generic_manifest_binding"),
        table,
        "(schema_version = 'mirror.demo/D02GenericSourceAuthorityRecord/v1' "
        "AND acquisition_candidate_id IS NOT NULL AND selected_source_manifest_id IS NOT NULL "
        "AND manifest_position BETWEEN 1 AND 4) OR "
        "(schema_version <> 'mirror.demo/D02GenericSourceAuthorityRecord/v1' "
        "AND acquisition_candidate_id IS NULL AND selected_source_manifest_id IS NULL "
        "AND manifest_position IS NULL)",
    )


def _create_source_v3_constraints() -> None:
    table = "demo_d02_r2_source_authorities"
    op.create_check_constraint(
        op.f(f"ck_{table}_schema_version_shape"),
        table,
        "schema_version IN ('mirror.demo/D02R2SourceAuthorityRecord/v1',"
        "'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1',"
        "'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1',"
        "'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_evidence_root"),
        table,
        "(schema_version = 'mirror.demo/D02R2SourceAuthorityRecord/v1' "
        "AND evidence_root_id = 'P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT' "
        "AND generation_request_digest IS NULL AND execution_epoch IS NULL "
        "AND producer_task_id IS NULL AND dispatch_epoch IS NULL "
        "AND generation_source_asset_sha256 IS NULL "
        "AND generation_source_asset_byte_size IS NULL "
        "AND generation_source_asset_mime_type IS NULL "
        "AND generation_source_asset_width IS NULL AND generation_source_asset_height IS NULL "
        "AND source_normalization_receipt_digest IS NULL AND generation_policy_metadata IS NULL) OR "
        "(schema_version = 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1' "
        "AND evidence_root_id = 'P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_02' "
        "AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_02' AND dispatch_epoch = 2 "
        "AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 "
        "AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND generation_policy_metadata IS NULL) OR "
        "(schema_version = 'mirror.demo/D02R2Epoch3SourceAuthorityRecord/v1' "
        "AND evidence_root_id = 'P3_P7_D02_R2_E3_EVIDENCE_ROOT' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_03' "
        "AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_03' AND dispatch_epoch = 3 "
        "AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 "
        "AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND jsonb_typeof(generation_policy_metadata) = 'object') OR "
        "(schema_version = 'mirror.demo/D02R2Epoch4SourceAuthorityRecord/v1' "
        "AND evidence_root_id = 'P3_P7_D02_R2_E4_EVIDENCE_ROOT' "
        "AND generation_request_digest = generation_request_policy_digest "
        "AND execution_epoch = 'D02_R2_EPOCH_04' "
        "AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_04' AND dispatch_epoch = 4 "
        "AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
        "AND generation_source_asset_byte_size > 0 "
        "AND generation_source_asset_mime_type = 'image/png' "
        "AND generation_source_asset_width > 0 AND generation_source_asset_height > 0 "
        "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$' "
        "AND jsonb_typeof(generation_policy_metadata) = 'object')",
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_opaque_output_ids"),
        table,
        "source_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$' "
        "AND source_provenance_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'",
    )
    mandatory = (
        "source_asset_sha256",
        "source_authority_key",
        "execution_contract_digest",
        "root_name_receipt_digest",
        "generation_preregistration_digest",
        "source_allocation_manifest_digest",
        "source_producer_dispatch_digest",
        "source_generation_receipt_digest",
        "output_name_receipt_digest",
        "output_seal_receipt_digest",
        "registry_commit_receipt_digest",
        "generation_capability_authority_digest",
        "generation_request_policy_digest",
        "source_provenance_digest",
        "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest",
        "source_authority_digest",
        "source_qa_snapshot_digest",
    )
    nullable = (
        "generation_request_digest",
        "generation_source_asset_sha256",
        "source_normalization_receipt_digest",
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_digest_shapes"),
        table,
        " AND ".join(
            [f"{name} ~ '^[0-9a-f]{{64}}$'" for name in mandatory]
            + [f"({name} IS NULL OR {name} ~ '^[0-9a-f]{{64}}$')" for name in nullable]
        ),
    )


def _replace_identity_constraints(include_generic: bool) -> None:
    table = "demo_synthetic_identities"
    for name in ("schema_version_shape", "source_mode_null_matrix"):
        op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    versions = (
        "schema_version IN ('mirror.demo/DemoSyntheticIdentity/v1',"
        "'mirror.demo/DemoSyntheticIdentity/v2','mirror.demo/DemoSyntheticIdentity/v3',"
        "'mirror.demo/DemoSyntheticIdentity/v4','mirror.demo/DemoSyntheticIdentity/v5')"
        if include_generic
        else "schema_version IN ('mirror.demo/DemoSyntheticIdentity/v1',"
        "'mirror.demo/DemoSyntheticIdentity/v2','mirror.demo/DemoSyntheticIdentity/v3',"
        "'mirror.demo/DemoSyntheticIdentity/v4')"
    )
    op.create_check_constraint(op.f(f"ck_{table}_schema_version_shape"), table, versions)
    generic_branch = (
        "(schema_version = 'mirror.demo/DemoSyntheticIdentity/v5' "
        "AND source_authority_kind = 'DEMO_R2_GENERATED_SOURCE' "
        "AND r2_source_authority_record_id IS NOT NULL AND formal_synthetic_identity_id IS NULL "
        "AND formal_accepted_qa_run_id IS NULL AND formal_accepted_qa_snapshot_digest IS NULL "
        "AND source_output_id IS NOT NULL AND source_receipt_digest IS NULL "
        "AND source_authority_digest IS NOT NULL AND source_qa_snapshot_digest IS NOT NULL "
        "AND source_landmark_digest IS NOT NULL AND source_measurement_digest IS NOT NULL "
        "AND source_provenance_digest IS NOT NULL AND source_fact_snapshot IS NOT NULL "
        "AND source_fact_snapshot_digest IS NOT NULL AND source_measurement_projection IS NOT NULL "
        "AND source_measurement_projection_digest IS NOT NULL "
        "AND original_formal_identity_id_status = 'NOT_APPLICABLE_D02_GENERIC_SOURCE' "
        "AND adult_synthetic_attested IS TRUE "
        "AND importer_version = 'demo-d02-generic-identity-importer-v1' "
        "AND import_config_digest IS NOT NULL) OR "
        if include_generic
        else ""
    )
    v4_branch = (
        "(schema_version = 'mirror.demo/DemoSyntheticIdentity/v4' "
        "AND source_authority_kind = 'DEMO_R2_GENERATED_SOURCE' "
        "AND r2_source_authority_record_id IS NOT NULL AND formal_synthetic_identity_id IS NULL "
        "AND formal_accepted_qa_run_id IS NULL AND formal_accepted_qa_snapshot_digest IS NULL "
        "AND source_output_id IS NOT NULL AND source_receipt_digest IS NOT NULL "
        "AND source_authority_digest IS NOT NULL AND source_qa_snapshot_digest IS NOT NULL "
        "AND source_landmark_digest IS NOT NULL AND source_measurement_digest IS NOT NULL "
        "AND source_provenance_digest IS NOT NULL AND source_fact_snapshot IS NOT NULL "
        "AND source_fact_snapshot_digest IS NOT NULL AND source_measurement_projection IS NOT NULL "
        "AND source_measurement_projection_digest IS NOT NULL "
        "AND original_formal_identity_id_status = 'NOT_APPLICABLE_DEMO_R2_GENERATED_SOURCE' "
        "AND adult_synthetic_attested IS TRUE AND importer_version = 'demo-d02-r2-identity-importer-v1' "
        "AND import_config_digest IS NOT NULL) OR "
    )
    legacy_exclusion = (
        "schema_version NOT IN ('mirror.demo/DemoSyntheticIdentity/v4','mirror.demo/DemoSyntheticIdentity/v5')"
        if include_generic
        else "schema_version <> 'mirror.demo/DemoSyntheticIdentity/v4'"
    )
    legacy_branch = (
        f"({legacy_exclusion} AND r2_source_authority_record_id IS NULL AND (("
        "source_authority_kind = 'FORMAL_REFERENCE' AND schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3' "
        "AND formal_synthetic_identity_id IS NOT NULL AND formal_accepted_qa_run_id IS NOT NULL "
        "AND formal_accepted_qa_snapshot_digest IS NOT NULL AND source_output_id IS NULL "
        "AND source_receipt_digest IS NULL AND source_authority_digest IS NULL "
        "AND source_qa_snapshot_digest IS NULL AND source_landmark_digest IS NULL "
        "AND source_measurement_digest IS NULL AND source_provenance_digest IS NULL "
        "AND source_fact_snapshot IS NULL AND source_fact_snapshot_digest IS NULL "
        "AND source_measurement_projection IS NULL AND source_measurement_projection_digest IS NULL "
        "AND original_formal_identity_id_status IS NULL AND adult_synthetic_attested IS NULL "
        "AND importer_version IS NULL AND import_config_digest IS NULL) OR ("
        "source_authority_kind = 'DEMO_LOCAL_IMPORTED_COPY' AND formal_synthetic_identity_id IS NULL "
        "AND formal_accepted_qa_run_id IS NULL AND formal_accepted_qa_snapshot_digest IS NULL "
        "AND source_output_id IS NOT NULL AND source_receipt_digest IS NOT NULL "
        "AND source_authority_digest IS NOT NULL AND source_qa_snapshot_digest IS NOT NULL "
        "AND source_landmark_digest IS NOT NULL AND source_measurement_digest IS NOT NULL "
        "AND source_provenance_digest IS NOT NULL AND source_fact_snapshot IS NOT NULL "
        "AND source_fact_snapshot_digest IS NOT NULL AND source_measurement_projection IS NOT NULL "
        "AND source_measurement_projection_digest IS NOT NULL "
        "AND original_formal_identity_id_status = 'UNKNOWN_REDACTED_NOT_RECOVERED' "
        "AND adult_synthetic_attested IS TRUE AND ((schema_version = 'mirror.demo/DemoSyntheticIdentity/v2' "
        "AND importer_version = 'demo-d02-identity-importer-v2') OR "
        "(schema_version = 'mirror.demo/DemoSyntheticIdentity/v3' "
        "AND importer_version = 'demo-d02-identity-importer-v3')) "
        "AND import_config_digest IS NOT NULL)))"
    )
    op.create_check_constraint(
        op.f(f"ck_{table}_source_mode_null_matrix"),
        table,
        generic_branch + v4_branch + legacy_branch,
    )


def _replace_admission_constraints(include_generic: bool) -> None:
    table = "demo_d02_r2_epoch2_admissions"
    for name in ("schema_version_shape", "epoch_root"):
        op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    schemas = (
        "schema_version IN ('mirror.demo/D02R2Epoch2Admission/v1',"
        "'mirror.demo/D02R2Epoch3Admission/v1','mirror.demo/D02R2Epoch4Admission/v1',"
        "'mirror.demo/D02GenericAdmission/v1')"
        if include_generic
        else "schema_version IN ('mirror.demo/D02R2Epoch2Admission/v1',"
        "'mirror.demo/D02R2Epoch3Admission/v1','mirror.demo/D02R2Epoch4Admission/v1')"
    )
    op.create_check_constraint(op.f(f"ck_{table}_schema_version_shape"), table, schemas)
    legacy = (
        "(schema_version = 'mirror.demo/D02R2Epoch2Admission/v1' AND execution_epoch = 'D02_R2_EPOCH_02' "
        "AND evidence_root_id = 'P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT' AND selected_source_manifest_id IS NULL) OR "
        "(schema_version = 'mirror.demo/D02R2Epoch3Admission/v1' AND execution_epoch = 'D02_R2_EPOCH_03' "
        "AND evidence_root_id = 'P3_P7_D02_R2_E3_EVIDENCE_ROOT' AND selected_source_manifest_id IS NULL) OR "
        "(schema_version = 'mirror.demo/D02R2Epoch4Admission/v1' AND execution_epoch = 'D02_R2_EPOCH_04' "
        "AND evidence_root_id = 'P3_P7_D02_R2_E4_EVIDENCE_ROOT' AND selected_source_manifest_id IS NULL)"
    )
    if include_generic:
        legacy += (
            " OR (schema_version = 'mirror.demo/D02GenericAdmission/v1' "
            "AND execution_epoch = 'D02_AUTONOMOUS_V1' AND evidence_root_id IS NULL "
            "AND selected_source_manifest_id IS NOT NULL)"
        )
    else:
        legacy = legacy.replace(" AND selected_source_manifest_id IS NULL", "")
    op.create_check_constraint(op.f(f"ck_{table}_epoch_root"), table, legacy)


def _set_legacy_bank_pair_dispatch(*, include_generic: bool) -> None:
    """Route generic v1 rows away from the frozen legacy v1/v2 validators."""

    bank = "demo_question_banks"
    pair = "demo_question_pairs"
    for table, trigger in (
        (bank, "trg_demo_d02_question_bank_insert"),
        (pair, "trg_demo_d02_question_pair_insert"),
        (bank, "trg_demo_d02_complete_bank_demo_question_banks"),
        (pair, "trg_demo_d02_complete_bank_demo_question_pairs"),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON {table}")
    bank_schemas = ["mirror.demo/DemoQuestionBank/v3"]
    pair_schemas = ["mirror.demo/DemoQuestionPair/v3"]
    if include_generic:
        bank_schemas.append("mirror.demo/D02GenericQuestionBank/v1")
        pair_schemas.append("mirror.demo/D02GenericQuestionPair/v1")
    bank_when = " WHEN (NEW.schema_version NOT IN ({}))".format(
        ",".join(f"'{schema}'" for schema in bank_schemas)
    )
    pair_when = " WHEN (NEW.schema_version NOT IN ({}))".format(
        ",".join(f"'{schema}'" for schema in pair_schemas)
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_question_bank_insert "
        "BEFORE INSERT ON demo_question_banks FOR EACH ROW"
        f"{bank_when} EXECUTE FUNCTION mirror_demo_validate_d02_question_bank_insert()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_question_pair_insert "
        "BEFORE INSERT ON demo_question_pairs FOR EACH ROW"
        f"{pair_when} EXECUTE FUNCTION mirror_demo_validate_d02_question_pair_insert()"
    )
    for table, when_clause in ((bank, bank_when), (pair, pair_when)):
        op.execute(
            f"CREATE CONSTRAINT TRIGGER trg_demo_d02_complete_bank_{table} "
            f"AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW"
            f"{when_clause} EXECUTE FUNCTION mirror_demo_validate_d02_complete_bank()"
        )


def _extend_generic_screening_contracts() -> None:
    report = "demo_pair_screening_reports"
    bank = "demo_question_banks"
    pair = "demo_question_pairs"
    _set_legacy_bank_pair_dispatch(include_generic=True)
    for name in ("schema_version_shape", "exact_schema_version", "r2_v3_exact_counts"):
        op.drop_constraint(op.f(f"ck_{report}_{name}"), report, type_="check")
    op.create_check_constraint(
        op.f(f"ck_{report}_schema_version_shape"),
        report,
        "schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2','mirror.demo/D02PairScreeningReport/v3','mirror.demo/D02GenericPairScreeningReport/v1')",
    )
    op.create_check_constraint(
        op.f(f"ck_{report}_exact_schema_version"),
        report,
        "schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2','mirror.demo/D02PairScreeningReport/v3','mirror.demo/D02GenericPairScreeningReport/v1')",
    )
    op.create_check_constraint(
        op.f(f"ck_{report}_r2_v3_exact_counts"),
        report,
        "(schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2') AND measurement_gate_count IS NULL AND decode_structure_record_count IS NULL) OR (schema_version IN ('mirror.demo/D02PairScreeningReport/v3','mirror.demo/D02GenericPairScreeningReport/v1') AND measurement_gate_count = 48 AND decode_structure_record_count = 48)",
    )
    for table, names, expression in (
        (
            bank,
            ("schema_version_shape", "versioned_dimension_manifest"),
            "schema_version IN ('mirror.demo/DemoQuestionBank/v1','mirror.demo/DemoQuestionBank/v2','mirror.demo/DemoQuestionBank/v3','mirror.demo/D02GenericQuestionBank/v1')",
        ),
        (
            pair,
            ("schema_version_shape", "versioned_report_binding"),
            "schema_version IN ('mirror.demo/DemoQuestionPair/v1','mirror.demo/DemoQuestionPair/v2','mirror.demo/DemoQuestionPair/v3','mirror.demo/D02GenericQuestionPair/v1')",
        ),
    ):
        for name in names:
            op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
        op.create_check_constraint(op.f(f"ck_{table}_schema_version_shape"), table, expression)
    op.create_check_constraint(
        op.f(f"ck_{bank}_versioned_dimension_manifest"),
        bank,
        "(schema_version = 'mirror.demo/DemoQuestionBank/v1' AND jsonb_typeof(dimension_manifest) = 'array' AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR (schema_version IN ('mirror.demo/DemoQuestionBank/v2','mirror.demo/DemoQuestionBank/v3','mirror.demo/D02GenericQuestionBank/v1') AND jsonb_typeof(dimension_manifest) = 'object' AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f(f"ck_{pair}_versioned_report_binding"),
        pair,
        "(schema_version = 'mirror.demo/DemoQuestionPair/v1' AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR (schema_version IN ('mirror.demo/DemoQuestionPair/v2','mirror.demo/DemoQuestionPair/v3','mirror.demo/D02GenericQuestionPair/v1') AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
    )
    op.execute(_GENERIC_SCREENING_TRIGGER_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_d02_generic_report BEFORE INSERT ON demo_pair_screening_reports FOR EACH ROW WHEN (NEW.schema_version = 'mirror.demo/D02GenericPairScreeningReport/v1') EXECUTE FUNCTION mirror_demo_validate_d02_generic_report()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_generic_bank BEFORE INSERT ON demo_question_banks FOR EACH ROW WHEN (NEW.schema_version = 'mirror.demo/D02GenericQuestionBank/v1') EXECUTE FUNCTION mirror_demo_validate_d02_generic_bank()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_generic_pair BEFORE INSERT ON demo_question_pairs FOR EACH ROW WHEN (NEW.schema_version = 'mirror.demo/D02GenericQuestionPair/v1') EXECUTE FUNCTION mirror_demo_validate_d02_generic_pair()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d02_generic_complete_bank_bank AFTER INSERT ON demo_question_banks DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_generic_complete_bank()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d02_generic_complete_bank_pair AFTER INSERT ON demo_question_pairs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_generic_complete_bank()"
    )


def _restore_generic_screening_contracts() -> None:
    report = "demo_pair_screening_reports"
    bank = "demo_question_banks"
    pair = "demo_question_pairs"
    for table, trigger in (
        (report, "trg_demo_d02_generic_report"),
        (bank, "trg_demo_d02_generic_bank"),
        (pair, "trg_demo_d02_generic_pair"),
        (bank, "trg_demo_d02_generic_complete_bank_bank"),
        (pair, "trg_demo_d02_generic_complete_bank_pair"),
    ):
        op.execute(f"DROP TRIGGER {trigger} ON {table}")
    for function in (
        "mirror_demo_validate_d02_generic_complete_bank()",
        "mirror_demo_validate_d02_generic_pair()",
        "mirror_demo_validate_d02_generic_bank()",
        "mirror_demo_validate_d02_generic_report()",
    ):
        op.execute(f"DROP FUNCTION {function}")
    for table, names in (
        (report, ("schema_version_shape", "exact_schema_version", "r2_v3_exact_counts")),
        (bank, ("schema_version_shape", "versioned_dimension_manifest")),
        (pair, ("schema_version_shape", "versioned_report_binding")),
    ):
        for name in names:
            op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(
        op.f(f"ck_{report}_schema_version_shape"),
        report,
        "schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2','mirror.demo/D02PairScreeningReport/v3')",
    )
    op.create_check_constraint(
        op.f(f"ck_{report}_exact_schema_version"),
        report,
        "schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2','mirror.demo/D02PairScreeningReport/v3')",
    )
    op.create_check_constraint(
        op.f(f"ck_{report}_r2_v3_exact_counts"),
        report,
        "(schema_version IN ('mirror.demo/D02PairScreeningReport/v1','mirror.demo/D02PairScreeningReport/v2') AND measurement_gate_count IS NULL AND decode_structure_record_count IS NULL) OR (schema_version = 'mirror.demo/D02PairScreeningReport/v3' AND measurement_gate_count = 48 AND decode_structure_record_count = 48)",
    )
    op.create_check_constraint(
        op.f(f"ck_{bank}_schema_version_shape"),
        bank,
        "schema_version IN ('mirror.demo/DemoQuestionBank/v1','mirror.demo/DemoQuestionBank/v2','mirror.demo/DemoQuestionBank/v3')",
    )
    op.create_check_constraint(
        op.f(f"ck_{bank}_versioned_dimension_manifest"),
        bank,
        "(schema_version = 'mirror.demo/DemoQuestionBank/v1' AND jsonb_typeof(dimension_manifest) = 'array' AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR (schema_version IN ('mirror.demo/DemoQuestionBank/v2','mirror.demo/DemoQuestionBank/v3') AND jsonb_typeof(dimension_manifest) = 'object' AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f(f"ck_{pair}_schema_version_shape"),
        pair,
        "schema_version IN ('mirror.demo/DemoQuestionPair/v1','mirror.demo/DemoQuestionPair/v2','mirror.demo/DemoQuestionPair/v3')",
    )
    op.create_check_constraint(
        op.f(f"ck_{pair}_versioned_report_binding"),
        pair,
        "(schema_version = 'mirror.demo/DemoQuestionPair/v1' AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR (schema_version IN ('mirror.demo/DemoQuestionPair/v2','mirror.demo/DemoQuestionPair/v3') AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
    )
    _set_legacy_bank_pair_dispatch(include_generic=False)


def _extend_generic_source_and_admission() -> None:
    source = "demo_d02_r2_source_authorities"
    nullable_columns = (
        "evidence_root_id",
        "root_name_receipt_digest",
        "generation_preregistration_digest",
        "source_allocation_manifest_digest",
        "source_producer_dispatch_digest",
        "source_generation_receipt_digest",
        "output_name_receipt_digest",
        "output_seal_receipt_digest",
        "registry_commit_receipt_digest",
        "generation_capability_authority_digest",
        "source_provenance_output_id",
        "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest",
    )
    _drop_source_version_constraints()
    for column in nullable_columns:
        op.alter_column(source, column, existing_type=sa.String(), nullable=True)
    op.add_column(source, sa.Column("acquisition_candidate_id", sa.String(length=32)))
    op.add_column(source, sa.Column("selected_source_manifest_id", sa.String(length=32)))
    op.add_column(source, sa.Column("manifest_position", sa.SmallInteger()))
    op.create_foreign_key(
        op.f(
            "fk_demo_d02_r2_source_authorities_acquisition_candidate_id_demo_d02_source_candidates"
        ),
        source,
        "demo_d02_source_candidates",
        ["acquisition_candidate_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f(
            "fk_demo_d02_r2_source_authorities_selected_source_manifest_id_demo_d02_selected_source_manifests"
        ),
        source,
        "demo_d02_selected_source_manifests",
        ["selected_source_manifest_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_demo_d02_r2_source_authorities_acquisition_candidate_id"),
        source,
        ["acquisition_candidate_id"],
    )
    op.create_index(
        op.f("ix_demo_d02_r2_source_authorities_selected_source_manifest_id"),
        source,
        ["selected_source_manifest_id"],
    )
    op.create_unique_constraint("acquisition_candidate_id", source, ["acquisition_candidate_id"])
    op.create_unique_constraint(
        "manifest_position", source, ["selected_source_manifest_id", "manifest_position"]
    )
    _create_source_v4_constraints()
    op.execute(
        "ALTER FUNCTION mirror_demo_validate_d02_r2_source_authority() "
        "RENAME TO mirror_demo_validate_d02_r2_source_authority_pre_0015"
    )
    op.execute("DROP TRIGGER trg_demo_d02_r2_source_authority ON demo_d02_r2_source_authorities")
    op.execute(_SOURCE_TRIGGER_V4_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_d02_r2_source_authority "
        "BEFORE INSERT OR UPDATE OR DELETE ON demo_d02_r2_source_authorities "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_r2_source_authority()"
    )
    _replace_identity_constraints(True)
    op.execute(_GENERIC_IDENTITY_TRIGGER_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_d02_generic_identity BEFORE INSERT ON demo_synthetic_identities "
        "FOR EACH ROW WHEN (NEW.schema_version = 'mirror.demo/DemoSyntheticIdentity/v5') "
        "EXECUTE FUNCTION mirror_demo_validate_d02_generic_identity()"
    )

    admission = "demo_d02_r2_epoch2_admissions"
    _replace_admission_constraints(False)
    op.alter_column(
        admission, "evidence_root_id", existing_type=sa.String(length=128), nullable=True
    )
    op.add_column(admission, sa.Column("selected_source_manifest_id", sa.String(length=32)))
    op.create_foreign_key(
        op.f(
            "fk_demo_d02_r2_epoch2_admissions_selected_source_manifest_id_demo_d02_selected_source_manifests"
        ),
        admission,
        "demo_d02_selected_source_manifests",
        ["selected_source_manifest_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_demo_d02_r2_epoch2_admissions_selected_source_manifest_id"),
        admission,
        ["selected_source_manifest_id"],
    )
    op.create_unique_constraint(
        "selected_source_manifest_id", admission, ["selected_source_manifest_id"]
    )
    _replace_admission_constraints(True)
    op.execute(
        "DROP TRIGGER trg_demo_authority_demo_d02_r2_epoch2_admissions ON demo_d02_r2_epoch2_admissions"
    )
    op.execute(_ADMISSION_AUTHORITY_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_authority_demo_d02_r2_epoch2_admissions "
        "BEFORE INSERT OR UPDATE OR DELETE ON demo_d02_r2_epoch2_admissions "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_d02_admission()"
    )
    op.execute(
        "ALTER FUNCTION mirror_demo_validate_d02_r2_epoch2_admission() "
        "RENAME TO mirror_demo_validate_d02_r2_epoch2_admission_pre_0015"
    )
    op.execute(
        "DROP TRIGGER trg_demo_d02_r2_epoch2_admission_integrity ON demo_d02_r2_epoch2_admissions"
    )
    op.execute(_ADMISSION_TRIGGER_V4_SQL)
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d02_r2_epoch2_admission_integrity "
        "AFTER INSERT ON demo_d02_r2_epoch2_admissions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_r2_epoch2_admission()"
    )


def upgrade() -> None:
    op.execute(_R2_SOURCE_KEY_CALLED_ON_NULL_SQL)
    op.execute(_authority_projection_sql(include_generic_identity=True))
    _install_generic_write_guard()
    _create_acquisition_tables()
    _extend_generic_source_and_admission()
    _extend_generic_screening_contracts()


def downgrade() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (SELECT 1 FROM demo_d02_cohort_specs)
               OR EXISTS (SELECT 1 FROM demo_d02_source_acquisition_runs)
               OR EXISTS (SELECT 1 FROM demo_d02_source_acquisition_events)
               OR EXISTS (SELECT 1 FROM demo_d02_source_candidates)
               OR EXISTS (SELECT 1 FROM demo_d02_selected_source_manifests)
               OR EXISTS (
                   SELECT 1 FROM demo_d02_r2_source_authorities
                   WHERE schema_version = 'mirror.demo/D02GenericSourceAuthorityRecord/v1'
               ) OR EXISTS (
                   SELECT 1 FROM demo_synthetic_identities
                   WHERE schema_version = 'mirror.demo/DemoSyntheticIdentity/v5'
                ) OR EXISTS (
                    SELECT 1 FROM demo_d02_r2_epoch2_admissions
                    WHERE schema_version = 'mirror.demo/D02GenericAdmission/v1'
                ) OR EXISTS (
                    SELECT 1 FROM demo_pair_screening_reports
                    WHERE schema_version = 'mirror.demo/D02GenericPairScreeningReport/v1'
                ) OR EXISTS (
                    SELECT 1 FROM demo_question_banks
                    WHERE schema_version = 'mirror.demo/D02GenericQuestionBank/v1'
                ) OR EXISTS (
                    SELECT 1 FROM demo_question_pairs
                    WHERE schema_version = 'mirror.demo/D02GenericQuestionPair/v1'
                ) THEN
                RAISE EXCEPTION 'D02 autonomous acquisition authority exists; downgrade is forbidden';
            END IF;
        END;
        $block$;
        """
    )
    _restore_write_guard_v10()
    _restore_generic_screening_contracts()
    admission = "demo_d02_r2_epoch2_admissions"
    op.execute(
        "DROP TRIGGER trg_demo_d02_r2_epoch2_admission_integrity ON demo_d02_r2_epoch2_admissions"
    )
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_epoch2_admission()")
    op.execute(
        "ALTER FUNCTION mirror_demo_validate_d02_r2_epoch2_admission_pre_0015() "
        "RENAME TO mirror_demo_validate_d02_r2_epoch2_admission"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d02_r2_epoch2_admission_integrity "
        "AFTER INSERT ON demo_d02_r2_epoch2_admissions DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_r2_epoch2_admission()"
    )
    op.execute(
        "DROP TRIGGER trg_demo_authority_demo_d02_r2_epoch2_admissions ON demo_d02_r2_epoch2_admissions"
    )
    op.execute("DROP FUNCTION mirror_demo_guard_d02_admission()")
    op.execute(
        "CREATE TRIGGER trg_demo_authority_demo_d02_r2_epoch2_admissions "
        "BEFORE INSERT OR UPDATE OR DELETE ON demo_d02_r2_epoch2_admissions "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
    )
    # demo_0014 will restore the legacy integrity function when this revision is removed.
    op.drop_constraint("selected_source_manifest_id", admission, type_="unique")
    op.drop_index(
        op.f("ix_demo_d02_r2_epoch2_admissions_selected_source_manifest_id"), table_name=admission
    )
    op.drop_constraint(
        op.f(
            "fk_demo_d02_r2_epoch2_admissions_selected_source_manifest_id_demo_d02_selected_source_manifests"
        ),
        admission,
        type_="foreignkey",
    )
    _replace_admission_constraints(False)
    op.drop_column(admission, "selected_source_manifest_id")
    op.alter_column(
        admission, "evidence_root_id", existing_type=sa.String(length=128), nullable=False
    )

    _replace_identity_constraints(False)
    op.execute("DROP TRIGGER trg_demo_d02_generic_identity ON demo_synthetic_identities")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_generic_identity()")
    source = "demo_d02_r2_source_authorities"
    op.execute("DROP TRIGGER trg_demo_d02_r2_source_authority ON demo_d02_r2_source_authorities")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_r2_source_authority()")
    op.drop_constraint(op.f(f"ck_{source}_generic_manifest_binding"), source, type_="check")
    _drop_source_version_constraints()
    op.drop_constraint("manifest_position", source, type_="unique")
    op.drop_constraint("acquisition_candidate_id", source, type_="unique")
    op.drop_index(
        op.f("ix_demo_d02_r2_source_authorities_selected_source_manifest_id"), table_name=source
    )
    op.drop_index(
        op.f("ix_demo_d02_r2_source_authorities_acquisition_candidate_id"), table_name=source
    )
    op.drop_constraint(
        op.f(
            "fk_demo_d02_r2_source_authorities_selected_source_manifest_id_demo_d02_selected_source_manifests"
        ),
        source,
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f(
            "fk_demo_d02_r2_source_authorities_acquisition_candidate_id_demo_d02_source_candidates"
        ),
        source,
        type_="foreignkey",
    )
    op.drop_column(source, "manifest_position")
    op.drop_column(source, "selected_source_manifest_id")
    op.drop_column(source, "acquisition_candidate_id")
    for column in (
        "evidence_root_id",
        "root_name_receipt_digest",
        "generation_preregistration_digest",
        "source_allocation_manifest_digest",
        "source_producer_dispatch_digest",
        "source_generation_receipt_digest",
        "output_name_receipt_digest",
        "output_seal_receipt_digest",
        "registry_commit_receipt_digest",
        "generation_capability_authority_digest",
        "source_provenance_output_id",
        "source_provenance_name_receipt_digest",
        "source_provenance_seal_receipt_digest",
        "source_provenance_registry_commit_receipt_digest",
    ):
        op.alter_column(source, column, existing_type=sa.String(), nullable=False)
    _create_source_v3_constraints()
    op.execute(
        "ALTER FUNCTION mirror_demo_validate_d02_r2_source_authority_pre_0015() "
        "RENAME TO mirror_demo_validate_d02_r2_source_authority"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d02_r2_source_authority "
        "BEFORE INSERT OR UPDATE OR DELETE ON demo_d02_r2_source_authorities "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d02_r2_source_authority()"
    )

    for table in (
        "demo_d02_selected_source_manifests",
        "demo_d02_source_acquisition_events",
        "demo_d02_source_candidates",
        "demo_d02_source_acquisition_runs",
        "demo_d02_cohort_specs",
    ):
        op.execute(f"DROP TRIGGER trg_{table}_authority ON {table}")
    op.execute(
        "DROP TRIGGER trg_demo_d02_events_budget_consistency ON demo_d02_source_acquisition_events"
    )
    op.execute(
        "DROP TRIGGER trg_demo_d02_runs_budget_consistency ON demo_d02_source_acquisition_runs"
    )
    op.execute("DROP FUNCTION mirror_demo_validate_d02_budget_consistency()")
    op.execute("DROP FUNCTION mirror_demo_validate_d02_acquisition_row()")
    op.drop_table("demo_d02_selected_source_manifests")
    op.drop_table("demo_d02_source_acquisition_events")
    op.drop_table("demo_d02_source_candidates")
    op.drop_table("demo_d02_source_acquisition_runs")
    op.drop_table("demo_d02_cohort_specs")
    op.execute(_authority_projection_sql(include_generic_identity=False))
    op.execute(_R2_SOURCE_KEY_STRICT_SQL)
