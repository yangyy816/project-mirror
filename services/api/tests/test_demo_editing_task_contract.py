from __future__ import annotations

from dataclasses import replace

import pytest

from mirror_api.demo_editing_task_contract import DemoEditingTaskMessage


def _message() -> DemoEditingTaskMessage:
    return DemoEditingTaskMessage(
        demo_actor_id="a" * 32,
        job_id="b" * 32,
        operation="edit_plan.execute",
        request_id="request-1234",
    )


def test_editing_task_message_round_trip_is_exact() -> None:
    message = _message()
    assert DemoEditingTaskMessage.from_message(message.to_message()) == message


@pytest.mark.parametrize(
    "message",
    [
        replace(_message(), demo_actor_id="not-an-id"),
        replace(_message(), job_id="0" * 31),
        replace(_message(), operation="tool.verify"),  # type: ignore[arg-type]
        replace(_message(), request_id="short"),
        replace(_message(), request_id="request\nunsafe"),
        replace(_message(), schema_version="future"),
    ],
)
def test_editing_task_message_rejects_invalid_authority(
    message: DemoEditingTaskMessage,
) -> None:
    with pytest.raises(ValueError):
        message.validate()


def test_editing_task_message_rejects_extra_or_non_string_fields() -> None:
    payload: dict[str, object] = _message().to_message()
    payload["private_locator"] = "forbidden"
    with pytest.raises(ValueError):
        DemoEditingTaskMessage.from_message(payload)  # type: ignore[arg-type]

    payload = _message().to_message()
    payload["job_id"] = 1
    with pytest.raises(ValueError):
        DemoEditingTaskMessage.from_message(payload)  # type: ignore[arg-type]
