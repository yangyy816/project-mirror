"""Assemble a validated generic D02 runtime result for atomic admission.

This module is the deterministic boundary between an already-passed runtime
screening result and ``D02GenericAdmissionCoordinator``.  It creates no image
bytes and resolves no private locator.  Source/result storage keys are opaque
product identifiers; local primary/backup locations remain solely in the
ignored availability indices.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_generic_admission_coordinator as coordinator
from mirror_api import demo_d02_generic_screening as screening
from mirror_api import demo_d02_r2_authority as r2
from mirror_api.demo_d02_final_orchestrator import FormalRuntimeBundleView, ResultPersistence
from mirror_api.demo_d02_r2_runtime_forward import RuntimeScreeningResult
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import D02SelectedSourceManifest

QUESTION_BANK_POLICY_SCHEMA: Final = "mirror.demo/D02AutonomousQuestionBankPolicy/v1"
ADMISSION_POLICY_SCHEMA: Final = "mirror.demo/D02AutonomousAdmissionPolicy/v1"


class D02GenericRuntimeAdmissionError(RuntimeError):
    """Stable generic-assembly failure without private state."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _hash(schema: str, payload: Mapping[str, object]) -> str:
    import hashlib

    return hashlib.sha256(
        schema.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def question_bank_policy_payload() -> dict[str, object]:
    return {
        "schema_version": QUESTION_BANK_POLICY_SCHEMA,
        "report_schema": screening.REPORT_SCHEMA,
        "selected_dimension_count": 2,
        "selected_pair_count": 16,
        "selected_side_count": 32,
        "selection": "R2_FIXED_PRIORITY_PAIR_SELECTION_V3",
        "routing": "SELF_STATE_CONDITIONED_PAIRWISE_LOGISTIC_V1",
        "stopping": "EXPLICIT_UNCERTAINTY_AND_RESPONSE_BUDGET_V1",
        "neighborhood": "CONTINUOUS_MORPHOLOGY_NEIGHBORHOOD_V1",
        "beauty_scoring": "FORBIDDEN",
        "sensitive_trait_routing": "FORBIDDEN",
    }


def admission_policy_payload() -> dict[str, object]:
    return {
        "schema_version": ADMISSION_POLICY_SCHEMA,
        "source_count": 4,
        "asset_count": 52,
        "asset_variant_count": 48,
        "question_pair_count": 16,
        "selected_side_count": 32,
        "transaction": "SINGLE_POSTGRESQL_TRANSACTION",
        "idempotency": "KEY_AND_CANONICAL_PAYLOAD_BOUND",
        "collision": "FAIL_CLOSED",
        "partial_rows": "FORBIDDEN",
        "private_locator_in_database": False,
    }


QUESTION_BANK_POLICY_DIGEST: Final = _hash(
    QUESTION_BANK_POLICY_SCHEMA, question_bank_policy_payload()
)
ADMISSION_POLICY_DIGEST: Final = _hash(ADMISSION_POLICY_SCHEMA, admission_policy_payload())


@dataclass(frozen=True, slots=True)
class D02QuestionBankConfiguration:
    created_at: str
    version: str = "d02-autonomous-v1"
    algorithm_config_digest: str = QUESTION_BANK_POLICY_DIGEST
    routing_version: str = "self-state-pairwise-logistic-v1"
    stopping_version: str = "explicit-uncertainty-budget-v1"
    neighborhood_version: str = "continuous-morphology-neighborhood-v1"
    admission_policy_digest: str = ADMISSION_POLICY_DIGEST

    def __post_init__(self) -> None:
        if not isinstance(self.created_at, str) or not self.created_at:
            _fail("QUESTION_BANK_CREATED_AT_INVALID")
        for value in (
            self.version,
            self.routing_version,
            self.stopping_version,
            self.neighborhood_version,
        ):
            if (
                not isinstance(value, str)
                or not 1 <= len(value) <= 64
                or any(
                    character
                    not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
                    for character in value
                )
            ):
                _fail("QUESTION_BANK_VERSION_INVALID")
        for value in (self.algorithm_config_digest, self.admission_policy_digest):
            _digest(value, "QUESTION_BANK_POLICY")


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label}_DIGEST_INVALID")
    return value


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label}_INVALID")
    return cast(Mapping[str, object], value)


