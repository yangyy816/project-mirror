from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from mirror_api.db import Base
from mirror_api.models import new_id, utcnow

D02_LOCAL_QA_DIGEST_SEPARATION_CHECK_SQL = """
schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3'
OR source_authority_kind <> 'DEMO_LOCAL_IMPORTED_COPY'
OR (
    source_qa_snapshot_digest IS NOT NULL
    AND jsonb_typeof(source_fact_snapshot) IS NOT DISTINCT FROM 'object'
    AND (source_fact_snapshot ->> 'source_qa_snapshot_digest')
        IS NOT DISTINCT FROM source_qa_snapshot_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM formal_canonical_asset_sha256
    AND source_qa_snapshot_digest IS DISTINCT FROM source_receipt_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_authority_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_landmark_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_measurement_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_provenance_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_fact_snapshot_digest
    AND source_qa_snapshot_digest IS DISTINCT FROM source_measurement_projection_digest
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_asset_sha256')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_receipt_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_authority_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'qa_policy_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_landmark_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_provenance_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_projection_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'raw_measurement_authority_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_measurement_observation_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (source_fact_snapshot ->> 'source_repeat_certification_digest')
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'source_p2_candidate_manifest_content_digest'
        )
    AND source_qa_snapshot_digest
        IS DISTINCT FROM (
            source_fact_snapshot ->> 'dimension_authority_manifest_content_digest'
        )
)
"""


def _authority_constraints(
    table_name: str,
    *,
    schema_version_expression: str = "schema_version ~ '^mirror[.]demo/[A-Za-z0-9]+/v1$'",
) -> tuple[CheckConstraint | UniqueConstraint, ...]:
    return (
        CheckConstraint("id ~ '^[0-9a-f]{32}$'", name="id_shape"),
        CheckConstraint(
            schema_version_expression,
            name="schema_version_shape",
        ),
        CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'",
            name="canonical_payload_object",
        ),
        CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name="content_digest_shape",
        ),
        UniqueConstraint(
            "content_digest",
            name=f"uq_{table_name}_content_digest",
        ),
    )


class DemoAuthorityMixin:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    schema_version: Mapped[str] = mapped_column(String(112), nullable=False)
    canonical_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class DemoActor(DemoAuthorityMixin, Base):
    __tablename__ = "demo_actors"

    actor_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    credential_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    authority_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tombstoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        *_authority_constraints(__tablename__),
        UniqueConstraint(
            "credential_key_id",
            name="uq_demo_actors_credential_key_id",
        ),
        UniqueConstraint(
            "id",
            "actor_kind",
            name="uq_demo_actors_id_actor_kind",
        ),
        CheckConstraint(
            "actor_kind IN ('LOCAL_SINGLE_USER','AUTOMATED_TEST')",
            name="actor_kind",
        ),
        CheckConstraint(
            "tombstoned_at IS NULL OR tombstoned_at >= created_at",
            name="tombstone_not_before_creation",
        ),
    )


class DemoSession(DemoAuthorityMixin, Base):
    __tablename__ = "demo_sessions"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    context_seed: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tombstoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        *_authority_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            name="uq_demo_sessions_id_actor",
        ),
        CheckConstraint(
            "context_seed ~ '^[0-9a-f]{64}$'",
            name="context_seed_shape",
        ),
        CheckConstraint(
            "jsonb_typeof(config) = 'object'",
            name="config_object",
        ),
        CheckConstraint(
            "closed_at IS NULL OR closed_at >= created_at",
            name="close_not_before_creation",
        ),
        CheckConstraint(
            "tombstoned_at IS NULL OR (closed_at IS NOT NULL AND tombstoned_at >= closed_at)",
            name="tombstone_order",
        ),
    )


class DemoD02R2SourceAuthority(DemoAuthorityMixin, Base):
    """Public structural projection of one private D02-R2 source authority."""

    __tablename__ = "demo_d02_r2_source_authorities"

    execution_contract_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_root_id: Mapped[str] = mapped_column(String(128), nullable=False)
    root_name_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_preregistration_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_allocation_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_producer_dispatch_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source_output_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    source_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_asset_byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_asset_mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_asset_width: Mapped[int] = mapped_column(Integer, nullable=False)
    source_asset_height: Mapped[int] = mapped_column(Integer, nullable=False)
    source_generation_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    output_name_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    output_seal_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    registry_commit_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_capability_authority_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_request_policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_request_digest: Mapped[str | None] = mapped_column(String(64))
    execution_epoch: Mapped[str | None] = mapped_column(String(64))
    producer_task_id: Mapped[str | None] = mapped_column(String(128))
    dispatch_epoch: Mapped[int | None] = mapped_column(SmallInteger)
    generation_source_asset_sha256: Mapped[str | None] = mapped_column(String(64))
    generation_source_asset_byte_size: Mapped[int | None] = mapped_column(BigInteger)
    generation_source_asset_mime_type: Mapped[str | None] = mapped_column(String(64))
    generation_source_asset_width: Mapped[int | None] = mapped_column(Integer)
    generation_source_asset_height: Mapped[int | None] = mapped_column(Integer)
    source_normalization_receipt_digest: Mapped[str | None] = mapped_column(String(64))
    source_provenance_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_provenance_output_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_provenance_name_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_provenance_seal_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_provenance_registry_commit_receipt_digest: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    source_authority_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_authority_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_qa_snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    adult_synthetic_attested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    synthetic_only_attested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    real_person_reference_used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    authority_state: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        *_authority_constraints(
            __tablename__,
            schema_version_expression=(
                "schema_version IN ('mirror.demo/D02R2SourceAuthorityRecord/v1',"
                "'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1')"
            ),
        ),
        UniqueConstraint("execution_contract_digest", "source_ordinal", name="execution_ordinal"),
        UniqueConstraint("source_output_id", name="source_output_id"),
        UniqueConstraint("source_generation_receipt_digest", name="source_generation_receipt"),
        UniqueConstraint("output_name_receipt_digest", name="output_name_receipt"),
        UniqueConstraint("output_seal_receipt_digest", name="output_seal_receipt"),
        UniqueConstraint("registry_commit_receipt_digest", name="registry_commit_receipt"),
        UniqueConstraint("source_provenance_output_id", name="source_provenance_output_id"),
        UniqueConstraint("source_provenance_name_receipt_digest", name="source_provenance_name"),
        UniqueConstraint("source_provenance_seal_receipt_digest", name="source_provenance_seal"),
        UniqueConstraint(
            "source_provenance_registry_commit_receipt_digest", name="source_provenance_commit"
        ),
        UniqueConstraint("source_authority_digest", name="source_authority_digest"),
        UniqueConstraint("source_authority_key", name="source_authority_key"),
        UniqueConstraint("source_qa_snapshot_digest", name="source_qa_snapshot_digest"),
        UniqueConstraint("generation_request_digest", name="generation_request_digest"),
        UniqueConstraint(
            "source_normalization_receipt_digest", name="source_normalization_receipt_digest"
        ),
        CheckConstraint("source_ordinal BETWEEN 1 AND 4", name="source_ordinal"),
        CheckConstraint("source_asset_byte_size > 0", name="positive_asset_byte_size"),
        CheckConstraint(
            "source_asset_width > 0 AND source_asset_height > 0", name="positive_dimensions"
        ),
        CheckConstraint(
            "source_asset_mime_type = 'image/jpeg'",
            name="decoded_mime",
        ),
        CheckConstraint(
            "adult_synthetic_attested IS TRUE AND synthetic_only_attested IS TRUE "
            "AND real_person_reference_used IS FALSE",
            name="fixed_attestations",
        ),
        CheckConstraint("authority_state = 'PRINCIPAL_ACCEPTED'", name="authority_state"),
        CheckConstraint(
            "(schema_version = 'mirror.demo/D02R2SourceAuthorityRecord/v1' "
            "AND evidence_root_id = 'P3_P7_D02_R2_CC08_E1_EVIDENCE_ROOT' "
            "AND generation_request_digest IS NULL AND execution_epoch IS NULL "
            "AND producer_task_id IS NULL AND dispatch_epoch IS NULL "
            "AND generation_source_asset_sha256 IS NULL "
            "AND generation_source_asset_byte_size IS NULL "
            "AND generation_source_asset_mime_type IS NULL "
            "AND generation_source_asset_width IS NULL "
            "AND generation_source_asset_height IS NULL "
            "AND source_normalization_receipt_digest IS NULL) OR "
            "(schema_version = 'mirror.demo/D02R2Epoch2SourceAuthorityRecord/v1' "
            "AND evidence_root_id = 'P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT' "
            "AND generation_request_digest = generation_request_policy_digest "
            "AND execution_epoch = 'D02_R2_EPOCH_02' "
            "AND producer_task_id = 'P3_P7_D02_R2_SOURCE_COHORT_02' "
            "AND dispatch_epoch = 2 "
            "AND generation_source_asset_sha256 ~ '^[0-9a-f]{64}$' "
            "AND generation_source_asset_byte_size > 0 "
            "AND generation_source_asset_mime_type = 'image/png' "
            "AND generation_source_asset_width > 0 "
            "AND generation_source_asset_height > 0 "
            "AND source_normalization_receipt_digest ~ '^[0-9a-f]{64}$')",
            name="evidence_root",
        ),
        CheckConstraint(
            "source_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$' "
            "AND source_provenance_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'",
            name="opaque_output_ids",
        ),
        CheckConstraint(
            "source_asset_sha256 ~ '^[0-9a-f]{64}$' AND source_authority_key ~ '^[0-9a-f]{64}$' "
            "AND execution_contract_digest ~ '^[0-9a-f]{64}$' "
            "AND root_name_receipt_digest ~ '^[0-9a-f]{64}$' "
            "AND generation_preregistration_digest ~ '^[0-9a-f]{64}$' "
            "AND source_allocation_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND source_producer_dispatch_digest ~ '^[0-9a-f]{64}$' "
            "AND source_generation_receipt_digest ~ '^[0-9a-f]{64}$' "
            "AND output_name_receipt_digest ~ '^[0-9a-f]{64}$' "
            "AND output_seal_receipt_digest ~ '^[0-9a-f]{64}$' "
            "AND registry_commit_receipt_digest ~ '^[0-9a-f]{64}$' "
            "AND generation_capability_authority_digest ~ '^[0-9a-f]{64}$' "
            "AND generation_request_policy_digest ~ '^[0-9a-f]{64}$' "
            "AND (generation_request_digest IS NULL OR "
            "generation_request_digest ~ '^[0-9a-f]{64}$') "
            "AND (generation_source_asset_sha256 IS NULL OR "
            "generation_source_asset_sha256 ~ '^[0-9a-f]{64}$') "
            "AND (source_normalization_receipt_digest IS NULL OR "
            "source_normalization_receipt_digest ~ '^[0-9a-f]{64}$') "
            "AND source_provenance_digest ~ '^[0-9a-f]{64}$' "
            "AND source_provenance_name_receipt_digest ~ '^[0-9a-f]{64}$' "
            "AND source_provenance_seal_receipt_digest ~ '^[0-9a-f]{64}$' "
            "AND source_provenance_registry_commit_receipt_digest ~ '^[0-9a-f]{64}$' "
            "AND source_authority_digest ~ '^[0-9a-f]{64}$' "
            "AND source_qa_snapshot_digest ~ '^[0-9a-f]{64}$'",
            name="digest_shapes",
        ),
    )


