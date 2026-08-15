from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Request, Response, status

from mirror_api.auth.types import AuthenticatedActor
from mirror_api.auth_dependencies import get_current_actor
from mirror_api.errors import APIError, ErrorEnvelope
from mirror_api.schemas import (
    PrivateUploadGrantResponse,
    PurposeConsentGrantResponse,
    PurposeConsentRequirementResponse,
    PurposeConsentStateResponse,
    PurposeConsentWithdrawalResponse,
    UploadIntentCreateRequest,
    UploadIntentCreationResponse,
    UploadIntentResponse,
)
from mirror_api.upload_control import (
    ConsentFailure,
    ConsentRequirement,
    ConsentService,
    ConsentState,
    UploadDeclaration,
    UploadIntentFailure,
    UploadIntentService,
    UploadIntentView,
)
from mirror_api.upload_control_dependencies import (
    get_consent_service,
    get_upload_intent_service,
)

router = APIRouter(prefix="/api/v1", tags=["private-upload-control"])

IdempotencyKey = Annotated[
    str,
    Header(min_length=8, max_length=128, alias="Idempotency-Key"),
]


def _request_id(request: Request) -> str:
    return str(request.state.request_id)


def _raise_consent_failure(failure: ConsentFailure) -> NoReturn:
    if failure.code == "idempotency_conflict":
        raise APIError(
            status_code=409, code=failure.code, message="用途授权请求冲突。"
        ) from failure
    if failure.code == "active_user_required":
        raise APIError(
            status_code=403,
            code=failure.code,
            message="当前账号尚不可授予该用途授权。",
        ) from failure
    raise APIError(
        status_code=404,
        code=failure.code,
        message="用途授权不存在或不可操作。",
    ) from failure


def _raise_upload_failure(failure: UploadIntentFailure) -> NoReturn:
    mapping = {
        "idempotency_conflict": (409, "上传请求与已有幂等请求冲突。"),
        "purpose_consent_required": (403, "当前用途授权无效。"),
        "upload_intent_throttled": (429, "上传请求过于频繁。"),
        "upload_intent_quota_exceeded": (429, "待处理上传数量已达上限。"),
        "upload_byte_quota_exceeded": (429, "待处理上传容量已达上限。"),
        "upload_intent_expired": (410, "上传意图已过期。"),
        "upload_intent_cancelled": (409, "上传意图已取消。"),
        "upload_object_missing": (409, "隔离上传对象尚不存在。"),
        "upload_metadata_mismatch": (409, "上传对象与声明不一致。"),
        "invalid_storage_grant": (503, "暂时无法创建安全上传凭证。"),
        "quarantine_cleanup_failed": (503, "隔离对象清理尚未完成。"),
    }
    status_code, message = mapping.get(
        failure.code,
        (404, "上传意图不存在或不可操作。"),
    )
    raise APIError(status_code=status_code, code=failure.code, message=message) from failure


def _requirement(requirement: ConsentRequirement) -> PurposeConsentRequirementResponse:
    return PurposeConsentRequirementResponse.model_validate(
        {
            "consent_type": requirement.consent_type,
            "purpose_code": requirement.purpose_code,
            "purpose_version": requirement.purpose_version,
            "policy_code": requirement.policy_code,
            "policy_version": requirement.policy_version,
            "policy_digest": requirement.policy_digest,
            "operations": list(requirement.operations),
        }
    )


def _consent_state(state: ConsentState) -> PurposeConsentStateResponse:
    return PurposeConsentStateResponse(
        status=state.status,
        requirement=_requirement(state.requirement),
        grant_id=state.grant_id,
        granted_at=state.granted_at,
        expires_at=state.expires_at,
        missing_reason=state.missing_reason,
    )


def _intent(view: UploadIntentView) -> UploadIntentResponse:
    return UploadIntentResponse.model_validate(
        {
            "intent_id": view.intent_id,
            "status": view.status,
            "content_type": view.declaration.content_type,
            "byte_size": view.declaration.byte_size,
            "sha256": view.declaration.sha256,
            "grant_expires_at": view.grant_expires_at,
            "uploaded_at": view.uploaded_at,
            "cancelled_at": view.cancelled_at,
            "expired_at": view.expired_at,
        }
    )


