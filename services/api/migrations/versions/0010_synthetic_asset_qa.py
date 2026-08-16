"""Add synthetic normalization, QA, and canonical identity authority.

Revision ID: 0010_synthetic_asset_qa
Revises: 0009_generation_batch_pipeline
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_synthetic_asset_qa"
down_revision: str | None = "0009_generation_batch_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_synthetic_asset_records() -> None:
    op.create_table(
        "synthetic_asset_records",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("source_object_id", sa.String(length=32), nullable=False),
        sa.Column("normalized_asset_id", sa.String(length=32), nullable=True),
        sa.Column("normalizer_version", sa.String(length=64), nullable=False),
        sa.Column("normalizer_config_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_code", sa.String(length=64), nullable=True),
        sa.Column("normalization_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("normalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qa_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qa_finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("identity_registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticAssetRecord/v1'",
            name=op.f("ck_synthetic_asset_records_schema_version"),
        ),
        sa.CheckConstraint(
            "normalizer_version ~ '^[a-z][a-z0-9._-]{2,63}$'",
            name=op.f("ck_synthetic_asset_records_normalizer_version"),
        ),
        sa.CheckConstraint(
            "normalizer_config_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_synthetic_asset_records_normalizer_config_digest"),
        ),
        sa.CheckConstraint(
            "status IN ('NORMALIZATION_PENDING','NORMALIZING','NORMALIZED',"
            "'NORMALIZATION_FAILED','QA_PENDING','QA_RUNNING','QA_PASSED','REJECTED',"
            "'QA_FAILED','IDENTITY_REGISTERED')",
            name=op.f("ck_synthetic_asset_records_status"),
        ),
        sa.CheckConstraint(
            "result_code IS NULL OR result_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_synthetic_asset_records_result_code"),
        ),
        sa.CheckConstraint(
            "(status IN ('NORMALIZATION_PENDING','NORMALIZING','NORMALIZATION_FAILED') "
            "AND normalized_asset_id IS NULL) OR "
            "(status IN ('NORMALIZED','QA_PENDING','QA_RUNNING','QA_PASSED','REJECTED',"
            "'QA_FAILED','IDENTITY_REGISTERED') AND normalized_asset_id IS NOT NULL)",
            name=op.f("ck_synthetic_asset_records_normalized_asset_shape"),
        ),
        sa.CheckConstraint(
            "(status = 'NORMALIZATION_PENDING' AND normalization_started_at IS NULL "
            "AND normalized_at IS NULL AND qa_started_at IS NULL AND qa_finalized_at IS NULL "
            "AND identity_registered_at IS NULL AND result_code IS NULL) OR "
            "(status = 'NORMALIZING' AND normalization_started_at IS NOT NULL "
            "AND normalized_at IS NULL AND qa_started_at IS NULL AND qa_finalized_at IS NULL "
            "AND identity_registered_at IS NULL AND result_code IS NULL) OR "
            "(status = 'NORMALIZATION_FAILED' AND normalization_started_at IS NOT NULL "
            "AND normalized_at IS NULL AND qa_started_at IS NULL AND qa_finalized_at IS NULL "
            "AND identity_registered_at IS NULL AND result_code IS NOT NULL) OR "
            "(status IN ('NORMALIZED','QA_PENDING') AND normalization_started_at IS NOT NULL "
            "AND normalized_at IS NOT NULL AND qa_started_at IS NULL AND qa_finalized_at IS NULL "
            "AND identity_registered_at IS NULL AND result_code IS NULL) OR "
            "(status = 'QA_RUNNING' AND normalization_started_at IS NOT NULL "
            "AND normalized_at IS NOT NULL AND qa_started_at IS NOT NULL "
            "AND qa_finalized_at IS NULL AND identity_registered_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status = 'QA_PASSED' AND normalization_started_at IS NOT NULL "
            "AND normalized_at IS NOT NULL AND qa_started_at IS NOT NULL "
            "AND qa_finalized_at IS NOT NULL AND identity_registered_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status IN ('REJECTED','QA_FAILED') AND normalization_started_at IS NOT NULL "
            "AND normalized_at IS NOT NULL AND qa_started_at IS NOT NULL "
            "AND qa_finalized_at IS NOT NULL AND identity_registered_at IS NULL "
            "AND result_code IS NOT NULL) OR "
            "(status = 'IDENTITY_REGISTERED' AND normalization_started_at IS NOT NULL "
            "AND normalized_at IS NOT NULL AND qa_started_at IS NOT NULL "
            "AND qa_finalized_at IS NOT NULL AND identity_registered_at IS NOT NULL "
            "AND result_code IS NULL)",
            name=op.f("ck_synthetic_asset_records_status_shape"),
        ),
        sa.CheckConstraint(
            "(normalization_started_at IS NULL OR normalization_started_at >= created_at) AND "
            "(normalized_at IS NULL OR normalized_at >= normalization_started_at) AND "
            "(qa_started_at IS NULL OR qa_started_at >= normalized_at) AND "
            "(qa_finalized_at IS NULL OR qa_finalized_at >= qa_started_at) AND "
            "(identity_registered_at IS NULL OR identity_registered_at >= qa_finalized_at)",
            name=op.f("ck_synthetic_asset_records_timestamp_order"),
        ),
        sa.ForeignKeyConstraint(
            ["source_object_id"],
            ["synthetic_source_objects.id"],
            name=op.f("fk_synthetic_asset_records_source_object_id_synthetic_source_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["normalized_asset_id"],
            ["assets.id"],
            name=op.f("fk_synthetic_asset_records_normalized_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_synthetic_asset_records")),
        sa.UniqueConstraint(
            "source_object_id", name=op.f("uq_synthetic_asset_records_source_object_id")
        ),
        sa.UniqueConstraint(
            "normalized_asset_id", name=op.f("uq_synthetic_asset_records_normalized_asset_id")
        ),
    )


def _create_synthetic_qa_tables() -> None:
    op.create_table(
        "synthetic_qa_runs",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("synthetic_asset_record_id", sa.String(length=32), nullable=False),
        sa.Column("normalized_asset_id", sa.String(length=32), nullable=False),
        sa.Column("qa_policy_id", sa.String(length=32), nullable=False),
        sa.Column("vision_provider_reference", sa.String(length=128), nullable=True),
        sa.Column("vision_algorithm_reference", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticQARun/v1'",
            name=op.f("ck_synthetic_qa_runs_schema_version"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','PASSED','REJECTED','FAILED')",
            name=op.f("ck_synthetic_qa_runs_status"),
        ),
        sa.CheckConstraint(
            "result_code IS NULL OR result_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_synthetic_qa_runs_result_code"),
        ),
        sa.CheckConstraint(
            "(status IN ('PENDING','RUNNING','PASSED') AND result_code IS NULL) OR "
            "(status IN ('REJECTED','FAILED') AND result_code IS NOT NULL)",
            name=op.f("ck_synthetic_qa_runs_result_shape"),
        ),
        sa.CheckConstraint(
            "(status = 'PENDING' AND started_at IS NULL AND finalized_at IS NULL) OR "
            "(status = 'RUNNING' AND started_at IS NOT NULL AND finalized_at IS NULL) OR "
            "(status IN ('PASSED','REJECTED','FAILED') AND started_at IS NOT NULL "
            "AND finalized_at IS NOT NULL)",
            name=op.f("ck_synthetic_qa_runs_timestamp_shape"),
        ),
        sa.CheckConstraint(
            "finalized_at IS NULL OR finalized_at >= started_at",
            name=op.f("ck_synthetic_qa_runs_timestamp_order"),
        ),
        sa.ForeignKeyConstraint(
            ["synthetic_asset_record_id"],
            ["synthetic_asset_records.id"],
            name=op.f("fk_synthetic_qa_runs_synthetic_asset_record_id_synthetic_asset_records"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["normalized_asset_id"],
            ["assets.id"],
            name=op.f("fk_synthetic_qa_runs_normalized_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["qa_policy_id"],
            ["synthetic_qa_policies.id"],
            name=op.f("fk_synthetic_qa_runs_qa_policy_id_synthetic_qa_policies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_synthetic_qa_runs")),
        sa.UniqueConstraint(
            "normalized_asset_id",
            "qa_policy_id",
            name=op.f("uq_synthetic_qa_runs_unique_asset_policy"),
        ),
    )
    op.create_index(
        op.f("ix_synthetic_qa_runs_synthetic_asset_record_id"),
        "synthetic_qa_runs",
        ["synthetic_asset_record_id"],
    )
    op.create_index(
        op.f("ix_synthetic_qa_runs_normalized_asset_id"),
        "synthetic_qa_runs",
        ["normalized_asset_id"],
    )
    op.create_index(
        op.f("ix_synthetic_qa_runs_qa_policy_id"),
        "synthetic_qa_runs",
        ["qa_policy_id"],
    )

    op.create_table(
        "synthetic_qa_measurements",
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("qa_run_id", sa.String(length=32), nullable=False),
        sa.Column("measurement_kind", sa.String(length=48), nullable=False),
        sa.Column("measurement_code", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("algorithm_reference", sa.String(length=128), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=8, scale=7), nullable=True),
        sa.Column("hard_gate", sa.Boolean(), nullable=False),
        sa.Column("threshold_outcome", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticQAMeasurement/v1'",
            name=op.f("ck_synthetic_qa_measurements_schema_version"),
        ),
        sa.CheckConstraint(
            "measurement_kind ~ '^[a-z][a-z0-9_]{2,47}$'",
            name=op.f("ck_synthetic_qa_measurements_measurement_kind"),
        ),
        sa.CheckConstraint(
            "measurement_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_synthetic_qa_measurements_measurement_code"),
        ),
        sa.CheckConstraint(
            "json_typeof(payload) = 'object'",
            name=op.f("ck_synthetic_qa_measurements_payload_object"),
        ),
        sa.CheckConstraint(
            "payload_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_synthetic_qa_measurements_payload_digest"),
        ),
        sa.CheckConstraint(
            "algorithm_reference ~ '^[a-z][a-z0-9._:/-]{2,127}$'",
            name=op.f("ck_synthetic_qa_measurements_algorithm_reference"),
        ),
        sa.CheckConstraint(
            "algorithm_version ~ '^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$'",
            name=op.f("ck_synthetic_qa_measurements_algorithm_version"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_synthetic_qa_measurements_confidence"),
        ),
        sa.CheckConstraint(
            "threshold_outcome IN ('PASSED','FAILED','NOT_APPLICABLE')",
            name=op.f("ck_synthetic_qa_measurements_threshold_outcome"),
        ),
        sa.CheckConstraint(
            "reason_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_synthetic_qa_measurements_reason_code"),
        ),
        sa.ForeignKeyConstraint(
            ["qa_run_id"],
            ["synthetic_qa_runs.id"],
            name=op.f("fk_synthetic_qa_measurements_qa_run_id_synthetic_qa_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_synthetic_qa_measurements")),
        sa.UniqueConstraint(
            "qa_run_id",
            "measurement_code",
            name=op.f("uq_synthetic_qa_measurements_unique_run_measurement"),
        ),
    )
    op.create_index(
        op.f("ix_synthetic_qa_measurements_qa_run_id"),
        "synthetic_qa_measurements",
        ["qa_run_id"],
    )

    op.create_table(
        "synthetic_qa_review_decisions",
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("qa_run_id", sa.String(length=32), nullable=False),
        sa.Column("review_kind", sa.String(length=48), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("actor_reference", sa.String(length=128), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticQAReviewDecision/v1'",
            name=op.f("ck_synthetic_qa_review_decisions_schema_version"),
        ),
        sa.CheckConstraint(
            "review_kind ~ '^[a-z][a-z0-9_]{2,47}$'",
            name=op.f("ck_synthetic_qa_review_decisions_review_kind"),
        ),
        sa.CheckConstraint(
            "decision IN ('PASSED','REJECTED')",
            name=op.f("ck_synthetic_qa_review_decisions_decision"),
        ),
        sa.CheckConstraint(
            "reason_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_synthetic_qa_review_decisions_reason_code"),
        ),
        sa.CheckConstraint(
            "actor_reference ~ '^[a-z0-9][a-z0-9._:@/-]{2,127}$'",
            name=op.f("ck_synthetic_qa_review_decisions_actor_reference"),
        ),
        sa.CheckConstraint(
            "reviewed_at <= created_at",
            name=op.f("ck_synthetic_qa_review_decisions_review_timestamp"),
        ),
        sa.ForeignKeyConstraint(
            ["qa_run_id"],
            ["synthetic_qa_runs.id"],
            name=op.f("fk_synthetic_qa_review_decisions_qa_run_id_synthetic_qa_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_synthetic_qa_review_decisions")),
        sa.UniqueConstraint(
            "qa_run_id",
            "review_kind",
            name=op.f("uq_synthetic_qa_review_decisions_unique_run_review_kind"),
        ),
    )
    op.create_index(
        op.f("ix_synthetic_qa_review_decisions_qa_run_id"),
        "synthetic_qa_review_decisions",
        ["qa_run_id"],
    )


def _strengthen_synthetic_identity() -> None:
    op.add_column(
        "synthetic_identities",
        sa.Column(
            "authority_kind",
            sa.String(length=24),
            nullable=False,
            server_default="LEGACY_SKELETON",
        ),
    )
    op.add_column(
        "synthetic_identities", sa.Column("canonical_asset_id", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "synthetic_identities",
        sa.Column("accepted_qa_run_id", sa.String(length=32), nullable=True),
    )
    for column_name, column_type in (
        ("generator_provider", sa.String(length=64)),
        ("generator_model", sa.String(length=128)),
        ("prompt_version", sa.String(length=48)),
        ("provenance", sa.JSON()),
    ):
        op.alter_column(
            "synthetic_identities", column_name, existing_type=column_type, nullable=True
        )
    op.create_foreign_key(
        op.f("fk_synthetic_identities_canonical_asset_id_assets"),
        "synthetic_identities",
        "assets",
        ["canonical_asset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_synthetic_identities_accepted_qa_run_id_synthetic_qa_runs"),
        "synthetic_identities",
        "synthetic_qa_runs",
        ["accepted_qa_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        op.f("uq_synthetic_identities_canonical_asset_id"),
        "synthetic_identities",
        ["canonical_asset_id"],
    )
    op.create_unique_constraint(
        op.f("uq_synthetic_identities_accepted_qa_run_id"),
        "synthetic_identities",
        ["accepted_qa_run_id"],
    )
    op.create_check_constraint(
        op.f("ck_synthetic_identities_authority_kind"),
        "synthetic_identities",
        "authority_kind IN ('LEGACY_SKELETON','CANONICAL_QA')",
    )
    op.create_check_constraint(
        op.f("ck_synthetic_identities_canonical_authority_shape"),
        "synthetic_identities",
        "(authority_kind = 'LEGACY_SKELETON' AND canonical_asset_id IS NULL "
        "AND accepted_qa_run_id IS NULL) OR "
        "(authority_kind = 'CANONICAL_QA' AND canonical_asset_id IS NOT NULL "
        "AND accepted_qa_run_id IS NOT NULL)",
    )
    op.alter_column(
        "synthetic_identities",
        "authority_kind",
        existing_type=sa.String(length=24),
        server_default="CANONICAL_QA",
    )


def _install_m3_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_validate_synthetic_asset_record() RETURNS trigger AS $$
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

        CREATE TRIGGER trg_synthetic_asset_records_guard
        BEFORE INSERT OR UPDATE ON synthetic_asset_records
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_synthetic_asset_record();
        CREATE TRIGGER trg_synthetic_asset_records_immutable_delete
        BEFORE DELETE ON synthetic_asset_records
        FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_synthetic_qa_run() RETURNS trigger AS $$
        DECLARE
            record_row synthetic_asset_records%ROWTYPE;
            policy_status varchar(24);
            required_reviews integer;
            allowed_transition boolean;
        BEGIN
            SELECT * INTO record_row FROM synthetic_asset_records
             WHERE id = NEW.synthetic_asset_record_id FOR UPDATE;
            IF record_row.id IS NULL
               OR record_row.normalized_asset_id IS DISTINCT FROM NEW.normalized_asset_id THEN
                RAISE EXCEPTION 'QA run must match normalized asset record';
            END IF;
            SELECT approval_status INTO policy_status FROM synthetic_qa_policies
             WHERE id = NEW.qa_policy_id;
            IF policy_status IS DISTINCT FROM 'APPROVED' THEN
                RAISE EXCEPTION 'QA run requires approved QA policy';
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'PENDING' OR record_row.status <> 'NORMALIZED' THEN
                    RAISE EXCEPTION 'QA run must start pending from normalized record';
                END IF;
                UPDATE synthetic_asset_records
                   SET status = 'QA_PENDING', updated_at = NEW.created_at
                 WHERE id = record_row.id;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'QA pending record transition failed';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.id IS DISTINCT FROM NEW.id
               OR OLD.created_at IS DISTINCT FROM NEW.created_at
               OR OLD.schema_version IS DISTINCT FROM NEW.schema_version
               OR OLD.synthetic_asset_record_id IS DISTINCT FROM NEW.synthetic_asset_record_id
               OR OLD.normalized_asset_id IS DISTINCT FROM NEW.normalized_asset_id
               OR OLD.qa_policy_id IS DISTINCT FROM NEW.qa_policy_id
               OR OLD.vision_provider_reference IS DISTINCT FROM NEW.vision_provider_reference
               OR OLD.vision_algorithm_reference IS DISTINCT FROM NEW.vision_algorithm_reference THEN
                RAISE EXCEPTION 'QA run authority is immutable';
            END IF;
            allowed_transition :=
                (OLD.status = 'PENDING' AND NEW.status = 'RUNNING') OR
                (OLD.status = 'RUNNING' AND NEW.status IN ('PASSED','REJECTED','FAILED'));
            IF OLD.status IS DISTINCT FROM NEW.status AND NOT allowed_transition THEN
                RAISE EXCEPTION 'invalid QA run state transition';
            END IF;
            IF OLD.status = 'PENDING' AND NEW.status = 'RUNNING' THEN
                UPDATE synthetic_asset_records
                   SET status = 'QA_RUNNING', qa_started_at = NEW.started_at,
                       updated_at = NEW.updated_at
                 WHERE id = record_row.id AND status = 'QA_PENDING';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'QA running record transition failed';
                END IF;
            ELSIF OLD.status = 'RUNNING' AND NEW.status = 'PASSED' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM synthetic_qa_measurements WHERE qa_run_id = NEW.id
                ) OR EXISTS (
                    SELECT 1 FROM synthetic_qa_measurements
                     WHERE qa_run_id = NEW.id AND hard_gate
                       AND threshold_outcome <> 'PASSED'
                ) THEN
                    RAISE EXCEPTION 'QA pass requires measurements and no unresolved hard failure';
                END IF;
                SELECT count(*) INTO required_reviews
                  FROM synthetic_qa_review_decisions
                 WHERE qa_run_id = NEW.id
                   AND review_kind IN ('adult_presentation','likeness_risk','license_rights')
                   AND decision = 'PASSED';
                IF required_reviews <> 3 THEN
                    RAISE EXCEPTION 'QA pass requires all mandatory human reviews';
                END IF;
                UPDATE synthetic_asset_records
                   SET status = 'QA_PASSED', qa_finalized_at = NEW.finalized_at,
                       updated_at = NEW.updated_at
                 WHERE id = record_row.id AND status = 'QA_RUNNING';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'QA passed record transition failed';
                END IF;
            ELSIF OLD.status = 'RUNNING' AND NEW.status = 'REJECTED' THEN
                UPDATE synthetic_asset_records
                   SET status = 'REJECTED', qa_finalized_at = NEW.finalized_at,
                       result_code = NEW.result_code, updated_at = NEW.updated_at
                 WHERE id = record_row.id AND status = 'QA_RUNNING';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'QA rejected record transition failed';
                END IF;
            ELSIF OLD.status = 'RUNNING' AND NEW.status = 'FAILED' THEN
                UPDATE synthetic_asset_records
                   SET status = 'QA_FAILED', qa_finalized_at = NEW.finalized_at,
                       result_code = NEW.result_code, updated_at = NEW.updated_at
                 WHERE id = record_row.id AND status = 'QA_RUNNING';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'QA failed record transition failed';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_synthetic_qa_runs_guard
        BEFORE INSERT OR UPDATE ON synthetic_qa_runs
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_synthetic_qa_run();
        CREATE TRIGGER trg_synthetic_qa_runs_immutable_delete
        BEFORE DELETE ON synthetic_qa_runs
        FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_synthetic_qa_evidence() RETURNS trigger AS $$
        DECLARE
            run_status varchar(16);
        BEGIN
            SELECT status INTO run_status FROM synthetic_qa_runs
             WHERE id = NEW.qa_run_id FOR UPDATE;
            IF run_status IS DISTINCT FROM 'RUNNING' THEN
                RAISE EXCEPTION 'QA evidence may only be appended to a running QA run';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_synthetic_qa_measurements_guard
        BEFORE INSERT ON synthetic_qa_measurements
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_synthetic_qa_evidence();
        CREATE TRIGGER trg_synthetic_qa_review_decisions_guard
        BEFORE INSERT ON synthetic_qa_review_decisions
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_synthetic_qa_evidence();
        CREATE TRIGGER trg_synthetic_qa_measurements_immutable
        BEFORE UPDATE OR DELETE ON synthetic_qa_measurements
        FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();
        CREATE TRIGGER trg_synthetic_qa_review_decisions_immutable
        BEFORE UPDATE OR DELETE ON synthetic_qa_review_decisions
        FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_canonical_synthetic_identity() RETURNS trigger AS $$
        DECLARE
            qa_record synthetic_qa_runs%ROWTYPE;
            asset_record synthetic_asset_records%ROWTYPE;
        BEGIN
            IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'synthetic identity authority is immutable';
            END IF;
            IF NEW.bank_version_id IS NOT NULL
               OR NEW.authority_kind <> 'CANONICAL_QA'
               OR NEW.canonical_asset_id IS NULL
               OR NEW.accepted_qa_run_id IS NULL THEN
                RAISE EXCEPTION 'new synthetic identity requires bank-independent canonical QA';
            END IF;
            SELECT * INTO qa_record FROM synthetic_qa_runs
             WHERE id = NEW.accepted_qa_run_id FOR UPDATE;
            SELECT * INTO asset_record FROM synthetic_asset_records
             WHERE normalized_asset_id = NEW.canonical_asset_id FOR UPDATE;
            IF qa_record.status IS DISTINCT FROM 'PASSED'
               OR qa_record.normalized_asset_id IS DISTINCT FROM NEW.canonical_asset_id
               OR asset_record.status IS DISTINCT FROM 'QA_PASSED'
               OR asset_record.id IS DISTINCT FROM qa_record.synthetic_asset_record_id THEN
                RAISE EXCEPTION 'canonical identity requires matching passed QA authority';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_synthetic_identities_canonical_guard
        BEFORE INSERT OR UPDATE OR DELETE ON synthetic_identities
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_canonical_synthetic_identity();

        CREATE FUNCTION mirror_mark_identity_registered() RETURNS trigger AS $$
        BEGIN
            UPDATE synthetic_asset_records
               SET status = 'IDENTITY_REGISTERED', identity_registered_at = NEW.created_at,
                   updated_at = NEW.created_at
             WHERE normalized_asset_id = NEW.canonical_asset_id AND status = 'QA_PASSED';
            IF NOT FOUND THEN
                RAISE EXCEPTION 'canonical identity record registration transition failed';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_synthetic_identities_mark_registered
        AFTER INSERT ON synthetic_identities
        FOR EACH ROW EXECUTE FUNCTION mirror_mark_identity_registered();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_source_deletion_evidence() RETURNS trigger AS $$
        DECLARE
            source_record synthetic_source_objects%ROWTYPE;
        BEGIN
            SELECT * INTO source_record FROM synthetic_source_objects
             WHERE id = NEW.source_object_id FOR UPDATE;
            IF EXISTS (
                SELECT 1 FROM synthetic_asset_records
                 WHERE source_object_id = NEW.source_object_id
                   AND status IN ('NORMALIZATION_PENDING','NORMALIZING')
            ) THEN
                RAISE EXCEPTION 'source object is protected by active normalization';
            END IF;
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
        """
    )


