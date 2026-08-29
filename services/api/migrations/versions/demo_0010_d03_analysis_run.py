"""Add the Demo-only D03 analysis request and execution authority.

Revision ID: demo_0010_d03_analysis_run
Revises: demo_0009_d02_r2_e2_adm
Create Date: 2026-08-29

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

# The migration composes SQL only from its own frozen literal variants.
# ruff: noqa: S608

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0010_d03_analysis_run"
down_revision: str | None = "demo_0009_d02_r2_e2_adm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"


def _authority_projection_sql(*, schema_aware: bool) -> str:
    face_observation_projection = (
        """
    IF authority_table = 'demo_face_observations'
       AND row_data ->> 'schema_version' = 'mirror.demo/DemoFaceObservation/v1' THEN
        projected := projected - 'analysis_run_id';
    END IF;
"""
        if schema_aware
        else ""
    )
    d02_r2_compatibility_projection = r"""
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
       AND row_data ->> 'schema_version' =
           'mirror.demo/D02PairScreeningReport/v3' THEN
        projected := projected - 'report_digest';
    END IF;
"""
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
{d02_r2_compatibility_projection}
{face_observation_projection}
    IF authority_table NOT LIKE 'demo\_%' ESCAPE E'\\' THEN
        RAISE EXCEPTION 'Demo authority projection rejected unexpected table %', authority_table;
    END IF;
    RETURN projected;
END;
$function$;
"""


def _job_binding_sql(*, analysis_target: str, include_analysis_run: bool) -> str:
    analysis_case = (
        """
        WHEN 'ANALYSIS_RUN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_analysis_runs target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
"""
        if include_analysis_run
        else ""
    )
    return f"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_job_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_target_type text;
    expected_job_hash text;
    target_valid boolean := false;
    job_row jobs%ROWTYPE;
BEGIN
    expected_target_type := CASE NEW.endpoint_operation
        WHEN 'analysis.create' THEN '{analysis_target}'
        WHEN 'questionnaire.run.create' THEN 'QUESTIONNAIRE_RUN'
        WHEN 'profile.compile' THEN 'DEMO_ACTOR'
        WHEN 'editing_session.create' THEN 'EDITING_SESSION'
        WHEN 'edit_plan.create' THEN 'EDIT_PLAN'
        WHEN 'edit_plan.execute' THEN 'EDIT_PLAN'
        WHEN 'image_version.restore' THEN 'IMAGE_VERSION'
        WHEN 'profile.rebuild' THEN 'DEMO_ACTOR'
        WHEN 'self_transfer.execute' THEN 'SELF_TRANSFER_RUN'
        WHEN 'tool.verify' THEN 'TOOL_RUN'
        WHEN 'context.compile' THEN 'DEMO_SESSION'
        ELSE NULL
    END;
    IF expected_target_type IS NULL OR NEW.target_type <> expected_target_type THEN
        RAISE EXCEPTION 'Demo endpoint and typed target disagree';
    END IF;

    CASE NEW.target_type
        WHEN 'DEMO_ACTOR' THEN
            target_valid := NEW.target_id = NEW.demo_actor_id
                AND EXISTS (SELECT 1 FROM demo_actors WHERE id = NEW.demo_actor_id);
        WHEN 'DEMO_SESSION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL
                AND NEW.target_id = NEW.demo_session_id
                AND EXISTS (
                    SELECT 1 FROM demo_sessions target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                );
{analysis_case}
        WHEN 'FACE_OBSERVATION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_face_observations target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'QUESTIONNAIRE_RUN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_questionnaire_runs target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'SELF_TRANSFER_RUN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_self_transfer_runs target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.record_kind = 'REQUEST'
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'EDITING_SESSION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_editing_sessions target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'IMAGE_VERSION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_image_versions target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'EDIT_PLAN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_edit_plans target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'EDIT_OPERATION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_edit_operations target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'TOOL_RUN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1
                FROM demo_tool_runs target_row
                JOIN demo_job_bindings execution_binding
                  ON execution_binding.id = target_row.demo_job_binding_id
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
                  AND execution_binding.demo_actor_id = NEW.demo_actor_id
            );
    END CASE;
    IF NOT target_valid THEN
        RAISE EXCEPTION 'Demo job binding target ownership mismatch';
    END IF;

    SELECT * INTO job_row FROM jobs WHERE id = NEW.job_id FOR KEY SHARE;
    expected_job_hash := encode(
        sha256(
            convert_to(
                'mirror.demo/JobIdempotency/v1' || E'\n' || NEW.demo_actor_id || E'\n' ||
                NEW.endpoint_operation || E'\n' || NEW.idempotency_key_hash,
                'UTF8'
            )
        ),
        'hex'
    );
    IF NOT FOUND
        OR job_row.job_type <> ('demo_p3_p7.' || NEW.endpoint_operation)
        OR job_row.idempotency_key_hash <> expected_job_hash
        OR job_row.status <> 'PENDING'
        OR job_row.owner_user_id IS NOT NULL
        OR job_row.ingestion_upload_intent_id IS NOT NULL
        OR job_row.payload::jsonb <> '{{}}'::jsonb
        OR job_row.attempt_count <> 0
        OR job_row.lease_token IS NOT NULL
        OR job_row.lease_acquired_at IS NOT NULL
        OR job_row.lease_expires_at IS NOT NULL
        OR job_row.finalized_at IS NOT NULL
        OR job_row.result_asset_id IS NOT NULL
        OR job_row.result_code IS NOT NULL THEN
        RAISE EXCEPTION 'Formal Job is not a valid pending Demo execution envelope';
    END IF;
    RETURN NEW;
