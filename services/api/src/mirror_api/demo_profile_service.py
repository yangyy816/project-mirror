"""PostgreSQL-authoritative execution for the deterministic P5 compiler.

This module is deliberately an application boundary: it projects immutable
Demo authority rows into the pure compiler, then materializes its four output
rows and their bundle in one database transaction.  It has no Celery import.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_models import (
    DemoActor,
    DemoDesiredDeltaProfile,
    DemoIdentityConstraints,
    DemoJobBinding,
    DemoPreferenceEvent,
    DemoProfileCompilationBundle,
    DemoQuestionnaireRun,
    DemoQuestionnaireStep,
    DemoQuestionPair,
    DemoSelfState,
    DemoSelfTransferDimensionEvidence,
    DemoSelfTransferRun,
    DemoSession,
    DemoStyleProfile,
)
from mirror_api.demo_posterior import (
    PairwiseChoice,
    PairwiseObservation,
    PosteriorConfig,
    PosteriorError,
    canonical_json_bytes,
    infer_pairwise_posterior,
)
from mirror_api.demo_profile_compiler import (
    AuthorityEvent,
    EventSource,
    EventType,
    ProfileCompilation,
    ProfileCompilerError,
    ProfileCompilerInput,
    QuestionnaireEvidence,
    SelfStateAnchor,
    SelfStateDimension,
    SelfTransferEvidence,
    SelfTransferOutcome,
    compile_profile,
)
from mirror_api.demo_questionnaire_bank import (
    QuestionBankProjectionError,
    load_admitted_question_bank,
)
from mirror_api.demo_questionnaire_service import (
    DEMO_QUESTIONNAIRE_JOB_TYPE,
    DEMO_QUESTIONNAIRE_RUN_OPERATION,
)
from mirror_api.models import Job, JobAttempt, new_id, utcnow

DEMO_PROFILE_COMPILE_OPERATION = "profile.compile"
DEMO_PROFILE_COMPILE_JOB_TYPE = "demo_p3_p7.profile.compile"
DEMO_DESIRED_DELTA_SCHEMA = "mirror.demo/DemoDesiredDeltaProfile/v1"
DEMO_STYLE_SCHEMA = "mirror.demo/DemoStyleProfile/v1"
DEMO_CONSTRAINTS_SCHEMA = "mirror.demo/DemoIdentityConstraints/v1"
DEMO_BUNDLE_SCHEMA = "mirror.demo/DemoProfileCompilationBundle/v1"
DEMO_SELF_TRANSFER_PROJECTION_VERSION = "demo-self-transfer-projection-v1"
DEMO_SELF_TRANSFER_PROJECTION_CONFIG_DIGEST = hashlib.sha256(
    canonical_json_bytes(
        {
            "policy": "verified-result-measured-delta-per-dimension-v1",
            "projection_version": DEMO_SELF_TRANSFER_PROJECTION_VERSION,
        }
    )
).hexdigest()
_ID = re.compile(r"^[0-9a-f]{32}$")
_TERMINAL = frozenset({"COMPLETED", "REJECTED", "FAILED", "CANCELLED"})
_PROFILE_EVENT_TYPES = frozenset(item.value for item in EventType)
_SCOPED_CONSTRAINT_EVENT_TYPES = frozenset(
    {
        EventType.FEATURE_LOCKED,
        EventType.FEATURE_UNLOCKED,
        EventType.MAXIMUM_INTENSITY_CHANGED,
        EventType.PROHIBITED_OPERATION_ADDED,
    }
)


class DemoProfileServiceError(RuntimeError):
    """Base profile compilation service failure."""


class DemoProfileInputError(DemoProfileServiceError):
    """The internal worker command violates its frozen boundary."""


class DemoProfileUnavailable(DemoProfileServiceError):
    """Owner-bound profile compilation authority is unavailable."""


class DemoProfileRejected(DemoProfileServiceError):
    """Persisted authority is well-formed but cannot be safely compiled."""


class DemoProfileAuthorityCorruption(DemoProfileServiceError):
    """Persisted authority or an already-published bundle cannot be replayed."""


@dataclass(frozen=True)
class DemoProfileCompilationResult:
    job_id: str
    bundle_id: str
    desired_delta_profile_id: str
    style_profile_id: str
    persistent_constraints_id: str
    session_override_constraints_id: str
    compilation_digest: str
    replayed: bool


@dataclass(frozen=True)
class _EventAuthorityDigests:
    style: tuple[str, ...]
    persistent_constraints: tuple[str, ...]
    session_constraints: tuple[str, ...]


class DemoProfileCompilationService:
    """Serialize P5 materialization through the actor and formal Job authority."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = session_factory
        self._now = now
        self._posterior_config = PosteriorConfig()

    async def compile(self, *, demo_actor_id: str, job_id: str) -> DemoProfileCompilationResult:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(job_id, "job_id")
        terminal_error: DemoProfileServiceError | None = None
        result: DemoProfileCompilationResult | None = None
        async with self._sessions() as session:
            async with session.begin():
                job, binding, actor = await self._lock_context(session, demo_actor_id, job_id)
                existing = await self._bundle_for_binding(session, binding.id)
                if job.status == "COMPLETED":
                    if existing is None:
                        raise DemoProfileAuthorityCorruption("completed profile Job has no bundle")
                    return await self._replay_bundle(session, job, binding, existing)
                if job.status in _TERMINAL:
                    raise DemoProfileUnavailable("profile Job is terminal")
                if job.status != "PENDING" or job.attempt_count != 0:
                    raise DemoProfileUnavailable("profile Job is not a fresh durable execution")
                if existing is not None:
                    raise DemoProfileAuthorityCorruption("active profile Job already has a bundle")

                now = self._normalized_now()
                attempt = JobAttempt(
                    id=new_id(), job_id=job.id, attempt=1, status="RUNNING", started_at=now
                )
                session.add(attempt)
                job.status = "RUNNING"
                job.attempt_count = 1
                job.updated_at = now
                await session.flush()

                try:
                    (
                        compilation,
                        self_state,
                        desired_evidence_digests,
                        event_digests,
                    ) = await self._compile_input(session, actor=actor, binding=binding)
                    result = await self._materialize(
                        session,
                        binding=binding,
                        self_state=self_state,
                        compilation=compilation,
                        desired_evidence_digests=desired_evidence_digests,
                        event_digests=event_digests,
                        now=now,
                    )
                except DemoProfileRejected as exc:
                    terminal_error = exc
                    _finish_job(
                        job,
                        attempt,
                        status="REJECTED",
                        result_code="PROFILE_REJECTED",
                        error_code=None,
                        now=now,
                    )
                except DemoProfileAuthorityCorruption as exc:
                    terminal_error = exc
                    _finish_job(
                        job,
                        attempt,
                        status="FAILED",
                        result_code="PROFILE_AUTHORITY_CORRUPTION",
                        error_code="PROFILE_AUTHORITY_CORRUPTION",
                        now=now,
                    )
                else:
                    _finish_job(
                        job,
                        attempt,
                        status="COMPLETED",
                        result_code="PROFILE_COMPILED",
                        error_code=None,
                        now=now,
                    )
                await session.flush()
        if terminal_error is not None:
            raise terminal_error
        if result is None:
            raise DemoProfileAuthorityCorruption("profile compiler produced no durable result")
        return result

    async def _lock_context(
        self, session: AsyncSession, demo_actor_id: str, job_id: str
    ) -> tuple[Job, DemoJobBinding, DemoActor]:
        job = cast(
            Job | None, await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
        )
        binding = cast(
            DemoJobBinding | None,
            await session.scalar(
                select(DemoJobBinding).where(DemoJobBinding.job_id == job_id).with_for_update()
            ),
        )
        if job is None or binding is None:
            raise DemoProfileUnavailable("profile Job authority is unavailable")
        if (
            binding.demo_actor_id != demo_actor_id
            or binding.endpoint_operation != DEMO_PROFILE_COMPILE_OPERATION
            or binding.target_type != "DEMO_ACTOR"
            or binding.target_id != demo_actor_id
            or binding.demo_session_id is None
            or job.job_type != DEMO_PROFILE_COMPILE_JOB_TYPE
            or job.payload != {}
            or job.owner_user_id is not None
            or job.ingestion_upload_intent_id is not None
            or job.result_asset_id is not None
        ):
            raise DemoProfileUnavailable("profile Job envelope is invalid")
        actor = cast(
            DemoActor | None,
            await session.scalar(
                select(DemoActor).where(DemoActor.id == demo_actor_id).with_for_update()
            ),
        )
        if actor is None or actor.tombstoned_at is not None:
            raise DemoProfileUnavailable("Demo actor is unavailable")
        demo_session = await session.get(DemoSession, binding.demo_session_id)
        if demo_session is None or demo_session.demo_actor_id != actor.id:
            raise DemoProfileUnavailable("profile Job Session is unavailable")
        return job, binding, actor

    async def _compile_input(
        self, session: AsyncSession, *, actor: DemoActor, binding: DemoJobBinding
    ) -> tuple[
        ProfileCompilation,
        DemoSelfState,
        tuple[str, ...],
        _EventAuthorityDigests,
    ]:
        assert binding.demo_session_id is not None
        self_state, questionnaire_runs = await self._resolve_anchor(
            session, actor.id, binding.demo_session_id
        )
        questionnaire, questionnaire_digests = await self._questionnaire_evidence(
            session,
            actor.id,
            binding.demo_session_id,
            self_state.id,
            questionnaire_runs,
        )
        transfer, transfer_digests = await self._self_transfer_evidence(
            session, actor.id, binding.demo_session_id, self_state.id
        )
        events, event_digests, as_of = await self._events(
            session, actor.id, binding.demo_session_id
        )
        dimensions = tuple(
            SelfStateDimension(key, value)
            for key, value in sorted(self_state.measurements.items())
            if type(value) is int
        )
        if len(dimensions) != len(self_state.measurements):
            raise DemoProfileRejected("SelfState measurements are not integer authority")
        try:
            profile_input = ProfileCompilerInput(
                actor_id=actor.id,
                self_state=SelfStateAnchor(self_state.content_digest, dimensions),
                questionnaire=questionnaire,
                self_transfer=transfer,
                authority_events=events,
                compilation_session_id=binding.demo_session_id,
                as_of_event_sequence=as_of,
            )
            return (
                compile_profile(profile_input),
                self_state,
                tuple(sorted({*questionnaire_digests, *transfer_digests})),
                event_digests,
            )
        except (ProfileCompilerError, PosteriorError, ValueError) as exc:
            raise DemoProfileRejected("profile authority cannot be compiled") from exc

    async def _resolve_anchor(
        self, session: AsyncSession, actor_id: str, session_id: str
    ) -> tuple[DemoSelfState, tuple[DemoQuestionnaireRun, ...]]:
        questionnaire_runs = await self._consumable_questionnaire_runs(
            session, actor_id, session_id
        )
        rows = sorted({run.self_state_id for run in questionnaire_runs})
        if not rows:
            rows = list(
                (
                    await session.scalars(
                        select(DemoSelfState.id).where(
                            DemoSelfState.demo_actor_id == actor_id,
                            DemoSelfState.demo_session_id == session_id,
                        )
                    )
                ).all()
            )
        if len(rows) != 1:
            raise DemoProfileRejected("profile compilation requires exactly one SelfState anchor")
        anchor = cast(
            DemoSelfState | None,
            await session.scalar(
                select(DemoSelfState)
                .where(
                    DemoSelfState.id == rows[0],
                    DemoSelfState.demo_actor_id == actor_id,
                    DemoSelfState.demo_session_id == session_id,
                )
                .with_for_update()
            ),
        )
        if anchor is None:
            raise DemoProfileAuthorityCorruption("anchor SelfState is unavailable")
        return anchor, questionnaire_runs

    async def _consumable_questionnaire_runs(
        self, session: AsyncSession, actor_id: str, session_id: str
    ) -> tuple[DemoQuestionnaireRun, ...]:
        runs = list(
            (
                await session.scalars(
                    select(DemoQuestionnaireRun).where(
                        DemoQuestionnaireRun.demo_actor_id == actor_id,
                        DemoQuestionnaireRun.demo_session_id == session_id,
                    )
                )
            ).all()
        )
        if not runs:
            return ()
        run_ids = [run.id for run in runs]
        terminal_steps = list(
            (
                await session.scalars(
                    select(DemoQuestionnaireStep)
                    .where(
                        DemoQuestionnaireStep.questionnaire_run_id.in_(run_ids),
                        DemoQuestionnaireStep.event_type.in_(("STOPPED", "INVALIDATED")),
                    )
                    .order_by(
                        DemoQuestionnaireStep.questionnaire_run_id,
                        DemoQuestionnaireStep.event_sequence,
                    )
                )
            ).all()
        )
        steps_by_run: dict[str, list[DemoQuestionnaireStep]] = defaultdict(list)
        for step in terminal_steps:
            steps_by_run[step.questionnaire_run_id].append(step)

        completion_rows = (
            await session.execute(
                select(DemoJobBinding, Job, JobAttempt)
                .join(Job, Job.id == DemoJobBinding.job_id)
                .join(
                    JobAttempt,
                    and_(
                        JobAttempt.job_id == Job.id,
                        JobAttempt.attempt == Job.attempt_count,
                    ),
                )
                .where(
                    DemoJobBinding.demo_actor_id == actor_id,
                    DemoJobBinding.demo_session_id == session_id,
                    DemoJobBinding.endpoint_operation == DEMO_QUESTIONNAIRE_RUN_OPERATION,
                    DemoJobBinding.target_type == "QUESTIONNAIRE_RUN",
                    DemoJobBinding.target_id.in_(run_ids),
                    Job.job_type == DEMO_QUESTIONNAIRE_JOB_TYPE,
                )
            )
        ).all()
        completion_by_run: dict[str, tuple[Job, JobAttempt]] = {}
        for binding, job, attempt in completion_rows:
            if binding.target_id in completion_by_run:
                raise DemoProfileAuthorityCorruption(
                    "questionnaire run has multiple completion authorities"
                )
            completion_by_run[binding.target_id] = (job, attempt)

        consumable: list[DemoQuestionnaireRun] = []
        for run in runs:
            terminal = steps_by_run.get(run.id, [])
            if any(step.event_type == "INVALIDATED" for step in terminal):
                continue
            stopped = [step for step in terminal if step.event_type == "STOPPED"]
            completion = completion_by_run.get(run.id)
            if not stopped and completion is None:
                continue
            if len(stopped) != 1 or completion is None:
                raise DemoProfileAuthorityCorruption(
                    "questionnaire completion authority is incomplete"
                )
            stop = stopped[0]
            snapshot = stop.response_snapshot
            reason = snapshot.get("reason") if isinstance(snapshot, dict) else None
            job, attempt = completion
            if (
                stop.step_number is not None
                or stop.question_pair_id is not None
                or not isinstance(reason, str)
                or job.status != "COMPLETED"
                or attempt.status != "COMPLETED"
                or job.result_code != reason
                or attempt.result_code != reason
            ):
                raise DemoProfileAuthorityCorruption(
                    "questionnaire completion authority does not replay"
                )
            consumable.append(run)
        return tuple(sorted(consumable, key=lambda run: run.id))

    async def _questionnaire_evidence(
        self,
        session: AsyncSession,
        actor_id: str,
        session_id: str,
        self_state_id: str,
        runs: tuple[DemoQuestionnaireRun, ...],
    ) -> tuple[tuple[QuestionnaireEvidence, ...], tuple[str, ...]]:
        if any(
            run.demo_actor_id != actor_id
            or run.demo_session_id != session_id
            or run.self_state_id != self_state_id
            for run in runs
        ):
            raise DemoProfileAuthorityCorruption("questionnaire anchor authority is inconsistent")
        if not runs:
            return (), ()
        if any(
            run.algorithm_config_digest != self._posterior_config.posterior_config_digest
            for run in runs
        ):
            raise DemoProfileRejected("questionnaire posterior configuration is unsupported")
        run_ids = [run.id for run in runs]
        bank_config_by_id: dict[str, str] = {}
        try:
            for question_bank_id in sorted({run.question_bank_id for run in runs}):
                projection = await load_admitted_question_bank(session, question_bank_id)
                bank_config_by_id[question_bank_id] = projection.config_digest
        except QuestionBankProjectionError as exc:
            raise DemoProfileAuthorityCorruption(
                "questionnaire bank authority cannot be replayed"
            ) from exc
        run_by_id = {run.id: run for run in runs}
        steps = list(
            (
                await session.scalars(
                    select(DemoQuestionnaireStep)
                    .where(
                        DemoQuestionnaireStep.questionnaire_run_id.in_(run_ids),
                        DemoQuestionnaireStep.event_type == "RESPONDED",
                    )
                    .order_by(
                        DemoQuestionnaireStep.questionnaire_run_id,
                        DemoQuestionnaireStep.event_sequence,
                    )
                )
            ).all()
        )
        pair_ids = {step.question_pair_id for step in steps if step.question_pair_id is not None}
        pairs = (
            list(
                (
                    await session.scalars(
                        select(DemoQuestionPair).where(DemoQuestionPair.id.in_(pair_ids))
                    )
                ).all()
            )
            if pair_ids
            else []
        )
        pair_by_id = {pair.id: pair for pair in pairs}
        observations: dict[str, list[PairwiseObservation]] = defaultdict(list)
        directional: dict[str, int] = defaultdict(int)
        ties: dict[str, int] = defaultdict(int)
        for step in steps:
            pair_id = step.question_pair_id
            pair = pair_by_id.get(pair_id) if pair_id is not None else None
            run = run_by_id.get(step.questionnaire_run_id)
            snapshot = step.response_snapshot or {}
            if (
                pair is None
                or run is None
                or pair.question_bank_id != run.question_bank_id
                or not isinstance(snapshot, dict)
            ):
                raise DemoProfileAuthorityCorruption(
                    "questionnaire response authority is incomplete"
                )
            bank_config_digest = bank_config_by_id[run.question_bank_id]
            try:
                choice = PairwiseChoice(cast(str, snapshot["choice"]))
                observation = PairwiseObservation(
                    dimension_key=pair.dimension_key,
                    left_delta_ppm=pair.left_delta_ppm,
                    right_delta_ppm=pair.right_delta_ppm,
                    magnitude_ppm=pair.magnitude_ppm,
                    stimulus_config_version=bank_config_digest,
                    posterior_config_digest=self._posterior_config.posterior_config_digest,
                    choice=choice,
                )
            except (KeyError, TypeError, ValueError, PosteriorError) as exc:
                raise DemoProfileAuthorityCorruption(
                    "questionnaire response cannot be replayed"
                ) from exc
            observations[pair.dimension_key].append(observation)
            if choice in {PairwiseChoice.LEFT, PairwiseChoice.RIGHT}:
                directional[pair.dimension_key] += 1
            elif choice is PairwiseChoice.INDISTINGUISHABLE:
                ties[pair.dimension_key] += 1
        evidence: list[QuestionnaireEvidence] = []
        for key in sorted(observations):
            result = infer_pairwise_posterior(tuple(observations[key]), self._posterior_config)
            evidence.append(QuestionnaireEvidence(key, result, directional[key], ties[key]))
        source_digests = {
            *(run.content_digest for run in runs),
            *(step.content_digest for step in steps),
        }
        return tuple(evidence), tuple(sorted(source_digests))

    async def _self_transfer_evidence(
        self, session: AsyncSession, actor_id: str, session_id: str, self_state_id: str
    ) -> tuple[tuple[SelfTransferEvidence, ...], tuple[str, ...]]:
        rows = (
            await session.execute(
                select(
                    DemoSelfTransferDimensionEvidence, DemoSelfTransferRun, DemoDesiredDeltaProfile
                )
                .join(
                    DemoSelfTransferRun,
                    DemoSelfTransferRun.id
                    == DemoSelfTransferDimensionEvidence.self_transfer_run_id,
                )
                .join(
                    DemoDesiredDeltaProfile,
                    DemoDesiredDeltaProfile.id == DemoSelfTransferRun.desired_delta_profile_id,
                )
                .where(
                    DemoSelfTransferDimensionEvidence.demo_actor_id == actor_id,
                    DemoSelfTransferDimensionEvidence.demo_session_id == session_id,
                    DemoSelfTransferRun.record_kind == "RESULT",
                    DemoDesiredDeltaProfile.self_state_id == self_state_id,
                )
            )
        ).all()
        by_dimension: dict[str, SelfTransferEvidence] = {}
        source_digests: set[str] = set()
        for evidence, run, _profile in rows:
            if evidence.dimension_key in by_dimension:
                raise DemoProfileRejected("multiple self-transfer authorities target one dimension")
            if (
                evidence.projection_version != DEMO_SELF_TRANSFER_PROJECTION_VERSION
                or evidence.projection_config_digest != DEMO_SELF_TRANSFER_PROJECTION_CONFIG_DIGEST
            ):
                raise DemoProfileRejected("self-transfer projection configuration is unsupported")
            try:
                by_dimension[evidence.dimension_key] = SelfTransferEvidence(
                    evidence.dimension_key,
                    evidence.desired_delta_ppm,
                    evidence.confidence_ppm,
                    run.user_outcome == "ACCEPTED",
                    SelfTransferOutcome(evidence.verifier_outcome),
                    evidence.content_digest,
                )
            except (ValueError, ProfileCompilerError) as exc:
                raise DemoProfileAuthorityCorruption("self-transfer projection is invalid") from exc
            source_digests.add(run.content_digest)
            source_digests.add(evidence.verifier_digest)
        return (
            tuple(by_dimension[key] for key in sorted(by_dimension)),
            tuple(sorted(source_digests)),
        )

    async def _events(
        self, session: AsyncSession, actor_id: str, session_id: str
    ) -> tuple[tuple[AuthorityEvent, ...], _EventAuthorityDigests, int]:
        as_of = await session.scalar(
            select(func.coalesce(func.max(DemoPreferenceEvent.event_sequence), 0)).where(
                DemoPreferenceEvent.demo_actor_id == actor_id
            )
        )
        if type(as_of) is not int:
            raise DemoProfileAuthorityCorruption("event sequence authority is invalid")
        rows = list(
            (
                await session.scalars(
                    select(DemoPreferenceEvent)
                    .where(
                        DemoPreferenceEvent.demo_actor_id == actor_id,
                        DemoPreferenceEvent.event_type.in_(_PROFILE_EVENT_TYPES),
                    )
                    .order_by(DemoPreferenceEvent.event_sequence)
                )
            ).all()
        )
        events: list[AuthorityEvent] = []
        style_digests: list[str] = []
        persistent_constraint_digests: list[str] = []
        session_constraint_digests: list[str] = []
        for row in rows:
            try:
                event = AuthorityEvent.create(
                    sequence=row.event_sequence,
                    event_type=EventType(row.event_type),
                    source=EventSource(row.source_type),
                    session_id=row.demo_session_id,
                    signal=row.signal,
                    source_authority_digest=row.content_digest,
                )
            except (ValueError, ProfileCompilerError) as exc:
                raise DemoProfileRejected(
                    "profile event is not explicit compiler authority"
                ) from exc
            events.append(event)
            if event.source is not EventSource.EXPLICIT_USER_ACTION:
                continue
            if event.event_type is EventType.EXPLICIT_STYLE_SELECTION:
                style_digests.append(row.content_digest)
            elif event.event_type is EventType.TEMPORARY_SESSION_OVERRIDE:
                if event.session_id == session_id:
                    session_constraint_digests.append(row.content_digest)
            elif event.event_type in _SCOPED_CONSTRAINT_EVENT_TYPES:
                scope = event.signal.get("constraint_scope")
                if scope == "PERSISTENT":
                    persistent_constraint_digests.append(row.content_digest)
                elif scope == "SESSION_OVERRIDE" and event.session_id == session_id:
                    session_constraint_digests.append(row.content_digest)
        return (
            tuple(events),
            _EventAuthorityDigests(
                style=tuple(sorted(style_digests)),
                persistent_constraints=tuple(sorted(persistent_constraint_digests)),
                session_constraints=tuple(sorted(session_constraint_digests)),
            ),
            as_of,
        )

    async def _materialize(
        self,
        session: AsyncSession,
        *,
        binding: DemoJobBinding,
        self_state: DemoSelfState,
        compilation: ProfileCompilation,
        desired_evidence_digests: tuple[str, ...],
        event_digests: _EventAuthorityDigests,
        now: datetime,
    ) -> DemoProfileCompilationResult:
        assert binding.demo_session_id is not None
        desired_version = await _next_version(
            session, DemoDesiredDeltaProfile, binding.demo_actor_id
        )
        style_version = await _next_version(session, DemoStyleProfile, binding.demo_actor_id)
        constraint_version = await _next_version(
            session, DemoIdentityConstraints, binding.demo_actor_id
        )
        desired_id, style_id, persistent_id, session_id = new_id(), new_id(), new_id(), new_id()
        desired_payload = _desired_payload(
            binding,
            self_state,
            compilation,
            desired_version,
            desired_evidence_digests,
        )
        desired = _authority_row(
            DemoDesiredDeltaProfile, desired_id, DEMO_DESIRED_DELTA_SCHEMA, desired_payload, now
        )
        style_payload = _style_payload(
            binding,
            compilation,
            style_version,
            desired_id,
            event_digests.style,
        )
        style = _authority_row(DemoStyleProfile, style_id, DEMO_STYLE_SCHEMA, style_payload, now)
        persistent_payload = _constraint_payload(
            binding.demo_actor_id,
            self_state.id,
            None,
            "PERSISTENT",
            constraint_version,
            compilation.persistent_constraints,
            event_digests.persistent_constraints,
        )
        persistent = _authority_row(
            DemoIdentityConstraints, persistent_id, DEMO_CONSTRAINTS_SCHEMA, persistent_payload, now
        )
        session_payload = _constraint_payload(
            binding.demo_actor_id,
            self_state.id,
            binding.demo_session_id,
            "SESSION_OVERRIDE",
            constraint_version + 1,
            compilation.session_override_constraints,
            event_digests.session_constraints,
        )
        session_constraints = _authority_row(
            DemoIdentityConstraints, session_id, DEMO_CONSTRAINTS_SCHEMA, session_payload, now
        )
        session.add_all((desired, style, persistent, session_constraints))
        await session.flush()
        bundle_id = new_id()
        bundle_payload = _bundle_payload(
            binding,
            self_state,
            compilation,
            bundle_id,
            desired,
            style,
            persistent,
            session_constraints,
        )
        bundle = _authority_row(
            DemoProfileCompilationBundle, bundle_id, DEMO_BUNDLE_SCHEMA, bundle_payload, now
        )
        session.add(bundle)
        await session.flush()
        return DemoProfileCompilationResult(
            binding.job_id,
            bundle_id,
            desired_id,
            style_id,
            persistent_id,
            session_id,
            compilation.compilation_digest,
            False,
        )

    async def _bundle_for_binding(
        self, session: AsyncSession, binding_id: str
    ) -> DemoProfileCompilationBundle | None:
        return cast(
            DemoProfileCompilationBundle | None,
            await session.scalar(
                select(DemoProfileCompilationBundle).where(
                    DemoProfileCompilationBundle.demo_job_binding_id == binding_id
                )
            ),
        )

    async def _replay_bundle(
        self,
        session: AsyncSession,
        job: Job,
        binding: DemoJobBinding,
        bundle: DemoProfileCompilationBundle,
    ) -> DemoProfileCompilationResult:
        if (
            binding.demo_session_id is None
            or bundle.demo_actor_id != binding.demo_actor_id
            or bundle.demo_session_id != binding.demo_session_id
        ):
            raise DemoProfileAuthorityCorruption("profile bundle ownership is invalid")
        desired = await session.get(DemoDesiredDeltaProfile, bundle.desired_delta_profile_id)
        style = await session.get(DemoStyleProfile, bundle.style_profile_id)
        persistent = await session.get(DemoIdentityConstraints, bundle.persistent_constraints_id)
        session_constraints = await session.get(
            DemoIdentityConstraints, bundle.session_override_constraints_id
        )
        if (
            desired is None
            or style is None
            or persistent is None
            or session_constraints is None
            or desired.demo_job_binding_id != binding.id
            or style.demo_job_binding_id != binding.id
            or bundle.compilation_digest != _bundle_compilation_digest(bundle.canonical_payload)
        ):
            raise DemoProfileAuthorityCorruption("profile bundle replay authority is invalid")
        return DemoProfileCompilationResult(
            job.id,
            bundle.id,
            desired.id,
            style.id,
            persistent.id,
            session_constraints.id,
            bundle.compilation_digest,
            True,
        )

    def _normalized_now(self) -> datetime:
        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise DemoProfileAuthorityCorruption("profile service clock must be timezone-aware")
        return now.astimezone(UTC)


