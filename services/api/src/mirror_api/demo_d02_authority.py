"""Pure, fail-closed Candidate 3 D02 authority graph builder and validator.

This module intentionally operates only on caller-supplied canonical evidence.
It neither resolves assets nor accesses a database, provider, private runtime, or
filesystem.  Its narrow purpose is to construct and replay the frozen v2/v3/v4
digest DAG described by D02 Change Control 02, Revision 10.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Final, NoReturn, cast

from mirror_api.demo_measurement_quality import (
    CONFIDENCE_KIND,
    IMPORT_CONFIG_DIGEST,
    MEASUREMENT_CONFIG_DIGEST,
    QUALITY_CONFIG_DIGEST,
    QUALITY_MANIFEST_DIGEST,
    RELIABILITY_KIND,
    RUNTIME_MANIFEST_DIGEST,
    TOPOLOGY_DIGEST,
    VISION_MODEL_MANIFEST_DIGEST,
    MeasurementQualityError,
    canonical_json_bytes,
    default_authority_bindings,
    derive_result_m3_record_id,
    mirror_demo_digest,
    ppm_from_fixed18,
    require_replayed_measurement_config_digest,
)

type JsonScalar = bool | int | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

RAW_SCHEMA: Final = "mirror.demo/D02RawMeasurementAuthority/v2"
PROJECTION_SCHEMA: Final = "mirror.demo/D02MorphologyProjection/v2"
FACTS_SCHEMA: Final = "mirror.demo/RecoveredSyntheticIdentityFacts/v3"
IDENTITY_SCHEMA: Final = "mirror.demo/DemoSyntheticIdentity/v3"
SOURCE_ENTRY_SCHEMA: Final = "mirror.demo/D02SourceAuthorityManifestEntry/v3"
SOURCE_MANIFEST_SCHEMA: Final = "mirror.demo/D02SourceAuthorityManifest/v1"
SOURCE_M3_SCHEMA: Final = "mirror.demo/D02SourceM3RepeatRecord/v2"
RESULT_M3_SCHEMA: Final = "mirror.demo/D02ResultM3RepeatRecord/v2"
GATE_SCHEMA: Final = "mirror.demo/D02MeasurementGateRecord/v4"
SCHEMA_POLICY_SCHEMA: Final = "mirror.demo/D02SchemaAndPolicyBinding/v2"
REPORT_SCHEMA: Final = "mirror.demo/D02PairScreeningReport/v2"
CASE_ENTRY_SCHEMA: Final = "mirror.demo/D02GeometryCaseManifestEntry/v3"
CASE_MANIFEST_SCHEMA: Final = "mirror.demo/D02GeometryCaseManifest/v1"
EXECUTION_CONFIGURATION_SCHEMA: Final = "mirror.demo/D02ExecutionConfiguration/v1"
M4_EXECUTION_SCHEMA: Final = "mirror.demo/D02M4ExecutionRecord/v1"
STRUCTURE_SCHEMA: Final = "mirror.demo/D02DecodeStructureImmutabilityRecord/v1"
MANUAL_SCHEMA: Final = "mirror.demo/D02ManualArtifactDecision/v1"
SOURCE_IMAGE_SCHEMA: Final = "mirror.demo/D02SourceImageAuthorityRecord/v2"
RESULT_IMAGE_SCHEMA: Final = "mirror.demo/D02ResultImageAuthorityRecord/v2"
SOURCE_IMAGE_ID_DOMAIN: Final = "mirror.demo/D02SourceImageAuthorityRecordId/v1"
RESULT_IMAGE_ID_DOMAIN: Final = "mirror.demo/D02ResultImageAuthorityRecordId/v1"
PHASH_EVIDENCE_SCHEMA: Final = "mirror.demo/D02PHashObservationEvidence/v2"
PHASH_SIGNATURE_SCHEMA: Final = "mirror.demo/D02PHashSignatureRecord/v1"
PHASH_COMPARISON_SCHEMA: Final = "mirror.demo/D02PHashComparisonRecord/v1"
EXACT_DUPLICATE_SCHEMA: Final = "mirror.demo/D02ExactDuplicateEvidence/v2"
PAIR_SCHEMA: Final = "mirror.demo/D02PairScreeningRecord/v3"
PAIR_ID_DOMAIN: Final = "mirror.demo/D02PairScreeningRecordId/v1"
EVALUATED_SIDE_SCHEMA: Final = "mirror.demo/D02EvaluatedPairSide/v3"
UNSUPPORTED_SIDE_SCHEMA: Final = "mirror.demo/D02UnsupportedPairSide/v3"
AUTOMATED_SIDE_GATE_SCHEMA: Final = "mirror.demo/D02AutomatedSideGate/v1"
DIMENSION_SCHEMA: Final = "mirror.demo/D02DimensionEligibilityRecord/v3"
DIMENSION_SIDE_GATE_SCHEMA: Final = "mirror.demo/D02DimensionSideGateEntry/v1"
DIMENSION_PAIR_GATE_SCHEMA: Final = "mirror.demo/D02DimensionPairGateEntry/v1"
SIXTEEN_SIDE_GATE_SCHEMA: Final = "mirror.demo/D02SixteenSideGate/v1"
EIGHT_PAIR_GATE_SCHEMA: Final = "mirror.demo/D02EightPairGate/v1"
SELECTION_SCHEMA: Final = "mirror.demo/D02SelectionTraceRecord/v2"
SELECTED_PAIR_SCHEMA: Final = "mirror.demo/D02SelectedPairManifestEntry/v2"
SELECTED_PAIR_MANIFEST_SCHEMA: Final = "mirror.demo/D02SelectedPairManifest/v2"
NETWORK_BOUNDARY_SCHEMA: Final = "mirror.demo/D02NetworkRuntimeBoundary/v2"
VARIANT_LINEAGE_SCHEMA: Final = "mirror.demo/D02AssetVariantLineage/v1"
IMPORTED_ASSET_ID_DOMAIN: Final = "mirror.demo/D02ImportedAssetId/v1"
ASSET_VARIANT_ID_DOMAIN: Final = "mirror.demo/D02AssetVariantId/v1"
SOURCE_AUTHORITY_KEY_DOMAIN: Final = "mirror.demo/SourceAuthorityKey/v1"
LOCAL_SOURCE_AUTHORITY_KIND: Final = "DEMO_LOCAL_IMPORTED_COPY"
UNKNOWN_FORMAL_IDENTITY_STATUS: Final = "UNKNOWN_REDACTED_NOT_RECOVERED"
VARIANT_TYPE: Final = "demo_p3_p7_geometry_v1"
LOCAL_ADMISSION_CONFIG_SCHEMA: Final = "mirror.demo/D02LocalSyntheticAdmissionConfiguration/v1"
LOCAL_ADMISSION_CONFIG_PAYLOAD: Final[dict[str, JsonValue]] = {
    "track": "DEMO_PROTOTYPE",
    "source_mode": LOCAL_SOURCE_AUTHORITY_KIND,
    "identity_schema_version": IDENTITY_SCHEMA,
    "import_config_digest": IMPORT_CONFIG_DIGEST,
    "source_output_id_contract": "OPAQUE_PRIVATE_OUTPUT_REGISTRY_ID_V1",
    "source_receipt_binding_required": True,
    "adult_synthetic_attestation_required": True,
    "original_formal_identity_id_status": UNKNOWN_FORMAL_IDENTITY_STATUS,
    "public_internet_egress": "DENIED_DURING_CORE_EXECUTION",
    "production_release": "NOT_AUTHORIZED",
}
LOCAL_ADMISSION_CONFIG_DIGEST: Final = mirror_demo_digest(
    LOCAL_ADMISSION_CONFIG_SCHEMA,
    LOCAL_ADMISSION_CONFIG_PAYLOAD,
)
REVISION_9_PREREGISTRATION_SHA256: Final = (
    "3fb0a1192d006560d45083b8d9d933f15a22648c0108f81ef305d31980073ba3"
)
SCREENING_POLICY_DIGEST: Final = mirror_demo_digest(
    "mirror.demo/D02ScreeningPolicyRoot/v1",
    {
        "preregistration_id": "P3_P7_D02_PAIR_SCREENING_V9",
        "policy_schema": "mirror.demo/D02PairScreeningPolicy/v8",
        "policy_revision": 9,
        "preregistration_sha256": REVISION_9_PREREGISTRATION_SHA256,
    },
)
EMPTY_LOCK_POLICY_DIGEST: Final = mirror_demo_digest(
    "mirror.demo/D02EmptyNeutralLockPolicy/v1",
    {
        "policy_id": "D02_FROZEN_EMPTY_NEUTRAL_POLICY_V1",
        "ordered_feature_locks": [],
        "ordered_temporary_session_overrides": [],
        "ordered_prohibited_operations": [],
    },
)

DIMENSIONS: Final = (
    "cheekbone_width",
    "chin_height",
    "eye_spacing",
    "jaw_width",
    "mouth_width",
    "nose_width",
)
CASE_DIMENSIONS: Final = ("jaw_width", "chin_height", "eye_spacing")
CASE_DIRECTIONS: Final = ("DECREASE", "INCREASE")
CASE_MAGNITUDES: Final = (15_000, 30_000)
REPORT_GROUPS: Final = (
    "schema_and_policy",
    "ordered_source_manifest",
    "ordered_case_manifest",
    "source_m3_repeat_evidence",
    "m4_repeat_evidence",
    "result_m3_repeat_evidence",
    "measurement_gate_evidence",
    "decode_structure_immutability_evidence",
    "manual_review_evidence",
    "exact_duplicate_evidence",
    "phash_observation_evidence",
    "pair_quality_evidence",
    "dimension_eligibility",
    "fixed_priority_selection_trace",
    "selected_pair_manifest",
    "network_and_runtime_boundary",
)

_DIGEST = re.compile(r"[0-9a-f]{64}$")
_ID = re.compile(r"[0-9a-f]{32}$")
_OPAQUE_OUTPUT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_FIXED18 = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{18}$")
_SIGNED_FIXED18 = re.compile(r"-?(?:0|[1-9][0-9]*)\.[0-9]{18}$")
_RAW_KEYS: Final = {
    "measurement_version",
    "decimal_serialization_version",
    "source_p2_candidate_manifest_content_digest",
    "dimension_authority_manifest_content_digest",
    "measurement_config_digest",
    "measurement_quality_config_digest",
    "measurement_quality_manifest_content_digest",
    "confidence_kind",
    "reliability_kind",
    "runtime_manifest_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "source_repeat_certification_digest",
    "ordered_entries",
}
_RAW_ENTRY_KEYS: Final = {
    "dimension_key",
    "support_state",
    "raw_value_fixed18",
    "raw_confidence_fixed18",
    "raw_reliability_fixed18",
    "unsupported_reason",
}
_PROJECTION_KEYS: Final = {
    "measurement_version",
    "measurement_projection_version",
    "measurement_quantization_version",
    "source_p2_candidate_manifest_content_digest",
    "dimension_authority_manifest_content_digest",
    "measurement_config_digest",
    "measurement_quality_config_digest",
    "measurement_quality_manifest_content_digest",
    "confidence_kind",
    "reliability_kind",
    "runtime_manifest_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "source_repeat_certification_digest",
    "ordered_entries",
}
_PROJECTION_ENTRY_KEYS: Final = {
    "dimension_key",
    "support_state",
    "value_ppm",
    "unit",
    "confidence_ppm",
    "reliability_ppm",
    "unsupported_reason",
}
_FACTS_KEYS: Final = {
    "source_output_id",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "source_receipt_digest",
    "source_authority_digest",
    "qa_policy_digest",
    "source_qa_snapshot_digest",
    "source_landmark_digest",
    "source_measurement_digest",
    "source_provenance_digest",
    "source_measurement_projection",
    "source_measurement_projection_digest",
    "raw_measurement_authority",
    "raw_measurement_authority_digest",
    "adult_synthetic_attested",
    "original_formal_identity_id_status",
    "measurement_projection_version",
    "measurement_quantization_version",
    "source_p2_candidate_manifest_content_digest",
    "dimension_authority_manifest_content_digest",
    "source_measurement_observation",
    "source_measurement_observation_digest",
    "source_repeat_certification",
    "source_repeat_certification_digest",
}
_SOURCE_ENTRY_KEYS: Final = {
    "schema_version",
    "source_ordinal",
    "source_authority_kind",
    "source_authority_key",
    "source_admission_event_id",
    "source_admission_content_digest",
    "source_output_id",
    "source_asset_id",
    "source_asset_sha256",
    "source_asset_byte_size",
    "source_asset_mime_type",
    "source_asset_width",
    "source_asset_height",
    "source_receipt_digest",
    "source_authority_digest",
    "source_qa_snapshot_digest",
    "source_landmark_digest",
    "source_measurement_digest",
    "source_provenance_digest",
    "source_fact_snapshot_digest",
    "raw_measurement_authority_digest",
    "source_measurement_projection_digest",
    "adult_synthetic_attested",
    "original_formal_identity_id_status",
    "source_p2_candidate_manifest_content_digest",
    "dimension_authority_manifest_content_digest",
    "measurement_config_digest",
    "measurement_quality_config_digest",
    "measurement_quality_manifest_content_digest",
    "confidence_kind",
    "reliability_kind",
    "runtime_manifest_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "source_repeat_certification_digest",
    "import_config_digest",
    "ordered_supported_measurements",
    "record_digest",
}
_SOURCE_M3_KEYS: Final = {
    "schema_version",
    "source_m3_record_id",
    "source_ordinal",
    "source_authority_key",
    "source_admission_event_id",
    "source_asset_id",
    "source_asset_sha256",
    "repeat_index",
    "execution_receipt_digest",
    "vision_model_manifest_digest",
    "runtime_manifest_digest",
    "topology_digest",
    "canonical_output_digest",
    "landmark_digest",
    "measurement_observation",
    "measurement_observation_digest",
    "face_count",
    "landmark_count",
    "coordinates_finite",
    "coordinates_in_bounds",
    "repeat_gate_passed",
    "record_digest",
}
_RESULT_M3_KEYS: Final = {
    "schema_version",
    "result_m3_record_id",
    "case_id",
    "case_specification_digest",
    "result_output_id",
    "result_sha256",
    "repeat_index",
    "execution_receipt_digest",
    "vision_model_manifest_digest",
    "runtime_manifest_digest",
    "topology_digest",
    "canonical_output_digest",
    "landmark_digest",
    "measurement_observation",
    "measurement_observation_digest",
    "face_count",
    "landmark_count",
    "coordinates_finite",
    "coordinates_in_bounds",
    "observation_state",
    "repeat_gate_passed",
    "record_digest",
}
_GATE_KEYS: Final = {
    "schema_version",
    "case_id",
    "case_specification_digest",
    "dimension_key",
    "requested_direction",
    "requested_magnitude_ppm",
    "monotonicity_peer_case_id",
    "source_target_measurement",
    "ordered_source_control_measurements",
    "ordered_result_repeat_measurements",
    "measurement_evaluation_state",
    "gate_evaluation",
    "result_repeat_certification",
    "result_repeat_certification_digest",
    "record_digest",
}
_BINDING_KEYS: Final = {
    "schema_version",
    "source_manifest_digest",
    "case_manifest_digest",
    "screening_policy_digest",
    "runtime_manifest_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "measurement_execution_config",
    "measurement_config_digest",
    "measurement_quality_config_digest",
    "measurement_quality_manifest_content_digest",
    "confidence_kind",
    "reliability_kind",
    "manual_review_policy_digest",
    "duplicate_policy_digest",
    "phash_implementation_digest",
}
_REPORT_ROW_KEYS: Final = {
    "id",
    "schema_version",
    "canonical_payload",
    "content_digest",
    "created_at",
    "source_manifest_digest",
    "case_manifest_digest",
    "screening_policy_digest",
    "runtime_manifest_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "measurement_config_digest",
    "manual_review_policy_digest",
    "duplicate_policy_digest",
    "phash_implementation_digest",
    "report_payload",
    "report_digest",
    "status",
    "source_count",
    "case_count",
    "source_m3_repeat_count",
    "m4_execution_count",
    "result_m3_repeat_count",
    "manual_decision_count",
    "exact_sha_record_count",
    "phash_comparison_count",
    "candidate_pair_count",
    "selected_pair_count",
    "selected_result_side_count",
    "eligible_dimension_keys",
    "selected_dimension_keys",
    "selected_pair_manifest_digest",
}
_IDENTITY_ROW_KEYS: Final = {
    "id",
    "schema_version",
    "canonical_payload",
    "content_digest",
    "created_at",
    "formal_synthetic_identity_id",
    "formal_canonical_asset_id",
    "formal_canonical_asset_sha256",
    "formal_accepted_qa_run_id",
    "formal_accepted_qa_snapshot_digest",
    "admission_sequence",
    "admission_action",
    "admission_config_digest",
    "supersedes_id",
    "source_output_id",
    "source_receipt_digest",
    "source_authority_digest",
    "source_qa_snapshot_digest",
    "source_landmark_digest",
    "source_measurement_digest",
    "source_provenance_digest",
    "source_fact_snapshot",
    "source_fact_snapshot_digest",
    "source_measurement_projection",
    "source_measurement_projection_digest",
    "original_formal_identity_id_status",
    "adult_synthetic_attested",
    "importer_version",
    "import_config_digest",
    "source_authority_kind",
    "source_authority_key",
}
_SOURCE_CERT_KEYS: Final = {
    "schema_version",
    "subject",
    "runtime_manifest_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "measurement_config_digest",
    "measurement_quality_config_digest",
    "measurement_quality_manifest_content_digest",
    "reliability_kind",
    "repeat_count",
    "ordered_repeat_bindings",
    "certification_state",
    "certified_raw_reliability_fixed18",
    "certified_reliability_ppm",
    "source_repeat_certification_digest",
}
_RESULT_CERT_KEYS: Final = _SOURCE_CERT_KEYS - {"source_repeat_certification_digest"} | {
    "result_repeat_certification_digest"
}
_CASE_ENTRY_KEYS: Final = {
    "schema_version",
    "case_ordinal",
    "case_id",
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
    "geometry_ontology_version_digest",
    "dimension_key",
    "priority_index",
    "direction",
    "direction_index",
    "magnitude_ppm",
    "magnitude_index",
    "ordered_control_dimensions",
    "warp_plan_digest",
    "geometry_algorithm_version",
    "runtime_manifest_digest",
    "runtime_config_digest",
    "output_policy_version",
    "output_width",
    "output_height",
    "determinism_level",
    "execution_config_digest",
    "case_specification_digest",
    "record_digest",
}
_EXECUTION_AUTHORITY_KEYS: Final = {
    "screening_policy_digest",
    "runtime_manifest_digest",
    "vision_model_manifest_digest",
    "topology_digest",
    "measurement_config_digest",
    "manual_review_policy_digest",
    "duplicate_policy_digest",
    "phash_implementation_digest",
}
_CASE_BUILD_FIELDS: Final = {
    "geometry_ontology_version_digest",
    "warp_plan_digest",
    "geometry_algorithm_version",
    "runtime_config_digest",
    "output_policy_version",
    "output_width",
    "output_height",
    "determinism_level",
}
_M4_EXECUTION_KEYS: Final = {
    "schema_version",
    "m4_execution_record_id",
    "case_id",
    "case_specification_digest",
    "replay_index",
    "source_output_id",
    "source_asset_id",
    "source_asset_sha256",
    "result_output_id",
    "result_sha256",
    "result_byte_size",
    "result_mime_type",
    "result_width",
    "result_height",
    "changed_pixel_count",
    "warp_plan_digest",
    "geometry_algorithm_version",
    "runtime_manifest_digest",
    "runtime_config_digest",
    "determinism_level",
    "execution_receipt_digest",
    "execution_succeeded",
    "record_digest",
}
_M4_BUILD_FIELDS: Final = {
    "replay_index",
    "source_output_id",
    "result_output_id",
    "result_sha256",
    "result_byte_size",
    "result_mime_type",
    "result_width",
    "result_height",
    "changed_pixel_count",
    "execution_receipt_digest",
    "execution_succeeded",
}
_STRUCTURE_KEYS: Final = {
    "schema_version",
    "case_id",
    "case_specification_digest",
    "source_asset_id",
    "source_asset_sha256",
    "m4_execution_record_digests",
    "result_output_id",
    "result_sha256",
    "result_byte_size",
    "result_mime_type",
    "result_width",
    "result_height",
    "result_image_record_id",
    "source_decode_valid",
    "result_decode_valid",
    "bounded_dimensions_passed",
    "source_checksum_unchanged",
    "m4_replay_bytes_equal",
    "m4_replay_dimensions_equal",
    "changed_pixel_count_equal",
    "changed_pixel_count_positive",
    "immutable_result_binding_passed",
    "exact_lineage_passed",
    "target_and_controls_complete",
    "structure_gate_passed",
    "record_digest",
}
_STRUCTURE_BUILD_FIELDS: Final = {"result_image_record_id"}
_MANUAL_KEYS: Final = {
    "schema_version",
    "case_id",
    "result_sha256",
    "manual_review_version",
    "manual_review_policy_digest",
    "decision_sequence",
    "background_seam",
    "disconnected_contour",
    "duplicated_feature",
    "warp_tear",
    "verdict",
    "review_authority_digest",
    "manual_decision_digest",
}
_MANUAL_BUILD_FIELDS: Final = {
    "manual_review_version",
    "decision_sequence",
    "background_seam",
    "disconnected_contour",
    "duplicated_feature",
    "warp_tear",
    "review_authority_digest",
}
_SOURCE_IMAGE_KEYS: Final = {
    "schema_version",
    "image_record_ordinal",
    "image_record_id",
    "authority_role",
    "source_ordinal",
    "source_authority_key",
    "source_admission_event_id",
    "source_asset_id",
    "sha256",
    "byte_size",
    "mime_type",
    "width",
    "height",
    "image_record_digest",
}
_RESULT_IMAGE_KEYS: Final = {
    "schema_version",
    "image_record_ordinal",
    "image_record_id",
    "authority_role",
    "source_ordinal",
    "source_authority_key",
    "source_admission_event_id",
    "case_id",
    "case_specification_digest",
    "result_output_id",
    "deterministic_result_asset_id",
    "sha256",
    "byte_size",
    "mime_type",
    "width",
    "height",
    "image_record_digest",
}
_PHASH_EVIDENCE_KEYS: Final = {
    "schema_version",
    "implementation_digest",
    "bit_width",
    "threshold_policy",
    "ordered_record_signatures",
    "comparisons",
}
_PHASH_SIGNATURE_KEYS: Final = {
    "schema_version",
    "image_record_ordinal",
    "image_record_id",
    "image_record_digest",
    "image_sha256",
    "phash_hex",
    "signature_digest",
}
_PHASH_COMPARISON_KEYS: Final = {
    "schema_version",
    "comparison_ordinal",
    "left_image_record_ordinal",
    "left_image_record_id",
    "left_signature_digest",
    "right_image_record_ordinal",
    "right_image_record_id",
    "right_signature_digest",
    "hamming_distance",
    "comparison_digest",
}
_EXACT_DUPLICATE_KEYS: Final = {
    "schema_version",
    "image_records",
    "all_record_sha_unique",
    "source_sha_unique",
    "result_sha_unique",
    "source_result_sha_disjoint",
    "exact_sha_gate_passed",
}
_PAIR_WRAPPER_KEYS: Final = {
    "schema_version",
    "pair_screening_record_payload",
    "pair_screening_record_digest",
}
_PAIR_PAYLOAD_KEYS: Final = {
    "pair_record_id",
    "source_ordinal",
    "source_authority_key",
    "source_admission_event_id",
    "source_asset_id",
    "source_asset_sha256",
    "dimension_key",
    "priority_index",
    "magnitude_ppm",
    "screening_policy_digest",
    "left",
    "right",
    "same_source_gate_passed",
    "opposed_direction_gate_passed",
    "equal_magnitude_gate_passed",
    "pair_side_gates_passed",
    "empty_lock_policy_gate_passed",
    "pair_quality_state",
    "pair_quality_ppm",
    "lock_conclusion",
    "lock_policy_digest",
    "pair_gate_passed",
}
_PAIR_SIDE_COMMON_KEYS: Final = {
    "schema_version",
    "measurement_evaluation_state",
    "case_id",
    "case_specification_digest",
    "requested_direction",
    "requested_magnitude_ppm",
    "result_output_id",
    "result_asset_id",
    "result_asset_sha256",
    "result_asset_byte_size",
    "result_asset_mime_type",
    "result_asset_width",
    "result_asset_height",
    "asset_variant_id",
    "asset_variant_type",
    "lineage_digest",
    "image_record_id",
    "image_record_digest",
    "result_m3_record_digests",
    "measurement_gate_record_digest",
    "decode_structure_record_digest",
    "manual_decision_digest",
    "automated_gate_digest",
    "automated_gate_passed",
    "manual_gate_passed",
    "side_gate_passed",
    "side_quality_state",
    "side_quality_component_ppm",
}
_EVALUATED_SIDE_KEYS: Final = _PAIR_SIDE_COMMON_KEYS | {
    "raw_signed_target_delta_fixed18",
    "raw_target_absolute_delta_fixed18",
    "raw_max_control_drift_fixed18",
    "measured_signed_delta_ppm",
    "drift_ppm",
}
_UNSUPPORTED_SIDE_KEYS: Final = _PAIR_SIDE_COMMON_KEYS | {
    "unsupported_repeat_indexes",
    "ordered_unsupported_reasons",
}
_DIMENSION_KEYS: Final = {
    "schema_version",
    "dimension_key",
    "priority_index",
    "ordered_pair_screening_record_digests",
    "ordered_side_automated_gate_digests",
    "sixteen_side_gate_digest",
    "eight_pair_gate_digest",
    "all_sixteen_side_gates_passed",
    "all_eight_pair_gates_passed",
    "all_manual_gates_passed",
    "global_exact_sha_gate_passed",
    "empty_lock_policy_gate_passed",
    "eligible",
    "failure_reasons",
    "record_digest",
}
_SELECTION_KEYS: Final = {
    "schema_version",
    "selection_step",
    "dimension_key",
    "priority_index",
    "dimension_eligibility_record_digest",
    "eligible",
    "eligible_rank",
    "selection_decision",
    "selection_slot",
    "selected",
    "record_digest",
}
_SELECTED_PAIR_KEYS: Final = {
    "schema_version",
    "selected_pair_ordinal",
    "selected_dimension_slot",
    "dimension_key",
    "priority_index",
    "source_ordinal",
    "source_authority_key",
    "source_admission_event_id",
    "magnitude_ppm",
    "pair_record_id",
    "pair_screening_record_digest",
    "left_case_id",
    "left_result_asset_id",
    "left_result_asset_sha256",
    "left_asset_variant_id",
    "right_case_id",
    "right_result_asset_id",
    "right_result_asset_sha256",
    "right_asset_variant_id",
    "entry_digest",
}
_NETWORK_BOUNDARY_KEYS: Final = {
    "schema_version",
    "public_internet_egress",
    "localhost_and_docker_internal_network",
    "proxy_environment_present",
    "production_provider_calls",
    "runtime_generation_calls",
    "boundary_receipt_digest",
}
_SOURCE_GRAPH_PACKET_KEYS: Final = {
    "facts",
    "identity_row",
    "source_entry",
    "source_manifest_digest",
    "source_records",
}
_VARIANT_BINDING_KEYS: Final = {
    "source_asset_id",
    "source_asset_sha256",
    "result_asset_id",
    "result_asset_sha256",
    "asset_variant_id",
    "asset_variant_type",
    "case_specification_digest",
}
_PERSISTED_BOOLEAN_FIELDS: Final = frozenset(
    {
        "adult_synthetic_attested",
        "coordinates_finite",
        "coordinates_in_bounds",
        "repeat_gate_passed",
        "execution_succeeded",
        "direction_gate_passed",
        "target_min_gate_passed",
        "target_max_gate_passed",
        "control_drift_gate_passed",
        "magnitude_monotonicity_gate_passed",
        "measurement_gate_passed",
        "source_decode_valid",
        "result_decode_valid",
        "bounded_dimensions_passed",
        "source_checksum_unchanged",
        "m4_replay_bytes_equal",
        "m4_replay_dimensions_equal",
        "changed_pixel_count_equal",
        "changed_pixel_count_positive",
        "immutable_result_binding_passed",
        "exact_lineage_passed",
        "target_and_controls_complete",
        "structure_gate_passed",
        "background_seam",
        "disconnected_contour",
        "duplicated_feature",
        "warp_tear",
        "all_record_sha_unique",
        "source_sha_unique",
        "result_sha_unique",
        "source_result_sha_disjoint",
        "exact_sha_gate_passed",
        "automated_gate_passed",
        "manual_gate_passed",
        "side_gate_passed",
        "same_source_gate_passed",
        "opposed_direction_gate_passed",
        "equal_magnitude_gate_passed",
        "pair_side_gates_passed",
        "empty_lock_policy_gate_passed",
        "pair_gate_passed",
        "all_sixteen_side_gates_passed",
        "all_eight_pair_gates_passed",
        "all_manual_gates_passed",
        "global_exact_sha_gate_passed",
        "eligible",
        "selected",
        "localhost_and_docker_internal_network",
        "proxy_environment_present",
    }
)
_PERSISTED_BOOLEAN_ARRAY_FIELDS: Final = frozenset({"result_m3_repeat_gate_results"})
_SUPPORTED_OBSERVABILITY_MIN_FIXED18_UNITS: Final = 1_000_000_000_000
_FAILURE_REASONS: Final = (
    "ONE_OR_MORE_SIDE_GATES_FAILED",
    "ONE_OR_MORE_PAIR_GATES_FAILED",
    "ONE_OR_MORE_MANUAL_GATES_FAILED",
    "GLOBAL_EXACT_SHA_GATE_FAILED",
    "EMPTY_LOCK_POLICY_GATE_FAILED",
)
_PHASH_HEX = re.compile(r"[0-9a-f]{16}$")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class D02AuthorityError(ValueError):
    """An exact D02 Candidate 3 authority contract failed."""


def _fail(message: str) -> NoReturn:
    raise D02AuthorityError(message)


def _validate_persisted_boolean_closure(value: object) -> None:
    """Enforce Revision 9's exhaustive Boolean names on one exact schema envelope."""
    if not isinstance(value, Mapping):
        return
    for key, item in value.items():
        if not isinstance(key, str):
            _fail("persisted JSON object keys must be strings")
        if key in _PERSISTED_BOOLEAN_FIELDS:
            if type(item) is not bool:
                _fail(f"persisted Boolean field {key} must be a literal Boolean")
        elif key in _PERSISTED_BOOLEAN_ARRAY_FIELDS:
            if not isinstance(item, list) or any(type(member) is not bool for member in item):
                _fail(f"persisted Boolean array {key} must contain only literal Booleans")
        elif type(item) is bool:
            _fail("unlisted persisted Boolean field is invalid")


