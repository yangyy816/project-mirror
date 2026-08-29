from __future__ import annotations

import hashlib
import io
import json
import socket
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, cast

import pytest
from PIL import Image, ImageDraw
from test_demo_d02_r2_authority import _report_input_template
from test_demo_d02_r2_epoch2_admission import (
    _asset_rows,
    _epoch2_packet,
    _normalization_fixture,
    _variant_rows,
)
from test_demo_d02_r2_schema_authority import _build_r2_bank_and_pairs
from test_demo_d02_r2_screening_execution import _Adapters
from test_demo_measurement_quality import _landmarks

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as authority
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_r2_epoch2_admission import (
    NormalizedSource,
    build_epoch2_source_authority,
    build_epoch2_source_qa_snapshot,
    build_epoch2_source_record,
    validate_epoch2_admission_packet,
)


def _digest(marker: str) -> str:
    return hashlib.sha256(marker.encode()).hexdigest()


def _jpeg(marker: int) -> bytes:
    image = Image.new("RGB", (32, 32), (30 + marker * 20, 70 + marker * 10, 110))
    draw = ImageDraw.Draw(image)
    draw.rectangle((marker, marker, marker + 7, marker + 7), fill=(200, 20 * marker, 40))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=95, subsampling=0)
    return output.getvalue()


