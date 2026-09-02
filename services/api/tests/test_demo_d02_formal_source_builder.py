from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Callable, Generator, Mapping
from io import BytesIO, StringIO
from pathlib import Path
from typing import cast

import pytest
from PIL import Image
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from mirror_api import demo_d02_private_vision_backend as private_backend
from mirror_api.demo_d02_acquisition_operator import (
    D02AcquisitionOperator,
    D02LocalDurableIndex,
)
from mirror_api.demo_d02_candidate_qualification import (
    D02CandidateNormalizer,
    NormalizedCandidateMaterial,
)
from mirror_api.demo_d02_formal_source_builder import (
    D02FormalSourceBuilderError,
    FinalFormalSource,
    FormalSourceManualReview,
    bind_formal_measurements,
    build_formal_runtime_bundle,
    build_formal_source_authority,
    finalize_formal_source,
    initialize_formal_sources,
    prepare_formal_source,
)
from mirror_api.demo_d02_private_vision_backend import (
    ProcessOutcome,
    WindowsFaceLandmarkerOfflineM3Backend,
)
from mirror_api.demo_d02_r2_runtime_forward import (
    DemoM3M4Executor,
    DurableSourceDescriptor,
    OfflineM4Backend,
    SourceDescriptorManifest,
    SourceMaterial,
    build_default_model_identity,
    build_default_runtime_recipe,
    mint_runtime_handles,
)
from mirror_api.demo_d02_r2_screening_execution import _validated_sources
from mirror_api.demo_d02_source_acquisition import D02SourceAcquisitionService
from mirror_api.demo_models import (
    D02CohortSpec,
    D02SelectedSourceManifest,
    D02SourceCandidate,
)

pytestmark = pytest.mark.integration


def _m3_stderr() -> bytes:
    lines = [f"INFO: synthetic diagnostic {index:02d}" for index in range(22)]
    lines[1] = "W0000 00:00:1234567890.123456 100 source.cc:10] synthetic warning one"
    lines[9] = "W0000 00:00:1234567890.234567 101 source.cc:20] synthetic warning two"
    lines[15] = "W0000 00:00:1234567890.345678 102 source.cc:30] synthetic warning three"
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


@pytest.fixture(autouse=True)
def _synthetic_diagnostic_grammar(monkeypatch: pytest.MonkeyPatch) -> None:
    digests = tuple(
        hashlib.sha256(
            private_backend._ABSL_DIAGNOSTIC_PREFIX_RE.sub(b"<ABSL> ", line, count=1)
        ).hexdigest()
        for line in _m3_stderr().splitlines()
    )
    monkeypatch.setattr(private_backend, "_EXPECTED_DIAGNOSTIC_LINE_DIGESTS", digests)


def _digest(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _result_input(marker: int) -> BytesIO:
    image = Image.new("RGB", (96, 96), (marker * 40, 90, 160))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    line = json.dumps(
        {
            "outcome": "RESULT",
            "result": {
                "image_url": "data:image/png;base64,"
                + base64.b64encode(buffer.getvalue()).decode("ascii")
            },
        },
        separators=(",", ":"),
    )
    return BytesIO((line + "\n").encode("utf-8"))


def _m3_stdout() -> bytes:
    points = ["0.500000,0.500000,0.000000" for _ in range(478)]
    anchors = {
        10: (0.50, 0.10),
        17: (0.50, 0.60),
        61: (0.40, 0.60),
        98: (0.45, 0.50),
        123: (0.30, 0.50),
        133: (0.40, 0.40),
        152: (0.50, 0.90),
        234: (0.25, 0.70),
        291: (0.60, 0.60),
        327: (0.55, 0.50),
        352: (0.70, 0.50),
        362: (0.60, 0.40),
        454: (0.75, 0.70),
    }
    for index, (x, y) in anchors.items():
        points[index] = f"{x:.6f},{y:.6f},0.000000"
    return (
        "\r\n".join(
            (
                "detect_status=ok",
                "face_count=1",
                "detect_latency_us=12345",
                "face_0_landmark_count=478",
                f"face_0_landmarks={';'.join(points)}",
                "matrix_count=1",
                "matrix_0=" + ",".join("1.000000" for _ in range(18)),
                "close_status=ok",
            )
        )
        + "\r\n"
    ).encode("ascii")


def _runner(
    calls: list[tuple[str, ...]],
) -> Callable[[tuple[str, ...], float, int], ProcessOutcome]:
    def run(command: tuple[str, ...], _timeout: float, _limit: int) -> ProcessOutcome:
        calls.append(command)
        assert Path(command[2]).is_file()
        return ProcessOutcome(returncode=0, stdout=_m3_stdout(), stderr=_m3_stderr())

    return run


@pytest.fixture  # type: ignore[untyped-decorator]
def formal_context(
    tmp_path: Path,
) -> Generator[
    tuple[
        D02AcquisitionOperator,
        D02CandidateNormalizer,
        sessionmaker[Session],
        Path,
    ]
]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, "
                "demo_d02_r2_source_authorities, demo_d02_selected_source_manifests, "
                "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
                "demo_d02_source_acquisition_runs, demo_d02_cohort_specs CASCADE"
            )
        )
    root = tmp_path.resolve(strict=True)
    (root / ".private-handoff").mkdir()
    index = D02LocalDurableIndex(workspace_root=root)
    yield (
        D02AcquisitionOperator(session_factory=sessions, durable_index=index),
        D02CandidateNormalizer(durable_index=index),
        sessions,
        root,
    )
    with sessions.begin() as session:
        session.execute(
            text(
                "TRUNCATE TABLE demo_d02_r2_epoch2_admissions, "
                "demo_d02_r2_source_authorities, demo_d02_selected_source_manifests, "
                "demo_d02_source_acquisition_events, demo_d02_source_candidates, "
                "demo_d02_source_acquisition_runs, demo_d02_cohort_specs CASCADE"
            )
        )
    engine.dispose()


