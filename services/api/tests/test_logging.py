from mirror_api.logging import redact_mapping


def test_sensitive_log_fields_are_redacted_recursively() -> None:
    payload = {
        "request_id": "request-test-1234",
        "phone": "not-a-real-phone",
        "nested": {"authorization": "Bearer no-real-token", "safe": "ok"},
        "provider_credentials": "must-not-leak",
    }
    redacted = redact_mapping(payload)
    assert redacted["request_id"] == "request-test-1234"
    assert redacted["phone"] == "[REDACTED]"
    assert redacted["nested"]["authorization"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "ok"
    assert redacted["provider_credentials"] == "[REDACTED]"
