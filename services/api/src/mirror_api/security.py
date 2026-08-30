from __future__ import annotations

import hmac
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt

from mirror_api.errors import APIError

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PIXEL_COUNT = 40_000_000
SAFE_STORAGE_KEY = re.compile(r"^[a-z0-9][a-z0-9/_-]{0,254}$")
PHONE_BODY = re.compile(r"^1[3-9]\d{9}$")
KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
TOKEN_ID = re.compile(r"^[0-9a-f]{32}$")
REFRESH_TOKEN_PROOF = re.compile(r"^[0-9a-f]{64}$")
HMACPurpose = Literal["phone", "otp", "invite", "idempotency", "refresh", "provider-reference"]


class SecurityValidationError(ValueError):
    """A stable error suitable for a public authentication boundary."""


@dataclass(frozen=True)
class RefreshToken:
    value: str
    key_id: str
    token_id: str
    hmac_value: str


@dataclass(frozen=True)
class RefreshCookiePolicy:
    name: str
    httponly: bool
    secure: bool
    samesite: Literal["lax"]
    path: str
    max_age_seconds: int


@dataclass(frozen=True)
class UploadMetadata:
    mime_type: str
    byte_size: int
    width: int
    height: int


def validate_storage_key(key: str) -> str:
    if not SAFE_STORAGE_KEY.fullmatch(key) or ".." in key or key.startswith("/"):
        raise APIError(
            status_code=400,
            code="unsafe_storage_key",
            message="存储对象路径不合法。",
        )
    return key


def validate_upload_metadata(metadata: UploadMetadata) -> UploadMetadata:
    if metadata.mime_type not in ALLOWED_MIME_TYPES:
        raise APIError(status_code=415, code="unsupported_image_type", message="不支持该图片类型。")
    if metadata.byte_size <= 0 or metadata.byte_size > MAX_UPLOAD_BYTES:
        raise APIError(status_code=413, code="image_too_large", message="图片文件大小超限。")
    if metadata.width <= 0 or metadata.height <= 0:
        raise APIError(status_code=400, code="invalid_dimensions", message="图片尺寸无效。")
    if metadata.width * metadata.height > MAX_PIXEL_COUNT:
        raise APIError(status_code=413, code="pixel_count_exceeded", message="图片像素总量超限。")
    return metadata


def normalize_china_phone(value: str) -> str:
    """Return the sole accepted representation: +86 followed by an 11-digit mainland number."""
    compact = value.strip().replace(" ", "").replace("-", "")
    if compact.startswith("+86"):
        number = compact[3:]
    elif compact.startswith("86"):
        number = compact[2:]
    else:
        number = compact
    if not PHONE_BODY.fullmatch(number):
        raise SecurityValidationError("invalid mainland phone number")
    return f"+86{number}"


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _purpose_message(purpose: HMACPurpose, value: str) -> bytes:
    return f"project-mirror:{purpose}:v1:{value}".encode()


def hmac_digest(
    value: str,
    *,
    purpose: HMACPurpose,
    keyring: Mapping[str, str],
    key_id: str,
) -> str:
    if not KEY_ID.fullmatch(key_id) or key_id not in keyring:
        raise SecurityValidationError("unknown security key id")
    digest = hmac.digest(
        keyring[key_id].encode("utf-8"), _purpose_message(purpose, value), "sha256"
    )
    return f"{key_id}:{digest.hex()}"


def verify_hmac(
    value: str,
    expected: str,
    *,
    purpose: HMACPurpose,
    keyring: Mapping[str, str],
) -> bool:
    key_id, separator, _digest = expected.partition(":")
    if not separator or not KEY_ID.fullmatch(key_id) or key_id not in keyring:
        return False
    candidate = hmac_digest(value, purpose=purpose, keyring=keyring, key_id=key_id)
    return hmac.compare_digest(candidate, expected)


