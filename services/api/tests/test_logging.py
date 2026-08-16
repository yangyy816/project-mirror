import json
import logging

import pytest

from mirror_api.logging import OperationalEvent, emit_operational_event, redact_mapping


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


def test_operational_event_is_canonical_allowlisted_and_payload_free(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("mirror.tests.operational")
    marker = "must-never-appear"
    with caplog.at_level(logging.INFO, logger=logger.name):
        emit_operational_event(
            logger,
            OperationalEvent(
                event_name="job.dispatch.completed",
                outcome="succeeded",
                request_id="request-test-1234",
                operation="asset_ingestion",
                duration_ms=12,
                job_id="job-test-12345678",
            ),
        )
    payload = json.loads(caplog.records[-1].message)
    assert payload == {
        "duration_ms": 12,
        "event_name": "job.dispatch.completed",
        "job_id": "job-test-12345678",
        "operation": "asset_ingestion",
        "outcome": "succeeded",
        "request_id": "request-test-1234",
    }
    assert marker not in caplog.text
    assert not ({"phone", "token", "credential", "signed_url", "object_key"} & payload.keys())


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"event_name": "Invalid Event"}, "event name"),
        ({"outcome": "unknown"}, "outcome"),
        ({"request_id": "short"}, "request correlation"),
        ({"job_id": "contains/slash"}, "job correlation"),
        ({"route_template": "/unsafe?token=value"}, "route template"),
    ],
)
def test_operational_event_rejects_unbounded_or_sensitive_shapes(
    override: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "event_name": "http.request.completed",
        "outcome": "succeeded",
        "request_id": "request-test-1234",
        "operation": "http_request",
    }
    values.update(override)
    with pytest.raises(ValueError, match=message):
        OperationalEvent(**values)  # type: ignore[arg-type]
