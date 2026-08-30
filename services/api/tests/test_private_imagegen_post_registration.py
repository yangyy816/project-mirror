from __future__ import annotations

import base64
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from PIL import Image

from mirror_api.providers.base import (
    FaceLandmark,
    FaceLandmarkSet,
    FaceObservation,
    PoseEstimate,
    ProviderCostFact,
    ProviderProvenanceFact,
    ProviderSafetyFact,
    SyntheticVisionResult,
)
from mirror_api.synthetic_dataset import private_execution_overlay as overlay
from mirror_api.synthetic_dataset import private_imagegen_post_registration as post

TIMESTAMP = "2026-08-31T00:00:00Z"


def _png_bytes() -> bytes:
    """A procedural, non-human RGB fixture; it never leaves this process."""
    image = Image.new("RGB", (64, 64), (12, 34, 56))
    try:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        image.close()


def _binding(*, next_unused_ordinal: str = "CAL-REQ-004") -> overlay.GenesisBinding:
    return overlay.GenesisBinding(
        genesis_output_id="GENESIS-CC06-0001",
        genesis_bootstrap_sha256="1" * 64,
        genesis_receipt_sha256="2" * 64,
        private_registry_sha256="3" * 64,
        generation_specification_version="generation-v3",
        generation_specification_sha256="4" * 64,
        assignment_manifest_version="assignment-v3",
        assignment_manifest_sha256="5" * 64,
        prompt_template_version="prompt-v3",
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
        next_unused_ordinal=next_unused_ordinal,
    )


def _pins() -> tuple[str, str]:
    return overlay.sha256_file(Path(overlay.__file__)), overlay.sha256_file(Path(post.__file__))


def _capabilities() -> tuple[post.PrivateVisionCapabilityBinding, ...]:
    return tuple(
        post.PrivateVisionCapabilityBinding(
            capability_id=f"cap-{platform.split('_')[0]}-cc06",
            platform=cast(
                Literal[
                    "linux_x86_64_network_none", "windows_amd64_process_specific_outbound_deny"
                ],
                platform,
            ),
            runtime_sha256=post.RUNTIME_SHA256_BY_PLATFORM[platform],
            model_sha256=post.MODEL_SHA256,
            manifest_version=post.MANIFEST_VERSION,
            manifest_sha256=post.MANIFEST_SHA256,
            qa_policy_version=post.QA_POLICY_VERSION,
            qa_policy_sha256=post.QA_POLICY_SHA256,
            zero_egress_evidence_id=f"egress-{platform.split('_')[0]}-cc06",
            zero_egress_evidence_sha256=("8" if platform.startswith("linux") else "9") * 64,
            approved_scope=post.APPROVED_SCOPE,
        )
        for platform in post.RUNTIME_SHA256_BY_PLATFORM
    )


class _Executor:
    def __init__(self, *, variant: str = "pass") -> None:
        self.variant = variant
        self.calls: list[str] = []

    def inspect_synthetic(
        self, *, request: Any, platform: str, repeat_index: int, operation_id: str
    ) -> post.PrivateVisionOperationEvidence:
        self.calls.append(operation_id)
        if self.variant == "interrupt":
            raise KeyboardInterrupt
        capability = next(item for item in _capabilities() if item.platform == platform)
        pose = PoseEstimate(
            yaw_degrees=11.0 if self.variant == "pose" else 0.0,
            pitch_degrees=0.0,
            roll_degrees=0.0,
            confidence=1.0,
        )
        observations: tuple[FaceObservation, ...]
        if self.variant == "no_face":
            observations = ()
        else:
            observations = (
                FaceObservation(
                    observation_reference="face-cc06-001",
                    landmarks=FaceLandmarkSet(
                        coordinate_system="normalized_image_v1",
                        landmarks=tuple(
                            FaceLandmark(
                                landmark_code=f"pt{index:03d}",
                                x=0.2 + (index / 5_000),
                                y=0.3 + (index / 10_000),
                                confidence=1.0,
                            )
                            for index in range(478)
                        ),
                    ),
                    pose=pose,
                    geometry_measurements=(),
                ),
            )
        result = SyntheticVisionResult(
            request_reference=request.request_reference,
            provider_run_reference="run-cc06-001",
            observations=observations,
            safety=ProviderSafetyFact(
                policy_reference="policy-cc06", outcome="passed", reason_code="pass-cc06"
            ),
            cost=ProviderCostFact(currency="CNY", amount_micros=0, status="final"),
            provenance=ProviderProvenanceFact(
                provider_reference="provider-cc06",
                model_reference="model-cc06",
                model_version_reference="modelv-cc06",
                policy_reference="policy-cc06",
                retention_status="not_retained",
                output_rights="internal_evaluation_only",
            ),
        )
        return post.PrivateVisionOperationEvidence(
            vision_result=result,
            transformation_matrix=(1.0,) * 16,
            bbox_area=0.2,
            rotation_degrees=0.0,
            platform=capability.platform,
            capability_id=(
                "cap-mismatch-cc06"
                if self.variant == "binding_mismatch"
                else capability.capability_id
            ),
            runtime_sha256=capability.runtime_sha256,
            model_sha256=capability.model_sha256,
            manifest_version=capability.manifest_version,
            manifest_sha256=capability.manifest_sha256,
            qa_policy_version=capability.qa_policy_version,
            qa_policy_sha256=capability.qa_policy_sha256,
            zero_egress_evidence_id=capability.zero_egress_evidence_id,
            zero_egress_evidence_sha256=capability.zero_egress_evidence_sha256,
            approved_scope=capability.approved_scope,
        )


