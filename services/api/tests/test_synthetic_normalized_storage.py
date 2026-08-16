from __future__ import annotations

from asyncio import gather
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from mirror_api.image_sanitizer import DEFAULT_IMAGE_SANITIZER_CONFIG, sanitize_image
from mirror_api.providers.base import (
    SyntheticNormalizedImage,
    SyntheticNormalizedStorageWriteRequest,
    SyntheticStorageConflictError,
    SyntheticStorageOperationError,
)
from mirror_api.providers.synthetic_normalized_local import (
    LocalSyntheticNormalizedStorageProvider,
)
from mirror_api.storage_keys import (
    internal_synthetic_normalized_object_key,
    synthetic_normalized_storage_reference,
)
from mirror_api.synthetic_dataset.normalization_types import normalizer_config_digest


def _canonical(color: tuple[int, int, int], tmp_path: Path) -> SyntheticNormalizedImage:
    image = Image.new("RGB", (64, 64), color)
    output = BytesIO()
    try:
        image.save(output, format="PNG")
    finally:
        image.close()
    sanitized = sanitize_image(
        output.getvalue(), declared_mime_type="image/png", spool_root=tmp_path / "spool"
    )
    return SyntheticNormalizedImage(
        content=sanitized.bytes_value,
        sha256=sanitized.sha256,
        byte_size=sanitized.byte_size,
        width=sanitized.width,
        height=sanitized.height,
    )


def _request(
    reference: str, image: SyntheticNormalizedImage
) -> SyntheticNormalizedStorageWriteRequest:
    return SyntheticNormalizedStorageWriteRequest(
        storage_reference=reference,
        image=image,
        normalizer_version="image-sanitizer-v1",
        normalizer_config_digest=normalizer_config_digest(DEFAULT_IMAGE_SANITIZER_CONFIG),
    )


def test_normalizer_config_and_storage_reference_are_platform_stable() -> None:
    digest = normalizer_config_digest(DEFAULT_IMAGE_SANITIZER_CONFIG)
    assert digest == "5ebe5ea3e9b0e5c8ad86b93166e38f11da7bdcd76a7a2801aadd0f30e32f81de"
    reference = synthetic_normalized_storage_reference("1" * 32, digest)
    assert reference == "normalized-6320826878b666f51d991fa33c20e834b3f3c00aab2425a1f4124"
    assert internal_synthetic_normalized_object_key(reference) == (
        "internal-synthetic/v1/normalized/"
        "7f9b3833b3aa4bdb9a982b0fa937321e1924166834367368e9dc21696bf3a817"
    )


@pytest.mark.asyncio
async def test_local_normalized_storage_is_immutable_private_and_repeatable(
    tmp_path: Path,
) -> None:
    provider = LocalSyntheticNormalizedStorageProvider(root=tmp_path)
    digest = normalizer_config_digest(DEFAULT_IMAGE_SANITIZER_CONFIG)
    reference = synthetic_normalized_storage_reference("2" * 32, digest)
    request = _request(reference, _canonical((20, 40, 60), tmp_path))
    first, second = await gather(
        provider.store_normalized_image_if_absent(request=request),
        provider.store_normalized_image_if_absent(request=request),
    )
    assert first == second
    assert first.storage_key == internal_synthetic_normalized_object_key(reference)
    assert first.storage_key.startswith("internal-synthetic/v1/normalized/")
    payload = b"".join(
        [chunk async for chunk in provider.stream_normalized_image(storage_reference=reference)]
    )
    assert sha256(payload).hexdigest() == first.sha256
    assert await provider.inspect_normalized_image(storage_reference=reference) == first

    conflicting = _request(reference, _canonical((60, 40, 20), tmp_path))
    with pytest.raises(SyntheticStorageConflictError, match="synthetic storage conflict"):
        await provider.store_normalized_image_if_absent(request=conflicting)
    assert list(tmp_path.rglob(".part-*")) == []


@pytest.mark.asyncio
async def test_local_normalized_storage_detects_payload_and_metadata_tamper(
    tmp_path: Path,
) -> None:
    provider = LocalSyntheticNormalizedStorageProvider(root=tmp_path)
    digest = normalizer_config_digest(DEFAULT_IMAGE_SANITIZER_CONFIG)
    reference = synthetic_normalized_storage_reference("3" * 32, digest)
    await provider.store_normalized_image_if_absent(
        request=_request(reference, _canonical((10, 20, 30), tmp_path))
    )
    target = tmp_path / Path(internal_synthetic_normalized_object_key(reference))
    payload = target / "payload"
    payload.write_bytes(payload.read_bytes() + b"tampered")
    with pytest.raises(SyntheticStorageOperationError) as integrity:
        await provider.inspect_normalized_image(storage_reference=reference)
    assert integrity.value.reason == "synthetic_integrity_mismatch"

    second_reference = synthetic_normalized_storage_reference("4" * 32, digest)
    await provider.store_normalized_image_if_absent(
        request=_request(second_reference, _canonical((30, 20, 10), tmp_path))
    )
    second_target = tmp_path / Path(internal_synthetic_normalized_object_key(second_reference))
    (second_target / "metadata.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SyntheticStorageOperationError) as metadata:
        await provider.inspect_normalized_image(storage_reference=second_reference)
    assert metadata.value.reason == "synthetic_metadata_invalid"
