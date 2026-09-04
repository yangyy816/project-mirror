from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Generator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)
from test_demo_stepped_self_transfer_acceptance import _stepped_execution

from mirror_api.config import Settings
from mirror_api.demo_editing_asset_loader import DemoAssetByteReference, DemoAssetLoadError
from mirror_api.demo_editing_dependencies import get_demo_editing_media_service
from mirror_api.demo_editing_media import (
    DemoEditingMediaAuthorityCorruption,
    DemoEditingMediaBytesUnavailable,
    DemoEditingMediaInputError,
    DemoEditingMediaService,
    DemoEditingMediaUnavailable,
)
from mirror_api.demo_models import DemoImageVersion
from mirror_api.errors import APIError
from mirror_api.models import Asset, Job, utcnow

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy() -> Any:
    if os.name == "nt":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def postgres_session() -> Generator[Session]:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is unavailable")
    engine = create_engine(url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as session:
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
        yield session
        session.rollback()
        _truncate_demo_authority(session)
        _truncate_formal_synthetic_fixture_authority(session)
    engine.dispose()


@dataclass
class _Loader:
    references: list[DemoAssetByteReference]
    content: bytes = b"fixture-jpeg"
    error: DemoAssetLoadError | None = None
    after_load: Callable[[], None] | None = None

    async def load(self, reference: DemoAssetByteReference) -> bytes:
        self.references.append(reference)
        if self.error is not None:
            raise self.error
        if self.after_load is not None:
            callback, self.after_load = self.after_load, None
            callback()
        return self.content


def _service(
    sessions: async_sessionmaker[AsyncSession], loader: _Loader
) -> DemoEditingMediaService:
    return DemoEditingMediaService(session_factory=sessions, asset_loader=loader)


@pytest.mark.asyncio
async def test_media_resolves_exact_input_and_result_without_disclosure(
    postgres_session: Session,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions, engine, graph, _, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    loader = _Loader([])
    service = _service(sessions, loader)
    monkeypatch.setattr(
        "mirror_api.demo_editing_media.decode_canonical_rgb_image", lambda *_a, **_k: None
    )
    try:
        result = await service.load(
            demo_actor_id=graph["actor"].id,
            job_id=execution.job_id,
            side="RESULT",
        )
        source = await service.load(
            demo_actor_id=graph["actor"].id,
            job_id=execution.job_id,
            side="INPUT",
        )
        published_image = postgres_session.get(DemoImageVersion, published.image_version_id)
        assert published_image is not None
        assert result.content == source.content == b"fixture-jpeg"
        assert loader.references[0].asset_id == published_image.result_asset_id
        assert loader.references[0].sha256 == published_image.result_asset_sha256
        assert loader.references[1].asset_id == graph["image"].result_asset_id
        assert loader.references[1].sha256 == graph["image"].result_asset_sha256
        assert all(item.synthetic is True for item in loader.references)
        assert "storage_key" not in repr(result)
        assert not any(item.storage_key in repr(result) for item in loader.references)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_media_rejects_invalid_side_foreign_owner_and_nonterminal_job(
    postgres_session: Session,
    tmp_path: Any,
) -> None:
    sessions, engine, graph, _, execution, _ = await _stepped_execution(postgres_session, tmp_path)
    service = _service(sessions, _Loader([]))
    try:
        with pytest.raises(DemoEditingMediaInputError):
            await service.load(
                demo_actor_id=graph["actor"].id,
                job_id=execution.job_id,
                side="LEFT",  # type: ignore[arg-type]
            )
        with pytest.raises(DemoEditingMediaUnavailable):
            await service.load(
                demo_actor_id="f" * 32,
                job_id=execution.job_id,
                side="RESULT",
            )
        postgres_session.execute(
            update(Job)
            .where(Job.id == execution.job_id)
            .values(status="PENDING", finalized_at=None, result_code=None)
        )
        postgres_session.commit()
        with pytest.raises(DemoEditingMediaUnavailable):
            await service.load(
                demo_actor_id=graph["actor"].id,
                job_id=execution.job_id,
                side="RESULT",
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "value"),
    (("deleted_at", "NOW"), ("mime_type", "image/png"), ("sha256", "f" * 64)),
    ids=("deleted", "mime", "digest-substitution"),
)
async def test_media_rejects_result_asset_authority_drift(
    postgres_session: Session,
    tmp_path: Any,
    mutation: str,
    value: object,
) -> None:
    sessions, engine, graph, _, execution, published = await _stepped_execution(
        postgres_session, tmp_path
    )
    image = postgres_session.get(DemoImageVersion, published.image_version_id)
    assert image is not None
    replacement = utcnow() if value == "NOW" else value
    postgres_session.execute(
        update(Asset).where(Asset.id == image.result_asset_id).values({mutation: replacement})
    )
    postgres_session.commit()
    try:
        with pytest.raises(DemoEditingMediaAuthorityCorruption):
            await _service(sessions, _Loader([])).load(
                demo_actor_id=graph["actor"].id,
                job_id=execution.job_id,
                side="RESULT",
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_media_maps_loader_and_decode_failure_without_locator(
    postgres_session: Session,
    tmp_path: Any,
) -> None:
    sessions, engine, graph, _, execution, _ = await _stepped_execution(postgres_session, tmp_path)
    try:
        unavailable = DemoAssetLoadError("ASSET_BYTES_UNAVAILABLE", "fixture unavailable")
        with pytest.raises(DemoEditingMediaBytesUnavailable) as loader_error:
            await _service(sessions, _Loader([], error=unavailable)).load(
                demo_actor_id=graph["actor"].id,
                job_id=execution.job_id,
                side="RESULT",
            )
        with pytest.raises(DemoEditingMediaBytesUnavailable) as decode_error:
            await _service(sessions, _Loader([], content=b"not-a-jpeg")).load(
                demo_actor_id=graph["actor"].id,
                job_id=execution.job_id,
                side="RESULT",
            )
        assert "storage" not in str(loader_error.value).lower()
        assert "storage" not in str(decode_error.value).lower()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_media_revalidates_exact_execution_after_load(
    postgres_session: Session,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions, engine, graph, _, execution, _ = await _stepped_execution(postgres_session, tmp_path)

    def terminate_job() -> None:
        postgres_session.execute(
            update(Job)
            .where(Job.id == execution.job_id)
            .values(status="FAILED", result_code="SYNTHETIC_RACE")
        )
        postgres_session.commit()

    loader = _Loader([], after_load=terminate_job)
    monkeypatch.setattr(
        "mirror_api.demo_editing_media.decode_canonical_rgb_image", lambda *_a, **_k: None
    )
    try:
        with pytest.raises(DemoEditingMediaUnavailable):
            await _service(sessions, loader).load(
                demo_actor_id=graph["actor"].id,
                job_id=execution.job_id,
                side="RESULT",
            )
    finally:
        await engine.dispose()


def test_media_dependency_is_local_only(tmp_path: Any) -> None:
    sessions = cast(async_sessionmaker[AsyncSession], object())
    request = cast(
        Any,
        SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(auth_infrastructure=SimpleNamespace(sessions=sessions))
            )
        ),
    )
    local = cast(
        Settings,
        SimpleNamespace(
            app_env="test",
            synthetic_storage_provider="local",
            local_storage_root=tmp_path,
        ),
    )
    assert isinstance(
        get_demo_editing_media_service(request, settings=local),
        DemoEditingMediaService,
    )
    remote = cast(
        Settings,
        SimpleNamespace(
            app_env="production",
            synthetic_storage_provider="local",
            local_storage_root=tmp_path,
        ),
    )
    with pytest.raises(APIError) as raised:
        get_demo_editing_media_service(request, settings=remote)
    assert raised.value.status_code == 503
    assert raised.value.code == "DEMO_EDIT_MEDIA_RUNTIME_UNAVAILABLE"
