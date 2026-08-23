from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, create_engine, delete, inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import conv
from test_geometry_variant_authority_invariants import _canonical_source, _result_asset

from mirror_api.demo_models import (
    DEMO_TABLE_NAMES,
    DemoAcceptedVisualEpisode,
    DemoActor,
    DemoAestheticProfile,
    DemoBaselineFaceModel,
    DemoCommandBinding,
    DemoContextCompilation,
    DemoDesiredDeltaProfile,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoFaceObservation,
    DemoFaceObservationRepeat,
    DemoIdentityConstraints,
    DemoImageVersion,
    DemoJobBinding,
    DemoPairScreeningReport,
    DemoPreferenceEvent,
    DemoQuestionBank,
    DemoQuestionnaireRun,
    DemoQuestionnaireStep,
    DemoQuestionPair,
    DemoReferenceProfile,
    DemoSelfState,
    DemoSelfTransferRun,
    DemoSession,
    DemoStyleProfile,
    DemoSyntheticIdentity,
    DemoToolRun,
    DemoVerificationResult,
)
from mirror_api.models import (
    Asset,
    AssetVariant,
    Job,
    JobAttempt,
    SyntheticIdentity,
    SyntheticQARun,
    new_id,
    utcnow,
)

DEMO_REVISION = "demo_0003_d02_import_auth"
D02_DOWN_REVISION = "demo_0002_p3_p7_command_auth"
BASE_DEMO_REVISION = "demo_0001_p3_p7_core"
FORMAL_DOWN_REVISION = "0014_m5_eval_authority"
GENESIS_DIGEST = "0" * 64
_NON_AUTHORITY_COLUMNS = {
    "id",
    "schema_version",
    "canonical_payload",
    "content_digest",
    "created_at",
    "closed_at",
    "tombstoned_at",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(schema_version: str, payload: Any) -> str:
    authority = f"{schema_version}\n{_canonical_json(payload)}".encode()
    return hashlib.sha256(authority).hexdigest()


def _authority_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _build_demo_row(
    model: type[Any],
    /,
    *,
    row_id: str | None = None,
    created_at: datetime | None = None,
    authority_schema_version: str | None = None,
    **authority_fields: Any,
) -> Any:
    authority_created_at = created_at or datetime(2026, 8, 23, 3, 0, tzinfo=UTC)
    schema_version = authority_schema_version or (
        "mirror.demo/DemoSyntheticIdentity/v2"
        if model is DemoSyntheticIdentity
        else f"mirror.demo/{model.__name__}/v1"
    )
    row = model(
        id=row_id or new_id(),
        schema_version=schema_version,
        canonical_payload={},
        content_digest="0" * 64,
        created_at=authority_created_at,
        **authority_fields,
    )
    payload: dict[str, Any] = {}
    for column in row.__table__.columns:
        if column.name in _NON_AUTHORITY_COLUMNS:
            continue
        value = getattr(row, column.name)
        if value is JSON.NULL:
            payload[column.name] = None
        else:
            payload[column.name] = _authority_time(value) if isinstance(value, datetime) else value
    if model is DemoSyntheticIdentity and schema_version.endswith("/v2"):
        formal_identity_id = authority_fields.get("formal_synthetic_identity_id")
        if formal_identity_id is not None:
            source_authority_kind = "FORMAL_REFERENCE"
            source_authority_key = _digest(
                "mirror.demo/SourceAuthorityKey/v1",
                {
                    "formal_synthetic_identity_id": formal_identity_id,
                    "source_authority_kind": source_authority_kind,
                },
            )
        else:
            source_authority_kind = "DEMO_LOCAL_IMPORTED_COPY"
            source_authority_key = _digest(
                "mirror.demo/SourceAuthorityKey/v1",
                {
                    "formal_canonical_asset_id": authority_fields["formal_canonical_asset_id"],
                    "source_asset_sha256": authority_fields["formal_canonical_asset_sha256"],
                    "source_authority_kind": source_authority_kind,
                    "source_output_id": authority_fields["source_output_id"],
                    "source_receipt_digest": authority_fields["source_receipt_digest"],
                },
            )
        payload["source_authority_kind"] = source_authority_kind
        payload["source_authority_key"] = source_authority_key
    row.canonical_payload = payload
    row.content_digest = _digest(schema_version, payload)
    if model is DemoSyntheticIdentity and schema_version.endswith("/v2") and row_id is None:
        row.id = _digest(
            "mirror.demo/DemoSyntheticIdentityAdmissionEventId/v2",
            {
                "admission_action": authority_fields["admission_action"],
                "admission_config_digest": authority_fields["admission_config_digest"],
                "admission_sequence": authority_fields["admission_sequence"],
                "canonical_payload_digest": row.content_digest,
                "source_authority_key": source_authority_key,
                "source_authority_kind": source_authority_kind,
                "supersedes_id": authority_fields.get("supersedes_id"),
            },
        )[:32]
    return row


def _insert_demo_row(
    session: Session,
    model: type[Any],
    /,
    *,
    created_at: datetime | None = None,
    **authority_fields: Any,
) -> Any:
    row = _build_demo_row(
        model,
        created_at=created_at,
        **authority_fields,
    )
    session.add(row)
    session.commit()
    return row


def _formal_qa_snapshot_digest(session: Session, identity: SyntheticIdentity) -> str:
    assert identity.accepted_qa_run_id is not None
    result = session.scalar(
        text("SELECT mirror_demo_formal_qa_snapshot_digest(:qa_run_id)"),
        {"qa_run_id": identity.accepted_qa_run_id},
    )
    assert isinstance(result, str)
    return result


def _synthetic_admission_fields(
    session: Session,
    source_asset: Asset,
    formal_identity: SyntheticIdentity,
    *,
    sequence: int,
    action: str,
    supersedes_id: str | None,
    config_marker: str,
) -> dict[str, Any]:
    assert formal_identity.accepted_qa_run_id is not None
    return {
        "formal_synthetic_identity_id": formal_identity.id,
        "formal_canonical_asset_id": source_asset.id,
        "formal_canonical_asset_sha256": source_asset.sha256,
        "formal_accepted_qa_run_id": formal_identity.accepted_qa_run_id,
        "formal_accepted_qa_snapshot_digest": _formal_qa_snapshot_digest(session, formal_identity),
        "admission_sequence": sequence,
        "admission_action": action,
        "admission_config_digest": hashlib.sha256(config_marker.encode()).hexdigest(),
        "supersedes_id": supersedes_id,
    }


def _insert_job_binding(
    session: Session,
    actor: DemoActor,
    *,
    endpoint_operation: str,
    target_type: str,
    target_id: str,
    demo_session: DemoSession | None,
    request_digest: str | None = None,
) -> tuple[Job, DemoJobBinding]:
    client_key_hash = hashlib.sha256(new_id().encode()).hexdigest()
    formal_hash = hashlib.sha256(
        (
            f"mirror.demo/JobIdempotency/v1\n{actor.id}\n{endpoint_operation}\n{client_key_hash}"
        ).encode()
    ).hexdigest()
    job = Job(
        id=new_id(),
        job_type=f"demo_p3_p7.{endpoint_operation}",
        status="PENDING",
        idempotency_key_hash=formal_hash,
        request_id=f"demo-d01b-{new_id()}",
        payload={},
        owner_user_id=None,
    )
    session.add(job)
    session.commit()
    binding = _insert_demo_row(
        session,
        DemoJobBinding,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id if demo_session is not None else None,
        job_id=job.id,
        endpoint_operation=endpoint_operation,
        idempotency_key_hash=client_key_hash,
        request_digest=request_digest or hashlib.sha256(new_id().encode()).hexdigest(),
        target_type=target_type,
        target_id=target_id,
    )
    return job, binding


def _insert_command_binding(
    session: Session,
    actor: DemoActor,
    *,
    endpoint_operation: str,
    response_type: str,
    response_id: str,
    response_status: int,
    demo_session: DemoSession | None,
    idempotency_key_hash: str | None = None,
    request_digest: str | None = None,
) -> DemoCommandBinding:
    return _insert_demo_row(
        session,
        DemoCommandBinding,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id if demo_session is not None else None,
        endpoint_operation=endpoint_operation,
        idempotency_key_hash=(
            idempotency_key_hash or hashlib.sha256(new_id().encode()).hexdigest()
        ),
        request_digest=request_digest or hashlib.sha256(new_id().encode()).hexdigest(),
        response_type=response_type,
        response_id=response_id,
        response_status=response_status,
    )


def _truncate_demo_authority(session: Session) -> None:
    existing_demo_tables = set(
        session.scalars(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename LIKE 'demo_%'"
            )
        )
    )
    table_list = ", ".join(sorted(DEMO_TABLE_NAMES & existing_demo_tables))
    if table_list:
        session.execute(text(f"TRUNCATE TABLE {table_list} CASCADE"))
    session.execute(
        text("DELETE FROM asset_variants WHERE variant_type LIKE 'demo_p3_p7\\_%' ESCAPE '\\'")
    )
    session.execute(
        text(
            "DELETE FROM job_attempts WHERE job_id IN "
            "(SELECT id FROM jobs WHERE job_type LIKE 'demo_p3_p7.%')"
        )
    )
    session.execute(text("DELETE FROM jobs WHERE job_type LIKE 'demo_p3_p7.%'"))
    session.commit()


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with Session(engine) as db_session:
        _truncate_demo_authority(db_session)
        yield db_session
        db_session.rollback()
        _truncate_demo_authority(db_session)
    engine.dispose()


def _insert_actor(
    session: Session,
    *,
    actor_id: str | None = None,
    credential_key_id: str | None = None,
) -> DemoActor:
    authority_at = datetime(2026, 8, 23, 0, 0, tzinfo=UTC)
    schema_version = "mirror.demo/DemoActor/v1"
    payload = {
        "actor_kind": "AUTOMATED_TEST",
        "authority_at": _authority_time(authority_at),
        "credential_key_id": credential_key_id or new_id() + new_id(),
    }
    actor = DemoActor(
        id=actor_id or new_id(),
        schema_version=schema_version,
        canonical_payload=payload,
        content_digest=_digest(schema_version, payload),
        created_at=authority_at,
        actor_kind="AUTOMATED_TEST",
        credential_key_id=payload["credential_key_id"],
        authority_at=authority_at,
    )
    session.add(actor)
    session.commit()
    return actor


def _insert_session(session: Session, actor: DemoActor, *, config: dict[str, Any]) -> DemoSession:
    expires_at = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)
    schema_version = "mirror.demo/DemoSession/v1"
    payload = {
        "config": config,
        "context_seed": "1" * 64,
        "demo_actor_id": actor.id,
        "expires_at": _authority_time(expires_at),
    }
    demo_session = DemoSession(
        id=new_id(),
        schema_version=schema_version,
        canonical_payload=payload,
        content_digest=_digest(schema_version, payload),
        created_at=actor.created_at,
        demo_actor_id=actor.id,
        config=config,
        context_seed="1" * 64,
        expires_at=expires_at,
    )
    session.add(demo_session)
    session.commit()
    return demo_session


def _insert_preference_event(
    session: Session,
    actor: DemoActor,
    *,
    sequence: int,
    previous_digest: str,
    signal: dict[str, Any],
    demo_session: DemoSession | None = None,
    event_type: str = "EXPLICIT_STYLE_SELECTION",
    source_type: str = "EXPLICIT_USER_ACTION",
    target_type: str | None = None,
    target_id: str | None = None,
    occurred_at: datetime | None = None,
    commit: bool = True,
) -> DemoPreferenceEvent:
    event_time = occurred_at or datetime(2026, 8, 23, 1, sequence, tzinfo=UTC)
    schema_version = "mirror.demo/DemoPreferenceEvent/v1"
    payload = {
        "demo_actor_id": actor.id,
        "demo_session_id": demo_session.id if demo_session is not None else None,
        "event_sequence": sequence,
        "event_type": event_type,
        "occurred_at": _authority_time(event_time),
        "previous_event_digest": previous_digest,
        "signal": signal,
        "source_type": source_type,
        "target_id": target_id,
        "target_type": target_type,
    }
    event = DemoPreferenceEvent(
        id=new_id(),
        schema_version=schema_version,
        canonical_payload=payload,
        content_digest=_digest(schema_version, payload),
        created_at=event_time,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id if demo_session is not None else None,
        event_sequence=sequence,
        event_type=event_type,
        source_type=source_type,
        target_type=target_type,
        target_id=target_id,
        signal=signal,
        occurred_at=event_time,
        previous_event_digest=previous_digest,
    )
    session.add(event)
    if commit:
        session.commit()
    else:
        session.flush()
    return event


def _accepted_synthetic_source(session: Session) -> tuple[Asset, SyntheticIdentity]:
    """Reuse a qualified formal fixture when present; create it only on a fresh database."""
    identity = session.scalar(
        select(SyntheticIdentity)
        .join(Asset, Asset.id == SyntheticIdentity.canonical_asset_id)
        .join(SyntheticQARun, SyntheticQARun.id == SyntheticIdentity.accepted_qa_run_id)
        .where(
            SyntheticIdentity.bank_version_id.is_(None),
            SyntheticIdentity.authority_kind == "CANONICAL_QA",
            SyntheticIdentity.adult_synthetic_attested.is_(True),
            SyntheticQARun.status == "PASSED",
            SyntheticQARun.normalized_asset_id == SyntheticIdentity.canonical_asset_id,
            Asset.owner_user_id.is_(None),
            Asset.synthetic.is_(True),
            Asset.deleted_at.is_(None),
        )
    )
    if identity is not None:
        source_asset = session.get(Asset, identity.canonical_asset_id)
        assert source_asset is not None
        return source_asset, identity
    source_asset, identity, _, _ = _canonical_source(session)
    return source_asset, identity


def _result_variant(
    session: Session, source_asset: Asset, *, sha: str, variant_type: str
) -> tuple[Asset, AssetVariant]:
    result_asset = _result_asset(session, source_asset, sha=sha)
    variant = AssetVariant(
        id=new_id(),
        source_asset_id=source_asset.id,
        result_asset_id=result_asset.id,
        variant_type=variant_type,
    )
    session.add(variant)
    session.commit()
    return result_asset, variant


def _d02_result_variant(
    session: Session, source_asset: Asset, *, marker: str
) -> tuple[Asset, AssetVariant]:
    result_asset = Asset(
        id=new_id(),
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key=f"demo-d02-selected/{marker}/{new_id()}",
        mime_type=source_asset.mime_type,
        byte_size=source_asset.byte_size,
        width=source_asset.width,
        height=source_asset.height,
        sha256=hashlib.sha256(f"d02-result/{marker}/{new_id()}".encode()).hexdigest(),
        synthetic=True,
        is_ai_generated=False,
        is_ai_modified=True,
    )
    variant = AssetVariant(
        id=new_id(),
        source_asset_id=source_asset.id,
        result_asset_id=result_asset.id,
        variant_type="demo_p3_p7_geometry_v1",
    )
    session.add_all((result_asset, variant))
    return result_asset, variant


