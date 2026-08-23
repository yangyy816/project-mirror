from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mirror_api.config import get_settings
from mirror_api.demo_models import DemoActor
from mirror_api.main import create_app
from mirror_api.models import new_id


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _authority_digest(schema_version: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(schema_version.encode() + b"\n" + _canonical_json(payload)).hexdigest()


def _authority_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def test_main_application_authenticates_demo_actor_from_postgresql(
    monkeypatch: pytest.MonkeyPatch,
    app_env: str,
) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")

    credential = f"d01c-{new_id()}"
    credential_key_id = f"d01c-{new_id()}"
    credential_digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()
    authority_at = datetime(2026, 8, 23, 12, tzinfo=UTC)
    schema_version = "mirror.demo/DemoActor/v1"
    payload = {
        "actor_kind": "AUTOMATED_TEST",
        "authority_at": _authority_time(authority_at),
        "credential_key_id": credential_key_id,
    }
    actor = DemoActor(
        id=new_id(),
        schema_version=schema_version,
        canonical_payload=payload,
        content_digest=_authority_digest(schema_version, payload),
        created_at=authority_at,
        actor_kind="AUTOMATED_TEST",
        credential_key_id=credential_key_id,
        authority_at=authority_at,
    )
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            session.add(actor)
            session.commit()
    finally:
        engine.dispose()

    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("TASK_RUNNER", "celery" if app_env == "ci" else "local")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv(
        "DEMO_BEARER_TOKEN_SHA256_BY_KEY_ID",
        json.dumps({credential_key_id: credential_digest}),
    )
    get_settings.cache_clear()
    app = create_app()
    try:
        with TestClient(app) as client:
            accepted = client.get(
                "/api/v1/demo/capabilities",
                headers={"Authorization": f"Bearer {credential}"},
            )
            assert accepted.status_code == 200
            assert accepted.json()["track"] == "DEMO_PROTOTYPE"

            rejected = client.get(
                "/api/v1/demo/capabilities",
                headers={"Authorization": "Bearer invalid-d01c-credential"},
            )
            assert rejected.status_code == 401
            assert rejected.json()["code"] == "demo_authentication_failed"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.fixture(params=["test", "ci"])
def app_env(request: pytest.FixtureRequest) -> str:
    return str(request.param)
