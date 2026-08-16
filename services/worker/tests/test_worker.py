from __future__ import annotations

import json
import os

import pytest
from mirror_api.config import Settings
from mirror_api.ingestion.task_contract import IngestionTaskMessage

from mirror_worker.application import FoundationProbeService, TaskEnvelope
from mirror_worker.celery_adapter import (
    INGESTION_RETRY_POLICY,
    RETRY_POLICY,
    celery_app,
    cleanup_asset_ingestion,
    foundation_probe,
    process_asset_ingestion,
    reconcile_asset_ingestion,
)
from mirror_worker.local import LocalTaskRunner


def envelope() -> TaskEnvelope:
    return TaskEnvelope(
        job_id="a" * 32,
        request_id="request-test-1234",
        idempotency_key_hash="b" * 64,
        task_type="foundation_probe",
        payload={},
    )


def test_application_logic_has_no_celery_dependency() -> None:
    result = FoundationProbeService().execute(envelope())
    assert result == {
        "job_id": "a" * 32,
        "request_id": "request-test-1234",
        "status": "ok",
    }


def test_task_contract_round_trips_through_json() -> None:
    message = json.loads(json.dumps(envelope().to_message()))
    assert TaskEnvelope.from_message(message) == envelope()


def test_local_runner_is_development_only(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = LocalTaskRunner(Settings(app_env="test"))
    assert runner.dispatch(envelope()) == "a" * 32

    captured: list[dict[str, str]] = []

    async def fake_ingestion_runner(
        message: dict[str, str], *, settings: Settings
    ) -> dict[str, str]:
        assert settings.app_env == "test"
        captured.append(message)
        return {"job_id": message["job_id"], "status": "no_op"}

    monkeypatch.setattr("mirror_worker.local.run_ingestion_message", fake_ingestion_runner)
    ingestion_message = IngestionTaskMessage(job_id="c" * 32, request_id="local-ingestion-request")
    assert runner.dispatch_ingestion(ingestion_message) == ingestion_message.job_id
    assert captured == [ingestion_message.to_message()]
    with pytest.raises(RuntimeError, match="DEVELOPMENT ONLY"):
        LocalTaskRunner(
            Settings(
                app_env="production",
                sms_provider="tencent",
                storage_provider="tencent_cos",
                task_runner="celery",
                vision_provider="disabled",
                image_generation_provider="disabled",
                synthetic_storage_provider="disabled",
                agent_provider="disabled",
                auth_token_secret="x" * 64,
                auth_jwt_keyring={"test-jwt-v1": "j" * 64},
                auth_jwt_active_kid="test-jwt-v1",
                auth_hmac_keyring={"test-hmac-v1": "h" * 64},
                auth_hmac_active_kid="test-hmac-v1",
                facial_data_purpose={"policy_digest": "f" * 64},
                auth_callback_url="https://mirror.example/auth/callback",
                cors_origins=["https://mirror.example"],
                tencent_secret_id="configured-in-secret-manager",  # noqa: S106
                tencent_secret_key="configured-in-secret-manager",  # noqa: S106
                tencent_region="ap-beijing",
                tencent_cos_bucket="private-bucket",
                tencent_sms_app_id="configured",
                tencent_sms_sign_name="configured",
            )
        )


def test_celery_registration_and_retry_policy() -> None:
    assert "mirror.foundation_probe" in celery_app.tasks
    assert RETRY_POLICY == {"max_retries": 3, "retry_backoff": True, "retry_jitter": True}
    assert foundation_probe.run(envelope().to_message())["status"] == "ok"
    assert {
        "mirror.asset_ingestion.process",
        "mirror.asset_ingestion.cleanup",
        "mirror.asset_ingestion.reconcile",
    } <= set(celery_app.tasks)
    assert INGESTION_RETRY_POLICY == {
        "max_retries": 3,
        "retry_backoff": True,
        "retry_backoff_max": 60,
        "retry_jitter": True,
    }
    routes = celery_app.conf.task_routes
    assert routes["mirror.asset_ingestion.process"]["queue"] == "mirror.ingestion"
    assert routes["mirror.asset_ingestion.cleanup"]["queue"] == "mirror.maintenance"
    assert celery_app.conf.worker_prefetch_multiplier == 1


@pytest.mark.integration
def test_linux_celery_redis_round_trip() -> None:
    if os.getenv("RUN_CELERY_INTEGRATION") != "true":
        pytest.skip("NOT VERIFIED LOCALLY: Linux Celery + Redis worker unavailable")
    result = foundation_probe.apply_async(args=[envelope().to_message()], task_id=envelope().job_id)
    assert result.get(timeout=15) == {
        "job_id": envelope().job_id,
        "request_id": envelope().request_id,
        "status": "ok",
    }


@pytest.mark.integration
def test_linux_ingestion_celery_redis_round_trip() -> None:
    if os.getenv("RUN_CELERY_INTEGRATION") != "true":
        pytest.skip("NOT VERIFIED LOCALLY: Linux Celery + Redis worker unavailable")
    message = IngestionTaskMessage(job_id="e" * 32, request_id="celery-ingestion-test")
    result = process_asset_ingestion.apply_async(args=[message.to_message()])
    assert result.get(timeout=20) == {"job_id": message.job_id, "status": "no_op"}


def test_ingestion_tasks_use_late_ack_and_worker_lost_recovery() -> None:
    for task in (process_asset_ingestion, cleanup_asset_ingestion, reconcile_asset_ingestion):
        assert task.acks_late is True
        assert task.reject_on_worker_lost is True
