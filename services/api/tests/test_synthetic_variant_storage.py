from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mirror_api.providers.base import SyntheticStorageConflictError
from mirror_api.providers.synthetic_variant_local import LocalSyntheticVariantStorageProvider
from mirror_api.storage_keys import synthetic_variant_storage_reference
from mirror_api.synthetic_dataset.geometry_transform import GeometryTransformResult
from mirror_api.synthetic_dataset.variant_storage import VariantStorageWriteRequest


def _result(content: bytes = b"canonical-jpeg-fixture") -> GeometryTransformResult:
    return GeometryTransformResult(
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        width=16,
        height=16,
        changed_pixel_count=4,
        runtime_version="opencv-5-0-0-mirror-v1",
        runtime_manifest_digest="7" * 64,
        warp_plan_digest="8" * 64,
    )


def _request(content: bytes = b"canonical-jpeg-fixture") -> VariantStorageWriteRequest:
    run_id = "a" * 32
    specification_digest = "b" * 64
    return VariantStorageWriteRequest(
        storage_reference=synthetic_variant_storage_reference(run_id, specification_digest),
        transform_run_reference=run_id,
        specification_digest=specification_digest,
        output_policy_version="variant-output-v1",
        result=_result(content),
    )


@pytest.mark.asyncio
async def test_variant_storage_is_private_create_if_absent_and_integrity_checked(
    tmp_path: Path,
) -> None:
    provider = LocalSyntheticVariantStorageProvider(root=tmp_path / "private")
    request = _request()
    first = await provider.store_variant_if_absent(request=request)
    second = await provider.store_variant_if_absent(request=request)
    assert first == second
    assert first.storage_key.startswith("internal-synthetic/v1/variants/")
    assert "a" * 32 not in first.storage_key
    assert "b" * 64 not in first.storage_key
    streamed = bytearray()
    async for chunk in provider.stream_variant(storage_reference=request.storage_reference):
        streamed.extend(chunk)
    assert bytes(streamed) == request.result.content
    with pytest.raises(SyntheticStorageConflictError):
        await provider.store_variant_if_absent(request=_request(b"different-deterministic-output"))
    assert await provider.delete_variant(storage_reference=request.storage_reference) == "deleted"
    assert await provider.delete_variant(storage_reference=request.storage_reference) == "not_found"


@pytest.mark.asyncio
async def test_variant_storage_rejects_tampered_payload(tmp_path: Path) -> None:
    root = tmp_path / "private"
    provider = LocalSyntheticVariantStorageProvider(root=root)
    request = _request()
    receipt = await provider.store_variant_if_absent(request=request)
    payload = root / receipt.storage_key / "payload"
    payload.write_bytes(b"tampered")
    with pytest.raises(Exception, match="synthetic storage operation was rejected"):
        await provider.inspect_variant(storage_reference=request.storage_reference)
