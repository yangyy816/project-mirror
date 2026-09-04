"""Admit the immutable D06 stepped self-transfer authority version.

Revision ID: demo_0019_d06_stepped_transfer
Revises: demo_0018_d03_pose_evidence
Create Date: 2026-09-04

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
FORWARD_REPAIR_ONLY: TRUE
"""

from collections.abc import Sequence

from alembic import op

revision: str = "demo_0019_d06_stepped_transfer"
down_revision: str | None = "demo_0018_d03_pose_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
FORWARD_REPAIR_ONLY = True

_CONSTRAINT_NAME = "ck_demo_self_transfer_runs_schema_version_shape"
_V1_SCHEMA_VERSION = "mirror.demo/DemoSelfTransferRun/v1"
_V2_SCHEMA_VERSION = "mirror.demo/DemoSelfTransferRun/v2"
_V1_ONLY_EXPRESSION = "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'"
_V1_V2_EXPRESSION = f"schema_version IN ('{_V1_SCHEMA_VERSION}','{_V2_SCHEMA_VERSION}')"


def upgrade() -> None:
    op.drop_constraint(
        op.f(_CONSTRAINT_NAME),
        "demo_self_transfer_runs",
        type_="check",
    )
    op.create_check_constraint(
        op.f(_CONSTRAINT_NAME),
        "demo_self_transfer_runs",
        _V1_V2_EXPRESSION,
    )


def downgrade() -> None:
    # Immutable v2 authority cannot be destructively rewritten for a rollback.
    # This guard runs before the constraint DDL, so a populated downgrade fails
    # atomically and leaves the v1/v2 closed set in place.
    op.execute(
        """
DO $block$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM demo_self_transfer_runs
        WHERE schema_version = 'mirror.demo/DemoSelfTransferRun/v2'
    ) THEN
        RAISE EXCEPTION 'D06 stepped-transfer downgrade blocked by populated v2 authority';
    END IF;
END;
$block$;
"""
    )
    op.drop_constraint(
        op.f(_CONSTRAINT_NAME),
        "demo_self_transfer_runs",
        type_="check",
    )
    op.create_check_constraint(
        op.f(_CONSTRAINT_NAME),
        "demo_self_transfer_runs",
        _V1_ONLY_EXPRESSION,
    )
