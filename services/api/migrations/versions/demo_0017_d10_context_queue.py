"""Add queued D10 Context compilation authority.

Revision ID: demo_0017_d10_context_queue
Revises: demo_0016_d06_ref_profile_queue
Create Date: 2026-09-01

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
FORWARD_REPAIR_ONLY: TRUE
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0017_d10_context_queue"
down_revision: str | None = "demo_0016_d06_ref_profile_queue"
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
        sa.CheckConstraint("id ~ '^[0-9a-f]{32}$'", name=op.f(f"ck_{table}_id_shape")),
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


_REQUEST_VALIDATOR_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_context_compile_request()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    binding_row demo_job_bindings%ROWTYPE;
    profile_row demo_aesthetic_profiles%ROWTYPE;
    job_row jobs%ROWTYPE;
BEGIN
    SELECT * INTO binding_row FROM demo_job_bindings WHERE id = NEW.demo_job_binding_id;
    SELECT * INTO profile_row FROM demo_aesthetic_profiles WHERE id = NEW.aesthetic_profile_id;
    SELECT * INTO job_row FROM jobs WHERE id = binding_row.job_id;
    IF binding_row.id IS NULL OR profile_row.id IS NULL OR job_row.id IS NULL
       OR binding_row.demo_actor_id <> NEW.demo_actor_id
       OR binding_row.demo_session_id IS DISTINCT FROM NEW.demo_session_id
       OR binding_row.endpoint_operation <> 'context.compile'
       OR binding_row.target_type <> 'DEMO_SESSION'
       OR binding_row.target_id <> NEW.demo_session_id
       OR profile_row.demo_actor_id <> NEW.demo_actor_id
       OR profile_row.content_digest <> NEW.aesthetic_profile_digest
       OR job_row.job_type <> 'demo_p3_p7.context.compile'
       OR job_row.status <> 'PENDING'
       OR job_row.attempt_count <> 0
       OR job_row.payload::jsonb <> '{}'::jsonb
       OR job_row.owner_user_id IS NOT NULL
       OR job_row.ingestion_upload_intent_id IS NOT NULL
       OR job_row.result_asset_id IS NOT NULL THEN
        RAISE EXCEPTION 'Context compile request authority mismatch';
    END IF;
    RETURN NEW;
END;
$function$;
"""


_RESULT_VALIDATOR_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_context_compile_result()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    request_row demo_context_compile_requests%ROWTYPE;
    binding_row demo_job_bindings%ROWTYPE;
    context_row demo_context_compilations%ROWTYPE;
    job_row jobs%ROWTYPE;
    attempt_row job_attempts%ROWTYPE;
BEGIN
    SELECT * INTO request_row
    FROM demo_context_compile_requests
    WHERE id = NEW.compile_request_id;
    SELECT * INTO binding_row
    FROM demo_job_bindings
    WHERE id = NEW.demo_job_binding_id;
    SELECT * INTO context_row
    FROM demo_context_compilations
    WHERE id = NEW.context_compilation_id;
    IF request_row.id IS NULL OR binding_row.id IS NULL OR context_row.id IS NULL
       OR request_row.demo_actor_id <> NEW.demo_actor_id
       OR request_row.demo_session_id <> NEW.demo_session_id
       OR request_row.demo_job_binding_id <> NEW.demo_job_binding_id
       OR request_row.input_digest <> NEW.input_digest
       OR binding_row.demo_actor_id <> NEW.demo_actor_id
       OR binding_row.demo_session_id IS DISTINCT FROM NEW.demo_session_id
       OR binding_row.endpoint_operation <> 'context.compile'
       OR binding_row.target_type <> 'DEMO_SESSION'
       OR binding_row.target_id <> NEW.demo_session_id
       OR context_row.demo_actor_id <> NEW.demo_actor_id
       OR context_row.demo_session_id <> NEW.demo_session_id
       OR context_row.aesthetic_profile_id <> request_row.aesthetic_profile_id
       OR context_row.context_as_of_time <> request_row.context_as_of_time
       OR context_row.current_instruction_digest <> request_row.current_instruction_digest
       OR context_row.compilation_watermark <> request_row.compilation_watermark
       OR context_row.content_digest <> NEW.context_digest THEN
        RAISE EXCEPTION 'Context compile result authority mismatch';
    END IF;

    SELECT * INTO job_row FROM jobs WHERE id = binding_row.job_id;
    SELECT * INTO attempt_row
    FROM job_attempts
    WHERE job_id = job_row.id AND attempt = job_row.attempt_count;
    IF job_row.id IS NULL OR attempt_row.id IS NULL
       OR job_row.status <> 'COMPLETED'
       OR job_row.result_code <> 'CONTEXT_COMPILED'
       OR job_row.finalized_at IS NULL
       OR job_row.lease_token IS NOT NULL
       OR job_row.lease_acquired_at IS NOT NULL
       OR job_row.lease_expires_at IS NOT NULL
       OR attempt_row.status <> 'COMPLETED'
       OR attempt_row.result_code <> 'CONTEXT_COMPILED'
       OR attempt_row.finished_at IS NULL THEN
        RAISE EXCEPTION 'Context compile result lacks terminal Job authority';
    END IF;
    RETURN NEW;
