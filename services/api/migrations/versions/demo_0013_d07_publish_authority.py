"""Add D07 quarantine artifact and PASS-only publication authority.

Revision ID: demo_0013_d07_publish_auth
Revises: demo_0012_d05_profile_auth
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

revision: str = "demo_0013_d07_publish_auth"
down_revision: str | None = "demo_0012_d05_profile_auth"
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


_D07_VALIDATION_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_edit_artifact()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    operation_row demo_edit_operations%ROWTYPE;
    plan_row demo_edit_plans%ROWTYPE;
    binding_row demo_job_bindings%ROWTYPE;
    attempt_job_id text;
    expected_object_key text;
BEGIN
    SELECT * INTO operation_row FROM demo_edit_operations
    WHERE id = NEW.edit_operation_id
      AND demo_actor_id = NEW.demo_actor_id
      AND demo_session_id = NEW.demo_session_id;
    IF NOT FOUND OR operation_row.engine IS DISTINCT FROM NEW.engine THEN
        RAISE EXCEPTION 'Demo edit artifact operation ownership mismatch';
    END IF;

    SELECT * INTO plan_row FROM demo_edit_plans
    WHERE id = operation_row.edit_plan_id
      AND record_kind = 'RESULT'
      AND demo_actor_id = NEW.demo_actor_id
      AND demo_session_id = NEW.demo_session_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo edit artifact lacks RESULT plan';
    END IF;

    SELECT * INTO binding_row FROM demo_job_bindings
    WHERE id = NEW.execution_job_binding_id
      AND demo_actor_id = NEW.demo_actor_id
      AND demo_session_id = NEW.demo_session_id
      AND endpoint_operation = 'edit_plan.execute'
      AND target_type = 'EDIT_PLAN'
      AND target_id = plan_row.id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo edit artifact lacks exact execution JobBinding';
    END IF;

    SELECT job_id INTO attempt_job_id FROM job_attempts
    WHERE id = NEW.formal_job_attempt_id;
    IF attempt_job_id IS DISTINCT FROM binding_row.job_id THEN
        RAISE EXCEPTION 'Demo edit artifact JobAttempt ownership mismatch';
    END IF;

    expected_object_key := 'demo-quarantine/' || NEW.demo_actor_id || '/' ||
        NEW.execution_job_binding_id || '/' || NEW.edit_operation_id || '/' ||
        NEW.formal_job_attempt_id;
    IF NEW.private_object_key IS DISTINCT FROM expected_object_key THEN
        RAISE EXCEPTION 'Demo edit artifact private object key is not deterministic';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_edit_artifact_event()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    artifact_row demo_edit_artifacts%ROWTYPE;
    materialized_row demo_edit_artifact_events%ROWTYPE;
    prior_row demo_edit_artifact_events%ROWTYPE;
    verification_row demo_verification_results%ROWTYPE;
    tool_row demo_tool_runs%ROWTYPE;
    image_row demo_image_versions%ROWTYPE;
    asset_row assets%ROWTYPE;
    variant_row asset_variants%ROWTYPE;
    prior_sequence integer;
BEGIN
    SELECT * INTO artifact_row FROM demo_edit_artifacts
    WHERE id = NEW.demo_edit_artifact_id
      AND demo_actor_id = NEW.demo_actor_id
      AND demo_session_id = NEW.demo_session_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo edit artifact event ownership mismatch';
    END IF;

    SELECT COALESCE(max(sequence), 0) INTO prior_sequence
    FROM demo_edit_artifact_events
    WHERE demo_edit_artifact_id = NEW.demo_edit_artifact_id;
    IF NEW.sequence <> prior_sequence + 1 THEN
        RAISE EXCEPTION 'Demo edit artifact event sequence is not contiguous';
    END IF;

    SELECT * INTO prior_row FROM demo_edit_artifact_events
    WHERE demo_edit_artifact_id = NEW.demo_edit_artifact_id
    ORDER BY sequence DESC LIMIT 1;
    IF FOUND AND prior_row.event_type IN ('PROMOTED','CLEANED') THEN
        RAISE EXCEPTION 'Demo edit artifact terminal state cannot transition';
    END IF;
    IF FOUND AND prior_row.event_type IN ('REJECTED','CANCELLED')
       AND NEW.event_type <> 'CLEANED' THEN
        RAISE EXCEPTION 'Rejected or cancelled Demo artifact may only be cleaned';
    END IF;

    IF NEW.event_type = 'MATERIALIZED' THEN
        IF NEW.sequence <> 1
           OR NEW.engine_digest IS DISTINCT FROM artifact_row.expected_engine_digest
           OR NEW.config_digest IS DISTINCT FROM artifact_row.expected_config_digest THEN
            RAISE EXCEPTION 'Demo materialized artifact metadata disagrees with reservation';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.event_type = 'CANCELLED' THEN
        IF NEW.sequence NOT IN (1, 2)
           OR (NEW.sequence = 2 AND prior_row.event_type <> 'MATERIALIZED') THEN
            RAISE EXCEPTION 'Demo artifact cancellation transition is invalid';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.event_type = 'CLEANED' THEN
        IF prior_row.event_type NOT IN ('REJECTED','CANCELLED') THEN
            RAISE EXCEPTION 'Only rejected or cancelled Demo artifacts may be cleaned';
        END IF;
        RETURN NEW;
    END IF;

    SELECT * INTO materialized_row FROM demo_edit_artifact_events
    WHERE demo_edit_artifact_id = NEW.demo_edit_artifact_id
      AND sequence = 1
      AND event_type = 'MATERIALIZED';
    IF NOT FOUND OR NEW.sequence <> 2 THEN
        RAISE EXCEPTION 'Demo artifact publication decision requires materialization';
    END IF;

    SELECT * INTO verification_row FROM demo_verification_results
    WHERE id = NEW.verification_result_id
      AND demo_edit_artifact_id = NEW.demo_edit_artifact_id
      AND demo_actor_id = NEW.demo_actor_id
      AND demo_session_id = NEW.demo_session_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo artifact decision lacks exact verification';
    END IF;

    IF NEW.event_type = 'REJECTED' THEN
        IF verification_row.outcome NOT IN ('FAIL','HUMAN_REVIEW')
           OR verification_row.image_version_id IS NOT NULL
           OR verification_row.output_asset_id IS NOT NULL THEN
            RAISE EXCEPTION 'Demo artifact rejection references publishable verification';
        END IF;
        RETURN NEW;
    END IF;

    IF verification_row.outcome <> 'PASS'
       OR verification_row.image_version_id IS DISTINCT FROM NEW.image_version_id
       OR verification_row.output_asset_id IS DISTINCT FROM NEW.promoted_asset_id THEN
        RAISE EXCEPTION 'Demo artifact promotion requires PASS verification';
    END IF;
    PERFORM mirror_demo_require_asset(
        NEW.promoted_asset_id,
        verification_row.output_asset_sha256
    );
    SELECT * INTO asset_row FROM assets WHERE id = NEW.promoted_asset_id;
    IF asset_row.sha256 IS DISTINCT FROM materialized_row.object_sha256
       OR asset_row.byte_size IS DISTINCT FROM materialized_row.byte_size
       OR asset_row.width IS DISTINCT FROM materialized_row.width
       OR asset_row.height IS DISTINCT FROM materialized_row.height
       OR asset_row.mime_type IS DISTINCT FROM materialized_row.mime_type
       OR asset_row.asset_role <> 'derived'
       OR NOT asset_row.synthetic THEN
        RAISE EXCEPTION 'Promoted Demo Asset disagrees with materialized artifact';
    END IF;

    SELECT * INTO tool_row FROM demo_tool_runs
    WHERE id = verification_row.tool_run_id
      AND demo_edit_artifact_id = NEW.demo_edit_artifact_id
      AND outcome = 'COMPLETED';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo artifact promotion lacks completed ToolRun';
    END IF;

    SELECT * INTO variant_row FROM asset_variants
    WHERE id = NEW.promoted_asset_variant_id
      AND source_asset_id = tool_row.input_asset_id
      AND result_asset_id = NEW.promoted_asset_id
      AND variant_type LIKE 'demo_p3_p7\_%' ESCAPE '\';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo artifact promotion AssetVariant mismatch';
    END IF;

    SELECT * INTO image_row FROM demo_image_versions
    WHERE id = NEW.image_version_id
      AND demo_actor_id = NEW.demo_actor_id
      AND demo_session_id = NEW.demo_session_id
      AND source_asset_id = tool_row.input_asset_id
      AND result_asset_id = NEW.promoted_asset_id
      AND result_asset_variant_id = NEW.promoted_asset_variant_id
      AND tool_run_digest = tool_row.content_digest
      AND verifier_digest = verification_row.content_digest
      AND version_kind IN ('EDITED','RESTORED','ROLLED_BACK');
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo artifact promotion ImageVersion mismatch';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d07_tool_run()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    artifact_row demo_edit_artifacts%ROWTYPE;
BEGIN
    PERFORM mirror_demo_require_asset(NEW.input_asset_id, NEW.input_asset_sha256);
    SELECT artifact.* INTO artifact_row
    FROM demo_edit_artifacts artifact
    JOIN demo_edit_operations operation_row
      ON operation_row.id = artifact.edit_operation_id
    JOIN demo_edit_plans plan_row
      ON plan_row.id = operation_row.edit_plan_id
    JOIN demo_image_versions input_version
      ON input_version.id = plan_row.input_image_version_id
    JOIN demo_job_bindings binding_row
      ON binding_row.id = artifact.execution_job_binding_id
    JOIN job_attempts attempt_row
      ON attempt_row.id = artifact.formal_job_attempt_id
     AND attempt_row.job_id = binding_row.job_id
    WHERE artifact.id = NEW.demo_edit_artifact_id
      AND artifact.demo_actor_id = NEW.demo_actor_id
      AND artifact.demo_session_id = NEW.demo_session_id
      AND artifact.edit_operation_id = NEW.edit_operation_id
      AND artifact.execution_job_binding_id = NEW.demo_job_binding_id
      AND artifact.formal_job_attempt_id = NEW.formal_job_attempt_id
      AND operation_row.content_digest = NEW.edit_operation_digest
      AND plan_row.record_kind = 'RESULT'
      AND operation_row.operation_index >= 0
      AND operation_row.operation_index < jsonb_array_length(plan_row.operation_specs)
      AND plan_row.operation_specs -> operation_row.operation_index = jsonb_build_object(
          'engine', operation_row.engine,
          'operation_type', operation_row.operation_type,
          'parameters', operation_row.parameters,
          'preserve', operation_row.preserve,
          'expected_effect', operation_row.expected_effect
      )
      AND binding_row.demo_actor_id = NEW.demo_actor_id
      AND binding_row.demo_session_id = NEW.demo_session_id
      AND binding_row.endpoint_operation = 'edit_plan.execute'
      AND binding_row.target_type = 'EDIT_PLAN'
      AND binding_row.target_id = plan_row.id
      AND (
          (
              operation_row.operation_index = 0
              AND input_version.result_asset_id = NEW.input_asset_id
              AND input_version.result_asset_sha256 = NEW.input_asset_sha256
          ) OR (
              operation_row.operation_index > 0
              AND EXISTS (
                  SELECT 1
                  FROM demo_image_versions previous_image
                  JOIN demo_tool_runs previous_tool
                    ON previous_tool.content_digest = previous_image.tool_run_digest
                  JOIN demo_edit_operations previous_operation
                    ON previous_operation.id = previous_tool.edit_operation_id
                  WHERE previous_image.plan_digest = plan_row.content_digest
                    AND previous_operation.edit_plan_id = plan_row.id
                    AND previous_operation.operation_index = operation_row.operation_index - 1
                    AND previous_image.result_asset_id = NEW.input_asset_id
                    AND previous_image.result_asset_sha256 = NEW.input_asset_sha256
                    AND previous_tool.demo_job_binding_id = NEW.demo_job_binding_id
                    AND previous_tool.formal_job_attempt_id = NEW.formal_job_attempt_id
              )
          )
      );
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo ToolRun artifact reservation mismatch';
    END IF;
    IF NEW.outcome = 'COMPLETED' AND NOT EXISTS (
        SELECT 1 FROM demo_edit_artifact_events
        WHERE demo_edit_artifact_id = NEW.demo_edit_artifact_id
          AND event_type = 'MATERIALIZED'
    ) THEN
        RAISE EXCEPTION 'Completed Demo ToolRun requires materialized artifact';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_d07_verification()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    binding_job_id text;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM demo_tool_runs tool_row
        JOIN demo_edit_artifacts artifact_row
          ON artifact_row.id = tool_row.demo_edit_artifact_id
        JOIN demo_job_bindings binding_row
          ON binding_row.id = NEW.demo_job_binding_id
        JOIN job_attempts attempt_row
          ON attempt_row.id = NEW.formal_job_attempt_id
         AND attempt_row.job_id = binding_row.job_id
        WHERE tool_row.id = NEW.tool_run_id
          AND tool_row.demo_actor_id = NEW.demo_actor_id
          AND tool_row.demo_session_id = NEW.demo_session_id
          AND tool_row.outcome = 'COMPLETED'
          AND tool_row.demo_edit_artifact_id = NEW.demo_edit_artifact_id
          AND artifact_row.demo_actor_id = NEW.demo_actor_id
          AND artifact_row.demo_session_id = NEW.demo_session_id
          AND binding_row.demo_actor_id = NEW.demo_actor_id
          AND binding_row.demo_session_id = NEW.demo_session_id
          AND binding_row.endpoint_operation = 'tool.verify'
          AND binding_row.target_type = 'TOOL_RUN'
          AND binding_row.target_id = tool_row.id
    ) THEN
        RAISE EXCEPTION 'Demo verification ToolRun, artifact, or JobAttempt mismatch';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM demo_edit_artifact_events
        WHERE demo_edit_artifact_id = NEW.demo_edit_artifact_id
          AND event_type = 'MATERIALIZED'
    ) THEN
        RAISE EXCEPTION 'Demo verification requires materialized artifact';
    END IF;
    IF NEW.outcome = 'PASS' THEN
        PERFORM mirror_demo_require_asset(NEW.output_asset_id, NEW.output_asset_sha256);
    ELSIF EXISTS (
        SELECT 1 FROM demo_edit_artifact_events
        WHERE demo_edit_artifact_id = NEW.demo_edit_artifact_id
          AND event_type = 'PROMOTED'
    ) THEN
        RAISE EXCEPTION 'Rejected Demo verification cannot reference promoted artifact';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_require_image_execution_binding(
    authority_image_version_id text
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    image_row record;
    parent_row record;
    plan_row record;
    tool_row record;
    operation_row record;
    artifact_row record;
    materialized_row record;
    verification_row record;
BEGIN
    SELECT * INTO image_row FROM demo_image_versions
    WHERE id = authority_image_version_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution binding lacks ImageVersion';
    END IF;
    PERFORM mirror_demo_require_asset(image_row.source_asset_id, image_row.source_asset_sha256);
    PERFORM mirror_demo_require_asset(image_row.result_asset_id, image_row.result_asset_sha256);
    IF NOT EXISTS (
        SELECT 1 FROM asset_variants variant_row
        WHERE variant_row.id = image_row.result_asset_variant_id
          AND variant_row.source_asset_id = image_row.source_asset_id
          AND variant_row.result_asset_id = image_row.result_asset_id
          AND variant_row.variant_type LIKE 'demo_p3_p7\_%' ESCAPE '\'
    ) THEN
        RAISE EXCEPTION 'Demo image execution binding has invalid AssetVariant';
    END IF;

    IF image_row.sequence = 0 THEN
        IF image_row.version_kind <> 'ORIGINAL'
           OR image_row.parent_version_id IS NOT NULL
           OR image_row.plan_digest IS NOT NULL
           OR image_row.tool_run_digest IS NOT NULL
           OR image_row.verifier_digest IS NOT NULL
           OR EXISTS (
               SELECT 1 FROM demo_verification_results
               WHERE image_version_id = image_row.id
           ) THEN
            RAISE EXCEPTION 'Original Demo ImageVersion has execution authority';
        END IF;
        RETURN;
    END IF;

    IF image_row.version_kind NOT IN ('EDITED','RESTORED','ROLLED_BACK') THEN
        RAISE EXCEPTION 'Only PASS-published Demo ImageVersions may enter history';
    END IF;
    SELECT * INTO parent_row FROM demo_image_versions
    WHERE id = image_row.parent_version_id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND editing_session_id = image_row.editing_session_id
      AND sequence = image_row.sequence - 1
      AND result_asset_id = image_row.source_asset_id
      AND result_asset_sha256 = image_row.source_asset_sha256;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution parent binding mismatch';
    END IF;

    SELECT * INTO plan_row FROM demo_edit_plans
    WHERE content_digest = image_row.plan_digest
      AND record_kind = 'RESULT'
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND editing_session_id = image_row.editing_session_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution plan digest mismatch';
    END IF;

    SELECT * INTO tool_row FROM demo_tool_runs
    WHERE content_digest = image_row.tool_run_digest
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND outcome = 'COMPLETED'
      AND input_asset_id = parent_row.result_asset_id
      AND input_asset_sha256 = parent_row.result_asset_sha256
      AND output_asset_id IS NULL
      AND output_asset_sha256 IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution ToolRun digest mismatch';
    END IF;

    SELECT * INTO operation_row FROM demo_edit_operations
    WHERE id = tool_row.edit_operation_id
      AND content_digest = tool_row.edit_operation_digest
      AND edit_plan_id = plan_row.id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id;
    IF NOT FOUND
       OR operation_row.operation_index < 0
       OR operation_row.operation_index >= jsonb_array_length(plan_row.operation_specs)
       OR plan_row.operation_specs -> operation_row.operation_index IS DISTINCT FROM
          jsonb_build_object(
              'engine', operation_row.engine,
              'operation_type', operation_row.operation_type,
              'parameters', operation_row.parameters,
              'preserve', operation_row.preserve,
              'expected_effect', operation_row.expected_effect
          ) THEN
        RAISE EXCEPTION 'Demo image execution operation digest or specification mismatch';
    END IF;

    SELECT * INTO artifact_row FROM demo_edit_artifacts
    WHERE id = tool_row.demo_edit_artifact_id
      AND edit_operation_id = tool_row.edit_operation_id
      AND execution_job_binding_id = tool_row.demo_job_binding_id
      AND formal_job_attempt_id = tool_row.formal_job_attempt_id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution artifact reservation mismatch';
    END IF;
    SELECT * INTO materialized_row FROM demo_edit_artifact_events
    WHERE demo_edit_artifact_id = artifact_row.id
      AND event_type = 'MATERIALIZED'
      AND object_sha256 = image_row.result_asset_sha256;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution lacks exact materialized artifact';
    END IF;

    IF operation_row.operation_index = 0 THEN
        IF plan_row.input_image_version_id IS DISTINCT FROM parent_row.id THEN
            RAISE EXCEPTION 'First Demo plan operation does not consume plan input';
        END IF;
    ELSIF parent_row.plan_digest IS DISTINCT FROM plan_row.content_digest OR NOT EXISTS (
        SELECT 1
        FROM demo_tool_runs previous_tool
        JOIN demo_edit_operations previous_operation
          ON previous_operation.id = previous_tool.edit_operation_id
        WHERE previous_tool.content_digest = parent_row.tool_run_digest
          AND previous_operation.edit_plan_id = plan_row.id
          AND previous_operation.operation_index = operation_row.operation_index - 1
          AND previous_tool.demo_job_binding_id = tool_row.demo_job_binding_id
          AND previous_tool.formal_job_attempt_id = tool_row.formal_job_attempt_id
    ) THEN
        RAISE EXCEPTION 'Demo multi-operation plan execution is not contiguous';
    END IF;

    SELECT * INTO verification_row FROM demo_verification_results
    WHERE content_digest = image_row.verifier_digest
      AND image_version_id = image_row.id
      AND tool_run_id = tool_row.id
      AND demo_edit_artifact_id = artifact_row.id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND output_asset_id = image_row.result_asset_id
      AND output_asset_sha256 = image_row.result_asset_sha256
      AND outcome = 'PASS';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution PASS verifier digest mismatch';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM demo_edit_artifact_events promotion_row
        WHERE promotion_row.demo_edit_artifact_id = artifact_row.id
          AND promotion_row.event_type = 'PROMOTED'
          AND promotion_row.promoted_asset_id = image_row.result_asset_id
          AND promotion_row.promoted_asset_variant_id = image_row.result_asset_variant_id
          AND promotion_row.verification_result_id = verification_row.id
          AND promotion_row.image_version_id = image_row.id
    ) THEN
        RAISE EXCEPTION 'Demo image execution lacks exact promotion authority';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_image_execution_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_TABLE_NAME = 'demo_image_versions' THEN
        PERFORM mirror_demo_require_image_execution_binding(NEW.id);
    ELSIF NEW.outcome = 'PASS' THEN
        PERFORM mirror_demo_require_image_execution_binding(NEW.image_version_id);
    ELSIF NEW.image_version_id IS NOT NULL OR NEW.output_asset_id IS NOT NULL THEN
        RAISE EXCEPTION 'Rejected Demo verification cannot publish an ImageVersion';
    END IF;
    RETURN NEW;
END;
$function$;
"""