def _finish_job(
    job: Job,
    attempt: JobAttempt,
    *,
    status: str,
    result_code: str,
    error_code: str | None,
    now: datetime,
) -> None:
    if job.status != "RUNNING" or attempt.status != "RUNNING":
        raise DemoProfileAuthorityCorruption("profile Job cannot finish from its current state")
    attempt.status = status
    attempt.result_code = result_code if status != "FAILED" else None
    attempt.error_code = error_code
    attempt.finished_at = now
    job.status = status
    job.lease_token = None
    job.lease_acquired_at = None
    job.lease_expires_at = None
    job.finalized_at = now
    job.result_code = result_code
    job.updated_at = now


async def _next_version(session: AsyncSession, model: Any, actor_id: str) -> int:
    value = await session.scalar(
        select(func.coalesce(func.max(model.version), 0)).where(model.demo_actor_id == actor_id)
    )
    if type(value) is not int:
        raise DemoProfileAuthorityCorruption("profile version authority is invalid")
    return value + 1


def _authority_row(
    model: Any, identifier: str, schema: str, payload: dict[str, Any], now: datetime
) -> Any:
    return model(
        id=identifier,
        schema_version=schema,
        canonical_payload=payload,
        content_digest=_authority_digest(schema, payload),
        created_at=now,
        **payload,
    )