@router.get(
    "/users/me/consents",
    response_model=PurposeConsentStateResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def get_current_consent(
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: ConsentService = Depends(get_consent_service),
) -> PurposeConsentStateResponse:
    return _consent_state(await service.current_state(user_id=actor.user_id))


@router.post(
    "/users/me/consents",
    status_code=status.HTTP_201_CREATED,
    response_model=PurposeConsentGrantResponse,
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
)
async def grant_current_consent(
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: ConsentService = Depends(get_consent_service),
) -> PurposeConsentGrantResponse:
    try:
        result = await service.grant(
            user_id=actor.user_id,
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
    except ConsentFailure as exc:
        _raise_consent_failure(exc)
    return PurposeConsentGrantResponse(
        grant_id=result.grant_id,
        granted_at=result.granted_at,
        expires_at=result.expires_at,
    )


@router.post(
    "/users/me/consents/{grant_id}/withdrawals",
    status_code=status.HTTP_201_CREATED,
    response_model=PurposeConsentWithdrawalResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def withdraw_current_consent(
    grant_id: str,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: ConsentService = Depends(get_consent_service),
) -> PurposeConsentWithdrawalResponse:
    try:
        result = await service.withdraw(
            user_id=actor.user_id,
            grant_id=grant_id,
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
    except ConsentFailure as exc:
        _raise_consent_failure(exc)
    return PurposeConsentWithdrawalResponse(
        withdrawal_id=result.withdrawal_id,
        grant_id=result.grant_id,
        withdrawn_at=result.withdrawn_at,
    )


@router.post(
    "/assets/upload-intents",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadIntentCreationResponse,
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
)
async def create_upload_intent(
    payload: UploadIntentCreateRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: UploadIntentService = Depends(get_upload_intent_service),
) -> UploadIntentCreationResponse:
    try:
        result = await service.create(
            user_id=actor.user_id,
            declaration=UploadDeclaration(
                content_type=payload.content_type,
                byte_size=payload.byte_size,
                sha256=payload.sha256,
            ),
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
    except UploadIntentFailure as exc:
        _raise_upload_failure(exc)
    upload = None
    if result.grant is not None:
        upload = PrivateUploadGrantResponse(
            method=result.grant.method,
            url=result.grant.url,
            required_headers=dict(result.grant.required_headers),
            expires_at=result.grant.expires_at,
        )
    return UploadIntentCreationResponse(intent=_intent(result.intent), upload=upload)


@router.get(
    "/assets/upload-intents/{intent_id}",
    response_model=UploadIntentResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def get_upload_intent(
    intent_id: str,
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: UploadIntentService = Depends(get_upload_intent_service),
) -> UploadIntentResponse:
    try:
        return _intent(await service.get(user_id=actor.user_id, intent_id=intent_id))
    except UploadIntentFailure as exc:
        _raise_upload_failure(exc)


@router.post(
    "/assets/upload-intents/{intent_id}/complete",
    response_model=UploadIntentResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def complete_upload_intent(
    intent_id: str,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: UploadIntentService = Depends(get_upload_intent_service),
) -> UploadIntentResponse:
    try:
        result = await service.complete(
            user_id=actor.user_id,
            intent_id=intent_id,
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
    except UploadIntentFailure as exc:
        _raise_upload_failure(exc)
    return _intent(result.intent)


@router.delete(
    "/assets/upload-intents/{intent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def cancel_upload_intent(
    intent_id: str,
    request: Request,
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: UploadIntentService = Depends(get_upload_intent_service),
) -> Response:
    try:
        await service.cancel(
            user_id=actor.user_id,
            intent_id=intent_id,
            request_id=_request_id(request),
        )
    except UploadIntentFailure as exc:
        _raise_upload_failure(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
