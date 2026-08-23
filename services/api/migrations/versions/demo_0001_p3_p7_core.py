"""Branch-local P3-P7 algorithmic prototype authority.

Revision ID: demo_0001_p3_p7_core
Revises: 0014_m5_eval_authority
Create Date: 2026-08-23

PROTOTYPE_MIGRATION: TRUE
FORMAL_PHASE_AUTHORITY: FALSE
DIRECT_MAINLINE_CHERRY_PICK: FORBIDDEN
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "demo_0001_p3_p7_core"
down_revision: str | None = "0014_m5_eval_authority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROTOTYPE_MIGRATION = True
FORMAL_PHASE_AUTHORITY = False
DIRECT_MAINLINE_CHERRY_PICK = "FORBIDDEN"


def _common_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=112), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def _common_constraints(table_name: str) -> tuple[sa.Constraint, ...]:
    return (
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{32}$'",
            name=op.f(f"ck_{table_name}_id_shape"),
        ),
        sa.CheckConstraint(
            "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
            name=op.f(f"ck_{table_name}_schema_version_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'",
            name=op.f(f"ck_{table_name}_canonical_payload_object"),
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name=op.f(f"ck_{table_name}_content_digest_shape"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
        sa.UniqueConstraint(
            "content_digest",
            name=op.f(f"uq_{table_name}_content_digest"),
        ),
    )


def _create_session_and_p3_tables() -> None:
    op.create_table(
        "demo_actors",
        *_common_columns(),
        sa.Column("actor_kind", sa.String(length=32), nullable=False),
        sa.Column("credential_key_id", sa.String(length=64), nullable=False),
        sa.Column("authority_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
        *_common_constraints("demo_actors"),
        sa.UniqueConstraint(
            "credential_key_id",
            name=op.f("uq_demo_actors_credential_key_id"),
        ),
        sa.UniqueConstraint(
            "id",
            "actor_kind",
            name=op.f("uq_demo_actors_id_actor_kind"),
        ),
        sa.CheckConstraint(
            "actor_kind IN ('LOCAL_SINGLE_USER','AUTOMATED_TEST')",
            name=op.f("ck_demo_actors_actor_kind"),
        ),
        sa.CheckConstraint(
            "tombstoned_at IS NULL OR tombstoned_at >= created_at",
            name=op.f("ck_demo_actors_tombstone_not_before_creation"),
        ),
    )
    op.create_table(
        "demo_sessions",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("context_seed", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
        *_common_constraints("demo_sessions"),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_sessions_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            name=op.f("uq_demo_sessions_id_actor"),
        ),
        sa.CheckConstraint(
            "context_seed ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_sessions_context_seed_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(config) = 'object'",
            name=op.f("ck_demo_sessions_config_object"),
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR closed_at >= created_at",
            name=op.f("ck_demo_sessions_close_not_before_creation"),
        ),
        sa.CheckConstraint(
            "tombstoned_at IS NULL OR (closed_at IS NOT NULL AND tombstoned_at >= closed_at)",
            name=op.f("ck_demo_sessions_tombstone_order"),
        ),
    )
    op.create_table(
        "demo_synthetic_identities",
        *_common_columns(),
        sa.Column("formal_synthetic_identity_id", sa.String(length=32), nullable=False),
        sa.Column("formal_canonical_asset_id", sa.String(length=32), nullable=False),
        sa.Column("formal_canonical_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("formal_accepted_qa_run_id", sa.String(length=32), nullable=False),
        sa.Column("formal_accepted_qa_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("admission_sequence", sa.Integer(), nullable=False),
        sa.Column("admission_action", sa.String(length=16), nullable=False),
        sa.Column("admission_config_digest", sa.String(length=64), nullable=False),
        sa.Column("supersedes_id", sa.String(length=32), nullable=True),
        *_common_constraints("demo_synthetic_identities"),
        sa.ForeignKeyConstraint(
            ["formal_synthetic_identity_id"],
            ["synthetic_identities.id"],
            name=op.f(
                "fk_demo_synthetic_identities_formal_synthetic_identity_id_synthetic_identities"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["formal_canonical_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_synthetic_identities_formal_canonical_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["formal_accepted_qa_run_id"],
            ["synthetic_qa_runs.id"],
            name=op.f("fk_demo_synthetic_identities_formal_accepted_qa_run_id_synthetic_qa_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["demo_synthetic_identities.id"],
            name=op.f("fk_demo_synthetic_identities_supersedes_id_demo_synthetic_identities"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "formal_synthetic_identity_id",
            "admission_sequence",
            name=op.f("uq_demo_synthetic_identities_formal_sequence"),
        ),
        sa.UniqueConstraint(
            "supersedes_id",
            name=op.f("uq_demo_synthetic_identities_supersedes_id"),
        ),
        sa.CheckConstraint(
            "admission_sequence > 0",
            name=op.f("ck_demo_synthetic_identities_positive_admission_sequence"),
        ),
        sa.CheckConstraint(
            "admission_action IN ('ADMIT','REVOKE')",
            name=op.f("ck_demo_synthetic_identities_admission_action"),
        ),
        sa.CheckConstraint(
            "admission_config_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_synthetic_identities_admission_config_digest_shape"),
        ),
        sa.CheckConstraint(
            "formal_canonical_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_synthetic_identities_formal_canonical_asset_sha_shape"),
        ),
        sa.CheckConstraint(
            "formal_accepted_qa_snapshot_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_synthetic_identities_qa_snapshot_digest_shape"),
        ),
        sa.CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id <> id",
            name=op.f("ck_demo_synthetic_identities_not_self_superseding"),
        ),
    )
    op.create_table(
        "demo_face_observations",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("demo_synthetic_identity_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("analyzer_version", sa.String(length=64), nullable=False),
        sa.Column("runtime_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("config_digest", sa.String(length=64), nullable=False),
        sa.Column("repeat_count", sa.Integer(), nullable=False),
        sa.Column("observation_state", sa.String(length=24), nullable=False),
        sa.Column("unsupported_reason", sa.String(length=64), nullable=True),
        *_common_constraints("demo_face_observations"),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_face_observations_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_synthetic_identity_id"],
            ["demo_synthetic_identities.id"],
            name=op.f(
                "fk_demo_face_observations_demo_synthetic_identity_id_demo_synthetic_identities"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_face_observations_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_face_observations_id_actor_session"),
        ),
        sa.CheckConstraint(
            "source_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_face_observations_source_sha_shape"),
        ),
        sa.CheckConstraint(
            "runtime_manifest_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_face_observations_runtime_manifest_digest_shape"),
        ),
        sa.CheckConstraint(
            "config_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_face_observations_config_digest_shape"),
        ),
        sa.CheckConstraint(
            "repeat_count = 3",
            name=op.f("ck_demo_face_observations_three_repeats"),
        ),
        sa.CheckConstraint(
            "(observation_state = 'SUPPORTED' AND unsupported_reason IS NULL) OR "
            "(observation_state = 'UNSUPPORTED' AND unsupported_reason IS NOT NULL)",
            name=op.f("ck_demo_face_observations_observation_state_shape"),
        ),
    )
    op.create_table(
        "demo_face_observation_repeats",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("observation_id", sa.String(length=32), nullable=False),
        sa.Column("repeat_index", sa.Integer(), nullable=False),
        sa.Column("runtime_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("model_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("landmarks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pose", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quality", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("measurements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_face_observation_repeats"),
        sa.ForeignKeyConstraint(
            ["observation_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_face_observations.id",
                "demo_face_observations.demo_actor_id",
                "demo_face_observations.demo_session_id",
            ],
            name=op.f("fk_demo_face_observation_repeats_observation_owner"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "observation_id",
            "repeat_index",
            name=op.f("uq_demo_face_observation_repeats_observation_repeat"),
        ),
        sa.CheckConstraint(
            "repeat_index BETWEEN 1 AND 3",
            name=op.f("ck_demo_face_observation_repeats_repeat_index"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(landmarks) = 'array'",
            name=op.f("ck_demo_face_observation_repeats_landmarks_array"),
        ),
        sa.CheckConstraint(
            "jsonb_array_length(landmarks) = 478",
            name=op.f("ck_demo_face_observation_repeats_landmark_count"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(pose) = 'object'",
            name=op.f("ck_demo_face_observation_repeats_pose_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(quality) = 'object'",
            name=op.f("ck_demo_face_observation_repeats_quality_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(measurements) = 'object'",
            name=op.f("ck_demo_face_observation_repeats_measurements_object"),
        ),
    )
    op.create_table(
        "demo_baseline_face_models",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("observation_id", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("aggregation_version", sa.String(length=64), nullable=False),
        sa.Column("measurement_version", sa.String(length=64), nullable=False),
        sa.Column(
            "ordered_repeat_digests",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("measurements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reliability", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("uncertainty", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unsupported_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_baseline_face_models"),
        sa.ForeignKeyConstraint(
            ["observation_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_face_observations.id",
                "demo_face_observations.demo_actor_id",
                "demo_face_observations.demo_session_id",
            ],
            name=op.f("fk_demo_baseline_face_models_observation_owner"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "observation_id",
            "version",
            name=op.f("uq_demo_baseline_face_models_observation_version"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_baseline_face_models_id_actor_session"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_demo_baseline_face_models_positive_version"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(ordered_repeat_digests) = 'array' "
            "AND jsonb_array_length(ordered_repeat_digests) = 3",
            name=op.f("ck_demo_baseline_face_models_three_repeat_digests"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(measurements) = 'object'",
            name=op.f("ck_demo_baseline_face_models_measurements_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reliability) = 'object'",
            name=op.f("ck_demo_baseline_face_models_reliability_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(uncertainty) = 'object'",
            name=op.f("ck_demo_baseline_face_models_uncertainty_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(unsupported_state) = 'object'",
            name=op.f("ck_demo_baseline_face_models_unsupported_state_object"),
        ),
    )
    op.create_table(
        "demo_self_states",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("baseline_face_model_id", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("ontology_version", sa.String(length=64), nullable=False),
        sa.Column("derivation_version", sa.String(length=64), nullable=False),
        sa.Column("measurements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reliability", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("uncertainty", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "routing_eligibility",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        *_common_constraints("demo_self_states"),
        sa.ForeignKeyConstraint(
            ["baseline_face_model_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_baseline_face_models.id",
                "demo_baseline_face_models.demo_actor_id",
                "demo_baseline_face_models.demo_session_id",
            ],
            name=op.f("fk_demo_self_states_baseline_owner"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "baseline_face_model_id",
            "version",
            name=op.f("uq_demo_self_states_baseline_version"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_self_states_id_actor_session"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_demo_self_states_positive_version"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(measurements) = 'object'",
            name=op.f("ck_demo_self_states_measurements_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reliability) = 'object'",
            name=op.f("ck_demo_self_states_reliability_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(uncertainty) = 'object'",
            name=op.f("ck_demo_self_states_uncertainty_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(routing_eligibility) = 'object'",
            name=op.f("ck_demo_self_states_routing_eligibility_object"),
        ),
    )


def _create_p4_tables() -> None:
    op.create_table(
        "demo_question_banks",
        *_common_columns(),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("algorithm_config_digest", sa.String(length=64), nullable=False),
        sa.Column("routing_version", sa.String(length=64), nullable=False),
        sa.Column("stopping_version", sa.String(length=64), nullable=False),
        sa.Column("neighborhood_version", sa.String(length=64), nullable=False),
        sa.Column("pair_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("dimension_manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_question_banks"),
        sa.UniqueConstraint("version", name=op.f("uq_demo_question_banks_version")),
        sa.CheckConstraint(
            "algorithm_config_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_question_banks_algorithm_config_digest_shape"),
        ),
        sa.CheckConstraint(
            "pair_manifest_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_question_banks_pair_manifest_digest_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(dimension_manifest) = 'array'",
            name=op.f("ck_demo_question_banks_dimension_manifest_array"),
        ),
    )
    op.create_table(
        "demo_question_pairs",
        *_common_columns(),
        sa.Column("question_bank_id", sa.String(length=32), nullable=False),
        sa.Column("demo_synthetic_identity_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("left_asset_id", sa.String(length=32), nullable=False),
        sa.Column("left_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("right_asset_id", sa.String(length=32), nullable=False),
        sa.Column("right_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("left_asset_variant_id", sa.String(length=32), nullable=False),
        sa.Column("right_asset_variant_id", sa.String(length=32), nullable=False),
        sa.Column("dimension_key", sa.String(length=48), nullable=False),
        sa.Column("magnitude_ppm", sa.Integer(), nullable=False),
        sa.Column("left_delta_ppm", sa.Integer(), nullable=False),
        sa.Column("right_delta_ppm", sa.Integer(), nullable=False),
        sa.Column("pair_quality_ppm", sa.Integer(), nullable=False),
        sa.Column("qa_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_question_pairs"),
        sa.ForeignKeyConstraint(
            ["question_bank_id"],
            ["demo_question_banks.id"],
            name=op.f("fk_demo_question_pairs_question_bank_id_demo_question_banks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_synthetic_identity_id"],
            ["demo_synthetic_identities.id"],
            name=op.f(
                "fk_demo_question_pairs_demo_synthetic_identity_id_demo_synthetic_identities"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_question_pairs_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["left_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_question_pairs_left_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["right_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_question_pairs_right_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["left_asset_variant_id"],
            ["asset_variants.id"],
            name=op.f("fk_demo_question_pairs_left_asset_variant_id_asset_variants"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["right_asset_variant_id"],
            ["asset_variants.id"],
            name=op.f("fk_demo_question_pairs_right_asset_variant_id_asset_variants"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "question_bank_id",
            "demo_synthetic_identity_id",
            "dimension_key",
            "magnitude_ppm",
            name=op.f("uq_demo_question_pairs_bank_identity_dimension_magnitude"),
        ),
        sa.CheckConstraint(
            "source_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_question_pairs_source_sha_shape"),
        ),
        sa.CheckConstraint(
            "left_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_question_pairs_left_sha_shape"),
        ),
        sa.CheckConstraint(
            "right_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_question_pairs_right_sha_shape"),
        ),
        sa.CheckConstraint(
            "left_asset_id <> right_asset_id AND source_asset_id <> left_asset_id "
            "AND source_asset_id <> right_asset_id",
            name=op.f("ck_demo_question_pairs_distinct_pair_assets"),
        ),
        sa.CheckConstraint(
            "magnitude_ppm > 0",
            name=op.f("ck_demo_question_pairs_positive_magnitude"),
        ),
        sa.CheckConstraint(
            "left_delta_ppm = -magnitude_ppm AND right_delta_ppm = magnitude_ppm",
            name=op.f("ck_demo_question_pairs_opposite_pair_deltas"),
        ),
        sa.CheckConstraint(
            "pair_quality_ppm BETWEEN 0 AND 1000000",
            name=op.f("ck_demo_question_pairs_pair_quality_range"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(qa_payload) = 'object'",
            name=op.f("ck_demo_question_pairs_qa_payload_object"),
        ),
    )
    op.create_table(
        "demo_questionnaire_runs",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("question_bank_id", sa.String(length=32), nullable=False),
        sa.Column("self_state_id", sa.String(length=32), nullable=False),
        sa.Column("algorithm_config_digest", sa.String(length=64), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("max_questions", sa.Integer(), nullable=False),
        sa.Column("initial_posterior", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_questionnaire_runs"),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_questionnaire_runs_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_bank_id"],
            ["demo_question_banks.id"],
            name=op.f("fk_demo_questionnaire_runs_question_bank_id_demo_question_banks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["self_state_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_self_states.id",
                "demo_self_states.demo_actor_id",
                "demo_self_states.demo_session_id",
            ],
            name=op.f("fk_demo_questionnaire_runs_self_state_owner"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_questionnaire_runs_id_actor_session"),
        ),
        sa.CheckConstraint(
            "algorithm_config_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_questionnaire_runs_algorithm_config_digest_shape"),
        ),
        sa.CheckConstraint(
            "max_questions BETWEEN 12 AND 16",
            name=op.f("ck_demo_questionnaire_runs_question_limit"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(initial_posterior) = 'object'",
            name=op.f("ck_demo_questionnaire_runs_initial_posterior_object"),
        ),
    )
    op.create_table(
        "demo_questionnaire_steps",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("questionnaire_run_id", sa.String(length=32), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("question_pair_id", sa.String(length=32), nullable=True),
        sa.Column("routing_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "response_snapshot",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("posterior_before", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("posterior_after", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scheduler_version", sa.String(length=64), nullable=False),
        *_common_constraints("demo_questionnaire_steps"),
        sa.ForeignKeyConstraint(
            ["questionnaire_run_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_questionnaire_runs.id",
                "demo_questionnaire_runs.demo_actor_id",
                "demo_questionnaire_runs.demo_session_id",
            ],
            name=op.f("fk_demo_questionnaire_steps_run_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_pair_id"],
            ["demo_question_pairs.id"],
            name=op.f("fk_demo_questionnaire_steps_question_pair_id_demo_question_pairs"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "questionnaire_run_id",
            "event_sequence",
            name=op.f("uq_demo_questionnaire_steps_run_event_sequence"),
        ),
        sa.CheckConstraint(
            "event_sequence > 0",
            name=op.f("ck_demo_questionnaire_steps_positive_event_sequence"),
        ),
        sa.CheckConstraint(
            "step_number IS NULL OR step_number > 0",
            name=op.f("ck_demo_questionnaire_steps_positive_step_number"),
        ),
        sa.CheckConstraint(
            "event_type IN ('PRESENTED','RESPONDED','STOPPED','INVALIDATED')",
            name=op.f("ck_demo_questionnaire_steps_event_type"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(routing_snapshot) = 'object'",
            name=op.f("ck_demo_questionnaire_steps_routing_snapshot_object"),
        ),
        sa.CheckConstraint(
            "response_snapshot IS NULL OR jsonb_typeof(response_snapshot) = 'object'",
            name=op.f("ck_demo_questionnaire_steps_response_snapshot_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(posterior_before) = 'object'",
            name=op.f("ck_demo_questionnaire_steps_posterior_before_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(posterior_after) = 'object'",
            name=op.f("ck_demo_questionnaire_steps_posterior_after_object"),
        ),
    )


def _create_p5_tables() -> None:
    op.create_table(
        "demo_desired_delta_profiles",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("self_state_id", sa.String(length=32), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("as_of_event_sequence", sa.BigInteger(), nullable=False),
        sa.Column("compilation_watermark", sa.String(length=64), nullable=False),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_digests", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("restraint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_desired_delta_profiles"),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_desired_delta_profiles_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_desired_delta_profiles_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["self_state_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_self_states.id",
                "demo_self_states.demo_actor_id",
                "demo_self_states.demo_session_id",
            ],
            name=op.f("fk_demo_desired_delta_profiles_self_state_owner"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "version",
            name=op.f("uq_demo_desired_delta_profiles_actor_version"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_demo_desired_delta_profiles_positive_version"),
        ),
        sa.CheckConstraint(
            "as_of_event_sequence >= 0",
            name=op.f("ck_demo_desired_delta_profiles_nonnegative_event_sequence"),
        ),
        sa.CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_desired_delta_profiles_watermark_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(dimensions) = 'object'",
            name=op.f("ck_demo_desired_delta_profiles_dimensions_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_digests) = 'array'",
            name=op.f("ck_demo_desired_delta_profiles_evidence_digests_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(restraint) = 'object'",
            name=op.f("ck_demo_desired_delta_profiles_restraint_object"),
        ),
    )
    op.create_table(
        "demo_style_profiles",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=True),
        sa.Column("desired_delta_profile_id", sa.String(length=32), nullable=True),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("as_of_event_sequence", sa.BigInteger(), nullable=False),
        sa.Column("compilation_watermark", sa.String(length=64), nullable=False),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("negative_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_digests", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_style_profiles"),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_style_profiles_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_style_profiles_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["desired_delta_profile_id"],
            ["demo_desired_delta_profiles.id"],
            name=op.f(
                "fk_demo_style_profiles_desired_delta_profile_id_demo_desired_delta_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "version",
            name=op.f("uq_demo_style_profiles_actor_version"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_demo_style_profiles_positive_version"),
        ),
        sa.CheckConstraint(
            "as_of_event_sequence >= 0",
            name=op.f("ck_demo_style_profiles_nonnegative_event_sequence"),
        ),
        sa.CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_style_profiles_watermark_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(preferences) = 'object'",
            name=op.f("ck_demo_style_profiles_preferences_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(negative_evidence) = 'array'",
            name=op.f("ck_demo_style_profiles_negative_evidence_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_digests) = 'array'",
            name=op.f("ck_demo_style_profiles_evidence_digests_array"),
        ),
    )
    op.create_table(
        "demo_identity_constraints",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=True),
        sa.Column("self_state_id", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("constraint_scope", sa.String(length=24), nullable=False),
        sa.Column("source_event_digests", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("locks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bounds", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "prohibited_operations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        *_common_constraints("demo_identity_constraints"),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_identity_constraints_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_identity_constraints_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["self_state_id"],
            ["demo_self_states.id"],
            name=op.f("fk_demo_identity_constraints_self_state_id_demo_self_states"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "version",
            name=op.f("uq_demo_identity_constraints_actor_version"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_demo_identity_constraints_positive_version"),
        ),
        sa.CheckConstraint(
            "constraint_scope IN ('PERSISTENT','SESSION_OVERRIDE')",
            name=op.f("ck_demo_identity_constraints_constraint_scope"),
        ),
        sa.CheckConstraint(
            "(constraint_scope = 'PERSISTENT' AND demo_session_id IS NULL) OR "
            "(constraint_scope = 'SESSION_OVERRIDE' AND demo_session_id IS NOT NULL)",
            name=op.f("ck_demo_identity_constraints_constraint_scope_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_event_digests) = 'array'",
            name=op.f("ck_demo_identity_constraints_source_event_digests_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(locks) = 'object'",
            name=op.f("ck_demo_identity_constraints_locks_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(bounds) = 'object'",
            name=op.f("ck_demo_identity_constraints_bounds_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(prohibited_operations) = 'array'",
            name=op.f("ck_demo_identity_constraints_prohibited_operations_array"),
        ),
    )
    op.create_table(
        "demo_self_transfer_runs",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("desired_delta_profile_id", sa.String(length=32), nullable=False),
        sa.Column("record_kind", sa.String(length=16), nullable=False),
        sa.Column("request_run_id", sa.String(length=32), nullable=True),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=True),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("result_asset_id", sa.String(length=32), nullable=True),
        sa.Column("requested_delta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "measured_delta",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "non_target_drift",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("verifier_digest", sa.String(length=64), nullable=True),
        sa.Column("user_outcome", sa.String(length=24), nullable=True),
        *_common_constraints("demo_self_transfer_runs"),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_self_transfer_runs_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["desired_delta_profile_id"],
            ["demo_desired_delta_profiles.id"],
            name=op.f(
                "fk_demo_self_transfer_runs_desired_delta_profile_id_demo_desired_delta_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_run_id"],
            ["demo_self_transfer_runs.id"],
            name=op.f("fk_demo_self_transfer_runs_request_run_id_demo_self_transfer_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_self_transfer_runs_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["result_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_self_transfer_runs_result_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_self_transfer_runs_id_actor_session"),
        ),
        sa.CheckConstraint(
            "record_kind IN ('REQUEST','RESULT')",
            name=op.f("ck_demo_self_transfer_runs_record_kind"),
        ),
        sa.CheckConstraint(
            "(record_kind = 'REQUEST' AND request_run_id IS NULL AND result_asset_id IS NULL "
            "AND measured_delta IS NULL AND non_target_drift IS NULL AND verifier_digest IS NULL "
            "AND user_outcome IS NULL) OR "
            "(record_kind = 'RESULT' AND request_run_id IS NOT NULL "
            "AND demo_job_binding_id IS NOT NULL AND result_asset_id IS NOT NULL "
            "AND measured_delta IS NOT NULL AND non_target_drift IS NOT NULL "
            "AND verifier_digest IS NOT NULL "
            "AND user_outcome IN ('ACCEPTED','REJECTED','ADJUSTED'))",
            name=op.f("ck_demo_self_transfer_runs_record_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(requested_delta) = 'object'",
            name=op.f("ck_demo_self_transfer_runs_requested_delta_object"),
        ),
        sa.CheckConstraint(
            "measured_delta IS NULL OR jsonb_typeof(measured_delta) = 'object'",
            name=op.f("ck_demo_self_transfer_runs_measured_delta_object"),
        ),
        sa.CheckConstraint(
            "non_target_drift IS NULL OR jsonb_typeof(non_target_drift) = 'object'",
            name=op.f("ck_demo_self_transfer_runs_non_target_drift_object"),
        ),
        sa.CheckConstraint(
            "verifier_digest IS NULL OR verifier_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_self_transfer_runs_verifier_digest_shape"),
        ),
        sa.CheckConstraint(
            "result_asset_id IS NULL OR source_asset_id <> result_asset_id",
            name=op.f("ck_demo_self_transfer_runs_distinct_source_result"),
        ),
    )
    op.create_table(
        "demo_reference_profiles",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=True),
        sa.Column("desired_delta_profile_id", sa.String(length=32), nullable=False),
        sa.Column("style_profile_id", sa.String(length=32), nullable=True),
        sa.Column("identity_constraints_id", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_assets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("analysis_version", sa.String(length=64), nullable=False),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column("structured_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_digests", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_reference_profiles"),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_reference_profiles_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_reference_profiles_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["desired_delta_profile_id"],
            ["demo_desired_delta_profiles.id"],
            name=op.f(
                "fk_demo_reference_profiles_desired_delta_profile_id_demo_desired_delta_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["style_profile_id"],
            ["demo_style_profiles.id"],
            name=op.f("fk_demo_reference_profiles_style_profile_id_demo_style_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["identity_constraints_id"],
            ["demo_identity_constraints.id"],
            name=op.f(
                "fk_demo_reference_profiles_identity_constraints_id_demo_identity_constraints"
            ),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "version",
            name=op.f("uq_demo_reference_profiles_actor_version"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_demo_reference_profiles_positive_version"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_assets) = 'array'",
            name=op.f("ck_demo_reference_profiles_source_assets_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(structured_profile) = 'object'",
            name=op.f("ck_demo_reference_profiles_structured_profile_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_digests) = 'array'",
            name=op.f("ck_demo_reference_profiles_evidence_digests_array"),
        ),
    )


def _create_p6_tables() -> None:
    op.create_table(
        "demo_editing_sessions",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("desired_delta_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("style_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("identity_constraints_digest", sa.String(length=64), nullable=False),
        sa.Column("context_digest", sa.String(length=64), nullable=False),
        sa.Column("instruction_digest", sa.String(length=64), nullable=False),
        sa.Column("tool_registry_version", sa.String(length=64), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
        *_common_constraints("demo_editing_sessions"),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_editing_sessions_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_editing_sessions_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_editing_sessions_id_actor_session"),
        ),
        sa.CheckConstraint(
            "source_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_editing_sessions_source_sha_shape"),
        ),
        sa.CheckConstraint(
            "desired_delta_profile_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_editing_sessions_desired_delta_digest_shape"),
        ),
        sa.CheckConstraint(
            "style_profile_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_editing_sessions_style_digest_shape"),
        ),
        sa.CheckConstraint(
            "identity_constraints_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_editing_sessions_constraints_digest_shape"),
        ),
        sa.CheckConstraint(
            "context_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_editing_sessions_context_digest_shape"),
        ),
        sa.CheckConstraint(
            "instruction_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_editing_sessions_instruction_digest_shape"),
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR closed_at >= created_at",
            name=op.f("ck_demo_editing_sessions_close_not_before_creation"),
        ),
        sa.CheckConstraint(
            "tombstoned_at IS NULL OR (closed_at IS NOT NULL AND tombstoned_at >= closed_at)",
            name=op.f("ck_demo_editing_sessions_tombstone_order"),
        ),
    )
    op.create_table(
        "demo_image_versions",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("editing_session_id", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.String(length=32), nullable=True),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("result_asset_id", sa.String(length=32), nullable=False),
        sa.Column("result_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("result_asset_variant_id", sa.String(length=32), nullable=False),
        sa.Column("version_kind", sa.String(length=24), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=True),
        sa.Column("tool_run_digest", sa.String(length=64), nullable=True),
        sa.Column("verifier_digest", sa.String(length=64), nullable=True),
        *_common_constraints("demo_image_versions"),
        sa.ForeignKeyConstraint(
            ["editing_session_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_editing_sessions.id",
                "demo_editing_sessions.demo_actor_id",
                "demo_editing_sessions.demo_session_id",
            ],
            name=op.f("fk_demo_image_versions_editing_session_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["demo_image_versions.id"],
            name=op.f("fk_demo_image_versions_parent_version_id_demo_image_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_image_versions_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["result_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_image_versions_result_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["result_asset_variant_id"],
            ["asset_variants.id"],
            name=op.f("fk_demo_image_versions_result_asset_variant_id_asset_variants"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "editing_session_id",
            "sequence",
            name=op.f("uq_demo_image_versions_session_sequence"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_image_versions_id_actor_session"),
        ),
        sa.CheckConstraint(
            "sequence >= 0",
            name=op.f("ck_demo_image_versions_nonnegative_sequence"),
        ),
        sa.CheckConstraint(
            "(sequence = 0 AND parent_version_id IS NULL AND version_kind = 'ORIGINAL' "
            "AND plan_digest IS NULL AND tool_run_digest IS NULL AND verifier_digest IS NULL) OR "
            "(sequence > 0 AND parent_version_id IS NOT NULL "
            "AND version_kind IN ('EDITED','RESTORED','ROLLED_BACK','QUARANTINED') "
            "AND plan_digest IS NOT NULL AND tool_run_digest IS NOT NULL "
            "AND verifier_digest IS NOT NULL)",
            name=op.f("ck_demo_image_versions_lineage_authority_shape"),
        ),
        sa.CheckConstraint(
            "source_asset_id <> result_asset_id",
            name=op.f("ck_demo_image_versions_distinct_source_result"),
        ),
        sa.CheckConstraint(
            "source_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_image_versions_source_asset_sha_shape"),
        ),
        sa.CheckConstraint(
            "result_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_image_versions_result_asset_sha_shape"),
        ),
        sa.CheckConstraint(
            "version_kind IN ('ORIGINAL','EDITED','RESTORED','ROLLED_BACK','QUARANTINED')",
            name=op.f("ck_demo_image_versions_version_kind"),
        ),
        sa.CheckConstraint(
            "plan_digest IS NULL OR plan_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_image_versions_plan_digest_shape"),
        ),
        sa.CheckConstraint(
            "tool_run_digest IS NULL OR tool_run_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_image_versions_tool_run_digest_shape"),
        ),
        sa.CheckConstraint(
            "verifier_digest IS NULL OR verifier_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_image_versions_verifier_digest_shape"),
        ),
    )
    op.create_table(
        "demo_edit_plans",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("editing_session_id", sa.String(length=32), nullable=False),
        sa.Column("input_image_version_id", sa.String(length=32), nullable=False),
        sa.Column("record_kind", sa.String(length=16), nullable=False),
        sa.Column("request_plan_id", sa.String(length=32), nullable=True),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("desired_delta_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("style_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("identity_constraints_digest", sa.String(length=64), nullable=False),
        sa.Column("instruction_digest", sa.String(length=64), nullable=False),
        sa.Column("planner_version", sa.String(length=64), nullable=False),
        sa.Column("tool_registry_version", sa.String(length=64), nullable=False),
        sa.Column("operation_specs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_edit_plans"),
        sa.ForeignKeyConstraint(
            ["editing_session_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_editing_sessions.id",
                "demo_editing_sessions.demo_actor_id",
                "demo_editing_sessions.demo_session_id",
            ],
            name=op.f("fk_demo_edit_plans_editing_session_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["input_image_version_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_image_versions.id",
                "demo_image_versions.demo_actor_id",
                "demo_image_versions.demo_session_id",
            ],
            name=op.f("fk_demo_edit_plans_input_version_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_plan_id"],
            ["demo_edit_plans.id"],
            name=op.f("fk_demo_edit_plans_request_plan_id_demo_edit_plans"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "input_image_version_id",
            "plan_version",
            "record_kind",
            name=op.f("uq_demo_edit_plans_input_version_plan_version"),
        ),
        sa.UniqueConstraint(
            "request_plan_id",
            name=op.f("uq_demo_edit_plans_request_plan_id"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_edit_plans_id_actor_session"),
        ),
        sa.CheckConstraint(
            "record_kind IN ('REQUEST','RESULT')",
            name=op.f("ck_demo_edit_plans_record_kind"),
        ),
        sa.CheckConstraint(
            "(record_kind = 'REQUEST' AND request_plan_id IS NULL "
            "AND jsonb_array_length(operation_specs) = 0) OR "
            "(record_kind = 'RESULT' AND request_plan_id IS NOT NULL "
            "AND jsonb_array_length(operation_specs) > 0)",
            name=op.f("ck_demo_edit_plans_record_shape"),
        ),
        sa.CheckConstraint(
            "plan_version > 0",
            name=op.f("ck_demo_edit_plans_positive_plan_version"),
        ),
        sa.CheckConstraint(
            "desired_delta_profile_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_edit_plans_desired_delta_digest_shape"),
        ),
        sa.CheckConstraint(
            "style_profile_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_edit_plans_style_digest_shape"),
        ),
        sa.CheckConstraint(
            "identity_constraints_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_edit_plans_constraints_digest_shape"),
        ),
        sa.CheckConstraint(
            "instruction_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_edit_plans_instruction_digest_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(operation_specs) = 'array'",
            name=op.f("ck_demo_edit_plans_operation_specs_array"),
        ),
    )
    op.create_table(
        "demo_edit_operations",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("edit_plan_id", sa.String(length=32), nullable=False),
        sa.Column("operation_index", sa.Integer(), nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=False),
        sa.Column("operation_type", sa.String(length=48), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preserve", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_effect", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_edit_operations"),
        sa.ForeignKeyConstraint(
            ["edit_plan_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_edit_plans.id",
                "demo_edit_plans.demo_actor_id",
                "demo_edit_plans.demo_session_id",
            ],
            name=op.f("fk_demo_edit_operations_plan_owner"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "edit_plan_id",
            "operation_index",
            name=op.f("uq_demo_edit_operations_plan_index"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_edit_operations_id_actor_session"),
        ),
        sa.CheckConstraint(
            "operation_index >= 0",
            name=op.f("ck_demo_edit_operations_nonnegative_operation_index"),
        ),
        sa.CheckConstraint(
            "engine IN ('RASTER','GEOMETRY','MAKEUP','GENERATIVE')",
            name=op.f("ck_demo_edit_operations_engine"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(parameters) = 'object'",
            name=op.f("ck_demo_edit_operations_parameters_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(preserve) = 'array'",
            name=op.f("ck_demo_edit_operations_preserve_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(expected_effect) = 'object'",
            name=op.f("ck_demo_edit_operations_expected_effect_object"),
        ),
    )
    op.create_table(
        "demo_tool_runs",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("edit_operation_id", sa.String(length=32), nullable=False),
        sa.Column("edit_operation_digest", sa.String(length=64), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("formal_job_attempt_id", sa.String(length=32), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("tool_version", sa.String(length=64), nullable=False),
        sa.Column("input_asset_id", sa.String(length=32), nullable=False),
        sa.Column("input_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("output_asset_id", sa.String(length=32), nullable=True),
        sa.Column("output_asset_sha256", sa.String(length=64), nullable=True),
        sa.Column("effect_contract", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        *_common_constraints("demo_tool_runs"),
        sa.ForeignKeyConstraint(
            ["edit_operation_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_edit_operations.id",
                "demo_edit_operations.demo_actor_id",
                "demo_edit_operations.demo_session_id",
            ],
            name=op.f("fk_demo_tool_runs_operation_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["formal_job_attempt_id"],
            ["job_attempts.id"],
            name=op.f("fk_demo_tool_runs_formal_job_attempt_id_job_attempts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["input_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_tool_runs_input_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["output_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_tool_runs_output_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_tool_runs_id_actor_session"),
        ),
        sa.UniqueConstraint(
            "formal_job_attempt_id",
            "edit_operation_id",
            name=op.f("uq_demo_tool_runs_attempt_operation"),
        ),
        sa.CheckConstraint(
            "edit_operation_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_tool_runs_edit_operation_digest_shape"),
        ),
        sa.CheckConstraint(
            "input_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_tool_runs_input_sha_shape"),
        ),
        sa.CheckConstraint(
            "(output_asset_id IS NULL AND output_asset_sha256 IS NULL) OR "
            "(output_asset_id IS NOT NULL AND output_asset_sha256 ~ '^[0-9a-f]{64}$')",
            name=op.f("ck_demo_tool_runs_output_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(effect_contract) = 'object'",
            name=op.f("ck_demo_tool_runs_effect_contract_object"),
        ),
        sa.CheckConstraint(
            "outcome IN ('COMPLETED','REJECTED','FAILED','CANCELLED')",
            name=op.f("ck_demo_tool_runs_outcome"),
        ),
        sa.CheckConstraint(
            "(outcome = 'COMPLETED' AND output_asset_id IS NOT NULL) OR "
            "(outcome <> 'COMPLETED' AND output_asset_id IS NULL)",
            name=op.f("ck_demo_tool_runs_outcome_result_shape"),
        ),
    )
    op.create_table(
        "demo_verification_results",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("tool_run_id", sa.String(length=32), nullable=False),
        sa.Column("image_version_id", sa.String(length=32), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("output_asset_id", sa.String(length=32), nullable=False),
        sa.Column("output_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("verifier_version", sa.String(length=64), nullable=False),
        sa.Column("config_digest", sa.String(length=64), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("thresholds", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_verification_results"),
        sa.ForeignKeyConstraint(
            ["tool_run_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_tool_runs.id",
                "demo_tool_runs.demo_actor_id",
                "demo_tool_runs.demo_session_id",
            ],
            name=op.f("fk_demo_verification_results_tool_run_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["image_version_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_image_versions.id",
                "demo_image_versions.demo_actor_id",
                "demo_image_versions.demo_session_id",
            ],
            name=op.f("fk_demo_verification_results_image_version_owner"),
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["output_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_verification_results_output_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "output_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_verification_results_output_sha_shape"),
        ),
        sa.CheckConstraint(
            "config_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_verification_results_config_digest_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metrics) = 'object'",
            name=op.f("ck_demo_verification_results_metrics_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(thresholds) = 'object'",
            name=op.f("ck_demo_verification_results_thresholds_object"),
        ),
        sa.CheckConstraint(
            "outcome IN ('PASS','FAIL','HUMAN_REVIEW')",
            name=op.f("ck_demo_verification_results_outcome"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(reason_codes) = 'array'",
            name=op.f("ck_demo_verification_results_reason_codes_array"),
        ),
    )


def _create_p7_and_job_tables() -> None:
    op.create_table(
        "demo_preference_events",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=True),
        sa.Column("event_sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("source_type", sa.String(length=48), nullable=False),
        sa.Column("target_type", sa.String(length=48), nullable=True),
        sa.Column("target_id", sa.String(length=32), nullable=True),
        sa.Column("signal", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_event_digest", sa.String(length=64), nullable=False),
        *_common_constraints("demo_preference_events"),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_preference_events_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_preference_events_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "event_sequence",
            name=op.f("uq_demo_preference_events_actor_sequence"),
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "content_digest",
            name=op.f("uq_demo_preference_events_actor_digest"),
        ),
        sa.CheckConstraint(
            "event_sequence > 0",
            name=op.f("ck_demo_preference_events_positive_event_sequence"),
        ),
        sa.CheckConstraint(
            "event_type IN ('EXPLICIT_STYLE_SELECTION','FEATURE_LOCKED','FEATURE_UNLOCKED',"
            "'TEMPORARY_SESSION_OVERRIDE','MAXIMUM_INTENSITY_CHANGED',"
            "'PROHIBITED_OPERATION_ADDED','IMAGE_ACCEPTED','IMAGE_REJECTED','IMAGE_ADJUSTED',"
            "'LEARNING_DISABLED','LEARNING_ENABLED','RESET','ROLLBACK','TOMBSTONE','DELETE',"
            "'SESSION_CLOSED','ACTOR_TOMBSTONED','EDITING_SESSION_CLOSED')",
            name=op.f("ck_demo_preference_events_event_type"),
        ),
        sa.CheckConstraint(
            "source_type IN ('EXPLICIT_USER_ACTION','QUESTIONNAIRE','SELF_TRANSFER',"
            "'EDIT_FEEDBACK','SYSTEM_LIFECYCLE')",
            name=op.f("ck_demo_preference_events_source_type"),
        ),
        sa.CheckConstraint(
            "(target_type IS NULL AND target_id IS NULL) OR "
            "(target_type IN ('DEMO_ACTOR','BASELINE_FACE_MODEL','SELF_STATE',"
            "'DESIRED_DELTA_PROFILE','STYLE_PROFILE','REFERENCE_PROFILE','IMAGE_VERSION',"
            "'AESTHETIC_PROFILE','CONTEXT_COMPILATION') "
            "AND target_id ~ '^[0-9a-f]{32}$')",
            name=op.f("ck_demo_preference_events_target_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(signal) = 'object'",
            name=op.f("ck_demo_preference_events_signal_object"),
        ),
        sa.CheckConstraint(
            "previous_event_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_preference_events_previous_event_digest_shape"),
        ),
    )
    op.create_table(
        "demo_accepted_visual_episodes",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("editing_session_id", sa.String(length=32), nullable=False),
        sa.Column("accepted_image_version_id", sa.String(length=32), nullable=False),
        sa.Column("verification_result_id", sa.String(length=32), nullable=False),
        sa.Column("acceptance_event_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_id", sa.String(length=32), nullable=False),
        sa.Column("source_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("final_asset_id", sa.String(length=32), nullable=False),
        sa.Column("final_asset_sha256", sa.String(length=64), nullable=False),
        sa.Column("trajectory_digests", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("profile_digest", sa.String(length=64), nullable=False),
        sa.Column("context_digest", sa.String(length=64), nullable=False),
        sa.Column("instruction_digest", sa.String(length=64), nullable=False),
        *_common_constraints("demo_accepted_visual_episodes"),
        sa.ForeignKeyConstraint(
            ["editing_session_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_editing_sessions.id",
                "demo_editing_sessions.demo_actor_id",
                "demo_editing_sessions.demo_session_id",
            ],
            name=op.f("fk_demo_accepted_visual_episodes_editing_session_owner"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_image_version_id"],
            ["demo_image_versions.id"],
            name=op.f(
                "fk_demo_accepted_visual_episodes_accepted_image_version_id_demo_image_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verification_result_id"],
            ["demo_verification_results.id"],
            name=op.f(
                "fk_demo_accepted_visual_episodes_verification_result_id_demo_verification_results"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["acceptance_event_id"],
            ["demo_preference_events.id"],
            name=op.f(
                "fk_demo_accepted_visual_episodes_acceptance_event_id_demo_preference_events"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_accepted_visual_episodes_source_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["final_asset_id"],
            ["assets.id"],
            name=op.f("fk_demo_accepted_visual_episodes_final_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "source_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_accepted_visual_episodes_source_sha_shape"),
        ),
        sa.CheckConstraint(
            "final_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_accepted_visual_episodes_final_sha_shape"),
        ),
        sa.CheckConstraint(
            "source_asset_id <> final_asset_id",
            name=op.f("ck_demo_accepted_visual_episodes_distinct_source_final"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(trajectory_digests) = 'array'",
            name=op.f("ck_demo_accepted_visual_episodes_trajectory_digests_array"),
        ),
        sa.CheckConstraint(
            "profile_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_accepted_visual_episodes_profile_digest_shape"),
        ),
        sa.CheckConstraint(
            "context_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_accepted_visual_episodes_context_digest_shape"),
        ),
        sa.CheckConstraint(
            "instruction_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_accepted_visual_episodes_instruction_digest_shape"),
        ),
    )
    op.create_table(
        "demo_aesthetic_profiles",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("as_of_event_sequence", sa.BigInteger(), nullable=False),
        sa.Column("compilation_watermark", sa.String(length=64), nullable=False),
        sa.Column("reset_epoch", sa.Integer(), nullable=False),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column("evidence_digests", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("profile_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_constraints("demo_aesthetic_profiles"),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_aesthetic_profiles_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "generation",
            name=op.f("uq_demo_aesthetic_profiles_actor_generation"),
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "compilation_watermark",
            "compiler_version",
            "reset_epoch",
            name=op.f("uq_demo_aesthetic_profiles_rebuild_identity"),
        ),
        sa.CheckConstraint(
            "generation > 0",
            name=op.f("ck_demo_aesthetic_profiles_positive_generation"),
        ),
        sa.CheckConstraint(
            "as_of_event_sequence >= 0",
            name=op.f("ck_demo_aesthetic_profiles_nonnegative_event_sequence"),
        ),
        sa.CheckConstraint(
            "reset_epoch >= 0",
            name=op.f("ck_demo_aesthetic_profiles_nonnegative_reset_epoch"),
        ),
        sa.CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_aesthetic_profiles_watermark_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_digests) = 'array'",
            name=op.f("ck_demo_aesthetic_profiles_evidence_digests_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(profile_payload) = 'object'",
            name=op.f("ck_demo_aesthetic_profiles_profile_payload_object"),
        ),
    )
    op.create_table(
        "demo_context_compilations",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=False),
        sa.Column("aesthetic_profile_id", sa.String(length=32), nullable=False),
        sa.Column("demo_job_binding_id", sa.String(length=32), nullable=False),
        sa.Column("context_as_of_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("compilation_watermark", sa.String(length=64), nullable=False),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column("current_instruction_digest", sa.String(length=64), nullable=False),
        sa.Column("selected_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rejected_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("budgets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trace_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *_common_constraints("demo_context_compilations"),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_context_compilations_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["aesthetic_profile_id"],
            ["demo_aesthetic_profiles.id"],
            name=op.f("fk_demo_context_compilations_aesthetic_profile_id_demo_aesthetic_profiles"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "demo_session_id",
            "context_as_of_time",
            "compiler_version",
            name=op.f("uq_demo_context_compilations_same_input"),
        ),
        sa.CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_context_compilations_watermark_shape"),
        ),
        sa.CheckConstraint(
            "current_instruction_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_context_compilations_instruction_digest_shape"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(selected_evidence) = 'array'",
            name=op.f("ck_demo_context_compilations_selected_evidence_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(rejected_evidence) = 'array'",
            name=op.f("ck_demo_context_compilations_rejected_evidence_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(budgets) = 'object'",
            name=op.f("ck_demo_context_compilations_budgets_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(trace_payload) = 'object'",
            name=op.f("ck_demo_context_compilations_trace_payload_object"),
        ),
        sa.CheckConstraint(
            "expires_at >= context_as_of_time",
            name=op.f("ck_demo_context_compilations_expiry_order"),
        ),
    )
    op.create_table(
        "demo_job_bindings",
        *_common_columns(),
        sa.Column("demo_actor_id", sa.String(length=32), nullable=False),
        sa.Column("demo_session_id", sa.String(length=32), nullable=True),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("endpoint_operation", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=32), nullable=False),
        *_common_constraints("demo_job_bindings"),
        sa.ForeignKeyConstraint(
            ["demo_actor_id"],
            ["demo_actors.id"],
            name=op.f("fk_demo_job_bindings_demo_actor_id_demo_actors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name=op.f("fk_demo_job_bindings_session_actor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_demo_job_bindings_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "demo_actor_id",
            "endpoint_operation",
            "idempotency_key_hash",
            name=op.f("uq_demo_job_bindings_actor_operation_key"),
        ),
        sa.UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name=op.f("uq_demo_job_bindings_id_actor_session"),
        ),
        sa.CheckConstraint(
            "endpoint_operation IN ('analysis.create','questionnaire.run.create','profile.compile',"
            "'editing_session.create','edit_plan.create','edit_plan.execute',"
            "'image_version.restore','profile.rebuild','self_transfer.execute','tool.verify',"
            "'context.compile')",
            name=op.f("ck_demo_job_bindings_endpoint_operation"),
        ),
        sa.CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_job_bindings_idempotency_key_hash_shape"),
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_demo_job_bindings_request_digest_shape"),
        ),
        sa.CheckConstraint(
            "target_type IN ('DEMO_ACTOR','DEMO_SESSION','FACE_OBSERVATION',"
            "'QUESTIONNAIRE_RUN','SELF_TRANSFER_RUN','EDITING_SESSION','IMAGE_VERSION',"
            "'EDIT_PLAN','EDIT_OPERATION','TOOL_RUN')",
            name=op.f("ck_demo_job_bindings_target_type"),
        ),
        sa.CheckConstraint(
            "target_id ~ '^[0-9a-f]{32}$'",
            name=op.f("ck_demo_job_bindings_target_id_shape"),
        ),
    )


def _create_deferred_job_binding_foreign_keys() -> None:
    for table_name in (
        "demo_desired_delta_profiles",
        "demo_style_profiles",
        "demo_self_transfer_runs",
        "demo_tool_runs",
        "demo_verification_results",
        "demo_aesthetic_profiles",
        "demo_context_compilations",
    ):
        op.create_foreign_key(
            op.f(f"fk_{table_name}_demo_job_binding_id_demo_job_bindings"),
            table_name,
            "demo_job_bindings",
            ["demo_job_binding_id"],
            ["id"],
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        )


def _create_deferred_image_execution_foreign_keys() -> None:
    for local_column, remote_table in (
        ("plan_digest", "demo_edit_plans"),
        ("tool_run_digest", "demo_tool_runs"),
        ("verifier_digest", "demo_verification_results"),
    ):
        op.create_foreign_key(
            op.f(f"fk_demo_image_versions_{local_column}_{remote_table}"),
            "demo_image_versions",
            remote_table,
            [local_column],
            ["content_digest"],
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        )
    op.create_foreign_key(
        op.f("fk_demo_tool_runs_edit_operation_digest_demo_edit_operations"),
        "demo_tool_runs",
        "demo_edit_operations",
        ["edit_operation_digest"],
        ["content_digest"],
        ondelete="RESTRICT",
        deferrable=True,
        initially="DEFERRED",
    )


def _drop_deferred_image_execution_foreign_keys() -> None:
    for local_column, remote_table in (
        ("plan_digest", "demo_edit_plans"),
        ("tool_run_digest", "demo_tool_runs"),
        ("verifier_digest", "demo_verification_results"),
    ):
        op.drop_constraint(
            op.f(f"fk_demo_image_versions_{local_column}_{remote_table}"),
            "demo_image_versions",
            type_="foreignkey",
        )


_SINGLE_COLUMN_INDEXES: dict[str, tuple[str, ...]] = {
    "demo_sessions": ("demo_actor_id",),
    "demo_synthetic_identities": (
        "formal_synthetic_identity_id",
        "formal_canonical_asset_id",
        "formal_accepted_qa_run_id",
        "supersedes_id",
    ),
    "demo_face_observations": (
        "demo_actor_id",
        "demo_session_id",
        "demo_synthetic_identity_id",
        "source_asset_id",
    ),
    "demo_face_observation_repeats": (
        "demo_actor_id",
        "demo_session_id",
        "observation_id",
    ),
    "demo_baseline_face_models": (
        "demo_actor_id",
        "demo_session_id",
        "observation_id",
    ),
    "demo_self_states": ("baseline_face_model_id", "demo_actor_id", "demo_session_id"),
    "demo_question_pairs": (
        "demo_synthetic_identity_id",
        "left_asset_id",
        "left_asset_variant_id",
        "question_bank_id",
        "right_asset_id",
        "right_asset_variant_id",
        "source_asset_id",
    ),
    "demo_questionnaire_runs": (
        "demo_actor_id",
        "demo_session_id",
        "question_bank_id",
        "self_state_id",
    ),
    "demo_questionnaire_steps": (
        "demo_actor_id",
        "demo_session_id",
        "question_pair_id",
        "questionnaire_run_id",
    ),
    "demo_desired_delta_profiles": (
        "demo_actor_id",
        "demo_job_binding_id",
        "demo_session_id",
        "self_state_id",
    ),
    "demo_style_profiles": (
        "demo_actor_id",
        "demo_job_binding_id",
        "demo_session_id",
        "desired_delta_profile_id",
    ),
    "demo_identity_constraints": ("demo_actor_id", "demo_session_id", "self_state_id"),
    "demo_self_transfer_runs": (
        "demo_actor_id",
        "demo_session_id",
        "desired_delta_profile_id",
        "request_run_id",
        "result_asset_id",
        "source_asset_id",
    ),
    "demo_reference_profiles": (
        "demo_actor_id",
        "demo_session_id",
        "desired_delta_profile_id",
        "identity_constraints_id",
        "style_profile_id",
    ),
    "demo_editing_sessions": ("demo_actor_id", "demo_session_id", "source_asset_id"),
    "demo_image_versions": (
        "demo_actor_id",
        "demo_session_id",
        "editing_session_id",
        "parent_version_id",
        "source_asset_id",
    ),
    "demo_edit_plans": (
        "demo_actor_id",
        "demo_session_id",
        "editing_session_id",
        "input_image_version_id",
        "request_plan_id",
    ),
    "demo_edit_operations": ("demo_actor_id", "demo_session_id", "edit_plan_id"),
    "demo_tool_runs": (
        "demo_actor_id",
        "demo_session_id",
        "edit_operation_id",
        "demo_job_binding_id",
        "formal_job_attempt_id",
        "input_asset_id",
        "output_asset_id",
    ),
    "demo_verification_results": (
        "demo_actor_id",
        "demo_session_id",
        "output_asset_id",
    ),
    "demo_preference_events": ("demo_actor_id", "demo_session_id"),
    "demo_accepted_visual_episodes": (
        "demo_actor_id",
        "demo_session_id",
        "editing_session_id",
        "final_asset_id",
        "source_asset_id",
        "verification_result_id",
    ),
    "demo_aesthetic_profiles": ("demo_actor_id", "demo_job_binding_id"),
    "demo_context_compilations": (
        "aesthetic_profile_id",
        "demo_actor_id",
        "demo_session_id",
    ),
    "demo_job_bindings": ("demo_actor_id", "demo_session_id"),
}

_UNIQUE_SINGLE_COLUMN_INDEXES: dict[str, tuple[str, ...]] = {
    "demo_self_transfer_runs": ("demo_job_binding_id",),
    "demo_image_versions": ("result_asset_id", "result_asset_variant_id"),
    "demo_verification_results": (
        "demo_job_binding_id",
        "tool_run_id",
        "image_version_id",
    ),
    "demo_accepted_visual_episodes": ("acceptance_event_id", "accepted_image_version_id"),
    "demo_context_compilations": ("demo_job_binding_id",),
    "demo_job_bindings": ("job_id",),
}


def _create_indexes() -> None:
    for table_name, columns in _SINGLE_COLUMN_INDEXES.items():
        for column_name in columns:
            op.create_index(
                op.f(f"ix_{table_name}_{column_name}"),
                table_name,
                [column_name],
                unique=False,
            )
    for table_name, columns in _UNIQUE_SINGLE_COLUMN_INDEXES.items():
        for column_name in columns:
            op.create_index(
                op.f(f"ix_{table_name}_{column_name}"),
                table_name,
                [column_name],
                unique=True,
            )
    op.create_index(
        "ix_demo_question_pairs_routing",
        "demo_question_pairs",
        ["question_bank_id", "dimension_key", "demo_synthetic_identity_id", "magnitude_ppm"],
        unique=False,
    )
    op.create_index(
        "uq_demo_questionnaire_steps_run_step_event",
        "demo_questionnaire_steps",
        ["questionnaire_run_id", "step_number", "event_type"],
        unique=True,
        postgresql_where=sa.text("step_number IS NOT NULL"),
    )
    op.create_index(
        "ix_demo_aesthetic_profiles_rebuild",
        "demo_aesthetic_profiles",
        ["demo_actor_id", "compilation_watermark", "compiler_version", "reset_epoch"],
        unique=False,
    )
    op.create_index(
        "ix_demo_context_compilations_actor_as_of",
        "demo_context_compilations",
        ["demo_actor_id", "context_as_of_time", "compiler_version"],
        unique=False,
    )


_CANONICAL_AUTHORITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_canonical_json(input_value jsonb)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    value_kind text;
    canonical_value text;
BEGIN
    value_kind := jsonb_typeof(input_value);
    CASE value_kind
        WHEN 'object' THEN
            SELECT '{' || COALESCE(
                string_agg(
                    to_json(object_item.key)::text || ':' ||
                    mirror_demo_canonical_json(object_item.value),
                    ',' ORDER BY object_item.key COLLATE "C"
                ),
                ''
            ) || '}'
            INTO canonical_value
            FROM jsonb_each(input_value) AS object_item;
            RETURN canonical_value;
        WHEN 'array' THEN
            SELECT '[' || COALESCE(
                string_agg(
                    mirror_demo_canonical_json(array_item.value),
                    ',' ORDER BY array_item.ordinality
                ),
                ''
            ) || ']'
            INTO canonical_value
            FROM jsonb_array_elements(input_value) WITH ORDINALITY AS array_item(value, ordinality);
            RETURN canonical_value;
        WHEN 'string' THEN
            RETURN input_value::text;
        WHEN 'boolean' THEN
            RETURN input_value::text;
        WHEN 'null' THEN
            RETURN 'null';
        WHEN 'number' THEN
            canonical_value := input_value::text;
            IF canonical_value !~ '^(0|-?[1-9][0-9]*)$' THEN
                RAISE EXCEPTION 'Demo canonical authority requires integer numeric leaves';
            END IF;
            RETURN canonical_value;
        ELSE
            RAISE EXCEPTION 'Unsupported Demo canonical JSON type: %', value_kind;
    END CASE;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_digest(
    authority_schema_version text,
    authority_payload jsonb
)
RETURNS text
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
    SELECT encode(
        sha256(
            convert_to(
                authority_schema_version || E'\n' || mirror_demo_canonical_json(authority_payload),
                'UTF8'
            )
        ),
        'hex'
    );
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_authority_projection(
    row_data jsonb,
    authority_table text
)
RETURNS jsonb
LANGUAGE plpgsql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $function$
DECLARE
    projected jsonb;
    timestamp_key text;
BEGIN
    projected := row_data - ARRAY[
        'id',
        'schema_version',
        'canonical_payload',
        'content_digest',
        'created_at',
        'closed_at',
        'tombstoned_at'
    ]::text[];

    FOREACH timestamp_key IN ARRAY ARRAY[
        'authority_at',
        'expires_at',
        'occurred_at',
        'context_as_of_time'
    ]::text[] LOOP
        IF projected ? timestamp_key AND projected -> timestamp_key <> 'null'::jsonb THEN
            projected := jsonb_set(
                projected,
                ARRAY[timestamp_key],
                to_jsonb(
                    to_char(
                        (projected ->> timestamp_key)::timestamptz AT TIME ZONE 'UTC',
                        'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                    )
                ),
                false
            );
        END IF;
    END LOOP;

    IF authority_table NOT LIKE 'demo\_%' ESCAPE '\' THEN
        RAISE EXCEPTION 'Demo authority projection rejected unexpected table %', authority_table;
    END IF;
    RETURN projected;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_guard_authority()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_payload jsonb;
    expected_digest text;
    close_changed boolean := false;
    tombstone_changed boolean := false;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Demo authority row is append-only: %', TG_TABLE_NAME;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF TG_TABLE_NAME NOT IN ('demo_actors', 'demo_sessions', 'demo_editing_sessions') THEN
            RAISE EXCEPTION 'Demo authority row is immutable: %', TG_TABLE_NAME;
        END IF;

        IF TG_TABLE_NAME = 'demo_actors' THEN
            IF OLD.tombstoned_at IS NOT NULL
                OR NEW.tombstoned_at IS NULL
                OR (to_jsonb(NEW) - 'tombstoned_at') IS DISTINCT FROM
                   (to_jsonb(OLD) - 'tombstoned_at') THEN
                RAISE EXCEPTION 'Invalid Demo actor tombstone transition';
            END IF;
        ELSE
            close_changed := OLD.closed_at IS NULL AND NEW.closed_at IS NOT NULL;
            tombstone_changed := OLD.tombstoned_at IS NULL AND NEW.tombstoned_at IS NOT NULL;

            IF NOT (close_changed OR tombstone_changed)
                OR (tombstone_changed AND OLD.closed_at IS NULL)
                OR (OLD.closed_at IS NOT NULL AND NEW.closed_at IS DISTINCT FROM OLD.closed_at)
                OR (OLD.tombstoned_at IS NOT NULL AND
                    NEW.tombstoned_at IS DISTINCT FROM OLD.tombstoned_at)
                OR (to_jsonb(NEW) - ARRAY['closed_at', 'tombstoned_at']::text[]) IS DISTINCT FROM
                   (to_jsonb(OLD) - ARRAY['closed_at', 'tombstoned_at']::text[]) THEN
                RAISE EXCEPTION 'Invalid Demo terminal header transition: %', TG_TABLE_NAME;
            END IF;
        END IF;
    ELSIF TG_TABLE_NAME = 'demo_actors' THEN
        IF NEW.tombstoned_at IS NOT NULL THEN
            RAISE EXCEPTION 'Demo actor must be created active';
        END IF;
    ELSIF TG_TABLE_NAME IN ('demo_sessions', 'demo_editing_sessions') THEN
        IF NEW.closed_at IS NOT NULL OR NEW.tombstoned_at IS NOT NULL THEN
            RAISE EXCEPTION 'Demo session header must be created open';
        END IF;
    END IF;

    IF jsonb_typeof(NEW.canonical_payload) IS DISTINCT FROM 'object' THEN
        RAISE EXCEPTION 'Demo canonical payload must be a JSON object';
    END IF;

    expected_payload := mirror_demo_authority_projection(to_jsonb(NEW), TG_TABLE_NAME);
    IF NEW.canonical_payload IS DISTINCT FROM expected_payload THEN
        RAISE EXCEPTION 'Demo canonical payload disagrees with structured authority: %', TG_TABLE_NAME;
    END IF;

    expected_digest := mirror_demo_digest(NEW.schema_version, NEW.canonical_payload);
    IF NEW.content_digest IS DISTINCT FROM expected_digest THEN
        RAISE EXCEPTION 'Demo canonical digest mismatch: %', TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_require_image_execution_binding(
    authority_image_version_id text
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    image_row record;
    parent_row record;
    plan_row record;
    tool_row record;
    operation_row record;
    verification_row record;
BEGIN
    SELECT * INTO image_row
    FROM demo_image_versions
    WHERE id = authority_image_version_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution binding lacks ImageVersion';
    END IF;

    PERFORM mirror_demo_require_asset(
        image_row.source_asset_id,
        image_row.source_asset_sha256
    );
    PERFORM mirror_demo_require_asset(
        image_row.result_asset_id,
        image_row.result_asset_sha256
    );
    IF NOT EXISTS (
        SELECT 1 FROM asset_variants variant_row
        WHERE variant_row.id = image_row.result_asset_variant_id
          AND variant_row.source_asset_id = image_row.source_asset_id
          AND variant_row.result_asset_id = image_row.result_asset_id
          AND variant_row.variant_type LIKE 'demo_p3_p7\_%' ESCAPE '\'
    ) THEN
        RAISE EXCEPTION 'Demo image execution binding has invalid AssetVariant';
    END IF;

    IF image_row.sequence = 0 THEN
        IF image_row.version_kind <> 'ORIGINAL'
            OR image_row.parent_version_id IS NOT NULL
            OR image_row.plan_digest IS NOT NULL
            OR image_row.tool_run_digest IS NOT NULL
            OR image_row.verifier_digest IS NOT NULL
            OR EXISTS (
                SELECT 1 FROM demo_verification_results verification
                WHERE verification.image_version_id = image_row.id
            ) THEN
            RAISE EXCEPTION 'Original Demo ImageVersion has execution authority';
        END IF;
        RETURN;
    END IF;

    SELECT * INTO parent_row
    FROM demo_image_versions
    WHERE id = image_row.parent_version_id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND editing_session_id = image_row.editing_session_id
      AND sequence = image_row.sequence - 1
      AND result_asset_id = image_row.source_asset_id
      AND result_asset_sha256 = image_row.source_asset_sha256;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution parent binding mismatch';
    END IF;

    SELECT * INTO plan_row
    FROM demo_edit_plans
    WHERE content_digest = image_row.plan_digest
      AND record_kind = 'RESULT'
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND editing_session_id = image_row.editing_session_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution plan digest mismatch';
    END IF;

    SELECT * INTO tool_row
    FROM demo_tool_runs
    WHERE content_digest = image_row.tool_run_digest
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND outcome = 'COMPLETED'
      AND input_asset_id = parent_row.result_asset_id
      AND input_asset_sha256 = parent_row.result_asset_sha256
      AND output_asset_id = image_row.result_asset_id
      AND output_asset_sha256 = image_row.result_asset_sha256;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution ToolRun digest mismatch';
    END IF;

    SELECT * INTO operation_row
    FROM demo_edit_operations
    WHERE id = tool_row.edit_operation_id
      AND content_digest = tool_row.edit_operation_digest
      AND edit_plan_id = plan_row.id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id;
    IF NOT FOUND
        OR operation_row.operation_index < 0
        OR operation_row.operation_index >= jsonb_array_length(plan_row.operation_specs)
        OR plan_row.operation_specs -> operation_row.operation_index IS DISTINCT FROM
           jsonb_build_object(
               'engine', operation_row.engine,
               'operation_type', operation_row.operation_type,
               'parameters', operation_row.parameters,
               'preserve', operation_row.preserve,
               'expected_effect', operation_row.expected_effect
           ) THEN
        RAISE EXCEPTION 'Demo image execution operation digest or specification mismatch';
    END IF;

    IF operation_row.operation_index = 0 THEN
        IF plan_row.input_image_version_id IS DISTINCT FROM parent_row.id THEN
            RAISE EXCEPTION 'First Demo plan operation does not consume plan input';
        END IF;
    ELSIF parent_row.plan_digest IS DISTINCT FROM plan_row.content_digest OR NOT EXISTS (
        SELECT 1
        FROM demo_tool_runs previous_tool
        JOIN demo_edit_operations previous_operation
          ON previous_operation.id = previous_tool.edit_operation_id
        WHERE previous_tool.content_digest = parent_row.tool_run_digest
          AND previous_operation.edit_plan_id = plan_row.id
          AND previous_operation.operation_index = operation_row.operation_index - 1
          AND previous_tool.demo_job_binding_id = tool_row.demo_job_binding_id
          AND previous_tool.formal_job_attempt_id = tool_row.formal_job_attempt_id
    ) THEN
        RAISE EXCEPTION 'Demo multi-operation plan execution is not contiguous';
    END IF;

    SELECT * INTO verification_row
    FROM demo_verification_results
    WHERE content_digest = image_row.verifier_digest
      AND image_version_id = image_row.id
      AND tool_run_id = tool_row.id
      AND demo_actor_id = image_row.demo_actor_id
      AND demo_session_id = image_row.demo_session_id
      AND output_asset_id = image_row.result_asset_id
      AND output_asset_sha256 = image_row.result_asset_sha256;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo image execution verifier digest mismatch';
    END IF;

    IF (image_row.version_kind IN ('EDITED','RESTORED','ROLLED_BACK')
            AND verification_row.outcome <> 'PASS')
        OR (image_row.version_kind = 'QUARANTINED'
            AND verification_row.outcome NOT IN ('FAIL','HUMAN_REVIEW'))
        OR image_row.version_kind NOT IN (
            'EDITED','RESTORED','ROLLED_BACK','QUARANTINED'
        ) THEN
        RAISE EXCEPTION 'Demo ImageVersion kind and verifier outcome disagree';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_image_execution_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_TABLE_NAME = 'demo_image_versions' THEN
        PERFORM mirror_demo_require_image_execution_binding(NEW.id);
    ELSE
        PERFORM mirror_demo_require_image_execution_binding(NEW.image_version_id);
    END IF;
    RETURN NEW;
END;
$function$;
"""


