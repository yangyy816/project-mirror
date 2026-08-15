from __future__ import annotations

import pytest

from mirror_api.errors import APIError
from mirror_api.security import UploadMetadata, validate_storage_key, validate_upload_metadata


@pytest.mark.parametrize("key", ["../secret", "/absolute", "users/x/../../secret", "A/upper"])
def test_unsafe_storage_keys_are_rejected(key: str) -> None:
    with pytest.raises(APIError):
        validate_storage_key(key)


def test_dangerous_mime_and_decompression_bomb_metadata_are_rejected() -> None:
    with pytest.raises(APIError) as mime_error:
        validate_upload_metadata(
            UploadMetadata(mime_type="image/svg+xml", byte_size=10, width=10, height=10)
        )
    assert mime_error.value.status_code == 415

    with pytest.raises(APIError) as pixel_error:
        validate_upload_metadata(
            UploadMetadata(mime_type="image/jpeg", byte_size=10, width=100_000, height=100_000)
        )
    assert pixel_error.value.code == "pixel_count_exceeded"
