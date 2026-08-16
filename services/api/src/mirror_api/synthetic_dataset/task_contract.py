from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

SYNTHETIC_GENERATION_TASK_SCHEMA = "synthetic-generation-task-v1"
_ID = re.compile(r"[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class SyntheticGenerationTaskMessage:
    """Reference-only generation task; Prompt, policy, bytes and URLs are forbidden."""

    item_id: str
    job_id: str
    request_id: str
    schema_version: str = SYNTHETIC_GENERATION_TASK_SCHEMA

    def validate(self) -> None:
        if _ID.fullmatch(self.item_id) is None or _ID.fullmatch(self.job_id) is None:
            raise ValueError("generation task identifiers must be opaque")
        if not 8 <= len(self.request_id) <= 128 or any(
            character in self.request_id for character in "\r\n\0"
        ):
            raise ValueError("generation task request id is outside the safe boundary")
        if self.schema_version != SYNTHETIC_GENERATION_TASK_SCHEMA:
            raise ValueError("unsupported synthetic generation task schema version")

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> SyntheticGenerationTaskMessage:
        expected = {"item_id", "job_id", "request_id", "schema_version"}
        if set(message) != expected or not all(
            isinstance(value, str) for value in message.values()
        ):
            raise ValueError("synthetic generation task message has an invalid shape")
        result = cls(
            item_id=message["item_id"],
            job_id=message["job_id"],
            request_id=message["request_id"],
            schema_version=message["schema_version"],
        )
        result.validate()
        return result


class SyntheticGenerationDispatcher(Protocol):
    def dispatch_synthetic_generation(self, message: SyntheticGenerationTaskMessage) -> str: ...
