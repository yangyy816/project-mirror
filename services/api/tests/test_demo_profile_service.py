from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_demo_analysis_service import _runtime_evidence
from test_demo_analysis_service import _service as _analysis_service
from test_demo_questionnaire_integration import _database

import mirror_api.demo_profile_service as profile_service_module
from mirror_api.demo_analysis_service import CreateDemoAnalysis
from mirror_api.demo_models import (
    DemoAnalysisRun,
    DemoDesiredDeltaProfile,
    DemoIdentityConstraints,
    DemoJobBinding,
    DemoPreferenceEvent,
    DemoProfileCompilationBundle,
    DemoQuestionnaireRun,
    DemoQuestionnaireStep,
    DemoSession,
    DemoStyleProfile,
)
from mirror_api.demo_posterior import PairwiseChoice
from mirror_api.demo_preference_ledger import (
    GENESIS_EVENT_DIGEST,
    preference_event_content_digest,
)
from mirror_api.demo_profile_service import (
    DEMO_PROFILE_COMPILE_JOB_TYPE,
    DEMO_PROFILE_COMPILE_OPERATION,
    DemoProfileAuthorityCorruption,
    DemoProfileCompilationService,
    DemoProfileRejected,
    DemoProfileResultNotReady,
    DemoProfileResultTerminal,
    DemoProfileUnavailable,
    _authority_digest,
)
from mirror_api.demo_questionnaire_service import (
    CreateDemoQuestionnaireResponse,
    CreateDemoQuestionnaireRun,
    DemoQuestionnaireCompleted,
    DemoQuestionnaireNext,
    DemoQuestionnaireService,
)
from mirror_api.models import Job, JobAttempt, new_id, utcnow


@pytest.fixture(scope="module")
def event_loop_policy() -> Any:
    if os.name == "nt":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _profile_job(
    sessions: async_sessionmaker[AsyncSession],
    actor_id: str,
    session_id: str,
    *,
    key_material: str | None = None,
) -> str:
    job_id = new_id()
    binding_id = new_id()
    now = utcnow()
    binding_payload = {
        "demo_actor_id": actor_id,
        "demo_session_id": session_id,
        "endpoint_operation": DEMO_PROFILE_COMPILE_OPERATION,
        "idempotency_key_hash": _digest(key_material or job_id),
        "job_id": job_id,
        "request_digest": _digest("b"),
        "target_id": actor_id,
        "target_type": "DEMO_ACTOR",
    }
    # The generic Job key is already scoped by this test database invocation.
    job = Job(
        id=job_id,
        job_type=DEMO_PROFILE_COMPILE_JOB_TYPE,
        status="PENDING",
        idempotency_key_hash=hashlib.sha256(
            (
                f"mirror.demo/JobIdempotency/v1\n{actor_id}\n"
                f"{DEMO_PROFILE_COMPILE_OPERATION}\n{binding_payload['idempotency_key_hash']}"
            ).encode()
        ).hexdigest(),
        request_id=f"profile-test-{job_id}",
        payload={},
        owner_user_id=None,
        attempt_count=0,
        created_at=now,
        updated_at=now,
    )
    binding = DemoJobBinding(
        id=binding_id,
        schema_version="mirror.demo/DemoJobBinding/v1",
        canonical_payload=binding_payload,
        content_digest=_authority_digest("mirror.demo/DemoJobBinding/v1", binding_payload),
        created_at=now,
        **binding_payload,
    )
    async with sessions() as session:
        async with session.begin():
            session.add(job)
            await session.flush()
            session.add(binding)
            await session.flush()
    return job_id


