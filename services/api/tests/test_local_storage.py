from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi import FastAPI, Request, Response

from mirror_api.errors import APIError, api_error_handler
from mirror_api.middleware import LocalUploadAccessLogRedactionMiddleware, RequestIDMiddleware
from mirror_api.providers.local import LocalObjectStorageProvider
from mirror_api.routers.local_upload import router as local_upload_router


def _fixture_bytes() -> bytes:
    return b"project-mirror-synthetic-non-face-upload-fixture"


def _object_key(seed: str = "a") -> str:
    return f"quarantine/v1/{seed * 64}"


async def _body(data: bytes, *, split_at: int | None = None) -> AsyncIterator[bytes]:
    if split_at is None:
        yield data
        return
    yield data[:split_at]
    yield data[split_at:]


def _test_app(provider: LocalObjectStorageProvider) -> FastAPI:
    app = FastAPI()
    app.state.object_storage_provider = provider
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LocalUploadAccessLogRedactionMiddleware)
    app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    app.include_router(local_upload_router)
    return app


@pytest.mark.asyncio
async def test_local_upload_handle_is_redacted_before_access_logging() -> None:
    grant_handle = "grant-handle-sentinel"
    scope = {
        "type": "http",
        "path": f"/_local/private-upload/{grant_handle}",
        "raw_path": f"/_local/private-upload/{grant_handle}".encode(),
        "query_string": b"secret=query",
        "headers": [],
    }
    request = Request(scope)  # type: ignore[arg-type]

    async def call_next(_: Request) -> Response:
        return Response(status_code=204)

    middleware = LocalUploadAccessLogRedactionMiddleware(app=FastAPI())
    await middleware.dispatch(request, call_next)
    assert request.scope["path"] == "/_local/private-upload/[redacted]"
    assert request.scope["query_string"] == b""
    assert grant_handle not in str(request.scope)


@pytest.mark.asyncio
async def test_local_provider_streams_chunks_and_publishes_atomically(tmp_path: Path) -> None:
    fixture = _fixture_bytes()
    checksum = sha256(fixture).hexdigest()
    object_key = _object_key("0")
    provider = LocalObjectStorageProvider(root=tmp_path)
    grant = await provider.create_private_upload_grant(
        object_key=object_key,
        content_type="image/png",
        content_length=len(fixture),
        checksum_sha256=checksum,
    )
    await provider.receive_private_upload(
        grant_id=urlsplit(grant.url).path.rsplit("/", 1)[-1],
        authorization=grant.required_headers["X-Mirror-Upload-Authorization"],
        content_type=grant.required_headers["Content-Type"],
        content_length=int(grant.required_headers["Content-Length"]),
        checksum_sha256=grant.required_headers["X-Content-SHA256"],
        body=_body(fixture, split_at=7),
    )
    assert list(tmp_path.rglob("*.part")) == []
    assert (tmp_path / object_key).read_bytes() == fixture


