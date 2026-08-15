from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.state import InstanceState

from mirror_api.db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class IdMixin:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    phone_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    age_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InviteCode(IdMixin, TimestampMixin, Base):
    __tablename__ = "invite_codes"

    code_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("max_uses > 0", name="positive_max_uses"),
        CheckConstraint("use_count >= 0 AND use_count <= max_uses", name="valid_use_count"),
    )


class PhoneVerificationChallenge(IdMixin, Base):
    __tablename__ = "phone_verification_challenges"

    phone_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class UserSession(IdMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ConsentRecord(IdMixin, Base):
    __tablename__ = "consent_records"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_type: Mapped[str] = mapped_column(String(48), nullable=False)
    purpose: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(48), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("consent_records.id", ondelete="RESTRICT")
    )
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "(action = 'grant' AND granted_at IS NOT NULL AND withdrawn_at IS NULL) OR "
            "(action = 'withdraw' AND granted_at IS NULL AND withdrawn_at IS NOT NULL "
            "AND supersedes_id IS NOT NULL)",
            name="valid_consent_event",
        ),
    )


class Asset(IdMixin, TimestampMixin, Base):
    __tablename__ = "assets"

    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    asset_role: Mapped[str] = mapped_column(String(24), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_ai_modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "asset_role IN ('original','derived','synthetic')", name="valid_asset_role"
        ),
        CheckConstraint("byte_size > 0", name="positive_byte_size"),
        CheckConstraint("width > 0 AND height > 0", name="positive_dimensions"),
    )


class AssetVariant(IdMixin, Base):
    __tablename__ = "asset_variants"

    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    result_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), unique=True
    )
    variant_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint("source_asset_id <> result_asset_id", name="distinct_source_result"),
    )


class AssetAccessAudit(IdMixin, Base):
    __tablename__ = "asset_access_audits"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class BaselineFaceModel(IdMixin, Base):
    """Versioned measurement evidence; this row is not a trained ML model."""

    __tablename__ = "baseline_face_models"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    analyzer_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_schema_version: Mapped[str] = mapped_column(String(48), nullable=False)
    pose: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    quality_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    measurement_normalization_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "version"),
        CheckConstraint("version > 0", name="positive_baseline_face_model_version"),
    )


class BaselineMeasurement(IdMixin, Base):
    __tablename__ = "baseline_measurements"

    baseline_face_model_id: Mapped[str] = mapped_column(
        ForeignKey("baseline_face_models.id", ondelete="CASCADE"), index=True
    )
    measurement_key: Mapped[str] = mapped_column(String(96), nullable=False)
    normalized_value: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    measurement_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    measurement_method_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("baseline_face_model_id", "measurement_key"),
        CheckConstraint(
            "measurement_confidence >= 0 AND measurement_confidence <= 1",
            name="baseline_measurement_confidence_range",
        ),
    )


class SelfState(IdMixin, Base):
    __tablename__ = "self_states"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_face_model_id: Mapped[str] = mapped_column(
        ForeignKey("baseline_face_models.id", ondelete="RESTRICT"), index=True
    )
    reliable_dimensions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    unreliable_dimensions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    identity_anchor_reference: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    state_schema_version: Mapped[str] = mapped_column(String(48), nullable=False)
    derivation_algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "version"),
        CheckConstraint("version > 0", name="positive_self_state_version"),
    )


