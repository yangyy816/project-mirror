"""PostgreSQL-authoritative P4 questionnaire application service.

The service consumes the already admitted, read-only D02 bank projection and
the pure P4 posterior/routing modules.  It deliberately has no provider or
runtime dependency: questionnaire media is selected from the admitted bank and
``QUESTIONNAIRE_RUNTIME_GENERATIVE_CALLS`` remains zero.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_idempotency import (
    DemoIdempotencyPayloadConflict,
    DemoIdempotencyTarget,
    DemoSemanticIdempotencyCoordinator,
    canonical_json_bytes,
    idempotency_key_hash,
    semantic_request_digest,
)
from mirror_api.demo_models import (
    DemoCommandBinding,
    DemoJobBinding,
    DemoQuestionBank,
    DemoQuestionnaireRun,
    DemoQuestionnaireStep,
    DemoSelfState,
    DemoSession,
)
from mirror_api.demo_posterior import (
    MapLocation,
    PairwiseChoice,
    PairwiseObservation,
    PosteriorConfig,
    PosteriorError,
    PosteriorResult,
    infer_pairwise_posterior,
)
from mirror_api.demo_questionnaire_bank import (
    AdmittedQuestionBank,
    QuestionBankProjectionError,
    QuestionPairPresentation,
    load_admitted_question_bank,
)
from mirror_api.demo_questionnaire_routing import (
    DimensionProgress,
    QuestionPair,
    RoutingError,
    RoutingPolicy,
    SelfStateMeasurement,
    SelfStateSnapshot,
    decide_stop,
    schedule_questions,
)
from mirror_api.models import Job, JobAttempt, new_id, utcnow

DEMO_QUESTIONNAIRE_RUN_SCHEMA = "mirror.demo/DemoQuestionnaireRun/v1"
DEMO_QUESTIONNAIRE_STEP_SCHEMA = "mirror.demo/DemoQuestionnaireStep/v1"
DEMO_JOB_BINDING_SCHEMA = "mirror.demo/DemoJobBinding/v1"
DEMO_QUESTIONNAIRE_RUN_OPERATION = "questionnaire.run.create"
DEMO_QUESTIONNAIRE_RESPONSE_OPERATION = "questionnaire.response.create"
DEMO_QUESTIONNAIRE_JOB_TYPE = "demo_p3_p7.questionnaire.run.create"
QUESTIONNAIRE_SCHEDULER_VERSION = "demo-self-conditioned-routing-v1"
QUESTIONNAIRE_RUNTIME_GENERATIVE_CALLS = 0

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REQUEST_ID = re.compile(r"^[^\r\n\x00]{8,128}$")


class DemoQuestionnaireError(RuntimeError):
    """Base P4 application failure."""


class DemoQuestionnaireInputError(DemoQuestionnaireError):
    """The caller supplied an invalid application command."""


class DemoQuestionnaireUnavailable(DemoQuestionnaireError):
    """Owner-bound questionnaire authority is unavailable."""


class DemoQuestionnaireConflict(DemoQuestionnaireError):
    """Optimistic step/run version no longer names the current authority."""


class DemoQuestionnaireAuthorityCorruption(DemoQuestionnaireError):
    """Persisted append-only questionnaire evidence cannot be replayed."""


class DemoQuestionnairePayloadConflict(DemoQuestionnaireError):
    code = "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True)
class DemoQuestionnaireConfiguration:
    posterior: PosteriorConfig = field(default_factory=PosteriorConfig)
    routing: RoutingPolicy = field(default_factory=RoutingPolicy)
    scheduler_version: str = QUESTIONNAIRE_SCHEDULER_VERSION

    def validate(self) -> None:
        if self.scheduler_version != QUESTIONNAIRE_SCHEDULER_VERSION:
            raise DemoQuestionnaireInputError("scheduler_version is not supported")
        # Dataclass construction already validates both frozen domain configs.
        if not isinstance(self.posterior, PosteriorConfig) or not isinstance(
            self.routing, RoutingPolicy
        ):
            raise DemoQuestionnaireInputError("P4 domain configuration is invalid")


@dataclass(frozen=True)
class CreateDemoQuestionnaireRun:
    demo_actor_id: str
    demo_session_id: str
    self_state_id: str
    question_bank_version: str
    max_questions: int
    idempotency_key: str
    request_id: str

    def validate(self) -> None:
        for name, value in (
            ("demo_actor_id", self.demo_actor_id),
            ("demo_session_id", self.demo_session_id),
            ("self_state_id", self.self_state_id),
        ):
            _require_id(value, name)
        if not isinstance(self.question_bank_version, str) or not re.fullmatch(
            r"[A-Za-z0-9._-]{1,64}", self.question_bank_version
        ):
            raise DemoQuestionnaireInputError("question_bank_version is invalid")
        if type(self.max_questions) is not int or not 12 <= self.max_questions <= 16:
            raise DemoQuestionnaireInputError("max_questions must be in [12, 16]")
        idempotency_key_hash(self.idempotency_key)
        if _REQUEST_ID.fullmatch(self.request_id) is None:
            raise DemoQuestionnaireInputError("request_id is outside the safe boundary")


@dataclass(frozen=True)
class CreateDemoQuestionnaireResponse:
    demo_actor_id: str
    questionnaire_run_id: str
    selected_side: PairwiseChoice
    expected_step_sequence: int
    expected_run_version: int
    response_latency_ms: int
    idempotency_key: str

    def validate(self) -> None:
        _require_id(self.demo_actor_id, "demo_actor_id")
        _require_id(self.questionnaire_run_id, "questionnaire_run_id")
        if not isinstance(self.selected_side, PairwiseChoice):
            raise DemoQuestionnaireInputError("selected_side is invalid")
        if type(self.expected_step_sequence) is not int or self.expected_step_sequence < 1:
            raise DemoQuestionnaireInputError("expected_step_sequence must be positive")
        if type(self.expected_run_version) is not int or self.expected_run_version < 1:
            raise DemoQuestionnaireInputError("expected_run_version must be positive")
        if (
            type(self.response_latency_ms) is not int
            or not 0 <= self.response_latency_ms <= 3_600_000
        ):
            raise DemoQuestionnaireInputError("response_latency_ms is outside the public boundary")
        idempotency_key_hash(self.idempotency_key)


@dataclass(frozen=True)
class DemoQuestionnaireRunAccepted:
    job_id: str
    questionnaire_run_id: str
    demo_session_id: str
    replayed: bool


@dataclass(frozen=True)
class DemoQuestionnaireStepSnapshot:
    step_id: str
    questionnaire_run_id: str
    event_type: Literal["PRESENTED", "RESPONDED", "STOPPED", "INVALIDATED"]
    step_number: int | None
    step_sequence: int
    run_version: int


@dataclass(frozen=True)
class DemoQuestionnaireNext:
    kind: Literal["QUESTION"]
    snapshot: DemoQuestionnaireStepSnapshot
    question_pair_id: str
    dimension_key: str
    magnitude_ppm: int
    source_identity_id: str
    presentation: QuestionPairPresentation
    routing_score_ppm: int
    routing_components: Mapping[str, int]
    routing_evidence_digest: str


@dataclass(frozen=True)
class DemoQuestionnaireCompleted:
    kind: Literal["COMPLETED"]
    questionnaire_run_id: str
    completed_at: datetime


DemoQuestionnaireNextResult = DemoQuestionnaireNext | DemoQuestionnaireCompleted


class DemoQuestionnaireService:
    """Create and advance owner-bound, append-only questionnaire evidence."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        configuration: DemoQuestionnaireConfiguration = DemoQuestionnaireConfiguration(),
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        configuration.validate()
        self._sessions = session_factory
        self._configuration = configuration
        self._now = now
        self._response_idempotency = DemoSemanticIdempotencyCoordinator(
            session_factory=session_factory
        )

    async def create(self, command: CreateDemoQuestionnaireRun) -> DemoQuestionnaireRunAccepted:
        command.validate()
        key_hash = idempotency_key_hash(command.idempotency_key)
        request_digest = semantic_request_digest(
            {
                "max_questions": command.max_questions,
                "question_bank_version": command.question_bank_version,
                "self_state_id": command.self_state_id,
                "session_id": command.demo_session_id,
            }
        )
        async with self._sessions() as session:
            async with session.begin():
                existing = await self._job_binding_for_key(session, command.demo_actor_id, key_hash)
                if existing is not None:
                    return await self._replay_create(session, existing, request_digest)

                demo_session, self_state, bank_row, bank = await self._lock_create_context(
                    session, command
                )
                now = self._normalized_now()
                job_id = new_id()
                run_id = new_id()
                binding_id = new_id()
                seed = secrets.randbits(63)
                initial_posterior = _initial_posterior(bank, self._configuration.posterior)
                run_payload = _run_payload(
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=demo_session.id,
                    question_bank_id=bank_row.id,
                    self_state_id=self_state.id,
                    algorithm_config_digest=self._configuration.posterior.posterior_config_digest,
                    seed=seed,
                    max_questions=command.max_questions,
                    initial_posterior=initial_posterior,
                )
                job = Job(
                    id=job_id,
                    job_type=DEMO_QUESTIONNAIRE_JOB_TYPE,
                    status="PENDING",
                    idempotency_key_hash=_formal_job_key_hash(command.demo_actor_id, key_hash),
                    request_id=command.request_id,
                    payload={},
                    owner_user_id=None,
                    attempt_count=0,
                    created_at=now,
                    updated_at=now,
                )
                run = DemoQuestionnaireRun(
                    id=run_id,
                    schema_version=DEMO_QUESTIONNAIRE_RUN_SCHEMA,
                    canonical_payload=run_payload,
                    content_digest=_authority_digest(DEMO_QUESTIONNAIRE_RUN_SCHEMA, run_payload),
                    created_at=now,
                    **run_payload,
                )
                binding_payload = _job_binding_payload(
                    demo_actor_id=command.demo_actor_id,
                    demo_session_id=demo_session.id,
                    job_id=job_id,
                    idempotency_key_hash_value=key_hash,
                    request_digest=request_digest,
                    target_id=run_id,
                )
                binding = DemoJobBinding(
                    id=binding_id,
                    schema_version=DEMO_JOB_BINDING_SCHEMA,
                    canonical_payload=binding_payload,
                    content_digest=_authority_digest(DEMO_JOB_BINDING_SCHEMA, binding_payload),
                    created_at=now,
                    **binding_payload,
                )
                try:
                    async with session.begin_nested():
                        # PostgreSQL validates each DemoJobBinding against an
                        # already materialized owner-bound target. Keep all
                        # three rows in one transaction, but flush in authority
                        # dependency order so the trigger never observes a
                        # partial graph.
                        session.add(job)
                        await session.flush()
                        session.add(run)
                        await session.flush()
                        session.add(binding)
                        await session.flush()
                except IntegrityError as exc:
                    winner = await self._job_binding_for_key(
                        session, command.demo_actor_id, key_hash
                    )
                    if winner is None:
                        raise DemoQuestionnaireAuthorityCorruption(
                            "questionnaire create conflict did not expose a reloadable winner"
                        ) from exc
                    return await self._replay_create(session, winner, request_digest)
                return DemoQuestionnaireRunAccepted(job_id, run_id, demo_session.id, False)

    async def next(
        self, *, demo_actor_id: str, questionnaire_run_id: str
    ) -> DemoQuestionnaireNextResult:
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(questionnaire_run_id, "questionnaire_run_id")
        async with self._sessions() as session:
            async with session.begin():
                run = await self._lock_run(session, demo_actor_id, questionnaire_run_id)
                job, current_attempt = await self._lock_run_job(session, run)
                if job.status in {"REJECTED", "FAILED", "CANCELLED"}:
                    raise DemoQuestionnaireConflict(f"questionnaire Job is terminal: {job.status}")
                bank = await self._load_bank(session, run)
                steps = await self._steps(session, run.id, lock=True)
                self_state = await self._self_state(session, run, lock=True)
                state = _replay_state(run, self_state, steps, bank, self._configuration)
                if state.stop_step is not None:
                    self._require_completed_job(job, current_attempt, state.stop_step)
                    return DemoQuestionnaireCompleted(
                        "COMPLETED", run.id, state.stop_step.created_at
                    )
                if job.status == "COMPLETED":
                    raise DemoQuestionnaireAuthorityCorruption(
                        "completed questionnaire Job lacks its STOPPED evidence"
                    )
                if job.status == "PENDING":
                    current_attempt = self._start_job(session, job, self._normalized_now())
                elif job.status != "RUNNING" or current_attempt is None:
                    raise DemoQuestionnaireAuthorityCorruption(
                        "questionnaire Job is not a valid active execution"
                    )
                if state.open_presented is not None:
                    return _next_from_presented(state.open_presented, bank)

                routing_policy = _routing_policy_for_run(run, self._configuration.routing)
                stop = decide_stop(
                    total_questions_asked=state.presented_count,
                    progress=tuple(state.progress.values()),
                    policy=routing_policy,
                )
                if stop.should_stop:
                    now = self._normalized_now()
                    step = _stopped_step(run, state, stop.reason.value, now, self._configuration)
                    session.add(step)
                    self._complete_job(job, current_attempt, stop.reason.value, now)
                    await session.flush()
                    return DemoQuestionnaireCompleted("COMPLETED", run.id, step.created_at)

                plan = schedule_questions(
                    bank=_remaining_bank(bank, steps),
                    self_state=state.self_state,
                    progress=tuple(state.progress.values()),
                    total_questions_asked=state.presented_count,
                    limit=1,
                    policy=routing_policy,
                )
                if len(plan.selected_pair_ids) != 1:
                    raise DemoQuestionnaireUnavailable("no eligible admitted pair can be presented")
                pair_id = plan.selected_pair_ids[0]
                pair = _pair_by_id(bank, pair_id)
                score = next(item for item in plan.scores if item.pair_id == pair_id)
                now = self._normalized_now()
                step = _presented_step(run, state, pair, score, bank, now, self._configuration)
                session.add(step)
                await session.flush()
                return _next_from_presented(step, bank)

    async def respond(
        self, command: CreateDemoQuestionnaireResponse
    ) -> DemoQuestionnaireStepSnapshot:
        command.validate()
        semantic_request = {
            "expected_run_version": command.expected_run_version,
            "expected_step_sequence": command.expected_step_sequence,
            "response_latency_ms": command.response_latency_ms,
            "run_id": command.questionnaire_run_id,
            "selected_side": command.selected_side.value,
        }

        async def create_target(
            session: AsyncSession,
        ) -> DemoIdempotencyTarget[DemoQuestionnaireStep]:
            # A competing transaction may have read no command binding before
            # it waited for the run row.  Reload here so it follows the
            # coordinator's normal conflict/replay path rather than reporting a
            # stale presentation after the winner commits.
            run = await self._lock_run(session, command.demo_actor_id, command.questionnaire_run_id)
            existing = await self._response_target_for_key(
                session, command.demo_actor_id, command.idempotency_key
            )
            if existing is not None:
                return existing
            job, current_attempt = await self._lock_run_job(session, run)
            if job.status != "RUNNING" or current_attempt is None:
                raise DemoQuestionnaireConflict("questionnaire Job is not RUNNING")
            bank = await self._load_bank(session, run)
            steps = await self._steps(session, run.id, lock=True)
            self_state = await self._self_state(session, run, lock=True)
            state = _replay_state(run, self_state, steps, bank, self._configuration)
            presented = state.open_presented
            if state.stop_step is not None:
                raise DemoQuestionnaireConflict("questionnaire run is terminal")
            if presented is None:
                raise DemoQuestionnaireConflict("questionnaire run has no unanswered presentation")
            if presented.event_sequence != command.expected_step_sequence:
                raise DemoQuestionnaireConflict("expected_step_sequence is stale")
            if state.run_version != command.expected_run_version:
                raise DemoQuestionnaireConflict("expected_run_version is stale")
            pair = _pair_by_id(bank, _presented_pair_id(presented))
            before = _posterior_snapshot(state.posteriors)
            updated = dict(state.posteriors)
            observations = list(state.observations[pair.dimension_id])
            observations.append(
                PairwiseObservation(
                    dimension_key=pair.dimension_id,
                    left_delta_ppm=-pair.magnitude_ppm,
                    right_delta_ppm=pair.magnitude_ppm,
                    magnitude_ppm=pair.magnitude_ppm,
                    stimulus_config_version=bank.config_digest,
                    posterior_config_digest=self._configuration.posterior.posterior_config_digest,
                    choice=command.selected_side,
                )
            )
            updated[pair.dimension_id] = infer_pairwise_posterior(
                observations, self._configuration.posterior
            )
            after = _posterior_snapshot(updated)
            _require_only_target_dimension_changed(before, after, pair.dimension_id)
            now = self._normalized_now()
            step = _responded_step(
                run,
                state,
                presented,
                pair,
                command,
                before,
                after,
                now,
                self._configuration,
            )
            session.add(step)
            return DemoIdempotencyTarget(step, step.id, run.demo_session_id)

        async def load_target(
            session: AsyncSession, binding: DemoCommandBinding
        ) -> DemoIdempotencyTarget[DemoQuestionnaireStep] | None:
            step = await session.get(DemoQuestionnaireStep, binding.response_id)
            if (
                step is None
                or step.demo_actor_id != command.demo_actor_id
                or step.questionnaire_run_id != command.questionnaire_run_id
                or step.event_type != "RESPONDED"
            ):
                return None
            return DemoIdempotencyTarget(step, step.id, step.demo_session_id)

        try:
            result = await self._response_idempotency.execute(
                demo_actor_id=command.demo_actor_id,
                endpoint_operation=DEMO_QUESTIONNAIRE_RESPONSE_OPERATION,
                idempotency_key=command.idempotency_key,
                semantic_request=semantic_request,
                create_target=create_target,
                load_target=load_target,
            )
        except DemoIdempotencyPayloadConflict as exc:
            raise DemoQuestionnairePayloadConflict() from exc
        step = result.value
        return _step_snapshot(step)

    async def snapshot(
        self, *, demo_actor_id: str, questionnaire_run_id: str
    ) -> DemoQuestionnaireRunAccepted:
        """Return owner-bound create authority without leaking its command key."""
        _require_id(demo_actor_id, "demo_actor_id")
        _require_id(questionnaire_run_id, "questionnaire_run_id")
        async with self._sessions() as session:
            run = await self._load_run(session, demo_actor_id, questionnaire_run_id)
            binding = cast(
                DemoJobBinding | None,
                await session.scalar(
                    select(DemoJobBinding).where(
                        DemoJobBinding.target_type == "QUESTIONNAIRE_RUN",
                        DemoJobBinding.target_id == run.id,
                        DemoJobBinding.demo_actor_id == demo_actor_id,
                    )
                ),
            )
            if binding is None:
                raise DemoQuestionnaireAuthorityCorruption("run lacks its Job binding")
            return DemoQuestionnaireRunAccepted(binding.job_id, run.id, run.demo_session_id, True)

    async def _lock_create_context(
        self, session: AsyncSession, command: CreateDemoQuestionnaireRun
    ) -> tuple[DemoSession, DemoSelfState, DemoQuestionBank, AdmittedQuestionBank]:
        demo_session = cast(
            DemoSession | None,
            await session.scalar(
                select(DemoSession)
                .where(
                    DemoSession.id == command.demo_session_id,
                    DemoSession.demo_actor_id == command.demo_actor_id,
                    DemoSession.closed_at.is_(None),
                    DemoSession.tombstoned_at.is_(None),
                )
                .with_for_update()
            ),
        )
        if demo_session is None:
            raise DemoQuestionnaireUnavailable("active owner-bound Demo session is unavailable")
        self_state = cast(
            DemoSelfState | None,
            await session.scalar(
                select(DemoSelfState)
                .where(
                    DemoSelfState.id == command.self_state_id,
                    DemoSelfState.demo_actor_id == command.demo_actor_id,
                    DemoSelfState.demo_session_id == command.demo_session_id,
                )
                .with_for_update()
            ),
        )
        if self_state is None:
            raise DemoQuestionnaireUnavailable("owner-bound SelfState is unavailable")
        bank_row = await session.scalar(
            select(DemoQuestionBank).where(
                DemoQuestionBank.version == command.question_bank_version
            )
        )
        if bank_row is None:
            raise DemoQuestionnaireUnavailable("requested QuestionBank version is unavailable")
        bank = await self._load_bank_by_id(session, bank_row.id)
        return demo_session, self_state, bank_row, bank

    async def _load_bank(
        self, session: AsyncSession, run: DemoQuestionnaireRun
    ) -> AdmittedQuestionBank:
        bank = await self._load_bank_by_id(session, run.question_bank_id)
        if run.algorithm_config_digest != self._configuration.posterior.posterior_config_digest:
            raise DemoQuestionnaireAuthorityCorruption("run algorithm config is incompatible")
        return bank

    @staticmethod
    async def _load_bank_by_id(session: AsyncSession, bank_id: str) -> AdmittedQuestionBank:
        try:
            return await load_admitted_question_bank(session, bank_id)
        except QuestionBankProjectionError as exc:
            raise DemoQuestionnaireUnavailable("admitted QuestionBank is unavailable") from exc

    @staticmethod
    async def _self_state(
        session: AsyncSession, run: DemoQuestionnaireRun, *, lock: bool
    ) -> DemoSelfState:
        statement = select(DemoSelfState).where(
            DemoSelfState.id == run.self_state_id,
            DemoSelfState.demo_actor_id == run.demo_actor_id,
            DemoSelfState.demo_session_id == run.demo_session_id,
        )
        if lock:
            statement = statement.with_for_update()
        self_state = cast(DemoSelfState | None, await session.scalar(statement))
        if self_state is None:
            raise DemoQuestionnaireAuthorityCorruption("run SelfState authority is unavailable")
        return self_state

    @staticmethod
    async def _job_binding_for_key(
        session: AsyncSession, actor_id: str, key_hash: str
    ) -> DemoJobBinding | None:
        return cast(
            DemoJobBinding | None,
            await session.scalar(
                select(DemoJobBinding).where(
                    DemoJobBinding.demo_actor_id == actor_id,
                    DemoJobBinding.endpoint_operation == DEMO_QUESTIONNAIRE_RUN_OPERATION,
                    DemoJobBinding.idempotency_key_hash == key_hash,
                )
            ),
        )

    @staticmethod
    async def _response_target_for_key(
        session: AsyncSession, actor_id: str, idempotency_key: str
    ) -> DemoIdempotencyTarget[DemoQuestionnaireStep] | None:
        binding = cast(
            DemoCommandBinding | None,
            await session.scalar(
                select(DemoCommandBinding).where(
                    DemoCommandBinding.demo_actor_id == actor_id,
                    DemoCommandBinding.endpoint_operation == DEMO_QUESTIONNAIRE_RESPONSE_OPERATION,
                    DemoCommandBinding.idempotency_key_hash
                    == idempotency_key_hash(idempotency_key),
                )
            ),
        )
        if binding is None:
            return None
        step = await session.get(DemoQuestionnaireStep, binding.response_id)
        if step is None:
            raise DemoQuestionnaireAuthorityCorruption("response idempotency winner is missing")
        return DemoIdempotencyTarget(step, step.id, step.demo_session_id)

    async def _replay_create(
        self, session: AsyncSession, binding: DemoJobBinding, request_digest: str
    ) -> DemoQuestionnaireRunAccepted:
        if (
            binding.endpoint_operation != DEMO_QUESTIONNAIRE_RUN_OPERATION
            or binding.target_type != "QUESTIONNAIRE_RUN"
            or binding.request_digest != request_digest
        ):
            if binding.request_digest != request_digest:
                raise DemoQuestionnairePayloadConflict()
            raise DemoQuestionnaireAuthorityCorruption("QuestionnaireRun Job binding is invalid")
        run = await session.get(DemoQuestionnaireRun, binding.target_id)
        job = await session.get(Job, binding.job_id)
        if (
            run is None
            or job is None
            or run.demo_actor_id != binding.demo_actor_id
            or run.demo_session_id != binding.demo_session_id
            or job.job_type != DEMO_QUESTIONNAIRE_JOB_TYPE
            or job.payload != {}
        ):
            raise DemoQuestionnaireAuthorityCorruption(
                "QuestionnaireRun idempotency winner is invalid"
            )
        return DemoQuestionnaireRunAccepted(binding.job_id, run.id, run.demo_session_id, True)

    @staticmethod
    async def _lock_run(session: AsyncSession, actor_id: str, run_id: str) -> DemoQuestionnaireRun:
        run = cast(
            DemoQuestionnaireRun | None,
            await session.scalar(
                select(DemoQuestionnaireRun)
                .where(
                    DemoQuestionnaireRun.id == run_id,
                    DemoQuestionnaireRun.demo_actor_id == actor_id,
                )
                .with_for_update()
            ),
        )
        if run is None:
            raise DemoQuestionnaireUnavailable("owner-bound QuestionnaireRun is unavailable")
        return run

    @staticmethod
    async def _lock_run_job(
        session: AsyncSession, run: DemoQuestionnaireRun
    ) -> tuple[Job, JobAttempt | None]:
        row = (
            await session.execute(
                select(Job, DemoJobBinding)
                .join(DemoJobBinding, DemoJobBinding.job_id == Job.id)
                .where(
                    DemoJobBinding.endpoint_operation == DEMO_QUESTIONNAIRE_RUN_OPERATION,
                    DemoJobBinding.target_type == "QUESTIONNAIRE_RUN",
                    DemoJobBinding.target_id == run.id,
                    DemoJobBinding.demo_actor_id == run.demo_actor_id,
                    DemoJobBinding.demo_session_id == run.demo_session_id,
                )
                .with_for_update(of=Job)
            )
        ).one_or_none()
        if row is None:
            raise DemoQuestionnaireAuthorityCorruption("QuestionnaireRun lacks its Job authority")
        job, binding = row
        expected_binding_payload = _job_binding_payload(
            demo_actor_id=run.demo_actor_id,
            demo_session_id=run.demo_session_id,
            job_id=job.id,
            idempotency_key_hash_value=binding.idempotency_key_hash,
            request_digest=binding.request_digest,
            target_id=run.id,
        )
        if (
            binding.schema_version != DEMO_JOB_BINDING_SCHEMA
            or binding.canonical_payload != expected_binding_payload
            or binding.content_digest
            != _authority_digest(DEMO_JOB_BINDING_SCHEMA, expected_binding_payload)
            or job.job_type != DEMO_QUESTIONNAIRE_JOB_TYPE
            or job.idempotency_key_hash
            != _formal_job_key_hash(run.demo_actor_id, binding.idempotency_key_hash)
            or job.payload != {}
            or job.owner_user_id is not None
            or job.ingestion_upload_intent_id is not None
            or job.result_asset_id is not None
        ):
            raise DemoQuestionnaireAuthorityCorruption("questionnaire Job envelope is invalid")
        attempts = list(
            (
                await session.scalars(
                    select(JobAttempt)
                    .where(JobAttempt.job_id == job.id)
                    .order_by(JobAttempt.attempt)
                    .with_for_update()
                )
            ).all()
        )
        if job.attempt_count != len(attempts) or len(attempts) > 1:
            raise DemoQuestionnaireAuthorityCorruption(
                "questionnaire Job attempt cardinality is invalid"
            )
        current_attempt = attempts[-1] if attempts else None
        if job.status == "PENDING":
            if (
                current_attempt is not None
                or job.attempt_count != 0
                or job.lease_token is not None
                or job.lease_acquired_at is not None
                or job.lease_expires_at is not None
                or job.finalized_at is not None
                or job.result_code is not None
            ):
                raise DemoQuestionnaireAuthorityCorruption(
                    "PENDING questionnaire Job shape is invalid"
                )
        elif job.status == "RUNNING":
            if (
                current_attempt is None
                or current_attempt.attempt != 1
                or current_attempt.status != "RUNNING"
                or current_attempt.lease_token is not None
                or current_attempt.finished_at is not None
                or current_attempt.result_code is not None
                or current_attempt.error_code is not None
                or job.lease_token is not None
                or job.lease_acquired_at is not None
                or job.lease_expires_at is not None
                or job.finalized_at is not None
                or job.result_code is not None
            ):
                raise DemoQuestionnaireAuthorityCorruption(
                    "RUNNING questionnaire Job shape is invalid"
                )
        elif job.status in {"COMPLETED", "REJECTED", "FAILED", "CANCELLED"}:
            if (
                job.finalized_at is None
                or job.result_code is None
                or job.lease_token is not None
                or job.lease_acquired_at is not None
                or job.lease_expires_at is not None
            ):
                raise DemoQuestionnaireAuthorityCorruption(
                    "terminal questionnaire Job shape is invalid"
                )
            if current_attempt is not None and (
                current_attempt.status != job.status
                or current_attempt.finished_at is None
                or (
                    job.status == "FAILED"
                    and (
                        current_attempt.error_code != job.result_code
                        or current_attempt.result_code is not None
                    )
                )
                or (
                    job.status != "FAILED"
                    and (
                        current_attempt.result_code != job.result_code
                        or current_attempt.error_code is not None
                    )
                )
            ):
                raise DemoQuestionnaireAuthorityCorruption(
                    "terminal questionnaire Job and Attempt disagree"
                )
            if current_attempt is None and job.status != "CANCELLED":
                raise DemoQuestionnaireAuthorityCorruption(
                    "only pre-start cancellation may be zero-attempt terminal"
                )
        else:
            raise DemoQuestionnaireAuthorityCorruption("questionnaire Job status is invalid")
        return job, current_attempt

    @staticmethod
    def _start_job(session: AsyncSession, job: Job, now: datetime) -> JobAttempt:
        if job.status != "PENDING" or job.attempt_count != 0:
            raise DemoQuestionnaireAuthorityCorruption(
                "questionnaire Job cannot start from its current state"
            )
        attempt = JobAttempt(
            id=new_id(),
            job_id=job.id,
            attempt=1,
            status="RUNNING",
            lease_token=None,
            started_at=now,
        )
        session.add(attempt)
        job.status = "RUNNING"
        job.attempt_count = 1
        job.updated_at = now
        return attempt

    @staticmethod
    def _complete_job(job: Job, attempt: JobAttempt, reason: str, now: datetime) -> None:
        if job.status != "RUNNING" or attempt.status != "RUNNING":
            raise DemoQuestionnaireAuthorityCorruption(
                "questionnaire Job cannot complete from its current state"
            )
        attempt.status = "COMPLETED"
        attempt.result_code = reason
        attempt.error_code = None
        attempt.finished_at = now
        job.status = "COMPLETED"
        job.finalized_at = now
        job.result_code = reason
        job.updated_at = now

    @staticmethod
    def _require_completed_job(
        job: Job, attempt: JobAttempt | None, stop_step: DemoQuestionnaireStep
    ) -> None:
        reason = (
            None
            if stop_step.response_snapshot is None
            else stop_step.response_snapshot.get("reason")
        )
        if (
            job.status != "COMPLETED"
            or attempt is None
            or attempt.status != "COMPLETED"
            or not isinstance(reason, str)
            or job.result_code != reason
            or attempt.result_code != reason
        ):
            raise DemoQuestionnaireAuthorityCorruption(
                "STOPPED questionnaire evidence disagrees with Job completion"
            )

    @staticmethod
    async def _load_run(session: AsyncSession, actor_id: str, run_id: str) -> DemoQuestionnaireRun:
        run = cast(
            DemoQuestionnaireRun | None,
            await session.scalar(
                select(DemoQuestionnaireRun).where(
                    DemoQuestionnaireRun.id == run_id,
                    DemoQuestionnaireRun.demo_actor_id == actor_id,
                )
            ),
        )
        if run is None:
            raise DemoQuestionnaireUnavailable("owner-bound QuestionnaireRun is unavailable")
        return run

    @staticmethod
    async def _steps(
        session: AsyncSession, run_id: str, *, lock: bool
    ) -> tuple[DemoQuestionnaireStep, ...]:
        statement = (
            select(DemoQuestionnaireStep)
            .where(DemoQuestionnaireStep.questionnaire_run_id == run_id)
            .order_by(DemoQuestionnaireStep.event_sequence)
        )
        if lock:
            statement = statement.with_for_update()
        return tuple((await session.scalars(statement)).all())

    def _normalized_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise DemoQuestionnaireAuthorityCorruption("clock must be timezone-aware")
        return value.astimezone(UTC)


