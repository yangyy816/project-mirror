from __future__ import annotations

import base64
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from mirror_api.synthetic_dataset import legacy_overlay_bridge as bridge_module
from mirror_api.synthetic_dataset import private_execution_overlay as legacy
from mirror_api.synthetic_dataset.legacy_overlay_bridge import (
    LegacyBridgeError,
    create_or_verify_cal_req_004_bridge_from_legacy_receipt,
    verify_bridge_for_cal_req_004,
)
from mirror_api.synthetic_dataset.post_registration_request_reference import build_request_reference
from mirror_api.synthetic_dataset.private_post_registration_verifier_v2 import (
    append_v2_transition,
    initialize_from_legacy_bridge,
    recover_v2_chain_with_bridge,
    resource_profile,
)

LEGACY_OVERLAY_SHA256 = "1487d8d30f7354f7353b4784231ce5ca5b2a83ecdfd4356a152dcde3f5a09a4a"


@dataclass(frozen=True, slots=True)
class _LegacyFixture:
    bridge_path: Path
    receipt_path: Path
    controller_sha256: str
    receipt_sha256: str
    state_sha256: str
    registration_receipt_sha256: str
    output_id: str
    action_id: str
    registered_output_sha256: str


def _verifier_sha256() -> str:
    return legacy.sha256_file(
        Path(__file__).parents[1]
        / "src"
        / "mirror_api"
        / "synthetic_dataset"
        / "private_post_registration_verifier_v2.py"
    )


def _legacy_fixture(tmp_path: Path) -> _LegacyFixture:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").write_text("gitdir: synthetic-test-worktree\n", encoding="utf-8")
    (project / ".gitignore").write_text(".private-handoff/\n", encoding="utf-8")
    parent = project / ".private-handoff"
    parent.mkdir()
    root = parent / "overlay-cal-req-004"
    controller_sha256 = legacy.sha256_file(Path(legacy.__file__))
    initial = legacy.initialize_overlay(
        allowed_parent=parent,
        root=root,
        overlay_output_id="OVERLAY-CAL-REQ-004",
        controller_sha256=controller_sha256,
        binding=legacy.GenesisBinding(
            genesis_output_id="GENESIS-CAL-REQ-004",
            genesis_bootstrap_sha256="1" * 64,
            genesis_receipt_sha256="2" * 64,
            private_registry_sha256="3" * 64,
            generation_specification_version="generation-v1",
            generation_specification_sha256="4" * 64,
            assignment_manifest_version="assignment-v1",
            assignment_manifest_sha256="5" * 64,
            prompt_template_version="prompt-v1",
            prompt_template_sha256="6" * 64,
            policy_digest="7" * 64,
            request_call_count=3,
            requested_output_count=3,
            returned_output_count=3,
            raw_output_count=3,
            formal_calls_remaining=29,
            formal_raw_capacity_remaining=29,
            global_native_output_capacity_remaining=60,
            global_native_output_consumed=4,
            next_unused_ordinal="CAL-REQ-004",
        ),
        timestamp="2026-09-01T00:00:00Z",
    )
    action_id = "ACTION-CAL-REQ-004"
    output_id = "OUTPUT-CAL-REQ-004"
    prepared = legacy.prepare_dispatch(
        receipt_path=initial.receipt_path,
        expected_controller_sha256=controller_sha256,
        ordinal="CAL-REQ-004",
        action_id=action_id,
        expected_output_opaque_id=output_id,
        timestamp="2026-09-01T00:00:01Z",
    )
    consumed = legacy.consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=controller_sha256,
        action_id=action_id,
        timestamp="2026-09-01T00:00:02Z",
    )
    data_url = "data:image/png;base64," + base64.b64encode(
        b"\x89PNG\r\n\x1a\nprocedural-non-human-fixture"
    ).decode("ascii")
    returned = legacy.record_output_returned(
        receipt_path=consumed.receipt_path,
        expected_controller_sha256=controller_sha256,
        action_id=action_id,
        timestamp="2026-09-01T00:00:03Z",
        returned_output_count=1,
        exact_generated_artifact_receipt=data_url,
    )
    registered = legacy.register_imagegen_data_url_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=controller_sha256,
        action_id=action_id,
        project_worktree_root=project,
        imagegen_data_url=data_url,
        timestamp="2026-09-01T00:00:04Z",
    )
    verified = legacy.verify_overlay(
        registered.receipt_path, expected_controller_sha256=controller_sha256
    )
    receipt = cast(dict[str, Any], verified["receipt"])
    state = cast(dict[str, Any], verified["state"])
    registration = cast(dict[str, str], state["output_registration"])
    registration_evidence = legacy.verify_registration_before_decode(
        registered.receipt_path,
        expected_controller_sha256=controller_sha256,
        project_worktree_root=project,
    )
    control = parent / "legacy-bridge-control"
    control.mkdir()
    return _LegacyFixture(
        bridge_path=control / "bridge.json",
        receipt_path=registered.receipt_path,
        controller_sha256=controller_sha256,
        receipt_sha256=legacy.sha256_file(registered.receipt_path),
        state_sha256=cast(str, receipt["state_sha256"]),
        registration_receipt_sha256=registration["registration_receipt_sha256"],
        output_id=output_id,
        action_id=action_id,
        registered_output_sha256=cast(str, registration_evidence["source_sha256"]),
    )


