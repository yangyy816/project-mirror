from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mirror_api.image_sanitizer import ImageSanitizerConfig

Environment = Literal["development", "test", "ci", "production"]
AuthProvider = Literal["mock", "disabled", "verified_external"]
ProviderVerificationStatus = Literal["unverified", "verified"]
GateStatus = Literal["required", "approved"]
RateLimiterBackend = Literal["fake", "redis"]
ConsentOperation = Literal["private_upload", "security_validation"]

DEFAULT_AUTH_JWT_KEYRING = {"dev-v1": "development-only-not-for-production"}
DEFAULT_AUTH_HMAC_KEYRING = {"dev-v1": "development-only-hmac-not-for-production"}


class RequiredPolicySetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_code: str = Field(min_length=1, max_length=64)
    document_version: str = Field(min_length=1, max_length=64)
    document_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class PurposeConsentSetting(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    consent_type: Literal["facial_data_processing"] = "facial_data_processing"
    purpose_code: str = Field(default="personal_aesthetic_baseline", min_length=1, max_length=128)
    purpose_version: str = Field(default="purpose-v1", min_length=1, max_length=48)
    policy_code: str = Field(default="facial-data-policy", min_length=1, max_length=64)
    policy_version: str = Field(default="privacy-v1", min_length=1, max_length=48)
    policy_digest: str = Field(default="0" * 64, pattern=r"^[0-9a-f]{64}$")
    operations: tuple[ConsentOperation, ...] = (
        "private_upload",
        "security_validation",
    )

    @field_validator("operations")
    @classmethod
    def validate_operations(
        cls, value: tuple[ConsentOperation, ...]
    ) -> tuple[ConsentOperation, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("purpose consent operations must be non-empty and unique")
        return value


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
    auth_jwt_issuer: str = "project-mirror-api"
    auth_jwt_audience: str = "mirror-web"
    auth_jwt_keyring: dict[str, str] = Field(
        default_factory=lambda: DEFAULT_AUTH_JWT_KEYRING.copy()
    )
    auth_jwt_active_kid: str = "dev-v1"
    auth_hmac_keyring: dict[str, str] = Field(
        default_factory=lambda: DEFAULT_AUTH_HMAC_KEYRING.copy()
    )
    auth_hmac_active_kid: str = "dev-v1"
    auth_access_token_ttl_seconds: int = Field(default=300, ge=60, le=300)
    auth_refresh_token_ttl_seconds: int = Field(default=2_592_000, ge=86_400, le=2_592_000)
    auth_otp_ttl_seconds: int = Field(default=300, ge=60, le=900)
    auth_otp_attempt_limit: int = Field(default=5, ge=1, le=10)
    auth_refresh_cookie_name: str = "mirror_refresh"
    registration_enabled: bool = False
    age_assurance_provider: AuthProvider = "mock"
    age_assurance_provider_status: ProviderVerificationStatus = "unverified"
    registration_security_gate_status: GateStatus = "required"
    rate_limiter_backend: RateLimiterBackend = "fake"
    auth_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)
    auth_rate_limit_phone_limit: int = Field(default=5, ge=1, le=100)
    auth_rate_limit_ip_limit: int = Field(default=20, ge=1, le=1_000)
    auth_rate_limit_device_limit: int = Field(default=10, ge=1, le=1_000)
    auth_required_policies: list[RequiredPolicySetting] = Field(default_factory=list)
    facial_data_purpose: PurposeConsentSetting = Field(default_factory=PurposeConsentSetting)
    upload_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)
    upload_rate_limit_user_limit: int = Field(default=10, ge=1, le=1_000)
    upload_max_active_intents: int = Field(default=3, ge=1, le=100)
    upload_max_pending_bytes: int = Field(
        default=60 * 1024 * 1024,
        ge=20 * 1024 * 1024,
        le=2 * 1024 * 1024 * 1024,
    )

    sms_provider: Literal["mock", "tencent"] = "mock"
    storage_provider: Literal["local", "tencent_cos"] = "local"
    local_storage_root: Path = Path(".local-storage")
    local_upload_base_url: str = "http://127.0.0.1:8000"
    object_storage_private: bool = True
    signed_url_ttl_seconds: int = Field(default=300, ge=60, le=900)
    image_sanitizer_version: Literal["image-sanitizer-v1"] = "image-sanitizer-v1"
    image_sanitizer_max_input_bytes: int = Field(
        default=20 * 1024 * 1024, ge=1, le=20 * 1024 * 1024
    )
    image_sanitizer_max_output_bytes: int = Field(
        default=20 * 1024 * 1024, ge=1, le=20 * 1024 * 1024
    )
    image_sanitizer_min_edge_pixels: int = Field(default=64, ge=1, le=8192)
    image_sanitizer_max_edge_pixels: int = Field(default=8192, ge=64, le=8192)
    image_sanitizer_max_pixel_count: int = Field(default=40_000_000, ge=4096, le=40_000_000)
    image_sanitizer_spool_memory_bytes: int = Field(
        default=1024 * 1024, ge=1024, le=20 * 1024 * 1024
    )

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
        if self.storage_provider == "local":
            local_upload = urlparse(self.local_upload_base_url)
            if (
                local_upload.scheme != "http"
                or local_upload.hostname
                not in {
                    "127.0.0.1",
                    "localhost",
                }
                or any(
                    (
                        local_upload.username,
                        local_upload.password,
                        local_upload.query,
                        local_upload.fragment,
                        local_upload.path not in {"", "/"},
                    )
                )
            ):
                raise ValueError("local upload ingress must use a loopback HTTP origin")
        if self.image_sanitizer_min_edge_pixels > self.image_sanitizer_max_edge_pixels:
            raise ValueError("image sanitizer minimum edge cannot exceed maximum edge")
        if (
            self.image_sanitizer_max_pixel_count
            < self.image_sanitizer_min_edge_pixels * self.image_sanitizer_min_edge_pixels
        ):
            raise ValueError("image sanitizer pixel limit is below its minimum dimensions")

        if self.app_env in {"test", "ci"}:
            if any(
                provider != "mock"
                for provider in (
                    self.sms_provider,
                    self.vision_provider,
                    self.image_generation_provider,
                    self.agent_provider,
                    self.age_assurance_provider,
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
        if not self.registration_enabled and (
            self.legal_review_status != "required" or self.provider_benchmark_status != "required"
        ):
            failures.append("Phase 0 gates cannot be marked approved")
        if self._is_weak_secret(self.auth_token_secret):
            failures.append("secure non-default auth token secret required")
        if self.facial_data_purpose.policy_digest == "0" * 64:
            failures.append("configured purpose consent policy digest required")
        if self.auth_jwt_active_kid not in self.auth_jwt_keyring:
            failures.append("active JWT key id must exist in JWT keyring")
        if self.auth_hmac_active_kid not in self.auth_hmac_keyring:
            failures.append("active HMAC key id must exist in HMAC keyring")
        if any(self._is_weak_secret(secret) for secret in self.auth_jwt_keyring.values()):
            failures.append("secure non-default JWT keyring required")
        if any(self._is_weak_secret(secret) for secret in self.auth_hmac_keyring.values()):
            failures.append("secure non-default HMAC keyring required")
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
        if self.registration_enabled:
            if self.rate_limiter_backend != "redis":
                failures.append("registration requires Redis rate limiting")
            if self.sms_provider == "mock":
                failures.append("registration forbids mock SMS provider")
            if self.age_assurance_provider != "verified_external":
                failures.append("registration requires verified age provider")
            if self.age_assurance_provider_status != "verified":
                failures.append("registration requires verified age provider status")
            if self.registration_security_gate_status != "approved":
                failures.append("registration security gate must be approved")
            if self.legal_review_status != "approved":
                failures.append("registration legal review must be approved")
            if not self.auth_required_policies:
                failures.append("registration requires configured policy requirements")
        if failures:
            raise ValueError("unsafe production configuration: " + "; ".join(failures))

    @staticmethod
    def _is_weak_secret(secret: str) -> bool:
        return len(secret) < 32 or any(
            marker in secret.lower()
            for marker in ("development", "default", "change-me", "password", "example")
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def image_sanitizer_config(settings: Settings) -> ImageSanitizerConfig:
    """Create the single versioned sanitizer configuration from validated settings."""
    return ImageSanitizerConfig(
        version=settings.image_sanitizer_version,
        max_input_bytes=settings.image_sanitizer_max_input_bytes,
        max_output_bytes=settings.image_sanitizer_max_output_bytes,
        min_edge_pixels=settings.image_sanitizer_min_edge_pixels,
        max_edge_pixels=settings.image_sanitizer_max_edge_pixels,
        max_pixel_count=settings.image_sanitizer_max_pixel_count,
        spool_memory_bytes=settings.image_sanitizer_spool_memory_bytes,
    )