class DemoSyntheticIdentity(DemoAuthorityMixin, Base):
    __tablename__ = "demo_synthetic_identities"

    formal_synthetic_identity_id: Mapped[str | None] = mapped_column(
        ForeignKey("synthetic_identities.id", ondelete="RESTRICT"),
        index=True,
    )
    formal_canonical_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    formal_canonical_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    formal_accepted_qa_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("synthetic_qa_runs.id", ondelete="RESTRICT"), index=True
    )
    formal_accepted_qa_snapshot_digest: Mapped[str | None] = mapped_column(String(64))
    admission_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    admission_action: Mapped[str] = mapped_column(String(16), nullable=False)
    admission_config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_synthetic_identities.id", ondelete="RESTRICT"), index=True
    )
    source_output_id: Mapped[str | None] = mapped_column(String(128))
    source_receipt_digest: Mapped[str | None] = mapped_column(String(64))
    source_authority_digest: Mapped[str | None] = mapped_column(String(64))
    source_qa_snapshot_digest: Mapped[str | None] = mapped_column(String(64))
    source_landmark_digest: Mapped[str | None] = mapped_column(String(64))
    source_measurement_digest: Mapped[str | None] = mapped_column(String(64))
    source_provenance_digest: Mapped[str | None] = mapped_column(String(64))
    source_fact_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source_fact_snapshot_digest: Mapped[str | None] = mapped_column(String(64))
    source_measurement_projection: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source_measurement_projection_digest: Mapped[str | None] = mapped_column(String(64))
    original_formal_identity_id_status: Mapped[str | None] = mapped_column(String(48))
    adult_synthetic_attested: Mapped[bool | None] = mapped_column(Boolean)
    importer_version: Mapped[str | None] = mapped_column(String(64))
    import_config_digest: Mapped[str | None] = mapped_column(String(64))
    r2_source_authority_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_d02_r2_source_authorities.id", ondelete="RESTRICT"), index=True
    )
    source_authority_kind: Mapped[str] = mapped_column(
        String(32),
        Computed(
            "CASE WHEN formal_synthetic_identity_id IS NOT NULL "
            "THEN 'FORMAL_REFERENCE' WHEN r2_source_authority_record_id IS NOT NULL "
            "THEN 'DEMO_R2_GENERATED_SOURCE' ELSE 'DEMO_LOCAL_IMPORTED_COPY' END",
            persisted=True,
        ),
        nullable=False,
    )
    source_authority_key: Mapped[str] = mapped_column(
        String(64),
        Computed(
            "CASE WHEN formal_synthetic_identity_id IS NOT NULL "
            "THEN mirror_demo_formal_source_authority_key(formal_synthetic_identity_id) "
            "WHEN r2_source_authority_record_id IS NOT NULL "
            "THEN mirror_demo_r2_source_authority_key(source_output_id, "
            "formal_canonical_asset_id, formal_canonical_asset_sha256, source_receipt_digest, "
            "source_authority_digest) ELSE "
            "mirror_demo_local_source_authority_key(source_output_id, "
            "formal_canonical_asset_id, formal_canonical_asset_sha256, "
            "source_receipt_digest) END",
            persisted=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        *_authority_constraints(
            __tablename__,
            schema_version_expression=(
                "schema_version IN ('mirror.demo/DemoSyntheticIdentity/v1',"
                "'mirror.demo/DemoSyntheticIdentity/v2',"
                "'mirror.demo/DemoSyntheticIdentity/v3',"
                "'mirror.demo/DemoSyntheticIdentity/v4')"
            ),
        ),
        UniqueConstraint(
            "source_authority_key",
            "admission_sequence",
            name="uq_demo_synthetic_identities_source_sequence",
        ),
        UniqueConstraint(
            "supersedes_id",
            name="uq_demo_synthetic_identities_supersedes_id",
        ),
        CheckConstraint("admission_sequence > 0", name="positive_admission_sequence"),
        CheckConstraint(
            "admission_action IN ('ADMIT','REVOKE')",
            name="admission_action",
        ),
        CheckConstraint(
            "admission_config_digest ~ '^[0-9a-f]{64}$'",
            name="admission_config_digest_shape",
        ),
        CheckConstraint(
            "schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3' "
            "OR source_output_id IS NULL "
            "OR admission_config_digest = "
            "'ef87c397af7db78211a6d2440f0cb3eef4214080f5117ff7be89b6400b663b21'",
            name="d02_local_admission_config_exact",
        ),
        CheckConstraint(
            D02_LOCAL_QA_DIGEST_SEPARATION_CHECK_SQL,
            name="d02_local_qa_digest_separation",
        ),
        CheckConstraint(
            "formal_canonical_asset_sha256 ~ '^[0-9a-f]{64}$'",
            name="formal_canonical_asset_sha_shape",
        ),
        CheckConstraint(
            "formal_accepted_qa_snapshot_digest IS NULL OR "
            "formal_accepted_qa_snapshot_digest ~ '^[0-9a-f]{64}$'",
            name="qa_snapshot_digest_shape",
        ),
        CheckConstraint(
            "source_authority_kind IN ('FORMAL_REFERENCE','DEMO_LOCAL_IMPORTED_COPY',"
            "'DEMO_R2_GENERATED_SOURCE')",
            name="source_authority_kind",
        ),
        CheckConstraint(
            "source_authority_key ~ '^[0-9a-f]{64}$'",
            name="source_authority_key_shape",
        ),
        CheckConstraint(
            "source_output_id IS NULL OR source_output_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'",
            name="source_output_id_shape",
        ),
        CheckConstraint(
            "(source_receipt_digest IS NULL OR source_receipt_digest ~ '^[0-9a-f]{64}$') "
            "AND (source_authority_digest IS NULL OR source_authority_digest ~ '^[0-9a-f]{64}$') "
            "AND (source_qa_snapshot_digest IS NULL OR "
            "source_qa_snapshot_digest ~ '^[0-9a-f]{64}$') "
            "AND (source_landmark_digest IS NULL OR source_landmark_digest ~ '^[0-9a-f]{64}$') "
            "AND (source_measurement_digest IS NULL OR "
            "source_measurement_digest ~ '^[0-9a-f]{64}$') "
            "AND (source_provenance_digest IS NULL OR source_provenance_digest ~ '^[0-9a-f]{64}$') "
            "AND (source_fact_snapshot_digest IS NULL OR "
            "source_fact_snapshot_digest ~ '^[0-9a-f]{64}$') "
            "AND (source_measurement_projection_digest IS NULL OR "
            "source_measurement_projection_digest ~ '^[0-9a-f]{64}$') "
            "AND (import_config_digest IS NULL OR import_config_digest ~ '^[0-9a-f]{64}$')",
            name="local_digest_shapes",
        ),
        CheckConstraint(
            "(source_fact_snapshot IS NULL OR jsonb_typeof(source_fact_snapshot) = 'object') "
            "AND (source_measurement_projection IS NULL OR "
            "jsonb_typeof(source_measurement_projection) = 'object')",
            name="local_json_objects",
        ),
        CheckConstraint(
            "(schema_version = 'mirror.demo/DemoSyntheticIdentity/v4' "
            "AND source_authority_kind = 'DEMO_R2_GENERATED_SOURCE' "
            "AND r2_source_authority_record_id IS NOT NULL "
            "AND formal_synthetic_identity_id IS NULL "
            "AND formal_accepted_qa_run_id IS NULL "
            "AND formal_accepted_qa_snapshot_digest IS NULL "
            "AND source_output_id IS NOT NULL AND source_receipt_digest IS NOT NULL "
            "AND source_authority_digest IS NOT NULL "
            "AND source_qa_snapshot_digest IS NOT NULL "
            "AND source_landmark_digest IS NOT NULL AND source_measurement_digest IS NOT NULL "
            "AND source_provenance_digest IS NOT NULL AND source_fact_snapshot IS NOT NULL "
            "AND source_fact_snapshot_digest IS NOT NULL "
            "AND source_measurement_projection IS NOT NULL "
            "AND source_measurement_projection_digest IS NOT NULL "
            "AND original_formal_identity_id_status = 'NOT_APPLICABLE_DEMO_R2_GENERATED_SOURCE' "
            "AND adult_synthetic_attested IS TRUE "
            "AND importer_version = 'demo-d02-r2-identity-importer-v1' "
            "AND import_config_digest IS NOT NULL) OR "
            "(schema_version <> 'mirror.demo/DemoSyntheticIdentity/v4' "
            "AND r2_source_authority_record_id IS NULL AND ("
            "(source_authority_kind = 'FORMAL_REFERENCE' "
            "AND schema_version <> 'mirror.demo/DemoSyntheticIdentity/v3' "
            "AND formal_synthetic_identity_id IS NOT NULL "
            "AND formal_accepted_qa_run_id IS NOT NULL "
            "AND formal_accepted_qa_snapshot_digest IS NOT NULL "
            "AND source_output_id IS NULL AND source_receipt_digest IS NULL "
            "AND source_authority_digest IS NULL AND source_qa_snapshot_digest IS NULL "
            "AND source_landmark_digest IS NULL AND source_measurement_digest IS NULL "
            "AND source_provenance_digest IS NULL AND source_fact_snapshot IS NULL "
            "AND source_fact_snapshot_digest IS NULL "
            "AND source_measurement_projection IS NULL "
            "AND source_measurement_projection_digest IS NULL "
            "AND original_formal_identity_id_status IS NULL "
            "AND adult_synthetic_attested IS NULL AND importer_version IS NULL "
            "AND import_config_digest IS NULL) OR "
            "(source_authority_kind = 'DEMO_LOCAL_IMPORTED_COPY' "
            "AND formal_synthetic_identity_id IS NULL "
            "AND formal_accepted_qa_run_id IS NULL "
            "AND formal_accepted_qa_snapshot_digest IS NULL "
            "AND source_output_id IS NOT NULL AND source_receipt_digest IS NOT NULL "
            "AND source_authority_digest IS NOT NULL "
            "AND source_qa_snapshot_digest IS NOT NULL "
            "AND source_landmark_digest IS NOT NULL "
            "AND source_measurement_digest IS NOT NULL "
            "AND source_provenance_digest IS NOT NULL "
            "AND source_fact_snapshot IS NOT NULL "
            "AND source_fact_snapshot_digest IS NOT NULL "
            "AND source_measurement_projection IS NOT NULL "
            "AND source_measurement_projection_digest IS NOT NULL "
            "AND original_formal_identity_id_status = 'UNKNOWN_REDACTED_NOT_RECOVERED' "
            "AND adult_synthetic_attested IS TRUE "
            "AND ((schema_version = 'mirror.demo/DemoSyntheticIdentity/v2' "
            "AND importer_version = 'demo-d02-identity-importer-v2') OR "
            "(schema_version = 'mirror.demo/DemoSyntheticIdentity/v3' "
            "AND importer_version = 'demo-d02-identity-importer-v3')) "
            "AND import_config_digest IS NOT NULL)))",
            name="source_mode_null_matrix",
        ),
        CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id <> id", name="not_self_superseding"
        ),
    )