@pytest.mark.asyncio
async def test_local_ingress_is_write_only_one_time_and_deletable(tmp_path: Path) -> None:
    fixture = _fixture_bytes()
    checksum = sha256(fixture).hexdigest()
    object_key = _object_key()
    provider = LocalObjectStorageProvider(root=tmp_path)
    grant = await provider.create_private_upload_grant(
        object_key=object_key,
        content_type="image/png",
        content_length=len(fixture),
        checksum_sha256=checksum,
    )
    proof = grant.required_headers["X-Mirror-Upload-Authorization"]
    assert proof not in repr(provider)
    assert object_key not in grant.url

    transport = httpx.ASGITransport(app=_test_app(provider))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        path = urlsplit(grant.url).path
        response = await client.put(path, headers=dict(grant.required_headers), content=fixture)
        assert response.status_code == 204
        replay = await client.put(path, headers=dict(grant.required_headers), content=fixture)
        assert replay.status_code == 409
        assert proof not in replay.text
        assert object_key not in replay.text
        assert (await client.get(path)).status_code == 405

    metadata = await provider.inspect_quarantine_object(object_key=object_key)
    assert metadata is not None
    assert metadata.byte_size == len(fixture)
    assert metadata.sha256 == checksum
    assert await provider.delete_quarantine_object(object_key=object_key) == "deleted"
    assert await provider.delete_quarantine_object(object_key=object_key) == "not_found"
    assert await provider.inspect_quarantine_object(object_key=object_key) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_status"),
    (
        ("short", 400),
        ("oversize", 413),
        ("mime", 415),
        ("checksum_header", 400),
        ("checksum_body", 400),
    ),
)
async def test_local_ingress_rejects_metadata_and_integrity_mismatch(
    tmp_path: Path,
    case: str,
    expected_status: int,
) -> None:
    fixture = _fixture_bytes()
    checksum = sha256(fixture).hexdigest()
    seed = {
        "short": "1",
        "oversize": "2",
        "mime": "3",
        "checksum_header": "4",
        "checksum_body": "5",
    }[case]
    object_key = _object_key(seed)
    provider = LocalObjectStorageProvider(root=tmp_path)
    grant = await provider.create_private_upload_grant(
        object_key=object_key,
        content_type="image/png",
        content_length=len(fixture),
        checksum_sha256=checksum,
    )
    headers = dict(grant.required_headers)
    body = fixture
    if case == "short":
        body = fixture[:-1]
    elif case == "oversize":
        body = fixture + b"x"
    elif case == "mime":
        headers["Content-Type"] = "image/jpeg"
    elif case == "checksum_header":
        headers["X-Content-SHA256"] = "0" * 64
    elif case == "checksum_body":
        body = b"x" * len(fixture)

    transport = httpx.ASGITransport(app=_test_app(provider))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.put(
            urlsplit(grant.url).path,
            headers=headers,
            content=body,
        )
    assert response.status_code == expected_status
    assert object_key not in response.text
    assert await provider.inspect_quarantine_object(object_key=object_key) is None
    assert list(tmp_path.rglob("*.part")) == []


@pytest.mark.asyncio
async def test_local_ingress_expiry_and_invalid_proof_fail_closed(tmp_path: Path) -> None:
    now = datetime(2026, 8, 16, tzinfo=UTC)
    current = [now]
    fixture = _fixture_bytes()
    checksum = sha256(fixture).hexdigest()
    provider = LocalObjectStorageProvider(
        root=tmp_path,
        ttl_seconds=60,
        clock=lambda: current[0],
        proof_key=b"test-only-local-proof-key" * 2,
    )
    expired = await provider.create_private_upload_grant(
        object_key=_object_key("d"),
        content_type="image/png",
        content_length=len(fixture),
        checksum_sha256=checksum,
    )
    current[0] = now + timedelta(seconds=60)
    transport = httpx.ASGITransport(app=_test_app(provider))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.put(
            urlsplit(expired.url).path,
            headers=dict(expired.required_headers),
            content=fixture,
        )
        assert response.status_code == 410

    current[0] = now
    invalid = await provider.create_private_upload_grant(
        object_key=_object_key("e"),
        content_type="image/png",
        content_length=len(fixture),
        checksum_sha256=checksum,
    )
    invalid_headers = dict(invalid.required_headers)
    invalid_headers["X-Mirror-Upload-Authorization"] = "invalid-proof"
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.put(
            urlsplit(invalid.url).path,
            headers=invalid_headers,
            content=fixture,
        )
        assert response.status_code == 404
        replay = await client.put(
            urlsplit(invalid.url).path,
            headers=dict(invalid.required_headers),
            content=fixture,
        )
        assert replay.status_code == 409


@pytest.mark.asyncio
async def test_local_storage_rejects_paths_and_symlink_components(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = LocalObjectStorageProvider(root=tmp_path)
    fixture = _fixture_bytes()
    checksum = sha256(fixture).hexdigest()
    with pytest.raises((APIError, ValueError)):
        await provider.create_private_upload_grant(
            object_key="quarantine/v1/../../outside",
            content_type="image/png",
            content_length=len(fixture),
            checksum_sha256=checksum,
        )

    quarantine = tmp_path / "quarantine"
    outside = tmp_path / "outside"
    outside.mkdir(exist_ok=True)
    try:
        quarantine.symlink_to(outside, target_is_directory=True)
    except OSError:
        original_is_symlink = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda path: path == quarantine or original_is_symlink(path),
        )
    with pytest.raises(ValueError, match="symlink"):
        await provider.create_private_upload_grant(
            object_key=_object_key("f"),
            content_type="image/png",
            content_length=len(fixture),
            checksum_sha256=checksum,
        )