class BaselineMorphologyDescriptor(IdMixin, Base):
    __tablename__ = "baseline_morphology_descriptors"

    source_self_state_id: Mapped[str] = mapped_column(
        ForeignKey("self_states.id", ondelete="RESTRICT"), unique=True
    )
    descriptor_version: Mapped[str] = mapped_column(String(48), nullable=False)
    measurement_normalization_version: Mapped[str] = mapped_column(String(48), nullable=False)
    continuous_dimensions: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    reliability: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class QuestionBankVersion(IdMixin, Base):
    __tablename__ = "question_bank_versions"

    version: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    qa_version: Mapped[str] = mapped_column(String(48), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SyntheticIdentity(IdMixin, Base):
    __tablename__ = "synthetic_identities"

    bank_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_bank_versions.id", ondelete="RESTRICT"), index=True
    )
    generator_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    generator_model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(48), nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    adult_synthetic_attested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class QuestionAsset(IdMixin, Base):
    __tablename__ = "question_assets"

    synthetic_identity_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_identities.id", ondelete="RESTRICT"), index=True
    )
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), unique=True)
    target_feature: Mapped[str] = mapped_column(String(64), nullable=False)
    target_delta: Mapped[Decimal] = mapped_column(Numeric(8, 5), nullable=False)
    measured_delta: Mapped[Decimal | None] = mapped_column(Numeric(8, 5))
    measurements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    qa_status: Mapped[str] = mapped_column(String(24), default="generated", nullable=False)
    qa_version: Mapped[str] = mapped_column(String(48), nullable=False)


class QuestionTemplate(IdMixin, Base):
    __tablename__ = "question_templates"

    bank_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_bank_versions.id", ondelete="RESTRICT"), index=True
    )
    slot_id: Mapped[str] = mapped_column(String(48), nullable=False)
    target_dimension: Mapped[str] = mapped_column(String(96), nullable=False)
    question_purpose: Mapped[str] = mapped_column(String(48), nullable=False)
    stimulus_strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    coverage_role: Mapped[str] = mapped_column(String(48), nullable=False)
    expected_evidence_type: Mapped[str] = mapped_column(String(48), nullable=False)
    validation_requirements: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    template_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (UniqueConstraint("bank_version_id", "slot_id", "template_version"),)


class QuestionnaireRun(IdMixin, Base):
    __tablename__ = "questionnaire_runs"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    bank_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_bank_versions.id", ondelete="RESTRICT"), index=True
    )
    baseline_face_model_id: Mapped[str] = mapped_column(
        ForeignKey("baseline_face_models.id", ondelete="RESTRICT"), index=True
    )
    self_state_version_id: Mapped[str] = mapped_column(
        ForeignKey("self_states.id", ondelete="RESTRICT"), index=True
    )
    routing_algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    route_seed: Mapped[str] = mapped_column(String(128), nullable=False)
    measurement_normalization_version: Mapped[str] = mapped_column(String(48), nullable=False)
    morphology_descriptor_version: Mapped[str] = mapped_column(String(48), nullable=False)
    neighborhood_metric_version: Mapped[str] = mapped_column(String(48), nullable=False)
    stimulus_generator_version: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    posterior: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("question_count >= 0", name="nonnegative_question_count"),)


class QuestionInstance(IdMixin, Base):
    __tablename__ = "question_instances"

    questionnaire_run_id: Mapped[str] = mapped_column(
        ForeignKey("questionnaire_runs.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[str] = mapped_column(
        ForeignKey("question_templates.id", ondelete="RESTRICT"), index=True
    )
    baseline_face_model_id: Mapped[str] = mapped_column(
        ForeignKey("baseline_face_models.id", ondelete="RESTRICT")
    )
    self_state_version_id: Mapped[str] = mapped_column(
        ForeignKey("self_states.id", ondelete="RESTRICT")
    )
    synthetic_identity_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_identities.id", ondelete="RESTRICT")
    )
    asset_a_id: Mapped[str] = mapped_column(ForeignKey("question_assets.id", ondelete="RESTRICT"))
    asset_b_id: Mapped[str] = mapped_column(ForeignKey("question_assets.id", ondelete="RESTRICT"))
    target_dimension: Mapped[str] = mapped_column(String(96), nullable=False)
    variant_a_delta: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    variant_b_delta: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    neighborhood_distance: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    neighborhood_metric_version: Mapped[str] = mapped_column(String(48), nullable=False)
    excluded_target_dimensions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    randomization_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    question_bank_version: Mapped[str] = mapped_column(String(48), nullable=False)
    routing_algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    stimulus_generator_version: Mapped[str] = mapped_column(String(48), nullable=False)
    target_delta: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    non_target_max_error: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    isolation_threshold: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint("asset_a_id <> asset_b_id", name="distinct_question_instance_assets"),
        CheckConstraint("neighborhood_distance >= 0", name="nonnegative_neighborhood_distance"),
        CheckConstraint("non_target_max_error >= 0", name="nonnegative_non_target_error"),
        CheckConstraint("isolation_threshold >= 0", name="nonnegative_isolation_threshold"),
    )