_REFERENCE_AUTHORITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_require_asset(
    authority_asset_id text,
    expected_sha256 text DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
STABLE
AS $function$
DECLARE
    asset_row assets%ROWTYPE;
BEGIN
    IF authority_asset_id IS NULL THEN
        RAISE EXCEPTION 'Demo asset reference may not be null';
    END IF;
    SELECT * INTO asset_row FROM assets WHERE id = authority_asset_id;
    IF NOT FOUND
        OR asset_row.owner_user_id IS NOT NULL
        OR NOT asset_row.synthetic
        OR asset_row.deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'Demo asset reference is unavailable or outside synthetic scope';
    END IF;
    IF expected_sha256 IS NOT NULL AND asset_row.sha256 IS DISTINCT FROM expected_sha256 THEN
        RAISE EXCEPTION 'Demo asset checksum mismatch';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_formal_qa_snapshot_digest(
    authority_qa_run_id text
)
RETURNS text
LANGUAGE plpgsql
STABLE
STRICT
AS $function$
DECLARE
    snapshot_payload jsonb;
BEGIN
    SELECT jsonb_build_object(
        'qa_run', jsonb_build_object(
            'id', qa_row.id,
            'schema_version', qa_row.schema_version,
            'subject_kind', qa_row.subject_kind,
            'synthetic_asset_record_id', qa_row.synthetic_asset_record_id,
            'transform_run_id', qa_row.transform_run_id,
            'normalized_asset_id', qa_row.normalized_asset_id,
            'qa_policy_id', qa_row.qa_policy_id,
            'vision_provider_reference', qa_row.vision_provider_reference,
            'vision_algorithm_reference', qa_row.vision_algorithm_reference,
            'status', qa_row.status,
            'result_code', qa_row.result_code,
            'started_at', to_char(
                qa_row.started_at AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
            ),
            'finalized_at', to_char(
                qa_row.finalized_at AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
            )
        ),
        'qa_policy', jsonb_build_object(
            'id', policy_row.id,
            'schema_version', policy_row.schema_version,
            'version', policy_row.version,
            'content_digest', policy_row.content_digest,
            'approval_status', policy_row.approval_status,
            'approved_at', to_char(
                policy_row.approved_at AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
            )
        ),
        'measurements', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'schema_version', measurement_row.schema_version,
                    'measurement_kind', measurement_row.measurement_kind,
                    'measurement_code', measurement_row.measurement_code,
                    'payload_digest', measurement_row.payload_digest,
                    'algorithm_reference', measurement_row.algorithm_reference,
                    'algorithm_version', measurement_row.algorithm_version,
                    'confidence_scaled_1e7', CASE
                        WHEN measurement_row.confidence IS NULL THEN NULL
                        ELSE (measurement_row.confidence * 10000000)::bigint
                    END,
                    'hard_gate', measurement_row.hard_gate,
                    'threshold_outcome', measurement_row.threshold_outcome,
                    'reason_code', measurement_row.reason_code
                )
                ORDER BY measurement_row.measurement_code COLLATE "C"
            )
            FROM synthetic_qa_measurements measurement_row
            WHERE measurement_row.qa_run_id = qa_row.id
        ),
        'reviews', (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'schema_version', review_row.schema_version,
                    'review_kind', review_row.review_kind,
                    'decision', review_row.decision,
                    'reason_code', review_row.reason_code,
                    'actor_reference', review_row.actor_reference,
                    'reviewed_at', to_char(
                        review_row.reviewed_at AT TIME ZONE 'UTC',
                        'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                    )
                )
                ORDER BY review_row.review_kind COLLATE "C"
            )
            FROM synthetic_qa_review_decisions review_row
            WHERE review_row.qa_run_id = qa_row.id
        )
    )
    INTO snapshot_payload
    FROM synthetic_qa_runs qa_row
    JOIN synthetic_qa_policies policy_row ON policy_row.id = qa_row.qa_policy_id
    WHERE qa_row.id = authority_qa_run_id
      AND qa_row.subject_kind = 'CANONICAL_BASE'
      AND qa_row.status = 'PASSED'
      AND qa_row.started_at IS NOT NULL
      AND qa_row.finalized_at IS NOT NULL
      AND policy_row.approval_status = 'APPROVED'
      AND policy_row.approved_at IS NOT NULL
      AND EXISTS (
          SELECT 1 FROM synthetic_qa_measurements measurement_row
          WHERE measurement_row.qa_run_id = qa_row.id
      )
      AND NOT EXISTS (
          SELECT 1 FROM synthetic_qa_measurements measurement_row
          WHERE measurement_row.qa_run_id = qa_row.id
            AND measurement_row.hard_gate
            AND measurement_row.threshold_outcome <> 'PASSED'
      )
      AND (
          SELECT count(*)
          FROM synthetic_qa_review_decisions review_row
          WHERE review_row.qa_run_id = qa_row.id
            AND review_row.review_kind IN (
                'adult_presentation', 'likeness_risk', 'license_rights'
            )
            AND review_row.decision = 'PASSED'
      ) = 3;

    IF snapshot_payload IS NULL THEN
        RAISE EXCEPTION 'Formal synthetic QA snapshot is not eligible for Demo admission';
    END IF;
    RETURN encode(
        sha256(
            convert_to(
                'mirror.demo/FormalSyntheticQASnapshot/v1' || E'\n' ||
                mirror_demo_canonical_json(snapshot_payload),
                'UTF8'
            )
        ),
        'hex'
    );
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_require_current_synthetic_admission(
    authority_admission_id text
)
RETURNS void
LANGUAGE plpgsql
AS $function$
DECLARE
    admission_row record;
    latest_admission_id text;