def _insert_local_d02_identity(
    session: Session, *, marker: str
) -> tuple[Asset, DemoSyntheticIdentity]:
    source_asset = Asset(
        id=new_id(),
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key=f"demo-d02-recovered/{marker}/{new_id()}",
        mime_type="image/png",
        byte_size=68,
        width=1,
        height=1,
        sha256=hashlib.sha256(f"d02-source/{marker}/{new_id()}".encode()).hexdigest(),
        synthetic=True,
        is_ai_generated=True,
        is_ai_modified=False,
    )
    session.add(source_asset)
    session.commit()

    source_output_id = f"d02-source-{marker}"
    source_receipt_digest = hashlib.sha256(f"receipt/{marker}".encode()).hexdigest()
    source_authority_digest = hashlib.sha256(f"authority/{marker}".encode()).hexdigest()
    source_qa_snapshot_digest = hashlib.sha256(f"qa/{marker}".encode()).hexdigest()
    source_landmark_digest = hashlib.sha256(f"landmarks/{marker}".encode()).hexdigest()
    source_provenance_digest = hashlib.sha256(f"provenance/{marker}".encode()).hexdigest()
    qa_policy_digest = hashlib.sha256(f"qa-policy/{marker}".encode()).hexdigest()
    dimensions = (
        "cheekbone_width",
        "chin_height",
        "eye_spacing",
        "jaw_width",
        "mouth_width",
        "nose_width",
    )
    raw_entries = [
        {
            "dimension_key": dimension_key,
            "support_state": "SUPPORTED",
            "raw_value_fixed18": "0.100000000000000000",
            "raw_confidence_fixed18": "0.900000000000000000",
            "raw_reliability_fixed18": "0.900000000000000000",
            "unsupported_reason": None,
        }
        for dimension_key in dimensions
    ]
    projection_entries = [
        {
            "dimension_key": dimension_key,
            "support_state": "SUPPORTED",
            "value_ppm": 100_000,
            "unit": "FACE_HEIGHT_PPM",
            "confidence_ppm": 900_000,
            "reliability_ppm": 900_000,
            "unsupported_reason": None,
        }
        for dimension_key in dimensions
    ]
    source_manifest_digest = "eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4"
    dimension_manifest_digest = "d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a"
    raw_measurement_authority = {
        "measurement_version": "demo-d02-face-height-normalized-measurement-v1",
        "decimal_serialization_version": "demo-d02-decimal-fixed18-v1",
        "source_p2_candidate_manifest_content_digest": source_manifest_digest,
        "dimension_authority_manifest_content_digest": dimension_manifest_digest,
        "ordered_entries": raw_entries,
    }
    raw_measurement_authority_digest = _digest(
        "mirror.demo/D02RawMeasurementAuthority/v1", raw_measurement_authority
    )
    source_measurement_projection = {
        "measurement_version": "demo-d02-face-height-normalized-measurement-v1",
        "measurement_projection_version": "demo-d02-morphology-projection-v1",
        "measurement_quantization_version": "demo-d02-round-half-even-ppm-v1",
        "source_p2_candidate_manifest_content_digest": source_manifest_digest,
        "dimension_authority_manifest_content_digest": dimension_manifest_digest,
        "ordered_entries": projection_entries,
    }
    source_measurement_projection_digest = _digest(
        "mirror.demo/D02MorphologyProjection/v1", source_measurement_projection
    )
    source_fact_snapshot = {
        "source_output_id": source_output_id,
        "source_asset_sha256": source_asset.sha256,
        "source_asset_byte_size": source_asset.byte_size,
        "source_asset_mime_type": source_asset.mime_type,
        "source_asset_width": source_asset.width,
        "source_asset_height": source_asset.height,
        "source_receipt_digest": source_receipt_digest,
        "source_authority_digest": source_authority_digest,
        "qa_policy_digest": qa_policy_digest,
        "source_qa_snapshot_digest": source_qa_snapshot_digest,
        "source_landmark_digest": source_landmark_digest,
        "source_measurement_digest": raw_measurement_authority_digest,
        "source_provenance_digest": source_provenance_digest,
        "source_measurement_projection": source_measurement_projection,
        "source_measurement_projection_digest": source_measurement_projection_digest,
        "raw_measurement_authority": raw_measurement_authority,
        "raw_measurement_authority_digest": raw_measurement_authority_digest,
        "adult_synthetic_attested": True,
        "original_formal_identity_id_status": "UNKNOWN_REDACTED_NOT_RECOVERED",
        "measurement_projection_version": "demo-d02-morphology-projection-v1",
        "measurement_quantization_version": "demo-d02-round-half-even-ppm-v1",
        "source_p2_candidate_manifest_content_digest": source_manifest_digest,
        "dimension_authority_manifest_content_digest": dimension_manifest_digest,
    }
    source_fact_snapshot_digest = _digest(
        "mirror.demo/RecoveredSyntheticIdentityFacts/v2", source_fact_snapshot
    )
    admission = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        formal_synthetic_identity_id=None,
        formal_canonical_asset_id=source_asset.id,
        formal_canonical_asset_sha256=source_asset.sha256,
        formal_accepted_qa_run_id=None,
        formal_accepted_qa_snapshot_digest=None,
        admission_sequence=1,
        admission_action="ADMIT",
        admission_config_digest=hashlib.sha256(f"admission-config/{marker}".encode()).hexdigest(),
        supersedes_id=None,
        source_output_id=source_output_id,
        source_receipt_digest=source_receipt_digest,
        source_authority_digest=source_authority_digest,
        source_qa_snapshot_digest=source_qa_snapshot_digest,
        source_landmark_digest=source_landmark_digest,
        source_measurement_digest=raw_measurement_authority_digest,
        source_provenance_digest=source_provenance_digest,
        source_fact_snapshot=source_fact_snapshot,
        source_fact_snapshot_digest=source_fact_snapshot_digest,
        source_measurement_projection=source_measurement_projection,
        source_measurement_projection_digest=source_measurement_projection_digest,
        original_formal_identity_id_status="UNKNOWN_REDACTED_NOT_RECOVERED",
        adult_synthetic_attested=True,
        importer_version="demo-d02-identity-importer-v2",
        import_config_digest=hashlib.sha256(f"import-config/{marker}".encode()).hexdigest(),
    )
    return source_asset, admission


def _insert_d02_question_bank(
    session: Session,
    primary_source: Asset,
    primary_admission: DemoSyntheticIdentity,
) -> tuple[DemoQuestionBank, DemoQuestionPair]:
    marker = new_id()

    source_authorities: list[tuple[Asset, DemoSyntheticIdentity]] = [
        (primary_source, primary_admission)
    ]
    for source_index in range(1, 4):
        source_asset, admission = _insert_local_d02_identity(
            session, marker=f"{marker}-{source_index}"
        )
        source_authorities.append((source_asset, admission))
    source_authorities.sort(
        key=lambda authority: (
            str(authority[1].source_authority_key),
            authority[1].id,
        )
    )

    selected_dimensions = ("jaw_width", "chin_height")
    magnitudes = (15_000, 30_000)

    def evidence_digest(label: str) -> str:
        return hashlib.sha256(f"d02/{marker}/{label}".encode()).hexdigest()

    selected_records: list[dict[str, Any]] = []
    for source_index, (_, admission) in enumerate(source_authorities):
        for dimension_key in selected_dimensions:
            for magnitude_ppm in magnitudes:
                selected_records.append(
                    {
                        "dimension_key": dimension_key,
                        "magnitude_ppm": magnitude_ppm,
                        "pair_screening_record_digest": evidence_digest(
                            f"pair/{source_index}/{dimension_key}/{magnitude_ppm}"
                        ),
                        "source_admission_event_id": admission.id,
                    }
                )

    ordered_source_manifest = [
        {
            "source_admission_event_id": admission.id,
            "source_asset_id": source_asset.id,
            "source_asset_sha256": source_asset.sha256,
            "source_authority_key": admission.source_authority_key,
        }
        for source_asset, admission in source_authorities
    ]
    ordered_case_manifest = [
        {"case_index": index, "case_digest": evidence_digest(f"case/{index}")}
        for index in range(48)
    ]
    dimension_eligibility = [
        {
            "dimension_key": dimension_key,
            "priority_index": priority_index,
            "eligible": priority_index <= 2,
            "sixteen_side_gate_digest": evidence_digest(f"dimension/{dimension_key}/sixteen-side"),
            "eight_pair_gate_digest": evidence_digest(f"dimension/{dimension_key}/eight-pair"),
            "failure_reasons": [] if priority_index <= 2 else ["NOT_SELECTED"],
        }
        for priority_index, dimension_key in enumerate(
            ("jaw_width", "chin_height", "eye_spacing"), start=1
        )
    ]
    source_manifest_digest = _digest(
        "mirror.demo/D02SourceAuthorityManifest/v1", ordered_source_manifest
    )
    case_manifest_digest = _digest("mirror.demo/D02GeometryCaseManifest/v1", ordered_case_manifest)
    report_digests = {
        "source_manifest_digest": source_manifest_digest,
        "case_manifest_digest": case_manifest_digest,
        "screening_policy_digest": evidence_digest("screening-policy"),
        "runtime_manifest_digest": evidence_digest("runtime-manifest"),
        "vision_model_manifest_digest": evidence_digest("vision-model-manifest"),
        "topology_digest": evidence_digest("topology"),
        "measurement_config_digest": evidence_digest("measurement-config"),
        "manual_review_policy_digest": evidence_digest("manual-review-policy"),
        "duplicate_policy_digest": evidence_digest("duplicate-policy"),
        "phash_implementation_digest": evidence_digest("phash-implementation"),
    }
    report_payload: dict[str, Any] = {
        "schema_and_policy": report_digests,
        "ordered_source_manifest": ordered_source_manifest,
        "ordered_case_manifest": ordered_case_manifest,
        "source_m3_repeat_evidence": [evidence_digest(f"source-m3/{index}") for index in range(12)],
        "m4_repeat_evidence": [evidence_digest(f"m4/{index}") for index in range(96)],
        "result_m3_repeat_evidence": [
            evidence_digest(f"result-m3/{index}") for index in range(144)
        ],
        "measurement_gate_evidence": [
            evidence_digest(f"measurement-gate/{index}") for index in range(48)
        ],
        "decode_structure_immutability_evidence": [
            evidence_digest(f"decode/{index}") for index in range(48)
        ],
        "manual_review_evidence": [evidence_digest(f"manual/{index}") for index in range(48)],
        "exact_duplicate_evidence": {
            "image_records": [evidence_digest(f"image-record/{index}") for index in range(52)],
            "exact_sha_gate_passed": True,
        },
        "phash_observation_evidence": {
            "implementation_digest": report_digests["phash_implementation_digest"],
            "comparisons": [evidence_digest(f"phash/{index}") for index in range(1326)],
        },
        "pair_quality_evidence": [evidence_digest(f"pair-quality/{index}") for index in range(24)],
        "dimension_eligibility": dimension_eligibility,
        "fixed_priority_selection_trace": [
            {"dimension_key": entry["dimension_key"], "selected": index < 2}
            for index, entry in enumerate(dimension_eligibility)
        ],
        "selected_pair_manifest": selected_records,
        "network_and_runtime_boundary": {
            "public_internet_egress": "DENIED",
            "localhost_and_docker_internal_network": True,
            "production_provider_calls": 0,
            "runtime_generation_calls": 0,
        },
    }
    report_schema = "mirror.demo/D02PairScreeningReport/v1"
    report_digest = _digest(report_schema, report_payload)
    selected_pair_manifest_digest = _digest(
        "mirror.demo/D02SelectedPairManifest/v1", selected_records
    )
    report = _build_demo_row(
        DemoPairScreeningReport,
        row_id=_digest(
            "mirror.demo/D02PairScreeningReportId/v1",
            {"report_digest": report_digest},
        )[:32],
        authority_schema_version=report_schema,
        source_manifest_digest=report_digests["source_manifest_digest"],
        case_manifest_digest=report_digests["case_manifest_digest"],
        screening_policy_digest=report_digests["screening_policy_digest"],
        runtime_manifest_digest=report_digests["runtime_manifest_digest"],
        vision_model_manifest_digest=report_digests["vision_model_manifest_digest"],
        topology_digest=report_digests["topology_digest"],
        measurement_config_digest=report_digests["measurement_config_digest"],
        manual_review_policy_digest=report_digests["manual_review_policy_digest"],
        duplicate_policy_digest=report_digests["duplicate_policy_digest"],
        phash_implementation_digest=report_digests["phash_implementation_digest"],
        report_payload=report_payload,
        report_digest=report_digest,
        status="PASSED",
        source_count=4,
        case_count=48,
        source_m3_repeat_count=12,
        m4_execution_count=96,
        result_m3_repeat_count=144,
        manual_decision_count=48,
        exact_sha_record_count=52,
        phash_comparison_count=1326,
        candidate_pair_count=24,
        selected_pair_count=16,
        selected_result_side_count=32,
        eligible_dimension_keys=list(selected_dimensions),
        selected_dimension_keys=list(selected_dimensions),
        selected_pair_manifest_digest=selected_pair_manifest_digest,
    )
    session.add(report)
    session.commit()

    algorithm_config_digest = evidence_digest("algorithm-config")
    dimension_manifest = {
        "schema_version": "mirror.demo/D02QuestionBankDimensionManifest/v1",
        "screening_report_id": report.id,
        "screening_report_digest": report.report_digest,
        "source_manifest_digest": report.source_manifest_digest,
        "source_p2_candidate_manifest_content_digest": (
            "eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4"
        ),
        "dimension_authority_manifest_content_digest": (
            "d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a"
        ),
        "selected_pair_manifest_digest": selected_pair_manifest_digest,
        "selected_dimensions": [
            {
                "dimension_key": entry["dimension_key"],
                "priority_index": entry["priority_index"],
                "sixteen_side_gate_digest": entry["sixteen_side_gate_digest"],
                "eight_pair_gate_digest": entry["eight_pair_gate_digest"],
            }
            for entry in dimension_eligibility[:2]
        ],
    }
    bank_id = _digest(
        "mirror.demo/D02QuestionBankId/v1",
        {
            "algorithm_config_digest": algorithm_config_digest,
            "screening_report_digest": report.report_digest,
            "screening_report_id": report.id,
            "selected_pair_manifest_digest": selected_pair_manifest_digest,
        },
    )[:32]
    bank = _build_demo_row(
        DemoQuestionBank,
        row_id=bank_id,
        authority_schema_version="mirror.demo/DemoQuestionBank/v2",
        version=f"fixture-bank-{marker}",
        algorithm_config_digest=algorithm_config_digest,
        routing_version="fixture-route-v2",
        stopping_version="fixture-stop-v2",
        neighborhood_version="fixture-neighborhood-v2",
        pair_manifest_digest=selected_pair_manifest_digest,
        dimension_manifest=dimension_manifest,
        screening_report_id=report.id,
        screening_report_digest=report.report_digest,
    )

    pair_materials: list[tuple[dict[str, Any], Asset, AssetVariant, Asset, AssetVariant]] = []
    for pair_index, selected_record in enumerate(selected_records):
        source_asset, _ = source_authorities[pair_index // 4]
        left_asset, left_variant = _d02_result_variant(
            session, source_asset, marker=f"{marker}/{pair_index}/left"
        )
        right_asset, right_variant = _d02_result_variant(
            session, source_asset, marker=f"{marker}/{pair_index}/right"
        )
        pair_materials.append(
            (selected_record, left_asset, left_variant, right_asset, right_variant)
        )
    session.commit()

    pairs: list[DemoQuestionPair] = []
    for pair_index, material in enumerate(pair_materials):
        selected_record, left_asset, left_variant, right_asset, right_variant = material
        source_asset, admission = source_authorities[pair_index // 4]
        dimension_key = str(selected_record["dimension_key"])
        magnitude_ppm = int(selected_record["magnitude_ppm"])
        magnitude_fixed18 = f"0.{magnitude_ppm:06d}{'0' * 12}"

        def side_payload(
            *,
            side: str,
            result_asset: Asset,
            result_variant: AssetVariant,
            pair_index_value: int,
            source_asset_value: Asset,
            magnitude_ppm_value: int,
            magnitude_fixed18_value: str,
        ) -> dict[str, Any]:
            requested_direction = "DECREASE" if side == "left" else "INCREASE"
            signed_delta = -magnitude_ppm_value if side == "left" else magnitude_ppm_value
            return {
                "case_id": new_id(),
                "case_specification_digest": evidence_digest(
                    f"case-spec/{pair_index_value}/{side}"
                ),
                "result_asset_id": result_asset.id,
                "result_asset_sha256": result_asset.sha256,
                "asset_variant_id": result_variant.id,
                "asset_variant_type": "demo_p3_p7_geometry_v1",
                "lineage_digest": _digest(
                    "mirror.demo/D02AssetVariantLineage/v1",
                    {
                        "result_asset_id": result_asset.id,
                        "result_asset_sha256": result_asset.sha256,
                        "source_asset_id": source_asset_value.id,
                        "source_asset_sha256": source_asset_value.sha256,
                        "variant_type": "demo_p3_p7_geometry_v1",
                    },
                ),
                "requested_direction": requested_direction,
                "requested_magnitude_ppm": magnitude_ppm_value,
                "raw_signed_target_delta_fixed18": (
                    f"-{magnitude_fixed18_value}" if side == "left" else magnitude_fixed18_value
                ),
                "raw_target_absolute_delta_fixed18": magnitude_fixed18_value,
                "raw_max_control_drift_fixed18": "0.000000000000000000",
                "measured_signed_delta_ppm": signed_delta,
                "drift_ppm": 0,
                "automated_gate_digest": evidence_digest(
                    f"automated-gate/{pair_index_value}/{side}"
                ),
                "manual_decision_digest": evidence_digest(
                    f"manual-decision/{pair_index_value}/{side}"
                ),
                "side_quality_component_ppm": 900_000,
            }

        qa_payload = {
            "schema_version": "mirror.demo/D02QuestionPairQAPayload/v1",
            "screening_report_id": report.id,
            "screening_report_digest": report.report_digest,
            "pair_screening_record_digest": selected_record["pair_screening_record_digest"],
            "source_authority_key": admission.source_authority_key,
            "source_admission_event_id": admission.id,
            "source_asset": {"id": source_asset.id, "sha256": source_asset.sha256},
            "dimension_key": dimension_key,
            "magnitude_ppm": magnitude_ppm,
            "left": side_payload(
                side="left",
                result_asset=left_asset,
                result_variant=left_variant,
                pair_index_value=pair_index,
                source_asset_value=source_asset,
                magnitude_ppm_value=magnitude_ppm,
                magnitude_fixed18_value=magnitude_fixed18,
            ),
            "right": side_payload(
                side="right",
                result_asset=right_asset,
                result_variant=right_variant,
                pair_index_value=pair_index,
                source_asset_value=source_asset,
                magnitude_ppm_value=magnitude_ppm,
                magnitude_fixed18_value=magnitude_fixed18,
            ),
            "pair_quality_ppm": 900_000,
            "lock_conclusion": "COMPATIBLE",
            "lock_policy_digest": evidence_digest(f"lock-policy/{pair_index}"),
        }
        pair_id = _digest(
            "mirror.demo/D02QuestionPairId/v1",
            {
                "dimension_key": dimension_key,
                "magnitude_ppm": magnitude_ppm,
                "pair_screening_record_digest": selected_record["pair_screening_record_digest"],
                "question_bank_id": bank.id,
                "source_admission_event_id": admission.id,
            },
        )[:32]
        pairs.append(
            _build_demo_row(
                DemoQuestionPair,
                row_id=pair_id,
                authority_schema_version="mirror.demo/DemoQuestionPair/v2",
                question_bank_id=bank.id,
                demo_synthetic_identity_id=admission.id,
                source_asset_id=source_asset.id,
                source_asset_sha256=source_asset.sha256,
                left_asset_id=left_asset.id,
                left_asset_sha256=left_asset.sha256,
                right_asset_id=right_asset.id,
                right_asset_sha256=right_asset.sha256,
                left_asset_variant_id=left_variant.id,
                right_asset_variant_id=right_variant.id,
                dimension_key=dimension_key,
                magnitude_ppm=magnitude_ppm,
                left_delta_ppm=-magnitude_ppm,
                right_delta_ppm=magnitude_ppm,
                pair_quality_ppm=900_000,
                qa_payload=qa_payload,
                screening_report_id=report.id,
                screening_report_digest=report.report_digest,
            )
        )
    session.add(bank)
    session.add_all(pairs)
    session.commit()
    return bank, pairs[0]


def _insert_episode(
    session: Session, graph: dict[str, Any], trajectory_digests: list[str]
) -> DemoAcceptedVisualEpisode:
    actor = graph["actor"]
    demo_session = graph["session"]
    editing_session = graph["editing_session"]
    image0 = graph["image0"]
    image1 = graph["image1"]
    verification = graph["verification"]
    accepted_event = graph["accepted_event"]
    desired_delta = graph["desired_delta"]
    return _insert_demo_row(
        session,
        DemoAcceptedVisualEpisode,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        editing_session_id=editing_session.id,
        accepted_image_version_id=image1.id,
        verification_result_id=verification.id,
        acceptance_event_id=accepted_event.id,
        source_asset_id=image0.source_asset_id,
        source_asset_sha256=graph["source_asset"].sha256,
        final_asset_id=image1.result_asset_id,
        final_asset_sha256=graph["image1_asset"].sha256,
        trajectory_digests=trajectory_digests,
        profile_digest=desired_delta.content_digest,
        context_digest=editing_session.context_digest,
        instruction_digest=editing_session.instruction_digest,
    )


def _prepare_followup_execution(
    session: Session,
    graph: dict[str, Any],
    *,
    image_overrides: dict[str, Any] | None = None,
    verification_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actor = graph["actor"]
    demo_session = graph["session"]
    editing_session = graph["editing_session"]
    parent_image = graph["image1"]
    parent_asset = graph["image1_asset"]
    desired_delta = graph["desired_delta"]
    style = graph["style"]
    constraints = graph["constraints"]
    operation_spec: dict[str, Any] = {
        "engine": "RASTER",
        "operation_type": "fixture_contrast",
        "parameters": {"contrast_ppm": 25_000},
        "preserve": ["identity"],
        "expected_effect": {"contrast_ppm": 25_000},
    }
    plan_fields = {
        "demo_actor_id": actor.id,
        "demo_session_id": demo_session.id,
        "editing_session_id": editing_session.id,
        "input_image_version_id": parent_image.id,
        "plan_version": 2,
        "desired_delta_profile_digest": desired_delta.content_digest,
        "style_profile_digest": style.content_digest,
        "identity_constraints_digest": constraints.content_digest,
        "instruction_digest": editing_session.instruction_digest,
        "planner_version": "fixture-planner-v1",
        "tool_registry_version": editing_session.tool_registry_version,
    }
    request_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="REQUEST",
        request_plan_id=None,
        operation_specs=[],
    )
    result_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="RESULT",
        request_plan_id=request_plan.id,
        operation_specs=[operation_spec],
    )
    operation = _insert_demo_row(
        session,
        DemoEditOperation,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        edit_plan_id=result_plan.id,
        operation_index=0,
        engine=operation_spec["engine"],
        operation_type=operation_spec["operation_type"],
        parameters=operation_spec["parameters"],
        preserve=operation_spec["preserve"],
        expected_effect=operation_spec["expected_effect"],
    )
    execution_job, execution_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="edit_plan.execute",
        target_type="EDIT_PLAN",
        target_id=result_plan.id,
        demo_session=demo_session,
    )
    attempt = JobAttempt(
        id=new_id(),
        job_id=execution_job.id,
        attempt=1,
        status="PENDING",
        started_at=utcnow(),
    )
    session.add(attempt)
    session.commit()
    output_asset, output_variant = _result_variant(
        session,
        parent_asset,
        sha=hashlib.sha256(new_id().encode()).hexdigest(),
        variant_type="demo_p3_p7_followup_result",
    )
    tool_run = _insert_demo_row(
        session,
        DemoToolRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        edit_operation_id=operation.id,
        edit_operation_digest=operation.content_digest,
        demo_job_binding_id=execution_binding.id,
        formal_job_attempt_id=attempt.id,
        tool_name="fixture-contrast",
        tool_version="fixture-contrast-v1",
        input_asset_id=parent_asset.id,
        input_asset_sha256=parent_asset.sha256,
        output_asset_id=output_asset.id,
        output_asset_sha256=output_asset.sha256,
        effect_contract={"identity_preserved": 1},
        outcome="COMPLETED",
    )
    _, verification_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="tool.verify",
        target_type="TOOL_RUN",
        target_id=tool_run.id,
        demo_session=demo_session,
    )
    image_id = new_id()
    verification_fields: dict[str, Any] = {
        "demo_actor_id": actor.id,
        "demo_session_id": demo_session.id,
        "tool_run_id": tool_run.id,
        "image_version_id": image_id,
        "demo_job_binding_id": verification_binding.id,
        "output_asset_id": output_asset.id,
        "output_asset_sha256": output_asset.sha256,
        "verifier_version": "fixture-verify-v1",
        "config_digest": "f" * 64,
        "metrics": {"identity_ppm": 1_000_000},
        "thresholds": {"identity_min_ppm": 900_000},
        "outcome": "PASS",
        "reason_codes": [],
    }
    if verification_overrides:
        verification_fields.update(verification_overrides)
    verification = _build_demo_row(DemoVerificationResult, **verification_fields)
    image_fields: dict[str, Any] = {
        "demo_actor_id": actor.id,
        "demo_session_id": demo_session.id,
        "editing_session_id": editing_session.id,
        "sequence": 2,
        "parent_version_id": parent_image.id,
        "source_asset_id": parent_asset.id,
        "source_asset_sha256": parent_asset.sha256,
        "result_asset_id": output_asset.id,
        "result_asset_sha256": output_asset.sha256,
        "result_asset_variant_id": output_variant.id,
        "version_kind": "EDITED",
        "plan_digest": result_plan.content_digest,
        "tool_run_digest": tool_run.content_digest,
        "verifier_digest": verification.content_digest,
    }
    if image_overrides:
        image_fields.update(image_overrides)
    image = _build_demo_row(DemoImageVersion, row_id=image_id, **image_fields)
    return {
        "image": image,
        "verification": verification,
        "request_plan": request_plan,
        "result_plan": result_plan,
        "operation": operation,
        "tool_run": tool_run,
        "output_asset": output_asset,
        "output_variant": output_variant,
        "execution_binding": execution_binding,
        "attempt": attempt,
    }