END;
$function$;
"""


_D03_AUTHORITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_analysis_run()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    session_row demo_sessions%ROWTYPE;
    identity_row demo_synthetic_identities%ROWTYPE;
BEGIN
    IF TG_OP IS DISTINCT FROM 'INSERT' THEN
        RAISE EXCEPTION 'Demo AnalysisRun is append-only';
    END IF;
    IF NEW.schema_version <> 'mirror.demo/DemoAnalysisRun/v1' THEN
        RAISE EXCEPTION 'Demo AnalysisRun schema is unsupported';
    END IF;
    SELECT * INTO session_row
    FROM demo_sessions
    WHERE id = NEW.demo_session_id AND demo_actor_id = NEW.demo_actor_id;
    IF NOT FOUND OR session_row.closed_at IS NOT NULL OR session_row.tombstoned_at IS NOT NULL
       OR session_row.expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'Demo AnalysisRun requires an active owned Session';
    END IF;
    IF session_row.config IS DISTINCT FROM jsonb_build_object(
        'schema_version', 'mirror.demo/DemoSessionConfig/v1',
        'synthetic_identity_id', NEW.demo_synthetic_identity_id
    ) THEN
        RAISE EXCEPTION 'Demo AnalysisRun Session identity configuration is invalid';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM demo_actors actor_row
        WHERE actor_row.id = NEW.demo_actor_id AND actor_row.tombstoned_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Demo AnalysisRun actor is unavailable';
    END IF;
    PERFORM mirror_demo_require_current_synthetic_admission(NEW.demo_synthetic_identity_id);
    SELECT * INTO identity_row
    FROM demo_synthetic_identities
    WHERE id = NEW.demo_synthetic_identity_id;
    IF identity_row.formal_canonical_asset_id IS DISTINCT FROM NEW.source_asset_id
       OR identity_row.formal_canonical_asset_sha256 IS DISTINCT FROM NEW.source_asset_sha256 THEN
        RAISE EXCEPTION 'Demo AnalysisRun source differs from current identity authority';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_analysis_run_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    authority_run_id text;
    run_row demo_analysis_runs%ROWTYPE;
    binding_row demo_job_bindings%ROWTYPE;
    job_row jobs%ROWTYPE;
BEGIN
    IF TG_TABLE_NAME = 'demo_analysis_runs' THEN
        authority_run_id := NEW.id;
    ELSIF NEW.target_type = 'ANALYSIS_RUN' THEN
        authority_run_id := NEW.target_id;
    ELSE
        RETURN NULL;
    END IF;
    SELECT * INTO run_row FROM demo_analysis_runs WHERE id = authority_run_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo AnalysisRun reverse binding lacks run';
    END IF;
    SELECT * INTO binding_row FROM demo_job_bindings WHERE id = run_row.demo_job_binding_id;
    IF NOT FOUND
       OR binding_row.id IS DISTINCT FROM run_row.demo_job_binding_id
       OR binding_row.demo_actor_id IS DISTINCT FROM run_row.demo_actor_id
       OR binding_row.demo_session_id IS DISTINCT FROM run_row.demo_session_id
       OR binding_row.endpoint_operation <> 'analysis.create'
       OR binding_row.target_type <> 'ANALYSIS_RUN'
       OR binding_row.target_id IS DISTINCT FROM run_row.id THEN
        RAISE EXCEPTION 'Demo AnalysisRun reverse binding is inconsistent';
    END IF;
    SELECT * INTO job_row FROM jobs WHERE id = binding_row.job_id;
    IF NOT FOUND OR job_row.job_type <> 'demo_p3_p7.analysis.create' THEN
        RAISE EXCEPTION 'Demo AnalysisRun binding lacks its exact formal Job';
    END IF;
    RETURN NULL;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d03_result_row()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    run_row demo_analysis_runs%ROWTYPE;
BEGIN
    CASE TG_TABLE_NAME
        WHEN 'demo_face_observations' THEN
            IF NEW.schema_version <> 'mirror.demo/DemoFaceObservation/v2'
               OR NEW.analysis_run_id IS NULL THEN
                RAISE EXCEPTION 'New Demo FaceObservation requires v2 AnalysisRun authority';
            END IF;
            SELECT * INTO run_row FROM demo_analysis_runs WHERE id = NEW.analysis_run_id;
            IF NOT FOUND
               OR NEW.demo_actor_id IS DISTINCT FROM run_row.demo_actor_id
               OR NEW.demo_session_id IS DISTINCT FROM run_row.demo_session_id
               OR NEW.demo_synthetic_identity_id IS DISTINCT FROM run_row.demo_synthetic_identity_id
               OR NEW.source_asset_id IS DISTINCT FROM run_row.source_asset_id
               OR NEW.source_asset_sha256 IS DISTINCT FROM run_row.source_asset_sha256
               OR NEW.analyzer_version IS DISTINCT FROM run_row.analyzer_version
               OR NEW.runtime_manifest_digest IS DISTINCT FROM run_row.runtime_manifest_digest
               OR NEW.config_digest IS DISTINCT FROM run_row.observation_config_digest
               OR NEW.repeat_count IS DISTINCT FROM run_row.repeat_count THEN
                RAISE EXCEPTION 'Demo FaceObservation differs from AnalysisRun authority';
            END IF;
        WHEN 'demo_face_observation_repeats' THEN
            SELECT analysis_row.* INTO run_row
            FROM demo_face_observations observation_row
            JOIN demo_analysis_runs analysis_row
              ON analysis_row.id = observation_row.analysis_run_id
            WHERE observation_row.id = NEW.observation_id
              AND observation_row.demo_actor_id = NEW.demo_actor_id
              AND observation_row.demo_session_id = NEW.demo_session_id;
            IF NOT FOUND
               OR NEW.runtime_manifest_digest IS DISTINCT FROM run_row.runtime_manifest_digest
               OR NEW.model_manifest_digest IS DISTINCT FROM run_row.model_manifest_digest THEN
                RAISE EXCEPTION 'Demo FaceObservation repeat differs from AnalysisRun authority';
            END IF;
        WHEN 'demo_baseline_face_models' THEN
            SELECT analysis_row.* INTO run_row
            FROM demo_face_observations observation_row
            JOIN demo_analysis_runs analysis_row
              ON analysis_row.id = observation_row.analysis_run_id
            WHERE observation_row.id = NEW.observation_id
              AND observation_row.demo_actor_id = NEW.demo_actor_id
              AND observation_row.demo_session_id = NEW.demo_session_id;
            IF NOT FOUND
               OR NEW.aggregation_version IS DISTINCT FROM run_row.baseline_aggregation_version
               OR NEW.measurement_version IS DISTINCT FROM run_row.measurement_version THEN
                RAISE EXCEPTION 'Demo BaselineFaceModel differs from AnalysisRun authority';
            END IF;
        WHEN 'demo_self_states' THEN
            SELECT analysis_row.* INTO run_row
            FROM demo_baseline_face_models baseline_row
            JOIN demo_face_observations observation_row
              ON observation_row.id = baseline_row.observation_id
            JOIN demo_analysis_runs analysis_row
              ON analysis_row.id = observation_row.analysis_run_id
            WHERE baseline_row.id = NEW.baseline_face_model_id
              AND baseline_row.demo_actor_id = NEW.demo_actor_id
              AND baseline_row.demo_session_id = NEW.demo_session_id;
            IF NOT FOUND
               OR NEW.ontology_version IS DISTINCT FROM run_row.self_state_ontology_version
               OR NEW.derivation_version IS DISTINCT FROM run_row.self_state_derivation_version THEN
                RAISE EXCEPTION 'Demo SelfState differs from AnalysisRun authority';
            END IF;
    END CASE;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_guard_d03_job_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.job_type <> 'demo_p3_p7.analysis.create'
       AND (TG_OP = 'INSERT' OR OLD.job_type <> 'demo_p3_p7.analysis.create') THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'PENDING' OR NEW.attempt_count <> 0 THEN
            RAISE EXCEPTION 'D03 Job must be created PENDING with zero attempts';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.job_type IS DISTINCT FROM OLD.job_type
       OR NEW.idempotency_key_hash IS DISTINCT FROM OLD.idempotency_key_hash
       OR NEW.request_id IS DISTINCT FROM OLD.request_id
       OR NEW.payload::jsonb IS DISTINCT FROM OLD.payload::jsonb
       OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id
       OR NEW.ingestion_upload_intent_id IS DISTINCT FROM OLD.ingestion_upload_intent_id
       OR NEW.result_asset_id IS DISTINCT FROM OLD.result_asset_id THEN
        RAISE EXCEPTION 'D03 Job immutable envelope changed';
    END IF;
    IF OLD.status = 'PENDING' AND NEW.status = 'RUNNING' THEN
        IF NEW.attempt_count <> OLD.attempt_count + 1 THEN
            RAISE EXCEPTION 'D03 Job claim must create exactly one attempt';
        END IF;
    ELSIF OLD.status = 'PENDING' AND NEW.status = 'CANCELLED' THEN
        IF NEW.attempt_count <> 0 THEN
            RAISE EXCEPTION 'D03 pre-claim cancellation cannot create an attempt';
        END IF;
    ELSIF OLD.status = 'RUNNING'
          AND NEW.status IN ('COMPLETED','REJECTED','FAILED','CANCELLED') THEN
        IF NEW.attempt_count <> OLD.attempt_count THEN
            RAISE EXCEPTION 'D03 terminal transition cannot change attempt count';
        END IF;
    ELSE
        RAISE EXCEPTION 'Illegal D03 Job transition % to %', OLD.status, NEW.status;
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d03_result_publication()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    authority_run_id text;
    job_row jobs%ROWTYPE;
BEGIN
    CASE TG_TABLE_NAME
        WHEN 'demo_face_observations' THEN
            authority_run_id := NEW.analysis_run_id;
        WHEN 'demo_face_observation_repeats' THEN
            SELECT observation_row.analysis_run_id INTO authority_run_id
            FROM demo_face_observations observation_row
            WHERE observation_row.id = NEW.observation_id;
        WHEN 'demo_baseline_face_models' THEN
            SELECT observation_row.analysis_run_id INTO authority_run_id
            FROM demo_face_observations observation_row
            WHERE observation_row.id = NEW.observation_id;
        WHEN 'demo_self_states' THEN
            SELECT observation_row.analysis_run_id INTO authority_run_id
            FROM demo_baseline_face_models baseline_row
            JOIN demo_face_observations observation_row
              ON observation_row.id = baseline_row.observation_id
            WHERE baseline_row.id = NEW.baseline_face_model_id;
    END CASE;
    SELECT job.* INTO job_row
    FROM demo_analysis_runs run_row
    JOIN demo_job_bindings binding_row ON binding_row.id = run_row.demo_job_binding_id
    JOIN jobs job ON job.id = binding_row.job_id
    WHERE run_row.id = authority_run_id;
    IF NOT FOUND OR job_row.status <> 'COMPLETED' THEN
        RAISE EXCEPTION 'D03 result authority must publish atomically with COMPLETED Job';
    END IF;
    PERFORM mirror_demo_require_d03_job_state(job_row.id);
    RETURN NULL;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_require_d03_job_state(target_job_id text)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    job_row jobs%ROWTYPE;
    binding_row demo_job_bindings%ROWTYPE;
    run_row demo_analysis_runs%ROWTYPE;
    attempt_row job_attempts%ROWTYPE;
    observation_row demo_face_observations%ROWTYPE;
    observation_found boolean;
    attempt_total integer;
    repeat_total integer;
    baseline_total integer;
    self_state_total integer;
BEGIN
    SELECT * INTO job_row FROM jobs WHERE id = target_job_id;
    IF NOT FOUND OR job_row.job_type <> 'demo_p3_p7.analysis.create' THEN
        RETURN;
    END IF;
    SELECT * INTO binding_row FROM demo_job_bindings WHERE job_id = job_row.id;
    IF NOT FOUND OR binding_row.endpoint_operation <> 'analysis.create'
       OR binding_row.target_type <> 'ANALYSIS_RUN' THEN
        RAISE EXCEPTION 'D03 Job lacks exact Demo binding';
    END IF;
    SELECT * INTO run_row FROM demo_analysis_runs WHERE id = binding_row.target_id;
    IF NOT FOUND OR run_row.demo_job_binding_id IS DISTINCT FROM binding_row.id THEN
        RAISE EXCEPTION 'D03 Job lacks exact AnalysisRun authority';
    END IF;
    IF job_row.owner_user_id IS NOT NULL
       OR job_row.ingestion_upload_intent_id IS NOT NULL
       OR job_row.payload::jsonb <> '{}'::jsonb
       OR job_row.result_asset_id IS NOT NULL THEN
        RAISE EXCEPTION 'D03 Job envelope is invalid';
    END IF;
    SELECT count(*) INTO attempt_total FROM job_attempts WHERE job_id = job_row.id;
    IF attempt_total <> job_row.attempt_count THEN
        RAISE EXCEPTION 'D03 Job requires exactly its declared Attempt cardinality';
    END IF;
    IF job_row.status = 'PENDING' THEN
        IF job_row.attempt_count <> 0 OR job_row.lease_token IS NOT NULL
           OR job_row.lease_acquired_at IS NOT NULL OR job_row.lease_expires_at IS NOT NULL
           OR job_row.finalized_at IS NOT NULL OR job_row.result_code IS NOT NULL
           OR EXISTS (SELECT 1 FROM job_attempts WHERE job_id = job_row.id) THEN
            RAISE EXCEPTION 'D03 PENDING Job shape is invalid';
        END IF;
        RETURN;
    END IF;
    IF job_row.status = 'RUNNING' THEN
        SELECT * INTO attempt_row FROM job_attempts
        WHERE job_id = job_row.id AND attempt = job_row.attempt_count;
        IF job_row.attempt_count <> 1 OR job_row.lease_token IS NULL
           OR job_row.lease_acquired_at IS NULL
           OR job_row.lease_expires_at <= job_row.lease_acquired_at
           OR job_row.finalized_at IS NOT NULL OR job_row.result_code IS NOT NULL
           OR NOT FOUND OR attempt_row.status <> 'RUNNING'
           OR attempt_row.lease_token IS DISTINCT FROM job_row.lease_token
           OR attempt_row.finished_at IS NOT NULL
           OR attempt_row.result_code IS NOT NULL OR attempt_row.error_code IS NOT NULL THEN
            RAISE EXCEPTION 'D03 RUNNING Job or Attempt shape is invalid';
        END IF;
        RETURN;
    END IF;
    IF job_row.status NOT IN ('COMPLETED','REJECTED','FAILED','CANCELLED')
       OR job_row.finalized_at IS NULL OR job_row.result_code IS NULL
       OR job_row.lease_token IS NOT NULL OR job_row.lease_acquired_at IS NOT NULL
       OR job_row.lease_expires_at IS NOT NULL THEN
        RAISE EXCEPTION 'D03 terminal Job shape is invalid';
    END IF;
    IF job_row.attempt_count = 0 THEN
        IF job_row.status <> 'CANCELLED'
           OR EXISTS (SELECT 1 FROM job_attempts WHERE job_id = job_row.id) THEN
            RAISE EXCEPTION 'Only pre-claim D03 cancellation may be zero-attempt terminal';
        END IF;
    ELSE
        IF job_row.attempt_count <> 1 THEN
            RAISE EXCEPTION 'Claimed D03 terminal Job requires exactly one Attempt';
        END IF;
        SELECT * INTO attempt_row FROM job_attempts
        WHERE job_id = job_row.id AND attempt = job_row.attempt_count;
        IF NOT FOUND OR attempt_row.status IS DISTINCT FROM job_row.status
           OR attempt_row.finished_at IS NULL THEN
            RAISE EXCEPTION 'D03 terminal Job and current Attempt disagree';
        END IF;
        IF job_row.status = 'FAILED' THEN
            IF attempt_row.error_code IS DISTINCT FROM job_row.result_code
               OR attempt_row.result_code IS NOT NULL THEN
                RAISE EXCEPTION 'D03 failed Attempt result shape is invalid';
            END IF;
        ELSIF attempt_row.result_code IS DISTINCT FROM job_row.result_code
              OR attempt_row.error_code IS NOT NULL THEN
            RAISE EXCEPTION 'D03 terminal Attempt result shape is invalid';
        END IF;
    END IF;
    SELECT * INTO observation_row
    FROM demo_face_observations WHERE analysis_run_id = run_row.id;
    observation_found := FOUND;
    IF job_row.status = 'COMPLETED' THEN
        PERFORM mirror_demo_require_current_synthetic_admission(run_row.demo_synthetic_identity_id);
        IF NOT EXISTS (
            SELECT 1 FROM demo_sessions session_row
            WHERE session_row.id = run_row.demo_session_id
              AND session_row.demo_actor_id = run_row.demo_actor_id
              AND session_row.closed_at IS NULL AND session_row.tombstoned_at IS NULL
              AND session_row.expires_at > clock_timestamp()
              AND session_row.config = jsonb_build_object(
                  'schema_version', 'mirror.demo/DemoSessionConfig/v1',
                  'synthetic_identity_id', run_row.demo_synthetic_identity_id
              )
        ) OR NOT observation_found
          OR observation_row.observation_state IS DISTINCT FROM job_row.result_code THEN
            RAISE EXCEPTION 'D03 completion authority is stale or missing';
        END IF;
        SELECT count(*) INTO repeat_total FROM demo_face_observation_repeats
        WHERE observation_id = observation_row.id;
        SELECT count(*) INTO baseline_total FROM demo_baseline_face_models
        WHERE observation_id = observation_row.id;
        SELECT count(*) INTO self_state_total
        FROM demo_self_states self_row
        JOIN demo_baseline_face_models baseline_row
          ON baseline_row.id = self_row.baseline_face_model_id
        WHERE baseline_row.observation_id = observation_row.id;
        IF repeat_total <> 3 OR baseline_total <> 1 OR self_state_total <> 1 THEN
            RAISE EXCEPTION 'D03 completion requires one complete final authority graph';
        END IF;
    ELSIF observation_found THEN
        RAISE EXCEPTION 'Non-completed D03 Job cannot publish final authority';
    END IF;
    RETURN;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d03_job_state()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    target_job_id text;
BEGIN
    IF TG_TABLE_NAME = 'jobs' THEN
        target_job_id := NEW.id;
    ELSIF TG_OP = 'DELETE' THEN
        target_job_id := OLD.job_id;
    ELSE
        target_job_id := NEW.job_id;
    END IF;
    PERFORM mirror_demo_require_d03_job_state(target_job_id);
    RETURN NULL;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_guard_d03_job_attempt()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    target_job_id text;
    job_row jobs%ROWTYPE;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_job_id := OLD.job_id;
    ELSE
        target_job_id := NEW.job_id;
    END IF;
    SELECT * INTO job_row FROM jobs WHERE id = target_job_id;
    IF NOT FOUND OR job_row.job_type <> 'demo_p3_p7.analysis.create' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM demo_job_bindings binding_row
        WHERE binding_row.job_id = job_row.id
          AND binding_row.endpoint_operation = 'analysis.create'
          AND binding_row.target_type = 'ANALYSIS_RUN'
    ) THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'RUNNING' OR NEW.lease_token IS NULL
           OR NEW.finished_at IS NOT NULL OR NEW.result_code IS NOT NULL
           OR NEW.error_code IS NOT NULL THEN
            RAISE EXCEPTION 'D03 JobAttempt must begin as a RUNNING lease';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'DELETE' OR OLD.status <> 'RUNNING' THEN
        RAISE EXCEPTION 'Terminal D03 JobAttempt is immutable';
    END IF;
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.job_id IS DISTINCT FROM OLD.job_id
       OR NEW.attempt IS DISTINCT FROM OLD.attempt
       OR NEW.lease_token IS DISTINCT FROM OLD.lease_token
       OR NEW.started_at IS DISTINCT FROM OLD.started_at
       OR NEW.status NOT IN ('COMPLETED','REJECTED','FAILED','CANCELLED')
       OR NEW.finished_at IS NULL OR NEW.finished_at < NEW.started_at
       OR (NEW.status = 'FAILED' AND (
           NEW.error_code IS NULL OR NEW.result_code IS NOT NULL
       ))
       OR (NEW.status <> 'FAILED' AND (
           NEW.result_code IS NULL OR NEW.error_code IS NOT NULL
       )) THEN
        RAISE EXCEPTION 'D03 JobAttempt must finish its RUNNING lease exactly once';
    END IF;
    RETURN NEW;
END;
$function$;
"""