BEGIN
    SELECT * INTO admission_row
    FROM demo_synthetic_identities
    WHERE id = authority_admission_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Demo synthetic admission authority does not exist';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'mirror.demo.synthetic-admission/' || admission_row.formal_synthetic_identity_id,
            0
        )
    );
    SELECT id INTO latest_admission_id
    FROM demo_synthetic_identities
    WHERE formal_synthetic_identity_id = admission_row.formal_synthetic_identity_id
    ORDER BY admission_sequence DESC
    LIMIT 1;

    IF latest_admission_id IS DISTINCT FROM admission_row.id
        OR admission_row.admission_action <> 'ADMIT' THEN
        RAISE EXCEPTION 'Demo synthetic admission is not the current eligible row';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM synthetic_identities identity_row
        JOIN synthetic_qa_runs qa_row
          ON qa_row.id = identity_row.accepted_qa_run_id
        JOIN assets asset_row
          ON asset_row.id = identity_row.canonical_asset_id
        WHERE identity_row.id = admission_row.formal_synthetic_identity_id
          AND identity_row.bank_version_id IS NULL
          AND identity_row.authority_kind = 'CANONICAL_QA'
          AND identity_row.adult_synthetic_attested
          AND identity_row.canonical_asset_id = admission_row.formal_canonical_asset_id
          AND identity_row.accepted_qa_run_id = admission_row.formal_accepted_qa_run_id
          AND qa_row.subject_kind = 'CANONICAL_BASE'
          AND qa_row.status = 'PASSED'
          AND qa_row.normalized_asset_id = admission_row.formal_canonical_asset_id
          AND asset_row.owner_user_id IS NULL
          AND asset_row.asset_role = 'synthetic'
          AND asset_row.internal_purpose = 'synthetic_dataset'
          AND asset_row.synthetic
          AND asset_row.deleted_at IS NULL
          AND asset_row.sha256 = admission_row.formal_canonical_asset_sha256
          AND mirror_demo_formal_qa_snapshot_digest(qa_row.id) =
              admission_row.formal_accepted_qa_snapshot_digest
    ) THEN
        RAISE EXCEPTION 'Demo synthetic admission live authority no longer matches snapshot';
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_evidence_owned_by(
    authority_actor_id text,
    authority_digest text
)
RETURNS boolean
LANGUAGE plpgsql
STABLE
STRICT
AS $function$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM demo_face_observations evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_face_observation_repeats evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_baseline_face_models evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_self_states evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_questionnaire_runs evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_questionnaire_steps evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_desired_delta_profiles evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_style_profiles evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_identity_constraints evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_self_transfer_runs evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_reference_profiles evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_editing_sessions evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_image_versions evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_edit_plans evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_edit_operations evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_tool_runs evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_verification_results evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_preference_events evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_accepted_visual_episodes evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_aesthetic_profiles evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    ) OR EXISTS (
        SELECT 1 FROM demo_context_compilations evidence_row
        WHERE evidence_row.demo_actor_id = authority_actor_id
          AND evidence_row.content_digest = authority_digest
    );
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_references()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    source_item jsonb;
    source_view_count integer;
    binding_job_id text;
    previous_admission record;
    has_previous_admission boolean;
    expected_qa_snapshot_digest text;