def _prepare_execution_step(
    session: Session,
    graph: dict[str, Any],
    *,
    parent_image: DemoImageVersion,
    parent_asset: Asset,
    result_plan: DemoEditPlan,
    operation: DemoEditOperation,
    execution_binding: DemoJobBinding,
    attempt: JobAttempt,
    sequence: int,
    marker: str,
    version_kind: str = "EDITED",
    verification_outcome: str = "PASS",
) -> dict[str, Any]:
    actor = graph["actor"]
    demo_session = graph["session"]
    editing_session = graph["editing_session"]
    output_asset, output_variant = _result_variant(
        session,
        parent_asset,
        sha=hashlib.sha256(f"{marker}-{new_id()}".encode()).hexdigest(),
        variant_type=f"demo_p3_p7_{marker}",
    )
    tool_run = _insert_demo_row(
        session,
        DemoToolRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        edit_operation_id=operation.id,
        edit_operation_digest=operation.content_digest,
        demo_job_binding_id=execution_binding.id,
        formal_job_attempt_id=attempt.id,
        tool_name=f"fixture-{marker}",
        tool_version="fixture-step-v1",
        input_asset_id=parent_asset.id,
        input_asset_sha256=parent_asset.sha256,
        output_asset_id=output_asset.id,
        output_asset_sha256=output_asset.sha256,
        effect_contract={"identity_preserved": 1},
        outcome="COMPLETED",
    )
    _, verification_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="tool.verify",
        target_type="TOOL_RUN",
        target_id=tool_run.id,
        demo_session=demo_session,
    )
    image_id = new_id()
    verification = _build_demo_row(
        DemoVerificationResult,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        tool_run_id=tool_run.id,
        image_version_id=image_id,
        demo_job_binding_id=verification_binding.id,
        output_asset_id=output_asset.id,
        output_asset_sha256=output_asset.sha256,
        verifier_version="fixture-verify-v1",
        config_digest=hashlib.sha256(f"verify-{marker}".encode()).hexdigest(),
        metrics={"identity_ppm": 1_000_000},
        thresholds={"identity_min_ppm": 900_000},
        outcome=verification_outcome,
        reason_codes=[] if verification_outcome == "PASS" else ["fixture_rejected"],
    )
    image = _build_demo_row(
        DemoImageVersion,
        row_id=image_id,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        editing_session_id=editing_session.id,
        sequence=sequence,
        parent_version_id=parent_image.id,
        source_asset_id=parent_asset.id,
        source_asset_sha256=parent_asset.sha256,
        result_asset_id=output_asset.id,
        result_asset_sha256=output_asset.sha256,
        result_asset_variant_id=output_variant.id,
        version_kind=version_kind,
        plan_digest=result_plan.content_digest,
        tool_run_digest=tool_run.content_digest,
        verifier_digest=verification.content_digest,
    )
    return {
        "image": image,
        "verification": verification,
        "tool_run": tool_run,
        "output_asset": output_asset,
        "output_variant": output_variant,
    }


def _commit_execution_pair(session: Session, step: dict[str, Any]) -> None:
    session.add(step["image"])
    session.flush()
    session.add(step["verification"])
    session.commit()


def _insert_two_operation_execution(session: Session, graph: dict[str, Any]) -> dict[str, Any]:
    actor = graph["actor"]
    demo_session = graph["session"]
    editing_session = graph["editing_session"]
    operation_specs: list[dict[str, Any]] = [
        {
            "engine": "RASTER",
            "operation_type": "fixture_exposure",
            "parameters": {"exposure_ppm": 15_000},
            "preserve": ["identity"],
            "expected_effect": {"exposure_ppm": 15_000},
        },
        {
            "engine": "RASTER",
            "operation_type": "fixture_saturation",
            "parameters": {"saturation_ppm": 20_000},
            "preserve": ["identity"],
            "expected_effect": {"saturation_ppm": 20_000},
        },
    ]
    plan_fields = {
        "demo_actor_id": actor.id,
        "demo_session_id": demo_session.id,
        "editing_session_id": editing_session.id,
        "input_image_version_id": graph["image1"].id,
        "plan_version": 2,
        "desired_delta_profile_digest": graph["desired_delta"].content_digest,
        "style_profile_digest": graph["style"].content_digest,
        "identity_constraints_digest": graph["constraints"].content_digest,
        "instruction_digest": editing_session.instruction_digest,
        "planner_version": "fixture-planner-v1",
        "tool_registry_version": editing_session.tool_registry_version,
    }
    request_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="REQUEST",
        request_plan_id=None,
        operation_specs=[],
    )
    result_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="RESULT",
        request_plan_id=request_plan.id,
        operation_specs=operation_specs,
    )
    operations = [
        _insert_demo_row(
            session,
            DemoEditOperation,
            demo_actor_id=actor.id,
            demo_session_id=demo_session.id,
            edit_plan_id=result_plan.id,
            operation_index=index,
            engine=operation_spec["engine"],
            operation_type=operation_spec["operation_type"],
            parameters=operation_spec["parameters"],
            preserve=operation_spec["preserve"],
            expected_effect=operation_spec["expected_effect"],
        )
        for index, operation_spec in enumerate(operation_specs)
    ]
    execution_job, execution_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="edit_plan.execute",
        target_type="EDIT_PLAN",
        target_id=result_plan.id,
        demo_session=demo_session,
    )
    attempt = JobAttempt(
        id=new_id(),
        job_id=execution_job.id,
        attempt=1,
        status="PENDING",
        started_at=utcnow(),
    )
    session.add(attempt)
    session.commit()
    first_step = _prepare_execution_step(
        session,
        graph,
        parent_image=graph["image1"],
        parent_asset=graph["image1_asset"],
        result_plan=result_plan,
        operation=operations[0],
        execution_binding=execution_binding,
        attempt=attempt,
        sequence=2,
        marker="multi_operation_0",
    )
    _commit_execution_pair(session, first_step)
    second_step = _prepare_execution_step(
        session,
        graph,
        parent_image=first_step["image"],
        parent_asset=first_step["output_asset"],
        result_plan=result_plan,
        operation=operations[1],
        execution_binding=execution_binding,
        attempt=attempt,
        sequence=3,
        marker="multi_operation_1",
    )
    _commit_execution_pair(session, second_step)
    return {
        "request_plan": request_plan,
        "result_plan": result_plan,
        "operations": operations,
        "execution_binding": execution_binding,
        "attempt": attempt,
        "first_step": first_step,
        "second_step": second_step,
    }