@dataclass(frozen=True)
class _RunState:
    self_state: SelfStateSnapshot
    posteriors: Mapping[str, PosteriorResult]
    observations: Mapping[str, tuple[PairwiseObservation, ...]]
    progress: Mapping[str, DimensionProgress]
    presented_count: int
    next_event_sequence: int
    run_version: int
    open_presented: DemoQuestionnaireStep | None
    stop_step: DemoQuestionnaireStep | None


def _replay_state(
    run: DemoQuestionnaireRun,
    self_state_row: DemoSelfState,
    steps: Sequence[DemoQuestionnaireStep],
    bank: AdmittedQuestionBank,
    configuration: DemoQuestionnaireConfiguration,
) -> _RunState:
    self_state = _self_state_snapshot(self_state_row, bank)
    dimensions = tuple(sorted({pair.dimension_id for pair in bank.pairs}))
    posteriors = _posterior_from_initial(run.initial_posterior, dimensions, configuration.posterior)
    observations: dict[str, list[PairwiseObservation]] = {dimension: [] for dimension in dimensions}
    response_pairs: dict[str, list[QuestionPair]] = {dimension: [] for dimension in dimensions}
    presented_by_number: dict[int, DemoQuestionnaireStep] = {}
    answered_numbers: set[int] = set()
    open_presented: DemoQuestionnaireStep | None = None
    stop_step: DemoQuestionnaireStep | None = None
    expected_sequence = 1
    for step in steps:
        if (
            step.demo_actor_id != run.demo_actor_id
            or step.demo_session_id != run.demo_session_id
            or step.questionnaire_run_id != run.id
            or step.event_sequence != expected_sequence
        ):
            raise DemoQuestionnaireAuthorityCorruption("questionnaire event sequence is invalid")
        expected_sequence += 1
        if step.event_type == "PRESENTED":
            if (
                stop_step is not None
                or step.step_number is None
                or step.step_number in presented_by_number
            ):
                raise DemoQuestionnaireAuthorityCorruption("presentation state is invalid")
            _require_step_posterior(step, posteriors)
            if step.posterior_after != _posterior_snapshot(posteriors):
                raise DemoQuestionnaireAuthorityCorruption(
                    "presentation posterior_after does not replay"
                )
            presented_by_number[step.step_number] = step
            open_presented = step
        elif step.event_type == "RESPONDED":
            if (
                stop_step is not None
                or step.step_number is None
                or step.step_number in answered_numbers
            ):
                raise DemoQuestionnaireAuthorityCorruption("response state is invalid")
            presented = presented_by_number.get(step.step_number)
            if presented is None or open_presented is None or open_presented.id != presented.id:
                raise DemoQuestionnaireAuthorityCorruption(
                    "response does not match the open presentation"
                )
            pair_id = _presented_pair_id(presented)
            if step.question_pair_id != pair_id:
                raise DemoQuestionnaireAuthorityCorruption(
                    "response pair differs from presentation"
                )
            pair = _pair_by_id(bank, pair_id)
            choice = _response_choice(step)
            _require_step_posterior(step, posteriors)
            observation = PairwiseObservation(
                dimension_key=pair.dimension_id,
                left_delta_ppm=-pair.magnitude_ppm,
                right_delta_ppm=pair.magnitude_ppm,
                magnitude_ppm=pair.magnitude_ppm,
                stimulus_config_version=bank.config_digest,
                posterior_config_digest=configuration.posterior.posterior_config_digest,
                choice=choice,
            )
            observations[pair.dimension_id].append(observation)
            response_pairs[pair.dimension_id].append(pair)
            updated = infer_pairwise_posterior(
                observations[pair.dimension_id], configuration.posterior
            )
            after = _posterior_snapshot({**posteriors, pair.dimension_id: updated})
            if step.posterior_after != after:
                raise DemoQuestionnaireAuthorityCorruption("response posterior replay differs")
            posteriors[pair.dimension_id] = updated
            answered_numbers.add(step.step_number)
            open_presented = None
        elif step.event_type == "STOPPED":
            if stop_step is not None or open_presented is not None or step.step_number is not None:
                raise DemoQuestionnaireAuthorityCorruption("stop state is invalid")
            _require_step_posterior(step, posteriors)
            if step.posterior_after != _posterior_snapshot(posteriors):
                raise DemoQuestionnaireAuthorityCorruption("stop posterior_after does not replay")
            stop_step = step
        else:
            raise DemoQuestionnaireAuthorityCorruption("unsupported questionnaire event type")
    progress = _progress(dimensions, posteriors, observations, response_pairs)
    return _RunState(
        self_state,
        dict(posteriors),
        {key: tuple(value) for key, value in observations.items()},
        progress,
        len(presented_by_number),
        expected_sequence,
        expected_sequence,
        open_presented,
        stop_step,
    )