BEGIN
    CASE TG_TABLE_NAME
        WHEN 'demo_synthetic_identities' THEN
            PERFORM pg_advisory_xact_lock(
                hashtextextended(
                    'mirror.demo.synthetic-admission/' || NEW.formal_synthetic_identity_id,
                    0
                )
            );
            SELECT * INTO previous_admission
            FROM demo_synthetic_identities
            WHERE formal_synthetic_identity_id = NEW.formal_synthetic_identity_id
            ORDER BY admission_sequence DESC
            LIMIT 1
            FOR UPDATE;
            has_previous_admission := FOUND;

            IF NOT has_previous_admission THEN
                IF NEW.admission_sequence <> 1
                    OR NEW.admission_action <> 'ADMIT'
                    OR NEW.supersedes_id IS NOT NULL THEN
                    RAISE EXCEPTION 'First Demo synthetic identity event must be ADMIT';
                END IF;
            ELSIF NEW.admission_sequence <> previous_admission.admission_sequence + 1
                OR NEW.supersedes_id IS DISTINCT FROM previous_admission.id
                OR NEW.admission_action = previous_admission.admission_action THEN
                RAISE EXCEPTION 'Demo synthetic identity admission chain is not latest';
            END IF;

            IF NEW.admission_action = 'REVOKE' THEN
                IF NOT has_previous_admission
                    OR NEW.formal_canonical_asset_id IS DISTINCT FROM
                       previous_admission.formal_canonical_asset_id
                    OR NEW.formal_canonical_asset_sha256 IS DISTINCT FROM
                       previous_admission.formal_canonical_asset_sha256
                    OR NEW.formal_accepted_qa_run_id IS DISTINCT FROM
                       previous_admission.formal_accepted_qa_run_id
                    OR NEW.formal_accepted_qa_snapshot_digest IS DISTINCT FROM
                       previous_admission.formal_accepted_qa_snapshot_digest THEN
                    RAISE EXCEPTION 'Demo synthetic revocation must copy the frozen snapshot';
                END IF;
            ELSE
                expected_qa_snapshot_digest := mirror_demo_formal_qa_snapshot_digest(
                    NEW.formal_accepted_qa_run_id
                );
                IF expected_qa_snapshot_digest IS DISTINCT FROM
                   NEW.formal_accepted_qa_snapshot_digest OR NOT EXISTS (
                    SELECT 1
                    FROM synthetic_identities identity_row
                    JOIN synthetic_qa_runs qa_row
                      ON qa_row.id = identity_row.accepted_qa_run_id
                    JOIN assets asset_row
                      ON asset_row.id = identity_row.canonical_asset_id
                    WHERE identity_row.id = NEW.formal_synthetic_identity_id
                      AND identity_row.bank_version_id IS NULL
                      AND identity_row.authority_kind = 'CANONICAL_QA'
                      AND identity_row.adult_synthetic_attested
                      AND identity_row.canonical_asset_id = NEW.formal_canonical_asset_id
                      AND identity_row.accepted_qa_run_id = NEW.formal_accepted_qa_run_id
                      AND qa_row.subject_kind = 'CANONICAL_BASE'
                      AND qa_row.status = 'PASSED'
                      AND qa_row.normalized_asset_id = NEW.formal_canonical_asset_id
                      AND asset_row.owner_user_id IS NULL
                      AND asset_row.asset_role = 'synthetic'
                      AND asset_row.internal_purpose = 'synthetic_dataset'
                      AND asset_row.synthetic
                      AND asset_row.deleted_at IS NULL
                      AND asset_row.sha256 = NEW.formal_canonical_asset_sha256
                ) THEN
                    RAISE EXCEPTION 'Demo synthetic identity snapshot does not match formal authority';
                END IF;
            END IF;

        WHEN 'demo_face_observations' THEN
            PERFORM mirror_demo_require_asset(NEW.source_asset_id, NEW.source_asset_sha256);
            PERFORM mirror_demo_require_current_synthetic_admission(
                NEW.demo_synthetic_identity_id
            );
            IF NOT EXISTS (
                SELECT 1 FROM demo_synthetic_identities demo_identity
                WHERE demo_identity.id = NEW.demo_synthetic_identity_id
                  AND demo_identity.formal_canonical_asset_id = NEW.source_asset_id
                  AND demo_identity.formal_canonical_asset_sha256 = NEW.source_asset_sha256
            ) THEN
                RAISE EXCEPTION 'Demo face observation source does not match synthetic identity';
            END IF;

        WHEN 'demo_baseline_face_models' THEN
            IF NOT EXISTS (
                SELECT 1
                FROM demo_face_observations observation_row
                WHERE observation_row.id = NEW.observation_id
                  AND observation_row.demo_actor_id = NEW.demo_actor_id
                  AND observation_row.demo_session_id = NEW.demo_session_id
                  AND NEW.ordered_repeat_digests = (
                      SELECT jsonb_agg(repeat_row.content_digest ORDER BY repeat_row.repeat_index)
                      FROM demo_face_observation_repeats repeat_row
                      WHERE repeat_row.observation_id = observation_row.id
                  )
            ) THEN
                RAISE EXCEPTION 'Demo baseline repeat lineage mismatch';
            END IF;

        WHEN 'demo_question_pairs' THEN
            PERFORM mirror_demo_require_asset(NEW.source_asset_id, NEW.source_asset_sha256);
            PERFORM mirror_demo_require_asset(NEW.left_asset_id, NEW.left_asset_sha256);
            PERFORM mirror_demo_require_asset(NEW.right_asset_id, NEW.right_asset_sha256);
            PERFORM mirror_demo_require_current_synthetic_admission(
                NEW.demo_synthetic_identity_id
            );
            IF NOT EXISTS (
                SELECT 1 FROM demo_synthetic_identities demo_identity
                WHERE demo_identity.id = NEW.demo_synthetic_identity_id
                  AND demo_identity.formal_canonical_asset_id = NEW.source_asset_id
                  AND demo_identity.formal_canonical_asset_sha256 = NEW.source_asset_sha256
            ) THEN
                RAISE EXCEPTION 'Demo question pair source identity lineage mismatch';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM asset_variants variant_row
                WHERE variant_row.id = NEW.left_asset_variant_id
                  AND variant_row.source_asset_id = NEW.source_asset_id
                  AND variant_row.result_asset_id = NEW.left_asset_id
                  AND variant_row.variant_type LIKE 'demo_p3_p7\_%' ESCAPE '\'
            ) OR NOT EXISTS (
                SELECT 1 FROM asset_variants variant_row
                WHERE variant_row.id = NEW.right_asset_variant_id
                  AND variant_row.source_asset_id = NEW.source_asset_id
                  AND variant_row.result_asset_id = NEW.right_asset_id
                  AND variant_row.variant_type LIKE 'demo_p3_p7\_%' ESCAPE '\'
            ) THEN
                RAISE EXCEPTION 'Demo question pair AssetVariant lineage mismatch';
            END IF;

        WHEN 'demo_questionnaire_steps' THEN
            IF NEW.question_pair_id IS NOT NULL AND NOT EXISTS (
                SELECT 1
                FROM demo_questionnaire_runs run_row
                JOIN demo_question_pairs pair_row
                  ON pair_row.id = NEW.question_pair_id
                 AND pair_row.question_bank_id = run_row.question_bank_id
                WHERE run_row.id = NEW.questionnaire_run_id
                  AND run_row.demo_actor_id = NEW.demo_actor_id
                  AND run_row.demo_session_id = NEW.demo_session_id
            ) THEN
                RAISE EXCEPTION 'Demo questionnaire step pair is outside its frozen bank';
            END IF;

        WHEN 'demo_desired_delta_profiles' THEN
            IF EXISTS (
                SELECT 1
                FROM jsonb_array_elements(NEW.evidence_digests) AS digest_entry(value)
                WHERE jsonb_typeof(digest_entry.value) <> 'string'
                   OR digest_entry.value #>> '{}' !~ '^[0-9a-f]{64}$'
                   OR NOT mirror_demo_evidence_owned_by(
                       NEW.demo_actor_id,
                       digest_entry.value #>> '{}'
                   )
            ) THEN
                RAISE EXCEPTION 'Demo DesiredDelta evidence ownership mismatch';
            END IF;
            IF NEW.demo_job_binding_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM demo_job_bindings binding_row
                WHERE binding_row.id = NEW.demo_job_binding_id
                  AND binding_row.demo_actor_id = NEW.demo_actor_id
                  AND binding_row.demo_session_id = NEW.demo_session_id
                  AND binding_row.endpoint_operation IN ('profile.compile', 'profile.rebuild')
                  AND binding_row.target_type = 'DEMO_ACTOR'
                  AND binding_row.target_id = NEW.demo_actor_id
            ) THEN
                RAISE EXCEPTION 'Demo DesiredDelta compiler Job binding ownership mismatch';
            END IF;

        WHEN 'demo_style_profiles' THEN
            IF NEW.desired_delta_profile_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM demo_desired_delta_profiles profile_row
                WHERE profile_row.id = NEW.desired_delta_profile_id
                  AND profile_row.demo_actor_id = NEW.demo_actor_id
                  AND (NEW.demo_session_id IS NULL
                       OR profile_row.demo_session_id = NEW.demo_session_id)
            ) THEN
                RAISE EXCEPTION 'Demo StyleProfile DesiredDelta ownership mismatch';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM jsonb_array_elements(NEW.evidence_digests) AS digest_entry(value)
                WHERE jsonb_typeof(digest_entry.value) <> 'string'
                   OR digest_entry.value #>> '{}' !~ '^[0-9a-f]{64}$'
                   OR NOT mirror_demo_evidence_owned_by(
                       NEW.demo_actor_id,
                       digest_entry.value #>> '{}'
                   )
            ) THEN
                RAISE EXCEPTION 'Demo StyleProfile evidence ownership mismatch';
            END IF;
            IF NEW.demo_job_binding_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM demo_job_bindings binding_row
                WHERE binding_row.id = NEW.demo_job_binding_id
                  AND binding_row.demo_actor_id = NEW.demo_actor_id
                  AND binding_row.demo_session_id IS NOT DISTINCT FROM NEW.demo_session_id
                  AND binding_row.endpoint_operation IN ('profile.compile', 'profile.rebuild')
                  AND binding_row.target_type = 'DEMO_ACTOR'
                  AND binding_row.target_id = NEW.demo_actor_id
            ) THEN
                RAISE EXCEPTION 'Demo StyleProfile compiler Job binding ownership mismatch';
            END IF;

        WHEN 'demo_identity_constraints' THEN
            IF NEW.self_state_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM demo_self_states state_row
                WHERE state_row.id = NEW.self_state_id
                  AND state_row.demo_actor_id = NEW.demo_actor_id
                  AND (NEW.demo_session_id IS NULL
                       OR state_row.demo_session_id = NEW.demo_session_id)
            ) THEN
                RAISE EXCEPTION 'Demo IdentityConstraints SelfState ownership mismatch';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM jsonb_array_elements(NEW.source_event_digests) AS digest_entry(value)
                WHERE jsonb_typeof(digest_entry.value) <> 'string'
                   OR NOT EXISTS (
                       SELECT 1 FROM demo_preference_events event_row
                       WHERE event_row.demo_actor_id = NEW.demo_actor_id
                         AND event_row.content_digest = digest_entry.value #>> '{}'
                   )
            ) THEN
                RAISE EXCEPTION 'Demo IdentityConstraints source event ownership mismatch';
            END IF;

        WHEN 'demo_self_transfer_runs' THEN
            PERFORM mirror_demo_require_asset(NEW.source_asset_id, NULL);
            IF NOT EXISTS (
                SELECT 1 FROM demo_desired_delta_profiles profile_row
                WHERE profile_row.id = NEW.desired_delta_profile_id
                  AND profile_row.demo_actor_id = NEW.demo_actor_id
                  AND profile_row.demo_session_id = NEW.demo_session_id
            ) THEN
                RAISE EXCEPTION 'Demo self-transfer DesiredDelta ownership mismatch';
            END IF;
            IF NEW.result_asset_id IS NOT NULL THEN
                PERFORM mirror_demo_require_asset(NEW.result_asset_id, NULL);
            END IF;
            IF NEW.record_kind = 'RESULT' AND NOT EXISTS (
                SELECT 1
                FROM demo_self_transfer_runs request_row
                JOIN demo_job_bindings binding_row
                  ON binding_row.id = NEW.demo_job_binding_id
                WHERE request_row.id = NEW.request_run_id
                  AND request_row.record_kind = 'REQUEST'
                  AND request_row.demo_actor_id = NEW.demo_actor_id
                  AND request_row.demo_session_id = NEW.demo_session_id
                  AND request_row.desired_delta_profile_id = NEW.desired_delta_profile_id
                  AND request_row.source_asset_id = NEW.source_asset_id
                  AND request_row.requested_delta = NEW.requested_delta
                  AND binding_row.demo_actor_id = NEW.demo_actor_id
                  AND binding_row.demo_session_id = NEW.demo_session_id
                  AND binding_row.endpoint_operation = 'self_transfer.execute'
                  AND binding_row.target_type = 'SELF_TRANSFER_RUN'
                  AND binding_row.target_id = request_row.id
            ) THEN
                RAISE EXCEPTION 'Demo self-transfer result lineage mismatch';
            END IF;

        WHEN 'demo_reference_profiles' THEN
            IF NOT EXISTS (
                SELECT 1 FROM demo_desired_delta_profiles profile_row
                WHERE profile_row.id = NEW.desired_delta_profile_id
                  AND profile_row.demo_actor_id = NEW.demo_actor_id
                  AND (NEW.demo_session_id IS NULL
                       OR profile_row.demo_session_id = NEW.demo_session_id)
            ) OR (NEW.style_profile_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM demo_style_profiles style_row
                WHERE style_row.id = NEW.style_profile_id
                  AND style_row.demo_actor_id = NEW.demo_actor_id
                  AND (style_row.demo_session_id IS NULL
                       OR style_row.demo_session_id = NEW.demo_session_id)
            )) OR (NEW.identity_constraints_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM demo_identity_constraints constraints_row
                WHERE constraints_row.id = NEW.identity_constraints_id
                  AND constraints_row.demo_actor_id = NEW.demo_actor_id
                  AND (constraints_row.demo_session_id IS NULL
                       OR constraints_row.demo_session_id = NEW.demo_session_id)
            )) THEN
                RAISE EXCEPTION 'Demo ReferenceProfile input ownership mismatch';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM jsonb_array_elements(NEW.evidence_digests) AS digest_entry(value)
                WHERE jsonb_typeof(digest_entry.value) <> 'string'
                   OR digest_entry.value #>> '{}' !~ '^[0-9a-f]{64}$'
                   OR NOT mirror_demo_evidence_owned_by(
                       NEW.demo_actor_id,
                       digest_entry.value #>> '{}'
                   )
            ) THEN
                RAISE EXCEPTION 'Demo ReferenceProfile evidence ownership mismatch';
            END IF;
            IF jsonb_array_length(NEW.source_assets) NOT BETWEEN 1 AND 3 THEN
                RAISE EXCEPTION 'Demo reference profile requires one to three source assets';
            END IF;
            SELECT count(DISTINCT source_entry.value ->> 'view')
            INTO source_view_count
            FROM jsonb_array_elements(NEW.source_assets) AS source_entry(value);
            IF source_view_count <> jsonb_array_length(NEW.source_assets) THEN
                RAISE EXCEPTION 'Demo reference profile source views must be unique';
            END IF;
            FOR source_item IN
                SELECT source_entry.value
                FROM jsonb_array_elements(NEW.source_assets) AS source_entry(value)
            LOOP
                IF jsonb_typeof(source_item) <> 'object'
                    OR NOT source_item ?& ARRAY['asset_id', 'sha256', 'view']
                    OR source_item ->> 'asset_id' !~ '^[0-9a-f]{32}$'
                    OR source_item ->> 'sha256' !~ '^[0-9a-f]{64}$'
                    OR source_item ->> 'view' NOT IN ('FRONT', 'THREE_QUARTER', 'SIDE') THEN
                    RAISE EXCEPTION 'Demo reference profile source entry is invalid';
                END IF;
                PERFORM mirror_demo_require_asset(
                    source_item ->> 'asset_id',
                    source_item ->> 'sha256'
                );
            END LOOP;

        WHEN 'demo_editing_sessions' THEN
            PERFORM mirror_demo_require_asset(NEW.source_asset_id, NEW.source_asset_sha256);

        WHEN 'demo_image_versions' THEN
            PERFORM mirror_demo_require_asset(
                NEW.source_asset_id,
                NEW.source_asset_sha256
            );
            PERFORM mirror_demo_require_asset(
                NEW.result_asset_id,
                NEW.result_asset_sha256
            );
            IF NEW.sequence = 0 THEN
                IF NOT EXISTS (
                    SELECT 1 FROM demo_editing_sessions editing_row
                    WHERE editing_row.id = NEW.editing_session_id
                      AND editing_row.demo_actor_id = NEW.demo_actor_id
                      AND editing_row.demo_session_id = NEW.demo_session_id
                      AND editing_row.source_asset_id = NEW.source_asset_id
                      AND editing_row.source_asset_sha256 = NEW.source_asset_sha256
                ) THEN
                    RAISE EXCEPTION 'Initial Demo image version source mismatch';
                END IF;
            ELSIF NOT EXISTS (
                SELECT 1 FROM demo_image_versions parent_row
                WHERE parent_row.id = NEW.parent_version_id
                  AND parent_row.editing_session_id = NEW.editing_session_id
                  AND parent_row.demo_actor_id = NEW.demo_actor_id
                  AND parent_row.demo_session_id = NEW.demo_session_id
                  AND parent_row.sequence = NEW.sequence - 1
                  AND parent_row.result_asset_id = NEW.source_asset_id
                  AND parent_row.result_asset_sha256 = NEW.source_asset_sha256
            ) THEN
                RAISE EXCEPTION 'Demo image version parent lineage mismatch';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM asset_variants variant_row
                WHERE variant_row.id = NEW.result_asset_variant_id
                  AND variant_row.source_asset_id = NEW.source_asset_id
                  AND variant_row.result_asset_id = NEW.result_asset_id
                  AND variant_row.variant_type LIKE 'demo_p3_p7\_%' ESCAPE '\'
            ) THEN
                RAISE EXCEPTION 'Demo image version AssetVariant lineage mismatch';
            END IF;

        WHEN 'demo_edit_plans' THEN
            IF NOT EXISTS (
                SELECT 1
                FROM demo_image_versions input_row
                WHERE input_row.id = NEW.input_image_version_id
                  AND input_row.demo_actor_id = NEW.demo_actor_id
                  AND input_row.demo_session_id = NEW.demo_session_id
                  AND input_row.editing_session_id = NEW.editing_session_id
                  AND input_row.version_kind <> 'QUARANTINED'
                  AND (
                      input_row.sequence = 0 OR EXISTS (
                          SELECT 1
                          FROM demo_edit_plans prior_plan
                          JOIN demo_tool_runs prior_tool
                            ON prior_tool.content_digest = input_row.tool_run_digest
                          JOIN demo_edit_operations prior_operation
                            ON prior_operation.id = prior_tool.edit_operation_id
                           AND prior_operation.edit_plan_id = prior_plan.id
                          JOIN demo_verification_results prior_verification
                            ON prior_verification.content_digest = input_row.verifier_digest
                           AND prior_verification.image_version_id = input_row.id
                          WHERE prior_plan.content_digest = input_row.plan_digest
                            AND prior_operation.operation_index =
                                jsonb_array_length(prior_plan.operation_specs) - 1
                            AND prior_verification.outcome = 'PASS'
                      )
                  )
            ) THEN
                RAISE EXCEPTION 'Demo EditPlan input must be an original or final verified plan output';
            END IF;
            IF NEW.record_kind = 'RESULT' AND NOT EXISTS (
                SELECT 1 FROM demo_edit_plans request_row
                WHERE request_row.id = NEW.request_plan_id
                  AND request_row.record_kind = 'REQUEST'
                  AND request_row.demo_actor_id = NEW.demo_actor_id
                  AND request_row.demo_session_id = NEW.demo_session_id
                  AND request_row.editing_session_id = NEW.editing_session_id
                  AND request_row.input_image_version_id = NEW.input_image_version_id
                  AND request_row.plan_version = NEW.plan_version
                  AND request_row.desired_delta_profile_digest = NEW.desired_delta_profile_digest
                  AND request_row.style_profile_digest = NEW.style_profile_digest
                  AND request_row.identity_constraints_digest = NEW.identity_constraints_digest
                  AND request_row.instruction_digest = NEW.instruction_digest
                  AND request_row.planner_version = NEW.planner_version
                  AND request_row.tool_registry_version = NEW.tool_registry_version
            ) THEN
                RAISE EXCEPTION 'Demo EditPlan result request lineage mismatch';
            END IF;

        WHEN 'demo_tool_runs' THEN
            PERFORM mirror_demo_require_asset(NEW.input_asset_id, NEW.input_asset_sha256);
            IF NEW.output_asset_id IS NOT NULL THEN
                PERFORM mirror_demo_require_asset(NEW.output_asset_id, NEW.output_asset_sha256);
            END IF;
            SELECT binding_row.job_id INTO binding_job_id
            FROM demo_job_bindings binding_row
            JOIN demo_edit_operations operation_row
              ON operation_row.id = NEW.edit_operation_id
            JOIN demo_edit_plans plan_row
              ON plan_row.id = operation_row.edit_plan_id
            JOIN demo_image_versions input_version
              ON input_version.id = plan_row.input_image_version_id
            WHERE binding_row.id = NEW.demo_job_binding_id
              AND binding_row.demo_actor_id = NEW.demo_actor_id
              AND binding_row.demo_session_id = NEW.demo_session_id
              AND binding_row.endpoint_operation = 'edit_plan.execute'
              AND binding_row.target_type = 'EDIT_PLAN'
              AND binding_row.target_id = plan_row.id
              AND plan_row.record_kind = 'RESULT'
              AND operation_row.content_digest = NEW.edit_operation_digest
              AND operation_row.operation_index >= 0
              AND operation_row.operation_index < jsonb_array_length(plan_row.operation_specs)
              AND plan_row.operation_specs -> operation_row.operation_index = jsonb_build_object(
                  'engine', operation_row.engine,
                  'operation_type', operation_row.operation_type,
                  'parameters', operation_row.parameters,
                  'preserve', operation_row.preserve,
                  'expected_effect', operation_row.expected_effect
              )
              AND (
                  (
                      operation_row.operation_index = 0
                      AND input_version.result_asset_id = NEW.input_asset_id
                      AND input_version.result_asset_sha256 = NEW.input_asset_sha256
                  ) OR (
                      operation_row.operation_index > 0
                      AND EXISTS (
                          SELECT 1
                          FROM demo_image_versions previous_image
                          JOIN demo_tool_runs previous_tool
                            ON previous_tool.content_digest = previous_image.tool_run_digest
                          JOIN demo_edit_operations previous_operation
                            ON previous_operation.id = previous_tool.edit_operation_id
                          WHERE previous_image.plan_digest = plan_row.content_digest
                            AND previous_operation.edit_plan_id = plan_row.id
                            AND previous_operation.operation_index =
                                operation_row.operation_index - 1
                            AND previous_image.result_asset_id = NEW.input_asset_id
                            AND previous_image.result_asset_sha256 = NEW.input_asset_sha256
                            AND previous_tool.demo_job_binding_id = NEW.demo_job_binding_id
                            AND previous_tool.formal_job_attempt_id = NEW.formal_job_attempt_id
                      )
                  )
              );
            IF binding_job_id IS NULL OR NOT EXISTS (
                SELECT 1 FROM job_attempts attempt_row
                WHERE attempt_row.id = NEW.formal_job_attempt_id
                  AND attempt_row.job_id = binding_job_id
            ) THEN
                RAISE EXCEPTION 'Demo ToolRun JobAttempt ownership mismatch';
            END IF;

        WHEN 'demo_verification_results' THEN
            PERFORM mirror_demo_require_asset(NEW.output_asset_id, NEW.output_asset_sha256);
            IF NOT EXISTS (
                SELECT 1
                FROM demo_tool_runs tool_row
                JOIN demo_job_bindings binding_row
                  ON binding_row.id = NEW.demo_job_binding_id
                JOIN demo_image_versions image_row
                  ON image_row.id = NEW.image_version_id
                WHERE tool_row.id = NEW.tool_run_id
                  AND tool_row.demo_actor_id = NEW.demo_actor_id
                  AND tool_row.demo_session_id = NEW.demo_session_id
                  AND tool_row.outcome = 'COMPLETED'
                  AND tool_row.output_asset_id = NEW.output_asset_id
                  AND tool_row.output_asset_sha256 = NEW.output_asset_sha256
                  AND binding_row.demo_actor_id = NEW.demo_actor_id
                  AND binding_row.demo_session_id = NEW.demo_session_id
                  AND binding_row.endpoint_operation = 'tool.verify'
                  AND binding_row.target_type = 'TOOL_RUN'
                  AND binding_row.target_id = tool_row.id
                  AND image_row.demo_actor_id = NEW.demo_actor_id
                  AND image_row.demo_session_id = NEW.demo_session_id
                  AND image_row.tool_run_digest = tool_row.content_digest
                  AND image_row.verifier_digest = NEW.content_digest
                  AND image_row.result_asset_id = NEW.output_asset_id
                  AND image_row.result_asset_sha256 = NEW.output_asset_sha256
                  AND (
                      (image_row.version_kind IN ('EDITED','RESTORED','ROLLED_BACK')
                       AND NEW.outcome = 'PASS')
                      OR (image_row.version_kind = 'QUARANTINED'
                          AND NEW.outcome IN ('FAIL','HUMAN_REVIEW'))
                  )
            ) THEN
                RAISE EXCEPTION 'Demo verification ToolRun ownership mismatch';
            END IF;

        WHEN 'demo_aesthetic_profiles' THEN
            IF EXISTS (
                SELECT 1
                FROM jsonb_array_elements(NEW.evidence_digests) AS digest_entry(value)
                WHERE jsonb_typeof(digest_entry.value) <> 'string'
                   OR digest_entry.value #>> '{}' !~ '^[0-9a-f]{64}$'
                   OR NOT mirror_demo_evidence_owned_by(
                       NEW.demo_actor_id,
                       digest_entry.value #>> '{}'
                   )
            ) THEN
                RAISE EXCEPTION 'Demo AestheticProfile evidence ownership mismatch';
            END IF;
            IF NEW.demo_job_binding_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM demo_job_bindings binding_row
                WHERE binding_row.id = NEW.demo_job_binding_id
                  AND binding_row.demo_actor_id = NEW.demo_actor_id
                  AND binding_row.endpoint_operation IN ('profile.compile', 'profile.rebuild')
                  AND binding_row.target_type = 'DEMO_ACTOR'
                  AND binding_row.target_id = NEW.demo_actor_id
            ) THEN
                RAISE EXCEPTION 'Demo AestheticProfile compiler Job binding ownership mismatch';
            END IF;

        WHEN 'demo_context_compilations' THEN
            IF NOT EXISTS (
                SELECT 1 FROM demo_aesthetic_profiles profile_row
                WHERE profile_row.id = NEW.aesthetic_profile_id
                  AND profile_row.demo_actor_id = NEW.demo_actor_id
            ) OR NOT EXISTS (
                SELECT 1 FROM demo_job_bindings binding_row
                WHERE binding_row.id = NEW.demo_job_binding_id
                  AND binding_row.demo_actor_id = NEW.demo_actor_id
                  AND binding_row.demo_session_id = NEW.demo_session_id
                  AND binding_row.endpoint_operation = 'context.compile'
                  AND binding_row.target_type = 'DEMO_SESSION'
                  AND binding_row.target_id = NEW.demo_session_id
            ) THEN
                RAISE EXCEPTION 'Demo ContextCompilation ownership mismatch';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM jsonb_array_elements(
                    NEW.selected_evidence || NEW.rejected_evidence
                ) AS evidence_entry(value)
                WHERE jsonb_typeof(evidence_entry.value) IS DISTINCT FROM 'object'
                   OR jsonb_typeof(evidence_entry.value -> 'digest') IS DISTINCT FROM 'string'
                   OR evidence_entry.value ->> 'digest' !~ '^[0-9a-f]{64}$'
                   OR NOT mirror_demo_evidence_owned_by(
                       NEW.demo_actor_id,
                       evidence_entry.value ->> 'digest'
                   )
            ) THEN
                RAISE EXCEPTION 'Demo ContextCompilation evidence ownership mismatch';
            END IF;
    END CASE;
    RETURN NEW;
