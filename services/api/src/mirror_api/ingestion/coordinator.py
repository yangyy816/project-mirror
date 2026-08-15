from __future__ import annotations

import logging

from mirror_api.ingestion.service import IngestionService
from mirror_api.ingestion.task_contract import IngestionDispatcher, IngestionTaskMessage
from mirror_api.ingestion.types import IngestionJobResult, IngestionJobView

logger = logging.getLogger(__name__)


class IngestionCoordinator:
    """Coordinate durable Job creation with recoverable at-least-once dispatch."""

    def __init__(self, service: IngestionService, dispatcher: IngestionDispatcher) -> None:
        self._service = service
        self._dispatcher = dispatcher

    async def create(
        self,
        *,
        user_id: str,
        intent_id: str,
        idempotency_key: str,
        request_id: str,
    ) -> IngestionJobResult:
        result = await self._service.create(
            user_id=user_id,
            intent_id=intent_id,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )
        if result.created:
            try:
                self._dispatcher.dispatch_ingestion(
                    IngestionTaskMessage(job_id=result.job.job_id, request_id=request_id)
                )
            except Exception:
                logger.warning(
                    "ingestion dispatch deferred to reconciler",
                    extra={"job_id": result.job.job_id, "request_id": request_id},
                )
        return result

    async def get(self, *, user_id: str, job_id: str) -> IngestionJobView:
        return await self._service.get(user_id=user_id, job_id=job_id)