def _exact(value: object, keys: set[str], label: str) -> dict[str, Any]:
    _validate_persisted_boolean_closure(value)
    if not isinstance(value, Mapping) or set(value) != keys:
        _fail(f"{label} exact keys do not match")
    return {str(key): item for key, item in cast(Mapping[str, Any], value).items()}


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase hexadecimal ID")
    return value


def _opaque_output_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _OPAQUE_OUTPUT_ID.fullmatch(value) is None:
        _fail(f"{label} must be an opaque output ID")
    return value


def derive_local_source_authority_key(
    *,
    source_output_id: object,
    source_asset_id: object,
    source_asset_sha256: object,
    source_receipt_digest: object,
) -> str:
    """Replay the accepted generated local SourceAuthorityKey/v1 helper."""
    payload: dict[str, JsonValue] = {
        "source_authority_kind": LOCAL_SOURCE_AUTHORITY_KIND,
        "source_output_id": _opaque_output_id(source_output_id, "source output id"),
        "formal_canonical_asset_id": _id(source_asset_id, "source Asset ID"),
        "source_asset_sha256": _digest(source_asset_sha256, "source Asset sha256"),
        "source_receipt_digest": _digest(source_receipt_digest, "source receipt digest"),
    }
    return mirror_demo_digest(SOURCE_AUTHORITY_KEY_DOMAIN, payload)


def derive_imported_asset_id(
    *,
    asset_role: object,
    semantic_role: object,
    sha256: object,
    byte_size: object,
    mime_type: object,
    width: object,
    height: object,
) -> str:
    """Replay the accepted typed D02ImportedAssetId/v1 preimage."""
    if asset_role != "synthetic" or semantic_role not in {"SOURCE", "SELECTED_RESULT"}:
        _fail("imported Asset role or semantic role is invalid")
    digest = _digest(sha256, "imported Asset sha256")
    if type(byte_size) is not int or not 1 <= byte_size <= 9_223_372_036_854_775_807:
        _fail("imported Asset byte size is invalid")
    if mime_type not in {"image/jpeg", "image/png"}:
        _fail("imported Asset MIME type is invalid")
    if (
        type(width) is not int
        or not 1 <= width <= 2_147_483_647
        or type(height) is not int
        or not 1 <= height <= 2_147_483_647
    ):
        _fail("imported Asset dimensions are invalid")
    payload: dict[str, JsonValue] = {
        "asset_role": "synthetic",
        "semantic_role": semantic_role,
        "sha256": digest,
        "byte_size": byte_size,
        "mime_type": mime_type,
        "width": width,
        "height": height,
    }
    return mirror_demo_digest(IMPORTED_ASSET_ID_DOMAIN, payload)[:32]


def derive_asset_variant_id(
    *,
    variant_type: object,
    source_asset_id: object,
    source_asset_sha256: object,
    result_asset_id: object,
    result_asset_sha256: object,
    case_specification_digest: object,
) -> str:
    """Replay the accepted typed D02AssetVariantId/v1 preimage."""
    if variant_type != VARIANT_TYPE:
        _fail("D02 AssetVariant type is invalid")
    source_id = _id(source_asset_id, "D02 AssetVariant source Asset ID")
    result_id = _id(result_asset_id, "D02 AssetVariant result Asset ID")
    if source_id == result_id:
        _fail("D02 AssetVariant source and result Assets must be distinct")
    payload: dict[str, JsonValue] = {
        "variant_type": VARIANT_TYPE,
        "source_asset_id": source_id,
        "source_asset_sha256": _digest(source_asset_sha256, "D02 AssetVariant source Asset sha256"),
        "result_asset_id": result_id,
        "result_asset_sha256": _digest(result_asset_sha256, "D02 AssetVariant result Asset sha256"),
        "case_specification_digest": _digest(
            case_specification_digest, "D02 AssetVariant case specification digest"
        ),
    }
    return mirror_demo_digest(ASSET_VARIANT_ID_DOMAIN, payload)[:32]


def _fixed(value: object, label: str) -> str:
    if not isinstance(value, str) or _FIXED18.fullmatch(value) is None:
        _fail(f"{label} must be canonical non-negative fixed18")
    return value


def _signed_fixed(value: object, label: str) -> str:
    if not isinstance(value, str) or _SIGNED_FIXED18.fullmatch(value) is None:
        _fail(f"{label} must be canonical signed fixed18")
    if value.startswith("-") and set(value[1:].replace(".", "")) == {"0"}:
        _fail(f"{label} must normalize negative zero")
    return value


def _fixed18_units(value: object, label: str, *, signed: bool = False) -> int:
    """Return the exact 10^-18 integer representation without float arithmetic."""
    text = _signed_fixed(value, label) if signed else _fixed(value, label)
    negative = text.startswith("-")
    digits = text[1:] if negative else text
    whole, fraction = digits.split(".", maxsplit=1)
    result = int(whole) * 1_000_000_000_000_000_000 + int(fraction)
    return -result if negative else result


def _ppm_from_units(units: int) -> int:
    """Fixed18 -> ppm, round-half-even, matching Packet A's quantizer."""
    sign = -1 if units < 0 else 1
    absolute = abs(units)
    quotient, remainder = divmod(absolute, 1_000_000_000_000)
    if remainder > 500_000_000_000 or (remainder == 500_000_000_000 and quotient % 2 == 1):
        quotient += 1
    return sign * quotient


def _bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        _fail(f"{label} must be a JSON boolean")
    return value


def _validate_admission_event_shape(
    row: Mapping[str, object],
) -> tuple[int, str, str | None]:
    sequence = row.get("admission_sequence")
    action = row.get("admission_action")
    supersedes_id = row.get("supersedes_id")
    if type(sequence) is not int or not 1 <= sequence <= 2_147_483_647:
        _fail("identity admission sequence must be a positive integer within PostgreSQL range")
    if not isinstance(action, str) or action not in {"ADMIT", "REVOKE"}:
        _fail("identity admission action is invalid")
    admission_config_digest = _digest(
        row.get("admission_config_digest"), "identity admission config digest"
    )
    if (
        row.get("schema_version") == IDENTITY_SCHEMA
        and row.get("source_output_id") is not None
        and admission_config_digest != LOCAL_ADMISSION_CONFIG_DIGEST
    ):
        _fail("local v3 identity admission config digest is not the frozen D02 authority")
    if sequence == 1:
        if action != "ADMIT" or supersedes_id is not None:
            _fail("first identity admission event must be ADMIT without a predecessor")
    elif supersedes_id is None:
        _fail("later identity admission event must supersede a predecessor")
    else:
        supersedes_id = _id(supersedes_id, "identity admission predecessor ID")
    row_id = _id(row.get("id"), "identity admission event ID")
    if supersedes_id == row_id:
        _fail("identity admission event cannot supersede itself")
    return sequence, action, supersedes_id


def _ppm(value: object, label: str, *, signed: bool = False) -> int:
    if type(value) is not int or isinstance(value, bool):
        _fail(f"{label} must be an integer ppm")
    result = int(value)
    lower = -1_000_000 if signed else 0
    if result < lower or result > 1_000_000:
        _fail(f"{label} is outside the ppm range")
    return result


def _payload(value: Mapping[str, object], excluded: set[str]) -> dict[str, JsonValue]:
    try:
        # This intentionally reuses Packet A's integer-only canonical leaf gate.
        canonical_json_bytes(value)
        result = {key: item for key, item in value.items() if key not in excluded}
        canonical_json_bytes(result)
        return cast(dict[str, JsonValue], result)
    except MeasurementQualityError as error:
        raise D02AuthorityError(str(error)) from error


