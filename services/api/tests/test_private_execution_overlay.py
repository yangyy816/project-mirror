from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from mirror_api.synthetic_dataset.private_execution_overlay import (
    ExecutionOverlayError,
    GenesisBinding,
    consume_dispatch,
    initialize_overlay,
    mark_dispatch_failed,
    mark_registration_failed,
    prepare_dispatch,
    record_output_returned,
    register_output_before_decode,
    render_private_prompt,
    verify_overlay,
    verify_registration_before_decode,
)

CONTROLLER_SHA256 = "a" * 64
POLICY_DIGEST = "7" * 64
TIMESTAMP_0 = "2026-08-29T00:00:00Z"
TIMESTAMP_1 = "2026-08-29T00:00:01Z"
TIMESTAMP_2 = "2026-08-29T00:00:02Z"
TIMESTAMP_3 = "2026-08-29T00:00:03Z"


def _binding() -> GenesisBinding:
    return GenesisBinding(
        genesis_output_id="GENESIS-EPOCH3-0001",
        genesis_bootstrap_sha256="1" * 64,
        genesis_receipt_sha256="2" * 64,
        private_registry_sha256="3" * 64,
        generation_specification_version="generation-v3",
        generation_specification_sha256="4" * 64,
        assignment_manifest_version="assignment-v3",
        assignment_manifest_sha256="5" * 64,
        prompt_template_version="prompt-v3",
        prompt_template_sha256="6" * 64,
        policy_digest=POLICY_DIGEST,
    )


def _initialized(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "overlay-task-owned-0001"
    handle = initialize_overlay(
        allowed_parent=tmp_path,
        root=root,
        overlay_output_id="OVERLAY-EPOCH3-0001",
        controller_sha256=CONTROLLER_SHA256,
        binding=_binding(),
        timestamp=TIMESTAMP_0,
    )
    return root, handle.receipt_path


def _consumed(tmp_path: Path) -> tuple[Path, Path]:
    root, receipt = _initialized(tmp_path)
    prepared = prepare_dispatch(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        ordinal="CAL-REQ-002",
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_1,
    )
    consumed = consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_2,
    )
    return root, consumed.receipt_path


