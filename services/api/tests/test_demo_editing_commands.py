"""Narrow command-boundary tests that require no runtime or Provider."""

from __future__ import annotations

import pytest

from mirror_api.demo_editing_commands import (
    CreateDemoEditingSession,
    DemoEditingCommandInputError,
    ExecuteDemoEditPlan,
    RestoreDemoImageVersion,
)

_ID = "a" * 32
_DIGEST = "b" * 64
_REQUEST_ID = "request-01"
_KEY = "idempotency-key-01"


def test_editing_session_requires_exactly_one_source_selector() -> None:
    with pytest.raises(DemoEditingCommandInputError, match="exactly one"):
        CreateDemoEditingSession(
            demo_actor_id=_ID,
            demo_session_id=_ID,
            source_asset_id=_ID,
            source_image_version_id=_ID,
            idempotency_key=_KEY,
            request_id=_REQUEST_ID,
        ).validate()

    with pytest.raises(DemoEditingCommandInputError, match="exactly one"):
        CreateDemoEditingSession(
            demo_actor_id=_ID,
            demo_session_id=_ID,
            idempotency_key=_KEY,
            request_id=_REQUEST_ID,
        ).validate()


def test_execute_requires_quantized_plan_digest_and_known_mode() -> None:
    with pytest.raises(DemoEditingCommandInputError, match="SHA-256"):
        ExecuteDemoEditPlan(
            demo_actor_id=_ID,
            edit_plan_id=_ID,
            execution_mode="DETERMINISTIC_RASTER",
            expected_plan_digest="not-a-digest",
            idempotency_key=_KEY,
            request_id=_REQUEST_ID,
        ).validate()


def test_restore_requires_optimistic_current_digest() -> None:
    with pytest.raises(DemoEditingCommandInputError, match="SHA-256"):
        RestoreDemoImageVersion(
            demo_actor_id=_ID,
            target_image_version_id=_ID,
            expected_current_image_version_id=_ID,
            expected_current_image_version_digest="bad",
            idempotency_key=_KEY,
            request_id=_REQUEST_ID,
        ).validate()


def test_editing_session_source_asset_form_is_valid() -> None:
    CreateDemoEditingSession(
        demo_actor_id=_ID,
        demo_session_id=_ID,
        source_asset_id=_ID,
        idempotency_key=_KEY,
        request_id=_REQUEST_ID,
    ).validate()


def test_editing_session_canonical_source_selector_is_explicit_and_exclusive() -> None:
    CreateDemoEditingSession(
        demo_actor_id=_ID,
        demo_session_id=_ID,
        source_selector="SESSION_CANONICAL_ASSET",
        idempotency_key=_KEY,
        request_id=_REQUEST_ID,
    ).validate()

    for source in (
        {"source_asset_id": _ID},
        {"source_image_version_id": _ID},
    ):
        with pytest.raises(DemoEditingCommandInputError, match="forbids explicit"):
            CreateDemoEditingSession(
                demo_actor_id=_ID,
                demo_session_id=_ID,
                source_selector="SESSION_CANONICAL_ASSET",
                idempotency_key=_KEY,
                request_id=_REQUEST_ID,
                **source,
            ).validate()

    with pytest.raises(DemoEditingCommandInputError, match="unsupported"):
        CreateDemoEditingSession(
            demo_actor_id=_ID,
            demo_session_id=_ID,
            source_asset_id=_ID,
            source_selector="UNKNOWN",  # type: ignore[arg-type]
            idempotency_key=_KEY,
            request_id=_REQUEST_ID,
        ).validate()
