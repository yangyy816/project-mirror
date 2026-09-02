"""D02 Candidate PNG canonicalization and Principal review contracts.

This module is internal to the autonomous D02 runtime.  It turns the exact
two-copy PNG bound by the private availability index into two deterministic
canonical JPEG copies.  It does not update acquisition business state, call a
Provider, inspect a private namespace by discovery, or expose locators/bytes in
its public evidence payloads.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, NoReturn

from sqlalchemy.orm import Session

from mirror_api.demo_d02_acquisition_operator import D02LocalDurableIndex, LocalDurableEntry
from mirror_api.demo_d02_private_vision_backend import CandidateOneShotInspection
from mirror_api.demo_d02_r2_authority import R2_SOURCE_M3_SCHEMA
from mirror_api.demo_d02_r2_generation_receiver import (
    D02R2PngReceiverError,
    bind_principal_preallocated_destination,
)
from mirror_api.demo_d02_r2_runtime_forward import DurableSourceDescriptor
from mirror_api.demo_d02_source_acquisition import D02SourceAcquisitionService
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import D02SelectedSourceManifest, D02SourceCandidate
from mirror_api.image_sanitizer import (
    DEFAULT_IMAGE_SANITIZER_CONFIG,
    SANITIZER_VERSION,
    ImageSanitizationError,
    SanitizedImage,
    sanitize_image,
)

NORMALIZATION_POLICY_SCHEMA: Final = "mirror.demo/D02CandidateNormalizationPolicy/v1"
NORMALIZED_MATERIAL_SCHEMA: Final = "mirror.private/D02NormalizedCandidateMaterial/v1"
MANUAL_REVIEW_POLICY_SCHEMA: Final = "mirror.demo/D02CandidateManualReviewPolicy/v1"
MANUAL_REVIEW_SCHEMA: Final = "mirror.private/D02CandidateManualReview/v1"
QUALIFICATION_EVIDENCE_SCHEMA: Final = "mirror.private/D02CandidateQualificationEvidence/v1"

_NORMALIZED_MATERIAL_FACTORY_TOKEN: Final = object()
_QUALIFICATION_AUTHORITY_FACTORY_TOKEN: Final = object()
_DIGEST_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_ID_RE: Final = re.compile(r"[0-9a-f]{32}\Z")
_REJECTION_RE: Final = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")

_CONTENT_REJECTION_CODES: Final = frozenset(
    {
        "SUSPECTED_MINOR",
        "REAL_PERSON_OR_CELEBRITY_RISK",
        "MULTIPLE_FACES",
        "POSE_NOT_FRONT_FACING",
        "FEATURES_OBSTRUCTED",
        "QUALITY_INSUFFICIENT",
        "STYLE_CONTEXT_MISMATCH",
        "VARIABLE_CONTAMINATION",
        "ANTI_HOMOGENIZATION_REJECTED",
        "M3_UNSUPPORTED",
    }
)


class D02CandidateQualificationError(RuntimeError):
    """Stable, locator-free Candidate normalization/review failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def normalization_policy_payload() -> dict[str, object]:
    config = DEFAULT_IMAGE_SANITIZER_CONFIG
    return {
        "schema_version": NORMALIZATION_POLICY_SCHEMA,
        "normalizer_version": "d02-candidate-png-to-canonical-jpeg-v1",
        "sanitizer_version": SANITIZER_VERSION,
        "input_media_type": "image/png",
        "output_media_type": "image/jpeg",
        "max_input_bytes": config.max_input_bytes,
        "max_output_bytes": config.max_output_bytes,
        "min_edge_pixels": config.min_edge_pixels,
        "max_edge_pixels": config.max_edge_pixels,
        "max_pixel_count": config.max_pixel_count,
        "jpeg_quality_ladder": list(config.jpeg_quality_ladder),
        "metadata_preserved": False,
        "alpha_policy": "RGB_WHITE_BACKGROUND_V1",
        "two_copy_storage": "AVAILABILITY_MEASURE_NOT_AUTHORITY_CHAIN",
        "formal_source_reuses_exact_normalized_bytes": True,
    }