def _bridge(fixture: _LegacyFixture) -> tuple[Any, str]:
    verifier_sha256 = _verifier_sha256()
    bridge = create_or_verify_cal_req_004_bridge_from_legacy_receipt(
        bridge_path=fixture.bridge_path,
        legacy_receipt_path=fixture.receipt_path,
        expected_legacy_controller_sha256=fixture.controller_sha256,
        expected_legacy_receipt_sha256=fixture.receipt_sha256,
        expected_legacy_state_sha256=fixture.state_sha256,
        expected_registration_receipt_sha256=fixture.registration_receipt_sha256,
        expected_output_id=fixture.output_id,
        expected_action_id=fixture.action_id,
        verification_timestamp="2026-09-01T00:01:00Z",
        expected_new_verifier_sha256=verifier_sha256,
        policy_version="policy-v1",
        policy_sha256="8" * 64,
        registered_output_sha256=fixture.registered_output_sha256,
    )
    return bridge, verifier_sha256


def _request_reference() -> Any:
    return build_request_reference(
        ordinal="CAL-REQ-004",
        action_id="ACTION-CAL-REQ-004",
        expected_output_id="OUTPUT-CAL-REQ-004",
        source_output_sha256="1" * 64,
        registration_receipt_sha256="2" * 64,
        legacy_bridge_sha256="3" * 64,
        policy_version="policy-v1",
        policy_sha256="4" * 64,
        runtime_sha256="5" * 64,
        model_sha256="6" * 64,
    )


def test_legacy_overlay_controller_is_byte_exact() -> None:
    assert legacy.sha256_file(Path(legacy.__file__)) == LEGACY_OVERLAY_SHA256


def test_bridge_factory_requires_a_real_verified_legacy_receipt(tmp_path: Path) -> None:
    fixture = _legacy_fixture(tmp_path)
    bridge, verifier_sha256 = _bridge(fixture)
    verified = verify_bridge_for_cal_req_004(
        bridge_path=fixture.bridge_path,
        expected_bridge_sha256=bridge.sha256,
        expected_legacy_controller_sha256=fixture.controller_sha256,
        expected_legacy_receipt_sha256=fixture.receipt_sha256,
    )
    assert verified["new_verifier_sha256"] == verifier_sha256
    bridge_source = Path(bridge_module.__file__).read_text(encoding="utf-8")
    assert "LegacyOverlayAttestation" not in bridge_source
    assert "def _create_or_verify_cal_req_004_bridge" not in bridge_source


def test_bridge_factory_rejects_a_tampered_legacy_receipt(tmp_path: Path) -> None:
    fixture = _legacy_fixture(tmp_path)
    payload = legacy._read_json(fixture.receipt_path)
    payload["phase"] = "READY"
    fixture.receipt_path.write_bytes(legacy.canonical_json_bytes(payload))
    with pytest.raises(LegacyBridgeError, match="LEGACY_RECEIPT_VERIFICATION_FAILED"):
        _bridge(fixture)


def test_bridge_rejects_reuse_with_another_controller(tmp_path: Path) -> None:
    fixture = _legacy_fixture(tmp_path)
    bridge, _verifier_sha256 = _bridge(fixture)
    with pytest.raises(LegacyBridgeError, match="BINDING_INVALID"):
        verify_bridge_for_cal_req_004(
            bridge_path=fixture.bridge_path,
            expected_bridge_sha256=bridge.sha256,
            expected_legacy_controller_sha256="a" * 64,
            expected_legacy_receipt_sha256=fixture.receipt_sha256,
        )


