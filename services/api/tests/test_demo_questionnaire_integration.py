from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import Any, cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_demo_analysis_service import (
    _command as _analysis_command,
)
from test_demo_analysis_service import (
    _database as _analysis_database,
)
from test_demo_analysis_service import (
    _runtime_evidence,
)
from test_demo_analysis_service import (
    _service as _analysis_service,
)
from test_demo_d02_r2_epoch2_admission import _bundle, _digest

from mirror_api.demo_analysis_service import DemoAnalysisPublication
from mirror_api.demo_d02_r2_epoch2_admission import D02R2Epoch2AdmissionCoordinator
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_models import (
    DemoCommandBinding,
    DemoQuestionnaireRun,
    DemoQuestionnaireStep,
    DemoQuestionPair,
)
from mirror_api.demo_posterior import PairwiseChoice
from mirror_api.demo_questionnaire_service import (
    DEMO_QUESTIONNAIRE_RESPONSE_OPERATION,
    CreateDemoQuestionnaireResponse,
    CreateDemoQuestionnaireRun,
    DemoQuestionnaireCompleted,
    DemoQuestionnaireConflict,
    DemoQuestionnaireNext,
    DemoQuestionnaireService,
)
from mirror_api.models import Job, JobAttempt, new_id


@dataclass(frozen=True)
class _QuestionnaireContext:
    actor_id: str
    session_id: str
    self_state_id: str
    question_bank_version: str


@asynccontextmanager
async def _database() -> AsyncIterator[
    tuple[async_sessionmaker[AsyncSession], _QuestionnaireContext]
]:
    async with _analysis_database() as (sessions, analysis_fixture):
        bundle = _bundle()
        admission = D02R2Epoch2AdmissionCoordinator(session_factory=sessions)
        await admission.admit(
            idempotency_key=_digest(f"d04b-admission-{new_id()}"),
            bundle=bundle,
        )

        analysis = _analysis_service(sessions)
        analysis_command = _analysis_command(
            analysis_fixture,
            key=f"d04b-self-state-{new_id()}",
        )
        accepted = await analysis.create(analysis_command)
        reservation = await analysis.claim(
            analysis_run_id=accepted.analysis_run_id,
            job_id=accepted.job_id,
            request_id=analysis_command.request_id,
        )
        assert reservation is not None
        source_manifest = cast(
            list[Mapping[str, Any]],
            cast(Mapping[str, Any], bundle.report_row["report_payload"])["ordered_source_manifest"],
        )
        supported_measurements = cast(
            list[Mapping[str, Any]], source_manifest[0]["ordered_supported_measurements"]
        )
        source_anchor = {
            cast(str, item["dimension_key"]): cast(int, item["value_ppm"])
            for item in supported_measurements
        }
        runtime_evidence = _runtime_evidence()
        runtime_evidence = replace(
            runtime_evidence,
            repeats=tuple(
                replace(
                    repeat,
                    dimensions=tuple(
                        replace(
                            dimension,
                            value_ppm=source_anchor[dimension.dimension],
                        )
                        for dimension in repeat.dimensions
                    ),
                )
                for repeat in runtime_evidence.repeats
            ),
        )
        publication = cast(
            DemoAnalysisPublication,
            await analysis.complete(reservation, runtime_evidence),
        )

        yield (
            sessions,
            _QuestionnaireContext(
                actor_id=analysis_fixture.demo_actor_id,
                session_id=analysis_fixture.demo_session_id,
                self_state_id=publication.self_state_id,
                question_bank_version=cast(str, bundle.question_bank_row["version"]),
            ),
        )


def _create_command(
    context: _QuestionnaireContext,
    *,
    key: str,
    max_questions: int = 12,
) -> CreateDemoQuestionnaireRun:
    return CreateDemoQuestionnaireRun(
        demo_actor_id=context.actor_id,
        demo_session_id=context.session_id,
        self_state_id=context.self_state_id,
        question_bank_version=context.question_bank_version,
        max_questions=max_questions,
        idempotency_key=key,
        request_id=f"d04b-request-{new_id()}",
    )


async def _steps(
    sessions: async_sessionmaker[AsyncSession], run_id: str
) -> tuple[DemoQuestionnaireStep, ...]:
    async with sessions() as session:
        return tuple(
            (
                await session.scalars(
                    select(DemoQuestionnaireStep)
                    .where(DemoQuestionnaireStep.questionnaire_run_id == run_id)
                    .order_by(DemoQuestionnaireStep.event_sequence)
                )
            ).all()
        )


