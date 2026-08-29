"""Celery-independent D03 analysis Worker executor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

from mirror_api.demo_analysis_service import (
    DemoAnalysisPublication,
    DemoAnalysisReservation,
    DemoAnalysisRuntimeEvidence,
    DemoAnalysisUnavailable,
)
from mirror_api.demo_analysis_task_contract import DemoAnalysisTaskMessage

ExecutionStatus = Literal["COMPLETED", "REJECTED", "FAILED", "NO_OP"]
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def _sanitize_runtime_error_code(code: str, *, fallback: str) -> str:
    if isinstance(code, str) and _ERROR_CODE.fullmatch(code) is not None:
        return code
    return fallback


class DemoAnalysisRuntimePort(Protocol):
    """Task-scoped live runtime boundary; no locator is exposed to the executor."""

    async def observe(
        self, reservation: DemoAnalysisReservation
    ) -> DemoAnalysisRuntimeEvidence: ...


class DemoAnalysisApplication(Protocol):
    async def claim(
        self, *, analysis_run_id: str, job_id: str, request_id: str
    ) -> DemoAnalysisReservation | None: ...

    async def complete(
        self,
        reservation: DemoAnalysisReservation,
        evidence: DemoAnalysisRuntimeEvidence,
    ) -> DemoAnalysisPublication | None: ...

    async def terminalize(
        self,
        reservation: DemoAnalysisReservation,
        *,
        status: Literal["REJECTED", "FAILED"],
        code: str,
    ) -> bool: ...


class DemoAnalysisRuntimeRejected(RuntimeError):
    """The runtime produced a policy/eligibility rejection, not an execution failure."""

    def __init__(self, code: str) -> None:
        self.code = _sanitize_runtime_error_code(code, fallback="RUNTIME_REJECTED")
        super().__init__("demo analysis runtime rejected")


class DemoAnalysisRuntimeFailed(RuntimeError):
    """The runtime or storage boundary failed before producing accepted evidence."""

    def __init__(self, code: str) -> None:
        self.code = _sanitize_runtime_error_code(code, fallback="RUNTIME_EXECUTION_FAILED")
        super().__init__("demo analysis runtime failed")


@dataclass(frozen=True)
class DemoAnalysisTaskResult:
    analysis_run_id: str
    job_id: str
    status: ExecutionStatus
    observation_id: str | None = None
    observation_digest: str | None = None


class DemoAnalysisTaskExecutor:
    """Claim once, call the injected runtime once, then publish or fail atomically."""

    def __init__(
        self,
        *,
        application: DemoAnalysisApplication,
        runtime: DemoAnalysisRuntimePort,
    ) -> None:
        self._application = application
        self._runtime = runtime

    async def execute(self, message: DemoAnalysisTaskMessage) -> DemoAnalysisTaskResult:
        message.validate()
        reservation = await self._application.claim(
            analysis_run_id=message.analysis_run_id,
            job_id=message.job_id,
            request_id=message.request_id,
        )
        if reservation is None:
            return _result(message, status="NO_OP")
        try:
            evidence = await self._runtime.observe(reservation)
        except DemoAnalysisRuntimeRejected as exc:
            await self._application.terminalize(reservation, status="REJECTED", code=exc.code)
            return _result(message, status="REJECTED")
        except DemoAnalysisRuntimeFailed as exc:
            await self._application.terminalize(reservation, status="FAILED", code=exc.code)
            return _result(message, status="FAILED")
        except Exception:
            await self._application.terminalize(
                reservation, status="FAILED", code="RUNTIME_EXECUTION_FAILED"
            )
            return _result(message, status="FAILED")

        try:
            publication = await self._application.complete(reservation, evidence)
        except DemoAnalysisUnavailable:
            await self._application.terminalize(
                reservation,
                status="REJECTED",
                code="ANALYSIS_AUTHORITY_UNAVAILABLE",
            )
            return _result(message, status="REJECTED")
        except Exception:
            await self._application.terminalize(
                reservation, status="FAILED", code="ANALYSIS_PUBLICATION_FAILED"
            )
            return _result(message, status="FAILED")
        if publication is None:
            return _result(message, status="NO_OP")
        return _publication_result(publication)


def _result(message: DemoAnalysisTaskMessage, *, status: ExecutionStatus) -> DemoAnalysisTaskResult:
    return DemoAnalysisTaskResult(
        analysis_run_id=message.analysis_run_id,
        job_id=message.job_id,
        status=status,
    )


def _publication_result(publication: DemoAnalysisPublication) -> DemoAnalysisTaskResult:
    return DemoAnalysisTaskResult(
        analysis_run_id=publication.analysis_run_id,
        job_id=publication.job_id,
        status="COMPLETED",
        observation_id=publication.observation_id,
        observation_digest=publication.observation_digest,
    )