NORMALIZATION_POLICY_DIGEST: Final = hashlib.sha256(
    NORMALIZATION_POLICY_SCHEMA.encode("utf-8")
    + b"\n"
    + canonical_json_bytes(normalization_policy_payload())
).hexdigest()


def manual_review_policy_payload() -> dict[str, object]:
    return {
        "schema_version": MANUAL_REVIEW_POLICY_SCHEMA,
        "reviewer_role": "D02_SUBSYSTEM_PRINCIPAL",
        "synthetic_adult_required": True,
        "suspected_minor_required": False,
        "real_person_reference_required": False,
        "celebrity_imitation_suspected_required": False,
        "single_face_required": True,
        "front_facing_required": True,
        "features_unobstructed_required": True,
        "quality_sufficient_required": True,
        "style_context_match_required": True,
        "variable_contamination_required": False,
        "anti_homogenization_required": True,
        "beauty_scoring_forbidden": True,
        "sensitive_trait_inference_forbidden": True,
        "manual_review_is_candidate_provisional": True,
        "formal_manifest_review_must_reexecute": True,
        "rejection_codes": sorted(_CONTENT_REJECTION_CODES),
    }


MANUAL_REVIEW_POLICY_DIGEST: Final = hashlib.sha256(
    MANUAL_REVIEW_POLICY_SCHEMA.encode("utf-8")
    + b"\n"
    + canonical_json_bytes(manual_review_policy_payload())
).hexdigest()


@dataclass(frozen=True, slots=True, init=False)
class NormalizedCandidateMaterial:
    candidate_id: str
    candidate_content_digest: str
    call_started_event_digest: str
    source_output_id: str
    sha256: str
    byte_size: int
    width: int
    height: int
    normalization_policy_digest: str
    content: bytes = field(repr=False)

    def __init__(
        self,
        *,
        candidate_id: str,
        candidate_content_digest: str,
        call_started_event_digest: str,
        source_output_id: str,
        sha256: str,
        byte_size: int,
        width: int,
        height: int,
        normalization_policy_digest: str,
        content: bytes,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _NORMALIZED_MATERIAL_FACTORY_TOKEN:
            raise TypeError("NormalizedCandidateMaterial must be issued by the D02 normalizer")
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "candidate_content_digest", candidate_content_digest)
        object.__setattr__(self, "call_started_event_digest", call_started_event_digest)
        object.__setattr__(self, "source_output_id", source_output_id)
        object.__setattr__(self, "sha256", sha256)
        object.__setattr__(self, "byte_size", byte_size)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "normalization_policy_digest", normalization_policy_digest)
        object.__setattr__(self, "content", content)

    def public_payload(self) -> dict[str, object]:
        return {
            "schema_version": NORMALIZED_MATERIAL_SCHEMA,
            "candidate_id": self.candidate_id,
            "candidate_content_digest": self.candidate_content_digest,
            "call_started_event_digest": self.call_started_event_digest,
            "source_output_id": self.source_output_id,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "media_type": "image/jpeg",
            "width": self.width,
            "height": self.height,
            "normalization_policy_digest": self.normalization_policy_digest,
        }


