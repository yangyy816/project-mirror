"""Add immutable geometry variant and result QA authority.

Revision ID: 0012_geometry_variant_authority
Revises: 0011_offline_synth_source
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_geometry_variant_authority"
down_revision: str | None = "0011_offline_synth_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_variant_tables() -> None:
    op.create_table(
        "variant_specifications",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("source_identity_id", sa.String(length=32), nullable=False),
        sa.Column("source_qa_run_id", sa.String(length=32), nullable=False),
        sa.Column("geometry_ontology_version_id", sa.String(length=32), nullable=False),
        sa.Column("target_dimension", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("relative_magnitude_ppm", sa.Integer(), nullable=False),
        sa.Column("control_dimensions", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("runtime_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("tolerance_policy_id", sa.String(length=32), nullable=False),
        sa.Column("output_width", sa.Integer(), nullable=False),
        sa.Column("output_height", sa.Integer(), nullable=False),
        sa.Column("output_policy_version", sa.String(length=64), nullable=False),
        sa.Column("determinism_level", sa.String(length=32), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/VariantSpecification/v1'",
            name=op.f("ck_variant_specifications_schema_version"),
        ),
        sa.CheckConstraint(
            "target_dimension ~ '^[a-z][a-z0-9_]{0,63}$'",
            name=op.f("ck_variant_specifications_target_dimension"),
        ),
        sa.CheckConstraint(
            "direction IN ('INCREASE','DECREASE')",
            name=op.f("ck_variant_specifications_direction"),
        ),
        sa.CheckConstraint(
            "relative_magnitude_ppm BETWEEN 1 AND 1000000",
            name=op.f("ck_variant_specifications_relative_magnitude_ppm"),
        ),
        sa.CheckConstraint(
            "json_typeof(control_dimensions) = 'array' "
            "AND json_array_length(control_dimensions) > 0",
            name=op.f("ck_variant_specifications_control_dimensions"),
        ),
        sa.CheckConstraint(
            "algorithm_version ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'",
            name=op.f("ck_variant_specifications_algorithm_version"),
        ),
        sa.CheckConstraint(
            "runtime_manifest_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_variant_specifications_runtime_digest"),
        ),
        sa.CheckConstraint(
            "output_width BETWEEN 1 AND 16384 AND output_height BETWEEN 1 AND 16384 "
            "AND output_width::bigint * output_height::bigint <= 64000000",
            name=op.f("ck_variant_specifications_output_bounds"),
        ),
        sa.CheckConstraint(
            "output_policy_version ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'",
            name=op.f("ck_variant_specifications_output_policy_version"),
        ),
        sa.CheckConstraint(
            "determinism_level IN ('BIT_EXACT_CROSS_PLATFORM','BIT_EXACT_SAME_PLATFORM',"
            "'MEASUREMENT_EQUIVALENT')",
            name=op.f("ck_variant_specifications_determinism_level"),
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_variant_specifications_content_digest"),
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_variant_specifications_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_identity_id"],
            ["synthetic_identities.id"],
            name=op.f("fk_variant_specifications_source_identity_id_synthetic_identities"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_qa_run_id"],
            ["synthetic_qa_runs.id"],
            name=op.f("fk_variant_specifications_source_qa_run_id_synthetic_qa_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["geometry_ontology_version_id"],
            ["geometry_ontology_versions.id"],
            name=op.f(
                "fk_variant_specifications_geometry_ontology_version_id_geometry_ontology_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tolerance_policy_id"],
            ["synthetic_qa_policies.id"],
            name=op.f("fk_variant_specifications_tolerance_policy_id_synthetic_qa_policies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_variant_specifications")),
        sa.UniqueConstraint(
            "content_digest", name=op.f("uq_variant_specifications_content_digest")
        ),
    )
    for column in (
        "source_asset_id",
        "source_identity_id",
        "source_qa_run_id",
        "geometry_ontology_version_id",
        "tolerance_policy_id",
    ):
        op.create_index(
            op.f(f"ix_variant_specifications_{column}"),
            "variant_specifications",
            [column],
        )

    op.create_table(
        "transform_runs",
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("variant_specification_id", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("result_asset_id", sa.String(length=32), nullable=True),
        sa.Column("result_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("output_stored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("measurement_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/TransformRun/v1'",
            name=op.f("ck_transform_runs_schema_version"),
        ),
        sa.CheckConstraint("attempt > 0", name=op.f("ck_transform_runs_attempt")),
        sa.CheckConstraint(
            "status IN ('SPECIFIED','RUNNING','OUTPUT_STORED','MEASURING','COMPLETED',"
            "'REJECTED','FAILED','CANCELLED')",
            name=op.f("ck_transform_runs_status"),
        ),
        sa.CheckConstraint(
            "result_code IS NULL OR result_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_transform_runs_result_code"),
        ),
        sa.CheckConstraint(
            "(status IN ('SPECIFIED','RUNNING','OUTPUT_STORED','MEASURING','COMPLETED') "
            "AND result_code IS NULL) OR "
            "(status IN ('REJECTED','FAILED','CANCELLED') AND result_code IS NOT NULL)",
            name=op.f("ck_transform_runs_result_shape"),
        ),
        sa.CheckConstraint(
            "(status = 'SPECIFIED' AND started_at IS NULL AND output_stored_at IS NULL "
            "AND measurement_started_at IS NULL AND finalized_at IS NULL "
            "AND result_asset_id IS NULL) OR "
            "(status = 'RUNNING' AND started_at IS NOT NULL AND output_stored_at IS NULL "
            "AND measurement_started_at IS NULL AND finalized_at IS NULL "
            "AND result_asset_id IS NULL) OR "
            "(status = 'OUTPUT_STORED' AND started_at IS NOT NULL AND output_stored_at IS NOT NULL "
            "AND measurement_started_at IS NULL AND finalized_at IS NULL "
            "AND result_asset_id IS NOT NULL) OR "
            "(status = 'MEASURING' AND started_at IS NOT NULL AND output_stored_at IS NOT NULL "
            "AND measurement_started_at IS NOT NULL AND finalized_at IS NULL "
            "AND result_asset_id IS NOT NULL) OR "
            "(status = 'COMPLETED' AND started_at IS NOT NULL AND output_stored_at IS NOT NULL "
            "AND measurement_started_at IS NOT NULL AND finalized_at IS NOT NULL "
            "AND result_asset_id IS NOT NULL) OR "
            "(status IN ('REJECTED','FAILED') AND started_at IS NOT NULL "
            "AND finalized_at IS NOT NULL) OR "
            "(status = 'CANCELLED' AND finalized_at IS NOT NULL)",
            name=op.f("ck_transform_runs_status_shape"),
        ),
        sa.CheckConstraint(
            "(output_stored_at IS NULL OR output_stored_at >= started_at) AND "
            "(measurement_started_at IS NULL OR measurement_started_at >= output_stored_at) AND "
            "(finalized_at IS NULL OR started_at IS NULL OR finalized_at >= started_at) AND "
            "(finalized_at IS NULL OR measurement_started_at IS NULL "
            "OR finalized_at >= measurement_started_at)",
            name=op.f("ck_transform_runs_timestamp_order"),
        ),
        sa.ForeignKeyConstraint(
            ["variant_specification_id"],
            ["variant_specifications.id"],
            name=op.f("fk_transform_runs_variant_specification_id_variant_specifications"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["result_asset_id"],
            ["assets.id"],
            name=op.f("fk_transform_runs_result_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transform_runs")),
        sa.UniqueConstraint(
            "variant_specification_id",
            "attempt",
            name=op.f("uq_transform_runs_unique_specification_attempt"),
        ),
        sa.UniqueConstraint("result_asset_id", name=op.f("uq_transform_runs_result_asset_id")),
    )
    op.create_index(
        op.f("ix_transform_runs_variant_specification_id"),
        "transform_runs",
        ["variant_specification_id"],
    )
    op.create_index(
        "uq_transform_runs_completed_specification",
        "transform_runs",
        ["variant_specification_id"],
        unique=True,
        postgresql_where=sa.text("status = 'COMPLETED'"),
    )


def _extend_qa_subject_union() -> None:
    op.add_column(
        "synthetic_qa_runs",
        sa.Column("subject_kind", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "synthetic_qa_runs",
        sa.Column("transform_run_id", sa.String(length=32), nullable=True),
    )
    op.execute("UPDATE synthetic_qa_runs SET subject_kind = 'CANONICAL_BASE'")
    op.alter_column("synthetic_qa_runs", "subject_kind", nullable=False)
    op.alter_column("synthetic_qa_runs", "synthetic_asset_record_id", nullable=True)
    op.drop_constraint(
        op.f("ck_synthetic_qa_runs_schema_version"), "synthetic_qa_runs", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_synthetic_qa_runs_schema_version"),
        "synthetic_qa_runs",
        "schema_version IN ('mirror.synthetic-dataset/SyntheticQARun/v1',"
        "'mirror.synthetic-dataset/SyntheticQARun/v2')",
    )
    op.create_check_constraint(
        op.f("ck_synthetic_qa_runs_subject_kind"),
        "synthetic_qa_runs",
        "subject_kind IN ('CANONICAL_BASE','GEOMETRY_VARIANT')",
    )
    op.create_check_constraint(
        op.f("ck_synthetic_qa_runs_subject_shape"),
        "synthetic_qa_runs",
        "(subject_kind = 'CANONICAL_BASE' AND synthetic_asset_record_id IS NOT NULL "
        "AND transform_run_id IS NULL) OR "
        "(subject_kind = 'GEOMETRY_VARIANT' AND synthetic_asset_record_id IS NULL "
        "AND transform_run_id IS NOT NULL "
        "AND schema_version = 'mirror.synthetic-dataset/SyntheticQARun/v2')",
    )
    op.create_foreign_key(
        op.f("fk_synthetic_qa_runs_transform_run_id_transform_runs"),
        "synthetic_qa_runs",
        "transform_runs",
        ["transform_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        op.f("uq_synthetic_qa_runs_transform_run_id"),
        "synthetic_qa_runs",
        ["transform_run_id"],
    )


def _install_variant_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_validate_variant_specification() RETURNS trigger AS $$
        DECLARE
            identity_record synthetic_identities%ROWTYPE;
            qa_record synthetic_qa_runs%ROWTYPE;
            source_asset assets%ROWTYPE;
            ontology_status varchar(24);
            policy_status varchar(24);
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'variant specification is immutable';
            END IF;
            SELECT * INTO identity_record FROM synthetic_identities
             WHERE id = NEW.source_identity_id FOR UPDATE;
            SELECT * INTO qa_record FROM synthetic_qa_runs
             WHERE id = NEW.source_qa_run_id FOR UPDATE;
            SELECT * INTO source_asset FROM assets
             WHERE id = NEW.source_asset_id FOR UPDATE;
            SELECT approval_status INTO ontology_status FROM geometry_ontology_versions
             WHERE id = NEW.geometry_ontology_version_id;
            SELECT approval_status INTO policy_status FROM synthetic_qa_policies
             WHERE id = NEW.tolerance_policy_id;
            IF identity_record.authority_kind IS DISTINCT FROM 'CANONICAL_QA'
               OR NOT identity_record.adult_synthetic_attested
               OR identity_record.canonical_asset_id IS DISTINCT FROM NEW.source_asset_id
               OR identity_record.accepted_qa_run_id IS DISTINCT FROM NEW.source_qa_run_id
               OR qa_record.subject_kind IS DISTINCT FROM 'CANONICAL_BASE'
               OR qa_record.status IS DISTINCT FROM 'PASSED'
               OR qa_record.normalized_asset_id IS DISTINCT FROM NEW.source_asset_id
               OR source_asset.id IS NULL
               OR source_asset.owner_user_id IS NOT NULL
               OR source_asset.asset_role IS DISTINCT FROM 'synthetic'
               OR NOT source_asset.synthetic
               OR source_asset.internal_purpose IS DISTINCT FROM 'synthetic_dataset'
               OR source_asset.deleted_at IS NOT NULL
               OR NEW.output_width IS DISTINCT FROM source_asset.width
               OR NEW.output_height IS DISTINCT FROM source_asset.height THEN
                RAISE EXCEPTION 'variant specification requires matching canonical synthetic authority';
            END IF;
            IF ontology_status IS DISTINCT FROM 'APPROVED'
               OR policy_status IS DISTINCT FROM 'APPROVED' THEN
                RAISE EXCEPTION 'variant specification requires approved ontology and tolerance policy';
            END IF;
            IF EXISTS (
                SELECT 1 FROM json_array_elements(NEW.control_dimensions) AS dimension
                 WHERE json_typeof(dimension) <> 'string'
                    OR (dimension #>> '{}') !~ '^[a-z][a-z0-9_]{0,63}$'
                    OR (dimension #>> '{}') = NEW.target_dimension
            ) OR (
                SELECT count(*) FROM json_array_elements_text(NEW.control_dimensions)
            ) <> (
                SELECT count(DISTINCT dimension)
                  FROM json_array_elements_text(NEW.control_dimensions) AS dimension
            ) THEN
                RAISE EXCEPTION 'variant specification control dimensions are invalid';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_variant_specifications_guard
        BEFORE INSERT OR UPDATE OR DELETE ON variant_specifications
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_variant_specification();
        """
    )
    op.execute(
        """
        CREATE FUNCTION mirror_validate_transform_run() RETURNS trigger AS $$
        DECLARE
            specification variant_specifications%ROWTYPE;
            source_asset assets%ROWTYPE;
            result_asset assets%ROWTYPE;
            allowed_transition boolean;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'transform run authority is immutable';
            END IF;
            SELECT * INTO specification FROM variant_specifications
             WHERE id = NEW.variant_specification_id FOR UPDATE;
            IF specification.id IS NULL THEN
                RAISE EXCEPTION 'transform run requires immutable variant specification';
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'SPECIFIED' OR NEW.result_asset_id IS NOT NULL
                   OR NEW.result_code IS NOT NULL OR NEW.started_at IS NOT NULL
                   OR NEW.output_stored_at IS NOT NULL OR NEW.measurement_started_at IS NOT NULL
                   OR NEW.finalized_at IS NOT NULL THEN
                    RAISE EXCEPTION 'transform run must start specified';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.id IS DISTINCT FROM NEW.id
               OR OLD.created_at IS DISTINCT FROM NEW.created_at
               OR OLD.schema_version IS DISTINCT FROM NEW.schema_version
               OR OLD.variant_specification_id IS DISTINCT FROM NEW.variant_specification_id
               OR OLD.attempt IS DISTINCT FROM NEW.attempt THEN
                RAISE EXCEPTION 'transform run authority is immutable';
            END IF;
            IF (OLD.result_asset_id IS NOT NULL
                AND OLD.result_asset_id IS DISTINCT FROM NEW.result_asset_id)
               OR (OLD.started_at IS NOT NULL AND OLD.started_at IS DISTINCT FROM NEW.started_at)
               OR (OLD.output_stored_at IS NOT NULL
                   AND OLD.output_stored_at IS DISTINCT FROM NEW.output_stored_at)
               OR (OLD.measurement_started_at IS NOT NULL
                   AND OLD.measurement_started_at IS DISTINCT FROM NEW.measurement_started_at)
               OR (OLD.finalized_at IS NOT NULL
                   AND OLD.finalized_at IS DISTINCT FROM NEW.finalized_at)
               OR (OLD.result_code IS NOT NULL AND OLD.result_code IS DISTINCT FROM NEW.result_code) THEN
                RAISE EXCEPTION 'transform run evidence is immutable once recorded';
            END IF;
            IF (OLD.started_at IS NULL AND NEW.started_at IS NOT NULL
                AND NOT (OLD.status = 'SPECIFIED' AND NEW.status = 'RUNNING'))
               OR (OLD.result_asset_id IS NULL AND NEW.result_asset_id IS NOT NULL
                   AND NOT (OLD.status = 'RUNNING' AND NEW.status = 'OUTPUT_STORED'))
               OR (OLD.output_stored_at IS NULL AND NEW.output_stored_at IS NOT NULL
                   AND NOT (OLD.status = 'RUNNING' AND NEW.status = 'OUTPUT_STORED'))
               OR (OLD.measurement_started_at IS NULL AND NEW.measurement_started_at IS NOT NULL
                   AND NOT (OLD.status = 'OUTPUT_STORED' AND NEW.status = 'MEASURING'))
               OR (OLD.finalized_at IS NULL AND NEW.finalized_at IS NOT NULL
                   AND NEW.status NOT IN ('COMPLETED','REJECTED','FAILED','CANCELLED'))
               OR (OLD.result_code IS NULL AND NEW.result_code IS NOT NULL
                   AND NEW.status NOT IN ('REJECTED','FAILED','CANCELLED')) THEN
                RAISE EXCEPTION 'transform run evidence does not match state transition';
            END IF;
            allowed_transition :=
                (OLD.status = 'SPECIFIED' AND NEW.status IN ('RUNNING','CANCELLED')) OR
                (OLD.status = 'RUNNING' AND NEW.status IN (
                    'OUTPUT_STORED','REJECTED','FAILED','CANCELLED'
                )) OR
                (OLD.status = 'OUTPUT_STORED' AND NEW.status IN (
                    'MEASURING','REJECTED','FAILED'
                )) OR
                (OLD.status = 'MEASURING' AND NEW.status IN (
                    'COMPLETED','REJECTED','FAILED'
                ));
            IF OLD.status IS DISTINCT FROM NEW.status AND NOT allowed_transition THEN
                RAISE EXCEPTION 'invalid transform run state transition';
            END IF;
            IF NEW.result_asset_id IS NOT NULL THEN
                SELECT * INTO source_asset FROM assets WHERE id = specification.source_asset_id;
                SELECT * INTO result_asset FROM assets WHERE id = NEW.result_asset_id FOR UPDATE;
                IF result_asset.id IS NULL
                   OR result_asset.id = source_asset.id
                   OR result_asset.owner_user_id IS NOT NULL
                   OR result_asset.asset_role IS DISTINCT FROM 'synthetic'
                   OR NOT result_asset.synthetic
                   OR NOT result_asset.is_ai_modified
                   OR result_asset.internal_purpose IS DISTINCT FROM 'synthetic_dataset'
                   OR result_asset.deleted_at IS NOT NULL
                   OR result_asset.width IS DISTINCT FROM specification.output_width
                   OR result_asset.height IS DISTINCT FROM specification.output_height
                   OR result_asset.sha256 IS NOT DISTINCT FROM source_asset.sha256 THEN
                    RAISE EXCEPTION 'transform result requires a distinct immutable synthetic asset';
                END IF;
            END IF;
            IF NEW.status = 'MEASURING' AND NOT EXISTS (
                SELECT 1 FROM synthetic_qa_runs
                 WHERE transform_run_id = NEW.id
                   AND subject_kind = 'GEOMETRY_VARIANT'
                   AND normalized_asset_id = NEW.result_asset_id
                   AND status = 'RUNNING'
            ) THEN
                RAISE EXCEPTION 'measuring transform requires matching running QA';
            END IF;
            IF NEW.status = 'COMPLETED' AND NOT EXISTS (
                SELECT 1 FROM synthetic_qa_runs
                 WHERE transform_run_id = NEW.id
                   AND subject_kind = 'GEOMETRY_VARIANT'
                   AND normalized_asset_id = NEW.result_asset_id
                   AND status = 'PASSED'
            ) THEN
                RAISE EXCEPTION 'completed transform requires matching passed QA';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_transform_runs_guard
        BEFORE INSERT OR UPDATE OR DELETE ON transform_runs
        FOR EACH ROW EXECUTE FUNCTION mirror_validate_transform_run();
        """
    )


