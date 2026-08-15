from __future__ import annotations

from fastapi import Request

from mirror_api.config import Settings
from mirror_api.errors import APIError
from mirror_api.providers.base import ObjectStorageProvider
from mirror_api.providers.local import LocalObjectStorageProvider
from mirror_api.providers.tencent import TencentCosProvider


def create_object_storage_provider(settings: Settings) -> ObjectStorageProvider:
    if settings.storage_provider == "local":
        return LocalObjectStorageProvider(
            root=settings.local_storage_root,
            base_url=settings.local_upload_base_url,
            ttl_seconds=settings.signed_url_ttl_seconds,
        )
    return TencentCosProvider()


def get_local_object_storage_provider(request: Request) -> LocalObjectStorageProvider:
    provider = request.app.state.object_storage_provider
    if not isinstance(provider, LocalObjectStorageProvider):
        raise APIError(
            status_code=404,
            code="local_upload_unavailable",
            message="本地上传入口不可用。",
        )
    return provider
