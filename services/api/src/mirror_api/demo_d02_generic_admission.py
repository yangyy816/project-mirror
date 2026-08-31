"""Pure builders for the generic D02 acquisition admission boundary.

This module deliberately contains no ORM, filesystem, provider, or network
access.  Candidate evidence is provisional; formal source and identity rows
must be built from the completed four-source graph.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from mirror_api.demo_d02_r2_authority import (
    R2_SOURCE_AUTHORITY_KIND,
    R2_SOURCE_KEY_DOMAIN,
)
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest

SOURCE_SCHEMA: Final = "mirror.demo/D02GenericSourceAuthorityRecord/v1"
SOURCE_ID_SCHEMA: Final = "mirror.demo/D02GenericSourceAuthorityRecordId/v1"
PROVENANCE_SCHEMA: Final = "mirror.demo/D02GenericSourceManifestEntryProvenance/v1"
AUTHORITY_SCHEMA: Final = "mirror.demo/D02GenericSourceAuthority/v1"
IDENTITY_SCHEMA: Final = "mirror.demo/DemoSyntheticIdentity/v5"
IDENTITY_ID_SCHEMA: Final = "mirror.demo/DemoSyntheticIdentityAdmissionEventId/v4"
ADMISSION_SCHEMA: Final = "mirror.demo/D02GenericAdmission/v1"
ADMISSION_ID_SCHEMA: Final = "mirror.demo/D02GenericAdmissionId/v1"
REQUEST_SCHEMA: Final = "mirror.demo/D02GenericAdmissionRequest/v1"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[0-9a-f]{32}\Z")
_OUTPUT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class GenericAdmissionError(ValueError):
    """Raised when the generic D02 authority cannot be replayed."""


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise GenericAdmissionError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise GenericAdmissionError(f"{label} must be a 32-character ID")
    return value


def _output(value: object, label: str) -> str:
    if not isinstance(value, str) or _OUTPUT.fullmatch(value) is None:
        raise GenericAdmissionError(f"{label} must be an opaque output ID")
    return value


def _hash(schema: str, payload: Mapping[str, object]) -> str:
    return mirror_demo_digest(schema, cast(Mapping[str, JsonValue], payload))


@dataclass(frozen=True, slots=True)
class NormalizedAsset:
    asset_id: str
    sha256: str
    byte_size: int
    width: int
    height: int
    mime_type: str = "image/jpeg"

    def __post_init__(self) -> None:
        _id(self.asset_id, "Asset ID")
        _digest(self.sha256, "Asset SHA-256")
        if type(self.byte_size) is not int or self.byte_size <= 0:
            raise GenericAdmissionError("Asset byte size is invalid")
        if (
            type(self.width) is not int
            or self.width <= 0
            or type(self.height) is not int
            or self.height <= 0
        ):
            raise GenericAdmissionError("Asset dimensions are invalid")
        if self.mime_type != "image/jpeg":
            raise GenericAdmissionError("formal generic source Asset must be JPEG")


@dataclass(frozen=True, slots=True)
class GenericSourceInput:
    acquisition_run_id: str
    cohort_spec_id: str
    manifest_id: str
    manifest_acquisition_run_id: str
    manifest_cohort_spec_id: str
    manifest_content_digest: str
    manifest_ordered_candidate_ids: tuple[str, str, str, str]
    candidate_id: str
    candidate_acquisition_run_id: str
    candidate_cohort_spec_id: str
    candidate_content_digest: str
    position: int
    spec_content_digest: str
    generation_policy_digest: str
    source_output_id: str
    normalized_asset: NormalizedAsset
    formal_source_qa_digest: str
    candidate_m3_evidence_digest: str
    candidate_qa_evidence_digest: str
    formal_facts: Mapping[str, object]
    formal_measurement_projection: Mapping[str, object]
    formal_landmark_digest: str


def build_source_provenance(value: GenericSourceInput) -> dict[str, object]:
    """Build provenance for one ordered manifest member."""
    for identifier, label in (
        (value.acquisition_run_id, "acquisition run ID"),
        (value.cohort_spec_id, "cohort spec ID"),
        (value.manifest_id, "Manifest ID"),
        (value.manifest_acquisition_run_id, "Manifest run ID"),
        (value.manifest_cohort_spec_id, "Manifest spec ID"),
        (value.candidate_id, "Candidate ID"),
        (value.candidate_acquisition_run_id, "Candidate run ID"),
        (value.candidate_cohort_spec_id, "Candidate spec ID"),
    ):
        _id(identifier, label)
    for digest, label in (
        (value.manifest_content_digest, "Manifest content digest"),
        (value.candidate_content_digest, "Candidate content digest"),
        (value.spec_content_digest, "Spec content digest"),
        (value.generation_policy_digest, "Generation policy digest"),
    ):
        _digest(digest, label)
    _output(value.source_output_id, "source output ID")
    if type(value.position) is not int or not 1 <= value.position <= 4:
        raise GenericAdmissionError("manifest position must be 1..4")
    if (
        value.acquisition_run_id != value.manifest_acquisition_run_id
        or value.acquisition_run_id != value.candidate_acquisition_run_id
        or value.cohort_spec_id != value.manifest_cohort_spec_id
        or value.cohort_spec_id != value.candidate_cohort_spec_id
    ):
        raise GenericAdmissionError("Candidate, Manifest, run, and spec must match")
    if (
        len(value.manifest_ordered_candidate_ids) != 4
        or len(set(value.manifest_ordered_candidate_ids)) != 4
        or value.manifest_ordered_candidate_ids[value.position - 1] != value.candidate_id
    ):
        raise GenericAdmissionError("Candidate does not occupy the declared Manifest position")
    payload = {
        "acquisition_run_id": value.acquisition_run_id,
        "cohort_spec_id": value.cohort_spec_id,
        "manifest_id": value.manifest_id,
        "manifest_content_digest": value.manifest_content_digest,
        "candidate_id": value.candidate_id,
        "candidate_content_digest": value.candidate_content_digest,
        "position": value.position,
        "spec_content_digest": value.spec_content_digest,
        "generation_policy_digest": value.generation_policy_digest,
        "source_output_id": value.source_output_id,
        "asset_id": value.normalized_asset.asset_id,
        "asset_sha256": value.normalized_asset.sha256,
        "asset_byte_size": value.normalized_asset.byte_size,
        "asset_mime_type": value.normalized_asset.mime_type,
        "asset_width": value.normalized_asset.width,
        "asset_height": value.normalized_asset.height,
    }
    return {
        "schema_version": PROVENANCE_SCHEMA,
        **payload,
        "content_digest": _hash(PROVENANCE_SCHEMA, payload),
    }


def build_source_authority(value: GenericSourceInput) -> dict[str, object]:
    provenance = build_source_provenance(value)
    formal_qa = _digest(value.formal_source_qa_digest, "formal source QA digest")
    for candidate_digest, label in (
        (value.candidate_m3_evidence_digest, "candidate M3 evidence digest"),
        (value.candidate_qa_evidence_digest, "candidate QA evidence digest"),
    ):
        if formal_qa == _digest(candidate_digest, label):
            raise GenericAdmissionError("formal source QA must not reuse provisional candidate QA")
    authority_payload = {
        "manifest_id": value.manifest_id,
        "manifest_content_digest": value.manifest_content_digest,
        "candidate_id": value.candidate_id,
        "candidate_content_digest": value.candidate_content_digest,
        "position": value.position,
        "spec_content_digest": value.spec_content_digest,
        "generation_policy_digest": value.generation_policy_digest,
        "provenance_digest": provenance["content_digest"],
        "formal_source_qa_digest": formal_qa,
        "asset_id": value.normalized_asset.asset_id,
        "asset_sha256": value.normalized_asset.sha256,
        "source_output_id": value.source_output_id,
    }
    authority_digest = _hash(AUTHORITY_SCHEMA, authority_payload)
    source_key = mirror_demo_digest(
        R2_SOURCE_KEY_DOMAIN,
        {
            "authority_kind": R2_SOURCE_AUTHORITY_KIND,
            "source_output_id": value.source_output_id,
            "source_asset_id": value.normalized_asset.asset_id,
            "source_asset_sha256": value.normalized_asset.sha256,
            "source_generation_receipt_digest": None,
            "authority_digest": authority_digest,
        },
    )
    row_payload = {
        "execution_contract_digest": value.spec_content_digest,
        "source_ordinal": value.position,
        "source_output_id": value.source_output_id,
        "source_asset_id": value.normalized_asset.asset_id,
        "source_asset_sha256": value.normalized_asset.sha256,
        "source_asset_byte_size": value.normalized_asset.byte_size,
        "source_asset_mime_type": "image/jpeg",
        "source_asset_width": value.normalized_asset.width,
        "source_asset_height": value.normalized_asset.height,
        "source_provenance_digest": provenance["content_digest"],
        "source_authority_digest": authority_digest,
        "source_authority_key": source_key,
        "source_qa_snapshot_digest": formal_qa,
        "generation_request_policy_digest": value.generation_policy_digest,
        "adult_synthetic_attested": True,
        "synthetic_only_attested": True,
        "real_person_reference_used": False,
        "authority_state": "PRINCIPAL_ACCEPTED",
        "execution_epoch": "D02_AUTONOMOUS_V1",
        "acquisition_candidate_id": value.candidate_id,
        "selected_source_manifest_id": value.manifest_id,
        "manifest_position": value.position,
    }
    content_digest = _hash(SOURCE_SCHEMA, row_payload)
    row = {
        "id": _hash(
            SOURCE_ID_SCHEMA,
            {
                "acquisition_candidate_id": value.candidate_id,
                "selected_source_manifest_id": value.manifest_id,
                "manifest_position": value.position,
                "source_asset_id": value.normalized_asset.asset_id,
                "content_digest": content_digest,
            },
        )[:32],
        "schema_version": SOURCE_SCHEMA,
        "canonical_payload": row_payload,
        "content_digest": content_digest,
        **row_payload,
    }
    return row


def validate_source_authority(
    value: GenericSourceInput,
    *,
    source_row: Mapping[str, object],
) -> Mapping[str, object]:
    """Replay one formal source row from its Candidate/Manifest input."""

    expected = build_source_authority(value)
    if dict(source_row) != expected:
        raise GenericAdmissionError("source row does not replay")
    return source_row


def build_identity_row(
    value: GenericSourceInput,
    *,
    source_row: Mapping[str, object],
) -> dict[str, object]:
    source = validate_source_authority(value, source_row=source_row)
    config = _digest(value.spec_content_digest, "admission config digest")
    facts = dict(value.formal_facts)
    projection = dict(value.formal_measurement_projection)
    common_evidence = {
        "acquisition_run_id": value.acquisition_run_id,
        "cohort_spec_id": value.cohort_spec_id,
        "selected_source_manifest_id": value.manifest_id,
        "manifest_position": value.position,
        "acquisition_candidate_id": value.candidate_id,
        "source_authority_digest": source["source_authority_digest"],
        "source_qa_snapshot_digest": source["source_qa_snapshot_digest"],
        "source_provenance_digest": source["source_provenance_digest"],
        "asset_id": source["source_asset_id"],
        "asset_sha256": source["source_asset_sha256"],
    }
    fact_payload = {**common_evidence, "facts": facts}
    projection_payload = {**common_evidence, "projection": projection}
    canonical = {
        "formal_synthetic_identity_id": None,
        "formal_canonical_asset_id": source["source_asset_id"],
        "formal_canonical_asset_sha256": source["source_asset_sha256"],
        "formal_accepted_qa_run_id": None,
        "formal_accepted_qa_snapshot_digest": None,
        "admission_sequence": 1,
        "admission_action": "ADMIT",
        "admission_config_digest": config,
        "supersedes_id": None,
        "source_output_id": source["source_output_id"],
        "source_receipt_digest": None,
        "source_authority_digest": source["source_authority_digest"],
        "source_qa_snapshot_digest": source["source_qa_snapshot_digest"],
        "source_landmark_digest": _digest(value.formal_landmark_digest, "landmark digest"),
        "source_measurement_digest": _hash(
            "mirror.demo/D02GenericSourceMeasurement/v1", projection_payload
        ),
        "source_provenance_digest": source["source_provenance_digest"],
        "source_fact_snapshot": fact_payload,
        "source_fact_snapshot_digest": _hash("mirror.demo/D02GenericSourceFacts/v1", fact_payload),
        "source_measurement_projection": projection_payload,
        "source_measurement_projection_digest": _hash(
            "mirror.demo/D02GenericSourceProjection/v1", projection_payload
        ),
        "original_formal_identity_id_status": "NOT_APPLICABLE_D02_GENERIC_SOURCE",
        "adult_synthetic_attested": True,
        "importer_version": "demo-d02-generic-identity-importer-v1",
        "import_config_digest": config,
        "r2_source_authority_record_id": source["id"],
    }
    canonical["source_authority_kind"] = "DEMO_R2_GENERATED_SOURCE"
    canonical["source_authority_key"] = source["source_authority_key"]
    row_digest = _hash(IDENTITY_SCHEMA, canonical)
    identity_id = _hash(
        IDENTITY_ID_SCHEMA,
        {
            "source_authority_kind": canonical["source_authority_kind"],
            "source_authority_key": canonical["source_authority_key"],
            "r2_source_authority_record_id": source["id"],
            "admission_sequence": 1,
            "admission_action": "ADMIT",
            "supersedes_id": None,
            "admission_config_digest": config,
            "canonical_payload_digest": row_digest,
        },
    )[:32]
    return {
        "id": identity_id,
        "schema_version": IDENTITY_SCHEMA,
        "canonical_payload": canonical,
        "content_digest": row_digest,
        **canonical,
    }


def validate_identity_row(
    value: GenericSourceInput,
    *,
    source_row: Mapping[str, object],
    identity_row: Mapping[str, object],
) -> Mapping[str, object]:
    """Replay one v5 identity from the exact generic formal source input."""

    expected = build_identity_row(value, source_row=source_row)
    if dict(identity_row) != expected:
        raise GenericAdmissionError("identity row does not replay")
    return identity_row


def build_generic_admission(
    *,
    idempotency_key_hash: str,
    request_payload: Mapping[str, object],
    selected_source_manifest_id: str,
    selected_source_manifest_digest: str,
    formal_source_manifest_digest: str,
    screening_report_id: str,
    screening_report_digest: str,
    question_bank_id: str,
    question_bank_content_digest: str,
    question_bank_version: str,
    selected_pair_manifest_digest: str,
) -> dict[str, object]:
    key = _digest(idempotency_key_hash, "idempotency key hash")
    manifest = _id(selected_source_manifest_id, "selected manifest ID")
    for digest, label in (
        (selected_source_manifest_digest, "selected source manifest digest"),
        (formal_source_manifest_digest, "formal source manifest digest"),
        (screening_report_digest, "screening report digest"),
        (question_bank_content_digest, "question bank content digest"),
        (selected_pair_manifest_digest, "selected pair manifest digest"),
    ):
        _digest(digest, label)
    _id(screening_report_id, "screening report ID")
    _id(question_bank_id, "question bank ID")
    request = {
        "schema_version": REQUEST_SCHEMA,
        **dict(request_payload),
        "selected_source_manifest_id": manifest,
        "selected_source_manifest_digest": selected_source_manifest_digest,
        "formal_source_manifest_digest": formal_source_manifest_digest,
        "screening_report_id": screening_report_id,
        "screening_report_digest": screening_report_digest,
        "question_bank_id": question_bank_id,
        "question_bank_content_digest": question_bank_content_digest,
        "question_bank_version": question_bank_version,
        "selected_pair_manifest_digest": selected_pair_manifest_digest,
    }
    request_digest = _hash(REQUEST_SCHEMA, request)
    canonical = {
        "idempotency_key_hash": key,
        "request_digest": request_digest,
        "execution_epoch": "D02_AUTONOMOUS_V1",
        "selected_source_manifest_id": manifest,
        "source_manifest_digest": formal_source_manifest_digest,
        "screening_report_id": screening_report_id,
        "screening_report_digest": screening_report_digest,
        "question_bank_id": question_bank_id,
        "question_bank_content_digest": question_bank_content_digest,
        "question_bank_version": question_bank_version,
        "selected_pair_manifest_digest": selected_pair_manifest_digest,
        "source_authority_count": 4,
        "synthetic_identity_count": 4,
        "question_pair_count": 16,
        "selected_result_side_count": 32,
        "admission_state": "COMPLETED",
    }
    content_digest = _hash(ADMISSION_SCHEMA, canonical)
    return {
        "id": _hash(
            ADMISSION_ID_SCHEMA,
            {
                "idempotency_key_hash": key,
                "request_digest": request_digest,
                "screening_report_id": screening_report_id,
                "question_bank_id": question_bank_id,
            },
        )[:32],
        "schema_version": ADMISSION_SCHEMA,
        "canonical_payload": canonical,
        "content_digest": content_digest,
        "evidence_root_id": None,
        **canonical,
    }


def validate_generic_admission_graph(
    value: object,
    *,
    idempotency_key_hash: str,
    request_payload: Mapping[str, object],
    selected_manifest: Mapping[str, object],
    source_inputs: Sequence[GenericSourceInput],
    source_rows: Sequence[Mapping[str, object]],
    identity_rows: Sequence[Mapping[str, object]],
    report: Mapping[str, object],
    bank: Mapping[str, object],
    pair_rows: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    """Replay the complete generic admission graph before persistence."""

    from mirror_api import demo_d02_generic_screening as screening

    if (
        selected_manifest.get("schema_version") != "mirror.demo/D02SelectedSourceManifest/v1"
        or selected_manifest.get("manifest_state") != "FINALIZED"
    ):
        raise GenericAdmissionError("selected source Manifest is not finalized")
    manifest_id = _id(selected_manifest.get("id"), "selected manifest ID")
    manifest_digest = _digest(
        selected_manifest.get("content_digest"), "selected source manifest digest"
    )
    if len(source_inputs) != 4 or len(source_rows) != 4 or len(identity_rows) != 4:
        raise GenericAdmissionError("generic admission requires four formal sources")
    screening.validate_report_row(
        report,
        source_inputs=source_inputs,
        source_rows=source_rows,
        identity_rows=identity_rows,
        selected_source_manifest_id=manifest_id,
        selected_source_manifest_digest=manifest_digest,
    )
    screening.validate_question_bank_row(
        bank,
        report=report,
        selected_source_manifest_id=manifest_id,
        selected_source_manifest_digest=manifest_digest,
    )
    screening.validate_complete_question_bank(report=report, bank=bank, pair_rows=pair_rows)
    expected = build_generic_admission(
        idempotency_key_hash=idempotency_key_hash,
        request_payload=request_payload,
        selected_source_manifest_id=manifest_id,
        selected_source_manifest_digest=manifest_digest,
        formal_source_manifest_digest=_digest(
            report.get("source_manifest_digest"), "formal source manifest digest"
        ),
        screening_report_id=_id(report.get("id"), "screening report ID"),
        screening_report_digest=_digest(report.get("report_digest"), "screening report digest"),
        question_bank_id=_id(bank.get("id"), "question bank ID"),
        question_bank_content_digest=_digest(
            bank.get("content_digest"), "question bank content digest"
        ),
        question_bank_version=cast(str, bank.get("version")),
        selected_pair_manifest_digest=_digest(
            report.get("selected_pair_manifest_digest"), "selected pair manifest digest"
        ),
    )
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise GenericAdmissionError("generic admission row does not replay")
    return cast(Mapping[str, object], value)
