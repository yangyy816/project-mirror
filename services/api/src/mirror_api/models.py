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
    ForeignKeyConstraint,
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

    phone_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
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

    phone_hash: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    invite_code_id: Mapped[str | None] = mapped_column(
        ForeignKey("invite_codes.id", ondelete="RESTRICT"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(48), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (CheckConstraint("attempts >= 0", name="nonnegative_challenge_attempts"),)


class UserSession(IdMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(32), nullable=False)
    token_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    refresh_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rotated_from_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_sessions.id", ondelete="RESTRICT"), unique=True
    )
    replaced_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_sessions.id", ondelete="RESTRICT"), unique=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(64))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        Index("ix_user_sessions_user_family", "user_id", "family_id"),
        CheckConstraint(
            "(rotated_from_id IS NULL OR rotated_from_id <> id) AND "
            "(replaced_by_id IS NULL OR replaced_by_id <> id)",
            name="valid_session_lineage",
        ),
    )


class InviteRedemption(IdMixin, Base):
    __tablename__ = "invite_redemptions"

    invite_code_id: Mapped[str] = mapped_column(
        ForeignKey("invite_codes.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    challenge_id: Mapped[str] = mapped_column(String(32), unique=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["challenge_id"],
            ["phone_verification_challenges.id"],
            name="fk_invite_redemption_challenge",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("user_id"),
    )


class AgeAssuranceRecord(IdMixin, Base):
    __tablename__ = "age_assurance_records"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_reference_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("provider", "provider_reference_hash"),
        CheckConstraint(
            "result IN ('verified','not_verified','indeterminate')",
            name="valid_age_assurance_result",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at >= verified_at",
            name="valid_age_assurance_expiry",
        ),
    )


class PolicyAcceptanceRecord(IdMixin, Base):
    __tablename__ = "policy_acceptance_records"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_code: Mapped[str] = mapped_column(String(64), nullable=False)
    document_version: Mapped[str] = mapped_column(String(64), nullable=False)
    document_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("user_id", "document_code", "document_version", "document_digest"),
    )


class ConsentRecord(IdMixin, Base):
    __tablename__ = "consent_records"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_type: Mapped[str] = mapped_column(String(48), nullable=False)
    purpose: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose_version: Mapped[str] = mapped_column(String(48), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    policy_code: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(48), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("consent_records.id", ondelete="RESTRICT")
    )
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="unique_consent_owner"),
        UniqueConstraint("supersedes_id", name="unique_consent_supersession"),
        CheckConstraint(
            "(action = 'grant' AND granted_at IS NOT NULL AND withdrawn_at IS NULL) OR "
            "(action = 'withdraw' AND granted_at IS NULL AND withdrawn_at IS NOT NULL "
            "AND supersedes_id IS NOT NULL)",
            name="valid_consent_event",
        ),
        CheckConstraint(
            "expires_at IS NULL OR (action = 'grant' AND expires_at >= granted_at)",
            name="valid_consent_expiry",
        ),
    )


class UploadIntent(IdMixin, TimestampMixin, Base):
    __tablename__ = "upload_intents"

    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    consent_record_id: Mapped[str] = mapped_column(String(32), index=True)
    object_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    declared_mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    declared_byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    declared_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="awaiting_upload", nullable=False)
    grant_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quarantine_retention_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["consent_record_id", "owner_user_id"],
            ["consent_records.id", "consent_records.user_id"],
            name="fk_upload_intents_consent_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "owner_user_id", name="unique_upload_intent_owner"),
        Index("ix_upload_intents_owner_status", "owner_user_id", "status"),
        CheckConstraint(
            "declared_byte_size > 0 AND declared_byte_size <= 20971520",
            name="valid_declared_byte_size",
        ),
        CheckConstraint(
            "declared_sha256 ~ '^[0-9a-f]{64}$'",
            name="valid_declared_sha256",
        ),
        CheckConstraint(
            "declared_mime_type IN ('image/jpeg','image/png','image/webp')",
            name="valid_declared_image_mime",
        ),
        CheckConstraint(
            "status IN ('awaiting_upload','uploaded_unverified','processing',"
            "'promoted','rejected','cancelled','expired')",
            name="valid_upload_intent_status",
        ),
        CheckConstraint(
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
            name="valid_upload_intent_timestamps",
        ),
        CheckConstraint(
            "quarantine_retention_deadline IS NULL OR "
            "(uploaded_at IS NOT NULL AND quarantine_retention_deadline > uploaded_at "
            "AND quarantine_retention_deadline <= uploaded_at + INTERVAL '24 hours')",
            name="valid_quarantine_retention_deadline",
        ),
        CheckConstraint(
            "uploaded_at IS NULL OR quarantine_retention_deadline IS NOT NULL",
            name="uploaded_requires_quarantine_retention",
        ),
        CheckConstraint(
            "grant_expires_at > created_at",
            name="valid_upload_grant_expiry",
        ),
    )