_LEGACY_IMAGE_EXECUTION_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_require_image_execution_binding(
    authority_image_version_id text
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    image_row record;
    parent_row record;
    plan_row record;
    tool_row record;
    operation_row record;
    verification_row record;
BEGIN
    SELECT * INTO image_row FROM demo_image_versions WHERE id = authority_image_version_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution binding lacks ImageVersion';
    END IF;
    PERFORM mirror_demo_require_asset(image_row.source_asset_id, image_row.source_asset_sha256);
    PERFORM mirror_demo_require_asset(image_row.result_asset_id, image_row.result_asset_sha256);
    IF NOT EXISTS (
        SELECT 1 FROM asset_variants variant_row
        WHERE variant_row.id = image_row.result_asset_variant_id
          AND variant_row.source_asset_id = image_row.source_asset_id
          AND variant_row.result_asset_id = image_row.result_asset_id
          AND variant_row.variant_type LIKE 'demo_p3_p7\_%' ESCAPE '\'
    ) THEN
        RAISE EXCEPTION 'Demo image execution binding has invalid AssetVariant';
    END IF;
    IF image_row.sequence = 0 THEN
        IF image_row.version_kind <> 'ORIGINAL'
           OR image_row.parent_version_id IS NOT NULL
           OR image_row.plan_digest IS NOT NULL
           OR image_row.tool_run_digest IS NOT NULL
           OR image_row.verifier_digest IS NOT NULL
           OR EXISTS (
               SELECT 1 FROM demo_verification_results verification
               WHERE verification.image_version_id = image_row.id
           ) THEN
            RAISE EXCEPTION 'Original Demo ImageVersion has execution authority';
        END IF;
        RETURN;
    END IF;
    SELECT * INTO parent_row FROM demo_image_versions
    WHERE id = image_row.parent_version_id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND editing_session_id = image_row.editing_session_id
      AND sequence = image_row.sequence - 1
      AND result_asset_id = image_row.source_asset_id
      AND result_asset_sha256 = image_row.source_asset_sha256;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution parent binding mismatch';
    END IF;
    SELECT * INTO plan_row FROM demo_edit_plans
    WHERE content_digest = image_row.plan_digest
      AND record_kind = 'RESULT'
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND editing_session_id = image_row.editing_session_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution plan digest mismatch';
    END IF;
    SELECT * INTO tool_row FROM demo_tool_runs
    WHERE content_digest = image_row.tool_run_digest
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND outcome = 'COMPLETED'
      AND input_asset_id = parent_row.result_asset_id
      AND input_asset_sha256 = parent_row.result_asset_sha256
      AND output_asset_id = image_row.result_asset_id
      AND output_asset_sha256 = image_row.result_asset_sha256;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution ToolRun digest mismatch';
    END IF;
    SELECT * INTO operation_row FROM demo_edit_operations
    WHERE id = tool_row.edit_operation_id
      AND content_digest = tool_row.edit_operation_digest
      AND edit_plan_id = plan_row.id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution operation digest or specification mismatch';
    END IF;
    SELECT * INTO verification_row FROM demo_verification_results
    WHERE content_digest = image_row.verifier_digest
      AND image_version_id = image_row.id
      AND tool_run_id = tool_row.id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND output_asset_id = image_row.result_asset_id
      AND output_asset_sha256 = image_row.result_asset_sha256;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution verifier digest mismatch';
    END IF;
    IF (image_row.version_kind IN ('EDITED','RESTORED','ROLLED_BACK')
            AND verification_row.outcome <> 'PASS')
       OR (image_row.version_kind = 'QUARANTINED'
            AND verification_row.outcome NOT IN ('FAIL','HUMAN_REVIEW')) THEN
        RAISE EXCEPTION 'Demo ImageVersion kind and verifier outcome disagree';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_image_execution_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_TABLE_NAME = 'demo_image_versions' THEN
        PERFORM mirror_demo_require_image_execution_binding(NEW.id);
    ELSE
        PERFORM mirror_demo_require_image_execution_binding(NEW.image_version_id);
    END IF;
    RETURN NEW;
END;
$function$;
"""


def upgrade() -> None:
    op.execute("LOCK TABLE demo_tool_runs, demo_verification_results IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (SELECT 1 FROM demo_tool_runs)
               OR EXISTS (SELECT 1 FROM demo_verification_results) THEN
                RAISE EXCEPTION 'cannot reinterpret populated pre-D07 publication authority';
            END IF;
        END;
        $block$;
        """
    )

    op.create_table(
        "demo_edit_artifacts",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("edit_operation_id", sa.String(length=32), nullable=False),
        sa.Column("execution_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("formal_job_attempt_id", sa.String(length=32), nullable=False),
        sa.Column("private_object_key", sa.String(length=255), nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("expected_engine_digest", sa.String(length=64), nullable=False),
        sa.Column("expected_config_digest", sa.String(length=64), nullable=False),
        *_common_constraints("demo_edit_artifacts"),
        sa.ForeignKeyConstraint(
            ["edit_operation_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_edit_operations.id",
                "demo_edit_operations.demo_actor_id",
                "demo_edit_operations.demo_session_id",
            ],
            name=op.f("fk_demo_edit_artifacts_operation_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["execution_job_binding_id"],
            ["demo_job_bindings.id"],
            name=op.f("fk_demo_edit_artifacts_execution_job_binding_id_demo_job_bindings"),
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["formal_job_attempt_id"],
            ["job_attempts.id"],
            name=op.f("fk_demo_edit_artifacts_formal_job_attempt_id_job_attempts"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "execution_job_binding_id",
            "formal_job_attempt_id",
            "edit_operation_id",
            name=op.f("uq_demo_edit_artifacts_execution_attempt_operation"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_edit_artifacts_id_actor_session"),
        ),
        sa.UniqueConstraint(
            "private_object_key",
            name=op.f("uq_demo_edit_artifacts_private_object_key"),
        ),
        sa.CheckConstraint(
            "private_object_key ~ "
            "'^demo-quarantine/[0-9a-f]{32}/[0-9a-f]{32}/[0-9a-f]{32}/[0-9a-f]{32}$'",
            name=op.f("ck_demo_edit_artifacts_private_object_key_shape"),
        ),
        sa.CheckConstraint(
            "engine IN ('RASTER','GEOMETRY')",
            name=op.f("ck_demo_edit_artifacts_engine"),
        ),
        sa.CheckConstraint(
            "expected_engine_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_edit_artifacts_expected_engine_digest_shape"),
        ),
        sa.CheckConstraint(
            "expected_config_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_edit_artifacts_expected_config_digest_shape"),
        ),
    )
    for column_name in (
        "demo_actor_id",
        "demo_session_id",
        "edit_operation_id",
        "execution_job_binding_id",
        "formal_job_attempt_id",
    ):
        op.create_index(
            op.f(f"ix_demo_edit_artifacts_{column_name}"),
            "demo_edit_artifacts",
            [column_name],
            unique=False,
        )

    op.add_column(
        "demo_tool_runs",
        sa.Column("demo_edit_artifact_id", sa.String(length=32), nullable=False),
    )
    op.create_foreign_key(
        op.f("fk_demo_tool_runs_demo_edit_artifact_id_demo_edit_artifacts"),
        "demo_tool_runs",
        "demo_edit_artifacts",
        ["demo_edit_artifact_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_demo_tool_runs_demo_edit_artifact_id"),
        "demo_tool_runs",
        ["demo_edit_artifact_id"],
        unique=True,
    )
    op.drop_constraint(
        op.f("ck_demo_tool_runs_outcome_result_shape"),
        "demo_tool_runs",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_tool_runs_output_shape"),
        "demo_tool_runs",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_tool_runs_output_shape"),
        "demo_tool_runs",
        "output_asset_id IS NULL AND output_asset_sha256 IS NULL",
    )

    op.add_column(
        "demo_verification_results",
        sa.Column("demo_edit_artifact_id", sa.String(length=32), nullable=False),
    )
    op.add_column(
        "demo_verification_results",
        sa.Column("formal_job_attempt_id", sa.String(length=32), nullable=False),
    )
    op.alter_column(
        "demo_verification_results",
        "image_version_id",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.alter_column(
        "demo_verification_results",
        "output_asset_id",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.alter_column(
        "demo_verification_results",
        "output_asset_sha256",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.create_foreign_key(
        op.f("fk_demo_verification_results_demo_edit_artifact_id_demo_edit_artifacts"),
        "demo_verification_results",
        "demo_edit_artifacts",
        ["demo_edit_artifact_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_demo_verification_results_formal_job_attempt_id_job_attempts"),
        "demo_verification_results",
        "job_attempts",
        ["formal_job_attempt_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_demo_verification_results_demo_edit_artifact_id"),
        "demo_verification_results",
        ["demo_edit_artifact_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_demo_verification_results_formal_job_attempt_id"),
        "demo_verification_results",
        ["formal_job_attempt_id"],
        unique=False,
    )
    op.drop_constraint(
        op.f("ck_demo_verification_results_output_sha_shape"),
        "demo_verification_results",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_verification_results_publication_shape"),
        "demo_verification_results",
        "(outcome = 'PASS' AND image_version_id IS NOT NULL "
        "AND output_asset_id IS NOT NULL "
        "AND output_asset_sha256 ~ '^[0-9a-f]{64}$') OR "
        "(outcome IN ('FAIL','HUMAN_REVIEW') AND image_version_id IS NULL "
        "AND output_asset_id IS NULL AND output_asset_sha256 IS NULL)",
    )

    op.create_table(
        "demo_edit_artifact_events",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("demo_edit_artifact_id", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("object_sha256", sa.String(length=64), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=64), nullable=True),
        sa.Column("engine_digest", sa.String(length=64), nullable=True),
        sa.Column("config_digest", sa.String(length=64), nullable=True),
        sa.Column("promoted_asset_id", sa.String(length=32), nullable=True),
        sa.Column("promoted_asset_variant_id", sa.String(length=32), nullable=True),
        sa.Column("verification_result_id", sa.String(length=32), nullable=True),
        sa.Column("image_version_id", sa.String(length=32), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        *_common_constraints("demo_edit_artifact_events"),
        sa.ForeignKeyConstraint(
            ["demo_edit_artifact_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_edit_artifacts.id",
                "demo_edit_artifacts.demo_actor_id",
                "demo_edit_artifacts.demo_session_id",
            ],
            name=op.f("fk_demo_edit_artifact_events_artifact_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["promoted_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_edit_artifact_events_promoted_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["promoted_asset_variant_id"],
            ["asset_variants.id"],
            name=op.f("fk_demo_edit_artifact_events_promoted_asset_variant_id_asset_variants"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verification_result_id"],
            ["demo_verification_results.id"],
            name=op.f(
                "fk_demo_edit_artifact_events_verification_result_id_demo_verification_results"
            ),
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["image_version_id"],
            ["demo_image_versions.id"],
            name=op.f("fk_demo_edit_artifact_events_image_version_id_demo_image_versions"),
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint(
            "demo_edit_artifact_id",
            "sequence",
            name=op.f("uq_demo_edit_artifact_events_artifact_sequence"),
        ),
        sa.UniqueConstraint(
            "demo_edit_artifact_id",
            "event_type",
            name=op.f("uq_demo_edit_artifact_events_artifact_type"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_edit_artifact_events_id_actor_session"),
        ),
        sa.CheckConstraint(
            "sequence > 0",
            name=op.f("ck_demo_edit_artifact_events_positive_sequence"),
        ),
        sa.CheckConstraint(
            "event_type IN ('MATERIALIZED','PROMOTED','REJECTED','CANCELLED','CLEANED')",
            name=op.f("ck_demo_edit_artifact_events_event_type"),
        ),
        sa.CheckConstraint(
            "(event_type = 'MATERIALIZED' AND object_sha256 ~ '^[0-9a-f]{64}$' "
            "AND byte_size > 0 AND width > 0 AND height > 0 "
            "AND mime_type IN ('image/jpeg','image/png') "
            "AND engine_digest ~ '^[0-9a-f]{64}$' "
            "AND config_digest ~ '^[0-9a-f]{64}$' "
            "AND promoted_asset_id IS NULL AND promoted_asset_variant_id IS NULL "
            "AND verification_result_id IS NULL AND image_version_id IS NULL "
            "AND reason_code IS NULL) OR "
            "(event_type = 'PROMOTED' AND object_sha256 IS NULL AND byte_size IS NULL "
            "AND width IS NULL AND height IS NULL AND mime_type IS NULL "
            "AND engine_digest IS NULL AND config_digest IS NULL "
            "AND promoted_asset_id IS NOT NULL AND promoted_asset_variant_id IS NOT NULL "
            "AND verification_result_id IS NOT NULL AND image_version_id IS NOT NULL "
            "AND reason_code IS NULL) OR "
            "(event_type = 'REJECTED' AND object_sha256 IS NULL AND byte_size IS NULL "
            "AND width IS NULL AND height IS NULL AND mime_type IS NULL "
            "AND engine_digest IS NULL AND config_digest IS NULL "
            "AND promoted_asset_id IS NULL AND promoted_asset_variant_id IS NULL "
            "AND verification_result_id IS NOT NULL AND image_version_id IS NULL "
            "AND reason_code IS NOT NULL) OR "
            "(event_type IN ('CANCELLED','CLEANED') AND object_sha256 IS NULL "
            "AND byte_size IS NULL AND width IS NULL AND height IS NULL "
            "AND mime_type IS NULL AND engine_digest IS NULL AND config_digest IS NULL "
            "AND promoted_asset_id IS NULL AND promoted_asset_variant_id IS NULL "
            "AND verification_result_id IS NULL AND image_version_id IS NULL "
            "AND reason_code IS NOT NULL)",
            name=op.f("ck_demo_edit_artifact_events_event_shape"),
        ),
    )
    for column_name in ("demo_actor_id", "demo_session_id", "demo_edit_artifact_id"):
        op.create_index(
            op.f(f"ix_demo_edit_artifact_events_{column_name}"),
            "demo_edit_artifact_events",
            [column_name],
            unique=False,
        )
    for column_name in (
        "promoted_asset_id",
        "promoted_asset_variant_id",
        "verification_result_id",
        "image_version_id",
    ):
        op.create_index(
            op.f(f"ix_demo_edit_artifact_events_{column_name}"),
            "demo_edit_artifact_events",
            [column_name],
            unique=True,
        )

    op.execute(_D07_VALIDATION_SQL)
    for table_name in ("demo_edit_artifacts", "demo_edit_artifact_events"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_demo_authority_{table_name} "
                f"BEFORE INSERT OR UPDATE OR DELETE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
            )
        )
    op.execute(
        "CREATE TRIGGER trg_demo_edit_artifact_validation "
        "BEFORE INSERT ON demo_edit_artifacts "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_edit_artifact()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_edit_artifact_event_validation "
        "BEFORE INSERT ON demo_edit_artifact_events "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_edit_artifact_event()"
    )
    op.execute("DROP TRIGGER trg_demo_references_demo_tool_runs ON demo_tool_runs")
    op.execute(
        "DROP TRIGGER trg_demo_references_demo_verification_results ON demo_verification_results"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_references_demo_tool_runs "
        "BEFORE INSERT ON demo_tool_runs "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d07_tool_run()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_references_demo_verification_results "
        "BEFORE INSERT ON demo_verification_results "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d07_verification()"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (SELECT 1 FROM demo_edit_artifacts)
               OR EXISTS (SELECT 1 FROM demo_edit_artifact_events) THEN
                RAISE EXCEPTION 'cannot downgrade populated D07 publication authority';
            END IF;
        END;
        $block$;
        """
    )
    op.execute(
        "DROP TRIGGER trg_demo_references_demo_verification_results ON demo_verification_results"
    )
    op.execute("DROP TRIGGER trg_demo_references_demo_tool_runs ON demo_tool_runs")
    op.execute(
        "CREATE TRIGGER trg_demo_references_demo_tool_runs "
        "BEFORE INSERT ON demo_tool_runs "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_references()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_references_demo_verification_results "
        "BEFORE INSERT ON demo_verification_results "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_references()"
    )
    op.execute("DROP TRIGGER trg_demo_edit_artifact_event_validation ON demo_edit_artifact_events")
    op.execute("DROP TRIGGER trg_demo_edit_artifact_validation ON demo_edit_artifacts")
    for table_name in ("demo_edit_artifact_events", "demo_edit_artifacts"):
        op.execute(f"DROP TRIGGER trg_demo_authority_{table_name} ON {table_name}")

    op.execute(_LEGACY_IMAGE_EXECUTION_SQL)
    op.execute("DROP FUNCTION mirror_demo_validate_d07_verification()")
    op.execute("DROP FUNCTION mirror_demo_validate_d07_tool_run()")
    op.execute("DROP FUNCTION mirror_demo_validate_edit_artifact_event()")
    op.execute("DROP FUNCTION mirror_demo_validate_edit_artifact()")

    op.drop_table("demo_edit_artifact_events")
    op.drop_constraint(
        op.f("ck_demo_verification_results_publication_shape"),
        "demo_verification_results",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_verification_results_output_sha_shape"),
        "demo_verification_results",
        "output_asset_sha256 ~ '^[0-9a-f]{64}$'",
    )
    op.drop_index(
        op.f("ix_demo_verification_results_formal_job_attempt_id"),
        table_name="demo_verification_results",
    )
    op.drop_index(
        op.f("ix_demo_verification_results_demo_edit_artifact_id"),
        table_name="demo_verification_results",
    )
    op.drop_constraint(
        op.f("fk_demo_verification_results_formal_job_attempt_id_job_attempts"),
        "demo_verification_results",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_demo_verification_results_demo_edit_artifact_id_demo_edit_artifacts"),
        "demo_verification_results",
        type_="foreignkey",
    )
    op.drop_column("demo_verification_results", "formal_job_attempt_id")
    op.drop_column("demo_verification_results", "demo_edit_artifact_id")
    op.alter_column(
        "demo_verification_results",
        "output_asset_sha256",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "demo_verification_results",
        "output_asset_id",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.alter_column(
        "demo_verification_results",
        "image_version_id",
        existing_type=sa.String(length=32),
        nullable=False,
    )

    op.drop_constraint(
        op.f("ck_demo_tool_runs_output_shape"),
        "demo_tool_runs",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_tool_runs_output_shape"),
        "demo_tool_runs",
        "(output_asset_id IS NULL AND output_asset_sha256 IS NULL) OR "
        "(output_asset_id IS NOT NULL AND output_asset_sha256 ~ '^[0-9a-f]{64}$')",
    )
    op.create_check_constraint(
        op.f("ck_demo_tool_runs_outcome_result_shape"),
        "demo_tool_runs",
        "(outcome = 'COMPLETED' AND output_asset_id IS NOT NULL) OR "
        "(outcome <> 'COMPLETED' AND output_asset_id IS NULL)",
    )
    op.drop_index(
        op.f("ix_demo_tool_runs_demo_edit_artifact_id"),
        table_name="demo_tool_runs",
    )
    op.drop_constraint(
        op.f("fk_demo_tool_runs_demo_edit_artifact_id_demo_edit_artifacts"),
        "demo_tool_runs",
        type_="foreignkey",
    )
    op.drop_column("demo_tool_runs", "demo_edit_artifact_id")
    op.drop_table("demo_edit_artifacts")
