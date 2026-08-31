from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from mirror_api.config import get_settings
from mirror_api.models import (
    OfflineSyntheticSourceAdmission,
    SyntheticAssetRecord,
    SyntheticSourceObject,
    new_id,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 18, tzinfo=UTC)


@pytest.fixture
def session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE synthetic_asset_records, "
                "synthetic_source_object_deletion_evidence, "
                "synthetic_source_objects, offline_synthetic_source_admissions CASCADE"
            )
        )
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def _admission(**overrides: object) -> OfflineSyntheticSourceAdmission:
    values: dict[str, object] = {
        "id": new_id(),
        "schema_version": "mirror.synthetic-dataset/OfflineSyntheticSourceAdmission/v1",
        "admission_evidence_schema_version": (
            "mirror.synthetic-dataset/CodexNativeAdmissionEvidence/v2"
        ),
        "specification_reference": "offline-v01-spec-a",
        "specification_version": "offline-v01-spec-v1",
        "generation_policy_reference": "offline-policy-v1",
        "prompt_template_reference": "offline-prompt-v1",
        "prompt_digest": "a" * 64,
        "item_reference": "offline-v01-item-a",
        "attempt": 1,
        "source_kind": "CODEX_NATIVE_IMAGEGEN",
        "provenance_level": "PROVENANCE_ONLY",
        "cost_accounting_mode": "REQUEST_COUNT_ONLY",
        "synthetic_only": True,
        "real_person_reference_used": False,
        "generated_at": NOW,
        "admitted_at": NOW + timedelta(seconds=1),
        "sha256": "b" * 64,
        "media_type": "image/png",
        "byte_size": 68,
        "width": 1,
        "height": 1,
        "requested_width": None,
        "requested_height": None,
        "dimensions_match_requested": None,
        "storage_reference": f"native-{new_id()}",
        "retention_expires_at": NOW + timedelta(days=1),
        "admission_evidence_digest": "c" * 64,
        "model_reference": None,
        "model_version_reference": None,
        "provider_request_reference": None,
        "provider_actual_seed": None,
        "provider_usage": None,
        "provider_cost": None,
    }
    values.update(overrides)
    return OfflineSyntheticSourceAdmission(**values)


def _source(
    admission: OfflineSyntheticSourceAdmission, **overrides: object
) -> SyntheticSourceObject:
    values: dict[str, object] = {
        "id": new_id(),
        "schema_version": "mirror.synthetic-dataset/SyntheticSourceObject/v2",
        "generation_item_id": None,
        "job_attempt_id": None,
        "offline_admission_id": admission.id,
        "storage_reference": admission.storage_reference,
        "sha256": admission.sha256,
        "media_type": admission.media_type,
        "byte_size": admission.byte_size,
        "width": admission.width,
        "height": admission.height,
        "retention_expires_at": admission.retention_expires_at,
        "created_at": admission.admitted_at,
    }
    values.update(overrides)
    return SyntheticSourceObject(**values)


def test_offline_receipt_preserves_known_null_facts_and_is_immutable(session: Session) -> None:
    admission = _admission()
    session.add(admission)
    session.commit()

    for field, value in (
        ("model_reference", "invented"),
        ("provider_actual_seed", 1),
        ("provider_usage", {"invented": True}),
        ("provider_cost", {"invented": True}),
    ):
        with pytest.raises(DBAPIError, match="offline synthetic source admission is immutable"):
            session.execute(
                update(OfflineSyntheticSourceAdmission)
                .where(OfflineSyntheticSourceAdmission.id == admission.id)
                .values({field: value})
            )
            session.commit()
        session.rollback()

    with pytest.raises(DBAPIError):
        session.add(_admission(admission_evidence_digest=admission.admission_evidence_digest))
        session.commit()
    session.rollback()


def test_offline_source_xor_metadata_binding_and_normalization_authority(session: Session) -> None:
    admission = _admission()
    session.add(admission)
    session.commit()
    source = _source(admission)
    session.add(source)
    session.commit()

    record = SyntheticAssetRecord(
        id=new_id(),
        source_object_id=source.id,
        normalizer_version="image-sanitizer-v1",
        normalizer_config_digest="d" * 64,
    )
    session.add(record)
    session.commit()
    assert record.status == "NORMALIZATION_PENDING"

    with pytest.raises(DBAPIError, match="offline synthetic source object differs"):
        session.add(_source(admission, storage_reference="native-metadata-mismatch"))
        session.commit()
    session.rollback()

    with pytest.raises(DBAPIError):
        session.add(
            SyntheticSourceObject(
                id=new_id(),
                schema_version="mirror.synthetic-dataset/SyntheticSourceObject/v2",
                generation_item_id="not-a-real-generation-item",
                job_attempt_id=None,
                offline_admission_id=admission.id,
                storage_reference="native-xor-negative",
                sha256="e" * 64,
                media_type="image/png",
                byte_size=1,
                width=1,
                height=1,
                retention_expires_at=NOW + timedelta(days=1),
                created_at=NOW,
            )
        )
        session.commit()
    session.rollback()


def test_0011_downgrade_fails_closed_when_offline_authority_exists(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    admission = _admission()
    session.add(admission)
    session.commit()
    session.close()

    database_url = os.environ["TEST_DATABASE_URL"]
    root = Path(__file__).resolve().parents[3]
    config = Config(root / "services" / "api" / "alembic.ini")
    config.set_main_option("script_location", str(root / "services" / "api" / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    with pytest.raises(DBAPIError, match="0011 downgrade would discard offline"):
        command.downgrade(config, "0010_synthetic_asset_qa")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "demo_0017_d10_context_queue"
        )
    engine.dispose()
    get_settings.cache_clear()
