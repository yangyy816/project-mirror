"""Fail-closed D03 adapters for public D02 source authority and fresh M3 evidence."""

from __future__ import annotations

import base64
import math
import threading
from collections.abc import Mapping
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from typing import Protocol, cast

from mirror_api import demo_d02_authority as d02_authority
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_analysis_service import (
    DemoAnalysisRepeatEvidence,
    DemoAnalysisReservation,
    DemoAnalysisRuntimeEvidence,
    DemoLandmark,
    DemoPose,
)
from mirror_api.demo_analysis_source_authority import (
    AdmittedD02SourceReference,
    DemoAnalysisSourceAuthorityError,
)
from mirror_api.demo_d02_r2_authority import R2_SOURCE_M3_SCHEMA
from mirror_api.demo_d02_r2_runtime_forward import (
    NETWORK_POLICY,
    BackendM3Result,
    DurableSourceDescriptor,
    M3ExecutionOutput,
    build_default_model_identity,
)
from mirror_api.demo_face_runtime import DimensionObservation

from mirror_worker.demo_analysis import DemoAnalysisRuntimeFailed, DemoAnalysisRuntimeRejected

_EVIDENCE_REFERENCE_PREFIX = "d03m3r_"


class AdmittedD02SourceResolver(Protocol):
    """Resolve one public D02 source reference without returning bytes or locators."""

    async def resolve(self, asset_id: str) -> AdmittedD02SourceReference: ...


class AdmittedD02SourceLoader(Protocol):
    """Load the already-authorized source bytes for one admitted reference."""

    async def load(self, reference: AdmittedD02SourceReference) -> bytes: ...


class PreparedSourceM3Group(Protocol):
    """Public shape returned by a qualified M3 backend; no private backend type leaks here."""

    descriptor_digest: str
    landmark_digest: str
    landmarks: tuple[tuple[float, float, float], ...]
    outputs: tuple[BackendM3Result, BackendM3Result, BackendM3Result]


class PreparedSourceM3Backend(Protocol):
    execution_runtime_set_digest: str
    model_identity_digest: str
    model_config_digest: str
    weights_digest_or_no_weights: str
    network_policy: str

    def prepare_source_group(
        self, *, content: bytes, descriptor: DurableSourceDescriptor
    ) -> PreparedSourceM3Group: ...


class PreparedSourceM3BackendFactory(Protocol):
    """Create an attempt-scoped backend. Implementations must not cache it."""

    def create(self) -> PreparedSourceM3Backend: ...


class DemoAnalysisM3CapabilityUnavailable(RuntimeError):
    """The current process has no explicitly installed private M3 capability."""

    def __init__(self) -> None:
        super().__init__("D03_M3_CAPABILITY_NOT_INSTALLED")