class DemoAnalysisRun(DemoAuthorityMixin, Base):
    __tablename__ = "demo_analysis_runs"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_session_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    demo_synthetic_identity_id: Mapped[str] = mapped_column(
        ForeignKey("demo_synthetic_identities.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    source_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    demo_job_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "demo_job_bindings.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        unique=True,
        nullable=False,
    )
    analyzer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    model_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_aggregation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    measurement_version: Mapped[str] = mapped_column(String(64), nullable=False)
    self_state_ontology_version: Mapped[str] = mapped_column(String(64), nullable=False)
    self_state_derivation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    repeat_count: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_analysis_runs_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_analysis_runs_id_actor_session",
        ),
        CheckConstraint("source_asset_sha256 ~ '^[0-9a-f]{64}$'", name="source_sha_shape"),
        CheckConstraint(
            "runtime_manifest_digest ~ '^[0-9a-f]{64}$'",
            name="runtime_manifest_digest_shape",
        ),
        CheckConstraint(
            "model_manifest_digest ~ '^[0-9a-f]{64}$'",
            name="model_manifest_digest_shape",
        ),
        CheckConstraint(
            "observation_config_digest ~ '^[0-9a-f]{64}$'",
            name="observation_config_digest_shape",
        ),
        CheckConstraint("repeat_count = 3", name="three_repeats"),
    )


class DemoFaceObservation(DemoAuthorityMixin, Base):
    __tablename__ = "demo_face_observations"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_synthetic_identity_id: Mapped[str] = mapped_column(
        ForeignKey("demo_synthetic_identities.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    source_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_analysis_runs.id", ondelete="RESTRICT"),
        index=True,
        unique=True,
    )
    analyzer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    repeat_count: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_state: Mapped[str] = mapped_column(String(24), nullable=False)
    unsupported_reason: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        *_authority_constraints(
            __tablename__,
            schema_version_expression=(
                "schema_version IN ('mirror.demo/DemoFaceObservation/v1',"
                "'mirror.demo/DemoFaceObservation/v2')"
            ),
        ),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_face_observations_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_face_observations_id_actor_session",
        ),
        CheckConstraint("source_asset_sha256 ~ '^[0-9a-f]{64}$'", name="source_sha_shape"),
        CheckConstraint(
            "runtime_manifest_digest ~ '^[0-9a-f]{64}$'",
            name="runtime_manifest_digest_shape",
        ),
        CheckConstraint("config_digest ~ '^[0-9a-f]{64}$'", name="config_digest_shape"),
        CheckConstraint("repeat_count = 3", name="three_repeats"),
        CheckConstraint(
            "(schema_version = 'mirror.demo/DemoFaceObservation/v1' "
            "AND analysis_run_id IS NULL) OR "
            "(schema_version = 'mirror.demo/DemoFaceObservation/v2' "
            "AND analysis_run_id IS NOT NULL)",
            name="analysis_run_version_shape",
        ),
        CheckConstraint(
            "(observation_state = 'SUPPORTED' AND unsupported_reason IS NULL) OR "
            "(observation_state = 'UNSUPPORTED' AND unsupported_reason IS NOT NULL)",
            name="observation_state_shape",
        ),
    )


class DemoFaceObservationRepeat(DemoAuthorityMixin, Base):
    __tablename__ = "demo_face_observation_repeats"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    observation_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    repeat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    runtime_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    model_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    landmarks: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    pose: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    quality: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["observation_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_face_observations.id",
                "demo_face_observations.demo_actor_id",
                "demo_face_observations.demo_session_id",
            ],
            name="fk_demo_face_observation_repeats_observation_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "observation_id",
            "repeat_index",
            name="uq_demo_face_observation_repeats_observation_repeat",
        ),
        CheckConstraint("repeat_index BETWEEN 1 AND 3", name="repeat_index"),
        CheckConstraint("jsonb_typeof(landmarks) = 'array'", name="landmarks_array"),
        CheckConstraint("jsonb_array_length(landmarks) = 478", name="landmark_count"),
        CheckConstraint("jsonb_typeof(pose) = 'object'", name="pose_object"),
        CheckConstraint("jsonb_typeof(quality) = 'object'", name="quality_object"),
        CheckConstraint("jsonb_typeof(measurements) = 'object'", name="measurements_object"),
    )


class DemoBaselineFaceModel(DemoAuthorityMixin, Base):
    __tablename__ = "demo_baseline_face_models"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    observation_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    measurement_version: Mapped[str] = mapped_column(String(64), nullable=False)
    ordered_repeat_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reliability: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    uncertainty: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    unsupported_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["observation_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_face_observations.id",
                "demo_face_observations.demo_actor_id",
                "demo_face_observations.demo_session_id",
            ],
            name="fk_demo_baseline_face_models_observation_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "observation_id",
            "version",
            name="uq_demo_baseline_face_models_observation_version",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_baseline_face_models_id_actor_session",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint(
            "jsonb_typeof(ordered_repeat_digests) = 'array' "
            "AND jsonb_array_length(ordered_repeat_digests) = 3",
            name="three_repeat_digests",
        ),
        CheckConstraint("jsonb_typeof(measurements) = 'object'", name="measurements_object"),
        CheckConstraint("jsonb_typeof(reliability) = 'object'", name="reliability_object"),
        CheckConstraint("jsonb_typeof(uncertainty) = 'object'", name="uncertainty_object"),
        CheckConstraint(
            "jsonb_typeof(unsupported_state) = 'object'",
            name="unsupported_state_object",
        ),
    )


class DemoSelfState(DemoAuthorityMixin, Base):
    __tablename__ = "demo_self_states"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    baseline_face_model_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    ontology_version: Mapped[str] = mapped_column(String(64), nullable=False)
    derivation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reliability: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    uncertainty: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    routing_eligibility: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["baseline_face_model_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_baseline_face_models.id",
                "demo_baseline_face_models.demo_actor_id",
                "demo_baseline_face_models.demo_session_id",
            ],
            name="fk_demo_self_states_baseline_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "baseline_face_model_id",
            "version",
            name="uq_demo_self_states_baseline_version",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_self_states_id_actor_session",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("jsonb_typeof(measurements) = 'object'", name="measurements_object"),
        CheckConstraint("jsonb_typeof(reliability) = 'object'", name="reliability_object"),
        CheckConstraint("jsonb_typeof(uncertainty) = 'object'", name="uncertainty_object"),
        CheckConstraint(
            "jsonb_typeof(routing_eligibility) = 'object'",
            name="routing_eligibility_object",
        ),
    )


