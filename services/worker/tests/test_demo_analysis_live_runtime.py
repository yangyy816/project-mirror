from __future__ import annotations

import hashlib
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from mirror_api import demo_d02_generic_admission as admission
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_analysis_service import DemoAnalysisReservation
from mirror_api.demo_analysis_source_authority import (
    AdmittedD02SourceReference,
    DemoAnalysisSourceAuthorityError,
)
from mirror_api.demo_d02_r2_authority import R2_SOURCE_M3_SCHEMA
from mirror_api.demo_d02_r2_runtime_forward import (
    NETWORK_POLICY,
    BackendM3Result,
    DurableSourceDescriptor,
    build_default_model_identity,
)
from PIL import Image

from mirror_worker.demo_analysis import DemoAnalysisRuntimeFailed, DemoAnalysisRuntimeRejected
from mirror_worker.demo_analysis_runtime import LiveDemoAnalysisRuntime

_ASSET_ID = "a" * 32
_SOURCE_SHA = ""


def _jpeg() -> bytes:
    image = Image.new("RGB", (2, 2), color=(12, 34, 56))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


_CONTENT = _jpeg()
_SOURCE_SHA = hashlib.sha256(_CONTENT).hexdigest()


def _reference() -> AdmittedD02SourceReference:
    return AdmittedD02SourceReference(
        asset_id=_ASSET_ID,
        storage_key=f"internal-synthetic/v1/d02/source/{_ASSET_ID}",
        sha256=_SOURCE_SHA,
        byte_size=len(_CONTENT),
        mime_type="image/jpeg",
        width=2,
        height=2,
        source_authority_digest="b" * 64,
        source_output_id="d02-source-1",
        source_ordinal=1,
        generation_request_identity="c" * 64,
        source_provenance_digest="d" * 64,
        source_authority_key="e" * 64,
        source_schema_version=admission.SOURCE_SCHEMA,
    )


def _reservation(**changes: object) -> DemoAnalysisReservation:
    model = build_default_model_identity()
    values: dict[str, object] = {
        "analysis_run_id": "1" * 32,
        "job_id": "2" * 32,
        "attempt_id": "3" * 32,
        "attempt": 1,
        "lease_token": "4" * 64,
        "lease_expires_at": datetime(2026, 9, 3, tzinfo=UTC) + timedelta(minutes=5),
        "request_id": "d03-live-runtime-test",
        "demo_actor_id": "5" * 32,
        "demo_session_id": "6" * 32,
        "demo_synthetic_identity_id": "7" * 32,
        "source_asset_id": _ASSET_ID,
        "source_asset_sha256": _SOURCE_SHA,
        "analyzer_version": "demo-face-observation-v1",
        "runtime_manifest_digest": measurement.RUNTIME_MANIFEST_DIGEST,
        "model_manifest_digest": model.weights_digest_or_no_weights,
        "observation_config_digest": measurement.MEASUREMENT_CONFIG_DIGEST,
    }
    values.update(changes)
    return DemoAnalysisReservation(**values)  # type: ignore[arg-type]


def _measurement_landmarks() -> dict[int, dict[str, str]]:
    points = {index: {"x": "0.500000", "y": "0.500000"} for index in range(478)}
    points.update(
        {
            10: {"x": "0.500000", "y": "0.100000"},
            17: {"x": "0.500000", "y": "0.800000"},
            61: {"x": "0.200000", "y": "0.400000"},
            98: {"x": "0.300000", "y": "0.500000"},
            123: {"x": "0.200000", "y": "0.300000"},
            133: {"x": "0.350000", "y": "0.400000"},
            152: {"x": "0.500000", "y": "0.900000"},
            234: {"x": "0.150000", "y": "0.700000"},
            291: {"x": "0.800000", "y": "0.400000"},
            327: {"x": "0.700000", "y": "0.500000"},
            352: {"x": "0.800000", "y": "0.300000"},
            362: {"x": "0.650000", "y": "0.400000"},
            454: {"x": "0.850000", "y": "0.700000"},
        }
    )
    return points


