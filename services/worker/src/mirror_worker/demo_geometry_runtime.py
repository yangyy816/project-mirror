"""Process-local D08 private runtime capability boundary.

The D02 custodian installs an opaque factory inside the controlled Worker
process.  Nothing in this module discovers, serializes, or logs private runtime
locators or image bytes.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from mirror_api.demo_d02_r2_runtime_forward import DemoM3M4Executor
from mirror_api.demo_d08_geometry_runtime_adapter import D02M4GeometryRuntimeAdapter
from mirror_api.demo_d08_geometry_verifier import IndependentGeometryVerifierRouter
from mirror_api.demo_editing_service import EditVerifier
from mirror_api.demo_geometry_editor import GeometryExecutionBackend


@dataclass(frozen=True, slots=True)
class DemoGeometryCapability:
    """Attempt-scoped backend/verifier pair created before any Job claim."""

    backend: GeometryExecutionBackend = field(repr=False)
    verifier: EditVerifier = field(repr=False)

    def __post_init__(self) -> None:
        if not callable(getattr(self.backend, "execute", None)):
            raise TypeError("D08 geometry backend is invalid")
        if not callable(self.verifier):
            raise TypeError("D08 geometry verifier is invalid")


class DemoGeometryCapabilityFactory(Protocol):
    """Create a fresh capability pair; implementations must not reuse attempts."""

    def create(self) -> DemoGeometryCapability: ...


@dataclass(frozen=True, slots=True)
class D02GeometryRuntimeBundle:
    """Public executor/case inputs returned by a private custodian-owned factory."""

    executor: DemoM3M4Executor = field(repr=False)
    case_rows: tuple[Mapping[str, object], ...] = field(repr=False)
    additional_executors: tuple[DemoM3M4Executor, ...] = field(default=(), repr=False)


class D02GeometryRuntimeBundleFactory(Protocol):
    """Materialize one fresh reconstructed bundle inside the controlled process."""

    def create(self) -> D02GeometryRuntimeBundle: ...


@dataclass(frozen=True, slots=True)
class AcceptedD02GeometryCapabilityFactory:
    """Tracked composition; only the injected bundle factory may hold private config."""

    bundle_factory: D02GeometryRuntimeBundleFactory = field(repr=False)

    def create(self) -> DemoGeometryCapability:
        bundle = self.bundle_factory.create()
        if not isinstance(bundle, D02GeometryRuntimeBundle):
            raise TypeError("D08 geometry runtime bundle is invalid")
        return DemoGeometryCapability(
            backend=D02M4GeometryRuntimeAdapter(
                executor=bundle.executor,
                case_rows=bundle.case_rows,
                additional_executors=bundle.additional_executors,
            ),
            verifier=IndependentGeometryVerifierRouter(
                bundle.executor,
                bundle.additional_executors,
            ),
        )


class DemoGeometryCapabilityRegistry:
    """One-shot process-local factory holder with no serialization surface."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._factory: DemoGeometryCapabilityFactory | None = None

    def install(self, factory: DemoGeometryCapabilityFactory) -> None:
        if not callable(getattr(factory, "create", None)):
            raise TypeError("D08 geometry capability factory is invalid")
        with self._lock:
            if self._factory is not None:
                raise RuntimeError("D08_GEOMETRY_CAPABILITY_ALREADY_INSTALLED")
            self._factory = factory

    def optional(self) -> DemoGeometryCapabilityFactory | None:
        with self._lock:
            return self._factory

    def require(self) -> DemoGeometryCapabilityFactory:
        factory = self.optional()
        if factory is None:
            raise RuntimeError("D08_GEOMETRY_CAPABILITY_NOT_INSTALLED")
        return factory


_PROCESS_GEOMETRY_CAPABILITY = DemoGeometryCapabilityRegistry()


def install_demo_geometry_capability_factory(factory: DemoGeometryCapabilityFactory) -> None:
    """Install one task-scoped factory before starting the controlled Worker."""

    _PROCESS_GEOMETRY_CAPABILITY.install(factory)


def optional_demo_geometry_capability_factory() -> DemoGeometryCapabilityFactory | None:
    """Return the opaque factory when this process explicitly installed it."""

    return _PROCESS_GEOMETRY_CAPABILITY.optional()


def require_demo_geometry_capability_factory() -> DemoGeometryCapabilityFactory:
    """Fail closed without discovering any private runtime material."""

    return _PROCESS_GEOMETRY_CAPABILITY.require()
