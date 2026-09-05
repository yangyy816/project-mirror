"""One-shot D12 lifecycle checks on an isolated actor and the existing real worker.

Private startup injects settings. No test fixtures, table cleanup, asset bytes,
runtime factories, or service startup are performed here. Failure stops the run;
an existing actor is never silently restarted.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit

from celery import Celery
from mirror_api.config import Settings
from mirror_api.demo_analysis_dependencies import accepted_demo_analysis_configuration
from mirror_api.demo_analysis_service import CreateDemoSessionAnalysis, DemoAnalysisService
from mirror_api.demo_analysis_task_contract import DemoAnalysisTaskMessage
from mirror_api.demo_context_queue_service import (
    CreateDemoContextCompilation,
    DemoContextCompilationAccepted,
    DemoContextQueueService,
    DemoContextQueueUnavailable,
)
from mirror_api.demo_context_task_contract import DemoContextTaskMessage
from mirror_api.demo_idempotency import canonical_json_bytes
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_memory_service import (
    DemoMemoryService,
    DemoMemoryUnavailable,
    RebuildDemoAestheticProfile,
)
from mirror_api.demo_memory_task_contract import DemoMemoryTaskMessage
from mirror_api.demo_models import (
    DemoAcceptedVisualEpisode,
    DemoActor,
    DemoAestheticProfile,
    DemoAnalysisRun,
    DemoContextCompilation,
    DemoContextCompileRequest,
    DemoContextCompileResult,
    DemoImageVersion,
    DemoJobBinding,
    DemoPreferenceEvent,
    DemoReferenceProfile,
)
from mirror_api.demo_posterior import PairwiseChoice
from mirror_api.demo_preference_ledger import (
    AppendDemoPreferenceEvent,
    append_demo_preference_event,
)
from mirror_api.demo_preference_ledger import (
    DemoPreferenceEventType as EventType,
)
from mirror_api.demo_preference_ledger import (
    DemoPreferenceSourceType as SourceType,
)
from mirror_api.demo_preference_ledger import (
    DemoPreferenceTargetType as TargetType,
)
from mirror_api.demo_profile_commands import (
    DEMO_PROFILE_COMPILER_VERSION,
    CreateDemoProfileCompilation,
    DemoProfileCommandService,
)
from mirror_api.demo_profile_task_contract import DemoProfileTaskMessage
from mirror_api.demo_questionnaire_service import (
    CreateDemoAnalysisQuestionnaireRun,
    CreateDemoQuestionnaireResponse,
    DemoQuestionnaireService,
)
from mirror_api.demo_session_service import CreateDemoSession, DemoSessionService
from mirror_api.models import Job
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TASK = "P3_P7_D12_ISOLATED_LIFECYCLE_20260905"
ACTOR_ID = hashlib.sha256(TASK.encode()).hexdigest()[:32]
PROTECTED_ACTOR_ID = "0d515974d5654fe287ebe914a2d8cc53"
IDENTITY_ID = "968013d585fe36238d56904a61f69966"
STAGE = "INITIALIZE"


def digest(label: str) -> str:
    return hashlib.sha256(f"{TASK}/{label}".encode()).hexdigest()


class CheckFailure(RuntimeError):
    """Only first-party constant check codes may cross the public output boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise CheckFailure(code)


def report(stage: str, **facts: Any) -> None:
    global STAGE
    STAGE = stage
    print(json.dumps({"stage": stage, **facts}), flush=True)


