from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace

import pytest

from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_targeted_m4_repair_backend as backend
from mirror_api.image_sanitizer import canonicalize_rgb_image, decode_canonical_rgb_image


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _content() -> bytes:
    width = height = 96
    pixels = bytes(
        component
        for y in range(height)
        for x in range(width)
        for component in ((x * 13 + y * 7) % 256, (x * 3 + y * 17) % 256, (x * y) % 256)
    )
    return canonicalize_rgb_image(pixels, width=width, height=height).bytes_value


def _material() -> runtime.SourceMaterial:
    content = _content()
    descriptor = runtime.DurableSourceDescriptor(
        source_id="3" * 32,
        source_output_id="source-3",
        ordinal=3,
        content_sha256=hashlib.sha256(content).hexdigest(),
        media_type="image/jpeg",
        width=96,
        height=96,
        byte_length=len(content),
        generation_request_identity=_digest("generation"),
        provenance_identity=_digest("provenance"),
        source_authority_key=_digest("authority"),
        source_schema_version="d02-source-v1",
    )
    return runtime.SourceMaterial(descriptor=descriptor, content=content)


def _entry(material: runtime.SourceMaterial) -> dict[str, object]:
    descriptor = material.descriptor
    return {
        "source_asset_id": descriptor.source_id,
        "source_output_id": descriptor.source_output_id,
        "source_asset_sha256": descriptor.content_sha256,
        "source_ordinal": descriptor.ordinal,
        "source_asset_mime_type": descriptor.media_type,
        "source_asset_width": descriptor.width,
        "source_asset_height": descriptor.height,
        "source_asset_byte_size": descriptor.byte_length,
        "source_authority_key": descriptor.source_authority_key,
    }


def _case(
    instance: backend.D02TargetedM4RepairBackend, material: runtime.SourceMaterial
) -> dict[str, object]:
    entry = _entry(material)
    packet: Mapping[str, object] = {
        "source_manifest_entry": dict(entry),
        "supporting_row": dict(entry),
    }
    return {
        **entry,
        "case_ordinal": 25,
        "dimension_key": "jaw_width",
        "direction": "DECREASE",
        "magnitude_ppm": 15_000,
        **instance.case_fields(
            source_packet=packet,
            source_entry=entry,
            case_ordinal=25,
            dimension_key="jaw_width",
            direction="DECREASE",
            magnitude_ppm=15_000,
        ),
        "case_id": "2" * 32,
        "case_specification_digest": _digest("case"),
    }


def test_targeted_repair_is_deterministic_canonical_and_replay_limited() -> None:
    material = _material()
    first_backend = backend.D02TargetedM4RepairBackend(material=material)
    first_case = _case(first_backend, material)
    first = first_backend.transform(
        content=material.content,
        descriptor=material.descriptor,
        case_entry=first_case,
        replay_index=1,
    )
    second = first_backend.transform(
        content=material.content,
        descriptor=material.descriptor,
        case_entry=first_case,
        replay_index=2,
    )
    replay_backend = backend.D02TargetedM4RepairBackend(material=material)
    replay = replay_backend.transform(
        content=material.content,
        descriptor=material.descriptor,
        case_entry=_case(replay_backend, material),
        replay_index=1,
    )

    assert first.content == second.content == replay.content
    assert first.changed_pixel_count == second.changed_pixel_count == replay.changed_pixel_count
    assert first.changed_pixel_count > 0
    decoded = decode_canonical_rgb_image(first.content, expected_width=96, expected_height=96)
    assert decoded.width == decoded.height == 96
    assert first.content.startswith(b"\xff\xd8\xff")

    with pytest.raises(backend.TargetedM4RepairError):
        first_backend.transform(
            content=material.content,
            descriptor=material.descriptor,
            case_entry=first_case,
            replay_index=2,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_ordinal", 24),
        ("dimension_key", "chin_height"),
        ("direction", "INCREASE"),
        ("magnitude_ppm", 30_000),
    ],
)
def test_case_fields_reject_every_non_target_selector(field: str, value: object) -> None:
    material = _material()
    instance = backend.D02TargetedM4RepairBackend(material=material)
    entry = _entry(material)
    values: dict[str, object] = {
        "case_ordinal": 25,
        "dimension_key": "jaw_width",
        "direction": "DECREASE",
        "magnitude_ppm": 15_000,
    }
    values[field] = value
    with pytest.raises(backend.TargetedM4RepairError):
        instance.case_fields(
            source_packet={"source_manifest_entry": entry, "supporting_row": entry},
            source_entry=entry,
            **values,  # type: ignore[arg-type]
        )


def test_transform_rejects_tamper_substitution_and_does_not_echo_private_values() -> None:
    material = _material()
    instance = backend.D02TargetedM4RepairBackend(material=material)
    case = _case(instance, material)
    tampered = dict(case)
    tampered["warp_plan_digest"] = _digest("tampered")
    altered = bytearray(material.content)
    altered[-4] ^= 0x01
    substituted_descriptor = replace(material.descriptor, source_id="4" * 32)

    for kwargs in (
        {"case_entry": tampered, "content": material.content},
        {"case_entry": case, "content": bytes(altered)},
        {"case_entry": case, "content": material.content, "descriptor": substituted_descriptor},
    ):
        with pytest.raises(backend.TargetedM4RepairError) as raised:
            descriptor = kwargs.pop("descriptor", material.descriptor)
            instance.transform(
                descriptor=descriptor,
                replay_index=1,
                **kwargs,
            )
        assert "private" not in str(raised.value).lower()
        assert "\\" not in str(raised.value)
        assert "ff" not in str(raised.value).lower()


def test_config_and_case_digests_are_versioned_and_configuration_bound() -> None:
    material = _material()
    default = backend.D02TargetedM4RepairBackend(material=material)
    tuned_config = backend.TargetedJawRepairConfig(strength_ppm=50_000)
    tuned = backend.D02TargetedM4RepairBackend(material=material, config=tuned_config)

    assert default.config_digest != tuned.config_digest
    assert default.warp_plan_digest != tuned.warp_plan_digest
    assert default.implementation_digest == tuned.implementation_digest
    assert default.repair_policy_digest == tuned.repair_policy_digest
    assert _case(default, material)["warp_plan_digest"] == default.warp_plan_digest
    assert _case(tuned, material)["warp_plan_digest"] == tuned.warp_plan_digest


def test_rejects_source_outside_case_25_selector() -> None:
    content = _content()
    descriptor = runtime.DurableSourceDescriptor(
        source_id="1" * 32,
        source_output_id="source-1",
        ordinal=1,
        content_sha256=hashlib.sha256(content).hexdigest(),
        media_type="image/jpeg",
        width=96,
        height=96,
        byte_length=len(content),
        generation_request_identity=_digest("generation-one"),
        provenance_identity=_digest("provenance-one"),
        source_authority_key=_digest("authority-one"),
        source_schema_version="d02-source-v1",
    )
    with pytest.raises(backend.TargetedM4RepairError):
        backend.D02TargetedM4RepairBackend(
            material=runtime.SourceMaterial(descriptor=descriptor, content=content)
        )