def issue_access_token(
    *,
    subject: str,
    session_id: str,
    scope: str | tuple[str, ...],
    keyring: Mapping[str, str],
    active_key_id: str,
    issuer: str,
    audience: str,
    ttl_seconds: int = 300,
    now: datetime | None = None,
) -> str:
    if active_key_id not in keyring or ttl_seconds > 300 or ttl_seconds < 1:
        raise SecurityValidationError("invalid access-token signing configuration")
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    payload: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "sid": session_id,
        "scope": " ".join(scope) if isinstance(scope, tuple) else scope,
        "jti": secrets.token_urlsafe(24),
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(
        payload, keyring[active_key_id], algorithm="HS256", headers={"kid": active_key_id}
    )


def verify_access_token(
    token: str,
    *,
    keyring: Mapping[str, str],
    issuer: str,
    audience: str,
) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
        key_id = header.get("kid")
        if not isinstance(key_id, str) or key_id not in keyring:
            raise SecurityValidationError("invalid access token")
        return jwt.decode(
            token,
            keyring[key_id],
            algorithms=["HS256"],
            issuer=issuer,
            audience=audience,
            options={"require": ["iss", "aud", "sub", "sid", "scope", "jti", "iat", "nbf", "exp"]},
        )
    except (jwt.PyJWTError, SecurityValidationError) as exc:
        raise SecurityValidationError("invalid access token") from exc


def _derive_refresh_token_proof(*, token_id: str, keyring: Mapping[str, str], key_id: str) -> str:
    derived = hmac_digest(token_id, purpose="refresh", keyring=keyring, key_id=key_id)
    return derived.partition(":")[2]


def create_refresh_token(
    *, keyring: Mapping[str, str], active_key_id: str, token_id: str | None = None
) -> RefreshToken:
    if not KEY_ID.fullmatch(active_key_id) or active_key_id not in keyring:
        raise SecurityValidationError("invalid refresh-token signing configuration")
    resolved_token_id = token_id or secrets.token_hex(16)
    if not TOKEN_ID.fullmatch(resolved_token_id):
        raise SecurityValidationError("invalid refresh-token identifier")
    proof = _derive_refresh_token_proof(
        token_id=resolved_token_id, keyring=keyring, key_id=active_key_id
    )
    value = f"rt1.{active_key_id}.{resolved_token_id}.{proof}"
    return RefreshToken(
        value=value,
        key_id=active_key_id,
        token_id=resolved_token_id,
        hmac_value=hmac_digest(value, purpose="refresh", keyring=keyring, key_id=active_key_id),
    )


def verify_refresh_token(token: str, expected_hmac: str, *, keyring: Mapping[str, str]) -> bool:
    parts = token.split(".")
    if len(parts) != 4:
        return False
    prefix, key_id, token_id, proof = parts
    if (
        prefix != "rt1"
        or not KEY_ID.fullmatch(key_id)
        or key_id not in keyring
        or not TOKEN_ID.fullmatch(token_id)
        or not REFRESH_TOKEN_PROOF.fullmatch(proof)
    ):
        return False
    expected_proof = _derive_refresh_token_proof(token_id=token_id, keyring=keyring, key_id=key_id)
    if not hmac.compare_digest(proof, expected_proof):
        return False
    return verify_hmac(token, expected_hmac, purpose="refresh", keyring=keyring)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(provided: str | None, expected: str) -> bool:
    return provided is not None and hmac.compare_digest(provided, expected)


def validate_origin(origin: str | None, allowed_origins: tuple[str, ...] | list[str]) -> str:
    if origin is None or not any(
        hmac.compare_digest(origin, allowed) for allowed in allowed_origins
    ):
        raise SecurityValidationError("origin is not allowed")
    return origin


def refresh_cookie_policy(
    *,
    app_env: Literal["development", "test", "ci", "production"],
    name: str,
    ttl_seconds: int,
) -> RefreshCookiePolicy:
    return RefreshCookiePolicy(
        name=name,
        httponly=True,
        secure=app_env == "production",
        samesite="lax",
        path="/api/v1/auth",
        max_age_seconds=ttl_seconds,
    )


def sanitize_request_validation_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove framework-supplied input echoes before a validation error is serialized."""
    return [
        {key: value for key, value in error.items() if key not in {"ctx", "input"}}
        for error in errors
    ]