def _initial_posterior(bank: AdmittedQuestionBank, config: PosteriorConfig) -> dict[str, Any]:
    dimensions = tuple(sorted({pair.dimension_id for pair in bank.pairs}))
    return _posterior_snapshot(
        {dimension: infer_pairwise_posterior((), config) for dimension in dimensions}
    )


def _posterior_from_initial(
    value: object, dimensions: Sequence[str], config: PosteriorConfig
) -> dict[str, PosteriorResult]:
    if not isinstance(value, Mapping) or set(value) != set(dimensions):
        raise DemoQuestionnaireAuthorityCorruption("initial posterior dimensions are invalid")
    results: dict[str, PosteriorResult] = {}
    for dimension in dimensions:
        payload = value.get(dimension)
        results[dimension] = _posterior_from_payload(payload, config)
        expected = infer_pairwise_posterior((), config)
        if results[dimension] != expected:
            raise DemoQuestionnaireAuthorityCorruption("initial posterior does not replay")
    return results


def _posterior_from_payload(value: object, config: PosteriorConfig) -> PosteriorResult:
    if not isinstance(value, Mapping):
        raise DemoQuestionnaireAuthorityCorruption("posterior snapshot is invalid")
    try:
        result = PosteriorResult(
            result_schema_version=cast(str, value["result_schema_version"]),
            algorithm_version=cast(str, value["algorithm_version"]),
            posterior_config_digest=cast(str, value["posterior_config_digest"]),
            evidence_digest=cast(str, value["evidence_digest"]),
            posterior_mean_ppm=cast(int, value["posterior_mean_ppm"]),
            map_location=MapLocation(cast(str, value["map_location"])),
            laplace_sd_ppm=cast(int, value["laplace_sd_ppm"]),
            posterior_sd_ppm=cast(int, value["posterior_sd_ppm"]),
            confidence_ppm=cast(int, value["confidence_ppm"]),
            consistency_ppm=cast(int, value["consistency_ppm"]),
        )
    except (KeyError, TypeError, ValueError, PosteriorError) as exc:
        raise DemoQuestionnaireAuthorityCorruption("posterior snapshot cannot be parsed") from exc
    if (
        result.canonical_payload() != dict(value)
        or result.posterior_config_digest != config.posterior_config_digest
    ):
        raise DemoQuestionnaireAuthorityCorruption("posterior snapshot authority is invalid")
    return result


