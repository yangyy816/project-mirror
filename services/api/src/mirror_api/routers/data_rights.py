from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response, status

from mirror_api.account_deletion.service import (
    AccountDeletionFailure,
    AccountDeletionResult,
)
from mirror_api.asset_access.service import AssetAccessDenied, AssetAccessService
from mirror_api.asset_access.types import AssetView
from mirror_api.asset_access_dependencies import get_asset_access_service
from mirror_api.asset_deletion.coordinator import AssetDeletionCoordinator
from mirror_api.asset_deletion.service import AssetDeletionFailure, AssetDeletionResult
from mirror_api.asset_deletion_dependencies import get_asset_deletion_coordinator
from mirror_api.auth.types import AuthenticatedActor
from mirror_api.auth_dependencies import (
    clear_auth_cookies,
    get_account_deletion_status_actor,
    get_current_actor,
)
from mirror_api.config import Settings, get_settings
from mirror_api.data_export.service import (
    DataExportAccessDenied,
    DataExportFailure,
    DataExportResult,
)
from mirror_api.data_rights.coordinator import DataRightsCoordinator
from mirror_api.data_rights_dependencies import get_data_rights_coordinator
from mirror_api.errors import APIError, ErrorEnvelope
from mirror_api.schemas import (
    AccountDeletionResponse,
    AssetDeletionResponse,
    AssetListResponse,
    AssetResponse,
    DataExportResponse,
    PrivateDownloadGrantResponse,
)

router = APIRouter(prefix="/api/v1", tags=["user-data-rights"])

OpaqueId = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]
IdempotencyKey = Annotated[
    str,
    Header(min_length=8, max_length=128, alias="Idempotency-Key"),
]


def _asset(view: AssetView) -> AssetResponse:
    return AssetResponse(
        asset_id=view.id,
        asset_role=view.asset_role,
        mime_type=view.mime_type,
        byte_size=view.byte_size,
        width=view.width,
        height=view.height,
        created_at=view.created_at,
    )


def _asset_deletion(result: AssetDeletionResult) -> AssetDeletionResponse:
    return AssetDeletionResponse(
        deletion_request_id=result.request_id,
        job_id=result.job_id,
        status=result.status,
    )


def _data_export(result: DataExportResult) -> DataExportResponse:
    return DataExportResponse(
        export_id=result.export_id,
        job_id=result.job_id,
        status=result.status,
        schema_version=result.schema_version,
        requested_at=result.requested_at,
        ready_at=result.ready_at,
        expires_at=result.expires_at,
    )


def _account_deletion(result: AccountDeletionResult) -> AccountDeletionResponse:
    return AccountDeletionResponse(
        deletion_request_id=result.request_id,
        job_id=result.job_id,
        status=result.status,
        requested_at=result.requested_at,
        completed_at=result.completed_at,
    )


def _raise_asset_access_denied(failure: Exception) -> NoReturn:
    raise APIError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="asset_not_found",
        message="资产不存在或不可访问。",
    ) from failure