END;
$function$;
"""


def upgrade() -> None:
    request_table = "demo_context_compile_requests"
    request_schema = "mirror.demo/DemoContextCompileRequest/v1"
    op.create_table(
        request_table,
        *_authority_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("aesthetic_profile_id", sa.String(length=32), nullable=False),
        sa.Column("aesthetic_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("context_as_of_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_instruction_digest", sa.String(length=64), nullable=False),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column(
            "selected_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "rejected_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("budgets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trace_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("compilation_watermark", sa.String(length=64), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        ),
        sa.ForeignKeyConstraint(
            ["aesthetic_profile_id"],
            ["demo_aesthetic_profiles.id"],
            name=op.f(f"fk_{request_table}_aesthetic_profile_id_demo_aesthetic_profiles"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_job_binding_id",
            name=op.f(f"uq_{request_table}_demo_job_binding_id"),
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "input_digest",
            name=op.f(f"uq_{request_table}_actor_input_digest"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f(f"uq_{request_table}_id_actor_session"),
        ),
        sa.CheckConstraint(
            "aesthetic_profile_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{request_table}_profile_digest_shape"),
        ),
        sa.CheckConstraint(
            "current_instruction_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{request_table}_instruction_digest_shape"),
        ),
        sa.CheckConstraint(
            "compiler_version = 'demo-context-compiler-v1'",
            name=op.f(f"ck_{request_table}_compiler_version"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(selected_evidence) = 'array'",
            name=op.f(f"ck_{request_table}_selected_evidence_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(rejected_evidence) = 'array'",
            name=op.f(f"ck_{request_table}_rejected_evidence_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(budgets) = 'object'",
            name=op.f(f"ck_{request_table}_budgets_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(trace_payload) = 'object'",
            name=op.f(f"ck_{request_table}_trace_payload_object"),
        ),
        sa.CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{request_table}_watermark_shape"),
        ),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{request_table}_input_digest_shape"),
        ),
        sa.CheckConstraint(
            "expires_at >= context_as_of_time",
            name=op.f(f"ck_{request_table}_expiry_order"),
        ),
        sa.CheckConstraint(
            "execution_policy_version = 'demo-context-queue-v1'",
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
        "aesthetic_profile_id",
    ):
        op.create_index(op.f(f"ix_{request_table}_{column}"), request_table, [column])

    result_table = "demo_context_compile_results"
    result_schema = "mirror.demo/DemoContextCompileResult/v1"
    op.create_table(
        result_table,
        *_authority_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("compile_request_id", sa.String(length=32), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("context_compilation_id", sa.String(length=32), nullable=False),
        sa.Column("context_digest", sa.String(length=64), nullable=False),
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
            ["context_compilation_id"],
            ["demo_context_compilations.id"],
            name=op.f(f"fk_{result_table}_context_compilation_id_demo_context_compilations"),
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
            "context_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{result_table}_context_digest_shape"),
        ),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{result_table}_input_digest_shape"),
        ),
        sa.CheckConstraint(
            "result_code = 'CONTEXT_COMPILED'",
            name=op.f(f"ck_{result_table}_result_code"),
        ),
    )
    for column in (
        "demo_actor_id",
        "demo_session_id",
        "compile_request_id",
        "demo_job_binding_id",
    ):
        op.create_index(op.f(f"ix_{result_table}_{column}"), result_table, [column])
    op.create_index(
        op.f(f"ix_{result_table}_context_compilation_id"),
        result_table,
        ["context_compilation_id"],
        unique=True,
    )

    op.execute(_REQUEST_VALIDATOR_SQL)
    op.execute(_RESULT_VALIDATOR_SQL)
    for table in (request_table, result_table):
        op.execute(
            f"CREATE TRIGGER trg_demo_authority_{table} "
            f"BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
        )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_context_compile_request_integrity "
        "AFTER INSERT ON demo_context_compile_requests "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION mirror_demo_validate_context_compile_request()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_context_compile_result_integrity "
        "AFTER INSERT ON demo_context_compile_results "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
        "EXECUTE FUNCTION mirror_demo_validate_context_compile_result()"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (SELECT 1 FROM demo_context_compile_requests)
               OR EXISTS (SELECT 1 FROM demo_context_compile_results) THEN
                RAISE EXCEPTION 'D10 queued Context authority exists; downgrade is forbidden';
            END IF;
        END;
        $block$;
        """
    )
    op.execute(
        "DROP TRIGGER trg_demo_context_compile_result_integrity ON demo_context_compile_results"
    )
    op.execute(
        "DROP TRIGGER trg_demo_context_compile_request_integrity ON demo_context_compile_requests"
    )
    op.execute(
        "DROP TRIGGER trg_demo_authority_demo_context_compile_results "
        "ON demo_context_compile_results"
    )
    op.execute(
        "DROP TRIGGER trg_demo_authority_demo_context_compile_requests "
        "ON demo_context_compile_requests"
    )
    op.execute("DROP FUNCTION mirror_demo_validate_context_compile_result()")
    op.execute("DROP FUNCTION mirror_demo_validate_context_compile_request()")
    op.drop_table("demo_context_compile_results")
    op.drop_table("demo_context_compile_requests")
