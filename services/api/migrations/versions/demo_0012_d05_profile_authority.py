"""Add D05 profile compilation and self-transfer projection authority.

Revision ID: demo_0012_d05_profile_auth
Revises: demo_0011_d03_job_recovery
Create Date: 2026-08-30

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0012_d05_profile_auth"
down_revision: str | None = "demo_0011_d03_job_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"


def _common_columns() -> tuple[sa.Column[Any], ...]:
    return (
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def _common_constraints(table_name: str) -> tuple[sa.Constraint, ...]:
    return (
        sa.CheckConstraint("id ~ '^[0-9a-f]{32}$'", name=op.f(f"ck_{table_name}_id_shape")),
        sa.CheckConstraint(
            "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
            name=op.f(f"ck_{table_name}_schema_version_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'",
            name=op.f(f"ck_{table_name}_canonical_payload_object"),
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{table_name}_content_digest_shape"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
        sa.UniqueConstraint("content_digest", name=op.f(f"uq_{table_name}_content_digest")),
    )


_VALIDATION_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_profile_compilation_bundle()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    binding_row demo_job_bindings%ROWTYPE;
    desired_row demo_desired_delta_profiles%ROWTYPE;
    style_row demo_style_profiles%ROWTYPE;
    persistent_row demo_identity_constraints%ROWTYPE;
    session_row demo_identity_constraints%ROWTYPE;
BEGIN
    SELECT * INTO binding_row FROM demo_job_bindings WHERE id = NEW.demo_job_binding_id;
    IF NOT FOUND OR binding_row.demo_actor_id IS DISTINCT FROM NEW.demo_actor_id
       OR binding_row.demo_session_id IS DISTINCT FROM NEW.demo_session_id
       OR binding_row.endpoint_operation <> 'profile.compile'
       OR binding_row.target_type <> 'DEMO_ACTOR'
       OR binding_row.target_id <> NEW.demo_actor_id THEN
        RAISE EXCEPTION 'Profile compilation bundle lacks exact JobBinding';
    END IF;

    SELECT * INTO desired_row FROM demo_desired_delta_profiles
    WHERE id = NEW.desired_delta_profile_id;
    IF NOT FOUND OR desired_row.demo_actor_id <> NEW.demo_actor_id
       OR desired_row.demo_session_id <> NEW.demo_session_id
       OR desired_row.self_state_id <> NEW.self_state_id
       OR desired_row.demo_job_binding_id IS DISTINCT FROM NEW.demo_job_binding_id
       OR desired_row.as_of_event_sequence <> NEW.as_of_event_sequence
       OR desired_row.compilation_watermark <> NEW.compilation_watermark
       OR desired_row.compiler_version <> NEW.compiler_version THEN
        RAISE EXCEPTION 'Profile compilation bundle DesiredDeltaProfile mismatch';
    END IF;

    SELECT * INTO style_row FROM demo_style_profiles WHERE id = NEW.style_profile_id;
    IF NOT FOUND OR style_row.demo_actor_id <> NEW.demo_actor_id
       OR style_row.demo_session_id IS DISTINCT FROM NEW.demo_session_id
       OR style_row.desired_delta_profile_id <> NEW.desired_delta_profile_id
       OR style_row.demo_job_binding_id IS DISTINCT FROM NEW.demo_job_binding_id
       OR style_row.as_of_event_sequence <> NEW.as_of_event_sequence
       OR style_row.compilation_watermark <> NEW.compilation_watermark
       OR style_row.compiler_version <> NEW.compiler_version THEN
        RAISE EXCEPTION 'Profile compilation bundle StyleProfile mismatch';
    END IF;

    SELECT * INTO persistent_row FROM demo_identity_constraints
    WHERE id = NEW.persistent_constraints_id;
    IF NOT FOUND OR persistent_row.demo_actor_id <> NEW.demo_actor_id
       OR persistent_row.demo_session_id IS NOT NULL
       OR persistent_row.self_state_id IS DISTINCT FROM NEW.self_state_id
       OR persistent_row.constraint_scope <> 'PERSISTENT' THEN
        RAISE EXCEPTION 'Profile compilation bundle persistent constraints mismatch';
    END IF;

    SELECT * INTO session_row FROM demo_identity_constraints
    WHERE id = NEW.session_override_constraints_id;
    IF NOT FOUND OR session_row.demo_actor_id <> NEW.demo_actor_id
       OR session_row.demo_session_id IS DISTINCT FROM NEW.demo_session_id
       OR session_row.self_state_id IS DISTINCT FROM NEW.self_state_id
       OR session_row.constraint_scope <> 'SESSION_OVERRIDE' THEN
        RAISE EXCEPTION 'Profile compilation bundle session constraints mismatch';
    END IF;

    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements_text(style_row.evidence_digests) digest(value)
        WHERE NOT EXISTS (
            SELECT 1 FROM demo_preference_events event_row
            WHERE event_row.demo_actor_id = NEW.demo_actor_id
              AND event_row.content_digest = digest.value
              AND event_row.event_sequence <= NEW.as_of_event_sequence
              AND event_row.source_type = 'EXPLICIT_USER_ACTION'
              AND event_row.event_type = 'EXPLICIT_STYLE_SELECTION'
        )
    ) OR jsonb_typeof(style_row.preferences -> 'style_keys') IS DISTINCT FROM 'array'
      OR (
        jsonb_array_length(style_row.preferences -> 'style_keys') > 0
        AND jsonb_array_length(style_row.evidence_digests) = 0
    ) OR (
        SELECT count(*) FROM jsonb_array_elements_text(style_row.evidence_digests)
    ) <> (
        SELECT count(DISTINCT value)
        FROM jsonb_array_elements_text(style_row.evidence_digests) digest(value)
    ) OR EXISTS (
        SELECT 1 FROM jsonb_array_elements_text(persistent_row.source_event_digests) digest(value)
        WHERE NOT EXISTS (
            SELECT 1 FROM demo_preference_events event_row
            WHERE event_row.demo_actor_id = NEW.demo_actor_id
              AND event_row.content_digest = digest.value
              AND event_row.event_sequence <= NEW.as_of_event_sequence
              AND event_row.source_type = 'EXPLICIT_USER_ACTION'
              AND event_row.event_type IN (
                  'FEATURE_LOCKED',
                  'FEATURE_UNLOCKED',
                  'MAXIMUM_INTENSITY_CHANGED',
                  'PROHIBITED_OPERATION_ADDED'
              )
              AND event_row.signal ->> 'constraint_scope' = 'PERSISTENT'
        )
    ) OR (
        SELECT count(*) FROM jsonb_array_elements_text(persistent_row.source_event_digests)
    ) <> (
        SELECT count(DISTINCT value)
        FROM jsonb_array_elements_text(persistent_row.source_event_digests) digest(value)
    ) OR EXISTS (
        SELECT 1 FROM jsonb_array_elements_text(session_row.source_event_digests) digest(value)
        WHERE NOT EXISTS (
            SELECT 1 FROM demo_preference_events event_row
            WHERE event_row.demo_actor_id = NEW.demo_actor_id
              AND event_row.demo_session_id = NEW.demo_session_id
              AND event_row.content_digest = digest.value
              AND event_row.event_sequence <= NEW.as_of_event_sequence
              AND event_row.source_type = 'EXPLICIT_USER_ACTION'
              AND (
                  event_row.event_type = 'TEMPORARY_SESSION_OVERRIDE'
                  OR (
                      event_row.event_type IN (
                          'FEATURE_LOCKED',
                          'FEATURE_UNLOCKED',
                          'MAXIMUM_INTENSITY_CHANGED',
                          'PROHIBITED_OPERATION_ADDED'
                      )
                      AND event_row.signal ->> 'constraint_scope' = 'SESSION_OVERRIDE'
                  )
              )
        )
    ) OR (
        SELECT count(*) FROM jsonb_array_elements_text(session_row.source_event_digests)
    ) <> (
        SELECT count(DISTINCT value)
        FROM jsonb_array_elements_text(session_row.source_event_digests) digest(value)
    ) THEN
        RAISE EXCEPTION 'Profile compilation bundle references non-authoritative explicit event';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_self_transfer_dimension_evidence()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    transfer_row demo_self_transfer_runs%ROWTYPE;
    verifier_row demo_verification_results%ROWTYPE;
BEGIN
    SELECT * INTO transfer_row FROM demo_self_transfer_runs
    WHERE id = NEW.self_transfer_run_id;
    IF NOT FOUND OR transfer_row.demo_actor_id <> NEW.demo_actor_id
       OR transfer_row.demo_session_id <> NEW.demo_session_id
       OR transfer_row.record_kind <> 'RESULT'
       OR transfer_row.verifier_digest IS DISTINCT FROM NEW.verifier_digest
       OR transfer_row.measured_delta IS NULL
       OR NOT (transfer_row.measured_delta ? NEW.dimension_key)
       OR (transfer_row.measured_delta ->> NEW.dimension_key)::integer
          <> NEW.desired_delta_ppm THEN
        RAISE EXCEPTION 'Self-transfer dimension evidence parent mismatch';
    END IF;

    SELECT * INTO verifier_row FROM demo_verification_results
    WHERE content_digest = NEW.verifier_digest;
    IF NOT FOUND OR verifier_row.demo_actor_id <> NEW.demo_actor_id
       OR verifier_row.demo_session_id <> NEW.demo_session_id
       OR verifier_row.outcome <> NEW.verifier_outcome THEN
        RAISE EXCEPTION 'Self-transfer dimension evidence verifier mismatch';
    END IF;
    RETURN NEW;
END;
$function$;
"""