class DemoAnalysisM3CapabilityRegistry:
    """One-shot process-local holder; the factory is never serialized or logged."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._factory: PreparedSourceM3BackendFactory | None = None

    def install(self, factory: PreparedSourceM3BackendFactory) -> None:
        if not callable(getattr(factory, "create", None)):
            raise TypeError("D03 M3 backend factory is invalid")
        with self._lock:
            if self._factory is not None:
                raise RuntimeError("D03_M3_CAPABILITY_ALREADY_INSTALLED")
            self._factory = factory

    def require(self) -> PreparedSourceM3BackendFactory:
        with self._lock:
            if self._factory is None:
                raise DemoAnalysisM3CapabilityUnavailable()
            return self._factory


_PROCESS_M3_CAPABILITY = DemoAnalysisM3CapabilityRegistry()


def install_demo_analysis_m3_backend_factory(factory: PreparedSourceM3BackendFactory) -> None:
    """Install one task-scoped capability before starting the dedicated Worker."""

    _PROCESS_M3_CAPABILITY.install(factory)


def require_demo_analysis_m3_backend_factory() -> PreparedSourceM3BackendFactory:
    """Fail before Job claim when the dedicated Worker lacks its capability."""

    return _PROCESS_M3_CAPABILITY.require()


class LiveDemoAnalysisRuntime:
    """Build one D03 evidence triplet from a fresh, already-qualified M3 backend."""

    def __init__(
        self,
        *,
        source_resolver: AdmittedD02SourceResolver,
        source_loader: AdmittedD02SourceLoader,
        backend_factory: PreparedSourceM3BackendFactory,
    ) -> None:
        self._source_resolver = source_resolver
        self._source_loader = source_loader
        self._backend_factory = backend_factory

    async def observe(self, reservation: DemoAnalysisReservation) -> DemoAnalysisRuntimeEvidence:
        _validate_reservation_bindings(reservation)
        reference = await self._resolve_reference(reservation.source_asset_id)
        if (
            reference.asset_id != reservation.source_asset_id
            or reference.sha256 != reservation.source_asset_sha256
        ):
            raise DemoAnalysisRuntimeRejected("D02_SOURCE_AUTHORITY_MISMATCH")
        descriptor = _durable_descriptor(reference)
        content = await self._load_source(reference)
        backend = self._create_backend()
        _validate_backend_bindings(backend)
        prepared = self._prepare(backend, content=content, descriptor=descriptor)
        return _build_evidence(prepared, descriptor=descriptor, reference=reference)

    async def _resolve_reference(self, asset_id: str) -> AdmittedD02SourceReference:
        try:
            return await self._source_resolver.resolve(asset_id)
        except DemoAnalysisSourceAuthorityError as error:
            raise DemoAnalysisRuntimeRejected("D02_SOURCE_AUTHORITY_UNAVAILABLE") from error
        except Exception as error:
            raise DemoAnalysisRuntimeFailed("D03_SOURCE_RESOLUTION_FAILED") from error

    async def _load_source(self, reference: AdmittedD02SourceReference) -> bytes:
        try:
            content = await self._source_loader.load(reference)
        except Exception as error:
            raise DemoAnalysisRuntimeFailed("D03_SOURCE_LOAD_FAILED") from error
        if type(content) is not bytes or len(content) != reference.byte_size:
            raise DemoAnalysisRuntimeFailed("D03_SOURCE_LOAD_FAILED")
        return content

    def _create_backend(self) -> PreparedSourceM3Backend:
        try:
            return self._backend_factory.create()
        except Exception as error:
            raise DemoAnalysisRuntimeFailed("D03_M3_BACKEND_UNAVAILABLE") from error

    @staticmethod
    def _prepare(
        backend: PreparedSourceM3Backend, *, content: bytes, descriptor: DurableSourceDescriptor
    ) -> PreparedSourceM3Group:
        try:
            return backend.prepare_source_group(content=content, descriptor=descriptor)
        except Exception as error:
            raise DemoAnalysisRuntimeFailed("D03_M3_EVIDENCE_INVALID") from error


class DeferredDemoAnalysisRuntime:
    """Expose no fake observations while runtime replay is intentionally deferred."""

    async def observe(self, reservation: DemoAnalysisReservation) -> DemoAnalysisRuntimeEvidence:
        del reservation
        raise DemoAnalysisRuntimeFailed("M3_RUNTIME_REPLAY_NOT_CURRENTLY_MATERIALIZED")


def _validate_reservation_bindings(reservation: DemoAnalysisReservation) -> None:
    model = build_default_model_identity()
    if (
        reservation.runtime_manifest_digest != measurement.RUNTIME_MANIFEST_DIGEST
        or reservation.model_manifest_digest != model.weights_digest_or_no_weights
        or reservation.observation_config_digest != measurement.MEASUREMENT_CONFIG_DIGEST
    ):
        raise DemoAnalysisRuntimeFailed("D03_RUNTIME_BINDING_MISMATCH")


def _durable_descriptor(reference: AdmittedD02SourceReference) -> DurableSourceDescriptor:
    try:
        return reference.durable_descriptor()
    except Exception as error:
        raise DemoAnalysisRuntimeRejected("D02_SOURCE_AUTHORITY_MISMATCH") from error


def _validate_backend_bindings(backend: PreparedSourceM3Backend) -> None:
    model = build_default_model_identity()
    try:
        valid = (
            backend.execution_runtime_set_digest == measurement.RUNTIME_MANIFEST_DIGEST
            and backend.model_identity_digest == model.identity_digest
            and backend.model_config_digest == model.config_digest
            and backend.weights_digest_or_no_weights == model.weights_digest_or_no_weights
            and backend.network_policy == NETWORK_POLICY
        )
    except Exception as error:
        raise DemoAnalysisRuntimeFailed("D03_M3_RUNTIME_BINDING_MISMATCH") from error
    if not valid:
        raise DemoAnalysisRuntimeFailed("D03_M3_RUNTIME_BINDING_MISMATCH")


def _build_evidence(
    prepared: PreparedSourceM3Group,
    *,
    descriptor: DurableSourceDescriptor,
    reference: AdmittedD02SourceReference,
) -> DemoAnalysisRuntimeEvidence:
    try:
        if (
            prepared.descriptor_digest != descriptor.descriptor_digest
            or len(prepared.landmarks) != 478
            or len(prepared.outputs) != 3
        ):
            raise ValueError("prepared M3 group is inconsistent")
        landmarks = tuple(_quantize_landmark(item) for item in prepared.landmarks)
        outputs = tuple(M3ExecutionOutput.create(item) for item in prepared.outputs)
        receipts: set[str] = set()
        repeats: list[DemoAnalysisRepeatEvidence] = []
        for repeat_index, output in enumerate(outputs, start=1):
            _validate_source_output(
                output,
                reference=reference,
                expected_landmark_digest=prepared.landmark_digest,
            )
            fields = output.fields
            receipt = cast(str, fields["execution_receipt_digest"])
            if receipt in receipts:
                raise ValueError("M3 execution receipts must be unique")
            receipts.add(receipt)
            repeats.append(
                DemoAnalysisRepeatEvidence(
                    repeat_index=repeat_index,
                    evidence_reference=_evidence_reference(receipt),
                    landmarks=landmarks,
                    pose=DemoPose(),
                    dimensions=_dimensions_from_observation(
                        cast(Mapping[str, object], fields["measurement_observation"])
                    ),
                    face_count=cast(int, fields["face_count"]),
                )
            )
        return DemoAnalysisRuntimeEvidence(
            repeats=cast(
                tuple[
                    DemoAnalysisRepeatEvidence,
                    DemoAnalysisRepeatEvidence,
                    DemoAnalysisRepeatEvidence,
                ],
                tuple(repeats),
            )
        )
    except (KeyError, TypeError, ValueError, InvalidOperation) as error:
        raise DemoAnalysisRuntimeFailed("D03_M3_EVIDENCE_INVALID") from error


def _validate_source_output(
    output: M3ExecutionOutput,
    *,
    reference: AdmittedD02SourceReference,
    expected_landmark_digest: str,
) -> None:
    fields = output.fields
    if (
        output.payload_schema != R2_SOURCE_M3_SCHEMA
        or fields["runtime_manifest_digest"] != measurement.RUNTIME_MANIFEST_DIGEST
        or fields["vision_model_manifest_digest"] != measurement.VISION_MODEL_MANIFEST_DIGEST
        or fields["topology_digest"] != measurement.TOPOLOGY_DIGEST
        or fields["canonical_output_digest"] != reference.sha256
        or fields["landmark_digest"] != expected_landmark_digest
        or fields["face_count"] != 1
        or fields["landmark_count"] != 478
        or fields["coordinates_finite"] is not True
        or fields["coordinates_in_bounds"] is not True
        or fields["repeat_gate_passed"] is not True
    ):
        raise ValueError("M3 output binding is invalid")
    observation = fields["measurement_observation"]
    verified = d02_authority.validate_measurement_observation(observation, role="SOURCE")
    subject = cast(Mapping[str, object], verified["subject"])
    if (
        subject["source_output_id"] != reference.source_output_id
        or subject["source_asset_id"] != reference.asset_id
        or subject["source_asset_sha256"] != reference.sha256
        or verified["canonical_output_digest"] != reference.sha256
        or verified["landmark_digest"] != expected_landmark_digest
        or verified["measurement_observation_digest"] != fields["measurement_observation_digest"]
    ):
        raise ValueError("M3 observation source binding is invalid")


def _quantize_landmark(value: object) -> DemoLandmark:
    if not isinstance(value, tuple) or len(value) != 3:
        raise ValueError("M3 landmark shape is invalid")
    return DemoLandmark(*(_ppm_from_float(coordinate) for coordinate in value))


def _ppm_from_float(value: object) -> int:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("M3 landmark coordinate is invalid")
    with localcontext() as context:
        context.prec = 50
        scaled = Decimal(str(value)) * Decimal(1_000_000)
        return int(scaled.to_integral_value(rounding=ROUND_HALF_EVEN))


def _dimensions_from_observation(
    observation: Mapping[str, object],
) -> tuple[DimensionObservation, ...]:
    verified = d02_authority.validate_measurement_observation(observation, role="SOURCE")
    entries = cast(list[Mapping[str, object]], verified["ordered_measurements"])
    dimensions: list[DimensionObservation] = []
    for dimension, entry in zip(d02_authority.DIMENSIONS, entries, strict=True):
        support_state = entry["support_state"]
        raw_observability = entry["raw_observability_fixed18"]
        confidence = (
            0
            if raw_observability is None
            else measurement.ppm_from_fixed18(cast(str, raw_observability))
        )
        if support_state == "SUPPORTED":
            dimensions.append(
                DimensionObservation(
                    dimension=dimension,
                    support_state="SUPPORTED",
                    value_ppm=measurement.ppm_from_fixed18(cast(str, entry["raw_value_fixed18"])),
                    measurement_confidence_ppm=confidence,
                )
            )
        elif support_state == "UNSUPPORTED":
            dimensions.append(
                DimensionObservation(
                    dimension=dimension,
                    support_state="UNSUPPORTED",
                    value_ppm=None,
                    measurement_confidence_ppm=confidence,
                    unsupported_reason=cast(str, entry["unsupported_reason"]),
                )
            )
        else:
            raise ValueError("M3 measurement support state is invalid")
    return tuple(dimensions)


def _evidence_reference(receipt_digest: str) -> str:
    raw = bytes.fromhex(receipt_digest)
    return _EVIDENCE_REFERENCE_PREFIX + base64.b32encode(raw).decode("ascii").lower().rstrip("=")