def _desired_payload(
    binding: DemoJobBinding,
    self_state: DemoSelfState,
    compilation: ProfileCompilation,
    version: int,
    evidence_digests: Sequence[str],
) -> dict[str, Any]:
    return {
        "demo_actor_id": binding.demo_actor_id,
        "demo_session_id": binding.demo_session_id,
        "self_state_id": self_state.id,
        "demo_job_binding_id": binding.id,
        "version": version,
        "as_of_event_sequence": compilation.as_of_event_sequence,
        "compilation_watermark": compilation.compilation_watermark,
        "compiler_version": "demo-profile-compiler-v1",
        "dimensions": {
            item.dimension_key: item.canonical_payload() for item in compilation.desired_deltas
        },
        "evidence_digests": list(evidence_digests),
        "restraint": {
            item.dimension_key: item.restraint.value for item in compilation.desired_deltas
        },
    }


def _style_payload(
    binding: DemoJobBinding,
    compilation: ProfileCompilation,
    version: int,
    desired_id: str,
    evidence_digests: Sequence[str],
) -> dict[str, Any]:
    return {
        "demo_actor_id": binding.demo_actor_id,
        "demo_session_id": binding.demo_session_id,
        "desired_delta_profile_id": desired_id,
        "demo_job_binding_id": binding.id,
        "version": version,
        "as_of_event_sequence": compilation.as_of_event_sequence,
        "compilation_watermark": compilation.compilation_watermark,
        "compiler_version": "demo-profile-compiler-v1",
        "preferences": {"style_keys": list(compilation.style_preferences)},
        "negative_evidence": list(compilation.negative_style_evidence),
        "evidence_digests": list(evidence_digests),
    }