def _insert_full_demo_graph(session: Session, *, include_episode: bool = True) -> dict[str, Any]:
    """Insert one valid authority lineage spanning every Demo table."""

    def digest(character: str) -> str:
        return character * 64

    actor = _insert_actor(session)
    demo_session = _insert_session(session, actor, config={"graph": 1})
    source_asset, formal_identity = _accepted_synthetic_source(session)
    synthetic_identity = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        formal_synthetic_identity_id=formal_identity.id,
        formal_canonical_asset_id=source_asset.id,
        formal_canonical_asset_sha256=source_asset.sha256,
        formal_accepted_qa_run_id=formal_identity.accepted_qa_run_id,
        formal_accepted_qa_snapshot_digest=_formal_qa_snapshot_digest(session, formal_identity),
        admission_sequence=1,
        admission_action="ADMIT",
        admission_config_digest=digest("1"),
        supersedes_id=None,
    )
    observation = _insert_demo_row(
        session,
        DemoFaceObservation,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        demo_synthetic_identity_id=synthetic_identity.id,
        source_asset_id=source_asset.id,
        source_asset_sha256=source_asset.sha256,
        analyzer_version="fixture-analyzer-v1",
        runtime_manifest_digest=digest("2"),
        config_digest=digest("3"),
        repeat_count=3,
        observation_state="SUPPORTED",
        unsupported_reason=None,
    )
    repeats = [
        _insert_demo_row(
            session,
            DemoFaceObservationRepeat,
            demo_actor_id=actor.id,
            demo_session_id=demo_session.id,
            observation_id=observation.id,
            repeat_index=index,
            runtime_manifest_digest=digest("2"),
            model_manifest_digest=digest("4"),
            landmarks=[0] * 478,
            pose={"yaw_ppm": 0},
            quality={"score_ppm": 1_000_000},
            measurements={"jaw_width_ppm": 0},
        )
        for index in range(1, 4)
    ]
    baseline = _insert_demo_row(
        session,
        DemoBaselineFaceModel,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        observation_id=observation.id,
        version=1,
        aggregation_version="fixture-aggregate-v1",
        measurement_version="fixture-measure-v1",
        ordered_repeat_digests=[repeat.content_digest for repeat in repeats],
        measurements={"jaw_width_ppm": 0},
        reliability={"jaw_width_ppm": 1_000_000},
        uncertainty={"jaw_width_ppm": 0},
        unsupported_state={},
    )
    self_state = _insert_demo_row(
        session,
        DemoSelfState,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        baseline_face_model_id=baseline.id,
        version=1,
        ontology_version="fixture-ontology-v1",
        derivation_version="fixture-derive-v1",
        measurements={"jaw_width_ppm": 0},
        reliability={"jaw_width_ppm": 1_000_000},
        uncertainty={"jaw_width_ppm": 0},
        routing_eligibility={"eligible": 1},
    )
    bank, question_pair = _insert_d02_question_bank(session, source_asset, synthetic_identity)
    pair_screening_report = session.get(DemoPairScreeningReport, bank.screening_report_id)
    assert pair_screening_report is not None
    questionnaire_run = _insert_demo_row(
        session,
        DemoQuestionnaireRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        question_bank_id=bank.id,
        self_state_id=self_state.id,
        algorithm_config_digest=bank.algorithm_config_digest,
        seed=1,
        max_questions=12,
        initial_posterior={"jaw_width_ppm": 0},
    )
    questionnaire_step = _insert_demo_row(
        session,
        DemoQuestionnaireStep,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        questionnaire_run_id=questionnaire_run.id,
        event_sequence=1,
        step_number=1,
        event_type="PRESENTED",
        question_pair_id=question_pair.id,
        routing_snapshot={"selected": 1},
        response_snapshot=None,
        posterior_before={"jaw_width_ppm": 0},
        posterior_after={"jaw_width_ppm": 0},
        scheduler_version="fixture-scheduler-v1",
    )
    questionnaire_response_step = _insert_demo_row(
        session,
        DemoQuestionnaireStep,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        questionnaire_run_id=questionnaire_run.id,
        event_sequence=2,
        step_number=1,
        event_type="RESPONDED",
        question_pair_id=question_pair.id,
        routing_snapshot={"selected": 1},
        response_snapshot={"choice": "RIGHT"},
        posterior_before={"jaw_width_ppm": 0},
        posterior_after={"jaw_width_ppm": 1_000},
        scheduler_version="fixture-scheduler-v1",
    )
    response_command_binding = _insert_command_binding(
        session,
        actor,
        endpoint_operation="questionnaire.response.create",
        response_type="QUESTIONNAIRE_STEP",
        response_id=questionnaire_response_step.id,
        response_status=201,
        demo_session=demo_session,
    )
    source_event = _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={"locked": 1},
        demo_session=demo_session,
        event_type="FEATURE_LOCKED",
    )
    _, compiler_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="profile.compile",
        target_type="DEMO_ACTOR",
        target_id=actor.id,
        demo_session=demo_session,
    )
    desired_delta = _insert_demo_row(
        session,
        DemoDesiredDeltaProfile,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        self_state_id=self_state.id,
        demo_job_binding_id=compiler_binding.id,
        version=1,
        as_of_event_sequence=1,
        compilation_watermark=source_event.content_digest,
        compiler_version="fixture-profile-v1",
        dimensions={"jaw_width_ppm": 10_000},
        evidence_digests=[source_event.content_digest],
        restraint={"max_ppm": 10_000},
    )
    style = _insert_demo_row(
        session,
        DemoStyleProfile,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        desired_delta_profile_id=desired_delta.id,
        demo_job_binding_id=compiler_binding.id,
        version=1,
        as_of_event_sequence=1,
        compilation_watermark=source_event.content_digest,
        compiler_version="fixture-style-v1",
        preferences={"finish": "natural"},
        negative_evidence=[],
        evidence_digests=[source_event.content_digest],
    )
    constraints = _insert_demo_row(
        session,
        DemoIdentityConstraints,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        self_state_id=self_state.id,
        version=1,
        constraint_scope="SESSION_OVERRIDE",
        source_event_digests=[source_event.content_digest],
        locks={"identity": 1},
        bounds={"max_ppm": 10_000},
        prohibited_operations=[],
    )
    transfer_request = _insert_demo_row(
        session,
        DemoSelfTransferRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        desired_delta_profile_id=desired_delta.id,
        record_kind="REQUEST",
        request_run_id=None,
        demo_job_binding_id=None,
        source_asset_id=source_asset.id,
        result_asset_id=None,
        requested_delta={"jaw_width_ppm": 10_000},
        measured_delta=None,
        non_target_drift=None,
        verifier_digest=None,
        user_outcome=None,
    )
    _, transfer_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="self_transfer.execute",
        target_type="SELF_TRANSFER_RUN",
        target_id=transfer_request.id,
        demo_session=demo_session,
    )
    transfer_asset = _result_asset(session, source_asset, sha=digest("9"))
    transfer_result = _insert_demo_row(
        session,
        DemoSelfTransferRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        desired_delta_profile_id=desired_delta.id,
        record_kind="RESULT",
        request_run_id=transfer_request.id,
        demo_job_binding_id=transfer_binding.id,
        source_asset_id=source_asset.id,
        result_asset_id=transfer_asset.id,
        requested_delta={"jaw_width_ppm": 10_000},
        measured_delta={"jaw_width_ppm": 10_000},
        non_target_drift={"max_ppm": 0},
        verifier_digest=digest("a"),
        user_outcome="ACCEPTED",
    )
    reference_profile = _insert_demo_row(
        session,
        DemoReferenceProfile,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        desired_delta_profile_id=desired_delta.id,
        style_profile_id=style.id,
        identity_constraints_id=constraints.id,
        version=1,
        source_assets=[
            {"asset_id": source_asset.id, "sha256": source_asset.sha256, "view": "FRONT"}
        ],
        analysis_version="fixture-reference-v1",
        compiler_version="fixture-reference-compiler-v1",
        structured_profile={"reference": 1},
        evidence_digests=[source_event.content_digest],
    )
    editing_session = _insert_demo_row(
        session,
        DemoEditingSession,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        source_asset_id=source_asset.id,
        source_asset_sha256=source_asset.sha256,
        desired_delta_profile_digest=desired_delta.content_digest,
        style_profile_digest=style.content_digest,
        identity_constraints_digest=constraints.content_digest,
        context_digest=digest("b"),
        instruction_digest=digest("c"),
        tool_registry_version="fixture-tools-v1",
        closed_at=None,
        tombstoned_at=None,
    )
    image0_asset, image0_variant = _result_variant(
        session,
        source_asset,
        sha=digest("d"),
        variant_type="demo_p3_p7_original_snapshot",
    )
    image0 = _insert_demo_row(
        session,
        DemoImageVersion,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        editing_session_id=editing_session.id,
        sequence=0,
        parent_version_id=None,
        source_asset_id=source_asset.id,
        source_asset_sha256=source_asset.sha256,
        result_asset_id=image0_asset.id,
        result_asset_sha256=image0_asset.sha256,
        result_asset_variant_id=image0_variant.id,
        version_kind="ORIGINAL",
        plan_digest=None,
        tool_run_digest=None,
        verifier_digest=None,
    )
    plan_fields = {
        "demo_actor_id": actor.id,
        "demo_session_id": demo_session.id,
        "editing_session_id": editing_session.id,
        "input_image_version_id": image0.id,
        "plan_version": 1,
        "desired_delta_profile_digest": desired_delta.content_digest,
        "style_profile_digest": style.content_digest,
        "identity_constraints_digest": constraints.content_digest,
        "instruction_digest": editing_session.instruction_digest,
        "planner_version": "fixture-planner-v1",
        "tool_registry_version": editing_session.tool_registry_version,
    }
    request_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="REQUEST",
        request_plan_id=None,
        operation_specs=[],
    )
    operation_spec: dict[str, Any] = {
        "engine": "GEOMETRY",
        "operation_type": "fixture_warp",
        "parameters": {"delta_ppm": 10_000},
        "preserve": ["identity"],
        "expected_effect": {"jaw_width_ppm": 10_000},
    }
    result_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="RESULT",
        request_plan_id=request_plan.id,
        operation_specs=[operation_spec],
    )
    operation = _insert_demo_row(
        session,
        DemoEditOperation,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        edit_plan_id=result_plan.id,
        operation_index=0,
        engine=operation_spec["engine"],
        operation_type=operation_spec["operation_type"],
        parameters=operation_spec["parameters"],
        preserve=operation_spec["preserve"],
        expected_effect=operation_spec["expected_effect"],
    )
    execution_job, execution_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="edit_plan.execute",
        target_type="EDIT_PLAN",
        target_id=result_plan.id,
        demo_session=demo_session,
    )
    attempt = JobAttempt(
        id=new_id(),
        job_id=execution_job.id,
        attempt=1,
        status="PENDING",
        started_at=utcnow(),
    )
    session.add(attempt)
    session.commit()
    image1_asset, image1_variant = _result_variant(
        session, image0_asset, sha=digest("e"), variant_type="demo_p3_p7_edit_result"
    )
    tool_run = _insert_demo_row(
        session,
        DemoToolRun,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        edit_operation_id=operation.id,
        edit_operation_digest=operation.content_digest,
        demo_job_binding_id=execution_binding.id,
        formal_job_attempt_id=attempt.id,
        tool_name="fixture-tool",
        tool_version="fixture-tool-v1",
        input_asset_id=image0_asset.id,
        input_asset_sha256=image0_asset.sha256,
        output_asset_id=image1_asset.id,
        output_asset_sha256=image1_asset.sha256,
        effect_contract={"identity_preserved": 1},
        outcome="COMPLETED",
    )
    _, verification_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="tool.verify",
        target_type="TOOL_RUN",
        target_id=tool_run.id,
        demo_session=demo_session,
    )
    image1_id = new_id()
    verification = _build_demo_row(
        DemoVerificationResult,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        tool_run_id=tool_run.id,
        image_version_id=image1_id,
        demo_job_binding_id=verification_binding.id,
        output_asset_id=image1_asset.id,
        output_asset_sha256=image1_asset.sha256,
        verifier_version="fixture-verify-v1",
        config_digest=digest("f"),
        metrics={"identity_ppm": 1_000_000},
        thresholds={"identity_min_ppm": 900_000},
        outcome="PASS",
        reason_codes=[],
    )
    image1 = _build_demo_row(
        DemoImageVersion,
        row_id=image1_id,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        editing_session_id=editing_session.id,
        sequence=1,
        parent_version_id=image0.id,
        source_asset_id=image0_asset.id,
        source_asset_sha256=image0_asset.sha256,
        result_asset_id=image1_asset.id,
        result_asset_sha256=image1_asset.sha256,
        result_asset_variant_id=image1_variant.id,
        version_kind="EDITED",
        plan_digest=result_plan.content_digest,
        tool_run_digest=tool_run.content_digest,
        verifier_digest=verification.content_digest,
    )
    session.add(image1)
    session.flush()
    session.add(verification)
    session.commit()
    accepted_event = _insert_preference_event(
        session,
        actor,
        sequence=2,
        previous_digest=source_event.content_digest,
        signal={"accepted": 1},
        demo_session=demo_session,
        event_type="IMAGE_ACCEPTED",
        source_type="EXPLICIT_USER_ACTION",
        target_type="IMAGE_VERSION",
        target_id=image1.id,
    )
    aesthetic_profile = _insert_demo_row(
        session,
        DemoAestheticProfile,
        demo_actor_id=actor.id,
        demo_job_binding_id=compiler_binding.id,
        generation=1,
        as_of_event_sequence=2,
        compilation_watermark=accepted_event.content_digest,
        reset_epoch=0,
        compiler_version="fixture-aesthetic-v1",
        evidence_digests=[accepted_event.content_digest],
        profile_payload={"accepted_episode": 1},
    )
    _, context_binding = _insert_job_binding(
        session,
        actor,
        endpoint_operation="context.compile",
        target_type="DEMO_SESSION",
        target_id=demo_session.id,
        demo_session=demo_session,
    )
    context = _insert_demo_row(
        session,
        DemoContextCompilation,
        demo_actor_id=actor.id,
        demo_session_id=demo_session.id,
        aesthetic_profile_id=aesthetic_profile.id,
        demo_job_binding_id=context_binding.id,
        context_as_of_time=datetime(2026, 8, 23, 4, 0, tzinfo=UTC),
        compilation_watermark=accepted_event.content_digest,
        compiler_version="fixture-context-v1",
        current_instruction_digest=editing_session.instruction_digest,
        selected_evidence=[{"digest": accepted_event.content_digest}],
        rejected_evidence=[],
        budgets={"tokens": 1},
        trace_payload={"selected": 1},
        expires_at=datetime(2026, 8, 24, 4, 0, tzinfo=UTC),
    )
    graph = {
        "actor": actor,
        "session": demo_session,
        "source_asset": source_asset,
        "formal_identity": formal_identity,
        "synthetic_identity": synthetic_identity,
        "observation": observation,
        "repeats": repeats,
        "baseline": baseline,
        "self_state": self_state,
        "pair_screening_report": pair_screening_report,
        "bank": bank,
        "question_pair": question_pair,
        "questionnaire_run": questionnaire_run,
        "questionnaire_step": questionnaire_step,
        "questionnaire_response_step": questionnaire_response_step,
        "response_command_binding": response_command_binding,
        "source_event": source_event,
        "compiler_binding": compiler_binding,
        "desired_delta": desired_delta,
        "style": style,
        "constraints": constraints,
        "transfer_request": transfer_request,
        "transfer_result": transfer_result,
        "reference_profile": reference_profile,
        "editing_session": editing_session,
        "image0": image0,
        "image0_asset": image0_asset,
        "image0_variant": image0_variant,
        "request_plan": request_plan,
        "result_plan": result_plan,
        "operation": operation,
        "execution_binding": execution_binding,
        "tool_run": tool_run,
        "image1": image1,
        "image1_asset": image1_asset,
        "image1_variant": image1_variant,
        "verification": verification,
        "accepted_event": accepted_event,
        "aesthetic_profile": aesthetic_profile,
        "context": context,
        "context_binding": context_binding,
    }
    if include_episode:
        graph["episode"] = _insert_episode(
            session, graph, [image0.content_digest, image1.content_digest]
        )
    return graph


def test_formal_qa_snapshot_digest_is_deterministic_and_frozen(
    session: Session,
) -> None:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    first_digest = _formal_qa_snapshot_digest(session, formal_identity)
    second_digest = _formal_qa_snapshot_digest(session, formal_identity)
    assert first_digest == second_digest

    admission = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=1,
            action="ADMIT",
            supersedes_id=None,
            config_marker="deterministic-admit",
        ),
    )
    assert admission.formal_accepted_qa_snapshot_digest == first_digest
    assert admission.formal_canonical_asset_sha256 == source_asset.sha256


def test_synthetic_admission_rejects_mismatched_formal_snapshot(session: Session) -> None:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    alternate_asset = _result_asset(
        session,
        source_asset,
        sha=hashlib.sha256(b"alternate-admission-asset").hexdigest(),
    )
    valid_fields = _synthetic_admission_fields(
        session,
        source_asset,
        formal_identity,
        sequence=1,
        action="ADMIT",
        supersedes_id=None,
        config_marker="snapshot-mismatch",
    )
    mismatches = (
        {"formal_canonical_asset_sha256": hashlib.sha256(b"wrong-sha").hexdigest()},
        {"formal_accepted_qa_snapshot_digest": hashlib.sha256(b"wrong-qa-snapshot").hexdigest()},
        {
            "formal_canonical_asset_id": alternate_asset.id,
            "formal_canonical_asset_sha256": alternate_asset.sha256,
        },
    )
    for mismatch in mismatches:
        fields = {**valid_fields, **mismatch}
        with pytest.raises(
            DBAPIError,
            match="D02 formal source snapshot does not match live authority",
        ):
            _insert_demo_row(session, DemoSyntheticIdentity, **fields)
        session.rollback()


def test_synthetic_admission_allows_admit_revoke_readmit_chain(session: Session) -> None:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    first_admit = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=1,
            action="ADMIT",
            supersedes_id=None,
            config_marker="chain-admit-1",
        ),
    )
    revoke = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=2,
            action="REVOKE",
            supersedes_id=first_admit.id,
            config_marker="chain-revoke",
        ),
    )
    second_admit = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=3,
            action="ADMIT",
            supersedes_id=revoke.id,
            config_marker="chain-admit-2",
        ),
    )
    assert second_admit.admission_sequence == 3
    assert second_admit.supersedes_id == revoke.id
    assert second_admit.formal_accepted_qa_snapshot_digest == (
        first_admit.formal_accepted_qa_snapshot_digest
    )


def test_synthetic_admission_rejects_invalid_successor_chain_and_snapshot(
    session: Session,
) -> None:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    first_admit = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=1,
            action="ADMIT",
            supersedes_id=None,
            config_marker="invalid-successor-root",
        ),
    )
    invalid_chains = (
        {
            "admission_sequence": 3,
            "admission_action": "REVOKE",
            "supersedes_id": first_admit.id,
        },
        {
            "admission_sequence": 2,
            "admission_action": "REVOKE",
            "supersedes_id": new_id(),
        },
        {
            "admission_sequence": 2,
            "admission_action": "ADMIT",
            "supersedes_id": first_admit.id,
        },
    )
    for chain_override in invalid_chains:
        fields = _synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=2,
            action="REVOKE",
            supersedes_id=first_admit.id,
            config_marker=f"invalid-chain-{chain_override}",
        )
        fields.update(chain_override)
        with pytest.raises(
            DBAPIError,
            match="D02 source admission chain is not the next alternating event",
        ):
            _insert_demo_row(session, DemoSyntheticIdentity, **fields)
        session.rollback()

    wrong_snapshot = _synthetic_admission_fields(
        session,
        source_asset,
        formal_identity,
        sequence=2,
        action="REVOKE",
        supersedes_id=first_admit.id,
        config_marker="invalid-revoke-snapshot",
    )
    wrong_snapshot["formal_canonical_asset_sha256"] = hashlib.sha256(
        b"invalid-revoke-snapshot"
    ).hexdigest()
    with pytest.raises(
        DBAPIError,
        match="D02 revocation must copy source Asset authority",
    ):
        _insert_demo_row(session, DemoSyntheticIdentity, **wrong_snapshot)
    session.rollback()