@dataclass(frozen=True, slots=True)
class CandidateManualReview:
    candidate_id: str
    candidate_content_digest: str
    normalized_sha256: str
    selector_slot_id: str
    reviewer_role: str
    synthetic_adult_attested: bool
    suspected_minor: bool
    real_person_reference_used: bool
    celebrity_imitation_suspected: bool
    face_count: int
    front_facing: bool
    features_unobstructed: bool
    quality_sufficient: bool
    style_context_match: bool
    variable_contamination: bool
    anti_homogenization_passed: bool
    rejection_code: str | None = None

    def __post_init__(self) -> None:
        if _ID_RE.fullmatch(self.candidate_id) is None:
            _fail("MANUAL_REVIEW_CANDIDATE_ID_INVALID")
        for value in (self.candidate_content_digest, self.normalized_sha256):
            if _DIGEST_RE.fullmatch(value) is None:
                _fail("MANUAL_REVIEW_DIGEST_INVALID")
        if re.fullmatch(r"D02_SLOT_0[1-4]", self.selector_slot_id) is None:
            _fail("MANUAL_REVIEW_SLOT_INVALID")
        if self.reviewer_role != "D02_SUBSYSTEM_PRINCIPAL":
            _fail("MANUAL_REVIEW_ROLE_INVALID")
        if any(
            type(value) is not bool
            for value in (
                self.synthetic_adult_attested,
                self.suspected_minor,
                self.real_person_reference_used,
                self.celebrity_imitation_suspected,
                self.front_facing,
                self.features_unobstructed,
                self.quality_sufficient,
                self.style_context_match,
                self.variable_contamination,
                self.anti_homogenization_passed,
            )
        ):
            _fail("MANUAL_REVIEW_BOOLEAN_INVALID")
        if type(self.face_count) is not int or self.face_count < 0:
            _fail("MANUAL_REVIEW_FACE_COUNT_INVALID")
        if self.rejection_code is not None and (
            _REJECTION_RE.fullmatch(self.rejection_code) is None
            or self.rejection_code not in _CONTENT_REJECTION_CODES
        ):
            _fail("MANUAL_REVIEW_REJECTION_CODE_INVALID")

    @property
    def accepted(self) -> bool:
        required = (
            self.synthetic_adult_attested
            and not self.suspected_minor
            and not self.real_person_reference_used
            and not self.celebrity_imitation_suspected
            and self.face_count == 1
            and self.front_facing
            and self.features_unobstructed
            and self.quality_sufficient
            and self.style_context_match
            and not self.variable_contamination
            and self.anti_homogenization_passed
        )
        if required and self.rejection_code is not None:
            _fail("MANUAL_REVIEW_ACCEPTED_WITH_REJECTION")
        if not required and self.rejection_code is None:
            _fail("MANUAL_REVIEW_REJECTION_REASON_REQUIRED")
        return required

    def private_payload(self) -> dict[str, object]:
        return {
            "schema_version": MANUAL_REVIEW_SCHEMA,
            "candidate_id": self.candidate_id,
            "candidate_content_digest": self.candidate_content_digest,
            "normalized_sha256": self.normalized_sha256,
            "selector_slot_id": self.selector_slot_id,
            "reviewer_role": self.reviewer_role,
            "manual_review_policy_digest": MANUAL_REVIEW_POLICY_DIGEST,
            "synthetic_adult_attested": self.synthetic_adult_attested,
            "suspected_minor": self.suspected_minor,
            "real_person_reference_used": self.real_person_reference_used,
            "celebrity_imitation_suspected": self.celebrity_imitation_suspected,
            "face_count": self.face_count,
            "front_facing": self.front_facing,
            "features_unobstructed": self.features_unobstructed,
            "quality_sufficient": self.quality_sufficient,
            "style_context_match": self.style_context_match,
            "variable_contamination": self.variable_contamination,
            "anti_homogenization_passed": self.anti_homogenization_passed,
            "decision": "ACCEPT" if self.accepted else "REJECT",
            "rejection_code": self.rejection_code,
        }

    @property
    def evidence_digest(self) -> str:
        return hashlib.sha256(
            MANUAL_REVIEW_SCHEMA.encode("utf-8")
            + b"\n"
            + canonical_json_bytes(self.private_payload())
        ).hexdigest()


@dataclass(frozen=True, slots=True, init=False)
class CandidateQualificationAuthority:
    candidate_id: str
    candidate_content_digest: str
    normalized_sha256: str
    m3_supported: bool
    m3_evidence_digest: str
    qa_accepted: bool
    qa_evidence_digest: str
    identity_family_digest: str | None
    rejection_code: str | None

    def __init__(
        self,
        *,
        candidate_id: str,
        candidate_content_digest: str,
        normalized_sha256: str,
        m3_supported: bool,
        m3_evidence_digest: str,
        qa_accepted: bool,
        qa_evidence_digest: str,
        identity_family_digest: str | None,
        rejection_code: str | None,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _QUALIFICATION_AUTHORITY_FACTORY_TOKEN:
            raise TypeError("CandidateQualificationAuthority must be issued by the D02 qualifier")
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "candidate_content_digest", candidate_content_digest)
        object.__setattr__(self, "normalized_sha256", normalized_sha256)
        object.__setattr__(self, "m3_supported", m3_supported)
        object.__setattr__(self, "m3_evidence_digest", m3_evidence_digest)
        object.__setattr__(self, "qa_accepted", qa_accepted)
        object.__setattr__(self, "qa_evidence_digest", qa_evidence_digest)
        object.__setattr__(self, "identity_family_digest", identity_family_digest)
        object.__setattr__(self, "rejection_code", rejection_code)


