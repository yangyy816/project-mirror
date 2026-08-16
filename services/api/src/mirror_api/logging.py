from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "code",
    "cookie",
    "phone",
    "phone_number",
    "secret",
    "signed_url",
    "token",
    "tencent_secret_id",
    "tencent_secret_key",
}

_EVENT_NAME = re.compile(r"^[a-z][a-z0-9_.]{2,63}$")
_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
_OPERATION = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
_HTTP_METHOD = re.compile(r"^[A-Z]{3,10}$")
_ROUTE_TEMPLATE = re.compile(r"^/[A-Za-z0-9_./{}-]{0,127}$")
_OUTCOMES = frozenset({"deferred", "failed", "rejected", "succeeded"})


@dataclass(frozen=True)
class OperationalEvent:
    """Allowlisted, payload-free event suitable for log-based counts and latency."""

    event_name: str
    outcome: str
    request_id: str
    operation: str
    duration_ms: int | None = None
    status_code: int | None = None
    job_id: str | None = None
    method: str | None = None
    route_template: str | None = None

    def __post_init__(self) -> None:
        if not _EVENT_NAME.fullmatch(self.event_name):
            raise ValueError("invalid operational event name")
        if self.outcome not in _OUTCOMES:
            raise ValueError("invalid operational event outcome")
        if not _CORRELATION_ID.fullmatch(self.request_id):
            raise ValueError("invalid operational request correlation")
        if not _OPERATION.fullmatch(self.operation):
            raise ValueError("invalid operational event operation")
        if self.duration_ms is not None and not 0 <= self.duration_ms <= 86_400_000:
            raise ValueError("invalid operational event duration")
        if self.status_code is not None and not 100 <= self.status_code <= 599:
            raise ValueError("invalid operational status code")
        if self.job_id is not None and not _CORRELATION_ID.fullmatch(self.job_id):
            raise ValueError("invalid operational job correlation")
        if self.method is not None and not _HTTP_METHOD.fullmatch(self.method):
            raise ValueError("invalid operational HTTP method")
        if self.route_template is not None and not _ROUTE_TEMPLATE.fullmatch(self.route_template):
            raise ValueError("invalid operational route template")


def emit_operational_event(logger: logging.Logger, event: OperationalEvent) -> None:
    """Emit canonical JSON without accepting arbitrary metadata or sensitive payloads."""

    payload = {key: value for key, value in asdict(event).items() if value is not None}
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    if event.outcome in {"deferred", "failed"}:
        logger.warning(serialized)
    else:
        logger.info(serialized)


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, item in value.items():
        if key.lower() in SENSITIVE_KEYS or any(
            marker in key.lower() for marker in ("password", "credential", "secret", "token")
        ):
            redacted[key] = "[REDACTED]"
        elif isinstance(item, Mapping):
            redacted[key] = redact_mapping(item)
        elif isinstance(item, list):
            redacted[key] = [redact_mapping(x) if isinstance(x, Mapping) else x for x in item]
        else:
            redacted[key] = item
    return redacted