def _packet_with_jpeg(marker: str, ordinal: int, jpeg: bytes) -> dict[str, object]:
    template = _epoch2_packet(marker, ordinal)
    generation_receipt = cast(dict[str, object], template["generation_receipt"])
    source_sha256 = hashlib.sha256(jpeg).hexdigest()
    normalized_template = _normalization_fixture(
        generation_receipt=generation_receipt,
        source_sha256=source_sha256,
        source_byte_size=len(jpeg),
        width=32,
        height=32,
    )
    normalized = NormalizedSource(
        jpeg_bytes=jpeg,
        sha256=source_sha256,
        byte_size=len(jpeg),
        width=32,
        height=32,
        receipt=normalized_template.receipt,
    )
    source_asset_id = cast(
        str,
        cast(dict[str, object], template["identity_row"])["formal_canonical_asset_id"],
    )
    source_authority = build_epoch2_source_authority(
        generation_receipt=generation_receipt,
        normalized_source=normalized,
        source_asset_id=source_asset_id,
    )
    qa = build_epoch2_source_qa_snapshot(
        source_authority=source_authority,
        generation_receipt=generation_receipt,
        qa_policy_digest=_digest(f"runtime-qa-policy-{marker}"),
        decode_record_digest=_digest(f"runtime-decode-{marker}"),
        ordered_review_decision_digests=[
            _digest(f"runtime-review-{marker}-{index}") for index in range(6)
        ],
    )
    supporting = build_epoch2_source_record(
        source_authority=source_authority,
        source_qa_snapshot=qa,
        generation_receipt=generation_receipt,
        created_at="2026-08-29T00:00:00Z",
    )
    source_key = cast(str, supporting["source_authority_key"])
    facts = deepcopy(cast(dict[str, object], template["facts"]))
    facts.update(
        source_asset_sha256=supporting["source_asset_sha256"],
        source_asset_byte_size=supporting["source_asset_byte_size"],
        source_asset_mime_type=supporting["source_asset_mime_type"],
        source_asset_width=supporting["source_asset_width"],
        source_asset_height=supporting["source_asset_height"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
    )
    identity = deepcopy(cast(dict[str, object], template["identity_row"]))
    identity.update(
        formal_canonical_asset_id=supporting["source_asset_id"],
        formal_canonical_asset_sha256=supporting["source_asset_sha256"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
        source_fact_snapshot=facts,
        source_fact_snapshot_digest=authority.digest_r2_facts(facts),
        source_authority_key=source_key,
        r2_source_authority_record_id=supporting["id"],
    )
    identity_canonical = {
        key: value
        for key, value in identity.items()
        if key
        not in {
            "id",
            "schema_version",
            "canonical_payload",
            "content_digest",
            "created_at",
        }
    }
    identity["canonical_payload"] = identity_canonical
    identity["content_digest"] = measurement.mirror_demo_digest(
        authority.R2_IDENTITY_SCHEMA,
        cast(dict[str, measurement.JsonValue], identity_canonical),
    )
    identity["id"] = measurement.mirror_demo_digest(
        authority.R2_IDENTITY_ID_DOMAIN,
        cast(
            dict[str, measurement.JsonValue],
            {
                "source_authority_kind": authority.R2_SOURCE_AUTHORITY_KIND,
                "source_authority_key": source_key,
                "r2_source_authority_record_id": supporting["id"],
                "admission_sequence": identity["admission_sequence"],
                "admission_action": identity["admission_action"],
                "supersedes_id": identity["supersedes_id"],
                "admission_config_digest": identity["admission_config_digest"],
                "canonical_payload_digest": identity["content_digest"],
            },
        ),
    )[:32]
    entry = deepcopy(cast(dict[str, object], template["source_manifest_entry"]))
    entry.update(
        source_authority_key=source_key,
        source_admission_event_id=identity["id"],
        source_admission_content_digest=identity["content_digest"],
        source_output_id=supporting["source_output_id"],
        source_asset_id=supporting["source_asset_id"],
        source_asset_sha256=supporting["source_asset_sha256"],
        source_asset_byte_size=supporting["source_asset_byte_size"],
        source_asset_mime_type=supporting["source_asset_mime_type"],
        source_asset_width=supporting["source_asset_width"],
        source_asset_height=supporting["source_asset_height"],
        source_receipt_digest=supporting["source_generation_receipt_digest"],
        source_authority_digest=supporting["source_authority_digest"],
        source_qa_snapshot_digest=supporting["source_qa_snapshot_digest"],
        source_provenance_digest=supporting["source_provenance_digest"],
        source_fact_snapshot_digest=identity["source_fact_snapshot_digest"],
        r2_source_authority_record_id=supporting["id"],
    )
    entry["record_digest"] = measurement.mirror_demo_digest(
        authority.R2_SOURCE_ENTRY_SCHEMA,
        cast(
            dict[str, measurement.JsonValue],
            {
                key: value
                for key, value in entry.items()
                if key not in {"schema_version", "record_digest"}
            },
        ),
    )
    return {
        "generation_receipt": generation_receipt,
        "source_authority": source_authority,
        "source_qa_snapshot": qa,
        "supporting_row": supporting,
        "facts": facts,
        "identity_row": identity,
        "source_manifest_entry": entry,
        "source_manifest_digest": _digest("pending-runtime-manifest"),
    }


@dataclass(frozen=True)
class _RuntimeInputs:
    packets: tuple[dict[str, object], ...]
    materials: tuple[runtime.SourceMaterial, ...]
    fields: dict[str, object]


def _rebind_packet_measurement(
    packet: dict[str, object], outputs: list[runtime.M3ExecutionOutput]
) -> None:
    observation = deepcopy(cast(dict[str, object], outputs[0].fields["measurement_observation"]))
    repeat_keys = (
        "execution_receipt_digest",
        "canonical_output_digest",
        "landmark_digest",
        "measurement_observation_digest",
        "face_count",
        "landmark_count",
        "coordinates_finite",
        "coordinates_in_bounds",
        "repeat_gate_passed",
    )
    certificate = measurement.build_source_repeat_certification(
        subject=cast(dict[str, object], observation["subject"]),
        bindings=measurement.default_authority_bindings(),
        ordered_repeat_bindings=[
            {
                "repeat_index": repeat_index,
                **{key: output.fields[key] for key in repeat_keys},
            }
            for repeat_index, output in enumerate(outputs, start=1)
        ],
    )
    facts = cast(dict[str, object], packet["facts"])
    raw = legacy.build_raw_measurement_authority(
        observation,
        certificate,
        source_p2_candidate_manifest_content_digest=cast(
            str, facts["source_p2_candidate_manifest_content_digest"]
        ),
        dimension_authority_manifest_content_digest=cast(
            str, facts["dimension_authority_manifest_content_digest"]
        ),
    )
    projection = legacy.build_morphology_projection(raw)
    projection_digest = legacy.digest_morphology_projection(projection)
    facts.update(
        source_landmark_digest=observation["landmark_digest"],
        source_measurement_digest=observation["measurement_observation_digest"],
        source_measurement_projection=projection,
        source_measurement_projection_digest=projection_digest,
        raw_measurement_authority=raw,
        raw_measurement_authority_digest=legacy.digest_raw_measurement_authority(raw),
        measurement_projection_version=projection["measurement_projection_version"],
        measurement_quantization_version=projection["measurement_quantization_version"],
        source_measurement_observation=observation,
        source_measurement_observation_digest=observation["measurement_observation_digest"],
        source_repeat_certification=certificate,
        source_repeat_certification_digest=certificate["source_repeat_certification_digest"],
    )
    identity = cast(dict[str, object], packet["identity_row"])
    identity.update(
        source_landmark_digest=facts["source_landmark_digest"],
        source_measurement_digest=facts["source_measurement_digest"],
        source_fact_snapshot=facts,
        source_fact_snapshot_digest=authority.digest_r2_facts(facts),
        source_measurement_projection=projection,
        source_measurement_projection_digest=projection_digest,
    )
    identity_canonical = {
        key: value
        for key, value in identity.items()
        if key
        not in {
            "id",
            "schema_version",
            "canonical_payload",
            "content_digest",
            "created_at",
        }
    }
    identity["canonical_payload"] = identity_canonical
    identity["content_digest"] = measurement.mirror_demo_digest(
        authority.R2_IDENTITY_SCHEMA,
        cast(dict[str, measurement.JsonValue], identity_canonical),
    )
    supporting = cast(dict[str, object], packet["supporting_row"])
    identity["id"] = measurement.mirror_demo_digest(
        authority.R2_IDENTITY_ID_DOMAIN,
        cast(
            dict[str, measurement.JsonValue],
            {
                "source_authority_kind": authority.R2_SOURCE_AUTHORITY_KIND,
                "source_authority_key": identity["source_authority_key"],
                "r2_source_authority_record_id": supporting["id"],
                "admission_sequence": identity["admission_sequence"],
                "admission_action": identity["admission_action"],
                "supersedes_id": identity["supersedes_id"],
                "admission_config_digest": identity["admission_config_digest"],
                "canonical_payload_digest": identity["content_digest"],
            },
        ),
    )[:32]
    entry = cast(dict[str, object], packet["source_manifest_entry"])
    entry.update(
        source_admission_event_id=identity["id"],
        source_admission_content_digest=identity["content_digest"],
        source_landmark_digest=facts["source_landmark_digest"],
        source_measurement_digest=facts["source_measurement_digest"],
        source_fact_snapshot_digest=identity["source_fact_snapshot_digest"],
        raw_measurement_authority_digest=facts["raw_measurement_authority_digest"],
        source_measurement_projection_digest=projection_digest,
        source_repeat_certification_digest=facts["source_repeat_certification_digest"],
        ordered_supported_measurements=authority._r2_supported_measurements_from_facts(facts),
    )
    entry["record_digest"] = measurement.mirror_demo_digest(
        authority.R2_SOURCE_ENTRY_SCHEMA,
        cast(
            dict[str, measurement.JsonValue],
            {
                key: value
                for key, value in entry.items()
                if key not in {"schema_version", "record_digest"}
            },
        ),
    )


@pytest.fixture(scope="module")
def runtime_inputs() -> _RuntimeInputs:
    packets = tuple(
        _packet_with_jpeg(marker, ordinal, _jpeg(ordinal))
        for ordinal, marker in enumerate("abcd", start=1)
    )
    descriptors = runtime.SourceDescriptorManifest.from_epoch2_packets(packets).descriptors
    materials = tuple(
        runtime.SourceMaterial(descriptor=descriptor, content=_jpeg(index))
        for index, descriptor in enumerate(descriptors, start=1)
    )
    fields, _ = _report_input_template()
    manifest = runtime.SourceDescriptorManifest(descriptors)
    recipe = runtime.build_default_runtime_recipe()
    model = runtime.build_default_model_identity()
    runtime_handle, model_handle = runtime.mint_runtime_handles(
        manifest, recipe=recipe, model_identity=model
    )
    adapters = _Adapters(deepcopy(fields))
    m3 = _SyntheticM3Backend(
        recipe=recipe,
        model=model,
        packets=packets,
        adapters=adapters,
    )
    m4 = _SyntheticM4Backend(recipe=recipe)
    executor = runtime.reconstruct_executor(
        manifest,
        recipe=recipe,
        model_identity=model,
        runtime_handle=runtime_handle,
        model_handle=model_handle,
        m3_backend=m3,
        m4_backend=m4,
    )
    for packet, material in zip(packets, materials, strict=True):
        _rebind_packet_measurement(
            packet,
            [
                executor.inspect_source(material=material, repeat_index=repeat_index)
                for repeat_index in range(1, 4)
            ],
        )
    manifest_digest = legacy._sequence_digest(
        authority.R2_SOURCE_MANIFEST_SCHEMA,
        [cast(dict[str, object], packet["source_manifest_entry"]) for packet in packets],
    )
    for packet in packets:
        packet["source_manifest_digest"] = manifest_digest
        validate_epoch2_admission_packet(packet)
        authority.validate_r2_admission_packet(packet)
    return _RuntimeInputs(packets=packets, materials=materials, fields=fields)


def _observation_digest(observation: dict[str, object]) -> str:
    return measurement.mirror_demo_digest(
        measurement.MEASUREMENT_OBSERVATION_SCHEMA,
        cast(
            dict[str, measurement.JsonValue],
            {
                key: value
                for key, value in observation.items()
                if key not in {"schema_version", "measurement_observation_digest"}
            },
        ),
    )


class _SyntheticM3Backend:
    def __init__(
        self,
        *,
        recipe: runtime.DemoRuntimeRecipe,
        model: runtime.DemoModelIdentity,
        packets: tuple[dict[str, object], ...],
        adapters: _Adapters,
        mode: str = "ok",
    ) -> None:
        self.execution_runtime_set_digest = recipe.runtime_manifest_digest
        self.model_identity_digest = model.identity_digest
        self.model_config_digest = model.config_digest
        self.weights_digest_or_no_weights = model.weights_digest_or_no_weights
        self.network_policy = recipe.network_policy
        self._packets = {
            cast(
                str,
                cast(dict[str, object], packet["supporting_row"])["source_asset_id"],
            ): packet
            for packet in packets
        }
        self._adapters = adapters
        self.mode = mode
        self.source_calls = 0
        self.result_calls = 0

    def _bind_fields(
        self,
        fields: dict[str, object],
        *,
        role: str,
        subject: dict[str, object],
        canonical_output_digest: str,
    ) -> dict[str, object]:
        observation = deepcopy(cast(dict[str, object], fields["measurement_observation"]))
        landmark_digest = cast(str, fields["landmark_digest"])
        if self.mode == "unsupported":
            observation = cast(
                dict[str, object],
                measurement.build_measurement_observation(
                    observation_role=cast(Any, role),
                    subject=subject,
                    canonical_output_digest=canonical_output_digest,
                    landmark_digest=landmark_digest,
                    bindings=measurement.default_authority_bindings(),
                    measurement_landmarks=_landmarks(),
                    ordered_observability_repeats=[deepcopy(_landmarks()) for _ in range(3)],
                    runtime_unsupported_dimensions=("cheekbone_width",),
                ),
            )
        else:
            observation["subject"] = subject
            observation["canonical_output_digest"] = canonical_output_digest
            observation["measurement_observation_digest"] = _observation_digest(observation)
        fields["canonical_output_digest"] = canonical_output_digest
        fields["measurement_observation"] = observation
        fields["measurement_observation_digest"] = observation["measurement_observation_digest"]
        if role == "RESULT":
            entries = cast(list[dict[str, object]], observation["ordered_measurements"])
            fields["observation_state"] = (
                "UNSUPPORTED_EXPLICIT"
                if any(item["support_state"] == "UNSUPPORTED" for item in entries)
                else "SUPPORTED"
            )
        return fields

    def inspect_source(
        self,
        *,
        content: bytes,
        descriptor: runtime.DurableSourceDescriptor,
        repeat_index: int,
    ) -> runtime.BackendM3Result:
        self.source_calls += 1
        packet = self._packets[descriptor.source_id]
        fields = self._adapters.inspect_source(source_packet=packet, repeat_index=repeat_index)
        canonical_digest = hashlib.sha256(content).hexdigest()
        fields = self._bind_fields(
            fields,
            role="SOURCE",
            subject={
                "schema_version": measurement.SOURCE_SUBJECT_SCHEMA,
                "source_output_id": descriptor.source_output_id,
                "source_asset_id": descriptor.source_id,
                "source_asset_sha256": canonical_digest,
            },
            canonical_output_digest=canonical_digest,
        )
        if self.mode == "partial_source":
            fields.pop("landmark_digest")
        payload_schema = (
            authority.R2_RESULT_M3_SCHEMA
            if self.mode == "source_schema_mismatch"
            else authority.R2_SOURCE_M3_SCHEMA
        )
        return runtime.BackendM3Result(payload_schema=payload_schema, fields=fields)

    def inspect_result(
        self,
        *,
        content: bytes,
        case_entry: Mapping[str, object],
        repeat_index: int,
    ) -> runtime.BackendM3Result:
        self.result_calls += 1
        result_sha256 = hashlib.sha256(content).hexdigest()
        result_output_id = f"m4-{case_entry['case_id']}"
        fields = self._adapters.inspect_result(
            case_entry=case_entry,
            m4_record={
                "result_output_id": result_output_id,
                "result_sha256": result_sha256,
            },
            repeat_index=repeat_index,
        )
        fields = self._bind_fields(
            fields,
            role="RESULT",
            subject={
                "schema_version": measurement.RESULT_SUBJECT_SCHEMA,
                "case_id": case_entry["case_id"],
                "case_specification_digest": case_entry["case_specification_digest"],
                "result_output_id": result_output_id,
                "result_sha256": result_sha256,
            },
            canonical_output_digest=result_sha256,
        )
        if self.mode == "partial_result":
            fields.pop("measurement_observation")
        payload_schema = (
            authority.R2_SOURCE_M3_SCHEMA
            if self.mode == "result_schema_mismatch"
            else authority.R2_RESULT_M3_SCHEMA
        )
        return runtime.BackendM3Result(payload_schema=payload_schema, fields=fields)


@dataclass(frozen=True)
class _M4Shape:
    content: bytes
    changed_pixel_count: int
    payload_schema: str


class _SyntheticM4Backend:
    def __init__(self, *, recipe: runtime.DemoRuntimeRecipe, mode: str = "ok") -> None:
        self.execution_runtime_set_digest = recipe.runtime_manifest_digest
        self.algorithm_version = recipe.m4_algorithm_version
        self.network_policy = recipe.network_policy
        self.mode = mode
        self.calls = 0

    def transform(
        self,
        *,
        content: bytes,
        descriptor: runtime.DurableSourceDescriptor,
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> runtime.BackendM4Result:
        del descriptor, replay_index
        self.calls += 1
        if self.mode == "partial_failure":
            raise runtime.RuntimeForwardError("synthetic M4 partial failure")
        with Image.open(io.BytesIO(content)) as image:
            rendered = image.convert("RGB")
        marker = hashlib.sha256(cast(str, case_entry["case_id"]).encode()).digest()
        x = marker[0] % 24
        y = marker[1] % 24
        color = (marker[2], marker[3], marker[4])
        ImageDraw.Draw(rendered).rectangle((x, y, x + 7, y + 7), fill=color)
        output = io.BytesIO()
        rendered.save(output, format="JPEG", quality=95, subsampling=0)
        result = output.getvalue()
        if self.mode == "schema_mismatch":
            return cast(
                runtime.BackendM4Result,
                _M4Shape(
                    content=result,
                    changed_pixel_count=64,
                    payload_schema=authority.R2_SOURCE_M3_SCHEMA,
                ),
            )
        return runtime.BackendM4Result(content=result, changed_pixel_count=64)


@dataclass(frozen=True)
class _ExecutorFixture:
    executor: runtime.DemoM3M4Executor
    m3: _SyntheticM3Backend
    m4: _SyntheticM4Backend
    recipe: runtime.DemoRuntimeRecipe
    model: runtime.DemoModelIdentity
    runtime_handle: runtime.M3RuntimeHandle
    model_handle: runtime.M3ModelHandle


def _executor(
    inputs: _RuntimeInputs, *, m3_mode: str = "ok", m4_mode: str = "ok"
) -> _ExecutorFixture:
    manifest = runtime.SourceDescriptorManifest.from_epoch2_packets(inputs.packets)
    recipe = runtime.build_default_runtime_recipe()
    model = runtime.build_default_model_identity()
    runtime_handle, model_handle = runtime.mint_runtime_handles(
        manifest, recipe=recipe, model_identity=model
    )
    adapters = _Adapters(deepcopy(inputs.fields))
    m3 = _SyntheticM3Backend(
        recipe=recipe,
        model=model,
        packets=inputs.packets,
        adapters=adapters,
        mode=m3_mode,
    )
    m4 = _SyntheticM4Backend(recipe=recipe, mode=m4_mode)
    executor = runtime.reconstruct_executor(
        manifest,
        recipe=recipe,
        model_identity=model,
        runtime_handle=runtime_handle,
        model_handle=model_handle,
        m3_backend=m3,
        m4_backend=m4,
    )
    return _ExecutorFixture(
        executor=executor,
        m3=m3,
        m4=m4,
        recipe=recipe,
        model=model,
        runtime_handle=runtime_handle,
        model_handle=model_handle,
    )


def _case(inputs: _RuntimeInputs, recipe: runtime.DemoRuntimeRecipe) -> dict[str, object]:
    descriptor = inputs.materials[0].descriptor
    return {
        "case_id": _digest("runtime-case")[:32],
        "case_ordinal": 1,
        "case_specification_digest": _digest("runtime-case-specification"),
        "source_asset_id": descriptor.source_id,
        "source_asset_sha256": descriptor.content_sha256,
        "source_ordinal": descriptor.ordinal,
        "runtime_manifest_digest": recipe.runtime_manifest_digest,
        "geometry_algorithm_version": recipe.m4_algorithm_version,
        "output_width": descriptor.width,
        "output_height": descriptor.height,
    }


def test_four_durable_descriptors_and_handles_replay(runtime_inputs: _RuntimeInputs) -> None:
    manifest = runtime.SourceDescriptorManifest.from_epoch2_packets(runtime_inputs.packets)
    recipe = runtime.build_default_runtime_recipe()
    model = runtime.build_default_model_identity()
    first = runtime.mint_runtime_handles(manifest, recipe=recipe, model_identity=model)
    second = runtime.mint_runtime_handles(manifest, recipe=recipe, model_identity=model)
    assert len(manifest.descriptors) == 4
    assert tuple(item.ordinal for item in manifest.descriptors) == (1, 2, 3, 4)
    assert first == second
    assert first[0].handle_digest == second[0].handle_digest
    assert first[1].handle_digest == second[1].handle_digest


@pytest.mark.parametrize("mode", ["missing", "reordered", "duplicate"])
def test_source_count_and_order_fail_closed(runtime_inputs: _RuntimeInputs, mode: str) -> None:
    packets = list(runtime_inputs.packets)
    if mode == "missing":
        packets = packets[:3]
    elif mode == "reordered":
        packets[0], packets[1] = packets[1], packets[0]
    else:
        packets[1] = packets[0]
    with pytest.raises(runtime.RuntimeForwardError):
        runtime.SourceDescriptorManifest.from_epoch2_packets(packets)


@pytest.mark.parametrize("mode", ["digest", "width", "height", "byte_length"])
def test_source_material_descriptor_mismatch_fails_closed(
    runtime_inputs: _RuntimeInputs, mode: str
) -> None:
    material = runtime_inputs.materials[0]
    changes_by_mode: dict[str, dict[str, object]] = {
        "digest": {"content_sha256": _digest("wrong-source")},
        "width": {"width": material.descriptor.width + 1},
        "height": {"height": material.descriptor.height + 1},
        "byte_length": {"byte_length": material.descriptor.byte_length + 1},
    }
    descriptor = replace(material.descriptor, **changes_by_mode[mode])
    with pytest.raises(runtime.RuntimeForwardError):
        runtime.SourceMaterial(descriptor=descriptor, content=material.content)


def test_media_type_and_non_jpeg_fail_closed(runtime_inputs: _RuntimeInputs) -> None:
    descriptor = runtime_inputs.materials[0].descriptor
    with pytest.raises(runtime.RuntimeForwardError, match="canonical JPEG"):
        replace(descriptor, media_type="image/png")
    png_output = io.BytesIO()
    Image.new("RGB", (32, 32), (1, 2, 3)).save(png_output, format="PNG")
    png = png_output.getvalue()
    forged = replace(
        descriptor,
        content_sha256=hashlib.sha256(png).hexdigest(),
        byte_length=len(png),
    )
    with pytest.raises(runtime.RuntimeForwardError, match="JPEG envelope"):
        runtime.SourceMaterial(descriptor=forged, content=png)


@pytest.mark.parametrize("kind", ["recipe", "config", "weights"])
def test_recipe_and_model_identity_mismatch_fail_closed(
    runtime_inputs: _RuntimeInputs, kind: str
) -> None:
    manifest = runtime.SourceDescriptorManifest.from_epoch2_packets(runtime_inputs.packets)
    recipe = runtime.build_default_runtime_recipe()
    model = runtime.build_default_model_identity()
    if kind == "recipe":
        recipe = replace(recipe, recipe_version="demo-m3-m4-runtime-recipe-v2")
    elif kind == "config":
        model = replace(model, config_digest=_digest("other-model-config"))
    else:
        model = replace(model, weights_digest_or_no_weights=_digest("other-model-weights"))
    with pytest.raises(runtime.RuntimeForwardError, match="accepted Demo-only"):
        runtime.mint_runtime_handles(manifest, recipe=recipe, model_identity=model)


@pytest.mark.parametrize("kind", ["runtime_handle", "model_handle", "backend_identity"])
def test_tampered_handles_and_backend_identity_fail_closed(
    runtime_inputs: _RuntimeInputs, kind: str
) -> None:
    fixture = _executor(runtime_inputs)
    runtime_handle = fixture.runtime_handle
    model_handle = fixture.model_handle
    if kind == "runtime_handle":
        runtime_handle = replace(runtime_handle, recipe_digest=_digest("tampered-recipe"))
    elif kind == "model_handle":
        model_handle = replace(model_handle, model_config_digest=_digest("tampered-model"))
    else:
        fixture.m3.model_config_digest = _digest("tampered-backend")
    with pytest.raises(runtime.RuntimeForwardError):
        runtime.reconstruct_executor(
            fixture.executor.manifest,
            recipe=fixture.recipe,
            model_identity=fixture.model,
            runtime_handle=runtime_handle,
            model_handle=model_handle,
            m3_backend=fixture.m3,
            m4_backend=fixture.m4,
        )


def test_m3_execution_supported_and_unsupported(runtime_inputs: _RuntimeInputs) -> None:
    supported = _executor(runtime_inputs)
    output = supported.executor.inspect_source(material=runtime_inputs.materials[0], repeat_index=1)
    assert (
        output.fields["canonical_output_digest"]
        == runtime_inputs.materials[0].descriptor.content_sha256
    )
    assert output.fields["repeat_gate_passed"] is True
    assert supported.m3.source_calls == 1

    unsupported = _executor(runtime_inputs, m3_mode="unsupported")
    unsupported_output = unsupported.executor.inspect_source(
        material=runtime_inputs.materials[0], repeat_index=1
    )
    observation = cast(dict[str, object], unsupported_output.fields["measurement_observation"])
    entries = cast(list[dict[str, object]], observation["ordered_measurements"])
    assert entries[0]["support_state"] == "UNSUPPORTED"


@pytest.mark.parametrize("mode", ["partial_source", "source_schema_mismatch"])
def test_m3_partial_and_schema_failure(runtime_inputs: _RuntimeInputs, mode: str) -> None:
    fixture = _executor(runtime_inputs, m3_mode=mode)
    with pytest.raises(runtime.RuntimeForwardError):
        fixture.executor.inspect_source(material=runtime_inputs.materials[0], repeat_index=1)


@pytest.mark.parametrize("mode", ["partial_result", "result_schema_mismatch"])
def test_m3_result_partial_and_schema_failure(runtime_inputs: _RuntimeInputs, mode: str) -> None:
    fixture = _executor(runtime_inputs, m3_mode=mode)
    case = _case(runtime_inputs, fixture.recipe)
    transformed = fixture.executor.transform(
        material=runtime_inputs.materials[0], case_entry=case, replay_index=1
    )
    with pytest.raises(runtime.RuntimeForwardError):
        fixture.executor.inspect_result(output=transformed, case_entry=case, repeat_index=1)


def test_m4_execution_and_deterministic_replay(runtime_inputs: _RuntimeInputs) -> None:
    fixture = _executor(runtime_inputs)
    case = _case(runtime_inputs, fixture.recipe)
    first = fixture.executor.transform(
        material=runtime_inputs.materials[0], case_entry=case, replay_index=1
    )
    second = fixture.executor.transform(
        material=runtime_inputs.materials[0], case_entry=case, replay_index=2
    )
    assert first.content == second.content
    assert first.result_sha256 == second.result_sha256
    assert first.result_output_id == second.result_output_id
    assert first.execution_receipt_digest != second.execution_receipt_digest
    assert fixture.m4.calls == 2
    result = fixture.executor.inspect_result(output=first, case_entry=case, repeat_index=1)
    assert result.fields["canonical_output_digest"] == first.result_sha256


@pytest.mark.parametrize("mode", ["partial_failure", "schema_mismatch"])
def test_m4_partial_and_schema_failure(runtime_inputs: _RuntimeInputs, mode: str) -> None:
    fixture = _executor(runtime_inputs, m4_mode=mode)
    with pytest.raises(runtime.RuntimeForwardError):
        fixture.executor.transform(
            material=runtime_inputs.materials[0],
            case_entry=_case(runtime_inputs, fixture.recipe),
            replay_index=1,
        )


@dataclass(frozen=True)
class _ScreeningFixture:
    result: runtime.RuntimeScreeningResult
    m3: _SyntheticM3Backend
    m4: _SyntheticM4Backend


class _RuntimeCaseFields:
    def __init__(self, *, adapters: _Adapters, recipe: runtime.DemoRuntimeRecipe) -> None:
        self._adapters = adapters
        self._recipe = recipe

    def case_fields(
        self,
        *,
        source_packet: Mapping[str, object],
        source_entry: Mapping[str, object],
        case_ordinal: int,
        dimension_key: str,
        direction: str,
        magnitude_ppm: int,
    ) -> Mapping[str, object]:
        fields = self._adapters.case_fields(
            source_packet=source_packet,
            source_entry=source_entry,
            case_ordinal=case_ordinal,
            dimension_key=dimension_key,
            direction=direction,
            magnitude_ppm=magnitude_ppm,
        )
        fields["geometry_algorithm_version"] = self._recipe.m4_algorithm_version
        fields["output_width"] = source_entry["source_asset_width"]
        fields["output_height"] = source_entry["source_asset_height"]
        return fields


def _screen(inputs: _RuntimeInputs, *, failing_manual: bool = False) -> _ScreeningFixture:
    manifest = runtime.SourceDescriptorManifest.from_epoch2_packets(inputs.packets)
    recipe = runtime.build_default_runtime_recipe()
    model = runtime.build_default_model_identity()
    runtime_handle, model_handle = runtime.mint_runtime_handles(
        manifest, recipe=recipe, model_identity=model
    )
    adapters = _Adapters(deepcopy(inputs.fields))
    adapters.failing_manual = failing_manual
    m3 = _SyntheticM3Backend(
        recipe=recipe,
        model=model,
        packets=inputs.packets,
        adapters=adapters,
    )
    m4 = _SyntheticM4Backend(recipe=recipe)
    payload = cast(dict[str, object], inputs.fields["report_payload"])
    result = runtime.run_runtime_screening(
        runtime.RuntimeScreeningRequest(
            created_at=cast(str, inputs.fields["created_at"]),
            source_packets=inputs.packets,
            source_materials=inputs.materials,
            execution_authority=cast(dict[str, object], payload["schema_and_policy"]),
            recipe=recipe,
            model_identity=model,
            runtime_handle=runtime_handle,
            model_handle=model_handle,
            m3_backend=m3,
            m4_backend=m4,
            case_fields=_RuntimeCaseFields(adapters=adapters, recipe=recipe),
            measurement_gate=adapters,
            manual_review=adapters,
            phash=adapters,
        )
    )
    return _ScreeningFixture(result=result, m3=m3, m4=m4)


@pytest.fixture(scope="module")
def successful_screening(runtime_inputs: _RuntimeInputs) -> _ScreeningFixture:
    return _screen(runtime_inputs)


def test_screening_bridge_reuses_complete_contract(
    successful_screening: _ScreeningFixture,
) -> None:
    result = successful_screening.result
    assert result.report_row["status"] == "PASSED"
    assert result.report_row["source_count"] == 4
    assert result.report_row["case_count"] == 48
    assert result.report_row["m4_execution_count"] == 96
    assert result.report_row["result_m3_repeat_count"] == 144
    assert result.report_row["selected_pair_count"] == 16
    assert result.report_row["selected_result_side_count"] == 32
    assert len(result.result_outputs) == 48
    assert result.admission_ready is True
    assert successful_screening.m3.source_calls == 12
    assert successful_screening.m3.result_calls == 144
    assert successful_screening.m4.calls == 96


def test_failed_screening_cannot_create_admission_bundle(
    runtime_inputs: _RuntimeInputs,
) -> None:
    failed = _screen(runtime_inputs, failing_manual=True).result
    assert failed.report_row["status"] == "FAILED"
    assert failed.admission_ready is False
    with pytest.raises(runtime.RuntimeForwardError, match="not eligible"):
        runtime.build_epoch2_admission_bundle(
            failed,
            asset_rows=(),
            asset_variant_rows=(),
            question_bank_row={},
            question_pair_rows=(),
        )


def test_result_builds_existing_epoch2_admission_bundle(
    runtime_inputs: _RuntimeInputs,
    successful_screening: _ScreeningFixture,
) -> None:
    report = cast(dict[str, object], successful_screening.result.report_row)
    packets = list(runtime_inputs.packets)
    bank, pairs = _build_r2_bank_and_pairs(report, packets)
    bundle = runtime.build_epoch2_admission_bundle(
        successful_screening.result,
        asset_rows=_asset_rows(report, packets),
        asset_variant_rows=_variant_rows(report),
        question_bank_row=bank,
        question_pair_rows=pairs,
    )
    assert len(bundle.source_packets) == 4
    assert len(bundle.asset_rows) == 52
    assert len(bundle.asset_variant_rows) == 48
    assert len(bundle.question_pair_rows) == 16


def test_no_network_execution(
    runtime_inputs: _RuntimeInputs, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(*_: object, **__: object) -> None:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    fixture = _executor(runtime_inputs)
    source = fixture.executor.inspect_source(material=runtime_inputs.materials[0], repeat_index=1)
    result = fixture.executor.transform(
        material=runtime_inputs.materials[0],
        case_entry=_case(runtime_inputs, fixture.recipe),
        replay_index=1,
    )
    assert source.fields["repeat_gate_passed"] is True
    assert result.execution_succeeded is True


def test_public_handles_do_not_leak_private_material(
    runtime_inputs: _RuntimeInputs,
) -> None:
    fixture = _executor(runtime_inputs)
    descriptor = runtime_inputs.materials[0].descriptor
    public = json.dumps(
        {
            "descriptor": descriptor.payload(),
            "recipe": fixture.recipe.payload(),
            "model": fixture.model.payload(),
            "runtime_handle": fixture.runtime_handle.payload(),
            "model_handle": fixture.model_handle.payload(),
        },
        sort_keys=True,
    ).lower()
    for forbidden in (
        "prompt",
        "private_locator",
        "absolute_path",
        "raw_bytes",
        "image_bytes",
    ):
        assert forbidden not in public
    assert "content=" not in repr(runtime_inputs.materials[0])
    with pytest.raises(runtime.RuntimeForwardError, match="forbidden field"):
        runtime.BackendM3Result(
            payload_schema=authority.R2_SOURCE_M3_SCHEMA,
            fields={"prompt": "forbidden"},
        )
