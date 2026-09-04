from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, cast

import pytest

from mirror_api.demo_job_service import DemoJobSnapshot, DemoJobStatus, DemoJobTargetSnapshot
from mirror_api.demo_reference_profile_coordinator import DemoReferenceProfileCoordinator
from mirror_api.demo_reference_profile_service import (
    CreateDemoReferenceProfileCompilation,
    DemoReferenceProfileCompilationAccepted,
)
from mirror_api.demo_self_transfer_service import DemoReferenceSource

_ACTOR_ID = "1" * 32
_SESSION_ID = "2" * 32
_JOB_ID = "3" * 32
_COMPILE_REQUEST_ID = "4" * 32
_AUTHORITY_REQUEST_ID = "d06-reference-private-correlation"
_RESULT_DIGEST = "5" * 64


@dataclass
class _Service:
    async def admit(
        self, command: CreateDemoReferenceProfileCompilation
    ) -> DemoReferenceProfileCompilationAccepted:
        del command
        return DemoReferenceProfileCompilationAccepted(
            _JOB_ID,
            _COMPILE_REQUEST_ID,
            _AUTHORITY_REQUEST_ID,
            False,
        )


@dataclass
class _Jobs:
    async def get(self, *, demo_actor_id: str, job_id: str) -> DemoJobSnapshot:
        assert (demo_actor_id, job_id) == (_ACTOR_ID, _JOB_ID)
        return DemoJobSnapshot(
            job_id=_JOB_ID,
            demo_actor_id=_ACTOR_ID,
            demo_session_id=_SESSION_ID,
            status=cast(DemoJobStatus, "PENDING"),
            capability="P5_REFERENCE_PROFILE",
            job_binding_digest="6" * 64,
            target=DemoJobTargetSnapshot(
                target_type="REFERENCE_PROFILE_REQUEST",
                target_id=_COMPILE_REQUEST_ID,
                authority_digest="7" * 64,
            ),
            result_code=None,
            finalized_at=None,
        )


@dataclass
class _Dispatcher:
    fail: bool

    def dispatch_demo_reference_profile(self, message: object) -> str:
        if self.fail:
            raise RuntimeError("synthetic dispatch failure")
        return cast(Any, message).job_id


def _command() -> CreateDemoReferenceProfileCompilation:
    return CreateDemoReferenceProfileCompilation(
        demo_actor_id=_ACTOR_ID,
        demo_session_id=_SESSION_ID,
        desired_delta_profile_id="8" * 32,
        style_profile_id="9" * 32,
        identity_constraints_id="a" * 32,
        sources=(DemoReferenceSource("b" * 32, "FRONT"),),
        idempotency_key=f"d06-stepped-reference-{_RESULT_DIGEST}",
        request_id=_AUTHORITY_REQUEST_ID,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", (False, True), ids=("succeeded", "deferred"))
async def test_reference_dispatch_logs_no_authority_identifiers(
    fail: bool,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger_name = "mirror_api.demo_reference_profile_coordinator"
    event_logger = logging.getLogger(logger_name)
    monkeypatch.setattr(event_logger, "disabled", False)
    monkeypatch.setattr(event_logger, "propagate", True)
    caplog.set_level(logging.INFO, logger=logger_name)
    coordinator = DemoReferenceProfileCoordinator(
        service=cast(Any, _Service()),
        jobs=cast(Any, _Jobs()),
        dispatcher=cast(Any, _Dispatcher(fail)),
    )

    result = await coordinator.create(_command())

    assert result.job.job_id == _JOB_ID
    events = [json.loads(record.message) for record in caplog.records]
    assert events[-1] == {
        "event_name": "job.dispatch.completed",
        "operation": "demo_reference_profile",
        "outcome": "deferred" if fail else "succeeded",
        "request_id": "d06-reference-dispatch",
    }
    assert all(
        secret not in caplog.text
        for secret in (
            _JOB_ID,
            _COMPILE_REQUEST_ID,
            _AUTHORITY_REQUEST_ID,
            _RESULT_DIGEST,
        )
    )
