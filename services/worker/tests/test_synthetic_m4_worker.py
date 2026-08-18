from __future__ import annotations

import asyncio
from dataclasses import fields

import pytest
from mirror_api.config import Settings
from mirror_api.synthetic_dataset.m4_orchestration_service import (
    M4RetryableError,
    M4TaskResult,
)
from mirror_api.synthetic_dataset.task_contract import SyntheticTransformTaskMessage

from mirror_worker.ingestion import RetryableWorkerFailure
from mirror_worker.runtime import create_synthetic_m4_runtime
from mirror_worker.synthetic_m4 import SyntheticM4Reconciler, SyntheticM4TaskExecutor


class FakeM4Application:
    def __init__(self) -> None:
        self.message = SyntheticTransformTaskMessage(
            transform_run_id="a" * 32,
            job_id="b" * 32,
            request_id="m4-worker-fixture",
        )
        self.retry = False

    async def execute_transform(self, message: SyntheticTransformTaskMessage) -> M4TaskResult:
        assert message == self.message
        if self.retry:
            raise M4RetryableError("variant_storage_unavailable")
        return M4TaskResult(
            message.transform_run_id,
            message.job_id,
            "variant_qa_pending",
            "c" * 32,
            "d" * 32,
        )

    async def reconciliation_candidates(
        self, *, limit: int = 100
    ) -> tuple[SyntheticTransformTaskMessage, ...]:
        assert limit == 10
        return (self.message,)


class CapturingDispatcher:
    def __init__(self) -> None:
        self.messages: list[SyntheticTransformTaskMessage] = []

    def dispatch_synthetic_transform(self, message: SyntheticTransformTaskMessage) -> str:
        self.messages.append(message)
        return message.job_id


def test_m4_task_contract_is_closed_and_reference_only() -> None:
    message = FakeM4Application().message
    assert SyntheticTransformTaskMessage.from_message(message.to_message()) == message
    assert set(message.to_message()) == {
        "transform_run_id",
        "job_id",
        "request_id",
        "schema_version",
    }
    expanded: dict[str, object] = dict(message.to_message())
    expanded["warp_plan"] = {"forbidden": True}
    with pytest.raises(ValueError, match="invalid shape"):
        SyntheticTransformTaskMessage.from_message(expanded)


def test_m4_runtime_composes_the_configured_geometry_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_provider = object()
    captured: list[Settings] = []

    def fake_factory(settings: Settings) -> object:
        captured.append(settings)
        return configured_provider

    monkeypatch.setattr("mirror_worker.runtime.create_geometry_transform_provider", fake_factory)
    settings = Settings(
        app_env="test",
        synthetic_storage_provider="local",
        geometry_transform_provider="disabled",
    )
    runtime = create_synthetic_m4_runtime(settings)
    try:
        transform_service = runtime.application._transforms
        assert transform_service._transform is configured_provider
        assert captured == [settings]
    finally:
        asyncio.run(runtime.engine.dispose())


def test_m4_runtime_fails_before_storage_composition_when_geometry_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_: Settings) -> object:
        raise RuntimeError("geometry transform provider is not enabled")

    def storage_must_not_be_composed(*_: object, **__: object) -> object:
        pytest.fail("storage must not be composed after geometry fail-closed")

    monkeypatch.setattr("mirror_worker.runtime.create_geometry_transform_provider", unavailable)
    monkeypatch.setattr(
        "mirror_worker.runtime.LocalSyntheticNormalizedStorageProvider",
        storage_must_not_be_composed,
    )
    monkeypatch.setattr(
        "mirror_worker.runtime.LocalSyntheticVariantStorageProvider",
        storage_must_not_be_composed,
    )
    with pytest.raises(RuntimeError, match="provider is not enabled"):
        create_synthetic_m4_runtime(Settings(app_env="test", synthetic_storage_provider="local"))


def test_m4_runtime_path_never_enters_message_or_result_contracts() -> None:
    assert {field.name for field in fields(SyntheticTransformTaskMessage)} == {
        "transform_run_id",
        "job_id",
        "request_id",
        "schema_version",
    }
    assert {field.name for field in fields(M4TaskResult)} == {
        "transform_run_id",
        "job_id",
        "status",
        "result_asset_id",
        "qa_run_id",
    }


@pytest.mark.asyncio
async def test_m4_worker_redacts_retryable_failure_and_reconciles() -> None:
    application = FakeM4Application()
    executor = SyntheticM4TaskExecutor(application)
    result = await executor.execute(application.message)
    assert result.status == "variant_qa_pending"
    application.retry = True
    with pytest.raises(RetryableWorkerFailure, match="synthetic transform remains retryable"):
        await executor.execute(application.message)
    dispatcher = CapturingDispatcher()
    dispatched = await SyntheticM4Reconciler(application, dispatcher).execute(limit=10)
    assert dispatched == (application.message.transform_run_id,)
    assert dispatcher.messages == [application.message]
