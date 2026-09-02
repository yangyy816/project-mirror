from __future__ import annotations

from typing import cast

import pytest
from mirror_api.config import Settings
from mirror_api.demo_analysis_service import DemoAnalysisDispatchCandidate
from mirror_api.demo_analysis_task_contract import DemoAnalysisTaskMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_worker import runtime as runtime_module
from mirror_worker.demo_analysis_runtime import (
    DemoAnalysisM3CapabilityRegistry,
    DemoAnalysisM3CapabilityUnavailable,
    PreparedSourceM3Backend,
)
from mirror_worker.local import LocalTaskRunner


class _BackendFactory:
    def create(self) -> PreparedSourceM3Backend:
        raise AssertionError("unit composition test must not create a backend")


def _message() -> DemoAnalysisTaskMessage:
    return DemoAnalysisTaskMessage(
        analysis_run_id="a" * 32,
        job_id="b" * 32,
        request_id="d03-composition-request",
    )


def test_process_capability_registry_is_one_shot_and_fail_closed() -> None:
    empty = DemoAnalysisM3CapabilityRegistry()
    with pytest.raises(DemoAnalysisM3CapabilityUnavailable, match="CAPABILITY_NOT_INSTALLED"):
        empty.require()
    with pytest.raises(TypeError, match="factory is invalid"):
        empty.install(cast(object, object()))  # type: ignore[arg-type]

    registry = DemoAnalysisM3CapabilityRegistry()
    factory = _BackendFactory()
    registry.install(factory)
    assert registry.require() is factory
    with pytest.raises(RuntimeError, match="CAPABILITY_ALREADY_INSTALLED"):
        registry.install(factory)


def test_runtime_composition_requires_capability_before_engine_or_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing() -> _BackendFactory:
        raise DemoAnalysisM3CapabilityUnavailable()

    def unexpected_engine(_: str) -> object:
        raise AssertionError("engine must not be created without an M3 capability")

    monkeypatch.setattr(runtime_module, "require_demo_analysis_m3_backend_factory", missing)
    monkeypatch.setattr(runtime_module, "create_async_engine", unexpected_engine)

    with pytest.raises(DemoAnalysisM3CapabilityUnavailable, match="CAPABILITY_NOT_INSTALLED"):
        runtime_module.create_demo_analysis_runtime(Settings(app_env="test"))


def test_local_runner_requires_and_forwards_explicit_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[dict[str, str], object]] = []

    async def fake_run(
        message: dict[str, str],
        *,
        settings: Settings,
        backend_factory: object,
    ) -> dict[str, str | None]:
        assert settings.app_env == "test"
        captured.append((message, backend_factory))
        return {}

    monkeypatch.setattr("mirror_worker.local.run_demo_analysis_message", fake_run)
    message = _message()
    with pytest.raises(DemoAnalysisM3CapabilityUnavailable):
        LocalTaskRunner(Settings(app_env="test")).dispatch_demo_analysis(message)
    assert captured == []

    factory = _BackendFactory()
    runner = LocalTaskRunner(
        Settings(app_env="test"),
        demo_analysis_backend_factory=factory,
    )
    assert runner.dispatch_demo_analysis(message) == message.job_id
    assert captured == [(message.to_message(), factory)]


class _Engine:
    disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class _ReconciliationApplication:
    async def reconciliation_candidates(
        self, *, limit: int
    ) -> tuple[DemoAnalysisDispatchCandidate, ...]:
        assert limit == 1
        return (DemoAnalysisDispatchCandidate("a" * 32, "b" * 32, "request-01"),)


class _Dispatcher:
    def __init__(self) -> None:
        self.messages: list[DemoAnalysisTaskMessage] = []

    def dispatch_demo_analysis(self, message: DemoAnalysisTaskMessage) -> str:
        self.messages.append(message)
        return message.job_id


@pytest.mark.asyncio
async def test_reconciliation_needs_no_private_runtime_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _Engine()
    application = _ReconciliationApplication()

    def create_application(
        _: Settings,
    ) -> tuple[object, async_sessionmaker[AsyncSession], object]:
        return (
            engine,
            cast(async_sessionmaker[AsyncSession], object()),
            application,
        )

    def unexpected_capability() -> _BackendFactory:
        raise AssertionError("maintenance reconciliation must not read a private capability")

    monkeypatch.setattr(runtime_module, "_create_demo_analysis_application", create_application)
    monkeypatch.setattr(
        runtime_module,
        "require_demo_analysis_m3_backend_factory",
        unexpected_capability,
    )
    dispatcher = _Dispatcher()

    assert await runtime_module.run_demo_analysis_reconciliation(
        dispatcher=dispatcher,
        limit=1,
        settings=Settings(app_env="test"),
    ) == ("b" * 32,)
    assert dispatcher.messages == [DemoAnalysisTaskMessage("a" * 32, "b" * 32, "request-01")]
    assert engine.disposed is True