def _accepted_selection(
    operator: D02AcquisitionOperator,
    normalizer: D02CandidateNormalizer,
    sessions: sessionmaker[Session],
) -> tuple[
    D02CohortSpec,
    D02SelectedSourceManifest,
    list[D02SourceCandidate],
    list[NormalizedCandidateMaterial],
]:
    run_id = cast(str, operator.bootstrap()["run_id"])
    manifest: D02SelectedSourceManifest | None = None
    for marker in range(1, 5):
        assert (
            operator.call_session(
                run_id=run_id, input_stream=_result_input(marker), output=StringIO()
            )
            == 0
        )
        with sessions() as session:
            candidate = session.scalar(
                select(D02SourceCandidate).where(D02SourceCandidate.provider_ordinal == marker)
            )
            assert candidate is not None
            normalizer.normalize(candidate)
        with sessions.begin() as session:
            candidate = session.scalar(
                select(D02SourceCandidate).where(D02SourceCandidate.provider_ordinal == marker)
            )
            assert candidate is not None
            service = D02SourceAcquisitionService(session)
            service.record_m3_supported(
                candidate_id=candidate.id, evidence_digest=_digest(f"m3-{marker}")
            )
            manifest = service.record_qa_accepted(
                candidate_id=candidate.id,
                evidence_digest=_digest(f"qa-{marker}"),
                identity_family_digest=_digest(f"family-{marker}"),
            )
    assert manifest is not None
    with sessions() as session:
        manifest = session.scalar(select(D02SelectedSourceManifest))
        spec = session.scalar(select(D02CohortSpec))
        assert manifest is not None and spec is not None
        candidates = [
            candidate
            for item in manifest.ordered_candidate_ids
            if (candidate := session.get(D02SourceCandidate, item)) is not None
        ]
        assert len(candidates) == 4
    return spec, manifest, candidates, [normalizer.recover(item) for item in candidates]


def _accepted_review(
    manifest: D02SelectedSourceManifest, candidate: D02SourceCandidate, sha256: str, position: int
) -> FormalSourceManualReview:
    return FormalSourceManualReview(
        manifest_id=manifest.id,
        manifest_content_digest=manifest.content_digest,
        position=position,
        candidate_id=candidate.id,
        normalized_sha256=sha256,
        reviewer_role="D02_SUBSYSTEM_PRINCIPAL",
        synthetic_adult_attested=True,
        suspected_minor=False,
        real_person_reference_used=False,
        celebrity_imitation_suspected=False,
        style_context_match=True,
        anti_homogenization_passed=True,
    )