class DemoPairScreeningReport(DemoAuthorityMixin, Base):
    __tablename__ = "demo_pair_screening_reports"

    source_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    case_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    screening_policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    vision_model_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    topology_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    measurement_config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    manual_review_policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    duplicate_policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    phash_implementation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    report_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    report_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_m3_repeat_count: Mapped[int] = mapped_column(Integer, nullable=False)
    m4_execution_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result_m3_repeat_count: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement_gate_count: Mapped[int | None] = mapped_column(Integer)
    decode_structure_record_count: Mapped[int | None] = mapped_column(Integer)
    manual_decision_count: Mapped[int] = mapped_column(Integer, nullable=False)
    exact_sha_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    phash_comparison_count: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_pair_count: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_pair_count: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_result_side_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_dimension_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    selected_dimension_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    selected_pair_manifest_digest: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        *_authority_constraints(
            __tablename__,
            schema_version_expression=(
                "schema_version IN ('mirror.demo/D02PairScreeningReport/v1',"
                "'mirror.demo/D02PairScreeningReport/v2',"
                "'mirror.demo/D02PairScreeningReport/v3')"
            ),
        ),
        UniqueConstraint("report_digest", name="uq_demo_pair_screening_reports_report_digest"),
        CheckConstraint(
            "schema_version IN ('mirror.demo/D02PairScreeningReport/v1',"
            "'mirror.demo/D02PairScreeningReport/v2','mirror.demo/D02PairScreeningReport/v3')",
            name="exact_schema_version",
        ),
        CheckConstraint(
            "source_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND case_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND screening_policy_digest ~ '^[0-9a-f]{64}$' "
            "AND runtime_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND vision_model_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND topology_digest ~ '^[0-9a-f]{64}$' "
            "AND measurement_config_digest ~ '^[0-9a-f]{64}$' "
            "AND manual_review_policy_digest ~ '^[0-9a-f]{64}$' "
            "AND duplicate_policy_digest ~ '^[0-9a-f]{64}$' "
            "AND phash_implementation_digest ~ '^[0-9a-f]{64}$' "
            "AND report_digest ~ '^[0-9a-f]{64}$' "
            "AND (selected_pair_manifest_digest IS NULL OR "
            "selected_pair_manifest_digest ~ '^[0-9a-f]{64}$')",
            name="digest_shapes",
        ),
        CheckConstraint(
            "jsonb_typeof(report_payload) = 'object' "
            "AND jsonb_typeof(eligible_dimension_keys) = 'array' "
            "AND jsonb_typeof(selected_dimension_keys) = 'array'",
            name="json_shapes",
        ),
        CheckConstraint("status IN ('PASSED','FAILED')", name="status"),
        CheckConstraint(
            "source_count = 4 AND case_count = 48 "
            "AND source_m3_repeat_count = 12 AND m4_execution_count = 96 "
            "AND result_m3_repeat_count = 144 AND manual_decision_count = 48 "
            "AND exact_sha_record_count = 52 AND phash_comparison_count = 1326 "
            "AND candidate_pair_count = 24 AND ("
            "(status = 'PASSED' AND selected_pair_count = 16 "
            "AND selected_result_side_count = 32 "
            "AND jsonb_array_length(selected_dimension_keys) = 2 "
            "AND selected_pair_manifest_digest IS NOT NULL) OR "
            "(status = 'FAILED' AND selected_pair_count = 0 "
            "AND selected_result_side_count = 0 "
            "AND jsonb_array_length(selected_dimension_keys) = 0 "
            "AND selected_pair_manifest_digest IS NULL))",
            name="fixed_cardinality",
        ),
        CheckConstraint(
            "(schema_version IN ('mirror.demo/D02PairScreeningReport/v1',"
            "'mirror.demo/D02PairScreeningReport/v2') AND measurement_gate_count IS NULL "
            "AND decode_structure_record_count IS NULL) OR "
            "(schema_version = 'mirror.demo/D02PairScreeningReport/v3' "
            "AND measurement_gate_count = 48 AND decode_structure_record_count = 48)",
            name="r2_v3_exact_counts",
        ),
    )


class DemoQuestionBank(DemoAuthorityMixin, Base):
    __tablename__ = "demo_question_banks"

    version: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm_config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    routing_version: Mapped[str] = mapped_column(String(64), nullable=False)
    stopping_version: Mapped[str] = mapped_column(String(64), nullable=False)
    neighborhood_version: Mapped[str] = mapped_column(String(64), nullable=False)
    pair_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension_manifest: Mapped[list[Any] | dict[str, Any]] = mapped_column(JSONB, nullable=False)
    screening_report_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_pair_screening_reports.id", ondelete="RESTRICT"), index=True
    )
    screening_report_digest: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        *_authority_constraints(
            __tablename__,
            schema_version_expression=(
                "schema_version IN ('mirror.demo/DemoQuestionBank/v1',"
                "'mirror.demo/DemoQuestionBank/v2','mirror.demo/DemoQuestionBank/v3')"
            ),
        ),
        UniqueConstraint("version", name="uq_demo_question_banks_version"),
        CheckConstraint(
            "algorithm_config_digest ~ '^[0-9a-f]{64}$'",
            name="algorithm_config_digest_shape",
        ),
        CheckConstraint(
            "pair_manifest_digest ~ '^[0-9a-f]{64}$'",
            name="pair_manifest_digest_shape",
        ),
        CheckConstraint(
            "(schema_version = 'mirror.demo/DemoQuestionBank/v1' "
            "AND jsonb_typeof(dimension_manifest) = 'array' "
            "AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR "
            "(schema_version IN ('mirror.demo/DemoQuestionBank/v2',"
            "'mirror.demo/DemoQuestionBank/v3') "
            "AND jsonb_typeof(dimension_manifest) = 'object' "
            "AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
            name="versioned_dimension_manifest",
        ),
        CheckConstraint(
            "screening_report_digest IS NULL OR screening_report_digest ~ '^[0-9a-f]{64}$'",
            name="screening_report_digest_shape",
        ),
    )