def _registered(
    tmp_path: Path, *, ordinal: str = "CAL-REQ-004"
) -> tuple[Path, dict[str, str], bytes]:
    (tmp_path / ".git").write_text("gitdir: synthetic-test-worktree\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".private-handoff/\n", encoding="utf-8")
    parent = tmp_path / ".private-handoff"
    parent.mkdir()
    overlay_sha, post_sha = _pins()
    initial = overlay.initialize_overlay(
        allowed_parent=parent,
        root=parent / "overlay-cc06-0001",
        overlay_output_id="OVERLAY-CC06-0001",
        controller_sha256=overlay_sha,
        binding=_binding(next_unused_ordinal=ordinal),
        timestamp=TIMESTAMP,
    )
    ordinal_suffix = ordinal.rsplit("-", 1)[-1]
    action_id = f"action-cc06-{ordinal_suffix}"
    output_id = f"OUTPUT-CC06-{ordinal_suffix}"
    prepared = overlay.prepare_dispatch(
        receipt_path=initial.receipt_path,
        expected_controller_sha256=overlay_sha,
        ordinal=ordinal,
        action_id=action_id,
        expected_output_opaque_id=output_id,
        timestamp=TIMESTAMP,
    )
    consumed = overlay.consume_dispatch(
        receipt_path=prepared.receipt_path,
        expected_controller_sha256=overlay_sha,
        action_id=action_id,
        timestamp=TIMESTAMP,
    )
    image = _png_bytes()
    data_url = "data:image/png;base64," + base64.b64encode(image).decode("ascii")
    returned = overlay.record_output_returned(
        receipt_path=consumed.receipt_path,
        expected_controller_sha256=overlay_sha,
        action_id=action_id,
        timestamp=TIMESTAMP,
        returned_output_count=1,
        exact_generated_artifact_receipt=data_url,
    )
    registered = overlay.register_imagegen_data_url_before_decode(
        receipt_path=returned.receipt_path,
        expected_controller_sha256=overlay_sha,
        action_id=action_id,
        project_worktree_root=tmp_path,
        imagegen_data_url=data_url,
        timestamp=TIMESTAMP,
    )
    receipt = cast(
        dict[str, Any],
        overlay.verify_overlay(registered.receipt_path, expected_controller_sha256=overlay_sha)[
            "receipt"
        ],
    )
    return (
        registered.receipt_path,
        {
            "overlay_sha": overlay_sha,
            "post_sha": post_sha,
            "receipt_sha": overlay.sha256_file(registered.receipt_path),
            "state_sha": cast(str, receipt["state_sha256"]),
            "event_sha": cast(str, receipt["event_sha256"]),
        },
        image,
    )


def _authority_by_platform(
    capabilities: tuple[post.PrivateVisionCapabilityBinding, ...],
) -> dict[str, str]:
    return {
        capability.platform: overlay.sha256_bytes(
            overlay.canonical_json_bytes(post._capability_payload(capability))
        )
        for capability in capabilities
    }


def _process(
    tmp_path: Path,
    receipt_path: Path,
    pins: dict[str, str],
    executor: _Executor,
    *,
    authority_by_platform: Mapping[str, str] | None = None,
    timestamp: str = TIMESTAMP,
) -> post.PostRegistrationHandle:
    capabilities = _capabilities()
    return post.process_registered_output(
        receipt_path=receipt_path,
        expected_overlay_receipt_sha256=pins["receipt_sha"],
        expected_overlay_state_sha256=pins["state_sha"],
        expected_overlay_event_sha256=pins["event_sha"],
        expected_overlay_controller_sha256=pins["overlay_sha"],
        expected_post_registration_controller_sha256=pins["post_sha"],
        project_worktree_root=tmp_path,
        capabilities=capabilities,
        expected_capability_authority_sha256_by_platform=(
            _authority_by_platform(capabilities)
            if authority_by_platform is None
            else authority_by_platform
        ),
        executor=executor,
        timestamp=timestamp,
    )


def _terminal_state(handle: post.PostRegistrationHandle, pins: dict[str, str]) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        overlay.verify_overlay(handle.receipt_path, expected_controller_sha256=pins["overlay_sha"])[
            "state"
        ],
    )