def test_staged_formal_builder_replays_four_generic_runtime_packets(
    formal_context: tuple[
        D02AcquisitionOperator,
        D02CandidateNormalizer,
        sessionmaker[Session],
        Path,
    ],
) -> None:
    operator, normalizer, sessions, root = formal_context
    spec, manifest, candidates, materials = _accepted_selection(operator, normalizer, sessions)
    selection = initialize_formal_sources(
        spec=spec, manifest=manifest, candidates=candidates, materials=materials
    )
    calls: list[tuple[str, ...]] = []
    staging_root = root / ".private-handoff" / "runtime-staging"
    staging_root.mkdir()
    backend = WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=staging_root, runner=_runner(calls)
    )
    prepared = [
        prepare_formal_source(
            selection=selection,
            position=position,
            prepared_m3=backend.prepare_source_group(
                content=material.content,
                descriptor=selection.provisional_descriptors[position - 1],
            ),
            manual_review=_accepted_review(manifest, candidate, material.sha256, position),
        )
        for position, (candidate, material) in enumerate(zip(candidates, materials, strict=True), 1)
    ]
    authorities = [build_formal_source_authority(item) for item in prepared]
    descriptors = cast(
        tuple[
            DurableSourceDescriptor,
            DurableSourceDescriptor,
            DurableSourceDescriptor,
            DurableSourceDescriptor,
        ],
        tuple(item.final_descriptor for item in authorities),
    )
    descriptor_manifest = SourceDescriptorManifest(descriptors)
    recipe = build_default_runtime_recipe()
    model = build_default_model_identity()
    runtime_handle, model_handle = mint_runtime_handles(
        descriptor_manifest, recipe=recipe, model_identity=model
    )
    executor = DemoM3M4Executor(
        manifest=descriptor_manifest,
        recipe=recipe,
        model_identity=model,
        runtime_handle=runtime_handle,
        model_handle=model_handle,
        m3_backend=backend,
        m4_backend=cast(OfflineM4Backend, object()),
    )
    finals: list[FinalFormalSource] = []
    for authority, material in zip(authorities, materials, strict=True):
        outputs = [
            executor.inspect_source(
                material=SourceMaterial(
                    descriptor=authority.final_descriptor, content=material.content
                ),
                repeat_index=index,
            )
            for index in (1, 2, 3)
        ]
        finals.append(
            finalize_formal_source(bind_formal_measurements(authority=authority, outputs=outputs))
        )
    bundle = build_formal_runtime_bundle(finals)

    assert len(calls) == 12
    assert (
        bundle.descriptor_manifest.manifest_digest == bundle.runtime_handle.source_manifest_digest
    )
    assert bundle.runtime_source_manifest_digest != bundle.formal_source_manifest_digest
    assert all(
        packet["source_manifest_digest"] == bundle.runtime_source_manifest_digest
        for packet in bundle.runtime_packets
    )
    assert _validated_sources(bundle.runtime_packets)[2] == bundle.runtime_source_manifest_digest
    assert [
        cast(Mapping[str, object], packet["supporting_row"])["source_ordinal"]
        for packet in bundle.runtime_packets
    ] == [
        1,
        2,
        3,
        4,
    ]
    assert all(
        "source_generation_receipt_digest"
        not in cast(Mapping[str, object], packet["supporting_row"])
        for packet in bundle.runtime_packets
    )
    assert all(
        cast(Mapping[str, object], packet["identity_row"])["source_receipt_digest"] is None
        for packet in bundle.runtime_packets
    )
    assert all(
        source.measurement.authority.source_row == source.source_row for source in bundle.sources
    )


def test_staged_formal_builder_rejects_wrong_review_and_reordered_final_sources(
    formal_context: tuple[
        D02AcquisitionOperator,
        D02CandidateNormalizer,
        sessionmaker[Session],
        Path,
    ],
) -> None:
    operator, normalizer, sessions, root = formal_context
    spec, manifest, candidates, materials = _accepted_selection(operator, normalizer, sessions)
    selection = initialize_formal_sources(
        spec=spec, manifest=manifest, candidates=candidates, materials=materials
    )
    staging_root = root / ".private-handoff" / "runtime-staging"
    staging_root.mkdir()
    backend = WindowsFaceLandmarkerOfflineM3Backend.for_testing(
        staging_root=staging_root, runner=_runner([])
    )
    with pytest.raises(D02FormalSourceBuilderError, match="MANUAL_REVIEW_BINDING"):
        prepare_formal_source(
            selection=selection,
            position=1,
            prepared_m3=backend.prepare_source_group(
                content=materials[0].content, descriptor=selection.provisional_descriptors[0]
            ),
            manual_review=_accepted_review(manifest, candidates[1], materials[0].sha256, 1),
        )
