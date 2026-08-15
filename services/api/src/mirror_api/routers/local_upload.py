from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from starlette.responses import StreamingResponse

from mirror_api.asset_access.service import AssetAccessDenied, AssetAccessService
from mirror_api.asset_access_dependencies import get_asset_access_service
from mirror_api.data_export.service import DataExportAccessDenied
from mirror_api.data_rights.coordinator import DataRightsCoordinator
from mirror_api.data_rights_dependencies import get_data_rights_coordinator
from mirror_api.errors import APIError
from mirror_api.providers.local import (
    DOWNLOAD_AUTHORIZATION_HEADER,
    UPLOAD_AUTHORIZATION_HEADER,
    UPLOAD_CHECKSUM_HEADER,
    LocalObjectStorageProvider,
    LocalStorageOperationError,
)
from mirror_api.storage_dependencies import get_local_object_storage_provider

router = APIRouter(include_in_schema=False)


@router.get("/_local/private-export-download/{grant_id}")
async def receive_local_private_export_download(
    grant_id: str,
    request: Request,
    coordinator: DataRightsCoordinator = Depends(get_data_rights_coordinator),
) -> StreamingResponse:
    try:
        redemption = await coordinator.exports.redeem_local_download(
            grant_id=grant_id,
            authorization=request.headers.get(DOWNLOAD_AUTHORIZATION_HEADER, ""),
        )
    except DataExportAccessDenied as exc:
        raise APIError(
            status_code=404,
            code="download_grant_not_found",
            message="下载凭证不存在。",
        ) from exc
    except LocalStorageOperationError as exc:
        raise _public_download_error(exc.reason) from exc
    return StreamingResponse(
        redemption.body,
        media_type=redemption.content_type,
        headers={
            "Content-Length": str(redemption.content_length),
            "Cache-Control": "private, no-store",
            "Content-Disposition": 'attachment; filename="project-mirror-data-export.zip"',
        },
    )


@router.get("/_local/private-download/{grant_id}")
async def receive_local_private_download(
    grant_id: str,
    request: Request,
    service: AssetAccessService = Depends(get_asset_access_service),
) -> StreamingResponse:
    try:
        redemption = await service.redeem_local_download(
            grant_id=grant_id,
            authorization=request.headers.get(DOWNLOAD_AUTHORIZATION_HEADER, ""),
            request_id=request.state.request_id,
        )
    except AssetAccessDenied as exc:
        raise APIError(
            status_code=404,
            code="download_grant_not_found",
            message="下载凭证不存在。",
        ) from exc
    except LocalStorageOperationError as exc:
        raise _public_download_error(exc.reason) from exc
    return StreamingResponse(
        redemption.body,
        media_type=redemption.content_type,
        headers={
            "Content-Length": str(redemption.content_length),
            "Cache-Control": "private, no-store",
            "Content-Disposition": 'attachment; filename="mirror-asset.jpg"',
        },
    )


@router.put("/_local/private-upload/{grant_id}", status_code=204)
async def receive_local_private_upload(
    grant_id: str,
    request: Request,
    storage: LocalObjectStorageProvider = Depends(get_local_object_storage_provider),
) -> Response:
    content_type = request.headers.get("content-type", "")
    checksum = request.headers.get(UPLOAD_CHECKSUM_HEADER, "")
    authorization = request.headers.get(UPLOAD_AUTHORIZATION_HEADER, "")
    try:
        content_length = int(request.headers.get("content-length", ""))
    except ValueError as exc:
        raise APIError(
            status_code=400,
            code="invalid_upload_headers",
            message="上传请求头无效。",
        ) from exc
    try:
        await storage.receive_private_upload(
            grant_id=grant_id,
            authorization=authorization,
            content_type=content_type,
            content_length=content_length,
            checksum_sha256=checksum,
            body=request.stream(),
        )
    except LocalStorageOperationError as exc:
        raise _public_upload_error(exc.reason) from exc
    return Response(status_code=204)


def _public_upload_error(reason: str) -> APIError:
    if reason == "grant_expired":
        return APIError(status_code=410, code="upload_grant_expired", message="上传凭证已过期。")
    if reason in {"grant_replayed", "object_already_exists"}:
        return APIError(status_code=409, code="upload_grant_consumed", message="上传凭证已使用。")
    if reason == "body_too_large":
        return APIError(
            status_code=413, code="upload_body_too_large", message="上传内容超过声明范围。"
        )
    if reason == "content_type_mismatch":
        return APIError(
            status_code=415, code="upload_type_mismatch", message="上传类型与声明不一致。"
        )
    if reason in {"unknown_grant", "invalid_authorization"}:
        return APIError(status_code=404, code="upload_grant_not_found", message="上传凭证不存在。")
    return APIError(
        status_code=400, code="upload_integrity_mismatch", message="上传内容与声明不一致。"
    )


def _public_download_error(reason: str) -> APIError:
    if reason == "download_grant_expired":
        return APIError(status_code=410, code="download_grant_expired", message="下载凭证已过期。")
    if reason == "download_grant_replayed":
        return APIError(status_code=409, code="download_grant_consumed", message="下载凭证已使用。")
    return APIError(status_code=404, code="download_grant_not_found", message="下载凭证不存在。")