def _authority_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _append_explicit_event(
    sessions: async_sessionmaker[AsyncSession],
    *,
    actor_id: str,
    event_type: str,
    signal: dict[str, object],
    session_id: str | None,
) -> DemoPreferenceEvent:
    now = utcnow()
    async with sessions() as session:
        async with session.begin():
            previous = await session.scalar(
                select(DemoPreferenceEvent)
                .where(DemoPreferenceEvent.demo_actor_id == actor_id)
                .order_by(DemoPreferenceEvent.event_sequence.desc())
                .limit(1)
            )
            sequence = 1 if previous is None else previous.event_sequence + 1
            payload = {
                "demo_actor_id": actor_id,
                "demo_session_id": session_id,
                "event_sequence": sequence,
                "event_type": event_type,
                "occurred_at": _authority_time(now),
                "previous_event_digest": (
                    GENESIS_EVENT_DIGEST if previous is None else previous.content_digest
                ),
                "signal": signal,
                "source_type": "EXPLICIT_USER_ACTION",
                "target_id": None,
                "target_type": None,
            }
            event = DemoPreferenceEvent(
                id=new_id(),
                schema_version="mirror.demo/DemoPreferenceEvent/v1",
                canonical_payload=payload,
                content_digest=preference_event_content_digest(payload),
                created_at=now,
                **payload,
            )
            session.add(event)
        return event


async def _create_second_self_state(
    sessions: async_sessionmaker[AsyncSession], actor_id: str, session_id: str
) -> str:
    async with sessions() as session:
        existing = await session.scalar(
            select(DemoAnalysisRun).where(
                DemoAnalysisRun.demo_actor_id == actor_id,
                DemoAnalysisRun.demo_session_id == session_id,
            )
        )
    assert existing is not None
    service = _analysis_service(sessions)
    command = CreateDemoAnalysis(
        demo_actor_id=actor_id,
        demo_session_id=session_id,
        source_asset_id=existing.source_asset_id,
        idempotency_key=f"profile-second-anchor-{new_id()}",
        request_id=f"profile-second-anchor-{new_id()}",
    )
    accepted = await service.create(command)
    reservation = await service.claim(
        analysis_run_id=accepted.analysis_run_id,
        job_id=accepted.job_id,
        request_id=command.request_id,
    )
    assert reservation is not None
    publication = await service.complete(reservation, _runtime_evidence())
    assert publication is not None
    return publication.self_state_id


async def _other_session(
    sessions: async_sessionmaker[AsyncSession], session_id: str
) -> DemoSession:
    async with sessions() as session:
        async with session.begin():
            original = await session.get(DemoSession, session_id)
            assert original is not None
            config = {**original.config, "profile_service_test": "other-session"}
            payload = {
                "config": config,
                "context_seed": _digest(new_id()),
                "demo_actor_id": original.demo_actor_id,
                "expires_at": _authority_time(original.expires_at),
            }
            other = DemoSession(
                id=new_id(),
                schema_version="mirror.demo/DemoSession/v1",
                canonical_payload=payload,
                content_digest=_authority_digest("mirror.demo/DemoSession/v1", payload),
                created_at=utcnow(),
                demo_actor_id=original.demo_actor_id,
                config=config,
                context_seed=payload["context_seed"],
                expires_at=original.expires_at,
                closed_at=None,
                tombstoned_at=None,
            )
            session.add(other)
        return other


async def _questionnaire_run(
    sessions: async_sessionmaker[AsyncSession], context: Any
) -> tuple[str, str]:
    questionnaires = DemoQuestionnaireService(session_factory=sessions)
    accepted = await questionnaires.create(
        CreateDemoQuestionnaireRun(
            demo_actor_id=context.actor_id,
            demo_session_id=context.session_id,
            self_state_id=context.self_state_id,
            question_bank_version=context.question_bank_version,
            max_questions=12,
            idempotency_key=_digest(new_id()),
            request_id=f"profile-questionnaire-{new_id()}",
        )
    )
    return accepted.questionnaire_run_id, accepted.job_id