class UploadIntentEvent(IdMixin, Base):
    __tablename__ = "upload_intent_events"

    upload_intent_id: Mapped[str] = mapped_column(
        ForeignKey("upload_intents.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created','grant_issued','upload_completed','cancelled',"
            "'expired','processing_started','promoted','rejected')",
            name="valid_upload_intent_event_type",
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
    internal_purpose: Mapped[str | None] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("id", "owner_user_id", name="unique_asset_owner"),
        CheckConstraint(
            "asset_role IN ('original','derived','synthetic')", name="valid_asset_role"
        ),
        CheckConstraint(
            "(asset_role = 'synthetic' AND owner_user_id IS NULL "
            "AND internal_purpose = 'synthetic_dataset' AND synthetic) OR "
            "(asset_role IN ('original','derived') AND internal_purpose IS NULL)",
            name="valid_asset_internal_purpose_shape",
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


class AssetDeletionRequest(IdMixin, Base):
    __tablename__ = "asset_deletion_requests"

    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    asset_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    job_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="requested", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(
            ["asset_id", "owner_user_id"],
            ["assets.id", "assets.owner_user_id"],
            name="fk_asset_deletion_requests_asset_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["job_id", "owner_user_id"],
            ["jobs.id", "jobs.owner_user_id"],
            name="fk_asset_deletion_requests_job_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('requested','processing','completed','failed')",
            name="valid_asset_deletion_status",
        ),
        CheckConstraint(
            "(status = 'requested' AND started_at IS NULL AND completed_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status = 'processing' AND started_at IS NOT NULL AND completed_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status IN ('completed','failed') AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL AND result_code IS NOT NULL)",
            name="valid_asset_deletion_shape",
        ),
    )


class AssetDeletionEvent(IdMixin, Base):
    __tablename__ = "asset_deletion_events"

    request_id: Mapped[str] = mapped_column(
        ForeignKey("asset_deletion_requests.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    result_code: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('requested','processing_started','completed','failed')",
            name="valid_asset_deletion_event_type",
        ),
    )


class DataExportRequest(IdMixin, Base):
    __tablename__ = "data_export_requests"

    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="requested", nullable=False)
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    sha256: Mapped[str | None] = mapped_column(String(64))
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "owner_user_id"],
            ["jobs.id", "jobs.owner_user_id"],
            name="fk_data_export_requests_job_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('requested','processing','ready','failed','expired')",
            name="valid_data_export_status",
        ),
        CheckConstraint(
            "byte_size IS NULL OR byte_size > 0", name="positive_data_export_byte_size"
        ),
        CheckConstraint(
            "(status NOT IN ('ready','expired')) OR "
            "(storage_key IS NOT NULL AND sha256 IS NOT NULL AND byte_size IS NOT NULL "
            "AND ready_at IS NOT NULL AND expires_at > ready_at)",
            name="ready_data_export_has_artifact",
        ),
        CheckConstraint(
            "status <> 'expired' OR (deleted_at IS NOT NULL AND result_code IS NOT NULL)",
            name="expired_data_export_has_evidence",
        ),
    )


class DataExportEvent(IdMixin, Base):
    __tablename__ = "data_export_events"

    request_id: Mapped[str] = mapped_column(
        ForeignKey("data_export_requests.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    result_code: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('requested','processing_started','ready','failed','expired')",
            name="valid_data_export_event_type",
        ),
    )


