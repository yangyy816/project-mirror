"""Add truthful versioned D03 repeat pose evidence.

Revision ID: demo_0018_d03_pose_evidence
Revises: demo_0017_d10_context_queue
Create Date: 2026-09-03

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
FORWARD_REPAIR_ONLY: TRUE
"""

from collections.abc import Sequence

from alembic import op

revision: str = "demo_0018_d03_pose_evidence"
down_revision: str | None = "demo_0017_d10_context_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
FORWARD_REPAIR_ONLY = True


_PREDECESSOR_GUARD_SQL = """
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM demo_face_observations observation_row
        JOIN demo_face_observation_repeats repeat_row
          ON repeat_row.observation_id = observation_row.id
         AND repeat_row.demo_actor_id = observation_row.demo_actor_id
         AND repeat_row.demo_session_id = observation_row.demo_session_id
        WHERE observation_row.schema_version = 'mirror.demo/DemoFaceObservation/v2'
          AND repeat_row.schema_version = 'mirror.demo/DemoFaceObservationRepeat/v1'
    ) THEN
        RAISE EXCEPTION
            'D03 pose-v2 upgrade blocked by populated v2 Observation/v1 Repeat predecessor graph';
    END IF;
END;
$block$;
"""


_POSE_VALIDATOR_SQL = r"""
CREATE FUNCTION mirror_demo_validate_d03_pose_repeat_version()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    observation_schema text;
BEGIN
    IF TG_TABLE_NAME = 'demo_face_observation_repeats' THEN
        SELECT schema_version INTO observation_schema
        FROM demo_face_observations
        WHERE id = NEW.observation_id
          AND demo_actor_id = NEW.demo_actor_id
          AND demo_session_id = NEW.demo_session_id;
        IF NOT FOUND OR NOT (
            (observation_schema = 'mirror.demo/DemoFaceObservation/v1'
             AND NEW.schema_version = 'mirror.demo/DemoFaceObservationRepeat/v1')
            OR
            (observation_schema = 'mirror.demo/DemoFaceObservation/v2'
             AND NEW.schema_version = 'mirror.demo/DemoFaceObservationRepeat/v2')
        ) THEN
            RAISE EXCEPTION 'D03 Observation and Repeat schema versions must match';
        END IF;
    ELSE
        IF EXISTS (
            SELECT 1
            FROM demo_face_observation_repeats repeat_row
            WHERE repeat_row.observation_id = NEW.id
              AND repeat_row.demo_actor_id = NEW.demo_actor_id
              AND repeat_row.demo_session_id = NEW.demo_session_id
              AND NOT (
                  (NEW.schema_version = 'mirror.demo/DemoFaceObservation/v1'
                   AND repeat_row.schema_version = 'mirror.demo/DemoFaceObservationRepeat/v1')
                  OR
                  (NEW.schema_version = 'mirror.demo/DemoFaceObservation/v2'
                   AND repeat_row.schema_version = 'mirror.demo/DemoFaceObservationRepeat/v2')
              )
        ) THEN
            RAISE EXCEPTION 'D03 Observation and Repeat schema versions must match';
        END IF;
    END IF;
    RETURN NULL;
END;
$function$;
"""


_POSE_V2_CHECK_SQL = """
schema_version = 'mirror.demo/DemoFaceObservationRepeat/v1' OR
(
    ((pose - ARRAY['state','reason']) = '{}'::jsonb
     AND pose ? 'state' AND pose ? 'reason'
     AND pose ->> 'state' = 'UNAVAILABLE'
     AND pose ->> 'reason' = 'M3_RUNTIME_DOES_NOT_EMIT_POSE')
    OR
    ((pose - ARRAY['state','yaw_ppm','pitch_ppm','roll_ppm']) = '{}'::jsonb
     AND pose ? 'state' AND pose ? 'yaw_ppm'
     AND pose ? 'pitch_ppm' AND pose ? 'roll_ppm'
     AND pose ->> 'state' = 'SUPPORTED'
     AND jsonb_typeof(pose -> 'yaw_ppm') = 'number'
     AND jsonb_typeof(pose -> 'pitch_ppm') = 'number'
     AND jsonb_typeof(pose -> 'roll_ppm') = 'number'
     AND pose ->> 'yaw_ppm' ~ '^-?(0|[1-9][0-9]*)$'
     AND pose ->> 'pitch_ppm' ~ '^-?(0|[1-9][0-9]*)$'
     AND pose ->> 'roll_ppm' ~ '^-?(0|[1-9][0-9]*)$'
     AND (pose ->> 'yaw_ppm')::numeric BETWEEN -1000000 AND 1000000
     AND (pose ->> 'pitch_ppm')::numeric BETWEEN -1000000 AND 1000000
     AND (pose ->> 'roll_ppm')::numeric BETWEEN -1000000 AND 1000000)
)
"""


def upgrade() -> None:
    # This must be first: predecessor data is immutable and cannot be rewritten.
    op.execute(_PREDECESSOR_GUARD_SQL)
    op.drop_constraint(
        op.f("ck_demo_face_observation_repeats_schema_version_shape"),
        "demo_face_observation_repeats",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_face_observation_repeats_schema_version_shape"),
        "demo_face_observation_repeats",
        "schema_version IN ('mirror.demo/DemoFaceObservationRepeat/v1',"
        "'mirror.demo/DemoFaceObservationRepeat/v2')",
    )
    op.create_check_constraint(
        op.f("ck_demo_face_observation_repeats_pose_v2_exact_union"),
        "demo_face_observation_repeats",
        _POSE_V2_CHECK_SQL,
    )
    op.execute(_POSE_VALIDATOR_SQL)
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d03_pose_repeat_version "
        "AFTER INSERT ON demo_face_observation_repeats DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d03_pose_repeat_version()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_d03_pose_observation_version "
        "AFTER INSERT ON demo_face_observations DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_d03_pose_repeat_version()"
    )


def downgrade() -> None:
    op.execute(
        """
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1 FROM demo_face_observation_repeats
        WHERE schema_version = 'mirror.demo/DemoFaceObservationRepeat/v2'
    ) THEN
        RAISE EXCEPTION 'D03 pose-v2 downgrade blocked by populated v2 Repeat authority';
    END IF;
END;
$block$;
"""
    )
    op.execute("DROP TRIGGER trg_demo_d03_pose_observation_version ON demo_face_observations")
    op.execute("DROP TRIGGER trg_demo_d03_pose_repeat_version ON demo_face_observation_repeats")
    op.execute("DROP FUNCTION mirror_demo_validate_d03_pose_repeat_version()")
    op.drop_constraint(
        op.f("ck_demo_face_observation_repeats_pose_v2_exact_union"),
        "demo_face_observation_repeats",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_demo_face_observation_repeats_schema_version_shape"),
        "demo_face_observation_repeats",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_demo_face_observation_repeats_schema_version_shape"),
        "demo_face_observation_repeats",
        "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
    )