@pytest.mark.asyncio
async def test_profile_compile_materializes_one_bundle_and_exactly_replays() -> None:
    async with _database() as (sessions, context):
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        service = DemoProfileCompilationService(session_factory=sessions)

        first = await service.compile(demo_actor_id=context.actor_id, job_id=job_id)
        replay = await service.compile(demo_actor_id=context.actor_id, job_id=job_id)

        assert first.replayed is False
        assert replay.replayed is True
        assert replay.bundle_id == first.bundle_id
        assert replay.compilation_digest == first.compilation_digest
        async with sessions() as session:
            bundles = list((await session.scalars(select(DemoProfileCompilationBundle))).all())
            desired = list((await session.scalars(select(DemoDesiredDeltaProfile))).all())
            styles = list((await session.scalars(select(DemoStyleProfile))).all())
            constraints = list((await session.scalars(select(DemoIdentityConstraints))).all())
            job = await session.get(Job, job_id)
            attempts = list(
                (await session.scalars(select(JobAttempt).where(JobAttempt.job_id == job_id))).all()
            )
        assert len(bundles) == len(desired) == len(styles) == 1
        assert len(constraints) == 2
        assert job is not None and (job.status, job.result_code) == (
            "COMPLETED",
            "PROFILE_COMPILED",
        )
        assert [(attempt.status, attempt.result_code) for attempt in attempts] == [
            ("COMPLETED", "PROFILE_COMPILED")
        ]


@pytest.mark.asyncio
async def test_profile_result_repeated_read_returns_exact_bundle_without_writes() -> None:
    async with _database() as (sessions, context):
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        service = DemoProfileCompilationService(session_factory=sessions)
        compiled = await service.compile(demo_actor_id=context.actor_id, job_id=job_id)

        async with sessions() as session:
            before = (
                len(list((await session.scalars(select(JobAttempt))).all())),
                len(list((await session.scalars(select(DemoProfileCompilationBundle))).all())),
                len(list((await session.scalars(select(DemoDesiredDeltaProfile))).all())),
                len(list((await session.scalars(select(DemoStyleProfile))).all())),
                len(list((await session.scalars(select(DemoIdentityConstraints))).all())),
            )

        first = await service.read_completed_result(
            demo_actor_id=context.actor_id,
            job_id=job_id,
        )
        second = await service.read_completed_result(
            demo_actor_id=context.actor_id,
            job_id=job_id,
        )

        assert first == second
        assert first.job_id == job_id
        assert first.session_id == context.session_id
        assert first.profile_id == compiled.bundle_id
        assert first.compilation_digest == compiled.compilation_digest
        async with sessions() as session:
            binding = await session.scalar(
                select(DemoJobBinding).where(DemoJobBinding.job_id == job_id)
            )
            after = (
                len(list((await session.scalars(select(JobAttempt))).all())),
                len(list((await session.scalars(select(DemoProfileCompilationBundle))).all())),
                len(list((await session.scalars(select(DemoDesiredDeltaProfile))).all())),
                len(list((await session.scalars(select(DemoStyleProfile))).all())),
                len(list((await session.scalars(select(DemoIdentityConstraints))).all())),
            )
        assert binding is not None
        assert first.job_binding_digest == binding.content_digest
        assert after == before


@pytest.mark.asyncio
async def test_profile_result_rejects_pending_job_without_creating_attempt() -> None:
    async with _database() as (sessions, context):
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)

        with pytest.raises(DemoProfileResultNotReady):
            await DemoProfileCompilationService(session_factory=sessions).read_completed_result(
                demo_actor_id=context.actor_id,
                job_id=job_id,
            )

        async with sessions() as session:
            attempts = list(
                (await session.scalars(select(JobAttempt).where(JobAttempt.job_id == job_id))).all()
            )
            bundles = list((await session.scalars(select(DemoProfileCompilationBundle))).all())
        assert attempts == bundles == []


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", ["REJECTED", "FAILED", "CANCELLED"])
async def test_profile_result_rejects_terminal_job_without_fallback(
    terminal_status: str,
) -> None:
    async with _database() as (sessions, context):
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        async with sessions() as session:
            async with session.begin():
                job = await session.get(Job, job_id)
                assert job is not None
                job.status = terminal_status
                job.finalized_at = utcnow()

        with pytest.raises(DemoProfileResultTerminal):
            await DemoProfileCompilationService(session_factory=sessions).read_completed_result(
                demo_actor_id=context.actor_id,
                job_id=job_id,
            )