def _posterior_snapshot(posteriors: Mapping[str, PosteriorResult]) -> dict[str, Any]:
    return {key: posteriors[key].canonical_payload() for key in sorted(posteriors)}


def _self_state_snapshot(
    self_state: DemoSelfState, bank: AdmittedQuestionBank
) -> SelfStateSnapshot:
    measurements: list[SelfStateMeasurement] = []
    dimensions = {pair.dimension_id for pair in bank.pairs}
    for dimension in sorted(dimensions):
        value = self_state.measurements.get(dimension)
        reliability = self_state.reliability.get(dimension)
        eligibility = self_state.routing_eligibility.get(dimension)
        if (
            type(value) is not int
            or type(reliability) is not int
            or not isinstance(eligibility, str)
        ):
            raise DemoQuestionnaireAuthorityCorruption("SelfState snapshot dimension is missing")
        try:
            measurements.append(
                SelfStateMeasurement(
                    dimension,
                    value,
                    reliability,
                    eligibility == "ROUTING_ELIGIBLE",
                )
            )
        except (KeyError, RoutingError) as exc:
            raise DemoQuestionnaireAuthorityCorruption("SelfState snapshot is invalid") from exc
    return SelfStateSnapshot(self_state.id, tuple(measurements))


def _progress(
    dimensions: Sequence[str],
    posteriors: Mapping[str, PosteriorResult],
    observations: Mapping[str, Sequence[PairwiseObservation]],
    response_pairs: Mapping[str, Sequence[QuestionPair]],
) -> dict[str, DimensionProgress]:
    result: dict[str, DimensionProgress] = {}
    for dimension in dimensions:
        entries = observations[dimension]
        effective = tuple(entry for entry in entries if entry.choice is not PairwiseChoice.SKIP)
        effective_pairs = tuple(
            pair
            for pair, entry in zip(response_pairs[dimension], entries, strict=True)
            if entry.choice is not PairwiseChoice.SKIP
        )
        result[dimension] = DimensionProgress(
            dimension,
            posteriors[dimension],
            len(effective),
            tuple(sorted({entry.magnitude_ppm for entry in effective})),
            tuple(sorted({pair.source_identity_id for pair in effective_pairs})),
        )
    return result


