from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mirror_api.synthetic_dataset import private_execution_overlay as legacy
from mirror_api.synthetic_dataset.legacy_overlay_bridge import (
    LegacyBridgeError,
    create_or_verify_cal_req_004_bridge,
    verify_bridge_for_cal_req_004,
)
from mirror_api.synthetic_dataset.legacy_overlay_verifier import (
    LEGACY_ATTESTATION_SCHEMA,
    LegacyOverlayAttestation,
)
from mirror_api.synthetic_dataset.post_registration_repeatability import (
    RepeatabilityAggregationError,
    RepeatabilityRecord,
    aggregate_repeatability,
)
from mirror_api.synthetic_dataset.post_registration_request_reference import build_request_reference
from mirror_api.synthetic_dataset.private_post_registration_verifier_v2 import (
    PostRegistrationVerifierV2Error,
    append_v2_transition,
    initialize_from_legacy_bridge,
    recover_v2_chain,
    recover_v2_chain_with_bridge,
    resource_profile,
    verify_v2_entry,
)

LEGACY_OVERLAY_SHA256 = "1487d8d30f7354f7353b4784231ce5ca5b2a83ecdfd4356a152dcde3f5a09a4a"


def _verifier_sha256() -> str:
    return legacy.sha256_file(
        Path(__file__).parents[1]
        / "src"
        / "mirror_api"
        / "synthetic_dataset"
        / "private_post_registration_verifier_v2.py"
    )


def _attestation() -> LegacyOverlayAttestation:
    payload: dict[str, object] = {
        "schema_version": LEGACY_ATTESTATION_SCHEMA,
        "verifier_version": "p2-m5-cal-req-004-legacy-overlay-verifier-v1",
        "legacy_controller_sha256": "a" * 64,
        "legacy_receipt_sha256": "b" * 64,
        "legacy_state_sha256": "c" * 64,
        "request_ordinal": "CAL-REQ-004",
        "action_id_sha256": "e" * 64,
        "expected_output_id": "output-r64-0001",
        "resource_ledger_sha256": "d" * 64,
        "phase": "OUTPUT_REGISTERED_PRE_DECODE",
        "sequence": 6,
        "registration_receipt_sha256": "f" * 64,
        "verification_timestamp": "2026-09-01T00:00:00Z",
    }
    return LegacyOverlayAttestation(
        payload=payload, sha256=legacy.sha256_bytes(legacy.canonical_json_bytes(payload))
    )


def test_legacy_overlay_controller_is_byte_exact() -> None:
    assert legacy.sha256_file(Path(legacy.__file__)) == LEGACY_OVERLAY_SHA256


def test_bridge_is_exact_and_rejects_other_ordinal(tmp_path: Path) -> None:
    bridge_path = tmp_path / "bridge.json"
    bridge = create_or_verify_cal_req_004_bridge(
        bridge_path=bridge_path,
        attestation=_attestation(),
        expected_legacy_controller_sha256="a" * 64,
        expected_new_verifier_sha256="e" * 64,
        policy_version="policy-v1",
        policy_sha256="f" * 64,
        registered_output_sha256="0" * 64,
    )
    assert bridge.sha256 == legacy.sha256_file(bridge_path)
    assert (
        verify_bridge_for_cal_req_004(
            bridge_path=bridge_path,
            expected_bridge_sha256=bridge.sha256,
            expected_legacy_controller_sha256="a" * 64,
            expected_legacy_receipt_sha256="b" * 64,
        )["scope"]
        == "CAL_REQ_004_POST_REGISTRATION_ONLY"
    )
    tampered = legacy._read_json(bridge_path)
    tampered["phase"] = "READY"
    bridge_path.write_bytes(legacy.canonical_json_bytes(tampered))
    with pytest.raises(LegacyBridgeError, match="DIGEST_MISMATCH"):
        verify_bridge_for_cal_req_004(
            bridge_path=bridge_path,
            expected_bridge_sha256=bridge.sha256,
            expected_legacy_controller_sha256="a" * 64,
            expected_legacy_receipt_sha256="b" * 64,
        )


