from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

ASSET_DELETION_TASK_SCHEMA = "asset-deletion-task-v1"


@dataclass(frozen=True)
class AssetDeletionTaskMessage:
    job_id: str
    request_id: str
    schema_version: str = ASSET_DELETION_TASK_SCHEMA

    def validate(self) -> None:
        if re.fullmatch(r"[0-9a-f]{32}", self.job_id) is None:
            raise ValueError("job_id must be an opaque 32-character lowercase hex identifier")
        if not 8 <= len(self.request_id) <= 128:
            raise ValueError("request_id length is invalid")
        if self.schema_version != ASSET_DELETION_TASK_SCHEMA:
            raise ValueError("unsupported asset deletion task schema version")

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> AssetDeletionTaskMessage:
        expected = {"job_id", "request_id", "schema_version"}
        if set(message) != expected or not all(
            isinstance(value, str) for value in message.values()
        ):
            raise ValueError("asset deletion task message has an invalid shape")
        result = cls(**message)
        result.validate()
        return result


class AssetDeletionDispatcher(Protocol):
    def dispatch_asset_deletion(self, message: AssetDeletionTaskMessage) -> str: ...