@pytest.mark.asyncio
async def test_profile_result_hides_missing_job_and_foreign_actor() -> None:
    async with _database() as (sessions, context):
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        service = DemoProfileCompilationService(session_factory=sessions)

        with pytest.raises(DemoProfileUnavailable):
            await service.read_completed_result(
                demo_actor_id=context.actor_id,
                job_id=new_id(),
            )
        with pytest.raises(DemoProfileUnavailable):
            await service.read_completed_result(
                demo_actor_id=new_id(),
                job_id=job_id,
            )


@pytest.mark.asyncio
async def test_profile_result_completed_job_without_bundle_is_corruption() -> None:
    async with _database() as (sessions, context):
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        now = utcnow()
        async with sessions() as session:
            async with session.begin():
                job = await session.get(Job, job_id)
                assert job is not None
                job.status = "COMPLETED"
                job.attempt_count = 1
                job.finalized_at = now
                job.result_code = "PROFILE_COMPILED"
                job.updated_at = now
                session.add(
                    JobAttempt(
                        id=new_id(),
                        job_id=job_id,
                        attempt=1,
                        status="COMPLETED",
                        result_code="PROFILE_COMPILED",
                        started_at=now,
                        finished_at=now,
                    )
                )

        with pytest.raises(DemoProfileAuthorityCorruption, match="has no bundle"):
            await DemoProfileCompilationService(session_factory=sessions).read_completed_result(
                demo_actor_id=context.actor_id,
                job_id=job_id,
            )


@pytest.mark.asyncio
async def test_profile_result_rejects_invalid_completed_attempt_shape() -> None:
    async with _database() as (sessions, context):
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        service = DemoProfileCompilationService(session_factory=sessions)
        await service.compile(demo_actor_id=context.actor_id, job_id=job_id)
        async with sessions() as session:
            async with session.begin():
                attempt = await session.scalar(
                    select(JobAttempt).where(JobAttempt.job_id == job_id)
                )
                assert attempt is not None
                attempt.result_code = "WRONG_RESULT"

        with pytest.raises(DemoProfileAuthorityCorruption, match="Attempt is invalid"):
            await service.read_completed_result(
                demo_actor_id=context.actor_id,
                job_id=job_id,
            )


@pytest.mark.asyncio
async def test_profile_compile_rejects_ambiguous_fallback_anchor_without_partial_output() -> None:
    async with _database() as (sessions, context):
        await _create_second_self_state(sessions, context.actor_id, context.session_id)
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)

        with pytest.raises(DemoProfileRejected, match="exactly one SelfState anchor"):
            await DemoProfileCompilationService(session_factory=sessions).compile(
                demo_actor_id=context.actor_id, job_id=job_id
            )

        async with sessions() as session:
            job = await session.get(Job, job_id)
            attempts = list(
                (await session.scalars(select(JobAttempt).where(JobAttempt.job_id == job_id))).all()
            )
            bundles = list((await session.scalars(select(DemoProfileCompilationBundle))).all())
            desired = list((await session.scalars(select(DemoDesiredDeltaProfile))).all())
            styles = list((await session.scalars(select(DemoStyleProfile))).all())
            constraints = list((await session.scalars(select(DemoIdentityConstraints))).all())
        assert job is not None and (job.status, job.result_code) == ("REJECTED", "PROFILE_REJECTED")
        assert [(attempt.status, attempt.result_code) for attempt in attempts] == [
            ("REJECTED", "PROFILE_REJECTED")
        ]
        assert bundles == desired == styles == constraints == []


