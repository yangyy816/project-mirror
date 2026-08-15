from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

DATA_EXPORT_TASK_SCHEMA = "data-export-task-v1"
ACCOUNT_DELETION_TASK_SCHEMA = "account-deletion-task-v1"


def _validate(job_id: str, request_id: str, schema_version: str, expected: str) -> None:
    if re.fullmatch(r"[0-9a-f]{32}", job_id) is None:
        raise ValueError("job_id must be an opaque 32-character lowercase hex identifier")
    if not 8 <= len(request_id) <= 128:
        raise ValueError("request_id length is invalid")
    if schema_version != expected:
        raise ValueError("unsupported data-rights task schema version")


@dataclass(frozen=True)
class DataExportTaskMessage:
    job_id: str
    request_id: str
    schema_version: str = DATA_EXPORT_TASK_SCHEMA

    def validate(self) -> None:
        _validate(self.job_id, self.request_id, self.schema_version, DATA_EXPORT_TASK_SCHEMA)

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> DataExportTaskMessage:
        result = cls(**_validated_shape(message))
        result.validate()
        return result


@dataclass(frozen=True)
class AccountDeletionTaskMessage:
    job_id: str
    request_id: str
    schema_version: str = ACCOUNT_DELETION_TASK_SCHEMA

    def validate(self) -> None:
        _validate(
            self.job_id,
            self.request_id,
            self.schema_version,
            ACCOUNT_DELETION_TASK_SCHEMA,
        )

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> AccountDeletionTaskMessage:
        result = cls(**_validated_shape(message))
        result.validate()
        return result


def _validated_shape(message: dict[str, Any]) -> dict[str, str]:
    expected = {"job_id", "request_id", "schema_version"}
    if set(message) != expected or not all(isinstance(value, str) for value in message.values()):
        raise ValueError("data-rights task message has an invalid shape")
    return {key: message[key] for key in expected}


class DataRightsDispatcher(Protocol):
    def dispatch_data_export(self, message: DataExportTaskMessage) -> str: ...

    def dispatch_account_deletion(self, message: AccountDeletionTaskMessage) -> str: ...
