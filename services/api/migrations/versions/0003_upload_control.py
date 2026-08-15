"""Add purpose consent evidence and quarantine upload control.

Revision ID: 0003_upload_control
Revises: 0002_identity_auth
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_upload_control"
down_revision: str | None = "0002_identity_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "consent_records",
        sa.Column(
            "purpose_version",
            sa.String(length=48),
            nullable=False,
            server_default="legacy-phase0",
        ),
    )
    op.add_column(
        "consent_records",
        sa.Column(
            "policy_code", sa.String(length=64), nullable=False, server_default="legacy-consent"
        ),
    )
    op.add_column(
        "consent_records",
        sa.Column(
            "policy_digest",
            sa.String(length=64),
            nullable=False,
            server_default="0" * 64,
        ),
    )
    op.add_column(
        "consent_records", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "consent_records",
        sa.Column(
            "request_id",
            sa.String(length=128),
            nullable=False,
            server_default="legacy-phase0",
        ),
    )
    for column_name, column_type in (
        ("purpose_version", sa.String(length=48)),
        ("policy_code", sa.String(length=64)),
        ("policy_digest", sa.String(length=64)),
        ("request_id", sa.String(length=128)),
    ):
        op.alter_column(
            "consent_records",
            column_name,
            existing_type=column_type,
            server_default=None,
        )
    op.create_check_constraint(
        op.f("ck_consent_records_valid_consent_expiry"),
        "consent_records",
        "expires_at IS NULL OR (action = 'grant' AND expires_at >= granted_at)",
    )
    op.create_unique_constraint(
        "unique_consent_owner",
        "consent_records",
        ["id", "user_id"],
    )
    op.create_unique_constraint(
        "unique_consent_supersession",
        "consent_records",
        ["supersedes_id"],
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_consent_supersession() RETURNS trigger AS $$
        DECLARE
            grant_record consent_records%ROWTYPE;
        BEGIN
            IF NEW.action = 'withdraw' THEN
                SELECT * INTO grant_record
                FROM consent_records
                WHERE id = NEW.supersedes_id
                FOR KEY SHARE;
                IF NOT FOUND OR grant_record.action <> 'grant'
                   OR grant_record.user_id <> NEW.user_id
                   OR grant_record.consent_type <> NEW.consent_type
                   OR grant_record.purpose <> NEW.purpose
                   OR grant_record.purpose_version <> NEW.purpose_version
                   OR grant_record.policy_code <> NEW.policy_code
                   OR grant_record.policy_version <> NEW.policy_version
                   OR grant_record.policy_digest <> NEW.policy_digest
                   OR grant_record.scope::jsonb IS DISTINCT FROM NEW.scope::jsonb THEN
                    RAISE EXCEPTION 'consent withdrawal must exactly supersede its grant';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER trg_consent_records_validate_supersession "
        "BEFORE INSERT ON consent_records "
        "FOR EACH ROW EXECUTE FUNCTION mirror_validate_consent_supersession();"
    )

    op.create_table(
        "upload_intents",
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("consent_record_id", sa.String(length=32), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("declared_mime_type", sa.String(length=64), nullable=False),
        sa.Column("declared_byte_size", sa.BigInteger(), nullable=False),
        sa.Column("declared_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("grant_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "declared_byte_size > 0 AND declared_byte_size <= 20971520",
            name=op.f("ck_upload_intents_valid_declared_byte_size"),
        ),
        sa.CheckConstraint(
            "declared_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_upload_intents_valid_declared_sha256"),
        ),
        sa.CheckConstraint(
            "declared_mime_type IN ('image/jpeg','image/png','image/webp')",
            name=op.f("ck_upload_intents_valid_declared_image_mime"),
        ),
        sa.CheckConstraint(
            "status IN ('awaiting_upload','uploaded_unverified','processing',"
            "'promoted','rejected','cancelled','expired')",
            name=op.f("ck_upload_intents_valid_upload_intent_status"),
        ),
        sa.CheckConstraint(
            "(status = 'uploaded_unverified' AND uploaded_at IS NOT NULL "
            "AND cancelled_at IS NULL AND expired_at IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL) OR "
            "(status = 'expired' AND expired_at IS NOT NULL) OR "
            "status IN ('awaiting_upload','processing','promoted','rejected')",
            name=op.f("ck_upload_intents_valid_upload_intent_timestamps"),
        ),
        sa.CheckConstraint(
            "grant_expires_at > created_at",
            name=op.f("ck_upload_intents_valid_upload_grant_expiry"),
        ),
        sa.ForeignKeyConstraint(
            ["consent_record_id", "owner_user_id"],
            ["consent_records.id", "consent_records.user_id"],
            name=op.f("fk_upload_intents_consent_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_upload_intents_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_upload_intents")),
        sa.UniqueConstraint("object_key", name=op.f("uq_upload_intents_object_key")),
    )
    op.create_index("ix_upload_intents_owner_user_id", "upload_intents", ["owner_user_id"])
    op.create_index("ix_upload_intents_consent_record_id", "upload_intents", ["consent_record_id"])
    op.create_index("ix_upload_intents_owner_status", "upload_intents", ["owner_user_id", "status"])

    op.create_table(
        "upload_intent_events",
        sa.Column("upload_intent_id", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('created','grant_issued','upload_completed','cancelled',"
            "'expired','processing_started','promoted','rejected')",
            name=op.f("ck_upload_intent_events_valid_upload_intent_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["upload_intent_id"],
            ["upload_intents.id"],
            name=op.f("fk_upload_intent_events_upload_intent_id_upload_intents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_upload_intent_events")),
    )
    op.create_index(
        "ix_upload_intent_events_upload_intent_id",
        "upload_intent_events",
        ["upload_intent_id"],
    )
    op.execute(
        "CREATE TRIGGER trg_upload_intent_events_immutable "
        "BEFORE UPDATE OR DELETE ON upload_intent_events "
        "FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_upload_intent_events_immutable ON upload_intent_events")
    op.drop_index("ix_upload_intent_events_upload_intent_id", table_name="upload_intent_events")
    op.drop_table("upload_intent_events")
    op.drop_index("ix_upload_intents_owner_status", table_name="upload_intents")
    op.drop_index("ix_upload_intents_consent_record_id", table_name="upload_intents")
    op.drop_index("ix_upload_intents_owner_user_id", table_name="upload_intents")
    op.drop_table("upload_intents")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_consent_records_validate_supersession ON consent_records"
    )
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_consent_supersession()")
    op.drop_constraint(
        "unique_consent_supersession",
        "consent_records",
        type_="unique",
    )
    op.drop_constraint(
        "unique_consent_owner",
        "consent_records",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_consent_records_valid_consent_expiry"),
        "consent_records",
        type_="check",
    )
    op.drop_column("consent_records", "request_id")
    op.drop_column("consent_records", "expires_at")
    op.drop_column("consent_records", "policy_digest")
    op.drop_column("consent_records", "policy_code")
    op.drop_column("consent_records", "purpose_version")
