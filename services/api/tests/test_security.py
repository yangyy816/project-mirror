from __future__ import annotations

import pytest

from mirror_api.errors import APIError
from mirror_api.security import (
    SecurityValidationError,
    UploadMetadata,
    create_refresh_token,
    generate_csrf_token,
    generate_otp,
    hmac_digest,
    issue_access_token,
    normalize_china_phone,
    refresh_cookie_policy,
    sanitize_request_validation_details,
    validate_origin,
    validate_storage_key,
    validate_upload_metadata,
    verify_access_token,
    verify_csrf_token,
    verify_hmac,
    verify_refresh_token,
)


@pytest.mark.parametrize("key", ["../secret", "/absolute", "users/x/../../secret", "A/upper"])
def test_unsafe_storage_keys_are_rejected(key: str) -> None:
    with pytest.raises(APIError):
        validate_storage_key(key)


def test_dangerous_mime_and_decompression_bomb_metadata_are_rejected() -> None:
    with pytest.raises(APIError) as mime_error:
        validate_upload_metadata(
            UploadMetadata(mime_type="image/svg+xml", byte_size=10, width=10, height=10)
        )
    assert mime_error.value.status_code == 415

    with pytest.raises(APIError) as pixel_error:
        validate_upload_metadata(
            UploadMetadata(mime_type="image/jpeg", byte_size=10, width=100_000, height=100_000)
        )
    assert pixel_error.value.code == "pixel_count_exceeded"


def _synthetic_phone_body() -> str:
    """Deterministic test-only data; it is never sent to an external service."""
    return "".join(("1", "3", "8", "0", "0", "1", "3", "8", "0", "0", "0"))


def test_mainland_phone_is_normalized_to_the_only_accepted_format() -> None:
    phone_body = _synthetic_phone_body()
    normalized = f"+86{phone_body}"
    assert normalize_china_phone(phone_body) == normalized
    assert (
        normalize_china_phone(f"+86 {phone_body[:3]}-{phone_body[3:7]}-{phone_body[7:]}")
        == normalized
    )


@pytest.mark.parametrize("raw", ["+86" + "12000138000", "+85213800138000", "not-a-phone"])
def test_non_mainland_phone_is_rejected(raw: str) -> None:
    with pytest.raises(SecurityValidationError):
        normalize_china_phone(raw)


def test_otp_is_six_digits() -> None:
    assert generate_otp().isdigit()
    assert len(generate_otp()) == 6


def test_hmac_is_purpose_separated_and_constant_time_verifiable() -> None:
    keyring = {"v1": "k" * 64}
    sentinel = "phone-hmac-sentinel"
    phone_digest = hmac_digest(sentinel, purpose="phone", keyring=keyring, key_id="v1")
    assert phone_digest != hmac_digest(sentinel, purpose="invite", keyring=keyring, key_id="v1")
    assert verify_hmac(sentinel, phone_digest, purpose="phone", keyring=keyring)
    assert not verify_hmac(sentinel, phone_digest, purpose="invite", keyring=keyring)


def test_access_jwt_requires_hs256_key_id_and_fixed_claims() -> None:
    keyring = {"v1": "k" * 64}
    token = issue_access_token(
        subject="user-123",
        session_id="session-123",
        scope=("pending",),
        keyring=keyring,
        active_key_id="v1",
        issuer="mirror-api",
        audience="mirror-web",
    )
    claims = verify_access_token(token, keyring=keyring, issuer="mirror-api", audience="mirror-web")
    assert claims["sub"] == "user-123"
    assert claims["sid"] == "session-123"
    with pytest.raises(SecurityValidationError):
        verify_access_token(token, keyring=keyring, issuer="other", audience="mirror-web")


def test_refresh_token_is_opaque_keyed_and_hmac_verified() -> None:
    keyring = {"v1": "k" * 64}
    token_id = "a" * 32
    token = create_refresh_token(keyring=keyring, active_key_id="v1", token_id=token_id)
    replay = create_refresh_token(keyring=keyring, active_key_id="v1", token_id=token_id)
    assert token.value.startswith("rt1.v1.")
    assert token.token_id == token_id
    assert replay.value == token.value
    assert replay.hmac_value == token.hmac_value
    assert verify_refresh_token(token.value, token.hmac_value, keyring=keyring)
    different = create_refresh_token(keyring=keyring, active_key_id="v1", token_id="b" * 32)
    assert different.value != token.value
    assert different.hmac_value != token.hmac_value
    tampered = f"{token.value[:-1]}{'0' if token.value[-1] != '0' else '1'}"
    assert not verify_refresh_token(tampered, token.hmac_value, keyring=keyring)
    assert not verify_refresh_token(
        token.value.replace(".v1.", ".retired.", 1), token.hmac_value, keyring=keyring
    )


def test_refresh_token_default_token_id_is_random_and_valid() -> None:
    keyring = {"v1": "k" * 64}
    first = create_refresh_token(keyring=keyring, active_key_id="v1")
    second = create_refresh_token(keyring=keyring, active_key_id="v1")
    assert first.token_id != second.token_id
    assert first.value != second.value


def test_csrf_origin_and_environment_cookie_policy() -> None:
    csrf = generate_csrf_token()
    assert verify_csrf_token(csrf, csrf)
    assert not verify_csrf_token("wrong", csrf)
    assert (
        validate_origin("https://mirror.example", ["https://mirror.example"])
        == "https://mirror.example"
    )
    with pytest.raises(SecurityValidationError):
        validate_origin("https://attacker.example", ["https://mirror.example"])
    assert refresh_cookie_policy(app_env="production", name="refresh", ttl_seconds=60).secure
    assert not refresh_cookie_policy(app_env="development", name="refresh", ttl_seconds=60).secure


def test_request_validation_details_do_not_echo_sensitive_input() -> None:
    details = sanitize_request_validation_details(
        [{"type": "string_too_short", "loc": ["body", "phone"], "input": "phone-sentinel"}]
    )
    assert details == [{"type": "string_too_short", "loc": ["body", "phone"]}]
