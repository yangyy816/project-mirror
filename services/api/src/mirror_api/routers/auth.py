from __future__ import annotations

from typing import Annotated, Literal, NoReturn, cast

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse

from mirror_api.auth import AuthFailure, AuthService
from mirror_api.auth.types import AuthenticatedActor
from mirror_api.auth_dependencies import (
    clear_auth_cookies,
    get_auth_service,
    get_current_actor,
    require_logout_csrf,
    require_refresh_request,
    set_refresh_cookies,
)
from mirror_api.config import Settings, get_settings
from mirror_api.errors import APIError, ErrorEnvelope
from mirror_api.schemas import (
    AccessTokenResponse,
    AgeAssuranceRequest,
    AgeAssuranceResponse,
    CurrentUserResponse,
    PolicyAcceptanceRequest,
    PolicyAcceptanceResponse,
    SessionRequest,
    SmsChallengeRequest,
    SmsChallengeResponse,
)

router = APIRouter(prefix="/api/v1", tags=["authentication"])

IdempotencyKey = Annotated[
    str,
    Header(min_length=8, max_length=128, alias="Idempotency-Key"),
]


def _request_id(request: Request) -> str:
    return str(request.state.request_id)


def _raise_auth_failure(failure: AuthFailure) -> NoReturn:
    if failure.code == "idempotency_conflict":
        raise APIError(status_code=409, code=failure.code, message="认证请求冲突。") from failure
    if failure.code == "authentication_throttled":
        raise APIError(
            status_code=429, code=failure.code, message="认证请求过于频繁。"
        ) from failure
    raise APIError(
        code=failure.code, message="认证凭据无效或已失效。", status_code=401
    ) from failure


def _access_response(access_token: str, scope: str) -> AccessTokenResponse:
    return AccessTokenResponse(access_token=access_token, scope=cast_scope(scope))


def cast_scope(scope: str) -> Literal["pending", "active"]:
    if scope not in {"pending", "active"}:
        raise ValueError("unexpected authentication scope")
    return cast(Literal["pending", "active"], scope)


@router.post(
    "/auth/sms-challenges",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SmsChallengeResponse,
    responses={
        401: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
        429: {"model": ErrorEnvelope},
    },
)
async def create_sms_challenge(
    payload: SmsChallengeRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    auth_service: AuthService = Depends(get_auth_service),
) -> SmsChallengeResponse:
    try:
        challenge = await auth_service.request_challenge(
            phone=payload.phone.get_secret_value(),
            invite_code=(
                payload.invite_code.get_secret_value() if payload.invite_code is not None else None
            ),
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
            ip_key=request.client.host if request.client is not None else "unknown",
            device_key=request.headers.get("X-Device-ID", "unknown"),
        )
    except AuthFailure as exc:
        _raise_auth_failure(exc)
    return SmsChallengeResponse(
        challenge_id=challenge.challenge_id, expires_at=challenge.expires_at
    )


@router.post(
    "/auth/sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=AccessTokenResponse,
    responses={401: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}},
)
async def create_session(
    payload: SessionRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    try:
        result = await auth_service.create_session(
            challenge_id=payload.challenge_id,
            otp=payload.otp.get_secret_value(),
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
    except AuthFailure as exc:
        _raise_auth_failure(exc)
    response = JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=_access_response(result.access_token, result.scope).model_dump(mode="json"),
    )
    set_refresh_cookies(response, result, settings)
    return response


@router.post(
    "/auth/token/refresh",
    response_model=AccessTokenResponse,
    responses={401: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}},
)
async def refresh_session(
    request: Request,
    idempotency_key: IdempotencyKey,
    refresh_token: str = Depends(require_refresh_request),
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> JSONResponse:
    try:
        result = await auth_service.refresh_session(
            refresh_token=refresh_token,
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
    except AuthFailure as exc:
        _raise_auth_failure(exc)
    response = JSONResponse(
        content=_access_response(result.access_token, result.scope).model_dump()
    )
    set_refresh_cookies(response, result, settings)
    return response


@router.delete(
    "/auth/sessions/current",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={401: {"model": ErrorEnvelope}},
)
async def logout_current_session(
    request: Request,
    _: None = Depends(require_logout_csrf),
    settings: Settings = Depends(get_settings),
    actor: AuthenticatedActor = Depends(get_current_actor),
    auth_service: AuthService = Depends(get_auth_service),
) -> Response:
    try:
        await auth_service.logout_family(
            session_id=actor.session_id, request_id=_request_id(request)
        )
    except AuthFailure as exc:
        _raise_auth_failure(exc)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings)
    return response


@router.get(
    "/users/me", response_model=CurrentUserResponse, responses={401: {"model": ErrorEnvelope}}
)
async def get_current_user(
    actor: AuthenticatedActor = Depends(get_current_actor),
    auth_service: AuthService = Depends(get_auth_service),
) -> CurrentUserResponse:
    try:
        requirements = await auth_service.onboarding_requirements(user_id=actor.user_id)
    except AuthFailure as exc:
        _raise_auth_failure(exc)
    return CurrentUserResponse(
        user_id=actor.user_id,
        status=cast_scope(actor.status),
        scope=cast_scope(actor.scope),
        onboarding_requirements=cast(
            list[Literal["age_assurance", "policy_acceptance"]], list(requirements)
        ),
    )


@router.post(
    "/users/me/age-assurances",
    status_code=status.HTTP_201_CREATED,
    response_model=AgeAssuranceResponse,
    responses={401: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}},
)
async def create_age_assurance(
    payload: AgeAssuranceRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    auth_service: AuthService = Depends(get_auth_service),
) -> AgeAssuranceResponse:
    try:
        outcome = await auth_service.record_age_assurance(
            user_id=actor.user_id,
            credential=payload.credential.get_secret_value(),
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
    except AuthFailure as exc:
        _raise_auth_failure(exc)
    return AgeAssuranceResponse(
        record_id=outcome.record_id,
        result=cast(Literal["verified", "not_verified", "indeterminate"], outcome.result),
        activated=outcome.activated,
    )


@router.post(
    "/users/me/policy-acceptances",
    status_code=status.HTTP_201_CREATED,
    response_model=PolicyAcceptanceResponse,
    responses={401: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}},
)
async def accept_policy(
    payload: PolicyAcceptanceRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    auth_service: AuthService = Depends(get_auth_service),
) -> PolicyAcceptanceResponse:
    try:
        requirement = auth_service.required_policy(
            code=payload.document_code,
            version=payload.document_version,
            digest=payload.document_digest,
        )
        activated = await auth_service.accept_policy(
            user_id=actor.user_id,
            requirement=requirement,
            source="web",
            idempotency_key=idempotency_key,
            request_id=_request_id(request),
        )
    except AuthFailure as exc:
        _raise_auth_failure(exc)
    return PolicyAcceptanceResponse(activated=activated)
