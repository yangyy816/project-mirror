from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from test_synthetic_m3_orchestration import _policy_content
from test_synthetic_normalization import _png_bytes, _raw_source

from mirror_api.models import (
    Asset,
    GeometryOntologyVersion,
    Job,
    JobAttempt,
    LandmarkWarpPlanAuthority,
    SyntheticAssetRecord,
    SyntheticIdentity,
    SyntheticQAMeasurement,
    SyntheticQAPolicy,
    SyntheticQAReviewDecision,
    SyntheticQARun,
    TransformRun,
    VariantSpecification,
    new_id,
    utcnow,
)
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.providers.synthetic_normalized_local import (
    LocalSyntheticNormalizedStorageProvider,
)
from mirror_api.providers.synthetic_variant_local import LocalSyntheticVariantStorageProvider
from mirror_api.synthetic_dataset.domain import (
    CanonicalPolicy,
    GeometryDimension,
    GeometryDimensionClassification,
    GeometryOntology,
    PolicyKind,
    ReasonCode,
)
from mirror_api.synthetic_dataset.geometry_transform import (
    GeometryTransformRequest,
    GeometryTransformResult,
    LandmarkWarpPlan,
    WarpControlPoint,
    WarpTriangle,
)
from mirror_api.synthetic_dataset.geometry_variant import (
    DeterminismLevel,
    TransformDirection,
)
from mirror_api.synthetic_dataset.geometry_variant import (
    VariantSpecification as VariantSpecificationDocument,
)
from mirror_api.synthetic_dataset.landmark_warp_plan_authority import (
    LANDMARK_WARP_PLAN_BUILDER_VERSION,
    LandmarkWarpPlanAdmissionService,
)
from mirror_api.synthetic_dataset.m4_orchestration_service import (
    M4RetryableError,
    SyntheticM4OrchestrationService,
)
from mirror_api.synthetic_dataset.normalization_service import SyntheticNormalizationService
from mirror_api.synthetic_dataset.normalization_types import NormalizationResult
from mirror_api.synthetic_dataset.orchestration_service import SyntheticM3OrchestrationService
from mirror_api.synthetic_dataset.transform_service import (
    SyntheticTransformService,
    TransformExecutionRejected,
)

pytestmark = pytest.mark.integration


@asynccontextmanager
async def _database() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield sessions
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE TABLE transform_runs, landmark_warp_plans, variant_specifications, "
                    "synthetic_identities, synthetic_qa_review_decisions, "
                    "synthetic_qa_measurements, synthetic_qa_runs, synthetic_asset_records, "
                    "synthetic_source_object_deletion_evidence, provider_cost_events, "
                    "synthetic_generation_evidence, synthetic_source_objects, generation_items, "
                    "generation_batches, job_attempts, jobs, synthetic_qa_policies, "
                    "geometry_ontology_versions, synthetic_generation_policies, "
                    "synthetic_prompt_templates, assets, "
                    "offline_synthetic_source_admissions CASCADE"
                )
            )
        await engine.dispose()


class _DeterministicTransform:
    def transform(self, *, request: GeometryTransformRequest) -> GeometryTransformResult:
        source = Image.open(io.BytesIO(request.source.content)).convert("RGB")
        source.putpixel((0, 0), (255, 0, 255))
        output = io.BytesIO()
        source.save(
            output,
            format="JPEG",
            quality=95,
            optimize=False,
            progressive=False,
            subsampling=0,
        )
        content = output.getvalue()
        return GeometryTransformResult(
            content=content,
            sha256=hashlib.sha256(content).hexdigest(),
            width=request.source.width,
            height=request.source.height,
            changed_pixel_count=1,
            runtime_version="fixture-transform-runtime-v1",
            runtime_manifest_digest=request.specification.runtime_manifest_digest,
            warp_plan_digest=request.warp_plan.content_digest,
        )


