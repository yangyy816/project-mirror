"""Reference-only task contract for deterministic Demo profile compilation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

DEMO_PROFILE_TASK_SCHEMA = "demo-profile-task-v1"
_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class DemoProfileTaskMessage:
    demo_actor_id: str
    job_id: str
    request_id: str
    schema_version: str = DEMO_PROFILE_TASK_SCHEMA

    def validate(self) -> None:
        if (
            not isinstance(self.demo_actor_id, str)
            or not isinstance(self.job_id, str)
            or _ID.fullmatch(self.demo_actor_id) is None
            or _ID.fullmatch(self.job_id) is None
        ):
            raise ValueError("profile task identifiers must be opaque")
        if (
            not isinstance(self.request_id, str)
            or not 8 <= len(self.request_id) <= 128
            or any(character in self.request_id for character in "\r\n\0")
        ):
            raise ValueError("profile task request id is outside the safe boundary")
        if self.schema_version != DEMO_PROFILE_TASK_SCHEMA:
            raise ValueError("unsupported profile task schema version")

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> DemoProfileTaskMessage:
        expected = {"demo_actor_id", "job_id", "request_id", "schema_version"}
        if set(message) != expected or not all(
            isinstance(value, str) for value in message.values()
        ):
            raise ValueError("profile task message has an invalid shape")
        result = cls(
            demo_actor_id=message["demo_actor_id"],
            job_id=message["job_id"],
            request_id=message["request_id"],
            schema_version=message["schema_version"],
        )
        result.validate()
        return result


class DemoProfileDispatcher(Protocol):
    def dispatch_demo_profile(self, message: DemoProfileTaskMessage) -> str: ...


__all__ = ["DemoProfileDispatcher", "DemoProfileTaskMessage"]