class QuestionnaireRoute(IdMixin, Base):
    __tablename__ = "questionnaire_routes"

    questionnaire_run_id: Mapped[str] = mapped_column(
        ForeignKey("questionnaire_runs.id", ondelete="CASCADE"), unique=True
    )
    self_state_version_id: Mapped[str] = mapped_column(
        ForeignKey("self_states.id", ondelete="RESTRICT"), index=True
    )
    routing_algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    route_seed: Mapped[str] = mapped_column(String(128), nullable=False)
    selected_template_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    coverage_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    uncertainty_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    routing_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class QuestionResponse(IdMixin, Base):
    __tablename__ = "question_responses"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("questionnaire_runs.id", ondelete="CASCADE"), index=True
    )
    question_instance_id: Mapped[str] = mapped_column(
        ForeignKey("question_instances.id", ondelete="RESTRICT")
    )
    ordinal_choice: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    response_ms: Mapped[int | None] = mapped_column(Integer)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("run_id", "question_instance_id"),
        CheckConstraint(
            "ordinal_choice >= -2 AND ordinal_choice <= 2", name="ordinal_choice_range"
        ),
    )


class DesiredDeltaProfileVersion(IdMixin, Base):
    __tablename__ = "desired_delta_profile_versions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    self_state_version_id: Mapped[str] = mapped_column(
        ForeignKey("self_states.id", ondelete="RESTRICT"), index=True
    )
    inference_algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_fusion_version: Mapped[str] = mapped_column(String(48), nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    questionnaire_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("questionnaire_runs.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("user_id", "version"),
        CheckConstraint("version > 0", name="delta_version_positive"),
    )


class DesiredDeltaDimension(IdMixin, Base):
    __tablename__ = "desired_delta_dimensions"

    desired_delta_profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("desired_delta_profile_versions.id", ondelete="CASCADE"), index=True
    )
    dimension_key: Mapped[str] = mapped_column(String(96), nullable=False)
    direction: Mapped[int] = mapped_column(Integer, nullable=False)
    magnitude: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    preference_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    generalization_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    transfer_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    user_lock: Mapped[str] = mapped_column(String(24), default="none", nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("desired_delta_profile_version_id", "dimension_key"),
        CheckConstraint("direction >= -1 AND direction <= 1", name="desired_delta_direction"),
        CheckConstraint("magnitude >= 0", name="nonnegative_desired_delta_magnitude"),
        CheckConstraint(
            "preference_confidence >= 0 AND preference_confidence <= 1",
            name="preference_confidence_range",
        ),
        CheckConstraint(
            "generalization_confidence >= 0 AND generalization_confidence <= 1",
            name="generalization_confidence_range",
        ),
        CheckConstraint(
            "transfer_confidence >= 0 AND transfer_confidence <= 1",
            name="transfer_confidence_range",
        ),
        CheckConstraint("user_lock IN ('none','preserve')", name="valid_user_lock"),
        CheckConstraint(
            "lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound",
            name="ordered_desired_delta_bounds",
        ),
    )


class StyleProfileVersion(IdMixin, Base):
    __tablename__ = "style_profile_versions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    negative_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    inference_algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("user_id", "version"),
        CheckConstraint("version > 0", name="positive_style_profile_version"),
    )


class IdentityConstraintVersion(IdMixin, Base):
    __tablename__ = "identity_constraint_versions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    self_state_version_id: Mapped[str] = mapped_column(
        ForeignKey("self_states.id", ondelete="RESTRICT"), index=True
    )
    preserve_regions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    feature_locks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    allowed_delta_bounds: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    edit_strength_limits: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    context_restrictions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    identity_preservation_requirements: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("user_id", "version"),
        CheckConstraint("version > 0", name="identity_version_positive"),
    )


