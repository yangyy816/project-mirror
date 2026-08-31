from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from typing import cast

import pytest
from test_demo_d02_generic_runtime_bridge import _generic_runtime_packets
from test_demo_d02_r2_runtime_forward import (
    _Adapters,
    _RuntimeCaseFields,
    _SyntheticM3Backend,
    _SyntheticM4Backend,
)

from mirror_api import demo_d02_generic_admission_coordinator as coordinator
from mirror_api import demo_d02_generic_screening as generic_screening
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api.demo_d02_final_orchestrator import ResultPersistence
from mirror_api.demo_d02_formal_source_builder import FormalSourceRuntimeBundle
from mirror_api.demo_d02_generic_runtime_admission import (
    D02GenericRuntimeAdmissionError,
    D02QuestionBankConfiguration,
    build_generic_runtime_admission_bundle,
)
from mirror_api.demo_models import D02SelectedSourceManifest


class _VerifiedResults:
    def verify_complete(self, *, outputs: object) -> None:
        assert isinstance(outputs, tuple)
        assert len(outputs) == 48


def _runtime_result() -> tuple[
    runtime.RuntimeScreeningResult,
    FormalSourceRuntimeBundle,
    D02SelectedSourceManifest,
]:
    packets, materials, fields = _generic_runtime_packets()
    descriptor_manifest = runtime.SourceDescriptorManifest.from_generic_packets(packets)
    recipe = runtime.build_default_runtime_recipe()
    model = runtime.build_default_model_identity()
    runtime_handle, model_handle = runtime.mint_runtime_handles(
        descriptor_manifest, recipe=recipe, model_identity=model
    )
    adapters = _Adapters(deepcopy(fields))
    result = runtime.run_runtime_screening(
        runtime.RuntimeScreeningRequest(
            created_at=cast(str, fields["created_at"]),
            source_packets=packets,
            source_materials=materials,
            execution_authority=cast(
                dict[str, object],
                cast(dict[str, object], fields["report_payload"])["schema_and_policy"],
            ),
            recipe=recipe,
            model_identity=model,
            runtime_handle=runtime_handle,
            model_handle=model_handle,
            m3_backend=_SyntheticM3Backend(
                recipe=recipe, model=model, packets=packets, adapters=adapters
            ),
            m4_backend=_SyntheticM4Backend(recipe=recipe),
            case_fields=_RuntimeCaseFields(adapters=adapters, recipe=recipe),
            measurement_gate=adapters,
            manual_review=adapters,
            phash=adapters,
        )
    )
    sources = tuple(
        SimpleNamespace(
            source_input=generic_screening.decode_generic_source_input(packet["source_input"]),
            source_row=packet["supporting_row"],
            identity_row=packet["identity_row"],
            position=index,
        )
        for index, packet in enumerate(packets, start=1)
    )
    formal = cast(
        FormalSourceRuntimeBundle,
        SimpleNamespace(
            sources=sources,
            source_manifest_entries=tuple(packet["source_manifest_entry"] for packet in packets),
            formal_source_manifest_digest=generic_screening.build_formal_source_manifest(
                source_inputs=tuple(source.source_input for source in sources),
                source_rows=tuple(source.source_row for source in sources),
                identity_rows=tuple(source.identity_row for source in sources),
                selected_source_manifest_id=sources[0].source_input.manifest_id,
                selected_source_manifest_digest=sources[0].source_input.manifest_content_digest,
            )[1],
            runtime_source_manifest_digest=packets[0]["source_manifest_digest"],
            runtime_packets=packets,
            descriptor_manifest=descriptor_manifest,
            runtime_handle=runtime_handle,
            model_handle=model_handle,
        ),
    )
    first = sources[0].source_input
    selected = cast(
        D02SelectedSourceManifest,
        SimpleNamespace(
            id=first.manifest_id,
            schema_version="mirror.demo/D02SelectedSourceManifest/v1",
            canonical_payload={"fixture": "selected"},
            content_digest=first.manifest_content_digest,
            acquisition_run_id=first.acquisition_run_id,
            cohort_spec_id=first.cohort_spec_id,
            generation_policy_digest=first.generation_policy_digest,
            ordered_candidate_ids=list(first.manifest_ordered_candidate_ids),
            source_count=4,
            manifest_state="FINALIZED",
        ),
    )
    return result, formal, selected


def test_runtime_result_builds_complete_generic_admission_bundle() -> None:
    result, formal, selected = _runtime_result()
    bundle = build_generic_runtime_admission_bundle(
        runtime_result=result,
        formal_bundle=formal,
        selected_manifest=selected,
        result_persistence=cast(ResultPersistence, _VerifiedResults()),
        configuration=D02QuestionBankConfiguration(created_at="2026-09-01T00:00:00Z"),
    )

    assert len(bundle.asset_rows) == 52
    assert len(bundle.asset_variant_rows) == 48
    assert len(bundle.question_pair_rows) == 16
    assert bundle.report_row["status"] == "PASSED"
    assert bundle.report_row["source_count"] == 4
    assert bundle.report_row["m4_execution_count"] == 96
    assert bundle.report_row["result_m3_repeat_count"] == 144
    coordinator.validate_generic_admission_bundle(
        idempotency_key="d02-final-runtime-test", bundle=bundle
    )


def test_runtime_bundle_rejects_result_digest_substitution() -> None:
    result, formal, selected = _runtime_result()
    substituted = SimpleNamespace(**vars(formal))
    substituted.runtime_handle = replace(formal.runtime_handle, source_manifest_digest="0" * 64)
    # The sealed runtime result must remain bound to the formal handles.
    with pytest.raises(
        D02GenericRuntimeAdmissionError,
        match="RUNTIME_FORMAL_BUNDLE_BINDING_INVALID",
    ):
        build_generic_runtime_admission_bundle(
            runtime_result=result,
            formal_bundle=cast(FormalSourceRuntimeBundle, substituted),
            selected_manifest=selected,
            result_persistence=cast(ResultPersistence, _VerifiedResults()),
            configuration=D02QuestionBankConfiguration(created_at="2026-09-01T00:00:00Z"),
        )