class D02CandidateQualificationService:
    """Bind real one-shot M3 and Principal review before mutating the ledger."""

    def __init__(self, *, durable_index: D02LocalDurableIndex) -> None:
        self._index = durable_index

    def evaluate(
        self,
        *,
        candidate: D02SourceCandidate,
        material: NormalizedCandidateMaterial,
        inspection: CandidateOneShotInspection,
        manual_review: CandidateManualReview,
    ) -> CandidateQualificationAuthority:
        _validate_candidate(candidate)
        if type(material) is not NormalizedCandidateMaterial:
            _fail("NORMALIZED_MATERIAL_AUTHORITY_INVALID")
        if type(inspection) is not CandidateOneShotInspection:
            _fail("CANDIDATE_M3_AUTHORITY_INVALID")
        if (
            material.candidate_id != candidate.id
            or material.candidate_content_digest != candidate.content_digest
            or material.call_started_event_digest != candidate.call_started_event_digest
            or manual_review.candidate_id != candidate.id
            or manual_review.candidate_content_digest != candidate.content_digest
            or manual_review.normalized_sha256 != material.sha256
            or manual_review.selector_slot_id != candidate.selector_slot_id
        ):
            _fail("CANDIDATE_QUALIFICATION_BINDING_MISMATCH")
        fields = inspection.result.fields
        observation = fields.get("measurement_observation")
        measurements = (
            observation.get("ordered_measurements") if isinstance(observation, dict) else None
        )
        if (
            inspection.result.payload_schema != R2_SOURCE_M3_SCHEMA
            or inspection.state != "PROVISIONAL_SINGLE_CANDIDATE_INSPECTION"
            or _DIGEST_RE.fullmatch(inspection.inspection_digest) is None
            or fields.get("canonical_output_digest") != material.sha256
            or fields.get("face_count") != 1
            or fields.get("landmark_count") != 478
            or fields.get("coordinates_finite") is not True
            or fields.get("coordinates_in_bounds") is not True
            or not isinstance(measurements, list)
            or len(measurements) != 6
        ):
            _fail("CANDIDATE_M3_BINDING_INVALID")
        m3_supported = all(
            isinstance(entry, dict) and entry.get("support_state") == "SUPPORTED"
            for entry in measurements
        )
        manual_accepted = manual_review.accepted
        qa_accepted = m3_supported and manual_accepted
        rejection_code = (
            None
            if qa_accepted
            else "M3_UNSUPPORTED"
            if not m3_supported
            else manual_review.rejection_code
        )
        identity_family_digest = (
            hashlib.sha256(
                b"mirror.demo/D02CandidateIdentityFamily/v1\n"
                + canonical_json_bytes(
                    {
                        "candidate_id": candidate.id,
                        "selector_slot_id": candidate.selector_slot_id,
                        "normalized_sha256": material.sha256,
                        "measurement_observation_digest": fields["measurement_observation_digest"],
                    }
                )
            ).hexdigest()
            if qa_accepted
            else None
        )
        evidence_payload = {
            "schema_version": QUALIFICATION_EVIDENCE_SCHEMA,
            "candidate_id": candidate.id,
            "candidate_content_digest": candidate.content_digest,
            "normalized_material": material.public_payload(),
            "m3_inspection_digest": inspection.inspection_digest,
            "m3_supported": m3_supported,
            "manual_review": manual_review.private_payload(),
            "qa_accepted": qa_accepted,
            "identity_family_digest": identity_family_digest,
            "rejection_code": rejection_code,
        }
        qa_digest = hashlib.sha256(
            QUALIFICATION_EVIDENCE_SCHEMA.encode("utf-8")
            + b"\n"
            + canonical_json_bytes(evidence_payload)
        ).hexdigest()
        evidence_document = {**evidence_payload, "qualification_digest": qa_digest}
        self._write_private_evidence(candidate.id, evidence_document)
        return CandidateQualificationAuthority(
            candidate_id=candidate.id,
            candidate_content_digest=candidate.content_digest,
            normalized_sha256=material.sha256,
            m3_supported=m3_supported,
            m3_evidence_digest=inspection.inspection_digest,
            qa_accepted=qa_accepted,
            qa_evidence_digest=(qa_digest if m3_supported else inspection.inspection_digest),
            identity_family_digest=identity_family_digest,
            rejection_code=rejection_code,
            _factory_token=_QUALIFICATION_AUTHORITY_FACTORY_TOKEN,
        )

    def apply_to_ledger(
        self,
        *,
        session: Session,
        authority_value: CandidateQualificationAuthority,
    ) -> D02SelectedSourceManifest | None:
        if type(authority_value) is not CandidateQualificationAuthority:
            _fail("CANDIDATE_QUALIFICATION_AUTHORITY_INVALID")
        candidate = session.get(D02SourceCandidate, authority_value.candidate_id)
        if (
            candidate is None
            or candidate.content_digest != authority_value.candidate_content_digest
            or candidate.candidate_state != "DURABLE"
        ):
            _fail("CANDIDATE_LEDGER_BINDING_MISMATCH")
        service = D02SourceAcquisitionService(session)
        if not authority_value.m3_supported:
            service.record_m3_unsupported(
                candidate_id=candidate.id,
                evidence_digest=authority_value.m3_evidence_digest,
                rejection_code="M3_UNSUPPORTED",
            )
            return None
        service.record_m3_supported(
            candidate_id=candidate.id,
            evidence_digest=authority_value.m3_evidence_digest,
        )
        if authority_value.qa_accepted:
            if authority_value.identity_family_digest is None:
                _fail("CANDIDATE_IDENTITY_FAMILY_MISSING")
            return service.record_qa_accepted(
                candidate_id=candidate.id,
                evidence_digest=authority_value.qa_evidence_digest,
                identity_family_digest=authority_value.identity_family_digest,
            )
        if authority_value.rejection_code is None:
            _fail("CANDIDATE_REJECTION_CODE_MISSING")
        service.record_qa_rejected(
            candidate_id=candidate.id,
            evidence_digest=authority_value.qa_evidence_digest,
            rejection_code=authority_value.rejection_code,
        )
        return None

    def _write_private_evidence(self, candidate_id: str, document: dict[str, object]) -> None:
        parent = self._index.objects_parent.parent / "qualification"
        _mkdir_exact(parent)
        leaf = f"d02-c{candidate_id}-qualification.json"
        path = parent / leaf
        content = (
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
        if path.exists():
            if _read_exact_file(path, maximum_bytes=1_048_576) != content:
                _fail("QUALIFICATION_EVIDENCE_COLLISION")
            return
        try:
            replayed = bind_principal_preallocated_destination(
                parent=parent,
                leaf_name=leaf,
            ).write_create_new_durable(content)
        except D02R2PngReceiverError as error:
            raise D02CandidateQualificationError("QUALIFICATION_EVIDENCE_WRITE_FAILED") from error
        if replayed != content:
            _fail("QUALIFICATION_EVIDENCE_REPLAY_FAILED")


class D02CandidateNormalizer:
    """Canonicalize and two-copy one exact durable Candidate without DB mutation."""

    def __init__(self, *, durable_index: D02LocalDurableIndex) -> None:
        self._index = durable_index

    def normalize(self, candidate: D02SourceCandidate) -> NormalizedCandidateMaterial:
        _validate_candidate(candidate)
        self._index.ensure_layout()
        entry = self._index.require_entry(candidate.call_started_event_digest)
        _validate_entry_candidate(entry, candidate)
        primary_png = self._index.bind_primary(entry).read_png_bytes()
        backup_png = self._index.bind_backup(entry).read_png_bytes()
        if (
            primary_png != backup_png
            or hashlib.sha256(primary_png).hexdigest() != candidate.durable_primary_sha256
        ):
            _fail("CANDIDATE_TWO_COPY_BINDING_MISMATCH")
        staging_root = self._index.objects_parent.parent / "runtime-staging"
        _mkdir_exact(staging_root)
        try:
            normalized = sanitize_image(
                primary_png,
                declared_mime_type="image/png",
                spool_root=staging_root,
            )
        except ImageSanitizationError as error:
            raise D02CandidateQualificationError("CANDIDATE_NORMALIZATION_FAILED") from error
        primary_leaf = f"d02-c{candidate.id}-normalized-primary.jpg"
        backup_leaf = f"d02-c{candidate.id}-normalized-backup.jpg"
        primary_path = self._index.objects_parent / primary_leaf
        backup_path = self._index.objects_parent / backup_leaf
        self._publish_or_replay(primary_path, primary_leaf, normalized)
        self._publish_or_replay(backup_path, backup_leaf, normalized)
        updated = self._index.record_normalized_jpeg(
            call_started_event_digest=candidate.call_started_event_digest,
            primary_path=primary_path,
            backup_path=backup_path,
            expected_sha256=normalized.sha256,
            expected_byte_size=normalized.byte_size,
            expected_width=normalized.width,
            expected_height=normalized.height,
        )
        replayed = self._index.read_normalized_jpeg(updated)
        if replayed != normalized.bytes_value:
            _fail("CANDIDATE_NORMALIZATION_REPLAY_FAILED")
        return _issue_normalized_material(candidate, normalized, replayed)

    def recover(self, candidate: D02SourceCandidate) -> NormalizedCandidateMaterial:
        _validate_candidate(candidate)
        self._index.ensure_layout()
        entry = self._index.require_entry(candidate.call_started_event_digest)
        _validate_entry_candidate(entry, candidate)
        content = self._index.read_normalized_jpeg(entry)
        if entry.normalized_primary is None:
            _fail("CANDIDATE_NORMALIZED_MATERIAL_MISSING")
        facts = entry.normalized_primary
        normalized = SanitizedImage(
            version=SANITIZER_VERSION,
            content_type="image/jpeg",
            bytes_value=content,
            sha256=facts.sha256,
            byte_size=facts.byte_size,
            width=facts.width,
            height=facts.height,
        )
        return _issue_normalized_material(candidate, normalized, content)

    def _publish_or_replay(self, path: Path, leaf_name: str, normalized: SanitizedImage) -> None:
        if path.exists():
            return
        try:
            replayed = bind_principal_preallocated_destination(
                parent=self._index.objects_parent,
                leaf_name=leaf_name,
            ).write_create_new_durable(normalized.bytes_value)
        except D02R2PngReceiverError as error:
            raise D02CandidateQualificationError("NORMALIZED_STORAGE_FAILED") from error
        if replayed != normalized.bytes_value:
            _fail("CANDIDATE_NORMALIZATION_REPLAY_FAILED")


def build_candidate_descriptor(
    *,
    candidate: D02SourceCandidate,
    material: NormalizedCandidateMaterial,
) -> DurableSourceDescriptor:
    _validate_candidate(candidate)
    if (
        type(material) is not NormalizedCandidateMaterial
        or material.candidate_id != candidate.id
        or material.candidate_content_digest != candidate.content_digest
        or material.call_started_event_digest != candidate.call_started_event_digest
        or material.source_output_id != candidate.output_id
    ):
        _fail("NORMALIZED_MATERIAL_AUTHORITY_INVALID")
    provisional_key = hashlib.sha256(
        b"mirror.demo/D02CandidateProvisionalSourceKey/v1\n"
        + canonical_json_bytes(
            {
                "candidate_id": candidate.id,
                "candidate_content_digest": candidate.content_digest,
                "normalized_sha256": material.sha256,
            }
        )
    ).hexdigest()
    return DurableSourceDescriptor(
        source_id=candidate.id,
        source_output_id=candidate.output_id,
        ordinal=int(candidate.selector_slot_id[-1]),
        content_sha256=material.sha256,
        media_type="image/jpeg",
        width=material.width,
        height=material.height,
        byte_length=material.byte_size,
        generation_request_identity=candidate.call_started_event_digest,
        provenance_identity=candidate.content_digest,
        source_authority_key=provisional_key,
        source_schema_version="mirror.demo/D02SourceCandidate/v1",
    )


def _issue_normalized_material(
    candidate: D02SourceCandidate,
    normalized: SanitizedImage,
    content: bytes,
) -> NormalizedCandidateMaterial:
    return NormalizedCandidateMaterial(
        candidate_id=candidate.id,
        candidate_content_digest=candidate.content_digest,
        call_started_event_digest=candidate.call_started_event_digest,
        source_output_id=candidate.output_id,
        sha256=normalized.sha256,
        byte_size=normalized.byte_size,
        width=normalized.width,
        height=normalized.height,
        normalization_policy_digest=NORMALIZATION_POLICY_DIGEST,
        content=content,
        _factory_token=_NORMALIZED_MATERIAL_FACTORY_TOKEN,
    )


def _validate_candidate(candidate: D02SourceCandidate) -> None:
    if (
        not isinstance(candidate, D02SourceCandidate)
        or candidate.candidate_state not in {"DURABLE", "M3_SUPPORTED", "QA_ACCEPTED"}
        or candidate.durable_media_type != "image/png"
        or candidate.durable_backup_sha256 != candidate.durable_primary_sha256
        or candidate.durable_byte_size < 1
        or candidate.durable_width < 1
        or candidate.durable_height < 1
    ):
        _fail("CANDIDATE_NOT_NORMALIZABLE")


def _validate_entry_candidate(entry: LocalDurableEntry, candidate: D02SourceCandidate) -> None:
    if (
        entry.run_id != candidate.acquisition_run_id
        or entry.cohort_spec_id != candidate.cohort_spec_id
        or entry.provider_ordinal != candidate.provider_ordinal
        or entry.selector_slot_id != candidate.selector_slot_id
        or entry.call_started_event_digest != candidate.call_started_event_digest
        or entry.primary is None
        or entry.backup is None
        or entry.primary.sha256 != candidate.durable_primary_sha256
        or entry.backup.sha256 != candidate.durable_backup_sha256
    ):
        _fail("CANDIDATE_PRIVATE_INDEX_BINDING_MISMATCH")


def _read_exact_file(path: Path, *, maximum_bytes: int) -> bytes:
    try:
        metadata = os.lstat(path)
        resolved = path.resolve(strict=True)
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise D02CandidateQualificationError("QUALIFICATION_EVIDENCE_INVALID") from error
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    identity = metadata.st_dev, metadata.st_ino
    if (
        resolved != path
        or parent != path.parent
        or not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or (reparse_flag and attributes & reparse_flag)
    ):
        _fail("QUALIFICATION_EVIDENCE_INVALID")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != identity or not stat.S_ISREG(opened.st_mode):
                _fail("QUALIFICATION_EVIDENCE_INVALID")
            chunks: list[bytes] = []
            total = 0
            while chunk := os.read(descriptor, 64 * 1024):
                total += len(chunk)
                if total > maximum_bytes:
                    _fail("QUALIFICATION_EVIDENCE_INVALID")
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except D02CandidateQualificationError:
        raise
    except OSError as error:
        raise D02CandidateQualificationError("QUALIFICATION_EVIDENCE_INVALID") from error


def _mkdir_exact(path: Path) -> None:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    except OSError as error:
        raise D02CandidateQualificationError("RUNTIME_STAGING_CREATE_FAILED") from error
    try:
        info = os.lstat(path)
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise D02CandidateQualificationError("RUNTIME_STAGING_INVALID") from error
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if (
        resolved != path
        or not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or (reparse_flag and attributes & reparse_flag)
    ):
        _fail("RUNTIME_STAGING_INVALID")


def _fail(code: str) -> NoReturn:
    raise D02CandidateQualificationError(code)