END;
$function$;
"""


_JOB_AND_LEDGER_AUTHORITY_SQL = r"""
CREATE OR REPLACE FUNCTION mirror_demo_validate_job_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_target_type text;
    expected_job_hash text;
    target_valid boolean := false;
    job_row jobs%ROWTYPE;
BEGIN
    expected_target_type := CASE NEW.endpoint_operation
        WHEN 'analysis.create' THEN 'FACE_OBSERVATION'
        WHEN 'questionnaire.run.create' THEN 'QUESTIONNAIRE_RUN'
        WHEN 'profile.compile' THEN 'DEMO_ACTOR'
        WHEN 'editing_session.create' THEN 'EDITING_SESSION'
        WHEN 'edit_plan.create' THEN 'EDIT_PLAN'
        WHEN 'edit_plan.execute' THEN 'EDIT_PLAN'
        WHEN 'image_version.restore' THEN 'IMAGE_VERSION'
        WHEN 'profile.rebuild' THEN 'DEMO_ACTOR'
        WHEN 'self_transfer.execute' THEN 'SELF_TRANSFER_RUN'
        WHEN 'tool.verify' THEN 'TOOL_RUN'
        WHEN 'context.compile' THEN 'DEMO_SESSION'
        ELSE NULL
    END;
    IF expected_target_type IS NULL OR NEW.target_type <> expected_target_type THEN
        RAISE EXCEPTION 'Demo endpoint and typed target disagree';
    END IF;

    CASE NEW.target_type
        WHEN 'DEMO_ACTOR' THEN
            target_valid := NEW.target_id = NEW.demo_actor_id
                AND EXISTS (SELECT 1 FROM demo_actors WHERE id = NEW.demo_actor_id);
        WHEN 'DEMO_SESSION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL
                AND NEW.target_id = NEW.demo_session_id
                AND EXISTS (
                    SELECT 1 FROM demo_sessions target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                );
        WHEN 'FACE_OBSERVATION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_face_observations target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'QUESTIONNAIRE_RUN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_questionnaire_runs target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'SELF_TRANSFER_RUN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_self_transfer_runs target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.record_kind = 'REQUEST'
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'EDITING_SESSION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_editing_sessions target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'IMAGE_VERSION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_image_versions target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'EDIT_PLAN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_edit_plans target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'EDIT_OPERATION' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM demo_edit_operations target_row
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
            );
        WHEN 'TOOL_RUN' THEN
            target_valid := NEW.demo_session_id IS NOT NULL AND EXISTS (
                SELECT 1
                FROM demo_tool_runs target_row
                JOIN demo_job_bindings execution_binding
                  ON execution_binding.id = target_row.demo_job_binding_id
                WHERE target_row.id = NEW.target_id
                  AND target_row.demo_actor_id = NEW.demo_actor_id
                  AND target_row.demo_session_id = NEW.demo_session_id
                  AND execution_binding.demo_actor_id = NEW.demo_actor_id
            );
    END CASE;
    IF NOT target_valid THEN
        RAISE EXCEPTION 'Demo job binding target ownership mismatch';
    END IF;

    SELECT * INTO job_row FROM jobs WHERE id = NEW.job_id FOR KEY SHARE;
    expected_job_hash := encode(
        sha256(
            convert_to(
                'mirror.demo/JobIdempotency/v1' || E'\n' || NEW.demo_actor_id || E'\n' ||
                NEW.endpoint_operation || E'\n' || NEW.idempotency_key_hash,
                'UTF8'
            )
        ),
        'hex'
    );
    IF NOT FOUND
        OR job_row.job_type <> ('demo_p3_p7.' || NEW.endpoint_operation)
        OR job_row.idempotency_key_hash <> expected_job_hash
        OR job_row.status <> 'PENDING'
        OR job_row.owner_user_id IS NOT NULL
        OR job_row.ingestion_upload_intent_id IS NOT NULL
        OR job_row.payload::jsonb <> '{}'::jsonb
        OR job_row.attempt_count <> 0
        OR job_row.lease_token IS NOT NULL
        OR job_row.lease_acquired_at IS NOT NULL
        OR job_row.lease_expires_at IS NOT NULL
        OR job_row.finalized_at IS NOT NULL
        OR job_row.result_asset_id IS NOT NULL
        OR job_row.result_code IS NOT NULL THEN
        RAISE EXCEPTION 'Formal Job is not a valid pending Demo execution envelope';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_preference_event()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    previous_sequence bigint;
    previous_digest text;
    target_valid boolean := false;
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtextextended('mirror.demo.preference/' || NEW.demo_actor_id, 0)
    );
    SELECT event_sequence, content_digest
    INTO previous_sequence, previous_digest
    FROM demo_preference_events
    WHERE demo_actor_id = NEW.demo_actor_id
    ORDER BY event_sequence DESC
    LIMIT 1;

    IF NOT FOUND THEN
        IF NEW.event_sequence <> 1 OR NEW.previous_event_digest <> repeat('0', 64) THEN
            RAISE EXCEPTION 'Demo preference ledger genesis is invalid';
        END IF;
    ELSIF NEW.event_sequence <> previous_sequence + 1
        OR NEW.previous_event_digest <> previous_digest THEN
        RAISE EXCEPTION 'Demo preference ledger sequence or digest chain is invalid';
    END IF;

    IF NEW.target_type IS NOT NULL THEN
        CASE NEW.target_type
            WHEN 'DEMO_ACTOR' THEN
                target_valid := NEW.target_id = NEW.demo_actor_id;
            WHEN 'BASELINE_FACE_MODEL' THEN
                target_valid := EXISTS (
                    SELECT 1 FROM demo_baseline_face_models target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                      AND (NEW.demo_session_id IS NULL OR
                           target_row.demo_session_id = NEW.demo_session_id)
                );
            WHEN 'SELF_STATE' THEN
                target_valid := EXISTS (
                    SELECT 1 FROM demo_self_states target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                      AND (NEW.demo_session_id IS NULL OR
                           target_row.demo_session_id = NEW.demo_session_id)
                );
            WHEN 'DESIRED_DELTA_PROFILE' THEN
                target_valid := EXISTS (
                    SELECT 1 FROM demo_desired_delta_profiles target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                      AND (NEW.demo_session_id IS NULL OR
                           target_row.demo_session_id = NEW.demo_session_id)
                );
            WHEN 'STYLE_PROFILE' THEN
                target_valid := EXISTS (
                    SELECT 1 FROM demo_style_profiles target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                      AND (NEW.demo_session_id IS NULL OR
                           target_row.demo_session_id = NEW.demo_session_id)
                );
            WHEN 'REFERENCE_PROFILE' THEN
                target_valid := EXISTS (
                    SELECT 1 FROM demo_reference_profiles target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                      AND (NEW.demo_session_id IS NULL OR
                           target_row.demo_session_id = NEW.demo_session_id)
                );
            WHEN 'IMAGE_VERSION' THEN
                target_valid := EXISTS (
                    SELECT 1 FROM demo_image_versions target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                      AND (NEW.demo_session_id IS NULL OR
                           target_row.demo_session_id = NEW.demo_session_id)
                );
            WHEN 'AESTHETIC_PROFILE' THEN
                target_valid := EXISTS (
                    SELECT 1 FROM demo_aesthetic_profiles target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                );
            WHEN 'CONTEXT_COMPILATION' THEN
                target_valid := EXISTS (
                    SELECT 1 FROM demo_context_compilations target_row
                    WHERE target_row.id = NEW.target_id
                      AND target_row.demo_actor_id = NEW.demo_actor_id
                      AND (NEW.demo_session_id IS NULL OR
                           target_row.demo_session_id = NEW.demo_session_id)
                );
        END CASE;
        IF NOT target_valid THEN
            RAISE EXCEPTION 'Demo preference event target ownership mismatch';
        END IF;
    END IF;

    IF NEW.event_type = 'ACTOR_TOMBSTONED' THEN
        IF NEW.source_type IS DISTINCT FROM 'SYSTEM_LIFECYCLE'
            OR NEW.demo_session_id IS NOT NULL
            OR NEW.target_type IS DISTINCT FROM 'DEMO_ACTOR'
            OR NEW.target_id IS DISTINCT FROM NEW.demo_actor_id
            OR NEW.signal <> '{}'::jsonb THEN
            RAISE EXCEPTION 'Demo actor tombstone lifecycle authority is invalid';
        END IF;
    ELSIF NEW.event_type = 'SESSION_CLOSED' THEN
        IF NEW.source_type IS DISTINCT FROM 'SYSTEM_LIFECYCLE'
            OR NEW.demo_session_id IS NULL
            OR NEW.target_type IS NOT NULL
            OR NEW.target_id IS NOT NULL
            OR NEW.signal <> '{}'::jsonb THEN
            RAISE EXCEPTION 'Demo session close lifecycle authority is invalid';
        END IF;
    ELSIF NEW.event_type = 'EDITING_SESSION_CLOSED' THEN
        IF NEW.source_type IS DISTINCT FROM 'SYSTEM_LIFECYCLE'
            OR NEW.demo_session_id IS NULL
            OR NEW.target_type IS NOT NULL
            OR NEW.target_id IS NOT NULL
            OR NEW.signal IS DISTINCT FROM jsonb_build_object(
                'editing_session_id', NEW.signal ->> 'editing_session_id'
            )
            OR COALESCE(NEW.signal ->> 'editing_session_id', '') !~ '^[0-9a-f]{32}$'
            OR NOT EXISTS (
                SELECT 1 FROM demo_editing_sessions editing_row
                WHERE editing_row.id = NEW.signal ->> 'editing_session_id'
                  AND editing_row.demo_actor_id = NEW.demo_actor_id
                  AND editing_row.demo_session_id = NEW.demo_session_id
            ) THEN
            RAISE EXCEPTION 'Demo editing session close lifecycle authority is invalid';
        END IF;
    ELSIF NEW.event_type = 'TOMBSTONE' AND NEW.target_type IS NULL THEN
        IF NEW.source_type IS DISTINCT FROM 'SYSTEM_LIFECYCLE'
            OR NEW.demo_session_id IS NULL
            OR NEW.target_id IS NOT NULL
            OR NEW.signal IS DISTINCT FROM jsonb_build_object(
                'authority_id', NEW.signal ->> 'authority_id',
                'authority_type', NEW.signal ->> 'authority_type'
            )
            OR COALESCE(NEW.signal ->> 'authority_id', '') !~ '^[0-9a-f]{32}$'
            OR COALESCE(NEW.signal ->> 'authority_type', '') NOT IN (
                'DEMO_SESSION',
                'EDITING_SESSION'
            )
            OR (
                NEW.signal ->> 'authority_type' = 'DEMO_SESSION'
                AND NEW.signal ->> 'authority_id' <> NEW.demo_session_id
            )
            OR (
                NEW.signal ->> 'authority_type' = 'EDITING_SESSION'
                AND NOT EXISTS (
                    SELECT 1 FROM demo_editing_sessions editing_row
                    WHERE editing_row.id = NEW.signal ->> 'authority_id'
                      AND editing_row.demo_actor_id = NEW.demo_actor_id
                      AND editing_row.demo_session_id = NEW.demo_session_id
                )
            ) THEN
            RAISE EXCEPTION 'Demo terminal tombstone lifecycle authority is invalid';
        END IF;
    ELSIF NEW.event_type = 'RESET' THEN
        IF NEW.target_type IS DISTINCT FROM 'DEMO_ACTOR'
            OR jsonb_typeof(NEW.signal -> 'reset_watermark') IS DISTINCT FROM 'number'
            OR (NEW.signal ->> 'reset_watermark')::bigint < 0
            OR (NEW.signal ->> 'reset_watermark')::bigint >= NEW.event_sequence THEN
            RAISE EXCEPTION 'Demo RESET requires actor target and prior event watermark';
        END IF;
    ELSIF NEW.event_type IN ('ROLLBACK', 'TOMBSTONE', 'DELETE') THEN
        IF NEW.target_type IS NULL OR NEW.target_type = 'DEMO_ACTOR' THEN
            RAISE EXCEPTION 'Demo lifecycle event requires a typed derived target';
        END IF;
    ELSIF NEW.event_type IN ('IMAGE_ACCEPTED', 'IMAGE_REJECTED', 'IMAGE_ADJUSTED') THEN
        IF NEW.target_type IS DISTINCT FROM 'IMAGE_VERSION'
            OR NEW.source_type NOT IN ('EXPLICIT_USER_ACTION', 'EDIT_FEEDBACK') THEN
            RAISE EXCEPTION 'Demo image feedback requires explicit user signal and ImageVersion target';
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_terminal_binding()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_TABLE_NAME = 'demo_preference_events' THEN
        IF NEW.event_type = 'ACTOR_TOMBSTONED' AND NOT EXISTS (
            SELECT 1 FROM demo_actors actor_row
            WHERE actor_row.id = NEW.demo_actor_id
              AND actor_row.tombstoned_at IS NOT DISTINCT FROM NEW.occurred_at
        ) THEN
            RAISE EXCEPTION 'Demo actor tombstone header lacks matching lifecycle event';
        ELSIF NEW.event_type = 'SESSION_CLOSED' AND NOT EXISTS (
            SELECT 1 FROM demo_sessions session_row
            WHERE session_row.id = NEW.demo_session_id
              AND session_row.demo_actor_id = NEW.demo_actor_id
              AND session_row.closed_at IS NOT DISTINCT FROM NEW.occurred_at
        ) THEN
            RAISE EXCEPTION 'Demo session close header lacks matching lifecycle event';
        ELSIF NEW.event_type = 'EDITING_SESSION_CLOSED' AND NOT EXISTS (
            SELECT 1 FROM demo_editing_sessions editing_row
            WHERE editing_row.id = NEW.signal ->> 'editing_session_id'
              AND editing_row.demo_actor_id = NEW.demo_actor_id
              AND editing_row.demo_session_id = NEW.demo_session_id
              AND editing_row.closed_at IS NOT DISTINCT FROM NEW.occurred_at
        ) THEN
            RAISE EXCEPTION 'Demo editing session close header lacks matching lifecycle event';
        ELSIF NEW.event_type = 'TOMBSTONE'
            AND NEW.target_type IS NULL
            AND NEW.signal ->> 'authority_type' = 'DEMO_SESSION'
            AND NOT EXISTS (
                SELECT 1 FROM demo_sessions session_row
                WHERE session_row.id = NEW.signal ->> 'authority_id'
                  AND session_row.demo_actor_id = NEW.demo_actor_id
                  AND session_row.id = NEW.demo_session_id
                  AND session_row.tombstoned_at IS NOT DISTINCT FROM NEW.occurred_at
            ) THEN
            RAISE EXCEPTION 'Demo session tombstone header lacks matching lifecycle event';
        ELSIF NEW.event_type = 'TOMBSTONE'
            AND NEW.target_type IS NULL
            AND NEW.signal ->> 'authority_type' = 'EDITING_SESSION'
            AND NOT EXISTS (
                SELECT 1 FROM demo_editing_sessions editing_row
                WHERE editing_row.id = NEW.signal ->> 'authority_id'
                  AND editing_row.demo_actor_id = NEW.demo_actor_id
                  AND editing_row.demo_session_id = NEW.demo_session_id
                  AND editing_row.tombstoned_at IS NOT DISTINCT FROM NEW.occurred_at
            ) THEN
            RAISE EXCEPTION 'Demo editing session tombstone header lacks matching lifecycle event';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_TABLE_NAME = 'demo_actors' THEN
        IF OLD.tombstoned_at IS NULL
            AND NEW.tombstoned_at IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM demo_preference_events event_row
                WHERE event_row.demo_actor_id = NEW.id
                  AND event_row.demo_session_id IS NULL
                  AND event_row.event_type = 'ACTOR_TOMBSTONED'
                  AND event_row.source_type = 'SYSTEM_LIFECYCLE'
                  AND event_row.target_type = 'DEMO_ACTOR'
                  AND event_row.target_id = NEW.id
                  AND event_row.signal = '{}'::jsonb
                  AND event_row.occurred_at IS NOT DISTINCT FROM NEW.tombstoned_at
            ) THEN
            RAISE EXCEPTION 'Demo actor tombstone requires matching lifecycle event';
        END IF;
    ELSIF TG_TABLE_NAME = 'demo_sessions' THEN
        IF OLD.closed_at IS NULL
            AND NEW.closed_at IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM demo_preference_events event_row
                WHERE event_row.demo_actor_id = NEW.demo_actor_id
                  AND event_row.demo_session_id = NEW.id
                  AND event_row.event_type = 'SESSION_CLOSED'
                  AND event_row.source_type = 'SYSTEM_LIFECYCLE'
                  AND event_row.target_type IS NULL
                  AND event_row.target_id IS NULL
                  AND event_row.signal = '{}'::jsonb
                  AND event_row.occurred_at IS NOT DISTINCT FROM NEW.closed_at
            ) THEN
            RAISE EXCEPTION 'Demo session close requires matching lifecycle event';
        END IF;
        IF OLD.tombstoned_at IS NULL
            AND NEW.tombstoned_at IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM demo_preference_events event_row
                WHERE event_row.demo_actor_id = NEW.demo_actor_id
                  AND event_row.demo_session_id = NEW.id
                  AND event_row.event_type = 'TOMBSTONE'
                  AND event_row.source_type = 'SYSTEM_LIFECYCLE'
                  AND event_row.target_type IS NULL
                  AND event_row.target_id IS NULL
                  AND event_row.signal = jsonb_build_object(
                      'authority_id', NEW.id,
                      'authority_type', 'DEMO_SESSION'
                  )
                  AND event_row.occurred_at IS NOT DISTINCT FROM NEW.tombstoned_at
            ) THEN
            RAISE EXCEPTION 'Demo session tombstone requires matching lifecycle event';
        END IF;
    ELSIF TG_TABLE_NAME = 'demo_editing_sessions' THEN
        IF OLD.closed_at IS NULL
            AND NEW.closed_at IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM demo_preference_events event_row
                WHERE event_row.demo_actor_id = NEW.demo_actor_id
                  AND event_row.demo_session_id = NEW.demo_session_id
                  AND event_row.event_type = 'EDITING_SESSION_CLOSED'
                  AND event_row.source_type = 'SYSTEM_LIFECYCLE'
                  AND event_row.target_type IS NULL
                  AND event_row.target_id IS NULL
                  AND event_row.signal = jsonb_build_object('editing_session_id', NEW.id)
                  AND event_row.occurred_at IS NOT DISTINCT FROM NEW.closed_at
            ) THEN
            RAISE EXCEPTION 'Demo editing session close requires matching lifecycle event';
        END IF;
        IF OLD.tombstoned_at IS NULL
            AND NEW.tombstoned_at IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM demo_preference_events event_row
                WHERE event_row.demo_actor_id = NEW.demo_actor_id
                  AND event_row.demo_session_id = NEW.demo_session_id
                  AND event_row.event_type = 'TOMBSTONE'
                  AND event_row.source_type = 'SYSTEM_LIFECYCLE'
                  AND event_row.target_type IS NULL
                  AND event_row.target_id IS NULL
                  AND event_row.signal = jsonb_build_object(
                      'authority_id', NEW.id,
                      'authority_type', 'EDITING_SESSION'
                  )
                  AND event_row.occurred_at IS NOT DISTINCT FROM NEW.tombstoned_at
            ) THEN
            RAISE EXCEPTION 'Demo editing session tombstone requires matching lifecycle event';
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION mirror_demo_validate_accepted_episode()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
    expected_trajectory jsonb;
    trajectory_count integer;
    terminal_sequence integer;
    trajectory_image_id text;
