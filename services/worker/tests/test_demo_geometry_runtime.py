from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from mirror_api.config import Settings

from mirror_worker import demo_geometry_runtime as geometry_module
from mirror_worker import runtime as runtime_module
from mirror_worker.demo_geometry_runtime import (
    AcceptedD02GeometryCapabilityFactory,
    D02GeometryRuntimeBundle,
    DemoGeometryCapability,
    DemoGeometryCapabilityRegistry,
)


class _Backend:
    def execute(self, *, request: object) -> object:
        raise AssertionError(f"unit composition must not execute {type(request).__name__}")


class _Verifier:
    async def __call__(self, command: object, materialized: object) -> object:
        del command, materialized
        raise AssertionError("unit composition must not run verifier")


class _Factory:
    def __init__(self) -> None:
        self.calls = 0
        self.capability = DemoGeometryCapability(
            backend=cast(Any, _Backend()), verifier=cast(Any, _Verifier())
        )

    def create(self) -> DemoGeometryCapability:
        self.calls += 1
        return self.capability


class _BundleFactory:
    def __init__(self, bundle: D02GeometryRuntimeBundle) -> None:
        self.bundle = bundle
        self.calls = 0

    def create(self) -> D02GeometryRuntimeBundle:
        self.calls += 1
        return self.bundle


def test_geometry_capability_registry_is_one_shot_and_non_serializing() -> None:
    empty = DemoGeometryCapabilityRegistry()
    assert empty.optional() is None
    with pytest.raises(RuntimeError, match="CAPABILITY_NOT_INSTALLED"):
        empty.require()
    with pytest.raises(TypeError, match="factory is invalid"):
        empty.install(cast(Any, object()))

    registry = DemoGeometryCapabilityRegistry()
    factory = _Factory()
    registry.install(factory)
    assert registry.optional() is factory
    assert registry.require() is factory
    with pytest.raises(RuntimeError, match="CAPABILITY_ALREADY_INSTALLED"):
        registry.install(factory)
    assert "_Backend" not in repr(factory.capability)
    assert "_Verifier" not in repr(factory.capability)


def test_tracked_factory_composes_backend_and_verifier_from_same_fresh_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = cast(Any, object())
    additional = cast(Any, object())
    rows = (cast(dict[str, object], {"case": "public"}),)
    bundle_factory = _BundleFactory(D02GeometryRuntimeBundle(executor, rows, (additional,)))
    backend, verifier = cast(Any, _Backend()), cast(Any, _Verifier())
    captured: list[tuple[object, object]] = []

    def make_backend(
        *, executor: object, case_rows: object, additional_executors: object
    ) -> object:
        captured.extend(((executor, case_rows), (additional_executors, "backend-additional")))
        return backend

    def make_verifier(executor: object, additional_executors: object) -> object:
        captured.extend(((executor, "verifier"), (additional_executors, "verifier-additional")))
        return verifier

    monkeypatch.setattr(geometry_module, "D02M4GeometryRuntimeAdapter", make_backend)
    monkeypatch.setattr(geometry_module, "IndependentGeometryVerifierRouter", make_verifier)

    capability = AcceptedD02GeometryCapabilityFactory(bundle_factory).create()

    assert bundle_factory.calls == 1
    assert capability.backend is backend
    assert capability.verifier is verifier
    assert captured == [
        (executor, rows),
        ((additional,), "backend-additional"),
        (executor, "verifier"),
        ((additional,), "verifier-additional"),
    ]


@pytest.mark.asyncio
async def test_worker_runtime_composes_attempt_scoped_geometry_pair(tmp_path: Path) -> None:
    factory = _Factory()
    settings = Settings(app_env="test", local_storage_root=tmp_path)
    runtime = runtime_module.create_demo_editing_runtime(
        settings, geometry_capability_factory=factory
    )
    try:
        assert factory.calls == 1
        assert runtime.application._geometry_backend is factory.capability.backend
        assert runtime.application._geometry_verifier is factory.capability.verifier
    finally:
        await runtime.engine.dispose()


def test_worker_runtime_sanitizes_private_factory_failure(tmp_path: Path) -> None:
    class _FailingFactory:
        def create(self) -> DemoGeometryCapability:
            raise RuntimeError("private-locator-must-not-escape")

    settings = Settings(app_env="test", local_storage_root=tmp_path)
    with pytest.raises(RuntimeError, match="capability composition failed") as raised:
        runtime_module.create_demo_editing_runtime(
            settings, geometry_capability_factory=_FailingFactory()
        )
    assert "private-locator" not in str(raised.value)
