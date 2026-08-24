"""Close Demo D02 private-execution admission authority gaps.

Revision ID: demo_0006_d02_private_exec
Revises: demo_0005_d02_quality_auth
Create Date: 2026-08-25

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

from alembic import op

revision: str = "demo_0006_d02_private_exec"
down_revision: str | None = "demo_0005_d02_quality_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"

_LOCK_SQL = "LOCK TABLE demo_synthetic_identities IN ACCESS EXCLUSIVE MODE;"

_UPGRADE_AUDIT_SQL = """
DO $audit$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM demo_synthetic_identities
        WHERE schema_version = 'mirror.demo/DemoSyntheticIdentity/v3'
          AND source_output_id IS NOT NULL
          AND admission_config_digest <>
              'ef87c397af7db78211a6d2440f0cb3eef4214080f5117ff7be89b6400b663b21'
    ) THEN
        RAISE EXCEPTION
            'D02 private-execution admission authority audit failed: local v3 config mismatch';
    END IF;
END
$audit$;
"""

_DOWNGRADE_PREFLIGHT_SQL = """
DO $preflight$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM demo_synthetic_identities
        WHERE schema_version = 'mirror.demo/DemoSyntheticIdentity/v3'
          AND source_output_id IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Cannot downgrade populated D02 v3 identity authority';
    END IF;
END
$preflight$;
"""


def upgrade() -> None:
    op.execute(_LOCK_SQL)
    op.execute(_UPGRADE_AUDIT_SQL)
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_d02_local_admission_config_exact"),
        "demo_synthetic_identities",
        "schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3' "
        "OR source_output_id IS NULL "
        "OR admission_config_digest = "
        "'ef87c397af7db78211a6d2440f0cb3eef4214080f5117ff7be89b6400b663b21'",
    )


def downgrade() -> None:
    op.execute(_LOCK_SQL)
    op.execute(_DOWNGRADE_PREFLIGHT_SQL)
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_d02_local_admission_config_exact"),
        "demo_synthetic_identities",
        type_="check",
    )