BEGIN
    PERFORM mirror_demo_require_asset(NEW.source_asset_id, NEW.source_asset_sha256);
    PERFORM mirror_demo_require_asset(NEW.final_asset_id, NEW.final_asset_sha256);
    IF jsonb_array_length(NEW.trajectory_digests) = 0 OR EXISTS (
        SELECT 1
        FROM jsonb_array_elements(NEW.trajectory_digests) AS digest_entry(value)
        WHERE jsonb_typeof(digest_entry.value) <> 'string'
           OR digest_entry.value #>> '{}' !~ '^[0-9a-f]{64}$'
    ) THEN
        RAISE EXCEPTION 'Demo accepted episode trajectory digest list is invalid';
    END IF;
    WITH RECURSIVE image_chain AS (
        SELECT
            image_row.id,
            image_row.parent_version_id,
            image_row.sequence,
            image_row.content_digest
        FROM demo_image_versions image_row
        WHERE image_row.id = NEW.accepted_image_version_id
          AND image_row.demo_actor_id = NEW.demo_actor_id
          AND image_row.demo_session_id = NEW.demo_session_id
          AND image_row.editing_session_id = NEW.editing_session_id

        UNION ALL

        SELECT
            parent_row.id,
            parent_row.parent_version_id,
            parent_row.sequence,
            parent_row.content_digest
        FROM demo_image_versions parent_row
        JOIN image_chain child_row
          ON child_row.parent_version_id = parent_row.id
        WHERE parent_row.demo_actor_id = NEW.demo_actor_id
          AND parent_row.demo_session_id = NEW.demo_session_id
          AND parent_row.editing_session_id = NEW.editing_session_id
          AND parent_row.sequence = child_row.sequence - 1
    )
    SELECT
        jsonb_agg(image_chain.content_digest ORDER BY image_chain.sequence),
        count(*)::integer,
        max(image_chain.sequence)::integer
    INTO expected_trajectory, trajectory_count, terminal_sequence
    FROM image_chain;
    IF trajectory_count = 0
        OR terminal_sequence <> trajectory_count - 1
        OR expected_trajectory IS DISTINCT FROM NEW.trajectory_digests THEN
        RAISE EXCEPTION 'Demo accepted episode trajectory lineage mismatch';
    END IF;

    FOR trajectory_image_id IN
        WITH RECURSIVE image_chain AS (
            SELECT image_row.id, image_row.parent_version_id, image_row.sequence
            FROM demo_image_versions image_row
            WHERE image_row.id = NEW.accepted_image_version_id

            UNION ALL

            SELECT parent_row.id, parent_row.parent_version_id, parent_row.sequence
            FROM demo_image_versions parent_row
            JOIN image_chain child_row ON child_row.parent_version_id = parent_row.id
        )
        SELECT image_chain.id FROM image_chain ORDER BY image_chain.sequence
    LOOP
        PERFORM mirror_demo_require_image_execution_binding(trajectory_image_id);
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM demo_image_versions image_row
        JOIN demo_editing_sessions editing_row
          ON editing_row.id = image_row.editing_session_id
        JOIN demo_edit_plans plan_row
          ON plan_row.content_digest = image_row.plan_digest
        JOIN demo_tool_runs tool_row
          ON tool_row.content_digest = image_row.tool_run_digest
        JOIN demo_edit_operations operation_row
          ON operation_row.id = tool_row.edit_operation_id
         AND operation_row.content_digest = tool_row.edit_operation_digest
         AND operation_row.edit_plan_id = plan_row.id
        JOIN demo_verification_results verification_row
          ON verification_row.id = NEW.verification_result_id
        JOIN demo_preference_events event_row
          ON event_row.id = NEW.acceptance_event_id
        WHERE image_row.id = NEW.accepted_image_version_id
          AND image_row.demo_actor_id = NEW.demo_actor_id
          AND image_row.demo_session_id = NEW.demo_session_id
          AND image_row.editing_session_id = NEW.editing_session_id
          AND image_row.result_asset_id = NEW.final_asset_id
          AND image_row.result_asset_sha256 = NEW.final_asset_sha256
          AND image_row.version_kind IN ('EDITED','RESTORED','ROLLED_BACK')
          AND editing_row.source_asset_id = NEW.source_asset_id
          AND editing_row.source_asset_sha256 = NEW.source_asset_sha256
          AND plan_row.record_kind = 'RESULT'
          AND operation_row.operation_index = jsonb_array_length(plan_row.operation_specs) - 1
          AND verification_row.demo_actor_id = NEW.demo_actor_id
          AND verification_row.demo_session_id = NEW.demo_session_id
          AND verification_row.image_version_id = image_row.id
          AND verification_row.tool_run_id = tool_row.id
          AND verification_row.content_digest = image_row.verifier_digest
          AND verification_row.output_asset_id = NEW.final_asset_id
          AND verification_row.output_asset_sha256 = NEW.final_asset_sha256
          AND verification_row.outcome = 'PASS'
          AND event_row.demo_actor_id = NEW.demo_actor_id
          AND event_row.demo_session_id = NEW.demo_session_id
          AND event_row.event_type = 'IMAGE_ACCEPTED'
          AND event_row.source_type IN ('EXPLICIT_USER_ACTION', 'EDIT_FEEDBACK')
          AND event_row.target_type = 'IMAGE_VERSION'
          AND event_row.target_id = image_row.id
    ) THEN
        RAISE EXCEPTION 'Only verified user-accepted Demo image versions may become episodes';
    END IF;
    RETURN NEW;
