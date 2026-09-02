from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mirror_api.demo_editing_asset_loader import (
    DemoAssetByteReference,
    DemoAssetLoadError,
    LocalDemoAssetByteLoader,
)


def _reference(content: bytes, *, key: str | None = None) -> DemoAssetByteReference:
    return DemoAssetByteReference(
        asset_id="a" * 32,
        storage_key=key or f"demo-original/v1/{'b' * 32}/{hashlib.sha256(content).hexdigest()}",
        sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        synthetic=True,
    )


def _write(root: Path, reference: DemoAssetByteReference, content: bytes) -> Path:
    payload = root.joinpath(*reference.storage_key.split("/"), "payload")
    payload.parent.mkdir(parents=True)
    payload.write_bytes(content)
    return payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key",
    [
        f"internal-synthetic/v1/normalized/{'1' * 64}",
        f"internal-synthetic/v1/variants/{'2' * 64}",
        f"internal-synthetic/v1/d02/source/{'7' * 32}",
        f"internal-synthetic/v1/d02/result/{'8' * 32}",
        f"demo-original/v1/{'3' * 32}/{'4' * 64}",
        f"demo-published/v1/{'5' * 32}/{'6' * 64}",
    ],
)
async def test_local_demo_asset_loader_accepts_only_private_synthetic_namespaces(
    tmp_path: Path, key: str
) -> None:
    content = b"synthetic-only-asset"
    reference = _reference(content, key=key)
    _write(tmp_path, reference, content)

    assert await LocalDemoAssetByteLoader(root=tmp_path).load(reference) == content


@pytest.mark.asyncio
async def test_local_demo_asset_loader_rejects_non_synthetic_and_tampered_bytes(
    tmp_path: Path,
) -> None:
    content = b"synthetic-only-asset"
    reference = _reference(content)
    payload = _write(tmp_path, reference, b"tampered")
    loader = LocalDemoAssetByteLoader(root=tmp_path)

    with pytest.raises(DemoAssetLoadError) as mismatch:
        await loader.load(reference)
    assert mismatch.value.code == "ASSET_SIZE_MISMATCH"

    payload.write_bytes(content)
    with pytest.raises(DemoAssetLoadError) as rejected:
        await loader.load(
            DemoAssetByteReference(
                reference.asset_id,
                reference.storage_key,
                reference.sha256,
                reference.byte_size,
                False,
            )
        )
    assert rejected.value.code == "ASSET_REFERENCE_INVALID"


@pytest.mark.asyncio
async def test_local_demo_asset_loader_rejects_unapproved_namespace_and_symlink(
    tmp_path: Path,
) -> None:
    content = b"synthetic-only-asset"
    bad = _reference(content, key=f"sanitized/v1/{'7' * 32}")
    with pytest.raises(DemoAssetLoadError) as rejected:
        await LocalDemoAssetByteLoader(root=tmp_path).load(bad)
    assert rejected.value.code == "ASSET_REFERENCE_INVALID"

    reference = _reference(content)
    payload = _write(tmp_path, reference, content)
    payload.unlink()
    target = tmp_path / "outside"
    target.write_bytes(content)
    try:
        payload.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(DemoAssetLoadError) as symlink:
        await LocalDemoAssetByteLoader(root=tmp_path).load(reference)
    assert symlink.value.code == "ASSET_PATH_INVALID"
