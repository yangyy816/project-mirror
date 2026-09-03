"""Real PostgreSQL coverage for Contract 04's analysis-scoped D11 flow.

The fixture deliberately uses only the admitted deterministic synthetic test
authority.  It never reads a D02 private namespace or provider output.
"""

from __future__ import annotations

import asyncio
import io
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_analysis_authority import (
    _analysis_context,
    _truncate_demo_analysis_test_authority,
)
from test_demo_analysis_service import _command as _analysis_command
from test_demo_analysis_service import _database as _analysis_database
from test_demo_analysis_service import _Fixture as _AnalysisFixture
from test_demo_analysis_service import _runtime_evidence
from test_demo_analysis_service import _service as _analysis_service
from test_demo_d02_generic_admission import _generic_admission_bundle
from test_demo_d02_targeted_m4_repair import (
    _Adapters as _ScreeningAdapters,
)
from test_demo_d02_targeted_m4_repair import (
    _compose as _targeted_successor,
)
from test_demo_d02_targeted_m4_repair import (
    _ordered_prepared_runtime,
)

from mirror_api import demo_d02_final_orchestrator as final_orchestrator
from mirror_api.demo_analysis_service import DemoAnalysisRepeatEvidence, DemoAnalysisRuntimeEvidence
from mirror_api.demo_d02_generic_admission_coordinator import (
    D02GenericAdmissionCoordinator,
    GenericAdmissionBundle,
)
from mirror_api.demo_editing_asset_loader import DemoAssetByteReference, DemoAssetLoadError
from mirror_api.demo_face_runtime import DimensionObservation
from mirror_api.demo_models import DemoQuestionnaireRun
from mirror_api.demo_posterior import PairwiseChoice
from mirror_api.demo_questionnaire_media import (
    DemoQuestionnaireMediaBytesUnavailable,
    DemoQuestionnaireMediaService,
    DemoQuestionnaireMediaUnavailable,
)
from mirror_api.demo_questionnaire_service import (
    CreateDemoAnalysisQuestionnaireRun,
    CreateDemoQuestionnaireResponse,
    DemoQuestionnaireConflict,
    DemoQuestionnaireNext,
    DemoQuestionnaireService,
    DemoQuestionnaireUnavailable,
)
from mirror_api.models import Asset, new_id


@dataclass(frozen=True)
class _RealFlowContext:
    actor_id: str
    analysis_run_id: str


@pytest.fixture(scope="module")
def event_loop_policy() -> Any:
    if os.name == "nt":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


def _jpeg(width: int, height: int) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), (20, 40, 60)).save(output, format="JPEG")
    return output.getvalue()


def _measurement_projection(position: int) -> dict[str, object]:
    dimensions = (
        "cheekbone_width",
        "chin_height",
        "eye_spacing",
        "jaw_width",
        "mouth_width",
        "nose_width",
    )
    return {
        "ordered_entries": [
            {
                "dimension_key": dimension,
                "support_state": "SUPPORTED",
                "unit": "FACE_HEIGHT_PPM",
                "unsupported_reason": None,
                "value_ppm": position * 10_000 + ordinal,
                "reliability_ppm": 900_000,
                "confidence_ppm": 800_000,
            }
            for ordinal, dimension in enumerate(dimensions, start=1)
        ]
    }


def _bank_runtime_evidence() -> DemoAnalysisRuntimeEvidence:
    evidence = _runtime_evidence()

    def add_eye_spacing(repeat: DemoAnalysisRepeatEvidence) -> DemoAnalysisRepeatEvidence:
        anchor_values = {"chin_height": 10_002, "eye_spacing": 10_003, "jaw_width": 10_004}
        dimensions = tuple(
            replace(item, value_ppm=anchor_values[item.dimension]) for item in repeat.dimensions
        )
        return replace(
            repeat,
            dimensions=tuple(
                sorted(
                    (
                        *dimensions,
                        DimensionObservation(
                            dimension="eye_spacing",
                            support_state="SUPPORTED",
                            value_ppm=anchor_values["eye_spacing"],
                            measurement_confidence_ppm=880_000,
                        ),
                    ),
                    key=lambda item: item.dimension,
                )
            ),
        )

    return replace(
        evidence,
        repeats=(
            add_eye_spacing(evidence.repeats[0]),
            add_eye_spacing(evidence.repeats[1]),
            add_eye_spacing(evidence.repeats[2]),
        ),
    )


