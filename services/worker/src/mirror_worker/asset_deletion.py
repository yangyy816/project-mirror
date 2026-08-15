from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mirror_api.asset_deletion.service import AssetDeletionResult
from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage


class AssetDeletionApplication(Protocol):
    async def process(self, *, job_id: str) -> AssetDeletionResult | None: ...


@dataclass(frozen=True)
class AssetDeletionExecutionResult:
    job_id: str
    status: str


class AssetDeletionTaskExecutor:
    def __init__(self, application: AssetDeletionApplication) -> None:
        self._application = application

    async def execute(self, message: AssetDeletionTaskMessage) -> AssetDeletionExecutionResult:
        message.validate()
        result = await self._application.process(job_id=message.job_id)
        return AssetDeletionExecutionResult(
            job_id=message.job_id,
            status="no_op" if result is None else result.status,
        )
