"""Add authoritative safe-image ingestion persistence.

Revision ID: 0004_safe_image_ingestion
Revises: 0003_upload_control
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_safe_image_ingestion"
down_revision: str | None = "0003_upload_control"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _install_ingestion_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_validate_asset_ingestion_record() RETURNS trigger AS $$
        DECLARE
            ingestion_job jobs%ROWTYPE;
            ingestion_asset assets%ROWTYPE;
        BEGIN
            SELECT * INTO ingestion_job
            FROM jobs
            WHERE id = NEW.job_id AND owner_user_id = NEW.owner_user_id
            FOR KEY SHARE;

            IF NOT FOUND OR ingestion_job.job_type <> 'asset_ingestion'
               OR ingestion_job.ingestion_upload_intent_id <> NEW.upload_intent_id
               OR ingestion_job.status <> NEW.outcome
               OR ingestion_job.result_asset_id IS DISTINCT FROM NEW.result_asset_id
               OR ingestion_job.result_code IS DISTINCT FROM NEW.result_code THEN
                RAISE EXCEPTION 'ingestion record must match its authoritative final job';
            END IF;

            IF NEW.outcome = 'promoted' THEN
                SELECT * INTO ingestion_asset
                FROM assets
                WHERE id = NEW.result_asset_id AND owner_user_id = NEW.owner_user_id
                FOR KEY SHARE;

                IF NOT FOUND OR ingestion_asset.asset_role <> 'original'
                   OR ingestion_asset.synthetic OR ingestion_asset.is_ai_generated
                   OR ingestion_asset.is_ai_modified OR ingestion_asset.deleted_at IS NOT NULL THEN
                    RAISE EXCEPTION 'promoted ingestion record requires an active immutable original asset';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_ingestion_job_final() RETURNS trigger AS $$
        DECLARE
            evidence asset_ingestion_records%ROWTYPE;
        BEGIN
            IF NEW.job_type = 'asset_ingestion' THEN
                SELECT * INTO evidence
                FROM asset_ingestion_records
                WHERE job_id = NEW.id;

                IF NEW.status IN ('promoted', 'rejected') THEN
                    IF NOT FOUND OR evidence.owner_user_id <> NEW.owner_user_id
                       OR evidence.upload_intent_id <> NEW.ingestion_upload_intent_id
                       OR evidence.outcome <> NEW.status
                       OR evidence.result_asset_id IS DISTINCT FROM NEW.result_asset_id
                       OR evidence.result_code <> NEW.result_code THEN
                        RAISE EXCEPTION 'final ingestion job requires matching final evidence';
                    END IF;
                ELSIF FOUND THEN
                    RAISE EXCEPTION 'non-final ingestion job cannot retain final evidence';
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_ingestion_intent_final() RETURNS trigger AS $$
        DECLARE
            evidence asset_ingestion_records%ROWTYPE;
        BEGIN
            SELECT * INTO evidence
            FROM asset_ingestion_records
            WHERE upload_intent_id = NEW.id;

            IF NEW.status IN ('promoted', 'rejected') THEN
                IF NOT FOUND OR evidence.owner_user_id <> NEW.owner_user_id
                   OR evidence.outcome <> NEW.status THEN
                    RAISE EXCEPTION 'final upload intent requires matching final ingestion evidence';
                END IF;
            ELSIF FOUND THEN
                RAISE EXCEPTION 'non-final upload intent cannot retain final ingestion evidence';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_protect_ingestion_job_attempt() RETURNS trigger AS $$
        DECLARE
            ingestion_job jobs%ROWTYPE;
            target_job_id varchar(32);
        BEGIN
            IF TG_OP = 'DELETE' THEN
                target_job_id := OLD.job_id;
            ELSE
                target_job_id := NEW.job_id;
            END IF;
            SELECT * INTO ingestion_job FROM jobs WHERE id = target_job_id;
            IF NOT FOUND OR ingestion_job.job_type <> 'asset_ingestion' THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END IF;

            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'leased' OR NEW.attempt <> ingestion_job.attempt_count
                   OR NEW.lease_token IS DISTINCT FROM ingestion_job.lease_token
                   OR ingestion_job.status <> 'leased' THEN
                    RAISE EXCEPTION 'ingestion attempt must be created for the current job lease';
                END IF;
            ELSIF TG_OP = 'DELETE' OR OLD.status <> 'leased' THEN
                RAISE EXCEPTION 'completed ingestion attempt is immutable';
            ELSIF NEW.job_id <> OLD.job_id OR NEW.attempt <> OLD.attempt
               OR NEW.lease_token IS DISTINCT FROM OLD.lease_token
               OR NEW.started_at IS DISTINCT FROM OLD.started_at
               OR NEW.status NOT IN ('retryable_failure', 'promoted', 'rejected')
               OR NEW.finished_at IS NULL OR NEW.finished_at < NEW.started_at
               OR NEW.result_code IS NULL THEN
                RAISE EXCEPTION 'ingestion attempt must finish from its lease exactly once';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_protect_promoted_ingestion_asset() RETURNS trigger AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM asset_ingestion_records
                WHERE outcome = 'promoted' AND result_asset_id = OLD.id
            ) AND (
                NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id
                OR NEW.asset_role IS DISTINCT FROM OLD.asset_role
                OR NEW.synthetic IS DISTINCT FROM OLD.synthetic
                OR NEW.is_ai_generated IS DISTINCT FROM OLD.is_ai_generated
                OR NEW.is_ai_modified IS DISTINCT FROM OLD.is_ai_modified
                OR NEW.storage_key IS DISTINCT FROM OLD.storage_key
                OR NEW.mime_type IS DISTINCT FROM OLD.mime_type
                OR NEW.byte_size IS DISTINCT FROM OLD.byte_size
                OR NEW.width IS DISTINCT FROM OLD.width
                OR NEW.height IS DISTINCT FROM OLD.height
                OR NEW.sha256 IS DISTINCT FROM OLD.sha256
            ) THEN
                RAISE EXCEPTION 'promoted ingestion asset identity and blob metadata are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_ingestion_job_attempt_consistency() RETURNS trigger AS $$
        DECLARE
            target_job_id varchar(32);
            ingestion_job jobs%ROWTYPE;
            current_attempt job_attempts%ROWTYPE;
        BEGIN
            IF TG_TABLE_NAME = 'jobs' THEN
                target_job_id := NEW.id;
            ELSIF TG_OP = 'DELETE' THEN
                target_job_id := OLD.job_id;
            ELSE
                target_job_id := NEW.job_id;
            END IF;

            SELECT * INTO ingestion_job FROM jobs WHERE id = target_job_id;
            IF NOT FOUND OR ingestion_job.job_type <> 'asset_ingestion' THEN
                RETURN NULL;
            END IF;

            IF ingestion_job.status = 'pending' THEN
                IF EXISTS (
                    SELECT 1 FROM job_attempts
                    WHERE job_id = ingestion_job.id AND status = 'leased'
                ) THEN
                    RAISE EXCEPTION 'pending ingestion job cannot retain a leased attempt';
                END IF;
            ELSIF ingestion_job.status = 'leased' THEN
                SELECT * INTO current_attempt FROM job_attempts
                WHERE job_id = ingestion_job.id AND attempt = ingestion_job.attempt_count;
                IF NOT FOUND OR current_attempt.status <> 'leased'
                   OR current_attempt.lease_token IS DISTINCT FROM ingestion_job.lease_token
                   OR EXISTS (
                       SELECT 1 FROM job_attempts
                       WHERE job_id = ingestion_job.id AND status = 'leased'
                         AND attempt <> ingestion_job.attempt_count
                   ) THEN
                    RAISE EXCEPTION 'leased ingestion job requires exactly its current leased attempt';
                END IF;
            ELSIF ingestion_job.status IN ('promoted', 'rejected') THEN
                SELECT * INTO current_attempt FROM job_attempts
                WHERE job_id = ingestion_job.id AND attempt = ingestion_job.attempt_count;
                IF NOT FOUND OR current_attempt.status <> ingestion_job.status
                   OR current_attempt.finished_at IS NULL
                   OR current_attempt.result_code IS DISTINCT FROM ingestion_job.result_code
                   OR EXISTS (
                       SELECT 1 FROM job_attempts
                       WHERE job_id = ingestion_job.id AND status = 'leased'
                   ) THEN
                    RAISE EXCEPTION 'final ingestion job requires its matching completed current attempt';
                END IF;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER trg_asset_ingestion_records_validate "
        "BEFORE INSERT ON asset_ingestion_records "
        "FOR EACH ROW EXECUTE FUNCTION mirror_validate_asset_ingestion_record();"
    )
    op.execute(
        "CREATE TRIGGER trg_asset_ingestion_records_immutable "
        "BEFORE UPDATE OR DELETE ON asset_ingestion_records "
        "FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_jobs_validate_ingestion_final "
        "AFTER INSERT OR UPDATE ON jobs DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_validate_ingestion_job_final();"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_upload_intents_validate_ingestion_final "
        "AFTER INSERT OR UPDATE ON upload_intents DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_validate_ingestion_intent_final();"
    )
    op.execute(
        "CREATE TRIGGER trg_job_attempts_protect_ingestion "
        "BEFORE INSERT OR UPDATE OR DELETE ON job_attempts "
        "FOR EACH ROW EXECUTE FUNCTION mirror_protect_ingestion_job_attempt();"
    )
    op.execute(
        "CREATE TRIGGER trg_assets_protect_promoted_ingestion "
        "BEFORE UPDATE ON assets "
        "FOR EACH ROW EXECUTE FUNCTION mirror_protect_promoted_ingestion_asset();"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_jobs_validate_ingestion_attempt_consistency "
        "AFTER INSERT OR UPDATE ON jobs DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_validate_ingestion_job_attempt_consistency();"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_job_attempts_validate_ingestion_consistency "
        "AFTER INSERT OR UPDATE OR DELETE ON job_attempts DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_validate_ingestion_job_attempt_consistency();"
    )


def _remove_ingestion_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_job_attempts_validate_ingestion_consistency ON job_attempts")
    op.execute("DROP TRIGGER IF EXISTS trg_jobs_validate_ingestion_attempt_consistency ON jobs")
    op.execute("DROP TRIGGER IF EXISTS trg_assets_protect_promoted_ingestion ON assets")
    op.execute("DROP TRIGGER IF EXISTS trg_job_attempts_protect_ingestion ON job_attempts")
    op.execute("DROP TRIGGER IF EXISTS trg_upload_intents_validate_ingestion_final ON upload_intents")
    op.execute("DROP TRIGGER IF EXISTS trg_jobs_validate_ingestion_final ON jobs")
    op.execute("DROP TRIGGER IF EXISTS trg_asset_ingestion_records_immutable ON asset_ingestion_records")
    op.execute("DROP TRIGGER IF EXISTS trg_asset_ingestion_records_validate ON asset_ingestion_records")
    op.execute("DROP FUNCTION IF EXISTS mirror_protect_ingestion_job_attempt()")
    op.execute("DROP FUNCTION IF EXISTS mirror_protect_promoted_ingestion_asset()")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_ingestion_job_attempt_consistency()")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_ingestion_intent_final()")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_ingestion_job_final()")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_asset_ingestion_record()")


def upgrade() -> None:
    op.add_column(
        "upload_intents",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("upload_intents", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "upload_intents",
        sa.Column("quarantine_retention_deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE upload_intents SET quarantine_retention_deadline = uploaded_at + INTERVAL '1 hour' "
        "WHERE uploaded_at IS NOT NULL"
    )
    op.drop_constraint(
        op.f("ck_upload_intents_valid_upload_intent_timestamps"),
        "upload_intents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_upload_intents_valid_upload_intent_timestamps"),
        "upload_intents",
        "(status = 'awaiting_upload' AND uploaded_at IS NULL "
        "AND processing_started_at IS NULL AND finalized_at IS NULL "
        "AND cancelled_at IS NULL AND expired_at IS NULL) OR "
        "(status = 'uploaded_unverified' AND uploaded_at IS NOT NULL "
        "AND processing_started_at IS NULL AND finalized_at IS NULL "
        "AND cancelled_at IS NULL AND expired_at IS NULL) OR "
        "(status = 'processing' AND uploaded_at IS NOT NULL "
        "AND processing_started_at IS NOT NULL AND finalized_at IS NULL "
        "AND cancelled_at IS NULL AND expired_at IS NULL) OR "
        "(status IN ('promoted','rejected') AND uploaded_at IS NOT NULL "
        "AND processing_started_at IS NOT NULL AND finalized_at IS NOT NULL "
        "AND finalized_at >= processing_started_at AND cancelled_at IS NULL "
        "AND expired_at IS NULL) OR "
        "(status = 'cancelled' AND cancelled_at IS NOT NULL "
        "AND processing_started_at IS NULL AND finalized_at IS NULL AND expired_at IS NULL) OR "
        "(status = 'expired' AND expired_at IS NOT NULL "
        "AND processing_started_at IS NULL AND finalized_at IS NULL AND cancelled_at IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_upload_intents_valid_quarantine_retention_deadline"),
        "upload_intents",
        "quarantine_retention_deadline IS NULL OR "
        "(uploaded_at IS NOT NULL AND quarantine_retention_deadline > uploaded_at "
        "AND quarantine_retention_deadline <= uploaded_at + INTERVAL '24 hours')",
    )
    op.create_check_constraint(
        op.f("ck_upload_intents_uploaded_requires_quarantine_retention"),
        "upload_intents",
        "uploaded_at IS NULL OR quarantine_retention_deadline IS NOT NULL",
    )
    op.create_unique_constraint("unique_upload_intent_owner", "upload_intents", ["id", "owner_user_id"])
    op.create_unique_constraint("unique_asset_owner", "assets", ["id", "owner_user_id"])

    op.add_column("jobs", sa.Column("owner_user_id", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("ingestion_upload_intent_id", sa.String(length=32), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("jobs", sa.Column("lease_token", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("lease_acquired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("result_asset_id", sa.String(length=32), nullable=True))
    op.add_column("jobs", sa.Column("result_code", sa.String(length=64), nullable=True))
    op.alter_column("jobs", "attempt_count", existing_type=sa.Integer(), server_default=None)
    op.create_index(op.f("ix_jobs_owner_user_id"), "jobs", ["owner_user_id"])
    op.create_unique_constraint("unique_job_owner", "jobs", ["id", "owner_user_id"])
    op.create_unique_constraint(
        op.f("uq_jobs_ingestion_upload_intent_id"), "jobs", ["ingestion_upload_intent_id"]
    )
    op.create_foreign_key(
        "fk_jobs_owner_user_id_users", "jobs", "users", ["owner_user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_jobs_ingestion_intent_owner",
        "jobs",
        "upload_intents",
        ["ingestion_upload_intent_id", "owner_user_id"],
        ["id", "owner_user_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_jobs_result_asset_owner",
        "jobs",
        "assets",
        ["result_asset_id", "owner_user_id"],
        ["id", "owner_user_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_jobs_nonnegative_job_attempt_count"), "jobs", "attempt_count >= 0"
    )
    op.create_check_constraint(
        op.f("ck_jobs_ingestion_job_type"),
        "jobs",
        "ingestion_upload_intent_id IS NULL OR job_type = 'asset_ingestion'",
    )
    op.create_check_constraint(
        op.f("ck_jobs_ingestion_job_owner_intent"),
        "jobs",
        "job_type <> 'asset_ingestion' OR "
        "(owner_user_id IS NOT NULL AND ingestion_upload_intent_id IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_jobs_valid_ingestion_job_lifecycle"),
        "jobs",
        "job_type <> 'asset_ingestion' OR ((status = 'pending' "
        "AND lease_token IS NULL AND lease_acquired_at IS NULL "
        "AND lease_expires_at IS NULL AND finalized_at IS NULL "
        "AND result_asset_id IS NULL AND result_code IS NULL) OR "
        "(status = 'leased' AND attempt_count > 0 AND lease_token IS NOT NULL "
        "AND lease_acquired_at IS NOT NULL AND lease_expires_at > lease_acquired_at "
        "AND finalized_at IS NULL AND result_asset_id IS NULL AND result_code IS NULL) OR "
        "(status = 'promoted' AND attempt_count > 0 AND lease_token IS NULL "
        "AND lease_acquired_at IS NULL AND lease_expires_at IS NULL "
        "AND finalized_at IS NOT NULL AND result_asset_id IS NOT NULL "
        "AND result_code IS NOT NULL) OR "
        "(status = 'rejected' AND attempt_count > 0 AND lease_token IS NULL "
        "AND lease_acquired_at IS NULL AND lease_expires_at IS NULL "
        "AND finalized_at IS NOT NULL AND result_asset_id IS NULL "
        "AND result_code IS NOT NULL))",
    )

    op.add_column("job_attempts", sa.Column("lease_token", sa.String(length=64), nullable=True))
    op.add_column("job_attempts", sa.Column("result_code", sa.String(length=64), nullable=True))

    op.create_table(
        "asset_ingestion_records",
        sa.Column("owner_user_id", sa.String(length=32), nullable=False),
        sa.Column("upload_intent_id", sa.String(length=32), nullable=False),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("result_asset_id", sa.String(length=32), nullable=True),
        sa.Column("result_code", sa.String(length=64), nullable=False),
        sa.Column("sanitizer_version", sa.String(length=64), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('promoted','rejected')",
            name=op.f("ck_asset_ingestion_records_valid_ingestion_outcome"),
        ),
        sa.CheckConstraint(
            "(outcome = 'promoted' AND result_asset_id IS NOT NULL "
            "AND sanitizer_version IS NOT NULL) OR "
            "(outcome = 'rejected' AND result_asset_id IS NULL "
            "AND sanitizer_version IS NULL)",
            name=op.f("ck_asset_ingestion_records_valid_ingestion_result_shape"),
        ),
        sa.CheckConstraint(
            "result_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_asset_ingestion_records_valid_ingestion_code"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name=op.f("fk_asset_ingestion_records_owner_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["upload_intent_id", "owner_user_id"],
            ["upload_intents.id", "upload_intents.owner_user_id"],
            name="fk_ingestion_records_intent_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "owner_user_id"],
            ["jobs.id", "jobs.owner_user_id"],
            name="fk_ingestion_records_job_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["result_asset_id", "owner_user_id"],
            ["assets.id", "assets.owner_user_id"],
            name="fk_ingestion_records_asset_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_ingestion_records")),
        sa.UniqueConstraint("upload_intent_id", name=op.f("uq_asset_ingestion_records_upload_intent_id")),
        sa.UniqueConstraint("job_id", name=op.f("uq_asset_ingestion_records_job_id")),
        sa.UniqueConstraint("result_asset_id", name=op.f("uq_asset_ingestion_records_result_asset_id")),
    )
    op.create_index(
        op.f("ix_asset_ingestion_records_owner_user_id"), "asset_ingestion_records", ["owner_user_id"]
    )
    _install_ingestion_triggers()


def downgrade() -> None:
    _remove_ingestion_triggers()
    op.drop_index(op.f("ix_asset_ingestion_records_owner_user_id"), table_name="asset_ingestion_records")
    op.drop_table("asset_ingestion_records")
    op.drop_column("job_attempts", "result_code")
    op.drop_column("job_attempts", "lease_token")
    op.drop_constraint(op.f("ck_jobs_valid_ingestion_job_lifecycle"), "jobs", type_="check")
    op.drop_constraint(op.f("ck_jobs_ingestion_job_owner_intent"), "jobs", type_="check")
    op.drop_constraint(op.f("ck_jobs_ingestion_job_type"), "jobs", type_="check")
    op.drop_constraint(op.f("ck_jobs_nonnegative_job_attempt_count"), "jobs", type_="check")
    op.drop_constraint("fk_jobs_result_asset_owner", "jobs", type_="foreignkey")
    op.drop_constraint("fk_jobs_ingestion_intent_owner", "jobs", type_="foreignkey")
    op.drop_constraint("fk_jobs_owner_user_id_users", "jobs", type_="foreignkey")
    op.drop_constraint(op.f("uq_jobs_ingestion_upload_intent_id"), "jobs", type_="unique")
    op.drop_constraint("unique_job_owner", "jobs", type_="unique")
    op.drop_index(op.f("ix_jobs_owner_user_id"), table_name="jobs")
    op.drop_column("jobs", "result_code")
    op.drop_column("jobs", "result_asset_id")
    op.drop_column("jobs", "finalized_at")
    op.drop_column("jobs", "lease_expires_at")
    op.drop_column("jobs", "lease_acquired_at")
    op.drop_column("jobs", "lease_token")
    op.drop_column("jobs", "attempt_count")
    op.drop_column("jobs", "ingestion_upload_intent_id")
    op.drop_column("jobs", "owner_user_id")
    op.drop_constraint("unique_asset_owner", "assets", type_="unique")
    op.drop_constraint("unique_upload_intent_owner", "upload_intents", type_="unique")
    op.drop_constraint(
        op.f("ck_upload_intents_uploaded_requires_quarantine_retention"),
        "upload_intents",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_upload_intents_valid_quarantine_retention_deadline"),
        "upload_intents",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_upload_intents_valid_upload_intent_timestamps"),
        "upload_intents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_upload_intents_valid_upload_intent_timestamps"),
        "upload_intents",
        "(status = 'uploaded_unverified' AND uploaded_at IS NOT NULL "
        "AND cancelled_at IS NULL AND expired_at IS NULL) OR "
        "(status = 'cancelled' AND cancelled_at IS NOT NULL) OR "
        "(status = 'expired' AND expired_at IS NOT NULL) OR "
        "status IN ('awaiting_upload','processing','promoted','rejected')",
    )
    op.drop_column("upload_intents", "quarantine_retention_deadline")
    op.drop_column("upload_intents", "finalized_at")
    op.drop_column("upload_intents", "processing_started_at")