def _exact_result_keys(bundle: GenericAdmissionBundle) -> GenericAdmissionBundle:
    assets: list[dict[str, object]] = []
    for original in bundle.asset_rows:
        row = dict(original)
        asset_id = cast(str, row["id"])
        if row["is_ai_modified"] is True:
            row["storage_key"] = f"internal-synthetic/v1/d02/result/{asset_id}"
        assets.append(row)
    return replace(bundle, asset_rows=tuple(assets))


@lru_cache(maxsize=1)
def _d04_compatible_report_template() -> dict[str, object]:
    successor = _targeted_successor()
    _, report_fields = _ordered_prepared_runtime()
    with patch.object(
        final_orchestrator,
        "PHashAdapter",
        lambda _: _ScreeningAdapters(deepcopy(report_fields)),
    ):
        result = final_orchestrator.finalize_runtime_evidence(
            prepared=successor.prepared,
            artifact_decisions=successor.artifact_decisions,
        )
    assert result.report_row["selected_dimension_keys"] == ["jaw_width", "eye_spacing"]
    return deepcopy(result.report_row)


@asynccontextmanager
async def _database(
    tmp_path: Path,
) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], _RealFlowContext]]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    sync_database_url = database_url.replace("+asyncpg", "+psycopg")
    sync_engine = create_engine(sync_database_url)
    try:
        with Session(sync_engine, expire_on_commit=False) as sync_session:
            _truncate_demo_analysis_test_authority(sync_session)
            actor, demo_session, identity = _analysis_context(sync_session)
            bundle = _exact_result_keys(
                _generic_admission_bundle(
                    sync_session,
                    tmp_path,
                    source_storage_key_factory=lambda asset_id, _position: (
                        f"internal-synthetic/v1/d02/source/{asset_id}"
                    ),
                    measurement_projection_factory=_measurement_projection,
                    report_template=_d04_compatible_report_template(),
                )
            )
            sync_session.commit()

        engine = create_async_engine(database_url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            admission = D02GenericAdmissionCoordinator(session_factory=sessions)
            await admission.admit(
                idempotency_key=f"d11-generic-admission-{new_id()}", bundle=bundle
            )
            analysis = _analysis_service(sessions)
            fixture = _AnalysisFixture(
                demo_actor_id=actor.id,
                demo_session_id=demo_session.id,
                demo_synthetic_identity_id=identity.id,
                source_asset_id=identity.formal_canonical_asset_id,
            )
            command = _analysis_command(
                fixture,
                key=f"d11-real-flow-analysis-{new_id()}",
            )
            accepted = await analysis.create(command)
            reservation = await analysis.claim(
                analysis_run_id=accepted.analysis_run_id,
                job_id=accepted.job_id,
                request_id=command.request_id,
            )
            assert reservation is not None
            publication = await analysis.complete(reservation, _bank_runtime_evidence())
            assert publication.self_state_id
            yield sessions, _RealFlowContext(actor.id, accepted.analysis_run_id)
        finally:
            await engine.dispose()
    finally:
        with Session(sync_engine) as sync_session:
            _truncate_demo_analysis_test_authority(sync_session)
        sync_engine.dispose()


def _create_command(
    *, actor_id: str, analysis_run_id: str, key: str
) -> CreateDemoAnalysisQuestionnaireRun:
    return CreateDemoAnalysisQuestionnaireRun(
        demo_actor_id=actor_id,
        analysis_run_id=analysis_run_id,
        idempotency_key=key,
        request_id=f"d11-real-flow-{new_id()}",
    )


@pytest.mark.asyncio
async def test_analysis_scoped_create_replays_and_concurrent_requests_have_one_run(
    tmp_path: Path,
) -> None:
    async with _database(tmp_path) as (sessions, context):
        service = DemoQuestionnaireService(session_factory=sessions)
        key = f"d11-analysis-create-{new_id()}"

        async with asyncio.TaskGroup() as group:
            first_task = group.create_task(
                service.create_for_analysis(
                    _create_command(
                        actor_id=context.actor_id,
                        analysis_run_id=context.analysis_run_id,
                        key=key,
                    )
                )
            )
            second_task = group.create_task(
                service.create_for_analysis(
                    _create_command(
                        actor_id=context.actor_id,
                        analysis_run_id=context.analysis_run_id,
                        key=key,
                    )
                )
            )
        first, second = first_task.result(), second_task.result()

        assert {first.questionnaire_run_id, second.questionnaire_run_id} == {
            first.questionnaire_run_id
        }
        assert {first.job_id, second.job_id} == {first.job_id}
        assert {first.replayed, second.replayed} == {False, True}

        async with sessions() as session:
            runs = tuple(
                (
                    await session.scalars(
                        select(DemoQuestionnaireRun).where(
                            DemoQuestionnaireRun.demo_actor_id == context.actor_id
                        )
                    )
                ).all()
            )
        assert len(runs) == 1
        assert runs[0].max_questions == 16


@pytest.mark.asyncio
async def test_analysis_scoped_create_fails_closed_when_no_generic_bank_is_admitted() -> None:
    """A completed D03 graph alone never authorizes a questionnaire bank."""
    async with _analysis_database() as (sessions, fixture):
        analysis = _analysis_service(sessions)
        command = _analysis_command(fixture, key=f"d11-no-bank-analysis-{new_id()}")
        accepted = await analysis.create(command)
        reservation = await analysis.claim(
            analysis_run_id=accepted.analysis_run_id,
            job_id=accepted.job_id,
            request_id=command.request_id,
        )
        assert reservation is not None
        await analysis.complete(reservation, _runtime_evidence())

        questionnaires = DemoQuestionnaireService(session_factory=sessions)
        with pytest.raises(DemoQuestionnaireUnavailable):
            await questionnaires.create_for_analysis(
                _create_command(
                    actor_id=fixture.demo_actor_id,
                    analysis_run_id=accepted.analysis_run_id,
                    key=f"d11-no-generic-bank-{new_id()}",
                )
            )


@pytest.mark.asyncio
async def test_analysis_scoped_create_rejects_expired_session(tmp_path: Path) -> None:
    async with _database(tmp_path) as (sessions, context):
        service = DemoQuestionnaireService(
            session_factory=sessions,
            now=lambda: datetime(2100, 1, 1, tzinfo=UTC),
        )
        with pytest.raises(DemoQuestionnaireUnavailable):
            await service.create_for_analysis(
                _create_command(
                    actor_id=context.actor_id,
                    analysis_run_id=context.analysis_run_id,
                    key=f"d11-expired-session-{new_id()}",
                )
            )


@pytest.mark.asyncio
async def test_analysis_scoped_create_rejects_wrong_actor_and_current_media_fails_closed(
    tmp_path: Path,
) -> None:
    async with _database(tmp_path) as (sessions, context):
        service = DemoQuestionnaireService(session_factory=sessions)

        with pytest.raises(DemoQuestionnaireUnavailable):
            await service.create_for_analysis(
                _create_command(
                    actor_id="f" * 32,
                    analysis_run_id=context.analysis_run_id,
                    key=f"d11-wrong-owner-{new_id()}",
                )
            )

        accepted = await service.create_for_analysis(
            _create_command(
                actor_id=context.actor_id,
                analysis_run_id=context.analysis_run_id,
                key=f"d11-media-current-{new_id()}",
            )
        )
        question = await service.next(
            demo_actor_id=context.actor_id,
            questionnaire_run_id=accepted.questionnaire_run_id,
        )
        assert isinstance(question, DemoQuestionnaireNext)

        # Cross-actor media lookup must fail before byte materialization.
        media = DemoQuestionnaireMediaService(
            session_factory=sessions,
            asset_loader=_NeverLoad(),
            questionnaire_service=service,
        )
        with pytest.raises(DemoQuestionnaireMediaUnavailable):
            await media.load(
                demo_actor_id="f" * 32,
                questionnaire_run_id=accepted.questionnaire_run_id,
                side="LEFT",
            )


@pytest.mark.asyncio
async def test_answered_or_stale_presentation_cannot_be_loaded(tmp_path: Path) -> None:
    async with _database(tmp_path) as (sessions, context):
        service = DemoQuestionnaireService(session_factory=sessions)
        accepted = await service.create_for_analysis(
            _create_command(
                actor_id=context.actor_id,
                analysis_run_id=context.analysis_run_id,
                key=f"d11-stale-media-{new_id()}",
            )
        )
        question = await service.next(
            demo_actor_id=context.actor_id,
            questionnaire_run_id=accepted.questionnaire_run_id,
        )
        assert isinstance(question, DemoQuestionnaireNext)
        await service.respond(
            CreateDemoQuestionnaireResponse(
                demo_actor_id=context.actor_id,
                questionnaire_run_id=accepted.questionnaire_run_id,
                selected_side=PairwiseChoice.LEFT,
                expected_step_sequence=question.snapshot.step_sequence,
                expected_run_version=question.snapshot.run_version,
                response_latency_ms=0,
                idempotency_key=f"d11-answer-{new_id()}",
            )
        )
        media = DemoQuestionnaireMediaService(
            session_factory=sessions,
            asset_loader=_NeverLoad(),
            questionnaire_service=service,
        )
        with pytest.raises(DemoQuestionnaireMediaUnavailable):
            await media.load(
                demo_actor_id=context.actor_id,
                questionnaire_run_id=accepted.questionnaire_run_id,
                side="RIGHT",
            )
        with pytest.raises(DemoQuestionnaireConflict):
            await service.respond(
                CreateDemoQuestionnaireResponse(
                    demo_actor_id=context.actor_id,
                    questionnaire_run_id=accepted.questionnaire_run_id,
                    selected_side=PairwiseChoice.RIGHT,
                    expected_step_sequence=question.snapshot.step_sequence,
                    expected_run_version=question.snapshot.run_version,
                    response_latency_ms=0,
                    idempotency_key=f"d11-stale-answer-{new_id()}",
                )
            )


@pytest.mark.asyncio
async def test_current_media_replays_exact_side_and_rejects_load_respond_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _database(tmp_path) as (sessions, context):
        service = DemoQuestionnaireService(session_factory=sessions)
        accepted = await service.create_for_analysis(
            _create_command(
                actor_id=context.actor_id,
                analysis_run_id=context.analysis_run_id,
                key=f"d11-media-success-{new_id()}",
            )
        )
        question = await service.next(
            demo_actor_id=context.actor_id,
            questionnaire_run_id=accepted.questionnaire_run_id,
        )
        assert isinstance(question, DemoQuestionnaireNext)
        async with sessions() as session:
            left = await session.get(Asset, question.presentation.left.result_asset_id)
        assert left is not None
        content = _jpeg(left.width, left.height)

        def decode_fixture(payload: bytes, *, expected_width: int, expected_height: int) -> object:
            with Image.open(io.BytesIO(payload)) as image:
                image.load()
                assert image.size == (expected_width, expected_height)
            return object()

        monkeypatch.setattr(
            "mirror_api.demo_questionnaire_media.decode_canonical_rgb_image",
            decode_fixture,
        )
        loader = _BytesLoader(content, left.id)
        media_service = DemoQuestionnaireMediaService(
            session_factory=sessions,
            asset_loader=loader,
            questionnaire_service=service,
        )
        loaded = await media_service.load(
            demo_actor_id=context.actor_id,
            questionnaire_run_id=accepted.questionnaire_run_id,
            side="LEFT",
        )
        assert loaded.content == content
        assert loaded.width == left.width
        assert loaded.height == left.height
        assert loader.loaded_asset_ids == [left.id]

        blocking = _BlockingLoader(content)
        raced_media = DemoQuestionnaireMediaService(
            session_factory=sessions,
            asset_loader=blocking,
            questionnaire_service=service,
        )
        task = asyncio.create_task(
            raced_media.load(
                demo_actor_id=context.actor_id,
                questionnaire_run_id=accepted.questionnaire_run_id,
                side="LEFT",
            )
        )
        await blocking.entered.wait()
        await service.respond(
            CreateDemoQuestionnaireResponse(
                demo_actor_id=context.actor_id,
                questionnaire_run_id=accepted.questionnaire_run_id,
                selected_side=PairwiseChoice.LEFT,
                expected_step_sequence=question.snapshot.step_sequence,
                expected_run_version=question.snapshot.run_version,
                response_latency_ms=0,
                idempotency_key=f"d11-media-race-response-{new_id()}",
            )
        )
        blocking.release.set()
        with pytest.raises(DemoQuestionnaireMediaUnavailable):
            await task


@pytest.mark.asyncio
async def test_current_media_maps_loader_and_decode_failures_to_bytes_unavailable(
    tmp_path: Path,
) -> None:
    async with _database(tmp_path) as (sessions, context):
        service = DemoQuestionnaireService(session_factory=sessions)
        accepted = await service.create_for_analysis(
            _create_command(
                actor_id=context.actor_id,
                analysis_run_id=context.analysis_run_id,
                key=f"d11-media-byte-failure-{new_id()}",
            )
        )
        question = await service.next(
            demo_actor_id=context.actor_id,
            questionnaire_run_id=accepted.questionnaire_run_id,
        )
        assert isinstance(question, DemoQuestionnaireNext)
        for loader in (
            _RejectingLoader("ASSET_BYTES_UNAVAILABLE"),
            _RejectingLoader("ASSET_DIGEST_MISMATCH"),
            _BytesLoader(b"not-a-jpeg", None),
            _BytesLoader(_jpeg(1, 1), None),
        ):
            media_service = DemoQuestionnaireMediaService(
                session_factory=sessions,
                asset_loader=loader,
                questionnaire_service=service,
            )
            with pytest.raises(DemoQuestionnaireMediaBytesUnavailable):
                await media_service.load(
                    demo_actor_id=context.actor_id,
                    questionnaire_run_id=accepted.questionnaire_run_id,
                    side="RIGHT",
                )


class _NeverLoad:
    async def load(self, reference: DemoAssetByteReference) -> bytes:
        raise AssertionError(f"media authority should reject before loading: {reference!r}")


class _BytesLoader:
    def __init__(self, content: bytes, expected_asset_id: str | None) -> None:
        self._content = content
        self._expected_asset_id = expected_asset_id
        self.loaded_asset_ids: list[str] = []

    async def load(self, reference: DemoAssetByteReference) -> bytes:
        asset_id = reference.asset_id
        if self._expected_asset_id is not None:
            assert asset_id == self._expected_asset_id
        self.loaded_asset_ids.append(asset_id)
        return self._content


class _BlockingLoader:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def load(self, reference: DemoAssetByteReference) -> bytes:
        del reference
        self.entered.set()
        await self.release.wait()
        return self._content


class _RejectingLoader:
    def __init__(self, code: str) -> None:
        self._code = code

    async def load(self, reference: DemoAssetByteReference) -> bytes:
        del reference
        raise DemoAssetLoadError(self._code, "fixture Asset bytes unavailable")