def test_stale_synthetic_admission_cannot_create_observation_or_pair(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    stale_admit = graph["synthetic_identity"]
    revoke = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            graph["source_asset"],
            graph["formal_identity"],
            sequence=2,
            action="REVOKE",
            supersedes_id=stale_admit.id,
            config_marker="stale-revoke",
        ),
    )
    assert revoke.admission_action == "REVOKE"

    observation = graph["observation"]
    with pytest.raises(
        DBAPIError,
        match="Demo synthetic admission is not the current eligible row",
    ):
        _insert_demo_row(
            session,
            DemoFaceObservation,
            demo_actor_id=observation.demo_actor_id,
            demo_session_id=observation.demo_session_id,
            demo_synthetic_identity_id=stale_admit.id,
            source_asset_id=observation.source_asset_id,
            source_asset_sha256=observation.source_asset_sha256,
            analyzer_version=observation.analyzer_version,
            runtime_manifest_digest=observation.runtime_manifest_digest,
            config_digest=observation.config_digest,
            repeat_count=observation.repeat_count,
            observation_state=observation.observation_state,
            unsupported_reason=observation.unsupported_reason,
        )
    session.rollback()

    pair = session.scalar(
        select(DemoQuestionPair)
        .where(DemoQuestionPair.demo_synthetic_identity_id == stale_admit.id)
        .order_by(DemoQuestionPair.id)
    )
    assert pair is not None
    with pytest.raises(
        DBAPIError,
        match="Demo synthetic admission is not the current eligible row",
    ):
        _insert_demo_row(
            session,
            DemoQuestionPair,
            authority_schema_version=pair.schema_version,
            question_bank_id=pair.question_bank_id,
            demo_synthetic_identity_id=stale_admit.id,
            source_asset_id=pair.source_asset_id,
            source_asset_sha256=pair.source_asset_sha256,
            left_asset_id=pair.left_asset_id,
            left_asset_sha256=pair.left_asset_sha256,
            right_asset_id=pair.right_asset_id,
            right_asset_sha256=pair.right_asset_sha256,
            left_asset_variant_id=pair.left_asset_variant_id,
            right_asset_variant_id=pair.right_asset_variant_id,
            dimension_key=pair.dimension_key,
            magnitude_ppm=pair.magnitude_ppm,
            left_delta_ppm=pair.left_delta_ppm,
            right_delta_ppm=pair.right_delta_ppm,
            pair_quality_ppm=pair.pair_quality_ppm,
            qa_payload=pair.qa_payload,
            screening_report_id=pair.screening_report_id,
            screening_report_digest=pair.screening_report_digest,
        )
    session.rollback()


def test_revoke_can_capture_formal_asset_tombstone_but_readmit_fails_closed(
    session: Session,
) -> None:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    admit = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=1,
            action="ADMIT",
            supersedes_id=None,
            config_marker="tombstone-admit",
        ),
    )
    savepoint = session.begin_nested()
    try:
        source_asset.deleted_at = datetime(2026, 8, 23, 8, 0, tzinfo=UTC)
        session.flush()
        revoke = _build_demo_row(
            DemoSyntheticIdentity,
            **_synthetic_admission_fields(
                session,
                source_asset,
                formal_identity,
                sequence=2,
                action="REVOKE",
                supersedes_id=admit.id,
                config_marker="tombstone-revoke",
            ),
        )
        session.add(revoke)
        session.flush()
        assert revoke.formal_canonical_asset_sha256 == admit.formal_canonical_asset_sha256

        readmit = _build_demo_row(
            DemoSyntheticIdentity,
            **_synthetic_admission_fields(
                session,
                source_asset,
                formal_identity,
                sequence=3,
                action="ADMIT",
                supersedes_id=revoke.id,
                config_marker="tombstone-readmit",
            ),
        )
        session.add(readmit)
        with pytest.raises(
            DBAPIError,
            match="D02 formal source snapshot does not match live authority",
        ):
            session.flush()
    finally:
        savepoint.rollback()
        session.expire_all()
    restored_asset = session.get(Asset, source_asset.id)
    assert restored_asset is not None
    assert restored_asset.deleted_at is None


def test_concurrent_synthetic_admission_successor_has_one_winner(
    session: Session,
) -> None:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    first_admit = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=1,
            action="ADMIT",
            supersedes_id=None,
            config_marker="concurrent-admit",
        ),
    )
    database_url = os.environ["TEST_DATABASE_URL"]
    base_fields = _synthetic_admission_fields(
        session,
        source_asset,
        formal_identity,
        sequence=2,
        action="REVOKE",
        supersedes_id=first_admit.id,
        config_marker="concurrent-placeholder",
    )
    barrier = Barrier(2)

    def append_successor(marker: str) -> str:
        engine = create_engine(database_url)
        try:
            with Session(engine) as worker_session:
                fields = {
                    **base_fields,
                    "admission_config_digest": hashlib.sha256(marker.encode()).hexdigest(),
                }
                worker_session.add(_build_demo_row(DemoSyntheticIdentity, **fields))
                barrier.wait(timeout=10)
                try:
                    worker_session.commit()
                except (DBAPIError, IntegrityError):
                    worker_session.rollback()
                    return "conflict"
                return "created"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(append_successor, ("left", "right")))
    assert results == ["conflict", "created"]
    session.expire_all()
    latest = session.scalar(
        select(DemoSyntheticIdentity)
        .where(DemoSyntheticIdentity.formal_synthetic_identity_id == formal_identity.id)
        .order_by(DemoSyntheticIdentity.admission_sequence.desc())
    )
    assert latest is not None
    assert latest.admission_sequence == 2
    assert latest.admission_action == "REVOKE"


def test_concurrent_local_synthetic_admission_successor_has_one_key_scoped_winner(
    session: Session,
) -> None:
    _, first_admit = _insert_local_d02_identity(
        session, marker=f"concurrent-local-admit-{new_id()}"
    )
    source_authority_key = first_admit.source_authority_key
    assert isinstance(source_authority_key, str)
    assert len(source_authority_key) == 64
    database_url = os.environ["TEST_DATABASE_URL"]
    base_fields = {
        column.name: getattr(first_admit, column.name)
        for column in first_admit.__table__.columns
        if column.name
        not in _NON_AUTHORITY_COLUMNS | {"source_authority_kind", "source_authority_key"}
    }
    base_fields.update(
        admission_sequence=2,
        admission_action="REVOKE",
        supersedes_id=first_admit.id,
    )
    barrier = Barrier(2)

    def append_successor(marker: str) -> str:
        engine = create_engine(database_url)
        try:
            with Session(engine) as worker_session:
                fields = {
                    **base_fields,
                    "admission_config_digest": hashlib.sha256(marker.encode()).hexdigest(),
                }
                worker_session.add(_build_demo_row(DemoSyntheticIdentity, **fields))
                barrier.wait(timeout=10)
                try:
                    worker_session.commit()
                except (DBAPIError, IntegrityError):
                    worker_session.rollback()
                    return "conflict"
                return "created"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(append_successor, ("local-left", "local-right")))
    assert results == ["conflict", "created"]
    session.expire_all()
    authority_rows = list(
        session.scalars(
            select(DemoSyntheticIdentity)
            .where(DemoSyntheticIdentity.source_authority_key == source_authority_key)
            .order_by(
                DemoSyntheticIdentity.admission_sequence,
                DemoSyntheticIdentity.id,
            )
        )
    )
    assert len(authority_rows) == 2
    assert [row.admission_sequence for row in authority_rows] == [1, 2]
    assert authority_rows[-1].admission_action == "REVOKE"
    assert authority_rows[-1].source_authority_key == source_authority_key


def test_image_verification_matching_bidirectional_edge_commits(session: Session) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    step = _prepare_followup_execution(session, graph)
    _commit_execution_pair(session, step)
    assert step["image"].sequence == 2
    assert step["verification"].image_version_id == step["image"].id
    assert step["image"].verifier_digest == step["verification"].content_digest


def test_original_image_rejects_execution_authority(session: Session) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    editing_session = _insert_demo_row(
        session,
        DemoEditingSession,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        source_asset_id=graph["source_asset"].id,
        source_asset_sha256=graph["source_asset"].sha256,
        desired_delta_profile_digest=graph["desired_delta"].content_digest,
        style_profile_digest=graph["style"].content_digest,
        identity_constraints_digest=graph["constraints"].content_digest,
        context_digest=hashlib.sha256(b"second-editing-context").hexdigest(),
        instruction_digest=hashlib.sha256(b"second-editing-instruction").hexdigest(),
        tool_registry_version="fixture-tools-v1",
        closed_at=None,
        tombstoned_at=None,
    )
    result_asset, result_variant = _result_variant(
        session,
        graph["source_asset"],
        sha=hashlib.sha256(b"invalid-original-execution").hexdigest(),
        variant_type="demo_p3_p7_invalid_original",
    )
    original = _build_demo_row(
        DemoImageVersion,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        editing_session_id=editing_session.id,
        sequence=0,
        parent_version_id=None,
        source_asset_id=graph["source_asset"].id,
        source_asset_sha256=graph["source_asset"].sha256,
        result_asset_id=result_asset.id,
        result_asset_sha256=result_asset.sha256,
        result_asset_variant_id=result_variant.id,
        version_kind="ORIGINAL",
        plan_digest=graph["result_plan"].content_digest,
        tool_run_digest=None,
        verifier_digest=None,
    )
    session.add(original)
    with pytest.raises(DBAPIError):
        session.flush()
    session.rollback()


@pytest.mark.parametrize("edge", ("image", "verification"))
def test_image_verification_half_edge_fails_at_commit(session: Session, edge: str) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    step = _prepare_followup_execution(session, graph)
    session.add(step[edge])
    with pytest.raises(DBAPIError):
        session.commit()
    session.rollback()