def _expected_counters() -> dict[str, int]:
    return {
        "request_call_count": 4,
        "requested_output_count": 4,
        "returned_output_count": 4,
        "raw_output_count": 4,
        "formal_calls_remaining": 28,
        "formal_raw_capacity_remaining": 28,
        "global_native_output_capacity_remaining": 59,
        "global_native_output_consumed": 5,
        "admitted_identity_count": 0,
        "rejected_output_count": 0,
        "failed_call_count": 0,
        "active_calls": 0,
    }


def test_success_chain_preserves_ledger_and_redacts_private_fixture(tmp_path: Path) -> None:
    receipt, pins, _image = _registered(tmp_path)
    executor = _Executor()
    handle = _process(tmp_path, receipt, pins, executor)
    state = _terminal_state(handle, pins)

    assert handle.phase == "POST_REGISTRATION_TECHNICAL_QA_PASSED"
    assert len(executor.calls) == 20
    assert state["counters"] == _expected_counters()


@pytest.mark.parametrize("variant", ("no_face", "pose"))
def test_content_gate_rejections_are_terminal_and_do_not_change_resources(
    tmp_path: Path, variant: str
) -> None:
    receipt, pins, _image = _registered(tmp_path)
    handle = _process(tmp_path, receipt, pins, _Executor(variant=variant))
    state = _terminal_state(handle, pins)
    assert handle.phase == "POST_REGISTRATION_CONTENT_REJECTED"
    assert state["counters"] == _expected_counters()
    assert state["decode_authorized"] is False


def test_capability_mismatch_is_reported_as_infrastructure_failure(tmp_path: Path) -> None:
    receipt, pins, _image = _registered(tmp_path)
    handle = _process(tmp_path, receipt, pins, _Executor(variant="binding_mismatch"))
    assert handle.phase == "POST_REGISTRATION_INFRA_FAILURE"


def test_capability_authority_mismatch_fails_closed_before_executor(tmp_path: Path) -> None:
    receipt, pins, _image = _registered(tmp_path)
    executor = _Executor()
    bad_authority = _authority_by_platform(_capabilities())
    bad_authority["linux_x86_64_network_none"] = "0" * 64
    with pytest.raises(post.PostRegistrationError, match="CAPABILITY_AUTHORITY_MISMATCH"):
        _process(
            tmp_path,
            receipt,
            pins,
            executor,
            authority_by_platform=bad_authority,
        )
    assert executor.calls == []


def test_duck_typed_evidence_is_not_persisted(tmp_path: Path) -> None:
    receipt, pins, _image = _registered(tmp_path)

    class DuckExecutor:
        def __init__(self) -> None:
            self.calls = 0

        def inspect_synthetic(self, **_kwargs: Any) -> object:
            self.calls += 1
            return object()

    executor = DuckExecutor()
    handle = _process(tmp_path, receipt, pins, cast(_Executor, executor))
    assert handle.phase == "POST_REGISTRATION_INFRA_FAILURE"
    assert executor.calls == 1


def test_plan_without_result_becomes_unknown_without_reinvocation(tmp_path: Path) -> None:
    receipt, pins, _image = _registered(tmp_path)
    interrupted = _Executor(variant="interrupt")
    with pytest.raises(KeyboardInterrupt):
        _process(tmp_path, receipt, pins, interrupted)
    never_reinvoke = _Executor(variant="interrupt")
    handle = _process(tmp_path, receipt, pins, never_reinvoke)
    assert handle.phase == "POST_REGISTRATION_UNKNOWN_M3_OUTCOME"
    assert never_reinvoke.calls == []