class AccountDeletionRequest(IdMixin, Base):
    __tablename__ = "account_deletion_requests"

    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="requested", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "owner_user_id"],
            ["jobs.id", "jobs.owner_user_id"],
            name="fk_account_deletion_requests_job_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('requested','processing','completed','failed')",
            name="valid_account_deletion_status",
        ),
        CheckConstraint(
            "(status = 'requested' AND started_at IS NULL AND completed_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status = 'processing' AND started_at IS NOT NULL AND completed_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status IN ('completed','failed') AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL AND result_code IS NOT NULL)",
            name="valid_account_deletion_shape",
        ),
    )


class AccountDeletionEvent(IdMixin, Base):
    __tablename__ = "account_deletion_events"

    request_id: Mapped[str] = mapped_column(
        ForeignKey("account_deletion_requests.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    result_code: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('requested','processing_started','completed','failed')",
            name="valid_account_deletion_event_type",
        ),
    )


class ObjectDeletionEvidence(IdMixin, Base):
    __tablename__ = "object_deletion_evidence"

    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    asset_deletion_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("asset_deletion_requests.id", ondelete="RESTRICT")
    )
    data_export_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("data_export_requests.id", ondelete="RESTRICT")
    )
    account_deletion_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("account_deletion_requests.id", ondelete="RESTRICT"), index=True
    )
    target_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    target_data_export_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("data_export_requests.id", ondelete="RESTRICT"), index=True
    )
    target_upload_intent_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "upload_intents.id",
            name="fk_object_deletion_evidence_target_upload_intent",
            ondelete="RESTRICT",
        ),
        index=True,
    )
    object_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    result_code: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(asset_deletion_request_id, data_export_request_id, "
            "account_deletion_request_id) = 1",
            name="one_object_deletion_authority",
        ),
        CheckConstraint(
            "(object_kind = 'asset' AND target_asset_id IS NOT NULL "
            "AND target_data_export_request_id IS NULL AND target_upload_intent_id IS NULL) OR "
            "(object_kind = 'data_export' AND target_asset_id IS NULL "
            "AND target_data_export_request_id IS NOT NULL "
            "AND target_upload_intent_id IS NULL) OR "
            "(object_kind = 'quarantine' AND target_asset_id IS NULL "
            "AND target_data_export_request_id IS NULL "
            "AND target_upload_intent_id IS NOT NULL)",
            name="one_object_deletion_target",
        ),
        UniqueConstraint(
            "asset_deletion_request_id",
            "target_asset_id",
            name="unique_asset_deletion_target_evidence",
        ),
        UniqueConstraint(
            "data_export_request_id",
            "target_data_export_request_id",
            name="unique_export_deletion_target_evidence",
        ),
        UniqueConstraint(
            "account_deletion_request_id",
            "target_asset_id",
            name="unique_account_asset_deletion_evidence",
        ),
        UniqueConstraint(
            "account_deletion_request_id",
            "target_data_export_request_id",
            name="unique_account_export_deletion_evidence",
        ),
        UniqueConstraint(
            "account_deletion_request_id",
            "target_upload_intent_id",
            name="unique_account_quarantine_deletion_evidence",
        ),
        CheckConstraint(
            "object_kind IN ('asset','data_export','quarantine')",
            name="valid_deleted_object_kind",
        ),
        CheckConstraint("outcome IN ('deleted','not_found')", name="valid_object_deletion_outcome"),
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


class SyntheticGenerationPolicy(IdMixin, TimestampMixin, Base):
    __tablename__ = "synthetic_generation_policies"

    schema_version: Mapped[str] = mapped_column(
        String(128), default="mirror.synthetic-dataset/SyntheticGenerationPolicy/v1", nullable=False
    )
    version: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(24), default="DRAFT", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "approval_status IN ('DRAFT','APPROVED')",
            name="approval_status",
        ),
        CheckConstraint(
            "(approval_status = 'DRAFT' AND approved_at IS NULL) OR "
            "(approval_status = 'APPROVED' AND approved_at IS NOT NULL)",
            name="approval_shape",
        ),
        CheckConstraint(
            "version ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'",
            name="canonical_version",
        ),
        CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="canonical_digest"),
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticGenerationPolicy/v1'",
            name="schema_version",
        ),
        CheckConstraint("json_typeof(content) = 'object'", name="content_object"),
    )


