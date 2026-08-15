"""Add authoritative user-data-rights lifecycle persistence.

Revision ID: 0005_data_rights_lifecycle
Revises: 0004_safe_image_ingestion
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_data_rights_lifecycle"
down_revision: str | None = "0004_safe_image_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _request_job_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["job_id", "owner_user_id"],
        ["jobs.id", "jobs.owner_user_id"],
        name=name,
        ondelete="RESTRICT",
    )


def _install_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_protect_data_rights_request() RETURNS trigger AS $$
        DECLARE
            allowed_transition boolean;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'data-rights request authority is append-only';
            END IF;

            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'requested' THEN
                    RAISE EXCEPTION 'data-rights request must start requested';
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.id IS DISTINCT FROM OLD.id
               OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id
               OR NEW.job_id IS DISTINCT FROM OLD.job_id
               OR NEW.idempotency_key_hash IS DISTINCT FROM OLD.idempotency_key_hash
               OR NEW.requested_at IS DISTINCT FROM OLD.requested_at
               OR (
                    TG_TABLE_NAME = 'asset_deletion_requests'
                    AND (to_jsonb(NEW) -> 'asset_id') IS DISTINCT FROM
                        (to_jsonb(OLD) -> 'asset_id')
               )
               OR (
                    TG_TABLE_NAME = 'data_export_requests'
                    AND (to_jsonb(NEW) -> 'schema_version') IS DISTINCT FROM
                        (to_jsonb(OLD) -> 'schema_version')
               ) THEN
                RAISE EXCEPTION 'data-rights request authority is immutable';
            END IF;

            allowed_transition := CASE TG_TABLE_NAME
                WHEN 'data_export_requests' THEN
                    (OLD.status = 'requested' AND NEW.status = 'processing')
                    OR (OLD.status = 'processing' AND NEW.status IN ('ready', 'failed'))
                    OR (OLD.status = 'ready' AND NEW.status = 'expired')
                ELSE
                    (OLD.status = 'requested' AND NEW.status = 'processing')
                    OR (OLD.status = 'processing' AND NEW.status IN ('completed', 'failed'))
            END;
            IF NOT allowed_transition THEN
                RAISE EXCEPTION 'invalid data-rights request status transition';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in (
        "asset_deletion_requests",
        "data_export_requests",
        "account_deletion_requests",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_protect_authority "
            f"BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW "
            "EXECUTE FUNCTION mirror_protect_data_rights_request()"
        )

    op.execute(
        """
        CREATE FUNCTION mirror_validate_data_rights_request_job() RETURNS trigger AS $$
        DECLARE
            authority jobs%ROWTYPE;
            expected_type text;
        BEGIN
            expected_type := CASE TG_TABLE_NAME
                WHEN 'asset_deletion_requests' THEN 'asset_deletion'
                WHEN 'data_export_requests' THEN 'data_export'
                WHEN 'account_deletion_requests' THEN 'account_deletion'
                ELSE NULL
            END;
            SELECT * INTO authority FROM jobs
            WHERE id = NEW.job_id AND owner_user_id = NEW.owner_user_id
            FOR KEY SHARE;
            IF NOT FOUND OR authority.job_type <> expected_type THEN
                RAISE EXCEPTION 'data-rights request requires matching owner-bound job';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in (
        "asset_deletion_requests",
        "data_export_requests",
        "account_deletion_requests",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_job_authority "
            f"BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW "
            "EXECUTE FUNCTION mirror_validate_data_rights_request_job()"
        )

    op.execute(
        """
        CREATE FUNCTION mirror_validate_object_deletion_evidence() RETURNS trigger AS $$
        DECLARE
            authority_owner varchar(32);
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
    op.execute(
        "CREATE TRIGGER trg_object_deletion_evidence_authority "
        "BEFORE INSERT ON object_deletion_evidence FOR EACH ROW "
        "EXECUTE FUNCTION mirror_validate_object_deletion_evidence()"
    )

    for table in (
        "asset_access_audits",
        "asset_deletion_events",
        "data_export_events",
        "account_deletion_events",
        "object_deletion_evidence",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation()"
        )

    op.execute(
        """
        CREATE FUNCTION mirror_validate_asset_deletion_tombstone() RETURNS trigger AS $$
        DECLARE projected_deleted_at timestamptz;
        BEGIN
            SELECT deleted_at INTO projected_deleted_at FROM assets
            WHERE id = NEW.asset_id AND owner_user_id = NEW.owner_user_id;
            IF projected_deleted_at IS NULL THEN
                RAISE EXCEPTION 'asset deletion request requires immediate asset tombstone';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_asset_deletion_tombstone "
        "AFTER INSERT OR UPDATE ON asset_deletion_requests DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_validate_asset_deletion_tombstone()"
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_account_deletion_projection() RETURNS trigger AS $$
        DECLARE projected_status varchar(24);
        BEGIN
            SELECT status INTO projected_status FROM users WHERE id = NEW.owner_user_id;
            IF projected_status NOT IN ('deletion_requested', 'deleted') THEN
                RAISE EXCEPTION 'account deletion request requires immediate user freeze';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_account_deletion_projection "
        "AFTER INSERT OR UPDATE ON account_deletion_requests DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_validate_account_deletion_projection()"
    )