def test_v2_chain_is_bridge_bound_and_fresh_process_recoverable(tmp_path: Path) -> None:
    fixture = _legacy_fixture(tmp_path)
    bridge, verifier_sha256 = _bridge(fixture)
    root = fixture.bridge_path.parent / "post-registration-v2-cal-req-004"
    entry = initialize_from_legacy_bridge(
        root=root,
        bridge_path=fixture.bridge_path,
        expected_bridge_sha256=bridge.sha256,
        expected_legacy_controller_sha256=fixture.controller_sha256,
        expected_legacy_receipt_sha256=fixture.receipt_sha256,
        expected_verifier_sha256=verifier_sha256,
        timestamp="2026-09-01T00:02:00Z",
    )
    bound = append_v2_transition(
        handle=entry,
        expected_verifier_sha256=verifier_sha256,
        request_reference=_request_reference(),
        timestamp="2026-09-01T00:03:00Z",
    )
    recovered = recover_v2_chain_with_bridge(
        handle=bound,
        bridge_path=fixture.bridge_path,
        expected_verifier_sha256=verifier_sha256,
    )
    assert cast(dict[str, Any], recovered["state"])["phase"] == "POST_REGISTRATION_ATTEMPT_BOUND"
    code = (
        "from pathlib import Path\n"
        "from mirror_api.synthetic_dataset.private_post_registration_verifier_v2 import (\n"
        " PostRegistrationVerifierV2Handle, recover_v2_chain_with_bridge\n)\n"
        f"h=PostRegistrationVerifierV2Handle(Path({str(bound.receipt_path)!r}),{bound.receipt_sha256!r},{bound.state_sha256!r})\n"
        f"recover_v2_chain_with_bridge(handle=h,bridge_path=Path({str(fixture.bridge_path)!r}),expected_verifier_sha256={verifier_sha256!r})\n"
    )
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_v2_transition_has_one_concurrent_winner(tmp_path: Path) -> None:
    fixture = _legacy_fixture(tmp_path)
    bridge, verifier_sha256 = _bridge(fixture)
    entry = initialize_from_legacy_bridge(
        root=fixture.bridge_path.parent / "post-registration-v2-cal-req-004",
        bridge_path=fixture.bridge_path,
        expected_bridge_sha256=bridge.sha256,
        expected_legacy_controller_sha256=fixture.controller_sha256,
        expected_legacy_receipt_sha256=fixture.receipt_sha256,
        expected_verifier_sha256=verifier_sha256,
        timestamp="2026-09-01T00:02:00Z",
    )

    def transition() -> str:
        return append_v2_transition(
            handle=entry,
            expected_verifier_sha256=verifier_sha256,
            request_reference=_request_reference(),
            timestamp="2026-09-01T00:03:00Z",
        ).receipt_sha256

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert len(set(executor.map(lambda _index: transition(), range(2)))) == 1
    cache_size = resource_profile()["verified_tip_cache_size"]
    assert isinstance(cache_size, int) and cache_size <= 32


def test_v2_rejects_tampered_bridge(tmp_path: Path) -> None:
    fixture = _legacy_fixture(tmp_path)
    bridge, verifier_sha256 = _bridge(fixture)
    payload = legacy._read_json(fixture.bridge_path)
    payload["phase"] = "READY"
    fixture.bridge_path.write_bytes(legacy.canonical_json_bytes(payload))
    with pytest.raises(LegacyBridgeError, match="DIGEST_MISMATCH"):
        verify_bridge_for_cal_req_004(
            bridge_path=fixture.bridge_path,
            expected_bridge_sha256=bridge.sha256,
            expected_legacy_controller_sha256=fixture.controller_sha256,
            expected_legacy_receipt_sha256=fixture.receipt_sha256,
        )
    assert verifier_sha256


def test_future_ordinal_is_rejected_by_request_reference() -> None:
    with pytest.raises(Exception, match="AUTHORITY_INVALID"):
        build_request_reference(
            ordinal="CAL-REQ-005",
            action_id="ACTION-CAL-REQ-005",
            expected_output_id="OUTPUT-CAL-REQ-005",
            source_output_sha256="1" * 64,
            registration_receipt_sha256="2" * 64,
            legacy_bridge_sha256="3" * 64,
            policy_version="policy-v1",
            policy_sha256="4" * 64,
            runtime_sha256="5" * 64,
            model_sha256="6" * 64,
        )