class DemoQuestionPair(DemoAuthorityMixin, Base):
    __tablename__ = "demo_question_pairs"

    question_bank_id: Mapped[str] = mapped_column(
        ForeignKey("demo_question_banks.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    demo_synthetic_identity_id: Mapped[str] = mapped_column(
        ForeignKey("demo_synthetic_identities.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    source_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    left_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    left_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    right_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    right_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    left_asset_variant_id: Mapped[str] = mapped_column(
        ForeignKey("asset_variants.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    right_asset_variant_id: Mapped[str] = mapped_column(
        ForeignKey("asset_variants.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    dimension_key: Mapped[str] = mapped_column(String(48), nullable=False)
    magnitude_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    left_delta_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    right_delta_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    pair_quality_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    qa_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    screening_report_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_pair_screening_reports.id", ondelete="RESTRICT"), index=True
    )
    screening_report_digest: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        *_authority_constraints(
            __tablename__,
            schema_version_expression=(
                "schema_version IN ('mirror.demo/DemoQuestionPair/v1',"
                "'mirror.demo/DemoQuestionPair/v2','mirror.demo/DemoQuestionPair/v3')"
            ),
        ),
        UniqueConstraint(
            "question_bank_id",
            "demo_synthetic_identity_id",
            "dimension_key",
            "magnitude_ppm",
            name="uq_demo_question_pairs_bank_identity_dimension_magnitude",
        ),
        CheckConstraint("source_asset_sha256 ~ '^[0-9a-f]{64}$'", name="source_sha_shape"),
        CheckConstraint("left_asset_sha256 ~ '^[0-9a-f]{64}$'", name="left_sha_shape"),
        CheckConstraint("right_asset_sha256 ~ '^[0-9a-f]{64}$'", name="right_sha_shape"),
        CheckConstraint(
            "left_asset_id <> right_asset_id AND source_asset_id <> left_asset_id "
            "AND source_asset_id <> right_asset_id",
            name="distinct_pair_assets",
        ),
        CheckConstraint("magnitude_ppm > 0", name="positive_magnitude"),
        CheckConstraint(
            "left_delta_ppm = -magnitude_ppm AND right_delta_ppm = magnitude_ppm",
            name="opposite_pair_deltas",
        ),
        CheckConstraint(
            "pair_quality_ppm BETWEEN 0 AND 1000000",
            name="pair_quality_range",
        ),
        CheckConstraint("jsonb_typeof(qa_payload) = 'object'", name="qa_payload_object"),
        CheckConstraint(
            "(schema_version = 'mirror.demo/DemoQuestionPair/v1' "
            "AND screening_report_id IS NULL AND screening_report_digest IS NULL) OR "
            "(schema_version IN ('mirror.demo/DemoQuestionPair/v2',"
            "'mirror.demo/DemoQuestionPair/v3') "
            "AND screening_report_id IS NOT NULL AND screening_report_digest IS NOT NULL)",
            name="versioned_report_binding",
        ),
        CheckConstraint(
            "screening_report_digest IS NULL OR screening_report_digest ~ '^[0-9a-f]{64}$'",
            name="screening_report_digest_shape",
        ),
        Index(
            "ix_demo_question_pairs_routing",
            "question_bank_id",
            "dimension_key",
            "demo_synthetic_identity_id",
            "magnitude_ppm",
        ),
    )


class DemoD02R2Epoch2Admission(DemoAuthorityMixin, Base):
    """Atomic E2 binding for one complete Report/Bank/Pair authority graph."""

    __tablename__ = "demo_d02_r2_epoch2_admissions"

    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_epoch: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_root_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    screening_report_id: Mapped[str] = mapped_column(
        ForeignKey(
            "demo_pair_screening_reports.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=False,
        index=True,
    )
    screening_report_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    question_bank_id: Mapped[str] = mapped_column(
        ForeignKey(
            "demo_question_banks.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=False,
        index=True,
    )
    question_bank_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    question_bank_version: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_pair_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_authority_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    synthetic_identity_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    question_pair_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    selected_result_side_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    admission_state: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        *_authority_constraints(
            __tablename__,
            schema_version_expression=("schema_version = 'mirror.demo/D02R2Epoch2Admission/v1'"),
        ),
        UniqueConstraint("idempotency_key_hash", name="idempotency_key_hash"),
        UniqueConstraint("screening_report_id", name="screening_report_id"),
        UniqueConstraint("question_bank_id", name="question_bank_id"),
        CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$' "
            "AND request_digest ~ '^[0-9a-f]{64}$' "
            "AND source_manifest_digest ~ '^[0-9a-f]{64}$' "
            "AND screening_report_digest ~ '^[0-9a-f]{64}$' "
            "AND question_bank_content_digest ~ '^[0-9a-f]{64}$' "
            "AND selected_pair_manifest_digest ~ '^[0-9a-f]{64}$'",
            name="digest_shapes",
        ),
        CheckConstraint(
            "execution_epoch = 'D02_R2_EPOCH_02' "
            "AND evidence_root_id = 'P3_P7_D02_R2_CC08_E2_EVIDENCE_ROOT'",
            name="epoch_root",
        ),
        CheckConstraint(
            "source_authority_count = 4 AND synthetic_identity_count = 4 "
            "AND question_pair_count = 16 AND selected_result_side_count = 32",
            name="fixed_cardinality",
        ),
        CheckConstraint("admission_state = 'COMPLETED'", name="state"),
    )


class DemoQuestionnaireRun(DemoAuthorityMixin, Base):
    __tablename__ = "demo_questionnaire_runs"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    question_bank_id: Mapped[str] = mapped_column(
        ForeignKey("demo_question_banks.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    self_state_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    algorithm_config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_posterior: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_questionnaire_runs_session_actor",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["self_state_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_self_states.id",
                "demo_self_states.demo_actor_id",
                "demo_self_states.demo_session_id",
            ],
            name="fk_demo_questionnaire_runs_self_state_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_questionnaire_runs_id_actor_session",
        ),
        CheckConstraint(
            "algorithm_config_digest ~ '^[0-9a-f]{64}$'",
            name="algorithm_config_digest_shape",
        ),
        CheckConstraint("max_questions BETWEEN 12 AND 16", name="question_limit"),
        CheckConstraint(
            "jsonb_typeof(initial_posterior) = 'object'",
            name="initial_posterior_object",
        ),
    )


class DemoQuestionnaireStep(DemoAuthorityMixin, Base):
    __tablename__ = "demo_questionnaire_steps"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    questionnaire_run_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step_number: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    question_pair_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_question_pairs.id", ondelete="RESTRICT"), index=True
    )
    routing_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    posterior_before: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    posterior_after: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    scheduler_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["questionnaire_run_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_questionnaire_runs.id",
                "demo_questionnaire_runs.demo_actor_id",
                "demo_questionnaire_runs.demo_session_id",
            ],
            name="fk_demo_questionnaire_steps_run_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "questionnaire_run_id",
            "event_sequence",
            name="uq_demo_questionnaire_steps_run_event_sequence",
        ),
        CheckConstraint("event_sequence > 0", name="positive_event_sequence"),
        CheckConstraint("step_number IS NULL OR step_number > 0", name="positive_step_number"),
        CheckConstraint(
            "event_type IN ('PRESENTED','RESPONDED','STOPPED','INVALIDATED')",
            name="event_type",
        ),
        CheckConstraint(
            "jsonb_typeof(routing_snapshot) = 'object'",
            name="routing_snapshot_object",
        ),
        CheckConstraint(
            "response_snapshot IS NULL OR jsonb_typeof(response_snapshot) = 'object'",
            name="response_snapshot_object",
        ),
        CheckConstraint(
            "jsonb_typeof(posterior_before) = 'object'",
            name="posterior_before_object",
        ),
        CheckConstraint(
            "jsonb_typeof(posterior_after) = 'object'",
            name="posterior_after_object",
        ),
        Index(
            "uq_demo_questionnaire_steps_run_step_event",
            "questionnaire_run_id",
            "step_number",
            "event_type",
            unique=True,
            postgresql_where=text("step_number IS NOT NULL"),
        ),
    )


class DemoDesiredDeltaProfile(DemoAuthorityMixin, Base):
    __tablename__ = "demo_desired_delta_profiles"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    self_state_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_job_binding_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "demo_job_bindings.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of_event_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compilation_watermark: Mapped[str] = mapped_column(String(64), nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    restraint: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_desired_delta_profiles_session_actor",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["self_state_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_self_states.id",
                "demo_self_states.demo_actor_id",
                "demo_self_states.demo_session_id",
            ],
            name="fk_demo_desired_delta_profiles_self_state_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "version",
            name="uq_demo_desired_delta_profiles_actor_version",
        ),
        Index(
            "uq_demo_desired_delta_profiles_job_binding",
            "demo_job_binding_id",
            unique=True,
            postgresql_where=text("demo_job_binding_id IS NOT NULL"),
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("as_of_event_sequence >= 0", name="nonnegative_event_sequence"),
        CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name="watermark_shape",
        ),
        CheckConstraint("jsonb_typeof(dimensions) = 'object'", name="dimensions_object"),
        CheckConstraint(
            "jsonb_typeof(evidence_digests) = 'array'",
            name="evidence_digests_array",
        ),
        CheckConstraint("jsonb_typeof(restraint) = 'object'", name="restraint_object"),
    )


class DemoStyleProfile(DemoAuthorityMixin, Base):
    __tablename__ = "demo_style_profiles"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_session_id: Mapped[str | None] = mapped_column(String(32), index=True)
    desired_delta_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_desired_delta_profiles.id", ondelete="RESTRICT"), index=True
    )
    demo_job_binding_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "demo_job_bindings.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of_event_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compilation_watermark: Mapped[str] = mapped_column(String(64), nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    negative_evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    evidence_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_style_profiles_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "version",
            name="uq_demo_style_profiles_actor_version",
        ),
        Index(
            "uq_demo_style_profiles_job_binding",
            "demo_job_binding_id",
            unique=True,
            postgresql_where=text("demo_job_binding_id IS NOT NULL"),
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("as_of_event_sequence >= 0", name="nonnegative_event_sequence"),
        CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name="watermark_shape",
        ),
        CheckConstraint("jsonb_typeof(preferences) = 'object'", name="preferences_object"),
        CheckConstraint(
            "jsonb_typeof(negative_evidence) = 'array'",
            name="negative_evidence_array",
        ),
        CheckConstraint(
            "jsonb_typeof(evidence_digests) = 'array'",
            name="evidence_digests_array",
        ),
    )


class DemoIdentityConstraints(DemoAuthorityMixin, Base):
    __tablename__ = "demo_identity_constraints"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_session_id: Mapped[str | None] = mapped_column(String(32), index=True)
    self_state_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_self_states.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    constraint_scope: Mapped[str] = mapped_column(String(24), nullable=False)
    source_event_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    locks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    bounds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prohibited_operations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_identity_constraints_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "version",
            name="uq_demo_identity_constraints_actor_version",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint(
            "constraint_scope IN ('PERSISTENT','SESSION_OVERRIDE')",
            name="constraint_scope",
        ),
        CheckConstraint(
            "(constraint_scope = 'PERSISTENT' AND demo_session_id IS NULL) OR "
            "(constraint_scope = 'SESSION_OVERRIDE' AND demo_session_id IS NOT NULL)",
            name="constraint_scope_shape",
        ),
        CheckConstraint(
            "jsonb_typeof(source_event_digests) = 'array'",
            name="source_event_digests_array",
        ),
        CheckConstraint("jsonb_typeof(locks) = 'object'", name="locks_object"),
        CheckConstraint("jsonb_typeof(bounds) = 'object'", name="bounds_object"),
        CheckConstraint(
            "jsonb_typeof(prohibited_operations) = 'array'",
            name="prohibited_operations_array",
        ),
    )


