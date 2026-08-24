"""Harden Demo accepted-episode provenance authority.

Revision ID: demo_0004_d09_episode_prov
Revises: demo_0003_d02_import_auth
Create Date: 2026-08-24

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

from alembic import op

revision: str = "demo_0004_d09_episode_prov"
down_revision: str | None = "demo_0003_d02_import_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"


_EPISODE_TABLE_LOCK_SQL = "LOCK TABLE demo_accepted_visual_episodes IN ACCESS EXCLUSIVE MODE"


_LEGACY_ACCEPTED_EPISODE_VALIDATOR_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_accepted_episode()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_trajectory jsonb;
    trajectory_count integer;
    terminal_sequence integer;
    trajectory_image_id text;
BEGIN
    PERFORM mirror_demo_require_asset(NEW.source_asset_id, NEW.source_asset_sha256);
    PERFORM mirror_demo_require_asset(NEW.final_asset_id, NEW.final_asset_sha256);
    IF jsonb_array_length(NEW.trajectory_digests) = 0 OR EXISTS (
        SELECT 1
        FROM jsonb_array_elements(NEW.trajectory_digests) AS digest_entry(value)
        WHERE jsonb_typeof(digest_entry.value) <> 'string'
           OR digest_entry.value #>> '{}' !~ '^[0-9a-f]{64}$'
    ) THEN
        RAISE EXCEPTION 'Demo accepted episode trajectory digest list is invalid';
    END IF;
    WITH RECURSIVE image_chain AS (
        SELECT
            image_row.id,
            image_row.parent_version_id,
            image_row.sequence,
            image_row.content_digest
        FROM demo_image_versions image_row
        WHERE image_row.id = NEW.accepted_image_version_id
          AND image_row.demo_actor_id = NEW.demo_actor_id
          AND image_row.demo_session_id = NEW.demo_session_id
          AND image_row.editing_session_id = NEW.editing_session_id

        UNION ALL

        SELECT
            parent_row.id,
            parent_row.parent_version_id,
            parent_row.sequence,
            parent_row.content_digest
        FROM demo_image_versions parent_row
        JOIN image_chain child_row
          ON child_row.parent_version_id = parent_row.id
        WHERE parent_row.demo_actor_id = NEW.demo_actor_id
          AND parent_row.demo_session_id = NEW.demo_session_id
          AND parent_row.editing_session_id = NEW.editing_session_id
          AND parent_row.sequence = child_row.sequence - 1
    )
    SELECT
        jsonb_agg(image_chain.content_digest ORDER BY image_chain.sequence),
        count(*)::integer,
        max(image_chain.sequence)::integer
    INTO expected_trajectory, trajectory_count, terminal_sequence
    FROM image_chain;
    IF trajectory_count = 0
        OR terminal_sequence <> trajectory_count - 1
        OR expected_trajectory IS DISTINCT FROM NEW.trajectory_digests THEN
        RAISE EXCEPTION 'Demo accepted episode trajectory lineage mismatch';
    END IF;

    FOR trajectory_image_id IN
        WITH RECURSIVE image_chain AS (
            SELECT image_row.id, image_row.parent_version_id, image_row.sequence
            FROM demo_image_versions image_row
            WHERE image_row.id = NEW.accepted_image_version_id

            UNION ALL

            SELECT parent_row.id, parent_row.parent_version_id, parent_row.sequence
            FROM demo_image_versions parent_row
            JOIN image_chain child_row ON child_row.parent_version_id = parent_row.id
        )
        SELECT image_chain.id FROM image_chain ORDER BY image_chain.sequence
    LOOP
        PERFORM mirror_demo_require_image_execution_binding(trajectory_image_id);
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM demo_image_versions image_row
        JOIN demo_editing_sessions editing_row
          ON editing_row.id = image_row.editing_session_id
        JOIN demo_edit_plans plan_row
          ON plan_row.content_digest = image_row.plan_digest
        JOIN demo_tool_runs tool_row
          ON tool_row.content_digest = image_row.tool_run_digest
        JOIN demo_edit_operations operation_row
          ON operation_row.id = tool_row.edit_operation_id
         AND operation_row.content_digest = tool_row.edit_operation_digest
         AND operation_row.edit_plan_id = plan_row.id
        JOIN demo_verification_results verification_row
          ON verification_row.id = NEW.verification_result_id
        JOIN demo_preference_events event_row
          ON event_row.id = NEW.acceptance_event_id
        WHERE image_row.id = NEW.accepted_image_version_id
          AND image_row.demo_actor_id = NEW.demo_actor_id
          AND image_row.demo_session_id = NEW.demo_session_id
          AND image_row.editing_session_id = NEW.editing_session_id
          AND image_row.result_asset_id = NEW.final_asset_id
          AND image_row.result_asset_sha256 = NEW.final_asset_sha256
          AND image_row.version_kind IN ('EDITED','RESTORED','ROLLED_BACK')
          AND editing_row.source_asset_id = NEW.source_asset_id
          AND editing_row.source_asset_sha256 = NEW.source_asset_sha256
          AND plan_row.record_kind = 'RESULT'
          AND operation_row.operation_index = jsonb_array_length(plan_row.operation_specs) - 1
          AND verification_row.demo_actor_id = NEW.demo_actor_id
          AND verification_row.demo_session_id = NEW.demo_session_id
          AND verification_row.image_version_id = image_row.id
          AND verification_row.tool_run_id = tool_row.id
          AND verification_row.content_digest = image_row.verifier_digest
          AND verification_row.output_asset_id = NEW.final_asset_id
          AND verification_row.output_asset_sha256 = NEW.final_asset_sha256
          AND verification_row.outcome = 'PASS'
          AND event_row.demo_actor_id = NEW.demo_actor_id
          AND event_row.demo_session_id = NEW.demo_session_id
          AND event_row.event_type = 'IMAGE_ACCEPTED'
          AND event_row.source_type IN ('EXPLICIT_USER_ACTION', 'EDIT_FEEDBACK')
          AND event_row.target_type = 'IMAGE_VERSION'
          AND event_row.target_id = image_row.id
    ) THEN
        RAISE EXCEPTION 'Only verified user-accepted Demo image versions may become episodes';
    END IF;
    RETURN NEW;
END;
$function$;
"""