def test_durable_result_recovers_without_duplicate_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt, pins, _image = _registered(tmp_path)
    original = post._record_operation_result

    def interrupt_after_result(**kwargs: Any) -> None:
        original(**kwargs)
        raise KeyboardInterrupt

    monkeypatch.setattr(post, "_record_operation_result", interrupt_after_result)
    with pytest.raises(KeyboardInterrupt):
        _process(tmp_path, receipt, pins, _Executor())
    monkeypatch.setattr(post, "_record_operation_result", original)
    recovered = _Executor()
    handle = _process(tmp_path, receipt, pins, recovered)
    assert handle.phase == "POST_REGISTRATION_TECHNICAL_QA_PASSED"
    assert len(recovered.calls) == 19


def test_terminal_checkpoint_recovers_with_original_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt, pins, _image = _registered(tmp_path)
    original = post._transition

    def interrupt_after_checkpoint(**kwargs: Any) -> dict[str, Any]:
        if kwargs["phase"] in post._TERMINAL_PHASES:
            raise KeyboardInterrupt
        return original(**kwargs)

    monkeypatch.setattr(post, "_transition", interrupt_after_checkpoint)
    executor = _Executor()
    with pytest.raises(KeyboardInterrupt):
        _process(tmp_path, receipt, pins, executor)
    assert len(executor.calls) == 20

    monkeypatch.setattr(post, "_transition", original)
    recovered = _Executor()
    handle = _process(
        tmp_path,
        receipt,
        pins,
        recovered,
        timestamp="2026-08-31T00:00:01Z",
    )
    assert handle.phase == "POST_REGISTRATION_TECHNICAL_QA_PASSED"
    assert recovered.calls == []
    assert _terminal_state(handle, pins)["timestamp"] == TIMESTAMP


def test_successor_partial_intent_recovers_with_original_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt, pins, _image = _registered(tmp_path)
    terminal = _process(tmp_path, receipt, pins, _Executor())
    terminal_receipt = cast(
        dict[str, Any],
        overlay.verify_overlay(
            terminal.receipt_path, expected_controller_sha256=pins["overlay_sha"]
        )["receipt"],
    )
    successor_root = receipt.parent.parent / "overlay-cc06-0002"
    original = overlay._commit_transition

    def interrupt_successor_commit(**kwargs: Any) -> Any:
        if kwargs["root"] == successor_root:
            raise KeyboardInterrupt
        return original(**kwargs)

    monkeypatch.setattr(overlay, "_commit_transition", interrupt_successor_commit)
    with pytest.raises(KeyboardInterrupt):
        post.rollover_post_registration_successor(
            terminal_receipt_path=terminal.receipt_path,
            expected_terminal_receipt_sha256=terminal.receipt_sha256,
            expected_terminal_state_sha256=terminal.state_sha256,
            expected_terminal_event_sha256=cast(str, terminal_receipt["event_sha256"]),
            expected_overlay_controller_sha256=pins["overlay_sha"],
            expected_post_registration_controller_sha256=pins["post_sha"],
            project_worktree_root=tmp_path,
            successor_root=successor_root,
            successor_overlay_output_id="OVERLAY-CC06-0002",
            timestamp=TIMESTAMP,
        )

    monkeypatch.setattr(overlay, "_commit_transition", original)
    successor = post.rollover_post_registration_successor(
        terminal_receipt_path=terminal.receipt_path,
        expected_terminal_receipt_sha256=terminal.receipt_sha256,
        expected_terminal_state_sha256=terminal.state_sha256,
        expected_terminal_event_sha256=cast(str, terminal_receipt["event_sha256"]),
        expected_overlay_controller_sha256=pins["overlay_sha"],
        expected_post_registration_controller_sha256=pins["post_sha"],
        project_worktree_root=tmp_path,
        successor_root=successor_root,
        successor_overlay_output_id="OVERLAY-CC06-0002",
        timestamp="2026-08-31T00:00:01Z",
    )
    successor_state = cast(
        dict[str, Any],
        overlay.verify_overlay(
            successor.receipt_path, expected_controller_sha256=pins["overlay_sha"]
        )["state"],
    )
    assert successor.phase == "READY"
    assert successor_state["timestamp"] == TIMESTAMP