class DemoProfileCompilationBundle(DemoAuthorityMixin, Base):
    __tablename__ = "demo_profile_compilation_bundles"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_job_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "demo_job_bindings.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        index=True,
        nullable=False,
    )
    self_state_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    desired_delta_profile_id: Mapped[str] = mapped_column(
        ForeignKey("demo_desired_delta_profiles.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    style_profile_id: Mapped[str] = mapped_column(
        ForeignKey("demo_style_profiles.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    persistent_constraints_id: Mapped[str] = mapped_column(
        ForeignKey("demo_identity_constraints.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    session_override_constraints_id: Mapped[str] = mapped_column(
        ForeignKey("demo_identity_constraints.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    as_of_event_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compilation_watermark: Mapped[str] = mapped_column(String(64), nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    compilation_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_profile_compilation_bundles_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "demo_job_binding_id",
            name="uq_demo_profile_compilation_bundles_job_binding",
        ),
        UniqueConstraint(
            "desired_delta_profile_id",
            name="uq_demo_profile_compilation_bundles_desired_profile",
        ),
        UniqueConstraint(
            "style_profile_id",
            name="uq_demo_profile_compilation_bundles_style_profile",
        ),
        UniqueConstraint(
            "persistent_constraints_id",
            name="uq_demo_profile_compilation_bundles_persistent_constraints",
        ),
        UniqueConstraint(
            "session_override_constraints_id",
            name="uq_demo_profile_compilation_bundles_session_constraints",
        ),
        ForeignKeyConstraint(
            ["self_state_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_self_states.id",
                "demo_self_states.demo_actor_id",
                "demo_self_states.demo_session_id",
            ],
            name="fk_demo_profile_compilation_bundles_self_state_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint("as_of_event_sequence >= 0", name="nonnegative_event_sequence"),
        CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name="watermark_shape",
        ),
        CheckConstraint("input_digest ~ '^[0-9a-f]{64}$'", name="input_digest_shape"),
        CheckConstraint(
            "compilation_digest ~ '^[0-9a-f]{64}$'",
            name="compilation_digest_shape",
        ),
        CheckConstraint(
            "persistent_constraints_id <> session_override_constraints_id",
            name="distinct_constraint_rows",
        ),
    )


class DemoSelfTransferRun(DemoAuthorityMixin, Base):
    __tablename__ = "demo_self_transfer_runs"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    desired_delta_profile_id: Mapped[str] = mapped_column(
        ForeignKey("demo_desired_delta_profiles.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    record_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    request_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_self_transfer_runs.id", ondelete="RESTRICT"), index=True
    )
    demo_job_binding_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "demo_job_bindings.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        index=True,
        unique=True,
    )
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    result_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    requested_delta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    measured_delta: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    non_target_drift: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    verifier_digest: Mapped[str | None] = mapped_column(String(64))
    user_outcome: Mapped[str | None] = mapped_column(String(24))

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_self_transfer_runs_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_self_transfer_runs_id_actor_session",
        ),
        CheckConstraint("record_kind IN ('REQUEST','RESULT')", name="record_kind"),
        CheckConstraint(
            "(record_kind = 'REQUEST' AND request_run_id IS NULL AND result_asset_id IS NULL "
            "AND measured_delta IS NULL AND non_target_drift IS NULL AND verifier_digest IS NULL "
            "AND user_outcome IS NULL) OR "
            "(record_kind = 'RESULT' AND request_run_id IS NOT NULL "
            "AND demo_job_binding_id IS NOT NULL "
            "AND result_asset_id IS NOT NULL AND measured_delta IS NOT NULL "
            "AND non_target_drift IS NOT NULL AND verifier_digest IS NOT NULL "
            "AND user_outcome IN ('ACCEPTED','REJECTED','ADJUSTED'))",
            name="record_shape",
        ),
        CheckConstraint("jsonb_typeof(requested_delta) = 'object'", name="requested_delta_object"),
        CheckConstraint(
            "measured_delta IS NULL OR jsonb_typeof(measured_delta) = 'object'",
            name="measured_delta_object",
        ),
        CheckConstraint(
            "non_target_drift IS NULL OR jsonb_typeof(non_target_drift) = 'object'",
            name="non_target_drift_object",
        ),
        CheckConstraint(
            "verifier_digest IS NULL OR verifier_digest ~ '^[0-9a-f]{64}$'",
            name="verifier_digest_shape",
        ),
        CheckConstraint(
            "result_asset_id IS NULL OR source_asset_id <> result_asset_id",
            name="distinct_source_result",
        ),
    )


class DemoSelfTransferDimensionEvidence(DemoAuthorityMixin, Base):
    __tablename__ = "demo_self_transfer_evidence"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    self_transfer_run_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dimension_key: Mapped[str] = mapped_column(String(48), nullable=False)
    desired_delta_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_ppm: Mapped[int] = mapped_column(Integer, nullable=False)
    verifier_outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    verifier_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    projection_version: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_config_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["self_transfer_run_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_self_transfer_runs.id",
                "demo_self_transfer_runs.demo_actor_id",
                "demo_self_transfer_runs.demo_session_id",
            ],
            name="fk_demo_self_transfer_evidence_run_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "self_transfer_run_id",
            "dimension_key",
            name="uq_demo_self_transfer_evidence_run_dimension",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_self_transfer_evidence_id_actor_session",
        ),
        CheckConstraint(
            "dimension_key ~ '^[a-z][a-z0-9_]{0,47}$'",
            name="dimension_key_shape",
        ),
        CheckConstraint(
            "desired_delta_ppm BETWEEN -1000000 AND 1000000",
            name="desired_delta_range",
        ),
        CheckConstraint(
            "confidence_ppm BETWEEN 0 AND 1000000",
            name="confidence_range",
        ),
        CheckConstraint(
            "verifier_outcome IN ('PASS','FAIL','HUMAN_REVIEW')",
            name="verifier_outcome",
        ),
        ForeignKeyConstraint(
            ["verifier_digest"],
            ["demo_verification_results.content_digest"],
            name="fk_demo_self_transfer_evidence_verifier_digest",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "verifier_digest ~ '^[0-9a-f]{64}$'",
            name="verifier_digest_shape",
        ),
        CheckConstraint(
            "projection_config_digest ~ '^[0-9a-f]{64}$'",
            name="projection_config_digest_shape",
        ),
        CheckConstraint("projection_version <> ''", name="projection_version_nonempty"),
    )


class DemoReferenceProfile(DemoAuthorityMixin, Base):
    __tablename__ = "demo_reference_profiles"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_session_id: Mapped[str | None] = mapped_column(String(32), index=True)
    desired_delta_profile_id: Mapped[str] = mapped_column(
        ForeignKey("demo_desired_delta_profiles.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    style_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_style_profiles.id", ondelete="RESTRICT"), index=True
    )
    identity_constraints_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_identity_constraints.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_assets: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(64), nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    structured_profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_reference_profiles_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "version",
            name="uq_demo_reference_profiles_actor_version",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        CheckConstraint("jsonb_typeof(source_assets) = 'array'", name="source_assets_array"),
        CheckConstraint(
            "jsonb_typeof(structured_profile) = 'object'",
            name="structured_profile_object",
        ),
        CheckConstraint(
            "jsonb_typeof(evidence_digests) = 'array'",
            name="evidence_digests_array",
        ),
    )


class DemoEditingSession(DemoAuthorityMixin, Base):
    __tablename__ = "demo_editing_sessions"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    source_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    desired_delta_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    style_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_constraints_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    context_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_registry_version: Mapped[str] = mapped_column(String(64), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tombstoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_editing_sessions_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_editing_sessions_id_actor_session",
        ),
        CheckConstraint("source_asset_sha256 ~ '^[0-9a-f]{64}$'", name="source_sha_shape"),
        CheckConstraint(
            "desired_delta_profile_digest ~ '^[0-9a-f]{64}$'",
            name="desired_delta_digest_shape",
        ),
        CheckConstraint(
            "style_profile_digest ~ '^[0-9a-f]{64}$'",
            name="style_digest_shape",
        ),
        CheckConstraint(
            "identity_constraints_digest ~ '^[0-9a-f]{64}$'",
            name="constraints_digest_shape",
        ),
        CheckConstraint("context_digest ~ '^[0-9a-f]{64}$'", name="context_digest_shape"),
        CheckConstraint(
            "instruction_digest ~ '^[0-9a-f]{64}$'",
            name="instruction_digest_shape",
        ),
        CheckConstraint(
            "closed_at IS NULL OR closed_at >= created_at",
            name="close_not_before_creation",
        ),
        CheckConstraint(
            "tombstoned_at IS NULL OR (closed_at IS NOT NULL AND tombstoned_at >= closed_at)",
            name="tombstone_order",
        ),
    )


class DemoImageVersion(DemoAuthorityMixin, Base):
    __tablename__ = "demo_image_versions"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    editing_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_image_versions.id", ondelete="RESTRICT"), index=True
    )
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    source_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    result_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, unique=True, nullable=False
    )
    result_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    result_asset_variant_id: Mapped[str] = mapped_column(
        ForeignKey("asset_variants.id", ondelete="RESTRICT"),
        index=True,
        unique=True,
        nullable=False,
    )
    version_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    plan_digest: Mapped[str | None] = mapped_column(String(64))
    tool_run_digest: Mapped[str | None] = mapped_column(String(64))
    verifier_digest: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["editing_session_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_editing_sessions.id",
                "demo_editing_sessions.demo_actor_id",
                "demo_editing_sessions.demo_session_id",
            ],
            name="fk_demo_image_versions_editing_session_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["plan_digest"],
            ["demo_edit_plans.content_digest"],
            name="fk_demo_image_versions_plan_digest_demo_edit_plans",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["tool_run_digest"],
            ["demo_tool_runs.content_digest"],
            name="fk_demo_image_versions_tool_run_digest_demo_tool_runs",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["verifier_digest"],
            ["demo_verification_results.content_digest"],
            name="fk_demo_image_versions_verifier_digest_demo_verification_results",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint(
            "editing_session_id",
            "sequence",
            name="uq_demo_image_versions_session_sequence",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_image_versions_id_actor_session",
        ),
        CheckConstraint("sequence >= 0", name="nonnegative_sequence"),
        CheckConstraint(
            "(sequence = 0 AND parent_version_id IS NULL AND version_kind = 'ORIGINAL' "
            "AND plan_digest IS NULL AND tool_run_digest IS NULL AND verifier_digest IS NULL) OR "
            "(sequence > 0 AND parent_version_id IS NOT NULL "
            "AND version_kind IN ('EDITED','RESTORED','ROLLED_BACK','QUARANTINED') "
            "AND plan_digest IS NOT NULL AND tool_run_digest IS NOT NULL "
            "AND verifier_digest IS NOT NULL)",
            name="lineage_authority_shape",
        ),
        CheckConstraint("source_asset_id <> result_asset_id", name="distinct_source_result"),
        CheckConstraint("source_asset_sha256 ~ '^[0-9a-f]{64}$'", name="source_asset_sha_shape"),
        CheckConstraint("result_asset_sha256 ~ '^[0-9a-f]{64}$'", name="result_asset_sha_shape"),
        CheckConstraint(
            "version_kind IN ('ORIGINAL','EDITED','RESTORED','ROLLED_BACK','QUARANTINED')",
            name="version_kind",
        ),
        CheckConstraint(
            "plan_digest IS NULL OR plan_digest ~ '^[0-9a-f]{64}$'",
            name="plan_digest_shape",
        ),
        CheckConstraint(
            "tool_run_digest IS NULL OR tool_run_digest ~ '^[0-9a-f]{64}$'",
            name="tool_run_digest_shape",
        ),
        CheckConstraint(
            "verifier_digest IS NULL OR verifier_digest ~ '^[0-9a-f]{64}$'",
            name="verifier_digest_shape",
        ),
    )