def _nominal_question_pair_deltas(pair: Mapping[str, object]) -> tuple[int, int]:
    magnitude = pair.get("magnitude_ppm")
    left = _mapping(pair.get("left"), "LEFT_PAIR_SIDE")
    right = _mapping(pair.get("right"), "RIGHT_PAIR_SIDE")
    left_measured = left.get("measured_signed_delta_ppm")
    right_measured = right.get("measured_signed_delta_ppm")
    if (
        type(magnitude) is not int
        or magnitude <= 0
        or left.get("requested_direction") != "DECREASE"
        or right.get("requested_direction") != "INCREASE"
        or type(left_measured) is not int
        or type(right_measured) is not int
        or left_measured >= 0
        or right_measured <= 0
    ):
        _fail("QUESTION_PAIR_DIRECTION_BINDING_INVALID")
    return -magnitude, magnitude


def _selected_manifest_row(manifest: D02SelectedSourceManifest) -> dict[str, object]:
    if manifest.manifest_state != "FINALIZED" or manifest.source_count != 4:
        _fail("SELECTED_SOURCE_MANIFEST_INVALID")
    return {
        "id": manifest.id,
        "schema_version": manifest.schema_version,
        "canonical_payload": manifest.canonical_payload,
        "content_digest": manifest.content_digest,
        "acquisition_run_id": manifest.acquisition_run_id,
        "cohort_spec_id": manifest.cohort_spec_id,
        "generation_policy_digest": manifest.generation_policy_digest,
        "ordered_candidate_ids": list(manifest.ordered_candidate_ids),
        "source_count": manifest.source_count,
        "manifest_state": manifest.manifest_state,
    }


def _asset_row(
    *,
    asset_id: str,
    sha256: str,
    byte_size: int,
    width: int,
    height: int,
    kind: str,
) -> dict[str, object]:
    if kind not in {"source", "result"}:
        _fail("ASSET_KIND_INVALID")
    return {
        "id": asset_id,
        "owner_user_id": None,
        "asset_role": "synthetic",
        "storage_key": f"internal-synthetic/v1/d02/{kind}/{asset_id}",
        "mime_type": "image/jpeg",
        "byte_size": byte_size,
        "width": width,
        "height": height,
        "sha256": sha256,
        "synthetic": True,
        "is_ai_generated": kind == "source",
        "is_ai_modified": kind == "result",
        "internal_purpose": "synthetic_dataset",
    }