def _routing_policy_for_run(run: DemoQuestionnaireRun, policy: RoutingPolicy) -> RoutingPolicy:
    """Bind scheduling and stopping to the immutable per-run question budget."""

    if type(run.max_questions) is not int or not 12 <= run.max_questions <= 16:
        raise DemoQuestionnaireAuthorityCorruption("QuestionnaireRun max_questions is invalid")
    return replace(policy, maximum_questions=run.max_questions)


def _run_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str,
    question_bank_id: object,
    self_state_id: str,
    algorithm_config_digest: str,
    seed: int,
    max_questions: int,
    initial_posterior: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(question_bank_id, str):
        raise DemoQuestionnaireAuthorityCorruption("projected QuestionBank id is invalid")
    return {
        "algorithm_config_digest": algorithm_config_digest,
        "demo_actor_id": demo_actor_id,
        "demo_session_id": demo_session_id,
        "initial_posterior": dict(initial_posterior),
        "max_questions": max_questions,
        "question_bank_id": question_bank_id,
        "seed": seed,
        "self_state_id": self_state_id,
    }


def _job_binding_payload(
    *,
    demo_actor_id: str,
    demo_session_id: str,
    job_id: str,
    idempotency_key_hash_value: str,
    request_digest: str,
    target_id: str,
) -> dict[str, str]:
    return {
        "demo_actor_id": demo_actor_id,
        "demo_session_id": demo_session_id,
        "endpoint_operation": DEMO_QUESTIONNAIRE_RUN_OPERATION,
        "idempotency_key_hash": idempotency_key_hash_value,
        "job_id": job_id,
        "request_digest": request_digest,
        "target_id": target_id,
        "target_type": "QUESTIONNAIRE_RUN",
    }


