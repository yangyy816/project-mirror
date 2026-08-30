"""Typed, deterministic queue contract for queued D10 Profile rebuilds."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from mirror_api.demo_idempotency import canonical_json_bytes

DEMO_MEMORY_TASK_SCHEMA = "demo-memory-task-v1"
_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class DemoMemoryTaskMessage:
    demo_actor_id: str
    job_id: str
    request_id: str
    schema_version: str = DEMO_MEMORY_TASK_SCHEMA

    def validate(self) -> None:
        if (
            not isinstance(self.demo_actor_id, str)
            or not isinstance(self.job_id, str)
            or _ID.fullmatch(self.demo_actor_id) is None
            or _ID.fullmatch(self.job_id) is None
        ):
            raise ValueError("memory task identifiers must be opaque")
        if (
            not isinstance(self.request_id, str)
            or not 8 <= len(self.request_id) <= 128
            or any(character in self.request_id for character in "\r\n\0")
        ):
            raise ValueError("memory task request id is outside the safe boundary")
        if self.schema_version != DEMO_MEMORY_TASK_SCHEMA:
            raise ValueError("unsupported memory task schema version")

    @property
    def payload_digest(self) -> str:
        self.validate()
        return hashlib.sha256(
            self.schema_version.encode("utf-8") + b"\n" + canonical_json_bytes(self.to_message())
        ).hexdigest()

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> DemoMemoryTaskMessage:
        expected = {"demo_actor_id", "job_id", "request_id", "schema_version"}
        if set(message) != expected or not all(
            isinstance(value, str) for value in message.values()
        ):
            raise ValueError("memory task message has an invalid shape")
        result = cls(
            demo_actor_id=message["demo_actor_id"],
            job_id=message["job_id"],
            request_id=message["request_id"],
            schema_version=message["schema_version"],
        )
        result.validate()
        return result


class DemoMemoryDispatcher(Protocol):
    def dispatch_demo_memory(self, message: DemoMemoryTaskMessage) -> str: ...


__all__ = ["DemoMemoryDispatcher", "DemoMemoryTaskMessage"]
