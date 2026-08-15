from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request

from mirror_api.auth_dependencies import AuthInfrastructure
from mirror_api.config import Settings
from mirror_api.providers.base import ObjectStorageProvider
from mirror_api.upload_control import ConsentRequirement, ConsentService, UploadIntentService


@dataclass(frozen=True)
class UploadControlInfrastructure:
    requirement: ConsentRequirement
    consent_service: ConsentService
    upload_intent_service: UploadIntentService


def create_upload_control_infrastructure(
    settings: Settings,
    auth: AuthInfrastructure,
    storage: ObjectStorageProvider,
) -> UploadControlInfrastructure:
    configured = settings.facial_data_purpose
    requirement = ConsentRequirement(
        consent_type=configured.consent_type,
        purpose_code=configured.purpose_code,
        purpose_version=configured.purpose_version,
        policy_code=configured.policy_code,
        policy_version=configured.policy_version,
        policy_digest=configured.policy_digest,
        operations=configured.operations,
    )
    return UploadControlInfrastructure(
        requirement=requirement,
        consent_service=ConsentService(
            session_factory=auth.sessions,
            requirement=requirement,
            hmac_keyring=settings.auth_hmac_keyring,
            hmac_active_kid=settings.auth_hmac_active_kid,
        ),
        upload_intent_service=UploadIntentService(
            session_factory=auth.sessions,
            storage=storage,
            rate_limiter=auth.rate_limiter,
            requirement=requirement,
            hmac_keyring=settings.auth_hmac_keyring,
            hmac_active_kid=settings.auth_hmac_active_kid,
            rate_limit=settings.upload_rate_limit_user_limit,
            rate_window_seconds=settings.upload_rate_limit_window_seconds,
            max_active_intents=settings.upload_max_active_intents,
            max_pending_bytes=settings.upload_max_pending_bytes,
            quarantine_retention_seconds=settings.upload_quarantine_retention_seconds,
        ),
    )


def get_consent_service(request: Request) -> ConsentService:
    return cast(
        ConsentService,
        request.app.state.upload_control_infrastructure.consent_service,
    )


def get_upload_intent_service(request: Request) -> UploadIntentService:
    return cast(
        UploadIntentService,
        request.app.state.upload_control_infrastructure.upload_intent_service,
    )
