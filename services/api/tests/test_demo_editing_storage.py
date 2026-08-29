from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from mirror_api.demo_editing_storage import DemoEditingStorageError, DemoLocalPrivateObjectStorage


def _key(char: str = "a") -> str:
    return f"demo-quarantine/{char * 32}/{'b' * 32}/{'c' * 32}/{'d' * 32}"


@pytest.mark.asyncio
async def test_private_quarantine_storage_is_idempotent_and_readable(tmp_path: Path) -> None:
    storage = DemoLocalPrivateObjectStorage(root=tmp_path / "private")
    content = b"safe-unit-fixture"
    digest = hashlib.sha256(content).hexdigest()

    await storage.put_if_absent(key=_key(), content=content, sha256=digest)
    await storage.put_if_absent(key=_key(), content=content, sha256=digest)

    assert await storage.read(key=_key()) == content
    assert (tmp_path / "private" / _key() / "payload").is_file()


@pytest.mark.asyncio
async def test_private_quarantine_storage_rejects_conflict_and_bad_digest(tmp_path: Path) -> None:
    storage = DemoLocalPrivateObjectStorage(root=tmp_path)
    content = b"first"
    await storage.put_if_absent(
        key=_key(), content=content, sha256=hashlib.sha256(content).hexdigest()
    )

    with pytest.raises(DemoEditingStorageError) as conflict:
        await storage.put_if_absent(
            key=_key(), content=b"second", sha256=hashlib.sha256(b"second").hexdigest()
        )
    assert conflict.value.code == "STORAGE_OBJECT_CONFLICT"

    with pytest.raises(DemoEditingStorageError) as mismatch:
        await storage.put_if_absent(key=_key("e"), content=content, sha256="0" * 64)
    assert mismatch.value.code == "STORAGE_DIGEST_MISMATCH"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key",
    (
        "",
        "/demo-quarantine/a",
        "demo-quarantine/../a/b/c/d",
        "demo-quarantine\\a/b/c/d",
        "demo-quarantine//a/b/c/d",
        "demo-quarantine/a/a/a/a",
    ),
)
async def test_private_quarantine_storage_rejects_noncanonical_keys(
    tmp_path: Path, key: str
) -> None:
    storage = DemoLocalPrivateObjectStorage(root=tmp_path)
    with pytest.raises(DemoEditingStorageError) as rejected:
        await storage.read(key=key)
    assert rejected.value.code == "STORAGE_KEY_INVALID"


@pytest.mark.asyncio
async def test_private_quarantine_storage_rejects_symlink_and_tamper(tmp_path: Path) -> None:
    storage = DemoLocalPrivateObjectStorage(root=tmp_path / "private")
    content = b"original"
    digest = hashlib.sha256(content).hexdigest()
    await storage.put_if_absent(key=_key(), content=content, sha256=digest)
    payload = tmp_path / "private" / _key() / "payload"
    payload.write_bytes(b"tampered")

    with pytest.raises(DemoEditingStorageError) as conflict:
        await storage.put_if_absent(key=_key(), content=content, sha256=digest)
    assert conflict.value.code == "STORAGE_OBJECT_CONFLICT"

    namespace = tmp_path / "symlink-private"
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (namespace / "demo-quarantine").parent.mkdir(parents=True)
        (namespace / "demo-quarantine").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this host")
    symlink_storage = DemoLocalPrivateObjectStorage(root=namespace)
    with pytest.raises(DemoEditingStorageError) as rejected:
        await symlink_storage.read(key=_key())
    assert rejected.value.code == "STORAGE_PATH_INVALID"


@pytest.mark.asyncio
async def test_private_quarantine_storage_concurrent_writes_leave_one_complete_payload(
    tmp_path: Path,
) -> None:
    storage = DemoLocalPrivateObjectStorage(root=tmp_path)
    content = b"concurrent-private-fixture" * 4096
    digest = hashlib.sha256(content).hexdigest()
    await asyncio.gather(
        *[storage.put_if_absent(key=_key(), content=content, sha256=digest) for _ in range(16)]
    )
    assert await storage.read(key=_key()) == content
    assert not list((tmp_path / "demo-quarantine").rglob(".payload-*.part"))
