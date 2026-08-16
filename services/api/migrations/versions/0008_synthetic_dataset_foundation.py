"""Add synthetic dataset authority foundations.

Revision ID: 0008_synth_dataset_foundation
Revises: 0007_account_quarantine_evidence
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_synth_dataset_foundation"
down_revision: str | None = "0007_account_quarantine_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUTHORITY_TABLES = (
    "synthetic_generation_policies",
    "synthetic_prompt_templates",
    "synthetic_qa_policies",
    "geometry_ontology_versions",
)
_AUTHORITY_SCHEMA_VERSIONS = {
    "synthetic_generation_policies": "mirror.synthetic-dataset/SyntheticGenerationPolicy/v1",
    "synthetic_prompt_templates": "mirror.synthetic-dataset/SyntheticPromptTemplate/v1",
    "synthetic_qa_policies": "mirror.synthetic-dataset/SyntheticQAPolicy/v1",
    "geometry_ontology_versions": "mirror.synthetic-dataset/GeometryOntologyVersion/v1",
}


def _assert_no_existing_p2_rows() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM synthetic_identities)
               OR EXISTS (SELECT 1 FROM assets WHERE asset_role = 'synthetic') THEN
                RAISE EXCEPTION
                    '0008 requires Principal review before migrating existing P2 synthetic rows';
            END IF;
        END;
        $$;
        """
    )


def _create_authority_table(table_name: str, schema_version: str) -> None:
    op.create_table(
        table_name,
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=48), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("approval_status", sa.String(length=24), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "approval_status IN ('DRAFT','APPROVED')",
            name=op.f(f"ck_{table_name}_approval_status"),
        ),
        sa.CheckConstraint(
            "(approval_status = 'DRAFT' AND approved_at IS NULL) OR "
            "(approval_status = 'APPROVED' AND approved_at IS NOT NULL)",
            name=op.f(f"ck_{table_name}_approval_shape"),
        ),
        sa.CheckConstraint(
            "version ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'",
            name=op.f(f"ck_{table_name}_canonical_version"),
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{table_name}_canonical_digest"),
        ),
        sa.CheckConstraint(
            f"schema_version = '{schema_version}'",
            name=op.f(f"ck_{table_name}_schema_version"),
        ),
        sa.CheckConstraint(
            "json_typeof(content) = 'object'",
            name=op.f(f"ck_{table_name}_content_object"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
        sa.UniqueConstraint("version", name=op.f(f"uq_{table_name}_version")),
        sa.UniqueConstraint("content_digest", name=op.f(f"uq_{table_name}_content_digest")),
    )


def _install_synthetic_authority_protection() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_validate_synthetic_authority_record() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.approval_status <> 'DRAFT' OR NEW.approved_at IS NOT NULL THEN
                    RAISE EXCEPTION 'synthetic authority records must be inserted as DRAFT';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.schema_version IS DISTINCT FROM NEW.schema_version
               OR OLD.version IS DISTINCT FROM NEW.version
               OR to_jsonb(OLD.content) IS DISTINCT FROM to_jsonb(NEW.content)
               OR OLD.content_digest IS DISTINCT FROM NEW.content_digest THEN
                RAISE EXCEPTION 'synthetic authority content is immutable';
            END IF;
            IF OLD.id IS DISTINCT FROM NEW.id
               OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
                RAISE EXCEPTION 'synthetic authority record identity is immutable';
            END IF;
            IF OLD.approval_status = 'APPROVED' THEN
                RAISE EXCEPTION 'synthetic authority approval is immutable once approved';
            END IF;
            IF OLD.approval_status <> 'DRAFT' OR NEW.approval_status <> 'APPROVED'
               OR NEW.approved_at IS NULL THEN
                RAISE EXCEPTION 'synthetic authority approval must transition to approved';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table_name in _AUTHORITY_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_authority "
            f"BEFORE INSERT OR UPDATE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION mirror_validate_synthetic_authority_record();"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_immutable "
            f"BEFORE DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();"
        )