@pytest.mark.parametrize(
    ("digest_field", "digest_value"),
    (
        ("plan_digest", None),
        ("tool_run_digest", None),
        ("verifier_digest", None),
        ("plan_digest", "1" * 64),
        ("tool_run_digest", "2" * 64),
        ("verifier_digest", "3" * 64),
    ),
)
def test_derived_image_rejects_missing_or_arbitrary_lineage_digest(
    session: Session, digest_field: str, digest_value: str | None
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    step = _prepare_followup_execution(
        session,
        graph,
        image_overrides={digest_field: digest_value},
    )
    session.add(step["image"])
    with pytest.raises(DBAPIError):
        session.flush()
        session.add(step["verification"])
        session.commit()
    session.rollback()


@pytest.mark.parametrize("mismatch", ("source_sha", "result_sha", "asset_variant"))
def test_derived_image_rejects_asset_snapshot_or_variant_mismatch(
    session: Session, mismatch: str
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    override = {
        "source_sha": {"source_asset_sha256": hashlib.sha256(b"wrong-source-sha").hexdigest()},
        "result_sha": {"result_asset_sha256": hashlib.sha256(b"wrong-result-sha").hexdigest()},
        "asset_variant": {"result_asset_variant_id": graph["image1_variant"].id},
    }[mismatch]
    step = _prepare_followup_execution(session, graph, image_overrides=override)
    session.add(step["image"])
    with pytest.raises(DBAPIError):
        session.flush()
    session.rollback()


@pytest.mark.parametrize(
    ("version_kind", "verification_outcome"),
    (("QUARANTINED", "FAIL"), ("QUARANTINED", "HUMAN_REVIEW")),
)
def test_image_verifier_valid_outcome_mapping_commits(
    session: Session, version_kind: str, verification_outcome: str
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    step = _prepare_followup_execution(
        session,
        graph,
        image_overrides={"version_kind": version_kind},
        verification_overrides={"outcome": verification_outcome},
    )
    _commit_execution_pair(session, step)
    assert step["image"].version_kind == version_kind
    assert step["verification"].outcome == verification_outcome


@pytest.mark.parametrize(
    ("version_kind", "verification_outcome"),
    (
        ("EDITED", "FAIL"),
        ("RESTORED", "HUMAN_REVIEW"),
        ("ROLLED_BACK", "FAIL"),
        ("QUARANTINED", "PASS"),
    ),
)
def test_image_verifier_invalid_outcome_mapping_fails_closed(
    session: Session, version_kind: str, verification_outcome: str
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    step = _prepare_followup_execution(
        session,
        graph,
        image_overrides={"version_kind": version_kind},
        verification_overrides={"outcome": verification_outcome},
    )
    session.add(step["image"])
    session.flush()
    session.add(step["verification"])
    with pytest.raises(DBAPIError):
        session.commit()
    session.rollback()


def test_tool_run_requires_exact_operation_digest(session: Session) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    binding = graph["execution_binding"]
    attempt = JobAttempt(
        id=new_id(),
        job_id=binding.job_id,
        attempt=2,
        status="PENDING",
        started_at=utcnow(),
    )
    session.add(attempt)
    session.commit()
    output_asset = _result_asset(
        session,
        graph["image0_asset"],
        sha=hashlib.sha256(b"operation-digest-output").hexdigest(),
    )
    with pytest.raises(DBAPIError, match="Demo ToolRun JobAttempt ownership mismatch"):
        _insert_demo_row(
            session,
            DemoToolRun,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            edit_operation_id=graph["operation"].id,
            edit_operation_digest=hashlib.sha256(b"wrong-operation-digest").hexdigest(),
            demo_job_binding_id=binding.id,
            formal_job_attempt_id=attempt.id,
            tool_name="fixture-wrong-operation",
            tool_version="fixture-v1",
            input_asset_id=graph["image0_asset"].id,
            input_asset_sha256=graph["image0_asset"].sha256,
            output_asset_id=output_asset.id,
            output_asset_sha256=output_asset.sha256,
            effect_contract={"identity_preserved": 1},
            outcome="COMPLETED",
        )
    session.rollback()


def test_image_execution_rejects_cross_owner_plan_digest(session: Session) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    other_actor = _insert_actor(session)
    other_session = _insert_session(session, other_actor, config={"foreign-plan": 1})
    other_editing = _insert_demo_row(
        session,
        DemoEditingSession,
        demo_actor_id=other_actor.id,
        demo_session_id=other_session.id,
        source_asset_id=graph["source_asset"].id,
        source_asset_sha256=graph["source_asset"].sha256,
        desired_delta_profile_digest="4" * 64,
        style_profile_digest="5" * 64,
        identity_constraints_digest="6" * 64,
        context_digest="7" * 64,
        instruction_digest="8" * 64,
        tool_registry_version="fixture-tools-v1",
        closed_at=None,
        tombstoned_at=None,
    )
    other_image_asset, other_image_variant = _result_variant(
        session,
        graph["source_asset"],
        sha=hashlib.sha256(b"foreign-plan-original").hexdigest(),
        variant_type="demo_p3_p7_foreign_plan_original",
    )
    other_image = _insert_demo_row(
        session,
        DemoImageVersion,
        demo_actor_id=other_actor.id,
        demo_session_id=other_session.id,
        editing_session_id=other_editing.id,
        sequence=0,
        parent_version_id=None,
        source_asset_id=graph["source_asset"].id,
        source_asset_sha256=graph["source_asset"].sha256,
        result_asset_id=other_image_asset.id,
        result_asset_sha256=other_image_asset.sha256,
        result_asset_variant_id=other_image_variant.id,
        version_kind="ORIGINAL",
        plan_digest=None,
        tool_run_digest=None,
        verifier_digest=None,
    )
    foreign_plan_fields = {
        "demo_actor_id": other_actor.id,
        "demo_session_id": other_session.id,
        "editing_session_id": other_editing.id,
        "input_image_version_id": other_image.id,
        "plan_version": 1,
        "desired_delta_profile_digest": "4" * 64,
        "style_profile_digest": "5" * 64,
        "identity_constraints_digest": "6" * 64,
        "instruction_digest": other_editing.instruction_digest,
        "planner_version": "fixture-planner-v1",
        "tool_registry_version": other_editing.tool_registry_version,
    }
    foreign_request = _insert_demo_row(
        session,
        DemoEditPlan,
        **foreign_plan_fields,
        record_kind="REQUEST",
        request_plan_id=None,
        operation_specs=[],
    )
    foreign_result = _insert_demo_row(
        session,
        DemoEditPlan,
        **foreign_plan_fields,
        record_kind="RESULT",
        request_plan_id=foreign_request.id,
        operation_specs=[
            {
                "engine": "RASTER",
                "operation_type": "fixture_foreign",
                "parameters": {"contrast_ppm": 1},
                "preserve": ["identity"],
                "expected_effect": {"contrast_ppm": 1},
            }
        ],
    )
    step = _prepare_followup_execution(
        session,
        graph,
        image_overrides={"plan_digest": foreign_result.content_digest},
    )
    session.add(step["image"])
    session.flush()
    session.add(step["verification"])
    with pytest.raises(DBAPIError, match="Demo image execution plan digest mismatch"):
        session.commit()
    session.rollback()


def test_plan_operation_spec_mismatch_rejects_tool_run(session: Session) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    operation_spec = {
        "engine": "RASTER",
        "operation_type": "fixture_contrast",
        "parameters": {"contrast_ppm": 25_000},
        "preserve": ["identity"],
        "expected_effect": {"contrast_ppm": 25_000},
    }
    plan_fields = {
        "demo_actor_id": graph["actor"].id,
        "demo_session_id": graph["session"].id,
        "editing_session_id": graph["editing_session"].id,
        "input_image_version_id": graph["image1"].id,
        "plan_version": 2,
        "desired_delta_profile_digest": graph["desired_delta"].content_digest,
        "style_profile_digest": graph["style"].content_digest,
        "identity_constraints_digest": graph["constraints"].content_digest,
        "instruction_digest": graph["editing_session"].instruction_digest,
        "planner_version": "fixture-planner-v1",
        "tool_registry_version": graph["editing_session"].tool_registry_version,
    }
    request_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="REQUEST",
        request_plan_id=None,
        operation_specs=[],
    )
    result_plan = _insert_demo_row(
        session,
        DemoEditPlan,
        **plan_fields,
        record_kind="RESULT",
        request_plan_id=request_plan.id,
        operation_specs=[operation_spec],
    )
    mismatched_operation = _insert_demo_row(
        session,
        DemoEditOperation,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        edit_plan_id=result_plan.id,
        operation_index=0,
        engine=operation_spec["engine"],
        operation_type=operation_spec["operation_type"],
        parameters={"contrast_ppm": 30_000},
        preserve=operation_spec["preserve"],
        expected_effect=operation_spec["expected_effect"],
    )
    execution_job, execution_binding = _insert_job_binding(
        session,
        graph["actor"],
        endpoint_operation="edit_plan.execute",
        target_type="EDIT_PLAN",
        target_id=result_plan.id,
        demo_session=graph["session"],
    )
    attempt = JobAttempt(
        id=new_id(),
        job_id=execution_job.id,
        attempt=1,
        status="PENDING",
        started_at=utcnow(),
    )
    session.add(attempt)
    session.commit()
    output_asset = _result_asset(
        session,
        graph["image1_asset"],
        sha=hashlib.sha256(b"spec-mismatch-output").hexdigest(),
    )
    with pytest.raises(DBAPIError, match="Demo ToolRun JobAttempt ownership mismatch"):
        _insert_demo_row(
            session,
            DemoToolRun,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            edit_operation_id=mismatched_operation.id,
            edit_operation_digest=mismatched_operation.content_digest,
            demo_job_binding_id=execution_binding.id,
            formal_job_attempt_id=attempt.id,
            tool_name="fixture-spec-mismatch",
            tool_version="fixture-v1",
            input_asset_id=graph["image1_asset"].id,
            input_asset_sha256=graph["image1_asset"].sha256,
            output_asset_id=output_asset.id,
            output_asset_sha256=output_asset.sha256,
            effect_contract={"identity_preserved": 1},
            outcome="COMPLETED",
        )
    session.rollback()


def test_multi_operation_plan_shares_execution_binding_and_attempt(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    execution = _insert_two_operation_execution(session, graph)
    first_step = execution["first_step"]
    second_step = execution["second_step"]
    assert first_step["tool_run"].demo_job_binding_id == (
        second_step["tool_run"].demo_job_binding_id
    )
    assert first_step["tool_run"].formal_job_attempt_id == (
        second_step["tool_run"].formal_job_attempt_id
    )
    assert first_step["image"].sequence == 2
    assert second_step["image"].sequence == 3
    assert second_step["image"].parent_version_id == first_step["image"].id


def test_accepted_episode_traverses_complete_multi_operation_execution(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    execution = _insert_two_operation_execution(session, graph)
    first_step = execution["first_step"]
    second_step = execution["second_step"]
    final_event = _insert_preference_event(
        session,
        graph["actor"],
        sequence=3,
        previous_digest=graph["accepted_event"].content_digest,
        signal={"accepted": 1},
        demo_session=graph["session"],
        event_type="IMAGE_ACCEPTED",
        source_type="EXPLICIT_USER_ACTION",
        target_type="IMAGE_VERSION",
        target_id=second_step["image"].id,
    )
    final_graph = {
        **graph,
        "image1": second_step["image"],
        "image1_asset": second_step["output_asset"],
        "verification": second_step["verification"],
        "accepted_event": final_event,
    }
    trajectory = [
        graph["image0"].content_digest,
        graph["image1"].content_digest,
        first_step["image"].content_digest,
        second_step["image"].content_digest,
    ]
    episode = _insert_episode(session, final_graph, trajectory)
    assert episode.accepted_image_version_id == second_step["image"].id

    wrong_verifier_graph = {
        **final_graph,
        "verification": first_step["verification"],
    }
    with pytest.raises(
        DBAPIError,
        match="Only verified user-accepted Demo image versions may become episodes",
    ):
        _insert_episode(session, wrong_verifier_graph, trajectory)
    session.rollback()

    nonfinal_event = _insert_preference_event(
        session,
        graph["actor"],
        sequence=4,
        previous_digest=final_event.content_digest,
        signal={"accepted": 1},
        demo_session=graph["session"],
        event_type="IMAGE_ACCEPTED",
        source_type="EXPLICIT_USER_ACTION",
        target_type="IMAGE_VERSION",
        target_id=first_step["image"].id,
    )
    nonfinal_graph = {
        **graph,
        "image1": first_step["image"],
        "image1_asset": first_step["output_asset"],
        "verification": first_step["verification"],
        "accepted_event": nonfinal_event,
    }
    with pytest.raises(
        DBAPIError,
        match="Only verified user-accepted Demo image versions may become episodes",
    ):
        _insert_episode(session, nonfinal_graph, trajectory[:-1])
    session.rollback()


def test_full_demo_authority_graph_covers_every_table(session: Session) -> None:
    graph = _insert_full_demo_graph(session)
    authority_rows = [
        row
        for value in graph.values()
        for row in (value if isinstance(value, list) else [value])
        if getattr(row, "__table__", None) is not None and row.__table__.name in DEMO_TABLE_NAMES
    ]
    assert {row.__table__.name for row in authority_rows} == set(DEMO_TABLE_NAMES)
    for table_name in DEMO_TABLE_NAMES:
        assert session.scalar(text(f"SELECT count(*) FROM {table_name}")) >= 1  # noqa: S608


def test_every_demo_authority_row_rejects_direct_update_and_delete(session: Session) -> None:
    _insert_full_demo_graph(session)
    for table_name in sorted(DEMO_TABLE_NAMES):
        row_id = session.scalar(text(f"SELECT id FROM {table_name} LIMIT 1"))  # noqa: S608
        assert row_id is not None
        with pytest.raises(DBAPIError):
            session.execute(
                text(f"UPDATE {table_name} SET content_digest=content_digest WHERE id=:row_id"),  # noqa: S608
                {"row_id": row_id},
            )
        session.rollback()
        with pytest.raises(DBAPIError):
            session.execute(
                text(f"DELETE FROM {table_name} WHERE id=:row_id"),  # noqa: S608
                {"row_id": row_id},
            )
        session.rollback()


def test_cross_owner_and_session_references_fail_closed(session: Session) -> None:
    graph = _insert_full_demo_graph(session)
    other_actor = _insert_actor(session)
    other_session = _insert_session(session, other_actor, config={"other": 1})
    source_asset = graph["source_asset"]

    with pytest.raises(DBAPIError, match="ReferenceProfile input ownership mismatch"):
        _insert_demo_row(
            session,
            DemoReferenceProfile,
            demo_actor_id=other_actor.id,
            demo_session_id=other_session.id,
            desired_delta_profile_id=graph["desired_delta"].id,
            style_profile_id=None,
            identity_constraints_id=None,
            version=1,
            source_assets=[
                {"asset_id": source_asset.id, "sha256": source_asset.sha256, "view": "FRONT"}
            ],
            analysis_version="fixture-reference-v1",
            compiler_version="fixture-reference-compiler-v1",
            structured_profile={"reference": 1},
            evidence_digests=[graph["source_event"].content_digest],
        )
    session.rollback()

    foreign_result, foreign_variant = _result_variant(
        session,
        source_asset,
        sha="b" * 64,
        variant_type="demo_p3_p7_cross_owner_probe",
    )
    with pytest.raises(DBAPIError):
        _insert_demo_row(
            session,
            DemoImageVersion,
            demo_actor_id=other_actor.id,
            demo_session_id=other_session.id,
            editing_session_id=graph["editing_session"].id,
            sequence=0,
            parent_version_id=None,
            source_asset_id=source_asset.id,
            source_asset_sha256=source_asset.sha256,
            result_asset_id=foreign_result.id,
            result_asset_sha256=foreign_result.sha256,
            result_asset_variant_id=foreign_variant.id,
            version_kind="ORIGINAL",
            plan_digest=None,
            tool_run_digest=None,
            verifier_digest=None,
        )
    session.rollback()

    _, context_binding = _insert_job_binding(
        session,
        other_actor,
        endpoint_operation="context.compile",
        target_type="DEMO_SESSION",
        target_id=other_session.id,
        demo_session=other_session,
    )
    with pytest.raises(DBAPIError, match="ContextCompilation ownership mismatch"):
        _insert_demo_row(
            session,
            DemoContextCompilation,
            demo_actor_id=other_actor.id,
            demo_session_id=other_session.id,
            aesthetic_profile_id=graph["aesthetic_profile"].id,
            demo_job_binding_id=context_binding.id,
            context_as_of_time=datetime(2026, 8, 23, 5, 0, tzinfo=UTC),
            compilation_watermark="c" * 64,
            compiler_version="fixture-context-v1",
            current_instruction_digest="d" * 64,
            selected_evidence=[],
            rejected_evidence=[],
            budgets={"tokens": 1},
            trace_payload={"selected": 1},
            expires_at=datetime(2026, 8, 24, 5, 0, tzinfo=UTC),
        )
    session.rollback()

    with pytest.raises(DBAPIError):
        _insert_demo_row(
            session,
            DemoFaceObservationRepeat,
            demo_actor_id=other_actor.id,
            demo_session_id=other_session.id,
            observation_id=graph["observation"].id,
            repeat_index=1,
            runtime_manifest_digest="2" * 64,
            model_manifest_digest="4" * 64,
            landmarks=[0] * 478,
            pose={"yaw_ppm": 0},
            quality={"score_ppm": 1_000_000},
            measurements={"jaw_width_ppm": 0},
        )
    session.rollback()


def test_profile_and_context_evidence_requires_existing_actor_authority(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session)
    foreign_actor = _insert_actor(session)
    foreign_session = _insert_session(session, foreign_actor, config={"foreign": 1})
    foreign_event = _insert_preference_event(
        session,
        foreign_actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={"style_context": "foreign"},
        demo_session=foreign_session,
    )
    foreign_digest = foreign_event.content_digest

    with pytest.raises(DBAPIError, match="DesiredDelta evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoDesiredDeltaProfile,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            self_state_id=graph["self_state"].id,
            demo_job_binding_id=graph["compiler_binding"].id,
            version=2,
            as_of_event_sequence=2,
            compilation_watermark=foreign_digest,
            compiler_version="fixture-profile-v1",
            dimensions={"jaw_width_ppm": 9_000},
            evidence_digests=[foreign_digest],
            restraint={"max_ppm": 9_000},
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="StyleProfile evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoStyleProfile,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            desired_delta_profile_id=graph["desired_delta"].id,
            demo_job_binding_id=graph["compiler_binding"].id,
            version=2,
            as_of_event_sequence=2,
            compilation_watermark=foreign_digest,
            compiler_version="fixture-style-v1",
            preferences={"finish": "editorial"},
            negative_evidence=[],
            evidence_digests=[foreign_digest],
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="ReferenceProfile evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoReferenceProfile,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            desired_delta_profile_id=graph["desired_delta"].id,
            style_profile_id=graph["style"].id,
            identity_constraints_id=graph["constraints"].id,
            version=2,
            source_assets=[
                {
                    "asset_id": graph["source_asset"].id,
                    "sha256": graph["source_asset"].sha256,
                    "view": "FRONT",
                }
            ],
            analysis_version="fixture-reference-v1",
            compiler_version="fixture-reference-compiler-v1",
            structured_profile={"reference": 2},
            evidence_digests=[foreign_digest],
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="AestheticProfile evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoAestheticProfile,
            demo_actor_id=graph["actor"].id,
            demo_job_binding_id=graph["compiler_binding"].id,
            generation=2,
            as_of_event_sequence=2,
            compilation_watermark=foreign_digest,
            reset_epoch=0,
            compiler_version="fixture-aesthetic-v1",
            evidence_digests=[foreign_digest],
            profile_payload={"accepted_episode": 2},
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="ContextCompilation evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoContextCompilation,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            aesthetic_profile_id=graph["aesthetic_profile"].id,
            demo_job_binding_id=graph["context_binding"].id,
            context_as_of_time=datetime(2026, 8, 23, 5, 0, tzinfo=UTC),
            compilation_watermark=graph["accepted_event"].content_digest,
            compiler_version="fixture-context-v1",
            current_instruction_digest=graph["editing_session"].instruction_digest,
            selected_evidence=[{"digest": foreign_digest}],
            rejected_evidence=[],
            budgets={"tokens": 1},
            trace_payload={"selected": 1},
            expires_at=datetime(2026, 8, 24, 5, 0, tzinfo=UTC),
        )
    session.rollback()

    unknown_digest = hashlib.sha256(b"missing-demo-evidence").hexdigest()
    with pytest.raises(DBAPIError, match="ContextCompilation evidence ownership mismatch"):
        _insert_demo_row(
            session,
            DemoContextCompilation,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            aesthetic_profile_id=graph["aesthetic_profile"].id,
            demo_job_binding_id=graph["context_binding"].id,
            context_as_of_time=datetime(2026, 8, 23, 6, 0, tzinfo=UTC),
            compilation_watermark=graph["accepted_event"].content_digest,
            compiler_version="fixture-context-v1",
            current_instruction_digest=graph["editing_session"].instruction_digest,
            selected_evidence=[{"digest": unknown_digest}],
            rejected_evidence=[],
            budgets={"tokens": 1},
            trace_payload={"selected": 1},
            expires_at=datetime(2026, 8, 24, 6, 0, tzinfo=UTC),
        )
    session.rollback()


def test_context_evidence_allows_same_actor_next_session_recall(session: Session) -> None:
    graph = _insert_full_demo_graph(session)
    next_session = _insert_session(session, graph["actor"], config={"next_session": 1})
    _, next_binding = _insert_job_binding(
        session,
        graph["actor"],
        endpoint_operation="context.compile",
        target_type="DEMO_SESSION",
        target_id=next_session.id,
        demo_session=next_session,
    )
    context = _insert_demo_row(
        session,
        DemoContextCompilation,
        demo_actor_id=graph["actor"].id,
        demo_session_id=next_session.id,
        aesthetic_profile_id=graph["aesthetic_profile"].id,
        demo_job_binding_id=next_binding.id,
        context_as_of_time=datetime(2026, 8, 23, 7, 0, tzinfo=UTC),
        compilation_watermark=graph["accepted_event"].content_digest,
        compiler_version="fixture-context-v1",
        current_instruction_digest=hashlib.sha256(b"next-session-instruction").hexdigest(),
        selected_evidence=[{"digest": graph["accepted_event"].content_digest}],
        rejected_evidence=[],
        budgets={"tokens": 1},
        trace_payload={"recalled_previous_session": 1},
        expires_at=datetime(2026, 8, 24, 7, 0, tzinfo=UTC),
    )
    assert context.demo_session_id == next_session.id


@pytest.mark.parametrize(
    "trajectory_factory",
    (
        lambda graph: [graph["image1"].content_digest],
        lambda graph: [graph["image1"].content_digest, graph["image0"].content_digest],
        lambda graph: [graph["image0"].content_digest, "0" * 64],
    ),
    ids=("omitted-root", "wrong-order", "foreign-digest"),
)
def test_accepted_episode_requires_exact_root_to_leaf_trajectory(
    session: Session, trajectory_factory: Any
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    with pytest.raises(DBAPIError, match="accepted episode trajectory lineage mismatch"):
        _insert_episode(session, graph, trajectory_factory(graph))
    session.rollback()
    episode = _insert_episode(
        session, graph, [graph["image0"].content_digest, graph["image1"].content_digest]
    )
    assert episode.trajectory_digests == [
        graph["image0"].content_digest,
        graph["image1"].content_digest,
    ]


def test_demo_metadata_and_database_objects_match(session: Session) -> None:
    assert len(DEMO_TABLE_NAMES) == 29
    database_tables = set(
        session.scalars(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename LIKE 'demo_%'"
            )
        )
    )
    assert database_tables == set(DEMO_TABLE_NAMES)
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM pg_trigger "
                "WHERE NOT tgisinternal AND tgname LIKE 'trg_demo_authority_%'"
            )
        )
        == 29
    )
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM pg_trigger "
                "WHERE NOT tgisinternal AND tgname LIKE 'trg_demo_terminal_binding_%'"
            )
        )
        == 4
    )
    assert session.scalar(
        text("SELECT to_regprocedure('mirror_demo_evidence_owned_by(text,text)') IS NOT NULL")
    )
    assert session.scalar(
        text("SELECT to_regprocedure('mirror_demo_validate_terminal_binding()') IS NOT NULL")
    )
    assert session.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION


