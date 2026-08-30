from __future__ import annotations

import secrets

from celery import Celery

from mirror_api.demo_editing_task_contract import DemoEditingTaskMessage


class CeleryDemoEditingDispatcher:
    """Dispatch durable D07 intents over the localhost Redis/Celery topology."""

    def __init__(self, *, redis_url: str) -> None:
        self._celery = Celery("mirror-api-demo-editing", broker=redis_url, backend=redis_url)
        self._celery.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
        )

    def dispatch_demo_editing(self, message: DemoEditingTaskMessage) -> str:
        message.validate()
        self._celery.send_task(
            "mirror.demo_editing.process",
            args=[message.to_message()],
            task_id=secrets.token_hex(16),
            headers={"request_id": message.request_id, "job_id": message.job_id},
            queue="mirror.demo",
        )
        return message.job_id


class RecoverablePendingDemoEditingDispatcher:
    """Local boundary that leaves durable work PENDING for a local runner."""

    def dispatch_demo_editing(self, message: DemoEditingTaskMessage) -> str:
        message.validate()
        return message.job_id


__all__ = [
    "CeleryDemoEditingDispatcher",
    "RecoverablePendingDemoEditingDispatcher",
]