def _output(
    *,
    reference: AdmittedD02SourceReference,
    receipt: str,
    landmark_digest: str,
    unsupported: tuple[str, ...] = (),
) -> BackendM3Result:
    subject = {
        "schema_version": measurement.SOURCE_SUBJECT_SCHEMA,
        "source_output_id": reference.source_output_id,
        "source_asset_id": reference.asset_id,
        "source_asset_sha256": reference.sha256,
    }
    points = _measurement_landmarks()
    observation = measurement.build_measurement_observation(
        observation_role="SOURCE",
        subject=subject,
        canonical_output_digest=reference.sha256,
        landmark_digest=landmark_digest,
        bindings=measurement.default_authority_bindings(),
        measurement_landmarks=points,
        ordered_observability_repeats=(points, points, points),
        runtime_unsupported_dimensions=unsupported,
    )
    return BackendM3Result(
        payload_schema=R2_SOURCE_M3_SCHEMA,
        fields={
            "execution_receipt_digest": receipt,
            "vision_model_manifest_digest": measurement.VISION_MODEL_MANIFEST_DIGEST,
            "runtime_manifest_digest": measurement.RUNTIME_MANIFEST_DIGEST,
            "topology_digest": measurement.TOPOLOGY_DIGEST,
            "canonical_output_digest": reference.sha256,
            "landmark_digest": landmark_digest,
            "measurement_observation": observation,
            "measurement_observation_digest": observation["measurement_observation_digest"],
            "face_count": 1,
            "landmark_count": 478,
            "coordinates_finite": True,
            "coordinates_in_bounds": True,
            "repeat_gate_passed": True,
        },
    )


@dataclass
class _Group:
    descriptor_digest: str
    landmark_digest: str
    landmarks: tuple[tuple[float, float, float], ...]
    outputs: tuple[BackendM3Result, BackendM3Result, BackendM3Result]


class _Backend:
    def __init__(
        self,
        reference: AdmittedD02SourceReference,
        *,
        mutate: Callable[[_Group], None] | None = None,
        runtime_digest: str = measurement.RUNTIME_MANIFEST_DIGEST,
    ) -> None:
        model = build_default_model_identity()
        self.execution_runtime_set_digest = runtime_digest
        self.model_identity_digest = model.identity_digest
        self.model_config_digest = model.config_digest
        self.weights_digest_or_no_weights = model.weights_digest_or_no_weights
        self.network_policy = NETWORK_POLICY
        self._reference = reference
        self._mutate = mutate
        self.prepare_calls = 0
        self.real_output_calls = 0

    def prepare_source_group(
        self, *, content: bytes, descriptor: DurableSourceDescriptor
    ) -> _Group:
        assert content == _CONTENT
        assert descriptor == self._reference.durable_descriptor()
        self.prepare_calls += 1
        self.real_output_calls += 3
        digest = "f" * 64
        group = _Group(
            descriptor_digest=descriptor.descriptor_digest,
            landmark_digest=digest,
            landmarks=((0.0000005, 0.0000015, 0.0),) + ((0.5, 0.5, 0.0),) * 477,
            outputs=tuple(
                _output(
                    reference=self._reference,
                    receipt=f"{index:x}" * 64,
                    landmark_digest=digest,
                    unsupported=("nose_width",),
                )
                for index in (1, 2, 3)
            ),
        )
        if self._mutate is not None:
            self._mutate(group)
        return group


class _Factory:
    def __init__(self, reference: AdmittedD02SourceReference, **backend_kwargs: object) -> None:
        self._reference = reference
        self._backend_kwargs = backend_kwargs
        self.backends: list[_Backend] = []

    def create(self) -> _Backend:
        backend = _Backend(self._reference, **self._backend_kwargs)  # type: ignore[arg-type]
        self.backends.append(backend)
        return backend


class _Resolver:
    def __init__(
        self, reference: AdmittedD02SourceReference, error: Exception | None = None
    ) -> None:
        self.reference = reference
        self.error = error
        self.calls = 0

    async def resolve(self, asset_id: str) -> AdmittedD02SourceReference:
        self.calls += 1
        assert asset_id == _ASSET_ID
        if self.error is not None:
            raise self.error
        return self.reference


