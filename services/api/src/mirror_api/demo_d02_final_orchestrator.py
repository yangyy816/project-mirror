"""Staged, private-byte-safe orchestration for the final D02 runtime Gate.

The accepted R2 screening runner is intentionally all-or-nothing.  A real
Principal artifact review, however, can only be sealed after the first M4
result bytes exist.  This module therefore executes the expensive runtime once
and keeps its public adapter outputs in a sealed in-process stage.  After the
48 first-replay JPEGs are durable and reviewed, the accepted runner consumes a
strict replay adapter; it never invokes M3 or M4 a second time.

Private paths and bytes are inputs only.  They are never placed in the report,
generic source packets, PostgreSQL bundle, exceptions, or object reprs.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, NoReturn, Protocol, cast

from mirror_api import demo_d02_authority as legacy
from mirror_api import demo_d02_r2_authority as r2
from mirror_api import demo_d02_r2_runtime_forward as runtime
from mirror_api import demo_d02_r2_screening_execution as screening_execution
from mirror_api import demo_measurement_quality as measurement
from mirror_api.demo_d02_candidate_qualification import NormalizedCandidateMaterial
from mirror_api.demo_d02_formal_source_builder import (
    FinalFormalSource,
    FormalSourceManualReview,
    FormalSourceRuntimeBundle,
    bind_formal_measurements,
    build_formal_runtime_bundle,
    build_formal_source_authority,
    finalize_formal_source,
    initialize_formal_sources,
    prepare_formal_source,
)
from mirror_api.demo_d02_generic_admission import GenericSourceInput
from mirror_api.demo_d02_private_vision_backend import (
    PreparedSourceM3Group,
    WindowsFaceLandmarkerOfflineM3Backend,
)
from mirror_api.demo_d02_runtime_composition import _read_exact_file, _reject_duplicate_keys
from mirror_api.demo_d02_screening_adapters import (
    ManualReviewAdapter,
    MeasurementGateAdapter,
    PHashAdapter,
    PrincipalArtifactDecision,
)
from mirror_api.demo_d02_source_acquisition import D02SourceAcquisitionError
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_models import D02CohortSpec, D02SelectedSourceManifest, D02SourceCandidate
from mirror_api.synthetic_dataset.similarity import (
    PHASH_ALGORITHM_VERSION,
    PHASH_LOW_FREQUENCY_EDGE,
    PHASH_SAMPLE_EDGE,
)

EXECUTION_AUTHORITY_PENDING_SCHEMA: Final = "mirror.demo/D02ExecutionAuthorityPending/v1"
DUPLICATE_POLICY_SCHEMA: Final = "mirror.demo/D02RuntimeDuplicatePolicy/v1"
PHASH_IMPLEMENTATION_SCHEMA: Final = "mirror.demo/D02RuntimePHashImplementation/v1"
MEASUREMENT_AUTHORITY_RELATIVE: Final = (
    "docs/research/P3_P7_D02_MEASUREMENT_QUALITY_AUTHORITY_MANIFEST.json"
)

_ASSEMBLY_TOKEN: Final = object()
_PREPARED_TOKEN: Final = object()
_CASE_FIELD_KEYS: Final = (
    "geometry_ontology_version_digest",
    "warp_plan_digest",
    "geometry_algorithm_version",
    "runtime_config_digest",
    "output_policy_version",
    "output_width",
    "output_height",
    "determinism_level",
)


class D02FinalOrchestratorError(RuntimeError):
    """Stable final-runtime failure without private values."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class D02CaseM4Backend(Protocol):
    """One backend supplies the frozen case plan and the two M4 replays."""

    execution_runtime_set_digest: str
    algorithm_version: str
    network_policy: str

    def case_fields(
        self,
        *,
        source_packet: Mapping[str, object],
        source_entry: Mapping[str, object],
        case_ordinal: int,
        dimension_key: str,
        direction: str,
        magnitude_ppm: int,
    ) -> Mapping[str, object]: ...

    def transform(
        self,
        *,
        content: bytes,
        descriptor: runtime.DurableSourceDescriptor,
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> runtime.BackendM4Result: ...


class ResultPersistence(Protocol):
    """Availability-only sink used before any Report or admission can exist."""

    def persist(self, output: runtime.M4ExecutionOutput, case_ordinal: int) -> object: ...

    def verify_complete(self, *, outputs: Sequence[runtime.M4ExecutionOutput]) -> None: ...


M4BackendFactory = Callable[
    [
        tuple[
            runtime.SourceMaterial,
            runtime.SourceMaterial,
            runtime.SourceMaterial,
            runtime.SourceMaterial,
        ],
        dict[str, tuple[tuple[float, float, float], ...]],
    ],
    D02CaseM4Backend,
]


class FormalSourceView(Protocol):
    @property
    def position(self) -> int: ...

    @property
    def source_input(self) -> GenericSourceInput: ...

    @property
    def source_row(self) -> Mapping[str, object]: ...

    @property
    def identity_row(self) -> Mapping[str, object]: ...

    @property
    def source_m3_outputs(
        self,
    ) -> tuple[
        runtime.M3ExecutionOutput,
        runtime.M3ExecutionOutput,
        runtime.M3ExecutionOutput,
    ]: ...


class FormalRuntimeBundleView(Protocol):
    @property
    def sources(self) -> Sequence[FormalSourceView]: ...

    @property
    def source_manifest_entries(self) -> Sequence[Mapping[str, object]]: ...

    @property
    def formal_source_manifest_digest(self) -> str: ...

    @property
    def runtime_source_manifest_digest(self) -> str: ...

    @property
    def runtime_packets(self) -> Sequence[Mapping[str, object]]: ...

    @property
    def descriptor_manifest(self) -> runtime.SourceDescriptorManifest: ...

    @property
    def runtime_handle(self) -> runtime.M3RuntimeHandle: ...

    @property
    def model_handle(self) -> runtime.M3ModelHandle: ...


def _digest(schema: str, payload: Mapping[str, object]) -> str:
    import hashlib

    return hashlib.sha256(
        schema.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def duplicate_policy_payload() -> dict[str, object]:
    return {
        "schema_version": DUPLICATE_POLICY_SCHEMA,
        "exact_sha_collision_rejected": True,
        "image_count": 52,
        "comparison_count": 1326,
        "phash_is_observation_only": True,
        "phash_rejection_threshold": None,
        "anti_homogenization_review_required": True,
    }


def phash_implementation_payload() -> dict[str, object]:
    return {
        "schema_version": PHASH_IMPLEMENTATION_SCHEMA,
        "algorithm_version": PHASH_ALGORITHM_VERSION,
        "sample_edge": PHASH_SAMPLE_EDGE,
        "low_frequency_edge": PHASH_LOW_FREQUENCY_EDGE,
        "bit_count": PHASH_LOW_FREQUENCY_EDGE * PHASH_LOW_FREQUENCY_EDGE,
        "implementation": "FIRST_PARTY_DETERMINISTIC_NEAREST_DCT",
        "input": "CHECKSUM_BOUND_CANONICAL_JPEG",
    }


DUPLICATE_POLICY_DIGEST: Final = _digest(DUPLICATE_POLICY_SCHEMA, duplicate_policy_payload())
PHASH_IMPLEMENTATION_DIGEST: Final = _digest(
    PHASH_IMPLEMENTATION_SCHEMA, phash_implementation_payload()
)


def load_measurement_execution_config(*, workspace_root: Path) -> dict[str, object]:
    """Load only the fixed tracked measurement envelope, never a private locator."""

    if not isinstance(workspace_root, Path) or not workspace_root.is_absolute():
        _fail("MEASUREMENT_AUTHORITY_INVALID")
    try:
        content = _read_exact_file(
            workspace_root / MEASUREMENT_AUTHORITY_RELATIVE,
            maximum_bytes=2_000_000,
        )
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        if not isinstance(document, dict):
            _fail("MEASUREMENT_AUTHORITY_INVALID")
        config = document.get("measurement_execution_config")
        if document.get(
            "measurement_config_digest"
        ) != measurement.MEASUREMENT_CONFIG_DIGEST or not isinstance(config, Mapping):
            _fail("MEASUREMENT_AUTHORITY_INVALID")
        measurement.require_replayed_measurement_config_digest(
            config, measurement.MEASUREMENT_CONFIG_DIGEST
        )
        return dict(config)
    except D02FinalOrchestratorError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise D02FinalOrchestratorError("MEASUREMENT_AUTHORITY_INVALID") from error


@dataclass(frozen=True, slots=True, init=False)
class FormalRuntimeAssembly:
    bundle: FormalSourceRuntimeBundle
    source_materials: tuple[
        runtime.SourceMaterial,
        runtime.SourceMaterial,
        runtime.SourceMaterial,
        runtime.SourceMaterial,
    ] = field(repr=False)
    recipe: runtime.DemoRuntimeRecipe
    model_identity: runtime.DemoModelIdentity
    m3_backend: WindowsFaceLandmarkerOfflineM3Backend = field(repr=False, compare=False)
    m4_backend: D02CaseM4Backend = field(repr=False, compare=False)

    def __init__(
        self,
        *,
        bundle: FormalSourceRuntimeBundle,
        source_materials: tuple[
            runtime.SourceMaterial,
            runtime.SourceMaterial,
            runtime.SourceMaterial,
            runtime.SourceMaterial,
        ],
        recipe: runtime.DemoRuntimeRecipe,
        model_identity: runtime.DemoModelIdentity,
        m3_backend: WindowsFaceLandmarkerOfflineM3Backend,
        m4_backend: D02CaseM4Backend,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _ASSEMBLY_TOKEN:
            raise TypeError("FormalRuntimeAssembly must be issued by its orchestrator")
        object.__setattr__(self, "bundle", bundle)
        object.__setattr__(self, "source_materials", source_materials)
        object.__setattr__(self, "recipe", recipe)
        object.__setattr__(self, "model_identity", model_identity)
        object.__setattr__(self, "m3_backend", m3_backend)
        object.__setattr__(self, "m4_backend", m4_backend)


@dataclass(frozen=True, slots=True)
class RuntimeReviewSubject:
    case_id: str
    result_sha256: str
    decision_sequence: int


@dataclass(frozen=True, slots=True, init=False)
class PreparedRuntimeEvidence:
    formal_bundle: FormalRuntimeBundleView = field(repr=False, compare=False)
    source_materials: tuple[
        runtime.SourceMaterial,
        runtime.SourceMaterial,
        runtime.SourceMaterial,
        runtime.SourceMaterial,
    ] = field(repr=False)
    recipe: runtime.DemoRuntimeRecipe
    model_identity: runtime.DemoModelIdentity
    created_at: str
    execution_authority: Mapping[str, object]
    cases: tuple[Mapping[str, object], ...]
    m4_adapter_fields: tuple[Mapping[str, object], ...]
    result_m3_adapter_fields: tuple[Mapping[str, object], ...]
    result_outputs: tuple[runtime.M4ExecutionOutput, ...] = field(repr=False)

    def __init__(
        self,
        *,
        formal_bundle: FormalRuntimeBundleView,
        source_materials: tuple[
            runtime.SourceMaterial,
            runtime.SourceMaterial,
            runtime.SourceMaterial,
            runtime.SourceMaterial,
        ],
        recipe: runtime.DemoRuntimeRecipe,
        model_identity: runtime.DemoModelIdentity,
        created_at: str,
        execution_authority: Mapping[str, object],
        cases: tuple[Mapping[str, object], ...],
        m4_adapter_fields: tuple[Mapping[str, object], ...],
        result_m3_adapter_fields: tuple[Mapping[str, object], ...],
        result_outputs: tuple[runtime.M4ExecutionOutput, ...],
        _factory_token: object,
    ) -> None:
        if _factory_token is not _PREPARED_TOKEN:
            raise TypeError("PreparedRuntimeEvidence must be issued by its orchestrator")
        object.__setattr__(self, "formal_bundle", formal_bundle)
        object.__setattr__(self, "source_materials", source_materials)
        object.__setattr__(self, "recipe", recipe)
        object.__setattr__(self, "model_identity", model_identity)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "execution_authority", dict(execution_authority))
        object.__setattr__(self, "cases", tuple(dict(item) for item in cases))
        object.__setattr__(
            self, "m4_adapter_fields", tuple(dict(item) for item in m4_adapter_fields)
        )
        object.__setattr__(
            self,
            "result_m3_adapter_fields",
            tuple(dict(item) for item in result_m3_adapter_fields),
        )
        object.__setattr__(self, "result_outputs", result_outputs)

    @property
    def review_subjects(self) -> tuple[RuntimeReviewSubject, ...]:
        return tuple(
            RuntimeReviewSubject(
                case_id=output.case_id,
                result_sha256=output.result_sha256,
                decision_sequence=index,
            )
            for index, output in enumerate(self.result_outputs, start=1)
        )


def build_execution_authority(
    *,
    source_manifest_digest: str,
    measurement_execution_config: Mapping[str, object],
    manual_review_policy_digest: str,
    recipe: runtime.DemoRuntimeRecipe | None = None,
    model_identity: runtime.DemoModelIdentity | None = None,
    duplicate_policy_digest: str = DUPLICATE_POLICY_DIGEST,
    phash_implementation_digest: str = PHASH_IMPLEMENTATION_DIGEST,
) -> dict[str, object]:
    """Build the accepted R2 binding without trusting fixture/report state."""

    selected_recipe = recipe if recipe is not None else runtime.build_default_runtime_recipe()
    selected_model = (
        model_identity if model_identity is not None else runtime.build_default_model_identity()
    )
    try:
        measurement.require_replayed_measurement_config_digest(
            measurement_execution_config, selected_recipe.measurement_config_digest
        )
        binding: dict[str, object] = {
            "schema_version": r2.R2_SCHEMA_POLICY_SCHEMA,
            "source_manifest_digest": source_manifest_digest,
            "case_manifest_digest": _digest(
                EXECUTION_AUTHORITY_PENDING_SCHEMA,
                {"source_manifest_digest": source_manifest_digest, "stage": "CASES_PENDING"},
            ),
            "screening_policy_digest": selected_recipe.threshold_config_digest,
            "runtime_manifest_digest": selected_recipe.runtime_manifest_digest,
            "vision_model_manifest_digest": selected_model.weights_digest_or_no_weights,
            "topology_digest": selected_recipe.topology_digest,
            "measurement_execution_config": dict(measurement_execution_config),
            "measurement_config_digest": selected_recipe.measurement_config_digest,
            "measurement_quality_config_digest": measurement.QUALITY_CONFIG_DIGEST,
            "measurement_quality_manifest_content_digest": measurement.QUALITY_MANIFEST_DIGEST,
            "confidence_kind": measurement.CONFIDENCE_KIND,
            "reliability_kind": measurement.RELIABILITY_KIND,
            "manual_review_policy_digest": manual_review_policy_digest,
            "duplicate_policy_digest": duplicate_policy_digest,
            "phash_implementation_digest": phash_implementation_digest,
        }
        r2._r2_execution_authority(binding)
        return binding
    except (KeyError, TypeError, ValueError) as error:
        raise D02FinalOrchestratorError("EXECUTION_AUTHORITY_INVALID") from error


def assemble_formal_runtime(
    *,
    spec: D02CohortSpec,
    manifest: D02SelectedSourceManifest,
    candidates: Sequence[D02SourceCandidate],
    materials: Sequence[NormalizedCandidateMaterial],
    formal_reviews: Sequence[FormalSourceManualReview],
    m3_backend: WindowsFaceLandmarkerOfflineM3Backend,
    m4_backend_factory: M4BackendFactory,
    recipe: runtime.DemoRuntimeRecipe | None = None,
    model_identity: runtime.DemoModelIdentity | None = None,
) -> FormalRuntimeAssembly:
    """Create four formal sources and bind their only real source-M3 cycle."""

    if len(materials) != 4 or any(
        type(item) is not NormalizedCandidateMaterial for item in materials
    ):
        _fail("FORMAL_RUNTIME_MATERIALS_INVALID")
    if len(formal_reviews) != 4:
        _fail("FORMAL_RUNTIME_REVIEWS_INVALID")
    selected_recipe = recipe if recipe is not None else runtime.build_default_runtime_recipe()
    selected_model = (
        model_identity if model_identity is not None else runtime.build_default_model_identity()
    )
    try:
        selection = initialize_formal_sources(
            spec=spec,
            manifest=manifest,
            candidates=candidates,
            materials=materials,
        )
        prepared_groups: list[PreparedSourceM3Group] = []
        prepared_sources = []
        for position, (material, review) in enumerate(
            zip(selection.materials, formal_reviews, strict=True), start=1
        ):
            prepared_group = m3_backend.prepare_source_group(
                content=material.content,
                descriptor=selection.provisional_descriptors[position - 1],
            )
            prepared_groups.append(prepared_group)
            prepared_sources.append(
                prepare_formal_source(
                    selection=selection,
                    position=position,
                    prepared_m3=prepared_group,
                    manual_review=review,
                )
            )
        authority_stages = [build_formal_source_authority(item) for item in prepared_sources]
        descriptor_manifest = runtime.SourceDescriptorManifest(
            cast(
                tuple[
                    runtime.DurableSourceDescriptor,
                    runtime.DurableSourceDescriptor,
                    runtime.DurableSourceDescriptor,
                    runtime.DurableSourceDescriptor,
                ],
                tuple(item.final_descriptor for item in authority_stages),
            )
        )
        source_materials = cast(
            tuple[
                runtime.SourceMaterial,
                runtime.SourceMaterial,
                runtime.SourceMaterial,
                runtime.SourceMaterial,
            ],
            tuple(
                runtime.SourceMaterial(
                    descriptor=authority.final_descriptor, content=material.content
                )
                for authority, material in zip(authority_stages, selection.materials, strict=True)
            ),
        )
        landmarks = {
            authority.final_descriptor.source_id: prepared.landmarks
            for authority, prepared in zip(authority_stages, prepared_groups, strict=True)
        }
        m4_backend = m4_backend_factory(source_materials, landmarks)
        runtime_handle, model_handle = runtime.mint_runtime_handles(
            descriptor_manifest, recipe=selected_recipe, model_identity=selected_model
        )
        executor = runtime.reconstruct_executor(
            descriptor_manifest,
            recipe=selected_recipe,
            model_identity=selected_model,
            runtime_handle=runtime_handle,
            model_handle=model_handle,
            m3_backend=m3_backend,
            m4_backend=m4_backend,
        )
        final_sources: list[FinalFormalSource] = []
        for authority, source_material in zip(authority_stages, source_materials, strict=True):
            outputs = tuple(
                executor.inspect_source(material=source_material, repeat_index=repeat_index)
                for repeat_index in (1, 2, 3)
            )
            final_sources.append(
                finalize_formal_source(
                    bind_formal_measurements(authority=authority, outputs=outputs)
                )
            )
        bundle = build_formal_runtime_bundle(
            final_sources, recipe=selected_recipe, model_identity=selected_model
        )
        if (
            bundle.descriptor_manifest != descriptor_manifest
            or bundle.runtime_handle != runtime_handle
            or bundle.model_handle != model_handle
        ):
            _fail("FORMAL_RUNTIME_BUNDLE_REPLAY_FAILED")
        return FormalRuntimeAssembly(
            bundle=bundle,
            source_materials=source_materials,
            recipe=selected_recipe,
            model_identity=selected_model,
            m3_backend=m3_backend,
            m4_backend=m4_backend,
            _factory_token=_ASSEMBLY_TOKEN,
        )
    except D02FinalOrchestratorError:
        raise
    except (D02SourceAcquisitionError, KeyError, TypeError, ValueError) as error:
        raise D02FinalOrchestratorError("FORMAL_RUNTIME_ASSEMBLY_FAILED") from error


def prepare_runtime_evidence(
    *,
    assembly: FormalRuntimeAssembly,
    created_at: str,
    execution_authority: Mapping[str, object],
    result_persistence: ResultPersistence,
) -> PreparedRuntimeEvidence:
    """Execute and persist 48 results once, before manual artifact review."""

    if type(assembly) is not FormalRuntimeAssembly:
        _fail("FORMAL_RUNTIME_ASSEMBLY_INVALID")
    try:
        packets, sources, source_manifest_digest = screening_execution._validated_sources(
            assembly.bundle.runtime_packets
        )
        authority = dict(execution_authority)
        authority["source_manifest_digest"] = source_manifest_digest
        if source_manifest_digest != assembly.bundle.runtime_source_manifest_digest:
            _fail("FORMAL_RUNTIME_SOURCE_MANIFEST_MISMATCH")
        cases = screening_execution._build_cases(
            assembly.m4_backend,
            packets=packets,
            sources=sources,
            execution_authority=authority,
        )
        authority["case_manifest_digest"] = legacy._sequence_digest(
            r2.R2_CASE_MANIFEST_SCHEMA, cases
        )
        executor = runtime.reconstruct_executor(
            assembly.bundle.descriptor_manifest,
            recipe=assembly.recipe,
            model_identity=assembly.model_identity,
            runtime_handle=assembly.bundle.runtime_handle,
            model_handle=assembly.bundle.model_handle,
            m3_backend=assembly.m3_backend,
            m4_backend=assembly.m4_backend,
        )
        first_outputs: list[runtime.M4ExecutionOutput] = []
        m4_fields: list[Mapping[str, object]] = []
        result_fields: list[Mapping[str, object]] = []
        for case_ordinal, case in enumerate(cases, start=1):
            source_ordinal = cast(int, case["source_ordinal"])
            material = assembly.source_materials[source_ordinal - 1]
            first = executor.transform(material=material, case_entry=case, replay_index=1)
            result_persistence.persist(output=first, case_ordinal=case_ordinal)
            second = executor.transform(material=material, case_entry=case, replay_index=2)
            for output in (first, second):
                m4_fields.append(
                    {
                        "case_id": output.case_id,
                        "replay_index": output.replay_index,
                        **output.screening_fields(
                            source_output_id=material.descriptor.source_output_id
                        ),
                    }
                )
            first_outputs.append(first)
            for repeat_index in (1, 2, 3):
                result_fields.append(
                    executor.inspect_result(
                        output=first, case_entry=case, repeat_index=repeat_index
                    ).fields
                )
        if len(cases) != 48 or len(m4_fields) != 96 or len(result_fields) != 144:
            _fail("FORMAL_RUNTIME_CARDINALITY_INVALID")
        result_persistence.verify_complete(outputs=first_outputs)
        return PreparedRuntimeEvidence(
            formal_bundle=assembly.bundle,
            source_materials=assembly.source_materials,
            recipe=assembly.recipe,
            model_identity=assembly.model_identity,
            created_at=created_at,
            execution_authority=authority,
            cases=tuple(cases),
            m4_adapter_fields=tuple(m4_fields),
            result_m3_adapter_fields=tuple(result_fields),
            result_outputs=tuple(first_outputs),
            _factory_token=_PREPARED_TOKEN,
        )
    except D02FinalOrchestratorError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise D02FinalOrchestratorError("FORMAL_RUNTIME_PREPARATION_FAILED") from error


class _PreparedRuntimeReplayAdapter:
    def __init__(self, prepared: PreparedRuntimeEvidence) -> None:
        self._prepared = prepared
        self._case_calls: set[int] = set()
        self._source_calls: set[tuple[int, int]] = set()
        self._m4_calls: set[tuple[str, int]] = set()
        self._result_calls: set[tuple[str, int]] = set()
        self._case_by_ordinal = {cast(int, case["case_ordinal"]): case for case in prepared.cases}
        self._m4 = {
            (cast(str, item["case_id"]), cast(int, item["replay_index"])): item
            for item in prepared.m4_adapter_fields
        }
        self._result = {
            (
                cast(str, prepared.cases[index // 3]["case_id"]),
                index % 3 + 1,
            ): item
            for index, item in enumerate(prepared.result_m3_adapter_fields)
        }

    def case_fields(
        self,
        *,
        source_packet: Mapping[str, object],
        source_entry: Mapping[str, object],
        case_ordinal: int,
        dimension_key: str,
        direction: str,
        magnitude_ppm: int,
    ) -> Mapping[str, object]:
        del source_packet
        case = self._case_by_ordinal.get(case_ordinal)
        if (
            case is None
            or case_ordinal in self._case_calls
            or case.get("source_asset_id") != source_entry.get("source_asset_id")
            or case.get("dimension_key") != dimension_key
            or case.get("direction") != direction
            or case.get("magnitude_ppm") != magnitude_ppm
        ):
            _fail("PREPARED_CASE_REPLAY_INVALID")
        self._case_calls.add(case_ordinal)
        return {key: case[key] for key in _CASE_FIELD_KEYS}

    def inspect_source(
        self, *, source_packet: Mapping[str, object], repeat_index: int
    ) -> Mapping[str, object]:
        row = cast(Mapping[str, object], source_packet.get("supporting_row"))
        ordinal = cast(int, row.get("source_ordinal"))
        key = (ordinal, repeat_index)
        if (
            ordinal not in {1, 2, 3, 4}
            or repeat_index not in {1, 2, 3}
            or key in self._source_calls
        ):
            _fail("PREPARED_SOURCE_M3_REPLAY_INVALID")
        output = self._prepared.formal_bundle.sources[ordinal - 1].source_m3_outputs[
            repeat_index - 1
        ]
        self._source_calls.add(key)
        return dict(output.fields)

    def transform(
        self,
        *,
        source_packet: Mapping[str, object],
        case_entry: Mapping[str, object],
        replay_index: int,
    ) -> Mapping[str, object]:
        del source_packet
        key = (cast(str, case_entry.get("case_id")), replay_index)
        value = self._m4.get(key)
        if value is None or key in self._m4_calls:
            _fail("PREPARED_M4_REPLAY_INVALID")
        self._m4_calls.add(key)
        return dict(value)

    def inspect_result(
        self,
        *,
        case_entry: Mapping[str, object],
        m4_record: Mapping[str, object],
        repeat_index: int,
    ) -> Mapping[str, object]:
        key = (cast(str, case_entry.get("case_id")), repeat_index)
        value = self._result.get(key)
        if (
            value is None
            or key in self._result_calls
            or m4_record.get("result_sha256") != value.get("canonical_output_digest")
        ):
            _fail("PREPARED_RESULT_M3_REPLAY_INVALID")
        self._result_calls.add(key)
        return dict(value)

    def assert_complete(self) -> None:
        if (
            len(self._case_calls) != 48
            or len(self._source_calls) != 12
            or len(self._m4_calls) != 96
            or len(self._result_calls) != 144
        ):
            _fail("PREPARED_RUNTIME_REPLAY_INCOMPLETE")


def finalize_runtime_evidence(
    *,
    prepared: PreparedRuntimeEvidence,
    artifact_decisions: Mapping[str, PrincipalArtifactDecision],
) -> runtime.RuntimeScreeningResult:
    """Apply sealed Principal decisions and build the accepted Report by replay."""

    if type(prepared) is not PreparedRuntimeEvidence:
        _fail("PREPARED_RUNTIME_EVIDENCE_INVALID")
    if set(artifact_decisions) != {subject.case_id for subject in prepared.review_subjects}:
        _fail("ARTIFACT_REVIEW_CARDINALITY_INVALID")
    screening_decisions = _screening_artifact_decisions(
        prepared=prepared,
        artifact_decisions=artifact_decisions,
    )
    adapter = _PreparedRuntimeReplayAdapter(prepared)
    jpeg_by_digest = {
        material.descriptor.content_sha256: material.content
        for material in prepared.source_materials
    }
    jpeg_by_digest.update(
        {output.result_sha256: output.content for output in prepared.result_outputs}
    )
    try:
        report = screening_execution.run_offline_screening(
            screening_execution.OfflineScreeningRequest(
                created_at=prepared.created_at,
                source_packets=prepared.formal_bundle.runtime_packets,
                execution_authority=prepared.execution_authority,
                case_fields=adapter,
                vision_m3=adapter,
                m4=adapter,
                measurement_gate=MeasurementGateAdapter(),
                manual_review=ManualReviewAdapter(screening_decisions),
                phash=PHashAdapter(jpeg_by_digest),
            )
        )
        adapter.assert_complete()
        return runtime.RuntimeScreeningResult(
            report_row=report,
            source_packets=tuple(prepared.formal_bundle.runtime_packets),
            result_outputs=prepared.result_outputs,
            runtime_handle_digest=prepared.formal_bundle.runtime_handle.handle_digest,
            model_handle_digest=prepared.formal_bundle.model_handle.handle_digest,
            source_descriptor_manifest_digest=(
                prepared.formal_bundle.descriptor_manifest.manifest_digest
            ),
            recipe_digest=prepared.recipe.recipe_digest,
            model_identity_digest=prepared.model_identity.identity_digest,
        )
    except D02FinalOrchestratorError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise D02FinalOrchestratorError("FORMAL_RUNTIME_SCREENING_FAILED") from error


def _screening_artifact_decisions(
    *,
    prepared: PreparedRuntimeEvidence,
    artifact_decisions: Mapping[str, PrincipalArtifactDecision],
) -> dict[str, PrincipalArtifactDecision]:
    """Project sealed review observations into the runner's canonical order."""

    subjects = {subject.case_id: subject for subject in prepared.review_subjects}
    if set(artifact_decisions) != set(subjects):
        _fail("ARTIFACT_REVIEW_CARDINALITY_INVALID")
    result: dict[str, PrincipalArtifactDecision] = {}
    for decision_sequence, case_id in enumerate(sorted(subjects), start=1):
        subject = subjects[case_id]
        decision = artifact_decisions[case_id]
        if decision.result_sha256 != subject.result_sha256:
            _fail("ARTIFACT_REVIEW_BINDING_INVALID")
        if decision.decision_sequence == decision_sequence:
            result[case_id] = decision
            continue
        result[case_id] = PrincipalArtifactDecision.seal(
            case_id=decision.case_id,
            result_sha256=decision.result_sha256,
            decision_sequence=decision_sequence,
            manual_review_version=decision.manual_review_version,
            manual_review_policy_digest=decision.manual_review_policy_digest,
            background_seam=decision.background_seam,
            disconnected_contour=decision.disconnected_contour,
            duplicated_feature=decision.duplicated_feature,
            warp_tear=decision.warp_tear,
        )
    return result


def _fail(code: str) -> NoReturn:
    raise D02FinalOrchestratorError(code)