class SyntheticPromptTemplate(IdMixin, TimestampMixin, Base):
    __tablename__ = "synthetic_prompt_templates"

    schema_version: Mapped[str] = mapped_column(
        String(128), default="mirror.synthetic-dataset/SyntheticPromptTemplate/v1", nullable=False
    )
    version: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(24), default="DRAFT", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("approval_status IN ('DRAFT','APPROVED')", name="approval_status"),
        CheckConstraint(
            "(approval_status = 'DRAFT' AND approved_at IS NULL) OR "
            "(approval_status = 'APPROVED' AND approved_at IS NOT NULL)",
            name="approval_shape",
        ),
        CheckConstraint(
            "version ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'",
            name="canonical_version",
        ),
        CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="canonical_digest"),
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticPromptTemplate/v1'",
            name="schema_version",
        ),
        CheckConstraint("json_typeof(content) = 'object'", name="content_object"),
    )


class SyntheticQAPolicy(IdMixin, TimestampMixin, Base):
    __tablename__ = "synthetic_qa_policies"

    schema_version: Mapped[str] = mapped_column(
        String(128), default="mirror.synthetic-dataset/SyntheticQAPolicy/v1", nullable=False
    )
    version: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(24), default="DRAFT", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("approval_status IN ('DRAFT','APPROVED')", name="approval_status"),
        CheckConstraint(
            "(approval_status = 'DRAFT' AND approved_at IS NULL) OR "
            "(approval_status = 'APPROVED' AND approved_at IS NOT NULL)",
            name="approval_shape",
        ),
        CheckConstraint(
            "version ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'",
            name="canonical_version",
        ),
        CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="canonical_digest"),
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticQAPolicy/v1'",
            name="schema_version",
        ),
        CheckConstraint("json_typeof(content) = 'object'", name="content_object"),
    )


class GeometryOntologyVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "geometry_ontology_versions"

    schema_version: Mapped[str] = mapped_column(
        String(128), default="mirror.synthetic-dataset/GeometryOntologyVersion/v1", nullable=False
    )
    version: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(24), default="DRAFT", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("approval_status IN ('DRAFT','APPROVED')", name="approval_status"),
        CheckConstraint(
            "(approval_status = 'DRAFT' AND approved_at IS NULL) OR "
            "(approval_status = 'APPROVED' AND approved_at IS NOT NULL)",
            name="approval_shape",
        ),
        CheckConstraint(
            "version ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-v[1-9][0-9]*$'",
            name="canonical_version",
        ),
        CheckConstraint("content_digest ~ '^[0-9a-f]{64}$'", name="canonical_digest"),
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/GeometryOntologyVersion/v1'",
            name="schema_version",
        ),
        CheckConstraint("json_typeof(content) = 'object'", name="content_object"),
    )