def _presented_step(
    run: DemoQuestionnaireRun,
    state: _RunState,
    pair: QuestionPair,
    score: Any,
    bank: AdmittedQuestionBank,
    now: datetime,
    configuration: DemoQuestionnaireConfiguration,
) -> DemoQuestionnaireStep:
    components = {
        "contradiction_priority_ppm": score.contradiction_priority_ppm,
        "coverage_need_ppm": score.coverage_need_ppm,
        "expected_fisher_information_ppm": score.expected_fisher_information_ppm,
        "morphology_neighborhood_compatibility_ppm": (
            score.morphology_neighborhood_compatibility_ppm
        ),
        "pair_quality_ppm": score.pair_quality_ppm,
        "posterior_uncertainty_ppm": score.posterior_uncertainty_ppm,
        "self_state_reliability_ppm": score.self_state_reliability_ppm,
    }
    routing = {
        "question_pair_id": pair.pair_id,
        "routing_components": components,
        "routing_evidence_digest": _routing_evidence_digest(run, state, pair, bank, components),
        "routing_score_ppm": score.score_ppm,
        "run_version": state.run_version + 1,
    }
    before = _posterior_snapshot(state.posteriors)
    payload = {
        "demo_actor_id": run.demo_actor_id,
        "demo_session_id": run.demo_session_id,
        "event_sequence": state.next_event_sequence,
        "event_type": "PRESENTED",
        "posterior_after": before,
        "posterior_before": before,
        "question_pair_id": pair.pair_id,
        "questionnaire_run_id": run.id,
        "response_snapshot": None,
        "routing_snapshot": routing,
        "scheduler_version": configuration.scheduler_version,
        "step_number": state.presented_count + 1,
    }
    return DemoQuestionnaireStep(
        id=new_id(),
        schema_version=DEMO_QUESTIONNAIRE_STEP_SCHEMA,
        canonical_payload=payload,
        content_digest=_authority_digest(DEMO_QUESTIONNAIRE_STEP_SCHEMA, payload),
        created_at=now,
        **payload,
    )