def test_successor_intent_recovers_after_crash_before_root_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt, pins, _image = _registered(tmp_path)
    terminal = _process(tmp_path, receipt, pins, _Executor())
    terminal_receipt = cast(
        dict[str, Any],
        overlay.verify_overlay(
            terminal.receipt_path, expected_controller_sha256=pins["overlay_sha"]
        )["receipt"],
    )
    successor_root = receipt.parent.parent / "overlay-cc06-0002"
    original = overlay._create_new_plain_directory

    def interrupt_before_root_creation(path: Path) -> None:
        if path == successor_root:
            raise KeyboardInterrupt
        original(path)

    monkeypatch.setattr(overlay, "_create_new_plain_directory", interrupt_before_root_creation)
    with pytest.raises(KeyboardInterrupt):
        post.rollover_post_registration_successor(
            terminal_receipt_path=terminal.receipt_path,
            expected_terminal_receipt_sha256=terminal.receipt_sha256,
            expected_terminal_state_sha256=terminal.state_sha256,
            expected_terminal_event_sha256=cast(str, terminal_receipt["event_sha256"]),
            expected_overlay_controller_sha256=pins["overlay_sha"],
            expected_post_registration_controller_sha256=pins["post_sha"],
            project_worktree_root=tmp_path,
            successor_root=successor_root,
            successor_overlay_output_id="OVERLAY-CC06-0002",
            timestamp=TIMESTAMP,
        )
    assert not successor_root.exists()

    monkeypatch.setattr(overlay, "_create_new_plain_directory", original)
    successor = post.rollover_post_registration_successor(
        terminal_receipt_path=terminal.receipt_path,
        expected_terminal_receipt_sha256=terminal.receipt_sha256,
        expected_terminal_state_sha256=terminal.state_sha256,
        expected_terminal_event_sha256=cast(str, terminal_receipt["event_sha256"]),
        expected_overlay_controller_sha256=pins["overlay_sha"],
        expected_post_registration_controller_sha256=pins["post_sha"],
        project_worktree_root=tmp_path,
        successor_root=successor_root,
        successor_overlay_output_id="OVERLAY-CC06-0002",
        timestamp="2026-08-31T00:00:01Z",
    )
    successor_state = cast(
        dict[str, Any],
        overlay.verify_overlay(
            successor.receipt_path, expected_controller_sha256=pins["overlay_sha"]
        )["state"],
    )
    assert successor.phase == "READY"
    assert successor_state["timestamp"] == TIMESTAMP


def test_content_rejection_advances_only_after_canary_tranche(tmp_path: Path) -> None:
    canary_root = tmp_path / "canary"
    canary_root.mkdir()
    receipt, pins, _image = _registered(canary_root)
    canary_terminal = _process(canary_root, receipt, pins, _Executor(variant="no_face"))
    canary_receipt = cast(
        dict[str, Any],
        overlay.verify_overlay(
            canary_terminal.receipt_path, expected_controller_sha256=pins["overlay_sha"]
        )["receipt"],
    )
    with pytest.raises(
        post.PostRegistrationError,
        match="POST_REGISTRATION_SUCCESSOR_TERMINAL_NOT_AUTHORIZED",
    ):
        post.rollover_post_registration_successor(
            terminal_receipt_path=canary_terminal.receipt_path,
            expected_terminal_receipt_sha256=canary_terminal.receipt_sha256,
            expected_terminal_state_sha256=canary_terminal.state_sha256,
            expected_terminal_event_sha256=cast(str, canary_receipt["event_sha256"]),
            expected_overlay_controller_sha256=pins["overlay_sha"],
            expected_post_registration_controller_sha256=pins["post_sha"],
            project_worktree_root=canary_root,
            successor_root=receipt.parent.parent / "overlay-cc06-0002",
            successor_overlay_output_id="OVERLAY-CC06-0002",
            timestamp=TIMESTAMP,
        )

    later_root = tmp_path / "later"
    later_root.mkdir()
    later_receipt, later_pins, _image = _registered(later_root, ordinal="CAL-REQ-005")
    later_terminal = _process(
        later_root,
        later_receipt,
        later_pins,
        _Executor(variant="no_face"),
    )
    later_terminal_receipt = cast(
        dict[str, Any],
        overlay.verify_overlay(
            later_terminal.receipt_path,
            expected_controller_sha256=later_pins["overlay_sha"],
        )["receipt"],
    )
    successor = post.rollover_post_registration_successor(
        terminal_receipt_path=later_terminal.receipt_path,
        expected_terminal_receipt_sha256=later_terminal.receipt_sha256,
        expected_terminal_state_sha256=later_terminal.state_sha256,
        expected_terminal_event_sha256=cast(str, later_terminal_receipt["event_sha256"]),
        expected_overlay_controller_sha256=later_pins["overlay_sha"],
        expected_post_registration_controller_sha256=later_pins["post_sha"],
        project_worktree_root=later_root,
        successor_root=later_receipt.parent.parent / "overlay-cc06-0002",
        successor_overlay_output_id="OVERLAY-CC06-0002",
        timestamp=TIMESTAMP,
    )
    assert successor.phase == "READY"


