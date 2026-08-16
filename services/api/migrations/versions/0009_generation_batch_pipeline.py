"""Add synthetic generation batch and raw evidence authority.

Revision ID: 0009_generation_batch_pipeline
Revises: 0008_synth_dataset_foundation
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_generation_batch_pipeline"
down_revision: str | None = "0008_synth_dataset_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABLE_TABLES = (
    "synthetic_source_objects",
    "synthetic_generation_evidence",
    "provider_cost_events",
    "synthetic_source_object_deletion_evidence",
)


def _create_generation_batches() -> None:
    op.create_table(
        "generation_batches",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("generation_policy_id", sa.String(length=32), nullable=False),
        sa.Column("prompt_template_id", sa.String(length=32), nullable=False),
        sa.Column("provider_reference", sa.String(length=128), nullable=False),
        sa.Column("model_reference", sa.String(length=128), nullable=False),
        sa.Column("model_version_reference", sa.String(length=128), nullable=False),
        sa.Column("pricing_snapshot_reference", sa.String(length=128), nullable=False),
        sa.Column("output_media_type", sa.String(length=32), nullable=False),
        sa.Column("output_width", sa.Integer(), nullable=False),
        sa.Column("output_height", sa.Integer(), nullable=False),
        sa.Column("output_max_bytes", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("hard_budget_micros", sa.BigInteger(), nullable=False),
        sa.Column("per_item_ceiling_micros", sa.BigInteger(), nullable=False),
        sa.Column("retry_ceiling", sa.Integer(), nullable=False),
        sa.Column("concurrency_ceiling", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/GenerationBatch/v1'",
            name=op.f("ck_generation_batches_schema_version"),
        ),
        sa.CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_generation_batches_idempotency_digest"),
        ),
        sa.CheckConstraint(
            "output_media_type IN ('image/jpeg','image/png','image/webp')",
            name=op.f("ck_generation_batches_output_media_type"),
        ),
        sa.CheckConstraint(
            "output_width > 0 AND output_height > 0 AND output_max_bytes > 0",
            name=op.f("ck_generation_batches_positive_output_bounds"),
        ),
        sa.CheckConstraint(
            "item_count > 0 AND item_count <= 10000",
            name=op.f("ck_generation_batches_item_count"),
        ),
        sa.CheckConstraint(
            "currency IN ('CNY','USD')", name=op.f("ck_generation_batches_currency")
        ),
        sa.CheckConstraint(
            "hard_budget_micros >= 0 AND per_item_ceiling_micros >= 0 "
            "AND per_item_ceiling_micros * item_count <= hard_budget_micros",
            name=op.f("ck_generation_batches_budget_shape"),
        ),
        sa.CheckConstraint(
            "retry_ceiling >= 0 AND retry_ceiling <= 20",
            name=op.f("ck_generation_batches_retry_ceiling"),
        ),
        sa.CheckConstraint(
            "concurrency_ceiling > 0 AND concurrency_ceiling <= item_count",
            name=op.f("ck_generation_batches_concurrency_ceiling"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','QUEUED','RUNNING','COMPLETED','PARTIAL','FAILED','CANCELLED')",
            name=op.f("ck_generation_batches_status"),
        ),
        sa.CheckConstraint(
            "(status = 'DRAFT' AND queued_at IS NULL AND started_at IS NULL "
            "AND finalized_at IS NULL) OR "
            "(status = 'QUEUED' AND queued_at IS NOT NULL AND started_at IS NULL "
            "AND finalized_at IS NULL) OR "
            "(status = 'RUNNING' AND queued_at IS NOT NULL AND started_at IS NOT NULL "
            "AND finalized_at IS NULL) OR "
            "(status IN ('COMPLETED','PARTIAL','FAILED','CANCELLED') "
            "AND queued_at IS NOT NULL AND finalized_at IS NOT NULL)",
            name=op.f("ck_generation_batches_status_timestamps"),
        ),
        sa.CheckConstraint(
            "(queued_at IS NULL OR queued_at >= created_at) AND "
            "(started_at IS NULL OR (queued_at IS NOT NULL AND started_at >= queued_at)) AND "
            "(finalized_at IS NULL OR finalized_at >= COALESCE(started_at, queued_at)) AND "
            "(cancel_requested_at IS NULL OR cancel_requested_at >= created_at)",
            name=op.f("ck_generation_batches_timestamp_order"),
        ),
        sa.ForeignKeyConstraint(
            ["generation_policy_id"],
            ["synthetic_generation_policies.id"],
            name=op.f("fk_generation_batches_generation_policy_id_synthetic_generation_policies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_template_id"],
            ["synthetic_prompt_templates.id"],
            name=op.f("fk_generation_batches_prompt_template_id_synthetic_prompt_templates"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_batches")),
        sa.UniqueConstraint(
            "idempotency_key_hash", name=op.f("uq_generation_batches_idempotency_key_hash")
        ),
    )
    op.create_index(
        op.f("ix_generation_batches_generation_policy_id"),
        "generation_batches",
        ["generation_policy_id"],
    )
    op.create_index(
        op.f("ix_generation_batches_prompt_template_id"),
        "generation_batches",
        ["prompt_template_id"],
    )


def _create_generation_items() -> None:
    op.create_check_constraint(
        op.f("ck_jobs_synthetic_generation_envelope"),
        "jobs",
        "job_type <> 'synthetic_generation' OR "
        "(owner_user_id IS NULL AND ingestion_upload_intent_id IS NULL "
        "AND result_asset_id IS NULL AND payload::jsonb = '{}'::jsonb)",
    )
    op.create_table(
        "generation_items",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("batch_id", sa.String(length=32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("request_reference", sa.String(length=128), nullable=False),
        sa.Column("requested_seed", sa.BigInteger(), nullable=True),
        sa.Column("reserved_budget_micros", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_code", sa.String(length=64), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/GenerationItem/v1'",
            name=op.f("ck_generation_items_schema_version"),
        ),
        sa.CheckConstraint("ordinal >= 0", name=op.f("ck_generation_items_ordinal")),
        sa.CheckConstraint(
            "requested_seed IS NULL OR requested_seed BETWEEN 0 AND 9223372036854775807",
            name=op.f("ck_generation_items_requested_seed"),
        ),
        sa.CheckConstraint(
            "reserved_budget_micros >= 0",
            name=op.f("ck_generation_items_reserved_budget"),
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED','GENERATING','RAW_STORED','GENERATION_FAILED','CANCELLED')",
            name=op.f("ck_generation_items_status"),
        ),
        sa.CheckConstraint(
            "(status = 'REQUESTED' AND started_at IS NULL AND finalized_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status = 'GENERATING' AND started_at IS NOT NULL AND finalized_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status IN ('RAW_STORED','GENERATION_FAILED','CANCELLED') "
            "AND finalized_at IS NOT NULL AND result_code IS NOT NULL)",
            name=op.f("ck_generation_items_status_shape"),
        ),
        sa.CheckConstraint(
            "result_code IS NULL OR result_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_generation_items_result_code"),
        ),
        sa.CheckConstraint(
            "(started_at IS NULL OR started_at >= created_at) AND "
            "(finalized_at IS NULL OR finalized_at >= COALESCE(started_at, created_at))",
            name=op.f("ck_generation_items_timestamp_order"),
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["generation_batches.id"],
            name=op.f("fk_generation_items_batch_id_generation_batches"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_generation_items_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_items")),
        sa.UniqueConstraint("batch_id", "ordinal", name="unique_batch_ordinal"),
        sa.UniqueConstraint("job_id", name=op.f("uq_generation_items_job_id")),
        sa.UniqueConstraint(
            "request_reference", name=op.f("uq_generation_items_request_reference")
        ),
    )
    op.create_index(op.f("ix_generation_items_batch_id"), "generation_items", ["batch_id"])


def _create_evidence_tables() -> None:
    op.create_table(
        "synthetic_source_objects",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("generation_item_id", sa.String(length=32), nullable=False),
        sa.Column("job_attempt_id", sa.String(length=32), nullable=False),
        sa.Column("storage_reference", sa.String(length=128), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=32), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticSourceObject/v1'",
            name=op.f("ck_synthetic_source_objects_schema_version"),
        ),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_synthetic_source_objects_sha256")
        ),
        sa.CheckConstraint(
            "media_type IN ('image/jpeg','image/png','image/webp')",
            name=op.f("ck_synthetic_source_objects_media_type"),
        ),
        sa.CheckConstraint(
            "byte_size > 0 AND width > 0 AND height > 0",
            name=op.f("ck_synthetic_source_objects_positive_metadata"),
        ),
        sa.CheckConstraint(
            "storage_reference ~ '^[a-z0-9][a-z0-9._:-]{2,127}$'",
            name=op.f("ck_synthetic_source_objects_storage_reference"),
        ),
        sa.CheckConstraint(
            "retention_expires_at > created_at",
            name=op.f("ck_synthetic_source_objects_retention"),
        ),
        sa.ForeignKeyConstraint(
            ["generation_item_id"],
            ["generation_items.id"],
            name=op.f("fk_synthetic_source_objects_generation_item_id_generation_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_attempt_id"],
            ["job_attempts.id"],
            name=op.f("fk_synthetic_source_objects_job_attempt_id_job_attempts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_synthetic_source_objects")),
        sa.UniqueConstraint(
            "generation_item_id", name=op.f("uq_synthetic_source_objects_generation_item_id")
        ),
        sa.UniqueConstraint(
            "job_attempt_id", name=op.f("uq_synthetic_source_objects_job_attempt_id")
        ),
        sa.UniqueConstraint(
            "storage_reference", name=op.f("uq_synthetic_source_objects_storage_reference")
        ),
    )
    op.create_table(
        "synthetic_generation_evidence",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("generation_item_id", sa.String(length=32), nullable=False),
        sa.Column("job_attempt_id", sa.String(length=32), nullable=False),
        sa.Column("provider_reference", sa.String(length=128), nullable=False),
        sa.Column("model_reference", sa.String(length=128), nullable=False),
        sa.Column("model_version_reference", sa.String(length=128), nullable=False),
        sa.Column("provider_run_reference", sa.String(length=128), nullable=False),
        sa.Column("safety_policy_reference", sa.String(length=128), nullable=False),
        sa.Column("safety_outcome", sa.String(length=16), nullable=False),
        sa.Column("safety_reason_code", sa.String(length=64), nullable=False),
        sa.Column("retention_status", sa.String(length=32), nullable=False),
        sa.Column("output_rights", sa.String(length=40), nullable=False),
        sa.Column("provider_actual_seed", sa.BigInteger(), nullable=True),
        sa.Column("provider_actual_parameters", sa.JSON(), nullable=False),
        sa.Column("reproducibility_level", sa.String(length=24), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticGenerationEvidence/v1'",
            name=op.f("ck_synthetic_generation_evidence_schema_version"),
        ),
        sa.CheckConstraint(
            "safety_outcome IN ('passed','rejected')",
            name=op.f("ck_synthetic_generation_evidence_safety_outcome"),
        ),
        sa.CheckConstraint(
            "safety_reason_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_synthetic_generation_evidence_safety_reason_code"),
        ),
        sa.CheckConstraint(
            "retention_status IN ('not_retained','contractually_bounded')",
            name=op.f("ck_synthetic_generation_evidence_retention_status"),
        ),
        sa.CheckConstraint(
            "output_rights IN ('internal_evaluation_only','synthetic_release_permitted')",
            name=op.f("ck_synthetic_generation_evidence_output_rights"),
        ),
        sa.CheckConstraint(
            "provider_actual_seed IS NULL OR provider_actual_seed BETWEEN 0 AND 9223372036854775807",
            name=op.f("ck_synthetic_generation_evidence_provider_seed"),
        ),
        sa.CheckConstraint(
            "json_typeof(provider_actual_parameters) = 'object'",
            name=op.f("ck_synthetic_generation_evidence_parameters_object"),
        ),
        sa.CheckConstraint(
            "reproducibility_level IN ('BIT_EXACT','SEED_REPLAYABLE','PROVENANCE_ONLY')",
            name=op.f("ck_synthetic_generation_evidence_reproducibility"),
        ),
        sa.ForeignKeyConstraint(
            ["generation_item_id"],
            ["generation_items.id"],
            name=op.f("fk_synthetic_generation_evidence_generation_item_id_generation_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_attempt_id"],
            ["job_attempts.id"],
            name=op.f("fk_synthetic_generation_evidence_job_attempt_id_job_attempts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_synthetic_generation_evidence")),
        sa.UniqueConstraint(
            "job_attempt_id", name=op.f("uq_synthetic_generation_evidence_job_attempt_id")
        ),
    )
    op.create_index(
        op.f("ix_synthetic_generation_evidence_generation_item_id"),
        "synthetic_generation_evidence",
        ["generation_item_id"],
    )
    op.create_table(
        "provider_cost_events",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("generation_item_id", sa.String(length=32), nullable=False),
        sa.Column("job_attempt_id", sa.String(length=32), nullable=False),
        sa.Column("event_kind", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("pricing_snapshot_reference", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/ProviderCostEvent/v1'",
            name=op.f("ck_provider_cost_events_schema_version"),
        ),
        sa.CheckConstraint(
            "event_kind IN ('estimated','final')",
            name=op.f("ck_provider_cost_events_event_kind"),
        ),
        sa.CheckConstraint(
            "currency IN ('CNY','USD')", name=op.f("ck_provider_cost_events_currency")
        ),
        sa.CheckConstraint("amount_micros >= 0", name=op.f("ck_provider_cost_events_amount")),
        sa.ForeignKeyConstraint(
            ["generation_item_id"],
            ["generation_items.id"],
            name=op.f("fk_provider_cost_events_generation_item_id_generation_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_attempt_id"],
            ["job_attempts.id"],
            name=op.f("fk_provider_cost_events_job_attempt_id_job_attempts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_cost_events")),
        sa.UniqueConstraint("job_attempt_id", name="unique_attempt_cost"),
    )
    op.create_index(
        op.f("ix_provider_cost_events_generation_item_id"),
        "provider_cost_events",
        ["generation_item_id"],
    )
    op.create_index(
        op.f("ix_provider_cost_events_job_attempt_id"),
        "provider_cost_events",
        ["job_attempt_id"],
    )
    op.create_table(
        "synthetic_source_object_deletion_evidence",
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("source_object_id", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("deletion_result", sa.String(length=16), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_reference", sa.String(length=128), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticSourceObjectDeletionEvidence/v1'",
            name=op.f("ck_synthetic_source_object_deletion_evidence_schema_version"),
        ),
        sa.CheckConstraint(
            "reason_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_synthetic_source_object_deletion_evidence_reason_code"),
        ),
        sa.CheckConstraint(
            "deletion_result IN ('deleted','not_found')",
            name=op.f("ck_synthetic_source_object_deletion_evidence_deletion_result"),
        ),
        sa.CheckConstraint(
            "actor_kind IN ('system','operator')",
            name=op.f("ck_synthetic_source_object_deletion_evidence_actor_kind"),
        ),
        sa.CheckConstraint(
            "(actor_kind = 'system' AND actor_reference IS NULL) OR "
            "(actor_kind = 'operator' AND actor_reference IS NOT NULL)",
            name=op.f("ck_synthetic_source_object_deletion_evidence_actor_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["source_object_id"],
            ["synthetic_source_objects.id"],
            name=op.f(
                "fk_synthetic_source_object_deletion_evidence_source_object_id_synthetic_source_objects"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_synthetic_source_object_deletion_evidence")),
        sa.UniqueConstraint(
            "source_object_id",
            name=op.f("uq_synthetic_source_object_deletion_evidence_source_object_id"),
        ),
    )


def _install_batch_item_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_validate_generation_batch() RETURNS trigger AS $$
        DECLARE
            generation_status text;
            prompt_status text;
            actual_item_count bigint;
            reserved_budget bigint;
            active_item_count bigint;
            raw_item_count bigint;
            failed_item_count bigint;
            cancelled_item_count bigint;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'DRAFT' THEN
                    RAISE EXCEPTION 'generation batch must be inserted as DRAFT';
                END IF;
                SELECT approval_status INTO generation_status
                  FROM synthetic_generation_policies WHERE id = NEW.generation_policy_id;
                SELECT approval_status INTO prompt_status
                  FROM synthetic_prompt_templates WHERE id = NEW.prompt_template_id;
                IF generation_status <> 'APPROVED' OR prompt_status <> 'APPROVED' THEN
                    RAISE EXCEPTION 'generation batch requires approved policy and prompt';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.schema_version IS DISTINCT FROM NEW.schema_version
               OR OLD.idempotency_key_hash IS DISTINCT FROM NEW.idempotency_key_hash
               OR OLD.generation_policy_id IS DISTINCT FROM NEW.generation_policy_id
               OR OLD.prompt_template_id IS DISTINCT FROM NEW.prompt_template_id
               OR OLD.provider_reference IS DISTINCT FROM NEW.provider_reference
               OR OLD.model_reference IS DISTINCT FROM NEW.model_reference
               OR OLD.model_version_reference IS DISTINCT FROM NEW.model_version_reference
               OR OLD.pricing_snapshot_reference IS DISTINCT FROM NEW.pricing_snapshot_reference
               OR OLD.output_media_type IS DISTINCT FROM NEW.output_media_type
               OR OLD.output_width IS DISTINCT FROM NEW.output_width
               OR OLD.output_height IS DISTINCT FROM NEW.output_height
               OR OLD.output_max_bytes IS DISTINCT FROM NEW.output_max_bytes
               OR OLD.item_count IS DISTINCT FROM NEW.item_count
               OR OLD.currency IS DISTINCT FROM NEW.currency
               OR OLD.hard_budget_micros IS DISTINCT FROM NEW.hard_budget_micros
               OR OLD.per_item_ceiling_micros IS DISTINCT FROM NEW.per_item_ceiling_micros
               OR OLD.retry_ceiling IS DISTINCT FROM NEW.retry_ceiling
               OR OLD.concurrency_ceiling IS DISTINCT FROM NEW.concurrency_ceiling
               OR OLD.id IS DISTINCT FROM NEW.id
               OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
                RAISE EXCEPTION 'generation batch configuration is immutable';
            END IF;
            IF OLD.cancel_requested_at IS NOT NULL
               AND OLD.cancel_requested_at IS DISTINCT FROM NEW.cancel_requested_at THEN
                RAISE EXCEPTION 'generation batch cancellation request is immutable';
            END IF;
            IF OLD.status = NEW.status THEN
                RETURN NEW;
            END IF;
            IF NOT (
                (OLD.status = 'DRAFT' AND NEW.status = 'QUEUED') OR
                (OLD.status = 'QUEUED' AND NEW.status IN ('RUNNING','FAILED','CANCELLED')) OR
                (OLD.status = 'RUNNING' AND NEW.status IN
                    ('COMPLETED','PARTIAL','FAILED','CANCELLED'))
            ) THEN
                RAISE EXCEPTION 'invalid generation batch transition';
            END IF;
            IF NEW.status = 'QUEUED' THEN
                PERFORM 1 FROM generation_items WHERE batch_id = NEW.id FOR UPDATE;
                SELECT COUNT(*), COALESCE(SUM(reserved_budget_micros), 0)
                  INTO actual_item_count, reserved_budget
                  FROM generation_items WHERE batch_id = NEW.id;
                IF actual_item_count <> NEW.item_count THEN
                    RAISE EXCEPTION 'generation batch requires its complete item set before queueing';
                END IF;
                IF reserved_budget > NEW.hard_budget_micros THEN
                    RAISE EXCEPTION 'generation batch item reservations exceed hard budget';
                END IF;
            END IF;
            IF NEW.status IN ('COMPLETED','PARTIAL','FAILED','CANCELLED') THEN
                PERFORM 1 FROM generation_items WHERE batch_id = NEW.id FOR UPDATE;
                SELECT
                    COUNT(*) FILTER (WHERE status IN ('REQUESTED','GENERATING')),
                    COUNT(*) FILTER (WHERE status = 'RAW_STORED'),
                    COUNT(*) FILTER (WHERE status = 'GENERATION_FAILED'),
                    COUNT(*) FILTER (WHERE status = 'CANCELLED')
                  INTO active_item_count, raw_item_count, failed_item_count,
                       cancelled_item_count
                  FROM generation_items WHERE batch_id = NEW.id;
                IF active_item_count <> 0 THEN
                    RAISE EXCEPTION 'terminal generation batch requires quiescent items';
                END IF;
                IF NEW.status = 'COMPLETED' AND raw_item_count <> NEW.item_count THEN
                    RAISE EXCEPTION 'completed generation batch requires all items raw stored';
                ELSIF NEW.status = 'FAILED' AND failed_item_count <> NEW.item_count THEN
                    RAISE EXCEPTION 'failed generation batch requires all items generation failed';
                ELSIF NEW.status = 'PARTIAL'
                      AND NOT (raw_item_count > 0 AND raw_item_count < NEW.item_count) THEN
                    RAISE EXCEPTION 'partial generation batch requires mixed terminal outcomes';
                ELSIF NEW.status = 'CANCELLED'
                      AND (NEW.cancel_requested_at IS NULL OR
                           raw_item_count + failed_item_count + cancelled_item_count
                           <> NEW.item_count) THEN
                    RAISE EXCEPTION 'cancelled generation batch requires cancellation and terminal items';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_generation_batches_guard
        BEFORE INSERT OR UPDATE ON generation_batches
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_generation_batch();
        CREATE TRIGGER trg_generation_batches_immutable_delete
        BEFORE DELETE ON generation_batches
        FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_generation_item() RETURNS trigger AS $$
        DECLARE
            batch_record generation_batches%ROWTYPE;
            job_record jobs%ROWTYPE;
            successful_attempt_id varchar(32);
            attempt_status varchar(24);
            attempt_result_code varchar(64);
            attempt_error_code varchar(64);
            attempt_finished_at timestamptz;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                SELECT * INTO batch_record FROM generation_batches
                 WHERE id = NEW.batch_id FOR UPDATE;
                SELECT * INTO job_record FROM jobs WHERE id = NEW.job_id FOR UPDATE;
                IF NEW.status <> 'REQUESTED' THEN
                    RAISE EXCEPTION 'generation item must be inserted as REQUESTED';
                END IF;
                IF batch_record.status <> 'DRAFT' THEN
                    RAISE EXCEPTION 'generation items can only be added to DRAFT batches';
                END IF;
                IF NEW.ordinal >= batch_record.item_count
                   OR NEW.reserved_budget_micros > batch_record.per_item_ceiling_micros THEN
                    RAISE EXCEPTION 'generation item exceeds batch bounds';
                END IF;
                IF job_record.job_type <> 'synthetic_generation'
                   OR job_record.owner_user_id IS NOT NULL
                   OR job_record.payload::jsonb <> '{}'::jsonb THEN
                    RAISE EXCEPTION 'generation item requires an ownerless reference-only job';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.schema_version IS DISTINCT FROM NEW.schema_version
               OR OLD.batch_id IS DISTINCT FROM NEW.batch_id
               OR OLD.ordinal IS DISTINCT FROM NEW.ordinal
               OR OLD.job_id IS DISTINCT FROM NEW.job_id
               OR OLD.request_reference IS DISTINCT FROM NEW.request_reference
               OR OLD.requested_seed IS DISTINCT FROM NEW.requested_seed
               OR OLD.reserved_budget_micros IS DISTINCT FROM NEW.reserved_budget_micros
               OR OLD.id IS DISTINCT FROM NEW.id
               OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
                RAISE EXCEPTION 'generation item authority is immutable';
            END IF;
            IF OLD.status = NEW.status THEN
                RETURN NEW;
            END IF;
            IF NOT (
                (OLD.status = 'REQUESTED' AND NEW.status IN ('GENERATING','CANCELLED')) OR
                (OLD.status = 'GENERATING' AND NEW.status IN
                    ('RAW_STORED','GENERATION_FAILED','CANCELLED'))
            ) THEN
                RAISE EXCEPTION 'invalid generation item transition';
            END IF;
            IF NEW.status = 'RAW_STORED' THEN
                SELECT source.job_attempt_id
                  INTO successful_attempt_id
                  FROM synthetic_source_objects source
                  JOIN synthetic_generation_evidence evidence
                    ON evidence.generation_item_id = source.generation_item_id
                   AND evidence.job_attempt_id = source.job_attempt_id
                  JOIN provider_cost_events cost
                    ON cost.generation_item_id = source.generation_item_id
                   AND cost.job_attempt_id = source.job_attempt_id
                 WHERE source.generation_item_id = NEW.id
                   AND evidence.safety_outcome = 'passed';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'raw stored item requires complete source evidence and cost chain';
                END IF;
                SELECT status, result_code, error_code, finished_at
                  INTO attempt_status, attempt_result_code, attempt_error_code,
                       attempt_finished_at
                  FROM job_attempts WHERE id = successful_attempt_id FOR UPDATE;
                IF attempt_status <> 'raw_stored'
                   OR attempt_finished_at IS NULL
                   OR attempt_error_code IS NOT NULL
                   OR attempt_result_code IS DISTINCT FROM NEW.result_code THEN
                    RAISE EXCEPTION 'raw stored item requires its matching successful attempt';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_generation_items_guard
        BEFORE INSERT OR UPDATE ON generation_items
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_generation_item();
        CREATE TRIGGER trg_generation_items_immutable_delete
        BEFORE DELETE ON generation_items
        FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();
        """
    )


