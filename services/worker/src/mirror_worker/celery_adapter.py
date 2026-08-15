from __future__ import annotations

from typing import Any

from celery import Celery
from mirror_api.config import get_settings

from mirror_worker.application import FoundationProbeService, TaskEnvelope

settings = get_settings()
celery_app = Celery("mirror-worker", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_default_queue="mirror.default",
)

RETRY_POLICY = {
    "max_retries": 3,
    "retry_backoff": True,
    "retry_jitter": True,
}


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.foundation_probe",
    autoretry_for=(RuntimeError,),
    **RETRY_POLICY,
)
def foundation_probe(message: dict[str, Any]) -> dict[str, str]:
    envelope = TaskEnvelope.from_message(message)
    return FoundationProbeService().execute(envelope)


class CeleryTaskDispatcher:
    def dispatch(self, envelope: TaskEnvelope) -> str:
        envelope.validate()
        foundation_probe.apply_async(
            args=[envelope.to_message()],
            task_id=envelope.job_id,
            headers={"request_id": envelope.request_id},
        )
        return envelope.job_id