class GenerationBatch(IdMixin, TimestampMixin, Base):
    __tablename__ = "generation_batches"

    schema_version: Mapped[str] = mapped_column(
        String(96), default="mirror.synthetic-dataset/GenerationBatch/v1", nullable=False
    )
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    generation_policy_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_generation_policies.id", ondelete="RESTRICT"), index=True
    )
    prompt_template_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_prompt_templates.id", ondelete="RESTRICT"), index=True
    )
    provider_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    model_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    pricing_snapshot_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    output_media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    output_width: Mapped[int] = mapped_column(Integer, nullable=False)
    output_height: Mapped[int] = mapped_column(Integer, nullable=False)
    output_max_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    hard_budget_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    per_item_ceiling_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    retry_ceiling: Mapped[int] = mapped_column(Integer, nullable=False)
    concurrency_ceiling: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", nullable=False)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/GenerationBatch/v1'",
            name="schema_version",
        ),
        CheckConstraint("idempotency_key_hash ~ '^[0-9a-f]{64}$'", name="idempotency_digest"),
        CheckConstraint(
            "output_media_type IN ('image/jpeg','image/png','image/webp')",
            name="output_media_type",
        ),
        CheckConstraint(
            "output_width > 0 AND output_height > 0 AND output_max_bytes > 0",
            name="positive_output_bounds",
        ),
        CheckConstraint("item_count > 0 AND item_count <= 10000", name="item_count"),
        CheckConstraint("currency IN ('CNY','USD')", name="currency"),
        CheckConstraint(
            "hard_budget_micros >= 0 AND per_item_ceiling_micros >= 0 "
            "AND per_item_ceiling_micros * item_count <= hard_budget_micros",
            name="budget_shape",
        ),
        CheckConstraint("retry_ceiling >= 0 AND retry_ceiling <= 20", name="retry_ceiling"),
        CheckConstraint(
            "concurrency_ceiling > 0 AND concurrency_ceiling <= item_count",
            name="concurrency_ceiling",
        ),
        CheckConstraint(
            "status IN ('DRAFT','QUEUED','RUNNING','COMPLETED','PARTIAL','FAILED','CANCELLED')",
            name="status",
        ),
        CheckConstraint(
            "(status = 'DRAFT' AND queued_at IS NULL AND started_at IS NULL "
            "AND finalized_at IS NULL) OR "
            "(status = 'QUEUED' AND queued_at IS NOT NULL AND started_at IS NULL "
            "AND finalized_at IS NULL) OR "
            "(status = 'RUNNING' AND queued_at IS NOT NULL AND started_at IS NOT NULL "
            "AND finalized_at IS NULL) OR "
            "(status IN ('COMPLETED','PARTIAL','FAILED','CANCELLED') "
            "AND queued_at IS NOT NULL AND finalized_at IS NOT NULL)",
            name="status_timestamps",
        ),
        CheckConstraint(
            "(queued_at IS NULL OR queued_at >= created_at) AND "
            "(started_at IS NULL OR (queued_at IS NOT NULL AND started_at >= queued_at)) AND "
            "(finalized_at IS NULL OR finalized_at >= COALESCE(started_at, queued_at)) AND "
            "(cancel_requested_at IS NULL OR cancel_requested_at >= created_at)",
            name="timestamp_order",
        ),
    )


class GenerationItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "generation_items"

    schema_version: Mapped[str] = mapped_column(
        String(96), default="mirror.synthetic-dataset/GenerationItem/v1", nullable=False
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("generation_batches.id", ondelete="RESTRICT"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    request_reference: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    requested_seed: Mapped[int | None] = mapped_column(BigInteger)
    reserved_budget_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="REQUESTED", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint("batch_id", "ordinal", name="unique_batch_ordinal"),
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/GenerationItem/v1'",
            name="schema_version",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal"),
        CheckConstraint(
            "requested_seed IS NULL OR requested_seed BETWEEN 0 AND 9223372036854775807",
            name="requested_seed",
        ),
        CheckConstraint("reserved_budget_micros >= 0", name="reserved_budget"),
        CheckConstraint(
            "status IN ('REQUESTED','GENERATING','RAW_STORED','GENERATION_FAILED','CANCELLED')",
            name="status",
        ),
        CheckConstraint(
            "(status = 'REQUESTED' AND started_at IS NULL AND finalized_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status = 'GENERATING' AND started_at IS NOT NULL AND finalized_at IS NULL "
            "AND result_code IS NULL) OR "
            "(status IN ('RAW_STORED','GENERATION_FAILED','CANCELLED') "
            "AND finalized_at IS NOT NULL AND result_code IS NOT NULL)",
            name="status_shape",
        ),
        CheckConstraint(
            "result_code IS NULL OR result_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name="result_code",
        ),
        CheckConstraint(
            "(started_at IS NULL OR started_at >= created_at) AND "
            "(finalized_at IS NULL OR finalized_at >= COALESCE(started_at, created_at))",
            name="timestamp_order",
        ),
    )


class SyntheticSourceObject(IdMixin, Base):
    __tablename__ = "synthetic_source_objects"

    schema_version: Mapped[str] = mapped_column(
        String(96), default="mirror.synthetic-dataset/SyntheticSourceObject/v1", nullable=False
    )
    generation_item_id: Mapped[str] = mapped_column(
        ForeignKey("generation_items.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    job_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("job_attempts.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    storage_reference: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticSourceObject/v1'",
            name="schema_version",
        ),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        CheckConstraint("media_type IN ('image/jpeg','image/png','image/webp')", name="media_type"),
        CheckConstraint("byte_size > 0 AND width > 0 AND height > 0", name="positive_metadata"),
        CheckConstraint(
            "storage_reference ~ '^[a-z0-9][a-z0-9._:-]{2,127}$'",
            name="storage_reference",
        ),
        CheckConstraint("retention_expires_at > created_at", name="retention"),
    )


class SyntheticGenerationEvidence(IdMixin, Base):
    __tablename__ = "synthetic_generation_evidence"

    schema_version: Mapped[str] = mapped_column(
        String(96),
        default="mirror.synthetic-dataset/SyntheticGenerationEvidence/v1",
        nullable=False,
    )
    generation_item_id: Mapped[str] = mapped_column(
        ForeignKey("generation_items.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    job_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("job_attempts.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    provider_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    model_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_run_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    safety_policy_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    safety_outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    safety_reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    retention_status: Mapped[str] = mapped_column(String(32), nullable=False)
    output_rights: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_actual_seed: Mapped[int | None] = mapped_column(BigInteger)
    provider_actual_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reproducibility_level: Mapped[str] = mapped_column(String(24), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticGenerationEvidence/v1'",
            name="schema_version",
        ),
        CheckConstraint("safety_outcome IN ('passed','rejected')", name="safety_outcome"),
        CheckConstraint(
            "safety_reason_code ~ '^[a-z][a-z0-9_]{2,63}$'",
            name="safety_reason_code",
        ),
        CheckConstraint(
            "retention_status IN ('not_retained','contractually_bounded')",
            name="retention_status",
        ),
        CheckConstraint(
            "output_rights IN ('internal_evaluation_only','synthetic_release_permitted')",
            name="output_rights",
        ),
        CheckConstraint(
            "provider_actual_seed IS NULL OR "
            "provider_actual_seed BETWEEN 0 AND 9223372036854775807",
            name="provider_seed",
        ),
        CheckConstraint(
            "json_typeof(provider_actual_parameters) = 'object'", name="parameters_object"
        ),
        CheckConstraint(
            "reproducibility_level IN ('BIT_EXACT','SEED_REPLAYABLE','PROVENANCE_ONLY')",
            name="reproducibility",
        ),
    )


class ProviderCostEvent(IdMixin, Base):
    __tablename__ = "provider_cost_events"

    schema_version: Mapped[str] = mapped_column(
        String(96), default="mirror.synthetic-dataset/ProviderCostEvent/v1", nullable=False
    )
    generation_item_id: Mapped[str] = mapped_column(
        ForeignKey("generation_items.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    job_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("job_attempts.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    event_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pricing_snapshot_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("job_attempt_id", name="unique_attempt_cost"),
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/ProviderCostEvent/v1'",
            name="schema_version",
        ),
        CheckConstraint("event_kind IN ('estimated','final')", name="event_kind"),
        CheckConstraint("currency IN ('CNY','USD')", name="currency"),
        CheckConstraint("amount_micros >= 0", name="amount"),
    )


class SyntheticSourceObjectDeletionEvidence(IdMixin, Base):
    __tablename__ = "synthetic_source_object_deletion_evidence"

    schema_version: Mapped[str] = mapped_column(
        String(112),
        default="mirror.synthetic-dataset/SyntheticSourceObjectDeletionEvidence/v1",
        nullable=False,
    )
    source_object_id: Mapped[str] = mapped_column(
        ForeignKey("synthetic_source_objects.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    deletion_result: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_reference: Mapped[str | None] = mapped_column(String(128))
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "schema_version = 'mirror.synthetic-dataset/SyntheticSourceObjectDeletionEvidence/v1'",
            name="schema_version",
        ),
        CheckConstraint("reason_code ~ '^[a-z][a-z0-9_]{2,63}$'", name="reason_code"),
        CheckConstraint("deletion_result IN ('deleted','not_found')", name="deletion_result"),
        CheckConstraint("actor_kind IN ('system','operator')", name="actor_kind"),
        CheckConstraint(
            "(actor_kind = 'system' AND actor_reference IS NULL) OR "
            "(actor_kind = 'operator' AND actor_reference IS NOT NULL)",
            name="actor_shape",
        ),
    )


class SyntheticIdentity(IdMixin, Base):
    __tablename__ = "synthetic_identities"

    bank_version_id: Mapped[str | None] = mapped_column(
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
    __table_args__ = (CheckConstraint("bank_version_id IS NULL", name="bank_independent"),)


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
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    ingestion_upload_intent_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lease_token: Mapped[str | None] = mapped_column(String(64))
    lease_acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_asset_id: Mapped[str | None] = mapped_column(String(32))
    result_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(
            ["ingestion_upload_intent_id", "owner_user_id"],
            ["upload_intents.id", "upload_intents.owner_user_id"],
            name="fk_jobs_ingestion_intent_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["result_asset_id", "owner_user_id"],
            ["assets.id", "assets.owner_user_id"],
            name="fk_jobs_result_asset_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "owner_user_id", name="unique_job_owner"),
        CheckConstraint("attempt_count >= 0", name="nonnegative_job_attempt_count"),
        CheckConstraint(
            "ingestion_upload_intent_id IS NULL OR job_type = 'asset_ingestion'",
            name="ingestion_job_type",
        ),
        CheckConstraint(
            "job_type <> 'asset_ingestion' OR "
            "(owner_user_id IS NOT NULL AND ingestion_upload_intent_id IS NOT NULL)",
            name="ingestion_job_owner_intent",
        ),
        CheckConstraint(
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
            "AND result_code IS NOT NULL) OR "
            "(status = 'cancelled' AND attempt_count = 0 AND lease_token IS NULL "
            "AND lease_acquired_at IS NULL AND lease_expires_at IS NULL "
            "AND finalized_at IS NOT NULL AND result_asset_id IS NULL "
            "AND result_code IS NOT NULL))",
            name="valid_ingestion_job_lifecycle",
        ),
        CheckConstraint(
            "job_type <> 'synthetic_generation' OR "
            "(owner_user_id IS NULL AND ingestion_upload_intent_id IS NULL "
            "AND result_asset_id IS NULL AND payload::jsonb = '{}'::jsonb)",
            name="synthetic_generation_envelope",
        ),
    )


class JobAttempt(IdMixin, Base):
    __tablename__ = "job_attempts"

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    lease_token: Mapped[str | None] = mapped_column(String(64))
    result_code: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("job_id", "attempt"),
        CheckConstraint("attempt > 0", name="positive_attempt"),
    )


class AssetIngestionRecord(IdMixin, Base):
    __tablename__ = "asset_ingestion_records"

    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    upload_intent_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    job_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    result_asset_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    result_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sanitizer_version: Mapped[str | None] = mapped_column(String(64))
    finalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["upload_intent_id", "owner_user_id"],
            ["upload_intents.id", "upload_intents.owner_user_id"],
            name="fk_ingestion_records_intent_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["job_id", "owner_user_id"],
            ["jobs.id", "jobs.owner_user_id"],
            name="fk_ingestion_records_job_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["result_asset_id", "owner_user_id"],
            ["assets.id", "assets.owner_user_id"],
            name="fk_ingestion_records_asset_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint("outcome IN ('promoted','rejected')", name="valid_ingestion_outcome"),
        CheckConstraint(
            "(outcome = 'promoted' AND result_asset_id IS NOT NULL "
            "AND sanitizer_version IS NOT NULL) OR "
            "(outcome = 'rejected' AND result_asset_id IS NULL "
            "AND sanitizer_version IS NULL)",
            name="valid_ingestion_result_shape",
        ),
        CheckConstraint("result_code ~ '^[a-z][a-z0-9_]{2,63}$'", name="valid_ingestion_code"),
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
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_reference: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(24), default="in_progress", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("actor_key", "scope", "key_hash"),
        CheckConstraint(
            "state IN ('in_progress','completed','failed') AND "
            "((state = 'completed' AND completed_at IS NOT NULL) OR "
            "(state <> 'completed' AND completed_at IS NULL))",
            name="valid_idempotency_state",
        ),
    )


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
    UploadIntentEvent,
    AssetIngestionRecord,
    InviteRedemption,
    AgeAssuranceRecord,
    PolicyAcceptanceRecord,
    CreditLedger,
    AIContentProvenance,
    SyntheticSourceObject,
    SyntheticGenerationEvidence,
    ProviderCostEvent,
    SyntheticSourceObjectDeletionEvidence,
):
    event.listen(immutable_model, "before_update", _reject_immutable_change)
    event.listen(immutable_model, "before_delete", _reject_immutable_change)