def _canonical_bytes(value: object, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise D02AuthorityError(f"{label} is not canonical JSON") from error


def _require_canonical_match(value: object, expected: object, label: str) -> None:
    if _canonical_bytes(value, label) != _canonical_bytes(expected, f"expected {label}"):
        _fail(f"{label} does not replay from authoritative evidence")


def _sequence_digest(schema: str, value: Sequence[Mapping[str, object]]) -> str:
    canonical = _canonical_bytes(list(value), f"{schema} sequence")
    return hashlib.sha256(schema.encode("utf-8") + b"\n" + canonical).hexdigest()


def _digest_for(schema: str, value: Mapping[str, object], excluded: set[str]) -> str:
    return mirror_demo_digest(schema, _payload(value, excluded))


def _require_digest_match(
    schema: str, value: Mapping[str, object], key: str, excluded: set[str]
) -> None:
    claimed = _digest(value.get(key), key)
    if _digest_for(schema, value, excluded | {key}) != claimed:
        _fail(f"{key} does not replay")


def validate_measurement_observation(
    value: object, *, role: str | None = None
) -> Mapping[str, Any]:
    """Replay Packet A's observation envelope before using it in this DAG."""
    item = _exact(
        value,
        {
            "schema_version",
            "observation_role",
            "subject",
            "canonical_output_digest",
            "landmark_digest",
            "runtime_manifest_digest",
            "vision_model_manifest_digest",
            "topology_digest",
            "measurement_config_digest",
            "measurement_quality_config_digest",
            "measurement_quality_manifest_content_digest",
            "confidence_kind",
            "ordered_measurements",
            "measurement_observation_digest",
        },
        "measurement observation",
    )
    if item["schema_version"] != "mirror.demo/D02MeasurementObservation/v1":
        _fail("measurement observation schema is invalid")
    if item["observation_role"] not in {"SOURCE", "RESULT"} or (
        role is not None and item["observation_role"] != role
    ):
        _fail("measurement observation role is invalid")
    expected = {
        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
        "topology_digest": TOPOLOGY_DIGEST,
        "measurement_config_digest": MEASUREMENT_CONFIG_DIGEST,
        "measurement_quality_config_digest": QUALITY_CONFIG_DIGEST,
        "measurement_quality_manifest_content_digest": QUALITY_MANIFEST_DIGEST,
        "confidence_kind": CONFIDENCE_KIND,
    }
    if any(item[key] != expected_value for key, expected_value in expected.items()):
        _fail("measurement observation authority binding differs from accepted manifest")
    _digest(item["canonical_output_digest"], "canonical_output_digest")
    _digest(item["landmark_digest"], "landmark_digest")
    subject = item["subject"]
    if item["observation_role"] == "SOURCE":
        source = _exact(
            subject,
            {"schema_version", "source_output_id", "source_asset_id", "source_asset_sha256"},
            "source subject",
        )
        if source["schema_version"] != "mirror.demo/D02SourceObservationSubject/v1":
            _fail("source subject schema is invalid")
        _opaque_output_id(source["source_output_id"], "source output id")
        _id(source["source_asset_id"], "source asset id")
        _digest(source["source_asset_sha256"], "source asset sha256")
    else:
        result = _exact(
            subject,
            {
                "schema_version",
                "case_id",
                "case_specification_digest",
                "result_output_id",
                "result_sha256",
            },
            "result subject",
        )
        if result["schema_version"] != "mirror.demo/D02ResultObservationSubject/v1":
            _fail("result subject schema is invalid")
        _id(result["case_id"], "case id")
        _opaque_output_id(result["result_output_id"], "result output id")
        _digest(result["case_specification_digest"], "case specification digest")
        _digest(result["result_sha256"], "result sha256")
    entries = item["ordered_measurements"]
    if not isinstance(entries, list) or len(entries) != len(DIMENSIONS):
        _fail("measurement observation entries must be the ordered six dimensions")
    for dimension, entry in zip(DIMENSIONS, entries, strict=True):
        actual = _exact(
            entry,
            {
                "schema_version",
                "dimension_key",
                "support_state",
                "raw_value_fixed18",
                "observability_state",
                "raw_observability_fixed18",
                "unsupported_reason",
            },
            "observation entry",
        )
        if (
            actual["schema_version"] != "mirror.demo/D02MeasurementObservationEntry/v1"
            or actual["dimension_key"] != dimension
        ):
            _fail("measurement observation entry order or schema is invalid")
        if actual["support_state"] == "SUPPORTED":
            if (
                _fixed18_units(actual["raw_value_fixed18"], "supported raw value")
                > 1_000_000_000_000_000_000
            ):
                _fail("supported observation raw value exceeds one")
            observable = _fixed(actual["raw_observability_fixed18"], "supported observability")
            observable_units = _fixed18_units(observable, "supported observability")
            if (
                actual["observability_state"] != "COMPUTED"
                or actual["unsupported_reason"] is not None
                or observable_units < _SUPPORTED_OBSERVABILITY_MIN_FIXED18_UNITS
                or observable_units > 1_000_000_000_000_000_000
                or ppm_from_fixed18(observable) < 1
            ):
                _fail("supported observation union is invalid")
        elif actual["support_state"] == "UNSUPPORTED":
            reason = actual["unsupported_reason"]
            if actual["raw_value_fixed18"] is not None or reason not in {
                "RUNTIME_UNSUPPORTED",
                "MISSING_MEASUREMENT",
                "OUT_OF_BOUNDS",
                "LOW_CONFIDENCE",
            }:
                _fail("unsupported observation union is invalid")
            if reason == "LOW_CONFIDENCE":
                observability = _fixed(
                    actual["raw_observability_fixed18"], "low-confidence observability"
                )
                if (
                    actual["observability_state"] != "COMPUTED"
                    or _fixed18_units(observability, "low-confidence observability")
                    >= _SUPPORTED_OBSERVABILITY_MIN_FIXED18_UNITS
                ):
                    _fail("low-confidence observation union is invalid")
            elif (
                actual["observability_state"] != "NOT_COMPUTABLE"
                or actual["raw_observability_fixed18"] is not None
            ):
                _fail("not-computable observation union is invalid")
        else:
            _fail("observation support state is invalid")
    _require_digest_match(
        "mirror.demo/D02MeasurementObservation/v1",
        item,
        "measurement_observation_digest",
        {"schema_version"},
    )
    return item


def validate_source_certificate(value: object) -> Mapping[str, Any]:
    cert = _exact(value, _SOURCE_CERT_KEYS, "source repeat certificate")
    if cert["schema_version"] != "mirror.demo/D02SourceRepeatDeterminismCertification/v1":
        _fail("source certificate schema is invalid")
    # Exact keys above deliberately exclude all post-admission fields and aliases.
    validate_measurement_subject(cert["subject"], "SOURCE")
    _validate_certificate_common(cert, "source_repeat_certification_digest", source=True)
    return cert


def _validate_source_certificate_observation_crosslinks(
    certificate: Mapping[str, Any], observation: Mapping[str, Any]
) -> None:
    if certificate["subject"] != observation["subject"]:
        _fail("source certificate subject does not match observation")
    bindings = cast(list[Mapping[str, Any]], certificate["ordered_repeat_bindings"])
    expected = {
        "canonical_output_digest": observation["canonical_output_digest"],
        "landmark_digest": observation["landmark_digest"],
        "measurement_observation_digest": observation["measurement_observation_digest"],
    }
    if any(
        binding[key] != expected_value
        for binding in bindings
        for key, expected_value in expected.items()
    ):
        _fail("source certificate digest lineage does not match observation")


def validate_result_certificate(
    value: object, records: Sequence[Mapping[str, object]]
) -> Mapping[str, Any]:
    cert = _exact(value, _RESULT_CERT_KEYS, "result repeat certificate")
    if cert["schema_version"] != "mirror.demo/D02ResultRepeatDeterminismCertification/v1":
        _fail("result certificate schema is invalid")
    validate_measurement_subject(cert["subject"], "RESULT")
    _validate_certificate_common(cert, "result_repeat_certification_digest", source=False)
    if len(records) != 3:
        _fail("result certification requires three existing ResultM3 records")
    for binding, record in zip(cert["ordered_repeat_bindings"], records, strict=True):
        verified_record = validate_result_m3_record(record)
        if not isinstance(binding, Mapping):
            _fail("result certificate binding is invalid")
        semantic_keys = (
            "result_m3_record_id",
            "repeat_index",
            "execution_receipt_digest",
            "canonical_output_digest",
            "landmark_digest",
            "measurement_observation_digest",
            "face_count",
            "landmark_count",
            "coordinates_finite",
            "coordinates_in_bounds",
            "observation_state",
            "repeat_gate_passed",
        )
        if any(binding.get(key) != verified_record[key] for key in semantic_keys):
            _fail("result certificate semantic tuple does not match ResultM3 record")
    return cert


def validate_measurement_subject(value: object, role: str) -> Mapping[str, Any]:
    if role == "SOURCE":
        subject = _exact(
            value,
            {"schema_version", "source_output_id", "source_asset_id", "source_asset_sha256"},
            "source subject",
        )
        if subject["schema_version"] != "mirror.demo/D02SourceObservationSubject/v1":
            _fail("source subject schema is invalid")
        _opaque_output_id(subject["source_output_id"], "source output id")
        _id(subject["source_asset_id"], "source asset id")
        _digest(subject["source_asset_sha256"], "source asset sha256")
        return subject
    subject = _exact(
        value,
        {
            "schema_version",
            "case_id",
            "case_specification_digest",
            "result_output_id",
            "result_sha256",
        },
        "result subject",
    )
    if subject["schema_version"] != "mirror.demo/D02ResultObservationSubject/v1":
        _fail("result subject schema is invalid")
    _id(subject["case_id"], "case id")
    _opaque_output_id(subject["result_output_id"], "result output id")
    _digest(subject["case_specification_digest"], "case specification digest")
    _digest(subject["result_sha256"], "result sha256")
    return subject


def _validate_certificate_common(
    cert: Mapping[str, object], digest_key: str, *, source: bool
) -> None:
    expected = {
        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
        "topology_digest": TOPOLOGY_DIGEST,
        "measurement_config_digest": MEASUREMENT_CONFIG_DIGEST,
        "measurement_quality_config_digest": QUALITY_CONFIG_DIGEST,
        "measurement_quality_manifest_content_digest": QUALITY_MANIFEST_DIGEST,
        "reliability_kind": RELIABILITY_KIND,
    }
    if any(cert[key] != expected_value for key, expected_value in expected.items()):
        _fail("repeat certificate binding differs from accepted manifest")
    if (
        type(cert["repeat_count"]) is not int
        or cert["repeat_count"] != 3
        or cert["certification_state"] != "CERTIFIED_EXACT_REPEAT"
        or cert["certified_raw_reliability_fixed18"] != "1.000000000000000000"
        or type(cert["certified_reliability_ppm"]) is not int
        or cert["certified_reliability_ppm"] != 1_000_000
    ):
        _fail("repeat certificate state is invalid")
    bindings = cert["ordered_repeat_bindings"]
    if not isinstance(bindings, list) or len(bindings) != 3:
        _fail("repeat certificate requires three ordered bindings")
    expected_keys = {
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
    }
    if not source:
        expected_keys |= {"result_m3_record_id", "observation_state"}
    for index, binding in enumerate(bindings, start=1):
        actual = _exact(binding, expected_keys, "repeat binding")
        if (
            type(actual["repeat_index"]) is not int
            or actual["repeat_index"] != index
            or type(actual["face_count"]) is not int
            or actual["face_count"] != 1
            or type(actual["landmark_count"]) is not int
            or actual["landmark_count"] != 478
            or actual["coordinates_finite"] is not True
            or actual["coordinates_in_bounds"] is not True
        ):
            _fail("repeat certificate binding structural precondition failed")
        for key in (
            "execution_receipt_digest",
            "canonical_output_digest",
            "landmark_digest",
            "measurement_observation_digest",
        ):
            _digest(actual[key], key)
        if not source:
            _id(actual["result_m3_record_id"], "result m3 record id")
            if actual["observation_state"] not in {"SUPPORTED", "UNSUPPORTED_EXPLICIT"}:
                _fail("result observation state is invalid")
            expected_repeat_gate = actual["observation_state"] == "SUPPORTED"
            if actual["repeat_gate_passed"] is not expected_repeat_gate:
                _fail("result repeat gate does not match observation support state")
        elif actual["repeat_gate_passed"] is not True:
            _fail("source repeat certificate requires every repeat Gate to pass")
    for key in ("canonical_output_digest", "landmark_digest", "measurement_observation_digest"):
        if len({binding[key] for binding in bindings if isinstance(binding, Mapping)}) != 1:
            _fail("repeat certificate digest family does not agree")
    if (
        not source
        and len(
            {binding["result_m3_record_id"] for binding in bindings if isinstance(binding, Mapping)}
        )
        != 3
    ):
        _fail("result certificate must reference three distinct records")
    if (
        not source
        and len(
            {binding["observation_state"] for binding in bindings if isinstance(binding, Mapping)}
        )
        != 1
    ):
        _fail("result certificate observation states must be semantically equal")
    _require_digest_match(str(cert["schema_version"]), cert, digest_key, {"schema_version"})


def build_raw_measurement_authority(
    observation: Mapping[str, object],
    certificate: Mapping[str, object],
    *,
    source_p2_candidate_manifest_content_digest: str,
    dimension_authority_manifest_content_digest: str,
) -> dict[str, JsonValue]:
    verified_observation = validate_measurement_observation(observation, role="SOURCE")
    verified_certificate = validate_source_certificate(certificate)
    _validate_source_certificate_observation_crosslinks(verified_certificate, verified_observation)
    entries: list[JsonValue] = []
    for entry in cast(list[Mapping[str, Any]], verified_observation["ordered_measurements"]):
        assert isinstance(entry, Mapping)
        if entry["support_state"] == "SUPPORTED":
            entries.append(
                {
                    "dimension_key": entry["dimension_key"],
                    "support_state": "SUPPORTED",
                    "raw_value_fixed18": entry["raw_value_fixed18"],
                    "raw_confidence_fixed18": entry["raw_observability_fixed18"],
                    "raw_reliability_fixed18": "1.000000000000000000",
                    "unsupported_reason": None,
                }
            )
        else:
            entries.append(
                {
                    "dimension_key": entry["dimension_key"],
                    "support_state": "UNSUPPORTED",
                    "raw_value_fixed18": None,
                    "raw_confidence_fixed18": None,
                    "raw_reliability_fixed18": None,
                    "unsupported_reason": entry["unsupported_reason"],
                }
            )
    raw: dict[str, JsonValue] = {
        "measurement_version": "demo-d02-landmark-distance-v1",
        "decimal_serialization_version": "fixed18-round-half-even-v1",
        "source_p2_candidate_manifest_content_digest": source_p2_candidate_manifest_content_digest,
        "dimension_authority_manifest_content_digest": dimension_authority_manifest_content_digest,
        "measurement_config_digest": MEASUREMENT_CONFIG_DIGEST,
        "measurement_quality_config_digest": QUALITY_CONFIG_DIGEST,
        "measurement_quality_manifest_content_digest": QUALITY_MANIFEST_DIGEST,
        "confidence_kind": CONFIDENCE_KIND,
        "reliability_kind": RELIABILITY_KIND,
        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
        "topology_digest": TOPOLOGY_DIGEST,
        "source_repeat_certification_digest": verified_certificate[
            "source_repeat_certification_digest"
        ],
        "ordered_entries": entries,
    }
    validate_raw_measurement_authority(raw)
    return raw


def validate_raw_measurement_authority(value: object) -> Mapping[str, Any]:
    raw = _exact(value, _RAW_KEYS, "raw measurement authority")
    _validate_shared_quality_fields(raw)
    if (
        raw["measurement_version"] != "demo-d02-landmark-distance-v1"
        or raw["decimal_serialization_version"] != "fixed18-round-half-even-v1"
    ):
        _fail("raw authority version token is invalid")
    _validate_raw_entries(raw["ordered_entries"])
    return raw


def build_morphology_projection(raw: Mapping[str, object]) -> dict[str, JsonValue]:
    verified_raw = validate_raw_measurement_authority(raw)
    entries: list[JsonValue] = []
    for entry in cast(list[Mapping[str, Any]], verified_raw["ordered_entries"]):
        assert isinstance(entry, Mapping)
        if entry["support_state"] == "SUPPORTED":
            entries.append(
                {
                    "dimension_key": entry["dimension_key"],
                    "support_state": "SUPPORTED",
                    "value_ppm": ppm_from_fixed18(str(entry["raw_value_fixed18"])),
                    "unit": "FACE_HEIGHT_PPM",
                    "confidence_ppm": ppm_from_fixed18(str(entry["raw_confidence_fixed18"])),
                    "reliability_ppm": ppm_from_fixed18(str(entry["raw_reliability_fixed18"])),
                    "unsupported_reason": None,
                }
            )
        else:
            entries.append(
                {
                    "dimension_key": entry["dimension_key"],
                    "support_state": "UNSUPPORTED",
                    "value_ppm": None,
                    "unit": "FACE_HEIGHT_PPM",
                    "confidence_ppm": None,
                    "reliability_ppm": None,
                    "unsupported_reason": entry["unsupported_reason"],
                }
            )
    projection: dict[str, JsonValue] = {
        "measurement_version": verified_raw["measurement_version"],
        "measurement_projection_version": "demo-d02-morphology-projection-v2",
        "measurement_quantization_version": "fixed18-to-ppm-round-half-even-v1",
        "source_p2_candidate_manifest_content_digest": verified_raw[
            "source_p2_candidate_manifest_content_digest"
        ],
        "dimension_authority_manifest_content_digest": verified_raw[
            "dimension_authority_manifest_content_digest"
        ],
        "measurement_config_digest": verified_raw["measurement_config_digest"],
        "measurement_quality_config_digest": verified_raw["measurement_quality_config_digest"],
        "measurement_quality_manifest_content_digest": verified_raw[
            "measurement_quality_manifest_content_digest"
        ],
        "confidence_kind": verified_raw["confidence_kind"],
        "reliability_kind": verified_raw["reliability_kind"],
        "runtime_manifest_digest": verified_raw["runtime_manifest_digest"],
        "vision_model_manifest_digest": verified_raw["vision_model_manifest_digest"],
        "topology_digest": verified_raw["topology_digest"],
        "source_repeat_certification_digest": verified_raw["source_repeat_certification_digest"],
        "ordered_entries": entries,
    }
    validate_morphology_projection(projection, raw=verified_raw)
    return projection


def validate_morphology_projection(
    value: object, *, raw: Mapping[str, object] | None = None
) -> Mapping[str, object]:
    projection = _exact(value, _PROJECTION_KEYS, "morphology projection")
    _validate_shared_quality_fields(projection)
    if (
        projection["measurement_projection_version"] != "demo-d02-morphology-projection-v2"
        or projection["measurement_quantization_version"] != "fixed18-to-ppm-round-half-even-v1"
    ):
        _fail("projection version token is invalid")
    entries = projection["ordered_entries"]
    if not isinstance(entries, list) or len(entries) != len(DIMENSIONS):
        _fail("projection must have six ordered entries")
    for dimension, entry in zip(DIMENSIONS, entries, strict=True):
        actual = _exact(entry, _PROJECTION_ENTRY_KEYS, "projection entry")
        if actual["dimension_key"] != dimension or actual["unit"] != "FACE_HEIGHT_PPM":
            _fail("projection entry dimension or unit is invalid")
        if actual["support_state"] == "SUPPORTED":
            if (
                not all(
                    type(actual[key]) is int and 1 <= int(actual[key]) <= 1_000_000
                    for key in ("value_ppm", "confidence_ppm", "reliability_ppm")
                )
                or actual["unsupported_reason"] is not None
            ):
                _fail("supported projection union is invalid")
        elif actual["support_state"] == "UNSUPPORTED":
            if any(
                actual[key] is not None
                for key in ("value_ppm", "confidence_ppm", "reliability_ppm")
            ):
                _fail("unsupported projection union is invalid")
        else:
            _fail("projection support state is invalid")
    if raw is not None:
        verified_raw = validate_raw_measurement_authority(raw)
        if any(
            projection[key] != verified_raw[key]
            for key in _RAW_KEYS - {"decimal_serialization_version", "ordered_entries"}
        ):
            _fail("raw/projection authority binding differs")
        raw_entries = cast(list[Mapping[str, Any]], verified_raw["ordered_entries"])
        for raw_entry, projection_entry in zip(raw_entries, entries, strict=True):
            assert isinstance(raw_entry, Mapping) and isinstance(projection_entry, Mapping)
            if raw_entry["support_state"] == "SUPPORTED" and (
                projection_entry["value_ppm"]
                != ppm_from_fixed18(str(raw_entry["raw_value_fixed18"]))
                or projection_entry["confidence_ppm"]
                != ppm_from_fixed18(str(raw_entry["raw_confidence_fixed18"]))
                or projection_entry["reliability_ppm"]
                != ppm_from_fixed18(str(raw_entry["raw_reliability_fixed18"]))
            ):
                _fail("projection ppm does not equal raw fixed18")
    return projection


def _validate_shared_quality_fields(value: Mapping[str, object]) -> None:
    expected = {
        "measurement_config_digest": MEASUREMENT_CONFIG_DIGEST,
        "measurement_quality_config_digest": QUALITY_CONFIG_DIGEST,
        "measurement_quality_manifest_content_digest": QUALITY_MANIFEST_DIGEST,
        "confidence_kind": CONFIDENCE_KIND,
        "reliability_kind": RELIABILITY_KIND,
        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
        "topology_digest": TOPOLOGY_DIGEST,
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        _fail("quality authority binding differs from accepted manifest")
    for key in (
        "source_p2_candidate_manifest_content_digest",
        "dimension_authority_manifest_content_digest",
        "source_repeat_certification_digest",
    ):
        _digest(value.get(key), key)


def _validate_raw_entries(value: object) -> None:
    if not isinstance(value, list) or len(value) != len(DIMENSIONS):
        _fail("raw authority must have six ordered entries")
    for dimension, entry in zip(DIMENSIONS, value, strict=True):
        actual = _exact(entry, _RAW_ENTRY_KEYS, "raw authority entry")
        if actual["dimension_key"] != dimension:
            _fail("raw authority entry order is invalid")
        if actual["support_state"] == "SUPPORTED":
            for key in ("raw_value_fixed18", "raw_confidence_fixed18", "raw_reliability_fixed18"):
                if _fixed18_units(actual[key], key) > 1_000_000_000_000_000_000:
                    _fail("supported raw fixed18 value exceeds one")
            if actual["raw_reliability_fixed18"] != "1.000000000000000000":
                _fail("supported raw reliability must be derived from exact repeat certification")
            if actual["unsupported_reason"] is not None:
                _fail("supported raw authority union is invalid")
        elif actual["support_state"] == "UNSUPPORTED":
            if any(
                actual[key] is not None
                for key in (
                    "raw_value_fixed18",
                    "raw_confidence_fixed18",
                    "raw_reliability_fixed18",
                )
            ) or actual["unsupported_reason"] not in {
                "RUNTIME_UNSUPPORTED",
                "MISSING_MEASUREMENT",
                "OUT_OF_BOUNDS",
                "LOW_CONFIDENCE",
            }:
                _fail("unsupported raw authority union is invalid")
        else:
            _fail("raw authority support state is invalid")


def digest_raw_measurement_authority(value: Mapping[str, object]) -> str:
    validate_raw_measurement_authority(value)
    return _digest_for(RAW_SCHEMA, value, set())


def digest_morphology_projection(value: Mapping[str, object]) -> str:
    validate_morphology_projection(value)
    return _digest_for(PROJECTION_SCHEMA, value, set())


def digest_facts(value: Mapping[str, object]) -> str:
    validate_facts(value)
    return _digest_for(FACTS_SCHEMA, value, set())


def validate_facts(value: object) -> Mapping[str, Any]:
    facts = _exact(value, _FACTS_KEYS, "recovered identity facts")
    observation = validate_measurement_observation(
        facts["source_measurement_observation"], role="SOURCE"
    )
    certificate = validate_source_certificate(facts["source_repeat_certification"])
    _validate_source_certificate_observation_crosslinks(certificate, observation)
    if (
        facts["source_measurement_observation_digest"]
        != observation["measurement_observation_digest"]
        or facts["source_measurement_digest"] != facts["source_measurement_observation_digest"]
    ):
        _fail("facts source measurement digest must be the observation digest")
    if facts["source_measurement_digest"] == facts["raw_measurement_authority_digest"]:
        _fail("facts source measurement digest must not alias raw authority digest")
    subject = cast(Mapping[str, Any], observation["subject"])
    if (
        facts["source_landmark_digest"] != observation["landmark_digest"]
        or facts["source_output_id"] != subject["source_output_id"]
    ):
        _fail("facts observation subject cross-link is invalid")
    if (
        facts["source_repeat_certification_digest"]
        != certificate["source_repeat_certification_digest"]
    ):
        _fail("facts source certificate cross-link is invalid")
    raw = cast(Mapping[str, Any], facts["raw_measurement_authority"])
    projection = cast(Mapping[str, Any], facts["source_measurement_projection"])
    validate_raw_measurement_authority(raw)
    validate_morphology_projection(projection, raw=raw)
    expected_raw = build_raw_measurement_authority(
        observation,
        certificate,
        source_p2_candidate_manifest_content_digest=cast(
            str, facts["source_p2_candidate_manifest_content_digest"]
        ),
        dimension_authority_manifest_content_digest=cast(
            str, facts["dimension_authority_manifest_content_digest"]
        ),
    )
    if raw != expected_raw or projection != build_morphology_projection(expected_raw):
        _fail("facts raw/projection must be exactly derived from observation and certificate")
    if facts["raw_measurement_authority_digest"] != digest_raw_measurement_authority(raw) or facts[
        "source_measurement_projection_digest"
    ] != digest_morphology_projection(projection):
        _fail("facts raw/projection digest does not replay")
    if any(
        facts[key] != raw[key]
        for key in (
            "source_p2_candidate_manifest_content_digest",
            "dimension_authority_manifest_content_digest",
        )
    ):
        _fail("facts raw authority binding differs")
    if (
        facts["measurement_projection_version"] != projection["measurement_projection_version"]
        or facts["measurement_quantization_version"]
        != projection["measurement_quantization_version"]
    ):
        _fail("facts projection version differs")
    _opaque_output_id(facts["source_output_id"], "facts source output id")
    _digest(facts["source_asset_sha256"], "facts source asset sha256")
    for key in (
        "source_receipt_digest",
        "source_authority_digest",
        "qa_policy_digest",
        "source_qa_snapshot_digest",
        "source_landmark_digest",
        "source_measurement_digest",
        "source_provenance_digest",
        "source_measurement_projection_digest",
        "raw_measurement_authority_digest",
        "source_measurement_observation_digest",
        "source_repeat_certification_digest",
    ):
        _digest(facts[key], key)
    if (
        type(facts["source_asset_byte_size"]) is not int
        or not 1 <= int(facts["source_asset_byte_size"]) <= 9_223_372_036_854_775_807
        or type(facts["source_asset_width"]) is not int
        or not 1 <= int(facts["source_asset_width"]) <= 2_147_483_647
        or type(facts["source_asset_height"]) is not int
        or not 1 <= int(facts["source_asset_height"]) <= 2_147_483_647
        or facts["source_asset_mime_type"] != "image/jpeg"
        or facts["adult_synthetic_attested"] is not True
        or facts["original_formal_identity_id_status"] != UNKNOWN_FORMAL_IDENTITY_STATUS
    ):
        _fail("facts asset or attestation fields are invalid")
    return facts


def derive_source_m3_record_id(
    *,
    source_manifest_digest: str,
    source_authority_key: str,
    source_admission_event_id: str,
    source_asset_id: str,
    source_asset_sha256: str,
    repeat_index: int,
) -> str:
    _digest(source_manifest_digest, "source manifest digest")
    _digest(source_authority_key, "source authority key")
    _id(source_admission_event_id, "source admission event id")
    _id(source_asset_id, "source asset id")
    _digest(source_asset_sha256, "source asset sha256")
    if type(repeat_index) is not int or repeat_index not in {1, 2, 3}:
        _fail("source repeat index must be one through three")
    preimage: dict[str, JsonValue] = {
        "source_manifest_digest": source_manifest_digest,
        "source_authority_key": source_authority_key,
        "source_admission_event_id": source_admission_event_id,
        "source_asset_id": source_asset_id,
        "source_asset_sha256": source_asset_sha256,
        "repeat_index": repeat_index,
        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
        "topology_digest": TOPOLOGY_DIGEST,
    }
    return mirror_demo_digest("mirror.demo/D02SourceM3RecordId/v1", preimage)[:32]


def _validate_source_m3_scalar_domains(record: Mapping[str, object]) -> None:
    for key in ("source_m3_record_id", "source_admission_event_id", "source_asset_id"):
        _id(record[key], key)
    for key in (
        "source_authority_key",
        "source_asset_sha256",
        "execution_receipt_digest",
        "vision_model_manifest_digest",
        "runtime_manifest_digest",
        "topology_digest",
        "canonical_output_digest",
        "landmark_digest",
        "measurement_observation_digest",
        "record_digest",
    ):
        _digest(record[key], key)
    if type(record["source_ordinal"]) is not int or not 1 <= int(record["source_ordinal"]) <= 4:
        _fail("source M3 ordinal must be an integer from one through four")
    if type(record["repeat_index"]) is not int or record["repeat_index"] not in {1, 2, 3}:
        _fail("source M3 repeat index must be an integer from one through three")
    for key in ("face_count", "landmark_count"):
        count = record[key]
        if type(count) is not int or not 0 <= count <= 2_147_483_647:
            _fail(f"source M3 {key} must be a nonnegative PostgreSQL integer")
    for key in ("coordinates_finite", "coordinates_in_bounds", "repeat_gate_passed"):
        _bool(record[key], f"source M3 {key}")


def validate_source_m3_record(
    value: object,
    *,
    certificate: Mapping[str, object],
    facts_observation: Mapping[str, object],
    source_manifest_digest: str,
) -> Mapping[str, Any]:
    record = _exact(value, _SOURCE_M3_KEYS, "source M3 repeat record")
    if record["schema_version"] != SOURCE_M3_SCHEMA:
        _fail("source M3 schema is invalid")
    _validate_source_m3_scalar_domains(record)
    verified_certificate = validate_source_certificate(certificate)
    observation = validate_measurement_observation(facts_observation, role="SOURCE")
    _validate_source_certificate_observation_crosslinks(verified_certificate, observation)
    expected_runtime_authority = {
        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
        "topology_digest": TOPOLOGY_DIGEST,
    }
    if any(
        record[key] != expected_digest or observation[key] != expected_digest
        for key, expected_digest in expected_runtime_authority.items()
    ):
        _fail("source M3 runtime authority does not match observation")
    if (
        record["canonical_output_digest"] != observation["canonical_output_digest"]
        or record["landmark_digest"] != observation["landmark_digest"]
    ):
        _fail("source M3 output lineage does not match observation")
    _digest(source_manifest_digest, "source manifest digest")
    expected_id = derive_source_m3_record_id(
        source_manifest_digest=source_manifest_digest,
        source_authority_key=str(record["source_authority_key"]),
        source_admission_event_id=str(record["source_admission_event_id"]),
        source_asset_id=str(record["source_asset_id"]),
        source_asset_sha256=str(record["source_asset_sha256"]),
        repeat_index=int(record["repeat_index"]),
    )
    if record["source_m3_record_id"] != expected_id:
        _fail("source M3 record ID is not derived after the source manifest")
    if (
        record["measurement_observation"] != observation
        or record["measurement_observation_digest"] != observation["measurement_observation_digest"]
    ):
        _fail("source M3 embedded observation cross-link is invalid")
    bindings = verified_certificate["ordered_repeat_bindings"]
    index = record["repeat_index"]
    if type(index) is not int or index not in {1, 2, 3} or not isinstance(bindings, list):
        _fail("source M3 repeat index is invalid")
    binding = bindings[index - 1]
    if not isinstance(binding, Mapping):
        _fail("source certificate binding is invalid")
    shared = (
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
    if any(record[key] != binding[key] for key in shared):
        _fail("source M3 certificate semantic tuple cross-link is invalid")
    if (
        record["source_asset_id"] != observation["subject"]["source_asset_id"]
        or record["source_asset_sha256"] != observation["subject"]["source_asset_sha256"]
    ):
        _fail("source M3 observation subject cross-link is invalid")
    _require_digest_match(SOURCE_M3_SCHEMA, record, "record_digest", {"schema_version"})
    return record


def validate_result_m3_record(value: object) -> Mapping[str, Any]:
    record = _exact(value, _RESULT_M3_KEYS, "result M3 repeat record")
    if record["schema_version"] != RESULT_M3_SCHEMA:
        _fail("result M3 schema is invalid")
    observation = validate_measurement_observation(record["measurement_observation"], role="RESULT")
    subject = observation["subject"]
    if not isinstance(subject, Mapping) or any(
        record[key] != subject[key]
        for key in ("case_id", "case_specification_digest", "result_output_id", "result_sha256")
    ):
        _fail("result M3 observation subject cross-link is invalid")
    if (
        record["measurement_observation_digest"] != observation["measurement_observation_digest"]
        or record["canonical_output_digest"] != observation["canonical_output_digest"]
        or record["landmark_digest"] != observation["landmark_digest"]
    ):
        _fail("result M3 observation digest cross-link is invalid")
    observation_entries = cast(list[Mapping[str, Any]], observation["ordered_measurements"])
    expected_observation_state = (
        "SUPPORTED"
        if all(entry["support_state"] == "SUPPORTED" for entry in observation_entries)
        else "UNSUPPORTED_EXPLICIT"
    )
    if (
        record["runtime_manifest_digest"] != RUNTIME_MANIFEST_DIGEST
        or record["vision_model_manifest_digest"] != VISION_MODEL_MANIFEST_DIGEST
        or record["topology_digest"] != TOPOLOGY_DIGEST
    ):
        _fail("result M3 runtime binding is invalid")
    if (
        type(record["repeat_index"]) is not int
        or record["repeat_index"] not in {1, 2, 3}
        or type(record["face_count"]) is not int
        or record["face_count"] != 1
        or type(record["landmark_count"]) is not int
        or record["landmark_count"] != 478
        or record["coordinates_finite"] is not True
        or record["coordinates_in_bounds"] is not True
        or record["observation_state"] not in {"SUPPORTED", "UNSUPPORTED_EXPLICIT"}
        or record["observation_state"] != expected_observation_state
        or type(record["repeat_gate_passed"]) is not bool
    ):
        _fail("result M3 structural state is invalid")
    if record["observation_state"] == "SUPPORTED" and record["repeat_gate_passed"] is not True:
        _fail("supported result M3 must pass repeat gate")
    if (
        record["observation_state"] == "UNSUPPORTED_EXPLICIT"
        and record["repeat_gate_passed"] is not False
    ):
        _fail("unsupported result M3 must fail repeat gate")
    if record["result_m3_record_id"] != derive_result_m3_record_id(
        case_id=record["case_id"],
        case_specification_digest=record["case_specification_digest"],
        result_output_id=record["result_output_id"],
        result_sha256=record["result_sha256"],
        repeat_index=record["repeat_index"],
        bindings=default_authority_bindings(),
    ):
        _fail("result M3 record ID preimage does not replay")
    _require_digest_match(RESULT_M3_SCHEMA, record, "record_digest", {"schema_version"})
    return record


def validate_measurement_gate(
    value: object,
    *,
    result_records: Sequence[Mapping[str, object]],
    source_measurement_authority: Mapping[str, object],
) -> Mapping[str, Any]:
    gate = _exact(value, _GATE_KEYS, "measurement gate")
    if gate["schema_version"] != GATE_SCHEMA:
        _fail("measurement gate schema is invalid")
    certificate = validate_result_certificate(gate["result_repeat_certification"], result_records)
    if (
        gate["result_repeat_certification_digest"]
        != certificate["result_repeat_certification_digest"]
    ):
        _fail("measurement gate result certificate digest cross-link is invalid")
    if len(result_records) != 3:
        _fail("measurement gate requires exactly three ResultM3 records")
    verified_records = [validate_result_m3_record(record) for record in result_records]
    if [record["repeat_index"] for record in verified_records] != [1, 2, 3]:
        _fail("measurement gate ResultM3 records must be repeat ordered")
    case_id = _id(gate["case_id"], "gate case id")
    case_specification_digest = _digest(
        gate["case_specification_digest"], "gate case specification"
    )
    dimension = gate["dimension_key"]
    if dimension not in DIMENSIONS or gate["requested_direction"] not in {"INCREASE", "DECREASE"}:
        _fail("measurement gate dimension or requested direction is invalid")
    if type(gate["requested_magnitude_ppm"]) is not int or gate["requested_magnitude_ppm"] not in {
        15_000,
        30_000,
    }:
        _fail("measurement gate requested magnitude is invalid")
    _id(gate["monotonicity_peer_case_id"], "monotonicity peer case id")
    source = validate_source_manifest_entry(source_measurement_authority)
    source_measurements = cast(list[Mapping[str, Any]], source["ordered_supported_measurements"])
    source_by_dimension = {str(item["dimension_key"]): item for item in source_measurements}
    target = _validate_supported_measurement(gate["source_target_measurement"], dimension=dimension)
    if target != source_by_dimension[cast(str, dimension)]:
        _fail("measurement gate target does not project source authority")
    controls = gate["ordered_source_control_measurements"]
    expected_controls = tuple(item for item in DIMENSIONS if item != dimension)
    if not isinstance(controls, list) or len(controls) != len(expected_controls):
        _fail("measurement gate requires five ordered source controls")
    parsed_controls = [
        _validate_supported_measurement(item, dimension=control_dimension)
        for control_dimension, item in zip(expected_controls, controls, strict=True)
    ]
    expected_source_controls = [
        source_by_dimension[control_dimension] for control_dimension in expected_controls
    ]
    if parsed_controls != expected_source_controls:
        _fail("measurement gate controls do not project source authority")
    measurements = gate["ordered_result_repeat_measurements"]
    if not isinstance(measurements, list) or len(measurements) != 3:
        _fail("measurement gate must preserve three result measurements")
    parsed_measurements = [
        _validate_result_measurement(
            measurement,
            record=record,
            target=target,
            controls=parsed_controls,
            dimension=cast(str, dimension),
            direction=cast(str, gate["requested_direction"]),
        )
        for measurement, record in zip(measurements, verified_records, strict=True)
    ]
    _validate_gate_evaluation(
        gate["measurement_evaluation_state"], gate["gate_evaluation"], parsed_measurements
    )
    if any(
        record["case_id"] != case_id
        or record["case_specification_digest"] != case_specification_digest
        for record in verified_records
    ):
        _fail("measurement gate case binding differs from ResultM3 records")
    _require_digest_match(GATE_SCHEMA, gate, "record_digest", {"schema_version"})
    return gate


def _observation_measurement(record: Mapping[str, Any], dimension: str) -> Mapping[str, Any]:
    observation = cast(Mapping[str, Any], record["measurement_observation"])
    entries = cast(list[Mapping[str, Any]], observation["ordered_measurements"])
    index = DIMENSIONS.index(dimension)
    entry = entries[index]
    if entry["dimension_key"] != dimension:
        _fail("ResultM3 observation dimension order is invalid")
    return entry


def _validate_result_measurement(
    value: object,
    *,
    record: Mapping[str, Any],
    target: Mapping[str, Any],
    controls: Sequence[Mapping[str, Any]],
    dimension: str,
    direction: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("result measurement must be an object")
    record_digest = record["record_digest"]
    target_observation = _observation_measurement(record, dimension)
    common = {
        "repeat_index": record["repeat_index"],
        "result_m3_record_digest": record_digest,
    }
    if target_observation["support_state"] == "UNSUPPORTED":
        item = _exact(
            value,
            {
                "schema_version",
                "repeat_index",
                "result_m3_record_digest",
                "unsupported_dimension_key",
                "unsupported_reason",
                "measurement_gate_passed",
            },
            "unsupported result measurement",
        )
        if (
            item["schema_version"] != "mirror.demo/D02UnsupportedResultMeasurement/v1"
            or any(item[key] != expected for key, expected in common.items())
            or item["unsupported_dimension_key"] != dimension
            or item["unsupported_reason"] != target_observation["unsupported_reason"]
            or item["measurement_gate_passed"] is not False
            or record["observation_state"] != "UNSUPPORTED_EXPLICIT"
        ):
            _fail("unsupported result measurement does not replay ResultM3 observation")
        return item
    if record["observation_state"] != "SUPPORTED":
        _fail("supported result measurement requires supported ResultM3 record")
    item = _exact(
        value,
        {
            "schema_version",
            "repeat_index",
            "result_m3_record_digest",
            "raw_result_target_fixed18",
            "raw_signed_target_delta_fixed18",
            "raw_target_absolute_delta_fixed18",
            "ordered_control_deltas",
            "winning_control_ordinal",
            "max_control_dimension_key",
            "raw_max_control_drift_fixed18",
            "measured_signed_delta_ppm",
            "target_absolute_delta_ppm",
            "drift_ppm",
            "direction_gate_passed",
            "target_min_gate_passed",
            "target_max_gate_passed",
            "control_drift_gate_passed",
        },
        "supported result measurement",
    )
    if item["schema_version"] != "mirror.demo/D02SupportedResultMeasurement/v1" or any(
        item[key] != expected for key, expected in common.items()
    ):
        _fail("supported result measurement record binding is invalid")
    source_units = _fixed18_units(target["raw_value_fixed18"], "source target value")
    result_units = _fixed18_units(target_observation["raw_value_fixed18"], "result target value")
    signed_units = result_units - source_units
    absolute_units = abs(signed_units)
    if (
        _fixed18_units(item["raw_result_target_fixed18"], "raw result target") != result_units
        or _fixed18_units(item["raw_signed_target_delta_fixed18"], "raw signed target", signed=True)
        != signed_units
        or _fixed18_units(item["raw_target_absolute_delta_fixed18"], "raw absolute target")
        != absolute_units
        or _ppm(item["measured_signed_delta_ppm"], "signed delta", signed=True)
        != _ppm_from_units(signed_units)
        or _ppm(item["target_absolute_delta_ppm"], "absolute target")
        != _ppm_from_units(absolute_units)
    ):
        _fail("supported result target delta does not replay embedded observation")
    delta_items = item["ordered_control_deltas"]
    if not isinstance(delta_items, list) or len(delta_items) != len(controls):
        _fail("supported result measurement requires five ordered control deltas")
    parsed_deltas: list[Mapping[str, Any]] = []
    observation = cast(Mapping[str, Any], record["measurement_observation"])
    observation_entries = cast(list[Mapping[str, Any]], observation["ordered_measurements"])
    for ordinal, (delta, control) in enumerate(zip(delta_items, controls, strict=True), start=1):
        parsed = _exact(
            delta,
            {
                "schema_version",
                "control_ordinal",
                "dimension_key",
                "raw_source_value_fixed18",
                "raw_result_value_fixed18",
                "raw_absolute_delta_fixed18",
                "drift_ppm",
            },
            "control delta",
        )
        dimension_key = control["dimension_key"]
        result_entry = observation_entries[DIMENSIONS.index(cast(str, dimension_key))]
        if (
            parsed["schema_version"] != "mirror.demo/D02ControlDelta/v1"
            or parsed["control_ordinal"] != ordinal
            or parsed["dimension_key"] != dimension_key
            or result_entry["support_state"] != "SUPPORTED"
        ):
            _fail("control delta schema, order, or result support is invalid")
        source_control_units = _fixed18_units(control["raw_value_fixed18"], "source control value")
        result_control_units = _fixed18_units(
            result_entry["raw_value_fixed18"], "result control value"
        )
        drift_units = abs(result_control_units - source_control_units)
        if (
            _fixed18_units(parsed["raw_source_value_fixed18"], "raw source control")
            != source_control_units
            or _fixed18_units(parsed["raw_result_value_fixed18"], "raw result control")
            != result_control_units
            or _fixed18_units(parsed["raw_absolute_delta_fixed18"], "raw control drift")
            != drift_units
            or _ppm(parsed["drift_ppm"], "control drift ppm") != _ppm_from_units(drift_units)
        ):
            _fail("control delta does not replay embedded observation")
        parsed_deltas.append(parsed)
    maximum = max(
        _fixed18_units(delta["raw_absolute_delta_fixed18"], "control maximum")
        for delta in parsed_deltas
    )
    winner = next(
        index
        for index, delta in enumerate(parsed_deltas, start=1)
        if _fixed18_units(delta["raw_absolute_delta_fixed18"], "control maximum") == maximum
    )
    winning_delta = parsed_deltas[winner - 1]
    if (
        item["winning_control_ordinal"] != winner
        or item["max_control_dimension_key"] != winning_delta["dimension_key"]
        or _fixed18_units(item["raw_max_control_drift_fixed18"], "maximum control drift") != maximum
        or _ppm(item["drift_ppm"], "maximum drift ppm") != winning_delta["drift_ppm"]
    ):
        _fail("control maximum tie-break does not replay")
    direction_ok = signed_units > 0 if direction == "INCREASE" else signed_units < 0
    minimum_ok = absolute_units >= 10_000_000_000_000
    maximum_ok = absolute_units <= 60_000_000_000_000_000
    drift_ok = maximum <= 20_000_000_000_000_000
    if (
        _bool(item["direction_gate_passed"], "direction gate") != direction_ok
        or _bool(item["target_min_gate_passed"], "target minimum gate") != minimum_ok
        or _bool(item["target_max_gate_passed"], "target maximum gate") != maximum_ok
        or _bool(item["control_drift_gate_passed"], "control drift gate") != drift_ok
    ):
        _fail("supported result measurement gate booleans do not replay")
    return item


def _validate_gate_evaluation(
    state: object, value: object, measurements: Sequence[Mapping[str, Any]]
) -> None:
    supported = all(
        measurement["schema_version"] == "mirror.demo/D02SupportedResultMeasurement/v1"
        for measurement in measurements
    )
    if supported:
        evaluation = _exact(
            value,
            {
                "schema_version",
                "direction_gate_passed",
                "target_min_gate_passed",
                "target_max_gate_passed",
                "control_drift_gate_passed",
                "magnitude_monotonicity_gate_passed",
                "measurement_gate_passed",
            },
            "supported gate evaluation",
        )
        if (
            state != "SUPPORTED_EVALUATED"
            or evaluation["schema_version"]
            != "mirror.demo/D02SupportedMeasurementGateEvaluation/v1"
        ):
            _fail("supported gate evaluation state is invalid")
        for key in (
            "direction_gate_passed",
            "target_min_gate_passed",
            "target_max_gate_passed",
            "control_drift_gate_passed",
        ):
            expected = all(_bool(measurement[key], key) for measurement in measurements)
            if _bool(evaluation[key], key) != expected:
                _fail("supported gate evaluation does not combine repeat gates")
        monotonicity = _bool(
            evaluation["magnitude_monotonicity_gate_passed"], "magnitude monotonicity gate"
        )
        expected_gate = (
            all(
                _bool(evaluation[key], key)
                for key in (
                    "direction_gate_passed",
                    "target_min_gate_passed",
                    "target_max_gate_passed",
                    "control_drift_gate_passed",
                )
            )
            and monotonicity
        )
        if _bool(evaluation["measurement_gate_passed"], "measurement gate") != expected_gate:
            _fail("supported measurement gate conjunction does not replay")
    else:
        evaluation = _exact(
            value,
            {
                "schema_version",
                "unsupported_repeat_indexes",
                "ordered_unsupported_reasons",
                "measurement_gate_passed",
            },
            "unsupported gate evaluation",
        )
        if (
            state != "UNSUPPORTED_EXPLICIT"
            or evaluation["schema_version"]
            != "mirror.demo/D02UnsupportedMeasurementGateEvaluation/v1"
            or evaluation["measurement_gate_passed"] is not False
        ):
            _fail("unsupported gate evaluation state is invalid")
        indexes = evaluation["unsupported_repeat_indexes"]
        reasons = evaluation["ordered_unsupported_reasons"]
        expected_indexes = [
            measurement["repeat_index"]
            for measurement in measurements
            if measurement["schema_version"] == "mirror.demo/D02UnsupportedResultMeasurement/v1"
        ]
        expected_reasons = [
            measurement["unsupported_reason"]
            for measurement in measurements
            if measurement["schema_version"] == "mirror.demo/D02UnsupportedResultMeasurement/v1"
        ]
        if indexes != expected_indexes or reasons != expected_reasons or not expected_indexes:
            _fail("unsupported gate evaluation does not replay repeat evidence")


def _validate_source_manifest_scalar_domains(entry: Mapping[str, object]) -> None:
    _id(entry["source_admission_event_id"], "source admission event id")
    _id(entry["source_asset_id"], "source Asset id")
    _opaque_output_id(entry["source_output_id"], "source output id")
    for key in (
        "source_authority_key",
        "source_admission_content_digest",
        "source_asset_sha256",
        "source_receipt_digest",
        "source_authority_digest",
        "source_qa_snapshot_digest",
        "source_landmark_digest",
        "source_measurement_digest",
        "source_provenance_digest",
        "source_fact_snapshot_digest",
        "raw_measurement_authority_digest",
        "source_measurement_projection_digest",
        "source_p2_candidate_manifest_content_digest",
        "dimension_authority_manifest_content_digest",
        "measurement_config_digest",
        "measurement_quality_config_digest",
        "measurement_quality_manifest_content_digest",
        "runtime_manifest_digest",
        "vision_model_manifest_digest",
        "topology_digest",
        "source_repeat_certification_digest",
        "import_config_digest",
        "record_digest",
    ):
        _digest(entry[key], key)
    if type(entry["source_ordinal"]) is not int or not 1 <= int(entry["source_ordinal"]) <= 4:
        _fail("source manifest ordinal must be an integer from one through four")
    if (
        type(entry["source_asset_byte_size"]) is not int
        or not 1 <= int(entry["source_asset_byte_size"]) <= 9_223_372_036_854_775_807
    ):
        _fail("source Asset byte size must be a positive PostgreSQL bigint")
    for key in ("source_asset_width", "source_asset_height"):
        dimension = entry[key]
        if type(dimension) is not int or not 1 <= dimension <= 2_147_483_647:
            _fail(f"{key} must be a positive PostgreSQL integer")
    _bool(entry["adult_synthetic_attested"], "adult synthetic attestation")


def validate_source_manifest_entry(value: object) -> Mapping[str, Any]:
    entry = _exact(value, _SOURCE_ENTRY_KEYS, "source authority manifest entry")
    if entry["schema_version"] != SOURCE_ENTRY_SCHEMA:
        _fail("source manifest entry schema is invalid")
    _validate_source_manifest_scalar_domains(entry)
    if "source_measurement_observation_digest" in entry:
        _fail("source manifest entry must not add an observation digest alias")
    _validate_shared_quality_fields(entry)
    expected_source_key = derive_local_source_authority_key(
        source_output_id=entry["source_output_id"],
        source_asset_id=entry["source_asset_id"],
        source_asset_sha256=entry["source_asset_sha256"],
        source_receipt_digest=entry["source_receipt_digest"],
    )
    if (
        entry["source_authority_kind"] != LOCAL_SOURCE_AUTHORITY_KIND
        or entry["source_authority_key"] != expected_source_key
        or entry["source_asset_mime_type"] != "image/jpeg"
        or entry["adult_synthetic_attested"] is not True
        or entry["original_formal_identity_id_status"] != UNKNOWN_FORMAL_IDENTITY_STATUS
        or entry["import_config_digest"] != IMPORT_CONFIG_DIGEST
    ):
        _fail("source manifest local authority shape or generated key is invalid")
    expected_asset_id = derive_imported_asset_id(
        asset_role="synthetic",
        semantic_role="SOURCE",
        sha256=entry["source_asset_sha256"],
        byte_size=entry["source_asset_byte_size"],
        mime_type=entry["source_asset_mime_type"],
        width=entry["source_asset_width"],
        height=entry["source_asset_height"],
    )
    if entry["source_asset_id"] != expected_asset_id:
        _fail("source imported Asset ID preimage does not replay")
    supported = entry["ordered_supported_measurements"]
    if not isinstance(supported, list) or len(supported) != len(DIMENSIONS):
        _fail("source manifest entry requires six ordered supported measurements")
    for dimension, item in zip(DIMENSIONS, supported, strict=True):
        _validate_supported_measurement(item, dimension=dimension)
    _require_digest_match(SOURCE_ENTRY_SCHEMA, entry, "record_digest", {"schema_version"})
    return entry


def _validate_supported_measurement(
    value: object, *, dimension: str | None = None
) -> Mapping[str, Any]:
    item = _exact(
        value,
        {
            "schema_version",
            "dimension_key",
            "raw_value_fixed18",
            "raw_confidence_fixed18",
            "raw_reliability_fixed18",
            "value_ppm",
            "confidence_ppm",
            "reliability_ppm",
            "unit",
        },
        "supported measurement",
    )
    if (
        item["schema_version"] != "mirror.demo/D02SupportedSourceMeasurement/v1"
        or item["dimension_key"] not in DIMENSIONS
        or (dimension is not None and item["dimension_key"] != dimension)
        or item["unit"] != "FACE_HEIGHT_PPM"
    ):
        _fail("supported measurement schema or dimension is invalid")
    for raw_key, ppm_key in (
        ("raw_value_fixed18", "value_ppm"),
        ("raw_confidence_fixed18", "confidence_ppm"),
        ("raw_reliability_fixed18", "reliability_ppm"),
    ):
        raw = _fixed18_units(item[raw_key], raw_key)
        ppm = _ppm(item[ppm_key], ppm_key)
        if raw > 1_000_000_000_000_000_000 or ppm < 1 or ppm != _ppm_from_units(raw):
            _fail("supported measurement raw/ppm projection is invalid")
    return item


def build_source_manifest_entry(fields: Mapping[str, object]) -> dict[str, JsonValue]:
    """Sign one post-admission v3 source-manifest entry without an alias digest."""
    required = _SOURCE_ENTRY_KEYS - {"schema_version", "record_digest"}
    _exact(fields, required, "source manifest entry input")
    entry: dict[str, JsonValue] = {
        "schema_version": SOURCE_ENTRY_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    entry["record_digest"] = _digest_for(SOURCE_ENTRY_SCHEMA, entry, {"schema_version"})
    validate_source_manifest_entry(entry)
    return entry


def build_source_m3_record(
    fields: Mapping[str, object],
    *,
    source_manifest_entries: Sequence[Mapping[str, object]],
    source_entry: Mapping[str, object],
    certificate: Mapping[str, object],
    facts_observation: Mapping[str, object],
    source_manifest_digest: str,
) -> dict[str, JsonValue]:
    """Validate and sign a SourceM3 v2 record in its complete authority context."""
    required = _SOURCE_M3_KEYS - {"schema_version", "record_digest"}
    _exact(fields, required, "source M3 record input")
    _digest(source_manifest_digest, "source manifest digest")
    verified_manifest_digest = digest_source_manifest(source_manifest_entries)
    if source_manifest_digest != verified_manifest_digest:
        _fail("source M3 aggregate source-manifest digest is invalid")
    entry = validate_source_manifest_entry(source_entry)
    ordinal = cast(int, entry["source_ordinal"])
    manifest_entry = validate_source_manifest_entry(source_manifest_entries[ordinal - 1])
    if entry != manifest_entry:
        _fail("source M3 source entry is not the exact aggregate-manifest member")
    record: dict[str, JsonValue] = {
        "schema_version": SOURCE_M3_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    record["record_digest"] = _digest_for(SOURCE_M3_SCHEMA, record, {"schema_version"})
    validate_source_m3_record(
        record,
        certificate=certificate,
        facts_observation=facts_observation,
        source_manifest_digest=source_manifest_digest,
    )
    if any(
        record[key] != entry[key]
        for key in (
            "source_ordinal",
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "source_asset_sha256",
        )
    ):
        _fail("source M3/source manifest authority equality is invalid")
    return record


def build_result_m3_record(fields: Mapping[str, object]) -> dict[str, JsonValue]:
    """Sign an acyclic ResultM3 v2 record; certificate construction remains downstream."""
    required = _RESULT_M3_KEYS - {"schema_version", "record_digest"}
    _exact(fields, required, "result M3 record input")
    record: dict[str, JsonValue] = {
        "schema_version": RESULT_M3_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    record["record_digest"] = _digest_for(RESULT_M3_SCHEMA, record, {"schema_version"})
    return record


def build_measurement_gate(fields: Mapping[str, object]) -> dict[str, JsonValue]:
    """Sign a Gate v4 record only after the result certificate is supplied."""
    required = _GATE_KEYS - {"schema_version", "record_digest"}
    _exact(fields, required, "measurement gate input")
    gate: dict[str, JsonValue] = {
        "schema_version": GATE_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    gate["record_digest"] = _digest_for(GATE_SCHEMA, gate, {"schema_version"})
    return gate


def build_facts(fields: Mapping[str, object]) -> dict[str, JsonValue]:
    """Validate and freeze a facts v3 snapshot; its digest is derived externally."""
    _exact(fields, _FACTS_KEYS, "recovered identity facts input")
    facts = cast(dict[str, JsonValue], dict(fields))
    validate_facts(facts)
    return facts


def build_identity_row(
    fields: Mapping[str, object], *, facts: Mapping[str, object]
) -> dict[str, JsonValue]:
    """Build the canonical v3 identity row and its admission-event ID deterministically."""
    required = _IDENTITY_ROW_KEYS - {"id", "schema_version", "canonical_payload", "content_digest"}
    _exact(fields, required, "synthetic identity row input")
    row: dict[str, JsonValue] = {
        "schema_version": IDENTITY_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    canonical = {
        key: item
        for key, item in row.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    row["canonical_payload"] = canonical
    row["content_digest"] = mirror_demo_digest(IDENTITY_SCHEMA, canonical)
    row["id"] = mirror_demo_digest(
        "mirror.demo/DemoSyntheticIdentityAdmissionEventId/v2",
        {
            "source_authority_kind": row["source_authority_kind"],
            "source_authority_key": row["source_authority_key"],
            "admission_sequence": row["admission_sequence"],
            "admission_action": row["admission_action"],
            "supersedes_id": row["supersedes_id"],
            "admission_config_digest": row["admission_config_digest"],
            "canonical_payload_digest": row["content_digest"],
        },
    )[:32]
    validate_identity_row(row, facts=facts)
    return row


def build_schema_and_policy_binding(fields: Mapping[str, object]) -> dict[str, JsonValue]:
    """Validate the non-self-digesting v2 report binding projection."""
    _exact(fields, _BINDING_KEYS - {"schema_version"}, "schema and policy binding input")
    binding: dict[str, JsonValue] = {
        "schema_version": SCHEMA_POLICY_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    validate_schema_and_policy_binding(binding)
    return binding


def digest_source_manifest(entries: Sequence[Mapping[str, object]]) -> str:
    if len(entries) != 4:
        _fail("source manifest must contain exactly four ordered entries")
    seen_source_keys: set[object] = set()
    seen_admission_ids: set[object] = set()
    seen_asset_ids: set[object] = set()
    seen_output_ids: set[object] = set()
    previous_order: tuple[str, str] | None = None
    for ordinal, entry in enumerate(entries, start=1):
        parsed = validate_source_manifest_entry(entry)
        order = (
            cast(str, parsed["source_authority_key"]),
            cast(str, parsed["source_admission_event_id"]),
        )
        if parsed["source_ordinal"] != ordinal:
            _fail("source manifest ordinal is invalid")
        if previous_order is not None and order <= previous_order:
            _fail("source manifest authority order is not strictly ascending")
        previous_order = order
        for value, seen, label in (
            (parsed["source_authority_key"], seen_source_keys, "source authority key"),
            (parsed["source_admission_event_id"], seen_admission_ids, "admission event ID"),
            (parsed["source_asset_id"], seen_asset_ids, "source Asset ID"),
            (parsed["source_output_id"], seen_output_ids, "source output ID"),
        ):
            if value in seen:
                _fail(f"source manifest duplicate {label}")
            seen.add(value)
    return _sequence_digest(SOURCE_MANIFEST_SCHEMA, entries)


def _execution_authority(value: Mapping[str, object]) -> Mapping[str, Any]:
    authority = _exact(value, _EXECUTION_AUTHORITY_KEYS, "execution authority")
    for key in _EXECUTION_AUTHORITY_KEYS:
        _digest(authority[key], key)
    if authority["screening_policy_digest"] != SCREENING_POLICY_DIGEST:
        _fail("screening policy root is not the accepted Revision 9 authority")
    return authority


def _case_controls(dimension: str) -> tuple[str, str, str, str, str]:
    if dimension not in CASE_DIMENSIONS:
        _fail("case dimension is not a frozen candidate")
    return tuple(item for item in DIMENSIONS if item != dimension)  # type: ignore[return-value]


def _case_execution_digest(
    entry: Mapping[str, object], execution_authority: Mapping[str, object]
) -> str:
    authority = _execution_authority(execution_authority)
    payload: dict[str, JsonValue] = {
        **cast(dict[str, JsonValue], authority),
        "geometry_algorithm_version": cast(str, entry["geometry_algorithm_version"]),
        "runtime_config_digest": cast(str, entry["runtime_config_digest"]),
        "output_policy_version": cast(str, entry["output_policy_version"]),
        "output_width": cast(int, entry["output_width"]),
        "output_height": cast(int, entry["output_height"]),
        "determinism_level": cast(str, entry["determinism_level"]),
    }
    return mirror_demo_digest(EXECUTION_CONFIGURATION_SCHEMA, payload)


def _case_id(entry: Mapping[str, object]) -> str:
    payload: dict[str, JsonValue] = {
        "source_manifest_digest": cast(str, entry["source_manifest_digest"]),
        "source_authority_key": cast(str, entry["source_authority_key"]),
        "source_admission_event_id": cast(str, entry["source_admission_event_id"]),
        "source_asset_sha256": cast(str, entry["source_asset_sha256"]),
        "source_p2_candidate_manifest_content_digest": cast(
            str, entry["source_p2_candidate_manifest_content_digest"]
        ),
        "dimension_authority_manifest_content_digest": cast(
            str, entry["dimension_authority_manifest_content_digest"]
        ),
        "dimension_key": cast(str, entry["dimension_key"]),
        "direction": cast(str, entry["direction"]),
        "magnitude_ppm": cast(int, entry["magnitude_ppm"]),
        "execution_config_digest": cast(str, entry["execution_config_digest"]),
    }
    return mirror_demo_digest("mirror.demo/D02GeometryCaseId/v1", payload)[:32]


def _case_specification_digest(entry: Mapping[str, object]) -> str:
    keys = _CASE_ENTRY_KEYS - {
        "schema_version",
        "case_ordinal",
        "case_id",
        "record_digest",
        "case_specification_digest",
    }
    return mirror_demo_digest(
        "mirror.demo/D02GeometryCaseSpecification/v1",
        _payload({key: entry[key] for key in keys}, set()),
    )


def _case_manifest_digest(entries: Sequence[Mapping[str, object]]) -> str:
    """The preregistration deliberately hashes the manifest array, not a wrapper."""
    try:
        canonical = json.dumps(
            list(entries),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise D02AuthorityError("case manifest is not canonical JSON") from error
    return hashlib.sha256(CASE_MANIFEST_SCHEMA.encode("utf-8") + b"\n" + canonical).hexdigest()


def validate_case_manifest_entry(
    value: object, *, execution_authority: Mapping[str, object]
) -> Mapping[str, Any]:
    """Replay one v3 geometry-case envelope without touching runtime state."""
    entry = _exact(value, _CASE_ENTRY_KEYS, "geometry case manifest entry")
    if entry["schema_version"] != CASE_ENTRY_SCHEMA:
        _fail("geometry case manifest entry schema is invalid")
    for key in (
        "source_manifest_digest",
        "source_asset_sha256",
        "source_qa_snapshot_digest",
        "source_measurement_projection_digest",
        "source_p2_candidate_manifest_content_digest",
        "dimension_authority_manifest_content_digest",
        "geometry_ontology_version_digest",
        "warp_plan_digest",
        "runtime_manifest_digest",
        "runtime_config_digest",
        "execution_config_digest",
        "case_specification_digest",
    ):
        _digest(entry[key], key)
    _id(entry["case_id"], "case id")
    _id(entry["source_admission_event_id"], "source admission event id")
    _id(entry["source_asset_id"], "source asset id")
    _digest(entry["source_authority_key"], "source authority key")
    if type(entry["case_ordinal"]) is not int or not 1 <= entry["case_ordinal"] <= 48:
        _fail("case ordinal is invalid")
    if entry["dimension_key"] not in CASE_DIMENSIONS:
        _fail("case dimension is invalid")
    if entry["direction"] not in CASE_DIRECTIONS:
        _fail("case direction is invalid")
    if entry["magnitude_ppm"] not in CASE_MAGNITUDES or type(entry["magnitude_ppm"]) is not int:
        _fail("case magnitude is invalid")
    if entry["priority_index"] != CASE_DIMENSIONS.index(entry["dimension_key"]) + 1:
        _fail("case priority index is invalid")
    if entry["direction_index"] != CASE_DIRECTIONS.index(entry["direction"]) + 1:
        _fail("case direction index is invalid")
    if entry["magnitude_index"] != CASE_MAGNITUDES.index(entry["magnitude_ppm"]) + 1:
        _fail("case magnitude index is invalid")
    if entry["ordered_control_dimensions"] != list(_case_controls(entry["dimension_key"])):
        _fail("case control dimensions are invalid")
    for key in ("geometry_algorithm_version", "output_policy_version", "determinism_level"):
        if not isinstance(entry[key], str) or _VERSION.fullmatch(entry[key]) is None:
            _fail(f"{key} is invalid")
    for key in ("output_width", "output_height"):
        if type(entry[key]) is not int or not 1 <= entry[key] <= 2_147_483_647:
            _fail(f"{key} is invalid")
    authority = _execution_authority(execution_authority)
    if entry["runtime_manifest_digest"] != authority["runtime_manifest_digest"]:
        _fail("case runtime manifest binding is invalid")
    if entry["execution_config_digest"] != _case_execution_digest(entry, authority):
        _fail("case execution configuration digest does not replay")
    if entry["case_id"] != _case_id(entry):
        _fail("case ID preimage does not replay")
    if entry["case_specification_digest"] != _case_specification_digest(entry):
        _fail("case specification digest does not replay")
    _require_digest_match(CASE_ENTRY_SCHEMA, entry, "record_digest", {"schema_version"})
    return entry


def build_case_manifest_entry(
    fields: Mapping[str, object], *, execution_authority: Mapping[str, object]
) -> dict[str, JsonValue]:
    """Build and self-validate a complete v3 geometry-case entry."""
    required = _CASE_ENTRY_KEYS - {
        "schema_version",
        "case_id",
        "execution_config_digest",
        "case_specification_digest",
        "record_digest",
    }
    _exact(fields, required, "geometry case manifest entry input")
    entry: dict[str, JsonValue] = {
        "schema_version": CASE_ENTRY_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
    }
    entry["execution_config_digest"] = _case_execution_digest(entry, execution_authority)
    entry["case_id"] = _case_id(entry)
    entry["case_specification_digest"] = _case_specification_digest(entry)
    entry["record_digest"] = _digest_for(CASE_ENTRY_SCHEMA, entry, {"schema_version"})
    validate_case_manifest_entry(entry, execution_authority=execution_authority)
    return entry


def validate_ordered_case_manifest(
    entries: Sequence[Mapping[str, object]],
    *,
    source_entries: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
    expected_digest: str | None = None,
) -> str:
    """Validate the frozen 4 x 3 x 2 x 2 Cartesian case matrix and return its digest."""
    if len(entries) != 48:
        _fail("case manifest must contain exactly 48 ordered entries")
    source_digest = digest_source_manifest(source_entries)
    seen_ids: set[str] = set()
    seen_specs: set[str] = set()
    seen_records: set[str] = set()
    for index, raw in enumerate(entries):
        entry = validate_case_manifest_entry(raw, execution_authority=execution_authority)
        source_ordinal = index // 12 + 1
        priority = index % 12 // 4 + 1
        direction_index = index % 4 // 2 + 1
        magnitude_index = index % 2 + 1
        source = validate_source_manifest_entry(source_entries[source_ordinal - 1])
        if (
            entry["case_ordinal"] != index + 1
            or entry["source_ordinal"] != source_ordinal
            or entry["dimension_key"] != CASE_DIMENSIONS[priority - 1]
            or entry["priority_index"] != priority
            or entry["direction"] != CASE_DIRECTIONS[direction_index - 1]
            or entry["direction_index"] != direction_index
            or entry["magnitude_ppm"] != CASE_MAGNITUDES[magnitude_index - 1]
            or entry["magnitude_index"] != magnitude_index
            or entry["source_manifest_digest"] != source_digest
        ):
            _fail("case manifest natural order or ordinal is invalid")
        for key in (
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "source_asset_sha256",
            "source_qa_snapshot_digest",
            "source_measurement_projection_digest",
            "source_p2_candidate_manifest_content_digest",
            "dimension_authority_manifest_content_digest",
        ):
            if entry[key] != source[key]:
                _fail("case manifest source authority binding is invalid")
        for value, seen, label in (
            (entry["case_id"], seen_ids, "case ID"),
            (entry["case_specification_digest"], seen_specs, "case specification digest"),
            (entry["record_digest"], seen_records, "case record digest"),
        ):
            if value in seen:
                _fail(f"case manifest duplicate {label}")
            seen.add(cast(str, value))
    digest = _case_manifest_digest(entries)
    if expected_digest is not None and _digest(expected_digest, "case manifest digest") != digest:
        _fail("case manifest digest does not replay")
    return digest


def build_ordered_case_manifest(
    source_entries: Sequence[Mapping[str, object]],
    *,
    execution_authority: Mapping[str, object],
    geometry_fields: Mapping[str, object],
) -> list[dict[str, JsonValue]]:
    """Derive the real 48-case frozen matrix from four validated source entries."""
    _exact(geometry_fields, _CASE_BUILD_FIELDS, "case geometry input")
    source_digest = digest_source_manifest(source_entries)
    entries: list[dict[str, JsonValue]] = []
    for source_ordinal, source_raw in enumerate(source_entries, start=1):
        source = validate_source_manifest_entry(source_raw)
        for priority, dimension in enumerate(CASE_DIMENSIONS, start=1):
            for direction_index, direction in enumerate(CASE_DIRECTIONS, start=1):
                for magnitude_index, magnitude in enumerate(CASE_MAGNITUDES, start=1):
                    fields: dict[str, object] = {
                        "case_ordinal": len(entries) + 1,
                        "source_manifest_digest": source_digest,
                        "source_ordinal": source_ordinal,
                        "source_authority_key": source["source_authority_key"],
                        "source_admission_event_id": source["source_admission_event_id"],
                        "source_asset_id": source["source_asset_id"],
                        "source_asset_sha256": source["source_asset_sha256"],
                        "source_qa_snapshot_digest": source["source_qa_snapshot_digest"],
                        "source_measurement_projection_digest": source[
                            "source_measurement_projection_digest"
                        ],
                        "source_p2_candidate_manifest_content_digest": source[
                            "source_p2_candidate_manifest_content_digest"
                        ],
                        "dimension_authority_manifest_content_digest": source[
                            "dimension_authority_manifest_content_digest"
                        ],
                        "runtime_manifest_digest": execution_authority["runtime_manifest_digest"],
                        "dimension_key": dimension,
                        "priority_index": priority,
                        "direction": direction,
                        "direction_index": direction_index,
                        "magnitude_ppm": magnitude,
                        "magnitude_index": magnitude_index,
                        "ordered_control_dimensions": list(_case_controls(dimension)),
                        **dict(geometry_fields),
                    }
                    entries.append(
                        build_case_manifest_entry(fields, execution_authority=execution_authority)
                    )
    validate_ordered_case_manifest(
        entries, source_entries=source_entries, execution_authority=execution_authority
    )
    return entries


def _m4_record_id(entry: Mapping[str, object], replay_index: int) -> str:
    if type(replay_index) is not int or replay_index not in {1, 2}:
        _fail("M4 replay index must be one or two")
    payload: dict[str, JsonValue] = {
        "case_id": cast(str, entry["case_id"]),
        "case_specification_digest": cast(str, entry["case_specification_digest"]),
        "replay_index": replay_index,
        "geometry_algorithm_version": cast(str, entry["geometry_algorithm_version"]),
        "runtime_manifest_digest": cast(str, entry["runtime_manifest_digest"]),
        "runtime_config_digest": cast(str, entry["runtime_config_digest"]),
        "determinism_level": cast(str, entry["determinism_level"]),
    }
    return mirror_demo_digest("mirror.demo/D02M4ExecutionRecordId/v1", payload)[:32]


def validate_m4_execution_record(
    value: object, *, case_entry: Mapping[str, object], execution_authority: Mapping[str, object]
) -> Mapping[str, Any]:
    """Replay one M4 execution receipt against its already validated case authority."""
    case = validate_case_manifest_entry(case_entry, execution_authority=execution_authority)
    record = _exact(value, _M4_EXECUTION_KEYS, "M4 execution record")
    if record["schema_version"] != M4_EXECUTION_SCHEMA:
        _fail("M4 execution record schema is invalid")
    _id(record["m4_execution_record_id"], "M4 execution record ID")
    for key in (
        "case_specification_digest",
        "source_asset_sha256",
        "result_sha256",
        "warp_plan_digest",
        "runtime_manifest_digest",
        "runtime_config_digest",
        "execution_receipt_digest",
    ):
        _digest(record[key], key)
    if (
        record["case_id"] != case["case_id"]
        or record["case_specification_digest"] != case["case_specification_digest"]
        or record["source_asset_id"] != case["source_asset_id"]
        or record["source_asset_sha256"] != case["source_asset_sha256"]
        or record["warp_plan_digest"] != case["warp_plan_digest"]
        or record["geometry_algorithm_version"] != case["geometry_algorithm_version"]
        or record["runtime_manifest_digest"] != case["runtime_manifest_digest"]
        or record["runtime_config_digest"] != case["runtime_config_digest"]
        or record["determinism_level"] != case["determinism_level"]
    ):
        _fail("M4 record case authority binding is invalid")
    if (
        not isinstance(record["source_output_id"], str)
        or _VERSION.fullmatch(record["source_output_id"]) is None
    ):
        _fail("M4 source output ID is invalid")
    if (
        not isinstance(record["result_output_id"], str)
        or _VERSION.fullmatch(record["result_output_id"]) is None
    ):
        _fail("M4 result output ID is invalid")
    if type(record["replay_index"]) is not int or record["replay_index"] not in {1, 2}:
        _fail("M4 replay index is invalid")
    if (
        type(record["result_byte_size"]) is not int
        or not 1 <= record["result_byte_size"] <= 9_223_372_036_854_775_807
    ):
        _fail("M4 result byte size is invalid")
    if record["result_mime_type"] != "image/jpeg":
        _fail("M4 result MIME type is invalid")
    for key in ("result_width", "result_height"):
        if type(record[key]) is not int or not 1 <= record[key] <= 2_147_483_647:
            _fail(f"M4 {key} is invalid")
    if (
        type(record["changed_pixel_count"]) is not int
        or not 1
        <= record["changed_pixel_count"]
        <= record["result_width"] * record["result_height"]
    ):
        _fail("M4 changed pixel count is invalid")
    if _bool(record["execution_succeeded"], "M4 execution succeeded") is not True:
        _fail("M4 execution must have succeeded")
    if record["m4_execution_record_id"] != _m4_record_id(case, record["replay_index"]):
        _fail("M4 execution record ID preimage does not replay")
    _require_digest_match(M4_EXECUTION_SCHEMA, record, "record_digest", {"schema_version"})
    return record


def build_m4_execution_record(
    fields: Mapping[str, object],
    *,
    case_entry: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> dict[str, JsonValue]:
    """Build one M4 receipt from a case plus execution-only receipt fields."""
    _exact(fields, _M4_BUILD_FIELDS, "M4 execution record input")
    case = validate_case_manifest_entry(case_entry, execution_authority=execution_authority)
    record: dict[str, JsonValue] = {
        "schema_version": M4_EXECUTION_SCHEMA,
        "case_id": cast(str, case["case_id"]),
        "case_specification_digest": cast(str, case["case_specification_digest"]),
        "source_asset_id": cast(str, case["source_asset_id"]),
        "source_asset_sha256": cast(str, case["source_asset_sha256"]),
        "warp_plan_digest": cast(str, case["warp_plan_digest"]),
        "geometry_algorithm_version": cast(str, case["geometry_algorithm_version"]),
        "runtime_manifest_digest": cast(str, case["runtime_manifest_digest"]),
        "runtime_config_digest": cast(str, case["runtime_config_digest"]),
        "determinism_level": cast(str, case["determinism_level"]),
        **cast(dict[str, JsonValue], dict(fields)),
    }
    record["m4_execution_record_id"] = _m4_record_id(record, cast(int, record["replay_index"]))
    record["record_digest"] = _digest_for(M4_EXECUTION_SCHEMA, record, {"schema_version"})
    validate_m4_execution_record(record, case_entry=case, execution_authority=execution_authority)
    return record


def validate_m4_repeat_evidence(
    records: Sequence[Mapping[str, object]],
    *,
    case_manifest: Sequence[Mapping[str, object]],
    source_entries: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> None:
    """Validate the fixed 48 cases by two deterministic M4 replays each."""
    validate_ordered_case_manifest(
        case_manifest,
        source_entries=source_entries,
        execution_authority=execution_authority,
    )
    if len(records) != 96:
        _fail("M4 evidence must contain exactly 96 ordered records")
    sources = [validate_source_manifest_entry(item) for item in source_entries]
    seen_ids: set[str] = set()
    seen_digests: set[str] = set()
    for index, raw in enumerate(records):
        case_index, expected_replay = divmod(index, 2)
        case = validate_case_manifest_entry(
            case_manifest[case_index], execution_authority=execution_authority
        )
        source = sources[int(case["source_ordinal"]) - 1]
        record = validate_m4_execution_record(
            raw, case_entry=case, execution_authority=execution_authority
        )
        if record["source_output_id"] != source["source_output_id"]:
            _fail("M4 record source output lineage is invalid")
        if record["replay_index"] != expected_replay + 1:
            _fail("M4 evidence natural replay order is invalid")
        for value, seen, label in (
            (record["m4_execution_record_id"], seen_ids, "M4 record ID"),
            (record["record_digest"], seen_digests, "M4 record digest"),
        ):
            if value in seen:
                _fail(f"M4 evidence duplicate {label}")
            seen.add(cast(str, value))
        if expected_replay == 1:
            first = validate_m4_execution_record(
                records[index - 1],
                case_entry=case,
                execution_authority=execution_authority,
            )
            for key in (
                "case_id",
                "case_specification_digest",
                "source_output_id",
                "source_asset_id",
                "source_asset_sha256",
                "result_output_id",
                "result_sha256",
                "result_byte_size",
                "result_mime_type",
                "result_width",
                "result_height",
                "changed_pixel_count",
                "warp_plan_digest",
                "geometry_algorithm_version",
                "runtime_manifest_digest",
                "runtime_config_digest",
                "determinism_level",
            ):
                if record[key] != first[key]:
                    _fail("M4 replay pair is not byte/dimension deterministic")


def _m4_pair(
    records: Sequence[Mapping[str, object]],
    case_index: int,
    *,
    case_entry: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    first = validate_m4_execution_record(
        records[case_index * 2], case_entry=case_entry, execution_authority=execution_authority
    )
    second = validate_m4_execution_record(
        records[case_index * 2 + 1], case_entry=case_entry, execution_authority=execution_authority
    )
    if first["replay_index"] != 1 or second["replay_index"] != 2:
        _fail("M4 replay pair order is invalid")
    return first, second


def _structure_values(
    case: Mapping[str, object], first: Mapping[str, object], second: Mapping[str, object]
) -> dict[str, bool]:
    bytes_equal = all(
        first[key] == second[key]
        for key in ("result_output_id", "result_sha256", "result_byte_size", "result_mime_type")
    )
    dimensions_equal = all(first[key] == second[key] for key in ("result_width", "result_height"))
    pixels_equal = first["changed_pixel_count"] == second["changed_pixel_count"]
    changed_pixel_count = first["changed_pixel_count"]
    if type(changed_pixel_count) is not int:
        _fail("M4 changed pixel count is invalid")
    values = {
        "source_decode_valid": True,
        "result_decode_valid": True,
        "bounded_dimensions_passed": (
            first["result_width"] == case["output_width"]
            and first["result_height"] == case["output_height"]
        ),
        "source_checksum_unchanged": True,
        "m4_replay_bytes_equal": bytes_equal,
        "m4_replay_dimensions_equal": dimensions_equal,
        "changed_pixel_count_equal": pixels_equal,
        "changed_pixel_count_positive": changed_pixel_count > 0,
        "immutable_result_binding_passed": True,
        "exact_lineage_passed": True,
        "target_and_controls_complete": True,
    }
    values["structure_gate_passed"] = all(values.values())
    return values


def validate_decode_structure_record(
    value: object,
    *,
    case_entry: Mapping[str, object],
    m4_first: Mapping[str, object],
    m4_second: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> Mapping[str, Any]:
    """Replay one derived decode/structure envelope from its case and two M4 receipts."""
    case = validate_case_manifest_entry(case_entry, execution_authority=execution_authority)
    first = validate_m4_execution_record(
        m4_first, case_entry=case, execution_authority=execution_authority
    )
    second = validate_m4_execution_record(
        m4_second, case_entry=case, execution_authority=execution_authority
    )
    if first["replay_index"] != 1 or second["replay_index"] != 2:
        _fail("structure M4 replay order is invalid")
    record = _exact(value, _STRUCTURE_KEYS, "decode structure record")
    if record["schema_version"] != STRUCTURE_SCHEMA:
        _fail("decode structure record schema is invalid")
    for key in (
        "case_specification_digest",
        "source_asset_sha256",
        "result_sha256",
        "record_digest",
    ):
        _digest(record[key], key)
    for key in ("case_id", "source_asset_id", "result_image_record_id"):
        _id(record[key], key)
    if (
        record["case_id"] != case["case_id"]
        or record["case_specification_digest"] != case["case_specification_digest"]
        or record["source_asset_id"] != case["source_asset_id"]
        or record["source_asset_sha256"] != case["source_asset_sha256"]
        or record["m4_execution_record_digests"]
        != [first["record_digest"], second["record_digest"]]
    ):
        _fail("decode structure case or M4 binding is invalid")
    for key in (
        "result_output_id",
        "result_sha256",
        "result_byte_size",
        "result_mime_type",
        "result_width",
        "result_height",
    ):
        if record[key] != first[key]:
            _fail("decode structure result binding is invalid")
    for key, expected in _structure_values(case, first, second).items():
        if _bool(record[key], key) != expected:
            _fail("decode structure gate is not derived")
    _require_digest_match(STRUCTURE_SCHEMA, record, "record_digest", {"schema_version"})
    return record


def build_decode_structure_record(
    fields: Mapping[str, object],
    *,
    case_entry: Mapping[str, object],
    m4_first: Mapping[str, object],
    m4_second: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> dict[str, JsonValue]:
    """Build the fully derived structure record; only the downstream image ID is supplied."""
    _exact(fields, _STRUCTURE_BUILD_FIELDS, "decode structure record input")
    case = validate_case_manifest_entry(case_entry, execution_authority=execution_authority)
    first = validate_m4_execution_record(
        m4_first, case_entry=case, execution_authority=execution_authority
    )
    second = validate_m4_execution_record(
        m4_second, case_entry=case, execution_authority=execution_authority
    )
    record: dict[str, JsonValue] = {
        "schema_version": STRUCTURE_SCHEMA,
        "case_id": cast(str, case["case_id"]),
        "case_specification_digest": cast(str, case["case_specification_digest"]),
        "source_asset_id": cast(str, case["source_asset_id"]),
        "source_asset_sha256": cast(str, case["source_asset_sha256"]),
        "m4_execution_record_digests": [first["record_digest"], second["record_digest"]],
        **{
            key: first[key]
            for key in (
                "result_output_id",
                "result_sha256",
                "result_byte_size",
                "result_mime_type",
                "result_width",
                "result_height",
            )
        },
        **cast(dict[str, JsonValue], dict(fields)),
        **_structure_values(case, first, second),
    }
    record["record_digest"] = _digest_for(STRUCTURE_SCHEMA, record, {"schema_version"})
    validate_decode_structure_record(
        record,
        case_entry=case,
        m4_first=first,
        m4_second=second,
        execution_authority=execution_authority,
    )
    return record


def validate_decode_structure_evidence(
    records: Sequence[Mapping[str, object]],
    *,
    case_manifest: Sequence[Mapping[str, object]],
    source_entries: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> None:
    """Validate the 48 ordered derived structure records against all M4 pairs."""
    if len(records) != 48:
        _fail("decode structure evidence must contain exactly 48 ordered records")
    validate_m4_repeat_evidence(
        m4_records,
        case_manifest=case_manifest,
        source_entries=source_entries,
        execution_authority=execution_authority,
    )
    seen: set[str] = set()
    for index, raw in enumerate(records):
        record = validate_decode_structure_record(
            raw,
            case_entry=case_manifest[index],
            m4_first=m4_records[index * 2],
            m4_second=m4_records[index * 2 + 1],
            execution_authority=execution_authority,
        )
        if record["record_digest"] in seen:
            _fail("decode structure evidence duplicate record digest")
        seen.add(cast(str, record["record_digest"]))


def validate_manual_artifact_decision(
    value: object,
    *,
    case_entry: Mapping[str, object],
    m4_first: Mapping[str, object],
    execution_authority: Mapping[str, object],
    expected_sequence: int | None = None,
) -> Mapping[str, Any]:
    """Replay one manual authority decision bound to a case's first deterministic M4 output."""
    case = validate_case_manifest_entry(case_entry, execution_authority=execution_authority)
    first = validate_m4_execution_record(
        m4_first, case_entry=case, execution_authority=execution_authority
    )
    record = _exact(value, _MANUAL_KEYS, "manual artifact decision")
    if record["schema_version"] != MANUAL_SCHEMA:
        _fail("manual artifact decision schema is invalid")
    for key in (
        "result_sha256",
        "manual_review_policy_digest",
        "review_authority_digest",
        "manual_decision_digest",
    ):
        _digest(record[key], key)
    if record["case_id"] != case["case_id"] or record["result_sha256"] != first["result_sha256"]:
        _fail("manual decision case or result binding is invalid")
    if (
        record["manual_review_policy_digest"]
        != _execution_authority(execution_authority)["manual_review_policy_digest"]
    ):
        _fail("manual review policy binding is invalid")
    if (
        not isinstance(record["manual_review_version"], str)
        or _VERSION.fullmatch(record["manual_review_version"]) is None
    ):
        _fail("manual review version is invalid")
    if type(record["decision_sequence"]) is not int or not 1 <= record["decision_sequence"] <= 48:
        _fail("manual decision sequence is invalid")
    if expected_sequence is not None and record["decision_sequence"] != expected_sequence:
        _fail("manual decision sequence order is invalid")
    artifacts = tuple(
        _bool(record[key], key)
        for key in ("background_seam", "disconnected_contour", "duplicated_feature", "warp_tear")
    )
    if record["verdict"] != ("FAIL" if any(artifacts) else "PASS"):
        _fail("manual verdict is not derived")
    _require_digest_match(MANUAL_SCHEMA, record, "manual_decision_digest", {"schema_version"})
    return record


def build_manual_artifact_decision(
    fields: Mapping[str, object],
    *,
    case_entry: Mapping[str, object],
    m4_first: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> dict[str, JsonValue]:
    """Build one manual decision with its case, result SHA, policy and verdict derived."""
    _exact(fields, _MANUAL_BUILD_FIELDS, "manual artifact decision input")
    case = validate_case_manifest_entry(case_entry, execution_authority=execution_authority)
    first = validate_m4_execution_record(
        m4_first, case_entry=case, execution_authority=execution_authority
    )
    artifacts = [
        _bool(fields[key], key)
        for key in ("background_seam", "disconnected_contour", "duplicated_feature", "warp_tear")
    ]
    record: dict[str, JsonValue] = {
        "schema_version": MANUAL_SCHEMA,
        "case_id": cast(str, case["case_id"]),
        "result_sha256": cast(str, first["result_sha256"]),
        "manual_review_policy_digest": cast(
            str, _execution_authority(execution_authority)["manual_review_policy_digest"]
        ),
        **cast(dict[str, JsonValue], dict(fields)),
        "verdict": "FAIL" if any(artifacts) else "PASS",
    }
    record["manual_decision_digest"] = _digest_for(MANUAL_SCHEMA, record, {"schema_version"})
    validate_manual_artifact_decision(
        record, case_entry=case, m4_first=first, execution_authority=execution_authority
    )
    return record


def validate_manual_review_evidence(
    records: Sequence[Mapping[str, object]],
    *,
    case_manifest: Sequence[Mapping[str, object]],
    source_entries: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> None:
    """Validate 48 C-collated manual decisions and their canonical sequence authority."""
    if len(records) != 48:
        _fail("manual review evidence must contain exactly 48 ordered records")
    validate_m4_repeat_evidence(
        m4_records,
        case_manifest=case_manifest,
        source_entries=source_entries,
        execution_authority=execution_authority,
    )
    cases = sorted(case_manifest, key=lambda entry: str(entry["case_id"]))
    case_positions = {str(case["case_id"]): index for index, case in enumerate(case_manifest)}
    seen: set[str] = set()
    for sequence, (record, case) in enumerate(zip(records, cases, strict=True), start=1):
        case_index = case_positions[str(case["case_id"])]
        parsed = validate_manual_artifact_decision(
            record,
            case_entry=case,
            m4_first=m4_records[case_index * 2],
            execution_authority=execution_authority,
            expected_sequence=sequence,
        )
        if parsed["manual_decision_digest"] in seen:
            _fail("manual review evidence duplicate decision digest")
        seen.add(cast(str, parsed["manual_decision_digest"]))


def _image_record_id(schema: str, value: Mapping[str, object]) -> str:
    if schema == SOURCE_IMAGE_SCHEMA:
        payload: dict[str, JsonValue] = {
            key: cast(JsonValue, value[key])
            for key in (
                "authority_role",
                "source_authority_key",
                "source_admission_event_id",
                "source_asset_id",
                "sha256",
            )
        }
        domain = SOURCE_IMAGE_ID_DOMAIN
    elif schema == RESULT_IMAGE_SCHEMA:
        payload = {
            key: cast(JsonValue, value[key])
            for key in (
                "authority_role",
                "source_authority_key",
                "source_admission_event_id",
                "case_id",
                "case_specification_digest",
                "result_output_id",
                "deterministic_result_asset_id",
                "sha256",
            )
        }
        domain = RESULT_IMAGE_ID_DOMAIN
    else:
        _fail("image record schema is invalid")
    return mirror_demo_digest(domain, payload)[:32]


def _image_record_digest(schema: str, record: Mapping[str, object]) -> str:
    return _digest_for(schema, record, {"schema_version", "image_record_digest"})


def _validate_image_record_shape(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("image authority record must be an object")
    schema = value.get("schema_version")
    if schema == SOURCE_IMAGE_SCHEMA:
        record = _exact(value, _SOURCE_IMAGE_KEYS, "source image authority record")
        if record["authority_role"] != "SOURCE":
            _fail("source image authority role is invalid")
        optional_keys: tuple[str, ...] = ()
    elif schema == RESULT_IMAGE_SCHEMA:
        record = _exact(value, _RESULT_IMAGE_KEYS, "result image authority record")
        if record["authority_role"] != "RESULT":
            _fail("result image authority role is invalid")
        optional_keys = (
            "case_id",
            "case_specification_digest",
            "result_output_id",
            "deterministic_result_asset_id",
        )
    else:
        _fail("image authority record schema is invalid")
    if (
        type(record["image_record_ordinal"]) is not int
        or not 1 <= record["image_record_ordinal"] <= 52
    ):
        _fail("image authority record ordinal is invalid")
    for key in ("image_record_id", "source_admission_event_id"):
        _id(record[key], key)
    if schema == SOURCE_IMAGE_SCHEMA:
        _id(record["source_asset_id"], "source_asset_id")
    for key in ("sha256", "image_record_digest"):
        _digest(record[key], key)
    _digest(record["source_authority_key"], "image source authority key")
    if type(record["source_ordinal"]) is not int or not 1 <= record["source_ordinal"] <= 4:
        _fail("image source ordinal is invalid")
    if (
        type(record["byte_size"]) is not int
        or not 1 <= record["byte_size"] <= 9_223_372_036_854_775_807
    ):
        _fail("image byte size is invalid")
    if record["mime_type"] != "image/jpeg":
        _fail("image MIME type is invalid")
    for key in ("width", "height"):
        if type(record[key]) is not int or not 1 <= record[key] <= 2_147_483_647:
            _fail(f"image {key} is invalid")
    for key in optional_keys:
        if key == "case_id":
            _id(record[key], key)
        elif key == "deterministic_result_asset_id":
            _id(record[key], key)
        elif key.endswith("digest"):
            _digest(record[key], key)
        elif not isinstance(record[key], str) or _VERSION.fullmatch(record[key]) is None:
            _fail(f"image {key} is invalid")
    if record["image_record_id"] != _image_record_id(cast(str, schema), record):
        _fail("image authority record ID preimage does not replay")
    if record["image_record_digest"] != _image_record_digest(cast(str, schema), record):
        _fail("image authority record digest does not replay")
    return record


def _image_context(
    source_entries: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    if len(source_entries) != 4 or len(case_manifest) != 48:
        _fail("image authority requires four sources and 48 cases")
    source_digest = digest_source_manifest(source_entries)
    validate_ordered_case_manifest(
        case_manifest,
        source_entries=source_entries,
        execution_authority=execution_authority,
    )
    validate_m4_repeat_evidence(
        m4_records,
        case_manifest=case_manifest,
        source_entries=source_entries,
        execution_authority=execution_authority,
    )
    sources = [validate_source_manifest_entry(item) for item in source_entries]
    cases = [
        validate_case_manifest_entry(item, execution_authority=execution_authority)
        for item in case_manifest
    ]
    if any(case["source_manifest_digest"] != source_digest for case in cases):
        _fail("image authority case/source manifest binding is invalid")
    first_m4 = [
        validate_m4_execution_record(
            m4_records[index * 2], case_entry=case, execution_authority=execution_authority
        )
        for index, case in enumerate(cases)
    ]
    return sources, cases, first_m4


def _expected_image_records(
    source_entries: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
    result_asset_ids: Mapping[str, object],
) -> list[dict[str, JsonValue]]:
    sources, cases, first_m4 = _image_context(
        source_entries, case_manifest, m4_records, execution_authority
    )
    case_ids = {cast(str, case["case_id"]) for case in cases}
    if set(result_asset_ids) != case_ids:
        _fail("result Asset IDs must bind exactly the 48 case IDs")
    validated_result_asset_ids = {
        case_id: _id(result_asset_ids[case_id], f"result Asset ID for case {case_id}")
        for case_id in case_ids
    }
    records: list[dict[str, JsonValue]] = []
    for source in sources:
        record: dict[str, JsonValue] = {
            "schema_version": SOURCE_IMAGE_SCHEMA,
            "authority_role": "SOURCE",
            "source_ordinal": cast(int, source["source_ordinal"]),
            "source_authority_key": cast(str, source["source_authority_key"]),
            "source_admission_event_id": cast(str, source["source_admission_event_id"]),
            "source_asset_id": cast(str, source["source_asset_id"]),
            "sha256": cast(str, source["source_asset_sha256"]),
            "byte_size": cast(int, source["source_asset_byte_size"]),
            "mime_type": cast(str, source["source_asset_mime_type"]),
            "width": cast(int, source["source_asset_width"]),
            "height": cast(int, source["source_asset_height"]),
        }
        record["image_record_id"] = _image_record_id(SOURCE_IMAGE_SCHEMA, record)
        records.append(record)
    for case, m4 in zip(cases, first_m4, strict=True):
        record = {
            "schema_version": RESULT_IMAGE_SCHEMA,
            "authority_role": "RESULT",
            "source_ordinal": cast(int, case["source_ordinal"]),
            "source_authority_key": cast(str, case["source_authority_key"]),
            "source_admission_event_id": cast(str, case["source_admission_event_id"]),
            "case_id": cast(str, case["case_id"]),
            "case_specification_digest": cast(str, case["case_specification_digest"]),
            "result_output_id": cast(str, m4["result_output_id"]),
            "deterministic_result_asset_id": validated_result_asset_ids[cast(str, case["case_id"])],
            "sha256": cast(str, m4["result_sha256"]),
            "byte_size": cast(int, m4["result_byte_size"]),
            "mime_type": cast(str, m4["result_mime_type"]),
            "width": cast(int, m4["result_width"]),
            "height": cast(int, m4["result_height"]),
        }
        record["image_record_id"] = _image_record_id(RESULT_IMAGE_SCHEMA, record)
        records.append(record)
    records.sort(key=lambda item: (cast(str, item["sha256"]), cast(str, item["image_record_id"])))
    for ordinal, record in enumerate(records, start=1):
        record["image_record_ordinal"] = ordinal
        schema = cast(str, record["schema_version"])
        record["image_record_digest"] = _image_record_digest(schema, record)
    return records


def build_image_authority_evidence(
    *,
    source_entries: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
    result_asset_ids: Mapping[str, object],
) -> list[dict[str, JsonValue]]:
    """Build the full image universe from source/M4 roots and caller-bound Asset IDs."""
    return _expected_image_records(
        source_entries,
        case_manifest,
        m4_records,
        execution_authority,
        result_asset_ids,
    )


def validate_image_authority_evidence(
    image_records: Sequence[Mapping[str, object]],
    *,
    source_entries: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
    result_asset_ids: Mapping[str, object],
) -> bool:
    """Validate all image lineage and return only the exact-SHA gate result."""
    if len(image_records) != 52:
        _fail("image authority evidence must contain exactly 52 records")
    expected = _expected_image_records(
        source_entries,
        case_manifest,
        m4_records,
        execution_authority,
        result_asset_ids,
    )
    parsed = [_validate_image_record_shape(record) for record in image_records]
    if list(parsed) != expected:
        _fail("image authority evidence does not replay from source/M4 authority")
    if [record["image_record_ordinal"] for record in parsed] != list(range(1, 53)):
        _fail("image authority ordinal order is invalid")
    return len({cast(str, record["sha256"]) for record in parsed}) == 52


def _exact_duplicate_values(
    image_records: Sequence[Mapping[str, object]],
) -> dict[str, bool]:
    parsed = [_validate_image_record_shape(record) for record in image_records]
    if len(parsed) != 52:
        _fail("exact duplicate evidence must contain exactly 52 image records")
    source_sha = [
        cast(str, record["sha256"]) for record in parsed if record["authority_role"] == "SOURCE"
    ]
    result_sha = [
        cast(str, record["sha256"]) for record in parsed if record["authority_role"] == "RESULT"
    ]
    if len(source_sha) != 4 or len(result_sha) != 48:
        _fail("exact duplicate source/result image cardinality is invalid")
    values = {
        "all_record_sha_unique": len(set(source_sha + result_sha)) == 52,
        "source_sha_unique": len(set(source_sha)) == 4,
        "result_sha_unique": len(set(result_sha)) == 48,
        "source_result_sha_disjoint": set(source_sha).isdisjoint(result_sha),
    }
    values["exact_sha_gate_passed"] = all(values.values())
    return values


def build_exact_duplicate_evidence(
    *,
    image_records: Sequence[Mapping[str, object]],
    source_entries: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
    result_asset_ids: Mapping[str, object],
) -> dict[str, JsonValue]:
    """Build the typed 52-image exact-SHA outcome Gate without pHash semantics."""
    validate_image_authority_evidence(
        image_records,
        source_entries=source_entries,
        case_manifest=case_manifest,
        m4_records=m4_records,
        execution_authority=execution_authority,
        result_asset_ids=result_asset_ids,
    )
    return {
        "schema_version": EXACT_DUPLICATE_SCHEMA,
        "image_records": cast(list[JsonValue], list(image_records)),
        **_exact_duplicate_values(image_records),
    }


def validate_exact_duplicate_evidence(
    value: object,
    *,
    source_entries: Sequence[Mapping[str, object]],
    case_manifest: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
    result_asset_ids: Mapping[str, object],
) -> Mapping[str, Any]:
    """Replay the typed exact-SHA wrapper and all source/M4 image authority."""
    evidence = _exact(value, _EXACT_DUPLICATE_KEYS, "exact duplicate evidence")
    if evidence["schema_version"] != EXACT_DUPLICATE_SCHEMA:
        _fail("exact duplicate evidence schema is invalid")
    image_records = evidence["image_records"]
    if not isinstance(image_records, list):
        _fail("exact duplicate image records must be an array")
    validate_image_authority_evidence(
        image_records,
        source_entries=source_entries,
        case_manifest=case_manifest,
        m4_records=m4_records,
        execution_authority=execution_authority,
        result_asset_ids=result_asset_ids,
    )
    expected = _exact_duplicate_values(image_records)
    for key, expected_value in expected.items():
        if _bool(evidence[key], key) != expected_value:
            _fail("exact duplicate Gate booleans do not replay")
    return evidence


def _phash_signature_digest(record: Mapping[str, object]) -> str:
    return _digest_for(PHASH_SIGNATURE_SCHEMA, record, {"schema_version", "signature_digest"})


def _phash_comparison_digest(record: Mapping[str, object]) -> str:
    return _digest_for(PHASH_COMPARISON_SCHEMA, record, {"schema_version", "comparison_digest"})


def _phash_hex(value: object) -> str:
    if not isinstance(value, str) or _PHASH_HEX.fullmatch(value) is None:
        _fail("pHash signature must be exactly 16 lowercase hexadecimal characters")
    return value


def build_phash_observation_evidence(
    *,
    image_records: Sequence[Mapping[str, object]],
    image_phashes: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> dict[str, JsonValue]:
    """Build observation-only pHash signatures and the complete unordered matrix."""
    if len(image_records) != 52:
        _fail("pHash evidence requires exactly 52 image records")
    parsed = [_validate_image_record_shape(record) for record in image_records]
    if [record["image_record_ordinal"] for record in parsed] != list(range(1, 53)):
        _fail("pHash image ordinal order is invalid")
    if set(image_phashes) != {cast(str, record["image_record_id"]) for record in parsed}:
        _fail("pHash signatures must bind exactly the 52 image record IDs")
    implementation_digest = cast(
        str, _execution_authority(execution_authority)["phash_implementation_digest"]
    )
    signatures: list[dict[str, JsonValue]] = []
    for image in parsed:
        signature: dict[str, JsonValue] = {
            "schema_version": PHASH_SIGNATURE_SCHEMA,
            "image_record_ordinal": cast(int, image["image_record_ordinal"]),
            "image_record_id": cast(str, image["image_record_id"]),
            "image_record_digest": cast(str, image["image_record_digest"]),
            "image_sha256": cast(str, image["sha256"]),
            "phash_hex": _phash_hex(image_phashes[cast(str, image["image_record_id"])]),
        }
        signature["signature_digest"] = _phash_signature_digest(signature)
        signatures.append(signature)
    comparisons: list[dict[str, JsonValue]] = []
    ordinal = 1
    for left_index, left in enumerate(signatures):
        for right in signatures[left_index + 1 :]:
            distance = (
                int(cast(str, left["phash_hex"]), 16) ^ int(cast(str, right["phash_hex"]), 16)
            ).bit_count()
            comparison: dict[str, JsonValue] = {
                "schema_version": PHASH_COMPARISON_SCHEMA,
                "comparison_ordinal": ordinal,
                "left_image_record_ordinal": left["image_record_ordinal"],
                "left_image_record_id": left["image_record_id"],
                "left_signature_digest": left["signature_digest"],
                "right_image_record_ordinal": right["image_record_ordinal"],
                "right_image_record_id": right["image_record_id"],
                "right_signature_digest": right["signature_digest"],
                "hamming_distance": distance,
            }
            comparison["comparison_digest"] = _phash_comparison_digest(comparison)
            comparisons.append(comparison)
            ordinal += 1
    return {
        "schema_version": PHASH_EVIDENCE_SCHEMA,
        "implementation_digest": implementation_digest,
        "bit_width": 64,
        "threshold_policy": "OBSERVATION_ONLY_NO_THRESHOLD",
        "ordered_record_signatures": cast(list[JsonValue], signatures),
        "comparisons": cast(list[JsonValue], comparisons),
    }


def validate_phash_observation_evidence(
    value: object,
    *,
    image_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> Mapping[str, Any]:
    """Replay only checksum-bound observation evidence; it has no selection semantics."""
    evidence = _exact(value, _PHASH_EVIDENCE_KEYS, "pHash observation evidence")
    if evidence["schema_version"] != PHASH_EVIDENCE_SCHEMA:
        _fail("pHash observation evidence schema is invalid")
    implementation_digest = _execution_authority(execution_authority)["phash_implementation_digest"]
    if evidence["implementation_digest"] != implementation_digest:
        _fail("pHash implementation digest binding is invalid")
    if (
        evidence["bit_width"] != 64
        or evidence["threshold_policy"] != "OBSERVATION_ONLY_NO_THRESHOLD"
    ):
        _fail("pHash observation policy is invalid")
    if len(image_records) != 52:
        _fail("pHash validation requires exactly 52 image records")
    images = [_validate_image_record_shape(record) for record in image_records]
    if [record["image_record_ordinal"] for record in images] != list(range(1, 53)):
        _fail("pHash image ordinal order is invalid")
    signatures = evidence["ordered_record_signatures"]
    comparisons = evidence["comparisons"]
    if not isinstance(signatures, list) or len(signatures) != 52:
        _fail("pHash evidence must contain exactly 52 ordered signatures")
    if not isinstance(comparisons, list) or len(comparisons) != 1326:
        _fail("pHash evidence must contain exactly 1326 ordered comparisons")
    parsed_signatures: list[Mapping[str, Any]] = []
    for image, raw in zip(images, signatures, strict=True):
        signature = _exact(raw, _PHASH_SIGNATURE_KEYS, "pHash signature")
        if signature["schema_version"] != PHASH_SIGNATURE_SCHEMA:
            _fail("pHash signature schema is invalid")
        if type(signature["image_record_ordinal"]) is not int:
            _fail("pHash signature image ordinal is invalid")
        for key in ("image_record_id",):
            _id(signature[key], key)
        for key in ("image_record_digest", "image_sha256", "signature_digest"):
            _digest(signature[key], key)
        if signature["image_record_ordinal"] != image["image_record_ordinal"] or any(
            signature[key] != image[image_key]
            for key, image_key in (
                ("image_record_id", "image_record_id"),
                ("image_record_digest", "image_record_digest"),
                ("image_sha256", "sha256"),
            )
        ):
            _fail("pHash signature image binding is invalid")
        _phash_hex(signature["phash_hex"])
        if signature["signature_digest"] != _phash_signature_digest(signature):
            _fail("pHash signature digest does not replay")
        parsed_signatures.append(signature)
    comparison_ordinal = 1
    for left_index, left in enumerate(parsed_signatures):
        for right in parsed_signatures[left_index + 1 :]:
            comparison = _exact(
                comparisons[comparison_ordinal - 1], _PHASH_COMPARISON_KEYS, "pHash comparison"
            )
            if comparison["schema_version"] != PHASH_COMPARISON_SCHEMA:
                _fail("pHash comparison schema is invalid")
            if (
                type(comparison["comparison_ordinal"]) is not int
                or comparison["comparison_ordinal"] != comparison_ordinal
            ):
                _fail("pHash comparison order is invalid")
            if any(
                type(comparison[key]) is not int
                for key in ("left_image_record_ordinal", "right_image_record_ordinal")
            ):
                _fail("pHash comparison image ordinals are invalid")
            expected_binding = {
                "left_image_record_ordinal": left["image_record_ordinal"],
                "left_image_record_id": left["image_record_id"],
                "left_signature_digest": left["signature_digest"],
                "right_image_record_ordinal": right["image_record_ordinal"],
                "right_image_record_id": right["image_record_id"],
                "right_signature_digest": right["signature_digest"],
            }
            if any(comparison[key] != expected for key, expected in expected_binding.items()):
                _fail("pHash comparison signature binding is invalid")
            distance = (
                int(cast(str, left["phash_hex"]), 16) ^ int(cast(str, right["phash_hex"]), 16)
            ).bit_count()
            if (
                type(comparison["hamming_distance"]) is not int
                or comparison["hamming_distance"] != distance
            ):
                _fail("pHash comparison Hamming distance is invalid")
            if comparison["comparison_digest"] != _phash_comparison_digest(comparison):
                _fail("pHash comparison digest does not replay")
            comparison_ordinal += 1
    return evidence


def validate_result_m3_gate_cross_graph(
    *,
    case_manifest: Sequence[Mapping[str, object]],
    source_entries: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    result_records: Sequence[Mapping[str, object]],
    gates: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
) -> None:
    """Validate the layered 48 x (M4x2, ResultM3x3, Gate) authority graph."""
    if len(case_manifest) != 48 or len(source_entries) != 4:
        _fail("ResultM3 graph requires 48 cases and four source authorities")
    if len(result_records) != 144 or len(gates) != 48:
        _fail("ResultM3 graph requires exactly 144 records and 48 gates")
    validate_m4_repeat_evidence(
        m4_records,
        case_manifest=case_manifest,
        source_entries=source_entries,
        execution_authority=execution_authority,
    )
    authority = _execution_authority(execution_authority)
    seen_ids: set[str] = set()
    seen_digests: set[str] = set()
    for case_index, case_raw in enumerate(case_manifest):
        case = validate_case_manifest_entry(case_raw, execution_authority=authority)
        source = validate_source_manifest_entry(source_entries[int(case["source_ordinal"]) - 1])
        for key in (
            "source_authority_key",
            "source_admission_event_id",
            "source_asset_id",
            "source_asset_sha256",
            "source_qa_snapshot_digest",
            "source_measurement_projection_digest",
            "source_p2_candidate_manifest_content_digest",
            "dimension_authority_manifest_content_digest",
        ):
            if case[key] != source[key]:
                _fail("ResultM3 graph case/source authority binding is invalid")
        first, _ = _m4_pair(m4_records, case_index, case_entry=case, execution_authority=authority)
        triple = result_records[case_index * 3 : case_index * 3 + 3]
        parsed = [validate_result_m3_record(record) for record in triple]
        if [item["repeat_index"] for item in parsed] != [1, 2, 3]:
            _fail("ResultM3 graph repeat order is invalid")
        for item in parsed:
            if (
                item["case_id"] != case["case_id"]
                or item["case_specification_digest"] != case["case_specification_digest"]
                or item["result_output_id"] != first["result_output_id"]
                or item["result_sha256"] != first["result_sha256"]
                or item["runtime_manifest_digest"] != case["runtime_manifest_digest"]
                or item["vision_model_manifest_digest"] != authority["vision_model_manifest_digest"]
                or item["topology_digest"] != authority["topology_digest"]
            ):
                _fail("ResultM3 graph M4/case/execution binding is invalid")
            for value, seen, label in (
                (item["result_m3_record_id"], seen_ids, "ResultM3 ID"),
                (item["record_digest"], seen_digests, "ResultM3 digest"),
            ):
                if value in seen:
                    _fail(f"ResultM3 graph duplicate {label}")
                seen.add(cast(str, value))
        gate = validate_measurement_gate(
            gates[case_index], result_records=parsed, source_measurement_authority=source
        )
        peer_index = case_index + 1 if case["magnitude_ppm"] == 15_000 else case_index - 1
        peer = validate_case_manifest_entry(
            case_manifest[peer_index], execution_authority=authority
        )
        if (
            gate["case_id"] != case["case_id"]
            or gate["case_specification_digest"] != case["case_specification_digest"]
            or gate["dimension_key"] != case["dimension_key"]
            or gate["requested_direction"] != case["direction"]
            or gate["requested_magnitude_ppm"] != case["magnitude_ppm"]
            or gate["monotonicity_peer_case_id"] != peer["case_id"]
        ):
            _fail("ResultM3 graph gate/case/peer binding is invalid")
    for lower_index in range(0, 48, 2):
        lower = cast(Mapping[str, Any], gates[lower_index])
        upper = cast(Mapping[str, Any], gates[lower_index + 1])
        lower_state = lower["measurement_evaluation_state"]
        upper_state = upper["measurement_evaluation_state"]
        if lower_state == upper_state == "SUPPORTED_EVALUATED":
            lower_measurements = cast(
                list[Mapping[str, Any]], lower["ordered_result_repeat_measurements"]
            )
            upper_measurements = cast(
                list[Mapping[str, Any]], upper["ordered_result_repeat_measurements"]
            )
            expected = all(
                _fixed18_units(
                    upper_item["raw_target_absolute_delta_fixed18"],
                    "upper magnitude target delta",
                )
                >= _fixed18_units(
                    lower_item["raw_target_absolute_delta_fixed18"],
                    "lower magnitude target delta",
                )
                for lower_item, upper_item in zip(
                    lower_measurements, upper_measurements, strict=True
                )
            )
            for gate in (lower, upper):
                evaluation = cast(Mapping[str, Any], gate["gate_evaluation"])
                if (
                    _bool(
                        evaluation["magnitude_monotonicity_gate_passed"],
                        "magnitude monotonicity gate",
                    )
                    != expected
                ):
                    _fail("magnitude peer monotonicity does not replay raw fixed18 evidence")
        elif "SUPPORTED_EVALUATED" in {lower_state, upper_state}:
            supported = lower if lower_state == "SUPPORTED_EVALUATED" else upper
            evaluation = cast(Mapping[str, Any], supported["gate_evaluation"])
            if _bool(
                evaluation["magnitude_monotonicity_gate_passed"],
                "mixed-peer monotonicity gate",
            ) or _bool(evaluation["measurement_gate_passed"], "mixed-peer measurement gate"):
                _fail("supported measurement with unsupported magnitude peer must fail closed")


def _side_quality_ppm(raw_drift: object, *, side_gate_passed: bool) -> int:
    drift_units = _fixed18_units(raw_drift, "side maximum control drift")
    if not side_gate_passed:
        return 0
    drift = Decimal(drift_units) / Decimal(10**18)
    value = ((Decimal(1) - drift / Decimal("0.020000000000000000")) * Decimal(1_000_000)).quantize(
        Decimal(1), rounding=ROUND_HALF_EVEN
    )
    return max(1, min(1_000_000, int(value)))


def _expected_result_variant_binding(
    case: Mapping[str, Any], first_m4: Mapping[str, Any]
) -> dict[str, JsonValue]:
    result_asset_id = derive_imported_asset_id(
        asset_role="synthetic",
        semantic_role="SELECTED_RESULT",
        sha256=first_m4["result_sha256"],
        byte_size=first_m4["result_byte_size"],
        mime_type=first_m4["result_mime_type"],
        width=first_m4["result_width"],
        height=first_m4["result_height"],
    )
    variant_id = derive_asset_variant_id(
        variant_type=VARIANT_TYPE,
        source_asset_id=case["source_asset_id"],
        source_asset_sha256=case["source_asset_sha256"],
        result_asset_id=result_asset_id,
        result_asset_sha256=first_m4["result_sha256"],
        case_specification_digest=case["case_specification_digest"],
    )
    return {
        "source_asset_id": cast(str, case["source_asset_id"]),
        "source_asset_sha256": cast(str, case["source_asset_sha256"]),
        "result_asset_id": result_asset_id,
        "result_asset_sha256": cast(str, first_m4["result_sha256"]),
        "asset_variant_id": variant_id,
        "asset_variant_type": VARIANT_TYPE,
        "case_specification_digest": cast(str, case["case_specification_digest"]),
    }


def _validate_result_variant_bindings(
    *,
    cases: Sequence[Mapping[str, Any]],
    m4_records: Sequence[Mapping[str, Any]],
    result_variant_bindings: Mapping[str, object],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, str]]:
    if len(cases) != 48 or len(m4_records) != 96:
        _fail("result AssetVariant validation requires 48 cases and 96 M4 records")
    case_ids = {cast(str, case["case_id"]) for case in cases}
    if set(result_variant_bindings) != case_ids:
        _fail("result variant bindings must cover exactly the 48 cases")
    variant_by_case: dict[str, Mapping[str, Any]] = {}
    result_asset_ids: dict[str, str] = {}
    source_asset_ids = {cast(str, case["source_asset_id"]) for case in cases}
    seen_result_asset_ids: set[str] = set()
    seen_variant_ids: set[str] = set()
    for case_index, case in enumerate(cases):
        case_id = cast(str, case["case_id"])
        first_m4 = m4_records[case_index * 2]
        expected = _expected_result_variant_binding(case, first_m4)
        actual = _exact(
            result_variant_bindings[case_id],
            _VARIANT_BINDING_KEYS,
            "result AssetVariant binding",
        )
        if actual != expected:
            _fail("result Asset/AssetVariant typed authority binding does not replay")
        result_asset_id = cast(str, actual["result_asset_id"])
        variant_id = cast(str, actual["asset_variant_id"])
        if (
            result_asset_id in source_asset_ids
            or result_asset_id in seen_result_asset_ids
            or variant_id in seen_variant_ids
        ):
            _fail("result Asset or AssetVariant authority is duplicated")
        seen_result_asset_ids.add(result_asset_id)
        seen_variant_ids.add(variant_id)
        result_asset_ids[case_id] = result_asset_id
        variant_by_case[case_id] = actual
    return variant_by_case, result_asset_ids


def _validated_pair_context(
    *,
    case_manifest: Sequence[Mapping[str, object]],
    source_entries: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    result_records: Sequence[Mapping[str, object]],
    gates: Sequence[Mapping[str, object]],
    structure_records: Sequence[Mapping[str, object]],
    manual_records: Sequence[Mapping[str, object]],
    image_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
    result_variant_bindings: Mapping[str, object],
) -> tuple[
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
    dict[str, Mapping[str, Any]],
]:
    authority = _execution_authority(execution_authority)
    cases = [
        validate_case_manifest_entry(item, execution_authority=authority) for item in case_manifest
    ]
    sources = [validate_source_manifest_entry(item) for item in source_entries]
    validate_ordered_case_manifest(
        case_manifest,
        source_entries=source_entries,
        execution_authority=authority,
    )
    validate_result_m3_gate_cross_graph(
        case_manifest=case_manifest,
        source_entries=source_entries,
        m4_records=m4_records,
        result_records=result_records,
        gates=gates,
        execution_authority=authority,
    )
    validate_decode_structure_evidence(
        structure_records,
        case_manifest=case_manifest,
        source_entries=source_entries,
        m4_records=m4_records,
        execution_authority=authority,
    )
    validate_manual_review_evidence(
        manual_records,
        case_manifest=case_manifest,
        source_entries=source_entries,
        m4_records=m4_records,
        execution_authority=authority,
    )
    variant_by_case, result_asset_ids = _validate_result_variant_bindings(
        cases=cases,
        m4_records=[cast(Mapping[str, Any], item) for item in m4_records],
        result_variant_bindings=result_variant_bindings,
    )
    case_ids = set(result_asset_ids)
    validate_image_authority_evidence(
        image_records,
        source_entries=source_entries,
        case_manifest=case_manifest,
        m4_records=m4_records,
        execution_authority=authority,
        result_asset_ids=result_asset_ids,
    )
    images = [_validate_image_record_shape(record) for record in image_records]
    result_image_by_case = {
        cast(str, record["case_id"]): record
        for record in images
        if record["authority_role"] == "RESULT"
    }
    if set(result_image_by_case) != case_ids:
        _fail("result image authority must cover exactly the 48 cases")
    manuals = [cast(Mapping[str, Any], item) for item in manual_records]
    manual_by_case = {cast(str, item["case_id"]): item for item in manuals}
    if set(manual_by_case) != case_ids:
        _fail("manual authority must cover exactly the 48 cases")
    structures = [cast(Mapping[str, Any], item) for item in structure_records]
    parsed_results = [validate_result_m3_record(item) for item in result_records]
    parsed_gates = [cast(Mapping[str, Any], item) for item in gates]
    return (
        sources,
        cases,
        parsed_results,
        parsed_gates,
        structures,
        [cast(Mapping[str, Any], item) for item in m4_records],
        manual_by_case,
        result_image_by_case,
        variant_by_case,
    )


def _expected_pair_side(
    *,
    case_index: int,
    expected_direction: str,
    cases: Sequence[Mapping[str, Any]],
    m4_records: Sequence[Mapping[str, Any]],
    result_records: Sequence[Mapping[str, Any]],
    gates: Sequence[Mapping[str, Any]],
    structures: Sequence[Mapping[str, Any]],
    manual_by_case: Mapping[str, Mapping[str, Any]],
    result_image_by_case: Mapping[str, Mapping[str, Any]],
    variant_by_case: Mapping[str, Mapping[str, Any]],
) -> dict[str, JsonValue]:
    case = cases[case_index]
    case_id = cast(str, case["case_id"])
    first_m4 = m4_records[case_index * 2]
    triple = result_records[case_index * 3 : case_index * 3 + 3]
    gate = gates[case_index]
    structure = structures[case_index]
    manual = manual_by_case[case_id]
    image = result_image_by_case[case_id]
    variant = variant_by_case[case_id]
    if (
        case["direction"] != expected_direction
        or structure["result_image_record_id"] != image["image_record_id"]
        or variant["source_asset_id"] != case["source_asset_id"]
        or variant["source_asset_sha256"] != case["source_asset_sha256"]
        or variant["result_asset_id"] != image["deterministic_result_asset_id"]
        or variant["result_asset_sha256"] != first_m4["result_sha256"]
        or variant["case_specification_digest"] != case["case_specification_digest"]
        or variant["asset_variant_type"] != VARIANT_TYPE
    ):
        _fail("pair side case/image/variant authority binding is invalid")
    result_m3_digests: list[JsonValue] = [cast(str, record["record_digest"]) for record in triple]
    repeat_gate_results: list[JsonValue] = [
        _bool(record["repeat_gate_passed"], "ResultM3 repeat Gate") for record in triple
    ]
    evaluation = cast(Mapping[str, Any], gate["gate_evaluation"])
    measurement_gate = _bool(evaluation["measurement_gate_passed"], "measurement gate")
    structure_gate = _bool(structure["structure_gate_passed"], "structure gate")
    automated_gate = all(repeat_gate_results) and measurement_gate and structure_gate
    manual_gate = manual["verdict"] == "PASS"
    side_gate = automated_gate and manual_gate
    automated_payload: dict[str, JsonValue] = {
        "case_id": case_id,
        "case_specification_digest": cast(str, case["case_specification_digest"]),
        "result_m3_record_digests": result_m3_digests,
        "result_m3_repeat_gate_results": repeat_gate_results,
        "measurement_gate_record_digest": cast(str, gate["record_digest"]),
        "measurement_evaluation_state": cast(str, gate["measurement_evaluation_state"]),
        "measurement_gate_passed": measurement_gate,
        "decode_structure_record_digest": cast(str, structure["record_digest"]),
        "structure_gate_passed": structure_gate,
        "automated_gate_passed": automated_gate,
    }
    lineage_digest = mirror_demo_digest(
        VARIANT_LINEAGE_SCHEMA,
        {
            "variant_type": VARIANT_TYPE,
            "source_asset_id": case["source_asset_id"],
            "source_asset_sha256": case["source_asset_sha256"],
            "result_asset_id": variant["result_asset_id"],
            "result_asset_sha256": first_m4["result_sha256"],
        },
    )
    common: dict[str, JsonValue] = {
        "measurement_evaluation_state": cast(str, gate["measurement_evaluation_state"]),
        "case_id": case_id,
        "case_specification_digest": cast(str, case["case_specification_digest"]),
        "requested_direction": expected_direction,
        "requested_magnitude_ppm": cast(int, case["magnitude_ppm"]),
        "result_output_id": cast(str, first_m4["result_output_id"]),
        "result_asset_id": cast(str, variant["result_asset_id"]),
        "result_asset_sha256": cast(str, first_m4["result_sha256"]),
        "result_asset_byte_size": cast(int, first_m4["result_byte_size"]),
        "result_asset_mime_type": cast(str, first_m4["result_mime_type"]),
        "result_asset_width": cast(int, first_m4["result_width"]),
        "result_asset_height": cast(int, first_m4["result_height"]),
        "asset_variant_id": cast(str, variant["asset_variant_id"]),
        "asset_variant_type": cast(str, variant["asset_variant_type"]),
        "lineage_digest": lineage_digest,
        "image_record_id": cast(str, image["image_record_id"]),
        "image_record_digest": cast(str, image["image_record_digest"]),
        "result_m3_record_digests": result_m3_digests,
        "measurement_gate_record_digest": cast(str, gate["record_digest"]),
        "decode_structure_record_digest": cast(str, structure["record_digest"]),
        "manual_decision_digest": cast(str, manual["manual_decision_digest"]),
        "automated_gate_digest": mirror_demo_digest(AUTOMATED_SIDE_GATE_SCHEMA, automated_payload),
        "automated_gate_passed": automated_gate,
        "manual_gate_passed": manual_gate,
        "side_gate_passed": side_gate,
    }
    if gate["measurement_evaluation_state"] == "SUPPORTED_EVALUATED":
        measurements = cast(list[Mapping[str, Any]], gate["ordered_result_repeat_measurements"])
        measurement = measurements[0]
        quality = _side_quality_ppm(
            measurement["raw_max_control_drift_fixed18"], side_gate_passed=side_gate
        )
        return {
            "schema_version": EVALUATED_SIDE_SCHEMA,
            **common,
            "raw_signed_target_delta_fixed18": cast(
                str, measurement["raw_signed_target_delta_fixed18"]
            ),
            "raw_target_absolute_delta_fixed18": cast(
                str, measurement["raw_target_absolute_delta_fixed18"]
            ),
            "raw_max_control_drift_fixed18": cast(
                str, measurement["raw_max_control_drift_fixed18"]
            ),
            "measured_signed_delta_ppm": cast(int, measurement["measured_signed_delta_ppm"]),
            "drift_ppm": cast(int, measurement["drift_ppm"]),
            "side_quality_state": "COMPUTED" if side_gate else "NOT_COMPUTED_GATE_FAILED",
            "side_quality_component_ppm": quality,
        }
    if gate["measurement_evaluation_state"] != "UNSUPPORTED_EXPLICIT":
        _fail("pair side measurement evaluation state is invalid")
    unsupported_indexes = evaluation["unsupported_repeat_indexes"]
    unsupported_reasons = evaluation["ordered_unsupported_reasons"]
    if not isinstance(unsupported_indexes, list) or not isinstance(unsupported_reasons, list):
        _fail("unsupported pair side evidence must use ordered arrays")
    if automated_gate or side_gate:
        _fail("unsupported pair side cannot pass automated or side Gate")
    return {
        "schema_version": UNSUPPORTED_SIDE_SCHEMA,
        **common,
        "unsupported_repeat_indexes": cast(list[JsonValue], unsupported_indexes),
        "ordered_unsupported_reasons": cast(list[JsonValue], unsupported_reasons),
        "side_quality_state": "NOT_COMPUTED_GATE_FAILED",
        "side_quality_component_ppm": 0,
    }


def _pair_record_id(payload: Mapping[str, object]) -> str:
    left = cast(Mapping[str, object], payload["left"])
    right = cast(Mapping[str, object], payload["right"])
    preimage: dict[str, JsonValue] = {
        "source_authority_key": cast(str, payload["source_authority_key"]),
        "source_admission_event_id": cast(str, payload["source_admission_event_id"]),
        "source_asset_sha256": cast(str, payload["source_asset_sha256"]),
        "dimension_key": cast(str, payload["dimension_key"]),
        "priority_index": cast(int, payload["priority_index"]),
        "magnitude_ppm": cast(int, payload["magnitude_ppm"]),
        "left_case_id": cast(str, left["case_id"]),
        "right_case_id": cast(str, right["case_id"]),
        "screening_policy_digest": SCREENING_POLICY_DIGEST,
        "lock_policy_digest": EMPTY_LOCK_POLICY_DIGEST,
    }
    return mirror_demo_digest(PAIR_ID_DOMAIN, preimage)[:32]


def build_pair_screening_evidence(
    *,
    case_manifest: Sequence[Mapping[str, object]],
    source_entries: Sequence[Mapping[str, object]],
    m4_records: Sequence[Mapping[str, object]],
    result_records: Sequence[Mapping[str, object]],
    gates: Sequence[Mapping[str, object]],
    structure_records: Sequence[Mapping[str, object]],
    manual_records: Sequence[Mapping[str, object]],
    image_records: Sequence[Mapping[str, object]],
    execution_authority: Mapping[str, object],
    result_variant_bindings: Mapping[str, object],
) -> list[dict[str, JsonValue]]:
    """Derive the fixed 24 pair wrappers from complete typed case-side authority."""
    (
        sources,
        cases,
        parsed_results,
        parsed_gates,
        structures,
        parsed_m4,
        manual_by_case,
        result_image_by_case,
        variant_by_case,
    ) = _validated_pair_context(
        case_manifest=case_manifest,
        source_entries=source_entries,
        m4_records=m4_records,
        result_records=result_records,
        gates=gates,
        structure_records=structure_records,
        manual_records=manual_records,
        image_records=image_records,
        execution_authority=execution_authority,
        result_variant_bindings=result_variant_bindings,
    )
    records: list[dict[str, JsonValue]] = []
    for source_index, source in enumerate(sources):
        for dimension_index, dimension in enumerate(CASE_DIMENSIONS):
            for magnitude_index, magnitude in enumerate(CASE_MAGNITUDES):
                left_index = source_index * 12 + dimension_index * 4 + magnitude_index
                right_index = left_index + 2
                left = _expected_pair_side(
                    case_index=left_index,
                    expected_direction="DECREASE",
                    cases=cases,
                    m4_records=parsed_m4,
                    result_records=parsed_results,
                    gates=parsed_gates,
                    structures=structures,
                    manual_by_case=manual_by_case,
                    result_image_by_case=result_image_by_case,
                    variant_by_case=variant_by_case,
                )
                right = _expected_pair_side(
                    case_index=right_index,
                    expected_direction="INCREASE",
                    cases=cases,
                    m4_records=parsed_m4,
                    result_records=parsed_results,
                    gates=parsed_gates,
                    structures=structures,
                    manual_by_case=manual_by_case,
                    result_image_by_case=result_image_by_case,
                    variant_by_case=variant_by_case,
                )
                pair_side_gate = bool(left["side_gate_passed"]) and bool(right["side_gate_passed"])
                payload: dict[str, JsonValue] = {
                    "source_ordinal": source_index + 1,
                    "source_authority_key": cast(str, source["source_authority_key"]),
                    "source_admission_event_id": cast(str, source["source_admission_event_id"]),
                    "source_asset_id": cast(str, source["source_asset_id"]),
                    "source_asset_sha256": cast(str, source["source_asset_sha256"]),
                    "dimension_key": dimension,
                    "priority_index": dimension_index + 1,
                    "magnitude_ppm": magnitude,
                    "screening_policy_digest": SCREENING_POLICY_DIGEST,
                    "left": left,
                    "right": right,
                    "same_source_gate_passed": True,
                    "opposed_direction_gate_passed": True,
                    "equal_magnitude_gate_passed": True,
                    "pair_side_gates_passed": pair_side_gate,
                    "empty_lock_policy_gate_passed": True,
                    "pair_quality_state": (
                        "COMPUTED" if pair_side_gate else "NOT_COMPUTED_GATE_FAILED"
                    ),
                    "pair_quality_ppm": (
                        min(
                            cast(int, left["side_quality_component_ppm"]),
                            cast(int, right["side_quality_component_ppm"]),
                        )
                        if pair_side_gate
                        else 0
                    ),
                    "lock_conclusion": "PASS_FOR_FROZEN_EMPTY_NEUTRAL_POLICY_ONLY",
                    "lock_policy_digest": EMPTY_LOCK_POLICY_DIGEST,
                    "pair_gate_passed": pair_side_gate,
                }
                payload["pair_record_id"] = _pair_record_id(payload)
                records.append(
                    {
                        "schema_version": PAIR_SCHEMA,
                        "pair_screening_record_payload": payload,
                        "pair_screening_record_digest": mirror_demo_digest(PAIR_SCHEMA, payload),
                    }
                )
    return records


def validate_pair_screening_evidence(
    records: Sequence[Mapping[str, object]],
    **context: object,
) -> list[Mapping[str, Any]]:
    """Replay all pair wrappers; caller fields never choose Gate or quality state."""
    expected = build_pair_screening_evidence(**cast(dict[str, Any], context))
    if len(records) != 24:
        _fail("pair screening evidence must contain exactly 24 ordered records")
    parsed: list[Mapping[str, Any]] = []
    for record, expected_record in zip(records, expected, strict=True):
        wrapper = _exact(record, _PAIR_WRAPPER_KEYS, "pair screening wrapper")
        if wrapper["schema_version"] != PAIR_SCHEMA:
            _fail("pair screening wrapper schema is invalid")
        _digest(wrapper["pair_screening_record_digest"], "pair screening record digest")
        payload = _exact(
            wrapper["pair_screening_record_payload"], _PAIR_PAYLOAD_KEYS, "pair payload"
        )
        _id(payload["pair_record_id"], "pair record ID")
        _digest(payload["screening_policy_digest"], "pair screening policy digest")
        _digest(payload["lock_policy_digest"], "pair lock policy digest")
        for side_name in ("left", "right"):
            side = payload[side_name]
            if not isinstance(side, Mapping):
                _fail("pair side must be an object")
            schema = side.get("schema_version")
            keys = (
                _EVALUATED_SIDE_KEYS if schema == EVALUATED_SIDE_SCHEMA else _UNSUPPORTED_SIDE_KEYS
            )
            _exact(side, keys, f"{side_name} pair side")
            if schema not in {EVALUATED_SIDE_SCHEMA, UNSUPPORTED_SIDE_SCHEMA}:
                _fail("pair side schema is invalid")
        _require_canonical_match(wrapper, expected_record, "pair screening record")
        parsed.append(wrapper)
    return parsed


def build_dimension_eligibility_evidence(
    pair_records: Sequence[Mapping[str, object]], *, exact_sha_gate_passed: bool
) -> list[dict[str, JsonValue]]:
    """Derive three fixed-priority dimension records from 24 pair wrappers."""
    if type(exact_sha_gate_passed) is not bool:
        _fail("global exact-SHA Gate must be a boolean")
    if len(pair_records) != 24:
        _fail("dimension eligibility requires exactly 24 pair records")
    records: list[dict[str, JsonValue]] = []
    for dimension_index, dimension in enumerate(CASE_DIMENSIONS):
        pair_digests: list[JsonValue] = []
        side_digests: list[JsonValue] = []
        side_entries: list[JsonValue] = []
        pair_entries: list[JsonValue] = []
        all_side = True
        all_pair = True
        all_manual = True
        all_lock = True
        for source_index in range(4):
            for magnitude_index, magnitude in enumerate(CASE_MAGNITUDES):
                pair_index = source_index * 6 + dimension_index * 2 + magnitude_index
                wrapper = _exact(
                    pair_records[pair_index], _PAIR_WRAPPER_KEYS, "dimension pair wrapper"
                )
                payload = _exact(
                    wrapper["pair_screening_record_payload"],
                    _PAIR_PAYLOAD_KEYS,
                    "dimension pair payload",
                )
                left = cast(Mapping[str, Any], payload["left"])
                right = cast(Mapping[str, Any], payload["right"])
                pair_digests.append(cast(str, wrapper["pair_screening_record_digest"]))
                for side_name, side in (("LEFT", left), ("RIGHT", right)):
                    automated = _bool(side["automated_gate_passed"], "automated side Gate")
                    manual = _bool(side["manual_gate_passed"], "manual side Gate")
                    side_gate = _bool(side["side_gate_passed"], "side Gate")
                    side_digests.append(cast(str, side["automated_gate_digest"]))
                    side_entries.append(
                        {
                            "schema_version": DIMENSION_SIDE_GATE_SCHEMA,
                            "source_ordinal": source_index + 1,
                            "magnitude_ppm": magnitude,
                            "side": side_name,
                            "case_id": cast(str, side["case_id"]),
                            "automated_gate_digest": cast(str, side["automated_gate_digest"]),
                            "manual_decision_digest": cast(str, side["manual_decision_digest"]),
                            "automated_gate_passed": automated,
                            "manual_gate_passed": manual,
                            "side_gate_passed": side_gate,
                        }
                    )
                    all_side = all_side and side_gate
                    all_manual = all_manual and manual
                pair_gate = _bool(payload["pair_gate_passed"], "pair Gate")
                pair_entries.append(
                    {
                        "schema_version": DIMENSION_PAIR_GATE_SCHEMA,
                        "source_ordinal": source_index + 1,
                        "magnitude_ppm": magnitude,
                        "pair_record_id": cast(str, payload["pair_record_id"]),
                        "pair_screening_record_digest": cast(
                            str, wrapper["pair_screening_record_digest"]
                        ),
                        "pair_gate_passed": pair_gate,
                    }
                )
                all_pair = all_pair and pair_gate
                all_lock = all_lock and _bool(
                    payload["empty_lock_policy_gate_passed"], "empty lock policy Gate"
                )
        eligible = all_side and all_pair and all_manual and exact_sha_gate_passed and all_lock
        failure_bools = (
            all_side,
            all_pair,
            all_manual,
            exact_sha_gate_passed,
            all_lock,
        )
        failure_reasons: list[JsonValue] = [
            reason
            for reason, passed in zip(_FAILURE_REASONS, failure_bools, strict=True)
            if not passed
        ]
        record: dict[str, JsonValue] = {
            "schema_version": DIMENSION_SCHEMA,
            "dimension_key": dimension,
            "priority_index": dimension_index + 1,
            "ordered_pair_screening_record_digests": pair_digests,
            "ordered_side_automated_gate_digests": side_digests,
            "sixteen_side_gate_digest": mirror_demo_digest(
                SIXTEEN_SIDE_GATE_SCHEMA,
                {
                    "dimension_key": dimension,
                    "priority_index": dimension_index + 1,
                    "ordered_side_gate_entries": side_entries,
                },
            ),
            "eight_pair_gate_digest": mirror_demo_digest(
                EIGHT_PAIR_GATE_SCHEMA,
                {
                    "dimension_key": dimension,
                    "priority_index": dimension_index + 1,
                    "ordered_pair_gate_entries": pair_entries,
                },
            ),
            "all_sixteen_side_gates_passed": all_side,
            "all_eight_pair_gates_passed": all_pair,
            "all_manual_gates_passed": all_manual,
            "global_exact_sha_gate_passed": exact_sha_gate_passed,
            "empty_lock_policy_gate_passed": all_lock,
            "eligible": eligible,
            "failure_reasons": failure_reasons,
        }
        record["record_digest"] = _digest_for(DIMENSION_SCHEMA, record, {"schema_version"})
        records.append(record)
    return records


def validate_dimension_eligibility_evidence(
    records: Sequence[Mapping[str, object]],
    *,
    pair_records: Sequence[Mapping[str, object]],
    exact_sha_gate_passed: bool,
) -> list[Mapping[str, Any]]:
    expected = build_dimension_eligibility_evidence(
        pair_records, exact_sha_gate_passed=exact_sha_gate_passed
    )
    if len(records) != 3:
        _fail("dimension eligibility must contain exactly three ordered records")
    parsed: list[Mapping[str, Any]] = []
    for record, expected_record in zip(records, expected, strict=True):
        item = _exact(record, _DIMENSION_KEYS, "dimension eligibility record")
        if item["schema_version"] != DIMENSION_SCHEMA:
            _fail("dimension eligibility schema is invalid")
        _digest(item["record_digest"], "dimension eligibility record digest")
        if not isinstance(item["failure_reasons"], list):
            _fail("dimension failure reasons must be an ordered array")
        _require_canonical_match(item, expected_record, "dimension eligibility record")
        parsed.append(item)
    return parsed


def build_selection_trace(
    dimension_records: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, JsonValue]], list[str], list[str], str]:
    """Derive the unique one of eight fixed-priority selection states."""
    if len(dimension_records) != 3:
        _fail("selection requires exactly three dimension records")
    eligible_flags: list[bool] = []
    parsed_dimensions: list[Mapping[str, Any]] = []
    for index, dimension_record in enumerate(dimension_records):
        item = _exact(dimension_record, _DIMENSION_KEYS, "selection dimension record")
        if (
            item["schema_version"] != DIMENSION_SCHEMA
            or item["dimension_key"] != CASE_DIMENSIONS[index]
            or item["priority_index"] != index + 1
        ):
            _fail("selection dimension order is invalid")
        _require_digest_match(DIMENSION_SCHEMA, item, "record_digest", {"schema_version"})
        parsed_dimensions.append(item)
        eligible_flags.append(_bool(item["eligible"], "dimension eligible"))
    eligible_count = sum(eligible_flags)
    eligible_keys = [
        dimension
        for dimension, eligible in zip(CASE_DIMENSIONS, eligible_flags, strict=True)
        if eligible
    ]
    selected_keys = eligible_keys[:2] if eligible_count >= 2 else []
    records: list[dict[str, JsonValue]] = []
    rank = 0
    for index, (dimension, dimension_record, eligible) in enumerate(
        zip(CASE_DIMENSIONS, parsed_dimensions, eligible_flags, strict=True), start=1
    ):
        if eligible:
            rank += 1
            eligible_rank = rank
        else:
            eligible_rank = 0
        selected = False
        slot = 0
        if not eligible:
            decision = "INELIGIBLE"
        elif eligible_count < 2:
            decision = "ELIGIBLE_NOT_SELECTED_INSUFFICIENT_SET"
        elif eligible_rank == 1:
            decision = "SELECTED_SLOT_1"
            selected = True
            slot = 1
        elif eligible_rank == 2:
            decision = "SELECTED_SLOT_2"
            selected = True
            slot = 2
        else:
            decision = "ELIGIBLE_NOT_SELECTED_CAPACITY"
        selection_record: dict[str, JsonValue] = {
            "schema_version": SELECTION_SCHEMA,
            "selection_step": index,
            "dimension_key": dimension,
            "priority_index": index,
            "dimension_eligibility_record_digest": cast(str, dimension_record["record_digest"]),
            "eligible": eligible,
            "eligible_rank": eligible_rank,
            "selection_decision": decision,
            "selection_slot": slot,
            "selected": selected,
        }
        selection_record["record_digest"] = _digest_for(
            SELECTION_SCHEMA, selection_record, {"schema_version"}
        )
        records.append(selection_record)
    status = "PASSED" if eligible_count >= 2 else "FAILED"
    return records, eligible_keys, selected_keys, status


def validate_selection_trace(
    records: Sequence[Mapping[str, object]],
    *,
    dimension_records: Sequence[Mapping[str, object]],
) -> tuple[list[str], list[str], str]:
    expected, eligible_keys, selected_keys, status = build_selection_trace(dimension_records)
    if len(records) != 3:
        _fail("selection trace must contain exactly three ordered records")
    for record, expected_record in zip(records, expected, strict=True):
        item = _exact(record, _SELECTION_KEYS, "selection trace record")
        if item["schema_version"] != SELECTION_SCHEMA:
            _fail("selection trace schema is invalid")
        _digest(item["record_digest"], "selection trace record digest")
        _require_canonical_match(item, expected_record, "selection trace record")
    return eligible_keys, selected_keys, status


def build_selected_pair_manifest(
    pair_records: Sequence[Mapping[str, object]], *, selected_dimension_keys: Sequence[str]
) -> tuple[list[dict[str, JsonValue]], str | None]:
    if len(pair_records) != 24:
        _fail("selected manifest requires exactly 24 pair records")
    if list(selected_dimension_keys) == []:
        return [], None
    if (
        len(selected_dimension_keys) != 2
        or len(set(selected_dimension_keys)) != 2
        or any(dimension not in CASE_DIMENSIONS for dimension in selected_dimension_keys)
    ):
        _fail("selected dimension keys must be exactly two frozen candidates")
    records: list[dict[str, JsonValue]] = []
    for slot, dimension in enumerate(selected_dimension_keys, start=1):
        dimension_index = CASE_DIMENSIONS.index(dimension)
        for source_index in range(4):
            for magnitude_index, magnitude in enumerate(CASE_MAGNITUDES):
                pair_index = source_index * 6 + dimension_index * 2 + magnitude_index
                wrapper = _exact(
                    pair_records[pair_index], _PAIR_WRAPPER_KEYS, "selected pair wrapper"
                )
                payload = _exact(
                    wrapper["pair_screening_record_payload"],
                    _PAIR_PAYLOAD_KEYS,
                    "selected pair payload",
                )
                if _bool(payload["pair_gate_passed"], "selected pair Gate") is not True:
                    _fail("selected manifest cannot project a failed pair")
                left = cast(Mapping[str, Any], payload["left"])
                right = cast(Mapping[str, Any], payload["right"])
                record: dict[str, JsonValue] = {
                    "schema_version": SELECTED_PAIR_SCHEMA,
                    "selected_pair_ordinal": len(records) + 1,
                    "selected_dimension_slot": slot,
                    "dimension_key": dimension,
                    "priority_index": dimension_index + 1,
                    "source_ordinal": source_index + 1,
                    "source_authority_key": cast(str, payload["source_authority_key"]),
                    "source_admission_event_id": cast(str, payload["source_admission_event_id"]),
                    "magnitude_ppm": magnitude,
                    "pair_record_id": cast(str, payload["pair_record_id"]),
                    "pair_screening_record_digest": cast(
                        str, wrapper["pair_screening_record_digest"]
                    ),
                    "left_case_id": cast(str, left["case_id"]),
                    "left_result_asset_id": cast(str, left["result_asset_id"]),
                    "left_result_asset_sha256": cast(str, left["result_asset_sha256"]),
                    "left_asset_variant_id": cast(str, left["asset_variant_id"]),
                    "right_case_id": cast(str, right["case_id"]),
                    "right_result_asset_id": cast(str, right["result_asset_id"]),
                    "right_result_asset_sha256": cast(str, right["result_asset_sha256"]),
                    "right_asset_variant_id": cast(str, right["asset_variant_id"]),
                }
                record["entry_digest"] = _digest_for(
                    SELECTED_PAIR_SCHEMA, record, {"schema_version"}
                )
                records.append(record)
    return records, _sequence_digest(SELECTED_PAIR_MANIFEST_SCHEMA, records)


def validate_selected_pair_manifest(
    records: Sequence[Mapping[str, object]],
    *,
    pair_records: Sequence[Mapping[str, object]],
    selected_dimension_keys: Sequence[str],
) -> str | None:
    expected, digest = build_selected_pair_manifest(
        pair_records, selected_dimension_keys=selected_dimension_keys
    )
    if len(records) != len(expected):
        _fail("selected pair manifest cardinality is invalid")
    for record, expected_record in zip(records, expected, strict=True):
        item = _exact(record, _SELECTED_PAIR_KEYS, "selected pair manifest entry")
        if item["schema_version"] != SELECTED_PAIR_SCHEMA:
            _fail("selected pair manifest entry schema is invalid")
        _require_digest_match(SELECTED_PAIR_SCHEMA, item, "entry_digest", {"schema_version"})
        _require_canonical_match(item, expected_record, "selected pair manifest entry")
    return digest


def validate_network_runtime_boundary(value: object) -> Mapping[str, Any]:
    boundary = _exact(value, _NETWORK_BOUNDARY_KEYS, "network and runtime boundary")
    if (
        boundary["schema_version"] != NETWORK_BOUNDARY_SCHEMA
        or boundary["public_internet_egress"] != "DENIED"
        or _bool(
            boundary["localhost_and_docker_internal_network"],
            "localhost and Docker internal network",
        )
        is not True
        or _bool(boundary["proxy_environment_present"], "proxy environment present") is not False
        or type(boundary["production_provider_calls"]) is not int
        or boundary["production_provider_calls"] != 0
        or type(boundary["runtime_generation_calls"]) is not int
        or boundary["runtime_generation_calls"] != 0
    ):
        _fail("network and runtime boundary is invalid")
    _digest(boundary["boundary_receipt_digest"], "network boundary receipt digest")
    return boundary


def validate_schema_and_policy_binding(
    value: object, *, measurement_execution_config: Mapping[str, object] | None = None
) -> Mapping[str, Any]:
    binding = _exact(value, _BINDING_KEYS, "schema and policy binding")
    if binding["schema_version"] != SCHEMA_POLICY_SCHEMA:
        _fail("schema and policy binding schema is invalid")
    expected = {
        "runtime_manifest_digest": RUNTIME_MANIFEST_DIGEST,
        "vision_model_manifest_digest": VISION_MODEL_MANIFEST_DIGEST,
        "topology_digest": TOPOLOGY_DIGEST,
        "measurement_config_digest": MEASUREMENT_CONFIG_DIGEST,
        "measurement_quality_config_digest": QUALITY_CONFIG_DIGEST,
        "measurement_quality_manifest_content_digest": QUALITY_MANIFEST_DIGEST,
        "confidence_kind": CONFIDENCE_KIND,
        "reliability_kind": RELIABILITY_KIND,
    }
    if any(binding[key] != expected_value for key, expected_value in expected.items()):
        _fail("schema and policy binding differs from accepted manifest")
    if binding["screening_policy_digest"] != SCREENING_POLICY_DIGEST:
        _fail("schema and policy screening root is not accepted Revision 9 authority")
    for key in (
        "source_manifest_digest",
        "case_manifest_digest",
        "manual_review_policy_digest",
        "duplicate_policy_digest",
        "phash_implementation_digest",
    ):
        _digest(binding[key], key)
    config = binding["measurement_execution_config"]
    if not isinstance(config, Mapping) or not config:
        _fail("schema and policy binding requires the exact measurement execution config")
    try:
        require_replayed_measurement_config_digest(config, binding["measurement_config_digest"])
    except MeasurementQualityError as error:
        raise D02AuthorityError("schema and policy measurement config does not replay") from error
    if (
        measurement_execution_config is not None
        and binding["measurement_execution_config"] != measurement_execution_config
    ):
        _fail("schema and policy config payload differs")
    return binding


def validate_complete_source_graph_packets(
    packets: Sequence[Mapping[str, object]],
    *,
    source_entries: Sequence[Mapping[str, object]],
    source_records: Sequence[Mapping[str, object]],
) -> str:
    """Require four full facts/identity/source/SourceM3 packets at report admission."""
    if len(packets) != 4 or len(source_records) != 12:
        _fail("complete source authority requires four packets and 12 SourceM3 records")
    manifest_digest = digest_source_manifest(source_entries)
    for index, packet_raw in enumerate(packets):
        packet = _exact(packet_raw, _SOURCE_GRAPH_PACKET_KEYS, "source graph packet")
        source_entry = packet["source_entry"]
        packet_records = packet["source_records"]
        if not isinstance(source_entry, Mapping) or not isinstance(packet_records, list):
            _fail("source graph packet entry or records are invalid")
        if len(packet_records) != 3:
            _fail("source graph packet must contain three SourceM3 records")
        if packet["source_manifest_digest"] != manifest_digest:
            _fail("source graph packet manifest digest is stale")
        _require_canonical_match(
            source_entry, source_entries[index], "source graph packet source entry"
        )
        report_records = source_records[index * 3 : index * 3 + 3]
        _require_canonical_match(
            packet_records, report_records, "source graph packet SourceM3 records"
        )
        if not isinstance(packet["facts"], Mapping) or not isinstance(
            packet["identity_row"], Mapping
        ):
            _fail("source graph facts and identity must be objects")
        validate_complete_source_graph(
            facts=cast(Mapping[str, object], packet["facts"]),
            identity_row=cast(Mapping[str, object], packet["identity_row"]),
            source_entry=source_entry,
            source_manifest_digest=manifest_digest,
            source_records=packet_records,
        )
    return manifest_digest


def _report_execution_authority(row: Mapping[str, object]) -> dict[str, object]:
    return {
        key: row[key]
        for key in (
            "screening_policy_digest",
            "runtime_manifest_digest",
            "vision_model_manifest_digest",
            "topology_digest",
            "measurement_config_digest",
            "manual_review_policy_digest",
            "duplicate_policy_digest",
            "phash_implementation_digest",
        )
    }


def _report_group_array(
    payload: Mapping[str, object], key: str, expected_count: int
) -> list[Mapping[str, object]]:
    value = payload[key]
    if not isinstance(value, list) or len(value) != expected_count:
        _fail(f"report {key} cardinality is invalid")
    if any(not isinstance(item, Mapping) for item in value):
        _fail(f"report {key} must contain only objects")
    return cast(list[Mapping[str, object]], value)


def _validate_report_semantics(
    row: Mapping[str, Any],
    *,
    source_graph_packets: Sequence[Mapping[str, object]],
    result_variant_bindings: Mapping[str, object],
) -> None:
    payload = _validate_report_payload(row["report_payload"])
    authority = _execution_authority(_report_execution_authority(row))
    binding = validate_schema_and_policy_binding(payload["schema_and_policy"])
    for key in _EXECUTION_AUTHORITY_KEYS:
        if binding[key] != authority[key]:
            _fail("report schema/policy group differs from row execution authority")
    source_entries = _report_group_array(payload, "ordered_source_manifest", 4)
    source_records = _report_group_array(payload, "source_m3_repeat_evidence", 12)
    source_manifest_digest = validate_complete_source_graph_packets(
        source_graph_packets,
        source_entries=source_entries,
        source_records=source_records,
    )
    if (
        row["source_manifest_digest"] != source_manifest_digest
        or binding["source_manifest_digest"] != source_manifest_digest
    ):
        _fail("report source manifest authority does not replay")
    cases = _report_group_array(payload, "ordered_case_manifest", 48)
    case_manifest_digest = validate_ordered_case_manifest(
        cases,
        source_entries=source_entries,
        execution_authority=authority,
    )
    if (
        row["case_manifest_digest"] != case_manifest_digest
        or binding["case_manifest_digest"] != case_manifest_digest
    ):
        _fail("report case manifest authority does not replay")
    m4_records = _report_group_array(payload, "m4_repeat_evidence", 96)
    result_records = _report_group_array(payload, "result_m3_repeat_evidence", 144)
    gates = _report_group_array(payload, "measurement_gate_evidence", 48)
    structures = _report_group_array(payload, "decode_structure_immutability_evidence", 48)
    manuals = _report_group_array(payload, "manual_review_evidence", 48)
    validate_result_m3_gate_cross_graph(
        case_manifest=cases,
        source_entries=source_entries,
        m4_records=m4_records,
        result_records=result_records,
        gates=gates,
        execution_authority=authority,
    )
    validate_decode_structure_evidence(
        structures,
        case_manifest=cases,
        source_entries=source_entries,
        m4_records=m4_records,
        execution_authority=authority,
    )
    validate_manual_review_evidence(
        manuals,
        case_manifest=cases,
        source_entries=source_entries,
        m4_records=m4_records,
        execution_authority=authority,
    )
    _, result_asset_ids = _validate_result_variant_bindings(
        cases=[cast(Mapping[str, Any], item) for item in cases],
        m4_records=[cast(Mapping[str, Any], item) for item in m4_records],
        result_variant_bindings=result_variant_bindings,
    )
    exact_duplicate = validate_exact_duplicate_evidence(
        payload["exact_duplicate_evidence"],
        source_entries=source_entries,
        case_manifest=cases,
        m4_records=m4_records,
        execution_authority=authority,
        result_asset_ids=result_asset_ids,
    )
    image_records = exact_duplicate["image_records"]
    if not isinstance(image_records, list):
        _fail("report exact duplicate image records must be an array")
    validate_phash_observation_evidence(
        payload["phash_observation_evidence"],
        image_records=cast(list[Mapping[str, object]], image_records),
        execution_authority=authority,
    )
    pair_records = _report_group_array(payload, "pair_quality_evidence", 24)
    validate_pair_screening_evidence(
        pair_records,
        case_manifest=cases,
        source_entries=source_entries,
        m4_records=m4_records,
        result_records=result_records,
        gates=gates,
        structure_records=structures,
        manual_records=manuals,
        image_records=cast(list[Mapping[str, object]], image_records),
        execution_authority=authority,
        result_variant_bindings=result_variant_bindings,
    )
    exact_sha_gate_passed = _bool(exact_duplicate["exact_sha_gate_passed"], "report exact-SHA Gate")
    dimension_records = _report_group_array(payload, "dimension_eligibility", 3)
    validate_dimension_eligibility_evidence(
        dimension_records,
        pair_records=pair_records,
        exact_sha_gate_passed=exact_sha_gate_passed,
    )
    selection_records = _report_group_array(payload, "fixed_priority_selection_trace", 3)
    eligible_keys, selected_keys, status = validate_selection_trace(
        selection_records, dimension_records=dimension_records
    )
    selected_manifest_raw = payload["selected_pair_manifest"]
    if not isinstance(selected_manifest_raw, list) or any(
        not isinstance(item, Mapping) for item in selected_manifest_raw
    ):
        _fail("selected pair manifest must be an array of objects")
    selected_manifest = cast(list[Mapping[str, object]], selected_manifest_raw)
    selected_manifest_digest = validate_selected_pair_manifest(
        selected_manifest,
        pair_records=pair_records,
        selected_dimension_keys=selected_keys,
    )
    validate_network_runtime_boundary(payload["network_and_runtime_boundary"])
    expected_counts = {
        "source_count": 4,
        "case_count": 48,
        "source_m3_repeat_count": 12,
        "m4_execution_count": 96,
        "result_m3_repeat_count": 144,
        "manual_decision_count": 48,
        "exact_sha_record_count": 52,
        "phash_comparison_count": 1326,
        "candidate_pair_count": 24,
        "selected_pair_count": 16 if status == "PASSED" else 0,
        "selected_result_side_count": 32 if status == "PASSED" else 0,
    }
    for key, expected in expected_counts.items():
        if type(row[key]) is not int or row[key] != expected:
            _fail("report fixed counts do not replay")
    if (
        row["status"] != status
        or row["eligible_dimension_keys"] != eligible_keys
        or row["selected_dimension_keys"] != selected_keys
        or row["selected_pair_manifest_digest"] != selected_manifest_digest
    ):
        _fail("report status, selection, or selected manifest projection is invalid")


def build_report_row(
    fields: Mapping[str, object],
    *,
    source_graph_packets: Sequence[Mapping[str, object]],
    result_variant_bindings: Mapping[str, object],
) -> dict[str, JsonValue]:
    """Construct a report row only after the complete 16-group payload exists."""
    required = _REPORT_ROW_KEYS - {
        "id",
        "schema_version",
        "canonical_payload",
        "content_digest",
        "report_digest",
    }
    _exact(fields, required, "report row input")
    payload = fields["report_payload"]
    _validate_report_payload(payload)
    report_digest = mirror_demo_digest(REPORT_SCHEMA, payload)  # type: ignore[arg-type]
    row: dict[str, JsonValue] = {
        "schema_version": REPORT_SCHEMA,
        **cast(dict[str, JsonValue], dict(fields)),
        "report_digest": report_digest,
    }
    canonical = {
        key: item
        for key, item in row.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    if row["status"] == "FAILED":
        canonical.pop("selected_pair_manifest_digest")
    elif row["status"] != "PASSED" or not row["selected_pair_manifest_digest"]:
        _fail("report status and selected manifest nullability are invalid")
    content_digest = mirror_demo_digest(REPORT_SCHEMA, canonical)
    row["canonical_payload"] = canonical
    row["content_digest"] = content_digest
    row["id"] = mirror_demo_digest(
        "mirror.demo/D02PairScreeningReportId/v1", {"report_digest": report_digest}
    )[:32]
    validate_report_row(
        row,
        source_graph_packets=source_graph_packets,
        result_variant_bindings=result_variant_bindings,
    )
    return row


def validate_report_row(
    value: object,
    *,
    source_graph_packets: Sequence[Mapping[str, object]],
    result_variant_bindings: Mapping[str, object],
) -> Mapping[str, Any]:
    row = _exact(value, _REPORT_ROW_KEYS, "pair screening report row")
    if row["schema_version"] != REPORT_SCHEMA:
        _fail("report schema is invalid")
    _id(row["id"], "report id")
    _validate_report_payload(row["report_payload"])
    if row["report_digest"] != mirror_demo_digest(REPORT_SCHEMA, row["report_payload"]):
        _fail("report digest does not replay")
    expected_id = mirror_demo_digest(
        "mirror.demo/D02PairScreeningReportId/v1", {"report_digest": row["report_digest"]}
    )[:32]
    if row["id"] != expected_id:
        _fail("report id does not replay")
    _validate_report_semantics(
        row,
        source_graph_packets=source_graph_packets,
        result_variant_bindings=result_variant_bindings,
    )
    canonical = {
        key: item
        for key, item in row.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    if row["status"] == "FAILED":
        if row["selected_pair_manifest_digest"] is not None:
            _fail("failed report selected manifest must be null")
        canonical.pop("selected_pair_manifest_digest")
    elif row["status"] != "PASSED" or row["selected_pair_manifest_digest"] is None:
        _fail("passed report selected manifest must be non-null")
    if row["canonical_payload"] != canonical or row["content_digest"] != mirror_demo_digest(
        REPORT_SCHEMA, canonical
    ):
        _fail("report structured canonical payload does not replay")
    if row["report_digest"] == row["content_digest"]:
        _fail("report digest and row content digest must remain distinct")
    return row


def _validate_report_payload(value: object) -> Mapping[str, Any]:
    payload = _exact(value, set(REPORT_GROUPS), "report payload")
    if "report_id" in payload or "report_digest" in payload:
        _fail("report payload must not contain self-authority fields")
    empty_groups = [
        name
        for name, item in payload.items()
        if name != "selected_pair_manifest" and item in ([], {}, None)
    ]
    if empty_groups:
        _fail("report payload cannot contain empty evidence groups")
    return payload


def validate_complete_source_graph(
    *,
    facts: Mapping[str, object],
    identity_row: Mapping[str, object],
    source_entry: Mapping[str, object],
    source_manifest_digest: str,
    source_records: Sequence[Mapping[str, object]],
) -> None:
    """Validate the material source DAG edges that span individual envelopes."""
    verified_facts = validate_facts(facts)
    identity = validate_identity_row(identity_row, facts=verified_facts)
    if (
        identity["admission_sequence"] != 1
        or identity["admission_action"] != "ADMIT"
        or identity["supersedes_id"] is not None
    ):
        _fail("source graph requires a self-contained first ADMIT event")
    entry = validate_source_manifest_entry(source_entry)
    _digest(source_manifest_digest, "source manifest digest")
    observation = cast(Mapping[str, Any], verified_facts["source_measurement_observation"])
    subject = observation.get("subject")
    if not isinstance(subject, Mapping) or (
        subject.get("source_asset_id") != entry["source_asset_id"]
        or subject.get("source_asset_sha256") != entry["source_asset_sha256"]
        or subject.get("source_asset_sha256") != verified_facts["source_asset_sha256"]
    ):
        _fail("facts observation/source Asset authority equality is invalid")
    if (
        entry["source_authority_kind"] != identity["source_authority_kind"]
        or entry["source_authority_key"] != identity["source_authority_key"]
    ):
        _fail("source manifest/identity authority key equality is invalid")
    source_fact_entry_keys = (
        "source_output_id",
        "source_asset_sha256",
        "source_asset_byte_size",
        "source_asset_mime_type",
        "source_asset_width",
        "source_asset_height",
        "source_receipt_digest",
        "source_authority_digest",
        "source_qa_snapshot_digest",
        "source_landmark_digest",
        "source_measurement_digest",
        "source_provenance_digest",
        "source_fact_snapshot_digest",
        "adult_synthetic_attested",
        "original_formal_identity_id_status",
        "source_p2_candidate_manifest_content_digest",
        "dimension_authority_manifest_content_digest",
        "measurement_config_digest",
        "measurement_quality_config_digest",
        "measurement_quality_manifest_content_digest",
        "confidence_kind",
        "reliability_kind",
        "runtime_manifest_digest",
        "vision_model_manifest_digest",
        "topology_digest",
        "source_repeat_certification_digest",
    )
    fact_entry_values = dict(verified_facts)
    fact_entry_values["source_fact_snapshot_digest"] = digest_facts(verified_facts)
    fact_entry_values.update(
        cast(Mapping[str, object], verified_facts["raw_measurement_authority"])
    )
    if any(entry[key] != fact_entry_values[key] for key in source_fact_entry_keys):
        _fail("source manifest/facts scalar authority equality is invalid")
    raw_entries = cast(
        list[Mapping[str, Any]], verified_facts["raw_measurement_authority"]["ordered_entries"]
    )
    projection_entries = cast(
        list[Mapping[str, Any]], verified_facts["source_measurement_projection"]["ordered_entries"]
    )
    expected_supported = [
        {
            "schema_version": "mirror.demo/D02SupportedSourceMeasurement/v1",
            "dimension_key": raw_entry["dimension_key"],
            "raw_value_fixed18": raw_entry["raw_value_fixed18"],
            "raw_confidence_fixed18": raw_entry["raw_confidence_fixed18"],
            "raw_reliability_fixed18": raw_entry["raw_reliability_fixed18"],
            "value_ppm": projection_entry["value_ppm"],
            "confidence_ppm": projection_entry["confidence_ppm"],
            "reliability_ppm": projection_entry["reliability_ppm"],
            "unit": "FACE_HEIGHT_PPM",
        }
        for raw_entry, projection_entry in zip(raw_entries, projection_entries, strict=True)
    ]
    if entry["ordered_supported_measurements"] != expected_supported:
        _fail("source manifest supported-measurement projection differs from facts")
    identity_fact_keys = (
        "source_output_id",
        "source_receipt_digest",
        "source_authority_digest",
        "source_qa_snapshot_digest",
        "source_landmark_digest",
        "source_measurement_digest",
        "source_provenance_digest",
        "source_fact_snapshot",
        "source_fact_snapshot_digest",
        "source_measurement_projection",
        "source_measurement_projection_digest",
        "original_formal_identity_id_status",
        "adult_synthetic_attested",
        "source_authority_kind",
        "source_authority_key",
    )
    if any(
        identity_row[key]
        != (
            verified_facts
            if key == "source_fact_snapshot"
            else verified_facts.get(key, identity_row[key])
        )
        for key in identity_fact_keys
        if key not in {"source_authority_kind", "source_authority_key"}
    ):
        _fail("identity/facts complete authority equality is invalid")
    if (
        entry["source_measurement_digest"] != verified_facts["source_measurement_digest"]
        or entry["raw_measurement_authority_digest"]
        != verified_facts["raw_measurement_authority_digest"]
        or entry["source_measurement_projection_digest"]
        != verified_facts["source_measurement_projection_digest"]
    ):
        _fail("source manifest/facts authority equality is invalid")
    if (
        entry["source_asset_id"] != identity["formal_canonical_asset_id"]
        or entry["source_asset_sha256"] != identity["formal_canonical_asset_sha256"]
        or entry["source_asset_sha256"] != verified_facts["source_asset_sha256"]
        or entry["source_asset_byte_size"] != verified_facts["source_asset_byte_size"]
        or entry["source_asset_mime_type"] != verified_facts["source_asset_mime_type"]
        or entry["source_asset_width"] != verified_facts["source_asset_width"]
        or entry["source_asset_height"] != verified_facts["source_asset_height"]
        or entry["import_config_digest"] != identity["import_config_digest"]
        or entry["import_config_digest"] != IMPORT_CONFIG_DIGEST
    ):
        _fail("source manifest identity/Asset/config authority equality is invalid")
    if (
        entry["source_repeat_certification_digest"]
        != verified_facts["source_repeat_certification_digest"]
        or entry["source_admission_event_id"] != identity_row["id"]
        or entry["source_admission_content_digest"] != identity_row["content_digest"]
    ):
        _fail("source manifest identity/certificate equality is invalid")
    if len(source_records) != 3:
        _fail("source graph requires three source M3 records")
    seen_record_ids: set[object] = set()
    for index, record in enumerate(source_records, start=1):
        if (
            record.get("repeat_index") != index
            or record.get("source_m3_record_id") in seen_record_ids
        ):
            _fail("source graph SourceM3 repeat order or ID uniqueness is invalid")
        seen_record_ids.add(record.get("source_m3_record_id"))
        parsed_record = validate_source_m3_record(
            record,
            certificate=verified_facts["source_repeat_certification"],
            facts_observation=verified_facts["source_measurement_observation"],
            source_manifest_digest=source_manifest_digest,
        )
        if any(
            parsed_record[key] != entry[key]
            for key in (
                "source_ordinal",
                "source_authority_key",
                "source_admission_event_id",
                "source_asset_id",
                "source_asset_sha256",
            )
        ):
            _fail("source M3/source manifest authority equality is invalid")


def validate_identity_row(value: object, *, facts: Mapping[str, object]) -> Mapping[str, Any]:
    row = _exact(value, _IDENTITY_ROW_KEYS, "synthetic identity row")
    if (
        row["schema_version"] != IDENTITY_SCHEMA
        or row["importer_version"] != "demo-d02-identity-importer-v3"
        or row["import_config_digest"] != IMPORT_CONFIG_DIGEST
    ):
        _fail("identity v3 schema or importer authority is invalid")
    _validate_admission_event_shape(row)
    verified = validate_facts(facts)
    formal_null_keys = (
        "formal_synthetic_identity_id",
        "formal_accepted_qa_run_id",
        "formal_accepted_qa_snapshot_digest",
    )
    local_nonnull_keys = (
        "formal_canonical_asset_id",
        "formal_canonical_asset_sha256",
        "source_output_id",
        "source_receipt_digest",
        "source_authority_digest",
        "source_qa_snapshot_digest",
        "source_landmark_digest",
        "source_measurement_digest",
        "source_provenance_digest",
        "source_fact_snapshot",
        "source_fact_snapshot_digest",
        "source_measurement_projection",
        "source_measurement_projection_digest",
        "original_formal_identity_id_status",
        "adult_synthetic_attested",
        "source_authority_kind",
        "source_authority_key",
    )
    if any(row[key] is not None for key in formal_null_keys) or any(
        row[key] is None for key in local_nonnull_keys
    ):
        _fail("local v3 identity null matrix is invalid")
    observation = cast(Mapping[str, Any], verified["source_measurement_observation"])
    subject = observation.get("subject")
    expected_asset_id = derive_imported_asset_id(
        asset_role="synthetic",
        semantic_role="SOURCE",
        sha256=verified["source_asset_sha256"],
        byte_size=verified["source_asset_byte_size"],
        mime_type=verified["source_asset_mime_type"],
        width=verified["source_asset_width"],
        height=verified["source_asset_height"],
    )
    expected_source_key = derive_local_source_authority_key(
        source_output_id=row["source_output_id"],
        source_asset_id=row["formal_canonical_asset_id"],
        source_asset_sha256=row["formal_canonical_asset_sha256"],
        source_receipt_digest=row["source_receipt_digest"],
    )
    copied_fact_keys = (
        "source_output_id",
        "source_receipt_digest",
        "source_authority_digest",
        "source_qa_snapshot_digest",
        "source_landmark_digest",
        "source_measurement_digest",
        "source_provenance_digest",
        "source_measurement_projection",
        "source_measurement_projection_digest",
        "original_formal_identity_id_status",
        "adult_synthetic_attested",
    )
    if (
        any(row[key] != verified[key] for key in copied_fact_keys)
        or row["source_fact_snapshot"] != verified
        or row["source_fact_snapshot_digest"] != digest_facts(verified)
        or not isinstance(subject, Mapping)
        or subject.get("source_output_id") != row["source_output_id"]
        or subject.get("source_asset_id") != expected_asset_id
        or subject.get("source_asset_sha256") != verified["source_asset_sha256"]
        or row["formal_canonical_asset_id"] != expected_asset_id
        or row["formal_canonical_asset_sha256"] != verified["source_asset_sha256"]
        or row["source_authority_kind"] != LOCAL_SOURCE_AUTHORITY_KIND
        or row["source_authority_key"] != expected_source_key
        or row["original_formal_identity_id_status"] != UNKNOWN_FORMAL_IDENTITY_STATUS
        or row["adult_synthetic_attested"] is not True
    ):
        _fail("identity/facts canonical row equality is invalid")
    canonical = {
        key: item
        for key, item in row.items()
        if key not in {"id", "schema_version", "canonical_payload", "content_digest", "created_at"}
    }
    if row["canonical_payload"] != canonical or row["content_digest"] != mirror_demo_digest(
        IDENTITY_SCHEMA, canonical
    ):
        _fail("identity canonical payload does not replay")
    preimage: dict[str, JsonValue] = {
        "source_authority_kind": row["source_authority_kind"],
        "source_authority_key": row["source_authority_key"],
        "admission_sequence": row["admission_sequence"],
        "admission_action": row["admission_action"],
        "supersedes_id": row["supersedes_id"],
        "admission_config_digest": row["admission_config_digest"],
        "canonical_payload_digest": row["content_digest"],
    }
    if (
        row["id"]
        != mirror_demo_digest("mirror.demo/DemoSyntheticIdentityAdmissionEventId/v2", preimage)[:32]
    ):
        _fail("identity admission event id does not replay")
    return row


def validate_admit_revoke_copy(admit: Mapping[str, object], revoke: Mapping[str, object]) -> None:
    """Prove the frozen pure v3 evidence copy equality across ADMIT and REVOKE."""
    copied = (
        "formal_canonical_asset_id",
        "formal_canonical_asset_sha256",
        "source_output_id",
        "source_receipt_digest",
        "source_authority_digest",
        "source_qa_snapshot_digest",
        "source_landmark_digest",
        "source_measurement_digest",
        "source_provenance_digest",
        "source_fact_snapshot",
        "source_fact_snapshot_digest",
        "source_measurement_projection",
        "source_measurement_projection_digest",
        "original_formal_identity_id_status",
        "adult_synthetic_attested",
        "importer_version",
        "import_config_digest",
        "source_authority_kind",
        "source_authority_key",
    )
    parsed_admit = _exact(admit, _IDENTITY_ROW_KEYS, "admit/revoke identity row")
    parsed_revoke = _exact(revoke, _IDENTITY_ROW_KEYS, "admit/revoke identity row")
    admit_sequence, admit_action, _ = _validate_admission_event_shape(parsed_admit)
    revoke_sequence, revoke_action, revoke_supersedes_id = _validate_admission_event_shape(
        parsed_revoke
    )
    if admit_action != "ADMIT" or revoke_action != "REVOKE":
        _fail("admit/revoke action is invalid")
    if revoke_sequence != admit_sequence + 1 or revoke_supersedes_id != _id(
        parsed_admit["id"], "admit event ID"
    ):
        _fail("admit/revoke chain is not the immediate alternating successor")
    if any(admit[key] != revoke[key] for key in copied):
        _fail("admit/revoke v3 authority copy differs")
