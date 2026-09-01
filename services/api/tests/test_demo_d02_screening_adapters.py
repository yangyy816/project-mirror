from __future__ import annotations

import hashlib
from copy import deepcopy
from io import BytesIO
from typing import cast

import pytest
from PIL import Image
from test_demo_d02_authority import _resign_observation, _source_certificate
from test_demo_d02_r2_authority import _report_input_template

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as authority
from mirror_api import demo_d02_screening_adapters as adapters


def _gate_inputs() -> tuple[
    dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]
]:
    fields, packets = _report_input_template()
    payload = cast(dict[str, object], fields["report_payload"])
    case = deepcopy(cast(list[dict[str, object]], payload["ordered_case_manifest"])[0])
    records = deepcopy(cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])[0:3])
    certificate = cast(list[dict[str, object]], payload["measurement_gate_evidence"])[0][
        "result_repeat_certification"
    ]
    return packets[0], case, records, cast(dict[str, object], certificate)


def test_measurement_adapter_replays_supported_fixed18_gate() -> None:
    packet, case, records, certificate = _gate_inputs()
    result = adapters.MeasurementGateAdapter().evaluate(
        source_packet=packet,
        case_entry=case,
        result_m3_records=records,
        result_repeat_certification=certificate,
    )
    assert result["measurement_evaluation_state"] == "SUPPORTED_EVALUATED"
    assert len(cast(list[object], result["ordered_result_repeat_measurements"])) == 3
    evaluation = cast(dict[str, object], result["gate_evaluation"])
    assert evaluation["measurement_gate_passed"] is True
    complete = authority.build_r2_measurement_gate(
        {
            **result,
            "case_id": case["case_id"],
            "case_specification_digest": case["case_specification_digest"],
            "dimension_key": case["dimension_key"],
            "requested_direction": case["direction"],
            "requested_magnitude_ppm": case["magnitude_ppm"],
            "monotonicity_peer_case_id": "a" * 32,
            "result_repeat_certification": certificate,
            "result_repeat_certification_digest": certificate["result_repeat_certification_digest"],
        }
    )
    authority._validate_r2_measurement_gate(
        complete,
        result_records=records,
        facts=cast(dict[str, object], packet["facts"]),
    )


def test_source_projection_preserves_raw_confidence_precision() -> None:
    packet, _, _, _ = _gate_inputs()
    facts = deepcopy(cast(dict[str, object], packet["facts"]))
    observation = deepcopy(cast(dict[str, object], facts["source_measurement_observation"]))
    observed = cast(list[dict[str, object]], observation["ordered_measurements"])
    raw_units = legacy._fixed18_units(observed[0]["raw_observability_fixed18"], "raw observability")
    observed[0]["raw_observability_fixed18"] = adapters._fixed18(raw_units - 1)
    _resign_observation(observation)
    prior_certificate = cast(dict[str, object], facts["source_repeat_certification"])
    prior_bindings = cast(list[dict[str, object]], prior_certificate["ordered_repeat_bindings"])
    certificate = _source_certificate(
        observation,
        execution_receipt_digest=cast(str, prior_bindings[0]["execution_receipt_digest"]),
    )
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
    facts.update(
        source_landmark_digest=observation["landmark_digest"],
        source_measurement_digest=observation["measurement_observation_digest"],
        source_measurement_observation=observation,
        source_measurement_observation_digest=observation["measurement_observation_digest"],
        source_repeat_certification=certificate,
        source_repeat_certification_digest=certificate["source_repeat_certification_digest"],
        raw_measurement_authority=raw,
        raw_measurement_authority_digest=legacy.digest_raw_measurement_authority(raw),
        source_measurement_projection=projection,
        source_measurement_projection_digest=legacy.digest_morphology_projection(projection),
    )
    authority.validate_r2_facts(facts)
    entries = cast(list[dict[str, object]], raw["ordered_entries"])
    projected = cast(list[dict[str, object]], projection["ordered_entries"])

    measurements = adapters._source_measurements_from_facts(cast(dict[str, object], facts))
    first = measurements[cast(str, entries[0]["dimension_key"])]

    assert first["raw_confidence_fixed18"] == entries[0]["raw_confidence_fixed18"]
    assert first["confidence_ppm"] == projected[0]["confidence_ppm"]
    assert first["raw_confidence_fixed18"] != adapters._fixed18(
        cast(int, projected[0]["confidence_ppm"]) * 1_000_000_000_000
    )


def test_measurement_adapter_rejects_result_certificate_mismatch() -> None:
    packet, case, records, certificate = _gate_inputs()
    certificate["result_repeat_certification_digest"] = "0" * 64
    with pytest.raises(adapters.D02ScreeningAdapterError):
        adapters.MeasurementGateAdapter().evaluate(
            source_packet=packet,
            case_entry=case,
            result_m3_records=records,
            result_repeat_certification=certificate,
        )


def test_manual_adapter_requires_sealed_case_and_result_binding() -> None:
    decision = adapters.PrincipalArtifactDecision.seal(
        case_id="case-a",
        result_sha256="a" * 64,
        decision_sequence=1,
        manual_review_version="manual-v1",
        manual_review_policy_digest="b" * 64,
        background_seam=False,
        disconnected_contour=False,
        duplicated_feature=False,
        warp_tear=False,
    )
    adapter = adapters.ManualReviewAdapter({"case-a": decision})
    fields = adapter.decision_fields(
        source_packet={},
        case_entry={"case_id": "case-a"},
        m4_record={"result_sha256": "a" * 64},
        decision_sequence=1,
        manual_review_policy_digest="b" * 64,
    )
    assert fields["warp_tear"] is False
    with pytest.raises(adapters.D02ScreeningAdapterError):
        adapter.decision_fields(
            source_packet={},
            case_entry={"case-a": "case-a"},
            m4_record={"result_sha256": "c" * 64},
            decision_sequence=1,
            manual_review_policy_digest="b" * 64,
        )
    with pytest.raises(adapters.D02ScreeningAdapterError):
        adapter.decision_fields(
            source_packet={},
            case_entry={"case_id": "case-a"},
            m4_record={"result_sha256": "a" * 64},
            decision_sequence=1,
            manual_review_policy_digest="c" * 64,
        )


def test_phash_adapter_fails_closed_for_missing_or_mismatched_bytes() -> None:
    with pytest.raises(adapters.D02ScreeningAdapterError):
        adapters.PHashAdapter({"a" * 64: b"not-a-jpeg"})


def test_phash_adapter_computes_from_checksum_bound_jpeg() -> None:
    output = BytesIO()
    Image.new("RGB", (64, 64), (40, 80, 120)).save(
        output, format="JPEG", quality=95, subsampling="4:2:0", optimize=False, progressive=False
    )
    jpeg = output.getvalue()
    sha256 = hashlib.sha256(jpeg).hexdigest()
    result = adapters.PHashAdapter({sha256: jpeg}).phash_hex(
        image_record={
            "sha256": sha256,
            "width": 64,
            "height": 64,
            "byte_size": len(jpeg),
            "mime_type": "image/jpeg",
        }
    )
    assert len(result) == 16


def test_concrete_adapters_have_no_private_bytes_in_repr() -> None:
    decision = adapters.PrincipalArtifactDecision.seal(
        case_id="case-a",
        result_sha256="a" * 64,
        decision_sequence=1,
        manual_review_version="manual-v1",
        manual_review_policy_digest="b" * 64,
        background_seam=False,
        disconnected_contour=False,
        duplicated_feature=False,
        warp_tear=False,
    )
    assert "case-a" not in repr(decision)