async def run(*, resume_d05: bool = False, resume_context: bool = False) -> None:
    settings = Settings(_env_file=None)
    require(settings.app_env != "production", "NON_PRODUCTION_ONLY")
    require(
        make_url(settings.database_url).host in {"localhost", "127.0.0.1", "::1"},
        "LOCAL_DATABASE_ONLY",
    )
    require(
        urlsplit(settings.redis_url).hostname in {"localhost", "127.0.0.1", "::1"},
        "LOCAL_BROKER_ONLY",
    )
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    memory = DemoMemoryService(session_factory=sessions)
    queue = DemoContextQueueService(session_factory=sessions)
    jobs = DemoJobService(session_factory=sessions)
    broker = Celery("mirror-d12-isolated", broker=settings.redis_url, backend=settings.redis_url)
    broker.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json")

    async def protected_snapshot() -> dict[str, list[tuple[str, str]]]:
        async with sessions() as db:
            return {
                model.__tablename__: list(
                    (
                        await db.execute(
                            select(model.id, model.content_digest)
                            .where(model.demo_actor_id == PROTECTED_ACTOR_ID)
                            .order_by(model.id)
                        )
                    ).tuples()
                )
                for model in (
                    DemoPreferenceEvent,
                    DemoAcceptedVisualEpisode,
                    DemoReferenceProfile,
                    DemoImageVersion,
                )
            }

    async def deliver(task: str, message: dict[str, str]) -> None:
        # Await the actual Celery result, including terminal duplicate deliveries.
        result = await asyncio.to_thread(
            broker.send_task, task, args=[message], queue="mirror.demo"
        )
        outcome = await asyncio.to_thread(result.get, timeout=45)
        require(isinstance(outcome, dict), "WORKER_RESULT_SHAPE")

    async def materialize_d05(session_id: str) -> None:
        report("ISOLATED_D05_SOURCE_RUNNING", actor_id=ACTOR_ID)
        analysis = DemoAnalysisService(
            session_factory=sessions, configuration=accepted_demo_analysis_configuration()
        )
        accepted = await analysis.create_for_session(
            CreateDemoSessionAnalysis(
                ACTOR_ID, session_id, digest("isolated-analysis"), "d12-isolated-analysis"
            )
        )
        await deliver(
            "mirror.demo_analysis.process",
            DemoAnalysisTaskMessage(
                accepted.analysis_run_id, accepted.job_id, accepted.request_id
            ).to_message(),
        )
        job = await jobs.get(demo_actor_id=ACTOR_ID, job_id=accepted.job_id)
        require(
            job.status == "COMPLETED" and job.result_code == "SUPPORTED",
            "ISOLATED_ANALYSIS_NOT_SUPPORTED",
        )
        questionnaires = DemoQuestionnaireService(session_factory=sessions)
        run = await questionnaires.create_for_analysis(
            CreateDemoAnalysisQuestionnaireRun(
                ACTOR_ID,
                accepted.analysis_run_id,
                digest("isolated-questionnaire"),
                "d12-isolated-questionnaire",
            )
        )
        answers = 0
        for ordinal in range(17):
            question = await questionnaires.next(
                demo_actor_id=ACTOR_ID, questionnaire_run_id=run.questionnaire_run_id
            )
            if question.kind == "COMPLETED":
                break
            require(ordinal < 16, "QUESTION_BUDGET_EXCEEDED")
            await questionnaires.respond(
                CreateDemoQuestionnaireResponse(
                    ACTOR_ID,
                    run.questionnaire_run_id,
                    PairwiseChoice.LEFT,
                    question.snapshot.step_sequence,
                    question.snapshot.run_version,
                    0,
                    digest(f"isolated-answer-{ordinal}"),
                )
            )
            answers += 1
        require(question.kind == "COMPLETED", "ISOLATED_QUESTIONNAIRE_INCOMPLETE")
        profiles = DemoProfileCommandService(session_factory=sessions)
        compiled = await profiles.create_compilation(
            CreateDemoProfileCompilation(
                ACTOR_ID,
                session_id,
                DEMO_PROFILE_COMPILER_VERSION,
                digest("isolated-d05"),
                "d12-isolated-d05",
            )
        )
        await deliver(
            "mirror.demo_profile.compile",
            DemoProfileTaskMessage(ACTOR_ID, compiled.job_id, compiled.request_id).to_message(),
        )
        profile_job = await jobs.get(demo_actor_id=ACTOR_ID, job_id=compiled.job_id)
        require(profile_job.status == "COMPLETED", "ISOLATED_D05_NOT_COMPLETED")
        report(
            "ISOLATED_D05_SOURCE_PASS",
            analysis_job_id=accepted.job_id,
            profile_job_id=compiled.job_id,
            automated_responses=answers,
            m3=3,
            m4=0,
        )

    async def append(
        event_type: EventType,
        *,
        target_type: TargetType | None = None,
        target_id: str | None = None,
        session_id: str | None = None,
        signal: dict[str, Any] | None = None,
    ) -> DemoPreferenceEvent:
        async with sessions() as db, db.begin():
            result = await append_demo_preference_event(
                db,
                AppendDemoPreferenceEvent(
                    ACTOR_ID,
                    session_id,
                    event_type,
                    SourceType.SYSTEM_LIFECYCLE if target_type else SourceType.EXPLICIT_USER_ACTION,
                    target_type,
                    target_id,
                    signal or {},
                    datetime.now(UTC),
                ),
            )
            return result.event

    async def rebuild(
        label: str,
        reason: Literal["USER_REQUEST", "RESET", "ROLLBACK"] = "USER_REQUEST",
    ) -> DemoAestheticProfile:
        accepted = await memory.admit_rebuild(
            RebuildDemoAestheticProfile(ACTOR_ID, reason, digest(label), f"d12-{label}")
        )
        await deliver(
            "mirror.demo_memory.rebuild",
            DemoMemoryTaskMessage(ACTOR_ID, accepted.job_id, accepted.request_id).to_message(),
        )
        job = await jobs.get(demo_actor_id=ACTOR_ID, job_id=accepted.job_id)
        require(job.status == "COMPLETED", "REBUILD_NOT_COMPLETED")
        async with sessions() as db:
            profile = await db.scalar(
                select(DemoAestheticProfile)
                .join(DemoJobBinding, DemoJobBinding.id == DemoAestheticProfile.demo_job_binding_id)
                .where(
                    DemoJobBinding.job_id == accepted.job_id,
                    DemoAestheticProfile.demo_actor_id == ACTOR_ID,
                )
            )
            require(profile is not None, "REBUILD_PROFILE_MISSING")
            assert profile is not None
            return profile

    async def admit_context(
        label: str,
        profile_id: str,
        session_id: str,
    ) -> DemoContextCompilationAccepted:
        return await queue.admit(
            CreateDemoContextCompilation(
                ACTOR_ID,
                session_id,
                profile_id,
                digest(f"instruction-{label}"),
                datetime.now(UTC),
                digest(label),
                f"d12-{label}",
            )
        )

    def message(accepted: DemoContextCompilationAccepted) -> dict[str, str]:
        return DemoContextTaskMessage(
            ACTOR_ID, accepted.job_id, accepted.context_request_id, accepted.request_id
        ).to_message()

    async def context(
        label: str,
        profile_id: str,
        session_id: str,
    ) -> tuple[DemoContextCompilationAccepted, DemoContextCompilation]:
        accepted = await admit_context(label, profile_id, session_id)
        await deliver("mirror.demo_context.compile", message(accepted))
        job = await jobs.get(demo_actor_id=ACTOR_ID, job_id=accepted.job_id)
        require(job.status == "COMPLETED", "CONTEXT_NOT_COMPLETED")
        async with sessions() as db:
            row = await db.scalar(
                select(DemoContextCompilation)
                .join(
                    DemoJobBinding, DemoJobBinding.id == DemoContextCompilation.demo_job_binding_id
                )
                .where(
                    DemoJobBinding.job_id == accepted.job_id,
                    DemoContextCompilation.demo_actor_id == ACTOR_ID,
                )
            )
            require(row is not None, "CONTEXT_MISSING")
            assert row is not None
            return accepted, row

    try:
        before = await protected_snapshot()
        require(len(before["demo_accepted_visual_episodes"]) >= 1, "LIVE_DEMO_BASELINE_MISSING")
        now = datetime.now(UTC)
        payload = {
            "actor_kind": "AUTOMATED_TEST",
            "authority_at": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "credential_key_id": digest("UNAUTHENTICATED_TEST_ACTOR"),
        }
        schema = "mirror.demo/DemoActor/v1"
        async with sessions() as db, db.begin():
            existing = await db.get(DemoActor, ACTOR_ID)
            if resume_d05 or resume_context:
                require(
                    existing is not None
                    and existing.actor_kind == "AUTOMATED_TEST"
                    and existing.credential_key_id == payload["credential_key_id"],
                    "EXACT_ISOLATED_OWNER_REQUIRED",
                )
                old_job = await db.get(Job, "9415b90fb06240818bda8b8c4c64b6ea")
                require(
                    old_job is not None
                    and old_job.status == "REJECTED"
                    and old_job.result_code == "PROFILE_REJECTED",
                    "EXACT_FAILED_CHECKPOINT_REQUIRED",
                )
                for model, expected_count in (
                    (DemoAnalysisRun, 1 if resume_context else 0),
                    (DemoAestheticProfile, 2 if resume_context else 0),
                ):
                    require(
                        await db.scalar(
                            select(func.count())
                            .select_from(model)
                            .where(model.demo_actor_id == ACTOR_ID)
                        )
                        == expected_count,
                        "RESUME_ALREADY_ADVANCED",
                    )
            else:
                require(existing is None, "ISOLATED_RUN_ALREADY_INITIALIZED")
                db.add(
                    DemoActor(
                        id=ACTOR_ID,
                        schema_version=schema,
                        canonical_payload=payload,
                        content_digest=hashlib.sha256(
                            schema.encode() + b"\n" + canonical_json_bytes(payload)
                        ).hexdigest(),
                        created_at=now,
                        actor_kind="AUTOMATED_TEST",
                        credential_key_id=payload["credential_key_id"],
                        authority_at=now,
                    )
                )
        session_service = DemoSessionService(session_factory=sessions)
        first = await session_service.create(
            CreateDemoSession(
                ACTOR_ID, IDENTITY_ID, digest("session-first-seed"), digest("session-first")
            )
        )
        second = await session_service.create(
            CreateDemoSession(
                ACTOR_ID, IDENTITY_ID, digest("session-second-seed"), digest("session-second")
            )
        )
        report(
            "ISOLATED_ACTOR_RECOVERED"
            if resume_d05 or resume_context
            else "ISOLATED_ACTOR_CREATED",
            actor_id=ACTOR_ID,
            sessions=2,
        )
        if resume_d05 or resume_context:
            async with sessions() as db:
                events = list(
                    await db.scalars(
                        select(DemoPreferenceEvent)
                        .where(DemoPreferenceEvent.demo_actor_id == ACTOR_ID)
                        .order_by(DemoPreferenceEvent.event_sequence)
                    )
                )
                require(
                    len(events) == (2 if resume_context else 1)
                    and events[0].event_type == "EXPLICIT_STYLE_SELECTION"
                    and events[0].signal == {"style_key": "d12_test"},
                    "EXACT_SEED_REQUIRED",
                )
                seed = events[0]
        else:
            seed = await append(
                EventType.EXPLICIT_STYLE_SELECTION, signal={"style_key": "d12_test"}
            )
        if resume_context:
            override = events[1]
            require(
                override.event_type == "TEMPORARY_SESSION_OVERRIDE"
                and override.demo_session_id == first.session_id,
                "EXACT_OVERRIDE_REQUIRED",
            )
            async with sessions() as db:
                profiles = list(
                    await db.scalars(
                        select(DemoAestheticProfile)
                        .where(DemoAestheticProfile.demo_actor_id == ACTOR_ID)
                        .order_by(DemoAestheticProfile.generation)
                    )
                )
                baseline, current = profiles
                job = await db.get(Job, "9b0eed347a0e42a680f4f4df70b9ce42")
                require(job is not None and job.status == "COMPLETED", "EXACT_CONTEXT_JOB_REQUIRED")
                assert job is not None
                request = await db.scalar(
                    select(DemoContextCompileRequest)
                    .join(
                        DemoJobBinding,
                        DemoJobBinding.id == DemoContextCompileRequest.demo_job_binding_id,
                    )
                    .where(
                        DemoJobBinding.job_id == job.id,
                        DemoContextCompileRequest.demo_actor_id == ACTOR_ID,
                    )
                )
                require(request is not None, "EXACT_CONTEXT_REQUEST_REQUIRED")
                assert request is not None
                stored_context = await db.scalar(
                    select(DemoContextCompilation).where(
                        DemoContextCompilation.demo_job_binding_id == request.demo_job_binding_id
                    )
                )
                require(
                    stored_context is not None
                    and stored_context.aesthetic_profile_id == current.id,
                    "EXACT_CONTEXT_REQUIRED",
                )
                assert stored_context is not None
                recalled = stored_context
                completed = DemoContextCompilationAccepted(job.id, request.id, job.request_id, True)
        else:
            await materialize_d05(first.session_id)
            baseline = await rebuild("baseline-with-legal-d05")
            override = await append(
                EventType.TEMPORARY_SESSION_OVERRIDE,
                session_id=first.session_id,
                signal={"dimension_key": "jaw_width", "value_ppm": 1000},
            )
            current = await rebuild("with-override")
            completed, recalled = await context("next-session", current.id, second.session_id)
        require(override.content_digest not in current.evidence_digests, "OVERRIDE_LEARNED")
        require(
            override.content_digest not in {x["digest"] for x in recalled.selected_evidence},
            "OVERRIDE_PROPAGATED",
        )
        require(
            {
                x["reason"]
                for x in recalled.rejected_evidence
                if x["digest"] == override.content_digest
            }
            == {"SESSION_SCOPE_MISMATCH"},
            "OVERRIDE_EXCLUSION_MISSING",
        )
        # A rejected override is not selected cross-session persistent evidence.
        expected_cross_session = any(
            entry.get("source_session_id") not in {None, second.session_id}
            for entry in recalled.selected_evidence
        )
        require(
            recalled.trace_payload["next_session_recall"] is expected_cross_session,
            "NEXT_SESSION_TRACE_INCONSISTENT",
        )
        await memory.recall_context(
            demo_actor_id=ACTOR_ID,
            demo_session_id=second.session_id,
            recall_at=recalled.context_as_of_time if resume_context else datetime.now(UTC),
        )
        report(
            "NEXT_SESSION_OVERRIDE_EXCLUSION_PASS", profile_id=current.id, context_id=recalled.id
        )
        async with sessions() as db:
            completed_job = await db.get(Job, completed.job_id)
            assert completed_job is not None
            attempts = completed_job.attempt_count
        await deliver("mirror.demo_context.compile", message(completed))
        async with sessions() as db:
            replayed_job = await db.get(Job, completed.job_id)
            assert replayed_job is not None
            require(replayed_job.attempt_count == attempts, "REDELIVERY_ADDED_ATTEMPT")
            require(
                await db.scalar(
                    select(func.count())
                    .select_from(DemoContextCompileResult)
                    .where(
                        DemoContextCompileResult.compile_request_id == completed.context_request_id
                    )
                )
                == 1,
                "REDELIVERY_CARDINALITY",
            )
        if second.expires_at <= datetime.now(UTC) + timedelta(minutes=3):
            second = await session_service.create(
                CreateDemoSession(
                    ACTOR_ID,
                    IDENTITY_ID,
                    digest("lifecycle-forward-seed"),
                    digest("lifecycle-forward-session"),
                )
            )
            report(
                "FORWARD_LIFECYCLE_SESSION_CREATED_OLD_EXPIRY_UNCHANGED",
                session_id=second.session_id,
            )
        cancelled = await admit_context("cancel-before-dispatch", current.id, second.session_id)
        await jobs.cancel(
            demo_actor_id=ACTOR_ID,
            job_id=cancelled.job_id,
            expected_status="PENDING",
            reason="USER_REQUEST",
            idempotency_key=digest("cancel-command"),
        )
        await deliver("mirror.demo_context.compile", message(cancelled))
        async with sessions() as db:
            require(
                await db.scalar(
                    select(func.count())
                    .select_from(DemoContextCompileResult)
                    .where(
                        DemoContextCompileResult.compile_request_id == cancelled.context_request_id
                    )
                )
                == 0,
                "CANCELLED_PARTIAL_RESULT",
            )
            require(
                await db.scalar(
                    select(func.count())
                    .select_from(DemoContextCompilation)
                    .join(
                        DemoJobBinding,
                        DemoJobBinding.id == DemoContextCompilation.demo_job_binding_id,
                    )
                    .where(DemoJobBinding.job_id == cancelled.job_id)
                )
                == 0,
                "CANCELLED_PARTIAL_CONTEXT",
            )
        require(
            not any(x.demo_actor_id == ACTOR_ID for x in await queue.reconciliation_candidates()),
            "TERMINAL_RECONCILIATION_CANDIDATE",
        )
        report(
            "CANCEL_AND_ACTUAL_REDELIVERY_PASS",
            completed_job_id=completed.job_id,
            cancelled_job_id=cancelled.job_id,
            partial_contexts=0,
        )
        report("LIFECYCLE_EVENTS_RUNNING")
        reset = await append(
            EventType.RESET,
            target_type=TargetType.DEMO_ACTOR,
            target_id=ACTOR_ID,
            signal={"reset_watermark": seed.event_sequence},
        )
        reset_profile = await rebuild("reset", "RESET")
        require(
            reset_profile.reset_epoch == 1
            and reset.content_digest in reset_profile.evidence_digests,
            "RESET_PROJECTION_INVALID",
        )
        rollback = await append(
            EventType.ROLLBACK, target_type=TargetType.AESTHETIC_PROFILE, target_id=baseline.id
        )
        rollback_profile = await rebuild("rollback", "ROLLBACK")
        require(
            reset.content_digest not in rollback_profile.evidence_digests
            and rollback.content_digest in rollback_profile.evidence_digests,
            "ROLLBACK_INVALID",
        )
        _, deletable = await context("before-delete", rollback_profile.id, second.session_id)
        await append(
            EventType.DELETE,
            target_type=TargetType.CONTEXT_COMPILATION,
            target_id=deletable.id,
            session_id=second.session_id,
        )
        try:
            await memory.recall_context(
                demo_actor_id=ACTOR_ID,
                demo_session_id=second.session_id,
                recall_at=datetime.now(UTC),
            )
        except DemoMemoryUnavailable:
            pass
        else:
            raise RuntimeError("DELETED_CONTEXT_RECALLED")
        await append(
            EventType.TOMBSTONE,
            target_type=TargetType.AESTHETIC_PROFILE,
            target_id=rollback_profile.id,
        )
        try:
            await admit_context("tombstoned-profile", rollback_profile.id, second.session_id)
        except DemoContextQueueUnavailable:
            pass
        else:
            raise RuntimeError("TOMBSTONED_PROFILE_ADMITTED")
        async with sessions() as db:
            require(
                await db.get(DemoAestheticProfile, baseline.id) is not None
                and await db.get(DemoContextCompilation, deletable.id) is not None,
                "HISTORICAL_AUTHORITY_REMOVED",
            )
            event_count = await db.scalar(
                select(func.count())
                .select_from(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == ACTOR_ID)
            )
            require(event_count == 6, "ISOLATED_EVENT_CARDINALITY")
        require(await protected_snapshot() == before, "PROTECTED_DEMO_CHANGED")
        report(
            "ISOLATED_LIFECYCLE_PASS",
            actor_id=ACTOR_ID,
            events=event_count,
            protected_main_flow_unchanged=True,
            imagegen_calls=0,
            m3=3,
            m4=0,
        )
    finally:
        broker.close()
        await engine.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        require(
            sys.argv[1:] in ([], ["--resume-from-d05"], ["--resume-after-context"]),
            "INVALID_EXECUTION_MODE",
        )
        if sys.platform == "win32":
            with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
                runner.run(
                    run(
                        resume_d05=sys.argv[1:] == ["--resume-from-d05"],
                        resume_context=sys.argv[1:] == ["--resume-after-context"],
                    )
                )
        else:
            asyncio.run(
                run(
                    resume_d05=sys.argv[1:] == ["--resume-from-d05"],
                    resume_context=sys.argv[1:] == ["--resume-after-context"],
                )
            )
    except Exception as error:
        # Never print exception text: DB drivers may include DSNs or SQL parameters.
        report(
            STAGE,
            status="FAILED",
            error_class=type(error).__name__,
            check_code=error.code if isinstance(error, CheckFailure) else "DETAILS_WITHHELD",
        )
        raise SystemExit(1) from None