class _Loader:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    async def load(self, reference: AdmittedD02SourceReference) -> bytes:
        self.calls += 1
        assert reference == _reference()
        if self.error is not None:
            raise self.error
        return _CONTENT


def _runtime(
    *,
    resolver: _Resolver | None = None,
    loader: _Loader | None = None,
    factory: _Factory | None = None,
) -> tuple[LiveDemoAnalysisRuntime, _Resolver, _Loader, _Factory]:
    reference = _reference()
    actual_resolver = resolver or _Resolver(reference)
    actual_loader = loader or _Loader()
    actual_factory = factory or _Factory(reference)
    return (
        LiveDemoAnalysisRuntime(
            source_resolver=actual_resolver,
            source_loader=actual_loader,
            backend_factory=actual_factory,
        ),
        actual_resolver,
        actual_loader,
        actual_factory,
    )


@pytest.mark.asyncio
async def test_live_runtime_uses_one_public_source_and_fresh_three_output_backend_per_attempt() -> (
    None
):
    runtime, resolver, loader, factory = _runtime()

    evidence = await runtime.observe(_reservation())
    assert (resolver.calls, loader.calls, len(factory.backends)) == (1, 1, 1)
    assert (factory.backends[0].prepare_calls, factory.backends[0].real_output_calls) == (1, 3)
    assert [repeat.repeat_index for repeat in evidence.repeats] == [1, 2, 3]
    assert all(
        len(repeat.landmarks) == 478 and repeat.face_count == 1 for repeat in evidence.repeats
    )
    assert evidence.repeats[0].landmarks[0].payload() == {"x_ppm": 0, "y_ppm": 2, "z_ppm": 0}
    assert len({repeat.evidence_reference for repeat in evidence.repeats}) == 3
    assert all(
        reference.startswith("d03m3r_") and len(reference) == 59
        for reference in (repeat.evidence_reference for repeat in evidence.repeats)
    )
    nose = next(
        entry for entry in evidence.repeats[0].dimensions if entry.dimension == "nose_width"
    )
    assert (
        nose.support_state,
        nose.value_ppm,
        nose.measurement_confidence_ppm,
        nose.unsupported_reason,
    ) == (
        "UNSUPPORTED",
        None,
        0,
        "RUNTIME_UNSUPPORTED",
    )
    supported = next(
        entry for entry in evidence.repeats[0].dimensions if entry.dimension == "jaw_width"
    )
    assert supported.support_state == "SUPPORTED" and supported.value_ppm is not None
    assert supported.measurement_confidence_ppm > 0

    await runtime.observe(_reservation(attempt_id="8" * 32, attempt=2))
    assert len(factory.backends) == 2
    assert factory.backends[0] is not factory.backends[1]
    assert all(backend.real_output_calls == 3 for backend in factory.backends)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda group: setattr(group, "descriptor_digest", "0" * 64), "D03_M3_EVIDENCE_INVALID"),
        (
            lambda group: setattr(group, "landmarks", group.landmarks[:-1]),
            "D03_M3_EVIDENCE_INVALID",
        ),
        (
            lambda group: setattr(group, "landmarks", ((float("nan"), 0.0, 0.0),) * 478),
            "D03_M3_EVIDENCE_INVALID",
        ),
    ],
)
async def test_live_runtime_fails_closed_for_prepared_group_tampering(
    mutation: Callable[[_Group], None], expected_code: str
) -> None:
    reference = _reference()
    runtime, _, _, _ = _runtime(factory=_Factory(reference, mutate=mutation))
    with pytest.raises(DemoAnalysisRuntimeFailed) as raised:
        await runtime.observe(_reservation())
    assert raised.value.code == expected_code
    assert "private" not in str(raised.value)


