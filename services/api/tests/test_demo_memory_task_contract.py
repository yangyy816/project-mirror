from __future__ import annotations

import pytest

from mirror_api.demo_memory_task_contract import (
    DEMO_MEMORY_TASK_SCHEMA,
    DemoMemoryTaskMessage,
)


def test_memory_task_message_is_canonical_and_round_trips() -> None:
    message = DemoMemoryTaskMessage(
        demo_actor_id="a" * 32,
        job_id="b" * 32,
        request_id="memory-request-0001",
    )

    payload = message.to_message()

    assert payload["schema_version"] == DEMO_MEMORY_TASK_SCHEMA
    assert DemoMemoryTaskMessage.from_message(payload) == message
    assert (
        message.payload_digest
        == DemoMemoryTaskMessage(
            demo_actor_id="a" * 32,
            job_id="b" * 32,
            request_id="memory-request-0001",
        ).payload_digest
    )
    assert (
        message.payload_digest
        != DemoMemoryTaskMessage(
            demo_actor_id="a" * 32,
            job_id="b" * 32,
            request_id="memory-request-0002",
        ).payload_digest
    )
    assert len(message.payload_digest) == 64


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "demo_actor_id": "a" * 32,
            "job_id": "b" * 32,
            "request_id": "memory-request-0001",
            "schema_version": "wrong",
        },
    ],
)
def test_memory_task_message_fails_closed_for_wrong_shape(payload: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        DemoMemoryTaskMessage.from_message(payload)
