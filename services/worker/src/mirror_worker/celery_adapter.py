from __future__ import annotations

import asyncio
import secrets
from typing import Any

from celery import Celery
from mirror_api.account_deletion.service import RetryableAccountDeletionFailure
from mirror_api.asset_deletion.service import RetryableAssetDeletionFailure
from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage
from mirror_api.config import get_settings
from mirror_api.data_export.service import RetryableDataExportFailure
from mirror_api.data_rights.task_contract import (
    AccountDeletionTaskMessage,
    DataExportTaskMessage,
)
from mirror_api.ingestion.task_contract import IngestionTaskMessage
from mirror_api.synthetic_dataset.task_contract import SyntheticGenerationTaskMessage

from mirror_worker.application import FoundationProbeService, TaskEnvelope
from mirror_worker.ingestion import RetryableWorkerFailure
from mirror_worker.runtime import (
    run_account_deletion_message,
    run_asset_deletion_message,
    run_cleanup_sweep,
    run_data_export_cleanup,
    run_data_export_message,
    run_data_rights_reconciliation,
    run_ingestion_message,
    run_reconciliation,
    run_synthetic_generation_message,
    run_synthetic_generation_reconciliation,
    run_synthetic_raw_cleanup,
)

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
        "mirror.asset_deletion.process": {"queue": "mirror.maintenance"},
        "mirror.data_export.process": {"queue": "mirror.maintenance"},
        "mirror.data_export.cleanup": {"queue": "mirror.maintenance"},
        "mirror.account_deletion.process": {"queue": "mirror.maintenance"},
        "mirror.data_rights.reconcile": {"queue": "mirror.maintenance"},
        "mirror.synthetic_generation.process": {"queue": "mirror.synthetic"},
        "mirror.synthetic_generation.reconcile": {"queue": "mirror.maintenance"},
        "mirror.synthetic_generation.cleanup": {"queue": "mirror.maintenance"},
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


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.asset_deletion.process",
    autoretry_for=(RetryableAssetDeletionFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=120,
    time_limit=150,
    **INGESTION_RETRY_POLICY,
)
def process_asset_deletion(message: dict[str, Any]) -> dict[str, str]:
    try:
        return asyncio.run(run_asset_deletion_message(message))
    except RetryableAssetDeletionFailure:
        raise
    except Exception as exc:
        raise RetryableAssetDeletionFailure("asset deletion execution failed transiently") from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.data_export.process",
    autoretry_for=(RetryableDataExportFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=300,
    time_limit=360,
    **INGESTION_RETRY_POLICY,
)
def process_data_export(message: dict[str, Any]) -> dict[str, str]:
    try:
        return asyncio.run(run_data_export_message(message))
    except RetryableDataExportFailure:
        raise
    except Exception as exc:
        raise RetryableDataExportFailure("data export execution failed transiently") from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.account_deletion.process",
    autoretry_for=(RetryableAccountDeletionFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=300,
    time_limit=360,
    **INGESTION_RETRY_POLICY,
)
def process_account_deletion(message: dict[str, Any]) -> dict[str, str]:
    try:
        return asyncio.run(run_account_deletion_message(message))
    except RetryableAccountDeletionFailure:
        raise
    except Exception as exc:
        raise RetryableAccountDeletionFailure(
            "account deletion execution failed transiently"
        ) from exc


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.data_export.cleanup",
    autoretry_for=(RetryableDataExportFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    **INGESTION_RETRY_POLICY,
)
def cleanup_data_exports(*, limit: int = 100) -> list[str]:
    return list(asyncio.run(run_data_export_cleanup(limit=limit)))


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.data_rights.reconcile",
    autoretry_for=(RetryableDataExportFailure, RetryableAccountDeletionFailure),
    acks_late=True,
    reject_on_worker_lost=True,
    **INGESTION_RETRY_POLICY,
)
def reconcile_data_rights(*, request_id: str, limit: int = 100) -> list[str]:
    return list(
        asyncio.run(
            run_data_rights_reconciliation(
                dispatcher=CeleryTaskDispatcher(), request_id=request_id, limit=limit
            )
        )
    )


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.synthetic_generation.process",
    autoretry_for=(RetryableWorkerFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=300,
    time_limit=360,
    **INGESTION_RETRY_POLICY,
)
def process_synthetic_generation(message: dict[str, Any]) -> dict[str, str]:
    try:
        return asyncio.run(run_synthetic_generation_message(message))
    except RetryableWorkerFailure:
        raise
    except Exception:
        raise RetryableWorkerFailure("synthetic generation execution failed transiently") from None


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.synthetic_generation.reconcile",
    autoretry_for=(RetryableWorkerFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    **INGESTION_RETRY_POLICY,
)
def reconcile_synthetic_generation(*, limit: int = 100) -> list[str]:
    return list(
        asyncio.run(
            run_synthetic_generation_reconciliation(dispatcher=CeleryTaskDispatcher(), limit=limit)
        )
    )


@celery_app.task(  # type: ignore[untyped-decorator]
    name="mirror.synthetic_generation.cleanup",
    autoretry_for=(RetryableWorkerFailure,),
    acks_late=True,
    reject_on_worker_lost=True,
    **INGESTION_RETRY_POLICY,
)
def cleanup_synthetic_generation(*, limit: int = 100) -> list[str]:
    return list(asyncio.run(run_synthetic_raw_cleanup(limit=limit)))


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

    def dispatch_asset_deletion(self, message: AssetDeletionTaskMessage) -> str:
        message.validate()
        process_asset_deletion.apply_async(
            args=[message.to_message()],
            task_id=secrets.token_hex(16),
            headers={"request_id": message.request_id, "job_id": message.job_id},
            queue="mirror.maintenance",
        )
        return message.job_id

    def dispatch_data_export(self, message: DataExportTaskMessage) -> str:
        message.validate()
        process_data_export.apply_async(
            args=[message.to_message()],
            task_id=secrets.token_hex(16),
            headers={"request_id": message.request_id, "job_id": message.job_id},
            queue="mirror.maintenance",
        )
        return message.job_id

    def dispatch_account_deletion(self, message: AccountDeletionTaskMessage) -> str:
        message.validate()
        process_account_deletion.apply_async(
            args=[message.to_message()],
            task_id=secrets.token_hex(16),
            headers={"request_id": message.request_id, "job_id": message.job_id},
            queue="mirror.maintenance",
        )
        return message.job_id

    def dispatch_synthetic_generation(self, message: SyntheticGenerationTaskMessage) -> str:
        message.validate()
        process_synthetic_generation.apply_async(
            args=[message.to_message()],
            task_id=secrets.token_hex(16),
            headers={"request_id": message.request_id, "job_id": message.job_id},
            queue="mirror.synthetic",
        )
        return message.job_id
