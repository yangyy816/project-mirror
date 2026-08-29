from __future__ import annotations

import secrets

from celery import Celery

from mirror_api.demo_profile_task_contract import DemoProfileTaskMessage


class CeleryDemoProfileDispatcher:
    """Reference-only P5 dispatch over the local Redis/Celery topology."""

    def __init__(self, *, redis_url: str) -> None:
        self._celery = Celery("mirror-api-demo-profile", broker=redis_url, backend=redis_url)
        self._celery.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
        )

    def dispatch_demo_profile(self, message: DemoProfileTaskMessage) -> str:
        message.validate()
        self._celery.send_task(
            "mirror.demo_profile.compile",
            args=[message.to_message()],
            task_id=secrets.token_hex(16),
            headers={"request_id": message.request_id, "job_id": message.job_id},
            queue="mirror.demo",
        )
        return message.job_id


class RecoverablePendingDemoProfileDispatcher:
    """Local boundary that leaves the durable Job pending for a later runner."""

    def dispatch_demo_profile(self, message: DemoProfileTaskMessage) -> str:
        message.validate()
        return message.job_id


__all__ = [
    "CeleryDemoProfileDispatcher",
    "RecoverablePendingDemoProfileDispatcher",
]