def _protect_generation_batch(mapper: object, connection: object, target: GenerationBatch) -> None:
    del mapper, connection
    state = inspect(target)
    mutable_fields = {
        "updated_at",
        "status",
        "cancel_requested_at",
        "queued_at",
        "started_at",
        "finalized_at",
    }
    if any(
        attribute.key not in mutable_fields and attribute.history.has_changes()
        for attribute in state.attrs
    ):
        raise ValueError("generation batch configuration is immutable")


def _protect_generation_item(mapper: object, connection: object, target: GenerationItem) -> None:
    del mapper, connection
    state = inspect(target)
    mutable_fields = {"updated_at", "status", "started_at", "finalized_at", "result_code"}
    if any(
        attribute.key not in mutable_fields and attribute.history.has_changes()
        for attribute in state.attrs
    ):
        raise ValueError("generation item authority is immutable")


event.listen(GenerationBatch, "before_update", _protect_generation_batch)
event.listen(GenerationBatch, "before_delete", _reject_immutable_change)
event.listen(GenerationItem, "before_update", _protect_generation_item)
event.listen(GenerationItem, "before_delete", _reject_immutable_change)


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
def _protect_internal_blob(mapper: object, connection: object, target: Asset) -> None:
    del mapper, connection
    state = inspect(target)
    old_role_values = state.attrs["asset_role"].history.deleted
    old_role = old_role_values[0] if old_role_values else target.asset_role
    if old_role != target.asset_role and "synthetic" in (old_role, target.asset_role):
        raise ValueError("synthetic asset role is immutable")
    immutable_fields: tuple[str, ...] = (
        "storage_key",
        "sha256",
        "byte_size",
        "width",
        "height",
        "mime_type",
        "is_ai_generated",
        "is_ai_modified",
    )
    if old_role == "synthetic" or target.asset_role == "synthetic":
        immutable_fields += ("owner_user_id", "internal_purpose", "synthetic", "asset_role")
    if target.asset_role in ("original", "synthetic") or old_role == "synthetic":
        if any(state.attrs[field].history.has_changes() for field in immutable_fields):
            raise ValueError(f"{old_role} asset blob metadata is immutable")


