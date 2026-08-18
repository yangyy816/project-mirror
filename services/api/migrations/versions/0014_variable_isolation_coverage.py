"""P2-M5 immutable variable-isolation, duplicate, and diversity authority.

Revision ID: 0014_m5_eval_authority
Revises: 0013_warp_plan_authority
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0014_m5_eval_authority"
down_revision: str | None = "0013_warp_plan_authority"
branch_labels: str | None = None
depends_on: str | None = None


def _hash_constraint(column: str, table: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"{column} ~ '^[0-9a-f]{{64}}$'", name=op.f(f"ck_{table}_{column}"))


def _create_tables() -> None:
    op.create_table(
        "synthetic_evaluation_policies",
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("geometry_ontology_version_id", sa.String(length=32), nullable=False),
        sa.Column("ontology_digest", sa.String(length=64), nullable=False),
        sa.Column("measurement_policy_version", sa.String(length=64), nullable=False),
        sa.Column("isolation_algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("duplicate_algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("split_rule_version", sa.String(length=64), nullable=False),
        sa.Column("canonical_content", sa.JSON(), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("approval_status", sa.String(length=24), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticEvaluationPolicy/v1'",
            name=op.f("ck_synthetic_evaluation_policies_schema_version"),
        ),
        sa.CheckConstraint(
            "approval_status IN ('DRAFT','APPROVED')",
            name=op.f("ck_synthetic_evaluation_policies_approval_status"),
        ),
        sa.CheckConstraint(
            "(approval_status = 'DRAFT' AND approved_at IS NULL) OR (approval_status = 'APPROVED' AND approved_at IS NOT NULL)",
            name=op.f("ck_synthetic_evaluation_policies_approval_shape"),
        ),
        sa.CheckConstraint(
            "version ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'",
            name=op.f("ck_synthetic_evaluation_policies_canonical_version"),
        ),
        _hash_constraint("ontology_digest", "synthetic_evaluation_policies"),
        _hash_constraint("content_digest", "synthetic_evaluation_policies"),
        sa.CheckConstraint(
            "json_typeof(canonical_content) = 'object'",
            name=op.f("ck_synthetic_evaluation_policies_content_object"),
        ),
        sa.ForeignKeyConstraint(
            ["geometry_ontology_version_id"],
            ["geometry_ontology_versions.id"],
            name=op.f(
                "fk_synthetic_evaluation_policies_geometry_ontology_version_id_geometry_ontology_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_synthetic_evaluation_policies")),
        sa.UniqueConstraint("version", name=op.f("uq_synthetic_evaluation_policies_version")),
        sa.UniqueConstraint(
            "content_digest", name=op.f("uq_synthetic_evaluation_policies_content_digest")
        ),
    )
    op.create_index(
        op.f("ix_synthetic_evaluation_policies_geometry_ontology_version_id"),
        "synthetic_evaluation_policies",
        ["geometry_ontology_version_id"],
        unique=False,
    )
    op.create_table(
        "synthetic_evaluation_dimension_rules",
        sa.Column("policy_id", sa.String(length=32), nullable=False),
        sa.Column("dimension_key", sa.String(length=64), nullable=False),
        sa.Column("region_group", sa.String(length=64), nullable=False),
        sa.Column("control_dimensions", sa.JSON(), nullable=False),
        sa.Column("target_error_tolerance_ppm", sa.Integer(), nullable=False),
        sa.Column("control_drift_tolerance_ppm", sa.Integer(), nullable=False),
        sa.Column("repeat_variance_tolerance_ppm", sa.Integer(), nullable=False),
        sa.Column("platform_variance_tolerance_ppm", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "dimension_key ~ '^[a-z][a-z0-9_]{0,63}$'",
            name=op.f("ck_synthetic_evaluation_dimension_rules_dimension_key"),
        ),
        sa.CheckConstraint(
            "region_group ~ '^[a-z][a-z0-9_]{0,63}$'",
            name=op.f("ck_synthetic_evaluation_dimension_rules_region_group"),
        ),
        sa.CheckConstraint(
            "json_typeof(control_dimensions) = 'array' AND json_array_length(control_dimensions) > 0",
            name=op.f("ck_synthetic_evaluation_dimension_rules_control_dimensions"),
        ),
        sa.CheckConstraint(
            "target_error_tolerance_ppm BETWEEN 0 AND 1000000 AND control_drift_tolerance_ppm BETWEEN 0 AND 1000000 AND repeat_variance_tolerance_ppm BETWEEN 0 AND 1000000 AND platform_variance_tolerance_ppm BETWEEN 0 AND 1000000",
            name=op.f("ck_synthetic_evaluation_dimension_rules_tolerance_bounds"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["synthetic_evaluation_policies.id"],
            name=op.f(
                "fk_synthetic_evaluation_dimension_rules_policy_id_synthetic_evaluation_policies"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_synthetic_evaluation_dimension_rules")),
        sa.UniqueConstraint(
            "policy_id",
            "dimension_key",
            name="unique_policy_dimension",
        ),
    )
    op.create_index(
        op.f("ix_synthetic_evaluation_dimension_rules_policy_id"),
        "synthetic_evaluation_dimension_rules",
        ["policy_id"],
        unique=False,
    )
    op.create_table(
        "similarity_signatures",
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("normalized_sha256", sa.String(length=64), nullable=False),
        sa.Column("phash_hex", sa.String(length=16), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SimilaritySignature/v1'",
            name=op.f("ck_similarity_signatures_schema_version"),
        ),
        sa.CheckConstraint(
            "algorithm_version = 'phash-dct-nearest-v1'",
            name=op.f("ck_similarity_signatures_algorithm_version"),
        ),
        _hash_constraint("normalized_sha256", "similarity_signatures"),
        sa.CheckConstraint(
            "phash_hex ~ '^[0-9a-f]{16}$'", name=op.f("ck_similarity_signatures_phash_hex")
        ),
        sa.CheckConstraint(
            "width BETWEEN 1 AND 8192 AND height BETWEEN 1 AND 8192",
            name=op.f("ck_similarity_signatures_bounds"),
        ),
        sa.CheckConstraint(
            "width::bigint * height::bigint <= 40000000",
            name=op.f("ck_similarity_signatures_total_pixels"),
        ),
        _hash_constraint("content_digest", "similarity_signatures"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_similarity_signatures_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_similarity_signatures")),
        sa.UniqueConstraint("asset_id", name=op.f("uq_similarity_signatures_asset_id")),
        sa.UniqueConstraint(
            "normalized_sha256", name=op.f("uq_similarity_signatures_normalized_sha256")
        ),
        sa.UniqueConstraint("content_digest", name=op.f("uq_similarity_signatures_content_digest")),
    )
    op.create_table(
        "duplicate_clusters",
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("cluster_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "algorithm_version = 'phash-dct-nearest-v1'",
            name=op.f("ck_duplicate_clusters_algorithm_version"),
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','FINALIZED')", name=op.f("ck_duplicate_clusters_status")
        ),
        sa.CheckConstraint(
            "(status = 'OPEN' AND finalized_at IS NULL) OR (status = 'FINALIZED' AND finalized_at IS NOT NULL)",
            name=op.f("ck_duplicate_clusters_finalization_shape"),
        ),
        _hash_constraint("cluster_digest", "duplicate_clusters"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_duplicate_clusters")),
        sa.UniqueConstraint("cluster_digest", name=op.f("uq_duplicate_clusters_cluster_digest")),
    )
    op.create_table(
        "duplicate_cluster_memberships",
        sa.Column("cluster_id", sa.String(length=32), nullable=False),
        sa.Column("signature_id", sa.String(length=32), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _hash_constraint("evidence_digest", "duplicate_cluster_memberships"),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["duplicate_clusters.id"],
            name=op.f("fk_duplicate_cluster_memberships_cluster_id_duplicate_clusters"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["signature_id"],
            ["similarity_signatures.id"],
            name=op.f("fk_duplicate_cluster_memberships_signature_id_similarity_signatures"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_duplicate_cluster_memberships")),
        sa.UniqueConstraint(
            "cluster_id",
            "signature_id",
            name="unique_cluster_signature",
        ),
        sa.UniqueConstraint("signature_id", name="single_cluster_signature"),
        sa.UniqueConstraint(
            "evidence_digest", name=op.f("uq_duplicate_cluster_memberships_evidence_digest")
        ),
    )
    op.create_table(
        "duplicate_cluster_decisions",
        sa.Column("cluster_id", sa.String(length=32), nullable=False),
        sa.Column("signature_id", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("actor_reference", sa.String(length=128), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('RETAIN','REJECT')", name=op.f("ck_duplicate_cluster_decisions_decision")
        ),
        sa.CheckConstraint(
            "reason_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name=op.f("ck_duplicate_cluster_decisions_reason_code"),
        ),
        sa.CheckConstraint(
            "actor_reference ~ '^[a-z0-9][a-z0-9._:@/-]{2,127}$'",
            name=op.f("ck_duplicate_cluster_decisions_actor_reference"),
        ),
        _hash_constraint("evidence_digest", "duplicate_cluster_decisions"),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["duplicate_clusters.id"],
            name=op.f("fk_duplicate_cluster_decisions_cluster_id_duplicate_clusters"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["signature_id"],
            ["similarity_signatures.id"],
            name=op.f("fk_duplicate_cluster_decisions_signature_id_similarity_signatures"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_duplicate_cluster_decisions")),
        sa.UniqueConstraint(
            "cluster_id",
            "signature_id",
            name="unique_cluster_decision",
        ),
        sa.UniqueConstraint(
            "evidence_digest", name=op.f("uq_duplicate_cluster_decisions_evidence_digest")
        ),
    )
    op.create_table(
        "evaluation_cohort_assignments",
        sa.Column("policy_id", sa.String(length=32), nullable=False),
        sa.Column("synthetic_identity_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("duplicate_cluster_id", sa.String(length=32)),
        sa.Column("split", sa.String(length=16), nullable=False),
        sa.Column("dimension_keys", sa.JSON(), nullable=False),
        sa.Column("assignment_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "split IN ('CALIBRATION','M4_SEEN','HOLDOUT')",
            name=op.f("ck_evaluation_cohort_assignments_split"),
        ),
        _hash_constraint("source_asset_sha256", "evaluation_cohort_assignments"),
        sa.CheckConstraint(
            "json_typeof(dimension_keys) = 'array' AND json_array_length(dimension_keys) > 0",
            name=op.f("ck_evaluation_cohort_assignments_dimension_keys"),
        ),
        _hash_constraint("assignment_digest", "evaluation_cohort_assignments"),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["synthetic_evaluation_policies.id"],
            name=op.f("fk_evaluation_cohort_assignments_policy_id_synthetic_evaluation_policies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["synthetic_identity_id"],
            ["synthetic_identities.id"],
            name=op.f(
                "fk_evaluation_cohort_assignments_synthetic_identity_id_synthetic_identities"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_evaluation_cohort_assignments_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_cluster_id"],
            ["duplicate_clusters.id"],
            name=op.f("fk_evaluation_cohort_assignments_duplicate_cluster_id_duplicate_clusters"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_cohort_assignments")),
        sa.UniqueConstraint(
            "policy_id",
            "synthetic_identity_id",
            name="unique_policy_identity",
        ),
        sa.UniqueConstraint(
            "policy_id",
            "source_asset_id",
            name="unique_policy_asset",
        ),
        sa.UniqueConstraint(
            "assignment_digest", name=op.f("uq_evaluation_cohort_assignments_assignment_digest")
        ),
    )
    for column in ("policy_id", "synthetic_identity_id", "source_asset_id", "duplicate_cluster_id"):
        op.create_index(
            op.f(f"ix_evaluation_cohort_assignments_{column}"),
            "evaluation_cohort_assignments",
            [column],
            unique=False,
        )
    op.create_table(
        "isolation_reports",
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("transform_run_id", sa.String(length=32), nullable=False),
        sa.Column("policy_id", sa.String(length=32), nullable=False),
        sa.Column("target_dimension", sa.String(length=64), nullable=False),
        sa.Column("requested_delta_ppm", sa.Integer(), nullable=False),
        sa.Column("measured_target_delta_ppm", sa.Integer(), nullable=False),
        sa.Column("target_error_ppm", sa.Integer(), nullable=False),
        sa.Column("control_deltas", sa.JSON(), nullable=False),
        sa.Column("non_target_drift_ppm", sa.Integer(), nullable=False),
        sa.Column("repeat_variance_ppm", sa.Integer(), nullable=False),
        sa.Column("platform_variance_ppm", sa.Integer(), nullable=False),
        sa.Column("artifact_gate_passed", sa.Boolean(), nullable=False),
        sa.Column("reliability_gate_passed", sa.Boolean(), nullable=False),
        sa.Column("conclusion", sa.String(length=16), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/IsolationReport/v1'",
            name=op.f("ck_isolation_reports_schema_version"),
        ),
        sa.CheckConstraint(
            "target_dimension ~ '^[a-z][a-z0-9_]{0,63}$'",
            name=op.f("ck_isolation_reports_target_dimension"),
        ),
        sa.CheckConstraint(
            "target_error_ppm BETWEEN 0 AND 10000000",
            name=op.f("ck_isolation_reports_target_error"),
        ),
        sa.CheckConstraint(
            "non_target_drift_ppm BETWEEN 0 AND 5000000 AND repeat_variance_ppm BETWEEN 0 AND 1000000 AND platform_variance_ppm BETWEEN 0 AND 1000000",
            name=op.f("ck_isolation_reports_measurement_bounds"),
        ),
        sa.CheckConstraint(
            "json_typeof(control_deltas) = 'object'",
            name=op.f("ck_isolation_reports_control_deltas"),
        ),
        sa.CheckConstraint(
            "json_typeof(reason_codes) = 'array'", name=op.f("ck_isolation_reports_reason_codes")
        ),
        sa.CheckConstraint(
            "conclusion IN ('PASSED','REJECTED')", name=op.f("ck_isolation_reports_conclusion")
        ),
        _hash_constraint("content_digest", "isolation_reports"),
        sa.ForeignKeyConstraint(
            ["transform_run_id"],
            ["transform_runs.id"],
            name=op.f("fk_isolation_reports_transform_run_id_transform_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["synthetic_evaluation_policies.id"],
            name=op.f("fk_isolation_reports_policy_id_synthetic_evaluation_policies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_isolation_reports")),
        sa.UniqueConstraint(
            "transform_run_id",
            "policy_id",
            name="unique_transform_policy_report",
        ),
        sa.UniqueConstraint("content_digest", name=op.f("uq_isolation_reports_content_digest")),
    )
    op.create_table(
        "similarity_pair_evidence",
        sa.Column("left_signature_id", sa.String(length=32), nullable=False),
        sa.Column("right_signature_id", sa.String(length=32), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("hamming_distance", sa.Integer(), nullable=False),
        sa.Column("candidate_kind", sa.String(length=24), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "left_signature_id < right_signature_id",
            name=op.f("ck_similarity_pair_evidence_canonical_order"),
        ),
        sa.CheckConstraint(
            "algorithm_version = 'phash-dct-nearest-v1'",
            name=op.f("ck_similarity_pair_evidence_algorithm_version"),
        ),
        sa.CheckConstraint(
            "hamming_distance BETWEEN 0 AND 64",
            name=op.f("ck_similarity_pair_evidence_hamming_distance"),
        ),
        sa.CheckConstraint(
            "candidate_kind = 'NEAR_DUPLICATE_CANDIDATE'",
            name=op.f("ck_similarity_pair_evidence_candidate_kind"),
        ),
        _hash_constraint("evidence_digest", "similarity_pair_evidence"),
        sa.ForeignKeyConstraint(
            ["left_signature_id"],
            ["similarity_signatures.id"],
            name=op.f("fk_similarity_pair_evidence_left_signature_id_similarity_signatures"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["right_signature_id"],
            ["similarity_signatures.id"],
            name=op.f("fk_similarity_pair_evidence_right_signature_id_similarity_signatures"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_similarity_pair_evidence")),
        sa.UniqueConstraint(
            "left_signature_id",
            "right_signature_id",
            name="unique_canonical_pair",
        ),
        sa.UniqueConstraint(
            "evidence_digest", name=op.f("uq_similarity_pair_evidence_evidence_digest")
        ),
    )
    op.create_table(
        "diversity_reports",
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("policy_id", sa.String(length=32), nullable=False),
        sa.Column("cohort_stage", sa.Integer(), nullable=False),
        sa.Column("report_payload", sa.JSON(), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/DiversityReport/v1'",
            name=op.f("ck_diversity_reports_schema_version"),
        ),
        sa.CheckConstraint(
            "cohort_stage IN (24,48,96)", name=op.f("ck_diversity_reports_cohort_stage")
        ),
        sa.CheckConstraint(
            "json_typeof(report_payload) = 'object'",
            name=op.f("ck_diversity_reports_payload_object"),
        ),
        _hash_constraint("content_digest", "diversity_reports"),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["synthetic_evaluation_policies.id"],
            name=op.f("fk_diversity_reports_policy_id_synthetic_evaluation_policies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_diversity_reports")),
        sa.UniqueConstraint(
            "policy_id",
            "cohort_stage",
            name="unique_policy_cohort_report",
        ),
        sa.UniqueConstraint("content_digest", name=op.f("uq_diversity_reports_content_digest")),
    )


def _install_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION mirror_validate_m5_policy() RETURNS trigger AS $$
        DECLARE ontology geometry_ontology_versions%ROWTYPE; content jsonb;
                canonical_rules text; canonical_policy text; expected_digest varchar(64);
        BEGIN
            IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'M5 evaluation policy is immutable'; END IF;
            SELECT * INTO ontology FROM geometry_ontology_versions WHERE id = NEW.geometry_ontology_version_id FOR SHARE;
            IF ontology.id IS NULL OR ontology.approval_status <> 'APPROVED' OR ontology.content_digest <> NEW.ontology_digest THEN
                RAISE EXCEPTION 'M5 evaluation policy requires approved matching ontology';
            END IF;
            IF NEW.measurement_policy_version !~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'
               OR NEW.isolation_algorithm_version !~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'
               OR NEW.duplicate_algorithm_version <> 'phash-dct-nearest-v1'
               OR NEW.split_rule_version !~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$' THEN
                RAISE EXCEPTION 'M5 evaluation policy version fields are invalid';
            END IF;
            content := NEW.canonical_content::jsonb;
            IF jsonb_typeof(content) <> 'object'
               OR content->>'version' IS DISTINCT FROM NEW.version
               OR content->>'ontology_version' IS DISTINCT FROM ontology.version
               OR content->>'ontology_digest' IS DISTINCT FROM NEW.ontology_digest
               OR content->>'measurement_policy_version' IS DISTINCT FROM NEW.measurement_policy_version
               OR content->>'isolation_algorithm_version' IS DISTINCT FROM NEW.isolation_algorithm_version
               OR content->>'duplicate_algorithm_version' IS DISTINCT FROM NEW.duplicate_algorithm_version
               OR content->>'split_rule_version' IS DISTINCT FROM NEW.split_rule_version
               OR content->'cohort_stages' IS DISTINCT FROM '[24,48,96]'::jsonb
               OR jsonb_typeof(content->'dimension_rules') <> 'array'
               OR jsonb_array_length(content->'dimension_rules') = 0 THEN
                RAISE EXCEPTION 'M5 evaluation policy canonical content disagrees with authority';
            END IF;
            SELECT string_agg(
                '{"control_dimensions":' || regexp_replace((item->'control_dimensions')::text, ', ', ',', 'g') ||
                ',"control_drift_tolerance_ppm":' || (item->>'control_drift_tolerance_ppm') ||
                ',"dimension_key":"' || (item->>'dimension_key') ||
                '","platform_variance_tolerance_ppm":' || (item->>'platform_variance_tolerance_ppm') ||
                ',"region_group":"' || (item->>'region_group') ||
                '","repeat_variance_tolerance_ppm":' || (item->>'repeat_variance_tolerance_ppm') ||
                ',"target_error_tolerance_ppm":' || (item->>'target_error_tolerance_ppm') || '}',
                ',' ORDER BY item->>'dimension_key'
            ) INTO canonical_rules FROM jsonb_array_elements(content->'dimension_rules') item;
            canonical_policy :=
                '{"cohort_stages":[24,48,96],"dimension_rules":[' || canonical_rules ||
                '],"duplicate_algorithm_version":"' || NEW.duplicate_algorithm_version ||
                '","isolation_algorithm_version":"' || NEW.isolation_algorithm_version ||
                '","measurement_policy_version":"' || NEW.measurement_policy_version ||
                '","ontology_digest":"' || NEW.ontology_digest ||
                '","ontology_version":"' || ontology.version ||
                '","split_rule_version":"' || NEW.split_rule_version ||
                '","version":"' || NEW.version || '"}';
            expected_digest := encode(sha256((NEW.schema_version || E'\\n' || canonical_policy)::bytea), 'hex');
            IF NEW.content_digest IS DISTINCT FROM expected_digest THEN
                RAISE EXCEPTION 'M5 evaluation policy digest mismatch';
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.id <> NEW.id OR OLD.created_at <> NEW.created_at OR OLD.version <> NEW.version
                   OR OLD.geometry_ontology_version_id <> NEW.geometry_ontology_version_id OR OLD.ontology_digest <> NEW.ontology_digest
                   OR OLD.measurement_policy_version <> NEW.measurement_policy_version OR OLD.isolation_algorithm_version <> NEW.isolation_algorithm_version
                   OR OLD.duplicate_algorithm_version <> NEW.duplicate_algorithm_version OR OLD.split_rule_version <> NEW.split_rule_version
                   OR OLD.canonical_content::jsonb IS DISTINCT FROM NEW.canonical_content::jsonb
                   OR OLD.content_digest <> NEW.content_digest THEN
                    RAISE EXCEPTION 'M5 evaluation policy content is immutable';
                END IF;
                IF NOT (OLD.approval_status = 'DRAFT' AND NEW.approval_status = 'APPROVED')
                   OR OLD.approved_at IS NOT NULL OR NEW.approved_at IS NULL THEN
                    RAISE EXCEPTION 'invalid M5 evaluation policy transition';
                END IF;
                IF (SELECT count(*) FROM synthetic_evaluation_dimension_rules WHERE policy_id=NEW.id)
                   <> jsonb_array_length(content->'dimension_rules')
                   OR EXISTS (
                       SELECT 1 FROM synthetic_evaluation_dimension_rules rule
                        WHERE rule.policy_id=NEW.id
                          AND NOT EXISTS (
                              SELECT 1 FROM jsonb_array_elements(content->'dimension_rules') item
                               WHERE item = jsonb_build_object(
                                   'control_dimensions', rule.control_dimensions::jsonb,
                                   'control_drift_tolerance_ppm', rule.control_drift_tolerance_ppm,
                                   'dimension_key', rule.dimension_key,
                                   'platform_variance_tolerance_ppm', rule.platform_variance_tolerance_ppm,
                                   'region_group', rule.region_group,
                                   'repeat_variance_tolerance_ppm', rule.repeat_variance_tolerance_ppm,
                                   'target_error_tolerance_ppm', rule.target_error_tolerance_ppm
                               )
                          )
                   ) THEN
                    RAISE EXCEPTION 'M5 evaluation policy approval requires exact dimension rules';
                END IF;
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_synthetic_evaluation_policies_guard BEFORE INSERT OR UPDATE OR DELETE ON synthetic_evaluation_policies FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_policy();

        CREATE FUNCTION mirror_validate_m5_dimension_rule() RETURNS trigger AS $$
        DECLARE ontology_content json;
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') THEN RAISE EXCEPTION 'M5 dimension rule is immutable'; END IF;
            IF EXISTS (SELECT 1 FROM synthetic_evaluation_policies WHERE id=NEW.policy_id AND approval_status='APPROVED')
               OR NEW.region_group ~ '(beauty|score|rank|race|ethnicity|ancestry|nationality|age|minor|adult|sexual)' THEN
                RAISE EXCEPTION 'invalid M5 dimension rule';
            END IF;
            SELECT ontology.content INTO ontology_content
              FROM synthetic_evaluation_policies policy
              JOIN geometry_ontology_versions ontology ON ontology.id = policy.geometry_ontology_version_id
             WHERE policy.id = NEW.policy_id;
            IF ontology_content IS NULL
               OR NOT (ontology_content::jsonb @> jsonb_build_object(
                   'dimensions', jsonb_build_object(
                       NEW.dimension_key, jsonb_build_object('region_group', NEW.region_group)
                   )
               )) THEN
                RAISE EXCEPTION 'M5 region group must be declared by the immutable ontology';
            END IF;
            IF EXISTS (SELECT 1 FROM json_array_elements_text(NEW.control_dimensions) AS x WHERE x !~ '^[a-z][a-z0-9_]{0,63}$' OR x = NEW.dimension_key)
               OR (SELECT count(*) <> count(DISTINCT value) FROM json_array_elements_text(NEW.control_dimensions) AS value) THEN
                RAISE EXCEPTION 'M5 control dimensions are invalid';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM synthetic_evaluation_policies policy,
                     jsonb_array_elements(policy.canonical_content::jsonb->'dimension_rules') item
                 WHERE policy.id=NEW.policy_id
                   AND item = jsonb_build_object(
                       'control_dimensions', NEW.control_dimensions::jsonb,
                       'control_drift_tolerance_ppm', NEW.control_drift_tolerance_ppm,
                       'dimension_key', NEW.dimension_key,
                       'platform_variance_tolerance_ppm', NEW.platform_variance_tolerance_ppm,
                       'region_group', NEW.region_group,
                       'repeat_variance_tolerance_ppm', NEW.repeat_variance_tolerance_ppm,
                       'target_error_tolerance_ppm', NEW.target_error_tolerance_ppm
                   )
            ) THEN
                RAISE EXCEPTION 'M5 dimension rule disagrees with policy canonical content';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_synthetic_evaluation_dimension_rules_guard BEFORE INSERT OR UPDATE OR DELETE ON synthetic_evaluation_dimension_rules FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_dimension_rule();

        CREATE FUNCTION mirror_validate_m5_cohort_assignment() RETURNS trigger AS $$
        DECLARE asset_row assets%ROWTYPE; identity_row synthetic_identities%ROWTYPE;
                accepted_qa synthetic_qa_runs%ROWTYPE; source_signature_id varchar(32);
                cluster_status varchar(16);
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') THEN RAISE EXCEPTION 'M5 cohort assignment is immutable'; END IF;
            SELECT * INTO asset_row FROM assets WHERE id=NEW.source_asset_id FOR SHARE;
            IF asset_row.id IS NULL OR asset_row.owner_user_id IS NOT NULL OR asset_row.asset_role <> 'synthetic'
               OR NOT asset_row.synthetic OR asset_row.internal_purpose <> 'synthetic_dataset' OR asset_row.deleted_at IS NOT NULL
               OR asset_row.sha256 <> NEW.source_asset_sha256 THEN RAISE EXCEPTION 'M5 cohort requires matching private synthetic asset'; END IF;
            SELECT * INTO identity_row FROM synthetic_identities WHERE id=NEW.synthetic_identity_id FOR SHARE;
            IF identity_row.id IS NULL OR identity_row.authority_kind <> 'CANONICAL_QA'
               OR identity_row.canonical_asset_id <> NEW.source_asset_id THEN
                RAISE EXCEPTION 'M5 cohort requires canonical synthetic identity asset authority';
            END IF;
            SELECT * INTO accepted_qa FROM synthetic_qa_runs WHERE id=identity_row.accepted_qa_run_id FOR SHARE;
            IF accepted_qa.id IS NULL OR accepted_qa.status <> 'PASSED'
               OR accepted_qa.normalized_asset_id <> NEW.source_asset_id THEN
                RAISE EXCEPTION 'M5 cohort requires passed identity QA authority';
            END IF;
            SELECT id INTO source_signature_id FROM similarity_signatures
             WHERE asset_id=NEW.source_asset_id AND normalized_sha256=NEW.source_asset_sha256 FOR SHARE;
            IF source_signature_id IS NULL THEN RAISE EXCEPTION 'M5 cohort requires matching similarity signature'; END IF;
            IF NOT EXISTS (SELECT 1 FROM synthetic_evaluation_policies WHERE id=NEW.policy_id AND approval_status='APPROVED') THEN RAISE EXCEPTION 'M5 cohort requires approved policy'; END IF;
            IF EXISTS (SELECT 1 FROM json_array_elements_text(NEW.dimension_keys) AS x LEFT JOIN synthetic_evaluation_dimension_rules r ON r.policy_id=NEW.policy_id AND r.dimension_key=x WHERE r.id IS NULL)
               OR (SELECT count(*) <> count(DISTINCT value) FROM json_array_elements_text(NEW.dimension_keys) AS value) THEN RAISE EXCEPTION 'M5 cohort dimensions are invalid'; END IF;
            IF NEW.duplicate_cluster_id IS NOT NULL THEN
                PERFORM pg_advisory_xact_lock(hashtextextended(NEW.policy_id || ':' || NEW.duplicate_cluster_id, 0));
                SELECT status INTO cluster_status FROM duplicate_clusters WHERE id=NEW.duplicate_cluster_id FOR UPDATE;
                IF cluster_status <> 'FINALIZED' THEN RAISE EXCEPTION 'M5 cohort requires finalized duplicate cluster'; END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM duplicate_cluster_memberships membership
                     WHERE membership.cluster_id=NEW.duplicate_cluster_id
                       AND membership.signature_id=source_signature_id
                ) THEN
                    RAISE EXCEPTION 'M5 cohort duplicate cluster does not contain source signature';
                END IF;
                IF EXISTS (SELECT 1 FROM evaluation_cohort_assignments e WHERE e.policy_id=NEW.policy_id AND e.duplicate_cluster_id=NEW.duplicate_cluster_id AND e.split<>NEW.split) THEN RAISE EXCEPTION 'M5 duplicate cluster split leakage'; END IF;
            END IF;
            IF EXISTS (SELECT 1 FROM evaluation_cohort_assignments e WHERE e.policy_id=NEW.policy_id AND e.split<>NEW.split AND (e.synthetic_identity_id=NEW.synthetic_identity_id OR e.source_asset_id=NEW.source_asset_id OR e.source_asset_sha256=NEW.source_asset_sha256)) THEN RAISE EXCEPTION 'M5 cohort split leakage'; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_evaluation_cohort_assignments_guard BEFORE INSERT OR UPDATE OR DELETE ON evaluation_cohort_assignments FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_cohort_assignment();

        CREATE FUNCTION mirror_validate_m5_isolation_report() RETURNS trigger AS $$
        DECLARE run_row transform_runs%ROWTYPE; specification variant_specifications%ROWTYPE;
                policy_row synthetic_evaluation_policies%ROWTYPE;
                rule_row synthetic_evaluation_dimension_rules%ROWTYPE;
                expected_controls text[]; actual_controls text[];
                expected_reasons text[] := ARRAY[]::text[]; actual_reasons text[];
                computed_non_target integer; expected_conclusion varchar(16);
                canonical_result text; expected_digest varchar(64);
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') THEN RAISE EXCEPTION 'M5 isolation report is immutable'; END IF;
            SELECT * INTO run_row FROM transform_runs WHERE id=NEW.transform_run_id FOR SHARE;
            IF run_row.id IS NULL OR run_row.status <> 'COMPLETED' OR NOT EXISTS (SELECT 1 FROM synthetic_qa_runs WHERE transform_run_id=run_row.id AND status='PASSED') THEN RAISE EXCEPTION 'M5 report requires completed M4 authority'; END IF;
            SELECT * INTO policy_row FROM synthetic_evaluation_policies
             WHERE id=NEW.policy_id AND approval_status='APPROVED' FOR SHARE;
            SELECT * INTO rule_row FROM synthetic_evaluation_dimension_rules
             WHERE policy_id=NEW.policy_id AND dimension_key=NEW.target_dimension FOR SHARE;
            IF policy_row.id IS NULL OR rule_row.id IS NULL THEN RAISE EXCEPTION 'M5 report requires approved policy dimension'; END IF;
            SELECT * INTO specification FROM variant_specifications WHERE id=run_row.variant_specification_id FOR SHARE;
            IF specification.id IS NULL OR specification.target_dimension <> NEW.target_dimension
               OR NEW.requested_delta_ppm <> (CASE specification.direction
                   WHEN 'INCREASE' THEN specification.relative_magnitude_ppm
                   WHEN 'DECREASE' THEN -specification.relative_magnitude_ppm
               END) THEN RAISE EXCEPTION 'M5 report must bind the transform target and signed requested delta'; END IF;
            SELECT array_agg(value ORDER BY value) INTO expected_controls
              FROM json_array_elements_text(rule_row.control_dimensions) value;
            SELECT array_agg(key ORDER BY key) INTO actual_controls FROM jsonb_object_keys(NEW.control_deltas::jsonb) key;
            IF expected_controls IS DISTINCT FROM actual_controls
               OR EXISTS (SELECT 1 FROM jsonb_each(NEW.control_deltas::jsonb) pair
                           WHERE jsonb_typeof(pair.value) <> 'number'
                              OR pair.value::text !~ '^-?[0-9]+$'
                              OR (pair.value::text)::integer NOT BETWEEN -5000000 AND 5000000) THEN
                RAISE EXCEPTION 'M5 report control deltas are invalid';
            END IF;
            IF NEW.target_error_ppm <> abs(NEW.measured_target_delta_ppm - NEW.requested_delta_ppm) THEN RAISE EXCEPTION 'M5 report target error mismatch'; END IF;
            SELECT max(abs((pair.value::text)::integer)) INTO computed_non_target
              FROM jsonb_each(NEW.control_deltas::jsonb) pair;
            IF NEW.non_target_drift_ppm IS DISTINCT FROM computed_non_target THEN
                RAISE EXCEPTION 'M5 report non-target drift mismatch';
            END IF;
            IF (NEW.requested_delta_ppm > 0) IS DISTINCT FROM (NEW.measured_target_delta_ppm > 0) THEN
                expected_reasons := array_append(expected_reasons, 'TARGET_DIRECTION_MISMATCH');
            END IF;
            IF NEW.target_error_ppm > rule_row.target_error_tolerance_ppm THEN
                expected_reasons := array_append(expected_reasons, 'TARGET_ERROR_EXCEEDED');
            END IF;
            IF NEW.non_target_drift_ppm > rule_row.control_drift_tolerance_ppm THEN
                expected_reasons := array_append(expected_reasons, 'CONTROL_DRIFT_EXCEEDED');
            END IF;
            IF NEW.repeat_variance_ppm > rule_row.repeat_variance_tolerance_ppm THEN
                expected_reasons := array_append(expected_reasons, 'REPEAT_VARIANCE_EXCEEDED');
            END IF;
            IF NEW.platform_variance_ppm > rule_row.platform_variance_tolerance_ppm THEN
                expected_reasons := array_append(expected_reasons, 'PLATFORM_VARIANCE_EXCEEDED');
            END IF;
            IF NOT NEW.artifact_gate_passed THEN
                expected_reasons := array_append(expected_reasons, 'ARTIFACT_GATE_FAILED');
            END IF;
            IF NOT NEW.reliability_gate_passed THEN
                expected_reasons := array_append(expected_reasons, 'RELIABILITY_GATE_FAILED');
            END IF;
            SELECT coalesce(array_agg(reason ORDER BY reason), ARRAY[]::text[])
              INTO expected_reasons FROM unnest(expected_reasons) reason;
            SELECT coalesce(array_agg(value), ARRAY[]::text[])
              INTO actual_reasons FROM json_array_elements_text(NEW.reason_codes) value;
            expected_conclusion := CASE WHEN cardinality(expected_reasons)=0 THEN 'PASSED' ELSE 'REJECTED' END;
            IF NEW.conclusion <> expected_conclusion OR actual_reasons IS DISTINCT FROM expected_reasons THEN
                RAISE EXCEPTION 'M5 report conclusion or reason codes mismatch';
            END IF;
            canonical_result :=
                '{"conclusion":"' || expected_conclusion ||
                '","non_target_drift_ppm":' || NEW.non_target_drift_ppm::text ||
                ',"policy_digest":"' || policy_row.content_digest ||
                '","policy_version":"' || policy_row.version ||
                '","reason_codes":' || replace(to_json(expected_reasons)::text, ', ', ',') ||
                ',"target_dimension":"' || NEW.target_dimension ||
                '","target_error_ppm":' || NEW.target_error_ppm::text ||
                ',"transform_run_reference":"' || NEW.transform_run_id || '"}';
            expected_digest := encode(sha256((
                'mirror.synthetic-dataset/IsolationReportResult/v1' || E'\\n' || canonical_result
            )::bytea), 'hex');
            IF NEW.content_digest IS DISTINCT FROM expected_digest THEN
                RAISE EXCEPTION 'M5 isolation report digest mismatch';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_isolation_reports_guard BEFORE INSERT OR UPDATE OR DELETE ON isolation_reports FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_isolation_report();

        CREATE FUNCTION mirror_validate_m5_signature() RETURNS trigger AS $$
        DECLARE asset_row assets%ROWTYPE; expected_digest varchar(64);
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') THEN RAISE EXCEPTION 'M5 similarity signature is immutable'; END IF;
            SELECT * INTO asset_row FROM assets WHERE id=NEW.asset_id FOR SHARE;
            IF asset_row.id IS NULL OR asset_row.owner_user_id IS NOT NULL OR asset_row.asset_role <> 'synthetic' OR NOT asset_row.synthetic OR asset_row.internal_purpose <> 'synthetic_dataset' OR asset_row.sha256 <> NEW.normalized_sha256 OR asset_row.width <> NEW.width OR asset_row.height <> NEW.height THEN RAISE EXCEPTION 'M5 signature must bind matching synthetic asset'; END IF;
            expected_digest := encode(sha256((
                NEW.schema_version || E'\\n' ||
                '{"algorithm_version":"' || NEW.algorithm_version ||
                '","height":' || NEW.height::text ||
                ',"normalized_sha256":"' || NEW.normalized_sha256 ||
                '","phash_hex":"' || NEW.phash_hex ||
                '","width":' || NEW.width::text || '}'
            )::bytea), 'hex');
            IF NEW.content_digest IS DISTINCT FROM expected_digest THEN
                RAISE EXCEPTION 'M5 similarity signature digest mismatch';
            END IF;
            IF EXISTS (SELECT 1 FROM similarity_signatures WHERE normalized_sha256=NEW.normalized_sha256) THEN RAISE EXCEPTION 'M5 exact duplicate is a hard reject'; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_similarity_signatures_guard BEFORE INSERT OR UPDATE OR DELETE ON similarity_signatures FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_signature();

        CREATE FUNCTION mirror_validate_m5_similarity_pair() RETURNS trigger AS $$
        DECLARE left_row similarity_signatures%ROWTYPE; right_row similarity_signatures%ROWTYPE;
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') THEN RAISE EXCEPTION 'M5 similarity pair evidence is immutable'; END IF;
            SELECT * INTO left_row FROM similarity_signatures WHERE id=NEW.left_signature_id FOR SHARE; SELECT * INTO right_row FROM similarity_signatures WHERE id=NEW.right_signature_id FOR SHARE;
            IF left_row.id IS NULL OR right_row.id IS NULL OR left_row.asset_id=right_row.asset_id OR left_row.algorithm_version<>NEW.algorithm_version OR right_row.algorithm_version<>NEW.algorithm_version OR left_row.normalized_sha256=right_row.normalized_sha256 THEN RAISE EXCEPTION 'M5 similarity pair is incompatible'; END IF;
            IF NEW.hamming_distance <> bit_count(
                (('x' || left_row.phash_hex)::bit(64)) # (('x' || right_row.phash_hex)::bit(64))
            ) THEN RAISE EXCEPTION 'M5 similarity pair Hamming distance mismatch'; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_similarity_pair_evidence_guard BEFORE INSERT OR UPDATE OR DELETE ON similarity_pair_evidence FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_similarity_pair();

        CREATE FUNCTION mirror_validate_m5_cluster() RETURNS trigger AS $$
        BEGIN
            IF TG_OP='DELETE' THEN RAISE EXCEPTION 'M5 duplicate cluster is append-only'; END IF;
            IF TG_OP='UPDATE' AND (OLD.id<>NEW.id OR OLD.created_at<>NEW.created_at OR OLD.algorithm_version<>NEW.algorithm_version OR OLD.cluster_digest<>NEW.cluster_digest OR NOT (OLD.status='OPEN' AND NEW.status='FINALIZED') OR OLD.finalized_at IS NOT NULL OR NEW.finalized_at IS NULL) THEN RAISE EXCEPTION 'invalid M5 duplicate cluster transition'; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_duplicate_clusters_guard BEFORE INSERT OR UPDATE OR DELETE ON duplicate_clusters FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_cluster();

        CREATE FUNCTION mirror_validate_m5_cluster_member() RETURNS trigger AS $$
        DECLARE cluster_row duplicate_clusters%ROWTYPE; signature_row similarity_signatures%ROWTYPE;
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') THEN RAISE EXCEPTION 'M5 cluster membership is immutable'; END IF;
            SELECT * INTO cluster_row FROM duplicate_clusters WHERE id=NEW.cluster_id FOR UPDATE; SELECT * INTO signature_row FROM similarity_signatures WHERE id=NEW.signature_id FOR SHARE;
            IF cluster_row.id IS NULL OR cluster_row.status<>'OPEN' OR signature_row.id IS NULL OR signature_row.algorithm_version<>cluster_row.algorithm_version THEN RAISE EXCEPTION 'invalid M5 cluster membership'; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_duplicate_cluster_memberships_guard BEFORE INSERT OR UPDATE OR DELETE ON duplicate_cluster_memberships FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_cluster_member();

        CREATE FUNCTION mirror_validate_m5_cluster_decision() RETURNS trigger AS $$
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') THEN RAISE EXCEPTION 'M5 cluster decision is immutable'; END IF;
            IF NOT EXISTS (SELECT 1 FROM duplicate_cluster_memberships WHERE cluster_id=NEW.cluster_id AND signature_id=NEW.signature_id) THEN RAISE EXCEPTION 'M5 decision requires cluster membership'; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_duplicate_cluster_decisions_guard BEFORE INSERT OR UPDATE OR DELETE ON duplicate_cluster_decisions FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_cluster_decision();

        CREATE FUNCTION mirror_validate_m5_diversity_report() RETURNS trigger AS $$
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') THEN RAISE EXCEPTION 'M5 diversity report is immutable'; END IF;
            IF NOT EXISTS (SELECT 1 FROM synthetic_evaluation_policies WHERE id=NEW.policy_id AND approval_status='APPROVED') OR lower(NEW.report_payload::text) ~ '(beauty|attractiveness|celebrity|race|ethnicity|ancestry|nationality|score|rank|percentile)' THEN RAISE EXCEPTION 'M5 diversity report contains prohibited authority'; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_diversity_reports_guard BEFORE INSERT OR UPDATE OR DELETE ON diversity_reports FOR EACH ROW EXECUTE FUNCTION mirror_validate_m5_diversity_report();
        """
    )


