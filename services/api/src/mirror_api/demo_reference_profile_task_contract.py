"""Opaque, reference-only queued D06 task contract."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Final, Protocol

DEMO_REFERENCE_PROFILE_TASK_SCHEMA: Final = "demo-reference-profile-task-v1"
_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class DemoReferenceProfileTaskMessage:
    demo_actor_id: str
    job_id: str
    compile_request_id: str
    request_id: str
    schema_version: str = DEMO_REFERENCE_PROFILE_TASK_SCHEMA

    def validate(self) -> None:
        identifiers = (self.demo_actor_id, self.job_id, self.compile_request_id)
        if any(type(value) is not str or _ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("reference profile task identifiers must be opaque")
        if (
            type(self.request_id) is not str
            or not 8 <= len(self.request_id) <= 128
            or any(char in self.request_id for char in "\r\n\0")
        ):
            raise ValueError("reference profile request id is outside the safe boundary")
        if self.schema_version != DEMO_REFERENCE_PROFILE_TASK_SCHEMA:
            raise ValueError("unsupported reference profile task schema")

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> DemoReferenceProfileTaskMessage:
        expected = {
            "demo_actor_id",
            "job_id",
            "compile_request_id",
            "request_id",
            "schema_version",
        }
        if set(message) != expected or not all(type(value) is str for value in message.values()):
            raise ValueError("reference profile task message has an invalid shape")
        result = cls(**message)
        result.validate()
        return result


class DemoReferenceProfileDispatcher(Protocol):
    def dispatch_demo_reference_profile(self, message: DemoReferenceProfileTaskMessage) -> str: ...


__all__ = [
    "DEMO_REFERENCE_PROFILE_TASK_SCHEMA",
    "DemoReferenceProfileDispatcher",
    "DemoReferenceProfileTaskMessage",
]
