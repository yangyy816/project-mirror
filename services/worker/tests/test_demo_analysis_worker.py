from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import pytest
from mirror_api.demo_analysis_service import (
    DemoAnalysisPublication,
    DemoAnalysisReservation,
    DemoAnalysisRuntimeEvidence,
    DemoAnalysisUnavailable,
)
from mirror_api.demo_analysis_task_contract import (
    DEMO_ANALYSIS_TASK_SCHEMA,
    DemoAnalysisTaskMessage,
)

from mirror_worker.demo_analysis import (
    DemoAnalysisRuntimeFailed,
    DemoAnalysisRuntimeRejected,
    DemoAnalysisTaskExecutor,
)

_RUN_ID = "a" * 32
_JOB_ID = "b" * 32
_REQUEST_ID = "d03-worker-request"


def _message() -> DemoAnalysisTaskMessage:
    return DemoAnalysisTaskMessage(
        analysis_run_id=_RUN_ID,
        job_id=_JOB_ID,
        request_id=_REQUEST_ID,
    )


def _reservation() -> DemoAnalysisReservation:
    now = datetime(2026, 8, 29, 12, tzinfo=UTC)
    return DemoAnalysisReservation(
        analysis_run_id=_RUN_ID,
        job_id=_JOB_ID,
        attempt_id="c" * 32,
        attempt=1,
        lease_token="d" * 64,
        lease_expires_at=now + timedelta(minutes=5),
        request_id=_REQUEST_ID,
        demo_actor_id="e" * 32,
        demo_session_id="f" * 32,
        demo_synthetic_identity_id="1" * 32,
        source_asset_id="2" * 32,
        source_asset_sha256="3" * 64,
        analyzer_version="demo-face-observation-v1",
        runtime_manifest_digest="4" * 64,
        model_manifest_digest="5" * 64,
        observation_config_digest="6" * 64,
    )


class _Application:
    def __init__(
        self,
        *,
        claim: DemoAnalysisReservation | None,
        publication: DemoAnalysisPublication | None = None,
        complete_error: Exception | None = None,
    ) -> None:
        self.claim_result = claim
        self.publication = publication
        self.complete_error = complete_error
        self.claim_calls = 0
        self.complete_calls = 0
        self.terminal_calls: list[tuple[str, str]] = []

    async def claim(
        self, *, analysis_run_id: str, job_id: str, request_id: str
    ) -> DemoAnalysisReservation | None:
        assert (analysis_run_id, job_id, request_id) == (_RUN_ID, _JOB_ID, _REQUEST_ID)
        self.claim_calls += 1
        return self.claim_result

    async def complete(
        self,
        reservation: DemoAnalysisReservation,
        evidence: DemoAnalysisRuntimeEvidence,
    ) -> DemoAnalysisPublication | None:
        assert reservation == self.claim_result
        assert evidence is _EVIDENCE
        self.complete_calls += 1
        if self.complete_error is not None:
            raise self.complete_error
        return self.publication

    async def terminalize(
        self,
        reservation: DemoAnalysisReservation,
        *,
        status: Literal["REJECTED", "FAILED"],
        code: str,
    ) -> bool:
        assert reservation == self.claim_result
        self.terminal_calls.append((status, code))
        return True


class _Runtime:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    async def observe(self, reservation: DemoAnalysisReservation) -> DemoAnalysisRuntimeEvidence:
        assert reservation == _reservation()
        self.calls += 1
        if self.error is not None:
            raise self.error
        return _EVIDENCE


_EVIDENCE = cast(DemoAnalysisRuntimeEvidence, object())


def test_reference_only_task_contract_rejects_extra_or_sensitive_fields() -> None:
    message = _message()
    assert message.to_message() == {
        "analysis_run_id": _RUN_ID,
        "job_id": _JOB_ID,
        "request_id": _REQUEST_ID,
        "schema_version": DEMO_ANALYSIS_TASK_SCHEMA,
    }
    assert DemoAnalysisTaskMessage.from_message(message.to_message()) == message
    with pytest.raises(ValueError, match="invalid shape"):
        DemoAnalysisTaskMessage.from_message(
            {**message.to_message(), "runtime_locator": "forbidden"}
        )
    with pytest.raises(ValueError, match="unsupported"):
        DemoAnalysisTaskMessage.from_message(
            {**message.to_message(), "schema_version": "demo-analysis-task-v2"}
        )
    with pytest.raises(ValueError, match="identifiers must be opaque"):
        DemoAnalysisTaskMessage(
            analysis_run_id=None,  # type: ignore[arg-type]
            job_id=_JOB_ID,
            request_id=_REQUEST_ID,
        ).validate()
    with pytest.raises(ValueError, match="request id"):
        DemoAnalysisTaskMessage(
            analysis_run_id=_RUN_ID,
            job_id=_JOB_ID,
            request_id=None,  # type: ignore[arg-type]
        ).validate()


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (DemoAnalysisRuntimeRejected("token=private-value"), "RUNTIME_REJECTED"),
        (
            DemoAnalysisRuntimeFailed("C:\\private\\runtime\\locator"),
            "RUNTIME_EXECUTION_FAILED",
        ),
    ],
)
def test_runtime_error_codes_are_sanitized_before_terminalization(
    error: DemoAnalysisRuntimeRejected | DemoAnalysisRuntimeFailed,
    expected_code: str,
) -> None:
    assert error.code == expected_code
    assert "private" not in str(error)
    assert "token" not in str(error)