class _UnavailableTransform:
    def transform(self, *, request: GeometryTransformRequest) -> GeometryTransformResult:
        del request
        raise RuntimeError("injected private runtime outage")


class _CountingTransform(_DeterministicTransform):
    def __init__(self) -> None:
        self.calls = 0

    def transform(self, *, request: GeometryTransformRequest) -> GeometryTransformResult:
        self.calls += 1
        return super().transform(request=request)


class _ReadCountingNormalizedStorage:
    def __init__(self, delegate: LocalSyntheticNormalizedStorageProvider) -> None:
        self._delegate = delegate
        self.reads = 0

    async def stream_normalized_image(self, *, storage_reference: str) -> AsyncIterator[bytes]:
        self.reads += 1
        async for chunk in self._delegate.stream_normalized_image(
            storage_reference=storage_reference
        ):
            yield chunk


class _NoopNormalizer:
    async def normalize_record(self, **_: object) -> NormalizationResult:
        return NormalizationResult(
            record_id="a" * 32,
            status="NORMALIZED",
            normalized_asset_id="b" * 32,
            result_code=None,
            sha256="c" * 64,
        )


def _pattern_png_bytes() -> bytes:
    image = Image.new("RGB", (64, 64))
    for y in range(64):
        for x in range(64):
            image.putpixel((x, y), (x * 4, y * 4, (x + y) * 2))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


