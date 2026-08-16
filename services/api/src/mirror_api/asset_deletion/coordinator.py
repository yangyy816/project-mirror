from __future__ import annotations

import logging

from mirror_api.asset_deletion.service import AssetDeletionResult, AssetDeletionService
from mirror_api.asset_deletion.task_contract import (
    AssetDeletionDispatcher,
    AssetDeletionTaskMessage,
)
from mirror_api.logging import OperationalEvent, emit_operational_event

logger = logging.getLogger(__name__)


class AssetDeletionCoordinator:
    def __init__(
        self, *, service: AssetDeletionService, dispatcher: AssetDeletionDispatcher
    ) -> None:
        self._service = service
        self._dispatcher = dispatcher

    async def create(
        self, *, user_id: str, asset_id: str, idempotency_key: str, request_id: str
    ) -> AssetDeletionResult:
        result = await self._service.request_deletion(
            user_id=user_id,
            asset_id=asset_id,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )
        if result.created:
            self._dispatch(result.job_id, request_id)
        return result

    async def reconcile(self, *, request_id: str, limit: int = 100) -> tuple[str, ...]:
        job_ids = await self._service.reconcile(limit=limit)
        for job_id in job_ids:
            self._dispatch(job_id, request_id)
        return job_ids

    def _dispatch(self, job_id: str, request_id: str) -> None:
        try:
            self._dispatcher.dispatch_asset_deletion(
                AssetDeletionTaskMessage(job_id=job_id, request_id=request_id)
            )
        except Exception:
            emit_operational_event(
                logger,
                OperationalEvent(
                    event_name="job.dispatch.completed",
                    outcome="deferred",
                    operation="asset_deletion",
                    job_id=job_id,
                    request_id=request_id,
                ),
            )
        else:
            emit_operational_event(
                logger,
                OperationalEvent(
                    event_name="job.dispatch.completed",
                    outcome="succeeded",
                    operation="asset_deletion",
                    job_id=job_id,
                    request_id=request_id,
                ),
            )