class SelfTransferValidationRun(IdMixin, Base):
    __tablename__ = "self_transfer_validation_runs"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    desired_delta_profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("desired_delta_profile_versions.id", ondelete="RESTRICT"), index=True
    )
    baseline_face_model_id: Mapped[str] = mapped_column(
        ForeignKey("baseline_face_models.id", ondelete="RESTRICT")
    )
    self_state_version_id: Mapped[str] = mapped_column(
        ForeignKey("self_states.id", ondelete="RESTRICT")
    )
    candidate_generation_version: Mapped[str] = mapped_column(String(48), nullable=False)
    refinement_algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SelfTransferValidationResponse(IdMixin, Base):
    __tablename__ = "self_transfer_validation_responses"

    validation_run_id: Mapped[str] = mapped_column(
        ForeignKey("self_transfer_validation_runs.id", ondelete="CASCADE"), index=True
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_references: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    selected_candidate_reference: Mapped[str | None] = mapped_column(String(128))
    rejected_candidate_references: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    explicit_correction: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    transfer_confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("validation_run_id", "round_number"),
        CheckConstraint("round_number > 0", name="round_positive"),
        CheckConstraint(
            "transfer_confidence >= 0 AND transfer_confidence <= 1",
            name="confidence_range",
        ),
    )


class AestheticProfile(IdMixin, Base):
    __tablename__ = "aesthetic_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    learning_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AestheticProfileVersion(IdMixin, Base):
    __tablename__ = "aesthetic_profile_versions"

    profile_id: Mapped[str] = mapped_column(
        ForeignKey("aesthetic_profiles.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    self_state_version_id: Mapped[str] = mapped_column(
        ForeignKey("self_states.id", ondelete="RESTRICT"), index=True
    )
    desired_delta_profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("desired_delta_profile_versions.id", ondelete="RESTRICT"), index=True
    )
    style_profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("style_profile_versions.id", ondelete="RESTRICT"), index=True
    )
    identity_constraint_version_id: Mapped[str] = mapped_column(
        ForeignKey("identity_constraint_versions.id", ondelete="RESTRICT"), index=True
    )
    negative_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    context_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    profile_confidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    learning_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False)
    questionnaire_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("questionnaire_runs.id", ondelete="RESTRICT")
    )
    self_transfer_validation_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("self_transfer_validation_runs.id", ondelete="RESTRICT")
    )
    preference_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("preference_events.id", ondelete="RESTRICT")
    )
    profile_generation_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("profile_id", "version"),
        CheckConstraint("version > 0", name="positive_profile_version"),
    )


class ReferenceSet(IdMixin, Base):
    __tablename__ = "reference_sets"

    profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("aesthetic_profile_versions.id", ondelete="RESTRICT"), unique=True
    )
    front_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"))
    three_quarter_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT")
    )
    side_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PreferenceEvent(IdMixin, Base):
    __tablename__ = "preference_events"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(32), nullable=False)
    signal: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    user_initiated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (CheckConstraint("user_initiated IS TRUE", name="requires_user_signal"),)


class EditingSession(IdMixin, TimestampMixin, Base):
    __tablename__ = "editing_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"))
    profile_version_id: Mapped[str] = mapped_column(
        ForeignKey("aesthetic_profile_versions.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    session_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Message(IdMixin, Base):
    __tablename__ = "messages"

    editing_session_id: Mapped[str] = mapped_column(
        ForeignKey("editing_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ImageVersion(IdMixin, Base):
    __tablename__ = "image_versions"

    editing_session_id: Mapped[str] = mapped_column(
        ForeignKey("editing_sessions.id", ondelete="CASCADE"), index=True
    )
    parent_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("image_versions.id", ondelete="RESTRICT")
    )
    result_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), unique=True
    )
    provenance_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_content_provenance.id", ondelete="RESTRICT")
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("editing_session_id", "sequence"),
        CheckConstraint("sequence >= 0", name="nonnegative_sequence"),
        CheckConstraint(
            "(sequence = 0 AND parent_version_id IS NULL) OR "
            "(sequence > 0 AND parent_version_id IS NOT NULL)",
            name="valid_version_lineage",
        ),
    )