END;
$function$;
"""


_DEMO_TABLES: tuple[str, ...] = (
    "demo_actors",
    "demo_sessions",
    "demo_synthetic_identities",
    "demo_face_observations",
    "demo_face_observation_repeats",
    "demo_baseline_face_models",
    "demo_self_states",
    "demo_question_banks",
    "demo_question_pairs",
    "demo_questionnaire_runs",
    "demo_questionnaire_steps",
    "demo_desired_delta_profiles",
    "demo_style_profiles",
    "demo_identity_constraints",
    "demo_self_transfer_runs",
    "demo_reference_profiles",
    "demo_editing_sessions",
    "demo_image_versions",
    "demo_edit_plans",
    "demo_edit_operations",
    "demo_tool_runs",
    "demo_verification_results",
    "demo_preference_events",
    "demo_accepted_visual_episodes",
    "demo_aesthetic_profiles",
    "demo_context_compilations",
    "demo_job_bindings",
)

_REFERENCE_GUARD_TABLES: tuple[str, ...] = (
    "demo_synthetic_identities",
    "demo_face_observations",
    "demo_baseline_face_models",
    "demo_question_pairs",
    "demo_questionnaire_steps",
    "demo_desired_delta_profiles",
    "demo_style_profiles",
    "demo_identity_constraints",
    "demo_self_transfer_runs",
    "demo_reference_profiles",
    "demo_editing_sessions",
    "demo_image_versions",
    "demo_edit_plans",
    "demo_tool_runs",
    "demo_verification_results",
    "demo_aesthetic_profiles",
    "demo_context_compilations",
)

_DEMO_TABLE_DROP_ORDER: tuple[str, ...] = (
    "demo_accepted_visual_episodes",
    "demo_preference_events",
    "demo_context_compilations",
    "demo_aesthetic_profiles",
    "demo_verification_results",
    "demo_tool_runs",
    "demo_edit_operations",
    "demo_edit_plans",
    "demo_image_versions",
    "demo_editing_sessions",
    "demo_reference_profiles",
    "demo_self_transfer_runs",
    "demo_identity_constraints",
    "demo_style_profiles",
    "demo_desired_delta_profiles",
    "demo_questionnaire_steps",
    "demo_questionnaire_runs",
    "demo_question_pairs",
    "demo_question_banks",
    "demo_self_states",
    "demo_baseline_face_models",
    "demo_face_observation_repeats",
    "demo_face_observations",
    "demo_synthetic_identities",
    "demo_job_bindings",
    "demo_sessions",
    "demo_actors",
)

_POPULATED_DOWNGRADE_SQL = r"""
DO $block$
DECLARE
    demo_table text;
    has_rows boolean;
