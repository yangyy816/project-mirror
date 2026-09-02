from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import cast

import pytest
from test_demo_d02_r2_runtime_forward import (
    _Adapters,
    _RuntimeCaseFields,
    _SyntheticM3Backend,
    _SyntheticM4Backend,
)
from test_demo_d02_r2_runtime_forward import (
    runtime_inputs as legacy_runtime_inputs,
)

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_generic_admission as admission
from mirror_api import demo_d02_generic_screening as generic
from mirror_api import demo_d02_r2_authority as authority
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_r2_screening_execution as execution
from mirror_api import demo_measurement_quality as measurement


def _digest(marker: str) -> str:
    return marker.encode().hex().ljust(64, "0")[:64]


def _generic_runtime_packets() -> tuple[
    tuple[dict[str, object], ...], tuple[runtime.SourceMaterial, ...], dict[str, object]
]:
    """Rebind qualified fake M3/M4 observations to generic formal sources."""

    inputs = legacy_runtime_inputs.__wrapped__()
    manifest_id = "f" * 32
    candidate_ids = tuple(char * 32 for char in "abcd")
    packets: list[dict[str, object]] = []
    for position, legacy_packet in enumerate(inputs.packets, start=1):
        supporting = cast(dict[str, object], legacy_packet["supporting_row"])
        facts = cast(dict[str, object], legacy_packet["facts"])
        source_input = admission.GenericSourceInput(
            acquisition_run_id="e" * 32,
            cohort_spec_id="d" * 32,
            manifest_id=manifest_id,
            manifest_acquisition_run_id="e" * 32,
            manifest_cohort_spec_id="d" * 32,
            manifest_content_digest=_digest("selected-manifest"),
            manifest_ordered_candidate_ids=cast(tuple[str, str, str, str], candidate_ids),
            candidate_id=candidate_ids[position - 1],
            candidate_acquisition_run_id="e" * 32,
            candidate_cohort_spec_id="d" * 32,
            candidate_content_digest=_digest(f"candidate-{position}"),
            position=position,
            spec_content_digest=_digest("cohort-spec"),
            generation_policy_digest=_digest("generation-policy"),
            source_output_id=cast(str, supporting["source_output_id"]),
            normalized_asset=admission.NormalizedAsset(
                asset_id=cast(str, supporting["source_asset_id"]),
                sha256=cast(str, supporting["source_asset_sha256"]),
                byte_size=cast(int, supporting["source_asset_byte_size"]),
                width=cast(int, supporting["source_asset_width"]),
                height=cast(int, supporting["source_asset_height"]),
            ),
            formal_source_qa_digest=_digest(f"formal-qa-{position}"),
            candidate_m3_evidence_digest=_digest(f"candidate-m3-{position}"),
            candidate_qa_evidence_digest=_digest(f"candidate-qa-{position}"),
            formal_facts=deepcopy(facts),
            formal_measurement_projection={"projection": position},
            formal_landmark_digest=cast(str, facts["source_landmark_digest"]),
        )
        source_row = admission.build_source_authority(source_input)
        identity_row = admission.build_identity_row(source_input, source_row=source_row)
        entry = generic.build_source_manifest_entry(
            source_input=source_input,
            source_row=source_row,
            identity_row=identity_row,
            selected_source_manifest_id=manifest_id,
            selected_source_manifest_digest=_digest("selected-manifest"),
        )
        packets.append(
            generic.build_generic_runtime_packet(
                source_input=source_input,
                source_row=source_row,
                identity_row=identity_row,
                source_manifest_entry=entry,
                source_manifest_digest=_digest("pending-manifest"),
            )
        )
    manifest_digest = legacy._sequence_digest(
        authority.R2_SOURCE_MANIFEST_SCHEMA,
        [cast(dict[str, object], packet["source_manifest_entry"]) for packet in packets],
    )
    finalized = tuple(
        {
            **packet,
            "source_manifest_digest": manifest_digest,
        }
        for packet in packets
    )
    descriptors = runtime.SourceDescriptorManifest.from_generic_packets(finalized).descriptors
    materials = tuple(
        runtime.SourceMaterial(descriptor=descriptor, content=material.content)
        for descriptor, material in zip(descriptors, inputs.materials, strict=True)
    )
    recipe = runtime.build_default_runtime_recipe()
    model = runtime.build_default_model_identity()
    runtime_handle, model_handle = runtime.mint_runtime_handles(
        runtime.SourceDescriptorManifest(descriptors), recipe=recipe, model_identity=model
    )
    adapters = _Adapters(deepcopy(inputs.fields))
    executor = runtime.reconstruct_executor(
        runtime.SourceDescriptorManifest(descriptors),
        recipe=recipe,
        model_identity=model,
        runtime_handle=runtime_handle,
        model_handle=model_handle,
        m3_backend=_SyntheticM3Backend(
            recipe=recipe, model=model, packets=finalized, adapters=adapters
        ),
        m4_backend=_SyntheticM4Backend(recipe=recipe),
    )
    rebuilt: list[dict[str, object]] = []
    for packet, material in zip(finalized, materials, strict=True):
        source_input = generic.decode_generic_source_input(packet["source_input"])
        fields = [
            {
                **dict(executor.inspect_source(material=material, repeat_index=repeat).fields),
                "repeat_index": repeat,
            }
            for repeat in range(1, 4)
        ]
        observation = cast(dict[str, object], fields[0]["measurement_observation"])
        old_facts = cast(dict[str, object], source_input.formal_facts)
        certificate = measurement.build_source_repeat_certification(
            subject=cast(
                dict[str, object],
                cast(dict[str, object], old_facts["source_repeat_certification"])["subject"],
            ),
            bindings=measurement.AuthorityBindings(
                runtime_manifest_digest=cast(str, observation["runtime_manifest_digest"]),
                vision_model_manifest_digest=cast(str, observation["vision_model_manifest_digest"]),
                topology_digest=cast(str, observation["topology_digest"]),
                measurement_config_digest=cast(str, observation["measurement_config_digest"]),
                measurement_quality_config_digest=cast(
                    str, observation["measurement_quality_config_digest"]
                ),
                measurement_quality_manifest_content_digest=cast(
                    str, observation["measurement_quality_manifest_content_digest"]
                ),
            ),
            ordered_repeat_bindings=[
                {
                    key: field[key]
                    for key in (
                        "repeat_index",
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
                }
                for field in fields
            ],
        )
        raw = legacy.build_raw_measurement_authority(
            observation,
            certificate,
            source_p2_candidate_manifest_content_digest=cast(
                str, old_facts["source_p2_candidate_manifest_content_digest"]
            ),
            dimension_authority_manifest_content_digest=cast(
                str, old_facts["dimension_authority_manifest_content_digest"]
            ),
        )
        projection = legacy.build_morphology_projection(raw)
        facts = {
            **deepcopy(old_facts),
            "source_measurement_observation": observation,
            "source_measurement_observation_digest": observation["measurement_observation_digest"],
            "source_measurement_digest": observation["measurement_observation_digest"],
            "source_landmark_digest": observation["landmark_digest"],
            "source_repeat_certification": certificate,
            "source_repeat_certification_digest": certificate["source_repeat_certification_digest"],
            "raw_measurement_authority": raw,
            "raw_measurement_authority_digest": legacy.digest_raw_measurement_authority(raw),
            "source_measurement_projection": projection,
            "source_measurement_projection_digest": legacy.digest_morphology_projection(projection),
            "measurement_projection_version": projection["measurement_projection_version"],
            "measurement_quantization_version": projection["measurement_quantization_version"],
        }
        updated = replace(source_input, formal_facts=facts)
        source_row = admission.build_source_authority(updated)
        identity_row = admission.build_identity_row(updated, source_row=source_row)
        entry = generic.build_source_manifest_entry(
            source_input=updated,
            source_row=source_row,
            identity_row=identity_row,
            selected_source_manifest_id=updated.manifest_id,
            selected_source_manifest_digest=updated.manifest_content_digest,
        )
        rebuilt.append(
            generic.build_generic_runtime_packet(
                source_input=updated,
                source_row=source_row,
                identity_row=identity_row,
                source_manifest_entry=entry,
                source_manifest_digest=_digest("pending-rebuilt-manifest"),
            )
        )
    rebuilt_digest = legacy._sequence_digest(
        authority.R2_SOURCE_MANIFEST_SCHEMA,
        [cast(dict[str, object], packet["source_manifest_entry"]) for packet in rebuilt],
    )
    finished = tuple({**packet, "source_manifest_digest": rebuilt_digest} for packet in rebuilt)
    return finished, materials, inputs.fields


def test_generic_packet_replays_and_runtime_manifest_rejects_substitution() -> None:
    packets, _, _ = _generic_runtime_packets()
    for packet in packets:
        generic.validate_generic_runtime_packet(packet)
        authority.validate_r2_admission_packet(packet)
        entry = cast(dict[str, object], packet["source_manifest_entry"])
        facts = cast(dict[str, object], packet["facts"])
        assert (
            entry["source_p2_candidate_manifest_content_digest"]
            == facts["source_p2_candidate_manifest_content_digest"]
        )
        assert (
            entry["dimension_authority_manifest_content_digest"]
            == facts["dimension_authority_manifest_content_digest"]
        )
    manifest = runtime.SourceDescriptorManifest.from_generic_packets(packets)
    assert tuple(item.ordinal for item in manifest.descriptors) == (1, 2, 3, 4)
    assert runtime._manifest_from_versioned_packets(packets) == manifest

    injected = deepcopy(packets[0])
    injected["generation_receipt"] = {"schema_version": "not-a-receipt"}
    with pytest.raises(ValueError):
        generic.validate_generic_runtime_packet(injected)

    mutated = deepcopy(packets[0])
    source_input = cast(dict[str, object], mutated["source_input"])
    source_input["candidate_id"] = "9" * 32
    with pytest.raises(ValueError):
        authority.validate_r2_admission_packet(mutated)

    with pytest.raises(runtime.RuntimeForwardError):
        runtime.SourceDescriptorManifest.from_generic_packets((packets[1], *packets[1:]))
    with pytest.raises(execution.ScreeningExecutionError):
        execution._validated_sources(
            tuple({**packet, "source_manifest_digest": _digest("wrong")} for packet in packets)
        )


def test_generic_packets_run_through_real_runtime_screening_bridge() -> None:
    packets, materials, fields = _generic_runtime_packets()
    manifest = runtime.SourceDescriptorManifest.from_generic_packets(packets)
    recipe = runtime.build_default_runtime_recipe()
    model = runtime.build_default_model_identity()
    runtime_handle, model_handle = runtime.mint_runtime_handles(
        manifest, recipe=recipe, model_identity=model
    )
    adapters = _Adapters(deepcopy(fields))
    m3 = _SyntheticM3Backend(recipe=recipe, model=model, packets=packets, adapters=adapters)
    m4 = _SyntheticM4Backend(recipe=recipe)
    payload = cast(dict[str, object], fields["report_payload"])

    result = runtime.run_runtime_screening(
        runtime.RuntimeScreeningRequest(
            created_at=cast(str, fields["created_at"]),
            source_packets=packets,
            source_materials=materials,
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
    assert result.report_row["source_count"] == 4
    assert result.report_row["case_count"] == 48
    assert m3.source_calls == 12
    assert m3.result_calls == 144
    assert m4.calls == 96