def test_bridge_rejects_legacy_attestation_extra_field(tmp_path: Path) -> None:
    payload = dict(_attestation().payload)
    payload["unexpected"] = "not-allowed"
    attestation = LegacyOverlayAttestation(
        payload=payload, sha256=legacy.sha256_bytes(legacy.canonical_json_bytes(payload))
    )
    with pytest.raises(LegacyBridgeError, match="ATTESTATION_BINDING_INVALID"):
        create_or_verify_cal_req_004_bridge(
            bridge_path=tmp_path / "bridge.json",
            attestation=attestation,
            expected_legacy_controller_sha256="a" * 64,
            expected_new_verifier_sha256="e" * 64,
            policy_version="policy-v1",
            policy_sha256="f" * 64,
            registered_output_sha256="0" * 64,
        )


def test_v2_entry_rejects_wrong_verifier_pin(tmp_path: Path) -> None:
    bridge_path = tmp_path / "bridge.json"
    bridge = create_or_verify_cal_req_004_bridge(
        bridge_path=bridge_path,
        attestation=_attestation(),
        expected_legacy_controller_sha256="a" * 64,
        expected_new_verifier_sha256=_verifier_sha256(),
        policy_version="policy-v1",
        policy_sha256="f" * 64,
        registered_output_sha256="0" * 64,
    )
    verifier_sha = legacy.sha256_file(
        Path(__file__).parents[1]
        / "src"
        / "mirror_api"
        / "synthetic_dataset"
        / "private_post_registration_verifier_v2.py"
    )
    root_parent = tmp_path / ".private-handoff"
    root_parent.mkdir()
    control_root = root_parent / "legacy-bridge-control"
    control_root.mkdir()
    handle = initialize_from_legacy_bridge(
        root=control_root / "post-registration-v2-cal-req-004",
        bridge_path=bridge_path,
        expected_bridge_sha256=bridge.sha256,
        expected_legacy_controller_sha256="a" * 64,
        expected_legacy_receipt_sha256="b" * 64,
        expected_verifier_sha256=verifier_sha,
        timestamp="2026-09-01T00:00:00Z",
    )
    with pytest.raises(PostRegistrationVerifierV2Error, match="ENTRY_BINDING_INVALID"):
        verify_v2_entry(handle=handle, expected_verifier_sha256="e" * 64)


def test_v2_entry_concurrent_initialization_has_one_receipt(tmp_path: Path) -> None:
    bridge_path = tmp_path / "bridge.json"
    bridge = create_or_verify_cal_req_004_bridge(
        bridge_path=bridge_path,
        attestation=_attestation(),
        expected_legacy_controller_sha256="a" * 64,
        expected_new_verifier_sha256=_verifier_sha256(),
        policy_version="policy-v1",
        policy_sha256="f" * 64,
        registered_output_sha256="0" * 64,
    )
    verifier_path = (
        Path(__file__).parents[1]
        / "src"
        / "mirror_api"
        / "synthetic_dataset"
        / "private_post_registration_verifier_v2.py"
    )
    verifier_sha = legacy.sha256_file(verifier_path)
    parent = tmp_path / ".private-handoff"
    parent.mkdir()
    control_root = parent / "legacy-bridge-control"
    control_root.mkdir()

    def initialize() -> str:
        return initialize_from_legacy_bridge(
            root=control_root / "post-registration-v2-cal-req-004",
            bridge_path=bridge_path,
            expected_bridge_sha256=bridge.sha256,
            expected_legacy_controller_sha256="a" * 64,
            expected_legacy_receipt_sha256="b" * 64,
            expected_verifier_sha256=verifier_sha,
            timestamp="2026-09-01T00:00:00Z",
        ).receipt_sha256

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert set(executor.map(lambda _index: initialize(), range(2))) == {initialize()}