def build_generic_runtime_admission_bundle(
    *,
    runtime_result: RuntimeScreeningResult,
    formal_bundle: FormalRuntimeBundleView,
    selected_manifest: D02SelectedSourceManifest,
    result_persistence: ResultPersistence,
    configuration: D02QuestionBankConfiguration,
) -> coordinator.GenericAdmissionBundle:
    """Build all 52 Assets, 48 variants, Report, Bank and 16 pairs."""

    if not runtime_result.admission_ready:
        _fail("RUNTIME_RESULT_NOT_ADMISSION_READY")
    if (
        tuple(runtime_result.source_packets) != formal_bundle.runtime_packets
        or runtime_result.source_descriptor_manifest_digest
        != formal_bundle.descriptor_manifest.manifest_digest
        or runtime_result.runtime_handle_digest != formal_bundle.runtime_handle.handle_digest
        or runtime_result.model_handle_digest != formal_bundle.model_handle.handle_digest
        or selected_manifest.id != formal_bundle.sources[0].source_input.manifest_id
        or selected_manifest.content_digest
        != formal_bundle.sources[0].source_input.manifest_content_digest
    ):
        _fail("RUNTIME_FORMAL_BUNDLE_BINDING_INVALID")
    result_persistence.verify_complete(outputs=runtime_result.result_outputs)
    try:
        payload = deepcopy(
            cast(
                dict[str, object],
                _mapping(runtime_result.report_row.get("report_payload"), "REPORT"),
            )
        )
        source_entries = [dict(item) for item in formal_bundle.source_manifest_entries]
        source_by_ordinal = {cast(int, item["source_ordinal"]): item for item in source_entries}
        asset_rows: list[dict[str, object]] = []
        asset_entries: list[dict[str, object]] = []
        for source in formal_bundle.sources:
            value = source.source_input.normalized_asset
            position = source.position
            row = _asset_row(
                asset_id=value.asset_id,
                sha256=value.sha256,
                byte_size=value.byte_size,
                width=value.width,
                height=value.height,
                kind="source",
            )
            asset_rows.append(row)
            asset_entries.append(
                screening.build_asset_manifest_entry(
                    asset_id=value.asset_id,
                    sha256=value.sha256,
                    byte_size=value.byte_size,
                    mime_type=value.mime_type,
                    width=value.width,
                    height=value.height,
                    asset_kind="SOURCE",
                    source_ordinal=position,
                    case_ordinal=None,
                )
            )

        cases = cast(list[dict[str, object]], payload["ordered_case_manifest"])
        case_ordinal_by_id = {
            cast(str, case["case_id"]): cast(int, case["case_ordinal"]) for case in cases
        }
        output_by_case = {output.case_id: output for output in runtime_result.result_outputs}
        exact_duplicate = dict(_mapping(payload["exact_duplicate_evidence"], "DUPLICATE_EVIDENCE"))
        image_records = exact_duplicate.get("image_records")
        if not isinstance(image_records, list):
            _fail("RESULT_IMAGE_AUTHORITY_INVALID")
        result_asset_by_case: dict[str, str] = {}
        for raw_image in image_records:
            image = _mapping(raw_image, "RESULT_IMAGE")
            if image.get("authority_role") != "RESULT":
                continue
            case_id = cast(str, image.get("case_id"))
            output = output_by_case.get(case_id)
            case_ordinal = case_ordinal_by_id.get(case_id)
            asset_id = image.get("deterministic_result_asset_id")
            source_ordinal = image.get("source_ordinal")
            if (
                output is None
                or case_ordinal is None
                or not isinstance(asset_id, str)
                or source_ordinal not in {1, 2, 3, 4}
                or image.get("sha256") != output.result_sha256
                or image.get("byte_size") != output.result_byte_size
                or image.get("mime_type") != output.result_mime_type
                or image.get("width") != output.result_width
                or image.get("height") != output.result_height
            ):
                _fail("RESULT_IMAGE_AUTHORITY_INVALID")
            result_asset_by_case[case_id] = asset_id
            row = _asset_row(
                asset_id=asset_id,
                sha256=output.result_sha256,
                byte_size=output.result_byte_size,
                width=output.result_width,
                height=output.result_height,
                kind="result",
            )
            asset_rows.append(row)
            asset_entries.append(
                screening.build_asset_manifest_entry(
                    asset_id=asset_id,
                    sha256=output.result_sha256,
                    byte_size=output.result_byte_size,
                    mime_type=output.result_mime_type,
                    width=output.result_width,
                    height=output.result_height,
                    asset_kind="RESULT",
                    source_ordinal=source_ordinal,
                    case_ordinal=case_ordinal,
                )
            )
        if len(result_asset_by_case) != 48 or len(asset_rows) != 52:
            _fail("RESULT_ASSET_CARDINALITY_INVALID")
        exact_duplicate["record_digest"] = _hash(
            cast(str, exact_duplicate["schema_version"]),
            {
                key: value
                for key, value in exact_duplicate.items()
                if key not in {"schema_version", "record_digest"}
            },
        )
        payload["exact_duplicate_evidence"] = exact_duplicate

        pair_wrappers = cast(list[dict[str, object]], payload["pair_quality_evidence"])
        variant_rows: list[dict[str, object]] = []
        variant_entries: list[dict[str, object]] = []
        seen_cases: set[str] = set()
        for wrapper in pair_wrappers:
            binding = wrapper.get("fixture_binding")
            if binding not in {None, "generic-formal-source-v1"}:
                _fail("PAIR_GENERIC_BINDING_INVALID")
            wrapper["fixture_binding"] = "generic-formal-source-v1"
            pair = _mapping(wrapper.get("pair_screening_record_payload"), "PAIR_PAYLOAD")
            source_ordinal = cast(int, pair.get("source_ordinal"))
            source_entry = source_by_ordinal[source_ordinal]
            for side_name in ("left", "right"):
                side = _mapping(pair.get(side_name), "PAIR_SIDE")
                case_id = cast(str, side.get("case_id"))
                case_ordinal = case_ordinal_by_id.get(case_id)
                variant_id = side.get("asset_variant_id")
                result_asset_id = side.get("result_asset_id")
                if (
                    case_id in seen_cases
                    or case_ordinal is None
                    or result_asset_by_case.get(case_id) != result_asset_id
                    or not isinstance(variant_id, str)
                    or side.get("asset_variant_type") != "demo_p3_p7_geometry_v1"
                ):
                    _fail("RESULT_VARIANT_AUTHORITY_INVALID")
                seen_cases.add(case_id)
                row = {
                    "id": variant_id,
                    "source_asset_id": source_entry["source_asset_id"],
                    "result_asset_id": result_asset_id,
                    "variant_type": side["asset_variant_type"],
                    "created_at": configuration.created_at,
                }
                variant_rows.append(row)
                variant_entries.append(
                    screening.build_variant_manifest_entry(
                        variant_id=variant_id,
                        source_asset_id=cast(str, row["source_asset_id"]),
                        result_asset_id=cast(str, result_asset_id),
                        source_ordinal=source_ordinal,
                        case_ordinal=case_ordinal,
                    )
                )
        if len(seen_cases) != 48 or len(variant_rows) != 48:
            _fail("RESULT_VARIANT_CARDINALITY_INVALID")

        payload["asset_authority_manifest"] = asset_entries
        payload["asset_variant_manifest"] = variant_entries
        selected_entries = cast(list[dict[str, object]], payload["selected_pair_manifest"])
        generic_selected_digest = _hash(
            screening.SELECTED_PAIR_MANIFEST_SCHEMA, {"ordered_entries": selected_entries}
        )
        report_fields = {
            key: deepcopy(runtime_result.report_row[key]) for key in r2.R2_REPORT_FIELDS
        }
        report_fields.update(
            report_payload=payload,
            source_manifest_digest=formal_bundle.formal_source_manifest_digest,
            selected_pair_manifest_digest=generic_selected_digest,
        )
        report = screening.build_report_row(
            report_fields,
            source_inputs=tuple(source.source_input for source in formal_bundle.sources),
            source_rows=tuple(source.source_row for source in formal_bundle.sources),
            identity_rows=tuple(source.identity_row for source in formal_bundle.sources),
            selected_source_manifest_id=selected_manifest.id,
            selected_source_manifest_digest=selected_manifest.content_digest,
        )

        selected_dimensions = cast(list[str], report["selected_dimension_keys"])
        dimension_manifest = {
            "schema_version": screening.DIMENSION_MANIFEST_SCHEMA,
            "screening_report_id": report["id"],
            "screening_report_digest": report["report_digest"],
            "selected_source_manifest_id": selected_manifest.id,
            "selected_source_manifest_digest": selected_manifest.content_digest,
            "formal_source_manifest_digest": formal_bundle.formal_source_manifest_digest,
            "selected_pair_manifest_digest": generic_selected_digest,
            "selected_dimensions": [
                {
                    "dimension_key": dimension,
                    "ordered_selected_pair_entry_digests": [
                        entry["entry_digest"]
                        for entry in selected_entries
                        if entry["dimension_key"] == dimension
                    ],
                }
                for dimension in selected_dimensions
            ],
        }
        bank = screening.build_question_bank_row(
            {
                "created_at": configuration.created_at,
                "version": configuration.version,
                "algorithm_config_digest": configuration.algorithm_config_digest,
                "routing_version": configuration.routing_version,
                "stopping_version": configuration.stopping_version,
                "neighborhood_version": configuration.neighborhood_version,
                "pair_manifest_digest": generic_selected_digest,
                "dimension_manifest": dimension_manifest,
                "screening_report_id": report["id"],
                "screening_report_digest": report["report_digest"],
            },
            report=report,
            selected_source_manifest_id=selected_manifest.id,
            selected_source_manifest_digest=selected_manifest.content_digest,
        )

        pair_rows: list[dict[str, object]] = []
        wrapper_by_digest = {
            cast(str, item["pair_screening_record_digest"]): item for item in pair_wrappers
        }
        for selected in selected_entries:
            wrapper = wrapper_by_digest[cast(str, selected["pair_screening_record_digest"])]
            pair = _mapping(wrapper["pair_screening_record_payload"], "PAIR_PAYLOAD")
            source_entry = source_by_ordinal[cast(int, pair["source_ordinal"])]
            qa = {
                "schema_version": screening.PAIR_QA_SCHEMA,
                "screening_report_id": report["id"],
                "screening_report_digest": report["report_digest"],
                "selected_source_manifest_id": selected_manifest.id,
                "selected_source_manifest_digest": selected_manifest.content_digest,
                "formal_source_manifest_digest": formal_bundle.formal_source_manifest_digest,
                "source_manifest_entry_schema_version": screening.SOURCE_ENTRY_SCHEMA,
                "source_manifest_entry_digest": source_entry["record_digest"],
                "pair_screening_record_schema_version": r2.R2_PAIR_SCREENING_SCHEMA,
                "pair_screening_record_digest": wrapper["pair_screening_record_digest"],
                "pair_screening_record_payload": wrapper,
                "selected_pair_manifest_digest": generic_selected_digest,
                "selected_pair_entry_schema_version": r2.R2_SELECTED_ENTRY_SCHEMA,
                "selected_pair_entry_digest": selected["entry_digest"],
                "selected_pair_entry_payload": selected,
            }
            left = _mapping(pair["left"], "LEFT_PAIR_SIDE")
            right = _mapping(pair["right"], "RIGHT_PAIR_SIDE")
            left_nominal_delta, right_nominal_delta = _nominal_question_pair_deltas(pair)
            pair_rows.append(
                screening.build_question_pair_row(
                    {
                        "created_at": configuration.created_at,
                        "question_bank_id": bank["id"],
                        "demo_synthetic_identity_id": source_entry["source_admission_event_id"],
                        "source_asset_id": source_entry["source_asset_id"],
                        "source_asset_sha256": source_entry["source_asset_sha256"],
                        "left_asset_id": left["result_asset_id"],
                        "left_asset_sha256": left["result_asset_sha256"],
                        "right_asset_id": right["result_asset_id"],
                        "right_asset_sha256": right["result_asset_sha256"],
                        "left_asset_variant_id": left["asset_variant_id"],
                        "right_asset_variant_id": right["asset_variant_id"],
                        "dimension_key": pair["dimension_key"],
                        "magnitude_ppm": pair["magnitude_ppm"],
                        "left_delta_ppm": left_nominal_delta,
                        "right_delta_ppm": right_nominal_delta,
                        "pair_quality_ppm": pair["pair_quality_ppm"],
                        "qa_payload": qa,
                        "screening_report_id": report["id"],
                        "screening_report_digest": report["report_digest"],
                    },
                    report=report,
                    bank=bank,
                )
            )
        screening.validate_complete_question_bank(report=report, bank=bank, pair_rows=pair_rows)
        return coordinator.GenericAdmissionBundle(
            request_payload={
                "operation": "D02_AUTONOMOUS_GENERIC_ADMISSION",
                "policy_digest": configuration.admission_policy_digest,
            },
            selected_manifest=_selected_manifest_row(selected_manifest),
            source_inputs=tuple(source.source_input for source in formal_bundle.sources),
            source_rows=tuple(source.source_row for source in formal_bundle.sources),
            identity_rows=tuple(source.identity_row for source in formal_bundle.sources),
            asset_rows=tuple(asset_rows),
            asset_variant_rows=tuple(variant_rows),
            report_row=report,
            question_bank_row=bank,
            question_pair_rows=tuple(pair_rows),
        )
    except D02GenericRuntimeAdmissionError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise D02GenericRuntimeAdmissionError("GENERIC_RUNTIME_ASSEMBLY_FAILED") from error


def _fail(code: str) -> NoReturn:
    raise D02GenericRuntimeAdmissionError(code)
