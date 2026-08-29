"""Reference-only D03 analysis task contract.

Messages contain opaque database identifiers only.  Image bytes, storage
locations, runtime/model handles, Prompts and credentials are intentionally
outside the queue contract.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

DEMO_ANALYSIS_TASK_SCHEMA = "demo-analysis-task-v1"
_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class DemoAnalysisTaskMessage:
    analysis_run_id: str
    job_id: str
    request_id: str
    schema_version: str = DEMO_ANALYSIS_TASK_SCHEMA

    def validate(self) -> None:
        if (
            not isinstance(self.analysis_run_id, str)
            or not isinstance(self.job_id, str)
            or _ID.fullmatch(self.analysis_run_id) is None
            or _ID.fullmatch(self.job_id) is None
        ):
            raise ValueError("analysis task identifiers must be opaque")
        if (
            not isinstance(self.request_id, str)
            or not 8 <= len(self.request_id) <= 128
            or any(character in self.request_id for character in "\r\n\0")
        ):
            raise ValueError("analysis task request id is outside the safe boundary")
        if self.schema_version != DEMO_ANALYSIS_TASK_SCHEMA:
            raise ValueError("unsupported analysis task schema version")

    def to_message(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> DemoAnalysisTaskMessage:
        expected = {"analysis_run_id", "job_id", "request_id", "schema_version"}
        if set(message) != expected or not all(
            isinstance(value, str) for value in message.values()
        ):
            raise ValueError("analysis task message has an invalid shape")
        result = cls(
            analysis_run_id=message["analysis_run_id"],
            job_id=message["job_id"],
            request_id=message["request_id"],
            schema_version=message["schema_version"],
        )
        result.validate()
        return result


class DemoAnalysisDispatcher(Protocol):
    def dispatch_demo_analysis(self, message: DemoAnalysisTaskMessage) -> str: ...