BEGIN
    FOREACH demo_table IN ARRAY ARRAY[
        'demo_actors',
        'demo_sessions',
        'demo_synthetic_identities',
        'demo_face_observations',
        'demo_face_observation_repeats',
        'demo_baseline_face_models',
        'demo_self_states',
        'demo_question_banks',
        'demo_question_pairs',
        'demo_questionnaire_runs',
        'demo_questionnaire_steps',
        'demo_desired_delta_profiles',
        'demo_style_profiles',
        'demo_identity_constraints',
        'demo_self_transfer_runs',
        'demo_reference_profiles',
        'demo_editing_sessions',
        'demo_image_versions',
        'demo_edit_plans',
        'demo_edit_operations',
        'demo_tool_runs',
        'demo_verification_results',
        'demo_preference_events',
        'demo_accepted_visual_episodes',
        'demo_aesthetic_profiles',
        'demo_context_compilations',
        'demo_job_bindings'
    ]::text[] LOOP
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I LIMIT 1)', demo_table)
        INTO has_rows;
        IF has_rows THEN
            RAISE EXCEPTION 'Prototype migration downgrade blocked by populated table %', demo_table;
        END IF;
    END LOOP;

    IF EXISTS (
        SELECT 1
        FROM job_attempts attempt_row
        JOIN jobs job_row ON job_row.id = attempt_row.job_id
        WHERE job_row.job_type LIKE 'demo_p3_p7.%'
    ) THEN
        RAISE EXCEPTION 'Prototype migration downgrade blocked by Demo JobAttempt authority';
    END IF;
    IF EXISTS (SELECT 1 FROM jobs WHERE job_type LIKE 'demo_p3_p7.%') THEN
        RAISE EXCEPTION 'Prototype migration downgrade blocked by Demo Job authority';
    END IF;
    IF EXISTS (
        SELECT 1 FROM asset_variants
        WHERE variant_type LIKE 'demo_p3_p7\_%' ESCAPE '\'
    ) THEN
        RAISE EXCEPTION 'Prototype migration downgrade blocked by Demo AssetVariant authority';
    END IF;
END;
$block$;
"""


def _create_database_authority() -> None:
    op.execute(_CANONICAL_AUTHORITY_SQL)
    op.execute(_REFERENCE_AUTHORITY_SQL)
    op.execute(_JOB_AND_LEDGER_AUTHORITY_SQL)
    for table_name in _DEMO_TABLES:
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_demo_authority_{table_name} "
                f"BEFORE INSERT OR UPDATE OR DELETE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION mirror_demo_guard_authority()"
            )
        )
    for table_name in _REFERENCE_GUARD_TABLES:
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_demo_references_{table_name} "
                f"BEFORE INSERT ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_references()"
            )
        )
    for table_name in ("demo_image_versions", "demo_verification_results"):
        op.execute(
            sa.text(
                f"CREATE CONSTRAINT TRIGGER trg_demo_image_execution_binding_{table_name} "
                f"AFTER INSERT ON {table_name} "
                "DEFERRABLE INITIALLY DEFERRED "
                "FOR EACH ROW EXECUTE FUNCTION "
                "mirror_demo_validate_image_execution_binding()"
            )
        )
    op.execute(
        "CREATE TRIGGER trg_demo_job_binding_validation "
        "BEFORE INSERT ON demo_job_bindings "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_job_binding()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_preference_event_chain "
        "BEFORE INSERT ON demo_preference_events "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_preference_event()"
    )
    for table_name in ("demo_actors", "demo_sessions", "demo_editing_sessions"):
        op.execute(
            sa.text(
                f"CREATE CONSTRAINT TRIGGER trg_demo_terminal_binding_{table_name} "
                f"AFTER UPDATE ON {table_name} "
                "DEFERRABLE INITIALLY DEFERRED "
                "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_terminal_binding()"
            )
        )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_demo_terminal_binding_preference_events "
        "AFTER INSERT ON demo_preference_events "
        "DEFERRABLE INITIALLY DEFERRED "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_terminal_binding()"
    )
    op.execute(
        "CREATE TRIGGER trg_demo_accepted_episode_validation "
        "BEFORE INSERT ON demo_accepted_visual_episodes "
        "FOR EACH ROW EXECUTE FUNCTION mirror_demo_validate_accepted_episode()"
    )


def upgrade() -> None:
    _create_session_and_p3_tables()
    _create_p4_tables()
    _create_p5_tables()
    _create_p6_tables()
    _create_p7_and_job_tables()
    _create_deferred_job_binding_foreign_keys()
    _create_deferred_image_execution_foreign_keys()
    _create_indexes()
    _create_database_authority()


def downgrade() -> None:
    op.execute(_POPULATED_DOWNGRADE_SQL)
    _drop_deferred_image_execution_foreign_keys()
    for table_name in _DEMO_TABLE_DROP_ORDER:
        op.drop_table(table_name)
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_accepted_episode()")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_image_execution_binding()")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_require_image_execution_binding(text)")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_terminal_binding()")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_preference_event()")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_job_binding()")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_validate_references()")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_require_current_synthetic_admission(text)")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_formal_qa_snapshot_digest(text)")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_evidence_owned_by(text, text)")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_require_asset(text, text)")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_guard_authority()")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_authority_projection(jsonb, text)")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_digest(text, jsonb)")
    op.execute("DROP FUNCTION IF EXISTS mirror_demo_canonical_json(jsonb)")