def test_v2_entry_is_fresh_process_verifiable(tmp_path: Path) -> None:
    bridge_path = tmp_path / "bridge.json"
    bridge = create_or_verify_cal_req_004_bridge(
        bridge_path=bridge_path,
        attestation=_attestation(),
        expected_legacy_controller_sha256="a" * 64,
        expected_new_verifier_sha256=_verifier_sha256(),
        policy_version="policy-v1",
        policy_sha256="f" * 64,
        registered_output_sha256="0" * 64,
    )
    verifier_path = (
        Path(__file__).parents[1]
        / "src"
        / "mirror_api"
        / "synthetic_dataset"
        / "private_post_registration_verifier_v2.py"
    )
    verifier_sha = legacy.sha256_file(verifier_path)
    parent = tmp_path / ".private-handoff"
    parent.mkdir()
    control_root = parent / "legacy-bridge-control"
    control_root.mkdir()
    handle = initialize_from_legacy_bridge(
        root=control_root / "post-registration-v2-cal-req-004",
        bridge_path=bridge_path,
        expected_bridge_sha256=bridge.sha256,
        expected_legacy_controller_sha256="a" * 64,
        expected_legacy_receipt_sha256="b" * 64,
        expected_verifier_sha256=verifier_sha,
        timestamp="2026-09-01T00:00:00Z",
    )
    code = (
        "from pathlib import Path\n"
        "from mirror_api.synthetic_dataset.private_post_registration_verifier_v2 import (\n"
        "    PostRegistrationVerifierV2Handle, verify_v2_entry\n"
        ")\n"
        f"h=PostRegistrationVerifierV2Handle(\nPath({str(handle.receipt_path)!r}),\n"
        f"{handle.receipt_sha256!r},\n{handle.state_sha256!r})\n"
        f"verify_v2_entry(handle=h, expected_verifier_sha256={verifier_sha!r})\n"
    )
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
        },
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_request_reference_changes_for_each_authority_edge() -> None:
    base = {
        "ordinal": "CAL-REQ-004",
        "action_id": "action-r64-0001",
        "expected_output_id": "output-r64-0001",
        "source_output_sha256": "1" * 64,
        "registration_receipt_sha256": "2" * 64,
        "legacy_bridge_sha256": "3" * 64,
        "policy_version": "policy-v1",
        "policy_sha256": "4" * 64,
        "runtime_sha256": "5" * 64,
        "model_sha256": "6" * 64,
    }
    reference = build_request_reference(**base)
    changed = {**base, "runtime_sha256": "7" * 64}
    assert build_request_reference(**changed).sha256 != reference.sha256


def test_repeatability_rejects_mixed_or_failed_authority() -> None:
    record = RepeatabilityRecord(
        "1" * 64, "2" * 64, "3" * 64, "4" * 64, "5" * 64, "passed", (0.1, 0.2)
    )
    assert aggregate_repeatability((record, record)) == (0.0, 0.0)
    with pytest.raises(RepeatabilityAggregationError, match="AUTHORITY_MISMATCH"):
        aggregate_repeatability(
            (
                record,
                RepeatabilityRecord(
                    "1" * 64, "2" * 64, "6" * 64, "4" * 64, "5" * 64, "passed", (0.1, 0.2)
                ),
            )
        )


def test_v2_twenty_operation_replay_is_stable(tmp_path: Path) -> None:
    bridge_path = tmp_path / "bridge.json"
    bridge = create_or_verify_cal_req_004_bridge(
        bridge_path=bridge_path,
        attestation=_attestation(),
        expected_legacy_controller_sha256="a" * 64,
        expected_new_verifier_sha256=_verifier_sha256(),
        policy_version="policy-v1",
        policy_sha256="f" * 64,
        registered_output_sha256="0" * 64,
    )
    verifier_path = (
        Path(__file__).parents[1]
        / "src"
        / "mirror_api"
        / "synthetic_dataset"
        / "private_post_registration_verifier_v2.py"
    )
    verifier_sha = legacy.sha256_file(verifier_path)
    parent = tmp_path / ".private-handoff"
    parent.mkdir()
    control_root = parent / "legacy-bridge-control"
    control_root.mkdir()
    receipts = {
        initialize_from_legacy_bridge(
            root=control_root / "post-registration-v2-cal-req-004",
            bridge_path=bridge_path,
            expected_bridge_sha256=bridge.sha256,
            expected_legacy_controller_sha256="a" * 64,
            expected_legacy_receipt_sha256="b" * 64,
            expected_verifier_sha256=verifier_sha,
            timestamp="2026-09-01T00:00:00Z",
        ).receipt_sha256
        for _ in range(20)
    }
    assert len(receipts) == 1
    record = RepeatabilityRecord(
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
        "passed",
        (0.1, 0.2),
    )
    with pytest.raises(RepeatabilityAggregationError, match="INCOMPLETE_OR_FAILED"):
        aggregate_repeatability(
            (
                record,
                RepeatabilityRecord(
                    "1" * 64, "2" * 64, "3" * 64, "4" * 64, "5" * 64, "failed", (0.1, 0.2)
                ),
            )
        )