class DemoEditPlan(DemoAuthorityMixin, Base):
    __tablename__ = "demo_edit_plans"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    editing_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    input_image_version_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    record_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    request_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("demo_edit_plans.id", ondelete="RESTRICT"), index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    desired_delta_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    style_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_constraints_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    planner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_registry_version: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_specs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["editing_session_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_editing_sessions.id",
                "demo_editing_sessions.demo_actor_id",
                "demo_editing_sessions.demo_session_id",
            ],
            name="fk_demo_edit_plans_editing_session_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["input_image_version_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_image_versions.id",
                "demo_image_versions.demo_actor_id",
                "demo_image_versions.demo_session_id",
            ],
            name="fk_demo_edit_plans_input_version_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "input_image_version_id",
            "plan_version",
            "record_kind",
            name="uq_demo_edit_plans_input_version_plan_version",
        ),
        UniqueConstraint(
            "request_plan_id",
            name="uq_demo_edit_plans_request_plan_id",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_edit_plans_id_actor_session",
        ),
        CheckConstraint("record_kind IN ('REQUEST','RESULT')", name="record_kind"),
        CheckConstraint(
            "(record_kind = 'REQUEST' AND request_plan_id IS NULL "
            "AND jsonb_array_length(operation_specs) = 0) OR "
            "(record_kind = 'RESULT' AND request_plan_id IS NOT NULL "
            "AND jsonb_array_length(operation_specs) > 0)",
            name="record_shape",
        ),
        CheckConstraint("plan_version > 0", name="positive_plan_version"),
        CheckConstraint(
            "desired_delta_profile_digest ~ '^[0-9a-f]{64}$'",
            name="desired_delta_digest_shape",
        ),
        CheckConstraint(
            "style_profile_digest ~ '^[0-9a-f]{64}$'",
            name="style_digest_shape",
        ),
        CheckConstraint(
            "identity_constraints_digest ~ '^[0-9a-f]{64}$'",
            name="constraints_digest_shape",
        ),
        CheckConstraint(
            "instruction_digest ~ '^[0-9a-f]{64}$'",
            name="instruction_digest_shape",
        ),
        CheckConstraint(
            "jsonb_typeof(operation_specs) = 'array'",
            name="operation_specs_array",
        ),
    )


class DemoEditOperation(DemoAuthorityMixin, Base):
    __tablename__ = "demo_edit_operations"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    edit_plan_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    operation_index: Mapped[int] = mapped_column(Integer, nullable=False)
    engine: Mapped[str] = mapped_column(String(32), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(48), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    preserve: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    expected_effect: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["edit_plan_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_edit_plans.id",
                "demo_edit_plans.demo_actor_id",
                "demo_edit_plans.demo_session_id",
            ],
            name="fk_demo_edit_operations_plan_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "edit_plan_id",
            "operation_index",
            name="uq_demo_edit_operations_plan_index",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_edit_operations_id_actor_session",
        ),
        CheckConstraint("operation_index >= 0", name="nonnegative_operation_index"),
        CheckConstraint(
            "engine IN ('RASTER','GEOMETRY','MAKEUP','GENERATIVE')",
            name="engine",
        ),
        CheckConstraint("jsonb_typeof(parameters) = 'object'", name="parameters_object"),
        CheckConstraint("jsonb_typeof(preserve) = 'array'", name="preserve_array"),
        CheckConstraint(
            "jsonb_typeof(expected_effect) = 'object'",
            name="expected_effect_object",
        ),
    )


class DemoToolRun(DemoAuthorityMixin, Base):
    __tablename__ = "demo_tool_runs"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    edit_operation_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    edit_operation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    demo_job_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "demo_job_bindings.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        index=True,
        nullable=False,
    )
    formal_job_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("job_attempts.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    input_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    output_asset_sha256: Mapped[str | None] = mapped_column(String(64))
    effect_contract: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["edit_operation_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_edit_operations.id",
                "demo_edit_operations.demo_actor_id",
                "demo_edit_operations.demo_session_id",
            ],
            name="fk_demo_tool_runs_operation_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["edit_operation_digest"],
            ["demo_edit_operations.content_digest"],
            name="fk_demo_tool_runs_edit_operation_digest_demo_edit_operations",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        UniqueConstraint(
            "formal_job_attempt_id",
            "edit_operation_id",
            name="uq_demo_tool_runs_attempt_operation",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_tool_runs_id_actor_session",
        ),
        CheckConstraint("input_asset_sha256 ~ '^[0-9a-f]{64}$'", name="input_sha_shape"),
        CheckConstraint(
            "edit_operation_digest ~ '^[0-9a-f]{64}$'",
            name="edit_operation_digest_shape",
        ),
        CheckConstraint(
            "(output_asset_id IS NULL AND output_asset_sha256 IS NULL) OR "
            "(output_asset_id IS NOT NULL AND output_asset_sha256 ~ '^[0-9a-f]{64}$')",
            name="output_shape",
        ),
        CheckConstraint(
            "jsonb_typeof(effect_contract) = 'object'",
            name="effect_contract_object",
        ),
        CheckConstraint(
            "outcome IN ('COMPLETED','REJECTED','FAILED','CANCELLED')",
            name="outcome",
        ),
        CheckConstraint(
            "(outcome = 'COMPLETED' AND output_asset_id IS NOT NULL) OR "
            "(outcome <> 'COMPLETED' AND output_asset_id IS NULL)",
            name="outcome_result_shape",
        ),
    )


class DemoVerificationResult(DemoAuthorityMixin, Base):
    __tablename__ = "demo_verification_results"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    tool_run_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True, unique=True)
    image_version_id: Mapped[str] = mapped_column(
        String(32), index=True, unique=True, nullable=False
    )
    demo_job_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "demo_job_bindings.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        index=True,
        unique=True,
        nullable=False,
    )
    output_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    output_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    verifier_version: Mapped[str] = mapped_column(String(64), nullable=False)
    config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["tool_run_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_tool_runs.id",
                "demo_tool_runs.demo_actor_id",
                "demo_tool_runs.demo_session_id",
            ],
            name="fk_demo_verification_results_tool_run_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["image_version_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_image_versions.id",
                "demo_image_versions.demo_actor_id",
                "demo_image_versions.demo_session_id",
            ],
            name="fk_demo_verification_results_image_version_owner",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("output_asset_sha256 ~ '^[0-9a-f]{64}$'", name="output_sha_shape"),
        CheckConstraint("config_digest ~ '^[0-9a-f]{64}$'", name="config_digest_shape"),
        CheckConstraint("jsonb_typeof(metrics) = 'object'", name="metrics_object"),
        CheckConstraint("jsonb_typeof(thresholds) = 'object'", name="thresholds_object"),
        CheckConstraint(
            "outcome IN ('PASS','FAIL','HUMAN_REVIEW')",
            name="outcome",
        ),
        CheckConstraint("jsonb_typeof(reason_codes) = 'array'", name="reason_codes_array"),
    )


class DemoPreferenceEvent(DemoAuthorityMixin, Base):
    __tablename__ = "demo_preference_events"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_session_id: Mapped[str | None] = mapped_column(String(32), index=True)
    event_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(48))
    target_id: Mapped[str | None] = mapped_column(String(32))
    signal: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    previous_event_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_preference_events_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "event_sequence",
            name="uq_demo_preference_events_actor_sequence",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "content_digest",
            name="uq_demo_preference_events_actor_digest",
        ),
        CheckConstraint("event_sequence > 0", name="positive_event_sequence"),
        CheckConstraint(
            "event_type IN ('EXPLICIT_STYLE_SELECTION','FEATURE_LOCKED','FEATURE_UNLOCKED',"
            "'TEMPORARY_SESSION_OVERRIDE','MAXIMUM_INTENSITY_CHANGED',"
            "'PROHIBITED_OPERATION_ADDED','IMAGE_ACCEPTED','IMAGE_REJECTED','IMAGE_ADJUSTED',"
            "'LEARNING_DISABLED','LEARNING_ENABLED','RESET','ROLLBACK','TOMBSTONE','DELETE',"
            "'SESSION_CLOSED','ACTOR_TOMBSTONED','EDITING_SESSION_CLOSED')",
            name="event_type",
        ),
        CheckConstraint(
            "source_type IN ('EXPLICIT_USER_ACTION','QUESTIONNAIRE','SELF_TRANSFER',"
            "'EDIT_FEEDBACK',"
            "'SYSTEM_LIFECYCLE')",
            name="source_type",
        ),
        CheckConstraint(
            "(target_type IS NULL AND target_id IS NULL) OR "
            "(target_type IN ('DEMO_ACTOR','BASELINE_FACE_MODEL','SELF_STATE',"
            "'DESIRED_DELTA_PROFILE','STYLE_PROFILE','REFERENCE_PROFILE','IMAGE_VERSION',"
            "'AESTHETIC_PROFILE','CONTEXT_COMPILATION') "
            "AND target_id ~ '^[0-9a-f]{32}$')",
            name="target_shape",
        ),
        CheckConstraint("jsonb_typeof(signal) = 'object'", name="signal_object"),
        CheckConstraint(
            "previous_event_digest ~ '^[0-9a-f]{64}$'",
            name="previous_event_digest_shape",
        ),
    )