def _constraint_payload(
    actor_id: str,
    self_state_id: str,
    session_id: str | None,
    scope: str,
    version: int,
    constraints: Any,
    source_digests: Sequence[str],
) -> dict[str, Any]:
    return {
        "demo_actor_id": actor_id,
        "demo_session_id": session_id,
        "self_state_id": self_state_id,
        "version": version,
        "constraint_scope": scope,
        "source_event_digests": list(source_digests),
        "locks": {item.dimension_key: item.canonical_payload() for item in constraints.locks},
        "bounds": {
            "maximum_intensity_ppm": {
                key: value for key, value in constraints.maximum_intensity_ppm
            }
        },
        "prohibited_operations": list(constraints.prohibited_operations),
    }


def _bundle_payload(
    binding: DemoJobBinding,
    self_state: DemoSelfState,
    compilation: ProfileCompilation,
    bundle_id: str,
    desired: Any,
    style: Any,
    persistent: Any,
    session_constraints: Any,
) -> dict[str, Any]:
    return {
        "demo_actor_id": binding.demo_actor_id,
        "demo_session_id": binding.demo_session_id,
        "demo_job_binding_id": binding.id,
        "self_state_id": self_state.id,
        "desired_delta_profile_id": desired.id,
        "style_profile_id": style.id,
        "persistent_constraints_id": persistent.id,
        "session_override_constraints_id": session_constraints.id,
        "as_of_event_sequence": compilation.as_of_event_sequence,
        "compilation_watermark": compilation.compilation_watermark,
        "compiler_version": "demo-profile-compiler-v1",
        "input_digest": compilation.input_digest,
        "compilation_digest": compilation.compilation_digest,
    }


def _bundle_compilation_digest(payload: Mapping[str, Any]) -> str:
    value = payload.get("compilation_digest")
    return value if isinstance(value, str) else ""


def _authority_digest(schema: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        schema.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoProfileInputError(f"{name} must be a lowercase hexadecimal ID")


__all__ = [
    "DEMO_SELF_TRANSFER_PROJECTION_CONFIG_DIGEST",
    "DEMO_SELF_TRANSFER_PROJECTION_VERSION",
    "DemoProfileAuthorityCorruption",
    "DemoProfileCompilationResult",
    "DemoProfileCompilationService",
    "DemoProfileInputError",
    "DemoProfileRejected",
    "DemoProfileServiceError",
    "DemoProfileUnavailable",
]
