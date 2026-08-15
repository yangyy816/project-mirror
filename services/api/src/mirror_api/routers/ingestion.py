from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, status

from mirror_api.auth.types import AuthenticatedActor
from mirror_api.auth_dependencies import get_current_actor
from mirror_api.errors import APIError, ErrorEnvelope
from mirror_api.ingestion.coordinator import IngestionCoordinator
from mirror_api.ingestion.types import IngestionFailure, IngestionJobView
from mirror_api.ingestion_dependencies import get_ingestion_coordinator
from mirror_api.schemas import IngestionJobResponse

router = APIRouter(prefix="/api/v1", tags=["safe-image-ingestion"])

OpaqueId = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]
IdempotencyKey = Annotated[
    str,
    Header(min_length=8, max_length=128, alias="Idempotency-Key"),
]


def _raise_ingestion_failure(failure: IngestionFailure) -> NoReturn:
    mapping = {
        "idempotency_conflict": (status.HTTP_409_CONFLICT, "摄入请求与已有幂等请求冲突。"),
        "upload_intent_not_ready": (status.HTTP_409_CONFLICT, "上传对象尚不可进入安全摄入。"),
        "quarantine_retention_expired": (status.HTTP_410_GONE, "隔离对象保留期限已结束。"),
        "authorization_revoked": (status.HTTP_403_FORBIDDEN, "当前用途授权无效。"),
    }
    status_code, message = mapping.get(
        failure.code,
        (status.HTTP_404_NOT_FOUND, "摄入任务不存在或不可操作。"),
    )
    raise APIError(status_code=status_code, code=failure.code, message=message) from failure


def _response(view: IngestionJobView) -> IngestionJobResponse:
    return IngestionJobResponse(
        job_id=view.job_id,
        status=view.status,
        result_code=view.result_code,
        asset_id=view.asset_id,
        finalized_at=view.finalized_at,
    )


@router.post(
    "/assets/upload-intents/{intent_id}/ingestion-jobs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestionJobResponse,
    responses={
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
        410: {"model": ErrorEnvelope},
    },
)
async def create_ingestion_job(
    intent_id: OpaqueId,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    coordinator: IngestionCoordinator = Depends(get_ingestion_coordinator),
) -> IngestionJobResponse:
    try:
        result = await coordinator.create(
            user_id=actor.user_id,
            intent_id=intent_id,
            idempotency_key=idempotency_key,
            request_id=str(request.state.request_id),
        )
    except IngestionFailure as exc:
        _raise_ingestion_failure(exc)
    return _response(result.job)


@router.get(
    "/jobs/{job_id}",
    response_model=IngestionJobResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def get_ingestion_job(
    job_id: OpaqueId,
    actor: AuthenticatedActor = Depends(get_current_actor),
    coordinator: IngestionCoordinator = Depends(get_ingestion_coordinator),
) -> IngestionJobResponse:
    try:
        return _response(await coordinator.get(user_id=actor.user_id, job_id=job_id))
    except IngestionFailure as exc:
        _raise_ingestion_failure(exc)
