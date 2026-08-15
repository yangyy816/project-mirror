from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mirror_api.account_deletion.service import AccountDeletionResult
from mirror_api.data_export.service import DataExportResult
from mirror_api.data_rights.task_contract import (
    AccountDeletionTaskMessage,
    DataExportTaskMessage,
)


class DataExportApplication(Protocol):
    async def process(self, *, job_id: str) -> DataExportResult | None: ...


class AccountDeletionApplication(Protocol):
    async def process(self, *, job_id: str) -> AccountDeletionResult | None: ...


@dataclass(frozen=True)
class DataRightsExecutionResult:
    job_id: str
    status: str


class DataExportTaskExecutor:
    def __init__(self, application: DataExportApplication) -> None:
        self._application = application

    async def execute(self, message: DataExportTaskMessage) -> DataRightsExecutionResult:
        message.validate()
        result = await self._application.process(job_id=message.job_id)
        return DataRightsExecutionResult(
            job_id=message.job_id,
            status="no_op" if result is None else result.status,
        )


class AccountDeletionTaskExecutor:
    def __init__(self, application: AccountDeletionApplication) -> None:
        self._application = application

    async def execute(self, message: AccountDeletionTaskMessage) -> DataRightsExecutionResult:
        message.validate()
        result = await self._application.process(job_id=message.job_id)
        return DataRightsExecutionResult(
            job_id=message.job_id,
            status="no_op" if result is None else result.status,
        )
