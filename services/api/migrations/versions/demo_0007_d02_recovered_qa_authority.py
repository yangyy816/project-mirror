"""Add recovered legacy QA typed-digest authority.

Revision ID: demo_0007_d02_recovered_qa
Revises: demo_0006_d02_private_exec
Create Date: 2026-08-25

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

# ruff: noqa: S608 -- all interpolated predicates are frozen module literals

from collections.abc import Sequence

from alembic import op

revision: str = "demo_0007_d02_recovered_qa"
down_revision: str | None = "demo_0006_d02_private_exec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"

_LOCK_SQL = "LOCK TABLE demo_synthetic_identities IN ACCESS EXCLUSIVE MODE;"

_D02_LOCAL_QA_DIGEST_SEPARATION_INNER_SQL = """(
    source_qa_snapshot_digest IS NOT NULL
    AND jsonb_typeof(source_fact_snapshot) IS NOT DISTINCT FROM 'object'
    AND (source_fact_snapshot ->> 'source_qa_snapshot_digest')
        IS NOT DISTINCT FROM source_qa_snapshot_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM formal_canonical_asset_sha256
    AND source_qa_snapshot_digest IS DISTINCT FROM source_receipt_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_authority_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_landmark_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_measurement_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_provenance_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_fact_snapshot_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_measurement_projection_digest
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_asset_sha256')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_receipt_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_authority_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'qa_policy_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_landmark_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_provenance_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_projection_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'raw_measurement_authority_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_observation_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_repeat_certification_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'source_p2_candidate_manifest_content_digest'
        )
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'dimension_authority_manifest_content_digest'
        )
)"""

_D02_LOCAL_QA_DIGEST_SEPARATION_CHECK_SQL = f"""
schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3'
OR source_authority_kind <> 'DEMO_LOCAL_IMPORTED_COPY'
OR {_D02_LOCAL_QA_DIGEST_SEPARATION_INNER_SQL}
"""

_UPGRADE_AUDIT_SQL = f"""
DO $audit$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM demo_synthetic_identities
        WHERE schema_version = 'mirror.demo/DemoSyntheticIdentity/v3'
          AND source_authority_kind = 'DEMO_LOCAL_IMPORTED_COPY'
          AND NOT {_D02_LOCAL_QA_DIGEST_SEPARATION_INNER_SQL}
        LIMIT 1
    ) THEN
        RAISE EXCEPTION
            'D02 recovered QA typed-digest separation audit failed';
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
          AND source_authority_kind = 'DEMO_LOCAL_IMPORTED_COPY'
    ) THEN
        RAISE EXCEPTION 'Cannot downgrade populated D02 recovered QA authority';
    END IF;
END
$preflight$;
"""


def upgrade() -> None:
    op.execute(_LOCK_SQL)
    op.execute(_UPGRADE_AUDIT_SQL)
    op.create_check_constraint(
        op.f("ck_demo_synthetic_identities_d02_local_qa_digest_separation"),
        "demo_synthetic_identities",
        _D02_LOCAL_QA_DIGEST_SEPARATION_CHECK_SQL,
    )


def downgrade() -> None:
    op.execute(_LOCK_SQL)
    op.execute(_DOWNGRADE_PREFLIGHT_SQL)
    op.drop_constraint(
        op.f("ck_demo_synthetic_identities_d02_local_qa_digest_separation"),
        "demo_synthetic_identities",
        type_="check",
    )
