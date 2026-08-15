"""Add owner-bound targets for dependency-aware object deletion evidence.

Revision ID: 0006_deletion_evidence_targets
Revises: 0005_data_rights_lifecycle
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_deletion_evidence_targets"
down_revision: str | None = "0005_data_rights_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _install_target_authority_function() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_object_deletion_evidence()
        RETURNS trigger AS $$
        DECLARE
            authority_owner varchar(32);
            authority_asset varchar(32);
            target_owner varchar(32);
            target_deleted_at timestamptz;
            reachable boolean;
        BEGIN
            IF NEW.object_kind = 'asset' THEN
                SELECT owner_user_id, deleted_at INTO target_owner, target_deleted_at FROM assets
                WHERE id = NEW.target_asset_id FOR KEY SHARE;
                IF target_deleted_at IS NULL THEN
                    RAISE EXCEPTION 'asset deletion evidence requires target tombstone';
                END IF;
            ELSE
                SELECT owner_user_id INTO target_owner FROM data_export_requests
                WHERE id = NEW.target_data_export_request_id FOR KEY SHARE;
            END IF;

            IF NEW.asset_deletion_request_id IS NOT NULL THEN
                SELECT owner_user_id, asset_id INTO authority_owner, authority_asset
                FROM asset_deletion_requests
                WHERE id = NEW.asset_deletion_request_id FOR KEY SHARE;
                IF NEW.object_kind <> 'asset' THEN
                    RAISE EXCEPTION 'asset deletion evidence requires asset object kind';
                END IF;
                WITH RECURSIVE dependency(id) AS (
                    SELECT authority_asset
                    UNION
                    SELECT variants.result_asset_id
                    FROM asset_variants variants
                    JOIN dependency parent ON variants.source_asset_id = parent.id
                )
                SELECT EXISTS(
                    SELECT 1 FROM dependency WHERE id = NEW.target_asset_id
                ) INTO reachable;
                IF NOT reachable THEN
                    RAISE EXCEPTION 'asset deletion evidence target is outside dependency graph';
                END IF;
            ELSIF NEW.data_export_request_id IS NOT NULL THEN
                SELECT owner_user_id INTO authority_owner FROM data_export_requests
                WHERE id = NEW.data_export_request_id FOR KEY SHARE;
                IF NEW.object_kind <> 'data_export'
                   OR NEW.target_data_export_request_id <> NEW.data_export_request_id THEN
                    RAISE EXCEPTION 'export deletion evidence requires its authoritative export target';
                END IF;
            ELSE
                SELECT owner_user_id INTO authority_owner FROM account_deletion_requests
                WHERE id = NEW.account_deletion_request_id FOR KEY SHARE;
            END IF;

            IF authority_owner IS NULL OR target_owner IS NULL
               OR authority_owner <> NEW.owner_user_id
               OR target_owner <> NEW.owner_user_id THEN
                RAISE EXCEPTION 'object deletion evidence owner must match authority and target';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def upgrade() -> None:
    op.drop_constraint(
        op.f("uq_object_deletion_evidence_asset_deletion_request_id"),
        "object_deletion_evidence",
        type_="unique",
    )
    op.drop_constraint(
        op.f("uq_object_deletion_evidence_data_export_request_id"),
        "object_deletion_evidence",
        type_="unique",
    )
    op.add_column("object_deletion_evidence", sa.Column("target_asset_id", sa.String(32)))
    op.add_column(
        "object_deletion_evidence",
        sa.Column("target_data_export_request_id", sa.String(32)),
    )
    op.create_foreign_key(
        op.f("fk_object_deletion_evidence_target_asset_id_assets"),
        "object_deletion_evidence",
        "assets",
        ["target_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_object_deletion_evidence_target_data_export_request_id_data_export_requests"),
        "object_deletion_evidence",
        "data_export_requests",
        ["target_data_export_request_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_object_deletion_evidence_one_object_deletion_target"),
        "object_deletion_evidence",
        "(object_kind = 'asset' AND target_asset_id IS NOT NULL "
        "AND target_data_export_request_id IS NULL) OR "
        "(object_kind = 'data_export' AND target_asset_id IS NULL "
        "AND target_data_export_request_id IS NOT NULL)",
    )
    for name, columns in (
        ("unique_asset_deletion_target_evidence", ["asset_deletion_request_id", "target_asset_id"]),
        (
            "unique_export_deletion_target_evidence",
            ["data_export_request_id", "target_data_export_request_id"],
        ),
        (
            "unique_account_asset_deletion_evidence",
            ["account_deletion_request_id", "target_asset_id"],
        ),
        (
            "unique_account_export_deletion_evidence",
            ["account_deletion_request_id", "target_data_export_request_id"],
        ),
    ):
        op.create_unique_constraint(name, "object_deletion_evidence", columns)
    op.create_index(
        op.f("ix_object_deletion_evidence_target_asset_id"),
        "object_deletion_evidence",
        ["target_asset_id"],
    )
    op.create_index(
        op.f("ix_object_deletion_evidence_target_data_export_request_id"),
        "object_deletion_evidence",
        ["target_data_export_request_id"],
    )
    _install_target_authority_function()


def downgrade() -> None:
    op.drop_index(
        op.f("ix_object_deletion_evidence_target_data_export_request_id"),
        table_name="object_deletion_evidence",
    )
    op.drop_index(
        op.f("ix_object_deletion_evidence_target_asset_id"),
        table_name="object_deletion_evidence",
    )
    for name in (
        "unique_account_export_deletion_evidence",
        "unique_account_asset_deletion_evidence",
        "unique_export_deletion_target_evidence",
        "unique_asset_deletion_target_evidence",
    ):
        op.drop_constraint(name, "object_deletion_evidence", type_="unique")
    op.drop_constraint(
        op.f("ck_object_deletion_evidence_one_object_deletion_target"),
        "object_deletion_evidence",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_object_deletion_evidence_target_data_export_request_id_data_export_requests"),
        "object_deletion_evidence",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_object_deletion_evidence_target_asset_id_assets"),
        "object_deletion_evidence",
        type_="foreignkey",
    )
    op.drop_column("object_deletion_evidence", "target_data_export_request_id")
    op.drop_column("object_deletion_evidence", "target_asset_id")
    op.create_unique_constraint(
        op.f("uq_object_deletion_evidence_asset_deletion_request_id"),
        "object_deletion_evidence",
        ["asset_deletion_request_id"],
    )
    op.create_unique_constraint(
        op.f("uq_object_deletion_evidence_data_export_request_id"),
        "object_deletion_evidence",
        ["data_export_request_id"],
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_object_deletion_evidence()
        RETURNS trigger AS $$
        DECLARE authority_owner varchar(32);
        BEGIN
            IF NEW.asset_deletion_request_id IS NOT NULL THEN
                SELECT owner_user_id INTO authority_owner FROM asset_deletion_requests
                WHERE id = NEW.asset_deletion_request_id FOR KEY SHARE;
                IF NEW.object_kind <> 'asset' THEN
                    RAISE EXCEPTION 'asset deletion evidence requires asset object kind';
                END IF;
            ELSIF NEW.data_export_request_id IS NOT NULL THEN
                SELECT owner_user_id INTO authority_owner FROM data_export_requests
                WHERE id = NEW.data_export_request_id FOR KEY SHARE;
                IF NEW.object_kind <> 'data_export' THEN
                    RAISE EXCEPTION 'export deletion evidence requires data_export object kind';
                END IF;
            ELSE
                SELECT owner_user_id INTO authority_owner FROM account_deletion_requests
                WHERE id = NEW.account_deletion_request_id FOR KEY SHARE;
            END IF;
            IF authority_owner IS NULL OR authority_owner <> NEW.owner_user_id THEN
                RAISE EXCEPTION 'object deletion evidence owner must match its authority';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
