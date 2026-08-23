"""Branch-local synchronous Demo command authority.

Revision ID: demo_0002_p3_p7_command_auth
Revises: demo_0001_p3_p7_core
Create Date: 2026-08-23

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0002_p3_p7_command_auth"
down_revision: str | None = "demo_0001_p3_p7_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"


_COMMAND_AUTHORITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_command_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_response_type text;
    expected_response_status integer;
    target_valid boolean := false;
BEGIN
    expected_response_type := CASE NEW.endpoint_operation
        WHEN 'session.create' THEN 'DEMO_SESSION'
        WHEN 'questionnaire.response.create' THEN 'QUESTIONNAIRE_STEP'
        WHEN 'style_feedback.create' THEN 'PREFERENCE_EVENT'
        WHEN 'constraint.create' THEN 'IDENTITY_CONSTRAINTS'
        WHEN 'image_version.feedback' THEN 'PREFERENCE_EVENT'
        WHEN 'job.cancel' THEN 'JOB'
        ELSE NULL
    END;
    expected_response_status := CASE NEW.endpoint_operation
        WHEN 'job.cancel' THEN 200
        ELSE 201
    END;

    IF expected_response_type IS NULL
        OR NEW.response_type <> expected_response_type
        OR NEW.response_status <> expected_response_status THEN
        RAISE EXCEPTION 'Demo command operation and typed response disagree';
    END IF;

    CASE NEW.response_type
        WHEN 'DEMO_SESSION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL
                AND NEW.response_id = NEW.demo_session_id
                AND EXISTS (
                    SELECT 1 FROM demo_sessions target_row
                    WHERE target_row.id = NEW.response_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                );
        WHEN 'QUESTIONNAIRE_STEP' THEN
            target_valid := NEW.demo_session_id IS NOT NULL
                AND EXISTS (
                    SELECT 1 FROM demo_questionnaire_steps target_row
                    WHERE target_row.id = NEW.response_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                      AND target_row.demo_session_id = NEW.demo_session_id
                      AND target_row.event_type = 'RESPONDED'
                );
        WHEN 'PREFERENCE_EVENT' THEN
            IF NEW.endpoint_operation = 'style_feedback.create' THEN
                target_valid := EXISTS (
                    SELECT 1 FROM demo_preference_events target_row
                    WHERE target_row.id = NEW.response_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                      AND target_row.demo_session_id IS NOT DISTINCT FROM NEW.demo_session_id
                      AND target_row.source_type = 'EXPLICIT_USER_ACTION'
                      AND target_row.event_type IN (
                          'EXPLICIT_STYLE_SELECTION',
                          'MAXIMUM_INTENSITY_CHANGED'
                      )
                );
            ELSIF NEW.endpoint_operation = 'image_version.feedback' THEN
                target_valid := NEW.demo_session_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM demo_preference_events target_row
                        JOIN demo_image_versions image_row
                          ON image_row.id = target_row.target_id
                        WHERE target_row.id = NEW.response_id
                          AND target_row.demo_actor_id = NEW.demo_actor_id
                          AND target_row.demo_session_id = NEW.demo_session_id
                          AND target_row.event_type IN (
                              'IMAGE_ACCEPTED',
                              'IMAGE_REJECTED',
                              'IMAGE_ADJUSTED'
                          )
                          AND target_row.source_type IN (
                              'EXPLICIT_USER_ACTION',
                              'EDIT_FEEDBACK'
                          )
                          AND target_row.target_type = 'IMAGE_VERSION'
                          AND image_row.demo_actor_id = NEW.demo_actor_id
                          AND image_row.demo_session_id = NEW.demo_session_id
                    );
            END IF;
        WHEN 'IDENTITY_CONSTRAINTS' THEN
            target_valid := EXISTS (
                SELECT 1 FROM demo_identity_constraints target_row
                WHERE target_row.id = NEW.response_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id IS NOT DISTINCT FROM NEW.demo_session_id
            );
        WHEN 'JOB' THEN
            target_valid := NEW.endpoint_operation = 'job.cancel'
                AND EXISTS (
                    SELECT 1
                    FROM jobs target_row
                    JOIN demo_job_bindings binding_row
                      ON binding_row.job_id = target_row.id
                    WHERE target_row.id = NEW.response_id
                      AND binding_row.demo_actor_id = NEW.demo_actor_id
                      AND binding_row.demo_session_id IS NOT DISTINCT FROM NEW.demo_session_id
                      AND target_row.job_type LIKE 'demo_p3_p7.%'
                      AND target_row.status = 'CANCELLED'
                      AND target_row.owner_user_id IS NULL
                      AND target_row.ingestion_upload_intent_id IS NULL
                      AND target_row.payload::jsonb = '{}'::jsonb
                      AND target_row.finalized_at IS NOT NULL
                      AND target_row.result_asset_id IS NULL
                      AND target_row.result_code IS NOT NULL
                );
    END CASE;

    IF NOT target_valid THEN
        RAISE EXCEPTION 'Demo command response ownership or lifecycle mismatch';
    END IF;
    RETURN NEW;
END;
$function$;
"""