async def _authority(
    sessions: async_sessionmaker[AsyncSession],
    private_root: Path,
    *,
    algorithm_version: str = "fixture-transform-v1",
    runtime_manifest_digest: str = "7" * 64,
    output_policy_version: str = "variant-output-v1",
    raw_bytes: bytes | None = None,
    target_dimension: str = "jaw_width",
    control_dimensions: tuple[str, ...] = ("nose_width",),
    ontology_classifications: dict[str, str] | None = None,
    bypass_domain_gate: bool = False,
) -> tuple[str, LocalSyntheticNormalizedStorageProvider]:
    raw_storage = LocalSyntheticRawStorageProvider(root=private_root)
    normalized_storage = LocalSyntheticNormalizedStorageProvider(root=private_root)
    source = await _raw_source(
        sessions,
        storage=raw_storage,
        raw_bytes=raw_bytes if raw_bytes is not None else _png_bytes(metadata=True),
    )
    normalizer = SyntheticNormalizationService(
        session_factory=sessions,
        raw_storage=raw_storage,
        normalized_storage=normalized_storage,
        spool_root=private_root / "spool",
        now=utcnow,
    )
    record_id = await normalizer.ensure_record(source_object_id=source.id)
    normalized = await normalizer.normalize_record(record_id=record_id)
    assert normalized.normalized_asset_id is not None

    content = _policy_content()
    qa_policy_document = CanonicalPolicy.create(
        kind=PolicyKind.SYNTHETIC_QA_POLICY,
        version="m4-transform-qa-v1",
        content=content,
    )
    classifications = ontology_classifications or {
        "jaw_width": "EXPERIMENTAL",
        "nose_width": "READY",
    }
    ontology_content = {
        "dimensions": {
            key: {"classification": classification}
            for key, classification in classifications.items()
        }
    }
    ontology_document = CanonicalPolicy.create(
        kind=PolicyKind.GEOMETRY_ONTOLOGY_VERSION,
        version="geometry-m4-runtime-v1",
        content=ontology_content,
    )
    async with sessions.begin() as session:
        policy = SyntheticQAPolicy(
            id=new_id(),
            version=qa_policy_document.version,
            content=content,
            content_digest=qa_policy_document.content_digest,
        )
        ontology_row = GeometryOntologyVersion(
            id=new_id(),
            version=ontology_document.version,
            content=ontology_content,
            content_digest=ontology_document.content_digest,
        )
        session.add_all((policy, ontology_row))
    async with sessions.begin() as session:
        await session.execute(
            update(SyntheticQAPolicy)
            .where(SyntheticQAPolicy.id == policy.id)
            .values(approval_status="APPROVED", approved_at=utcnow())
        )
        await session.execute(
            update(GeometryOntologyVersion)
            .where(GeometryOntologyVersion.id == ontology_row.id)
            .values(approval_status="APPROVED", approved_at=utcnow())
        )
        qa_run = SyntheticQARun(
            id=new_id(),
            synthetic_asset_record_id=record_id,
            normalized_asset_id=normalized.normalized_asset_id,
            qa_policy_id=policy.id,
            vision_provider_reference="deterministic-mock",
            vision_algorithm_reference="fixture-observation-v1",
        )
        session.add(qa_run)
    await _pass_qa(sessions, qa_run.id)
    async with sessions.begin() as session:
        identity = SyntheticIdentity(
            id=new_id(),
            canonical_asset_id=normalized.normalized_asset_id,
            accepted_qa_run_id=qa_run.id,
            adult_synthetic_attested=True,
        )
        session.add(identity)
    async with sessions() as session:
        record = await session.get(SyntheticAssetRecord, record_id)
        source_asset = await session.get(Asset, normalized.normalized_asset_id)
        assert record is not None and record.status == "IDENTITY_REGISTERED"
        assert source_asset is not None
    creation_keys = (target_dimension, *control_dimensions)
    dimensions: list[GeometryDimension] = []
    for key in dict.fromkeys(creation_keys):
        classification = GeometryDimensionClassification(
            "READY" if bypass_domain_gate else classifications[key]
        )
        if classification is GeometryDimensionClassification.READY:
            reasons: tuple[ReasonCode, ...] = ()
        elif classification is GeometryDimensionClassification.EXPERIMENTAL:
            reasons = (ReasonCode.FURTHER_RESEARCH,)
        elif classification is GeometryDimensionClassification.UNSUPPORTED:
            reasons = (ReasonCode.UNSUPPORTED_DIMENSION,)
        elif classification is GeometryDimensionClassification.REQUIRES_3D:
            reasons = (ReasonCode.REQUIRES_3D_RESEARCH,)
        else:
            reasons = (ReasonCode.STYLE_ONLY_DIMENSION,)
        dimensions.append(GeometryDimension(key, classification, reasons))
    ontology = GeometryOntology(authority=ontology_document, dimensions=tuple(dimensions))
    specification_document = VariantSpecificationDocument.create(
        ontology=ontology,
        source_asset_reference=source_asset.id,
        source_identity_reference=identity.id,
        source_qa_run_reference=qa_run.id,
        target_dimension=target_dimension,
        direction=TransformDirection.INCREASE,
        relative_magnitude_ppm=100_000,
        control_dimensions=control_dimensions,
        algorithm_version=algorithm_version,
        runtime_manifest_digest=runtime_manifest_digest,
        tolerance_policy_reference=policy.id,
        output_width=source_asset.width,
        output_height=source_asset.height,
        output_policy_version=output_policy_version,
        determinism_level=DeterminismLevel.BIT_EXACT_SAME_PLATFORM,
    )
    async with sessions.begin() as session:
        specification = VariantSpecification(
            id=new_id(),
            source_asset_id=source_asset.id,
            source_identity_id=identity.id,
            source_qa_run_id=qa_run.id,
            geometry_ontology_version_id=ontology_row.id,
            target_dimension=specification_document.target_dimension,
            direction=specification_document.direction.value,
            relative_magnitude_ppm=specification_document.relative_magnitude_ppm,
            control_dimensions=list(specification_document.control_dimensions),
            algorithm_version=specification_document.algorithm_version,
            runtime_manifest_digest=specification_document.runtime_manifest_digest,
            tolerance_policy_id=policy.id,
            output_width=specification_document.output_width,
            output_height=specification_document.output_height,
            output_policy_version=specification_document.output_policy_version,
            determinism_level=specification_document.determinism_level.value,
            content_digest=specification_document.content_digest,
        )
        session.add(specification)
    plan = LandmarkWarpPlan.create(
        specification_digest=specification.content_digest,
        control_points=(
            WarpControlPoint("a", 0.0, 0.0, 0.05, 0.0, 900_000),
            WarpControlPoint("b", 1.0, 0.0, 1.0, 0.0, 900_000),
            WarpControlPoint("c", 0.0, 1.0, 0.05, 1.0, 900_000),
        ),
        triangles=(WarpTriangle(("a", "b", "c")),),
    )
    authority = LandmarkWarpPlanAdmissionService.prepare(
        specification_digest=specification.content_digest,
        plan=plan,
        origin_reference="m4-runtime-fixture-01",
        origin_digest="a" * 64,
        builder_version=LANDMARK_WARP_PLAN_BUILDER_VERSION,
        builder_manifest_digest="b" * 64,
    )
    async with sessions.begin() as session:
        session.add(
            LandmarkWarpPlanAuthority(
                id=new_id(),
                variant_specification_id=specification.id,
                schema_version=authority.schema_version,
                plan_schema_version=authority.plan_schema_version,
                canonical_payload=authority.canonical_payload,
                warp_plan_digest=authority.warp_plan_digest,
                authority_digest=authority.authority_digest,
                origin_kind=authority.origin_kind.value,
                origin_reference=authority.origin_reference,
                origin_digest=authority.origin_digest,
                builder_version=authority.builder_version,
                builder_manifest_digest=authority.builder_manifest_digest,
            )
        )
        run = TransformRun(id=new_id(), variant_specification_id=specification.id, attempt=1)
        session.add(run)
    return run.id, normalized_storage


