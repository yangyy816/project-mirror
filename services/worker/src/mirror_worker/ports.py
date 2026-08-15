from __future__ import annotations

from typing import Protocol

from mirror_api.ingestion.task_contract import IngestionTaskMessage

from mirror_worker.application import TaskEnvelope


class TaskDispatcher(Protocol):
    def dispatch(self, envelope: TaskEnvelope) -> str: ...

    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str: ...
