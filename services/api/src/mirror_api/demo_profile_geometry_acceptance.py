"""Job-only server facade for accepting one profile-guided Geometry preview."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_editing_commands import DemoEditingCommandService
from mirror_api.demo_idempotency import DemoIdempotencyInputError, idempotency_key_hash
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_models import (
    DemoDesiredDeltaProfile,
    DemoEditingSession,
    DemoEditOperation,
    DemoEditPlan,
    DemoImageVersion,
)
from mirror_api.demo_profile_geometry_selector import (
    DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST,
    DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
)
from mirror_api.demo_self_transfer_acceptance import (
    AcceptDemoSteppedSelfTransfer,
    DemoSteppedSelfTransferAcceptanceCoordinator,
)
from mirror_api.demo_self_transfer_service import (
    CreateDemoSteppedSelfTransferRequest,
    DemoSelfTransferConflict,
    DemoSelfTransferService,
)
from mirror_api.models import new_id

_ID = re.compile(r"^[0-9a-f]{32}$")


class DemoProfileGeometryAcceptanceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AcceptProfileGeometryExecution:
    demo_actor_id: str
    execution_job_id: str
    idempotency_key: str
    outcome: Literal["FINAL_SAVE_AND_USE_AS_REFERENCE"]

    def validate(self) -> None:
        for name, value in (
            ("demo_actor_id", self.demo_actor_id),
            ("execution_job_id", self.execution_job_id),
        ):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise DemoProfileGeometryAcceptanceError("INVALID_ID", f"{name} is invalid")
        if self.outcome != "FINAL_SAVE_AND_USE_AS_REFERENCE":
            raise DemoProfileGeometryAcceptanceError("INVALID_OUTCOME", "outcome is unsupported")
        try:
            idempotency_key_hash(self.idempotency_key)
        except DemoIdempotencyInputError as exc:
            raise DemoProfileGeometryAcceptanceError(
                "INVALID_IDEMPOTENCY_KEY", "idempotency key is invalid"
            ) from exc


@dataclass(frozen=True, slots=True)
class DemoProfileGeometryAcceptanceResult:
    status: Literal["REFERENCE_PROFILE_PENDING", "REFERENCE_PROFILE_READY"]
    reference_profile_job_id: str | None
    queue_state: Literal["PENDING", "READY", "RECOVERY_REQUIRED"]


class DemoProfileGeometryAcceptanceFacade:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        editing: DemoEditingCommandService,
        transfer: DemoSelfTransferService,
        acceptance: DemoSteppedSelfTransferAcceptanceCoordinator,
        jobs: DemoJobService,
    ) -> None:
        self._sessions = session_factory
        self._editing = editing
        self._transfer = transfer
        self._acceptance = acceptance
        self._jobs = jobs

    async def accept(
        self, command: AcceptProfileGeometryExecution
    ) -> DemoProfileGeometryAcceptanceResult:
        command.validate()
        execution = await self._editing.read_execution_result(
            demo_actor_id=command.demo_actor_id,
            job_id=command.execution_job_id,
        )
        async with self._sessions() as session:
            editing = await session.get(DemoEditingSession, execution.editing_session_id)
            plan = await session.get(DemoEditPlan, execution.edit_plan_id)
            image = await session.get(DemoImageVersion, execution.image_version_id)
            operations = (
                ()
                if plan is None
                else tuple(
                    await session.scalars(
                        select(DemoEditOperation)
                        .where(DemoEditOperation.edit_plan_id == plan.id)
                        .order_by(DemoEditOperation.operation_index, DemoEditOperation.id)
                    )
                )
            )
            profiles = (
                ()
                if editing is None
                else tuple(
                    await session.scalars(
                        select(DemoDesiredDeltaProfile).where(
                            DemoDesiredDeltaProfile.demo_actor_id == command.demo_actor_id,
                            DemoDesiredDeltaProfile.demo_session_id == execution.session_id,
                            DemoDesiredDeltaProfile.content_digest
                            == editing.desired_delta_profile_digest,
                        )
                    )
                )
            )
            if (
                editing is None
                or plan is None
                or image is None
                or len(profiles) != 1
                or len(operations) != 1
                or operations[0].operation_index != 0
                or editing.demo_actor_id != command.demo_actor_id
                or editing.demo_session_id != execution.session_id
                or editing.id != execution.editing_session_id
                or editing.closed_at is not None
                or editing.tombstoned_at is not None
                or plan.demo_actor_id != command.demo_actor_id
                or plan.demo_session_id != execution.session_id
                or plan.editing_session_id != editing.id
                or plan.id != execution.edit_plan_id
                or plan.content_digest != execution.plan_digest
                or plan.record_kind != "RESULT"
                or image.demo_actor_id != command.demo_actor_id
                or image.demo_session_id != execution.session_id
                or image.editing_session_id != editing.id
                or image.id != execution.image_version_id
                or image.content_digest != execution.image_version_digest
                or image.plan_digest != plan.content_digest
                or operations[0].demo_actor_id != command.demo_actor_id
                or operations[0].demo_session_id != execution.session_id
                or operations[0].edit_plan_id != plan.id
                or operations[0].engine != "GEOMETRY"
                or operations[0].operation_type != "GEOMETRY"
            ):
                raise DemoProfileGeometryAcceptanceError(
                    "EXECUTION_CONTEXT_UNAVAILABLE", "execution context is unavailable"
                )
            selection = await self._transfer.select_profile_geometry_step_in_session(
                session,
                demo_actor_id=command.demo_actor_id,
                demo_session_id=execution.session_id,
                source_asset_id=editing.source_asset_id,
                desired_delta_profile_id=profiles[0].id,
                policy_version=DEMO_PROFILE_GUIDED_STEP_POLICY_VERSION,
                policy_digest=DEMO_PROFILE_GUIDED_STEP_POLICY_DIGEST,
            )
            if (
                operations[0].parameters.get("dimension_key") != selection.dimension_key
                or operations[0].parameters.get("delta_ppm") != selection.execution_delta_ppm
            ):
                raise DemoProfileGeometryAcceptanceError(
                    "EXECUTION_SELECTION_MISMATCH",
                    "execution does not match the current profile-guided selection",
                )
            profile_id = profiles[0].id
            source_asset_id = editing.source_asset_id

        created = await self._transfer.create_stepped_request(
            CreateDemoSteppedSelfTransferRequest(
                demo_actor_id=command.demo_actor_id,
                demo_session_id=execution.session_id,
                desired_delta_profile_id=profile_id,
                source_asset_id=source_asset_id,
                execution_job_id=command.execution_job_id,
                result_image_version_id=execution.image_version_id,
                selection=selection,
                idempotency_key=command.idempotency_key,
                request_id=new_id(),
            )
        )
        try:
            await self._transfer.reserve(
                demo_actor_id=command.demo_actor_id,
                request_run_id=created.request_run_id,
            )
        except DemoSelfTransferConflict as exc:
            if exc.code != "JOB_NOT_RESERVABLE":
                raise

        result = await self._acceptance.accept(
            AcceptDemoSteppedSelfTransfer(
                demo_actor_id=command.demo_actor_id,
                request_run_id=created.request_run_id,
                result_image_version_id=execution.image_version_id,
                final_save_idempotency_key=_final_save_key(command.idempotency_key),
                outcome=command.outcome,
            )
        )
        if result.reference_profile_job_id is None:
            return DemoProfileGeometryAcceptanceResult(
                "REFERENCE_PROFILE_PENDING", None, "RECOVERY_REQUIRED"
            )
        job = await self._jobs.get(
            demo_actor_id=command.demo_actor_id,
            job_id=result.reference_profile_job_id,
        )
        if job.status == "COMPLETED":
            return DemoProfileGeometryAcceptanceResult(
                "REFERENCE_PROFILE_READY", job.job_id, "READY"
            )
        if job.status in {"PENDING", "RUNNING"}:
            return DemoProfileGeometryAcceptanceResult(
                "REFERENCE_PROFILE_PENDING", job.job_id, "PENDING"
            )
        return DemoProfileGeometryAcceptanceResult(
            "REFERENCE_PROFILE_PENDING", job.job_id, "RECOVERY_REQUIRED"
        )


def _final_save_key(value: str) -> str:
    return (
        "d06-final-save-"
        + hashlib.sha256(b"mirror.demo/D06FinalSaveKey/v1\n" + value.encode("ascii")).hexdigest()
    )


__all__ = [
    "AcceptProfileGeometryExecution",
    "DemoProfileGeometryAcceptanceError",
    "DemoProfileGeometryAcceptanceFacade",
    "DemoProfileGeometryAcceptanceResult",
]