async def _pass_qa(
    sessions: async_sessionmaker[AsyncSession], qa_run_id: str, *, variant: bool = False
) -> None:
    async with sessions.begin() as session:
        await session.execute(
            update(SyntheticQARun)
            .where(SyntheticQARun.id == qa_run_id)
            .values(status="RUNNING", started_at=utcnow())
        )
        if variant:
            transform_id = await session.scalar(
                select(SyntheticQARun.transform_run_id).where(SyntheticQARun.id == qa_run_id)
            )
            assert transform_id is not None
            await session.execute(
                update(TransformRun)
                .where(TransformRun.id == transform_id)
                .values(status="MEASURING", measurement_started_at=utcnow())
            )
        session.add(
            SyntheticQAMeasurement(
                id=new_id(),
                qa_run_id=qa_run_id,
                measurement_kind="geometry_measurement",
                measurement_code="exactly_one_face",
                payload={"count": 1},
                payload_digest="4" * 64,
                algorithm_reference="mirror.fixture/face-count",
                algorithm_version="v1",
                confidence=1,
                hard_gate=True,
                threshold_outcome="PASSED",
                reason_code="exactly_one_face",
            )
        )
        now = utcnow()
        session.add_all(
            SyntheticQAReviewDecision(
                id=new_id(),
                qa_run_id=qa_run_id,
                review_kind=kind,
                decision="PASSED",
                reason_code=f"{kind}_passed",
                actor_reference="operator:m4-test",
                reviewed_at=now,
                created_at=utcnow(),
            )
            for kind in ("adult_presentation", "likeness_risk", "license_rights")
        )
    if not variant:
        async with sessions.begin() as session:
            await session.execute(
                update(SyntheticQARun)
                .where(SyntheticQARun.id == qa_run_id)
                .values(status="PASSED", finalized_at=utcnow())
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target_dimension", "control_dimensions", "classifications"),
    [
        ("unknown_width", ("nose_width",), {"nose_width": "READY"}),
        (
            "unsupported_width",
            ("nose_width",),
            {"unsupported_width": "UNSUPPORTED", "nose_width": "READY"},
        ),
        (
            "profile_depth",
            ("nose_width",),
            {"profile_depth": "REQUIRES_3D", "nose_width": "READY"},
        ),
        (
            "hair_texture",
            ("nose_width",),
            {"hair_texture": "STYLE_ONLY", "nose_width": "READY"},
        ),
        (
            "jaw_width",
            ("unsupported_control",),
            {"jaw_width": "EXPERIMENTAL", "unsupported_control": "UNSUPPORTED"},
        ),
    ],
)
async def test_persisted_nonresearchable_dimension_stops_before_any_io(
    tmp_path: Path,
    target_dimension: str,
    control_dimensions: tuple[str, ...],
    classifications: dict[str, str],
) -> None:
    async with _database() as sessions:
        private_root = tmp_path / "private"
        run_id, normalized_storage = await _authority(
            sessions,
            private_root,
            target_dimension=target_dimension,
            control_dimensions=control_dimensions,
            ontology_classifications=classifications,
            bypass_domain_gate=True,
        )
        read_counting_storage = _ReadCountingNormalizedStorage(normalized_storage)
        transform = _CountingTransform()
        service = SyntheticTransformService(
            session_factory=sessions,
            transform=transform,
            normalized_storage=read_counting_storage,
            variant_storage=LocalSyntheticVariantStorageProvider(root=private_root),
            now=utcnow,
        )

        with pytest.raises(TransformExecutionRejected) as rejected:
            await service.execute(transform_run_id=run_id)

        assert rejected.value.code == "variant_specification_not_researchable"
        assert read_counting_storage.reads == 0
        assert transform.calls == 0
        async with sessions() as session:
            run = await session.get(TransformRun, run_id)
            assert run is not None and run.status == "SPECIFIED"
            assert (
                await session.scalar(
                    select(func.count()).select_from(Asset).where(Asset.is_ai_modified)
                )
                == 0
            )