def upgrade() -> None:
    op.create_table(
        "asset_deletion_requests",
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("asset_id", sa.String(32), nullable=False),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result_code", sa.String(64)),
        sa.Column("id", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "status IN ('requested','processing','completed','failed')",
            name=op.f("ck_asset_deletion_requests_valid_asset_deletion_status"),
        ),
        sa.CheckConstraint(
            "(status = 'requested' AND started_at IS NULL AND completed_at IS NULL AND result_code IS NULL) OR "
            "(status = 'processing' AND started_at IS NOT NULL AND completed_at IS NULL AND result_code IS NULL) OR "
            "(status IN ('completed','failed') AND started_at IS NOT NULL AND completed_at IS NOT NULL AND result_code IS NOT NULL)",
            name=op.f("ck_asset_deletion_requests_valid_asset_deletion_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["asset_id", "owner_user_id"],
            ["assets.id", "assets.owner_user_id"],
            name=op.f("fk_asset_deletion_requests_asset_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_asset_deletion_requests_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        _request_job_fk(op.f("fk_asset_deletion_requests_job_owner")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_deletion_requests")),
        sa.UniqueConstraint("asset_id", name=op.f("uq_asset_deletion_requests_asset_id")),
        sa.UniqueConstraint("job_id", name=op.f("uq_asset_deletion_requests_job_id")),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name=op.f("uq_asset_deletion_requests_idempotency_key_hash"),
        ),
    )
    op.create_index(
        op.f("ix_asset_deletion_requests_owner_user_id"),
        "asset_deletion_requests",
        ["owner_user_id"],
    )
    op.create_table(
        "asset_deletion_events",
        sa.Column("request_id", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("result_code", sa.String(64)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('requested','processing_started','completed','failed')",
            name=op.f("ck_asset_deletion_events_valid_asset_deletion_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["asset_deletion_requests.id"],
            name=op.f("fk_asset_deletion_events_request_id_asset_deletion_requests"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_deletion_events")),
    )
    op.create_index(
        op.f("ix_asset_deletion_events_request_id"), "asset_deletion_events", ["request_id"]
    )

    op.create_table(
        "data_export_requests",
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("schema_version", sa.String(48), nullable=False),
        sa.Column("storage_key", sa.String(255)),
        sa.Column("sha256", sa.String(64)),
        sa.Column("byte_size", sa.BigInteger()),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("result_code", sa.String(64)),
        sa.Column("id", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "status IN ('requested','processing','ready','failed','expired')",
            name=op.f("ck_data_export_requests_valid_data_export_status"),
        ),
        sa.CheckConstraint(
            "byte_size IS NULL OR byte_size > 0",
            name=op.f("ck_data_export_requests_positive_data_export_byte_size"),
        ),
        sa.CheckConstraint(
            "(status NOT IN ('ready','expired')) OR (storage_key IS NOT NULL AND sha256 IS NOT NULL AND byte_size IS NOT NULL AND ready_at IS NOT NULL AND expires_at > ready_at)",
            name=op.f("ck_data_export_requests_ready_data_export_has_artifact"),
        ),
        sa.CheckConstraint(
            "status <> 'expired' OR (deleted_at IS NOT NULL AND result_code IS NOT NULL)",
            name=op.f("ck_data_export_requests_expired_data_export_has_evidence"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_data_export_requests_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        _request_job_fk(op.f("fk_data_export_requests_job_owner")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_export_requests")),
        sa.UniqueConstraint("job_id", name=op.f("uq_data_export_requests_job_id")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_data_export_requests_storage_key")),
        sa.UniqueConstraint(
            "idempotency_key_hash", name=op.f("uq_data_export_requests_idempotency_key_hash")
        ),
    )
    op.create_index(
        op.f("ix_data_export_requests_owner_user_id"),
        "data_export_requests",
        ["owner_user_id"],
    )
    op.create_table(
        "data_export_events",
        sa.Column("request_id", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("result_code", sa.String(64)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('requested','processing_started','ready','failed','expired')",
            name=op.f("ck_data_export_events_valid_data_export_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["data_export_requests.id"],
            name=op.f("fk_data_export_events_request_id_data_export_requests"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_export_events")),
    )
    op.create_index(op.f("ix_data_export_events_request_id"), "data_export_events", ["request_id"])

    op.create_table(
        "account_deletion_requests",
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result_code", sa.String(64)),
        sa.Column("id", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "status IN ('requested','processing','completed','failed')",
            name=op.f("ck_account_deletion_requests_valid_account_deletion_status"),
        ),
        sa.CheckConstraint(
            "(status = 'requested' AND started_at IS NULL AND completed_at IS NULL AND result_code IS NULL) OR "
            "(status = 'processing' AND started_at IS NOT NULL AND completed_at IS NULL AND result_code IS NULL) OR "
            "(status IN ('completed','failed') AND started_at IS NOT NULL AND completed_at IS NOT NULL AND result_code IS NOT NULL)",
            name=op.f("ck_account_deletion_requests_valid_account_deletion_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_account_deletion_requests_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        _request_job_fk(op.f("fk_account_deletion_requests_job_owner")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_deletion_requests")),
        sa.UniqueConstraint(
            "owner_user_id", name=op.f("uq_account_deletion_requests_owner_user_id")
        ),
        sa.UniqueConstraint("job_id", name=op.f("uq_account_deletion_requests_job_id")),
        sa.UniqueConstraint(
            "idempotency_key_hash",
            name=op.f("uq_account_deletion_requests_idempotency_key_hash"),
        ),
    )
    op.create_table(
        "account_deletion_events",
        sa.Column("request_id", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("result_code", sa.String(64)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('requested','processing_started','completed','failed')",
            name=op.f("ck_account_deletion_events_valid_account_deletion_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["account_deletion_requests.id"],
            name=op.f("fk_account_deletion_events_request_id_account_deletion_requests"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_deletion_events")),
    )
    op.create_index(
        op.f("ix_account_deletion_events_request_id"),
        "account_deletion_events",
        ["request_id"],
    )

    op.create_table(
        "object_deletion_evidence",
        sa.Column("owner_user_id", sa.String(32), nullable=False),
        sa.Column("asset_deletion_request_id", sa.String(32)),
        sa.Column("data_export_request_id", sa.String(32)),
        sa.Column("account_deletion_request_id", sa.String(32)),
        sa.Column("object_kind", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("result_code", sa.String(64), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "num_nonnulls(asset_deletion_request_id, data_export_request_id, account_deletion_request_id) = 1",
            name=op.f("ck_object_deletion_evidence_one_object_deletion_authority"),
        ),
        sa.CheckConstraint(
            "object_kind IN ('asset','data_export')",
            name=op.f("ck_object_deletion_evidence_valid_deleted_object_kind"),
        ),
        sa.CheckConstraint(
            "outcome IN ('deleted','not_found')",
            name=op.f("ck_object_deletion_evidence_valid_object_deletion_outcome"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_object_deletion_evidence_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_deletion_request_id"],
            ["asset_deletion_requests.id"],
            name=op.f(
                "fk_object_deletion_evidence_asset_deletion_request_id_asset_deletion_requests"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["data_export_request_id"],
            ["data_export_requests.id"],
            name=op.f("fk_object_deletion_evidence_data_export_request_id_data_export_requests"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["account_deletion_request_id"],
            ["account_deletion_requests.id"],
            name=op.f(
                "fk_object_deletion_evidence_account_deletion_request_id_account_deletion_requests"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_object_deletion_evidence")),
        sa.UniqueConstraint(
            "asset_deletion_request_id",
            name=op.f("uq_object_deletion_evidence_asset_deletion_request_id"),
        ),
        sa.UniqueConstraint(
            "data_export_request_id",
            name=op.f("uq_object_deletion_evidence_data_export_request_id"),
        ),
    )
    op.create_index(
        op.f("ix_object_deletion_evidence_owner_user_id"),
        "object_deletion_evidence",
        ["owner_user_id"],
    )
    op.create_index(
        op.f("ix_object_deletion_evidence_account_deletion_request_id"),
        "object_deletion_evidence",
        ["account_deletion_request_id"],
    )
    _install_triggers()


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_account_deletion_projection ON account_deletion_requests")
    op.execute("DROP FUNCTION mirror_validate_account_deletion_projection()")
    op.execute("DROP TRIGGER trg_asset_deletion_tombstone ON asset_deletion_requests")
    op.execute("DROP FUNCTION mirror_validate_asset_deletion_tombstone()")
    for table in (
        "object_deletion_evidence",
        "account_deletion_events",
        "data_export_events",
        "asset_deletion_events",
        "asset_access_audits",
    ):
        op.execute(f"DROP TRIGGER trg_{table}_append_only ON {table}")
    op.execute("DROP TRIGGER trg_object_deletion_evidence_authority ON object_deletion_evidence")
    op.execute("DROP FUNCTION mirror_validate_object_deletion_evidence()")
    for table in (
        "account_deletion_requests",
        "data_export_requests",
        "asset_deletion_requests",
    ):
        op.execute(f"DROP TRIGGER trg_{table}_job_authority ON {table}")
    op.execute("DROP FUNCTION mirror_validate_data_rights_request_job()")
    for table in (
        "account_deletion_requests",
        "data_export_requests",
        "asset_deletion_requests",
    ):
        op.execute(f"DROP TRIGGER trg_{table}_protect_authority ON {table}")
    op.execute("DROP FUNCTION mirror_protect_data_rights_request()")

    op.drop_index(
        op.f("ix_object_deletion_evidence_account_deletion_request_id"),
        table_name="object_deletion_evidence",
    )
    op.drop_index(
        op.f("ix_object_deletion_evidence_owner_user_id"),
        table_name="object_deletion_evidence",
    )
    op.drop_table("object_deletion_evidence")
    op.drop_index(
        op.f("ix_account_deletion_events_request_id"),
        table_name="account_deletion_events",
    )
    op.drop_table("account_deletion_events")
    op.drop_table("account_deletion_requests")
    op.drop_index(op.f("ix_data_export_events_request_id"), table_name="data_export_events")
    op.drop_table("data_export_events")
    op.drop_index(
        op.f("ix_data_export_requests_owner_user_id"),
        table_name="data_export_requests",
    )
    op.drop_table("data_export_requests")
    op.drop_index(
        op.f("ix_asset_deletion_events_request_id"),
        table_name="asset_deletion_events",
    )
    op.drop_table("asset_deletion_events")
    op.drop_index(
        op.f("ix_asset_deletion_requests_owner_user_id"),
        table_name="asset_deletion_requests",
    )
    op.drop_table("asset_deletion_requests")
