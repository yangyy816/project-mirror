"""Add immutable offline Codex-native synthetic source authority.

Revision ID: 0011_offline_synth_source
Revises: 0010_synthetic_asset_qa
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_offline_synth_source"
down_revision: str | None = "0010_synthetic_asset_qa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_offline_admissions() -> None:
    op.create_table(
        "offline_synthetic_source_admissions",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("admission_evidence_schema_version", sa.String(length=96), nullable=False),
        sa.Column("specification_reference", sa.String(length=128), nullable=False),
        sa.Column("specification_version", sa.String(length=96), nullable=False),
        sa.Column("generation_policy_reference", sa.String(length=128), nullable=False),
        sa.Column("prompt_template_reference", sa.String(length=128), nullable=False),
        sa.Column("prompt_digest", sa.String(length=64), nullable=False),
        sa.Column("item_reference", sa.String(length=128), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("provenance_level", sa.String(length=32), nullable=False),
        sa.Column("cost_accounting_mode", sa.String(length=32), nullable=False),
        sa.Column("synthetic_only", sa.Boolean(), nullable=False),
        sa.Column("real_person_reference_used", sa.Boolean(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=32), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("requested_width", sa.Integer(), nullable=True),
        sa.Column("requested_height", sa.Integer(), nullable=True),
        sa.Column("dimensions_match_requested", sa.Boolean(), nullable=True),
        sa.Column("storage_reference", sa.String(length=128), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("admission_evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("model_reference", sa.String(length=128), nullable=True),
        sa.Column("model_version_reference", sa.String(length=128), nullable=True),
        sa.Column("provider_request_reference", sa.String(length=128), nullable=True),
        sa.Column("provider_actual_seed", sa.BigInteger(), nullable=True),
        sa.Column("provider_usage", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("provider_cost", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/OfflineSyntheticSourceAdmission/v1'",
            name=op.f("ck_offline_synthetic_source_admissions_schema_version"),
        ),
        sa.CheckConstraint(
            "admission_evidence_schema_version IN "
            "('mirror.synthetic-dataset/CodexNativeAdmissionEvidence/v1',"
            "'mirror.synthetic-dataset/CodexNativeAdmissionEvidence/v2')",
            name=op.f("ck_offline_synthetic_source_admissions_evidence_schema"),
        ),
        sa.CheckConstraint(
            "source_kind = 'CODEX_NATIVE_IMAGEGEN'",
            name=op.f("ck_offline_synthetic_source_admissions_source_kind"),
        ),
        sa.CheckConstraint(
            "provenance_level = 'PROVENANCE_ONLY'",
            name=op.f("ck_offline_synthetic_source_admissions_provenance_level"),
        ),
        sa.CheckConstraint(
            "cost_accounting_mode = 'REQUEST_COUNT_ONLY'",
            name=op.f("ck_offline_synthetic_source_admissions_cost_accounting_mode"),
        ),
        sa.CheckConstraint(
            "synthetic_only", name=op.f("ck_offline_synthetic_source_admissions_synthetic_only")
        ),
        sa.CheckConstraint(
            "NOT real_person_reference_used",
            name=op.f("ck_offline_synthetic_source_admissions_no_real_person"),
        ),
        sa.CheckConstraint(
            "attempt >= 1", name=op.f("ck_offline_synthetic_source_admissions_attempt")
        ),
        sa.CheckConstraint(
            "prompt_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_offline_synthetic_source_admissions_prompt_digest"),
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_offline_synthetic_source_admissions_sha256")
        ),
        sa.CheckConstraint(
            "admission_evidence_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_offline_synthetic_source_admissions_evidence_digest"),
        ),
        sa.CheckConstraint(
            "media_type IN ('image/jpeg','image/png','image/webp')",
            name=op.f("ck_offline_synthetic_source_admissions_media_type"),
        ),
        sa.CheckConstraint(
            "byte_size > 0 AND width > 0 AND height > 0",
            name=op.f("ck_offline_synthetic_source_admissions_positive_metadata"),
        ),
        sa.CheckConstraint(
            "storage_reference ~ '^[a-z0-9][a-z0-9._:-]{2,127}$'",
            name=op.f("ck_offline_synthetic_source_admissions_storage_reference"),
        ),
        sa.CheckConstraint(
            "(requested_width IS NULL AND requested_height IS NULL "
            "AND dimensions_match_requested IS NULL) OR "
            "(requested_width > 0 AND requested_height > 0 "
            "AND dimensions_match_requested IS NOT NULL)",
            name=op.f("ck_offline_synthetic_source_admissions_request_dims"),
        ),
        sa.CheckConstraint(
            "retention_expires_at > admitted_at AND admitted_at >= generated_at",
            name=op.f("ck_offline_synthetic_source_admissions_timestamp_order"),
        ),
        sa.CheckConstraint(
            "model_reference IS NULL AND model_version_reference IS NULL "
            "AND provider_request_reference IS NULL AND provider_actual_seed IS NULL "
            "AND provider_usage IS NULL AND provider_cost IS NULL",
            name=op.f("ck_offline_synthetic_source_admissions_known_null_facts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_offline_synthetic_source_admissions")),
        sa.UniqueConstraint("storage_reference", name="uq_offline_admission_storage"),
        sa.UniqueConstraint(
            "admission_evidence_digest",
            name="uq_offline_admission_digest",
        ),
        sa.UniqueConstraint(
            "specification_reference",
            "item_reference",
            "attempt",
            name="uq_offline_admission_attempt",
        ),
    )


def _alter_source_authority_union() -> None:
    op.alter_column(
        "synthetic_source_objects",
        "generation_item_id",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.alter_column(
        "synthetic_source_objects",
        "job_attempt_id",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.add_column(
        "synthetic_source_objects",
        sa.Column("offline_admission_id", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        op.f(
            "fk_synthetic_source_objects_offline_admission_id_offline_synthetic_source_admissions"
        ),
        "synthetic_source_objects",
        "offline_synthetic_source_admissions",
        ["offline_admission_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        op.f("uq_synthetic_source_objects_offline_admission_id"),
        "synthetic_source_objects",
        ["offline_admission_id"],
    )
    op.drop_constraint(
        op.f("ck_synthetic_source_objects_schema_version"), "synthetic_source_objects"
    )
    op.create_check_constraint(
        op.f("ck_synthetic_source_objects_schema_version"),
        "synthetic_source_objects",
        "schema_version IN ('mirror.synthetic-dataset/SyntheticSourceObject/v1',"
        "'mirror.synthetic-dataset/SyntheticSourceObject/v2')",
    )
    op.create_check_constraint(
        op.f("ck_synthetic_source_objects_authority_shape"),
        "synthetic_source_objects",
        "(schema_version = 'mirror.synthetic-dataset/SyntheticSourceObject/v1' "
        "AND generation_item_id IS NOT NULL AND job_attempt_id IS NOT NULL "
        "AND offline_admission_id IS NULL) OR "
        "(schema_version = 'mirror.synthetic-dataset/SyntheticSourceObject/v2' "
        "AND generation_item_id IS NULL AND job_attempt_id IS NULL "
        "AND offline_admission_id IS NOT NULL)",
    )


def _install_offline_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_reject_offline_synthetic_source_admission_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'offline synthetic source admission is immutable';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_offline_synthetic_source_admissions_immutable
        BEFORE UPDATE OR DELETE ON offline_synthetic_source_admissions
        FOR EACH ROW EXECUTE FUNCTION mirror_reject_offline_synthetic_source_admission_mutation();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_generation_attempt_link() RETURNS trigger AS $$
        DECLARE
            item_record generation_items%ROWTYPE;
            batch_record generation_batches%ROWTYPE;
            admission_record offline_synthetic_source_admissions%ROWTYPE;
            attempt_job_id varchar(32);
            item_batch_id varchar(32);
        BEGIN
            IF TG_TABLE_NAME = 'synthetic_source_objects'
               AND NEW.schema_version = 'mirror.synthetic-dataset/SyntheticSourceObject/v2' THEN
                SELECT * INTO admission_record FROM offline_synthetic_source_admissions
                 WHERE id = NEW.offline_admission_id FOR UPDATE;
                IF admission_record.id IS NULL
                   OR EXISTS (
                       SELECT 1 FROM synthetic_source_object_deletion_evidence deletion
                        WHERE deletion.source_object_id = NEW.id
                   )
                   OR NEW.generation_item_id IS NOT NULL
                   OR NEW.job_attempt_id IS NOT NULL
                   OR NEW.storage_reference IS DISTINCT FROM admission_record.storage_reference
                   OR NEW.sha256 IS DISTINCT FROM admission_record.sha256
                   OR NEW.media_type IS DISTINCT FROM admission_record.media_type
                   OR NEW.byte_size IS DISTINCT FROM admission_record.byte_size
                   OR NEW.width IS DISTINCT FROM admission_record.width
                   OR NEW.height IS DISTINCT FROM admission_record.height
                   OR NEW.retention_expires_at IS DISTINCT FROM admission_record.retention_expires_at THEN
                    RAISE EXCEPTION 'offline synthetic source object differs from immutable admission';
                END IF;
                RETURN NEW;
            END IF;

            SELECT batch_id INTO item_batch_id FROM generation_items
             WHERE id = NEW.generation_item_id;
            SELECT * INTO batch_record FROM generation_batches
             WHERE id = item_batch_id FOR UPDATE;
            SELECT * INTO item_record FROM generation_items
             WHERE id = NEW.generation_item_id FOR UPDATE;
            IF item_record.batch_id IS DISTINCT FROM batch_record.id THEN
                RAISE EXCEPTION 'generation evidence item authority changed while locking';
            END IF;
            SELECT job_id INTO attempt_job_id FROM job_attempts WHERE id = NEW.job_attempt_id;
            IF attempt_job_id IS DISTINCT FROM item_record.job_id THEN
                RAISE EXCEPTION 'generation evidence attempt does not belong to item job';
            END IF;
            IF TG_TABLE_NAME = 'synthetic_source_objects' THEN
                IF NEW.schema_version <> 'mirror.synthetic-dataset/SyntheticSourceObject/v1'
                   OR NEW.offline_admission_id IS NOT NULL
                   OR item_record.status <> 'GENERATING'
                   OR NEW.media_type <> batch_record.output_media_type
                   OR NEW.byte_size > batch_record.output_max_bytes
                   OR NEW.width <> batch_record.output_width
                   OR NEW.height <> batch_record.output_height THEN
                    RAISE EXCEPTION 'synthetic source object violates generation bounds';
                END IF;
            ELSIF TG_TABLE_NAME = 'synthetic_generation_evidence' THEN
                IF NEW.provider_reference <> batch_record.provider_reference
                   OR NEW.model_reference <> batch_record.model_reference
                   OR NEW.model_version_reference <> batch_record.model_version_reference THEN
                    RAISE EXCEPTION 'generation evidence differs from pinned batch provider';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_synthetic_asset_record() RETURNS trigger AS $$
        DECLARE
            source_item_status varchar(24);
            offline_source_valid boolean;
            asset_record assets%ROWTYPE;
            allowed_transition boolean;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'NORMALIZATION_PENDING'
                   OR NEW.normalized_asset_id IS NOT NULL
                   OR NEW.normalization_started_at IS NOT NULL
                   OR NEW.normalized_at IS NOT NULL
                   OR NEW.qa_started_at IS NOT NULL
                   OR NEW.qa_finalized_at IS NOT NULL
                   OR NEW.identity_registered_at IS NOT NULL
                   OR NEW.result_code IS NOT NULL THEN
                    RAISE EXCEPTION 'synthetic asset record must start normalization pending';
                END IF;
                SELECT item.status INTO source_item_status
                  FROM synthetic_source_objects source
                  JOIN generation_items item ON item.id = source.generation_item_id
                 WHERE source.id = NEW.source_object_id FOR UPDATE OF source, item;
                SELECT EXISTS (
                    SELECT 1 FROM synthetic_source_objects source
                    JOIN offline_synthetic_source_admissions admission
                      ON admission.id = source.offline_admission_id
                    WHERE source.id = NEW.source_object_id
                      AND source.schema_version = 'mirror.synthetic-dataset/SyntheticSourceObject/v2'
                ) INTO offline_source_valid;
                IF (source_item_status IS DISTINCT FROM 'RAW_STORED' AND NOT offline_source_valid)
                   OR EXISTS (
                       SELECT 1 FROM synthetic_source_object_deletion_evidence
                        WHERE source_object_id = NEW.source_object_id
                   ) THEN
                    RAISE EXCEPTION 'normalization requires an undeleted raw-stored or offline-admitted source';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.id IS DISTINCT FROM NEW.id
               OR OLD.created_at IS DISTINCT FROM NEW.created_at
               OR OLD.schema_version IS DISTINCT FROM NEW.schema_version
               OR OLD.source_object_id IS DISTINCT FROM NEW.source_object_id
               OR OLD.normalizer_version IS DISTINCT FROM NEW.normalizer_version
               OR OLD.normalizer_config_digest IS DISTINCT FROM NEW.normalizer_config_digest THEN
                RAISE EXCEPTION 'synthetic asset record lineage is immutable';
            END IF;
            allowed_transition :=
                (OLD.status = 'NORMALIZATION_PENDING' AND NEW.status = 'NORMALIZING') OR
                (OLD.status = 'NORMALIZING' AND NEW.status IN ('NORMALIZED','NORMALIZATION_FAILED')) OR
                (OLD.status = 'NORMALIZED' AND NEW.status = 'QA_PENDING') OR
                (OLD.status = 'QA_PENDING' AND NEW.status = 'QA_RUNNING') OR
                (OLD.status = 'QA_RUNNING' AND NEW.status IN ('QA_PASSED','REJECTED','QA_FAILED')) OR
                (OLD.status = 'QA_PASSED' AND NEW.status = 'IDENTITY_REGISTERED');
            IF OLD.status IS DISTINCT FROM NEW.status AND NOT allowed_transition THEN
                RAISE EXCEPTION 'invalid synthetic asset record state transition';
            END IF;
            IF OLD.normalized_asset_id IS NOT NULL
               AND OLD.normalized_asset_id IS DISTINCT FROM NEW.normalized_asset_id THEN
                RAISE EXCEPTION 'normalized asset linkage is immutable';
            END IF;
            IF NEW.normalized_asset_id IS NOT NULL THEN
                SELECT * INTO asset_record FROM assets
                 WHERE id = NEW.normalized_asset_id FOR UPDATE;
                IF asset_record.id IS NULL
                   OR asset_record.owner_user_id IS NOT NULL
                   OR asset_record.asset_role <> 'synthetic'
                   OR NOT asset_record.synthetic
                   OR asset_record.internal_purpose <> 'synthetic_dataset'
                   OR asset_record.deleted_at IS NOT NULL THEN
                    RAISE EXCEPTION 'normalized linkage requires an active internal synthetic asset';
                END IF;
            END IF;
            IF NEW.status = 'IDENTITY_REGISTERED' AND NOT EXISTS (
                SELECT 1 FROM synthetic_identities
                 WHERE canonical_asset_id = NEW.normalized_asset_id
            ) THEN
                RAISE EXCEPTION 'identity-registered record requires canonical identity';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def upgrade() -> None:
    _create_offline_admissions()
    _alter_source_authority_union()
    _install_offline_guards()


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM offline_synthetic_source_admissions)
               OR EXISTS (
                   SELECT 1 FROM synthetic_source_objects
                    WHERE offline_admission_id IS NOT NULL
               ) THEN
                RAISE EXCEPTION '0011 downgrade would discard offline synthetic source authority';
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_offline_synthetic_source_admissions_immutable ON offline_synthetic_source_admissions"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS mirror_reject_offline_synthetic_source_admission_mutation()"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_generation_attempt_link() RETURNS trigger AS $$
        DECLARE
            item_record generation_items%ROWTYPE;
            batch_record generation_batches%ROWTYPE;
            attempt_job_id varchar(32);
            item_batch_id varchar(32);
        BEGIN
            SELECT batch_id INTO item_batch_id FROM generation_items
             WHERE id = NEW.generation_item_id;
            SELECT * INTO batch_record FROM generation_batches
             WHERE id = item_batch_id FOR UPDATE;
            SELECT * INTO item_record FROM generation_items
             WHERE id = NEW.generation_item_id FOR UPDATE;
            IF item_record.batch_id IS DISTINCT FROM batch_record.id THEN
                RAISE EXCEPTION 'generation evidence item authority changed while locking';
            END IF;
            SELECT job_id INTO attempt_job_id FROM job_attempts WHERE id = NEW.job_attempt_id;
            IF attempt_job_id IS DISTINCT FROM item_record.job_id THEN
                RAISE EXCEPTION 'generation evidence attempt does not belong to item job';
            END IF;
            IF TG_TABLE_NAME = 'synthetic_source_objects' THEN
                IF item_record.status <> 'GENERATING'
                   OR NEW.media_type <> batch_record.output_media_type
                   OR NEW.byte_size > batch_record.output_max_bytes
                   OR NEW.width <> batch_record.output_width
                   OR NEW.height <> batch_record.output_height THEN
                    RAISE EXCEPTION 'synthetic source object violates generation bounds';
                END IF;
            ELSIF TG_TABLE_NAME = 'synthetic_generation_evidence' THEN
                IF NEW.provider_reference <> batch_record.provider_reference
                   OR NEW.model_reference <> batch_record.model_reference
                   OR NEW.model_version_reference <> batch_record.model_version_reference THEN
                    RAISE EXCEPTION 'generation evidence differs from pinned batch provider';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE OR REPLACE FUNCTION mirror_validate_synthetic_asset_record() RETURNS trigger AS $$
        DECLARE
            source_item_status varchar(24);
            asset_record assets%ROWTYPE;
            allowed_transition boolean;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'NORMALIZATION_PENDING'
                   OR NEW.normalized_asset_id IS NOT NULL
                   OR NEW.normalization_started_at IS NOT NULL
                   OR NEW.normalized_at IS NOT NULL
                   OR NEW.qa_started_at IS NOT NULL
                   OR NEW.qa_finalized_at IS NOT NULL
                   OR NEW.identity_registered_at IS NOT NULL
                   OR NEW.result_code IS NOT NULL THEN
                    RAISE EXCEPTION 'synthetic asset record must start normalization pending';
                END IF;
                SELECT item.status INTO source_item_status
                  FROM synthetic_source_objects source
                  JOIN generation_items item ON item.id = source.generation_item_id
                 WHERE source.id = NEW.source_object_id FOR UPDATE OF source, item;
                IF source_item_status IS DISTINCT FROM 'RAW_STORED'
                   OR EXISTS (
                       SELECT 1 FROM synthetic_source_object_deletion_evidence
                        WHERE source_object_id = NEW.source_object_id
                   ) THEN
                    RAISE EXCEPTION 'normalization requires an undeleted raw-stored source';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.id IS DISTINCT FROM NEW.id
               OR OLD.created_at IS DISTINCT FROM NEW.created_at
               OR OLD.schema_version IS DISTINCT FROM NEW.schema_version
               OR OLD.source_object_id IS DISTINCT FROM NEW.source_object_id
               OR OLD.normalizer_version IS DISTINCT FROM NEW.normalizer_version
               OR OLD.normalizer_config_digest IS DISTINCT FROM NEW.normalizer_config_digest THEN
                RAISE EXCEPTION 'synthetic asset record lineage is immutable';
            END IF;
            allowed_transition :=
                (OLD.status = 'NORMALIZATION_PENDING' AND NEW.status = 'NORMALIZING') OR
                (OLD.status = 'NORMALIZING' AND NEW.status IN ('NORMALIZED','NORMALIZATION_FAILED')) OR
                (OLD.status = 'NORMALIZED' AND NEW.status = 'QA_PENDING') OR
                (OLD.status = 'QA_PENDING' AND NEW.status = 'QA_RUNNING') OR
                (OLD.status = 'QA_RUNNING' AND NEW.status IN ('QA_PASSED','REJECTED','QA_FAILED')) OR
                (OLD.status = 'QA_PASSED' AND NEW.status = 'IDENTITY_REGISTERED');
            IF OLD.status IS DISTINCT FROM NEW.status AND NOT allowed_transition THEN
                RAISE EXCEPTION 'invalid synthetic asset record state transition';
            END IF;
            IF OLD.normalized_asset_id IS NOT NULL
               AND OLD.normalized_asset_id IS DISTINCT FROM NEW.normalized_asset_id THEN
                RAISE EXCEPTION 'normalized asset linkage is immutable';
            END IF;
            IF NEW.normalized_asset_id IS NOT NULL THEN
                SELECT * INTO asset_record FROM assets
                 WHERE id = NEW.normalized_asset_id FOR UPDATE;
                IF asset_record.id IS NULL
                   OR asset_record.owner_user_id IS NOT NULL
                   OR asset_record.asset_role <> 'synthetic'
                   OR NOT asset_record.synthetic
                   OR asset_record.internal_purpose <> 'synthetic_dataset'
                   OR asset_record.deleted_at IS NOT NULL THEN
                    RAISE EXCEPTION 'normalized linkage requires an active internal synthetic asset';
                END IF;
            END IF;
            IF NEW.status = 'IDENTITY_REGISTERED' AND NOT EXISTS (
                SELECT 1 FROM synthetic_identities
                 WHERE canonical_asset_id = NEW.normalized_asset_id
            ) THEN
                RAISE EXCEPTION 'identity-registered record requires canonical identity';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.drop_constraint(
        op.f("ck_synthetic_source_objects_authority_shape"), "synthetic_source_objects"
    )
    op.drop_constraint(
        op.f("ck_synthetic_source_objects_schema_version"), "synthetic_source_objects"
    )
    op.create_check_constraint(
        op.f("ck_synthetic_source_objects_schema_version"),
        "synthetic_source_objects",
        "schema_version = 'mirror.synthetic-dataset/SyntheticSourceObject/v1'",
    )
    op.drop_constraint(
        op.f("uq_synthetic_source_objects_offline_admission_id"),
        "synthetic_source_objects",
        type_="unique",
    )
    op.drop_constraint(
        op.f(
            "fk_synthetic_source_objects_offline_admission_id_offline_synthetic_source_admissions"
        ),
        "synthetic_source_objects",
        type_="foreignkey",
    )
    op.drop_column("synthetic_source_objects", "offline_admission_id")
    op.alter_column(
        "synthetic_source_objects",
        "job_attempt_id",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.alter_column(
        "synthetic_source_objects",
        "generation_item_id",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.drop_table("offline_synthetic_source_admissions")
