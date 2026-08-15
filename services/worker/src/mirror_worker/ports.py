from __future__ import annotations

from typing import Protocol

from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage
from mirror_api.ingestion.task_contract import IngestionTaskMessage

from mirror_worker.application import TaskEnvelope


class TaskDispatcher(Protocol):
    def dispatch(self, envelope: TaskEnvelope) -> str: ...

    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str: ...

    def dispatch_asset_deletion(self, message: AssetDeletionTaskMessage) -> str: ...