class DemoAcceptedVisualEpisode(DemoAuthorityMixin, Base):
    __tablename__ = "demo_accepted_visual_episodes"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    editing_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    accepted_image_version_id: Mapped[str] = mapped_column(
        ForeignKey("demo_image_versions.id", ondelete="RESTRICT"),
        index=True,
        unique=True,
        nullable=False,
    )
    verification_result_id: Mapped[str] = mapped_column(
        ForeignKey("demo_verification_results.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    acceptance_event_id: Mapped[str] = mapped_column(
        ForeignKey("demo_preference_events.id", ondelete="RESTRICT"),
        index=True,
        unique=True,
        nullable=False,
    )
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    source_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    final_asset_id: Mapped[str] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    final_asset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    trajectory_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    context_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    instruction_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["editing_session_id", "demo_actor_id", "demo_session_id"],
            [
                "demo_editing_sessions.id",
                "demo_editing_sessions.demo_actor_id",
                "demo_editing_sessions.demo_session_id",
            ],
            name="fk_demo_accepted_visual_episodes_editing_session_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint("source_asset_sha256 ~ '^[0-9a-f]{64}$'", name="source_sha_shape"),
        CheckConstraint("final_asset_sha256 ~ '^[0-9a-f]{64}$'", name="final_sha_shape"),
        CheckConstraint("source_asset_id <> final_asset_id", name="distinct_source_final"),
        CheckConstraint(
            "jsonb_typeof(trajectory_digests) = 'array'",
            name="trajectory_digests_array",
        ),
        CheckConstraint("profile_digest ~ '^[0-9a-f]{64}$'", name="profile_digest_shape"),
        CheckConstraint("context_digest ~ '^[0-9a-f]{64}$'", name="context_digest_shape"),
        CheckConstraint(
            "instruction_digest ~ '^[0-9a-f]{64}$'",
            name="instruction_digest_shape",
        ),
    )


class DemoAestheticProfile(DemoAuthorityMixin, Base):
    __tablename__ = "demo_aesthetic_profiles"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_job_binding_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "demo_job_bindings.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        index=True,
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of_event_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compilation_watermark: Mapped[str] = mapped_column(String(64), nullable=False)
    reset_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    profile_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        UniqueConstraint(
            "demo_actor_id",
            "generation",
            name="uq_demo_aesthetic_profiles_actor_generation",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "compilation_watermark",
            "compiler_version",
            "reset_epoch",
            name="uq_demo_aesthetic_profiles_rebuild_identity",
        ),
        CheckConstraint("generation > 0", name="positive_generation"),
        CheckConstraint("as_of_event_sequence >= 0", name="nonnegative_event_sequence"),
        CheckConstraint("reset_epoch >= 0", name="nonnegative_reset_epoch"),
        CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name="watermark_shape",
        ),
        CheckConstraint(
            "jsonb_typeof(evidence_digests) = 'array'",
            name="evidence_digests_array",
        ),
        CheckConstraint(
            "jsonb_typeof(profile_payload) = 'object'",
            name="profile_payload_object",
        ),
        Index(
            "ix_demo_aesthetic_profiles_rebuild",
            "demo_actor_id",
            "compilation_watermark",
            "compiler_version",
            "reset_epoch",
        ),
    )


class DemoContextCompilation(DemoAuthorityMixin, Base):
    __tablename__ = "demo_context_compilations"

    demo_actor_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    demo_session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    aesthetic_profile_id: Mapped[str] = mapped_column(
        ForeignKey("demo_aesthetic_profiles.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    demo_job_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "demo_job_bindings.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        index=True,
        unique=True,
        nullable=False,
    )
    context_as_of_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    compilation_watermark: Mapped[str] = mapped_column(String(64), nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    current_instruction_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    rejected_evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    budgets: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    trace_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_context_compilations_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "demo_session_id",
            "context_as_of_time",
            "compiler_version",
            name="uq_demo_context_compilations_same_input",
        ),
        CheckConstraint(
            "compilation_watermark ~ '^[0-9a-f]{64}$'",
            name="watermark_shape",
        ),
        CheckConstraint(
            "current_instruction_digest ~ '^[0-9a-f]{64}$'",
            name="instruction_digest_shape",
        ),
        CheckConstraint(
            "jsonb_typeof(selected_evidence) = 'array'",
            name="selected_evidence_array",
        ),
        CheckConstraint(
            "jsonb_typeof(rejected_evidence) = 'array'",
            name="rejected_evidence_array",
        ),
        CheckConstraint("jsonb_typeof(budgets) = 'object'", name="budgets_object"),
        CheckConstraint("jsonb_typeof(trace_payload) = 'object'", name="trace_payload_object"),
        CheckConstraint("expires_at >= context_as_of_time", name="expiry_order"),
        Index(
            "ix_demo_context_compilations_actor_as_of",
            "demo_actor_id",
            "context_as_of_time",
            "compiler_version",
        ),
    )


class DemoJobBinding(DemoAuthorityMixin, Base):
    __tablename__ = "demo_job_bindings"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_session_id: Mapped[str | None] = mapped_column(String(32), index=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"), index=True, unique=True, nullable=False
    )
    endpoint_operation: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_job_bindings_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "endpoint_operation",
            "idempotency_key_hash",
            name="uq_demo_job_bindings_actor_operation_key",
        ),
        UniqueConstraint(
            "id",
            "demo_actor_id",
            "demo_session_id",
            name="uq_demo_job_bindings_id_actor_session",
        ),
        CheckConstraint(
            "endpoint_operation IN ('analysis.create','questionnaire.run.create','profile.compile',"
            "'editing_session.create','edit_plan.create','edit_plan.execute',"
            "'image_version.restore','profile.rebuild','self_transfer.execute','tool.verify',"
            "'context.compile')",
            name="endpoint_operation",
        ),
        CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$'",
            name="idempotency_key_hash_shape",
        ),
        CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'", name="request_digest_shape"),
        CheckConstraint(
            "target_type IN ('DEMO_ACTOR','DEMO_SESSION','ANALYSIS_RUN','FACE_OBSERVATION',"
            "'QUESTIONNAIRE_RUN','SELF_TRANSFER_RUN','EDITING_SESSION','IMAGE_VERSION',"
            "'EDIT_PLAN','EDIT_OPERATION','TOOL_RUN')",
            name="target_type",
        ),
        CheckConstraint("target_id ~ '^[0-9a-f]{32}$'", name="target_id_shape"),
        Index(
            "uq_demo_job_bindings_analysis_run_target",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("target_type = 'ANALYSIS_RUN'"),
        ),
    )


class DemoCommandBinding(DemoAuthorityMixin, Base):
    __tablename__ = "demo_command_bindings"

    demo_actor_id: Mapped[str] = mapped_column(
        ForeignKey("demo_actors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    demo_session_id: Mapped[str | None] = mapped_column(String(32), index=True)
    endpoint_operation: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    response_type: Mapped[str] = mapped_column(String(32), nullable=False)
    response_id: Mapped[str] = mapped_column(String(32), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        *_authority_constraints(__tablename__),
        ForeignKeyConstraint(
            ["demo_session_id", "demo_actor_id"],
            ["demo_sessions.id", "demo_sessions.demo_actor_id"],
            name="fk_demo_command_bindings_session_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "demo_actor_id",
            "endpoint_operation",
            "idempotency_key_hash",
            name="uq_demo_command_bindings_actor_operation_key",
        ),
        UniqueConstraint(
            "response_type",
            "response_id",
            name="uq_demo_command_bindings_typed_response",
        ),
        CheckConstraint(
            "endpoint_operation IN ('session.create','questionnaire.response.create',"
            "'style_feedback.create','constraint.create','image_version.feedback','job.cancel')",
            name="endpoint_operation",
        ),
        CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$'",
            name="idempotency_key_hash_shape",
        ),
        CheckConstraint("request_digest ~ '^[0-9a-f]{64}$'", name="request_digest_shape"),
        CheckConstraint(
            "response_type IN ('DEMO_SESSION','QUESTIONNAIRE_STEP',"
            "'PREFERENCE_EVENT','IDENTITY_CONSTRAINTS','JOB')",
            name="response_type",
        ),
        CheckConstraint("response_id ~ '^[0-9a-f]{32}$'", name="response_id_shape"),
        CheckConstraint("response_status IN (200,201)", name="response_status"),
    )


DEMO_TABLE_NAMES = frozenset(
    {
        "demo_actors",
        "demo_sessions",
        "demo_d02_r2_source_authorities",
        "demo_d02_r2_epoch2_admissions",
        "demo_synthetic_identities",
        "demo_analysis_runs",
        "demo_face_observations",
        "demo_face_observation_repeats",
        "demo_baseline_face_models",
        "demo_self_states",
        "demo_pair_screening_reports",
        "demo_question_banks",
        "demo_question_pairs",
        "demo_questionnaire_runs",
        "demo_questionnaire_steps",
        "demo_desired_delta_profiles",
        "demo_style_profiles",
        "demo_identity_constraints",
        "demo_profile_compilation_bundles",
        "demo_self_transfer_runs",
        "demo_self_transfer_evidence",
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
        "demo_command_bindings",
    }
)