def _install_asset_blob_protection() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_protect_original_asset() RETURNS trigger AS $$
        BEGIN
            IF OLD.asset_role IS DISTINCT FROM NEW.asset_role
               AND (OLD.asset_role = 'synthetic' OR NEW.asset_role = 'synthetic') THEN
                RAISE EXCEPTION 'synthetic asset role is immutable';
            END IF;
            IF OLD.asset_role = 'original' AND (
                NEW.asset_role IS DISTINCT FROM OLD.asset_role OR
                NEW.storage_key IS DISTINCT FROM OLD.storage_key OR
                NEW.sha256 IS DISTINCT FROM OLD.sha256 OR
                NEW.byte_size IS DISTINCT FROM OLD.byte_size OR
                NEW.width IS DISTINCT FROM OLD.width OR
                NEW.height IS DISTINCT FROM OLD.height OR
                NEW.mime_type IS DISTINCT FROM OLD.mime_type OR
                NEW.is_ai_generated IS DISTINCT FROM OLD.is_ai_generated OR
                NEW.is_ai_modified IS DISTINCT FROM OLD.is_ai_modified
            ) THEN
                RAISE EXCEPTION 'original asset blob metadata is immutable';
            END IF;
            IF OLD.asset_role = 'synthetic' AND (
                NEW.asset_role IS DISTINCT FROM OLD.asset_role OR
                NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id OR
                NEW.internal_purpose IS DISTINCT FROM OLD.internal_purpose OR
                NEW.storage_key IS DISTINCT FROM OLD.storage_key OR
                NEW.sha256 IS DISTINCT FROM OLD.sha256 OR
                NEW.byte_size IS DISTINCT FROM OLD.byte_size OR
                NEW.width IS DISTINCT FROM OLD.width OR
                NEW.height IS DISTINCT FROM OLD.height OR
                NEW.mime_type IS DISTINCT FROM OLD.mime_type OR
                NEW.synthetic IS DISTINCT FROM OLD.synthetic OR
                NEW.is_ai_generated IS DISTINCT FROM OLD.is_ai_generated OR
                NEW.is_ai_modified IS DISTINCT FROM OLD.is_ai_modified
            ) THEN
                RAISE EXCEPTION 'synthetic asset blob metadata is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def _restore_original_asset_blob_protection() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_protect_original_asset() RETURNS trigger AS $$
        BEGIN
            IF OLD.asset_role = 'original' AND (
                NEW.asset_role IS DISTINCT FROM OLD.asset_role OR
                NEW.storage_key IS DISTINCT FROM OLD.storage_key OR
                NEW.sha256 IS DISTINCT FROM OLD.sha256 OR
                NEW.byte_size IS DISTINCT FROM OLD.byte_size OR
                NEW.width IS DISTINCT FROM OLD.width OR
                NEW.height IS DISTINCT FROM OLD.height OR
                NEW.mime_type IS DISTINCT FROM OLD.mime_type OR
                NEW.is_ai_generated IS DISTINCT FROM OLD.is_ai_generated OR
                NEW.is_ai_modified IS DISTINCT FROM OLD.is_ai_modified
            ) THEN
                RAISE EXCEPTION 'original asset blob metadata is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def upgrade() -> None:
    _assert_no_existing_p2_rows()
    for table_name in _AUTHORITY_TABLES:
        _create_authority_table(table_name, _AUTHORITY_SCHEMA_VERSIONS[table_name])
    _install_synthetic_authority_protection()

    op.alter_column(
        "synthetic_identities",
        "bank_version_id",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.create_check_constraint(
        op.f("ck_synthetic_identities_bank_independent"),
        "synthetic_identities",
        "bank_version_id IS NULL",
    )
    op.add_column("assets", sa.Column("internal_purpose", sa.String(length=64), nullable=True))
    op.create_check_constraint(
        op.f("ck_assets_valid_asset_internal_purpose_shape"),
        "assets",
        "(asset_role = 'synthetic' AND owner_user_id IS NULL "
        "AND internal_purpose = 'synthetic_dataset' AND synthetic) OR "
        "(asset_role IN ('original','derived') AND internal_purpose IS NULL)",
    )
    _install_asset_blob_protection()


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM synthetic_generation_policies)
               OR EXISTS (SELECT 1 FROM synthetic_prompt_templates)
               OR EXISTS (SELECT 1 FROM synthetic_qa_policies)
               OR EXISTS (SELECT 1 FROM geometry_ontology_versions)
               OR EXISTS (SELECT 1 FROM synthetic_identities WHERE bank_version_id IS NULL)
               OR EXISTS (SELECT 1 FROM assets WHERE asset_role = 'synthetic') THEN
                RAISE EXCEPTION '0008 downgrade would discard P2 synthetic authority or data';
            END IF;
        END;
        $$;
        """
    )
    op.drop_constraint(
        op.f("ck_assets_valid_asset_internal_purpose_shape"), "assets", type_="check"
    )
    op.drop_column("assets", "internal_purpose")
    _restore_original_asset_blob_protection()
    op.drop_constraint(
        op.f("ck_synthetic_identities_bank_independent"),
        "synthetic_identities",
        type_="check",
    )
    op.alter_column(
        "synthetic_identities",
        "bank_version_id",
        existing_type=sa.String(length=32),
        nullable=False,
    )

    for table_name in _AUTHORITY_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON {table_name}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_authority ON {table_name}")
        op.drop_table(table_name)
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_synthetic_authority_record()")
