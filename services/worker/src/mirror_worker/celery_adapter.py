from __future__ import annotations

import asyncio
import secrets
from typing import Any

from celery import Celery
from mirror_api.config import get_settings

from mirror_worker.application import FoundationProbeService, TaskEnvelope
from mirror_worker.ingestion import IngestionTaskMessage, RetryableWorkerFailure
from mirror_worker.runtime import run_cleanup_sweep, run_ingestion_message, run_reconciliation

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
    worker_prefetch_multiplier=1,
    task_routes={
        "mirror.asset_ingestion.process": {"queue": "mirror.ingestion"},
        "mirror.asset_ingestion.cleanup": {"queue": "mirror.maintenance"},
        "mirror.asset_ingestion.reconcile": {"queue": "mirror.maintenance"},
    },
)

RETRY_POLICY = {
    "max_retries": 3,
    "retry_backoff": True,
    "retry_jitter": True,
}

INGESTION_RETRY_POLICY = {
    "max_retries": 3,
    "retry_backoff": True,
    "retry_backoff_max": 60,
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


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.asset_ingestion.process",
    autoretry_for=(RetryableWorkerFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=120,
    time_limit=150,
    **INGESTION_RETRY_POLICY,
)
def process_asset_ingestion(message: dict[str, Any]) -> dict[str, str]:
    try:
        return asyncio.run(run_ingestion_message(message))
    except RetryableWorkerFailure:
        raise
    except Exception as exc:
        raise RetryableWorkerFailure("ingestion execution failed transiently") from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.asset_ingestion.cleanup",
    autoretry_for=(RetryableWorkerFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    **INGESTION_RETRY_POLICY,
)
def cleanup_asset_ingestion(*, limit: int = 100) -> dict[str, int]:
    try:
        return asyncio.run(run_cleanup_sweep(limit=limit))
    except RetryableWorkerFailure:
        raise
    except Exception as exc:
        raise RetryableWorkerFailure("ingestion cleanup failed transiently") from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.asset_ingestion.reconcile",
    autoretry_for=(RetryableWorkerFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    **INGESTION_RETRY_POLICY,
)
def reconcile_asset_ingestion(*, request_id: str, limit: int = 100) -> list[str]:
    try:
        return list(
            asyncio.run(
                run_reconciliation(
                    dispatcher=CeleryTaskDispatcher(), request_id=request_id, limit=limit
                )
            )
        )
    except RetryableWorkerFailure:
        raise
    except Exception as exc:
        raise RetryableWorkerFailure("ingestion reconciliation failed transiently") from exc


class CeleryTaskDispatcher:
    def dispatch(self, envelope: TaskEnvelope) -> str:
        envelope.validate()
        foundation_probe.apply_async(
            args=[envelope.to_message()],
            task_id=envelope.job_id,
            headers={"request_id": envelope.request_id},
        )
        return envelope.job_id

    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str:
        message.validate()
        process_asset_ingestion.apply_async(
            args=[message.to_message()],
            task_id=secrets.token_hex(16),
            headers={"request_id": message.request_id, "job_id": message.job_id},
            queue="mirror.ingestion",
        )
        return message.job_id
