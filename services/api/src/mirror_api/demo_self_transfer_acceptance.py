"""Atomic D09 Final Save + D06 stepped self-transfer acceptance coordinator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_image_feedback_service import (
    CreateDemoImageFeedback,
    DemoImageFeedbackResult,
    DemoImageFeedbackService,
)
from mirror_api.demo_reference_profile_coordinator import DemoReferenceProfileCoordinator
from mirror_api.demo_reference_profile_service import (
    DemoReferenceProfileError,
    DemoReferenceProfileService,
)
from mirror_api.demo_self_transfer_service import (
    DemoSelfTransferResultAccepted,
    DemoSelfTransferService,
    FinalizeDemoSelfTransferResult,
)

_ID = re.compile(r"^[0-9a-f]{32}$")


class DemoSteppedSelfTransferAcceptanceError(RuntimeError):
    """The D06/D09 acceptance command is outside its frozen authority boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AcceptDemoSteppedSelfTransfer:
    demo_actor_id: str
    request_run_id: str
    result_image_version_id: str
    final_save_idempotency_key: str
    outcome: Literal["FINAL_SAVE_AND_USE_AS_REFERENCE"]

    def validate(self) -> None:
        for name, value in (
            ("demo_actor_id", self.demo_actor_id),
            ("request_run_id", self.request_run_id),
            ("result_image_version_id", self.result_image_version_id),
        ):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise DemoSteppedSelfTransferAcceptanceError(
                    "INVALID_ID", f"{name} must be a lowercase hexadecimal ID"
                )
        if self.outcome != "FINAL_SAVE_AND_USE_AS_REFERENCE":
            raise DemoSteppedSelfTransferAcceptanceError(
                "INVALID_OUTCOME", "stepped acceptance requires the explicit Final Save outcome"
            )


@dataclass(frozen=True, slots=True)
class DemoSteppedSelfTransferAcceptanceResult:
    feedback: DemoImageFeedbackResult
    transfer: DemoSelfTransferResultAccepted
    reference_profile_job_id: str | None
    reference_profile_replayed: bool | None
    queue_error_code: str | None


class DemoSteppedSelfTransferAcceptanceCoordinator:
    """Own the frozen D09 → D06 transaction, then ensure the durable queue.

    The deterministic Reference Profile admission occurs after the transaction
    commits.  Its dispatcher is intentionally delegated to the existing D06
    coordinator: a dispatch exception is recorded there as deferred while the
    durable Job remains PENDING for reconciliation.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        feedback: DemoImageFeedbackService,
        transfer: DemoSelfTransferService,
        reference_service: DemoReferenceProfileService,
        reference_coordinator: DemoReferenceProfileCoordinator,
    ) -> None:
        self._sessions = session_factory
        self._feedback = feedback
        self._transfer = transfer
        self._reference_service = reference_service
        self._reference_coordinator = reference_coordinator

    async def accept(
        self, command: AcceptDemoSteppedSelfTransfer
    ) -> DemoSteppedSelfTransferAcceptanceResult:
        command.validate()
        async with self._sessions() as session:
            async with session.begin():
                final_save = await self._feedback.create_final_save_in_session(
                    session,
                    CreateDemoImageFeedback(
                        demo_actor_id=command.demo_actor_id,
                        image_version_id=command.result_image_version_id,
                        feedback="ACCEPT",
                        acceptance_kind="FINAL_SAVE",
                        intensity_ppm=None,
                        idempotency_key=command.final_save_idempotency_key,
                    ),
                )
                transfer = await self._transfer.finalize_in_session(
                    session,
                    FinalizeDemoSelfTransferResult(
                        demo_actor_id=command.demo_actor_id,
                        request_run_id=command.request_run_id,
                        result_image_version_id=command.result_image_version_id,
                        user_outcome="ACCEPTED",
                        final_save_episode_id=final_save.episode_id,
                    ),
                )
        try:
            queue_command = await self._reference_service.command_for_accepted_stepped_result(
                demo_actor_id=command.demo_actor_id,
                result_run_id=transfer.result_run_id,
            )
            queued = await self._reference_coordinator.create(queue_command)
        except DemoReferenceProfileError as exc:
            # The user-owned Final Save and D06 evidence are already committed.
            # Do not misrepresent a post-commit recovery failure as a rollback.
            return DemoSteppedSelfTransferAcceptanceResult(
                final_save.feedback,
                transfer,
                None,
                None,
                exc.code,
            )
        return DemoSteppedSelfTransferAcceptanceResult(
            final_save.feedback,
            transfer,
            queued.job.job_id,
            queued.replayed,
            None,
        )


__all__ = [
    "AcceptDemoSteppedSelfTransfer",
    "DemoSteppedSelfTransferAcceptanceCoordinator",
    "DemoSteppedSelfTransferAcceptanceError",
    "DemoSteppedSelfTransferAcceptanceResult",
]
