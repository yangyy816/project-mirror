"""Formal three-repeat M3 evidence and generic-source fact construction.

Candidate M3/QA evidence is provisional.  After the immutable four-source
Manifest exists, this module consumes three real source M3 executions, builds
the accepted repeat certificate/raw/projection graph, and only then permits a
generic formal source to bind those facts.  It has no filesystem, Provider, or
database access.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_candidate_qualification import (
    NORMALIZATION_POLICY_DIGEST,
    NormalizedCandidateMaterial,
)
from mirror_api.demo_d02_r2_authority import R2_SOURCE_M3_SCHEMA
from mirror_api.demo_d02_r2_runtime_forward import M3ExecutionOutput
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import D02SourceCandidate

FORMAL_MEASUREMENT_SCHEMA: Final = "mirror.demo/D02FormalSourceMeasurementEvidence/v1"
NORMALIZATION_RECEIPT_SCHEMA: Final = "mirror.demo/D02CandidateNormalizationReceipt/v1"
SOURCE_P2_CANDIDATE_MANIFEST_DIGEST: Final = (
    "eb20210986efe641cc2d6eb5e69afb5b08b48a5b9fecb3feaab7b67bc1efd9e4"
)
DIMENSION_AUTHORITY_MANIFEST_DIGEST: Final = (
    "d4ffa375cf861ec6873270cd4b1c03c4270672f96dee4b8f71ae0678103ad33a"
)

_FORMAL_MEASUREMENT_FACTORY_TOKEN: Final = object()


class D02FormalSourceEvidenceError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True, init=False)
class FormalSourceMeasurementEvidence:
    observation: Mapping[str, object]
    certificate: Mapping[str, object]
    raw_measurement_authority: Mapping[str, object]
    measurement_projection: Mapping[str, object]
    landmark_digest: str
    observation_digest: str
    certificate_digest: str
    raw_digest: str
    projection_digest: str
    evidence_digest: str

    def __init__(
        self,
        *,
        observation: Mapping[str, object],
        certificate: Mapping[str, object],
        raw_measurement_authority: Mapping[str, object],
        measurement_projection: Mapping[str, object],
        landmark_digest: str,
        observation_digest: str,
        certificate_digest: str,
        raw_digest: str,
        projection_digest: str,
        evidence_digest: str,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _FORMAL_MEASUREMENT_FACTORY_TOKEN:
            raise TypeError("FormalSourceMeasurementEvidence must be issued by its builder")
        object.__setattr__(self, "observation", dict(observation))
        object.__setattr__(self, "certificate", dict(certificate))
        object.__setattr__(self, "raw_measurement_authority", dict(raw_measurement_authority))
        object.__setattr__(self, "measurement_projection", dict(measurement_projection))
        object.__setattr__(self, "landmark_digest", landmark_digest)
        object.__setattr__(self, "observation_digest", observation_digest)
        object.__setattr__(self, "certificate_digest", certificate_digest)
        object.__setattr__(self, "raw_digest", raw_digest)
        object.__setattr__(self, "projection_digest", projection_digest)
        object.__setattr__(self, "evidence_digest", evidence_digest)


def build_formal_measurement_evidence(
    outputs: Sequence[M3ExecutionOutput],
) -> FormalSourceMeasurementEvidence:
    if len(outputs) != 3 or any(type(output) is not M3ExecutionOutput for output in outputs):
        _fail("FORMAL_SOURCE_M3_CARDINALITY_INVALID")
    fields = [output.fields for output in outputs]
    if any(output.payload_schema != R2_SOURCE_M3_SCHEMA for output in outputs):
        _fail("FORMAL_SOURCE_M3_SCHEMA_INVALID")
    for key in (
        "canonical_output_digest",
        "landmark_digest",
        "measurement_observation_digest",
    ):
        if len({item[key] for item in fields}) != 1:
            _fail("FORMAL_SOURCE_M3_REPEAT_MISMATCH")
    if len({item["execution_receipt_digest"] for item in fields}) != 3:
        _fail("FORMAL_SOURCE_M3_RECEIPT_COLLISION")
    observation = fields[0].get("measurement_observation")
    if not isinstance(observation, Mapping):
        _fail("FORMAL_SOURCE_M3_OBSERVATION_INVALID")
    subject = observation.get("subject")
    if not isinstance(subject, Mapping):
        _fail("FORMAL_SOURCE_M3_SUBJECT_INVALID")
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
        subject=subject,
        bindings=measurement.default_authority_bindings(),
        ordered_repeat_bindings=[
            {"repeat_index": index, **{key: item[key] for key in repeat_keys}}
            for index, item in enumerate(fields, start=1)
        ],
    )
    raw = legacy.build_raw_measurement_authority(
        observation,
        certificate,
        source_p2_candidate_manifest_content_digest=SOURCE_P2_CANDIDATE_MANIFEST_DIGEST,
        dimension_authority_manifest_content_digest=DIMENSION_AUTHORITY_MANIFEST_DIGEST,
    )
    projection = legacy.build_morphology_projection(raw)
    raw_digest = legacy.digest_raw_measurement_authority(raw)
    projection_digest = legacy.digest_morphology_projection(projection)
    evidence_payload = {
        "schema_version": FORMAL_MEASUREMENT_SCHEMA,
        "ordered_m3_output_digests": [output.output_digest for output in outputs],
        "landmark_digest": fields[0]["landmark_digest"],
        "measurement_observation_digest": fields[0]["measurement_observation_digest"],
        "source_repeat_certification_digest": certificate["source_repeat_certification_digest"],
        "raw_measurement_authority_digest": raw_digest,
        "source_measurement_projection_digest": projection_digest,
    }
    evidence_digest = _digest(FORMAL_MEASUREMENT_SCHEMA, evidence_payload)
    return FormalSourceMeasurementEvidence(
        observation=cast(Mapping[str, object], observation),
        certificate=cast(Mapping[str, object], certificate),
        raw_measurement_authority=cast(Mapping[str, object], raw),
        measurement_projection=cast(Mapping[str, object], projection),
        landmark_digest=cast(str, fields[0]["landmark_digest"]),
        observation_digest=cast(str, fields[0]["measurement_observation_digest"]),
        certificate_digest=cast(str, certificate["source_repeat_certification_digest"]),
        raw_digest=raw_digest,
        projection_digest=projection_digest,
        evidence_digest=evidence_digest,
        _factory_token=_FORMAL_MEASUREMENT_FACTORY_TOKEN,
    )


def build_normalization_receipt_digest(
    *, candidate: D02SourceCandidate, material: NormalizedCandidateMaterial
) -> str:
    if (
        type(material) is not NormalizedCandidateMaterial
        or material.candidate_id != candidate.id
        or material.candidate_content_digest != candidate.content_digest
        or material.call_started_event_digest != candidate.call_started_event_digest
        or material.normalization_policy_digest != NORMALIZATION_POLICY_DIGEST
    ):
        _fail("NORMALIZATION_RECEIPT_BINDING_INVALID")
    return _digest(
        NORMALIZATION_RECEIPT_SCHEMA,
        {
            "candidate_id": candidate.id,
            "candidate_content_digest": candidate.content_digest,
            "input_png_sha256": candidate.durable_primary_sha256,
            "output_jpeg_sha256": material.sha256,
            "output_jpeg_byte_size": material.byte_size,
            "output_jpeg_width": material.width,
            "output_jpeg_height": material.height,
            "normalization_policy_digest": material.normalization_policy_digest,
        },
    )


def build_formal_source_facts(
    *,
    candidate: D02SourceCandidate,
    material: NormalizedCandidateMaterial,
    measurement_evidence: FormalSourceMeasurementEvidence,
    normalization_receipt_digest: str,
    source_authority_digest: str,
    source_qa_snapshot_digest: str,
    source_provenance_digest: str,
    qa_policy_digest: str,
) -> dict[str, object]:
    if type(measurement_evidence) is not FormalSourceMeasurementEvidence:
        _fail("FORMAL_MEASUREMENT_AUTHORITY_INVALID")
    for value in (
        normalization_receipt_digest,
        source_authority_digest,
        source_qa_snapshot_digest,
        source_provenance_digest,
        qa_policy_digest,
    ):
        if not isinstance(value, str) or len(value) != 64:
            _fail("FORMAL_SOURCE_DIGEST_INVALID")
    projection = measurement_evidence.measurement_projection
    facts = legacy.build_facts(
        {
            "source_output_id": candidate.output_id,
            "source_asset_sha256": material.sha256,
            "source_asset_byte_size": material.byte_size,
            "source_asset_mime_type": "image/jpeg",
            "source_asset_width": material.width,
            "source_asset_height": material.height,
            "source_receipt_digest": normalization_receipt_digest,
            "source_authority_digest": source_authority_digest,
            "qa_policy_digest": qa_policy_digest,
            "source_qa_snapshot_digest": source_qa_snapshot_digest,
            "source_landmark_digest": measurement_evidence.landmark_digest,
            "source_measurement_digest": measurement_evidence.observation_digest,
            "source_provenance_digest": source_provenance_digest,
            "source_measurement_projection": dict(projection),
            "source_measurement_projection_digest": measurement_evidence.projection_digest,
            "raw_measurement_authority": dict(measurement_evidence.raw_measurement_authority),
            "raw_measurement_authority_digest": measurement_evidence.raw_digest,
            "adult_synthetic_attested": True,
            "original_formal_identity_id_status": legacy.UNKNOWN_FORMAL_IDENTITY_STATUS,
            "measurement_projection_version": projection["measurement_projection_version"],
            "measurement_quantization_version": projection["measurement_quantization_version"],
            "source_p2_candidate_manifest_content_digest": (SOURCE_P2_CANDIDATE_MANIFEST_DIGEST),
            "dimension_authority_manifest_content_digest": (DIMENSION_AUTHORITY_MANIFEST_DIGEST),
            "source_measurement_observation": dict(measurement_evidence.observation),
            "source_measurement_observation_digest": measurement_evidence.observation_digest,
            "source_repeat_certification": dict(measurement_evidence.certificate),
            "source_repeat_certification_digest": measurement_evidence.certificate_digest,
        }
    )
    return cast(dict[str, object], facts)


def _digest(schema: str, payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        schema.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _fail(code: str) -> NoReturn:
    raise D02FormalSourceEvidenceError(code)
