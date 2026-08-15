from __future__ import annotations

import pytest
from pydantic import ValidationError

from mirror_api.config import Settings


def production_settings(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "app_env": "production",
        "debug": False,
        "database_url": "postgresql+psycopg://service:password@db.internal/mirror",
        "redis_url": "rediss://redis.internal/0",
        "cors_origins": ["https://mirror.example"],
        "auth_token_secret": "x" * 64,
        "auth_callback_url": "https://mirror.example/auth/callback",
        "sms_provider": "tencent",
        "storage_provider": "tencent_cos",
        "task_runner": "celery",
        "vision_provider": "disabled",
        "image_generation_provider": "disabled",
        "agent_provider": "disabled",
        "tencent_secret_id": "from-secret-manager",
        "tencent_secret_key": "from-secret-manager",
        "tencent_region": "ap-beijing",
        "tencent_cos_bucket": "private-bucket",
        "tencent_sms_app_id": "from-secret-manager",
        "tencent_sms_sign_name": "from-secret-manager",
    }
    values.update(overrides)
    return values


def test_sqlite_is_rejected_in_every_environment() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL is the only supported"):
        Settings(database_url="sqlite+pysqlite:///:memory:")


def test_public_object_storage_is_always_rejected() -> None:
    with pytest.raises(ValidationError, match="forbids public object storage"):
        Settings(object_storage_private=False)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"debug": True}, "debug must be false"),
        ({"sms_provider": "mock"}, "real SMS provider required"),
        ({"storage_provider": "local"}, "private Tencent COS required"),
        ({"task_runner": "local"}, "Celery task runner required"),
        ({"vision_provider": "mock"}, "production AI providers must remain disabled"),
        ({"auth_token_secret": "change-me"}, "secure non-default auth token secret"),
        ({"cors_origins": ["http://localhost:3000"]}, "CORS origin forbidden"),
        ({"auth_callback_url": "http://localhost/callback"}, "production callback required"),
        ({"sensitive_processing_enabled": True}, "forbids production sensitive processing"),
    ],
)
def test_production_fails_closed(override: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(**production_settings(**override))


def test_safe_phase_zero_production_shell_can_start_with_ai_disabled() -> None:
    settings = Settings(**production_settings())
    assert settings.vision_provider == "disabled"
    assert settings.sensitive_processing_enabled is False


def test_ci_requires_deterministic_providers_and_celery() -> None:
    with pytest.raises(ValidationError, match="ci must exercise"):
        Settings(app_env="ci", task_runner="local")
    with pytest.raises(ValidationError, match="deterministic mock"):
        Settings(app_env="ci", task_runner="celery", vision_provider="disabled")