@pytest.mark.asyncio
async def test_transform_duplicate_delivery_and_variant_qa_complete_once(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        private_root = tmp_path / "private"
        run_id, normalized_storage = await _authority(sessions, private_root)
        transforms = SyntheticTransformService(
            session_factory=sessions,
            transform=_DeterministicTransform(),
            normalized_storage=normalized_storage,
            variant_storage=LocalSyntheticVariantStorageProvider(root=private_root),
            now=utcnow,
        )
        service = SyntheticM4OrchestrationService(
            session_factory=sessions, transforms=transforms, now=utcnow
        )
        message = await service.schedule_transform(
            transform_run_id=run_id, request_id="m4-transform-idempotent"
        )
        first = await service.execute_transform(message)
        second = await service.execute_transform(message)
        assert first.status == "variant_qa_pending"
        assert second.status == "no_op"
        assert first.result_asset_id is not None and first.qa_run_id is not None
        async with sessions() as session:
            job = await session.get(Job, message.job_id)
            assert job is not None and job.payload == {} and job.status == "succeeded"
            assert (
                await session.scalar(
                    select(func.count()).select_from(Asset).where(Asset.is_ai_modified)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(SyntheticQARun)
                    .where(SyntheticQARun.transform_run_id == run_id)
                )
                == 1
            )
        await _pass_qa(sessions, first.qa_run_id, variant=True)
        m3 = SyntheticM3OrchestrationService(
            session_factory=sessions,
            normalizer=_NoopNormalizer(),  # type: ignore[arg-type]
            now=utcnow,
        )
        qa_message = await m3.schedule_qa(qa_run_id=first.qa_run_id, request_id="m4-variant-qa")
        qa_result = await m3.execute_qa(qa_message)
        assert qa_result.status == "qa_passed" and qa_result.identity_id is None
        async with sessions() as session:
            run = await session.get(TransformRun, run_id)
            qa_run = await session.get(SyntheticQARun, first.qa_run_id)
            assert run is not None and run.status == "COMPLETED"
            assert qa_run is not None and qa_run.status == "PASSED"


@pytest.mark.asyncio
async def test_transform_cancellation_is_terminal_and_cleans_orphan(tmp_path: Path) -> None:
    async with _database() as sessions:
        private_root = tmp_path / "private"
        run_id, normalized_storage = await _authority(sessions, private_root)
        transforms = SyntheticTransformService(
            session_factory=sessions,
            transform=_DeterministicTransform(),
            normalized_storage=normalized_storage,
            variant_storage=LocalSyntheticVariantStorageProvider(root=private_root),
            now=utcnow,
        )
        service = SyntheticM4OrchestrationService(
            session_factory=sessions, transforms=transforms, now=utcnow
        )
        message = await service.schedule_transform(
            transform_run_id=run_id, request_id="m4-transform-cancel"
        )
        assert await service.cancel(transform_run_id=run_id, reason_code="operator_cancelled")
        assert not await service.cancel(transform_run_id=run_id, reason_code="operator_cancelled")
        assert (await service.execute_transform(message)).status == "no_op"
        assert await service.reconciliation_candidates() == ()
        async with sessions() as session:
            run = await session.get(TransformRun, run_id)
            job = await session.get(Job, message.job_id)
            assert run is not None and run.status == "CANCELLED"
            assert job is not None and job.status == "cancelled" and job.payload == {}


@pytest.mark.asyncio
async def test_transform_retry_exhaustion_preserves_attempts_and_fails_authority(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        private_root = tmp_path / "private"
        run_id, normalized_storage = await _authority(sessions, private_root)
        transforms = SyntheticTransformService(
            session_factory=sessions,
            transform=_UnavailableTransform(),
            normalized_storage=normalized_storage,
            variant_storage=LocalSyntheticVariantStorageProvider(root=private_root),
            now=utcnow,
        )
        service = SyntheticM4OrchestrationService(
            session_factory=sessions, transforms=transforms, now=utcnow
        )
        message = await service.schedule_transform(
            transform_run_id=run_id, request_id="m4-transform-retry"
        )
        for _ in range(3):
            with pytest.raises(M4RetryableError, match="remains retryable"):
                await service.execute_transform(message)
        exhausted = await service.execute_transform(message)
        assert exhausted.status == "transform_failed"
        assert (await service.execute_transform(message)).status == "no_op"
        async with sessions() as session:
            run = await session.get(TransformRun, run_id)
            job = await session.get(Job, message.job_id)
            attempts = list(
                (
                    await session.scalars(
                        select(JobAttempt)
                        .where(JobAttempt.job_id == message.job_id)
                        .order_by(JobAttempt.attempt)
                    )
                ).all()
            )
            assert run is not None and run.status == "FAILED"
            assert job is not None and job.status == "failed" and job.attempt_count == 4
            assert [attempt.status for attempt in attempts] == [
                "retryable_failure",
                "retryable_failure",
                "retryable_failure",
                "failed",
            ]


@pytest.mark.asyncio
async def test_reconcile_recovers_result_committed_before_job_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with _database() as sessions:
        private_root = tmp_path / "private"
        run_id, normalized_storage = await _authority(sessions, private_root)
        transforms = SyntheticTransformService(
            session_factory=sessions,
            transform=_DeterministicTransform(),
            normalized_storage=normalized_storage,
            variant_storage=LocalSyntheticVariantStorageProvider(root=private_root),
            now=utcnow,
        )
        service = SyntheticM4OrchestrationService(
            session_factory=sessions, transforms=transforms, now=utcnow
        )
        message = await service.schedule_transform(
            transform_run_id=run_id, request_id="m4-envelope-recovery"
        )
        original = service._complete_success

        async def injected_failure(*_: object, **__: object) -> bool:
            return False

        monkeypatch.setattr(service, "_complete_success", injected_failure)
        first = await service.execute_transform(message)
        assert first.status == "no_op"
        monkeypatch.setattr(service, "_complete_success", original)
        recovered = await service.execute_transform(message)
        assert recovered.status == "variant_qa_pending"
        assert recovered.result_asset_id is not None
        assert recovered.qa_run_id is not None
        async with sessions() as session:
            job = await session.get(Job, message.job_id)
            assert job is not None and job.status == "succeeded"


@pytest.mark.asyncio
async def test_storage_before_database_crash_reuses_receipt_without_duplicate_asset(
    tmp_path: Path,
) -> None:
    async with _database() as sessions:
        private_root = tmp_path / "private"
        run_id, normalized_storage = await _authority(sessions, private_root)
        variant_storage = LocalSyntheticVariantStorageProvider(root=private_root)
        transforms = SyntheticTransformService(
            session_factory=sessions,
            transform=_DeterministicTransform(),
            normalized_storage=normalized_storage,
            variant_storage=variant_storage,
            now=utcnow,
        )

        async def crash(_: AsyncSession) -> None:
            raise RuntimeError("injected storage-before-db crash")

        with pytest.raises(RuntimeError, match="injected"):
            await transforms.execute(transform_run_id=run_id, completion_guard=crash)
        recovered = await transforms.execute(transform_run_id=run_id)
        replay = await transforms.execute(transform_run_id=run_id)
        assert recovered.stored and not replay.stored
        assert recovered.result_asset_id == replay.result_asset_id
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count()).select_from(Asset).where(Asset.is_ai_modified)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(SyntheticQARun)
                    .where(SyntheticQARun.transform_run_id == run_id)
                )
                == 1
            )


