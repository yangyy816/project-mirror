from __future__ import annotations

import pytest
from pydantic import ValidationError

from mirror_api.config import Settings, image_sanitizer_config


def production_settings(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "app_env": "production",
        "debug": False,
        "database_url": "postgresql+psycopg://service:password@db.internal/mirror",
        "redis_url": "rediss://redis.internal/0",
        "cors_origins": ["https://mirror.example"],
        "auth_token_secret": "x" * 64,
        "auth_jwt_keyring": {"prod-2026": "j" * 64},
        "auth_jwt_active_kid": "prod-2026",
        "auth_hmac_keyring": {"prod-2026": "h" * 64},
        "auth_hmac_active_kid": "prod-2026",
        "auth_callback_url": "https://mirror.example/auth/callback",
        "auth_required_policies": [
            {
                "document_code": "privacy",
                "document_version": "v1",
                "document_digest": "d" * 64,
            }
        ],
        "facial_data_purpose": {"policy_digest": "f" * 64},
        "sms_provider": "tencent",
        "storage_provider": "tencent_cos",
        "task_runner": "celery",
        "vision_provider": "disabled",
        "image_generation_provider": "disabled",
        "synthetic_storage_provider": "disabled",
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
    "url",
    (
        "https://uploads.example",
        "http://localhost:8000/path",
        "http://user:password@localhost:8000",
        "http://localhost:8000?token=value",
    ),
)
def test_local_upload_ingress_is_restricted_to_loopback(url: str) -> None:
    with pytest.raises(ValidationError, match="loopback HTTP origin"):
        Settings(local_upload_base_url=url)


def test_image_sanitizer_configuration_rejects_inconsistent_bounds() -> None:
    with pytest.raises(ValidationError, match="minimum edge"):
        Settings(image_sanitizer_min_edge_pixels=128, image_sanitizer_max_edge_pixels=64)
    with pytest.raises(ValidationError, match="pixel limit"):
        Settings(image_sanitizer_min_edge_pixels=128, image_sanitizer_max_pixel_count=4096)


def test_image_sanitizer_configuration_is_versioned_and_mapped() -> None:
    config = image_sanitizer_config(Settings(image_sanitizer_spool_memory_bytes=4096))
    assert config.version == "image-sanitizer-v1"
    assert config.spool_memory_bytes == 4096


@pytest.mark.parametrize("operations", ([], ["private_upload", "private_upload"]))
def test_purpose_consent_operations_are_non_empty_and_unique(operations: list[str]) -> None:
    with pytest.raises(ValidationError, match="non-empty and unique"):
        Settings(
            facial_data_purpose={
                "operations": operations,
                "policy_digest": "a" * 64,
            }
        )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"debug": True}, "debug must be false"),
        ({"sms_provider": "mock"}, "real SMS provider required"),
        ({"storage_provider": "local"}, "private Tencent COS required"),
        ({"task_runner": "local"}, "Celery task runner required"),
        ({"vision_provider": "mock"}, "production AI providers must remain disabled"),
        (
            {"synthetic_storage_provider": "mock"},
            "production synthetic storage provider must remain disabled",
        ),
        (
            {"synthetic_storage_provider": "local"},
            "production synthetic storage provider must remain disabled",
        ),
        ({"auth_token_secret": "change-me"}, "secure non-default auth token secret"),
        (
            {"facial_data_purpose": {"policy_digest": "0" * 64}},
            "configured purpose consent policy digest required",
        ),
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


def test_production_registration_requires_every_approved_dependency() -> None:
    settings = Settings(
        **production_settings(
            registration_enabled=True,
            rate_limiter_backend="redis",
            age_assurance_provider="verified_external",
            age_assurance_provider_status="verified",
            registration_security_gate_status="approved",
            legal_review_status="approved",
        )
    )
    assert settings.registration_enabled


def test_ci_requires_deterministic_providers_and_celery() -> None:
    with pytest.raises(ValidationError, match="ci must exercise"):
        Settings(app_env="ci", task_runner="local")
    with pytest.raises(ValidationError, match="deterministic mock"):
        Settings(app_env="ci", task_runner="celery", vision_provider="disabled")
    with pytest.raises(ValidationError, match="deterministic mock"):
        Settings(app_env="test", age_assurance_provider="disabled")
    with pytest.raises(ValidationError, match="deterministic mock"):
        Settings(app_env="ci", task_runner="celery", age_assurance_provider="disabled")
    assert (
        Settings(
            app_env="ci", task_runner="celery", synthetic_storage_provider="local"
        ).synthetic_storage_provider
        == "local"
    )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"registration_enabled": True}, "registration requires Redis rate limiting"),
        (
            {"registration_enabled": True, "rate_limiter_backend": "redis"},
            "registration requires verified age provider",
        ),
        (
            {
                "registration_enabled": True,
                "rate_limiter_backend": "redis",
                "age_assurance_provider": "verified_external",
            },
            "registration requires verified age provider status",
        ),
        (
            {
                "registration_enabled": True,
                "rate_limiter_backend": "redis",
                "age_assurance_provider": "verified_external",
                "age_assurance_provider_status": "verified",
                "registration_security_gate_status": "approved",
                "legal_review_status": "approved",
                "auth_required_policies": [],
            },
            "registration requires configured policy requirements",
        ),
        ({"auth_jwt_keyring": {"prod-2026": "default-key"}}, "secure non-default JWT keyring"),
    ],
)
def test_production_registration_and_keyrings_fail_closed(
    override: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(**production_settings(**override))
