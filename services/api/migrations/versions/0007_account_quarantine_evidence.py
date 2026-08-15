"""Add owner-bound quarantine targets for account-deletion evidence.

Revision ID: 0007_account_quarantine_evidence
Revises: 0006_deletion_evidence_targets
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_account_quarantine_evidence"
down_revision: str | None = "0006_deletion_evidence_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _install_account_quarantine_authority_function() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_object_deletion_evidence()
        RETURNS trigger AS $$
        DECLARE
            authority_owner varchar(32);
            authority_asset varchar(32);
            target_owner varchar(32);
            target_deleted_at timestamptz;
            target_upload_status varchar(32);
            reachable boolean;
        BEGIN
            IF NEW.object_kind = 'asset' THEN
                SELECT owner_user_id, deleted_at INTO target_owner, target_deleted_at FROM assets
                WHERE id = NEW.target_asset_id FOR KEY SHARE;
                IF target_deleted_at IS NULL THEN
                    RAISE EXCEPTION 'asset deletion evidence requires target tombstone';
                END IF;
            ELSIF NEW.object_kind = 'data_export' THEN
                SELECT owner_user_id INTO target_owner FROM data_export_requests
                WHERE id = NEW.target_data_export_request_id FOR KEY SHARE;
            ELSE
                SELECT owner_user_id, status INTO target_owner, target_upload_status
                FROM upload_intents
                WHERE id = NEW.target_upload_intent_id FOR KEY SHARE;
                IF target_upload_status NOT IN ('promoted','rejected','cancelled','expired') THEN
                    RAISE EXCEPTION 'quarantine deletion evidence requires terminal upload intent';
                END IF;
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


def _install_dependency_target_authority_function() -> None:
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
    op.add_column(
        "object_deletion_evidence",
        sa.Column("target_upload_intent_id", sa.String(32)),
    )
    op.create_foreign_key(
        "fk_object_deletion_evidence_target_upload_intent",
        "object_deletion_evidence",
        "upload_intents",
        ["target_upload_intent_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        op.f("ck_object_deletion_evidence_one_object_deletion_target"),
        "object_deletion_evidence",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_object_deletion_evidence_valid_deleted_object_kind"),
        "object_deletion_evidence",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_object_deletion_evidence_one_object_deletion_target"),
        "object_deletion_evidence",
        "(object_kind = 'asset' AND target_asset_id IS NOT NULL "
        "AND target_data_export_request_id IS NULL AND target_upload_intent_id IS NULL) OR "
        "(object_kind = 'data_export' AND target_asset_id IS NULL "
        "AND target_data_export_request_id IS NOT NULL AND target_upload_intent_id IS NULL) OR "
        "(object_kind = 'quarantine' AND target_asset_id IS NULL "
        "AND target_data_export_request_id IS NULL AND target_upload_intent_id IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_object_deletion_evidence_valid_deleted_object_kind"),
        "object_deletion_evidence",
        "object_kind IN ('asset','data_export','quarantine')",
    )
    op.create_unique_constraint(
        "unique_account_quarantine_deletion_evidence",
        "object_deletion_evidence",
        ["account_deletion_request_id", "target_upload_intent_id"],
    )
    op.create_index(
        op.f("ix_object_deletion_evidence_target_upload_intent_id"),
        "object_deletion_evidence",
        ["target_upload_intent_id"],
    )
    _install_account_quarantine_authority_function()


def downgrade() -> None:
    op.drop_index(
        op.f("ix_object_deletion_evidence_target_upload_intent_id"),
        table_name="object_deletion_evidence",
    )
    op.drop_constraint(
        "unique_account_quarantine_deletion_evidence",
        "object_deletion_evidence",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_object_deletion_evidence_valid_deleted_object_kind"),
        "object_deletion_evidence",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_object_deletion_evidence_one_object_deletion_target"),
        "object_deletion_evidence",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_object_deletion_evidence_one_object_deletion_target"),
        "object_deletion_evidence",
        "(object_kind = 'asset' AND target_asset_id IS NOT NULL "
        "AND target_data_export_request_id IS NULL) OR "
        "(object_kind = 'data_export' AND target_asset_id IS NULL "
        "AND target_data_export_request_id IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_object_deletion_evidence_valid_deleted_object_kind"),
        "object_deletion_evidence",
        "object_kind IN ('asset','data_export')",
    )
    op.drop_constraint(
        "fk_object_deletion_evidence_target_upload_intent",
        "object_deletion_evidence",
        type_="foreignkey",
    )
    op.drop_column("object_deletion_evidence", "target_upload_intent_id")
    _install_dependency_target_authority_function()
