from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

INGESTION_TASK_SCHEMA = "ingestion-task-v1"


@dataclass(frozen=True)
class IngestionTaskMessage:
    """Provider-neutral ingestion message containing references only."""

    job_id: str
    request_id: str
    schema_version: str = INGESTION_TASK_SCHEMA

    def validate(self) -> None:
        if re.fullmatch(r"[0-9a-f]{32}", self.job_id) is None:
            raise ValueError("job_id must be an opaque 32-character lowercase hex identifier")
        if not 8 <= len(self.request_id) <= 128:
            raise ValueError("request_id length is invalid")
        if self.schema_version != INGESTION_TASK_SCHEMA:
            raise ValueError("unsupported ingestion task schema version")

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> IngestionTaskMessage:
        expected = {"job_id", "request_id", "schema_version"}
        if set(message) != expected or not all(
            isinstance(value, str) for value in message.values()
        ):
            raise ValueError("ingestion task message has an invalid shape")
        task_message = cls(
            job_id=message["job_id"],
            request_id=message["request_id"],
            schema_version=message["schema_version"],
        )
        task_message.validate()
        return task_message


class IngestionDispatcher(Protocol):
    def dispatch_ingestion(self, message: IngestionTaskMessage) -> str: ...