@pytest.mark.asyncio
async def test_profile_compile_rolls_back_all_outputs_when_bundle_insert_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _database() as (sessions, context):
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        original_bundle_payload = profile_service_module._bundle_payload

        def invalid_bundle_payload(*args: Any, **kwargs: Any) -> dict[str, Any]:
            payload = original_bundle_payload(*args, **kwargs)
            payload["compilation_watermark"] = "invalid"
            return payload

        monkeypatch.setattr(
            profile_service_module,
            "_bundle_payload",
            invalid_bundle_payload,
        )
        with pytest.raises(DBAPIError):
            await DemoProfileCompilationService(session_factory=sessions).compile(
                demo_actor_id=context.actor_id,
                job_id=job_id,
            )

        async with sessions() as session:
            job = await session.get(Job, job_id)
            attempts = list(
                (await session.scalars(select(JobAttempt).where(JobAttempt.job_id == job_id))).all()
            )
            bundles = list((await session.scalars(select(DemoProfileCompilationBundle))).all())
            desired = list((await session.scalars(select(DemoDesiredDeltaProfile))).all())
            styles = list((await session.scalars(select(DemoStyleProfile))).all())
            constraints = list((await session.scalars(select(DemoIdentityConstraints))).all())
        assert job is not None and (job.status, job.attempt_count) == ("PENDING", 0)
        assert attempts == []
        assert bundles == desired == styles == constraints == []


@pytest.mark.asyncio
async def test_profile_compile_does_not_consume_unfinished_questionnaire() -> None:
    async with _database() as (sessions, context):
        run_id, questionnaire_job_id = await _questionnaire_run(sessions, context)
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        result = await DemoProfileCompilationService(session_factory=sessions).compile(
            demo_actor_id=context.actor_id, job_id=job_id
        )

        async with sessions() as session:
            desired = await session.get(DemoDesiredDeltaProfile, result.desired_delta_profile_id)
            questionnaire_job = await session.get(Job, questionnaire_job_id)
            questionnaire_run = await session.get(DemoQuestionnaireRun, run_id)
        assert desired is not None
        assert questionnaire_run is not None
        assert questionnaire_run.content_digest not in desired.evidence_digests
        assert questionnaire_job is not None and questionnaire_job.status == "PENDING"


@pytest.mark.asyncio
async def test_profile_compile_consumes_completed_questionnaire_answer_evidence() -> None:
    async with _database() as (sessions, context):
        run_id, questionnaire_job_id = await _questionnaire_run(sessions, context)
        questionnaires = DemoQuestionnaireService(session_factory=sessions)
        response_digests: list[str] = []
        for index in range(12):
            next_item = await questionnaires.next(
                demo_actor_id=context.actor_id, questionnaire_run_id=run_id
            )
            assert isinstance(next_item, DemoQuestionnaireNext)
            response = await questionnaires.respond(
                CreateDemoQuestionnaireResponse(
                    demo_actor_id=context.actor_id,
                    questionnaire_run_id=run_id,
                    selected_side=(PairwiseChoice.RIGHT if index == 0 else PairwiseChoice.SKIP),
                    expected_step_sequence=next_item.snapshot.step_sequence,
                    expected_run_version=next_item.snapshot.run_version,
                    response_latency_ms=10 + index,
                    idempotency_key=_digest(f"profile-response-{index}-{run_id}"),
                )
            )
            response_digests.append(response.step_id)
        terminal = await questionnaires.next(
            demo_actor_id=context.actor_id, questionnaire_run_id=run_id
        )
        assert isinstance(terminal, DemoQuestionnaireCompleted)

        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        result = await DemoProfileCompilationService(session_factory=sessions).compile(
            demo_actor_id=context.actor_id, job_id=job_id
        )
        async with sessions() as session:
            desired = await session.get(DemoDesiredDeltaProfile, result.desired_delta_profile_id)
            questionnaire_job = await session.get(Job, questionnaire_job_id)
            questionnaire_run = await session.get(DemoQuestionnaireRun, run_id)
            response_steps = list(
                (
                    await session.scalars(
                        select(DemoQuestionnaireStep).where(
                            DemoQuestionnaireStep.questionnaire_run_id == run_id,
                            DemoQuestionnaireStep.event_type == "RESPONDED",
                        )
                    )
                ).all()
            )
        assert desired is not None
        assert questionnaire_job is not None and questionnaire_job.status == "COMPLETED"
        assert questionnaire_run is not None
        assert questionnaire_run.content_digest in desired.evidence_digests
        assert len(response_digests) == len(response_steps) == 12
        assert all(step.content_digest in desired.evidence_digests for step in response_steps)


