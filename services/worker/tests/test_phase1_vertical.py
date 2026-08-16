from __future__ import annotations

import io
import os
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

import httpx
import mirror_api.auth.service as auth_service_module
import mirror_api.main as main_module
import pytest
import redis.asyncio as redis
from mirror_api.account_deletion.service import RetryableAccountDeletionFailure
from mirror_api.asset_deletion.service import AssetDeletionService
from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage
from mirror_api.auth import AuthService, PolicyRequirement
from mirror_api.auth_dependencies import CSRF_COOKIE_NAME, get_auth_service
from mirror_api.config import (
    PurposeConsentSetting,
    RequiredPolicySetting,
    Settings,
    get_settings,
)
from mirror_api.data_rights.task_contract import (
    AccountDeletionTaskMessage,
    DataExportTaskMessage,
)
from mirror_api.ingestion.service import IngestionService
from mirror_api.ingestion.task_contract import IngestionTaskMessage
from mirror_api.models import AuditLog, InviteCode, User, UserSession, new_id
from mirror_api.providers.local import LocalObjectStorageProvider
from mirror_api.providers.mock import MockAgeAssuranceProvider
from mirror_api.rate_limit import RedisRateLimiter
from PIL import Image
from sqlalchemy import select, text

from mirror_worker.asset_deletion import AssetDeletionTaskExecutor
from mirror_worker.cleanup import SqlAlchemyIngestionCleanup
from mirror_worker.data_rights import AccountDeletionTaskExecutor, DataExportTaskExecutor
from mirror_worker.ingestion import IngestionTaskExecutor

pytestmark = pytest.mark.integration


class _RecordingSmsProvider:
    def __init__(self) -> None:
        self.codes: list[str] = []

    async def send_verification_code(
        self, *, destination_phone: str, verification_code: str, request_reference: str
    ) -> str:
        del destination_phone, request_reference
        self.codes.append(verification_code)
        return f"phase1-fixture-message-{len(self.codes)}"


def _isolated_redis_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, "/14", "", ""))


def _synthetic_non_face_png() -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", (64, 64), color=(24, 96, 168))
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


