from __future__ import annotations

import re
from dataclasses import dataclass

from mirror_api.errors import APIError

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PIXEL_COUNT = 40_000_000
SAFE_STORAGE_KEY = re.compile(r"^[a-z0-9][a-z0-9/_-]{0,254}$")


@dataclass(frozen=True)
class UploadMetadata:
    mime_type: str
    byte_size: int
    width: int
    height: int


def validate_storage_key(key: str) -> str:
    if not SAFE_STORAGE_KEY.fullmatch(key) or ".." in key or key.startswith("/"):
        raise APIError(
            status_code=400,
            code="unsafe_storage_key",
            message="存储对象路径不合法。",
        )
    return key


def validate_upload_metadata(metadata: UploadMetadata) -> UploadMetadata:
    if metadata.mime_type not in ALLOWED_MIME_TYPES:
        raise APIError(status_code=415, code="unsupported_image_type", message="不支持该图片类型。")
    if metadata.byte_size <= 0 or metadata.byte_size > MAX_UPLOAD_BYTES:
        raise APIError(status_code=413, code="image_too_large", message="图片文件大小超限。")
    if metadata.width <= 0 or metadata.height <= 0:
        raise APIError(status_code=400, code="invalid_dimensions", message="图片尺寸无效。")
    if metadata.width * metadata.height > MAX_PIXEL_COUNT:
        raise APIError(status_code=413, code="pixel_count_exceeded", message="图片像素总量超限。")
    return metadata