def _responded_step(
    run: DemoQuestionnaireRun,
    state: _RunState,
    presented: DemoQuestionnaireStep,
    pair: QuestionPair,
    command: CreateDemoQuestionnaireResponse,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    now: datetime,
    configuration: DemoQuestionnaireConfiguration,
) -> DemoQuestionnaireStep:
    routing = dict(presented.routing_snapshot)
    routing["run_version"] = state.run_version + 1
    response = {
        "choice": command.selected_side.value,
        "presented_step_digest": presented.content_digest,
        "response_latency_ms": command.response_latency_ms,
    }
    payload = {
        "demo_actor_id": run.demo_actor_id,
        "demo_session_id": run.demo_session_id,
        "event_sequence": state.next_event_sequence,
        "event_type": "RESPONDED",
        "posterior_after": dict(after),
        "posterior_before": dict(before),
        "question_pair_id": pair.pair_id,
        "questionnaire_run_id": run.id,
        "response_snapshot": response,
        "routing_snapshot": routing,
        "scheduler_version": configuration.scheduler_version,
        "step_number": presented.step_number,
    }
    return DemoQuestionnaireStep(
        id=new_id(),
        schema_version=DEMO_QUESTIONNAIRE_STEP_SCHEMA,
        canonical_payload=payload,
        content_digest=_authority_digest(DEMO_QUESTIONNAIRE_STEP_SCHEMA, payload),
        created_at=now,
        **payload,
    )


