from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest
from test_demo_d02_r2_authority import _report_input_template

from mirror_api import demo_d02_r2_screening_execution as execution
from mirror_api import demo_measurement_quality as measurement


class _Adapters:
    def __init__(self, fields: dict[str, object]) -> None:
        payload = cast(dict[str, object], fields["report_payload"])
        self._cases = cast(list[dict[str, object]], payload["ordered_case_manifest"])
        self._source_m3 = cast(list[dict[str, object]], payload["source_m3_repeat_evidence"])
        self._m4 = cast(list[dict[str, object]], payload["m4_repeat_evidence"])
        self._result_m3 = cast(list[dict[str, object]], payload["result_m3_repeat_evidence"])
        self._gates = cast(list[dict[str, object]], payload["measurement_gate_evidence"])
        self._manual = cast(list[dict[str, object]], payload["manual_review_evidence"])
        phash = cast(dict[str, object], payload["phash_observation_evidence"])
        signatures = cast(list[dict[str, object]], phash["ordered_record_signatures"])
        self._phash = {item["image_record_id"]: item["phash_hex"] for item in signatures}
        exact = cast(dict[str, object], payload["exact_duplicate_evidence"])
        images = cast(list[dict[str, object]], exact["image_records"])
        self._phash_by_ordinal = {
            image["image_record_ordinal"]: self._phash[image["image_record_id"]] for image in images
        }
        self.inconsistent_m4 = False
        self.unsupported_source = False
        self.missing_phash = False
        self.failing_manual = False
        self.manual_policy_digests: list[str] = []

    def case_fields(self, **_: object) -> dict[str, object]:
        ordinal = cast(int, _["case_ordinal"])
        source = self._cases[ordinal - 1]
        excluded = {
            "schema_version",
            "case_id",
            "execution_config_digest",
            "case_specification_digest",
            "record_digest",
            "case_ordinal",
            "source_manifest_digest",
            "source_ordinal",
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "source_asset_sha256",
            "source_qa_snapshot_digest",
            "source_measurement_projection_digest",
            "source_p2_candidate_manifest_content_digest",
            "dimension_authority_manifest_content_digest",
            "r2_source_authority_record_id",
            "dimension_key",
            "priority_index",
            "direction",
            "direction_index",
            "magnitude_ppm",
            "magnitude_index",
            "ordered_control_dimensions",
            "runtime_manifest_digest",
        }
        return {key: deepcopy(value) for key, value in source.items() if key not in excluded}

    def inspect_source(self, **_: object) -> dict[str, object]:
        source_ordinal = cast(dict[str, object], _["source_packet"])["source_manifest_entry"]
        ordinal = cast(int, cast(dict[str, object], source_ordinal)["source_ordinal"])
        repeat = cast(int, _["repeat_index"])
        record = deepcopy(self._source_m3[(ordinal - 1) * 3 + repeat - 1])
        if self.unsupported_source:
            record["face_count"] = 0
        for key in (
            "schema_version",
            "source_m3_record_id",
            "record_digest",
            "source_ordinal",
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "source_asset_sha256",
            "source_authority_digest",
            "repeat_index",
        ):
            record.pop(key)
        return record

    def transform(self, **_: object) -> dict[str, object]:
        case = cast(dict[str, object], _["case_entry"])
        repeat = cast(int, _["replay_index"])
        record = deepcopy(self._m4[(cast(int, case["case_ordinal"]) - 1) * 2 + repeat - 1])
        if self.inconsistent_m4 and repeat == 2:
            record["result_sha256"] = "f" * 64
        for key in (
            "schema_version",
            "m4_execution_record_id",
            "record_digest",
            "case_id",
            "case_specification_digest",
            "replay_index",
            "source_asset_id",
            "source_asset_sha256",
            "warp_plan_digest",
            "geometry_algorithm_version",
            "runtime_manifest_digest",
            "runtime_config_digest",
            "determinism_level",
        ):
            record.pop(key)
        return record

    def inspect_result(self, **_: object) -> dict[str, object]:
        case = cast(dict[str, object], _["case_entry"])
        m4_record = cast(dict[str, object], _["m4_record"])
        repeat = cast(int, _["repeat_index"])
        record = deepcopy(self._result_m3[(cast(int, case["case_ordinal"]) - 1) * 3 + repeat - 1])
        observation = cast(dict[str, object], record["measurement_observation"])
        observation["subject"] = {
            "schema_version": measurement.RESULT_SUBJECT_SCHEMA,
            "case_id": case["case_id"],
            "case_specification_digest": case["case_specification_digest"],
            "result_output_id": m4_record["result_output_id"],
            "result_sha256": m4_record["result_sha256"],
        }
        observation["measurement_observation_digest"] = measurement.mirror_demo_digest(
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
        record["measurement_observation_digest"] = observation["measurement_observation_digest"]
        for key in (
            "schema_version",
            "result_m3_record_id",
            "record_digest",
            "case_id",
            "case_specification_digest",
            "result_output_id",
            "result_sha256",
            "repeat_index",
            "runtime_manifest_digest",
        ):
            record.pop(key)
        return record

    def evaluate(self, **_: object) -> dict[str, object]:
        case = cast(dict[str, object], _["case_entry"])
        result_records = cast(list[dict[str, object]], _["result_m3_records"])
        record = deepcopy(self._gates[cast(int, case["case_ordinal"]) - 1])
        measurements = cast(list[dict[str, object]], record["ordered_result_repeat_measurements"])
        for measurement_record, result_record in zip(measurements, result_records, strict=True):
            measurement_record["result_m3_record_digest"] = result_record["record_digest"]
        for key in (
            "schema_version",
            "record_digest",
            "case_id",
            "case_specification_digest",
            "dimension_key",
            "requested_direction",
            "requested_magnitude_ppm",
            "monotonicity_peer_case_id",
            "result_repeat_certification",
            "result_repeat_certification_digest",
        ):
            record.pop(key)
        return record

    def decision_fields(self, **_: object) -> dict[str, object]:
        self.manual_policy_digests.append(cast(str, _["manual_review_policy_digest"]))
        case = cast(dict[str, object], _["case_entry"])
        record = self._manual[cast(int, case["case_ordinal"]) - 1]
        result = {
            key: deepcopy(record[key])
            for key in (
                "manual_review_version",
                "decision_sequence",
                "background_seam",
                "disconnected_contour",
                "duplicated_feature",
                "warp_tear",
                "review_authority_digest",
            )
        }
        if self.failing_manual:
            result["warp_tear"] = True
        return result

    def phash_hex(self, **_: object) -> str:
        image = cast(dict[str, object], _["image_record"])
        image_id = cast(str, image["image_record_id"])
        if self.missing_phash:
            return "invalid"
        value = self._phash.get(image_id)
        if value is None:
            value = self._phash_by_ordinal[image["image_record_ordinal"]]
        return cast(str, value)


def _request(
    adapters: _Adapters, fields: dict[str, object], packets: list[dict[str, object]]
) -> execution.OfflineScreeningRequest:
    payload = cast(dict[str, object], fields["report_payload"])
    return execution.OfflineScreeningRequest(
        created_at=cast(str, fields["created_at"]),
        source_packets=packets,
        execution_authority=cast(dict[str, object], payload["schema_and_policy"]),
        case_fields=adapters,
        vision_m3=adapters,
        m4=adapters,
        measurement_gate=adapters,
        manual_review=adapters,
        phash=adapters,
    )


def test_run_replays_the_complete_happy_path() -> None:
    fields, packets = _report_input_template()
    adapters = _Adapters(fields)
    report = execution.run_offline_screening(_request(adapters, fields, packets))
    assert report["status"] == "PASSED"
    assert report["case_count"] == 48
    assert report["m4_execution_count"] == 96
    assert report["selected_pair_count"] == 16
    assert set(adapters.manual_policy_digests) == {
        cast(dict[str, object], fields["report_payload"])["schema_and_policy"][
            "manual_review_policy_digest"
        ]
    }
    payload = cast(dict[str, object], report["report_payload"])
    assert len(cast(list[object], payload["phash_observation_evidence"]["comparisons"])) == 1326  # type: ignore[index]


@pytest.mark.parametrize("mode", ["inconsistent_m4", "unsupported_source", "missing_phash"])
def test_run_fails_closed_when_required_evidence_is_invalid(mode: str) -> None:
    fields, packets = _report_input_template()
    adapters = _Adapters(fields)
    setattr(adapters, mode, True)
    with pytest.raises(execution.ScreeningExecutionError):
        execution.run_offline_screening(_request(adapters, fields, packets))


def test_insufficient_selection_returns_a_complete_failed_report() -> None:
    fields, packets = _report_input_template()
    adapters = _Adapters(fields)
    adapters.failing_manual = True
    report = execution.run_offline_screening(_request(adapters, fields, packets))
    assert report["status"] == "FAILED"
    assert report["selected_pair_count"] == 0


def test_run_rejects_missing_source_and_never_returns_partial_report() -> None:
    fields, packets = _report_input_template()
    with pytest.raises(execution.ScreeningExecutionError):
        execution.run_offline_screening(_request(_Adapters(fields), fields, packets[:3]))