def test_concurrent_callers_have_one_operation_winner_and_successor_is_single_use(
    tmp_path: Path,
) -> None:
    receipt, pins, _image = _registered(tmp_path)
    executor = _Executor()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_process, tmp_path, receipt, pins, executor) for _ in range(2)]
        outcomes = [future.exception() or future.result() for future in futures]
    assert (
        sum(
            isinstance(outcome, post.PostRegistrationHandle)
            and outcome.phase == "POST_REGISTRATION_TECHNICAL_QA_PASSED"
            for outcome in outcomes
        )
        == 1
    )
    assert (
        sum(
            isinstance(outcome, overlay.ExecutionOverlayError)
            and str(outcome) == "QUIESCENCE_LEASE_BUSY"
            for outcome in outcomes
        )
        == 1
    )
    assert len(executor.calls) == 20
    terminal = next(
        outcome for outcome in outcomes if isinstance(outcome, post.PostRegistrationHandle)
    )
    terminal_receipt = cast(
        dict[str, Any],
        overlay.verify_overlay(
            terminal.receipt_path, expected_controller_sha256=pins["overlay_sha"]
        )["receipt"],
    )
    successor_root = receipt.parent.parent / "overlay-cc06-0002"
    successor = post.rollover_post_registration_successor(
        terminal_receipt_path=terminal.receipt_path,
        expected_terminal_receipt_sha256=terminal.receipt_sha256,
        expected_terminal_state_sha256=terminal.state_sha256,
        expected_terminal_event_sha256=cast(str, terminal_receipt["event_sha256"]),
        expected_overlay_controller_sha256=pins["overlay_sha"],
        expected_post_registration_controller_sha256=pins["post_sha"],
        project_worktree_root=tmp_path,
        successor_root=successor_root,
        successor_overlay_output_id="OVERLAY-CC06-0002",
        timestamp=TIMESTAMP,
    )
    assert successor.phase == "READY"
    assert list((successor_root / "staging").iterdir()) == []
    assert list((successor_root / "records").iterdir()) == []
    with pytest.raises(post.PostRegistrationError, match="POST_REGISTRATION_SUCCESSOR"):
        post.rollover_post_registration_successor(
            terminal_receipt_path=terminal.receipt_path,
            expected_terminal_receipt_sha256=terminal.receipt_sha256,
            expected_terminal_state_sha256=terminal.state_sha256,
            expected_terminal_event_sha256=cast(str, terminal_receipt["event_sha256"]),
            expected_overlay_controller_sha256=pins["overlay_sha"],
            expected_post_registration_controller_sha256=pins["post_sha"],
            project_worktree_root=tmp_path,
            successor_root=successor_root,
            successor_overlay_output_id="OVERLAY-CC06-0002",
            timestamp=TIMESTAMP,
        )

    overlay.prepare_dispatch(
        receipt_path=successor.receipt_path,
        expected_controller_sha256=pins["overlay_sha"],
        ordinal="CAL-REQ-005",
        action_id="action-cc06-005",
        expected_output_opaque_id="OUTPUT-CC06-005",
        timestamp="2026-08-31T00:00:01Z",
        expected_ready_receipt_sha256=successor.receipt_sha256,
        expected_ready_state_sha256=successor.state_sha256,
    )
    with pytest.raises(post.PostRegistrationError, match="POST_REGISTRATION_SUCCESSOR"):
        post.verify_post_registration_successor(
            successor_receipt_path=successor.receipt_path,
            predecessor_receipt_path=terminal.receipt_path,
            expected_predecessor_receipt_sha256=terminal.receipt_sha256,
            expected_predecessor_state_sha256=terminal.state_sha256,
            expected_predecessor_event_sha256=cast(str, terminal_receipt["event_sha256"]),
            expected_overlay_controller_sha256=pins["overlay_sha"],
            expected_post_registration_controller_sha256=pins["post_sha"],
            project_worktree_root=tmp_path,
        )