_POPULATED_DOWNGRADE_SQL = r"""
DO $block$
BEGIN
    IF EXISTS (SELECT 1 FROM demo_command_bindings LIMIT 1) THEN
        RAISE EXCEPTION 'Prototype command authority downgrade blocked by populated table demo_command_bindings';
    END IF;
END;
$block$;
"""


def upgrade() -> None:
    op.create_table(
        "demo_command_bindings",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column(
            "canonical_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=True),
        sa.Column("endpoint_operation", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("response_type", sa.String(length=32), nullable=False),
        sa.Column("response_id", sa.String(length=32), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{32}$'",
            name=op.f("ck_demo_command_bindings_id_shape"),
        ),
        sa.CheckConstraint(
            "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
            name=op.f("ck_demo_command_bindings_schema_version_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'",
            name=op.f("ck_demo_command_bindings_canonical_payload_object"),
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_command_bindings_content_digest_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_command_bindings_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_command_bindings_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_command_bindings")),
        sa.UniqueConstraint(
            "content_digest",
            name=op.f("uq_demo_command_bindings_content_digest"),
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "endpoint_operation",
            "idempotency_key_hash",
            name=op.f("uq_demo_command_bindings_actor_operation_key"),
        ),
        sa.UniqueConstraint(
            "response_type",
            "response_id",
            name=op.f("uq_demo_command_bindings_typed_response"),
        ),
        sa.CheckConstraint(
            "endpoint_operation IN ('session.create','questionnaire.response.create',"
            "'style_feedback.create','constraint.create','image_version.feedback','job.cancel')",
            name=op.f("ck_demo_command_bindings_endpoint_operation"),
        ),
        sa.CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_command_bindings_idempotency_key_hash_shape"),
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_command_bindings_request_digest_shape"),
        ),
        sa.CheckConstraint(
            "response_type IN ('DEMO_SESSION','QUESTIONNAIRE_STEP',"
            "'PREFERENCE_EVENT','IDENTITY_CONSTRAINTS','JOB')",
            name=op.f("ck_demo_command_bindings_response_type"),
        ),
        sa.CheckConstraint(
            "response_id ~ '^[0-9a-f]{32}$'",
            name=op.f("ck_demo_command_bindings_response_id_shape"),
        ),
        sa.CheckConstraint(
            "response_status IN (200,201)",
            name=op.f("ck_demo_command_bindings_response_status"),
        ),
    )
    op.create_index(
        op.f("ix_demo_command_bindings_demo_actor_id"),
        "demo_command_bindings",
        ["demo_actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_demo_command_bindings_demo_session_id"),
        "demo_command_bindings",
        ["demo_session_id"],
        unique=False,
    )
    op.execute(_COMMAND_AUTHORITY_SQL)
    op.execute(
        "CREATE TRIGGER trg_demo_authority_demo_command_bindings "
        "BEFORE INSERT OR UPDATE OR DELETE ON demo_command_bindings "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_command_binding_validation "
        "BEFORE INSERT ON demo_command_bindings "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_command_binding()"
    )


def downgrade() -> None:
    op.execute(_POPULATED_DOWNGRADE_SQL)
    op.drop_table("demo_command_bindings")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_command_binding()")
