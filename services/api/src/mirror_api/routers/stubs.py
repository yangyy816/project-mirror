from __future__ import annotations

from fastapi import APIRouter, Depends, Header, status

from mirror_api.errors import APIError, ErrorEnvelope
from mirror_api.schemas import PlaceholderRequest

router = APIRouter(prefix="/api/v1", tags=["phase-boundaries"])


def require_authenticated_actor() -> str:
    raise APIError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="authentication_required",
        message="该能力需要完成认证，认证尚未进入当前 Phase。",
        details={"phase": "phase-0-foundation"},
    )


def not_implemented(capability: str) -> None:
    raise APIError(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        code="capability_not_implemented",
        message=f"{capability} 尚未进入当前 Phase 的实现范围。",
        details={"phase": "phase-0-foundation", "capability": capability},
    )


async def _create_stub(
    capability: str,
    payload: PlaceholderRequest,
    idempotency_key: str,
) -> None:
    del payload, idempotency_key
    not_implemented(capability)


@router.post("/assets", responses={501: {"model": ErrorEnvelope}})
async def create_asset(
    payload: PlaceholderRequest,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    actor_id: str = Depends(require_authenticated_actor),
) -> None:
    del actor_id
    await _create_stub("secure_asset_upload", payload, idempotency_key)


@router.post("/questionnaires/runs", responses={501: {"model": ErrorEnvelope}})
async def create_questionnaire_run(
    payload: PlaceholderRequest,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    actor_id: str = Depends(require_authenticated_actor),
) -> None:
    del actor_id
    await _create_stub("adaptive_questionnaire", payload, idempotency_key)


@router.post("/profiles", responses={501: {"model": ErrorEnvelope}})
async def create_profile(
    payload: PlaceholderRequest,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    actor_id: str = Depends(require_authenticated_actor),
) -> None:
    del actor_id
    await _create_stub("aesthetic_profile", payload, idempotency_key)


@router.post("/editing-sessions", responses={501: {"model": ErrorEnvelope}})
async def create_editing_session(
    payload: PlaceholderRequest,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    actor_id: str = Depends(require_authenticated_actor),
) -> None:
    del actor_id
    await _create_stub("non_destructive_editing", payload, idempotency_key)


@router.post("/billing/checkout", responses={501: {"model": ErrorEnvelope}})
async def create_checkout(
    payload: PlaceholderRequest,
    idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"),
    actor_id: str = Depends(require_authenticated_actor),
) -> None:
    del actor_id
    await _create_stub("real_payment", payload, idempotency_key)
