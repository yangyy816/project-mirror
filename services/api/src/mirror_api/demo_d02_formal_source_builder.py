"""Staged construction of generic formal D02 sources after final selection.

The acquisition ledger chooses four durable Candidates before the formal M3
evidence and generic source authority exist.  This module keeps that ordering
explicit: it first makes a descriptor suitable for the prepared M3 cycle,
then mints the facts-independent generic source row, then binds the delivered
formal M3 outputs into facts and finally replays the row byte-for-byte.

It is deliberately pure: callers supply persisted ORM projections and typed
private-runtime results; this module neither accesses storage nor starts a
backend process.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, NoReturn, cast

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_generic_admission as generic
from mirror_api import demo_d02_generic_screening as screening
from mirror_api import demo_d02_r2_authority as r2
from mirror_api.demo_d02_candidate_qualification import (
    NORMALIZATION_POLICY_DIGEST,
    NormalizedCandidateMaterial,
)
from mirror_api.demo_d02_formal_source_evidence import (
    FormalSourceMeasurementEvidence,
    build_formal_measurement_evidence,
    build_formal_source_facts,
    build_normalization_receipt_digest,
)
from mirror_api.demo_d02_private_vision_backend import PreparedSourceM3Group
from mirror_api.demo_d02_r2_runtime_forward import (
    BackendM3Result,
    DemoModelIdentity,
    DemoRuntimeRecipe,
    DurableSourceDescriptor,
    M3ExecutionOutput,
    M3ModelHandle,
    M3RuntimeHandle,
    SourceDescriptorManifest,
    build_default_model_identity,
    build_default_runtime_recipe,
    mint_runtime_handles,
)
from mirror_api.demo_measurement_quality import JsonValue, mirror_demo_digest
from mirror_api.demo_models import D02CohortSpec, D02SelectedSourceManifest, D02SourceCandidate

FORMAL_MANUAL_REVIEW_SCHEMA: Final = "mirror.demo/D02FormalSourceManualReview/v1"
FORMAL_QA_SCHEMA: Final = "mirror.demo/D02FormalSourceQAEvidence/v1"
ASSET_ID_SCHEMA: Final = "mirror.demo/D02FormalSourceAssetId/v1"
PROVISIONAL_DESCRIPTOR_SCHEMA: Final = "mirror.demo/D02FormalSourceProvisionalDescriptor/v1"

_SELECTION_TOKEN: Final = object()
_PREPARED_TOKEN: Final = object()
_AUTHORITY_TOKEN: Final = object()
_MEASUREMENT_TOKEN: Final = object()
_FINAL_TOKEN: Final = object()
_BUNDLE_TOKEN: Final = object()


class D02FormalSourceBuilderError(ValueError):
    """Raised for a non-replayable or out-of-order formal-source stage."""


def _fail(code: str) -> NoReturn:
    raise D02FormalSourceBuilderError(code)


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        _fail(f"{label}_INVALID")
    return value


def _id(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 32
        or any(char not in "0123456789abcdef" for char in value)
    ):
        _fail(f"{label}_INVALID")
    return value


def _hash(schema: str, payload: Mapping[str, object]) -> str:
    return mirror_demo_digest(schema, cast(Mapping[str, JsonValue], payload))


def _asset_id(
    *, manifest: D02SelectedSourceManifest, candidate: D02SourceCandidate, position: int
) -> str:
    return _hash(
        ASSET_ID_SCHEMA,
        {
            "manifest_id": manifest.id,
            "manifest_content_digest": manifest.content_digest,
            "candidate_id": candidate.id,
            "candidate_content_digest": candidate.content_digest,
            "position": position,
        },
    )[:32]


@dataclass(frozen=True, slots=True)
class FormalSourceManualReview:
    """Manifest-bound, non-provisional Principal review for one source."""

    manifest_id: str
    manifest_content_digest: str
    position: int
    candidate_id: str
    normalized_sha256: str
    reviewer_role: str
    synthetic_adult_attested: bool
    suspected_minor: bool
    real_person_reference_used: bool
    celebrity_imitation_suspected: bool
    style_context_match: bool
    anti_homogenization_passed: bool

    def __post_init__(self) -> None:
        _id(self.manifest_id, "FORMAL_REVIEW_MANIFEST_ID")
        _digest(self.manifest_content_digest, "FORMAL_REVIEW_MANIFEST_DIGEST")
        _id(self.candidate_id, "FORMAL_REVIEW_CANDIDATE_ID")
        _digest(self.normalized_sha256, "FORMAL_REVIEW_NORMALIZED_SHA256")
        if type(self.position) is not int or self.position not in {1, 2, 3, 4}:
            _fail("FORMAL_REVIEW_POSITION_INVALID")
        if self.reviewer_role != "D02_SUBSYSTEM_PRINCIPAL":
            _fail("FORMAL_REVIEW_ROLE_INVALID")
        if any(
            type(value) is not bool
            for value in (
                self.synthetic_adult_attested,
                self.suspected_minor,
                self.real_person_reference_used,
                self.celebrity_imitation_suspected,
                self.style_context_match,
                self.anti_homogenization_passed,
            )
        ):
            _fail("FORMAL_REVIEW_BOOLEAN_INVALID")

    @property
    def accepted(self) -> bool:
        return (
            self.synthetic_adult_attested
            and not self.suspected_minor
            and not self.real_person_reference_used
            and not self.celebrity_imitation_suspected
            and self.style_context_match
            and self.anti_homogenization_passed
        )

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": FORMAL_MANUAL_REVIEW_SCHEMA,
            "manifest_id": self.manifest_id,
            "manifest_content_digest": self.manifest_content_digest,
            "position": self.position,
            "candidate_id": self.candidate_id,
            "normalized_sha256": self.normalized_sha256,
            "reviewer_role": self.reviewer_role,
            "synthetic_adult_attested": self.synthetic_adult_attested,
            "suspected_minor": self.suspected_minor,
            "real_person_reference_used": self.real_person_reference_used,
            "celebrity_imitation_suspected": self.celebrity_imitation_suspected,
            "style_context_match": self.style_context_match,
            "anti_homogenization_passed": self.anti_homogenization_passed,
            "decision": "ACCEPT" if self.accepted else "REJECT",
        }


@dataclass(frozen=True, slots=True, init=False)
class FormalSourceSelection:
    spec: D02CohortSpec
    manifest: D02SelectedSourceManifest
    candidates: tuple[
        D02SourceCandidate, D02SourceCandidate, D02SourceCandidate, D02SourceCandidate
    ]
    materials: tuple[
        NormalizedCandidateMaterial,
        NormalizedCandidateMaterial,
        NormalizedCandidateMaterial,
        NormalizedCandidateMaterial,
    ]
    provisional_descriptors: tuple[
        DurableSourceDescriptor,
        DurableSourceDescriptor,
        DurableSourceDescriptor,
        DurableSourceDescriptor,
    ]

    def __init__(
        self,
        *,
        spec: D02CohortSpec,
        manifest: D02SelectedSourceManifest,
        candidates: tuple[
            D02SourceCandidate, D02SourceCandidate, D02SourceCandidate, D02SourceCandidate
        ],
        materials: tuple[
            NormalizedCandidateMaterial,
            NormalizedCandidateMaterial,
            NormalizedCandidateMaterial,
            NormalizedCandidateMaterial,
        ],
        provisional_descriptors: tuple[
            DurableSourceDescriptor,
            DurableSourceDescriptor,
            DurableSourceDescriptor,
            DurableSourceDescriptor,
        ],
        _factory_token: object,
    ) -> None:
        if _factory_token is not _SELECTION_TOKEN:
            raise TypeError("FormalSourceSelection must be issued by initialize_formal_sources")
        object.__setattr__(self, "spec", spec)
        object.__setattr__(self, "manifest", manifest)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "materials", materials)
        object.__setattr__(self, "provisional_descriptors", provisional_descriptors)


@dataclass(frozen=True, slots=True, init=False)
class PreparedFormalSource:
    selection: FormalSourceSelection
    position: int
    prepared_m3: PreparedSourceM3Group
    manual_review: FormalSourceManualReview
    formal_source_qa_digest: str

    def __init__(
        self,
        *,
        selection: FormalSourceSelection,
        position: int,
        prepared_m3: PreparedSourceM3Group,
        manual_review: FormalSourceManualReview,
        formal_source_qa_digest: str,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _PREPARED_TOKEN:
            raise TypeError("PreparedFormalSource must be issued by prepare_formal_source")
        object.__setattr__(self, "selection", selection)
        object.__setattr__(self, "position", position)
        object.__setattr__(self, "prepared_m3", prepared_m3)
        object.__setattr__(self, "manual_review", manual_review)
        object.__setattr__(self, "formal_source_qa_digest", formal_source_qa_digest)


@dataclass(frozen=True, slots=True, init=False)
class FormalSourceAuthorityStage:
    prepared: PreparedFormalSource
    shell_input: generic.GenericSourceInput
    source_row: Mapping[str, object]
    final_descriptor: DurableSourceDescriptor

    def __init__(
        self,
        *,
        prepared: PreparedFormalSource,
        shell_input: generic.GenericSourceInput,
        source_row: Mapping[str, object],
        final_descriptor: DurableSourceDescriptor,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _AUTHORITY_TOKEN:
            raise TypeError(
                "FormalSourceAuthorityStage must be issued by build_formal_source_authority"
            )
        object.__setattr__(self, "prepared", prepared)
        object.__setattr__(self, "shell_input", shell_input)
        object.__setattr__(self, "source_row", dict(source_row))
        object.__setattr__(self, "final_descriptor", final_descriptor)


@dataclass(frozen=True, slots=True, init=False)
class FormalSourceMeasurementStage:
    authority: FormalSourceAuthorityStage
    outputs: tuple[M3ExecutionOutput, M3ExecutionOutput, M3ExecutionOutput]
    measurement_evidence: FormalSourceMeasurementEvidence

    def __init__(
        self,
        *,
        authority: FormalSourceAuthorityStage,
        outputs: tuple[M3ExecutionOutput, M3ExecutionOutput, M3ExecutionOutput],
        measurement_evidence: FormalSourceMeasurementEvidence,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _MEASUREMENT_TOKEN:
            raise TypeError(
                "FormalSourceMeasurementStage must be issued by bind_formal_measurements"
            )
        object.__setattr__(self, "authority", authority)
        object.__setattr__(self, "outputs", outputs)
        object.__setattr__(self, "measurement_evidence", measurement_evidence)


@dataclass(frozen=True, slots=True, init=False)
class FinalFormalSource:
    measurement: FormalSourceMeasurementStage
    source_input: generic.GenericSourceInput
    source_row: Mapping[str, object]
    identity_row: Mapping[str, object]

    def __init__(
        self,
        *,
        measurement: FormalSourceMeasurementStage,
        source_input: generic.GenericSourceInput,
        source_row: Mapping[str, object],
        identity_row: Mapping[str, object],
        _factory_token: object,
    ) -> None:
        if _factory_token is not _FINAL_TOKEN:
            raise TypeError("FinalFormalSource must be issued by finalize_formal_source")
        object.__setattr__(self, "measurement", measurement)
        object.__setattr__(self, "source_input", source_input)
        object.__setattr__(self, "source_row", dict(source_row))
        object.__setattr__(self, "identity_row", dict(identity_row))

    @property
    def position(self) -> int:
        return self.measurement.authority.prepared.position

    @property
    def source_m3_outputs(
        self,
    ) -> tuple[M3ExecutionOutput, M3ExecutionOutput, M3ExecutionOutput]:
        return self.measurement.outputs


@dataclass(frozen=True, slots=True, init=False)
class FormalSourceRuntimeBundle:
    sources: tuple[FinalFormalSource, FinalFormalSource, FinalFormalSource, FinalFormalSource]
    source_manifest_entries: tuple[
        Mapping[str, object], Mapping[str, object], Mapping[str, object], Mapping[str, object]
    ]
    formal_source_manifest_digest: str
    runtime_source_manifest_digest: str
    runtime_packets: tuple[
        Mapping[str, object], Mapping[str, object], Mapping[str, object], Mapping[str, object]
    ]
    descriptor_manifest: SourceDescriptorManifest
    runtime_handle: M3RuntimeHandle
    model_handle: M3ModelHandle

    def __init__(
        self,
        *,
        sources: tuple[FinalFormalSource, FinalFormalSource, FinalFormalSource, FinalFormalSource],
        source_manifest_entries: tuple[
            Mapping[str, object], Mapping[str, object], Mapping[str, object], Mapping[str, object]
        ],
        formal_source_manifest_digest: str,
        runtime_source_manifest_digest: str,
        runtime_packets: tuple[
            Mapping[str, object], Mapping[str, object], Mapping[str, object], Mapping[str, object]
        ],
        descriptor_manifest: SourceDescriptorManifest,
        runtime_handle: M3RuntimeHandle,
        model_handle: M3ModelHandle,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _BUNDLE_TOKEN:
            raise TypeError(
                "FormalSourceRuntimeBundle must be issued by build_formal_runtime_bundle"
            )
        object.__setattr__(self, "sources", sources)
        object.__setattr__(
            self, "source_manifest_entries", tuple(dict(item) for item in source_manifest_entries)
        )
        object.__setattr__(self, "formal_source_manifest_digest", formal_source_manifest_digest)
        object.__setattr__(self, "runtime_source_manifest_digest", runtime_source_manifest_digest)
        object.__setattr__(self, "runtime_packets", tuple(dict(item) for item in runtime_packets))
        object.__setattr__(self, "descriptor_manifest", descriptor_manifest)
        object.__setattr__(self, "runtime_handle", runtime_handle)
        object.__setattr__(self, "model_handle", model_handle)


def initialize_formal_sources(
    *,
    spec: D02CohortSpec,
    manifest: D02SelectedSourceManifest,
    candidates: Sequence[D02SourceCandidate],
    materials: Sequence[NormalizedCandidateMaterial],
) -> FormalSourceSelection:
    """Freeze ordered Candidate/material bindings and deterministic Asset IDs."""

    if type(spec) is not D02CohortSpec or type(manifest) is not D02SelectedSourceManifest:
        _fail("FORMAL_SOURCE_LEDGER_AUTHORITY_INVALID")
    if len(candidates) != 4 or len(materials) != 4:
        _fail("FORMAL_SOURCE_CARDINALITY_INVALID")
    if manifest.manifest_state != "FINALIZED" or manifest.source_count != 4:
        _fail("FORMAL_SOURCE_MANIFEST_NOT_FINALIZED")
    if spec.spec_state != "REGISTERED":
        _fail("FORMAL_SOURCE_SPEC_NOT_REGISTERED")
    _id(spec.id, "FORMAL_SOURCE_SPEC_ID")
    _id(manifest.id, "FORMAL_SOURCE_MANIFEST_ID")
    _digest(spec.content_digest, "FORMAL_SOURCE_SPEC_DIGEST")
    _digest(manifest.content_digest, "FORMAL_SOURCE_MANIFEST_DIGEST")
    if (
        manifest.acquisition_run_id is None
        or manifest.cohort_spec_id != spec.id
        or manifest.generation_policy_digest != spec.generation_policy_digest
    ):
        _fail("FORMAL_SOURCE_MANIFEST_SPEC_BINDING_INVALID")
    candidate_tuple = tuple(candidates)
    material_tuple = tuple(materials)
    if any(type(item) is not D02SourceCandidate for item in candidate_tuple) or any(
        type(item) is not NormalizedCandidateMaterial for item in material_tuple
    ):
        _fail("FORMAL_SOURCE_TYPED_INPUT_INVALID")
    ordered_ids = tuple(manifest.ordered_candidate_ids)
    if len(ordered_ids) != 4 or tuple(item.id for item in candidate_tuple) != ordered_ids:
        _fail("FORMAL_SOURCE_CANDIDATE_ORDER_INVALID")
    descriptors: list[DurableSourceDescriptor] = []
    for position, (candidate, material) in enumerate(
        zip(candidate_tuple, material_tuple, strict=True), 1
    ):
        _validate_candidate_material(
            spec=spec, manifest=manifest, candidate=candidate, material=material
        )
        asset_id = _asset_id(manifest=manifest, candidate=candidate, position=position)
        placeholder = _hash(
            PROVISIONAL_DESCRIPTOR_SCHEMA,
            {
                "manifest_content_digest": manifest.content_digest,
                "candidate_id": candidate.id,
                "candidate_content_digest": candidate.content_digest,
                "position": position,
                "asset_id": asset_id,
                "kind": "provenance",
            },
        )
        descriptors.append(
            DurableSourceDescriptor(
                source_id=asset_id,
                source_output_id=candidate.output_id,
                ordinal=position,
                content_sha256=material.sha256,
                media_type="image/jpeg",
                width=material.width,
                height=material.height,
                byte_length=material.byte_size,
                generation_request_identity=candidate.content_digest,
                provenance_identity=placeholder,
                source_authority_key=_hash(
                    PROVISIONAL_DESCRIPTOR_SCHEMA,
                    {
                        "manifest_content_digest": manifest.content_digest,
                        "candidate_id": candidate.id,
                        "candidate_content_digest": candidate.content_digest,
                        "position": position,
                        "asset_id": asset_id,
                        "kind": "authority",
                    },
                ),
                source_schema_version=generic.SOURCE_SCHEMA,
            )
        )
    return FormalSourceSelection(
        spec=spec,
        manifest=manifest,
        candidates=cast(
            tuple[D02SourceCandidate, D02SourceCandidate, D02SourceCandidate, D02SourceCandidate],
            candidate_tuple,
        ),
        materials=cast(
            tuple[
                NormalizedCandidateMaterial,
                NormalizedCandidateMaterial,
                NormalizedCandidateMaterial,
                NormalizedCandidateMaterial,
            ],
            material_tuple,
        ),
        provisional_descriptors=cast(
            tuple[
                DurableSourceDescriptor,
                DurableSourceDescriptor,
                DurableSourceDescriptor,
                DurableSourceDescriptor,
            ],
            tuple(descriptors),
        ),
        _factory_token=_SELECTION_TOKEN,
    )


def prepare_formal_source(
    *,
    selection: FormalSourceSelection,
    position: int,
    prepared_m3: PreparedSourceM3Group,
    manual_review: FormalSourceManualReview,
) -> PreparedFormalSource:
    """Bind one cached three-repeat source group and final Principal review."""

    if (
        type(selection) is not FormalSourceSelection
        or type(prepared_m3) is not PreparedSourceM3Group
    ):
        _fail("FORMAL_SOURCE_PREPARE_AUTHORITY_INVALID")
    if type(position) is not int or position not in {1, 2, 3, 4}:
        _fail("FORMAL_SOURCE_PREPARE_POSITION_INVALID")
    candidate = selection.candidates[position - 1]
    material = selection.materials[position - 1]
    descriptor = selection.provisional_descriptors[position - 1]
    if (
        prepared_m3.descriptor_digest != descriptor.descriptor_digest
        or prepared_m3.landmark_digest != prepared_m3.outputs[0].fields.get("landmark_digest")
        or len(prepared_m3.outputs) != 3
        or any(type(item) is not BackendM3Result for item in prepared_m3.outputs)
    ):
        _fail("FORMAL_SOURCE_PREPARED_M3_BINDING_INVALID")
    _validate_formal_review(selection, position, candidate, material, manual_review)
    raw_digests = [_raw_m3_digest(item.payload_schema, item.fields) for item in prepared_m3.outputs]
    qa_digest = _hash(
        FORMAL_QA_SCHEMA,
        {
            "manifest_id": selection.manifest.id,
            "manifest_content_digest": selection.manifest.content_digest,
            "position": position,
            "candidate_id": candidate.id,
            "candidate_content_digest": candidate.content_digest,
            "normalized_sha256": material.sha256,
            "provisional_descriptor_digest": descriptor.descriptor_digest,
            "prepared_landmark_digest": prepared_m3.landmark_digest,
            "ordered_raw_m3_output_digests": raw_digests,
            "manual_review": manual_review.payload(),
        },
    )
    if qa_digest in {candidate.m3_evidence_digest, candidate.qa_evidence_digest}:
        _fail("FORMAL_SOURCE_QA_REUSES_CANDIDATE_EVIDENCE")
    return PreparedFormalSource(
        selection=selection,
        position=position,
        prepared_m3=prepared_m3,
        manual_review=manual_review,
        formal_source_qa_digest=qa_digest,
        _factory_token=_PREPARED_TOKEN,
    )


def build_formal_source_authority(prepared: PreparedFormalSource) -> FormalSourceAuthorityStage:
    """Mint the facts-independent generic source row exactly once."""

    if type(prepared) is not PreparedFormalSource:
        _fail("FORMAL_SOURCE_AUTHORITY_STAGE_INVALID")
    selection = prepared.selection
    candidate = selection.candidates[prepared.position - 1]
    provisional = selection.provisional_descriptors[prepared.position - 1]
    shell = _generic_input(
        selection=selection,
        position=prepared.position,
        formal_source_qa_digest=prepared.formal_source_qa_digest,
        formal_facts={},
        formal_measurement_projection={},
        formal_landmark_digest=prepared.prepared_m3.landmark_digest,
    )
    row = generic.build_source_authority(shell)
    if (
        "source_generation_receipt_digest" in row
        or row.get("source_qa_snapshot_digest") != prepared.formal_source_qa_digest
    ):
        _fail("FORMAL_SOURCE_GENERIC_ROW_RECEIPT_INVALID")
    final_descriptor = DurableSourceDescriptor(
        source_id=cast(str, row["source_asset_id"]),
        source_output_id=cast(str, row["source_output_id"]),
        ordinal=cast(int, row["source_ordinal"]),
        content_sha256=cast(str, row["source_asset_sha256"]),
        media_type=cast(str, row["source_asset_mime_type"]),
        width=cast(int, row["source_asset_width"]),
        height=cast(int, row["source_asset_height"]),
        byte_length=cast(int, row["source_asset_byte_size"]),
        generation_request_identity=candidate.content_digest,
        provenance_identity=cast(str, row["source_provenance_digest"]),
        source_authority_key=cast(str, row["source_authority_key"]),
        source_schema_version=cast(str, row["schema_version"]),
    )
    if any(
        getattr(final_descriptor, key) != getattr(provisional, key)
        for key in (
            "source_id",
            "source_output_id",
            "ordinal",
            "content_sha256",
            "media_type",
            "width",
            "height",
            "byte_length",
        )
    ):
        _fail("FORMAL_SOURCE_DESCRIPTOR_STABILITY_INVALID")
    return FormalSourceAuthorityStage(
        prepared=prepared,
        shell_input=shell,
        source_row=row,
        final_descriptor=final_descriptor,
        _factory_token=_AUTHORITY_TOKEN,
    )


def bind_formal_measurements(
    *,
    authority: FormalSourceAuthorityStage,
    outputs: Sequence[M3ExecutionOutput],
) -> FormalSourceMeasurementStage:
    """Accept the three final executor-wrapped outputs for the minted descriptor."""

    if type(authority) is not FormalSourceAuthorityStage or len(outputs) != 3:
        _fail("FORMAL_SOURCE_FINAL_M3_CARDINALITY_INVALID")
    output_tuple = tuple(outputs)
    if any(type(item) is not M3ExecutionOutput for item in output_tuple):
        _fail("FORMAL_SOURCE_FINAL_M3_TYPED_INVALID")
    prepared_outputs = authority.prepared.prepared_m3.outputs
    for raw, final in zip(prepared_outputs, output_tuple, strict=True):
        if (
            final.payload_schema != raw.payload_schema
            or final.payload_schema != r2.R2_SOURCE_M3_SCHEMA
        ):
            _fail("FORMAL_SOURCE_FINAL_M3_SCHEMA_INVALID")
        if any(
            final.fields.get(key) != value
            for key, value in raw.fields.items()
            if key != "execution_receipt_digest"
        ):
            _fail("FORMAL_SOURCE_FINAL_M3_PREPARED_OUTPUT_MISMATCH")
        subject = final.fields.get("measurement_observation")
        if not isinstance(subject, Mapping) or not isinstance(subject.get("subject"), Mapping):
            _fail("FORMAL_SOURCE_FINAL_M3_SUBJECT_INVALID")
        subject_fields = cast(Mapping[str, object], subject["subject"])
        descriptor = authority.final_descriptor
        if (
            subject_fields.get("source_output_id") != descriptor.source_output_id
            or subject_fields.get("source_asset_id") != descriptor.source_id
            or subject_fields.get("source_asset_sha256") != descriptor.content_sha256
        ):
            _fail("FORMAL_SOURCE_FINAL_M3_DESCRIPTOR_MISMATCH")
    evidence = build_formal_measurement_evidence(cast(Sequence[M3ExecutionOutput], output_tuple))
    return FormalSourceMeasurementStage(
        authority=authority,
        outputs=cast(tuple[M3ExecutionOutput, M3ExecutionOutput, M3ExecutionOutput], output_tuple),
        measurement_evidence=evidence,
        _factory_token=_MEASUREMENT_TOKEN,
    )


def finalize_formal_source(measurement: FormalSourceMeasurementStage) -> FinalFormalSource:
    """Build R2 facts and prove that they cannot change the already minted row."""

    if type(measurement) is not FormalSourceMeasurementStage:
        _fail("FORMAL_SOURCE_FINALIZE_STAGE_INVALID")
    authority = measurement.authority
    prepared = authority.prepared
    selection = prepared.selection
    position = prepared.position
    candidate = selection.candidates[position - 1]
    material = selection.materials[position - 1]
    row = authority.source_row
    facts = build_formal_source_facts(
        candidate=candidate,
        material=material,
        measurement_evidence=measurement.measurement_evidence,
        normalization_receipt_digest=build_normalization_receipt_digest(
            candidate=candidate, material=material
        ),
        source_authority_digest=cast(str, row["source_authority_digest"]),
        source_qa_snapshot_digest=cast(str, row["source_qa_snapshot_digest"]),
        source_provenance_digest=cast(str, row["source_provenance_digest"]),
        qa_policy_digest=selection.spec.qa_policy_digest,
    )
    # The legacy evidence builder deliberately emits its historical placeholder.
    # Generic runtime packets are governed by the frozen R2 validator, whose
    # equivalent explicit state is the non-applicable D02 generic-source value.
    facts["original_formal_identity_id_status"] = r2.R2_NOT_APPLICABLE_STATUS
    r2.validate_r2_facts(facts)
    source_input = _generic_input(
        selection=selection,
        position=position,
        formal_source_qa_digest=prepared.formal_source_qa_digest,
        formal_facts=facts,
        formal_measurement_projection=measurement.measurement_evidence.measurement_projection,
        formal_landmark_digest=measurement.measurement_evidence.landmark_digest,
    )
    rebuilt = generic.build_source_authority(source_input)
    if dict(row) != rebuilt:
        _fail("FORMAL_SOURCE_ROW_DRIFT_AFTER_FACTS")
    identity = generic.build_identity_row(source_input, source_row=rebuilt)
    if identity.get("source_receipt_digest") is not None:
        _fail("FORMAL_SOURCE_LEGACY_RECEIPT_INJECTED")
    return FinalFormalSource(
        measurement=measurement,
        source_input=source_input,
        source_row=rebuilt,
        identity_row=identity,
        _factory_token=_FINAL_TOKEN,
    )


def build_formal_runtime_bundle(
    sources: Sequence[FinalFormalSource],
    *,
    recipe: DemoRuntimeRecipe | None = None,
    model_identity: DemoModelIdentity | None = None,
) -> FormalSourceRuntimeBundle:
    """Aggregate exactly four finalized sources into packets and runtime handles."""

    if len(sources) != 4 or any(type(item) is not FinalFormalSource for item in sources):
        _fail("FORMAL_SOURCE_BUNDLE_CARDINALITY_INVALID")
    source_tuple = cast(
        tuple[FinalFormalSource, FinalFormalSource, FinalFormalSource, FinalFormalSource],
        tuple(sources),
    )
    if tuple(item.position for item in source_tuple) != (1, 2, 3, 4):
        _fail("FORMAL_SOURCE_BUNDLE_ORDER_INVALID")
    first = source_tuple[0].measurement.authority.prepared.selection
    if any(
        item.measurement.authority.prepared.selection.manifest.id != first.manifest.id
        or item.measurement.authority.prepared.selection.manifest.content_digest
        != first.manifest.content_digest
        or item.measurement.authority.prepared.selection.spec.id != first.spec.id
        or item.measurement.authority.prepared.selection.spec.content_digest
        != first.spec.content_digest
        for item in source_tuple
    ):
        _fail("FORMAL_SOURCE_BUNDLE_SELECTION_MISMATCH")
    inputs = tuple(item.source_input for item in source_tuple)
    rows = tuple(item.source_row for item in source_tuple)
    identities = tuple(item.identity_row for item in source_tuple)
    entries_list, formal_digest = screening.build_formal_source_manifest(
        source_inputs=inputs,
        source_rows=rows,
        identity_rows=identities,
        selected_source_manifest_id=first.manifest.id,
        selected_source_manifest_digest=first.manifest.content_digest,
    )
    entries = cast(
        tuple[
            Mapping[str, object], Mapping[str, object], Mapping[str, object], Mapping[str, object]
        ],
        tuple(entries_list),
    )
    runtime_manifest_digest = legacy._sequence_digest(r2.R2_SOURCE_MANIFEST_SCHEMA, entries)
    packets = tuple(
        screening.build_generic_runtime_packet(
            source_input=source.source_input,
            source_row=source.source_row,
            identity_row=source.identity_row,
            source_manifest_entry=entry,
            source_manifest_digest=runtime_manifest_digest,
        )
        for source, entry in zip(source_tuple, entries, strict=True)
    )
    for packet in packets:
        screening.validate_generic_runtime_packet(packet)
    descriptor_manifest = SourceDescriptorManifest.from_generic_packets(packets)
    runtime, model = mint_runtime_handles(
        descriptor_manifest,
        recipe=recipe if recipe is not None else build_default_runtime_recipe(),
        model_identity=model_identity
        if model_identity is not None
        else build_default_model_identity(),
    )
    return FormalSourceRuntimeBundle(
        sources=source_tuple,
        source_manifest_entries=entries,
        formal_source_manifest_digest=formal_digest,
        runtime_source_manifest_digest=runtime_manifest_digest,
        runtime_packets=cast(
            tuple[
                Mapping[str, object],
                Mapping[str, object],
                Mapping[str, object],
                Mapping[str, object],
            ],
            packets,
        ),
        descriptor_manifest=descriptor_manifest,
        runtime_handle=runtime,
        model_handle=model,
        _factory_token=_BUNDLE_TOKEN,
    )


def _validate_candidate_material(
    *,
    spec: D02CohortSpec,
    manifest: D02SelectedSourceManifest,
    candidate: D02SourceCandidate,
    material: NormalizedCandidateMaterial,
) -> None:
    checks = (
        ("RUN", candidate.acquisition_run_id == manifest.acquisition_run_id),
        ("SPEC", candidate.cohort_spec_id == spec.id),
        ("STATE", candidate.candidate_state == "QA_ACCEPTED"),
        ("M3", candidate.m3_state == "SUPPORTED" and candidate.m3_evidence_digest is not None),
        ("QA", candidate.qa_state == "ACCEPTED" and candidate.qa_evidence_digest is not None),
        ("ADULT", candidate.adult_status == "VERIFIED_SYNTHETIC_ADULT"),
        ("MINOR", candidate.suspected_minor is False),
        ("SYNTHETIC", candidate.synthetic_only_attested is True),
        ("REAL_PERSON", candidate.real_person_reference_used is False),
        ("BACKUP", candidate.durable_backup_sha256 == candidate.durable_primary_sha256),
        ("MATERIAL_ID", material.candidate_id == candidate.id),
        ("MATERIAL_CONTENT", material.candidate_content_digest == candidate.content_digest),
        (
            "MATERIAL_CALL",
            material.call_started_event_digest == candidate.call_started_event_digest,
        ),
        ("MATERIAL_OUTPUT", material.source_output_id == candidate.output_id),
        (
            "MATERIAL_DIMENSIONS",
            material.byte_size > 0 and material.width > 0 and material.height > 0,
        ),
        ("MATERIAL_POLICY", material.normalization_policy_digest == NORMALIZATION_POLICY_DIGEST),
    )
    for label, accepted in checks:
        if not accepted:
            _fail(f"FORMAL_SOURCE_CANDIDATE_MATERIAL_{label}_INVALID")


def _validate_formal_review(
    selection: FormalSourceSelection,
    position: int,
    candidate: D02SourceCandidate,
    material: NormalizedCandidateMaterial,
    review: FormalSourceManualReview,
) -> None:
    if (
        review.manifest_id != selection.manifest.id
        or review.manifest_content_digest != selection.manifest.content_digest
        or review.position != position
        or review.candidate_id != candidate.id
        or review.normalized_sha256 != material.sha256
        or not review.accepted
    ):
        _fail("FORMAL_SOURCE_MANUAL_REVIEW_BINDING_INVALID")


def _raw_m3_digest(payload_schema: str, fields: Mapping[str, object]) -> str:
    if payload_schema != r2.R2_SOURCE_M3_SCHEMA:
        _fail("FORMAL_SOURCE_PREPARED_M3_SCHEMA_INVALID")
    return _hash(
        "mirror.demo/D02FormalSourcePreparedM3Output/v1",
        {"payload_schema": payload_schema, "fields": dict(fields)},
    )


def _generic_input(
    *,
    selection: FormalSourceSelection,
    position: int,
    formal_source_qa_digest: str,
    formal_facts: Mapping[str, object],
    formal_measurement_projection: Mapping[str, object],
    formal_landmark_digest: str,
) -> generic.GenericSourceInput:
    candidate = selection.candidates[position - 1]
    material = selection.materials[position - 1]
    descriptor = selection.provisional_descriptors[position - 1]
    return generic.GenericSourceInput(
        acquisition_run_id=selection.manifest.acquisition_run_id,
        cohort_spec_id=selection.spec.id,
        manifest_id=selection.manifest.id,
        manifest_acquisition_run_id=selection.manifest.acquisition_run_id,
        manifest_cohort_spec_id=selection.manifest.cohort_spec_id,
        manifest_content_digest=selection.manifest.content_digest,
        manifest_ordered_candidate_ids=cast(
            tuple[str, str, str, str], tuple(selection.manifest.ordered_candidate_ids)
        ),
        candidate_id=candidate.id,
        candidate_acquisition_run_id=candidate.acquisition_run_id,
        candidate_cohort_spec_id=candidate.cohort_spec_id,
        candidate_content_digest=candidate.content_digest,
        position=position,
        spec_content_digest=selection.spec.content_digest,
        generation_policy_digest=selection.spec.generation_policy_digest,
        source_output_id=candidate.output_id,
        normalized_asset=generic.NormalizedAsset(
            asset_id=descriptor.source_id,
            sha256=material.sha256,
            byte_size=material.byte_size,
            width=material.width,
            height=material.height,
        ),
        formal_source_qa_digest=_digest(formal_source_qa_digest, "FORMAL_SOURCE_QA_DIGEST"),
        candidate_m3_evidence_digest=cast(str, candidate.m3_evidence_digest),
        candidate_qa_evidence_digest=cast(str, candidate.qa_evidence_digest),
        formal_facts=dict(formal_facts),
        formal_measurement_projection=dict(formal_measurement_projection),
        formal_landmark_digest=_digest(formal_landmark_digest, "FORMAL_SOURCE_LANDMARK_DIGEST"),
    )
