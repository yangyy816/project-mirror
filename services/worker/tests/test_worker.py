from __future__ import annotations

import json
import os

import pytest
from mirror_api.config import Settings

from mirror_worker.application import FoundationProbeService, TaskEnvelope
from mirror_worker.celery_adapter import RETRY_POLICY, celery_app, foundation_probe
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


def test_local_runner_is_development_only() -> None:
    runner = LocalTaskRunner(Settings(app_env="test"))
    assert runner.dispatch(envelope()) == "a" * 32
    with pytest.raises(RuntimeError, match="DEVELOPMENT ONLY"):
        LocalTaskRunner(
            Settings(
                app_env="production",
                sms_provider="tencent",
                storage_provider="tencent_cos",
                task_runner="celery",
                vision_provider="disabled",
                image_generation_provider="disabled",
                agent_provider="disabled",
                auth_token_secret="x" * 64,
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
