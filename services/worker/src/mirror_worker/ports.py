from __future__ import annotations

from typing import Protocol

from mirror_worker.application import TaskEnvelope


class TaskDispatcher(Protocol):
    def dispatch(self, envelope: TaskEnvelope) -> str: ...
