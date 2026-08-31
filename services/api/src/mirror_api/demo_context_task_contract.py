"""Opaque task envelope for queued D10 Context compilation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Final, Protocol

DEMO_CONTEXT_TASK_SCHEMA: Final = "demo-context-task-v1"
_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class DemoContextTaskMessage:
    demo_actor_id: str
    job_id: str
    context_request_id: str
    request_id: str
    schema_version: str = DEMO_CONTEXT_TASK_SCHEMA

    def validate(self) -> None:
        if any(
            type(value) is not str or _ID.fullmatch(value) is None
            for value in (self.demo_actor_id, self.job_id, self.context_request_id)
        ):
            raise ValueError("context task identifiers must be opaque")
        if (
            type(self.request_id) is not str
            or not 8 <= len(self.request_id) <= 128
            or any(char in self.request_id for char in "\r\n\0")
        ):
            raise ValueError("context task request id is outside the safe boundary")
        if self.schema_version != DEMO_CONTEXT_TASK_SCHEMA:
            raise ValueError("unsupported context task schema")

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> DemoContextTaskMessage:
        if set(message) != {
            "demo_actor_id",
            "job_id",
            "context_request_id",
            "request_id",
            "schema_version",
        } or not all(type(value) is str for value in message.values()):
            raise ValueError("context task message has an invalid shape")
        result = cls(**message)
        result.validate()
        return result


class DemoContextDispatcher(Protocol):
    def dispatch_demo_context(self, message: DemoContextTaskMessage) -> str: ...


__all__ = ["DEMO_CONTEXT_TASK_SCHEMA", "DemoContextDispatcher", "DemoContextTaskMessage"]