def _v2_entry(tmp_path: Path):  # type: ignore[no-untyped-def]
    bridge_path = tmp_path / "bridge.json"
    bridge = create_or_verify_cal_req_004_bridge(
        bridge_path=bridge_path,
        attestation=_attestation(),
        expected_legacy_controller_sha256="a" * 64,
        expected_new_verifier_sha256=_verifier_sha256(),
        policy_version="policy-v1",
        policy_sha256="f" * 64,
        registered_output_sha256="0" * 64,
    )
    verifier_path = (
        Path(__file__).parents[1]
        / "src"
        / "mirror_api"
        / "synthetic_dataset"
        / "private_post_registration_verifier_v2.py"
    )
    verifier_sha = legacy.sha256_file(verifier_path)
    parent = tmp_path / ".private-handoff"
    parent.mkdir()
    control_root = parent / "legacy-bridge-control"
    control_root.mkdir()
    handle = initialize_from_legacy_bridge(
        root=control_root / "post-registration-v2-cal-req-004",
        bridge_path=bridge_path,
        expected_bridge_sha256=bridge.sha256,
        expected_legacy_controller_sha256="a" * 64,
        expected_legacy_receipt_sha256="b" * 64,
        expected_verifier_sha256=verifier_sha,
        timestamp="2026-09-01T00:00:00Z",
    )
    return handle, verifier_sha


def _request_reference():  # type: ignore[no-untyped-def]
    return build_request_reference(
        ordinal="CAL-REQ-004",
        action_id="action-r64-0001",
        expected_output_id="output-r64-0001",
        source_output_sha256="1" * 64,
        registration_receipt_sha256="2" * 64,
        legacy_bridge_sha256="3" * 64,
        policy_version="policy-v1",
        policy_sha256="4" * 64,
        runtime_sha256="5" * 64,
        model_sha256="6" * 64,
    )


def test_v2_transition_is_append_only_recoverable_and_stale_safe(tmp_path: Path) -> None:
    entry, verifier_sha = _v2_entry(tmp_path)
    bound = append_v2_transition(
        handle=entry,
        expected_verifier_sha256=verifier_sha,
        request_reference=_request_reference(),
        timestamp="2026-09-01T00:01:00Z",
    )
    recovered = recover_v2_chain(handle=bound, expected_verifier_sha256=verifier_sha)
    assert recovered["state"]["phase"] == "POST_REGISTRATION_ATTEMPT_BOUND"
    assert (
        recover_v2_chain_with_bridge(
            handle=bound,
            bridge_path=tmp_path / "bridge.json",
            expected_verifier_sha256=verifier_sha,
        )["state"]["sequence"]
        == 1
    )
    with pytest.raises(PostRegistrationVerifierV2Error, match="BRANCH_FORK"):
        recover_v2_chain(handle=entry, expected_verifier_sha256=verifier_sha)
    assert (
        append_v2_transition(
            handle=entry,
            expected_verifier_sha256=verifier_sha,
            request_reference=_request_reference(),
            timestamp="2026-09-01T00:02:00Z",
        ).receipt_sha256
        == bound.receipt_sha256
    )


def test_v2_transition_has_exactly_one_concurrent_winner(tmp_path: Path) -> None:
    entry, verifier_sha = _v2_entry(tmp_path)

    def transition() -> str:
        return append_v2_transition(
            handle=entry,
            expected_verifier_sha256=verifier_sha,
            request_reference=_request_reference(),
            timestamp="2026-09-01T00:01:00Z",
        ).receipt_sha256

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: transition(), range(2)))
    assert results[0] == results[1]


