from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "ci", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Environment = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    debug: bool = False
    database_url: str = "postgresql+psycopg://mirror:mirror_dev_only@127.0.0.1:5432/mirror"
    redis_url: str = "redis://127.0.0.1:6379/0"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:3000", "http://localhost:3000"]
    )
    auth_token_secret: str = "development-only-not-for-production"  # noqa: S105
    auth_callback_url: str = "http://127.0.0.1:3000/auth/callback"

    sms_provider: Literal["mock", "tencent"] = "mock"
    storage_provider: Literal["local", "tencent_cos"] = "local"
    local_storage_root: Path = Path(".local-storage")
    object_storage_private: bool = True
    signed_url_ttl_seconds: int = Field(default=300, ge=60, le=900)

    vision_provider: Literal["mock", "disabled", "verified_external", "tencent_candidate"] = "mock"
    image_generation_provider: Literal[
        "mock", "disabled", "verified_external", "tencent_candidate"
    ] = "mock"
    agent_provider: Literal["mock", "disabled", "verified_external", "tencent_candidate"] = "mock"
    task_runner: Literal["local", "celery"] = "local"

    sensitive_processing_enabled: bool = False
    legal_review_status: Literal["required", "approved"] = "required"
    provider_benchmark_status: Literal["required", "approved"] = "required"

    tencent_secret_id: str | None = None
    tencent_secret_key: str | None = None
    tencent_region: str | None = None
    tencent_cos_bucket: str | None = None
    tencent_sms_app_id: str | None = None
    tencent_sms_sign_name: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_environment_boundary(self) -> Settings:
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("PostgreSQL is the only supported relational database")
        if not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("Redis URL must use redis:// or rediss://")
        if not self.object_storage_private:
            raise ValueError("Project Mirror forbids public object storage")

        if self.app_env in {"test", "ci"}:
            if any(
                provider != "mock"
                for provider in (
                    self.sms_provider,
                    self.vision_provider,
                    self.image_generation_provider,
                    self.agent_provider,
                )
            ):
                raise ValueError("test and ci require deterministic mock providers")
            if self.storage_provider != "local":
                raise ValueError("test and ci forbid real object storage writes")

        if self.app_env == "ci" and self.task_runner != "celery":
            raise ValueError("ci must exercise the Celery task adapter")

        if self.app_env == "production":
            self._validate_production()
        return self

    def _validate_production(self) -> None:
        failures: list[str] = []
        if self.debug:
            failures.append("debug must be false")
        if self.sms_provider != "tencent":
            failures.append("real SMS provider required")
        if self.storage_provider != "tencent_cos":
            failures.append("private Tencent COS required")
        if self.task_runner != "celery":
            failures.append("Celery task runner required")
        if any(
            provider != "disabled"
            for provider in (
                self.vision_provider,
                self.image_generation_provider,
                self.agent_provider,
            )
        ):
            failures.append("Phase 0 production AI providers must remain disabled")
        if self.sensitive_processing_enabled:
            failures.append("Phase 0 forbids production sensitive processing")
        if self.legal_review_status != "required" or self.provider_benchmark_status != "required":
            failures.append("Phase 0 gates cannot be marked approved")
        if len(self.auth_token_secret) < 32 or any(
            marker in self.auth_token_secret.lower()
            for marker in ("development", "default", "change-me", "password")
        ):
            failures.append("secure non-default auth token secret required")
        callback = urlparse(self.auth_callback_url)
        if callback.scheme != "https" or callback.hostname in {"localhost", "127.0.0.1"}:
            failures.append("HTTPS production callback required")
        for origin in self.cors_origins:
            parsed = urlparse(origin)
            if parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1"}:
                failures.append("development or insecure CORS origin forbidden")
                break
        required = {
            "tencent_secret_id": self.tencent_secret_id,
            "tencent_secret_key": self.tencent_secret_key,
            "tencent_region": self.tencent_region,
            "tencent_cos_bucket": self.tencent_cos_bucket,
            "tencent_sms_app_id": self.tencent_sms_app_id,
            "tencent_sms_sign_name": self.tencent_sms_sign_name,
        }
        failures.extend(f"missing {name}" for name, value in required.items() if not value)
        if failures:
            raise ValueError("unsafe production configuration: " + "; ".join(failures))


@lru_cache
def get_settings() -> Settings:
    return Settings()
