"""Add bounded D03 dispatch and expired-lease retry authority.

Revision ID: demo_0011_d03_job_recovery
Revises: demo_0010_d03_analysis_run
Create Date: 2026-08-29

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

from alembic import op

revision: str = "demo_0011_d03_job_recovery"
down_revision: str | None = "demo_0010_d03_analysis_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"

_RETRY_GUARD_SQL = r"""
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
        IF NEW.attempt_count <> 1 THEN
            RAISE EXCEPTION 'D03 initial claim must create attempt one';
        END IF;
    ELSIF OLD.status = 'RUNNING' AND NEW.status = 'RUNNING' THEN
        IF OLD.lease_expires_at IS NULL OR OLD.lease_expires_at > clock_timestamp()
           OR NEW.attempt_count <> OLD.attempt_count + 1
           OR NEW.attempt_count > 3
           OR NEW.lease_token IS NULL
           OR NEW.lease_token IS NOT DISTINCT FROM OLD.lease_token
           OR NEW.lease_acquired_at IS NULL
           OR NEW.lease_acquired_at < OLD.lease_expires_at
           OR NEW.lease_expires_at IS NULL
           OR NEW.lease_expires_at <= NEW.lease_acquired_at
           OR NEW.finalized_at IS NOT NULL OR NEW.result_code IS NOT NULL THEN
            RAISE EXCEPTION 'D03 retry requires one new post-expiry attempt';
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
"""

_RETRY_STATE_SQL = r"""
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
    prior_attempt_total integer;
    invalid_prior_attempt_total integer;
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
    IF attempt_total <> job_row.attempt_count OR job_row.attempt_count > 3 THEN
        RAISE EXCEPTION 'D03 Job requires its bounded declared Attempt cardinality';
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
    IF job_row.attempt_count < 1 THEN
        IF job_row.status <> 'CANCELLED' THEN
            RAISE EXCEPTION 'Only pre-claim D03 cancellation may have zero attempts';
        END IF;
    ELSE
        SELECT count(*) INTO prior_attempt_total FROM job_attempts
        WHERE job_id = job_row.id AND attempt < job_row.attempt_count;
        SELECT count(*) INTO invalid_prior_attempt_total FROM job_attempts
        WHERE job_id = job_row.id AND attempt < job_row.attempt_count
          AND (status <> 'FAILED' OR error_code <> 'D03_LEASE_EXPIRED'
               OR result_code IS NOT NULL OR finished_at IS NULL);
        IF prior_attempt_total <> job_row.attempt_count - 1
           OR invalid_prior_attempt_total <> 0 THEN
            RAISE EXCEPTION 'D03 prior attempts must be contiguous expired leases';
        END IF;
    END IF;
    IF job_row.status = 'RUNNING' THEN
        SELECT * INTO attempt_row FROM job_attempts
        WHERE job_id = job_row.id AND attempt = job_row.attempt_count;
        IF job_row.attempt_count NOT BETWEEN 1 AND 3 OR job_row.lease_token IS NULL
           OR job_row.lease_acquired_at IS NULL
           OR job_row.lease_expires_at <= job_row.lease_acquired_at
           OR job_row.finalized_at IS NOT NULL OR job_row.result_code IS NOT NULL
           OR NOT FOUND OR attempt_row.status <> 'RUNNING'
           OR attempt_row.lease_token IS DISTINCT FROM job_row.lease_token
           OR attempt_row.finished_at IS NOT NULL
           OR attempt_row.result_code IS NOT NULL OR attempt_row.error_code IS NOT NULL THEN
            RAISE EXCEPTION 'D03 RUNNING Job or current Attempt shape is invalid';
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
"""

_ORIGINAL_GUARD_SQL = r"""
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
"""

_ORIGINAL_STATE_SQL = r"""
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
"""


def upgrade() -> None:
    op.execute("LOCK TABLE jobs, job_attempts IN ACCESS EXCLUSIVE MODE")
    op.execute(_RETRY_GUARD_SQL)
    op.execute(_RETRY_STATE_SQL)


def downgrade() -> None:
    op.execute("LOCK TABLE jobs, job_attempts IN ACCESS EXCLUSIVE MODE")
    op.execute(
        r"""
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1 FROM jobs
        WHERE job_type = 'demo_p3_p7.analysis.create' AND attempt_count > 1
    ) THEN
        RAISE EXCEPTION 'cannot downgrade populated multi-attempt D03 authority';
    END IF;
END;
$block$;
"""
    )
    op.execute(_ORIGINAL_GUARD_SQL)
    op.execute(_ORIGINAL_STATE_SQL)