@pytest.mark.asyncio
async def test_live_runtime_fails_closed_for_output_and_runtime_binding_tampering() -> None:
    reference = _reference()

    def change_output(group: _Group) -> None:
        changed = dict(group.outputs[0].fields)
        changed["canonical_output_digest"] = "0" * 64
        group.outputs = (
            BackendM3Result(payload_schema=R2_SOURCE_M3_SCHEMA, fields=changed),
            group.outputs[1],
            group.outputs[2],
        )

    runtime, _, _, _ = _runtime(factory=_Factory(reference, mutate=change_output))
    with pytest.raises(DemoAnalysisRuntimeFailed, match="failed") as raised:
        await runtime.observe(_reservation())
    assert raised.value.code == "D03_M3_EVIDENCE_INVALID"

    def change_measurement_and_subject(group: _Group) -> None:
        changed = dict(group.outputs[0].fields)
        changed["measurement_observation"] = {"subject": {"source_asset_id": "0" * 32}}
        changed["measurement_observation_digest"] = "0" * 64
        group.outputs = (
            BackendM3Result(payload_schema=R2_SOURCE_M3_SCHEMA, fields=changed),
            group.outputs[1],
            group.outputs[2],
        )

    runtime, _, _, _ = _runtime(factory=_Factory(reference, mutate=change_measurement_and_subject))
    with pytest.raises(DemoAnalysisRuntimeFailed) as raised:
        await runtime.observe(_reservation())
    assert raised.value.code == "D03_M3_EVIDENCE_INVALID"

    def duplicate_receipt(group: _Group) -> None:
        changed = dict(group.outputs[0].fields)
        changed["execution_receipt_digest"] = group.outputs[1].fields["execution_receipt_digest"]
        group.outputs = (
            BackendM3Result(payload_schema=R2_SOURCE_M3_SCHEMA, fields=changed),
            group.outputs[1],
            group.outputs[2],
        )

    runtime, _, _, _ = _runtime(factory=_Factory(reference, mutate=duplicate_receipt))
    with pytest.raises(DemoAnalysisRuntimeFailed) as raised:
        await runtime.observe(_reservation())
    assert raised.value.code == "D03_M3_EVIDENCE_INVALID"

    runtime, _, _, factory = _runtime(factory=_Factory(reference, runtime_digest="0" * 64))
    with pytest.raises(DemoAnalysisRuntimeFailed) as raised:
        await runtime.observe(_reservation())
    assert raised.value.code == "D03_M3_RUNTIME_BINDING_MISMATCH"
    assert factory.backends[0].prepare_calls == 0


@pytest.mark.asyncio
async def test_live_runtime_rejects_missing_authority_and_never_leaks_error_detail() -> None:
    resolver = _Resolver(
        _reference(),
        error=DemoAnalysisSourceAuthorityError("D02_SOURCE_AUTHORITY_UNAVAILABLE", "C:/secret"),
    )
    loader = _Loader()
    runtime, _, _, factory = _runtime(resolver=resolver, loader=loader)
    with pytest.raises(DemoAnalysisRuntimeRejected) as raised:
        await runtime.observe(_reservation())
    assert raised.value.code == "D02_SOURCE_AUTHORITY_UNAVAILABLE"
    assert "secret" not in str(raised.value)
    assert (resolver.calls, loader.calls, len(factory.backends)) == (1, 0, 0)


@pytest.mark.asyncio
async def test_live_runtime_rejects_reservation_and_source_tampering_before_backend_execution() -> (
    None
):
    runtime, resolver, loader, factory = _runtime()
    with pytest.raises(DemoAnalysisRuntimeFailed) as raised:
        await runtime.observe(_reservation(runtime_manifest_digest="0" * 64))
    assert raised.value.code == "D03_RUNTIME_BINDING_MISMATCH"
    assert (resolver.calls, loader.calls, len(factory.backends)) == (0, 0, 0)

    changed = _reference()
    object.__setattr__(changed, "sha256", "0" * 64)
    runtime, resolver, loader, factory = _runtime(resolver=_Resolver(changed))
    with pytest.raises(DemoAnalysisRuntimeRejected) as raised:
        await runtime.observe(_reservation())
    assert raised.value.code == "D02_SOURCE_AUTHORITY_MISMATCH"
    assert (resolver.calls, loader.calls, len(factory.backends)) == (1, 0, 0)


def test_live_runtime_has_no_private_backend_or_result_store_dependency() -> None:
    source = Path(__file__).parents[1] / "src/mirror_worker/demo_analysis_runtime.py"
    text = source.read_text(encoding="utf-8")
    assert "demo_d02_private" not in text
    assert "DemoD02R2SourceAuthority" not in text
    assert "ResultM3" not in text
