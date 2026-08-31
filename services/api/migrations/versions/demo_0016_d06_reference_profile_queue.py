"""Add queued D06 Reference Profile orchestration authority.

Revision ID: demo_0016_d06_ref_profile_queue
Revises: demo_0015_d02_source_acq_pool
Create Date: 2026-09-01

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
FORWARD_REPAIR_ONLY: TRUE
"""

# ruff: noqa: S608 -- all SQL fragments are fixed migration constants.

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0016_d06_ref_profile_queue"
down_revision: str | None = "demo_0015_d02_source_acq_pool"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
FORWARD_REPAIR_ONLY = True


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column(
            "canonical_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def _authority_constraints(table: str, schema: str) -> tuple[sa.Constraint, ...]:
    return (
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        sa.UniqueConstraint("content_digest", name=op.f(f"uq_{table}_content_digest")),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{32}$'",
            name=op.f(f"ck_{table}_id_shape"),
        ),
        sa.CheckConstraint(
            f"schema_version = '{schema}'",
            name=op.f(f"ck_{table}_schema_version_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'",
            name=op.f(f"ck_{table}_canonical_payload_object"),
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{table}_content_digest_shape"),
        ),
    )


def _job_binding_sql(*, include_reference_profile: bool) -> str:
    operation_case = (
        "        WHEN 'reference_profile.compile' THEN 'REFERENCE_PROFILE_REQUEST'\n"
        if include_reference_profile
        else ""
    )
    target_case = (
        r"""
        WHEN 'REFERENCE_PROFILE_REQUEST' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_reference_compile_requests target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
                  AND target_row.demo_job_binding_id = NEW.id
            );
"""
        if include_reference_profile
        else ""
    )
    return rf"""
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
        WHEN 'analysis.create' THEN 'ANALYSIS_RUN'
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
{operation_case}        ELSE NULL
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
        WHEN 'ANALYSIS_RUN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_analysis_runs target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
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
{target_case}    END CASE;
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


_REQUEST_VALIDATOR_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_reference_profile_request()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    binding_row demo_job_bindings%ROWTYPE;
    desired_row demo_desired_delta_profiles%ROWTYPE;
    style_row demo_style_profiles%ROWTYPE;
    constraints_row demo_identity_constraints%ROWTYPE;
    source_binding jsonb;
    accepted_row demo_self_transfer_runs%ROWTYPE;
    image_row demo_image_versions%ROWTYPE;
    verifier_row demo_verification_results%ROWTYPE;
    asset_row assets%ROWTYPE;
    expected_evidence jsonb;
BEGIN
    SELECT * INTO binding_row FROM demo_job_bindings WHERE id = NEW.demo_job_binding_id;
    IF NOT FOUND
       OR binding_row.demo_actor_id <> NEW.demo_actor_id
       OR binding_row.demo_session_id IS DISTINCT FROM NEW.demo_session_id
       OR binding_row.endpoint_operation <> 'reference_profile.compile'
       OR binding_row.target_type <> 'REFERENCE_PROFILE_REQUEST'
       OR binding_row.target_id <> NEW.id THEN
        RAISE EXCEPTION 'Reference Profile request Job binding mismatch';
    END IF;

    SELECT * INTO desired_row
    FROM demo_desired_delta_profiles
    WHERE id = NEW.desired_delta_profile_id;
    IF NOT FOUND
       OR desired_row.demo_actor_id <> NEW.demo_actor_id
       OR desired_row.demo_session_id <> NEW.demo_session_id THEN
        RAISE EXCEPTION 'Reference Profile request DesiredDeltaProfile mismatch';
    END IF;

    IF NEW.style_profile_id IS NOT NULL THEN
        SELECT * INTO style_row FROM demo_style_profiles WHERE id = NEW.style_profile_id;
        IF NOT FOUND
           OR style_row.demo_actor_id <> NEW.demo_actor_id
           OR (style_row.demo_session_id IS NOT NULL
               AND style_row.demo_session_id <> NEW.demo_session_id)
           OR (style_row.desired_delta_profile_id IS NOT NULL
               AND style_row.desired_delta_profile_id <> NEW.desired_delta_profile_id) THEN
            RAISE EXCEPTION 'Reference Profile request StyleProfile mismatch';
        END IF;
    END IF;

    IF NEW.identity_constraints_id IS NOT NULL THEN
        SELECT * INTO constraints_row
        FROM demo_identity_constraints
        WHERE id = NEW.identity_constraints_id;
        IF NOT FOUND
           OR constraints_row.demo_actor_id <> NEW.demo_actor_id
           OR (constraints_row.demo_session_id IS NOT NULL
               AND constraints_row.demo_session_id <> NEW.demo_session_id)
           OR (constraints_row.self_state_id IS NOT NULL
               AND constraints_row.self_state_id <> desired_row.self_state_id) THEN
            RAISE EXCEPTION 'Reference Profile request IdentityConstraints mismatch';
        END IF;
    END IF;

    IF jsonb_typeof(NEW.source_bindings) <> 'array'
       OR jsonb_array_length(NEW.source_bindings) NOT BETWEEN 1 AND 3
       OR (SELECT count(DISTINCT value ->> 'asset_id')
           FROM jsonb_array_elements(NEW.source_bindings))
          <> jsonb_array_length(NEW.source_bindings)
       OR (SELECT count(DISTINCT value ->> 'view')
           FROM jsonb_array_elements(NEW.source_bindings))
          <> jsonb_array_length(NEW.source_bindings) THEN
        RAISE EXCEPTION 'Reference Profile source bindings are invalid';
    END IF;

    FOR source_binding IN SELECT value FROM jsonb_array_elements(NEW.source_bindings) LOOP
        IF NOT (source_binding ?& ARRAY[
            'asset_id', 'asset_sha256', 'view', 'self_transfer_run_id',
            'self_transfer_run_digest', 'image_version_id',
            'image_version_digest', 'verifier_digest', 'evidence_digests'
        ]::text[])
           OR source_binding - ARRAY[
            'asset_id', 'asset_sha256', 'view', 'self_transfer_run_id',
            'self_transfer_run_digest', 'image_version_id',
            'image_version_digest', 'verifier_digest', 'evidence_digests'
        ]::text[] <> '{}'::jsonb
           OR source_binding ->> 'view' NOT IN ('FRONT', 'THREE_QUARTER', 'SIDE')
           OR source_binding ->> 'asset_id' !~ '^[0-9a-f]{32}$'
           OR source_binding ->> 'asset_sha256' !~ '^[0-9a-f]{64}$'
           OR source_binding ->> 'self_transfer_run_id' !~ '^[0-9a-f]{32}$'
           OR source_binding ->> 'self_transfer_run_digest' !~ '^[0-9a-f]{64}$'
           OR source_binding ->> 'image_version_id' !~ '^[0-9a-f]{32}$'
           OR source_binding ->> 'image_version_digest' !~ '^[0-9a-f]{64}$'
           OR source_binding ->> 'verifier_digest' !~ '^[0-9a-f]{64}$'
           OR jsonb_typeof(source_binding -> 'evidence_digests') <> 'array'
           OR jsonb_array_length(source_binding -> 'evidence_digests') < 1 THEN
            RAISE EXCEPTION 'Reference Profile source binding shape is invalid';
        END IF;

        SELECT * INTO asset_row FROM assets WHERE id = source_binding ->> 'asset_id';
        IF NOT FOUND
           OR asset_row.sha256 <> source_binding ->> 'asset_sha256'
           OR asset_row.synthetic IS DISTINCT FROM true
           OR asset_row.deleted_at IS NOT NULL THEN
            RAISE EXCEPTION 'Reference Profile source Asset mismatch';
        END IF;

        SELECT * INTO accepted_row
        FROM demo_self_transfer_runs
        WHERE id = source_binding ->> 'self_transfer_run_id';
        IF NOT FOUND
           OR accepted_row.content_digest <> source_binding ->> 'self_transfer_run_digest'
           OR accepted_row.demo_actor_id <> NEW.demo_actor_id
           OR accepted_row.demo_session_id <> NEW.demo_session_id
           OR accepted_row.desired_delta_profile_id <> NEW.desired_delta_profile_id
           OR accepted_row.record_kind <> 'RESULT'
           OR accepted_row.result_asset_id <> source_binding ->> 'asset_id'
           OR accepted_row.user_outcome <> 'ACCEPTED'
           OR accepted_row.verifier_digest <> source_binding ->> 'verifier_digest' THEN
            RAISE EXCEPTION 'Reference Profile accepted self-transfer mismatch';
        END IF;

        SELECT * INTO image_row
        FROM demo_image_versions
        WHERE id = source_binding ->> 'image_version_id';
        IF NOT FOUND
           OR image_row.content_digest <> source_binding ->> 'image_version_digest'
           OR image_row.demo_actor_id <> NEW.demo_actor_id
           OR image_row.demo_session_id <> NEW.demo_session_id
           OR image_row.result_asset_id <> source_binding ->> 'asset_id'
           OR image_row.result_asset_sha256 <> source_binding ->> 'asset_sha256'
           OR image_row.version_kind <> 'EDITED'
           OR image_row.verifier_digest <> source_binding ->> 'verifier_digest' THEN
            RAISE EXCEPTION 'Reference Profile published ImageVersion mismatch';
        END IF;

        SELECT * INTO verifier_row
        FROM demo_verification_results
        WHERE content_digest = source_binding ->> 'verifier_digest';
        IF NOT FOUND
           OR verifier_row.demo_actor_id <> NEW.demo_actor_id
           OR verifier_row.demo_session_id <> NEW.demo_session_id
           OR verifier_row.image_version_id <> source_binding ->> 'image_version_id'
           OR verifier_row.output_asset_id <> source_binding ->> 'asset_id'
           OR verifier_row.output_asset_sha256 <> source_binding ->> 'asset_sha256'
           OR verifier_row.outcome <> 'PASS' THEN
            RAISE EXCEPTION 'Reference Profile PASS verifier mismatch';
        END IF;

        SELECT coalesce(jsonb_agg(content_digest ORDER BY dimension_key), '[]'::jsonb)
        INTO expected_evidence
        FROM demo_self_transfer_evidence
        WHERE self_transfer_run_id = accepted_row.id
          AND verifier_outcome = 'PASS'
          AND verifier_digest = verifier_row.content_digest;
        IF expected_evidence <> source_binding -> 'evidence_digests' THEN
            RAISE EXCEPTION 'Reference Profile evidence digest set mismatch';
        END IF;
    END LOOP;
    RETURN NEW;
END;
$function$;
"""


_RESULT_VALIDATOR_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_reference_profile_result()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    request_row demo_reference_compile_requests%ROWTYPE;
    binding_row demo_job_bindings%ROWTYPE;
    profile_row demo_reference_profiles%ROWTYPE;
    job_row jobs%ROWTYPE;
    attempt_row job_attempts%ROWTYPE;
BEGIN
    SELECT * INTO request_row
    FROM demo_reference_compile_requests
    WHERE id = NEW.compile_request_id;
    SELECT * INTO binding_row
    FROM demo_job_bindings
    WHERE id = NEW.demo_job_binding_id;
    SELECT * INTO profile_row
    FROM demo_reference_profiles
    WHERE id = NEW.reference_profile_id;
    IF request_row.id IS NULL OR binding_row.id IS NULL OR profile_row.id IS NULL
       OR request_row.demo_actor_id <> NEW.demo_actor_id
       OR request_row.demo_session_id <> NEW.demo_session_id
       OR request_row.demo_job_binding_id <> NEW.demo_job_binding_id
       OR request_row.input_digest <> NEW.input_digest
       OR binding_row.demo_actor_id <> NEW.demo_actor_id
       OR binding_row.demo_session_id IS DISTINCT FROM NEW.demo_session_id
       OR binding_row.target_type <> 'REFERENCE_PROFILE_REQUEST'
       OR binding_row.target_id <> NEW.compile_request_id
       OR profile_row.demo_actor_id <> NEW.demo_actor_id
       OR profile_row.demo_session_id <> NEW.demo_session_id
       OR profile_row.content_digest <> NEW.reference_profile_digest THEN
        RAISE EXCEPTION 'Reference Profile compile result authority mismatch';
    END IF;

    SELECT * INTO job_row FROM jobs WHERE id = binding_row.job_id;
    SELECT * INTO attempt_row
    FROM job_attempts
    WHERE job_id = job_row.id AND attempt = job_row.attempt_count;
    IF job_row.id IS NULL OR attempt_row.id IS NULL
       OR job_row.status <> 'COMPLETED'
       OR job_row.result_code <> 'REFERENCE_PROFILE_COMPILED'
       OR job_row.finalized_at IS NULL
       OR job_row.lease_token IS NOT NULL
       OR job_row.lease_acquired_at IS NOT NULL
       OR job_row.lease_expires_at IS NOT NULL
       OR attempt_row.status <> 'COMPLETED'
       OR attempt_row.result_code <> 'REFERENCE_PROFILE_COMPILED'
       OR attempt_row.finished_at IS NULL THEN
        RAISE EXCEPTION 'Reference Profile compile result lacks terminal Job authority';
    END IF;
    RETURN NEW;
END;
$function$;
"""


def _replace_job_binding_constraints(*, include_reference_profile: bool) -> None:
    op.drop_constraint(
        op.f("ck_demo_job_bindings_endpoint_operation"),
        "demo_job_bindings",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_job_bindings_target_type"),
        "demo_job_bindings",
        type_="check",
    )
    operations = (
        "'analysis.create','questionnaire.run.create','profile.compile',"
        "'editing_session.create','edit_plan.create','edit_plan.execute',"
        "'image_version.restore','profile.rebuild','self_transfer.execute','tool.verify',"
        "'context.compile'"
    )
    targets = (
        "'DEMO_ACTOR','DEMO_SESSION','ANALYSIS_RUN','FACE_OBSERVATION',"
        "'QUESTIONNAIRE_RUN','SELF_TRANSFER_RUN','EDITING_SESSION','IMAGE_VERSION',"
        "'EDIT_PLAN','EDIT_OPERATION','TOOL_RUN'"
    )
    if include_reference_profile:
        operations += ",'reference_profile.compile'"
        targets += ",'REFERENCE_PROFILE_REQUEST'"
    op.create_check_constraint(
        op.f("ck_demo_job_bindings_endpoint_operation"),
        "demo_job_bindings",
        f"endpoint_operation IN ({operations})",
    )
    op.create_check_constraint(
        op.f("ck_demo_job_bindings_target_type"),
        "demo_job_bindings",
        f"target_type IN ({targets})",
    )


def upgrade() -> None:
    request_table = "demo_reference_compile_requests"
    request_schema = "mirror.demo/DemoReferenceProfileCompileRequest/v1"
    op.create_table(
        request_table,
        *_authority_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("desired_delta_profile_id", sa.String(length=32), nullable=False),
        sa.Column("style_profile_id", sa.String(length=32), nullable=True),
        sa.Column("identity_constraints_id", sa.String(length=32), nullable=True),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column(
            "source_bindings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("execution_policy_version", sa.String(length=64), nullable=False),
        sa.Column("max_attempts", sa.SmallInteger(), nullable=False),
        sa.Column("lease_timeout_seconds", sa.Integer(), nullable=False),
        *_authority_constraints(request_table, request_schema),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f(f"fk_{request_table}_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f(f"fk_{request_table}_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_job_binding_id"],
            ["demo_job_bindings.id"],
            name=op.f(f"fk_{request_table}_demo_job_binding_id_demo_job_bindings"),
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["desired_delta_profile_id"],
            ["demo_desired_delta_profiles.id"],
            name=op.f(f"fk_{request_table}_desired_delta_profile_id_demo_desired_delta_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["style_profile_id"],
            ["demo_style_profiles.id"],
            name=op.f(f"fk_{request_table}_style_profile_id_demo_style_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["identity_constraints_id"],
            ["demo_identity_constraints.id"],
            name=op.f(f"fk_{request_table}_identity_constraints_id_demo_identity_constraints"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_job_binding_id",
            name=op.f(f"uq_{request_table}_demo_job_binding_id"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f(f"uq_{request_table}_id_actor_session"),
        ),
        sa.CheckConstraint(
            "compiler_version = 'demo-reference-profile-compiler-v1'",
            name=op.f(f"ck_{request_table}_compiler_version"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_bindings) = 'array' "
            "AND jsonb_array_length(source_bindings) BETWEEN 1 AND 3",
            name=op.f(f"ck_{request_table}_source_bindings_array"),
        ),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{request_table}_input_digest_shape"),
        ),
        sa.CheckConstraint(
            "execution_policy_version = 'demo-reference-profile-queue-v1'",
            name=op.f(f"ck_{request_table}_execution_policy_version"),
        ),
        sa.CheckConstraint("max_attempts = 3", name=op.f(f"ck_{request_table}_max_attempts")),
        sa.CheckConstraint(
            "lease_timeout_seconds = 300",
            name=op.f(f"ck_{request_table}_lease_timeout_seconds"),
        ),
    )
    for column in (
        "demo_actor_id",
        "demo_session_id",
        "demo_job_binding_id",
        "desired_delta_profile_id",
        "style_profile_id",
        "identity_constraints_id",
    ):
        op.create_index(op.f(f"ix_{request_table}_{column}"), request_table, [column])

    result_table = "demo_reference_compile_results"
    result_schema = "mirror.demo/DemoReferenceProfileCompileResult/v1"
    op.create_table(
        result_table,
        *_authority_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("compile_request_id", sa.String(length=32), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("reference_profile_id", sa.String(length=32), nullable=False),
        sa.Column("reference_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("result_code", sa.String(length=64), nullable=False),
        *_authority_constraints(result_table, result_schema),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f(f"fk_{result_table}_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f(f"fk_{result_table}_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["compile_request_id"],
            [f"{request_table}.id"],
            name=op.f(f"fk_{result_table}_compile_request_id_{request_table}"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_job_binding_id"],
            ["demo_job_bindings.id"],
            name=op.f(f"fk_{result_table}_demo_job_binding_id_demo_job_bindings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reference_profile_id"],
            ["demo_reference_profiles.id"],
            name=op.f(f"fk_{result_table}_reference_profile_id_demo_reference_profiles"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "compile_request_id",
            name=op.f(f"uq_{result_table}_compile_request_id"),
        ),
        sa.UniqueConstraint(
            "demo_job_binding_id",
            name=op.f(f"uq_{result_table}_demo_job_binding_id"),
        ),
        sa.CheckConstraint(
            "reference_profile_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{result_table}_reference_digest_shape"),
        ),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{result_table}_input_digest_shape"),
        ),
        sa.CheckConstraint(
            "result_code = 'REFERENCE_PROFILE_COMPILED'",
            name=op.f(f"ck_{result_table}_result_code"),
        ),
    )
    for column in (
        "demo_actor_id",
        "demo_session_id",
        "compile_request_id",
        "demo_job_binding_id",
        "reference_profile_id",
    ):
        op.create_index(op.f(f"ix_{result_table}_{column}"), result_table, [column])

    _replace_job_binding_constraints(include_reference_profile=True)
    op.create_index(
        "uq_demo_job_bindings_reference_profile_request_target",
        "demo_job_bindings",
        ["target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("target_type = 'REFERENCE_PROFILE_REQUEST'"),
    )
    op.execute(_job_binding_sql(include_reference_profile=True))
    op.execute(_REQUEST_VALIDATOR_SQL)
    op.execute(_RESULT_VALIDATOR_SQL)
    for table in (request_table, result_table):
        op.execute(
            f"CREATE TRIGGER trg_demo_authority_{table} "
            f"BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
        )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_reference_profile_request_integrity "
        "AFTER INSERT ON demo_reference_compile_requests "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION mirror_demo_validate_reference_profile_request()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_reference_profile_result_integrity "
        "AFTER INSERT ON demo_reference_compile_results "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION mirror_demo_validate_reference_profile_result()"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (SELECT 1 FROM demo_reference_compile_requests)
               OR EXISTS (SELECT 1 FROM demo_reference_compile_results)
               OR EXISTS (
                    SELECT 1 FROM demo_job_bindings
                    WHERE endpoint_operation = 'reference_profile.compile'
               ) THEN
                RAISE EXCEPTION 'D06 queued Reference Profile authority exists; downgrade is forbidden';
            END IF;
        END;
        $block$;
        """
    )
    op.execute(
        "DROP TRIGGER trg_demo_reference_profile_result_integrity ON demo_reference_compile_results"
    )
    op.execute(
        "DROP TRIGGER trg_demo_reference_profile_request_integrity "
        "ON demo_reference_compile_requests"
    )
    op.execute(
        "DROP TRIGGER trg_demo_authority_demo_reference_compile_results "
        "ON demo_reference_compile_results"
    )
    op.execute(
        "DROP TRIGGER trg_demo_authority_demo_reference_compile_requests "
        "ON demo_reference_compile_requests"
    )
    op.execute("DROP FUNCTION mirror_demo_validate_reference_profile_result()")
    op.execute("DROP FUNCTION mirror_demo_validate_reference_profile_request()")
    op.drop_index(
        "uq_demo_job_bindings_reference_profile_request_target",
        table_name="demo_job_bindings",
    )
    _replace_job_binding_constraints(include_reference_profile=False)
    op.execute(_job_binding_sql(include_reference_profile=False))
    op.drop_table("demo_reference_compile_results")
    op.drop_table("demo_reference_compile_requests")
