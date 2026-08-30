"""Typed, opaque Worker message for D07 editing operations."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Final, Literal, Protocol

DEMO_EDITING_TASK_SCHEMA: Final = "demo-editing-task-v1"
DemoEditingOperation = Literal[
    "editing_session.create",
    "edit_plan.create",
    "edit_plan.execute",
    "image_version.restore",
]
_OPERATIONS: Final = frozenset(
    {
        "editing_session.create",
        "edit_plan.create",
        "edit_plan.execute",
        "image_version.restore",
    }
)
_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class DemoEditingTaskMessage:
    demo_actor_id: str
    job_id: str
    operation: DemoEditingOperation
    request_id: str
    schema_version: str = DEMO_EDITING_TASK_SCHEMA

    def validate(self) -> None:
        if (
            type(self.demo_actor_id) is not str
            or type(self.job_id) is not str
            or _ID.fullmatch(self.demo_actor_id) is None
            or _ID.fullmatch(self.job_id) is None
        ):
            raise ValueError("editing task identifiers must be opaque")
        if type(self.operation) is not str or self.operation not in _OPERATIONS:
            raise ValueError("editing task operation is unsupported")
        if (
            type(self.request_id) is not str
            or not 8 <= len(self.request_id) <= 128
            or any(character in self.request_id for character in "\r\n\0")
        ):
            raise ValueError("editing task request id is outside the safe boundary")
        if self.schema_version != DEMO_EDITING_TASK_SCHEMA:
            raise ValueError("unsupported editing task schema version")

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> DemoEditingTaskMessage:
        expected = {
            "demo_actor_id",
            "job_id",
            "operation",
            "request_id",
            "schema_version",
        }
        if set(message) != expected or not all(type(value) is str for value in message.values()):
            raise ValueError("editing task message has an invalid shape")
        operation = message["operation"]
        if operation not in _OPERATIONS:
            raise ValueError("editing task operation is unsupported")
        result = cls(
            demo_actor_id=message["demo_actor_id"],
            job_id=message["job_id"],
            operation=operation,
            request_id=message["request_id"],
            schema_version=message["schema_version"],
        )
        result.validate()
        return result


class DemoEditingDispatcher(Protocol):
    def dispatch_demo_editing(self, message: DemoEditingTaskMessage) -> str: ...


__all__ = [
    "DEMO_EDITING_TASK_SCHEMA",
    "DemoEditingDispatcher",
    "DemoEditingOperation",
    "DemoEditingTaskMessage",
]