def upgrade() -> None:
    op.create_index(
        "uq_demo_desired_delta_profiles_job_binding",
        "demo_desired_delta_profiles",
        ["demo_job_binding_id"],
        unique=True,
        postgresql_where=sa.text("demo_job_binding_id IS NOT NULL"),
    )
    op.create_index(
        "uq_demo_style_profiles_job_binding",
        "demo_style_profiles",
        ["demo_job_binding_id"],
        unique=True,
        postgresql_where=sa.text("demo_job_binding_id IS NOT NULL"),
    )

    op.create_table(
        "demo_profile_compilation_bundles",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("self_state_id", sa.String(length=32), nullable=False),
        sa.Column("desired_delta_profile_id", sa.String(length=32), nullable=False),
        sa.Column("style_profile_id", sa.String(length=32), nullable=False),
        sa.Column("persistent_constraints_id", sa.String(length=32), nullable=False),
        sa.Column("session_override_constraints_id", sa.String(length=32), nullable=False),
        sa.Column("as_of_event_sequence", sa.BigInteger(), nullable=False),
        sa.Column("compilation_watermark", sa.String(length=64), nullable=False),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("compilation_digest", sa.String(length=64), nullable=False),
        *_common_constraints("demo_profile_compilation_bundles"),
        sa.ForeignKeyConstraint(["demo_actor_id"], ["demo_actors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_profile_compilation_bundles_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_job_binding_id"],
            ["demo_job_bindings.id"],
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["self_state_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_self_states.id",
                "demo_self_states.demo_actor_id",
                "demo_self_states.demo_session_id",
            ],
            name=op.f("fk_demo_profile_compilation_bundles_self_state_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["desired_delta_profile_id"],
            ["demo_desired_delta_profiles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["style_profile_id"], ["demo_style_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["persistent_constraints_id"],
            ["demo_identity_constraints.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_override_constraints_id"],
            ["demo_identity_constraints.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_job_binding_id",
            name=op.f("uq_demo_profile_compilation_bundles_job_binding"),
        ),
        sa.UniqueConstraint(
            "desired_delta_profile_id",
            name=op.f("uq_demo_profile_compilation_bundles_desired_profile"),
        ),
        sa.UniqueConstraint(
            "style_profile_id",
            name=op.f("uq_demo_profile_compilation_bundles_style_profile"),
        ),
        sa.UniqueConstraint(
            "persistent_constraints_id",
            name=op.f("uq_demo_profile_compilation_bundles_persistent_constraints"),
        ),
        sa.UniqueConstraint(
            "session_override_constraints_id",
            name=op.f("uq_demo_profile_compilation_bundles_session_constraints"),
        ),
        sa.CheckConstraint(
            "as_of_event_sequence >= 0",
            name=op.f("ck_demo_profile_compilation_bundles_nonnegative_event_sequence"),
        ),
        sa.CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_profile_compilation_bundles_watermark_shape"),
        ),
        sa.CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_profile_compilation_bundles_input_digest_shape"),
        ),
        sa.CheckConstraint(
            "compilation_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_profile_compilation_bundles_compilation_digest_shape"),
        ),
        sa.CheckConstraint(
            "persistent_constraints_id <> session_override_constraints_id",
            name=op.f("ck_demo_profile_compilation_bundles_distinct_constraint_rows"),
        ),
    )

    op.create_table(
        "demo_self_transfer_evidence",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("self_transfer_run_id", sa.String(length=32), nullable=False),
        sa.Column("dimension_key", sa.String(length=48), nullable=False),
        sa.Column("desired_delta_ppm", sa.Integer(), nullable=False),
        sa.Column("confidence_ppm", sa.Integer(), nullable=False),
        sa.Column("verifier_outcome", sa.String(length=24), nullable=False),
        sa.Column("verifier_digest", sa.String(length=64), nullable=False),
        sa.Column("projection_version", sa.String(length=64), nullable=False),
        sa.Column("projection_config_digest", sa.String(length=64), nullable=False),
        *_common_constraints("demo_self_transfer_evidence"),
        sa.ForeignKeyConstraint(
            ["self_transfer_run_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_self_transfer_runs.id",
                "demo_self_transfer_runs.demo_actor_id",
                "demo_self_transfer_runs.demo_session_id",
            ],
            name=op.f("fk_demo_self_transfer_evidence_run_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verifier_digest"],
            ["demo_verification_results.content_digest"],
            name=op.f("fk_demo_self_transfer_evidence_verifier_digest"),
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint(
            "self_transfer_run_id",
            "dimension_key",
            name=op.f("uq_demo_self_transfer_evidence_run_dimension"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_self_transfer_evidence_id_actor_session"),
        ),
        sa.CheckConstraint(
            "dimension_key ~ '^[a-z][a-z0-9_]{0,47}$'",
            name=op.f("ck_demo_self_transfer_evidence_dimension_key_shape"),
        ),
        sa.CheckConstraint(
            "desired_delta_ppm BETWEEN -1000000 AND 1000000",
            name=op.f("ck_demo_self_transfer_evidence_desired_delta_range"),
        ),
        sa.CheckConstraint(
            "confidence_ppm BETWEEN 0 AND 1000000",
            name=op.f("ck_demo_self_transfer_evidence_confidence_range"),
        ),
        sa.CheckConstraint(
            "verifier_outcome IN ('PASS','FAIL','HUMAN_REVIEW')",
            name=op.f("ck_demo_self_transfer_evidence_verifier_outcome"),
        ),
        sa.CheckConstraint(
            "verifier_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_self_transfer_evidence_verifier_digest_shape"),
        ),
        sa.CheckConstraint(
            "projection_config_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_self_transfer_evidence_projection_config_digest_shape"),
        ),
        sa.CheckConstraint(
            "projection_version <> ''",
            name=op.f("ck_demo_self_transfer_evidence_projection_version_nonempty"),
        ),
    )

    for table_name, columns in {
        "demo_profile_compilation_bundles": (
            "demo_actor_id",
            "demo_session_id",
            "demo_job_binding_id",
            "self_state_id",
            "desired_delta_profile_id",
            "style_profile_id",
            "persistent_constraints_id",
            "session_override_constraints_id",
        ),
        "demo_self_transfer_evidence": (
            "demo_actor_id",
            "demo_session_id",
            "self_transfer_run_id",
            "verifier_digest",
        ),
    }.items():
        for column_name in columns:
            op.create_index(
                op.f(f"ix_{table_name}_{column_name}"),
                table_name,
                [column_name],
                unique=False,
            )

    op.execute(_VALIDATION_SQL)
    for table_name in (
        "demo_profile_compilation_bundles",
        "demo_self_transfer_evidence",
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_demo_authority_{table_name} "
                f"BEFORE INSERT OR UPDATE OR DELETE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
            )
        )
    op.execute(
        "CREATE TRIGGER trg_demo_profile_compilation_bundle_validation "
        "BEFORE INSERT ON demo_profile_compilation_bundles "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_profile_compilation_bundle()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_self_transfer_evidence_validation "
        "BEFORE INSERT ON demo_self_transfer_evidence "
        "FOR EACH ROW EXECUTE FUNCTION "
        "mirror_demo_validate_self_transfer_dimension_evidence()"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (SELECT 1 FROM demo_profile_compilation_bundles)
               OR EXISTS (SELECT 1 FROM demo_self_transfer_evidence) THEN
                RAISE EXCEPTION 'cannot downgrade populated D05 profile authority';
            END IF;
        END;
        $block$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_demo_self_transfer_evidence_validation "
        "ON demo_self_transfer_evidence"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_demo_profile_compilation_bundle_validation "
        "ON demo_profile_compilation_bundles"
    )
    for table_name in (
        "demo_self_transfer_evidence",
        "demo_profile_compilation_bundles",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_demo_authority_{table_name} ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_self_transfer_dimension_evidence()")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_profile_compilation_bundle()")
    op.drop_table("demo_self_transfer_evidence")
    op.drop_table("demo_profile_compilation_bundles")
    op.drop_index("uq_demo_style_profiles_job_binding", table_name="demo_style_profiles")
    op.drop_index(
        "uq_demo_desired_delta_profiles_job_binding",
        table_name="demo_desired_delta_profiles",
    )
