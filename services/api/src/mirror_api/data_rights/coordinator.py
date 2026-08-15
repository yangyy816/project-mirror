from __future__ import annotations

import logging
from collections.abc import Callable

from mirror_api.account_deletion.service import AccountDeletionResult, AccountDeletionService
from mirror_api.data_export.service import DataExportResult, DataExportService
from mirror_api.data_rights.task_contract import (
    AccountDeletionTaskMessage,
    DataExportTaskMessage,
    DataRightsDispatcher,
)

logger = logging.getLogger(__name__)


class DataRightsCoordinator:
    def __init__(
        self,
        *,
        exports: DataExportService,
        account_deletions: AccountDeletionService,
        dispatcher: DataRightsDispatcher,
    ) -> None:
        self.exports = exports
        self.account_deletions = account_deletions
        self._dispatcher = dispatcher

    async def create_export(
        self, *, user_id: str, idempotency_key: str, request_id: str
    ) -> DataExportResult:
        result = await self.exports.request_export(
            user_id=user_id, idempotency_key=idempotency_key, request_id=request_id
        )
        if result.created:
            self._dispatch_export(result.job_id, request_id)
        return result

    async def create_account_deletion(
        self, *, user_id: str, idempotency_key: str, request_id: str
    ) -> AccountDeletionResult:
        result = await self.account_deletions.request_deletion(
            user_id=user_id, idempotency_key=idempotency_key, request_id=request_id
        )
        if result.created:
            self._dispatch_account(result.job_id, request_id)
        return result

    async def reconcile(self, *, request_id: str, limit: int = 100) -> tuple[str, ...]:
        export_jobs = await self.exports.reconcile(limit=limit)
        account_jobs = await self.account_deletions.reconcile(limit=limit)
        for job_id in export_jobs:
            self._dispatch_export(job_id, request_id)
        for job_id in account_jobs:
            self._dispatch_account(job_id, request_id)
        return export_jobs + account_jobs

    def _dispatch_export(self, job_id: str, request_id: str) -> None:
        self._dispatch(
            "data export",
            lambda: self._dispatcher.dispatch_data_export(
                DataExportTaskMessage(job_id=job_id, request_id=request_id)
            ),
            job_id,
            request_id,
        )

    def _dispatch_account(self, job_id: str, request_id: str) -> None:
        self._dispatch(
            "account deletion",
            lambda: self._dispatcher.dispatch_account_deletion(
                AccountDeletionTaskMessage(job_id=job_id, request_id=request_id)
            ),
            job_id,
            request_id,
        )

    @staticmethod
    def _dispatch(label: str, action: Callable[[], str], job_id: str, request_id: str) -> None:
        try:
            action()
        except Exception:
            logger.warning(
                "%s dispatch deferred to reconciler",
                label,
                extra={"job_id": job_id, "request_id": request_id},
            )