def upgrade() -> None:
    op.execute(
        "LOCK TABLE jobs, job_attempts, demo_actors, demo_sessions, "
        "demo_synthetic_identities, demo_face_observations, "
        "demo_face_observation_repeats, demo_baseline_face_models, demo_self_states, "
        "demo_job_bindings IN ACCESS EXCLUSIVE MODE"
    )
    op.create_table(
        "demo_analysis_runs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("demo_synthetic_identity_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("analyzer_version", sa.String(length=64), nullable=False),
        sa.Column("runtime_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("model_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("observation_config_digest", sa.String(length=64), nullable=False),
        sa.Column("baseline_aggregation_version", sa.String(length=64), nullable=False),
        sa.Column("measurement_version", sa.String(length=64), nullable=False),
        sa.Column("self_state_ontology_version", sa.String(length=64), nullable=False),
        sa.Column("self_state_derivation_version", sa.String(length=64), nullable=False),
        sa.Column("repeat_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("id ~ '^[0-9a-f]{32}$'", name=op.f("ck_demo_analysis_runs_id_shape")),
        sa.CheckConstraint(
            "schema_version = 'mirror.demo/DemoAnalysisRun/v1'",
            name=op.f("ck_demo_analysis_runs_schema_version_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'",
            name=op.f("ck_demo_analysis_runs_canonical_payload_object"),
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_analysis_runs_content_digest_shape"),
        ),
        sa.CheckConstraint(
            "source_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_analysis_runs_source_sha_shape"),
        ),
        sa.CheckConstraint(
            "runtime_manifest_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_analysis_runs_runtime_manifest_digest_shape"),
        ),
        sa.CheckConstraint(
            "model_manifest_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_analysis_runs_model_manifest_digest_shape"),
        ),
        sa.CheckConstraint(
            "observation_config_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_analysis_runs_observation_config_digest_shape"),
        ),
        sa.CheckConstraint("repeat_count = 3", name=op.f("ck_demo_analysis_runs_three_repeats")),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_analysis_runs_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_analysis_runs_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_synthetic_identity_id"],
            ["demo_synthetic_identities.id"],
            name=op.f("fk_demo_analysis_runs_demo_synthetic_identity_id_demo_synthetic_identities"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_analysis_runs_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_job_binding_id"],
            ["demo_job_bindings.id"],
            name=op.f("fk_demo_analysis_runs_demo_job_binding_id_demo_job_bindings"),
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("content_digest", name=op.f("uq_demo_analysis_runs_content_digest")),
        sa.UniqueConstraint(
            "demo_job_binding_id",
            name=op.f("uq_demo_analysis_runs_demo_job_binding_id"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_analysis_runs_id_actor_session"),
        ),
    )
    for column_name in (
        "demo_actor_id",
        "demo_session_id",
        "demo_synthetic_identity_id",
        "source_asset_id",
    ):
        op.create_index(
            op.f(f"ix_demo_analysis_runs_{column_name}"),
            "demo_analysis_runs",
            [column_name],
        )

    op.add_column(
        "demo_face_observations",
        sa.Column("analysis_run_id", sa.String(length=32)),
    )
    op.create_foreign_key(
        op.f("fk_demo_face_observations_analysis_run_id_demo_analysis_runs"),
        "demo_face_observations",
        "demo_analysis_runs",
        ["analysis_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_demo_face_observations_analysis_run_id"),
        "demo_face_observations",
        ["analysis_run_id"],
        unique=True,
    )
    op.drop_constraint(
        op.f("ck_demo_face_observations_schema_version_shape"),
        "demo_face_observations",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_face_observations_schema_version_shape"),
        "demo_face_observations",
        "schema_version IN ('mirror.demo/DemoFaceObservation/v1',"
        "'mirror.demo/DemoFaceObservation/v2')",
    )
    op.create_check_constraint(
        op.f("ck_demo_face_observations_analysis_run_version_shape"),
        "demo_face_observations",
        "(schema_version = 'mirror.demo/DemoFaceObservation/v1' AND analysis_run_id IS NULL) "
        "OR (schema_version = 'mirror.demo/DemoFaceObservation/v2' "
        "AND analysis_run_id IS NOT NULL)",
    )

    op.drop_constraint(
        op.f("ck_demo_job_bindings_target_type"),
        "demo_job_bindings",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_job_bindings_target_type"),
        "demo_job_bindings",
        "target_type IN ('DEMO_ACTOR','DEMO_SESSION','ANALYSIS_RUN','FACE_OBSERVATION',"
        "'QUESTIONNAIRE_RUN','SELF_TRANSFER_RUN','EDITING_SESSION','IMAGE_VERSION',"
        "'EDIT_PLAN','EDIT_OPERATION','TOOL_RUN')",
    )
    op.create_index(
        "uq_demo_job_bindings_analysis_run_target",
        "demo_job_bindings",
        ["target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("target_type = 'ANALYSIS_RUN'"),
    )

    op.execute(_authority_projection_sql(schema_aware=True))
    op.execute(_job_binding_sql(analysis_target="ANALYSIS_RUN", include_analysis_run=True))
    op.execute(_D03_AUTHORITY_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_authority_demo_analysis_runs "
        "BEFORE INSERT OR UPDATE OR DELETE ON demo_analysis_runs "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_validate_analysis_run "
        "BEFORE INSERT ON demo_analysis_runs "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_analysis_run()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_analysis_run_reverse_binding "
        "AFTER INSERT ON demo_analysis_runs DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_analysis_run_binding()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_analysis_binding_reverse_run "
        "AFTER INSERT ON demo_job_bindings DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_analysis_run_binding()"
    )
    for table_name in (
        "demo_face_observations",
        "demo_face_observation_repeats",
        "demo_baseline_face_models",
        "demo_self_states",
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_demo_d03_result_{table_name} "
                f"BEFORE INSERT ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d03_result_row()"
            )
        )
        op.execute(
            sa.text(
                f"CREATE CONSTRAINT TRIGGER trg_demo_d03_publication_{table_name} "
                f"AFTER INSERT ON {table_name} DEFERRABLE INITIALLY DEFERRED "
                "FOR EACH ROW EXECUTE FUNCTION "
                "mirror_demo_validate_d03_result_publication()"
            )
        )
    op.execute(
        "CREATE TRIGGER trg_demo_d03_job_transition "
        "BEFORE INSERT OR UPDATE ON jobs "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_d03_job_transition()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d03_job_state "
        "AFTER INSERT OR UPDATE ON jobs DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d03_job_state()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_d03_job_attempt_transition "
        "BEFORE INSERT OR UPDATE OR DELETE ON job_attempts "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_d03_job_attempt()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d03_job_attempt_state "
        "AFTER INSERT OR UPDATE OR DELETE ON job_attempts DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d03_job_state()"
    )


def downgrade() -> None:
    op.execute(
        """
DO $block$
BEGIN
    IF EXISTS (SELECT 1 FROM demo_analysis_runs)
       OR EXISTS (
           SELECT 1 FROM demo_face_observations
           WHERE schema_version = 'mirror.demo/DemoFaceObservation/v2'
              OR analysis_run_id IS NOT NULL
       ) THEN
        RAISE EXCEPTION 'Prototype downgrade blocked by D03 AnalysisRun authority';
    END IF;
END;
$block$;
"""
    )
    op.execute("DROP TRIGGER trg_demo_d03_job_attempt_state ON job_attempts")
    op.execute("DROP TRIGGER trg_demo_d03_job_attempt_transition ON job_attempts")
    op.execute("DROP TRIGGER trg_demo_d03_job_state ON jobs")
    op.execute("DROP TRIGGER trg_demo_d03_job_transition ON jobs")
    for table_name in (
        "demo_self_states",
        "demo_baseline_face_models",
        "demo_face_observation_repeats",
        "demo_face_observations",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_demo_d03_publication_{table_name} ON {table_name}")
        op.execute(f"DROP TRIGGER trg_demo_d03_result_{table_name} ON {table_name}")
    op.execute("DROP TRIGGER trg_demo_analysis_binding_reverse_run ON demo_job_bindings")
    op.execute("DROP TRIGGER trg_demo_analysis_run_reverse_binding ON demo_analysis_runs")
    op.execute("DROP TRIGGER trg_demo_validate_analysis_run ON demo_analysis_runs")
    op.execute("DROP TRIGGER trg_demo_authority_demo_analysis_runs ON demo_analysis_runs")
    op.execute("DROP FUNCTION mirror_demo_validate_d03_job_state()")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_d03_result_publication()")
    op.execute("DROP FUNCTION mirror_demo_require_d03_job_state(text)")
    op.execute("DROP FUNCTION mirror_demo_guard_d03_job_attempt()")
    op.execute("DROP FUNCTION mirror_demo_guard_d03_job_transition()")
    op.execute("DROP FUNCTION mirror_demo_validate_d03_result_row()")
    op.execute("DROP FUNCTION mirror_demo_validate_analysis_run_binding()")
    op.execute("DROP FUNCTION mirror_demo_validate_analysis_run()")

    op.drop_index("uq_demo_job_bindings_analysis_run_target", table_name="demo_job_bindings")
    op.drop_constraint(
        op.f("ck_demo_job_bindings_target_type"),
        "demo_job_bindings",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_job_bindings_target_type"),
        "demo_job_bindings",
        "target_type IN ('DEMO_ACTOR','DEMO_SESSION','FACE_OBSERVATION',"
        "'QUESTIONNAIRE_RUN','SELF_TRANSFER_RUN','EDITING_SESSION','IMAGE_VERSION',"
        "'EDIT_PLAN','EDIT_OPERATION','TOOL_RUN')",
    )
    op.execute(_job_binding_sql(analysis_target="FACE_OBSERVATION", include_analysis_run=False))

    op.drop_constraint(
        op.f("ck_demo_face_observations_analysis_run_version_shape"),
        "demo_face_observations",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_face_observations_schema_version_shape"),
        "demo_face_observations",
        type_="check",
    )
    op.drop_index(
        op.f("ix_demo_face_observations_analysis_run_id"),
        table_name="demo_face_observations",
    )
    op.drop_constraint(
        op.f("fk_demo_face_observations_analysis_run_id_demo_analysis_runs"),
        "demo_face_observations",
        type_="foreignkey",
    )
    op.drop_column("demo_face_observations", "analysis_run_id")
    op.create_check_constraint(
        op.f("ck_demo_face_observations_schema_version_shape"),
        "demo_face_observations",
        "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
    )
    op.drop_table("demo_analysis_runs")
    op.execute(_authority_projection_sql(schema_aware=False))