@pytest.mark.asyncio
async def test_linux_celery_redis_transform_round_trip_remains_reference_only() -> None:
    if os.getenv("RUN_M4_CELERY_INTEGRATION") != "true":
        pytest.skip("NOT VERIFIED LOCALLY: private M4 Celery runtime unavailable")
    private_root = Path(os.environ["LOCAL_STORAGE_ROOT"])
    runtime_root = Path(os.environ["M4_TEST_GEOMETRY_RUNTIME_ROOT"])

    from mirror_worker.celery_adapter import process_synthetic_transform

    from mirror_api.providers.opencv_geometry import (
        ALGORITHM_VERSION,
        load_private_opencv_runtime,
    )

    runtime = load_private_opencv_runtime(runtime_root)
    async with _database() as sessions:
        run_id, normalized_storage = await _authority(
            sessions,
            private_root,
            algorithm_version=ALGORITHM_VERSION,
            runtime_manifest_digest=runtime.manifest_digest,
            output_policy_version="image-sanitizer-v1",
            raw_bytes=_pattern_png_bytes(),
        )
        setup_service = SyntheticM4OrchestrationService(
            session_factory=sessions,
            transforms=SyntheticTransformService(
                session_factory=sessions,
                transform=_DeterministicTransform(),
                normalized_storage=normalized_storage,
                variant_storage=LocalSyntheticVariantStorageProvider(root=private_root),
                now=utcnow,
            ),
            now=utcnow,
        )
        message = await setup_service.schedule_transform(
            transform_run_id=run_id, request_id="m4-celery-reference-only"
        )
        async_result = process_synthetic_transform.apply_async(args=[message.to_message()])
        result = await asyncio.to_thread(async_result.get, timeout=30)
        assert set(result) == {
            "transform_run_id",
            "job_id",
            "status",
            "result_asset_id",
            "qa_run_id",
        }
        assert result["transform_run_id"] == run_id
        assert result["job_id"] == message.job_id
        async with sessions() as session:
            job = await session.get(Job, message.job_id)
            run = await session.get(TransformRun, run_id)
        assert job is not None and run is not None
        assert result["status"] == "variant_qa_pending", (
            job.result_code,
            run.result_code,
        )
        assert result["result_asset_id"] is not None
        assert result["qa_run_id"] is not None
        assert str(runtime_root) not in json.dumps(result, sort_keys=True)
        assert job.status == "succeeded" and job.payload == {}
        assert run.status == "OUTPUT_STORED"
        assert run.result_asset_id == result["result_asset_id"]