def test_overlay_prepare_and_consume_are_append_only_and_recoverable(tmp_path: Path) -> None:
    root, receipt = _initialized(tmp_path)
    initial = verify_overlay(receipt, expected_controller_sha256=CONTROLLER_SHA256)
    initial_state = cast(dict[str, Any], initial["state"])
    assert initial_state["phase"] == "READY"
    assert initial_state["next_unused_ordinal"] == "CAL-REQ-002"
    assert initial_state["counters"] == {
        "active_calls": 0,
        "admitted_identity_count": 0,
        "failed_call_count": 0,
        "formal_calls_remaining": 31,
        "formal_raw_capacity_remaining": 31,
        "global_native_output_capacity_remaining": 62,
        "global_native_output_consumed": 2,
        "raw_output_count": 1,
        "rejected_output_count": 0,
        "request_call_count": 1,
        "requested_output_count": 1,
        "returned_output_count": 1,
    }

    prepared = prepare_dispatch(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        ordinal="CAL-REQ-002",
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_1,
    )
    prepared_state = cast(
        dict[str, Any],
        verify_overlay(
            prepared.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert prepared.sequence == 1
    assert prepared_state["phase"] == "DISPATCH_PREPARED"
    assert prepared_state["counters"] == initial_state["counters"]

    consumed = consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_2,
    )
    consumed_state = cast(
        dict[str, Any],
        verify_overlay(
            consumed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert consumed.sequence == 2
    assert consumed_state["phase"] == "DISPATCH_STARTED_CONSUMED"
    assert consumed_state["next_unused_ordinal"] == "CAL-REQ-003"
    assert consumed_state["counters"]["request_call_count"] == 2
    assert consumed_state["counters"]["requested_output_count"] == 2
    assert consumed_state["counters"]["formal_calls_remaining"] == 30
    assert consumed_state["counters"]["global_native_output_capacity_remaining"] == 61
    assert consumed_state["counters"]["global_native_output_consumed"] == 3
    assert consumed_state["counters"]["active_calls"] == 1
    assert sorted(path.name for path in root.glob("event-*.json")) == [
        "event-000000.json",
        "event-000001.json",
        "event-000002.json",
    ]


def test_output_is_registered_and_receipted_before_any_decode(tmp_path: Path) -> None:
    root, receipt = _consumed(tmp_path)
    returned = record_output_returned(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
    )
    returned_state = cast(
        dict[str, Any],
        verify_overlay(
            returned.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert returned_state["phase"] == "OUTPUT_RETURNED_UNREGISTERED"
    assert returned_state["decode_authorized"] is False
    assert returned_state["counters"]["returned_output_count"] == 2
    assert returned_state["counters"]["raw_output_count"] == 2
    assert returned_state["counters"]["formal_raw_capacity_remaining"] == 30
    assert returned_state["counters"]["active_calls"] == 1

    artifact_root = tmp_path / "generated-artifacts"
    artifact_root.mkdir()
    source = artifact_root / "native-generated-artifact.bin"
    source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"non-human-synthetic-fixture")

    registered = register_output_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        output_opaque_id="OUTPUT-CAL-REQ-002",
        generated_artifact_path=source,
        allowed_generated_artifact_root=artifact_root,
        exact_generated_artifact_receipt="EXACT-TOOL-OUTPUT-HINT-RECEIPT",
        timestamp="2026-08-29T00:00:04Z",
    )
    result = verify_registration_before_decode(
        registered.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
    )
    assert result == {
        "status": "REGISTER_BEFORE_DECODE_PASS",
        "phase": "OUTPUT_REGISTERED_PRE_DECODE",
        "sequence": 4,
        "output_opaque_id": "OUTPUT-CAL-REQ-002",
        "source_sha256": result["source_sha256"],
        "staging_sha256": result["source_sha256"],
        "byte_size": len(source.read_bytes()),
        "media_type": "image/png",
        "magic_byte_class": "PNG_89504E470D0A1A0A",
        "decode_performed": False,
        "dimensions_read": False,
    }
    state = cast(
        dict[str, Any],
        verify_overlay(
            registered.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert state["decode_authorized"] is True
    assert state["counters"]["returned_output_count"] == 2
    assert state["counters"]["raw_output_count"] == 2
    assert state["counters"]["formal_raw_capacity_remaining"] == 30
    assert state["counters"]["active_calls"] == 0

    registration = cast(dict[str, Any], state["output_registration"])
    record = json.loads((root / "records" / registration["record_file"]).read_text())
    assert record["registration_status"] == "COMMITTED"
    assert record["decode_performed"] is False
    assert record["dimensions_read"] is False
    assert "dimensions" not in record
    assert (root / "staging" / "OUTPUT-CAL-REQ-002.raw").read_bytes() == source.read_bytes()


def test_duplicate_dispatch_and_wrong_ordinal_fail_closed(tmp_path: Path) -> None:
    _root, receipt = _initialized(tmp_path)
    with pytest.raises(ExecutionOverlayError, match="ORDINAL_MISMATCH"):
        prepare_dispatch(
            receipt_path=receipt,
            expected_controller_sha256=CONTROLLER_SHA256,
            ordinal="CAL-REQ-003",
            action_id="ACTION-CAL-REQ-003",
            timestamp=TIMESTAMP_1,
        )
    prepared = prepare_dispatch(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        ordinal="CAL-REQ-002",
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_1,
    )
    with pytest.raises(ExecutionOverlayError, match="PREPARE_STATE_INVALID"):
        prepare_dispatch(
            receipt_path=prepared.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            ordinal="CAL-REQ-002",
            action_id="ACTION-CAL-REQ-002-B",
            timestamp=TIMESTAMP_2,
        )
    consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_2,
    )
    with pytest.raises(ExecutionOverlayError, match="CREATE_NEW_TARGET_PREEXISTS"):
        consume_dispatch(
            receipt_path=prepared.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            timestamp=TIMESTAMP_2,
        )


def test_dispatch_failure_is_final_and_preserves_consumed_counters(tmp_path: Path) -> None:
    _root, receipt = _consumed(tmp_path)
    failed = mark_dispatch_failed(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        reason_code="NATIVE_TOOL_FAILED_ZERO_RETRY",
    )
    state = cast(
        dict[str, Any],
        verify_overlay(
            failed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert state["phase"] == "DISPATCH_FAILED_FINAL"
    assert state["hard_stop"] is True
    assert state["decode_authorized"] is False
    assert state["counters"]["request_call_count"] == 2
    assert state["counters"]["formal_calls_remaining"] == 30
    assert state["counters"]["failed_call_count"] == 1
    assert state["counters"]["active_calls"] == 0


def test_registration_failure_after_return_is_a_no_decode_hard_stop(tmp_path: Path) -> None:
    _root, receipt = _consumed(tmp_path)
    returned = record_output_returned(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
    )
    failed = mark_registration_failed(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp="2026-08-29T00:00:04Z",
        reason_code="OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE",
    )
    state = cast(
        dict[str, Any],
        verify_overlay(
            failed.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
        )["state"],
    )
    assert state["phase"] == "OUTPUT_REGISTRATION_FAILED_BEFORE_DECODE"
    assert state["hard_stop"] is True
    assert state["decode_authorized"] is False
    assert state["counters"]["request_call_count"] == 2
    assert state["counters"]["returned_output_count"] == 2
    assert state["counters"]["raw_output_count"] == 2
    assert state["counters"]["active_calls"] == 0


def test_registration_rejects_out_of_scope_paths_and_data_urls(tmp_path: Path) -> None:
    _root, receipt = _consumed(tmp_path)
    returned = record_output_returned(
        receipt_path=receipt,
        expected_controller_sha256=CONTROLLER_SHA256,
        action_id="ACTION-CAL-REQ-002",
        timestamp=TIMESTAMP_3,
        returned_output_count=1,
    )
    allowed_root = tmp_path / "allowed-generated-artifacts"
    allowed_root.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    with pytest.raises(ExecutionOverlayError, match="OUTSIDE_ALLOWED_ROOT"):
        register_output_before_decode(
            receipt_path=returned.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            output_opaque_id="OUTPUT-CAL-REQ-002",
            generated_artifact_path=outside,
            allowed_generated_artifact_root=allowed_root,
            exact_generated_artifact_receipt="EXACT-TOOL-OUTPUT-HINT-RECEIPT",
            timestamp="2026-08-29T00:00:04Z",
        )

    inside = allowed_root / "inside.bin"
    inside.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    with pytest.raises(ExecutionOverlayError, match="RECEIPT_MISSING"):
        register_output_before_decode(
            receipt_path=returned.receipt_path,
            expected_controller_sha256=CONTROLLER_SHA256,
            action_id="ACTION-CAL-REQ-002",
            output_opaque_id="OUTPUT-CAL-REQ-002",
            generated_artifact_path=inside,
            allowed_generated_artifact_root=allowed_root,
            exact_generated_artifact_receipt="data:image/png;base64,ignored",
            timestamp="2026-08-29T00:00:04Z",
        )


def test_hash_chain_detects_prior_event_tampering(tmp_path: Path) -> None:
    root, receipt = _consumed(tmp_path)
    event = root / "event-000000.json"
    event.write_bytes(event.read_bytes() + b" ")
    with pytest.raises(ExecutionOverlayError, match="EVENT_DIGEST_MISMATCH"):
        verify_overlay(receipt, expected_controller_sha256=CONTROLLER_SHA256)


def test_private_prompt_rendering_is_deterministic_and_requires_prohibition() -> None:
    template = {
        "plaintext_export": "PROHIBITED",
        "status": "MATERIALIZED_NOT_RENDERED_NOT_DISPATCHED",
        "policy_digest": POLICY_DIGEST,
        "render_placeholders": [
            "REQUEST_ORDINAL",
            "DECLARED_AGE_BAND",
            "MORPHOLOGY_DESCRIPTOR",
            "STYLE_DESCRIPTOR",
        ],
        "positive_segments": [
            ["synthetic non-real subject", "{DECLARED_AGE_BAND}"],
            ["morphology {MORPHOLOGY_DESCRIPTOR}", "style {STYLE_DESCRIPTOR}"],
        ],
        "negative_segments": [["no real person", "no text"]],
    }
    assignment = {
        "ordinal": "CAL-REQ-002",
        "declared_age_band": "ADULT_20_25",
        "morphology": "UPPER_HIGH",
        "style_family": "GENTLE_SOFT",
        "status": "NOT_CONSUMED",
        "retryable": False,
        "policy_binding": POLICY_DIGEST,
    }
    rendered = render_private_prompt(
        prompt_template=template,
        assignment_entry=assignment,
        ordinal="CAL-REQ-002",
        expected_policy_digest=POLICY_DIGEST,
    )
    assert rendered == (
        "REQUEST_ORDINAL: CAL-REQ-002\n"
        "POSITIVE_CONSTRAINT_GROUPS:\n"
        "1. synthetic non-real subject; ADULT_20_25\n"
        "2. morphology UPPER_HIGH; style GENTLE_SOFT\n"
        "NEGATIVE_CONSTRAINT_GROUPS:\n"
        "1. no real person; no text"
    )
    with pytest.raises(ExecutionOverlayError, match="EXPORT_POLICY_INVALID"):
        render_private_prompt(
            prompt_template={**template, "plaintext_export": "ALLOWED"},
            assignment_entry=assignment,
            ordinal="CAL-REQ-002",
            expected_policy_digest=POLICY_DIGEST,
        )


def test_controller_uses_no_directory_discovery_primitive() -> None:
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "mirror_api"
        / "synthetic_dataset"
        / "private_execution_overlay.py"
    )
    source = module_path.read_text(encoding="utf-8")
    assert ".iterdir(" not in source
    assert ".glob(" not in source
    assert ".rglob(" not in source
    assert "os.walk(" not in source
    assert "import requests" not in source
    assert "import urllib" not in source
    assert "import socket" not in source
    assert "import subprocess" not in source