@pytest.mark.asyncio
async def test_phase1_vertical_lifecycle_and_recovery_is_owner_bound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    base_redis_url = os.getenv("TEST_REDIS_URL")
    if not database_url or not base_redis_url:
        pytest.skip("NOT VERIFIED LOCALLY: PostgreSQL and Redis are required")

    origin = "http://127.0.0.1:3000"
    redis_url = _isolated_redis_url(base_redis_url)
    policy = PolicyRequirement("privacy", "phase1-v1", "d" * 64)
    settings = Settings(
        app_env="test",
        database_url=database_url,
        redis_url=redis_url,
        cors_origins=[origin],
        rate_limiter_backend="redis",
        task_runner="local",
        local_storage_root=tmp_path / "private-storage",
        auth_required_policies=[
            RequiredPolicySetting(
                document_code=policy.document_code,
                document_version=policy.document_version,
                document_digest=policy.document_digest,
            )
        ],
        facial_data_purpose=PurposeConsentSetting(policy_digest="e" * 64),
    )
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        auth_service_module,
        "normalize_china_phone",
        lambda _: "+86synthetic-phase1-fixture",
    )
    app = main_module.create_app()
    infrastructure = app.state.auth_infrastructure
    redis_client: Any = redis.from_url(redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
    prefix = f"mirror:phase1-vertical:{uuid.uuid4().hex}"
    sms = _RecordingSmsProvider()
    age_credential = "synthetic-phase1-age-credential"
    auth = AuthService(
        session_factory=infrastructure.sessions,
        sms_provider=sms,
        age_provider=MockAgeAssuranceProvider(
            fixture_statuses={
                MockAgeAssuranceProvider.fixture_credential_key(age_credential): "verified"
            }
        ),
        rate_limiter=RedisRateLimiter(redis_client, prefix=prefix),
        hmac_keyring=settings.auth_hmac_keyring,
        hmac_active_kid=settings.auth_hmac_active_kid,
        jwt_keyring=settings.auth_jwt_keyring,
        jwt_active_kid=settings.auth_jwt_active_kid,
        jwt_issuer=settings.auth_jwt_issuer,
        jwt_audience=settings.auth_jwt_audience,
        required_policies=(policy,),
        allow_new_registrations=True,
    )
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        await redis_client.ping()
    except Exception as exc:
        await infrastructure.engine.dispose()
        await redis_client.aclose()
        pytest.skip(f"NOT VERIFIED LOCALLY: Redis is unavailable ({type(exc).__name__})")

    await redis_client.flushdb()
    async with infrastructure.engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE users, invite_codes CASCADE"))
    async with infrastructure.sessions() as session:
        async with session.begin():
            session.add(
                InviteCode(
                    id=new_id(),
                    code_hash=auth._hmac("synthetic-phase1-invite", "invite"),
                )
            )

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url=origin) as client:
            challenge = await client.post(
                "/api/v1/auth/sms-challenges",
                headers={
                    "Idempotency-Key": "phase1-challenge-once",
                    "X-Device-ID": "phase1-synthetic-device",
                },
                json={
                    "phone": "synthetic-phase1-phone",
                    "invite_code": "synthetic-phase1-invite",
                },
            )
            assert challenge.status_code == 202 and sms.codes
            session_response = await client.post(
                "/api/v1/auth/sessions",
                headers={"Idempotency-Key": "phase1-session-once"},
                json={"challenge_id": challenge.json()["challenge_id"], "otp": sms.codes[0]},
            )
            assert session_response.status_code == 201
            pending_access = session_response.json()["access_token"]

            age = await client.post(
                "/api/v1/users/me/age-assurances",
                headers={
                    "Authorization": f"Bearer {pending_access}",
                    "Idempotency-Key": "phase1-age-once",
                },
                json={"credential": age_credential},
            )
            assert age.status_code == 201 and age.json()["activated"] is False
            accepted = await client.post(
                "/api/v1/users/me/policy-acceptances",
                headers={
                    "Authorization": f"Bearer {pending_access}",
                    "Idempotency-Key": "p" * 16,
                },
                json={
                    "document_code": policy.document_code,
                    "document_version": policy.document_version,
                    "document_digest": policy.document_digest,
                },
            )
            assert accepted.status_code == 201 and accepted.json()["activated"] is True
            csrf = client.cookies.get(CSRF_COOKIE_NAME)
            assert csrf is not None
            refreshed = await client.post(
                "/api/v1/auth/token/refresh",
                headers={
                    "Idempotency-Key": "phase1-refresh-once",
                    "Origin": origin,
                    "X-CSRF-Token": csrf,
                },
            )
            assert refreshed.status_code == 200 and refreshed.json()["scope"] == "active"
            active_access = refreshed.json()["access_token"]
            headers = {"Authorization": f"Bearer {active_access}"}

            consent = await client.post(
                "/api/v1/users/me/consents",
                headers={**headers, "Idempotency-Key": "phase1-consent-once"},
            )
            assert consent.status_code == 201

            payload = _synthetic_non_face_png()
            checksum = sha256(payload).hexdigest()
            intent = await client.post(
                "/api/v1/assets/upload-intents",
                headers={**headers, "Idempotency-Key": "phase1-upload-once"},
                json={
                    "content_type": "image/png",
                    "byte_size": len(payload),
                    "sha256": checksum,
                },
            )
            assert intent.status_code == 201 and intent.json()["upload"] is not None
            intent_id = intent.json()["intent"]["intent_id"]
            upload = intent.json()["upload"]
            uploaded = await client.put(
                upload["url"].removeprefix("http://127.0.0.1:8000"),
                headers=upload["required_headers"],
                content=payload,
            )
            assert uploaded.status_code == 204
            completed = await client.post(
                f"/api/v1/assets/upload-intents/{intent_id}/complete",
                headers={**headers, "Idempotency-Key": "phase1-complete-once"},
            )
            assert completed.status_code == 200
            ingestion = await client.post(
                f"/api/v1/assets/upload-intents/{intent_id}/ingestion-jobs",
                headers={**headers, "Idempotency-Key": "i" * 16},
            )
            assert ingestion.status_code == 202
            ingestion_job_id = ingestion.json()["job_id"]

            coordinator = app.state.ingestion_infrastructure.coordinator
            ingestion_service = cast(IngestionService, coordinator._service)
            storage = cast(LocalObjectStorageProvider, app.state.object_storage_provider)
            cleanup = SqlAlchemyIngestionCleanup(
                session_factory=infrastructure.sessions,
                storage=storage,
            )
            processed = await IngestionTaskExecutor(ingestion_service, cleanup).execute(
                IngestionTaskMessage(
                    job_id=ingestion_job_id,
                    request_id="phase1-ingestion-worker",
                )
            )
            assert processed.status == "promoted"
            job = await client.get(f"/api/v1/jobs/{ingestion_job_id}", headers=headers)
            assert job.status_code == 200 and job.json()["status"] == "promoted"
            asset_id = job.json()["asset_id"]
            assert isinstance(asset_id, str)

            asset_grant = await client.post(
                f"/api/v1/assets/{asset_id}/download-grants",
                headers={**headers, "Idempotency-Key": "phase1-asset-download"},
            )
            assert asset_grant.status_code == 201
            asset_download = await client.get(
                asset_grant.json()["url"].removeprefix("http://127.0.0.1:8000"),
                headers=asset_grant.json()["required_headers"],
            )
            assert asset_download.status_code == 200
            assert asset_download.headers["content-type"].startswith("image/jpeg")

            rights = app.state.data_rights_infrastructure.coordinator
            export = await client.post(
                "/api/v1/users/me/data-exports",
                headers={**headers, "Idempotency-Key": "phase1-export-once"},
            )
            assert export.status_code == 202
            export_job_id = export.json()["job_id"]
            export_result = await DataExportTaskExecutor(rights.exports).execute(
                DataExportTaskMessage(
                    job_id=export_job_id,
                    request_id="phase1-export-worker",
                )
            )
            assert export_result.status == "ready"
            export_state = await client.get(
                f"/api/v1/users/me/data-exports/{export.json()['export_id']}",
                headers=headers,
            )
            assert export_state.status_code == 200 and export_state.json()["status"] == "ready"

            asset_deletion = await client.delete(
                f"/api/v1/assets/{asset_id}",
                headers={**headers, "Idempotency-Key": "phase1-asset-delete"},
            )
            assert asset_deletion.status_code == 202
            asset_deletion_service = cast(
                AssetDeletionService,
                app.state.asset_deletion_infrastructure.coordinator._service,
            )
            deleted_asset = await AssetDeletionTaskExecutor(asset_deletion_service).execute(
                AssetDeletionTaskMessage(
                    job_id=asset_deletion.json()["job_id"],
                    request_id="phase1-asset-delete-worker",
                )
            )
            assert deleted_asset.status == "completed"
            assert (
                await client.get(f"/api/v1/assets/{asset_id}", headers=headers)
            ).status_code == 404

            account = await client.post(
                "/api/v1/users/me/deletion-requests",
                headers={**headers, "Idempotency-Key": "phase1-account-delete"},
            )
            assert account.status_code == 202
            account_message = AccountDeletionTaskMessage(
                job_id=account.json()["job_id"],
                request_id="phase1-account-delete-worker",
            )
            account_executor = AccountDeletionTaskExecutor(rights.account_deletions)
            with pytest.raises(
                RetryableAccountDeletionFailure,
                match="awaits terminal work or upload grant expiry",
            ):
                await account_executor.execute(account_message)
            rights.account_deletions._now = lambda: datetime(2035, 1, 1, tzinfo=UTC)
            deleted_account = await account_executor.execute(account_message)
            assert deleted_account.status == "completed"
            status = await client.get(
                "/api/v1/users/me/deletion-requests/current",
                headers=headers,
            )
            assert status.status_code == 200 and status.json()["status"] == "completed"
            assert (await client.get("/api/v1/assets", headers=headers)).status_code == 401

        async with infrastructure.sessions() as session:
            user = await session.scalar(select(User))
            persisted_session = await session.scalar(select(UserSession))
            audits = list((await session.scalars(select(AuditLog))).all())
            assert user is not None and user.status == "deleted"
            assert user.phone_hash != auth._hmac("+86synthetic-phase1-fixture", "phone")
            assert len(user.phone_hash) == 128
            int(user.phone_hash, 16)
            assert persisted_session is not None and persisted_session.revoked_at is not None
            assert audits
            persisted = str(
                [(audit.action, audit.request_id, audit.metadata_json) for audit in audits]
            )
            for marker in (
                "synthetic-phase1-phone",
                "synthetic-phase1-invite",
                age_credential,
                sms.codes[0],
                payload.hex(),
            ):
                assert marker not in persisted
    finally:
        async with infrastructure.engine.begin() as connection:
            await connection.execute(text("TRUNCATE TABLE users, invite_codes CASCADE"))
        await redis_client.flushdb()
        await redis_client.aclose()
        await infrastructure.engine.dispose()
        app.dependency_overrides.clear()
        get_settings.cache_clear()
