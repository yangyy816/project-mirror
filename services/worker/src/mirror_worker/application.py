from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TaskEnvelope:
    job_id: str
    request_id: str
    idempotency_key_hash: str
    task_type: str
    payload: dict[str, Any]
    schema_version: int = 1

    def validate(self) -> None:
        if len(self.job_id) != 32 or any(char not in "0123456789abcdef" for char in self.job_id):
            raise ValueError("job_id must be an opaque 32-character lowercase hex identifier")
        if not 8 <= len(self.request_id) <= 128:
            raise ValueError("request_id length is invalid")
        if len(self.idempotency_key_hash) != 64:
            raise ValueError("idempotency_key_hash must be a SHA-256 hex digest")
        if self.schema_version != 1:
            raise ValueError("unsupported task schema version")

    def to_message(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> TaskEnvelope:
        envelope = cls(**message)
        envelope.validate()
        return envelope


class FoundationProbeService:
    """Application logic with no Celery, Redis, database, or provider dependency."""

    def execute(self, envelope: TaskEnvelope) -> dict[str, str]:
        envelope.validate()
        if envelope.task_type != "foundation_probe":
            raise ValueError("unsupported task type")
        return {
            "job_id": envelope.job_id,
            "request_id": envelope.request_id,
            "status": "ok",
        }
