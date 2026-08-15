from __future__ import annotations

import secrets

from celery import Celery

from mirror_api.ingestion.task_contract import IngestionTaskMessage


class CeleryIngestionDispatcher:
    def __init__(self, *, redis_url: str) -> None:
        self._celery = Celery("mirror-api-dispatch", broker=redis_url, backend=redis_url)
        self._celery.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
        )

    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str:
        message.validate()
        self._celery.send_task(
            "mirror.asset_ingestion.process",
            args=[message.to_message()],
            task_id=secrets.token_hex(16),
            headers={"request_id": message.request_id, "job_id": message.job_id},
            queue="mirror.ingestion",
        )
        return message.job_id


class RecoverablePendingDispatcher:
    """Development-only boundary; the LocalTaskRunner or reconciler claims pending Jobs."""

    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str:
        message.validate()
        return message.job_id
