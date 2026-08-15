from __future__ import annotations

from collections.abc import Mapping
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