@router.get(
    "/assets",
    response_model=AssetListResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def list_assets(
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: AssetAccessService = Depends(get_asset_access_service),
) -> AssetListResponse:
    return AssetListResponse(
        assets=[_asset(item) for item in await service.list_assets(user_id=actor.user_id)]
    )


@router.get(
    "/assets/{asset_id}",
    response_model=AssetResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def get_asset(
    asset_id: OpaqueId,
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: AssetAccessService = Depends(get_asset_access_service),
) -> AssetResponse:
    try:
        return _asset(await service.get_asset(user_id=actor.user_id, asset_id=asset_id))
    except AssetAccessDenied as exc:
        _raise_asset_access_denied(exc)


@router.post(
    "/assets/{asset_id}/download-grants",
    status_code=status.HTTP_201_CREATED,
    response_model=PrivateDownloadGrantResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def create_asset_download_grant(
    asset_id: OpaqueId,
    request: Request,
    _idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    service: AssetAccessService = Depends(get_asset_access_service),
) -> PrivateDownloadGrantResponse:
    try:
        result = await service.create_download_grant(
            user_id=actor.user_id,
            asset_id=asset_id,
            request_id=str(request.state.request_id),
        )
    except AssetAccessDenied as exc:
        _raise_asset_access_denied(exc)
    return PrivateDownloadGrantResponse(
        method=result.grant.method,
        url=result.grant.url,
        required_headers=dict(result.grant.required_headers),
        expires_at=result.grant.expires_at,
    )


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AssetDeletionResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def delete_asset(
    asset_id: OpaqueId,
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    coordinator: AssetDeletionCoordinator = Depends(get_asset_deletion_coordinator),
) -> AssetDeletionResponse:
    try:
        result = await coordinator.create(
            user_id=actor.user_id,
            asset_id=asset_id,
            idempotency_key=idempotency_key,
            request_id=str(request.state.request_id),
        )
    except AssetDeletionFailure as exc:
        _raise_asset_access_denied(exc)
    return _asset_deletion(result)


@router.post(
    "/users/me/data-exports",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DataExportResponse,
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
)
async def create_data_export(
    request: Request,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    coordinator: DataRightsCoordinator = Depends(get_data_rights_coordinator),
) -> DataExportResponse:
    try:
        result = await coordinator.create_export(
            user_id=actor.user_id,
            idempotency_key=idempotency_key,
            request_id=str(request.state.request_id),
        )
    except DataExportFailure as exc:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="data_export_unavailable",
            message="当前账号不可创建数据导出。",
        ) from exc
    return _data_export(result)


@router.get(
    "/users/me/data-exports/{export_id}",
    response_model=DataExportResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def get_data_export(
    export_id: OpaqueId,
    actor: AuthenticatedActor = Depends(get_current_actor),
    coordinator: DataRightsCoordinator = Depends(get_data_rights_coordinator),
) -> DataExportResponse:
    try:
        return _data_export(
            await coordinator.exports.get_export(user_id=actor.user_id, export_id=export_id)
        )
    except DataExportAccessDenied as exc:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="data_export_not_found",
            message="数据导出不存在或不可访问。",
        ) from exc


@router.post(
    "/users/me/data-exports/{export_id}/download-grants",
    status_code=status.HTTP_201_CREATED,
    response_model=PrivateDownloadGrantResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def create_data_export_download_grant(
    export_id: OpaqueId,
    _idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    coordinator: DataRightsCoordinator = Depends(get_data_rights_coordinator),
) -> PrivateDownloadGrantResponse:
    try:
        grant = await coordinator.exports.create_download_grant(
            user_id=actor.user_id, export_id=export_id
        )
    except DataExportAccessDenied as exc:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="data_export_not_found",
            message="数据导出不存在或不可访问。",
        ) from exc
    return PrivateDownloadGrantResponse(
        method=grant.method,
        url=grant.url,
        required_headers=dict(grant.required_headers),
        expires_at=grant.expires_at,
    )


@router.post(
    "/users/me/deletion-requests",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AccountDeletionResponse,
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
)
async def create_account_deletion(
    request: Request,
    response: Response,
    idempotency_key: IdempotencyKey,
    actor: AuthenticatedActor = Depends(get_current_actor),
    coordinator: DataRightsCoordinator = Depends(get_data_rights_coordinator),
    settings: Settings = Depends(get_settings),
) -> AccountDeletionResponse:
    try:
        result = await coordinator.create_account_deletion(
            user_id=actor.user_id,
            idempotency_key=idempotency_key,
            request_id=str(request.state.request_id),
        )
    except AccountDeletionFailure as exc:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="account_deletion_unavailable",
            message="当前账号不可提交删除请求。",
        ) from exc
    clear_auth_cookies(response, settings)
    return _account_deletion(result)


@router.get(
    "/users/me/deletion-requests/current",
    response_model=AccountDeletionResponse,
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def get_current_account_deletion(
    actor: AuthenticatedActor = Depends(get_account_deletion_status_actor),
    coordinator: DataRightsCoordinator = Depends(get_data_rights_coordinator),
) -> AccountDeletionResponse:
    try:
        return _account_deletion(await coordinator.account_deletions.current(user_id=actor.user_id))
    except AccountDeletionFailure as exc:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="account_deletion_not_found",
            message="账号删除请求不存在。",
        ) from exc