def test_demo_orm_and_database_foreign_keys_match(session: Session) -> None:
    """Cover the cyclic foreign keys Alembic cannot include in its sort-based drift check."""

    database = inspect(session.bind)
    metadata = DemoActor.metadata
    preparer = session.bind.dialect.identifier_preparer

    def normalize(value: object) -> str:
        return "" if value is None else str(value).upper()

    def expected_foreign_keys(table_name: str) -> set[tuple[object, ...]]:
        rows: set[tuple[object, ...]] = set()
        for constraint in metadata.tables[table_name].foreign_key_constraints:
            elements = list(constraint.elements)
            rendered_name = preparer.truncate_and_render_constraint_name(conv(str(constraint.name)))
            rows.add(
                (
                    rendered_name,
                    tuple(element.parent.name for element in elements),
                    elements[0].column.table.name,
                    tuple(element.column.name for element in elements),
                    normalize(constraint.ondelete),
                    bool(constraint.deferrable),
                    normalize(constraint.initially),
                )
            )
        return rows

    def actual_foreign_keys(table_name: str) -> set[tuple[object, ...]]:
        rows: set[tuple[object, ...]] = set()
        for foreign_key in database.get_foreign_keys(table_name):
            options = foreign_key.get("options") or {}
            rows.add(
                (
                    foreign_key.get("name") or "",
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                    normalize(options.get("ondelete")),
                    bool(options.get("deferrable")),
                    normalize(options.get("initially")),
                )
            )
        return rows

    expected_count = 0
    actual_count = 0
    for table_name in DEMO_TABLE_NAMES:
        expected = expected_foreign_keys(table_name)
        actual = actual_foreign_keys(table_name)
        expected_count += len(expected)
        actual_count += len(actual)
        assert actual == expected, table_name

    assert expected_count == actual_count == 89


def test_canonical_json_digest_and_integer_numeric_authority(session: Session) -> None:
    assert (
        session.scalar(
            text("SELECT mirror_demo_canonical_json(jsonb_build_object('b', 2, 'a', 1))")
        )
        == '{"a":1,"b":2}'
    )
    negative_zero, zero, same_value = session.execute(
        text(
            "SELECT mirror_demo_canonical_json('-0'::jsonb), "
            "mirror_demo_canonical_json('0'::jsonb), '-0'::jsonb = '0'::jsonb"
        )
    ).one()
    assert (negative_zero, zero, same_value) == ("0", "0", True)

    with pytest.raises(DBAPIError, match="requires integer numeric leaves"):
        session.scalar(text("SELECT mirror_demo_canonical_json('1.5'::jsonb)"))
    session.rollback()

    actor = _insert_actor(session)
    with pytest.raises(DBAPIError, match="canonical digest mismatch"):
        session.execute(
            text(
                "INSERT INTO demo_actors "
                "(id,schema_version,canonical_payload,content_digest,created_at,"
                "actor_kind,credential_key_id,authority_at,tombstoned_at) "
                "SELECT :id,schema_version,canonical_payload,:wrong_digest,created_at,"
                "actor_kind,credential_key_id,authority_at,NULL "
                "FROM demo_actors WHERE id=:source_id"
            ),
            {
                "id": new_id(),
                "wrong_digest": "f" * 64,
                "source_id": actor.id,
            },
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="disagrees with structured authority"):
        session.execute(
            text(
                "INSERT INTO demo_actors "
                "(id,schema_version,canonical_payload,content_digest,created_at,"
                "actor_kind,credential_key_id,authority_at,tombstoned_at) "
                "SELECT :id,schema_version,canonical_payload,content_digest,created_at,"
                "'LOCAL_SINGLE_USER',credential_key_id,authority_at,NULL "
                "FROM demo_actors WHERE id=:source_id"
            ),
            {"id": new_id(), "source_id": actor.id},
        )
    session.rollback()

    with pytest.raises(DBAPIError, match="requires integer numeric leaves"):
        _insert_session(session, actor, config={"fractional": 0.5})


def test_nullable_jsonb_uses_sql_null_and_rejects_explicit_json_null(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session)
    nullable_state = session.execute(
        text(
            "SELECT response_snapshot IS NULL, jsonb_typeof(response_snapshot) "
            "FROM demo_questionnaire_steps WHERE id=:step_id"
        ),
        {"step_id": graph["questionnaire_step"].id},
    ).one()
    transfer_state = session.execute(
        text(
            "SELECT measured_delta IS NULL, jsonb_typeof(measured_delta), "
            "non_target_drift IS NULL, jsonb_typeof(non_target_drift) "
            "FROM demo_self_transfer_runs WHERE id=:run_id"
        ),
        {"run_id": graph["transfer_request"].id},
    ).one()
    assert nullable_state == (True, None)
    assert transfer_state == (True, None, True, None)

    with pytest.raises(DBAPIError, match="response_snapshot_object"):
        _insert_demo_row(
            session,
            DemoQuestionnaireStep,
            demo_actor_id=graph["actor"].id,
            demo_session_id=graph["session"].id,
            questionnaire_run_id=graph["questionnaire_run"].id,
            event_sequence=2,
            step_number=2,
            event_type="PRESENTED",
            question_pair_id=graph["question_pair"].id,
            routing_snapshot={"selected": 1},
            response_snapshot=JSON.NULL,
            posterior_before={"jaw_width_ppm": 0},
            posterior_after={"jaw_width_ppm": 0},
            scheduler_version="fixture-scheduler-v1",
        )
    session.rollback()

    for field_name, requested_ppm in (("measured_delta", 9_999), ("non_target_drift", 9_998)):
        nullable_fields = {"measured_delta": None, "non_target_drift": None}
        nullable_fields[field_name] = JSON.NULL
        with pytest.raises(DBAPIError, match=r"record_shape|_object"):
            _insert_demo_row(
                session,
                DemoSelfTransferRun,
                demo_actor_id=graph["actor"].id,
                demo_session_id=graph["session"].id,
                desired_delta_profile_id=graph["desired_delta"].id,
                record_kind="REQUEST",
                request_run_id=None,
                demo_job_binding_id=None,
                source_asset_id=graph["source_asset"].id,
                result_asset_id=None,
                requested_delta={"jaw_width_ppm": requested_ppm},
                verifier_digest=None,
                user_outcome=None,
                **nullable_fields,
            )
        session.rollback()


def test_direct_sql_immutability_and_terminal_transition(session: Session) -> None:
    actor = _insert_actor(session)
    with pytest.raises(DBAPIError, match="Invalid Demo actor tombstone transition"):
        session.execute(
            text("UPDATE demo_actors SET credential_key_id=:value WHERE id=:actor_id"),
            {"value": new_id() + new_id(), "actor_id": actor.id},
        )
    session.rollback()
    tombstoned_at = datetime(2026, 8, 23, 2, 0, tzinfo=UTC)
    session.execute(
        text("UPDATE demo_actors SET tombstoned_at=:value WHERE id=:actor_id"),
        {"value": tombstoned_at, "actor_id": actor.id},
    )
    with pytest.raises(DBAPIError, match="requires matching lifecycle event"):
        session.commit()
    session.rollback()

    _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={},
        event_type="ACTOR_TOMBSTONED",
        source_type="SYSTEM_LIFECYCLE",
        target_type="DEMO_ACTOR",
        target_id=actor.id,
        occurred_at=tombstoned_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_actors SET tombstoned_at=:value WHERE id=:actor_id"),
        {"value": tombstoned_at, "actor_id": actor.id},
    )
    session.commit()
    with pytest.raises(DBAPIError, match="Invalid Demo actor tombstone transition"):
        session.execute(
            text("UPDATE demo_actors SET tombstoned_at=:value WHERE id=:actor_id"),
            {"value": tombstoned_at, "actor_id": actor.id},
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(delete(DemoActor).where(DemoActor.id == actor.id))
    session.rollback()


def test_orphan_lifecycle_event_fails_closed_at_commit(session: Session) -> None:
    actor = _insert_actor(session)
    tombstoned_at = datetime(2026, 8, 23, 2, 30, tzinfo=UTC)
    _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={},
        event_type="ACTOR_TOMBSTONED",
        source_type="SYSTEM_LIFECYCLE",
        target_type="DEMO_ACTOR",
        target_id=actor.id,
        occurred_at=tombstoned_at,
        commit=False,
    )
    with pytest.raises(DBAPIError, match="header lacks matching lifecycle event"):
        session.commit()
    session.rollback()


def test_demo_session_terminal_transitions_are_monotonic(session: Session) -> None:
    actor = _insert_actor(session)
    demo_session = _insert_session(session, actor, config={"purpose": "terminal-test"})
    closed_at = datetime(2026, 8, 23, 2, 0, tzinfo=UTC)
    tombstoned_at = datetime(2026, 8, 23, 3, 0, tzinfo=UTC)

    with pytest.raises(DBAPIError, match="Invalid Demo terminal header transition"):
        session.execute(
            text("UPDATE demo_sessions SET tombstoned_at=:value WHERE id=:session_id"),
            {"value": tombstoned_at, "session_id": demo_session.id},
        )
    session.rollback()

    session.execute(
        text("UPDATE demo_sessions SET closed_at=:value WHERE id=:session_id"),
        {"value": closed_at, "session_id": demo_session.id},
    )
    with pytest.raises(DBAPIError, match="requires matching lifecycle event"):
        session.commit()
    session.rollback()

    close_event = _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={},
        demo_session=demo_session,
        event_type="SESSION_CLOSED",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=closed_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_sessions SET closed_at=:value WHERE id=:session_id"),
        {"value": closed_at, "session_id": demo_session.id},
    )
    session.commit()

    session.execute(
        text("UPDATE demo_sessions SET tombstoned_at=:value WHERE id=:session_id"),
        {"value": tombstoned_at, "session_id": demo_session.id},
    )
    with pytest.raises(DBAPIError, match="requires matching lifecycle event"):
        session.commit()
    session.rollback()

    _insert_preference_event(
        session,
        actor,
        sequence=2,
        previous_digest=close_event.content_digest,
        signal={"authority_id": demo_session.id, "authority_type": "DEMO_SESSION"},
        demo_session=demo_session,
        event_type="TOMBSTONE",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=tombstoned_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_sessions SET tombstoned_at=:value WHERE id=:session_id"),
        {"value": tombstoned_at, "session_id": demo_session.id},
    )
    session.commit()

    with pytest.raises(DBAPIError, match="Invalid Demo terminal header transition"):
        session.execute(
            text("UPDATE demo_sessions SET closed_at=:value WHERE id=:session_id"),
            {"value": datetime(2026, 8, 23, 4, 0, tzinfo=UTC), "session_id": demo_session.id},
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(delete(DemoSession).where(DemoSession.id == demo_session.id))
    session.rollback()


def test_editing_session_terminal_binding_rejects_wrong_target_owner_and_time(
    session: Session,
) -> None:
    graph = _insert_full_demo_graph(session)
    editing_session = graph["editing_session"]
    closed_at = datetime(2026, 8, 23, 8, 0, tzinfo=UTC)
    tombstoned_at = datetime(2026, 8, 23, 9, 0, tzinfo=UTC)

    session.execute(
        text("UPDATE demo_editing_sessions SET closed_at=:value WHERE id=:editing_id"),
        {"value": closed_at, "editing_id": editing_session.id},
    )
    with pytest.raises(DBAPIError, match="requires matching lifecycle event"):
        session.commit()
    session.rollback()

    other_actor = _insert_actor(session)
    other_session = _insert_session(session, other_actor, config={"other": 1})
    other_editing = _insert_demo_row(
        session,
        DemoEditingSession,
        demo_actor_id=other_actor.id,
        demo_session_id=other_session.id,
        source_asset_id=graph["source_asset"].id,
        source_asset_sha256=graph["source_asset"].sha256,
        desired_delta_profile_digest=hashlib.sha256(b"other-desired").hexdigest(),
        style_profile_digest=hashlib.sha256(b"other-style").hexdigest(),
        identity_constraints_digest=hashlib.sha256(b"other-constraints").hexdigest(),
        context_digest=hashlib.sha256(b"other-context").hexdigest(),
        instruction_digest=hashlib.sha256(b"other-instruction").hexdigest(),
        tool_registry_version="fixture-tools-v1",
        closed_at=None,
        tombstoned_at=None,
    )
    with pytest.raises(DBAPIError, match="editing session close lifecycle authority is invalid"):
        _insert_preference_event(
            session,
            graph["actor"],
            sequence=3,
            previous_digest=graph["accepted_event"].content_digest,
            signal={"editing_session_id": other_editing.id},
            demo_session=graph["session"],
            event_type="EDITING_SESSION_CLOSED",
            source_type="SYSTEM_LIFECYCLE",
            occurred_at=closed_at,
            commit=False,
        )
    session.rollback()

    _insert_preference_event(
        session,
        graph["actor"],
        sequence=3,
        previous_digest=graph["accepted_event"].content_digest,
        signal={"editing_session_id": editing_session.id},
        demo_session=graph["session"],
        event_type="EDITING_SESSION_CLOSED",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=closed_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_editing_sessions SET closed_at=:value WHERE id=:editing_id"),
        {
            "value": datetime(2026, 8, 23, 8, 1, tzinfo=UTC),
            "editing_id": editing_session.id,
        },
    )
    with pytest.raises(DBAPIError, match=r"lacks matching lifecycle event|requires matching"):
        session.commit()
    session.rollback()

    close_event = _insert_preference_event(
        session,
        graph["actor"],
        sequence=3,
        previous_digest=graph["accepted_event"].content_digest,
        signal={"editing_session_id": editing_session.id},
        demo_session=graph["session"],
        event_type="EDITING_SESSION_CLOSED",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=closed_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_editing_sessions SET closed_at=:value WHERE id=:editing_id"),
        {"value": closed_at, "editing_id": editing_session.id},
    )
    session.commit()

    _insert_preference_event(
        session,
        graph["actor"],
        sequence=4,
        previous_digest=close_event.content_digest,
        signal={"authority_id": editing_session.id, "authority_type": "EDITING_SESSION"},
        demo_session=graph["session"],
        event_type="TOMBSTONE",
        source_type="SYSTEM_LIFECYCLE",
        occurred_at=tombstoned_at,
        commit=False,
    )
    session.execute(
        text("UPDATE demo_editing_sessions SET tombstoned_at=:value WHERE id=:editing_id"),
        {"value": tombstoned_at, "editing_id": editing_session.id},
    )
    session.commit()


def test_preference_event_sequence_and_digest_chain(session: Session) -> None:
    actor = _insert_actor(session)
    first = _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={"style_context": "editorial"},
    )
    with pytest.raises(DBAPIError, match="sequence or digest chain is invalid"):
        _insert_preference_event(
            session,
            actor,
            sequence=3,
            previous_digest=first.content_digest,
            signal={"style_context": "minimal"},
        )
    session.rollback()
    second = _insert_preference_event(
        session,
        actor,
        sequence=2,
        previous_digest=first.content_digest,
        signal={"style_context": "minimal"},
    )
    assert second.event_sequence == 2
    assert (
        session.scalar(
            select(DemoPreferenceEvent.content_digest).where(DemoPreferenceEvent.id == second.id)
        )
        == second.content_digest
    )


def test_concurrent_preference_event_append_has_one_canonical_winner(session: Session) -> None:
    actor = _insert_actor(session)
    first = _insert_preference_event(
        session,
        actor,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        signal={"style_context": "first"},
    )
    database_url = os.environ["TEST_DATABASE_URL"]
    actor_id = actor.id
    first_digest = first.content_digest
    barrier = Barrier(2)

    def append(sequence_signal: str) -> str:
        engine = create_engine(database_url)
        try:
            with Session(engine) as worker_session:
                worker_actor = worker_session.get(DemoActor, actor_id)
                assert worker_actor is not None
                barrier.wait(timeout=10)
                try:
                    _insert_preference_event(
                        worker_session,
                        worker_actor,
                        sequence=2,
                        previous_digest=first_digest,
                        signal={"style_context": sequence_signal},
                    )
                except (DBAPIError, IntegrityError):
                    worker_session.rollback()
                    return "conflict"
                return "created"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(append, ("left", "right")))
    assert results == ["conflict", "created"]
    session.expire_all()
    events = session.scalars(
        select(DemoPreferenceEvent)
        .where(DemoPreferenceEvent.demo_actor_id == actor.id)
        .order_by(DemoPreferenceEvent.event_sequence)
    ).all()
    assert [event.event_sequence for event in events] == [1, 2]
    assert events[1].previous_event_digest == first.content_digest