def _stopped_step(
    run: DemoQuestionnaireRun,
    state: _RunState,
    reason: str,
    now: datetime,
    configuration: DemoQuestionnaireConfiguration,
) -> DemoQuestionnaireStep:
    posterior = _posterior_snapshot(state.posteriors)
    payload = {
        "demo_actor_id": run.demo_actor_id,
        "demo_session_id": run.demo_session_id,
        "event_sequence": state.next_event_sequence,
        "event_type": "STOPPED",
        "posterior_after": posterior,
        "posterior_before": posterior,
        "question_pair_id": None,
        "questionnaire_run_id": run.id,
        "response_snapshot": {"reason": reason},
        "routing_snapshot": {"reason": reason, "run_version": state.run_version + 1},
        "scheduler_version": configuration.scheduler_version,
        "step_number": None,
    }
    return DemoQuestionnaireStep(
        id=new_id(),
        schema_version=DEMO_QUESTIONNAIRE_STEP_SCHEMA,
        canonical_payload=payload,
        content_digest=_authority_digest(DEMO_QUESTIONNAIRE_STEP_SCHEMA, payload),
        created_at=now,
        **payload,
    )


def _next_from_presented(
    step: DemoQuestionnaireStep, bank: AdmittedQuestionBank
) -> DemoQuestionnaireNext:
    pair = _pair_by_id(bank, _presented_pair_id(step))
    presentation = bank.presentations.get(pair.pair_id)
    if presentation is None:
        raise DemoQuestionnaireAuthorityCorruption(
            "QuestionPair presentation authority is unavailable"
        )
    routing = step.routing_snapshot
    components = routing.get("routing_components")
    digest = routing.get("routing_evidence_digest")
    score = routing.get("routing_score_ppm")
    if (
        not isinstance(components, Mapping)
        or any(type(value) is not int for value in components.values())
        or not isinstance(digest, str)
        or _DIGEST.fullmatch(digest) is None
        or type(score) is not int
    ):
        raise DemoQuestionnaireAuthorityCorruption("presented routing snapshot is invalid")
    return DemoQuestionnaireNext(
        "QUESTION",
        _step_snapshot(step),
        pair.pair_id,
        pair.dimension_id,
        pair.magnitude_ppm,
        pair.source_identity_id,
        presentation,
        score,
        dict(cast(Mapping[str, int], components)),
        digest,
    )


def _step_snapshot(step: DemoQuestionnaireStep) -> DemoQuestionnaireStepSnapshot:
    run_version = step.routing_snapshot.get("run_version")
    if type(run_version) is not int or run_version < 1:
        raise DemoQuestionnaireAuthorityCorruption("step run version is invalid")
    return DemoQuestionnaireStepSnapshot(
        step.id,
        step.questionnaire_run_id,
        cast(Literal["PRESENTED", "RESPONDED", "STOPPED", "INVALIDATED"], step.event_type),
        step.step_number,
        step.event_sequence,
        run_version,
    )


def _presented_pair_id(step: DemoQuestionnaireStep) -> str:
    pair_id = step.routing_snapshot.get("question_pair_id")
    if step.question_pair_id != pair_id or not isinstance(pair_id, str):
        raise DemoQuestionnaireAuthorityCorruption("presentation pair authority is invalid")
    return pair_id


def _response_choice(step: DemoQuestionnaireStep) -> PairwiseChoice:
    value = (step.response_snapshot or {}).get("choice")
    try:
        return PairwiseChoice(cast(str, value))
    except ValueError as exc:
        raise DemoQuestionnaireAuthorityCorruption("response choice is invalid") from exc


def _require_step_posterior(
    step: DemoQuestionnaireStep, posteriors: Mapping[str, PosteriorResult]
) -> None:
    expected = _posterior_snapshot(posteriors)
    if step.posterior_before != expected:
        raise DemoQuestionnaireAuthorityCorruption("step posterior_before does not replay")


def _pair_by_id(bank: AdmittedQuestionBank, pair_id: str) -> QuestionPair:
    for pair in bank.pairs:
        if pair.pair_id == pair_id:
            return pair
    raise DemoQuestionnaireAuthorityCorruption("QuestionPair is not in the admitted bank")


def _remaining_bank(
    bank: AdmittedQuestionBank, steps: Sequence[DemoQuestionnaireStep]
) -> AdmittedQuestionBank:
    presented_pair_ids = {
        _presented_pair_id(step) for step in steps if step.event_type == "PRESENTED"
    }
    remaining = tuple(pair for pair in bank.pairs if pair.pair_id not in presented_pair_ids)
    return AdmittedQuestionBank(
        remaining,
        bank.morphology_scale_ppm,
        bank.morphology_scale_floor_ppm,
        bank.config_digest,
        bank.projection_digest,
        bank.canonical_payload,
        bank.presentations,
    )


def _require_only_target_dimension_changed(
    before: Mapping[str, Any], after: Mapping[str, Any], target: str
) -> None:
    if set(before) != set(after) or any(
        before[key] != after[key] for key in before if key != target
    ):
        raise DemoQuestionnaireAuthorityCorruption("response changed a non-target posterior")


def _routing_evidence_digest(
    run: DemoQuestionnaireRun,
    state: _RunState,
    pair: QuestionPair,
    bank: AdmittedQuestionBank,
    components: Mapping[str, int],
) -> str:
    payload = {
        "bank_projection_digest": bank.projection_digest,
        "components": dict(sorted(components.items())),
        "pair_id": pair.pair_id,
        "posterior": _posterior_snapshot(state.posteriors),
        "run_digest": run.content_digest,
        "self_state_id": run.self_state_id,
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _formal_job_key_hash(actor_id: str, client_key_hash: str) -> str:
    return hashlib.sha256(
        f"mirror.demo/JobIdempotency/v1\n{actor_id}\n{DEMO_QUESTIONNAIRE_RUN_OPERATION}\n"
        f"{client_key_hash}".encode()
    ).hexdigest()


def _authority_digest(schema: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        schema.encode("utf-8") + b"\n" + canonical_json_bytes(payload)
    ).hexdigest()


def _require_id(value: object, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoQuestionnaireInputError(f"{name} must be a lowercase hexadecimal ID")