def _install_evidence_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_validate_generation_attempt_link() RETURNS trigger AS $$
        DECLARE
            item_record generation_items%ROWTYPE;
            batch_record generation_batches%ROWTYPE;
            attempt_job_id varchar(32);
        BEGIN
            SELECT * INTO item_record FROM generation_items
             WHERE id = NEW.generation_item_id FOR UPDATE;
            SELECT * INTO batch_record FROM generation_batches
             WHERE id = item_record.batch_id FOR UPDATE;
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

        CREATE TRIGGER trg_synthetic_source_objects_link
        BEFORE INSERT ON synthetic_source_objects
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_generation_attempt_link();
        CREATE TRIGGER trg_synthetic_generation_evidence_link
        BEFORE INSERT ON synthetic_generation_evidence
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_generation_attempt_link();
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_provider_cost_event() RETURNS trigger AS $$
        DECLARE
            item_record generation_items%ROWTYPE;
            batch_record generation_batches%ROWTYPE;
            attempt_job_id varchar(32);
            item_spend bigint;
            batch_spend bigint;
        BEGIN
            SELECT * INTO item_record FROM generation_items
             WHERE id = NEW.generation_item_id FOR UPDATE;
            SELECT * INTO batch_record FROM generation_batches
             WHERE id = item_record.batch_id FOR UPDATE;
            SELECT job_id INTO attempt_job_id FROM job_attempts WHERE id = NEW.job_attempt_id;
            IF attempt_job_id IS DISTINCT FROM item_record.job_id THEN
                RAISE EXCEPTION 'provider cost attempt does not belong to item job';
            END IF;
            IF NEW.currency <> batch_record.currency
               OR NEW.pricing_snapshot_reference <> batch_record.pricing_snapshot_reference THEN
                RAISE EXCEPTION 'provider cost differs from pinned batch pricing';
            END IF;
            SELECT COALESCE(SUM(amount_micros), 0) INTO item_spend
              FROM provider_cost_events WHERE generation_item_id = item_record.id;
            SELECT COALESCE(SUM(cost.amount_micros), 0) INTO batch_spend
              FROM provider_cost_events cost
              JOIN generation_items item ON item.id = cost.generation_item_id
             WHERE item.batch_id = batch_record.id;
            IF item_spend + NEW.amount_micros > item_record.reserved_budget_micros
               OR batch_spend + NEW.amount_micros > batch_record.hard_budget_micros THEN
                RAISE EXCEPTION 'provider cost exceeds reserved budget';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_provider_cost_events_budget
        BEFORE INSERT ON provider_cost_events
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_provider_cost_event();
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_source_deletion_evidence() RETURNS trigger AS $$
        DECLARE
            source_record synthetic_source_objects%ROWTYPE;
        BEGIN
            SELECT * INTO source_record FROM synthetic_source_objects
             WHERE id = NEW.source_object_id FOR UPDATE;
            IF NEW.reason_code = 'retention_expired'
               AND NEW.deleted_at < source_record.retention_expires_at THEN
                RAISE EXCEPTION 'source object retention has not expired';
            END IF;
            IF NEW.deleted_at < source_record.created_at THEN
                RAISE EXCEPTION 'source deletion predates source creation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_source_deletion_evidence_guard
        BEFORE INSERT ON synthetic_source_object_deletion_evidence
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_source_deletion_evidence();
        """
    )
    for table_name in _IMMUTABLE_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_immutable "
            f"BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();"
        )


def upgrade() -> None:
    _create_generation_batches()
    _create_generation_items()
    _create_evidence_tables()
    _install_batch_item_guards()
    _install_evidence_guards()


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM generation_batches)
               OR EXISTS (SELECT 1 FROM generation_items)
               OR EXISTS (SELECT 1 FROM synthetic_source_objects)
               OR EXISTS (SELECT 1 FROM synthetic_generation_evidence)
               OR EXISTS (SELECT 1 FROM provider_cost_events)
               OR EXISTS (SELECT 1 FROM synthetic_source_object_deletion_evidence) THEN
                RAISE EXCEPTION '0009 downgrade would discard generation authority or evidence';
            END IF;
        END;
        $$;
        """
    )
    for table_name in _IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON {table_name}")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_source_deletion_evidence_guard "
        "ON synthetic_source_object_deletion_evidence"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_provider_cost_events_budget ON provider_cost_events")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_generation_evidence_link "
        "ON synthetic_generation_evidence"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_source_objects_link ON synthetic_source_objects"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_generation_items_guard ON generation_items")
    op.execute("DROP TRIGGER IF EXISTS trg_generation_items_immutable_delete ON generation_items")
    op.execute("DROP TRIGGER IF EXISTS trg_generation_batches_guard ON generation_batches")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_generation_batches_immutable_delete ON generation_batches"
    )
    op.drop_table("synthetic_source_object_deletion_evidence")
    op.drop_table("provider_cost_events")
    op.drop_index(
        op.f("ix_synthetic_generation_evidence_generation_item_id"),
        table_name="synthetic_generation_evidence",
    )
    op.drop_table("synthetic_generation_evidence")
    op.drop_table("synthetic_source_objects")
    op.drop_index(op.f("ix_generation_items_batch_id"), table_name="generation_items")
    op.drop_table("generation_items")
    op.drop_constraint(op.f("ck_jobs_synthetic_generation_envelope"), "jobs", type_="check")
    op.drop_index(op.f("ix_generation_batches_prompt_template_id"), table_name="generation_batches")
    op.drop_index(
        op.f("ix_generation_batches_generation_policy_id"), table_name="generation_batches"
    )
    op.drop_table("generation_batches")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_source_deletion_evidence()")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_provider_cost_event()")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_generation_attempt_link()")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_generation_item()")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_generation_batch()")