async def _assert_presentation_matches_admitted_pair(
    sessions: async_sessionmaker[AsyncSession], question: DemoQuestionnaireNext
) -> None:
    async with sessions() as session:
        pair = await session.get(DemoQuestionPair, question.question_pair_id)
    assert pair is not None
    presentation = question.presentation
    assert presentation.question_pair_digest == pair.content_digest
    assert presentation.source_asset_id == pair.source_asset_id
    assert presentation.source_checksum == pair.source_asset_sha256
    assert presentation.left.result_asset_id == pair.left_asset_id
    assert presentation.left.result_checksum == pair.left_asset_sha256
    assert presentation.left.measured_delta_ppm == pair.left_delta_ppm
    assert presentation.right.result_asset_id == pair.right_asset_id
    assert presentation.right.result_checksum == pair.right_asset_sha256
    assert presentation.right.measured_delta_ppm == pair.right_delta_ppm

    record = cast(Mapping[str, Any], pair.qa_payload["pair_screening_record_payload"])
    record_payload = cast(Mapping[str, Any], record["pair_screening_record_payload"])
    left = cast(Mapping[str, Any], record_payload["left"])
    right = cast(Mapping[str, Any], record_payload["right"])
    assert presentation.left.result_lineage_digest == left["lineage_digest"]
    assert presentation.right.result_lineage_digest == right["lineage_digest"]


@pytest.mark.asyncio
async def test_twelve_skips_stop_at_run_budget_and_complete_one_job_attempt() -> None:
    async with _database() as (sessions, context):
        questionnaires = DemoQuestionnaireService(session_factory=sessions)
        jobs = DemoJobService(session_factory=sessions)
        accepted = await questionnaires.create(
            _create_command(context, key=f"d04b-twelve-skip-{new_id()}")
        )

        pending = await jobs.get(demo_actor_id=context.actor_id, job_id=accepted.job_id)
        assert pending.status == "PENDING"

        response_ids: list[str] = []
        for index in range(12):
            question = await questionnaires.next(
                demo_actor_id=context.actor_id,
                questionnaire_run_id=accepted.questionnaire_run_id,
            )
            assert isinstance(question, DemoQuestionnaireNext)
            assert question.snapshot.step_number == index + 1
            await _assert_presentation_matches_admitted_pair(sessions, question)

            if index == 0:
                running = await jobs.get(
                    demo_actor_id=context.actor_id,
                    job_id=accepted.job_id,
                )
                assert running.status == "RUNNING"

            response_command = CreateDemoQuestionnaireResponse(
                demo_actor_id=context.actor_id,
                questionnaire_run_id=accepted.questionnaire_run_id,
                selected_side=PairwiseChoice.SKIP,
                expected_step_sequence=question.snapshot.step_sequence,
                expected_run_version=question.snapshot.run_version,
                response_latency_ms=10 + index,
                idempotency_key=f"d04b-response-{index}-{accepted.questionnaire_run_id}",
            )
            response = await questionnaires.respond(response_command)
            response_ids.append(response.step_id)
            if index == 0:
                replay = await questionnaires.respond(response_command)
                assert replay == response

        completed = await questionnaires.next(
            demo_actor_id=context.actor_id,
            questionnaire_run_id=accepted.questionnaire_run_id,
        )
        assert isinstance(completed, DemoQuestionnaireCompleted)
        assert len(set(response_ids)) == 12

        terminal = await jobs.get(demo_actor_id=context.actor_id, job_id=accepted.job_id)
        assert terminal.status == "COMPLETED"
        assert terminal.result_code == "FAIL_CLOSED_COVERAGE_UNMET_AT_MAXIMUM"

        persisted_steps = await _steps(sessions, accepted.questionnaire_run_id)
        assert [step.event_type for step in persisted_steps].count("PRESENTED") == 12
        assert [step.event_type for step in persisted_steps].count("RESPONDED") == 12
        assert [step.event_type for step in persisted_steps].count("STOPPED") == 1
        posterior_value_fields = {
            "posterior_mean_ppm",
            "laplace_sd_ppm",
            "posterior_sd_ppm",
            "confidence_ppm",
            "consistency_ppm",
        }
        for step in persisted_steps:
            if step.event_type != "RESPONDED":
                continue
            assert set(step.posterior_before) == set(step.posterior_after)
            for dimension in step.posterior_before:
                before = cast(Mapping[str, Any], step.posterior_before[dimension])
                after = cast(Mapping[str, Any], step.posterior_after[dimension])
                assert {field: before[field] for field in posterior_value_fields} == {
                    field: after[field] for field in posterior_value_fields
                }

        async with sessions() as session:
            attempts = tuple(
                (
                    await session.scalars(
                        select(JobAttempt).where(JobAttempt.job_id == accepted.job_id)
                    )
                ).all()
            )
            response_bindings = tuple(
                (
                    await session.scalars(
                        select(DemoCommandBinding).where(
                            DemoCommandBinding.demo_actor_id == context.actor_id,
                            DemoCommandBinding.endpoint_operation
                            == DEMO_QUESTIONNAIRE_RESPONSE_OPERATION,
                        )
                    )
                ).all()
            )
        assert len(attempts) == 1
        assert attempts[0].attempt == 1
        assert attempts[0].status == "COMPLETED"
        assert attempts[0].result_code == terminal.result_code
        assert len(response_bindings) == 12

        with pytest.raises(DemoQuestionnaireConflict):
            await questionnaires.respond(
                CreateDemoQuestionnaireResponse(
                    demo_actor_id=context.actor_id,
                    questionnaire_run_id=accepted.questionnaire_run_id,
                    selected_side=PairwiseChoice.SKIP,
                    expected_step_sequence=24,
                    expected_run_version=24,
                    response_latency_ms=1,
                    idempotency_key=f"d04b-after-stop-{new_id()}",
                )
            )