def test_job_binding_uses_namespaced_formal_job_and_typed_owner(session: Session) -> None:
    actor = _insert_actor(session)
    endpoint_operation = "profile.compile"
    client_key_hash = "2" * 64
    formal_hash = hashlib.sha256(
        (
            f"mirror.demo/JobIdempotency/v1\n{actor.id}\n{endpoint_operation}\n{client_key_hash}"
        ).encode()
    ).hexdigest()
    job = Job(
        id=new_id(),
        job_type=f"demo_p3_p7.{endpoint_operation}",
        status="PENDING",
        idempotency_key_hash=formal_hash,
        request_id="demo-d01b-job-binding",
        payload={},
        owner_user_id=None,
        ingestion_upload_intent_id=None,
        attempt_count=0,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(job)
    session.commit()

    schema_version = "mirror.demo/DemoJobBinding/v1"
    request_digest = "3" * 64
    payload = {
        "demo_actor_id": actor.id,
        "demo_session_id": None,
        "endpoint_operation": endpoint_operation,
        "idempotency_key_hash": client_key_hash,
        "job_id": job.id,
        "request_digest": request_digest,
        "target_id": actor.id,
        "target_type": "DEMO_ACTOR",
    }
    binding = DemoJobBinding(
        id=new_id(),
        schema_version=schema_version,
        canonical_payload=payload,
        content_digest=_digest(schema_version, payload),
        created_at=utcnow(),
        demo_actor_id=actor.id,
        demo_session_id=None,
        job_id=job.id,
        endpoint_operation=endpoint_operation,
        idempotency_key_hash=client_key_hash,
        request_digest=request_digest,
        target_type="DEMO_ACTOR",
        target_id=actor.id,
    )
    session.add(binding)
    session.commit()
    assert binding.job_id == job.id

    with pytest.raises((IntegrityError, DBAPIError)):
        session.execute(
            update(DemoJobBinding)
            .where(DemoJobBinding.id == binding.id)
            .values(request_digest="4" * 64)
        )
    session.rollback()


def test_concurrent_job_binding_idempotency_has_one_canonical_winner(session: Session) -> None:
    actor = _insert_actor(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    actor_id = actor.id
    endpoint_operation = "profile.compile"
    client_key_hash = "b" * 64
    formal_hash = hashlib.sha256(
        (
            f"mirror.demo/JobIdempotency/v1\n{actor_id}\n{endpoint_operation}\n{client_key_hash}"
        ).encode()
    ).hexdigest()
    barrier = Barrier(2)

    def create_binding(request_suffix: str) -> str:
        engine = create_engine(database_url)
        try:
            with Session(engine) as worker_session:
                job = Job(
                    id=new_id(),
                    job_type=f"demo_p3_p7.{endpoint_operation}",
                    status="PENDING",
                    idempotency_key_hash=formal_hash,
                    request_id=f"demo-d01b-concurrent-{request_suffix}",
                    payload={},
                    owner_user_id=None,
                )
                worker_session.add(job)
                barrier.wait(timeout=10)
                try:
                    worker_session.flush()
                    worker_actor = worker_session.get(DemoActor, actor_id)
                    assert worker_actor is not None
                    _insert_demo_row(
                        worker_session,
                        DemoJobBinding,
                        demo_actor_id=actor_id,
                        demo_session_id=None,
                        job_id=job.id,
                        endpoint_operation=endpoint_operation,
                        idempotency_key_hash=client_key_hash,
                        request_digest=hashlib.sha256(request_suffix.encode()).hexdigest(),
                        target_type="DEMO_ACTOR",
                        target_id=actor_id,
                    )
                except (DBAPIError, IntegrityError):
                    worker_session.rollback()
                    return "conflict"
                return "created"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(create_binding, ("left", "right")))
    assert results == ["conflict", "created"]
    session.expire_all()
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM demo_job_bindings "
                "WHERE demo_actor_id=:actor_id AND endpoint_operation=:operation "
                "AND idempotency_key_hash=:key_hash"
            ),
            {"actor_id": actor.id, "operation": endpoint_operation, "key_hash": client_key_hash},
        )
        == 1
    )


def test_command_binding_accepts_all_six_synchronous_operations(session: Session) -> None:
    graph = _insert_full_demo_graph(session)
    actor = graph["actor"]
    demo_session = graph["session"]
    style_event = _insert_preference_event(
        session,
        actor,
        sequence=3,
        previous_digest=graph["accepted_event"].content_digest,
        signal={"style_context": "editorial"},
        demo_session=demo_session,
        event_type="EXPLICIT_STYLE_SELECTION",
    )
    session_command = _insert_command_binding(
        session,
        actor,
        endpoint_operation="session.create",
        response_type="DEMO_SESSION",
        response_id=demo_session.id,
        response_status=201,
        demo_session=demo_session,
    )
    style_command = _insert_command_binding(
        session,
        actor,
        endpoint_operation="style_feedback.create",
        response_type="PREFERENCE_EVENT",
        response_id=style_event.id,
        response_status=201,
        demo_session=demo_session,
    )
    constraint_command = _insert_command_binding(
        session,
        actor,
        endpoint_operation="constraint.create",
        response_type="IDENTITY_CONSTRAINTS",
        response_id=graph["constraints"].id,
        response_status=201,
        demo_session=demo_session,
    )
    feedback_command = _insert_command_binding(
        session,
        actor,
        endpoint_operation="image_version.feedback",
        response_type="PREFERENCE_EVENT",
        response_id=graph["accepted_event"].id,
        response_status=201,
        demo_session=demo_session,
    )

    cancelled_job = session.get(Job, graph["compiler_binding"].job_id)
    assert cancelled_job is not None
    cancelled_job.status = "CANCELLED"
    cancelled_job.finalized_at = utcnow()
    cancelled_job.result_code = "CANCELLED_BY_USER"
    session.commit()
    cancel_command = _insert_command_binding(
        session,
        actor,
        endpoint_operation="job.cancel",
        response_type="JOB",
        response_id=cancelled_job.id,
        response_status=200,
        demo_session=demo_session,
    )

    commands = {
        graph["response_command_binding"].endpoint_operation,
        session_command.endpoint_operation,
        style_command.endpoint_operation,
        constraint_command.endpoint_operation,
        feedback_command.endpoint_operation,
        cancel_command.endpoint_operation,
    }
    assert commands == {
        "session.create",
        "questionnaire.response.create",
        "style_feedback.create",
        "constraint.create",
        "image_version.feedback",
        "job.cancel",
    }


@pytest.mark.parametrize(
    ("response_type", "response_status"),
    (("JOB", 201), ("DEMO_SESSION", 200)),
)
def test_command_binding_rejects_operation_type_or_status_mismatch(
    session: Session, response_type: str, response_status: int
) -> None:
    actor = _insert_actor(session)
    demo_session = _insert_session(session, actor, config={"command": 1})
    with pytest.raises(DBAPIError, match="operation and typed response disagree"):
        _insert_command_binding(
            session,
            actor,
            endpoint_operation="session.create",
            response_type=response_type,
            response_id=demo_session.id,
            response_status=response_status,
            demo_session=demo_session,
        )
    session.rollback()


def test_command_binding_rejects_wrong_owner_and_target_lifecycle(session: Session) -> None:
    actor = _insert_actor(session)
    other_actor = _insert_actor(session)
    other_session = _insert_session(session, other_actor, config={"other": 1})
    with pytest.raises(DBAPIError):
        _insert_command_binding(
            session,
            actor,
            endpoint_operation="session.create",
            response_type="DEMO_SESSION",
            response_id=other_session.id,
            response_status=201,
            demo_session=other_session,
        )
    session.rollback()

    graph = _insert_full_demo_graph(session)
    with pytest.raises(DBAPIError, match="response ownership or lifecycle mismatch"):
        _insert_command_binding(
            session,
            graph["actor"],
            endpoint_operation="questionnaire.response.create",
            response_type="QUESTIONNAIRE_STEP",
            response_id=graph["questionnaire_step"].id,
            response_status=201,
            demo_session=graph["session"],
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="response ownership or lifecycle mismatch"):
        _insert_command_binding(
            session,
            graph["actor"],
            endpoint_operation="image_version.feedback",
            response_type="PREFERENCE_EVENT",
            response_id=graph["source_event"].id,
            response_status=201,
            demo_session=graph["session"],
        )
    session.rollback()
    pending_job = session.get(Job, graph["context_binding"].job_id)
    assert pending_job is not None
    with pytest.raises(DBAPIError, match="response ownership or lifecycle mismatch"):
        _insert_command_binding(
            session,
            graph["actor"],
            endpoint_operation="job.cancel",
            response_type="JOB",
            response_id=pending_job.id,
            response_status=200,
            demo_session=graph["session"],
        )
    session.rollback()


def test_command_binding_response_cannot_be_claimed_by_two_keys(session: Session) -> None:
    actor = _insert_actor(session)
    demo_session = _insert_session(session, actor, config={"typed-response": 1})
    _insert_command_binding(
        session,
        actor,
        endpoint_operation="session.create",
        response_type="DEMO_SESSION",
        response_id=demo_session.id,
        response_status=201,
        demo_session=demo_session,
        idempotency_key_hash="1" * 64,
    )
    with pytest.raises(IntegrityError):
        _insert_command_binding(
            session,
            actor,
            endpoint_operation="session.create",
            response_type="DEMO_SESSION",
            response_id=demo_session.id,
            response_status=201,
            demo_session=demo_session,
            idempotency_key_hash="2" * 64,
        )
    session.rollback()


def test_concurrent_command_binding_has_one_atomic_canonical_winner(session: Session) -> None:
    actor = _insert_actor(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    actor_id = actor.id
    client_key_hash = "c" * 64
    barrier = Barrier(2)

    def create_session_command(marker: str) -> str:
        engine = create_engine(database_url)
        try:
            with Session(engine) as worker_session:
                worker_actor = worker_session.get(DemoActor, actor_id)
                assert worker_actor is not None
                target_session = _build_demo_row(
                    DemoSession,
                    created_at=worker_actor.created_at,
                    demo_actor_id=actor_id,
                    config={"marker": marker},
                    context_seed=hashlib.sha256(marker.encode()).hexdigest(),
                    expires_at=datetime(2026, 8, 24, 0, 0, tzinfo=UTC),
                    closed_at=None,
                    tombstoned_at=None,
                )
                command_binding = _build_demo_row(
                    DemoCommandBinding,
                    demo_actor_id=actor_id,
                    demo_session_id=target_session.id,
                    endpoint_operation="session.create",
                    idempotency_key_hash=client_key_hash,
                    request_digest=hashlib.sha256(marker.encode()).hexdigest(),
                    response_type="DEMO_SESSION",
                    response_id=target_session.id,
                    response_status=201,
                )
                worker_session.add(target_session)
                worker_session.flush()
                worker_session.add(command_binding)
                barrier.wait(timeout=10)
                try:
                    worker_session.commit()
                except (DBAPIError, IntegrityError):
                    worker_session.rollback()
                    return "conflict"
                return "created"
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(create_session_command, ("left", "right")))
    assert results == ["conflict", "created"]
    session.expire_all()
    assert (
        session.scalar(
            text(
                "SELECT count(*) FROM demo_command_bindings "
                "WHERE demo_actor_id=:actor_id AND endpoint_operation='session.create' "
                "AND idempotency_key_hash=:key_hash"
            ),
            {"actor_id": actor_id, "key_hash": client_key_hash},
        )
        == 1
    )
    assert session.scalar(text("SELECT count(*) FROM demo_sessions")) == 1


def test_empty_downgrade_and_reupgrade_lifecycle(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _truncate_demo_authority(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    try:
        command.downgrade(config, D02_DOWN_REVISION)
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
            D02_DOWN_REVISION
        )
        assert session.scalar(text("SELECT to_regclass('demo_pair_screening_reports') IS NULL"))
        assert session.scalar(text("SELECT to_regclass('demo_command_bindings') IS NOT NULL"))
        command.upgrade(config, DEMO_REVISION)
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION
        assert session.scalar(text("SELECT to_regclass('demo_pair_screening_reports') IS NOT NULL"))

        command.downgrade(config, BASE_DEMO_REVISION)
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
            BASE_DEMO_REVISION
        )
        assert session.scalar(text("SELECT to_regclass('demo_command_bindings') IS NULL"))
        command.upgrade(config, DEMO_REVISION)
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION

        command.downgrade(config, FORMAL_DOWN_REVISION)
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
            FORMAL_DOWN_REVISION
        )
        assert (
            session.scalar(text("SELECT count(*) FROM pg_tables WHERE tablename LIKE 'demo_%'"))
            == 0
        )
    finally:
        command.upgrade(config, DEMO_REVISION)
    assert session.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION


def test_populated_command_authority_blocks_downgrade_to_demo_base(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = _insert_actor(session)
    demo_session = _insert_session(session, actor, config={"downgrade": 2})
    binding = _insert_command_binding(
        session,
        actor,
        endpoint_operation="session.create",
        response_type="DEMO_SESSION",
        response_id=demo_session.id,
        response_status=201,
        demo_session=demo_session,
    )
    binding_id = binding.id
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    session.close()

    try:
        with pytest.raises(DBAPIError, match="command authority downgrade blocked"):
            command.downgrade(config, BASE_DEMO_REVISION)

        engine = create_engine(database_url)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                DEMO_REVISION
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM demo_command_bindings WHERE id=:binding_id"),
                    {"binding_id": binding_id},
                )
                == 1
            )
        engine.dispose()
    finally:
        command.upgrade(config, DEMO_REVISION)


def test_populated_downgrade_fails_closed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = _insert_actor(session)
    actor_id = actor.id
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    session.close()

    try:
        with pytest.raises(DBAPIError, match="downgrade blocked by populated table"):
            command.downgrade(config, FORMAL_DOWN_REVISION)

        engine = create_engine(database_url)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                DEMO_REVISION
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM demo_actors WHERE id=:actor_id"),
                    {"actor_id": actor_id},
                )
                == 1
            )
        engine.dispose()
    finally:
        command.upgrade(config, DEMO_REVISION)


@pytest.mark.parametrize(
    "populated_authority",
    ("job", "job_attempt", "asset_variant"),
)
def test_populated_formal_demo_authority_blocks_downgrade(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    populated_authority: str,
) -> None:
    """Each formal authority class independently prevents destructive rollback."""
    job = Job(
        id=new_id(),
        job_type="demo_p3_p7.profile.compile",
        status="PENDING",
        idempotency_key_hash=hashlib.sha256(new_id().encode()).hexdigest(),
        request_id=f"demo-d01b-downgrade-{populated_authority}",
        payload={},
        owner_user_id=None,
    )
    if populated_authority in {"job", "job_attempt"}:
        session.add(job)
        session.commit()
    if populated_authority == "job_attempt":
        session.add(
            JobAttempt(
                id=new_id(),
                job_id=job.id,
                attempt=1,
                status="PENDING",
                started_at=utcnow(),
            )
        )
        session.commit()
    if populated_authority == "asset_variant":
        source_asset = Asset(
            id=new_id(),
            owner_user_id=None,
            asset_role="synthetic",
            storage_key=f"internal-synthetic/v1/demo-d01b/{new_id()}",
            mime_type="image/png",
            byte_size=1,
            width=1,
            height=1,
            sha256=hashlib.sha256(new_id().encode()).hexdigest(),
            synthetic=True,
            is_ai_generated=True,
            is_ai_modified=False,
            internal_purpose="synthetic_dataset",
        )
        result_asset = Asset(
            id=new_id(),
            owner_user_id=None,
            asset_role="synthetic",
            storage_key=f"internal-synthetic/v1/demo-d01b/{new_id()}",
            mime_type="image/png",
            byte_size=1,
            width=1,
            height=1,
            sha256=hashlib.sha256(new_id().encode()).hexdigest(),
            synthetic=True,
            is_ai_generated=True,
            is_ai_modified=True,
            internal_purpose="synthetic_dataset",
        )
        session.add_all((source_asset, result_asset))
        session.commit()
        session.add(
            AssetVariant(
                id=new_id(),
                source_asset_id=source_asset.id,
                result_asset_id=result_asset.id,
                variant_type="demo_p3_p7_fixture",
            )
        )
        session.commit()

    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    session.close()

    expected_message = {
        "job": "Demo Job authority",
        "job_attempt": "Demo JobAttempt authority",
        "asset_variant": "Demo AssetVariant authority",
    }[populated_authority]
    try:
        with pytest.raises(DBAPIError, match=expected_message):
            command.downgrade(config, FORMAL_DOWN_REVISION)

        engine = create_engine(database_url)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                DEMO_REVISION
            )
        engine.dispose()
    finally:
        command.upgrade(config, DEMO_REVISION)

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname LIKE 'trg_demo_authority_%'"
                )
            )
            == 29
        )
    engine.dispose()