_LEGACY_PROVENANCE_ANCHOR = "          AND plan_row.record_kind = 'RESULT'\n"
_HARDENED_PROVENANCE_PREDICATES = r"""          AND plan_row.record_kind = 'RESULT'
          AND editing_row.demo_actor_id = NEW.demo_actor_id
          AND editing_row.demo_session_id = NEW.demo_session_id
          AND plan_row.demo_actor_id = NEW.demo_actor_id
          AND plan_row.demo_session_id = NEW.demo_session_id
          AND plan_row.editing_session_id = NEW.editing_session_id
          AND NEW.profile_digest = editing_row.desired_delta_profile_digest
          AND NEW.profile_digest = plan_row.desired_delta_profile_digest
          AND NEW.context_digest = editing_row.context_digest
          AND NEW.instruction_digest = editing_row.instruction_digest
          AND NEW.instruction_digest = plan_row.instruction_digest
"""

if _LEGACY_ACCEPTED_EPISODE_VALIDATOR_SQL.count(_LEGACY_PROVENANCE_ANCHOR) != 1:
    raise RuntimeError("Frozen accepted-episode validator anchor is not unique")

_HARDENED_ACCEPTED_EPISODE_VALIDATOR_SQL = _LEGACY_ACCEPTED_EPISODE_VALIDATOR_SQL.replace(
    _LEGACY_PROVENANCE_ANCHOR,
    _HARDENED_PROVENANCE_PREDICATES,
)


_UPGRADE_EXISTING_EPISODE_AUDIT_SQL = r"""
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM demo_accepted_visual_episodes episode_row
        WHERE NOT EXISTS (
            SELECT 1
            FROM demo_image_versions image_row
            JOIN demo_editing_sessions editing_row
              ON editing_row.id = image_row.editing_session_id
            JOIN demo_edit_plans plan_row
              ON plan_row.content_digest = image_row.plan_digest
            WHERE image_row.id = episode_row.accepted_image_version_id
              AND image_row.demo_actor_id = episode_row.demo_actor_id
              AND image_row.demo_session_id = episode_row.demo_session_id
              AND image_row.editing_session_id = episode_row.editing_session_id
              AND editing_row.demo_actor_id = episode_row.demo_actor_id
              AND editing_row.demo_session_id = episode_row.demo_session_id
              AND plan_row.demo_actor_id = episode_row.demo_actor_id
              AND plan_row.demo_session_id = episode_row.demo_session_id
              AND plan_row.editing_session_id = episode_row.editing_session_id
              AND plan_row.record_kind = 'RESULT'
              AND episode_row.profile_digest =
                  editing_row.desired_delta_profile_digest
              AND episode_row.profile_digest =
                  plan_row.desired_delta_profile_digest
              AND episode_row.context_digest = editing_row.context_digest
              AND episode_row.instruction_digest = editing_row.instruction_digest
              AND episode_row.instruction_digest = plan_row.instruction_digest
        )
    ) THEN
        RAISE EXCEPTION
            'Demo accepted episode provenance audit failed; evidence disposition required';
    END IF;
END;
$block$;
"""


_DOWNGRADE_EMPTY_EPISODE_PREFLIGHT_SQL = r"""
DO $block$
BEGIN
    IF EXISTS (SELECT 1 FROM demo_accepted_visual_episodes LIMIT 1) THEN
        RAISE EXCEPTION
            'Demo accepted episode provenance downgrade blocked by existing evidence';
    END IF;
END;
$block$;
"""


def upgrade() -> None:
    op.execute(_EPISODE_TABLE_LOCK_SQL)
    op.execute(_UPGRADE_EXISTING_EPISODE_AUDIT_SQL)
    op.execute(_HARDENED_ACCEPTED_EPISODE_VALIDATOR_SQL)


def downgrade() -> None:
    op.execute(_EPISODE_TABLE_LOCK_SQL)
    op.execute(_DOWNGRADE_EMPTY_EPISODE_PREFLIGHT_SQL)
    op.execute(_LEGACY_ACCEPTED_EPISODE_VALIDATOR_SQL)