@pytest.mark.asyncio
async def test_pending_and_running_cancellation_prevent_questionnaire_progress() -> None:
    async with _database() as (sessions, context):
        questionnaires = DemoQuestionnaireService(session_factory=sessions)
        jobs = DemoJobService(session_factory=sessions)

        pending = await questionnaires.create(
            _create_command(context, key=f"d04b-cancel-pending-{new_id()}")
        )
        cancelled_pending = await jobs.cancel(
            demo_actor_id=context.actor_id,
            job_id=pending.job_id,
            expected_status="PENDING",
            reason="USER_REQUEST",
            idempotency_key=f"d04b-cancel-command-{new_id()}",
        )
        assert cancelled_pending.status == "CANCELLED"
        with pytest.raises(DemoQuestionnaireConflict):
            await questionnaires.next(
                demo_actor_id=context.actor_id,
                questionnaire_run_id=pending.questionnaire_run_id,
            )
        assert await _steps(sessions, pending.questionnaire_run_id) == ()

        running = await questionnaires.create(
            _create_command(context, key=f"d04b-cancel-running-{new_id()}")
        )
        open_question = await questionnaires.next(
            demo_actor_id=context.actor_id,
            questionnaire_run_id=running.questionnaire_run_id,
        )
        assert isinstance(open_question, DemoQuestionnaireNext)
        cancelled_running = await jobs.cancel(
            demo_actor_id=context.actor_id,
            job_id=running.job_id,
            expected_status="RUNNING",
            reason="USER_REQUEST",
            idempotency_key=f"d04b-cancel-command-{new_id()}",
        )
        assert cancelled_running.status == "CANCELLED"
        with pytest.raises(DemoQuestionnaireConflict):
            await questionnaires.next(
                demo_actor_id=context.actor_id,
                questionnaire_run_id=running.questionnaire_run_id,
            )
        with pytest.raises(DemoQuestionnaireConflict):
            await questionnaires.respond(
                CreateDemoQuestionnaireResponse(
                    demo_actor_id=context.actor_id,
                    questionnaire_run_id=running.questionnaire_run_id,
                    selected_side=PairwiseChoice.RIGHT,
                    expected_step_sequence=open_question.snapshot.step_sequence,
                    expected_run_version=open_question.snapshot.run_version,
                    response_latency_ms=25,
                    idempotency_key=f"d04b-cancelled-response-{new_id()}",
                )
            )

        pending_steps = await _steps(sessions, pending.questionnaire_run_id)
        running_steps = await _steps(sessions, running.questionnaire_run_id)
        assert pending_steps == ()
        assert [step.event_type for step in running_steps] == ["PRESENTED"]

        async with sessions() as session:
            pending_job = await session.get(Job, pending.job_id)
            running_job = await session.get(Job, running.job_id)
            attempts = tuple(
                (
                    await session.scalars(
                        select(JobAttempt).where(
                            JobAttempt.job_id.in_((pending.job_id, running.job_id))
                        )
                    )
                ).all()
            )
            runs = tuple(
                (
                    await session.scalars(
                        select(DemoQuestionnaireRun).where(
                            DemoQuestionnaireRun.id.in_(
                                (pending.questionnaire_run_id, running.questionnaire_run_id)
                            )
                        )
                    )
                ).all()
            )
        assert pending_job is not None and pending_job.attempt_count == 0
        assert running_job is not None and running_job.attempt_count == 1
        assert len(attempts) == 1 and attempts[0].status == "CANCELLED"
        assert len(runs) == 2