def _validate_synthetic_authority_insert(mapper: object, connection: object, target: Any) -> None:
    del mapper, connection
    if target.approval_status not in (None, "DRAFT") or target.approved_at is not None:
        raise ValueError("synthetic authority records must be inserted as DRAFT")


def _protect_synthetic_authority_record(mapper: object, connection: object, target: Any) -> None:
    del mapper, connection
    state = inspect(target)
    assert state is not None
    if any(
        state.attrs[field].history.has_changes()
        for field in ("schema_version", "version", "content", "content_digest")
    ):
        raise ValueError("synthetic authority content is immutable")
    if any(state.attrs[field].history.has_changes() for field in ("id", "created_at")):
        raise ValueError("synthetic authority record identity is immutable")
    old_status = state.attrs["approval_status"].history.deleted
    if old_status and old_status[0] == "APPROVED":
        raise ValueError("synthetic authority approval is immutable once approved")
    new_status = state.attrs["approval_status"].history.added
    if (
        not old_status
        or not new_status
        or new_status[0] != "APPROVED"
        or target.approved_at is None
    ):
        raise ValueError("synthetic authority approval must transition to approved")


for synthetic_authority_model in (
    SyntheticGenerationPolicy,
    SyntheticPromptTemplate,
    SyntheticQAPolicy,
    GeometryOntologyVersion,
):
    event.listen(synthetic_authority_model, "before_insert", _validate_synthetic_authority_insert)
    event.listen(synthetic_authority_model, "before_update", _protect_synthetic_authority_record)
    event.listen(synthetic_authority_model, "before_delete", _reject_immutable_change)


def _validate_synthetic_identity_bank_independence(
    mapper: object, connection: object, target: SyntheticIdentity
) -> None:
    del mapper, connection
    if target.bank_version_id is not None:
        raise ValueError("synthetic identities must be bank-independent")


event.listen(SyntheticIdentity, "before_insert", _validate_synthetic_identity_bank_independence)
event.listen(SyntheticIdentity, "before_update", _validate_synthetic_identity_bank_independence)