@pytest.mark.asyncio
async def test_profile_compile_persists_actor_style_and_only_matching_session_override() -> None:
    async with _database() as (sessions, context):
        style = await _append_explicit_event(
            sessions,
            actor_id=context.actor_id,
            event_type="EXPLICIT_STYLE_SELECTION",
            signal={"style_key": "editorial", "negative_style_key": "retro"},
            session_id=None,
        )
        persistent = await _append_explicit_event(
            sessions,
            actor_id=context.actor_id,
            event_type="FEATURE_LOCKED",
            signal={
                "constraint_scope": "PERSISTENT",
                "dimension_key": "jaw_width",
                "minimum_ppm": -1,
                "maximum_ppm": 1,
            },
            session_id=None,
        )
        matching = await _append_explicit_event(
            sessions,
            actor_id=context.actor_id,
            event_type="TEMPORARY_SESSION_OVERRIDE",
            signal={"dimension_key": "jaw_width", "minimum_ppm": 0, "maximum_ppm": 0},
            session_id=context.session_id,
        )
        other_session = await _other_session(sessions, context.session_id)
        other = await _append_explicit_event(
            sessions,
            actor_id=context.actor_id,
            event_type="TEMPORARY_SESSION_OVERRIDE",
            signal={"dimension_key": "jaw_width", "minimum_ppm": 2, "maximum_ppm": 3},
            session_id=other_session.id,
        )
        job_id = await _profile_job(sessions, context.actor_id, context.session_id)
        result = await DemoProfileCompilationService(session_factory=sessions).compile(
            demo_actor_id=context.actor_id, job_id=job_id
        )

        async with sessions() as session:
            style_row = await session.get(DemoStyleProfile, result.style_profile_id)
            persistent_row = await session.get(
                DemoIdentityConstraints, result.persistent_constraints_id
            )
            session_row = await session.get(
                DemoIdentityConstraints, result.session_override_constraints_id
            )
        assert style_row is not None
        assert style_row.preferences == {"style_keys": ["editorial"]}
        assert style_row.negative_evidence == ["retro"]
        assert style_row.evidence_digests == [style.content_digest]
        assert persistent_row is not None
        assert persistent_row.source_event_digests == [persistent.content_digest]
        assert persistent_row.locks["jaw_width"]["mode"] == "PRESERVE"
        assert session_row is not None
        assert session_row.source_event_digests == [matching.content_digest]
        assert session_row.locks["jaw_width"]["mode"] == "ALLOW_CHANGE"
        assert other.content_digest not in session_row.source_event_digests


@pytest.mark.asyncio
async def test_profile_compile_serializes_versions_and_keeps_same_input_digest_stable() -> None:
    async with _database() as (sessions, context):
        first_job = await _profile_job(
            sessions, context.actor_id, context.session_id, key_material="first"
        )
        second_job = await _profile_job(
            sessions, context.actor_id, context.session_id, key_material="second"
        )
        service = DemoProfileCompilationService(session_factory=sessions)
        first, second = await asyncio.gather(
            service.compile(demo_actor_id=context.actor_id, job_id=first_job),
            service.compile(demo_actor_id=context.actor_id, job_id=second_job),
        )

        async with sessions() as session:
            desired = list(
                (
                    await session.scalars(
                        select(DemoDesiredDeltaProfile)
                        .where(DemoDesiredDeltaProfile.demo_actor_id == context.actor_id)
                        .order_by(DemoDesiredDeltaProfile.version)
                    )
                ).all()
            )
            jobs = [await session.get(Job, job_id) for job_id in (first_job, second_job)]
        assert first.compilation_digest == second.compilation_digest
        assert [row.version for row in desired] == [1, 2]
        assert all(job is not None and job.status == "COMPLETED" for job in jobs)