def upgrade() -> None:
    _create_synthetic_asset_records()
    _create_synthetic_qa_tables()
    _strengthen_synthetic_identity()
    _install_m3_guards()


def _restore_source_deletion_guard() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_source_deletion_evidence() RETURNS trigger AS $$
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
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM synthetic_asset_records)
               OR EXISTS (SELECT 1 FROM synthetic_qa_runs)
               OR EXISTS (SELECT 1 FROM synthetic_qa_measurements)
               OR EXISTS (SELECT 1 FROM synthetic_qa_review_decisions)
               OR EXISTS (
                   SELECT 1 FROM synthetic_identities WHERE authority_kind = 'CANONICAL_QA'
               ) THEN
                RAISE EXCEPTION '0010 downgrade would discard M3 normalization or QA authority';
            END IF;
        END;
        $$;
        """
    )
    _restore_source_deletion_guard()
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_identities_mark_registered ON synthetic_identities"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_identities_canonical_guard ON synthetic_identities"
    )
    op.execute("DROP FUNCTION IF EXISTS mirror_mark_identity_registered()")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_canonical_synthetic_identity()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_qa_review_decisions_immutable "
        "ON synthetic_qa_review_decisions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_qa_measurements_immutable "
        "ON synthetic_qa_measurements"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_qa_review_decisions_guard "
        "ON synthetic_qa_review_decisions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_qa_measurements_guard ON synthetic_qa_measurements"
    )
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_synthetic_qa_evidence()")
    op.execute("DROP TRIGGER IF EXISTS trg_synthetic_qa_runs_immutable_delete ON synthetic_qa_runs")
    op.execute("DROP TRIGGER IF EXISTS trg_synthetic_qa_runs_guard ON synthetic_qa_runs")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_synthetic_qa_run()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_asset_records_immutable_delete "
        "ON synthetic_asset_records"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_synthetic_asset_records_guard ON synthetic_asset_records"
    )
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_synthetic_asset_record()")

    op.drop_constraint(
        op.f("ck_synthetic_identities_canonical_authority_shape"),
        "synthetic_identities",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_synthetic_identities_authority_kind"),
        "synthetic_identities",
        type_="check",
    )
    op.drop_constraint(
        op.f("uq_synthetic_identities_accepted_qa_run_id"),
        "synthetic_identities",
        type_="unique",
    )
    op.drop_constraint(
        op.f("uq_synthetic_identities_canonical_asset_id"),
        "synthetic_identities",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_synthetic_identities_accepted_qa_run_id_synthetic_qa_runs"),
        "synthetic_identities",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_synthetic_identities_canonical_asset_id_assets"),
        "synthetic_identities",
        type_="foreignkey",
    )
    op.drop_column("synthetic_identities", "accepted_qa_run_id")
    op.drop_column("synthetic_identities", "canonical_asset_id")
    op.drop_column("synthetic_identities", "authority_kind")
    for column_name, column_type in (
        ("generator_provider", sa.String(length=64)),
        ("generator_model", sa.String(length=128)),
        ("prompt_version", sa.String(length=48)),
        ("provenance", sa.JSON()),
    ):
        op.alter_column(
            "synthetic_identities", column_name, existing_type=column_type, nullable=False
        )

    op.drop_index(
        op.f("ix_synthetic_qa_review_decisions_qa_run_id"),
        table_name="synthetic_qa_review_decisions",
    )
    op.drop_table("synthetic_qa_review_decisions")
    op.drop_index(
        op.f("ix_synthetic_qa_measurements_qa_run_id"),
        table_name="synthetic_qa_measurements",
    )
    op.drop_table("synthetic_qa_measurements")
    op.drop_index(op.f("ix_synthetic_qa_runs_qa_policy_id"), table_name="synthetic_qa_runs")
    op.drop_index(op.f("ix_synthetic_qa_runs_normalized_asset_id"), table_name="synthetic_qa_runs")
    op.drop_index(
        op.f("ix_synthetic_qa_runs_synthetic_asset_record_id"),
        table_name="synthetic_qa_runs",
    )
    op.drop_table("synthetic_qa_runs")
    op.drop_table("synthetic_asset_records")