def upgrade() -> None:
    _create_tables()
    _install_guards()


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM synthetic_evaluation_policies) OR EXISTS (SELECT 1 FROM synthetic_evaluation_dimension_rules)
             OR EXISTS (SELECT 1 FROM evaluation_cohort_assignments) OR EXISTS (SELECT 1 FROM isolation_reports)
             OR EXISTS (SELECT 1 FROM similarity_signatures) OR EXISTS (SELECT 1 FROM similarity_pair_evidence)
             OR EXISTS (SELECT 1 FROM duplicate_clusters) OR EXISTS (SELECT 1 FROM duplicate_cluster_memberships)
             OR EXISTS (SELECT 1 FROM duplicate_cluster_decisions) OR EXISTS (SELECT 1 FROM diversity_reports) THEN
             RAISE EXCEPTION '0014 downgrade would discard durable M5 evaluation authority';
          END IF;
        END $$;
    """)
    for trigger, table in (
        ("trg_diversity_reports_guard", "diversity_reports"),
        ("trg_duplicate_cluster_decisions_guard", "duplicate_cluster_decisions"),
        ("trg_duplicate_cluster_memberships_guard", "duplicate_cluster_memberships"),
        ("trg_duplicate_clusters_guard", "duplicate_clusters"),
        ("trg_similarity_pair_evidence_guard", "similarity_pair_evidence"),
        ("trg_similarity_signatures_guard", "similarity_signatures"),
        ("trg_isolation_reports_guard", "isolation_reports"),
        ("trg_evaluation_cohort_assignments_guard", "evaluation_cohort_assignments"),
        ("trg_synthetic_evaluation_dimension_rules_guard", "synthetic_evaluation_dimension_rules"),
        ("trg_synthetic_evaluation_policies_guard", "synthetic_evaluation_policies"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    for function in (
        "mirror_validate_m5_diversity_report",
        "mirror_validate_m5_cluster_decision",
        "mirror_validate_m5_cluster_member",
        "mirror_validate_m5_cluster",
        "mirror_validate_m5_similarity_pair",
        "mirror_validate_m5_signature",
        "mirror_validate_m5_isolation_report",
        "mirror_validate_m5_cohort_assignment",
        "mirror_validate_m5_dimension_rule",
        "mirror_validate_m5_policy",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}()")
    op.drop_table("diversity_reports")
    op.drop_table("similarity_pair_evidence")
    for column in ("duplicate_cluster_id", "source_asset_id", "synthetic_identity_id", "policy_id"):
        op.drop_index(
            op.f(f"ix_evaluation_cohort_assignments_{column}"),
            table_name="evaluation_cohort_assignments",
        )
    op.drop_table("isolation_reports")
    op.drop_table("evaluation_cohort_assignments")
    op.drop_table("duplicate_cluster_decisions")
    op.drop_table("duplicate_cluster_memberships")
    op.drop_table("duplicate_clusters")
    op.drop_table("similarity_signatures")
    op.drop_index(
        op.f("ix_synthetic_evaluation_dimension_rules_policy_id"),
        table_name="synthetic_evaluation_dimension_rules",
    )
    op.drop_table("synthetic_evaluation_dimension_rules")
    op.drop_index(
        op.f("ix_synthetic_evaluation_policies_geometry_ontology_version_id"),
        table_name="synthetic_evaluation_policies",
    )
    op.drop_table("synthetic_evaluation_policies")