def test_v2_transition_has_one_cross_process_winner(tmp_path: Path) -> None:
    entry, verifier_sha = _v2_entry(tmp_path)
    reference = _request_reference()
    code = (
        "from pathlib import Path\n"
        "from mirror_api.synthetic_dataset.private_post_registration_verifier_v2 import (\n"
        "    PostRegistrationVerifierV2Handle, append_v2_transition\n"
        ")\n"
        "from mirror_api.synthetic_dataset.post_registration_request_reference import (\n"
        "    build_request_reference\n"
        ")\n"
        f"handle=PostRegistrationVerifierV2Handle(Path({str(entry.receipt_path)!r}),"
        f"{entry.receipt_sha256!r},{entry.state_sha256!r})\n"
        "reference=build_request_reference(ordinal='CAL-REQ-004',"
        "action_id='action-r64-0001',expected_output_id='output-r64-0001',"
        "source_output_sha256='1'*64,registration_receipt_sha256='2'*64,"
        "legacy_bridge_sha256='3'*64,policy_version='policy-v1',policy_sha256='4'*64,"
        "runtime_sha256='5'*64,model_sha256='6'*64)\n"
        f"print(append_v2_transition(handle=handle,expected_verifier_sha256={verifier_sha!r},"
        "request_reference=reference,timestamp='2026-09-01T00:01:00Z').receipt_sha256)\n"
    )
    environment = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).parents[1] / "src"),
    }

    def invoke() -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [sys.executable, "-c", code],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: invoke(), range(2)))
    assert {result.returncode for result in results} == {0}
    expected = append_v2_transition(
        handle=entry,
        expected_verifier_sha256=verifier_sha,
        request_reference=reference,
        timestamp="2026-09-01T00:01:00Z",
    )
    assert {result.stdout.strip() for result in results} == {expected.receipt_sha256}


def test_v2_recovery_rejects_extra_branch_and_request_reference_mismatch(tmp_path: Path) -> None:
    entry, verifier_sha = _v2_entry(tmp_path)
    bound = append_v2_transition(
        handle=entry,
        expected_verifier_sha256=verifier_sha,
        request_reference=_request_reference(),
        timestamp="2026-09-01T00:01:00Z",
    )
    with pytest.raises(PostRegistrationVerifierV2Error, match="REQUEST_REFERENCE"):
        append_v2_transition(
            handle=entry,
            expected_verifier_sha256=verifier_sha,
            request_reference=build_request_reference(
                ordinal="CAL-REQ-004",
                action_id="action-r64-other",
                expected_output_id="output-r64-0001",
                source_output_sha256="1" * 64,
                registration_receipt_sha256="2" * 64,
                legacy_bridge_sha256="3" * 64,
                policy_version="policy-v1",
                policy_sha256="4" * 64,
                runtime_sha256="5" * 64,
                model_sha256="6" * 64,
            ),
            timestamp="2026-09-01T00:02:00Z",
        )
    state = legacy._read_json(bound.receipt_path)["state"]
    forged = {"receipt": {}, "state": state}
    (bound.receipt_path.parent / "receipt-000002.json").write_bytes(
        legacy.canonical_json_bytes(forged)
    )
    with pytest.raises(PostRegistrationVerifierV2Error, match="BRANCH_FORK"):
        recover_v2_chain(handle=bound, expected_verifier_sha256=verifier_sha)


def test_v2_resource_profile_is_bounded_over_twenty_verifications(tmp_path: Path) -> None:
    entry, verifier_sha = _v2_entry(tmp_path)
    bound = append_v2_transition(
        handle=entry,
        expected_verifier_sha256=verifier_sha,
        request_reference=_request_reference(),
        timestamp="2026-09-01T00:01:00Z",
    )
    for _ in range(20):
        assert (
            recover_v2_chain(handle=bound, expected_verifier_sha256=verifier_sha)["state"][
                "sequence"
            ]
            == 1
        )
    profile = resource_profile()
    assert profile["verified_tip_cache_size"] <= 32
    assert profile["windows_binding_initializations"] <= 1
