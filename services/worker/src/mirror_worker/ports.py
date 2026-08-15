from __future__ import annotations

from typing import Protocol

from mirror_worker.application import TaskEnvelope
from mirror_worker.ingestion import IngestionTaskMessage


class TaskDispatcher(Protocol):
    def dispatch(self, envelope: TaskEnvelope) -> str: ...

    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str: ...