def _replace_qa_guard_for_subject_union() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_synthetic_qa_run() RETURNS trigger AS $$
        DECLARE
            record_row synthetic_asset_records%ROWTYPE;
            transform_row transform_runs%ROWTYPE;
            policy_status varchar(24);
            required_reviews integer;
            allowed_transition boolean;
        BEGIN
            IF NEW.subject_kind = 'CANONICAL_BASE' THEN
                SELECT * INTO record_row FROM synthetic_asset_records
                 WHERE id = NEW.synthetic_asset_record_id FOR UPDATE;
                IF record_row.id IS NULL
                   OR NEW.transform_run_id IS NOT NULL
                   OR record_row.normalized_asset_id IS DISTINCT FROM NEW.normalized_asset_id THEN
                    RAISE EXCEPTION 'base QA run must match normalized asset record';
                END IF;
            ELSIF NEW.subject_kind = 'GEOMETRY_VARIANT' THEN
                SELECT * INTO transform_row FROM transform_runs
                 WHERE id = NEW.transform_run_id FOR UPDATE;
                IF NEW.synthetic_asset_record_id IS NOT NULL
                   OR NEW.schema_version <> 'mirror.synthetic-dataset/SyntheticQARun/v2'
                   OR transform_row.id IS NULL
                   OR (TG_OP = 'INSERT'
                       AND transform_row.status IS DISTINCT FROM 'OUTPUT_STORED')
                   OR (TG_OP = 'UPDATE'
                       AND transform_row.status NOT IN ('OUTPUT_STORED','MEASURING'))
                   OR transform_row.result_asset_id IS DISTINCT FROM NEW.normalized_asset_id THEN
                    RAISE EXCEPTION 'variant QA run must match output-stored transform result';
                END IF;
            ELSE
                RAISE EXCEPTION 'unknown QA subject kind';
            END IF;
            SELECT approval_status INTO policy_status FROM synthetic_qa_policies
             WHERE id = NEW.qa_policy_id;
            IF policy_status IS DISTINCT FROM 'APPROVED' THEN
                RAISE EXCEPTION 'QA run requires approved QA policy';
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.status <> 'PENDING' THEN
                    RAISE EXCEPTION 'QA run must start pending';
                END IF;
                IF NEW.subject_kind = 'CANONICAL_BASE' THEN
                    IF record_row.status <> 'NORMALIZED' THEN
                        RAISE EXCEPTION 'base QA run must start from normalized record';
                    END IF;
                    UPDATE synthetic_asset_records
                       SET status = 'QA_PENDING', updated_at = NEW.created_at
                     WHERE id = record_row.id;
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'QA pending record transition failed';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.id IS DISTINCT FROM NEW.id
               OR OLD.created_at IS DISTINCT FROM NEW.created_at
               OR OLD.schema_version IS DISTINCT FROM NEW.schema_version
               OR OLD.subject_kind IS DISTINCT FROM NEW.subject_kind
               OR OLD.synthetic_asset_record_id IS DISTINCT FROM NEW.synthetic_asset_record_id
               OR OLD.transform_run_id IS DISTINCT FROM NEW.transform_run_id
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
            IF OLD.status = 'PENDING' AND NEW.status = 'RUNNING'
               AND NEW.subject_kind = 'CANONICAL_BASE' THEN
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
                IF NEW.subject_kind = 'CANONICAL_BASE' THEN
                    UPDATE synthetic_asset_records
                       SET status = 'QA_PASSED', qa_finalized_at = NEW.finalized_at,
                           updated_at = NEW.updated_at
                     WHERE id = record_row.id AND status = 'QA_RUNNING';
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'QA passed record transition failed';
                    END IF;
                END IF;
            ELSIF OLD.status = 'RUNNING' AND NEW.status IN ('REJECTED','FAILED')
               AND NEW.subject_kind = 'CANONICAL_BASE' THEN
                UPDATE synthetic_asset_records
                   SET status = CASE WHEN NEW.status = 'REJECTED' THEN 'REJECTED' ELSE 'QA_FAILED' END,
                       qa_finalized_at = NEW.finalized_at, result_code = NEW.result_code,
                       updated_at = NEW.updated_at
                 WHERE id = record_row.id AND status = 'QA_RUNNING';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'QA terminal record transition failed';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def _restore_base_qa_guard() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION mirror_validate_synthetic_qa_run() RETURNS trigger AS $$
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
        """
    )


def upgrade() -> None:
    _create_variant_tables()
    _extend_qa_subject_union()
    _install_variant_guards()
    _replace_qa_guard_for_subject_union()


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM variant_specifications)
               OR EXISTS (SELECT 1 FROM transform_runs)
               OR EXISTS (
                   SELECT 1 FROM synthetic_qa_runs
                    WHERE subject_kind = 'GEOMETRY_VARIANT'
                       OR transform_run_id IS NOT NULL
               ) THEN
                RAISE EXCEPTION '0012 downgrade would discard M4 geometry variant authority';
            END IF;
        END;
        $$;
        """
    )
    _restore_base_qa_guard()
    op.drop_constraint(
        op.f("uq_synthetic_qa_runs_transform_run_id"),
        "synthetic_qa_runs",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_synthetic_qa_runs_transform_run_id_transform_runs"),
        "synthetic_qa_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("ck_synthetic_qa_runs_subject_shape"), "synthetic_qa_runs", type_="check"
    )
    op.drop_constraint(
        op.f("ck_synthetic_qa_runs_subject_kind"), "synthetic_qa_runs", type_="check"
    )
    op.drop_constraint(
        op.f("ck_synthetic_qa_runs_schema_version"), "synthetic_qa_runs", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_synthetic_qa_runs_schema_version"),
        "synthetic_qa_runs",
        "schema_version = 'mirror.synthetic-dataset/SyntheticQARun/v1'",
    )
    op.alter_column("synthetic_qa_runs", "synthetic_asset_record_id", nullable=False)
    op.drop_column("synthetic_qa_runs", "transform_run_id")
    op.drop_column("synthetic_qa_runs", "subject_kind")
    op.execute("DROP TRIGGER IF EXISTS trg_transform_runs_guard ON transform_runs")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_transform_run()")
    op.execute("DROP TRIGGER IF EXISTS trg_variant_specifications_guard ON variant_specifications")
    op.execute("DROP FUNCTION IF EXISTS mirror_validate_variant_specification()")
    op.drop_index("uq_transform_runs_completed_specification", table_name="transform_runs")
    op.drop_index(op.f("ix_transform_runs_variant_specification_id"), table_name="transform_runs")
    op.drop_table("transform_runs")
    for column in reversed(
        (
            "source_asset_id",
            "source_identity_id",
            "source_qa_run_id",
            "geometry_ontology_version_id",
            "tolerance_policy_id",
        )
    ):
        op.drop_index(
            op.f(f"ix_variant_specifications_{column}"), table_name="variant_specifications"
        )
    op.drop_table("variant_specifications")