@pytest.mark.asyncio
async def test_running_or_terminal_redelivery_is_noop_without_runtime_call() -> None:
    application = _Application(claim=None)
    runtime = _Runtime()
    result = await DemoAnalysisTaskExecutor(application=application, runtime=runtime).execute(
        _message()
    )
    assert result.status == "NO_OP"
    assert runtime.calls == 0
    assert application.complete_calls == 0
    assert application.terminal_calls == []


@pytest.mark.asyncio
async def test_success_calls_runtime_once_and_returns_opaque_publication() -> None:
    publication = DemoAnalysisPublication(
        analysis_run_id=_RUN_ID,
        job_id=_JOB_ID,
        observation_id="7" * 32,
        observation_digest="8" * 64,
        baseline_face_model_id="9" * 32,
        self_state_id="0" * 32,
        observation_state="SUPPORTED",
    )
    application = _Application(claim=_reservation(), publication=publication)
    runtime = _Runtime()
    result = await DemoAnalysisTaskExecutor(application=application, runtime=runtime).execute(
        _message()
    )
    assert result.status == "COMPLETED"
    assert result.observation_id == publication.observation_id
    assert result.observation_digest == publication.observation_digest
    assert runtime.calls == 1
    assert application.complete_calls == 1
    assert application.terminal_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status", "expected_terminal"),
    [
        (
            DemoAnalysisRuntimeRejected("FEATURE_NOT_ELIGIBLE"),
            "REJECTED",
            ("REJECTED", "FEATURE_NOT_ELIGIBLE"),
        ),
        (
            DemoAnalysisRuntimeFailed("M3_RUNTIME_UNAVAILABLE"),
            "FAILED",
            ("FAILED", "M3_RUNTIME_UNAVAILABLE"),
        ),
        (
            DemoAnalysisRuntimeRejected("token=private-value"),
            "REJECTED",
            ("REJECTED", "RUNTIME_REJECTED"),
        ),
        (
            DemoAnalysisRuntimeFailed("C:\\private\\runtime\\locator"),
            "FAILED",
            ("FAILED", "RUNTIME_EXECUTION_FAILED"),
        ),
        (RuntimeError("secret detail"), "FAILED", ("FAILED", "RUNTIME_EXECUTION_FAILED")),
    ],
)
async def test_runtime_failure_maps_to_structured_terminal_state_without_detail(
    error: Exception,
    expected_status: str,
    expected_terminal: tuple[str, str],
) -> None:
    application = _Application(claim=_reservation())
    runtime = _Runtime(error=error)
    result = await DemoAnalysisTaskExecutor(application=application, runtime=runtime).execute(
        _message()
    )
    assert result.status == expected_status
    assert result.observation_id is None and result.observation_digest is None
    assert application.terminal_calls == [expected_terminal]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status", "expected_terminal"),
    [
        (
            DemoAnalysisUnavailable("revoked"),
            "REJECTED",
            ("REJECTED", "ANALYSIS_AUTHORITY_UNAVAILABLE"),
        ),
        (
            RuntimeError("database detail"),
            "FAILED",
            ("FAILED", "ANALYSIS_PUBLICATION_FAILED"),
        ),
    ],
)
async def test_publication_failure_rolls_to_rejected_or_failed_without_detail(
    error: Exception,
    expected_status: str,
    expected_terminal: tuple[str, str],
) -> None:
    application = _Application(claim=_reservation(), complete_error=error)
    result = await DemoAnalysisTaskExecutor(application=application, runtime=_Runtime()).execute(
        _message()
    )
    assert result.status == expected_status
    assert application.terminal_calls == [expected_terminal]