class EditOperation(IdMixin, Base):
    __tablename__ = "edit_operations"

    image_version_id: Mapped[str] = mapped_column(
        ForeignKey("image_versions.id", ondelete="CASCADE"), index=True
    )
    operation_index: Mapped[int] = mapped_column(Integer, nullable=False)
    engine: Mapped[str] = mapped_column(String(24), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    preserve: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    __table_args__ = (
        UniqueConstraint("image_version_id", "operation_index"),
        CheckConstraint("operation_index >= 0", name="nonnegative_operation_index"),
    )


class ModelRun(IdMixin, Base):
    __tablename__ = "model_runs"

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(48), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(48))
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(32))
    input_asset_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Job(IdMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class JobAttempt(IdMixin, Base):
    __tablename__ = "job_attempts"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("job_id", "attempt"),
        CheckConstraint("attempt > 0", name="positive_attempt"),
    )


class Plan(IdMixin, Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Subscription(IdMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)


class Entitlement(IdMixin, Base):
    __tablename__ = "entitlements"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    feature: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(32), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_entitlements_user_feature", "user_id", "feature"),)


class CreditAccount(IdMixin, Base):
    __tablename__ = "credit_accounts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    currency: Mapped[str] = mapped_column(String(16), default="mirror_credit", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class CreditLedger(IdMixin, Base):
    __tablename__ = "credit_ledger"

    account_id: Mapped[str] = mapped_column(
        ForeignKey("credit_accounts.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(48), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint("amount <> 0", name="nonzero_amount"),
        UniqueConstraint("reference_type", "reference_id", "reason"),
    )


class PaymentEvent(IdMixin, Base):
    __tablename__ = "payment_events"

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_logs"

    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(48), nullable=False)
    target_id: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class IdempotencyRecord(IdMixin, Base):
    __tablename__ = "idempotency_records"

    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    actor_key: Mapped[str] = mapped_column(String(96), nullable=False)
    scope: Mapped[str] = mapped_column(String(96), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_reference: Mapped[str | None] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (UniqueConstraint("actor_key", "scope", "key_hash"),)


class AIContentProvenance(IdMixin, Base):
    __tablename__ = "ai_content_provenance"

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_asset_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(48), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(48), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(48), nullable=False)
    content_marker_status: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_marker_status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    job_id: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


def _reject_immutable_change(mapper: object, connection: object, target: object) -> None:
    del mapper, connection, target
    raise ValueError("immutable record cannot be updated or deleted")


for immutable_model in (
    BaselineMeasurement,
    BaselineMorphologyDescriptor,
    QuestionTemplate,
    QuestionInstance,
    QuestionnaireRoute,
    QuestionResponse,
    DesiredDeltaProfileVersion,
    DesiredDeltaDimension,
    StyleProfileVersion,
    IdentityConstraintVersion,
    SelfTransferValidationResponse,
    AestheticProfileVersion,
    ConsentRecord,
    CreditLedger,
    AIContentProvenance,
):
    event.listen(immutable_model, "before_update", _reject_immutable_change)
    event.listen(immutable_model, "before_delete", _reject_immutable_change)


def _protect_versioned_state(
    mapper: object, connection: object, target: BaselineFaceModel | SelfState
) -> None:
    del mapper, connection
    state = cast(InstanceState[BaselineFaceModel | SelfState], inspect(target))
    if any(
        attribute.key != "superseded_at" and attribute.history.has_changes()
        for attribute in state.attrs
    ):
        raise ValueError("versioned state evidence is immutable")


for versioned_state_model in (BaselineFaceModel, SelfState):
    event.listen(versioned_state_model, "before_update", _protect_versioned_state)
    event.listen(versioned_state_model, "before_delete", _reject_immutable_change)


@event.listens_for(Asset, "before_update")
def _protect_original_blob(mapper: object, connection: object, target: Asset) -> None:
    del mapper, connection
    state = inspect(target)
    immutable_fields = ("storage_key", "sha256", "byte_size", "width", "height", "mime_type")
    if target.asset_role == "original" and any(
        state.attrs[field].history.has_changes() for field in immutable_fields
    ):
        raise ValueError("original asset blob metadata is immutable")
