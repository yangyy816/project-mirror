from __future__ import annotations

import asyncio

from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage
from mirror_api.config import Settings, get_settings
from mirror_api.data_rights.task_contract import (
    AccountDeletionTaskMessage,
    DataExportTaskMessage,
)
from mirror_api.ingestion.task_contract import IngestionTaskMessage
from mirror_api.synthetic_dataset.task_contract import SyntheticGenerationTaskMessage

from mirror_worker.application import FoundationProbeService, TaskEnvelope
from mirror_worker.runtime import (
    run_account_deletion_message,
    run_asset_deletion_message,
    run_data_export_message,
    run_ingestion_message,
    run_synthetic_generation_message,
)


class LocalTaskRunner:
    """Synchronous DEVELOPMENT ONLY task runner."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if self.settings.app_env not in {"development", "test"}:
            raise RuntimeError("LocalTaskRunner is DEVELOPMENT ONLY")
        self.service = FoundationProbeService()

    def dispatch(self, envelope: TaskEnvelope) -> str:
        self.service.execute(envelope)
        return envelope.job_id

    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str:
        message.validate()
        asyncio.run(run_ingestion_message(message.to_message(), settings=self.settings))
        return message.job_id

    def dispatch_asset_deletion(self, message: AssetDeletionTaskMessage) -> str:
        message.validate()
        asyncio.run(run_asset_deletion_message(message.to_message(), settings=self.settings))
        return message.job_id

    def dispatch_data_export(self, message: DataExportTaskMessage) -> str:
        message.validate()
        asyncio.run(run_data_export_message(message.to_message(), settings=self.settings))
        return message.job_id

    def dispatch_account_deletion(self, message: AccountDeletionTaskMessage) -> str:
        message.validate()
        asyncio.run(run_account_deletion_message(message.to_message(), settings=self.settings))
        return message.job_id

    def dispatch_synthetic_generation(self, message: SyntheticGenerationTaskMessage) -> str:
        message.validate()
        asyncio.run(run_synthetic_generation_message(message.to_message(), settings=self.settings))
        return message.job_id
