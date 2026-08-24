from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from threading import Barrier, Event
from typing import Any, cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, create_engine, delete, inspect, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import conv
from test_demo_d02_authority import (
    _complete_report_fixture,
    _facts_identity_manifest,
    _resign_report_row,
)
from test_geometry_variant_authority_invariants import _canonical_source, _result_asset

from mirror_api.demo_d02_authority import derive_asset_variant_id
from mirror_api.demo_measurement_quality import IMPORT_CONFIG_DIGEST
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

DEMO_REVISION = "demo_0005_d02_quality_auth"
D02_QUALITY_DOWN_REVISION = "demo_0004_d09_episode_prov"
D09_DOWN_REVISION = "demo_0003_d02_import_auth"
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
        (
            "mirror.demo/DemoSyntheticIdentity/v3"
            if authority_fields.get("importer_version") == "demo-d02-identity-importer-v3"
            else "mirror.demo/DemoSyntheticIdentity/v2"
        )
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
    if model is DemoSyntheticIdentity and schema_version.endswith(("/v2", "/v3")):
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
    if (
        model is DemoSyntheticIdentity
        and schema_version.endswith(("/v2", "/v3"))
        and row_id is None
    ):
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


def _insert_legacy_local_d02_identity(
    session: Session, *, marker: str
) -> tuple[Asset, DemoSyntheticIdentity]:
    """Persist the frozen Revision 9 local-copy authority for migration tests."""

    source_asset = Asset(
        id=new_id(),
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key=f"demo-d02-recovered/{marker}/{new_id()}",
        mime_type="image/jpeg",
        byte_size=4096,
        width=64,
        height=64,
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


def _insert_local_d02_identity(
    session: Session, *, marker: str
) -> tuple[Asset, DemoSyntheticIdentity]:
    source_marker = marker[-1].lower()
    facts, identity_authority, _ = _facts_identity_manifest(source_marker=source_marker)
    asset_id = cast(str, identity_authority["formal_canonical_asset_id"])
    source_asset = session.get(Asset, asset_id)
    if source_asset is None:
        source_asset = Asset(
            id=asset_id,
            owner_user_id=None,
            asset_role="synthetic",
            internal_purpose="synthetic_dataset",
            storage_key=f"demo-d02-recovered/{marker}/{new_id()}",
            mime_type=facts["source_asset_mime_type"],
            byte_size=facts["source_asset_byte_size"],
            width=facts["source_asset_width"],
            height=facts["source_asset_height"],
            sha256=facts["source_asset_sha256"],
            synthetic=True,
            is_ai_generated=True,
            is_ai_modified=False,
        )
        session.add(source_asset)
        session.commit()
    else:
        assert source_asset.owner_user_id is None
        assert source_asset.asset_role == "synthetic"
        assert source_asset.internal_purpose == "synthetic_dataset"
        assert source_asset.mime_type == facts["source_asset_mime_type"]
        assert source_asset.byte_size == facts["source_asset_byte_size"]
        assert source_asset.width == facts["source_asset_width"]
        assert source_asset.height == facts["source_asset_height"]
        assert source_asset.sha256 == facts["source_asset_sha256"]
        assert source_asset.synthetic is True
        assert source_asset.is_ai_generated is True
        assert source_asset.is_ai_modified is False
        assert source_asset.deleted_at is None
    identity_fields = {
        column.name: identity_authority[column.name]
        for column in DemoSyntheticIdentity.__table__.columns
        if column.name in identity_authority and column.computed is None
    }
    identity_fields["created_at"] = datetime.fromisoformat(
        str(identity_authority["created_at"]).replace("Z", "+00:00")
    )
    admission = DemoSyntheticIdentity(**identity_fields)
    session.add(admission)
    session.commit()
    return source_asset, admission


_D02_PREREGISTRATION_SHA256 = "3fb0a1192d006560d45083b8d9d933f15a22648c0108f81ef305d31980073ba3"
_D02_SOURCE_MANIFEST_DIGEST = "eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4"
_D02_DIMENSION_MANIFEST_DIGEST = "d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a"
_D02_GEOMETRY_ONTOLOGY_DIGEST = "d902fe2cfdf69db9f62ccc2e5fa7c569227d652f1204aa683742fc3c592f38b9"
_D02_CANDIDATE_DIMENSIONS = ("jaw_width", "chin_height", "eye_spacing")
_D02_DIRECTIONS = ("DECREASE", "INCREASE")
_D02_MAGNITUDES = (15_000, 30_000)
_D02_CONTROL_DIMENSIONS = {
    "jaw_width": (
        "cheekbone_width",
        "chin_height",
        "eye_spacing",
        "mouth_width",
        "nose_width",
    ),
    "chin_height": (
        "cheekbone_width",
        "eye_spacing",
        "jaw_width",
        "mouth_width",
        "nose_width",
    ),
    "eye_spacing": (
        "cheekbone_width",
        "chin_height",
        "jaw_width",
        "mouth_width",
        "nose_width",
    ),
}


def _d02_fixed18(value: Decimal | int | str) -> str:
    decimal_value = Decimal(value)
    if decimal_value == 0:
        decimal_value = Decimal(0)
    return format(
        decimal_value.quantize(Decimal("0.000000000000000001"), rounding=ROUND_HALF_EVEN),
        ".18f",
    )


def _d02_ppm(value: Decimal | str) -> int:
    return int(
        (Decimal(value) * Decimal(1_000_000)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    )


def _d02_record(
    schema_version: str,
    payload: dict[str, Any],
    *,
    digest_key: str = "record_digest",
) -> dict[str, Any]:
    record = {"schema_version": schema_version, **payload}
    record[digest_key] = _digest(schema_version, payload)
    return record


def _d02_derived_id(schema_version: str, payload: dict[str, Any]) -> str:
    return _digest(schema_version, payload)[:32]


def _d02_screening_policy_digest() -> str:
    return _digest(
        "mirror.demo/D02ScreeningPolicyRoot/v1",
        {
            "preregistration_id": "P3_P7_D02_PAIR_SCREENING_V9",
            "policy_schema": "mirror.demo/D02PairScreeningPolicy/v8",
            "policy_revision": 9,
            "preregistration_sha256": _D02_PREREGISTRATION_SHA256,
        },
    )


def _d02_lock_policy_digest() -> str:
    return _digest(
        "mirror.demo/D02EmptyNeutralLockPolicy/v1",
        {
            "policy_id": "D02_FROZEN_EMPTY_NEUTRAL_POLICY_V1",
            "ordered_feature_locks": [],
            "ordered_temporary_session_overrides": [],
            "ordered_prohibited_operations": [],
        },
    )


def _insert_legacy_d02_question_bank_fixture(
    session: Session,
    primary_source: Asset,
    primary_admission: DemoSyntheticIdentity,
) -> tuple[DemoQuestionBank, DemoQuestionPair]:
    """Build the complete Revision 9 report DAG and its selected 16-pair bank."""

    # The full graph may pass a formal Phase-2 source here. D02 report authority is
    # deliberately rebuilt from four local recovered-copy admissions only.
    _ = primary_source, primary_admission
    marker = new_id()

    def evidence_digest(label: str) -> str:
        return _digest(
            "mirror.demo/D02FixtureEvidence/v1",
            {"label": label, "marker": marker},
        )

    source_authorities = [
        _insert_legacy_local_d02_identity(session, marker=f"{marker}-source-{source_index}")
        for source_index in range(1, 5)
    ]
    source_authorities.sort(
        key=lambda authority: (str(authority[1].source_authority_key), authority[1].id)
    )

    source_entries: list[dict[str, Any]] = []
    source_fixtures: list[dict[str, Any]] = []
    for source_ordinal, (source_asset, admission) in enumerate(source_authorities, start=1):
        raw_entries = admission.source_fact_snapshot["raw_measurement_authority"]["ordered_entries"]
        projection_entries = admission.source_measurement_projection["ordered_entries"]
        ordered_measurements = [
            {
                "schema_version": "mirror.demo/D02SupportedSourceMeasurement/v1",
                "dimension_key": str(raw_entry["dimension_key"]),
                "raw_value_fixed18": str(raw_entry["raw_value_fixed18"]),
                "raw_confidence_fixed18": str(raw_entry["raw_confidence_fixed18"]),
                "raw_reliability_fixed18": str(raw_entry["raw_reliability_fixed18"]),
                "value_ppm": int(projection_entry["value_ppm"]),
                "confidence_ppm": int(projection_entry["confidence_ppm"]),
                "reliability_ppm": int(projection_entry["reliability_ppm"]),
                "unit": "FACE_HEIGHT_PPM",
            }
            for raw_entry, projection_entry in zip(raw_entries, projection_entries, strict=True)
        ]
        source_entry = _d02_record(
            "mirror.demo/D02SourceAuthorityManifestEntry/v2",
            {
                "source_ordinal": source_ordinal,
                "source_authority_kind": "DEMO_LOCAL_IMPORTED_COPY",
                "source_authority_key": admission.source_authority_key,
                "source_admission_event_id": admission.id,
                "source_admission_content_digest": admission.content_digest,
                "source_output_id": admission.source_output_id,
                "source_asset_id": source_asset.id,
                "source_asset_sha256": source_asset.sha256,
                "source_asset_byte_size": source_asset.byte_size,
                "source_asset_mime_type": source_asset.mime_type,
                "source_asset_width": source_asset.width,
                "source_asset_height": source_asset.height,
                "source_receipt_digest": admission.source_receipt_digest,
                "source_authority_digest": admission.source_authority_digest,
                "source_qa_snapshot_digest": admission.source_qa_snapshot_digest,
                "source_landmark_digest": admission.source_landmark_digest,
                "source_measurement_digest": admission.source_measurement_digest,
                "source_provenance_digest": admission.source_provenance_digest,
                "source_fact_snapshot_digest": admission.source_fact_snapshot_digest,
                "raw_measurement_authority_digest": admission.source_measurement_digest,
                "source_measurement_projection_digest": (
                    admission.source_measurement_projection_digest
                ),
                "adult_synthetic_attested": True,
                "original_formal_identity_id_status": ("UNKNOWN_REDACTED_NOT_RECOVERED"),
                "source_p2_candidate_manifest_content_digest": (_D02_SOURCE_MANIFEST_DIGEST),
                "dimension_authority_manifest_content_digest": (_D02_DIMENSION_MANIFEST_DIGEST),
                "ordered_supported_measurements": ordered_measurements,
            },
        )
        source_entries.append(source_entry)
        source_fixtures.append(
            {
                "asset": source_asset,
                "admission": admission,
                "entry": source_entry,
                "measurements": {str(item["dimension_key"]): item for item in ordered_measurements},
            }
        )

    source_manifest_digest = _digest("mirror.demo/D02SourceAuthorityManifest/v1", source_entries)
    screening_policy_digest = _d02_screening_policy_digest()
    lock_policy_digest = _d02_lock_policy_digest()
    report_digests = {
        "source_manifest_digest": source_manifest_digest,
        "screening_policy_digest": screening_policy_digest,
        "runtime_manifest_digest": evidence_digest("runtime-manifest"),
        "vision_model_manifest_digest": evidence_digest("vision-model-manifest"),
        "topology_digest": evidence_digest("topology"),
        "measurement_config_digest": evidence_digest("measurement-config"),
        "manual_review_policy_digest": evidence_digest("manual-review-policy"),
        "duplicate_policy_digest": evidence_digest("duplicate-policy"),
        "phash_implementation_digest": evidence_digest("phash-implementation"),
    }
    execution_config_payload = {
        "screening_policy_digest": screening_policy_digest,
        "runtime_manifest_digest": report_digests["runtime_manifest_digest"],
        "vision_model_manifest_digest": report_digests["vision_model_manifest_digest"],
        "topology_digest": report_digests["topology_digest"],
        "measurement_config_digest": report_digests["measurement_config_digest"],
        "manual_review_policy_digest": report_digests["manual_review_policy_digest"],
        "duplicate_policy_digest": report_digests["duplicate_policy_digest"],
        "phash_implementation_digest": report_digests["phash_implementation_digest"],
        "geometry_algorithm_version": "demo-d02-geometry-v1",
        "runtime_config_digest": evidence_digest("runtime-config"),
        "output_policy_version": "demo-d02-output-jpeg-v1",
        "output_width": 64,
        "output_height": 64,
        "determinism_level": "BIT_EXACT",
    }
    execution_config_digest = _digest(
        "mirror.demo/D02ExecutionConfiguration/v1", execution_config_payload
    )

    case_fixtures: list[dict[str, Any]] = []
    case_by_key: dict[tuple[int, str, str, int], dict[str, Any]] = {}
    for source_fixture in source_fixtures:
        source_entry = source_fixture["entry"]
        for priority_index, dimension_key in enumerate(_D02_CANDIDATE_DIMENSIONS, start=1):
            for direction_index, direction in enumerate(_D02_DIRECTIONS, start=1):
                for magnitude_index, magnitude_ppm in enumerate(_D02_MAGNITUDES, start=1):
                    case_ordinal = len(case_fixtures) + 1
                    case_id_payload = {
                        "source_manifest_digest": source_manifest_digest,
                        "source_authority_key": source_entry["source_authority_key"],
                        "source_admission_event_id": source_entry["source_admission_event_id"],
                        "source_asset_sha256": source_entry["source_asset_sha256"],
                        "source_p2_candidate_manifest_content_digest": (
                            _D02_SOURCE_MANIFEST_DIGEST
                        ),
                        "dimension_authority_manifest_content_digest": (
                            _D02_DIMENSION_MANIFEST_DIGEST
                        ),
                        "dimension_key": dimension_key,
                        "direction": direction,
                        "magnitude_ppm": magnitude_ppm,
                        "execution_config_digest": execution_config_digest,
                    }
                    case_id = _d02_derived_id("mirror.demo/D02GeometryCaseId/v1", case_id_payload)
                    ordered_controls = list(_D02_CONTROL_DIMENSIONS[dimension_key])
                    warp_plan_digest = evidence_digest(f"warp-plan/{case_id}")
                    specification_payload = {
                        "source_manifest_digest": source_manifest_digest,
                        "source_ordinal": source_entry["source_ordinal"],
                        "source_authority_key": source_entry["source_authority_key"],
                        "source_admission_event_id": source_entry["source_admission_event_id"],
                        "source_asset_id": source_entry["source_asset_id"],
                        "source_asset_sha256": source_entry["source_asset_sha256"],
                        "source_qa_snapshot_digest": source_entry["source_qa_snapshot_digest"],
                        "source_measurement_projection_digest": source_entry[
                            "source_measurement_projection_digest"
                        ],
                        "source_p2_candidate_manifest_content_digest": (
                            _D02_SOURCE_MANIFEST_DIGEST
                        ),
                        "dimension_authority_manifest_content_digest": (
                            _D02_DIMENSION_MANIFEST_DIGEST
                        ),
                        "geometry_ontology_version_digest": (_D02_GEOMETRY_ONTOLOGY_DIGEST),
                        "dimension_key": dimension_key,
                        "priority_index": priority_index,
                        "direction": direction,
                        "direction_index": direction_index,
                        "magnitude_ppm": magnitude_ppm,
                        "magnitude_index": magnitude_index,
                        "ordered_control_dimensions": ordered_controls,
                        "warp_plan_digest": warp_plan_digest,
                        "geometry_algorithm_version": execution_config_payload[
                            "geometry_algorithm_version"
                        ],
                        "runtime_manifest_digest": report_digests["runtime_manifest_digest"],
                        "runtime_config_digest": execution_config_payload["runtime_config_digest"],
                        "output_policy_version": execution_config_payload["output_policy_version"],
                        "output_width": 64,
                        "output_height": 64,
                        "determinism_level": "BIT_EXACT",
                        "execution_config_digest": execution_config_digest,
                    }
                    case_specification_digest = _digest(
                        "mirror.demo/D02GeometryCaseSpecification/v1",
                        specification_payload,
                    )
                    case_entry = _d02_record(
                        "mirror.demo/D02GeometryCaseManifestEntry/v3",
                        {
                            "case_ordinal": case_ordinal,
                            "case_id": case_id,
                            **specification_payload,
                            "case_specification_digest": case_specification_digest,
                        },
                    )
                    result_sha256 = evidence_digest(f"result-bytes/{case_id}")
                    result_output_id = f"d02-result-{case_id}"
                    result_asset_id = evidence_digest(f"result-asset/{case_id}")[:32]
                    asset_variant_id = evidence_digest(f"variant/{case_id}")[:32]
                    fixture = {
                        "source": source_fixture,
                        "entry": case_entry,
                        "result_output_id": result_output_id,
                        "result_sha256": result_sha256,
                        "result_asset_id": result_asset_id,
                        "asset_variant_id": asset_variant_id,
                    }
                    case_fixtures.append(fixture)
                    case_by_key[
                        (
                            int(source_entry["source_ordinal"]),
                            dimension_key,
                            direction,
                            magnitude_ppm,
                        )
                    ] = fixture

    ordered_case_manifest = [fixture["entry"] for fixture in case_fixtures]
    case_manifest_digest = _digest("mirror.demo/D02GeometryCaseManifest/v1", ordered_case_manifest)
    report_digests["case_manifest_digest"] = case_manifest_digest

    source_m3_records: list[dict[str, Any]] = []
    for source_fixture in source_fixtures:
        source_entry = source_fixture["entry"]
        for repeat_index in range(1, 4):
            id_payload = {
                "source_manifest_digest": source_manifest_digest,
                "source_authority_key": source_entry["source_authority_key"],
                "source_admission_event_id": source_entry["source_admission_event_id"],
                "source_asset_id": source_entry["source_asset_id"],
                "source_asset_sha256": source_entry["source_asset_sha256"],
                "repeat_index": repeat_index,
                "vision_model_manifest_digest": report_digests["vision_model_manifest_digest"],
                "runtime_manifest_digest": report_digests["runtime_manifest_digest"],
                "topology_digest": report_digests["topology_digest"],
            }
            source_m3_records.append(
                _d02_record(
                    "mirror.demo/D02SourceM3RepeatRecord/v1",
                    {
                        "source_m3_record_id": _d02_derived_id(
                            "mirror.demo/D02SourceM3RecordId/v1", id_payload
                        ),
                        "source_ordinal": source_entry["source_ordinal"],
                        "source_authority_key": source_entry["source_authority_key"],
                        "source_admission_event_id": source_entry["source_admission_event_id"],
                        "source_asset_id": source_entry["source_asset_id"],
                        "source_asset_sha256": source_entry["source_asset_sha256"],
                        "repeat_index": repeat_index,
                        "execution_receipt_digest": evidence_digest(
                            f"source-m3-receipt/{source_entry['source_ordinal']}/{repeat_index}"
                        ),
                        "vision_model_manifest_digest": report_digests[
                            "vision_model_manifest_digest"
                        ],
                        "runtime_manifest_digest": report_digests["runtime_manifest_digest"],
                        "topology_digest": report_digests["topology_digest"],
                        "canonical_output_digest": source_entry["source_qa_snapshot_digest"],
                        "landmark_digest": source_entry["source_landmark_digest"],
                        "measurement_digest": source_entry["source_measurement_digest"],
                        "face_count": 1,
                        "landmark_count": 478,
                        "coordinates_finite": True,
                        "coordinates_in_bounds": True,
                        "repeat_gate_passed": True,
                    },
                )
            )

    m4_records: list[dict[str, Any]] = []
    result_m3_records: list[dict[str, Any]] = []
    for case_fixture in case_fixtures:
        case_entry = case_fixture["entry"]
        source_entry = case_fixture["source"]["entry"]
        case_m4_records: list[dict[str, Any]] = []
        for replay_index in range(1, 3):
            id_payload = {
                "case_id": case_entry["case_id"],
                "case_specification_digest": case_entry["case_specification_digest"],
                "replay_index": replay_index,
                "geometry_algorithm_version": case_entry["geometry_algorithm_version"],
                "runtime_manifest_digest": case_entry["runtime_manifest_digest"],
                "runtime_config_digest": case_entry["runtime_config_digest"],
                "determinism_level": case_entry["determinism_level"],
            }
            record = _d02_record(
                "mirror.demo/D02M4ExecutionRecord/v1",
                {
                    "m4_execution_record_id": _d02_derived_id(
                        "mirror.demo/D02M4ExecutionRecordId/v1", id_payload
                    ),
                    "case_id": case_entry["case_id"],
                    "case_specification_digest": case_entry["case_specification_digest"],
                    "replay_index": replay_index,
                    "source_output_id": source_entry["source_output_id"],
                    "source_asset_id": source_entry["source_asset_id"],
                    "source_asset_sha256": source_entry["source_asset_sha256"],
                    "result_output_id": case_fixture["result_output_id"],
                    "result_sha256": case_fixture["result_sha256"],
                    "result_byte_size": 4096,
                    "result_mime_type": "image/jpeg",
                    "result_width": 64,
                    "result_height": 64,
                    "changed_pixel_count": 64,
                    "warp_plan_digest": case_entry["warp_plan_digest"],
                    "geometry_algorithm_version": case_entry["geometry_algorithm_version"],
                    "runtime_manifest_digest": case_entry["runtime_manifest_digest"],
                    "runtime_config_digest": case_entry["runtime_config_digest"],
                    "determinism_level": case_entry["determinism_level"],
                    "execution_receipt_digest": evidence_digest(
                        f"m4-receipt/{case_entry['case_id']}/{replay_index}"
                    ),
                    "execution_succeeded": True,
                },
            )
            case_m4_records.append(record)
            m4_records.append(record)
        case_fixture["m4_records"] = case_m4_records

        case_result_m3: list[dict[str, Any]] = []
        for repeat_index in range(1, 4):
            id_payload = {
                "case_id": case_entry["case_id"],
                "case_specification_digest": case_entry["case_specification_digest"],
                "result_output_id": case_fixture["result_output_id"],
                "result_sha256": case_fixture["result_sha256"],
                "repeat_index": repeat_index,
                "vision_model_manifest_digest": report_digests["vision_model_manifest_digest"],
                "runtime_manifest_digest": report_digests["runtime_manifest_digest"],
                "topology_digest": report_digests["topology_digest"],
            }
            record = _d02_record(
                "mirror.demo/D02ResultM3RepeatRecord/v1",
                {
                    "result_m3_record_id": _d02_derived_id(
                        "mirror.demo/D02ResultM3RecordId/v1", id_payload
                    ),
                    "case_id": case_entry["case_id"],
                    "case_specification_digest": case_entry["case_specification_digest"],
                    "result_output_id": case_fixture["result_output_id"],
                    "result_sha256": case_fixture["result_sha256"],
                    "repeat_index": repeat_index,
                    "execution_receipt_digest": evidence_digest(
                        f"result-m3-receipt/{case_entry['case_id']}/{repeat_index}"
                    ),
                    "vision_model_manifest_digest": report_digests["vision_model_manifest_digest"],
                    "runtime_manifest_digest": report_digests["runtime_manifest_digest"],
                    "topology_digest": report_digests["topology_digest"],
                    "canonical_output_digest": evidence_digest(
                        f"result-canonical/{case_entry['case_id']}"
                    ),
                    "landmark_digest": evidence_digest(f"result-landmarks/{case_entry['case_id']}"),
                    "measurement_observation_digest": evidence_digest(
                        f"result-measurement/{case_entry['case_id']}"
                    ),
                    "face_count": 1,
                    "landmark_count": 478,
                    "coordinates_finite": True,
                    "coordinates_in_bounds": True,
                    "observation_state": "SUPPORTED",
                    "repeat_gate_passed": True,
                },
            )
            case_result_m3.append(record)
            result_m3_records.append(record)
        case_fixture["result_m3_records"] = case_result_m3

    measurement_records: list[dict[str, Any]] = []
    structure_records: list[dict[str, Any]] = []
    for case_fixture in case_fixtures:
        case_entry = case_fixture["entry"]
        source_measurements = case_fixture["source"]["measurements"]
        target_measurement = dict(source_measurements[case_entry["dimension_key"]])
        control_measurements = [
            dict(source_measurements[dimension_key])
            for dimension_key in case_entry["ordered_control_dimensions"]
        ]
        source_target = Decimal(target_measurement["raw_value_fixed18"])
        delta = Decimal(case_entry["magnitude_ppm"]) / Decimal(1_000_000)
        signed_delta = -delta if case_entry["direction"] == "DECREASE" else delta
        raw_result_target = source_target + signed_delta
        result_measurements: list[dict[str, Any]] = []
        for repeat_index, result_m3 in enumerate(case_fixture["result_m3_records"], start=1):
            control_deltas = [
                {
                    "schema_version": "mirror.demo/D02ControlDelta/v1",
                    "control_ordinal": control_ordinal,
                    "dimension_key": control_measurement["dimension_key"],
                    "raw_source_value_fixed18": control_measurement["raw_value_fixed18"],
                    "raw_result_value_fixed18": control_measurement["raw_value_fixed18"],
                    "raw_absolute_delta_fixed18": _d02_fixed18(0),
                    "drift_ppm": 0,
                }
                for control_ordinal, control_measurement in enumerate(control_measurements, start=1)
            ]
            result_measurements.append(
                {
                    "schema_version": ("mirror.demo/D02SupportedResultMeasurement/v1"),
                    "repeat_index": repeat_index,
                    "result_m3_record_digest": result_m3["record_digest"],
                    "raw_result_target_fixed18": _d02_fixed18(raw_result_target),
                    "raw_signed_target_delta_fixed18": _d02_fixed18(signed_delta),
                    "raw_target_absolute_delta_fixed18": _d02_fixed18(delta),
                    "ordered_control_deltas": control_deltas,
                    "winning_control_ordinal": 1,
                    "max_control_dimension_key": control_deltas[0]["dimension_key"],
                    "raw_max_control_drift_fixed18": _d02_fixed18(0),
                    "measured_signed_delta_ppm": _d02_ppm(signed_delta),
                    "target_absolute_delta_ppm": _d02_ppm(delta),
                    "drift_ppm": 0,
                    "direction_gate_passed": True,
                    "target_min_gate_passed": True,
                    "target_max_gate_passed": True,
                    "control_drift_gate_passed": True,
                }
            )
        peer_fixture = case_by_key[
            (
                int(case_entry["source_ordinal"]),
                str(case_entry["dimension_key"]),
                str(case_entry["direction"]),
                30_000 if case_entry["magnitude_ppm"] == 15_000 else 15_000,
            )
        ]
        measurement_record = _d02_record(
            "mirror.demo/D02MeasurementGateRecord/v3",
            {
                "case_id": case_entry["case_id"],
                "case_specification_digest": case_entry["case_specification_digest"],
                "dimension_key": case_entry["dimension_key"],
                "requested_direction": case_entry["direction"],
                "requested_magnitude_ppm": case_entry["magnitude_ppm"],
                "monotonicity_peer_case_id": peer_fixture["entry"]["case_id"],
                "source_target_measurement": target_measurement,
                "ordered_source_control_measurements": control_measurements,
                "ordered_result_repeat_measurements": result_measurements,
                "measurement_evaluation_state": "SUPPORTED_EVALUATED",
                "gate_evaluation": {
                    "schema_version": ("mirror.demo/D02SupportedMeasurementGateEvaluation/v1"),
                    "direction_gate_passed": True,
                    "target_min_gate_passed": True,
                    "target_max_gate_passed": True,
                    "control_drift_gate_passed": True,
                    "magnitude_monotonicity_gate_passed": True,
                    "measurement_gate_passed": True,
                },
            },
        )
        case_fixture["measurement_record"] = measurement_record
        measurement_records.append(measurement_record)

        result_image_id = _d02_derived_id(
            "mirror.demo/D02ResultImageAuthorityRecordId/v1",
            {
                "authority_role": "RESULT",
                "source_authority_key": case_fixture["source"]["entry"]["source_authority_key"],
                "source_admission_event_id": case_fixture["source"]["entry"][
                    "source_admission_event_id"
                ],
                "case_id": case_entry["case_id"],
                "case_specification_digest": case_entry["case_specification_digest"],
                "result_output_id": case_fixture["result_output_id"],
                "deterministic_result_asset_id": case_fixture["result_asset_id"],
                "sha256": case_fixture["result_sha256"],
            },
        )
        case_fixture["result_image_id"] = result_image_id
        structure_record = _d02_record(
            "mirror.demo/D02DecodeStructureImmutabilityRecord/v1",
            {
                "case_id": case_entry["case_id"],
                "case_specification_digest": case_entry["case_specification_digest"],
                "source_asset_id": case_entry["source_asset_id"],
                "source_asset_sha256": case_entry["source_asset_sha256"],
                "m4_execution_record_digests": [
                    record["record_digest"] for record in case_fixture["m4_records"]
                ],
                "result_output_id": case_fixture["result_output_id"],
                "result_sha256": case_fixture["result_sha256"],
                "result_byte_size": 4096,
                "result_mime_type": "image/jpeg",
                "result_width": 64,
                "result_height": 64,
                "result_image_record_id": result_image_id,
                "source_decode_valid": True,
                "result_decode_valid": True,
                "bounded_dimensions_passed": True,
                "source_checksum_unchanged": True,
                "m4_replay_bytes_equal": True,
                "m4_replay_dimensions_equal": True,
                "changed_pixel_count_equal": True,
                "changed_pixel_count_positive": True,
                "immutable_result_binding_passed": True,
                "exact_lineage_passed": True,
                "target_and_controls_complete": True,
                "structure_gate_passed": True,
            },
        )
        case_fixture["structure_record"] = structure_record
        structure_records.append(structure_record)

    manual_records: list[dict[str, Any]] = []
    manual_by_case: dict[str, dict[str, Any]] = {}
    for decision_sequence, case_fixture in enumerate(
        sorted(case_fixtures, key=lambda fixture: fixture["entry"]["case_id"]),
        start=1,
    ):
        case_id = case_fixture["entry"]["case_id"]
        manual_record = _d02_record(
            "mirror.demo/D02ManualArtifactDecision/v1",
            {
                "case_id": case_id,
                "result_sha256": case_fixture["result_sha256"],
                "manual_review_version": "demo-d02-manual-review-v1",
                "manual_review_policy_digest": report_digests["manual_review_policy_digest"],
                "decision_sequence": decision_sequence,
                "background_seam": False,
                "disconnected_contour": False,
                "duplicated_feature": False,
                "warp_tear": False,
                "verdict": "PASS",
                "review_authority_digest": evidence_digest(f"manual-review-authority/{case_id}"),
            },
            digest_key="manual_decision_digest",
        )
        manual_records.append(manual_record)
        manual_by_case[case_id] = manual_record
        case_fixture["manual_record"] = manual_record

    image_record_payloads: list[dict[str, Any]] = []
    for source_fixture in source_fixtures:
        source_entry = source_fixture["entry"]
        image_record_id = _d02_derived_id(
            "mirror.demo/D02SourceImageAuthorityRecordId/v1",
            {
                "authority_role": "SOURCE",
                "source_authority_key": source_entry["source_authority_key"],
                "source_admission_event_id": source_entry["source_admission_event_id"],
                "source_asset_id": source_entry["source_asset_id"],
                "sha256": source_entry["source_asset_sha256"],
            },
        )
        image_record_payloads.append(
            {
                "schema_version": "mirror.demo/D02SourceImageAuthorityRecord/v2",
                "image_record_id": image_record_id,
                "authority_role": "SOURCE",
                "source_ordinal": source_entry["source_ordinal"],
                "source_authority_key": source_entry["source_authority_key"],
                "source_admission_event_id": source_entry["source_admission_event_id"],
                "source_asset_id": source_entry["source_asset_id"],
                "sha256": source_entry["source_asset_sha256"],
                "byte_size": source_entry["source_asset_byte_size"],
                "mime_type": source_entry["source_asset_mime_type"],
                "width": source_entry["source_asset_width"],
                "height": source_entry["source_asset_height"],
            }
        )
    for case_fixture in case_fixtures:
        source_entry = case_fixture["source"]["entry"]
        case_entry = case_fixture["entry"]
        image_record_payloads.append(
            {
                "schema_version": "mirror.demo/D02ResultImageAuthorityRecord/v2",
                "image_record_id": case_fixture["result_image_id"],
                "authority_role": "RESULT",
                "source_ordinal": source_entry["source_ordinal"],
                "source_authority_key": source_entry["source_authority_key"],
                "source_admission_event_id": source_entry["source_admission_event_id"],
                "case_id": case_entry["case_id"],
                "case_specification_digest": case_entry["case_specification_digest"],
                "result_output_id": case_fixture["result_output_id"],
                "deterministic_result_asset_id": case_fixture["result_asset_id"],
                "sha256": case_fixture["result_sha256"],
                "byte_size": 4096,
                "mime_type": "image/jpeg",
                "width": 64,
                "height": 64,
            }
        )
    image_record_payloads.sort(
        key=lambda record: (str(record["sha256"]), str(record["image_record_id"]))
    )
    image_records: list[dict[str, Any]] = []
    image_by_id: dict[str, dict[str, Any]] = {}
    for image_record_ordinal, record_payload in enumerate(image_record_payloads, start=1):
        schema_version = str(record_payload.pop("schema_version"))
        image_record = _d02_record(
            schema_version,
            {"image_record_ordinal": image_record_ordinal, **record_payload},
            digest_key="image_record_digest",
        )
        image_records.append(image_record)
        image_by_id[str(image_record["image_record_id"])] = image_record

    signatures: list[dict[str, Any]] = []
    for image_record in image_records:
        phash_hex = f"{int(image_record['image_record_ordinal']):016x}"
        signatures.append(
            _d02_record(
                "mirror.demo/D02PHashSignatureRecord/v1",
                {
                    "image_record_ordinal": image_record["image_record_ordinal"],
                    "image_record_id": image_record["image_record_id"],
                    "image_record_digest": image_record["image_record_digest"],
                    "image_sha256": image_record["sha256"],
                    "phash_hex": phash_hex,
                },
                digest_key="signature_digest",
            )
        )
    comparisons: list[dict[str, Any]] = []
    comparison_ordinal = 0
    for left_index in range(52):
        for right_index in range(left_index + 1, 52):
            comparison_ordinal += 1
            left_signature = signatures[left_index]
            right_signature = signatures[right_index]
            distance = (
                int(str(left_signature["phash_hex"]), 16)
                ^ int(str(right_signature["phash_hex"]), 16)
            ).bit_count()
            comparisons.append(
                _d02_record(
                    "mirror.demo/D02PHashComparisonRecord/v1",
                    {
                        "comparison_ordinal": comparison_ordinal,
                        "left_image_record_ordinal": left_index + 1,
                        "left_image_record_id": left_signature["image_record_id"],
                        "left_signature_digest": left_signature["signature_digest"],
                        "right_image_record_ordinal": right_index + 1,
                        "right_image_record_id": right_signature["image_record_id"],
                        "right_signature_digest": right_signature["signature_digest"],
                        "hamming_distance": distance,
                    },
                    digest_key="comparison_digest",
                )
            )

    pair_wrappers: list[dict[str, Any]] = []
    pair_fixtures: list[dict[str, Any]] = []
    for source_fixture in source_fixtures:
        source_entry = source_fixture["entry"]
        for priority_index, dimension_key in enumerate(_D02_CANDIDATE_DIMENSIONS, start=1):
            for magnitude_ppm in _D02_MAGNITUDES:
                left_case = case_by_key[
                    (
                        int(source_entry["source_ordinal"]),
                        dimension_key,
                        "DECREASE",
                        magnitude_ppm,
                    )
                ]
                right_case = case_by_key[
                    (
                        int(source_entry["source_ordinal"]),
                        dimension_key,
                        "INCREASE",
                        magnitude_ppm,
                    )
                ]

                def pair_side(
                    case_fixture: dict[str, Any],
                    *,
                    side_schema: str,
                    magnitude_ppm: int,
                    source_entry: dict[str, Any],
                ) -> dict[str, Any]:
                    case_entry = case_fixture["entry"]
                    measurement_record = case_fixture["measurement_record"]
                    result_measurement = measurement_record["ordered_result_repeat_measurements"][0]
                    structure_record = case_fixture["structure_record"]
                    manual_record = case_fixture["manual_record"]
                    image_record = image_by_id[case_fixture["result_image_id"]]
                    result_m3_digests = [
                        record["record_digest"] for record in case_fixture["result_m3_records"]
                    ]
                    automated_gate_payload = {
                        "case_id": case_entry["case_id"],
                        "case_specification_digest": case_entry["case_specification_digest"],
                        "result_m3_record_digests": result_m3_digests,
                        "result_m3_repeat_gate_results": [True, True, True],
                        "measurement_gate_record_digest": measurement_record["record_digest"],
                        "measurement_evaluation_state": ("SUPPORTED_EVALUATED"),
                        "measurement_gate_passed": True,
                        "decode_structure_record_digest": structure_record["record_digest"],
                        "structure_gate_passed": True,
                        "automated_gate_passed": True,
                    }
                    return {
                        "schema_version": side_schema,
                        "measurement_evaluation_state": "SUPPORTED_EVALUATED",
                        "case_id": case_entry["case_id"],
                        "case_specification_digest": case_entry["case_specification_digest"],
                        "requested_direction": case_entry["direction"],
                        "requested_magnitude_ppm": magnitude_ppm,
                        "result_output_id": case_fixture["result_output_id"],
                        "result_asset_id": case_fixture["result_asset_id"],
                        "result_asset_sha256": case_fixture["result_sha256"],
                        "result_asset_byte_size": 4096,
                        "result_asset_mime_type": "image/jpeg",
                        "result_asset_width": 64,
                        "result_asset_height": 64,
                        "asset_variant_id": case_fixture["asset_variant_id"],
                        "asset_variant_type": "demo_p3_p7_geometry_v1",
                        "lineage_digest": _digest(
                            "mirror.demo/D02AssetVariantLineage/v1",
                            {
                                "variant_type": "demo_p3_p7_geometry_v1",
                                "source_asset_id": source_entry["source_asset_id"],
                                "source_asset_sha256": source_entry["source_asset_sha256"],
                                "result_asset_id": case_fixture["result_asset_id"],
                                "result_asset_sha256": case_fixture["result_sha256"],
                            },
                        ),
                        "image_record_id": image_record["image_record_id"],
                        "image_record_digest": image_record["image_record_digest"],
                        "result_m3_record_digests": result_m3_digests,
                        "measurement_gate_record_digest": measurement_record["record_digest"],
                        "decode_structure_record_digest": structure_record["record_digest"],
                        "manual_decision_digest": manual_record["manual_decision_digest"],
                        "raw_signed_target_delta_fixed18": result_measurement[
                            "raw_signed_target_delta_fixed18"
                        ],
                        "raw_target_absolute_delta_fixed18": result_measurement[
                            "raw_target_absolute_delta_fixed18"
                        ],
                        "raw_max_control_drift_fixed18": result_measurement[
                            "raw_max_control_drift_fixed18"
                        ],
                        "measured_signed_delta_ppm": result_measurement[
                            "measured_signed_delta_ppm"
                        ],
                        "drift_ppm": result_measurement["drift_ppm"],
                        "automated_gate_digest": _digest(
                            "mirror.demo/D02AutomatedSideGate/v1",
                            automated_gate_payload,
                        ),
                        "automated_gate_passed": True,
                        "manual_gate_passed": True,
                        "side_gate_passed": True,
                        "side_quality_state": "COMPUTED",
                        "side_quality_component_ppm": 1_000_000,
                    }

                left = pair_side(
                    left_case,
                    side_schema="mirror.demo/D02EvaluatedPairSide/v3",
                    magnitude_ppm=magnitude_ppm,
                    source_entry=source_entry,
                )
                right = pair_side(
                    right_case,
                    side_schema="mirror.demo/D02EvaluatedPairSide/v3",
                    magnitude_ppm=magnitude_ppm,
                    source_entry=source_entry,
                )
                pair_id_payload = {
                    "source_authority_key": source_entry["source_authority_key"],
                    "source_admission_event_id": source_entry["source_admission_event_id"],
                    "source_asset_sha256": source_entry["source_asset_sha256"],
                    "dimension_key": dimension_key,
                    "priority_index": priority_index,
                    "magnitude_ppm": magnitude_ppm,
                    "left_case_id": left["case_id"],
                    "right_case_id": right["case_id"],
                    "screening_policy_digest": screening_policy_digest,
                    "lock_policy_digest": lock_policy_digest,
                }
                pair_payload = {
                    "pair_record_id": _d02_derived_id(
                        "mirror.demo/D02PairScreeningRecordId/v1", pair_id_payload
                    ),
                    "source_ordinal": source_entry["source_ordinal"],
                    "source_authority_key": source_entry["source_authority_key"],
                    "source_admission_event_id": source_entry["source_admission_event_id"],
                    "source_asset_id": source_entry["source_asset_id"],
                    "source_asset_sha256": source_entry["source_asset_sha256"],
                    "dimension_key": dimension_key,
                    "priority_index": priority_index,
                    "magnitude_ppm": magnitude_ppm,
                    "screening_policy_digest": screening_policy_digest,
                    "left": left,
                    "right": right,
                    "same_source_gate_passed": True,
                    "opposed_direction_gate_passed": True,
                    "equal_magnitude_gate_passed": True,
                    "pair_side_gates_passed": True,
                    "empty_lock_policy_gate_passed": True,
                    "pair_quality_state": "COMPUTED",
                    "pair_quality_ppm": 1_000_000,
                    "lock_conclusion": ("PASS_FOR_FROZEN_EMPTY_NEUTRAL_POLICY_ONLY"),
                    "lock_policy_digest": lock_policy_digest,
                    "pair_gate_passed": True,
                }
                pair_digest = _digest("mirror.demo/D02PairScreeningRecord/v3", pair_payload)
                wrapper = {
                    "schema_version": "mirror.demo/D02PairScreeningRecord/v3",
                    "pair_screening_record_payload": pair_payload,
                    "pair_screening_record_digest": pair_digest,
                }
                pair_wrappers.append(wrapper)
                pair_fixtures.append(
                    {
                        "wrapper": wrapper,
                        "payload": pair_payload,
                        "left_case": left_case,
                        "right_case": right_case,
                    }
                )

    dimension_records: list[dict[str, Any]] = []
    dimension_by_key: dict[str, dict[str, Any]] = {}
    for priority_index, dimension_key in enumerate(_D02_CANDIDATE_DIMENSIONS, start=1):
        dimension_pairs = [
            fixture
            for fixture in pair_fixtures
            if fixture["payload"]["dimension_key"] == dimension_key
        ]
        side_entries: list[dict[str, Any]] = []
        pair_entries: list[dict[str, Any]] = []
        for pair_fixture in dimension_pairs:
            pair_payload = pair_fixture["payload"]
            for side_name, side_key in (("LEFT", "left"), ("RIGHT", "right")):
                side = pair_payload[side_key]
                side_entries.append(
                    {
                        "schema_version": ("mirror.demo/D02DimensionSideGateEntry/v1"),
                        "source_ordinal": pair_payload["source_ordinal"],
                        "magnitude_ppm": pair_payload["magnitude_ppm"],
                        "side": side_name,
                        "case_id": side["case_id"],
                        "automated_gate_digest": side["automated_gate_digest"],
                        "manual_decision_digest": side["manual_decision_digest"],
                        "automated_gate_passed": side["automated_gate_passed"],
                        "manual_gate_passed": side["manual_gate_passed"],
                        "side_gate_passed": side["side_gate_passed"],
                    }
                )
            pair_entries.append(
                {
                    "schema_version": "mirror.demo/D02DimensionPairGateEntry/v1",
                    "source_ordinal": pair_payload["source_ordinal"],
                    "magnitude_ppm": pair_payload["magnitude_ppm"],
                    "pair_record_id": pair_payload["pair_record_id"],
                    "pair_screening_record_digest": pair_fixture["wrapper"][
                        "pair_screening_record_digest"
                    ],
                    "pair_gate_passed": pair_payload["pair_gate_passed"],
                }
            )
        sixteen_side_gate_digest = _digest(
            "mirror.demo/D02SixteenSideGate/v1",
            {
                "dimension_key": dimension_key,
                "priority_index": priority_index,
                "ordered_side_gate_entries": side_entries,
            },
        )
        eight_pair_gate_digest = _digest(
            "mirror.demo/D02EightPairGate/v1",
            {
                "dimension_key": dimension_key,
                "priority_index": priority_index,
                "ordered_pair_gate_entries": pair_entries,
            },
        )
        dimension_record = _d02_record(
            "mirror.demo/D02DimensionEligibilityRecord/v3",
            {
                "dimension_key": dimension_key,
                "priority_index": priority_index,
                "ordered_pair_screening_record_digests": [
                    fixture["wrapper"]["pair_screening_record_digest"]
                    for fixture in dimension_pairs
                ],
                "ordered_side_automated_gate_digests": [
                    entry["automated_gate_digest"] for entry in side_entries
                ],
                "sixteen_side_gate_digest": sixteen_side_gate_digest,
                "eight_pair_gate_digest": eight_pair_gate_digest,
                "all_sixteen_side_gates_passed": True,
                "all_eight_pair_gates_passed": True,
                "all_manual_gates_passed": True,
                "global_exact_sha_gate_passed": True,
                "empty_lock_policy_gate_passed": True,
                "eligible": True,
                "failure_reasons": [],
            },
        )
        dimension_records.append(dimension_record)
        dimension_by_key[dimension_key] = dimension_record

    selection_trace: list[dict[str, Any]] = []
    for priority_index, dimension_key in enumerate(_D02_CANDIDATE_DIMENSIONS, start=1):
        if priority_index == 1:
            decision, slot, selected = "SELECTED_SLOT_1", 1, True
        elif priority_index == 2:
            decision, slot, selected = "SELECTED_SLOT_2", 2, True
        else:
            decision, slot, selected = (
                "ELIGIBLE_NOT_SELECTED_CAPACITY",
                0,
                False,
            )
        selection_trace.append(
            _d02_record(
                "mirror.demo/D02SelectionTraceRecord/v2",
                {
                    "selection_step": priority_index,
                    "dimension_key": dimension_key,
                    "priority_index": priority_index,
                    "dimension_eligibility_record_digest": dimension_by_key[dimension_key][
                        "record_digest"
                    ],
                    "eligible": True,
                    "eligible_rank": priority_index,
                    "selection_decision": decision,
                    "selection_slot": slot,
                    "selected": selected,
                },
            )
        )

    selected_manifest: list[dict[str, Any]] = []
    selected_pair_fixtures: list[dict[str, Any]] = []
    for selected_dimension_slot, dimension_key in enumerate(_D02_CANDIDATE_DIMENSIONS[:2], start=1):
        for pair_fixture in pair_fixtures:
            pair_payload = pair_fixture["payload"]
            if pair_payload["dimension_key"] != dimension_key:
                continue
            selected_pair_fixtures.append(pair_fixture)
            left = pair_payload["left"]
            right = pair_payload["right"]
            selected_manifest.append(
                _d02_record(
                    "mirror.demo/D02SelectedPairManifestEntry/v2",
                    {
                        "selected_pair_ordinal": len(selected_manifest) + 1,
                        "selected_dimension_slot": selected_dimension_slot,
                        "dimension_key": dimension_key,
                        "priority_index": pair_payload["priority_index"],
                        "source_ordinal": pair_payload["source_ordinal"],
                        "source_authority_key": pair_payload["source_authority_key"],
                        "source_admission_event_id": pair_payload["source_admission_event_id"],
                        "magnitude_ppm": pair_payload["magnitude_ppm"],
                        "pair_record_id": pair_payload["pair_record_id"],
                        "pair_screening_record_digest": pair_fixture["wrapper"][
                            "pair_screening_record_digest"
                        ],
                        "left_case_id": left["case_id"],
                        "left_result_asset_id": left["result_asset_id"],
                        "left_result_asset_sha256": left["result_asset_sha256"],
                        "left_asset_variant_id": left["asset_variant_id"],
                        "right_case_id": right["case_id"],
                        "right_result_asset_id": right["result_asset_id"],
                        "right_result_asset_sha256": right["result_asset_sha256"],
                        "right_asset_variant_id": right["asset_variant_id"],
                    },
                    digest_key="entry_digest",
                )
            )

    selected_pair_manifest_digest = _digest(
        "mirror.demo/D02SelectedPairManifest/v2", selected_manifest
    )
    report_payload = {
        "schema_and_policy": {
            "schema_version": "mirror.demo/D02SchemaAndPolicyBinding/v1",
            **report_digests,
        },
        "ordered_source_manifest": source_entries,
        "ordered_case_manifest": ordered_case_manifest,
        "source_m3_repeat_evidence": source_m3_records,
        "m4_repeat_evidence": m4_records,
        "result_m3_repeat_evidence": result_m3_records,
        "measurement_gate_evidence": measurement_records,
        "decode_structure_immutability_evidence": structure_records,
        "manual_review_evidence": manual_records,
        "exact_duplicate_evidence": {
            "schema_version": "mirror.demo/D02ExactDuplicateEvidence/v2",
            "image_records": image_records,
            "all_record_sha_unique": True,
            "source_sha_unique": True,
            "result_sha_unique": True,
            "source_result_sha_disjoint": True,
            "exact_sha_gate_passed": True,
        },
        "phash_observation_evidence": {
            "schema_version": "mirror.demo/D02PHashObservationEvidence/v2",
            "implementation_digest": report_digests["phash_implementation_digest"],
            "bit_width": 64,
            "threshold_policy": "OBSERVATION_ONLY_NO_THRESHOLD",
            "ordered_record_signatures": signatures,
            "comparisons": comparisons,
        },
        "pair_quality_evidence": pair_wrappers,
        "dimension_eligibility": dimension_records,
        "fixed_priority_selection_trace": selection_trace,
        "selected_pair_manifest": selected_manifest,
        "network_and_runtime_boundary": {
            "schema_version": "mirror.demo/D02NetworkRuntimeBoundary/v2",
            "public_internet_egress": "DENIED",
            "localhost_and_docker_internal_network": True,
            "proxy_environment_present": False,
            "production_provider_calls": 0,
            "runtime_generation_calls": 0,
            "boundary_receipt_digest": evidence_digest("network-boundary"),
        },
    }
    report_schema = "mirror.demo/D02PairScreeningReport/v1"
    report_digest = _digest(report_schema, report_payload)
    report = _build_demo_row(
        DemoPairScreeningReport,
        row_id=_d02_derived_id(
            "mirror.demo/D02PairScreeningReportId/v1",
            {"report_digest": report_digest},
        ),
        authority_schema_version=report_schema,
        source_manifest_digest=source_manifest_digest,
        case_manifest_digest=case_manifest_digest,
        screening_policy_digest=screening_policy_digest,
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
        eligible_dimension_keys=list(_D02_CANDIDATE_DIMENSIONS),
        selected_dimension_keys=list(_D02_CANDIDATE_DIMENSIONS[:2]),
        selected_pair_manifest_digest=selected_pair_manifest_digest,
    )
    session.add(report)
    session.commit()

    algorithm_config_digest = evidence_digest("questionnaire-algorithm-config")
    dimension_manifest = {
        "schema_version": "mirror.demo/D02QuestionBankDimensionManifest/v1",
        "screening_report_id": report.id,
        "screening_report_digest": report.report_digest,
        "source_manifest_digest": report.source_manifest_digest,
        "source_p2_candidate_manifest_content_digest": _D02_SOURCE_MANIFEST_DIGEST,
        "dimension_authority_manifest_content_digest": (_D02_DIMENSION_MANIFEST_DIGEST),
        "selected_pair_manifest_digest": selected_pair_manifest_digest,
        "selected_dimensions": [
            {
                "dimension_key": dimension_key,
                "priority_index": dimension_by_key[dimension_key]["priority_index"],
                "sixteen_side_gate_digest": dimension_by_key[dimension_key][
                    "sixteen_side_gate_digest"
                ],
                "eight_pair_gate_digest": dimension_by_key[dimension_key]["eight_pair_gate_digest"],
            }
            for dimension_key in _D02_CANDIDATE_DIMENSIONS[:2]
        ],
    }
    bank_id = _d02_derived_id(
        "mirror.demo/D02QuestionBankId/v1",
        {
            "screening_report_id": report.id,
            "screening_report_digest": report.report_digest,
            "selected_pair_manifest_digest": selected_pair_manifest_digest,
            "algorithm_config_digest": algorithm_config_digest,
        },
    )
    bank = _build_demo_row(
        DemoQuestionBank,
        row_id=bank_id,
        authority_schema_version="mirror.demo/DemoQuestionBank/v2",
        version=f"fixture-bank-r9-{marker}",
        algorithm_config_digest=algorithm_config_digest,
        routing_version="demo-bayesian-pairwise-logistic-v1",
        stopping_version="demo-p4-stopping-v1",
        neighborhood_version="demo-morphology-neighborhood-v1",
        pair_manifest_digest=selected_pair_manifest_digest,
        dimension_manifest=dimension_manifest,
        screening_report_id=report.id,
        screening_report_digest=report.report_digest,
    )

    result_assets: list[Asset] = []
    result_variants: list[AssetVariant] = []
    pairs: list[DemoQuestionPair] = []
    for pair_fixture in selected_pair_fixtures:
        pair_payload = pair_fixture["payload"]
        source_fixture = source_fixtures[int(pair_payload["source_ordinal"]) - 1]
        source_asset = source_fixture["asset"]
        for side_name in ("left", "right"):
            side = pair_payload[side_name]
            result_assets.append(
                Asset(
                    id=side["result_asset_id"],
                    owner_user_id=None,
                    asset_role="synthetic",
                    internal_purpose="synthetic_dataset",
                    storage_key=(f"demo-d02-selected-r9/{marker}/{side['result_asset_id']}"),
                    mime_type=side["result_asset_mime_type"],
                    byte_size=side["result_asset_byte_size"],
                    width=side["result_asset_width"],
                    height=side["result_asset_height"],
                    sha256=side["result_asset_sha256"],
                    synthetic=True,
                    is_ai_generated=False,
                    is_ai_modified=True,
                )
            )
            result_variants.append(
                AssetVariant(
                    id=side["asset_variant_id"],
                    source_asset_id=source_asset.id,
                    result_asset_id=side["result_asset_id"],
                    variant_type="demo_p3_p7_geometry_v1",
                )
            )
        qa_payload = {
            "schema_version": "mirror.demo/D02QuestionPairQAPayload/v2",
            "screening_report_id": report.id,
            "screening_report_digest": report.report_digest,
            "pair_screening_record_schema_version": ("mirror.demo/D02PairScreeningRecord/v3"),
            "pair_screening_record_digest": pair_fixture["wrapper"]["pair_screening_record_digest"],
            "pair_screening_record_payload": pair_payload,
        }
        pair_id = _d02_derived_id(
            "mirror.demo/D02QuestionPairId/v1",
            {
                "question_bank_id": bank.id,
                "pair_screening_record_digest": qa_payload["pair_screening_record_digest"],
                "source_admission_event_id": pair_payload["source_admission_event_id"],
                "dimension_key": pair_payload["dimension_key"],
                "magnitude_ppm": pair_payload["magnitude_ppm"],
            },
        )
        pairs.append(
            _build_demo_row(
                DemoQuestionPair,
                row_id=pair_id,
                authority_schema_version="mirror.demo/DemoQuestionPair/v2",
                question_bank_id=bank.id,
                demo_synthetic_identity_id=pair_payload["source_admission_event_id"],
                source_asset_id=pair_payload["source_asset_id"],
                source_asset_sha256=pair_payload["source_asset_sha256"],
                left_asset_id=pair_payload["left"]["result_asset_id"],
                left_asset_sha256=pair_payload["left"]["result_asset_sha256"],
                right_asset_id=pair_payload["right"]["result_asset_id"],
                right_asset_sha256=pair_payload["right"]["result_asset_sha256"],
                left_asset_variant_id=pair_payload["left"]["asset_variant_id"],
                right_asset_variant_id=pair_payload["right"]["asset_variant_id"],
                dimension_key=pair_payload["dimension_key"],
                magnitude_ppm=pair_payload["magnitude_ppm"],
                left_delta_ppm=pair_payload["left"]["measured_signed_delta_ppm"],
                right_delta_ppm=pair_payload["right"]["measured_signed_delta_ppm"],
                pair_quality_ppm=pair_payload["pair_quality_ppm"],
                qa_payload=qa_payload,
                screening_report_id=report.id,
                screening_report_digest=report.report_digest,
            )
        )
    session.add_all(result_assets)
    session.flush()
    session.add_all(result_variants)
    session.flush()
    session.add(bank)
    session.add_all(pairs)
    session.commit()
    return bank, pairs[0]


def _insert_d02_question_bank(
    session: Session,
    primary_source: Asset,
    primary_admission: DemoSyntheticIdentity,
    *,
    report_mutator: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[DemoQuestionBank, DemoQuestionPair]:
    """Persist the accepted v10 Report v2 graph and its selected 16-pair bank."""

    _ = primary_source, primary_admission
    report_authority, source_packets, variant_bindings = _complete_report_fixture(passing=True)
    if report_mutator is not None:
        report_authority = deepcopy(report_authority)
        report_mutator(report_authority)
        _resign_report_row(report_authority)

    def ensure_asset(**fields: Any) -> Asset:
        asset_id = cast(str, fields["id"])
        existing = session.get(Asset, asset_id)
        if existing is not None:
            for key in (
                "owner_user_id",
                "asset_role",
                "internal_purpose",
                "mime_type",
                "byte_size",
                "width",
                "height",
                "sha256",
                "synthetic",
                "is_ai_generated",
                "is_ai_modified",
            ):
                assert getattr(existing, key) == fields[key]
            assert existing.deleted_at is None
            return existing
        asset = Asset(**fields)
        session.add(asset)
        session.commit()
        return asset

    identity_by_id: dict[str, DemoSyntheticIdentity] = {}
    for packet in source_packets:
        facts = cast(dict[str, Any], packet["facts"])
        identity_authority = cast(dict[str, Any], packet["identity_row"])
        assert identity_authority["import_config_digest"] == IMPORT_CONFIG_DIGEST
        ensure_asset(
            id=identity_authority["formal_canonical_asset_id"],
            owner_user_id=None,
            asset_role="synthetic",
            internal_purpose="synthetic_dataset",
            storage_key=(f"demo-d02-v10/source/{identity_authority['formal_canonical_asset_id']}"),
            mime_type=facts["source_asset_mime_type"],
            byte_size=facts["source_asset_byte_size"],
            width=facts["source_asset_width"],
            height=facts["source_asset_height"],
            sha256=facts["source_asset_sha256"],
            synthetic=True,
            is_ai_generated=True,
            is_ai_modified=False,
        )
        identity_fields = {
            column.name: identity_authority[column.name]
            for column in DemoSyntheticIdentity.__table__.columns
            if column.name in identity_authority and column.computed is None
        }
        identity_fields["created_at"] = datetime.fromisoformat(
            cast(str, identity_authority["created_at"]).replace("Z", "+00:00")
        )
        identity_row = DemoSyntheticIdentity(**identity_fields)
        session.add(identity_row)
        session.commit()
        identity_by_id[identity_row.id] = identity_row

    image_by_case = {
        cast(str, image["case_id"]): cast(dict[str, Any], image)
        for image in cast(
            list[dict[str, Any]],
            report_authority["report_payload"]["exact_duplicate_evidence"]["image_records"],
        )
        if image["authority_role"] == "RESULT"
    }
    variants: list[AssetVariant] = []
    for case_id, raw_binding in cast(dict[str, Any], variant_bindings).items():
        binding = cast(dict[str, Any], raw_binding)
        image = image_by_case[case_id]
        assert image["deterministic_result_asset_id"] == binding["result_asset_id"]
        assert image["sha256"] == binding["result_asset_sha256"]
        expected_variant_id = derive_asset_variant_id(
            variant_type=binding["asset_variant_type"],
            source_asset_id=binding["source_asset_id"],
            source_asset_sha256=binding["source_asset_sha256"],
            result_asset_id=binding["result_asset_id"],
            result_asset_sha256=binding["result_asset_sha256"],
            case_specification_digest=binding["case_specification_digest"],
        )
        assert expected_variant_id == binding["asset_variant_id"]
        ensure_asset(
            id=binding["result_asset_id"],
            owner_user_id=None,
            asset_role="synthetic",
            internal_purpose="synthetic_dataset",
            storage_key=f"demo-d02-v10/result/{binding['result_asset_id']}",
            mime_type=image["mime_type"],
            byte_size=image["byte_size"],
            width=image["width"],
            height=image["height"],
            sha256=binding["result_asset_sha256"],
            synthetic=True,
            is_ai_generated=False,
            is_ai_modified=True,
        )
        variants.append(
            AssetVariant(
                id=binding["asset_variant_id"],
                source_asset_id=binding["source_asset_id"],
                result_asset_id=binding["result_asset_id"],
                variant_type=binding["asset_variant_type"],
            )
        )
    session.add_all(variants)
    session.commit()

    report_fields = {
        column.name: report_authority[column.name]
        for column in DemoPairScreeningReport.__table__.columns
        if column.name in report_authority and column.computed is None
    }
    report_fields["created_at"] = datetime.fromisoformat(
        cast(str, report_authority["created_at"]).replace("Z", "+00:00")
    )
    report = DemoPairScreeningReport(**report_fields)
    session.add(report)
    session.commit()

    report_payload = cast(dict[str, Any], report.report_payload)
    execution_config = cast(
        dict[str, Any],
        report_payload["schema_and_policy"]["measurement_execution_config"],
    )
    eligibility_by_key = {
        cast(str, entry["dimension_key"]): cast(dict[str, Any], entry)
        for entry in cast(list[dict[str, Any]], report_payload["dimension_eligibility"])
    }
    selected_dimensions = cast(list[str], report.selected_dimension_keys)
    algorithm_config_digest = _digest(
        "mirror.demo/D02QuestionnaireAlgorithmConfig/v1",
        {
            "routing_version": "demo-bayesian-pairwise-logistic-v1",
            "stopping_version": "demo-p4-stopping-v1",
            "neighborhood_version": "demo-morphology-neighborhood-v1",
            "screening_report_digest": report.report_digest,
        },
    )
    dimension_manifest = {
        "schema_version": "mirror.demo/D02QuestionBankDimensionManifest/v1",
        "screening_report_id": report.id,
        "screening_report_digest": report.report_digest,
        "source_manifest_digest": report.source_manifest_digest,
        "source_p2_candidate_manifest_content_digest": execution_config[
            "source_p2_candidate_manifest_content_digest"
        ],
        "dimension_authority_manifest_content_digest": execution_config[
            "dimension_authority_manifest_content_digest"
        ],
        "selected_pair_manifest_digest": report.selected_pair_manifest_digest,
        "selected_dimensions": [
            {
                "dimension_key": dimension_key,
                "priority_index": eligibility_by_key[dimension_key]["priority_index"],
                "sixteen_side_gate_digest": eligibility_by_key[dimension_key][
                    "sixteen_side_gate_digest"
                ],
                "eight_pair_gate_digest": eligibility_by_key[dimension_key][
                    "eight_pair_gate_digest"
                ],
            }
            for dimension_key in selected_dimensions
        ],
    }
    assert report.selected_pair_manifest_digest is not None
    bank_id = _d02_derived_id(
        "mirror.demo/D02QuestionBankId/v1",
        {
            "screening_report_id": report.id,
            "screening_report_digest": report.report_digest,
            "selected_pair_manifest_digest": report.selected_pair_manifest_digest,
            "algorithm_config_digest": algorithm_config_digest,
        },
    )
    bank = _build_demo_row(
        DemoQuestionBank,
        row_id=bank_id,
        authority_schema_version="mirror.demo/DemoQuestionBank/v2",
        version=f"d02-v10-{report.id}",
        algorithm_config_digest=algorithm_config_digest,
        routing_version="demo-bayesian-pairwise-logistic-v1",
        stopping_version="demo-p4-stopping-v1",
        neighborhood_version="demo-morphology-neighborhood-v1",
        pair_manifest_digest=report.selected_pair_manifest_digest,
        dimension_manifest=dimension_manifest,
        screening_report_id=report.id,
        screening_report_digest=report.report_digest,
    )

    wrappers_by_digest = {
        cast(str, wrapper["pair_screening_record_digest"]): cast(dict[str, Any], wrapper)
        for wrapper in cast(list[dict[str, Any]], report_payload["pair_quality_evidence"])
    }
    pairs: list[DemoQuestionPair] = []
    for selected_entry in cast(list[dict[str, Any]], report_payload["selected_pair_manifest"]):
        pair_digest = cast(str, selected_entry["pair_screening_record_digest"])
        wrapper = wrappers_by_digest[pair_digest]
        pair_payload = cast(dict[str, Any], wrapper["pair_screening_record_payload"])
        source_identity_id = cast(str, pair_payload["source_admission_event_id"])
        assert source_identity_id in identity_by_id
        left = cast(dict[str, Any], pair_payload["left"])
        right = cast(dict[str, Any], pair_payload["right"])
        qa_payload = {
            "schema_version": "mirror.demo/D02QuestionPairQAPayload/v2",
            "screening_report_id": report.id,
            "screening_report_digest": report.report_digest,
            "pair_screening_record_schema_version": wrapper["schema_version"],
            "pair_screening_record_digest": pair_digest,
            "pair_screening_record_payload": pair_payload,
        }
        pair_id = _d02_derived_id(
            "mirror.demo/D02QuestionPairId/v1",
            {
                "question_bank_id": bank.id,
                "pair_screening_record_digest": pair_digest,
                "source_admission_event_id": source_identity_id,
                "dimension_key": pair_payload["dimension_key"],
                "magnitude_ppm": pair_payload["magnitude_ppm"],
            },
        )
        pairs.append(
            _build_demo_row(
                DemoQuestionPair,
                row_id=pair_id,
                authority_schema_version="mirror.demo/DemoQuestionPair/v2",
                question_bank_id=bank.id,
                demo_synthetic_identity_id=source_identity_id,
                source_asset_id=pair_payload["source_asset_id"],
                source_asset_sha256=pair_payload["source_asset_sha256"],
                left_asset_id=left["result_asset_id"],
                left_asset_sha256=left["result_asset_sha256"],
                right_asset_id=right["result_asset_id"],
                right_asset_sha256=right["result_asset_sha256"],
                left_asset_variant_id=left["asset_variant_id"],
                right_asset_variant_id=right["asset_variant_id"],
                dimension_key=pair_payload["dimension_key"],
                magnitude_ppm=pair_payload["magnitude_ppm"],
                left_delta_ppm=left["measured_signed_delta_ppm"],
                right_delta_ppm=right["measured_signed_delta_ppm"],
                pair_quality_ppm=pair_payload["pair_quality_ppm"],
                qa_payload=qa_payload,
                screening_report_id=report.id,
                screening_report_digest=report.report_digest,
            )
        )
    session.add(bank)
    session.add_all(pairs)
    session.commit()
    return bank, pairs[0]


def _insert_mutated_d02_report_graph(
    session: Session,
    report_mutator: Callable[[dict[str, Any]], None],
) -> None:
    source_asset, formal_identity = _accepted_synthetic_source(session)
    primary_admission = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=1,
            action="ADMIT",
            supersedes_id=None,
            config_marker=f"d02-v10-report-attack-{new_id()}",
        ),
    )
    _insert_d02_question_bank(
        session,
        source_asset,
        primary_admission,
        report_mutator=report_mutator,
    )


def _resign_d02_record(record: dict[str, Any]) -> None:
    schema_version = cast(str, record["schema_version"])
    payload = {
        key: value
        for key, value in record.items()
        if key not in {"schema_version", "record_digest"}
    }
    record["record_digest"] = _digest(schema_version, payload)


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


def _episode_insert_values(
    graph: dict[str, Any],
    *,
    profile_digest: str | None = None,
    context_digest: str | None = None,
    instruction_digest: str | None = None,
) -> dict[str, Any]:
    episode = _build_demo_row(
        DemoAcceptedVisualEpisode,
        demo_actor_id=graph["actor"].id,
        demo_session_id=graph["session"].id,
        editing_session_id=graph["editing_session"].id,
        accepted_image_version_id=graph["image1"].id,
        verification_result_id=graph["verification"].id,
        acceptance_event_id=graph["accepted_event"].id,
        source_asset_id=graph["image0"].source_asset_id,
        source_asset_sha256=graph["source_asset"].sha256,
        final_asset_id=graph["image1"].result_asset_id,
        final_asset_sha256=graph["image1_asset"].sha256,
        trajectory_digests=[
            graph["image0"].content_digest,
            graph["image1"].content_digest,
        ],
        profile_digest=profile_digest or graph["desired_delta"].content_digest,
        context_digest=context_digest or graph["editing_session"].context_digest,
        instruction_digest=(instruction_digest or graph["editing_session"].instruction_digest),
    )
    return {
        column.name: getattr(episode, column.name)
        for column in DemoAcceptedVisualEpisode.__table__.columns
    }


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


def _insert_full_demo_graph(
    session: Session,
    *,
    include_episode: bool = True,
    plan_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    v10_report_validator_present = bool(
        session.scalar(
            text(
                "SELECT to_regprocedure("
                "'mirror_demo_validate_d02_screening_report_v10()'"
                ") IS NOT NULL"
            )
        )
    )
    insert_question_bank = (
        _insert_d02_question_bank
        if v10_report_validator_present
        else _insert_legacy_d02_question_bank_fixture
    )
    bank, question_pair = insert_question_bank(session, source_asset, synthetic_identity)
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
        **(plan_overrides or {}),
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

    pair = session.scalar(select(DemoQuestionPair).order_by(DemoQuestionPair.id))
    assert pair is not None
    pair_admit = session.get(DemoSyntheticIdentity, pair.demo_synthetic_identity_id)
    assert pair_admit is not None
    pair_admit_fields = {
        column.name: getattr(pair_admit, column.name)
        for column in pair_admit.__table__.columns
        if column.name
        not in _NON_AUTHORITY_COLUMNS | {"source_authority_kind", "source_authority_key"}
    }
    pair_admit_fields.update(
        admission_sequence=2,
        admission_action="REVOKE",
        admission_config_digest=hashlib.sha256(b"stale-pair-revoke").hexdigest(),
        supersedes_id=pair_admit.id,
    )
    pair_revoke = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **pair_admit_fields,
    )
    assert pair_revoke.admission_action == "REVOKE"

    with pytest.raises(
        DBAPIError,
        match="Demo synthetic admission is not the current eligible row",
    ):
        _insert_demo_row(
            session,
            DemoQuestionPair,
            authority_schema_version=pair.schema_version,
            question_bank_id=pair.question_bank_id,
            demo_synthetic_identity_id=pair_admit.id,
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


def test_local_synthetic_revocation_copies_import_config_authority(
    session: Session,
) -> None:
    _, first_admit = _insert_local_d02_identity(
        session, marker=f"local-revoke-import-config-{new_id()}"
    )
    base_fields = {
        column.name: getattr(first_admit, column.name)
        for column in first_admit.__table__.columns
        if column.name
        not in _NON_AUTHORITY_COLUMNS | {"source_authority_kind", "source_authority_key"}
    }
    base_fields.update(
        admission_sequence=2,
        admission_action="REVOKE",
        admission_config_digest=hashlib.sha256(b"local-revoke-import-config").hexdigest(),
        supersedes_id=first_admit.id,
    )

    with pytest.raises(
        DBAPIError,
        match="D02 v10 identity/facts canonical equality is invalid",
    ):
        _insert_demo_row(
            session,
            DemoSyntheticIdentity,
            **{
                **base_fields,
                "import_config_digest": hashlib.sha256(b"tampered-local-import-config").hexdigest(),
            },
        )
    session.rollback()

    revoke = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **base_fields,
    )
    assert revoke.admission_action == "REVOKE"
    assert revoke.import_config_digest == first_admit.import_config_digest


@pytest.mark.parametrize(
    ("attack", "expected_error"),
    (
        (
            "observation_payload_digest_split",
            "D02 v10 observation envelope or digest is invalid",
        ),
        ("certificate_gate_mismatch", "D02 v10 Gate graph binding is invalid"),
        (
            "mixed_source_m3_version",
            "D02 record shape or digest mismatch: mirror.demo/D02SourceM3RepeatRecord/v2",
        ),
    ),
)
def test_d02_v10_postgresql_rejects_resigned_graph_attacks(
    session: Session,
    attack: str,
    expected_error: str,
) -> None:
    def mutate(report: dict[str, Any]) -> None:
        payload = cast(dict[str, Any], report["report_payload"])
        if attack == "observation_payload_digest_split":
            record = cast(dict[str, Any], payload["result_m3_repeat_evidence"][0])
            observation = cast(dict[str, Any], record["measurement_observation"])
            measurement = cast(dict[str, Any], observation["ordered_measurements"][0])
            measurement["raw_value_fixed18"] = "0.424242424242424242"
            _resign_d02_record(record)
            return
        if attack == "certificate_gate_mismatch":
            gate = cast(dict[str, Any], payload["measurement_gate_evidence"][0])
            gate["result_repeat_certification_digest"] = "e" * 64
            _resign_d02_record(gate)
            return
        if attack == "mixed_source_m3_version":
            record = cast(dict[str, Any], payload["source_m3_repeat_evidence"][0])
            record["schema_version"] = "mirror.demo/D02SourceM3RepeatRecord/v1"
            _resign_d02_record(record)
            return
        raise AssertionError(f"unknown D02 attack: {attack}")

    with pytest.raises(DBAPIError, match=expected_error):
        _insert_mutated_d02_report_graph(session, mutate)
    session.rollback()


@pytest.mark.parametrize(
    "authority_key",
    (
        "measurement_config_digest",
        "measurement_quality_config_digest",
        "runtime_manifest_digest",
        "vision_model_manifest_digest",
        "topology_digest",
    ),
)
def test_d02_v10_postgresql_rejects_stale_schema_policy_authority(
    session: Session,
    authority_key: str,
) -> None:
    def mutate(report: dict[str, Any]) -> None:
        payload = cast(dict[str, Any], report["report_payload"])
        binding = cast(dict[str, Any], payload["schema_and_policy"])
        binding[authority_key] = "0" * 64

    with pytest.raises(DBAPIError, match="D02 v10 schema/policy authority is invalid"):
        _insert_mutated_d02_report_graph(session, mutate)
    session.rollback()


def test_d02_v10_rejects_new_legacy_local_identity_write(session: Session) -> None:
    with pytest.raises(
        DBAPIError,
        match="New Demo local synthetic identity events must use v3 authority",
    ):
        _insert_legacy_local_d02_identity(
            session,
            marker=f"legacy-write-rejected-{new_id()}",
        )
    session.rollback()


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


@pytest.mark.parametrize(
    "forged_fields",
    (
        ("profile_digest",),
        ("context_digest",),
        ("instruction_digest",),
        ("profile_digest", "context_digest", "instruction_digest"),
    ),
    ids=("profile-only", "context-only", "instruction-only", "combined"),
)
def test_accepted_episode_rejects_resigned_direct_sql_provenance_forgery(
    session: Session,
    forged_fields: tuple[str, ...],
) -> None:
    graph = _insert_full_demo_graph(session, include_episode=False)
    overrides = {
        field_name: hashlib.sha256(f"forged-{field_name}".encode()).hexdigest()
        for field_name in forged_fields
    }
    forged_values = _episode_insert_values(graph, **overrides)

    with pytest.raises(
        DBAPIError,
        match="Only verified user-accepted Demo image versions may become episodes",
    ):
        session.execute(DemoAcceptedVisualEpisode.__table__.insert().values(**forged_values))
        session.commit()
    session.rollback()

    assert session.scalar(text("SELECT count(*) FROM demo_accepted_visual_episodes")) == 0


@pytest.mark.parametrize(
    "plan_overrides",
    (
        {
            "desired_delta_profile_digest": hashlib.sha256(
                b"terminal-plan-profile-drift"
            ).hexdigest()
        },
        {"instruction_digest": hashlib.sha256(b"terminal-plan-instruction-drift").hexdigest()},
    ),
    ids=("terminal-plan-profile", "terminal-plan-instruction"),
)
def test_accepted_episode_rejects_isolated_terminal_plan_provenance_drift(
    session: Session,
    plan_overrides: dict[str, Any],
) -> None:
    graph = _insert_full_demo_graph(
        session,
        include_episode=False,
        plan_overrides=plan_overrides,
    )
    episode_values = _episode_insert_values(graph)

    assert episode_values["profile_digest"] == graph["editing_session"].desired_delta_profile_digest
    assert episode_values["instruction_digest"] == graph["editing_session"].instruction_digest
    assert (
        episode_values["profile_digest"] != graph["result_plan"].desired_delta_profile_digest
        or episode_values["instruction_digest"] != graph["result_plan"].instruction_digest
    )

    with pytest.raises(
        DBAPIError,
        match="Only verified user-accepted Demo image versions may become episodes",
    ):
        session.execute(DemoAcceptedVisualEpisode.__table__.insert().values(**episode_values))
        session.commit()
    session.rollback()

    assert session.scalar(text("SELECT count(*) FROM demo_accepted_visual_episodes")) == 0


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


def _demo_alembic_config(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _accepted_episode_function_definition(session: Session) -> str:
    return _postgres_function_definition(
        session,
        "mirror_demo_validate_accepted_episode()",
    )


def _postgres_function_definition(session: Session, signature: str) -> str:
    definition = session.scalar(
        text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
        {"signature": signature},
    )
    assert isinstance(definition, str)
    return definition


def _d02_authority_snapshot(session: Session) -> dict[str, Any]:
    queries = {
        "identities": (
            "SELECT COALESCE(jsonb_agg(to_jsonb(row_value) ORDER BY row_value.id), "
            "'[]'::jsonb) FROM demo_synthetic_identities AS row_value"
        ),
        "reports": (
            "SELECT COALESCE(jsonb_agg(to_jsonb(row_value) ORDER BY row_value.id), "
            "'[]'::jsonb) FROM demo_pair_screening_reports AS row_value"
        ),
        "banks": (
            "SELECT COALESCE(jsonb_agg(to_jsonb(row_value) ORDER BY row_value.id), "
            "'[]'::jsonb) FROM demo_question_banks AS row_value"
        ),
        "pairs": (
            "SELECT COALESCE(jsonb_agg(to_jsonb(row_value) ORDER BY row_value.id), "
            "'[]'::jsonb) FROM demo_question_pairs AS row_value"
        ),
    }
    return {name: session.scalar(text(query)) for name, query in queries.items()}


def _d02_trigger_definitions(session: Session) -> list[tuple[str, str, str]]:
    rows = session.execute(
        text(
            "SELECT trigger_row.tgrelid::regclass::text, trigger_row.tgname, "
            "pg_get_triggerdef(trigger_row.oid) "
            "FROM pg_trigger AS trigger_row "
            "WHERE NOT trigger_row.tgisinternal "
            "AND trigger_row.tgrelid IN ("
            "'demo_synthetic_identities'::regclass, "
            "'demo_pair_screening_reports'::regclass, "
            "'demo_question_banks'::regclass, "
            "'demo_question_pairs'::regclass) "
            "ORDER BY trigger_row.tgrelid::regclass::text, trigger_row.tgname"
        )
    ).all()
    return [
        (cast(str, table), cast(str, name), cast(str, definition))
        for table, name, definition in rows
    ]


def _wait_for_episode_access_exclusive_lock(
    session: Session,
    *,
    timeout_seconds: float = 10.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        granted_count = session.scalar(
            text(
                "SELECT count(*) FROM pg_locks lock_row "
                "WHERE lock_row.relation = "
                "'demo_accepted_visual_episodes'::regclass "
                "AND lock_row.mode = 'AccessExclusiveLock' "
                "AND lock_row.granted "
                "AND lock_row.pid <> pg_backend_pid()"
            )
        )
        if granted_count:
            session.commit()
            return
        session.commit()
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for D09 episode-table migration lock")


def _insert_episode_values_in_new_connection(
    database_url: str,
    values: dict[str, Any],
    started: Event,
) -> str:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            started.set()
            connection.execute(DemoAcceptedVisualEpisode.__table__.insert().values(**values))
    except DBAPIError:
        return "rejected"
    finally:
        engine.dispose()
    return "inserted"


def test_d02_quality_round_trip_preserves_legacy_rows_and_rejects_new_v1_report(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _truncate_demo_authority(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _demo_alembic_config(database_url)
    command.downgrade(config, D02_QUALITY_DOWN_REVISION)

    source_asset, formal_identity = _accepted_synthetic_source(session)
    primary_admission = _insert_demo_row(
        session,
        DemoSyntheticIdentity,
        **_synthetic_admission_fields(
            session,
            source_asset,
            formal_identity,
            sequence=1,
            action="ADMIT",
            supersedes_id=None,
            config_marker=f"d02-legacy-round-trip-{new_id()}",
        ),
    )
    bank, _ = _insert_legacy_d02_question_bank_fixture(
        session,
        source_asset,
        primary_admission,
    )
    report = session.get(DemoPairScreeningReport, bank.screening_report_id)
    assert report is not None
    report_values = {
        column.name: getattr(report, column.name)
        for column in DemoPairScreeningReport.__table__.columns
        if column.computed is None
    }
    legacy_snapshot = _d02_authority_snapshot(session)
    d09_definition = _accepted_episode_function_definition(session)
    legacy_guard_definition = _postgres_function_definition(
        session,
        "mirror_demo_guard_authority()",
    )
    session.commit()

    try:
        command.upgrade(config, DEMO_REVISION)
        assert _d02_authority_snapshot(session) == legacy_snapshot
        assert _accepted_episode_function_definition(session) == d09_definition
        session.commit()

        with pytest.raises(
            DBAPIError,
            match="New D02 screening reports must use v2 authority",
        ):
            session.execute(DemoPairScreeningReport.__table__.insert().values(**report_values))
            session.commit()
        session.rollback()

        command.downgrade(config, D02_QUALITY_DOWN_REVISION)
        assert _d02_authority_snapshot(session) == legacy_snapshot
        assert _accepted_episode_function_definition(session) == d09_definition
        assert (
            _postgres_function_definition(session, "mirror_demo_guard_authority()")
            == legacy_guard_definition
        )
        assert session.scalar(
            text(
                "SELECT to_regprocedure('mirror_demo_validate_d02_screening_report_v10()') IS NULL"
            )
        )
        session.commit()
    finally:
        session.rollback()
        current_revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        session.commit()
        if current_revision != DEMO_REVISION:
            command.upgrade(config, DEMO_REVISION)


def test_d02_quality_populated_downgrade_fails_closed_without_side_effects(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_full_demo_graph(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _demo_alembic_config(database_url)
    authority_snapshot = _d02_authority_snapshot(session)
    d09_definition = _accepted_episode_function_definition(session)
    v10_definition = _postgres_function_definition(
        session,
        "mirror_demo_validate_d02_screening_report_v10()",
    )
    trigger_definitions = _d02_trigger_definitions(session)
    session.commit()

    try:
        with pytest.raises(
            DBAPIError,
            match="Cannot downgrade populated D02 v3 identity authority",
        ):
            command.downgrade(config, D02_QUALITY_DOWN_REVISION)

        assert session.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION
        assert _d02_authority_snapshot(session) == authority_snapshot
        assert _accepted_episode_function_definition(session) == d09_definition
        assert (
            _postgres_function_definition(
                session,
                "mirror_demo_validate_d02_screening_report_v10()",
            )
            == v10_definition
        )
        assert _d02_trigger_definitions(session) == trigger_definitions
    finally:
        session.rollback()
        current_revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        session.commit()
        if current_revision != DEMO_REVISION:
            _truncate_demo_authority(session)
            command.upgrade(config, DEMO_REVISION)


def test_d09_empty_function_round_trip_restores_frozen_definitions(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _truncate_demo_authority(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _demo_alembic_config(database_url)
    hardened_definition = _accepted_episode_function_definition(session)
    session.commit()

    try:
        command.downgrade(config, FORMAL_DOWN_REVISION)
        command.upgrade(config, D09_DOWN_REVISION)
        demo_0003_baseline = _accepted_episode_function_definition(session)
        session.commit()
        assert demo_0003_baseline != hardened_definition

        command.upgrade(config, DEMO_REVISION)
        assert _accepted_episode_function_definition(session) == hardened_definition
        session.commit()

        command.downgrade(config, D09_DOWN_REVISION)
        assert _accepted_episode_function_definition(session) == demo_0003_baseline
        session.commit()
    finally:
        command.upgrade(config, DEMO_REVISION)
    assert _accepted_episode_function_definition(session) == hardened_definition


def test_d09_upgrade_preserves_legal_episode_bytes(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _truncate_demo_authority(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _demo_alembic_config(database_url)
    command.downgrade(config, D09_DOWN_REVISION)
    graph = _insert_full_demo_graph(session)
    episode_id = graph["episode"].id
    before = session.scalar(
        text("SELECT to_jsonb(episode_row) FROM demo_accepted_visual_episodes episode_row")
    )
    session.commit()

    try:
        command.upgrade(config, DEMO_REVISION)
        after = session.scalar(
            text(
                "SELECT to_jsonb(episode_row) FROM demo_accepted_visual_episodes "
                "episode_row WHERE id=:episode_id"
            ),
            {"episode_id": episode_id},
        )
        assert after == before
    finally:
        if session.scalar(text("SELECT version_num FROM alembic_version")) != DEMO_REVISION:
            _truncate_demo_authority(session)
            command.upgrade(config, DEMO_REVISION)


def test_d09_upgrade_rejects_resigned_legacy_forgery_without_rewriting(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _truncate_demo_authority(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _demo_alembic_config(database_url)
    command.downgrade(config, D09_DOWN_REVISION)
    graph = _insert_full_demo_graph(session, include_episode=False)
    forged_values = _episode_insert_values(
        graph,
        profile_digest=hashlib.sha256(b"legacy-forged-profile").hexdigest(),
        context_digest=hashlib.sha256(b"legacy-forged-context").hexdigest(),
        instruction_digest=hashlib.sha256(b"legacy-forged-instruction").hexdigest(),
    )
    session.execute(DemoAcceptedVisualEpisode.__table__.insert().values(**forged_values))
    session.commit()
    before = session.scalar(
        text(
            "SELECT to_jsonb(episode_row) FROM demo_accepted_visual_episodes episode_row "
            "WHERE id=:episode_id"
        ),
        {"episode_id": forged_values["id"]},
    )
    session.commit()

    try:
        with pytest.raises(DBAPIError, match="provenance audit failed"):
            command.upgrade(config, DEMO_REVISION)
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
            D09_DOWN_REVISION
        )
        after = session.scalar(
            text(
                "SELECT to_jsonb(episode_row) FROM demo_accepted_visual_episodes "
                "episode_row WHERE id=:episode_id"
            ),
            {"episode_id": forged_values["id"]},
        )
        assert after == before
    finally:
        session.rollback()
        _truncate_demo_authority(session)
        command.upgrade(config, DEMO_REVISION)


def test_d09_populated_downgrade_fails_closed_with_function_unchanged(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _truncate_demo_authority(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _demo_alembic_config(database_url)
    command.downgrade(config, D02_QUALITY_DOWN_REVISION)
    graph = _insert_full_demo_graph(session)
    episode_id = graph["episode"].id
    hardened_definition = _accepted_episode_function_definition(session)
    session.commit()

    try:
        with pytest.raises(DBAPIError, match="downgrade blocked by existing evidence"):
            command.downgrade(config, D09_DOWN_REVISION)

        assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
            D02_QUALITY_DOWN_REVISION
        )
        assert _accepted_episode_function_definition(session) == hardened_definition
        assert (
            session.scalar(
                text("SELECT count(*) FROM demo_accepted_visual_episodes WHERE id=:episode_id"),
                {"episode_id": episode_id},
            )
            == 1
        )
    finally:
        session.rollback()
        command.upgrade(config, DEMO_REVISION)


def test_d09_upgrade_serializes_concurrent_forged_insert_until_hardened_commit(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _truncate_demo_authority(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _demo_alembic_config(database_url)
    command.downgrade(config, D09_DOWN_REVISION)
    graph = _insert_full_demo_graph(session, include_episode=False)
    forged_values = _episode_insert_values(
        graph,
        profile_digest=hashlib.sha256(b"blocked-forged-profile").hexdigest(),
    )
    session.commit()

    blocker_engine = create_engine(database_url)
    blocker_connection = blocker_engine.connect()
    blocker_transaction = blocker_connection.begin()
    blocker_connection.execute(text("SELECT version_num FROM alembic_version FOR UPDATE"))
    insert_started = Event()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            migration_future = executor.submit(command.upgrade, config, DEMO_REVISION)
            try:
                _wait_for_episode_access_exclusive_lock(session)
                insert_future = executor.submit(
                    _insert_episode_values_in_new_connection,
                    database_url,
                    forged_values,
                    insert_started,
                )
                assert insert_started.wait(timeout=5)
                time.sleep(0.2)
                assert not insert_future.done()
            finally:
                if blocker_transaction.is_active:
                    blocker_transaction.commit()
            migration_future.result(timeout=20)
            assert insert_future.result(timeout=20) == "rejected"
    finally:
        if blocker_transaction.is_active:
            blocker_transaction.rollback()
        blocker_connection.close()
        blocker_engine.dispose()
        command.upgrade(config, DEMO_REVISION)

    assert session.scalar(text("SELECT version_num FROM alembic_version")) == DEMO_REVISION
    assert session.scalar(text("SELECT count(*) FROM demo_accepted_visual_episodes")) == 0


def test_d09_downgrade_serializes_insert_past_empty_check_and_restoration(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _truncate_demo_authority(session)
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = _demo_alembic_config(database_url)
    command.downgrade(config, D02_QUALITY_DOWN_REVISION)
    graph = _insert_full_demo_graph(session, include_episode=False)
    legal_values = _episode_insert_values(graph)
    session.commit()

    blocker_engine = create_engine(database_url)
    blocker_connection = blocker_engine.connect()
    blocker_transaction = blocker_connection.begin()
    blocker_connection.execute(text("SELECT version_num FROM alembic_version FOR UPDATE"))
    insert_started = Event()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            migration_future = executor.submit(
                command.downgrade,
                config,
                D09_DOWN_REVISION,
            )
            try:
                _wait_for_episode_access_exclusive_lock(session)
                insert_future = executor.submit(
                    _insert_episode_values_in_new_connection,
                    database_url,
                    legal_values,
                    insert_started,
                )
                assert insert_started.wait(timeout=5)
                time.sleep(0.2)
                assert not insert_future.done()
            finally:
                if blocker_transaction.is_active:
                    blocker_transaction.commit()
            migration_future.result(timeout=20)
            assert insert_future.result(timeout=20) == "inserted"

        assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
            D09_DOWN_REVISION
        )
        assert session.scalar(text("SELECT count(*) FROM demo_accepted_visual_episodes")) == 1
        session.commit()
        command.upgrade(config, DEMO_REVISION)
    finally:
        if blocker_transaction.is_active:
            blocker_transaction.rollback()
        blocker_connection.close()
        blocker_engine.dispose()
        command.upgrade(config, DEMO_REVISION)


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
