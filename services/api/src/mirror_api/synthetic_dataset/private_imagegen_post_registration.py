"""Private, digest-bound qualification after native imagegen registration.

This controller deliberately extends an already pinned overlay without editing
it.  All durable records live below the overlay's ignored private root; this
module never accepts a raw-image path, URL, provider SDK object, or database
handle.  The public surface is synchronous because the private capability is
injected by the Principal at the process boundary.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal, Protocol, cast

from mirror_api.image_sanitizer import (
    DEFAULT_IMAGE_SANITIZER_CONFIG,
    ImageSanitizationError,
    SanitizedImage,
    decode_canonical_rgb_image,
    sanitize_image,
)
from mirror_api.providers.base import (
    FaceLandmark,
    FaceLandmarkSet,
    FaceObservation,
    GeometryMeasurement,
    NormalizedSyntheticImagePayload,
    PoseEstimate,
    ProviderCostFact,
    ProviderProvenanceFact,
    ProviderSafetyFact,
    SyntheticVisionRequest,
    SyntheticVisionResult,
)
from mirror_api.synthetic_dataset import private_execution_overlay as _overlay

POST_REGISTRATION_SCHEMA: Final = "mirror.p2-m5/PrivatePostRegistration/v1"
POST_REGISTRATION_CHECKPOINT_SCHEMA: Final = "mirror.p2-m5/PrivatePostRegistrationCheckpoint/v1"
POST_REGISTRATION_ROLLOVER_SCHEMA: Final = "mirror.p2-m5/PrivatePostRegistrationRollover/v1"
POST_REGISTRATION_ROLLOVER_CONTRACT: Final = "p2-m5-cc06-post-registration-successor/v1"
MANIFEST_VERSION: Final = "p2-m5-cc04-b-v01-admission-runtime-v1"
MANIFEST_SHA256: Final = "a1d3698564c8ca0d0b6f01fa28b580d85135ccc8c502616527a140d80ba41cb3"
QA_POLICY_VERSION: Final = "p2-m3-v03-source-built-vision-qa-v1"
QA_POLICY_SHA256: Final = "8305cfaa25d084138fb67e93043a1e37842543a645085d19d3ef52ac8a6ce15f"
MODEL_SHA256: Final = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
APPROVED_SCOPE: Final = (
    "PRIVATE_SYNTHETIC_P2_M5_CC04_B_NORMALIZATION_FACE_POSE_LANDMARK_"
    "RELIABILITY_AND_MORPHOLOGY_ADMISSION_ONLY"
)
VISION_POLICY_REFERENCE: Final = "p2m5-m3-v03"
RUNTIME_SHA256_BY_PLATFORM: Final = {
    "linux_x86_64_network_none": "6a5fb35175efc2f014fb61f7f4abb2c78c38156bd6abf2186d1549cbf3f006a7",
    "windows_amd64_process_specific_outbound_deny": (
        "1c67ae02b90a5b00b58018c3c04db411134d781c6f53b195e68a6ce6136615ef"
    ),
}
_PLATFORMS: Final = tuple(RUNTIME_SHA256_BY_PLATFORM)
_REPEATS_PER_PLATFORM: Final = 10
_MAX_POST_REGISTRATION_TRANSITIONS: Final = 64
_PORT_REFERENCE: Final = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
_TERMINAL_PHASES: Final = frozenset(
    {
        "POST_REGISTRATION_TECHNICAL_QA_PASSED",
        "POST_REGISTRATION_CONTENT_REJECTED",
        "POST_REGISTRATION_INFRA_FAILURE",
        "POST_REGISTRATION_UNKNOWN_M3_OUTCOME",
    }
)


class PostRegistrationError(_overlay.ExecutionOverlayError):
    """Stable, redacted fail-closed error for the auxiliary controller."""


@dataclass(frozen=True, slots=True)
class PrivateVisionCapabilityBinding:
    """Opaque, task-scoped capability facts; locators are intentionally absent."""

    capability_id: str
    platform: Literal["linux_x86_64_network_none", "windows_amd64_process_specific_outbound_deny"]
    runtime_sha256: str
    model_sha256: str
    manifest_version: str
    manifest_sha256: str
    qa_policy_version: str
    qa_policy_sha256: str
    zero_egress_evidence_id: str
    zero_egress_evidence_sha256: str
    approved_scope: str


@dataclass(frozen=True, slots=True)
class PrivateVisionOperationEvidence:
    """Typed M3 result plus private technical evidence required by CC06."""

    vision_result: SyntheticVisionResult
    transformation_matrix: tuple[float, ...]
    bbox_area: float
    rotation_degrees: float
    platform: Literal["linux_x86_64_network_none", "windows_amd64_process_specific_outbound_deny"]
    capability_id: str
    runtime_sha256: str
    model_sha256: str
    manifest_version: str
    manifest_sha256: str
    qa_policy_version: str
    qa_policy_sha256: str
    zero_egress_evidence_id: str
    zero_egress_evidence_sha256: str
    approved_scope: str


class PrivateVisionOperationExecutor(Protocol):
    """The injected internal capability; no Provider SDK crosses this boundary."""

    def inspect_synthetic(
        self,
        *,
        request: SyntheticVisionRequest,
        platform: str,
        repeat_index: int,
        operation_id: str,
    ) -> PrivateVisionOperationEvidence: ...


@dataclass(frozen=True, slots=True)
class PostRegistrationHandle:
    """Runtime-only handle.  Its path is never written to a durable payload."""

    receipt_path: Path
    phase: str
    sequence: int
    checkpoint_sha256: str
    receipt_sha256: str
    state_sha256: str
    event_sha256: str


@dataclass(frozen=True, slots=True)
class _ExternalVerificationAuthority:
    """Caller-retained anchors that are not reconstructed from the private chain."""

    registered_receipt_sha256: str
    registered_state_sha256: str
    registered_event_sha256: str
    capability_authority_sha256_by_platform: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class _TerminalTipAuthority:
    """Externally retained exact terminal tip used to reject coherent rehashes."""

    receipt_sha256: str
    state_sha256: str
    event_sha256: str


@dataclass(frozen=True, slots=True)
class _VerifiedReceiptHistory:
    """Invocation-local index over a chain already verified from its current tip."""

    paths_by_tip: Mapping[tuple[str, str, str, str], Path]
    post_states: tuple[Mapping[str, Any], ...]


def process_registered_output(
    *,
    receipt_path: Path,
    expected_overlay_receipt_sha256: str,
    expected_overlay_state_sha256: str,
    expected_overlay_event_sha256: str,
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
    capabilities: tuple[PrivateVisionCapabilityBinding, ...],
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
    executor: PrivateVisionOperationExecutor,
    timestamp: str,
    expected_existing_terminal_receipt_sha256: str | None = None,
    expected_existing_terminal_state_sha256: str | None = None,
    expected_existing_terminal_event_sha256: str | None = None,
) -> PostRegistrationHandle:
    """Qualify one registered output or recover its exact durable result.

    A persisted operation plan is an irrevocable invocation boundary.  A fresh
    call finding a plan without a matching result writes UNKNOWN and does not
    call the executor again.
    """
    _validate_timestamp(timestamp)
    _assert_module_pin(expected_post_registration_controller_sha256)
    authority = _external_verification_authority(
        expected_registered_receipt_sha256=expected_overlay_receipt_sha256,
        expected_registered_state_sha256=expected_overlay_state_sha256,
        expected_registered_event_sha256=expected_overlay_event_sha256,
        expected_capability_authority_sha256_by_platform=(
            expected_capability_authority_sha256_by_platform
        ),
    )
    existing_terminal_tip = _optional_terminal_tip_authority(
        expected_receipt_sha256=expected_existing_terminal_receipt_sha256,
        expected_state_sha256=expected_existing_terminal_state_sha256,
        expected_event_sha256=expected_existing_terminal_event_sha256,
    )
    with _overlay._v2_quiescence_lease(receipt_path.parent):
        _validate_capabilities(
            capabilities,
            authority.capability_authority_sha256_by_platform,
        )
        context = _registered_context(
            receipt_path=receipt_path,
            expected_overlay_receipt_sha256=expected_overlay_receipt_sha256,
            expected_overlay_state_sha256=expected_overlay_state_sha256,
            expected_overlay_event_sha256=expected_overlay_event_sha256,
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            project_worktree_root=project_worktree_root,
        )
        state = context["state"]
        if state["phase"] in _TERMINAL_PHASES:
            if existing_terminal_tip is None:
                raise PostRegistrationError("POST_REGISTRATION_TERMINAL_TIP_AUTHORITY_REQUIRED")
            return _verify_post_registration_terminal_with_authority(
                receipt_path=_context_path(context),
                terminal_tip=existing_terminal_tip,
                authority=authority,
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                project_worktree_root=project_worktree_root,
            )
        if state["phase"] == "POST_REGISTRATION_M3_OPERATION_PLANNED":
            recovered = _recover_planned_operation(
                receipt_path=_context_path(context),
                context=context,
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                project_worktree_root=project_worktree_root,
                capabilities=capabilities,
                authority=authority,
                timestamp=timestamp,
            )
            if isinstance(recovered, PostRegistrationHandle):
                return recovered
        if state["phase"] == "OUTPUT_REGISTERED_PRE_DECODE":
            bound = _bind_and_normalize(
                receipt_path=_context_path(context),
                context=context,
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                project_worktree_root=project_worktree_root,
                authority=authority,
                timestamp=timestamp,
            )
            if isinstance(bound, PostRegistrationHandle):
                return bound
            context = bound
        elif state["phase"] != "POST_REGISTRATION_ATTEMPT_BOUND":
            raise PostRegistrationError("POST_REGISTRATION_STATE_INVALID")
        elif "normalized_file" not in _post_state(state):
            resumed = _normalize_bound_attempt(
                receipt_path=_context_path(context),
                context=context,
                output_id=_required_text(
                    state, "overlay_output_id", "POST_REGISTRATION_OUTPUT_ID_MISSING"
                ),
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                project_worktree_root=project_worktree_root,
                authority=authority,
                timestamp=timestamp,
            )
            if isinstance(resumed, PostRegistrationHandle):
                return resumed
            context = resumed

        while True:
            current_receipt_path = _context_path(context)
            state = context["state"]
            if state["phase"] in _TERMINAL_PHASES:
                if existing_terminal_tip is None:
                    raise PostRegistrationError("POST_REGISTRATION_TERMINAL_TIP_AUTHORITY_REQUIRED")
                return _verify_post_registration_terminal_with_authority(
                    receipt_path=current_receipt_path,
                    terminal_tip=existing_terminal_tip,
                    authority=authority,
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                    project_worktree_root=project_worktree_root,
                )
            failure_reason = _durable_failure_reason(_post_state(state))
            if failure_reason is not None:
                return _terminal(
                    receipt_path=current_receipt_path,
                    context=context,
                    phase="POST_REGISTRATION_INFRA_FAILURE",
                    reason_code=failure_reason,
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=(
                        expected_post_registration_controller_sha256
                    ),
                    project_worktree_root=project_worktree_root,
                    authority=authority,
                    timestamp=timestamp,
                )
            if state["phase"] == "POST_REGISTRATION_M3_OPERATION_PLANNED":
                recovered = _recover_planned_operation(
                    receipt_path=current_receipt_path,
                    context=context,
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                    project_worktree_root=project_worktree_root,
                    capabilities=capabilities,
                    authority=authority,
                    timestamp=timestamp,
                )
                if isinstance(recovered, PostRegistrationHandle):
                    return recovered
                context = recovered
                continue
            operation = _next_operation(state)
            if operation is None:
                return _terminal_from_results(
                    receipt_path=current_receipt_path,
                    context=context,
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                    project_worktree_root=project_worktree_root,
                    capabilities=capabilities,
                    authority=authority,
                    timestamp=timestamp,
                )
            planned = _plan_operation(
                receipt_path=current_receipt_path,
                context=context,
                operation=operation,
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                capabilities=capabilities,
                expected_capability_authority_sha256_by_platform=(
                    authority.capability_authority_sha256_by_platform
                ),
                timestamp=timestamp,
            )
            planned_path = _context_path(planned)
            plan = _planned_operation_record(planned)
            capability = _capability_for(capabilities, cast(str, operation["platform"]))
            try:
                request = _vision_request(planned_path.parent, planned["state"], plan)
            except (PostRegistrationError, OSError, TypeError, ValueError):
                failed = _record_operation_failure(
                    receipt_path=planned_path,
                    context=planned,
                    operation=operation,
                    capability=capability,
                    reason_code="POST_REGISTRATION_VISION_REQUEST_BUILD_FAILED",
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=(
                        expected_post_registration_controller_sha256
                    ),
                    timestamp=timestamp,
                )
                return _terminal(
                    receipt_path=_context_path(failed),
                    context=failed,
                    phase="POST_REGISTRATION_INFRA_FAILURE",
                    reason_code="POST_REGISTRATION_VISION_REQUEST_BUILD_FAILED",
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=(
                        expected_post_registration_controller_sha256
                    ),
                    project_worktree_root=project_worktree_root,
                    authority=authority,
                    timestamp=timestamp,
                )
            try:
                evidence = executor.inspect_synthetic(
                    request=request,
                    platform=cast(str, operation["platform"]),
                    repeat_index=cast(int, operation["repeat_index"]),
                    operation_id=cast(str, operation["operation_id"]),
                )
            except Exception:
                return _terminal(
                    receipt_path=planned_path,
                    context=planned,
                    phase="POST_REGISTRATION_UNKNOWN_M3_OUTCOME",
                    reason_code="POST_REGISTRATION_M3_EXECUTOR_RETURN_NOT_DURABLE",
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                    project_worktree_root=project_worktree_root,
                    authority=authority,
                    timestamp=timestamp,
                )
            try:
                _validate_evidence(evidence, capability, operation, request)
            except (PostRegistrationError, TypeError, ValueError):
                failed = _record_operation_failure(
                    receipt_path=planned_path,
                    context=planned,
                    operation=operation,
                    capability=capability,
                    reason_code="POST_REGISTRATION_OPERATION_EVIDENCE_BINDING_INVALID",
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=(
                        expected_post_registration_controller_sha256
                    ),
                    timestamp=timestamp,
                )
                return _terminal(
                    receipt_path=_context_path(failed),
                    context=failed,
                    phase="POST_REGISTRATION_INFRA_FAILURE",
                    reason_code="POST_REGISTRATION_OPERATION_EVIDENCE_BINDING_INVALID",
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
                    project_worktree_root=project_worktree_root,
                    authority=authority,
                    timestamp=timestamp,
                )
            try:
                context = _record_operation_result(
                    receipt_path=planned_path,
                    context=planned,
                    operation=operation,
                    evidence=evidence,
                    capability=capability,
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=(
                        expected_post_registration_controller_sha256
                    ),
                    timestamp=timestamp,
                )
            except Exception:
                recovered = _recover_planned_operation(
                    receipt_path=planned_path,
                    context=planned,
                    expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                    expected_post_registration_controller_sha256=(
                        expected_post_registration_controller_sha256
                    ),
                    project_worktree_root=project_worktree_root,
                    capabilities=capabilities,
                    authority=authority,
                    timestamp=timestamp,
                )
                if isinstance(recovered, PostRegistrationHandle):
                    return recovered
                context = recovered


def verify_post_registration_terminal(
    *,
    receipt_path: Path,
    expected_terminal_receipt_sha256: str,
    expected_terminal_state_sha256: str,
    expected_terminal_event_sha256: str,
    expected_registered_receipt_sha256: str,
    expected_registered_state_sha256: str,
    expected_registered_event_sha256: str,
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
) -> PostRegistrationHandle:
    """Verify a terminal checkpoint against caller-retained immutable anchors."""
    authority = _external_verification_authority(
        expected_registered_receipt_sha256=expected_registered_receipt_sha256,
        expected_registered_state_sha256=expected_registered_state_sha256,
        expected_registered_event_sha256=expected_registered_event_sha256,
        expected_capability_authority_sha256_by_platform=(
            expected_capability_authority_sha256_by_platform
        ),
    )
    terminal_tip = _terminal_tip_authority(
        expected_receipt_sha256=expected_terminal_receipt_sha256,
        expected_state_sha256=expected_terminal_state_sha256,
        expected_event_sha256=expected_terminal_event_sha256,
    )
    return _verify_post_registration_terminal_with_authority(
        receipt_path=receipt_path,
        terminal_tip=terminal_tip,
        authority=authority,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
        project_worktree_root=project_worktree_root,
    )


def _verify_post_registration_terminal_with_authority(
    *,
    receipt_path: Path,
    terminal_tip: _TerminalTipAuthority,
    authority: _ExternalVerificationAuthority,
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
) -> PostRegistrationHandle:
    """Internal verifier after exact external authority values are validated."""
    _assert_module_pin(expected_post_registration_controller_sha256)
    _overlay._validate_project_local_private_parent(
        project_worktree_root=project_worktree_root, allowed_parent=receipt_path.parent.parent
    )
    if _overlay.sha256_file(receipt_path) != terminal_tip.receipt_sha256:
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_TIP_MISMATCH")
    context = _current_context(
        receipt_path=receipt_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    _ensure_no_next_receipt(context)
    receipt = cast(dict[str, Any], context["receipt"])
    event = cast(dict[str, Any], context["event"])
    state = context["state"]
    if (
        receipt.get("state_sha256") != terminal_tip.state_sha256
        or receipt.get("event_sha256") != terminal_tip.event_sha256
    ):
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_TIP_MISMATCH")
    if state["phase"] not in _TERMINAL_PHASES:
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_REQUIRED")
    sequence = cast(int, receipt["sequence"])
    previous_name = receipt.get("previous_receipt_file")
    if previous_name != _overlay._receipt_name(sequence - 1):
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_PREDECESSOR_INVALID")
    previous_path = _overlay._safe_child(receipt_path.parent, cast(str, previous_name))
    previous = _current_context(
        receipt_path=previous_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    previous_state = cast(dict[str, Any], previous["state"])
    previous_post = _post_state(previous_state)
    post = _post_state(state)
    checkpoint_name = _required_text(
        post, "checkpoint_file", "POST_REGISTRATION_CHECKPOINT_MISSING"
    )
    checkpoint_path = _overlay._safe_child(receipt_path.parent / "records", checkpoint_name)
    checkpoint = _overlay._read_json(checkpoint_path)
    checkpoint_sha256 = _overlay.sha256_file(checkpoint_path)
    expected_checkpoint = {
        "schema_version": POST_REGISTRATION_CHECKPOINT_SCHEMA,
        "module_sha256": expected_post_registration_controller_sha256,
        "terminal_phase": state["phase"],
        "reason_code": event.get("reason_code"),
        "overlay_tip": _tip_payload(cast(dict[str, Any], previous["receipt"])),
        "post_registration": _redacted_post_binding(previous_post),
        "counters": dict(_counters(previous_state)),
        "decode_performed": previous_post.get("decode_performed") is True,
        "db_mutations": 0,
        "provider_calls_added": 0,
        "admission": 0,
        "timestamp": state.get("timestamp"),
    }
    expected_post = dict(previous_post)
    expected_post.update(
        {
            "checkpoint_file": checkpoint_name,
            "checkpoint_sha256": checkpoint_sha256,
        }
    )
    if (
        _overlay._read_plain_file_bytes(checkpoint_path)
        != _overlay.canonical_json_bytes(checkpoint)
        or checkpoint != expected_checkpoint
        or post != expected_post
        or post.get("checkpoint_sha256") != checkpoint_sha256
        or receipt.get("phase") != state["phase"]
        or event.get("event_type") != state["phase"]
        or event.get("post_registration_module_sha256")
        != expected_post_registration_controller_sha256
        or event.get("timestamp") != state.get("timestamp")
        or state.get("previous_state_sha256")
        != cast(dict[str, Any], previous["receipt"]).get("state_sha256")
        or event.get("previous_event_sha256")
        != cast(dict[str, Any], previous["receipt"]).get("event_sha256")
        or state.get("counters") != previous_state.get("counters")
    ):
        raise PostRegistrationError("POST_REGISTRATION_CHECKPOINT_INVALID")
    try:
        _verify_terminal_evidence(
            root=receipt_path.parent,
            state=previous_state,
            terminal_phase=cast(str, state["phase"]),
            terminal_reason_code=_required_text(
                event, "reason_code", "POST_REGISTRATION_TERMINAL_REASON_MISSING"
            ),
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
            project_worktree_root=project_worktree_root,
            authority=authority,
        )
    except PostRegistrationError:
        raise
    except (
        _overlay.ExecutionOverlayError,
        ImageSanitizationError,
        OSError,
        TypeError,
        ValueError,
    ):
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_EVIDENCE_INVALID") from None
    counters = _counters(state)
    expected_hard_stop = state["phase"] in {
        "POST_REGISTRATION_INFRA_FAILURE",
        "POST_REGISTRATION_UNKNOWN_M3_OUTCOME",
    }
    if (
        counters["active_calls"] != 0
        or state.get("decode_authorized") is not False
        or state.get("hard_stop") is not expected_hard_stop
    ):
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_COUNTERS_INVALID")
    return PostRegistrationHandle(
        receipt_path=receipt_path,
        phase=cast(str, state["phase"]),
        sequence=cast(int, state["sequence"]),
        checkpoint_sha256=checkpoint_sha256,
        receipt_sha256=_overlay.sha256_file(receipt_path),
        state_sha256=cast(str, context["receipt"]["state_sha256"]),
        event_sha256=cast(str, context["receipt"]["event_sha256"]),
    )


def rollover_post_registration_successor(
    *,
    terminal_receipt_path: Path,
    expected_terminal_receipt_sha256: str,
    expected_terminal_state_sha256: str,
    expected_terminal_event_sha256: str,
    expected_registered_receipt_sha256: str,
    expected_registered_state_sha256: str,
    expected_registered_event_sha256: str,
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
    successor_root: Path,
    successor_overlay_output_id: str,
    timestamp: str,
) -> PostRegistrationHandle:
    """Create the one zero-work successor of a technically passed canary."""
    _validate_timestamp(timestamp)
    _assert_module_pin(expected_post_registration_controller_sha256)
    terminal_tip = _terminal_tip_authority(
        expected_receipt_sha256=expected_terminal_receipt_sha256,
        expected_state_sha256=expected_terminal_state_sha256,
        expected_event_sha256=expected_terminal_event_sha256,
    )
    authority = _external_verification_authority(
        expected_registered_receipt_sha256=expected_registered_receipt_sha256,
        expected_registered_state_sha256=expected_registered_state_sha256,
        expected_registered_event_sha256=expected_registered_event_sha256,
        expected_capability_authority_sha256_by_platform=(
            expected_capability_authority_sha256_by_platform
        ),
    )
    _overlay._validate_project_local_private_parent(
        project_worktree_root=project_worktree_root,
        allowed_parent=terminal_receipt_path.parent.parent,
    )
    parent = terminal_receipt_path.parent.parent
    if (
        not terminal_receipt_path.is_absolute()
        or not successor_root.is_absolute()
        or successor_root.parent.resolve() != parent.resolve()
        or successor_root.resolve() == terminal_receipt_path.parent.resolve()
    ):
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_ROOT_INVALID")
    _overlay._validate_opaque_id(successor_root.name, "POST_REGISTRATION_SUCCESSOR_ROOT_NAME")
    _overlay._validate_opaque_id(
        successor_overlay_output_id, "POST_REGISTRATION_SUCCESSOR_OUTPUT_ID"
    )
    with _overlay._v2_quiescence_lease(terminal_receipt_path.parent):
        terminal = _verify_post_registration_terminal_with_authority(
            receipt_path=terminal_receipt_path,
            terminal_tip=terminal_tip,
            authority=authority,
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
            project_worktree_root=project_worktree_root,
        )
        context = _current_context(
            receipt_path=terminal_receipt_path,
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        )
        receipt = cast(dict[str, Any], context["receipt"])
        if not _successor_terminal_allowed(
            phase=terminal.phase,
            next_unused_ordinal=context["state"].get("next_unused_ordinal"),
        ):
            raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_TERMINAL_NOT_AUTHORIZED")
        if (
            terminal.receipt_sha256 != expected_terminal_receipt_sha256
            or receipt.get("state_sha256") != expected_terminal_state_sha256
            or receipt.get("event_sha256") != expected_terminal_event_sha256
        ):
            raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_PREDECESSOR_DIGEST_MISMATCH")
        if successor_overlay_output_id == context["state"].get("overlay_output_id"):
            raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_OUTPUT_ID_REUSED")
        intent_path = _successor_intent_path(
            parent=parent,
            terminal=terminal,
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
        )
        intent_preexists = intent_path.exists() or intent_path.is_symlink()
        if not intent_preexists and (successor_root.exists() or successor_root.is_symlink()):
            raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_ROOT_PREEXISTS_WITHOUT_INTENT")
        parent_sha256 = _overlay._validate_project_local_private_parent(
            project_worktree_root=project_worktree_root,
            allowed_parent=parent,
        )
        _create_or_verify_successor_intent(
            terminal=terminal,
            terminal_context=context,
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
            project_private_parent_sha256=parent_sha256,
            successor_root=successor_root,
            successor_overlay_output_id=successor_overlay_output_id,
            timestamp=timestamp,
        )
        if successor_root.exists() or successor_root.is_symlink():
            _overlay._require_plain_directory(successor_root)
        else:
            _overlay._create_new_plain_directory(successor_root)
        with _overlay._v2_quiescence_lease(successor_root):
            return _commit_successor(
                terminal_receipt_path=terminal_receipt_path,
                terminal_context=context,
                terminal=terminal,
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                expected_post_registration_controller_sha256=(
                    expected_post_registration_controller_sha256
                ),
                authority=authority,
                project_worktree_root=project_worktree_root,
                successor_root=successor_root,
                successor_overlay_output_id=successor_overlay_output_id,
                timestamp=timestamp,
            )


def verify_post_registration_successor(
    *,
    successor_receipt_path: Path,
    predecessor_receipt_path: Path,
    expected_predecessor_receipt_sha256: str,
    expected_predecessor_state_sha256: str,
    expected_predecessor_event_sha256: str,
    expected_registered_receipt_sha256: str,
    expected_registered_state_sha256: str,
    expected_registered_event_sha256: str,
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
) -> PostRegistrationHandle:
    """Verify one generic READY successor and its exact terminal predecessor."""
    _assert_module_pin(expected_post_registration_controller_sha256)
    predecessor_tip = _terminal_tip_authority(
        expected_receipt_sha256=expected_predecessor_receipt_sha256,
        expected_state_sha256=expected_predecessor_state_sha256,
        expected_event_sha256=expected_predecessor_event_sha256,
    )
    authority = _external_verification_authority(
        expected_registered_receipt_sha256=expected_registered_receipt_sha256,
        expected_registered_state_sha256=expected_registered_state_sha256,
        expected_registered_event_sha256=expected_registered_event_sha256,
        expected_capability_authority_sha256_by_platform=(
            expected_capability_authority_sha256_by_platform
        ),
    )
    if not successor_receipt_path.is_absolute() or not predecessor_receipt_path.is_absolute():
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_ABSOLUTE_PATH_REQUIRED")
    parent = successor_receipt_path.parent.parent
    _overlay._validate_project_local_private_parent(
        project_worktree_root=project_worktree_root,
        allowed_parent=parent,
    )
    if (
        predecessor_receipt_path.parent.parent.resolve() != parent.resolve()
        or predecessor_receipt_path.parent.resolve() == successor_receipt_path.parent.resolve()
    ):
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_ROOT_INVALID")
    _overlay._require_plain_directory(successor_receipt_path.parent)
    _overlay._require_plain_directory(predecessor_receipt_path.parent)
    with _overlay._v2_quiescence_lease(predecessor_receipt_path.parent):
        with _overlay._v2_quiescence_lease(successor_receipt_path.parent):
            return _verify_post_registration_successor_unleased(
                successor_receipt_path=successor_receipt_path,
                predecessor_receipt_path=predecessor_receipt_path,
                expected_predecessor_receipt_sha256=expected_predecessor_receipt_sha256,
                expected_predecessor_state_sha256=expected_predecessor_state_sha256,
                expected_predecessor_event_sha256=expected_predecessor_event_sha256,
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                expected_post_registration_controller_sha256=(
                    expected_post_registration_controller_sha256
                ),
                predecessor_tip=predecessor_tip,
                authority=authority,
                project_worktree_root=project_worktree_root,
            )


def _verify_post_registration_successor_unleased(
    *,
    successor_receipt_path: Path,
    predecessor_receipt_path: Path,
    expected_predecessor_receipt_sha256: str,
    expected_predecessor_state_sha256: str,
    expected_predecessor_event_sha256: str,
    predecessor_tip: _TerminalTipAuthority,
    authority: _ExternalVerificationAuthority,
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
) -> PostRegistrationHandle:
    predecessor = _verify_post_registration_terminal_with_authority(
        receipt_path=predecessor_receipt_path,
        terminal_tip=predecessor_tip,
        authority=authority,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
        project_worktree_root=project_worktree_root,
    )
    predecessor_context = _current_context(
        receipt_path=predecessor_receipt_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    if (
        predecessor.receipt_sha256 != expected_predecessor_receipt_sha256
        or predecessor_context["receipt"].get("state_sha256") != expected_predecessor_state_sha256
        or predecessor_context["receipt"].get("event_sha256") != expected_predecessor_event_sha256
    ):
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_PREDECESSOR_DIGEST_MISMATCH")
    if not _successor_terminal_allowed(
        phase=predecessor.phase,
        next_unused_ordinal=predecessor_context["state"].get("next_unused_ordinal"),
    ):
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_TERMINAL_NOT_AUTHORIZED")
    context = _current_context(
        receipt_path=successor_receipt_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    _ensure_no_next_receipt(
        context,
        error_code="POST_REGISTRATION_SUCCESSOR_STALE_CURRENT_TIP",
    )
    state = context["state"]
    receipt = cast(dict[str, Any], context["receipt"])
    event = cast(dict[str, Any], context["event"])
    if _overlay._read_plain_file_bytes(successor_receipt_path) != _overlay.canonical_json_bytes(
        receipt
    ):
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_RECEIPT_NOT_CANONICAL")
    parent = successor_receipt_path.parent.parent
    parent_sha256 = _overlay._validate_project_local_private_parent(
        project_worktree_root=project_worktree_root,
        allowed_parent=parent,
    )
    _overlay._require_empty_rollover_directory_v2(successor_receipt_path.parent / "staging")
    _overlay._require_empty_rollover_directory_v2(successor_receipt_path.parent / "records")
    if state.get("phase") != "READY" or state.get("decode_authorized") is not False:
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_NOT_READY")
    rollover = state.get("post_registration_rollover")
    cross_root = state.get("rollover_predecessor")
    if not isinstance(rollover, dict):
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_BINDING_MISSING")
    if not isinstance(cross_root, dict) or event.get("rollover_predecessor") != cross_root:
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_CROSS_ROOT_MISSING")
    intent_id = cross_root.get("rollover_intent_id")
    intent_file = cross_root.get("rollover_intent_file")
    intent_sha256 = cross_root.get("rollover_intent_sha256")
    if (
        not isinstance(intent_id, str)
        or not isinstance(intent_file, str)
        or not isinstance(intent_sha256, str)
        or intent_file != f"rollover-v2-intent-{intent_id}.json"
    ):
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_INTENT_BINDING_INVALID")
    _overlay._validate_opaque_id(intent_id, "POST_REGISTRATION_SUCCESSOR_INTENT_ID")
    _validate_lower_digest(
        intent_sha256,
        "POST_REGISTRATION_SUCCESSOR_INTENT_SHA256",
    )
    intent_path = _overlay._safe_child(parent, intent_file)
    intent = _read_canonical_json(
        intent_path,
        "POST_REGISTRATION_SUCCESSOR_INTENT_NOT_CANONICAL",
    )
    if _overlay.sha256_file(intent_path) != intent_sha256:
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_INTENT_DIGEST_MISMATCH")
    expected_predecessor = _successor_predecessor_binding(
        terminal=predecessor,
        terminal_context=predecessor_context,
        project_private_parent_sha256=parent_sha256,
    )
    expected_intent = _successor_intent_payload(
        terminal=predecessor,
        terminal_context=predecessor_context,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
        project_private_parent_sha256=parent_sha256,
        successor_root=successor_receipt_path.parent,
        successor_overlay_output_id=cast(str, state.get("overlay_output_id")),
        timestamp=cast(str, state.get("timestamp")),
    )
    expected_cross_root = {
        **expected_predecessor,
        "rollover_intent_id": intent_id,
        "rollover_intent_file": intent_file,
        "rollover_intent_sha256": intent_sha256,
    }
    if (
        intent != expected_intent
        or rollover != expected_intent
        or cross_root != expected_cross_root
        or receipt.get("sequence") != 0
        or receipt.get("phase") != "READY"
        or state.get("sequence") != 0
        or event.get("event_type") != "POST_REGISTRATION_SUCCESSOR_READY"
        or event.get("reason_code") != _successor_reason_code(predecessor.phase)
        or event.get("timestamp") != state.get("timestamp")
        or event.get("action_id") is not None
        or event.get("request_ordinal") is not None
        or state.get("binding") != predecessor_context["state"].get("binding")
        or state.get("counters") != predecessor_context["state"].get("counters")
        or state.get("next_unused_ordinal")
        != predecessor_context["state"].get("next_unused_ordinal")
        or any(
            state.get(key) is not None
            for key in (
                "current_action_id",
                "current_ordinal",
                "expected_output_opaque_id",
                "returned_output_binding",
                "output_registration_attempt",
                "output_registration",
            )
        )
        or state.get("hard_stop") is not False
        or (successor_receipt_path.parent / "receipt-000001.json").exists()
        or (successor_receipt_path.parent / "receipt-000001.json").is_symlink()
    ):
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_BINDING_INVALID")
    _overlay._require_empty_rollover_directory_v2(successor_receipt_path.parent / "staging")
    _overlay._require_empty_rollover_directory_v2(successor_receipt_path.parent / "records")
    return PostRegistrationHandle(
        receipt_path=successor_receipt_path,
        phase="READY",
        sequence=cast(int, state["sequence"]),
        checkpoint_sha256=predecessor.checkpoint_sha256,
        receipt_sha256=_overlay.sha256_file(successor_receipt_path),
        state_sha256=cast(str, context["receipt"]["state_sha256"]),
        event_sha256=cast(str, context["receipt"]["event_sha256"]),
    )


def _registered_context(
    *,
    receipt_path: Path,
    expected_overlay_receipt_sha256: str,
    expected_overlay_state_sha256: str,
    expected_overlay_event_sha256: str,
    expected_overlay_controller_sha256: str,
    project_worktree_root: Path,
) -> dict[str, Any]:
    _validate_digest(expected_overlay_receipt_sha256, "EXPECTED_OVERLAY_RECEIPT_SHA256")
    _validate_digest(expected_overlay_state_sha256, "EXPECTED_OVERLAY_STATE_SHA256")
    _validate_digest(expected_overlay_event_sha256, "EXPECTED_OVERLAY_EVENT_SHA256")
    _assert_overlay_pin(expected_overlay_controller_sha256)
    _overlay._validate_project_local_private_parent(
        project_worktree_root=project_worktree_root, allowed_parent=receipt_path.parent.parent
    )
    anchor = _current_context(
        receipt_path=receipt_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    anchor_receipt = cast(dict[str, Any], anchor["receipt"])
    anchor_state = cast(dict[str, Any], anchor["state"])
    if (
        anchor_state.get("phase") != "OUTPUT_REGISTERED_PRE_DECODE"
        or _overlay.sha256_file(receipt_path) != expected_overlay_receipt_sha256
        or anchor_receipt.get("state_sha256") != expected_overlay_state_sha256
        or anchor_receipt.get("event_sha256") != expected_overlay_event_sha256
    ):
        raise PostRegistrationError("POST_REGISTRATION_REGISTERED_TIP_MISMATCH")
    _overlay.verify_registration_before_decode(
        receipt_path,
        expected_controller_sha256=expected_overlay_controller_sha256,
        project_worktree_root=project_worktree_root,
    )
    current_path = _latest_receipt_path(
        anchor_receipt_path=receipt_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    context = _current_context(
        receipt_path=current_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    state = cast(dict[str, Any], context["state"])
    phase = state.get("phase")
    if phase in _TERMINAL_PHASES | {
        "POST_REGISTRATION_ATTEMPT_BOUND",
        "POST_REGISTRATION_M3_OPERATION_PLANNED",
    }:
        post = _post_state(state)
        attempt_path = _record_path(
            current_path.parent,
            _required_text(post, "attempt_file", "POST_REGISTRATION_ATTEMPT_MISSING"),
        )
        attempt = _overlay._read_json(attempt_path)
        tip = attempt.get("overlay_tip")
        if (
            not isinstance(tip, dict)
            or tip.get("receipt_sha256") != expected_overlay_receipt_sha256
            or tip.get("state_sha256") != expected_overlay_state_sha256
            or tip.get("event_sha256") != expected_overlay_event_sha256
            or tip.get("controller_sha256") != expected_overlay_controller_sha256
        ):
            raise PostRegistrationError("POST_REGISTRATION_REGISTERED_TIP_MISMATCH")
    elif phase != "OUTPUT_REGISTERED_PRE_DECODE":
        raise PostRegistrationError("POST_REGISTRATION_STATE_INVALID")
    _ensure_no_next_receipt(context)
    return context


def _bind_and_normalize(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
    authority: _ExternalVerificationAuthority,
    timestamp: str,
) -> dict[str, Any] | PostRegistrationHandle:
    receipt = context["receipt"]
    state = context["state"]
    root = receipt_path.parent
    registration = cast(dict[str, Any], state["output_registration"])
    output_id = _required_text(
        registration, "output_opaque_id", "POST_REGISTRATION_OUTPUT_ID_MISSING"
    )
    _overlay._validate_opaque_id(output_id, "POST_REGISTRATION_OUTPUT_ID")
    attempt = _attempt_payload(
        root=root,
        receipt=receipt,
        state=state,
        output_id=output_id,
        module_sha256=expected_post_registration_controller_sha256,
    )
    attempt_path = _record_path(root, f"post-registration-attempt-{output_id}.json")
    attempt_sha256, _ = _overlay._write_json_create_or_verify_exact(attempt_path, attempt)
    preliminary_post = {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "module_sha256": expected_post_registration_controller_sha256,
        "attempt_file": attempt_path.name,
        "attempt_sha256": attempt_sha256,
        "completed_operations": [],
        "decode_performed": False,
    }
    context = _transition(
        receipt_path=receipt_path,
        context=context,
        phase="POST_REGISTRATION_ATTEMPT_BOUND",
        event_type="POST_REGISTRATION_ATTEMPT_BOUND",
        reason_code="POST_REGISTRATION_ATTEMPT_DURABLE_BEFORE_RAW_READ",
        post=preliminary_post,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        timestamp=timestamp,
    )
    return _normalize_bound_attempt(
        receipt_path=_context_path(context),
        context=context,
        output_id=output_id,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
        project_worktree_root=project_worktree_root,
        authority=authority,
        timestamp=timestamp,
    )


def _normalize_bound_attempt(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    output_id: str,
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
    authority: _ExternalVerificationAuthority,
    timestamp: str,
) -> dict[str, Any] | PostRegistrationHandle:
    root = receipt_path.parent
    post_before = _post_state(context["state"])
    attempt_path = _record_path(
        root,
        _required_text(post_before, "attempt_file", "POST_REGISTRATION_ATTEMPT_MISSING"),
    )
    attempt = _overlay._read_json(attempt_path)
    attempt_sha256 = _overlay.sha256_file(attempt_path)
    staging_path = _overlay._safe_child(root / "staging", f"{output_id}.raw")
    raw = _overlay._read_plain_file_bytes(staging_path)
    if (
        _overlay.sha256_bytes(raw) != attempt["source_sha256"]
        or len(raw) != attempt["source_byte_size"]
    ):
        raise PostRegistrationError("POST_REGISTRATION_STAGING_BINDING_MISMATCH")
    try:
        normalized = sanitize_image(raw, declared_mime_type=cast(str, attempt["source_media_type"]))
        decode_canonical_rgb_image(
            normalized.bytes_value,
            expected_width=normalized.width,
            expected_height=normalized.height,
        )
    except ImageSanitizationError as error:
        return _terminal(
            receipt_path=receipt_path,
            context=context,
            phase="POST_REGISTRATION_CONTENT_REJECTED",
            reason_code=f"POST_REGISTRATION_NORMALIZATION_{error.code.upper()}",
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
            project_worktree_root=project_worktree_root,
            authority=authority,
            timestamp=timestamp,
        )
    normalized_name = f"normalized-{output_id}.jpeg"
    normalized_path = _record_path(root, normalized_name)
    normalized_sha256, _ = _overlay._write_bytes_create_or_verify_exact(
        normalized_path, normalized.bytes_value
    )
    normalization = _normalization_payload(
        attempt=attempt,
        attempt_sha256=attempt_sha256,
        normalized=normalized,
        normalized_name=normalized_name,
        normalized_sha256=normalized_sha256,
        module_sha256=expected_post_registration_controller_sha256,
    )
    normalization_name = f"post-registration-normalization-{output_id}.json"
    normalization_path = _record_path(root, normalization_name)
    normalization_sha256, _ = _overlay._write_json_create_or_verify_exact(
        normalization_path, normalization
    )
    post = {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "module_sha256": expected_post_registration_controller_sha256,
        "attempt_file": attempt_path.name,
        "attempt_sha256": attempt_sha256,
        "normalization_file": normalization_name,
        "normalization_sha256": normalization_sha256,
        "normalized_file": normalized_name,
        "normalized_sha256": normalized_sha256,
        "completed_operations": [],
        "decode_performed": True,
    }
    return _transition(
        receipt_path=receipt_path,
        context=context,
        phase="POST_REGISTRATION_ATTEMPT_BOUND",
        event_type="POST_REGISTRATION_ATTEMPT_BOUND",
        reason_code="POST_REGISTRATION_NORMALIZATION_AND_SECOND_DECODE_PASS",
        post=post,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        timestamp=timestamp,
    )


def _next_operation(state: Mapping[str, Any]) -> dict[str, Any] | None:
    post = _post_state(state)
    completed = post.get("completed_operations")
    if not isinstance(completed, list):
        raise PostRegistrationError("POST_REGISTRATION_COMPLETED_OPERATIONS_INVALID")
    completed_ids = {value for value in completed if isinstance(value, str)}
    if len(completed_ids) != len(completed):
        raise PostRegistrationError("POST_REGISTRATION_COMPLETED_OPERATIONS_INVALID")
    output_id = _required_text(state, "overlay_output_id", "POST_REGISTRATION_OUTPUT_ID_MISSING")
    for platform in _PLATFORMS:
        for repeat_index in range(1, _REPEATS_PER_PLATFORM + 1):
            operation_id = f"{output_id}-M3-{platform.split('_')[0].upper()}-{repeat_index:02d}"
            if operation_id not in completed_ids:
                return {
                    "operation_id": operation_id,
                    "platform": platform,
                    "repeat_index": repeat_index,
                }
    return None


def _plan_operation(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    operation: Mapping[str, Any],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    capabilities: tuple[PrivateVisionCapabilityBinding, ...],
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
    timestamp: str,
) -> dict[str, Any]:
    state = context["state"]
    post = _post_state(state)
    capability = _capability_for(capabilities, cast(str, operation["platform"]))
    request_reference, asset_reference = _vision_references(state, operation)
    capability_authority_sha256 = _capability_authority_sha256(
        capability,
        expected_capability_authority_sha256_by_platform,
    )
    plan = {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "record_kind": "M3_OPERATION_PLAN",
        "module_sha256": expected_post_registration_controller_sha256,
        "operation_id": operation["operation_id"],
        "platform": operation["platform"],
        "repeat_index": operation["repeat_index"],
        "capability": _capability_payload(capability),
        "capability_authority_sha256": capability_authority_sha256,
        "normalized_sha256": post["normalized_sha256"],
        "request_reference": request_reference,
        "normalized_asset_reference": asset_reference,
        "vision_policy_reference": VISION_POLICY_REFERENCE,
        "overlay_tip": _tip_payload(context["receipt"]),
        "provider_calls_added": 0,
        "db_mutations": 0,
        "admission": 0,
    }
    plan_path = _record_path(
        receipt_path.parent, f"post-registration-operation-{operation['operation_id']}.plan.json"
    )
    plan_sha256, _ = _overlay._write_json_create_or_verify_exact(plan_path, plan)
    planned_post = dict(post)
    planned_post.update(
        {"planned_operation_file": plan_path.name, "planned_operation_sha256": plan_sha256}
    )
    return _transition(
        receipt_path=receipt_path,
        context=context,
        phase="POST_REGISTRATION_M3_OPERATION_PLANNED",
        event_type="POST_REGISTRATION_M3_OPERATION_PLANNED",
        reason_code="POST_REGISTRATION_M3_PLAN_DURABLE_BEFORE_INVOCATION",
        post=planned_post,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        timestamp=timestamp,
    )


def _record_operation_result(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    operation: Mapping[str, Any],
    evidence: PrivateVisionOperationEvidence,
    capability: PrivateVisionCapabilityBinding,
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    timestamp: str,
) -> dict[str, Any]:
    post = _post_state(context["state"])
    plan_name = _required_text(post, "planned_operation_file", "POST_REGISTRATION_PLAN_MISSING")
    plan_path = _record_path(receipt_path.parent, plan_name)
    _overlay._read_json(plan_path)
    plan_sha256 = _overlay.sha256_file(plan_path)
    if plan_sha256 != post.get("planned_operation_sha256"):
        raise PostRegistrationError("POST_REGISTRATION_PLAN_DIGEST_MISMATCH")
    result = _result_payload(
        evidence=evidence,
        capability=capability,
        operation=operation,
        plan_sha256=plan_sha256,
        module_sha256=expected_post_registration_controller_sha256,
        timestamp=timestamp,
    )
    result_path = _record_path(
        receipt_path.parent, f"post-registration-operation-{operation['operation_id']}.result.json"
    )
    result_sha256, _ = _overlay._write_json_create_or_verify_exact(result_path, result)
    completed = list(cast(list[str], post["completed_operations"]))
    completed.append(cast(str, operation["operation_id"]))
    recovered_post = dict(post)
    recovered_post.update(
        {
            "completed_operations": completed,
            "last_operation_result_file": result_path.name,
            "last_operation_result_sha256": result_sha256,
        }
    )
    recovered_post.pop("planned_operation_file", None)
    recovered_post.pop("planned_operation_sha256", None)
    return _transition(
        receipt_path=receipt_path,
        context=context,
        phase="POST_REGISTRATION_ATTEMPT_BOUND",
        event_type="POST_REGISTRATION_M3_OPERATION_RESULT_DURABLE",
        reason_code="POST_REGISTRATION_M3_RESULT_DURABLE_AFTER_RETURN",
        post=recovered_post,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        timestamp=timestamp,
    )


def _recover_planned_operation(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
    capabilities: tuple[PrivateVisionCapabilityBinding, ...],
    authority: _ExternalVerificationAuthority,
    timestamp: str,
) -> PostRegistrationHandle | dict[str, Any]:
    post = _post_state(context["state"])
    try:
        plan, operation, capability = _verify_planned_operation(
            receipt_path=receipt_path,
            context=context,
            capabilities=capabilities,
            expected_capability_authority_sha256_by_platform=(
                authority.capability_authority_sha256_by_platform
            ),
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
        )
    except (PostRegistrationError, OSError, TypeError, ValueError):
        return _terminal(
            receipt_path=receipt_path,
            context=context,
            phase="POST_REGISTRATION_UNKNOWN_M3_OUTCOME",
            reason_code="POST_REGISTRATION_M3_PLAN_RECOVERY_INVALID",
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
            project_worktree_root=project_worktree_root,
            authority=authority,
            timestamp=timestamp,
        )
    operation_id = cast(str, operation["operation_id"])
    result_path = _record_path(
        receipt_path.parent,
        f"post-registration-operation-{operation_id}.result.json",
    )
    if not result_path.exists() or result_path.is_symlink():
        return _terminal(
            receipt_path=receipt_path,
            context=context,
            phase="POST_REGISTRATION_UNKNOWN_M3_OUTCOME",
            reason_code="POST_REGISTRATION_M3_PLAN_WITHOUT_RESULT",
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
            project_worktree_root=project_worktree_root,
            authority=authority,
            timestamp=timestamp,
        )
    try:
        result = _overlay._read_json(result_path)
        if _overlay._read_plain_file_bytes(result_path) != _overlay.canonical_json_bytes(result):
            raise PostRegistrationError("POST_REGISTRATION_RESULT_NOT_CANONICAL")
        if result.get("record_kind") == "M3_OPERATION_FAILURE":
            _verify_operation_failure_record(
                result=result,
                plan=plan,
                operation=operation,
                capability=capability,
                expected_post_registration_controller_sha256=(
                    expected_post_registration_controller_sha256
                ),
            )
            failed = _bind_durable_failure(
                receipt_path=receipt_path,
                context=context,
                result_path=result_path,
                reason_code=cast(str, result["reason_code"]),
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                timestamp=timestamp,
            )
            return _terminal(
                receipt_path=_context_path(failed),
                context=failed,
                phase="POST_REGISTRATION_INFRA_FAILURE",
                reason_code=cast(str, result["reason_code"]),
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                expected_post_registration_controller_sha256=(
                    expected_post_registration_controller_sha256
                ),
                project_worktree_root=project_worktree_root,
                authority=authority,
                timestamp=timestamp,
            )
        _verify_operation_result_record(
            result=result,
            plan=plan,
            operation=operation,
            capability=capability,
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
        )
    except (PostRegistrationError, OSError, TypeError, ValueError):
        return _terminal(
            receipt_path=receipt_path,
            context=context,
            phase="POST_REGISTRATION_UNKNOWN_M3_OUTCOME",
            reason_code="POST_REGISTRATION_M3_RESULT_RECOVERY_INVALID",
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
            project_worktree_root=project_worktree_root,
            authority=authority,
            timestamp=timestamp,
        )
    completed = list(cast(list[str], post["completed_operations"]))
    if operation_id not in completed:
        completed.append(operation_id)
    recovered_post = dict(post)
    recovered_post.update(
        {
            "completed_operations": completed,
            "last_operation_result_file": result_path.name,
            "last_operation_result_sha256": _overlay.sha256_file(result_path),
        }
    )
    recovered_post.pop("planned_operation_file", None)
    recovered_post.pop("planned_operation_sha256", None)
    return _transition(
        receipt_path=receipt_path,
        context=context,
        phase="POST_REGISTRATION_ATTEMPT_BOUND",
        event_type="POST_REGISTRATION_M3_OPERATION_RESULT_RECOVERED",
        reason_code="POST_REGISTRATION_M3_RESULT_RECOVERED_WITHOUT_REINVOKE",
        post=recovered_post,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        timestamp=timestamp,
    )


def _terminal_from_results(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
    capabilities: tuple[PrivateVisionCapabilityBinding, ...],
    authority: _ExternalVerificationAuthority,
    timestamp: str,
) -> PostRegistrationHandle:
    result_values: list[dict[str, Any]] = []
    try:
        for operation in _all_operations(context["state"]):
            capability = _capability_for(
                capabilities,
                cast(str, operation["platform"]),
            )
            result_values.append(
                _read_and_verify_completed_result(
                    root=receipt_path.parent,
                    state=context["state"],
                    operation=operation,
                    capability=capability,
                    expected_overlay_controller_sha256=(expected_overlay_controller_sha256),
                    expected_capability_authority_sha256_by_platform=(
                        authority.capability_authority_sha256_by_platform
                    ),
                    expected_post_registration_controller_sha256=(
                        expected_post_registration_controller_sha256
                    ),
                )
            )
    except (PostRegistrationError, OSError, TypeError, ValueError):
        return _terminal(
            receipt_path=receipt_path,
            context=context,
            phase="POST_REGISTRATION_INFRA_FAILURE",
            reason_code="POST_REGISTRATION_COMPLETED_RESULT_VERIFICATION_INVALID",
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
            project_worktree_root=project_worktree_root,
            authority=authority,
            timestamp=timestamp,
        )
    reason = _qa_reason(result_values)
    return _terminal(
        receipt_path=receipt_path,
        context=context,
        phase=(
            "POST_REGISTRATION_TECHNICAL_QA_PASSED"
            if reason is None
            else "POST_REGISTRATION_CONTENT_REJECTED"
        ),
        reason_code=(
            "POST_REGISTRATION_TECHNICAL_QA_ALL_V01_V03_GATES_PASS" if reason is None else reason
        ),
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
        project_worktree_root=project_worktree_root,
        authority=authority,
        timestamp=timestamp,
    )


def _terminal(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    phase: str,
    reason_code: str,
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
    authority: _ExternalVerificationAuthority,
    timestamp: str,
) -> PostRegistrationHandle:
    if phase not in _TERMINAL_PHASES:
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_PHASE_INVALID")
    state = context["state"]
    post = _post_state(state)
    checkpoint_base = {
        "schema_version": POST_REGISTRATION_CHECKPOINT_SCHEMA,
        "module_sha256": expected_post_registration_controller_sha256,
        "terminal_phase": phase,
        "reason_code": reason_code,
        "overlay_tip": _tip_payload(context["receipt"]),
        "post_registration": _redacted_post_binding(post),
        "counters": dict(_counters(state)),
        "decode_performed": post.get("decode_performed") is True,
        "db_mutations": 0,
        "provider_calls_added": 0,
        "admission": 0,
    }
    output_id = _required_text(state, "overlay_output_id", "POST_REGISTRATION_OUTPUT_ID_MISSING")
    checkpoint_path = _record_path(
        receipt_path.parent, f"post-registration-checkpoint-{output_id}.json"
    )
    effective_timestamp = timestamp
    if checkpoint_path.exists() or checkpoint_path.is_symlink():
        existing_checkpoint = _read_canonical_json(
            checkpoint_path,
            "POST_REGISTRATION_CHECKPOINT_NOT_CANONICAL",
        )
        effective_timestamp = _required_text(
            existing_checkpoint,
            "timestamp",
            "POST_REGISTRATION_CHECKPOINT_TIMESTAMP_INVALID",
        )
        _validate_timestamp(effective_timestamp)
        checkpoint = {**checkpoint_base, "timestamp": effective_timestamp}
        if existing_checkpoint != checkpoint:
            raise PostRegistrationError("POST_REGISTRATION_CHECKPOINT_RECOVERY_INVALID")
        checkpoint_sha256 = _overlay.sha256_file(checkpoint_path)
    else:
        checkpoint = {**checkpoint_base, "timestamp": effective_timestamp}
        checkpoint_sha256, _ = _overlay._write_json_create_or_verify_exact(
            checkpoint_path,
            checkpoint,
        )
    terminal_post = dict(post)
    terminal_post.update(
        {"checkpoint_file": checkpoint_path.name, "checkpoint_sha256": checkpoint_sha256}
    )
    result_context = _transition(
        receipt_path=receipt_path,
        context=context,
        phase=phase,
        event_type=phase,
        reason_code=reason_code,
        post=terminal_post,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        timestamp=effective_timestamp,
    )
    terminal_path = _context_path(result_context)
    terminal_receipt = cast(dict[str, Any], result_context["receipt"])
    return _verify_post_registration_terminal_with_authority(
        receipt_path=terminal_path,
        terminal_tip=_TerminalTipAuthority(
            receipt_sha256=_overlay.sha256_file(terminal_path),
            state_sha256=cast(str, terminal_receipt["state_sha256"]),
            event_sha256=cast(str, terminal_receipt["event_sha256"]),
        ),
        authority=authority,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
        project_worktree_root=project_worktree_root,
    )


def _verify_terminal_evidence(
    *,
    root: Path,
    state: Mapping[str, Any],
    terminal_phase: str,
    terminal_reason_code: str,
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
    authority: _ExternalVerificationAuthority,
) -> None:
    """Close terminal evidence over the actual immutable private records.

    The checkpoint only carries redacted hashes, so accepting it without
    reopening the referenced records would permit a later file deletion or
    replacement to evade both terminal verification and successor rollover.
    """
    post = _post_state(state)
    verified_history = _verified_receipt_history(
        root=root,
        maximum_sequence=cast(int, state["sequence"]),
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    historical_posts = verified_history.post_states
    _verify_attempt_evidence(
        root=root,
        state=state,
        post=post,
        historical_posts=historical_posts,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
        project_worktree_root=project_worktree_root,
        authority=authority,
    )
    normalization_fields = {
        "normalization_file",
        "normalization_sha256",
        "normalized_file",
        "normalized_sha256",
    }
    has_normalization = normalization_fields <= set(post)
    if normalization_fields & set(post) and not has_normalization:
        raise PostRegistrationError("POST_REGISTRATION_NORMALIZATION_EVIDENCE_PARTIAL")
    completed = post.get("completed_operations")
    if not isinstance(completed, list) or not all(isinstance(item, str) for item in completed):
        raise PostRegistrationError("POST_REGISTRATION_COMPLETED_OPERATIONS_INVALID")
    if len(set(completed)) != len(completed):
        raise PostRegistrationError("POST_REGISTRATION_COMPLETED_OPERATIONS_INVALID")
    all_operations = _all_operations(state)
    operation_by_id = {cast(str, item["operation_id"]): item for item in all_operations}
    if any(operation_id not in operation_by_id for operation_id in completed):
        raise PostRegistrationError("POST_REGISTRATION_COMPLETED_OPERATIONS_INVALID")

    if not has_normalization:
        _verify_operation_record_inventory(root=root, expected_names=set())
        if (
            terminal_phase != "POST_REGISTRATION_CONTENT_REJECTED"
            or not terminal_reason_code.startswith("POST_REGISTRATION_NORMALIZATION_")
            or post.get("decode_performed") is not False
            or completed
            or "planned_operation_file" in post
            or "planned_operation_sha256" in post
        ):
            raise PostRegistrationError("POST_REGISTRATION_TERMINAL_EVIDENCE_INVALID")
        return

    _verify_normalization_evidence(
        root=root,
        post=post,
        historical_posts=historical_posts,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
    )
    completed_results: list[dict[str, Any]] = []
    expected_operation_record_names: set[str] = set()
    for operation_id in completed:
        expected_operation_record_names.update(
            {
                f"post-registration-operation-{operation_id}.plan.json",
                f"post-registration-operation-{operation_id}.result.json",
            }
        )
        completed_results.append(
            _verify_persisted_completed_operation(
                root=root,
                state=state,
                post=post,
                historical_posts=historical_posts,
                verified_history=verified_history,
                operation=operation_by_id[operation_id],
                expected_overlay_controller_sha256=expected_overlay_controller_sha256,
                expected_post_registration_controller_sha256=(
                    expected_post_registration_controller_sha256
                ),
                authority=authority,
            )
        )

    planned_name = post.get("planned_operation_file")
    planned_sha256 = post.get("planned_operation_sha256")
    if (planned_name is None) != (planned_sha256 is None):
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_EVIDENCE_INVALID")

    if terminal_phase in {
        "POST_REGISTRATION_TECHNICAL_QA_PASSED",
        "POST_REGISTRATION_CONTENT_REJECTED",
    }:
        _verify_operation_record_inventory(
            root=root,
            expected_names=expected_operation_record_names,
        )
        if planned_name is not None or set(completed) != set(operation_by_id):
            raise PostRegistrationError("POST_REGISTRATION_TERMINAL_EVIDENCE_INCOMPLETE")
        reason = _qa_reason(completed_results)
        if (
            terminal_phase == "POST_REGISTRATION_TECHNICAL_QA_PASSED"
            and (
                reason is not None
                or terminal_reason_code != "POST_REGISTRATION_TECHNICAL_QA_ALL_V01_V03_GATES_PASS"
            )
        ) or (
            terminal_phase == "POST_REGISTRATION_CONTENT_REJECTED"
            and (reason is None or terminal_reason_code != reason)
        ):
            raise PostRegistrationError("POST_REGISTRATION_TERMINAL_QA_DISPOSITION_INVALID")
        return

    if (
        terminal_phase
        not in {
            "POST_REGISTRATION_INFRA_FAILURE",
            "POST_REGISTRATION_UNKNOWN_M3_OUTCOME",
        }
        or not isinstance(planned_name, str)
        or not isinstance(planned_sha256, str)
    ):
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_EVIDENCE_INVALID")
    plan_path = _record_path(root, planned_name)
    plan = _read_canonical_json(plan_path, "POST_REGISTRATION_PLAN_NOT_CANONICAL")
    operation_id = plan.get("operation_id")
    if not isinstance(operation_id, str) or operation_id not in operation_by_id:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_OPERATION_INVALID")
    operation, capability = _verify_persisted_operation_plan(
        root=root,
        state=state,
        post=post,
        historical_posts=historical_posts,
        plan=plan,
        operation=operation_by_id[operation_id],
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
        authority=authority,
    )
    if _overlay.sha256_file(plan_path) != planned_sha256:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_DIGEST_MISMATCH")
    expected_operation_record_names.add(plan_path.name)
    result_path = _record_path(
        root, f"post-registration-operation-{operation['operation_id']}.result.json"
    )
    if terminal_phase == "POST_REGISTRATION_UNKNOWN_M3_OUTCOME":
        _verify_operation_record_inventory(
            root=root,
            expected_names=expected_operation_record_names,
        )
        if (
            result_path.exists()
            or result_path.is_symlink()
            or terminal_reason_code
            not in {
                "POST_REGISTRATION_M3_PLAN_WITHOUT_RESULT",
                "POST_REGISTRATION_M3_EXECUTOR_RETURN_NOT_DURABLE",
            }
        ):
            raise PostRegistrationError("POST_REGISTRATION_UNKNOWN_EVIDENCE_INVALID")
        return
    if not result_path.exists() or result_path.is_symlink():
        raise PostRegistrationError("POST_REGISTRATION_INFRA_FAILURE_EVIDENCE_MISSING")
    expected_operation_record_names.add(result_path.name)
    _verify_operation_record_inventory(
        root=root,
        expected_names=expected_operation_record_names,
    )
    result = _read_canonical_json(result_path, "POST_REGISTRATION_FAILURE_RESULT_NOT_CANONICAL")
    _verify_operation_failure_record(
        result=result,
        plan=plan,
        operation=operation,
        capability=capability,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
    )
    if result.get("reason_code") != terminal_reason_code:
        raise PostRegistrationError("POST_REGISTRATION_INFRA_FAILURE_REASON_INVALID")
    if (
        post.get("failure_result_file") != result_path.name
        or post.get("failure_result_sha256") != _overlay.sha256_file(result_path)
        or post.get("failure_reason_code") != terminal_reason_code
    ):
        raise PostRegistrationError("POST_REGISTRATION_INFRA_FAILURE_EVIDENCE_INVALID")
    _require_historical_post_anchor(
        historical_posts,
        {
            "failure_result_file": result_path.name,
            "failure_result_sha256": _overlay.sha256_file(result_path),
            "failure_reason_code": terminal_reason_code,
        },
        "POST_REGISTRATION_INFRA_FAILURE_HISTORY_MISSING",
    )


def _verify_attempt_evidence(
    *,
    root: Path,
    state: Mapping[str, Any],
    post: Mapping[str, Any],
    historical_posts: tuple[Mapping[str, Any], ...],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_worktree_root: Path,
    authority: _ExternalVerificationAuthority,
) -> None:
    registration = state.get("output_registration")
    if not isinstance(registration, dict):
        raise PostRegistrationError("POST_REGISTRATION_ATTEMPT_BINDING_INVALID")
    output_id = _required_text(
        registration, "output_opaque_id", "POST_REGISTRATION_OUTPUT_ID_MISSING"
    )
    attempt_name = _required_text(post, "attempt_file", "POST_REGISTRATION_ATTEMPT_MISSING")
    if attempt_name != f"post-registration-attempt-{output_id}.json":
        raise PostRegistrationError("POST_REGISTRATION_ATTEMPT_BINDING_INVALID")
    attempt_path = _record_path(root, attempt_name)
    if attempt_path.is_symlink():
        raise PostRegistrationError("POST_REGISTRATION_ATTEMPT_SYMLINK_REJECTED")
    attempt = _read_canonical_json(attempt_path, "POST_REGISTRATION_ATTEMPT_NOT_CANONICAL")
    if _overlay.sha256_file(attempt_path) != post.get("attempt_sha256"):
        raise PostRegistrationError("POST_REGISTRATION_ATTEMPT_DIGEST_MISMATCH")
    record_file = _required_text(
        registration, "record_file", "POST_REGISTRATION_ATTEMPT_BINDING_INVALID"
    )
    registration_record_path = _record_path(root, record_file)
    registration_record = _read_canonical_json(
        registration_record_path, "POST_REGISTRATION_REGISTRATION_RECORD_NOT_CANONICAL"
    )
    registration_receipt_file = _required_text(
        registration,
        "registration_receipt_file",
        "POST_REGISTRATION_ATTEMPT_BINDING_INVALID",
    )
    registration_receipt_path = _record_path(root, registration_receipt_file)
    actual_registration_record_sha256 = _overlay.sha256_file(registration_record_path)
    actual_registration_receipt_sha256 = _overlay.sha256_file(registration_receipt_path)
    expected = {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "record_kind": "POST_REGISTRATION_ATTEMPT",
        "module_sha256": expected_post_registration_controller_sha256,
        "output_opaque_id": output_id,
        "overlay_tip": attempt.get("overlay_tip"),
        "registration_receipt_sha256": registration.get("registration_receipt_sha256"),
        "registration_record_sha256": registration.get("record_sha256"),
        "source_sha256": registration_record.get("source_sha256"),
        "source_byte_size": registration_record.get("byte_size"),
        "source_media_type": registration_record.get("media_type"),
        "db_mutations": 0,
        "provider_calls_added": 0,
        "admission": 0,
    }
    overlay_tip = attempt.get("overlay_tip")
    if not isinstance(overlay_tip, dict):
        raise PostRegistrationError("POST_REGISTRATION_ATTEMPT_BINDING_INVALID")
    expected_registered_tip = {
        "receipt_sha256": authority.registered_receipt_sha256,
        "state_sha256": authority.registered_state_sha256,
        "event_sha256": authority.registered_event_sha256,
        "controller_sha256": expected_overlay_controller_sha256,
    }
    if overlay_tip != expected_registered_tip:
        raise PostRegistrationError("POST_REGISTRATION_REGISTERED_TIP_MISMATCH")
    registered_receipt_path = _verify_tip_in_root(
        root=root,
        tip=overlay_tip,
        maximum_sequence=cast(int, state["sequence"]),
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    registered_context = _current_context(
        receipt_path=registered_receipt_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    registered_state = cast(dict[str, Any], registered_context["state"])
    registered_registration = registered_state.get("output_registration")
    replay = _overlay.verify_registration_before_decode(
        registered_receipt_path,
        expected_controller_sha256=expected_overlay_controller_sha256,
        project_worktree_root=project_worktree_root,
    )
    if (
        not isinstance(registered_registration, dict)
        or registration != registered_registration
        or registered_state.get("output_registration_attempt")
        != state.get("output_registration_attempt")
        or registered_state.get("current_action_id") != state.get("current_action_id")
        or registered_state.get("current_ordinal") != state.get("current_ordinal")
        or registered_state.get("overlay_output_id") != state.get("overlay_output_id")
        or actual_registration_record_sha256 != registration.get("record_sha256")
        or actual_registration_record_sha256 != attempt.get("registration_record_sha256")
        or actual_registration_receipt_sha256 != registration.get("registration_receipt_sha256")
        or actual_registration_receipt_sha256 != attempt.get("registration_receipt_sha256")
        or replay.get("output_opaque_id") != output_id
        or replay.get("source_sha256") != attempt.get("source_sha256")
        or replay.get("byte_size") != attempt.get("source_byte_size")
        or replay.get("media_type") != attempt.get("source_media_type")
    ):
        raise PostRegistrationError("POST_REGISTRATION_REGISTRATION_REPLAY_INVALID")
    if attempt != expected:
        raise PostRegistrationError("POST_REGISTRATION_ATTEMPT_BINDING_INVALID")
    _require_historical_post_anchor(
        historical_posts,
        {"attempt_file": attempt_name, "attempt_sha256": post.get("attempt_sha256")},
        "POST_REGISTRATION_ATTEMPT_HISTORY_MISSING",
    )


def _verified_receipt_history(
    *,
    root: Path,
    maximum_sequence: int,
    expected_overlay_controller_sha256: str,
) -> _VerifiedReceiptHistory:
    """Read each chain-bound receipt once for terminal evidence anchors."""
    historical: list[Mapping[str, Any]] = []
    paths_by_tip: dict[tuple[str, str, str, str], Path] = {}
    for sequence in range(maximum_sequence + 1):
        receipt_path = _overlay._safe_child(root, _overlay._receipt_name(sequence))
        if receipt_path.is_symlink():
            raise PostRegistrationError("POST_REGISTRATION_RECEIPT_SYMLINK_REJECTED")
        if not receipt_path.exists():
            raise PostRegistrationError("POST_REGISTRATION_HISTORY_RECEIPT_MISSING")
        receipt, _event, historical_state = _overlay._verify_receipt(
            receipt_path,
            expected_controller_sha256=expected_overlay_controller_sha256,
        )
        historical_post = historical_state.get("post_registration")
        if isinstance(historical_post, dict):
            historical.append(historical_post)
        key = _tip_key(_tip_payload(receipt))
        if key in paths_by_tip:
            raise PostRegistrationError("POST_REGISTRATION_HISTORY_TIP_DUPLICATE")
        paths_by_tip[key] = receipt_path
    return _VerifiedReceiptHistory(
        paths_by_tip=MappingProxyType(paths_by_tip),
        post_states=tuple(historical),
    )


def _require_historical_post_anchor(
    historical_posts: tuple[Mapping[str, Any], ...],
    expected: Mapping[str, object],
    code: str,
) -> None:
    if not any(
        all(post.get(key) == value for key, value in expected.items()) for post in historical_posts
    ):
        raise PostRegistrationError(code)


def _verify_operation_record_inventory(*, root: Path, expected_names: set[str]) -> None:
    records_dir = root / "records"
    if records_dir.is_symlink() or not records_dir.is_dir():
        raise PostRegistrationError("POST_REGISTRATION_OPERATION_RECORD_INVENTORY_INVALID")
    try:
        actual_names = {
            entry.name
            for entry in records_dir.iterdir()
            if entry.name.startswith("post-registration-operation-")
        }
    except OSError:
        raise PostRegistrationError(
            "POST_REGISTRATION_OPERATION_RECORD_INVENTORY_INVALID"
        ) from None
    if actual_names != expected_names:
        raise PostRegistrationError("POST_REGISTRATION_OPERATION_RECORD_INVENTORY_INVALID")


def _verify_normalization_evidence(
    *,
    root: Path,
    post: Mapping[str, Any],
    historical_posts: tuple[Mapping[str, Any], ...],
    expected_post_registration_controller_sha256: str,
) -> None:
    if post.get("decode_performed") is not True:
        raise PostRegistrationError("POST_REGISTRATION_NORMALIZATION_EVIDENCE_INVALID")
    normalization_name = _required_text(
        post, "normalization_file", "POST_REGISTRATION_NORMALIZATION_MISSING"
    )
    normalized_name = _required_text(
        post, "normalized_file", "POST_REGISTRATION_NORMALIZED_FILE_MISSING"
    )
    normalization_path = _record_path(root, normalization_name)
    normalized_path = _record_path(root, normalized_name)
    if normalization_path.is_symlink() or normalized_path.is_symlink():
        raise PostRegistrationError("POST_REGISTRATION_NORMALIZATION_SYMLINK_REJECTED")
    normalization = _read_canonical_json(
        normalization_path, "POST_REGISTRATION_NORMALIZATION_NOT_CANONICAL"
    )
    normalized_bytes = _overlay._read_plain_file_bytes(normalized_path)
    normalized_sha256 = _overlay.sha256_bytes(normalized_bytes)
    if (
        _overlay.sha256_file(normalization_path) != post.get("normalization_sha256")
        or normalized_sha256 != post.get("normalized_sha256")
        or normalization.get("normalized_file") != normalized_name
        or normalization.get("normalized_sha256") != normalized_sha256
        or normalization.get("normalized_byte_size") != len(normalized_bytes)
        or normalization.get("normalized_media_type") != "image/jpeg"
        or normalization.get("module_sha256") != expected_post_registration_controller_sha256
        or normalization.get("attempt_sha256") != post.get("attempt_sha256")
        or normalization.get("second_decode") != "PASS"
        or normalization.get("db_mutations") != 0
        or normalization.get("provider_calls_added") != 0
        or normalization.get("admission") != 0
    ):
        raise PostRegistrationError("POST_REGISTRATION_NORMALIZATION_EVIDENCE_INVALID")
    if (
        set(normalization)
        != {
            "schema_version",
            "record_kind",
            "module_sha256",
            "attempt_sha256",
            "source_sha256",
            "normalized_file",
            "normalized_sha256",
            "normalized_byte_size",
            "normalized_media_type",
            "width",
            "height",
            "sanitizer_version",
            "sanitizer_config_sha256",
            "second_decode",
            "db_mutations",
            "provider_calls_added",
            "admission",
        }
        or normalization.get("schema_version") != POST_REGISTRATION_SCHEMA
        or normalization.get("record_kind") != "NORMALIZATION"
    ):
        raise PostRegistrationError("POST_REGISTRATION_NORMALIZATION_EVIDENCE_INVALID")
    decode_canonical_rgb_image(
        normalized_bytes,
        expected_width=cast(int, normalization["width"]),
        expected_height=cast(int, normalization["height"]),
    )
    _require_historical_post_anchor(
        historical_posts,
        {
            "normalization_file": normalization_name,
            "normalization_sha256": post.get("normalization_sha256"),
            "normalized_file": normalized_name,
            "normalized_sha256": normalized_sha256,
        },
        "POST_REGISTRATION_NORMALIZATION_HISTORY_MISSING",
    )


def _capability_from_persisted_payload(value: object) -> PrivateVisionCapabilityBinding:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "capability_id",
            "platform",
            "runtime_sha256",
            "model_sha256",
            "manifest_version",
            "manifest_sha256",
            "qa_policy_version",
            "qa_policy_sha256",
            "zero_egress_evidence_id",
            "zero_egress_evidence_sha256",
            "approved_scope",
        }
        or value.get("platform") not in _PLATFORMS
    ):
        raise PostRegistrationError("POST_REGISTRATION_CAPABILITY_BINDING_INVALID")
    platform = cast(
        Literal["linux_x86_64_network_none", "windows_amd64_process_specific_outbound_deny"],
        value["platform"],
    )
    capability = PrivateVisionCapabilityBinding(
        capability_id=_required_text(
            value, "capability_id", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
        platform=platform,
        runtime_sha256=_required_text(
            value, "runtime_sha256", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
        model_sha256=_required_text(
            value, "model_sha256", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
        manifest_version=_required_text(
            value, "manifest_version", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
        manifest_sha256=_required_text(
            value, "manifest_sha256", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
        qa_policy_version=_required_text(
            value, "qa_policy_version", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
        qa_policy_sha256=_required_text(
            value, "qa_policy_sha256", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
        zero_egress_evidence_id=_required_text(
            value, "zero_egress_evidence_id", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
        zero_egress_evidence_sha256=_required_text(
            value, "zero_egress_evidence_sha256", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
        approved_scope=_required_text(
            value, "approved_scope", "POST_REGISTRATION_CAPABILITY_BINDING_INVALID"
        ),
    )
    if (
        capability.runtime_sha256 != RUNTIME_SHA256_BY_PLATFORM[platform]
        or capability.model_sha256 != MODEL_SHA256
        or capability.manifest_version != MANIFEST_VERSION
        or capability.manifest_sha256 != MANIFEST_SHA256
        or capability.qa_policy_version != QA_POLICY_VERSION
        or capability.qa_policy_sha256 != QA_POLICY_SHA256
        or capability.approved_scope != APPROVED_SCOPE
    ):
        raise PostRegistrationError("POST_REGISTRATION_CAPABILITY_BINDING_INVALID")
    _overlay._validate_opaque_id(capability.capability_id, "POST_REGISTRATION_CAPABILITY_ID")
    _overlay._validate_opaque_id(
        capability.zero_egress_evidence_id, "POST_REGISTRATION_EGRESS_EVIDENCE_ID"
    )
    _validate_lower_digest(
        capability.zero_egress_evidence_sha256, "POST_REGISTRATION_ZERO_EGRESS_EVIDENCE_SHA256"
    )
    return capability


def _verify_persisted_operation_plan(
    *,
    root: Path,
    state: Mapping[str, Any],
    post: Mapping[str, Any],
    historical_posts: tuple[Mapping[str, Any], ...],
    plan: Mapping[str, Any],
    operation: Mapping[str, Any],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    authority: _ExternalVerificationAuthority,
    verified_history: _VerifiedReceiptHistory | None = None,
) -> tuple[Mapping[str, Any], PrivateVisionCapabilityBinding]:
    capability = _capability_from_persisted_payload(plan.get("capability"))
    if capability.platform != operation["platform"]:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_BINDING_INVALID")
    overlay_tip = plan.get("overlay_tip")
    if not isinstance(overlay_tip, dict):
        raise PostRegistrationError("POST_REGISTRATION_PLAN_TIP_INVALID")
    _verify_tip_in_root(
        root=root,
        tip=overlay_tip,
        maximum_sequence=cast(int, state["sequence"]),
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        verified_history=verified_history,
    )
    expected = _operation_plan_payload(
        state=state,
        operation=operation,
        capability=capability,
        capability_authority_sha256=_capability_authority_sha256(
            capability,
            authority.capability_authority_sha256_by_platform,
        ),
        overlay_tip=overlay_tip,
        module_sha256=expected_post_registration_controller_sha256,
    )
    if plan != expected:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_BINDING_INVALID")
    plan_name = f"post-registration-operation-{operation['operation_id']}.plan.json"
    _require_historical_post_anchor(
        historical_posts,
        {
            "planned_operation_file": plan_name,
            "planned_operation_sha256": _overlay.sha256_bytes(_overlay.canonical_json_bytes(plan)),
        },
        "POST_REGISTRATION_PLAN_HISTORY_MISSING",
    )
    return operation, capability


def _verify_persisted_completed_operation(
    *,
    root: Path,
    state: Mapping[str, Any],
    post: Mapping[str, Any],
    historical_posts: tuple[Mapping[str, Any], ...],
    verified_history: _VerifiedReceiptHistory,
    operation: Mapping[str, Any],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    authority: _ExternalVerificationAuthority,
) -> dict[str, Any]:
    operation_id = cast(str, operation["operation_id"])
    plan_path = _record_path(root, f"post-registration-operation-{operation_id}.plan.json")
    plan = _read_canonical_json(plan_path, "POST_REGISTRATION_PLAN_NOT_CANONICAL")
    _operation, capability = _verify_persisted_operation_plan(
        root=root,
        state=state,
        post=post,
        historical_posts=historical_posts,
        verified_history=verified_history,
        plan=plan,
        operation=operation,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
        authority=authority,
    )
    result_path = _record_path(root, f"post-registration-operation-{operation_id}.result.json")
    result = _read_canonical_json(result_path, "POST_REGISTRATION_RESULT_NOT_CANONICAL")
    _verify_operation_result_record(
        result=result,
        plan=plan,
        operation=_operation,
        capability=capability,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
    )
    _require_historical_post_anchor(
        historical_posts,
        {
            "last_operation_result_file": result_path.name,
            "last_operation_result_sha256": _overlay.sha256_file(result_path),
        },
        "POST_REGISTRATION_RESULT_HISTORY_MISSING",
    )
    return result


def _transition(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    phase: str,
    event_type: str,
    reason_code: str,
    post: Mapping[str, Any],
    expected_overlay_controller_sha256: str,
    timestamp: str,
) -> dict[str, Any]:
    receipt = context["receipt"]
    state = context["state"]
    counters = dict(_counters(state))
    counters["active_calls"] = 0
    _overlay._validate_counters(counters)
    sequence = cast(int, receipt["sequence"]) + 1
    event = {
        "schema_version": _overlay.EVENT_SCHEMA,
        "overlay_output_id": state["overlay_output_id"],
        "sequence": sequence,
        "event_type": event_type,
        "timestamp": timestamp,
        "previous_event_sha256": receipt["event_sha256"],
        "action_id": state.get("current_action_id"),
        "request_ordinal": state.get("current_ordinal"),
        "reason_code": reason_code,
        "post_registration_module_sha256": post["module_sha256"],
    }
    new_state = dict(state)
    new_state.update(
        {
            "sequence": sequence,
            "phase": phase,
            "timestamp": timestamp,
            "previous_state_sha256": receipt["state_sha256"],
            "last_event_sha256": _overlay.sha256_bytes(_overlay.canonical_json_bytes(event)),
            "counters": counters,
            "decode_authorized": False,
            "hard_stop": phase
            in {"POST_REGISTRATION_INFRA_FAILURE", "POST_REGISTRATION_UNKNOWN_M3_OUTCOME"},
            "post_registration": dict(post),
        }
    )
    if receipt_path != _context_path(context):
        raise PostRegistrationError("POST_REGISTRATION_TRANSITION_STALE_CONTEXT")
    handle = _overlay._commit_transition(
        root=receipt_path.parent,
        sequence=sequence,
        controller_sha256=expected_overlay_controller_sha256,
        event=event,
        state=new_state,
        previous_receipt=_overlay._previous_receipt_binding(_context_path(context), receipt),
    )
    return _current_context(
        receipt_path=handle.receipt_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )


def _commit_successor(
    *,
    terminal_receipt_path: Path,
    terminal_context: Mapping[str, Mapping[str, Any]],
    terminal: PostRegistrationHandle,
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    authority: _ExternalVerificationAuthority,
    project_worktree_root: Path,
    successor_root: Path,
    successor_overlay_output_id: str,
    timestamp: str,
) -> PostRegistrationHandle:
    parent = terminal_receipt_path.parent.parent
    locked_terminal = _verify_post_registration_terminal_with_authority(
        receipt_path=terminal_receipt_path,
        terminal_tip=_TerminalTipAuthority(
            receipt_sha256=terminal.receipt_sha256,
            state_sha256=terminal.state_sha256,
            event_sha256=terminal.event_sha256,
        ),
        authority=authority,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
        project_worktree_root=project_worktree_root,
    )
    locked_context = _current_context(
        receipt_path=terminal_receipt_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    if (
        locked_terminal != terminal
        or locked_context["receipt"] != terminal_context["receipt"]
        or locked_context["event"] != terminal_context["event"]
        or locked_context["state"] != terminal_context["state"]
    ):
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_PREDECESSOR_CHANGED_UNDER_LEASE")
    existing_receipt = successor_root / _overlay._receipt_name(0)
    if existing_receipt.exists() or existing_receipt.is_symlink():
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_ALREADY_COMMITTED")
    parent_sha256 = _overlay._validate_project_local_private_parent(
        project_worktree_root=project_worktree_root,
        allowed_parent=parent,
    )
    intent_path, intent_sha256, effective_timestamp = _create_or_verify_successor_intent(
        terminal=terminal,
        terminal_context=terminal_context,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
        project_private_parent_sha256=parent_sha256,
        successor_root=successor_root,
        successor_overlay_output_id=successor_overlay_output_id,
        timestamp=timestamp,
    )
    intent = _read_canonical_json(
        intent_path,
        "POST_REGISTRATION_SUCCESSOR_INTENT_NOT_CANONICAL",
    )
    intent_id = cast(str, intent["rollover_intent_id"])
    _overlay._create_or_verify_plain_directory(successor_root / "staging")
    _overlay._create_or_verify_plain_directory(successor_root / "records")
    _overlay._require_empty_rollover_directory_v2(successor_root / "staging")
    _overlay._require_empty_rollover_directory_v2(successor_root / "records")
    predecessor_binding = _successor_predecessor_binding(
        terminal=terminal,
        terminal_context=terminal_context,
        project_private_parent_sha256=parent_sha256,
    )
    cross_root = {
        **predecessor_binding,
        "rollover_intent_id": intent_id,
        "rollover_intent_file": intent_path.name,
        "rollover_intent_sha256": intent_sha256,
    }
    event = {
        "schema_version": _overlay.EVENT_SCHEMA,
        "overlay_output_id": successor_overlay_output_id,
        "sequence": 0,
        "event_type": "POST_REGISTRATION_SUCCESSOR_READY",
        "timestamp": effective_timestamp,
        "previous_event_sha256": None,
        "action_id": None,
        "request_ordinal": None,
        "reason_code": _successor_reason_code(terminal.phase),
        "post_registration_module_sha256": expected_post_registration_controller_sha256,
        "rollover_predecessor": cross_root,
    }
    state = cast(dict[str, Any], terminal_context["state"])
    successor_state = {
        "schema_version": _overlay.STATE_SCHEMA,
        "overlay_schema_version": _overlay.OVERLAY_SCHEMA,
        "overlay_output_id": successor_overlay_output_id,
        "sequence": 0,
        "phase": "READY",
        "timestamp": effective_timestamp,
        "previous_state_sha256": None,
        "last_event_sha256": _overlay.sha256_bytes(_overlay.canonical_json_bytes(event)),
        "binding": dict(cast(dict[str, Any], state["binding"])),
        "rollover_predecessor": cross_root,
        "counters": dict(_counters(state)),
        "next_unused_ordinal": state["next_unused_ordinal"],
        "current_action_id": None,
        "current_ordinal": None,
        "expected_output_opaque_id": None,
        "returned_output_binding": None,
        "output_registration_attempt": None,
        "output_registration": None,
        "decode_authorized": False,
        "hard_stop": False,
        "post_registration_rollover": intent,
    }
    handle = _overlay._commit_transition(
        root=successor_root,
        sequence=0,
        controller_sha256=expected_overlay_controller_sha256,
        event=event,
        state=successor_state,
        previous_receipt=None,
    )
    return _verify_post_registration_successor_unleased(
        successor_receipt_path=handle.receipt_path,
        predecessor_receipt_path=terminal_receipt_path,
        expected_predecessor_receipt_sha256=terminal.receipt_sha256,
        expected_predecessor_state_sha256=terminal.state_sha256,
        expected_predecessor_event_sha256=cast(str, terminal_context["receipt"]["event_sha256"]),
        predecessor_tip=_TerminalTipAuthority(
            receipt_sha256=terminal.receipt_sha256,
            state_sha256=terminal.state_sha256,
            event_sha256=terminal.event_sha256,
        ),
        authority=authority,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=expected_post_registration_controller_sha256,
        project_worktree_root=project_worktree_root,
    )


def _successor_terminal_allowed(*, phase: str, next_unused_ordinal: object) -> bool:
    if phase == "POST_REGISTRATION_TECHNICAL_QA_PASSED":
        return True
    return (
        phase == "POST_REGISTRATION_CONTENT_REJECTED"
        and isinstance(next_unused_ordinal, str)
        and next_unused_ordinal != "CAL-REQ-005"
    )


def _successor_reason_code(phase: str) -> str:
    if phase == "POST_REGISTRATION_TECHNICAL_QA_PASSED":
        return "POST_REGISTRATION_TECHNICAL_PASS_SUCCESSOR_ZERO_WORK"
    if phase == "POST_REGISTRATION_CONTENT_REJECTED":
        return "POST_REGISTRATION_CONTENT_REJECTION_SUCCESSOR_ZERO_WORK"
    raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_TERMINAL_NOT_AUTHORIZED")


def _successor_intent_id(
    *,
    terminal: PostRegistrationHandle,
    expected_post_registration_controller_sha256: str,
) -> str:
    value = (
        "ROLLOVER-V2-CC06-"
        + _overlay.sha256_bytes(
            (
                POST_REGISTRATION_ROLLOVER_CONTRACT
                + "\n"
                + expected_post_registration_controller_sha256
                + "\n"
                + terminal.receipt_sha256
            ).encode("ascii")
        ).upper()
    )
    _overlay._validate_opaque_id(value, "POST_REGISTRATION_ROLLOVER_INTENT_ID")
    return value


def _successor_intent_path(
    *,
    parent: Path,
    terminal: PostRegistrationHandle,
    expected_post_registration_controller_sha256: str,
) -> Path:
    intent_id = _successor_intent_id(
        terminal=terminal,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
    )
    return _overlay._safe_child(parent, f"rollover-v2-intent-{intent_id}.json")


def _create_or_verify_successor_intent(
    *,
    terminal: PostRegistrationHandle,
    terminal_context: Mapping[str, Any],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_private_parent_sha256: str,
    successor_root: Path,
    successor_overlay_output_id: str,
    timestamp: str,
) -> tuple[Path, str, str]:
    intent_path = _successor_intent_path(
        parent=successor_root.parent,
        terminal=terminal,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
    )
    effective_timestamp = timestamp
    if intent_path.exists() or intent_path.is_symlink():
        existing_intent = _read_canonical_json(
            intent_path,
            "POST_REGISTRATION_SUCCESSOR_INTENT_NOT_CANONICAL",
        )
        effective_timestamp = _required_text(
            existing_intent,
            "timestamp",
            "POST_REGISTRATION_SUCCESSOR_INTENT_TIMESTAMP_INVALID",
        )
        _validate_timestamp(effective_timestamp)
        intent = _successor_intent_payload(
            terminal=terminal,
            terminal_context=terminal_context,
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
            project_private_parent_sha256=project_private_parent_sha256,
            successor_root=successor_root,
            successor_overlay_output_id=successor_overlay_output_id,
            timestamp=effective_timestamp,
        )
        if existing_intent != intent:
            raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_INTENT_BINDING_INVALID")
        return intent_path, _overlay.sha256_file(intent_path), effective_timestamp
    intent = _successor_intent_payload(
        terminal=terminal,
        terminal_context=terminal_context,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
        project_private_parent_sha256=project_private_parent_sha256,
        successor_root=successor_root,
        successor_overlay_output_id=successor_overlay_output_id,
        timestamp=effective_timestamp,
    )
    intent_sha256, _ = _overlay._write_json_create_or_verify_exact(intent_path, intent)
    return intent_path, intent_sha256, effective_timestamp


def _successor_predecessor_binding(
    *,
    terminal: PostRegistrationHandle,
    terminal_context: Mapping[str, Any],
    project_private_parent_sha256: str,
) -> dict[str, Any]:
    receipt = cast(dict[str, Any], terminal_context["receipt"])
    state = cast(dict[str, Any], terminal_context["state"])
    event = cast(dict[str, Any], terminal_context["event"])
    return {
        "predecessor_overlay_output_id": state["overlay_output_id"],
        "predecessor_receipt_sha256": terminal.receipt_sha256,
        "predecessor_state_sha256": terminal.state_sha256,
        "predecessor_event_sha256": receipt["event_sha256"],
        "predecessor_checkpoint_sha256": terminal.checkpoint_sha256,
        "predecessor_sequence": terminal.sequence,
        "predecessor_phase": terminal.phase,
        "predecessor_reason_code": event["reason_code"],
        "predecessor_next_unused_ordinal": state["next_unused_ordinal"],
        "predecessor_counters": dict(_counters(state)),
        "project_private_parent_sha256": project_private_parent_sha256,
    }


def _successor_intent_payload(
    *,
    terminal: PostRegistrationHandle,
    terminal_context: Mapping[str, Any],
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    project_private_parent_sha256: str,
    successor_root: Path,
    successor_overlay_output_id: str,
    timestamp: str,
) -> dict[str, Any]:
    predecessor = _successor_predecessor_binding(
        terminal=terminal,
        terminal_context=terminal_context,
        project_private_parent_sha256=project_private_parent_sha256,
    )
    state = cast(dict[str, Any], terminal_context["state"])
    return {
        "schema_version": POST_REGISTRATION_ROLLOVER_SCHEMA,
        "contract": POST_REGISTRATION_ROLLOVER_CONTRACT,
        "rollover_intent_id": _successor_intent_id(
            terminal=terminal,
            expected_post_registration_controller_sha256=(
                expected_post_registration_controller_sha256
            ),
        ),
        "overlay_controller_sha256": expected_overlay_controller_sha256,
        "module_sha256": expected_post_registration_controller_sha256,
        "successor_overlay_output_id": successor_overlay_output_id,
        "successor_root_name": successor_root.name,
        "predecessor": predecessor,
        "derived_ledger": {
            "next_unused_ordinal": state["next_unused_ordinal"],
            "counters": dict(_counters(state)),
        },
        "project_private_parent_sha256": project_private_parent_sha256,
        "create_mode": "CREATE_NEW_OR_RECOVER_EXACT_PARTIAL_ROOT",
        "generation_calls": 0,
        "ordinals_consumed": 0,
        "decode_performed": False,
        "dimensions_read": False,
        "db_mutations": 0,
        "provider_calls_added": 0,
        "admission": 0,
        "timestamp": timestamp,
    }


def _attempt_payload(
    *,
    root: Path,
    receipt: Mapping[str, Any],
    state: Mapping[str, Any],
    output_id: str,
    module_sha256: str,
) -> dict[str, Any]:
    registration = cast(dict[str, Any], state["output_registration"])
    result = {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "record_kind": "POST_REGISTRATION_ATTEMPT",
        "module_sha256": module_sha256,
        "output_opaque_id": output_id,
        "overlay_tip": _tip_payload(receipt),
        "registration_receipt_sha256": registration["registration_receipt_sha256"],
        "registration_record_sha256": registration["record_sha256"],
        "source_sha256": None,
        "source_byte_size": None,
        "source_media_type": None,
        "db_mutations": 0,
        "provider_calls_added": 0,
        "admission": 0,
    }
    registration_record = _overlay._read_json(
        _overlay._safe_child(root / "records", cast(str, registration["record_file"]))
    )
    result.update(
        {
            "source_sha256": registration_record["source_sha256"],
            "source_byte_size": registration_record["byte_size"],
            "source_media_type": registration_record["media_type"],
        }
    )
    return result


def _normalization_payload(
    *,
    attempt: Mapping[str, Any],
    attempt_sha256: str,
    normalized: SanitizedImage,
    normalized_name: str,
    normalized_sha256: str,
    module_sha256: str,
) -> dict[str, Any]:
    config_digest = _overlay.sha256_bytes(
        _overlay.canonical_json_bytes(
            {
                "version": DEFAULT_IMAGE_SANITIZER_CONFIG.version,
                "max_input_bytes": DEFAULT_IMAGE_SANITIZER_CONFIG.max_input_bytes,
                "max_output_bytes": DEFAULT_IMAGE_SANITIZER_CONFIG.max_output_bytes,
                "min_edge_pixels": DEFAULT_IMAGE_SANITIZER_CONFIG.min_edge_pixels,
                "max_edge_pixels": DEFAULT_IMAGE_SANITIZER_CONFIG.max_edge_pixels,
                "max_pixel_count": DEFAULT_IMAGE_SANITIZER_CONFIG.max_pixel_count,
                "jpeg_quality_ladder": list(DEFAULT_IMAGE_SANITIZER_CONFIG.jpeg_quality_ladder),
            }
        )
    )
    return {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "record_kind": "NORMALIZATION",
        "module_sha256": module_sha256,
        "attempt_sha256": attempt_sha256,
        "source_sha256": attempt["source_sha256"],
        "normalized_file": normalized_name,
        "normalized_sha256": normalized_sha256,
        "normalized_byte_size": normalized.byte_size,
        "normalized_media_type": normalized.content_type,
        "width": normalized.width,
        "height": normalized.height,
        "sanitizer_version": normalized.version,
        "sanitizer_config_sha256": config_digest,
        "second_decode": "PASS",
        "db_mutations": 0,
        "provider_calls_added": 0,
        "admission": 0,
    }


def _vision_request(
    root: Path,
    state: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> SyntheticVisionRequest:
    post = _post_state(state)
    normalized_path = _record_path(
        root,
        _required_text(
            post,
            "normalized_file",
            "POST_REGISTRATION_NORMALIZED_FILE_MISSING",
        ),
    )
    payload = NormalizedSyntheticImagePayload(
        normalized_asset_reference=_required_text(
            plan,
            "normalized_asset_reference",
            "POST_REGISTRATION_NORMALIZED_REFERENCE_MISSING",
        ),
        content=_overlay._read_plain_file_bytes(normalized_path),
        sha256=cast(str, post["normalized_sha256"]),
        media_type="image/jpeg",
    )
    return SyntheticVisionRequest(
        request_reference=_required_text(
            plan,
            "request_reference",
            "POST_REGISTRATION_REQUEST_REFERENCE_MISSING",
        ),
        normalized_image=payload,
        vision_policy_reference=_required_text(
            plan,
            "vision_policy_reference",
            "POST_REGISTRATION_POLICY_REFERENCE_MISSING",
        ),
    )


def _validate_capabilities(
    capabilities: tuple[PrivateVisionCapabilityBinding, ...],
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
) -> None:
    if (
        type(capabilities) is not tuple
        or len(capabilities) != 2
        or not all(type(item) is PrivateVisionCapabilityBinding for item in capabilities)
    ):
        raise PostRegistrationError("POST_REGISTRATION_CAPABILITY_SET_INVALID")
    if {item.platform for item in capabilities} != set(_PLATFORMS) or set(
        expected_capability_authority_sha256_by_platform
    ) != set(_PLATFORMS):
        raise PostRegistrationError("POST_REGISTRATION_CAPABILITY_SET_INVALID")
    for capability in capabilities:
        _overlay._validate_opaque_id(capability.capability_id, "POST_REGISTRATION_CAPABILITY_ID")
        _overlay._validate_opaque_id(
            capability.zero_egress_evidence_id, "POST_REGISTRATION_EGRESS_EVIDENCE_ID"
        )
        _validate_lower_digest(
            capability.zero_egress_evidence_sha256,
            "POST_REGISTRATION_ZERO_EGRESS_EVIDENCE_SHA256",
        )
        if (
            capability.runtime_sha256 != RUNTIME_SHA256_BY_PLATFORM[capability.platform]
            or capability.model_sha256 != MODEL_SHA256
            or capability.manifest_version != MANIFEST_VERSION
            or capability.manifest_sha256 != MANIFEST_SHA256
            or capability.qa_policy_version != QA_POLICY_VERSION
            or capability.qa_policy_sha256 != QA_POLICY_SHA256
            or capability.approved_scope != APPROVED_SCOPE
        ):
            raise PostRegistrationError("POST_REGISTRATION_CAPABILITY_BINDING_INVALID")
        _capability_authority_sha256(
            capability,
            expected_capability_authority_sha256_by_platform,
        )


def _capability_for(
    capabilities: tuple[PrivateVisionCapabilityBinding, ...], platform: str
) -> PrivateVisionCapabilityBinding:
    for capability in capabilities:
        if capability.platform == platform:
            return capability
    raise PostRegistrationError("POST_REGISTRATION_CAPABILITY_PLATFORM_MISSING")


def _validate_evidence(
    evidence: PrivateVisionOperationEvidence,
    capability: PrivateVisionCapabilityBinding,
    operation: Mapping[str, Any],
    request: SyntheticVisionRequest,
) -> None:
    if (
        type(evidence) is not PrivateVisionOperationEvidence
        or type(evidence.vision_result) is not SyntheticVisionResult
        or evidence.platform != capability.platform
        or evidence.capability_id != capability.capability_id
        or evidence.runtime_sha256 != capability.runtime_sha256
        or evidence.model_sha256 != capability.model_sha256
        or evidence.manifest_version != capability.manifest_version
        or evidence.manifest_sha256 != capability.manifest_sha256
        or evidence.qa_policy_version != capability.qa_policy_version
        or evidence.qa_policy_sha256 != capability.qa_policy_sha256
        or evidence.zero_egress_evidence_id != capability.zero_egress_evidence_id
        or evidence.zero_egress_evidence_sha256 != capability.zero_egress_evidence_sha256
        or evidence.approved_scope != capability.approved_scope
        or evidence.vision_result.request_reference != request.request_reference
        or evidence.vision_result.subject_kind != "synthetic"
    ):
        raise PostRegistrationError("POST_REGISTRATION_OPERATION_EVIDENCE_BINDING_INVALID")
    _validate_port_reference(
        evidence.vision_result.provider_run_reference,
        "POST_REGISTRATION_PROVIDER_RUN_REFERENCE",
    )
    _validate_canonical_vision_result(evidence.vision_result)
    if (
        type(evidence.transformation_matrix) is not tuple
        or len(evidence.transformation_matrix) != 16
        or not all(_is_finite_number(value) for value in evidence.transformation_matrix)
        or not _is_finite_number(evidence.bbox_area)
        or not 0.0 <= float(evidence.bbox_area) <= 1.0
        or not _is_finite_number(evidence.rotation_degrees)
    ):
        raise PostRegistrationError("POST_REGISTRATION_OPERATION_EVIDENCE_NUMERIC_INVALID")


def _result_payload(
    *,
    evidence: PrivateVisionOperationEvidence,
    capability: PrivateVisionCapabilityBinding,
    operation: Mapping[str, Any],
    plan_sha256: str,
    module_sha256: str,
    timestamp: str,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for observation in evidence.vision_result.observations:
        observations.append(
            {
                "observation_reference": observation.observation_reference,
                "landmarks": [
                    {
                        "landmark_code": landmark.landmark_code,
                        "x": landmark.x,
                        "y": landmark.y,
                        "confidence": landmark.confidence,
                    }
                    for landmark in observation.landmarks.landmarks
                ],
                "pose": {
                    "yaw_degrees": observation.pose.yaw_degrees,
                    "pitch_degrees": observation.pose.pitch_degrees,
                    "roll_degrees": observation.pose.roll_degrees,
                    "confidence": observation.pose.confidence,
                },
            }
        )
    return {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "record_kind": "M3_OPERATION_RESULT",
        "module_sha256": module_sha256,
        "operation_id": operation["operation_id"],
        "platform": operation["platform"],
        "repeat_index": operation["repeat_index"],
        "plan_sha256": plan_sha256,
        "capability": _capability_payload(capability),
        "request_reference": evidence.vision_result.request_reference,
        "provider_run_reference": evidence.vision_result.provider_run_reference,
        "safety_policy_reference": evidence.vision_result.safety.policy_reference,
        "safety_outcome": evidence.vision_result.safety.outcome,
        "safety_reason_code": evidence.vision_result.safety.reason_code,
        "observations": observations,
        "transformation_matrix": list(evidence.transformation_matrix),
        "bbox_area": evidence.bbox_area,
        "rotation_degrees": evidence.rotation_degrees,
        "timestamp": timestamp,
        "db_mutations": 0,
        "provider_calls_added": 0,
        "admission": 0,
    }


def _record_operation_failure(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    operation: Mapping[str, Any],
    capability: PrivateVisionCapabilityBinding,
    reason_code: str,
    expected_overlay_controller_sha256: str,
    expected_post_registration_controller_sha256: str,
    timestamp: str,
) -> dict[str, Any]:
    if receipt_path != _context_path(context):
        raise PostRegistrationError("POST_REGISTRATION_FAILURE_RESULT_STALE_CONTEXT")
    if reason_code not in {
        "POST_REGISTRATION_OPERATION_EVIDENCE_BINDING_INVALID",
        "POST_REGISTRATION_VISION_REQUEST_BUILD_FAILED",
    }:
        raise PostRegistrationError("POST_REGISTRATION_FAILURE_REASON_INVALID")
    plan = _planned_operation_record(context)
    payload = {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "record_kind": "M3_OPERATION_FAILURE",
        "module_sha256": expected_post_registration_controller_sha256,
        "operation_id": operation["operation_id"],
        "platform": operation["platform"],
        "repeat_index": operation["repeat_index"],
        "plan_sha256": _overlay.sha256_bytes(_overlay.canonical_json_bytes(plan)),
        "capability": _capability_payload(capability),
        "request_reference": plan["request_reference"],
        "reason_code": reason_code,
        "timestamp": timestamp,
        "db_mutations": 0,
        "provider_calls_added": 0,
        "admission": 0,
    }
    result_path = _record_path(
        receipt_path.parent,
        f"post-registration-operation-{operation['operation_id']}.result.json",
    )
    _overlay._write_json_create_or_verify_exact(result_path, payload)
    return _bind_durable_failure(
        receipt_path=receipt_path,
        context=context,
        result_path=result_path,
        reason_code=reason_code,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        timestamp=timestamp,
    )


def _bind_durable_failure(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    result_path: Path,
    reason_code: str,
    expected_overlay_controller_sha256: str,
    timestamp: str,
) -> dict[str, Any]:
    if reason_code == "POST_REGISTRATION_VISION_REQUEST_BUILD_FAILED":
        event_type = "POST_REGISTRATION_PRE_INVOKE_FAILURE_DURABLE"
        transition_reason_code = "POST_REGISTRATION_PRE_INVOKE_FAILURE_DURABLE_BEFORE_EXECUTOR"
    else:
        event_type = "POST_REGISTRATION_M3_FAILURE_DURABLE"
        transition_reason_code = "POST_REGISTRATION_M3_FAILURE_DURABLE_AFTER_RETURN"
    failed_post = dict(_post_state(cast(Mapping[str, Any], context["state"])))
    failed_post.update(
        {
            "failure_result_file": result_path.name,
            "failure_result_sha256": _overlay.sha256_file(result_path),
            "failure_reason_code": reason_code,
        }
    )
    return _transition(
        receipt_path=receipt_path,
        context=context,
        phase="POST_REGISTRATION_ATTEMPT_BOUND",
        event_type=event_type,
        reason_code=transition_reason_code,
        post=failed_post,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        timestamp=timestamp,
    )


def _planned_operation_record(context: Mapping[str, Any]) -> dict[str, Any]:
    receipt_path = _context_path(context)
    post = _post_state(cast(Mapping[str, Any], context["state"]))
    plan_name = _required_text(
        post,
        "planned_operation_file",
        "POST_REGISTRATION_PLAN_MISSING",
    )
    plan_path = _record_path(receipt_path.parent, plan_name)
    plan = _overlay._read_json(plan_path)
    if _overlay._read_plain_file_bytes(plan_path) != _overlay.canonical_json_bytes(
        plan
    ) or _overlay.sha256_file(plan_path) != post.get("planned_operation_sha256"):
        raise PostRegistrationError("POST_REGISTRATION_PLAN_DIGEST_MISMATCH")
    return plan


def _verify_planned_operation(
    *,
    receipt_path: Path,
    context: Mapping[str, Any],
    capabilities: tuple[PrivateVisionCapabilityBinding, ...],
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
    expected_post_registration_controller_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], PrivateVisionCapabilityBinding]:
    if receipt_path != _context_path(context):
        raise PostRegistrationError("POST_REGISTRATION_PLAN_STALE_CONTEXT")
    _ensure_no_next_receipt(context)
    state = cast(dict[str, Any], context["state"])
    receipt = cast(dict[str, Any], context["receipt"])
    if state.get("phase") != "POST_REGISTRATION_M3_OPERATION_PLANNED":
        raise PostRegistrationError("POST_REGISTRATION_PLAN_STATE_INVALID")
    previous_name = receipt.get("previous_receipt_file")
    if previous_name != _overlay._receipt_name(cast(int, receipt["sequence"]) - 1):
        raise PostRegistrationError("POST_REGISTRATION_PLAN_PREDECESSOR_INVALID")
    previous_path = _overlay._safe_child(receipt_path.parent, cast(str, previous_name))
    previous = _current_context(
        receipt_path=previous_path,
        expected_overlay_controller_sha256=cast(str, receipt["controller_sha256"]),
    )
    previous_state = cast(dict[str, Any], previous["state"])
    operation = _next_operation(previous_state)
    if operation is None:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_OPERATION_INVALID")
    plan = _planned_operation_record(context)
    if any(plan.get(key) != operation[key] for key in ("operation_id", "platform", "repeat_index")):
        raise PostRegistrationError("POST_REGISTRATION_PLAN_OPERATION_INVALID")
    capability = _capability_for(capabilities, cast(str, operation["platform"]))
    expected_plan = _operation_plan_payload(
        state=previous_state,
        operation=operation,
        capability=capability,
        capability_authority_sha256=_capability_authority_sha256(
            capability,
            expected_capability_authority_sha256_by_platform,
        ),
        overlay_tip=_tip_payload(cast(dict[str, Any], previous["receipt"])),
        module_sha256=expected_post_registration_controller_sha256,
    )
    expected_name = f"post-registration-operation-{operation['operation_id']}.plan.json"
    post = _post_state(state)
    previous_post = _post_state(previous_state)
    expected_post = dict(previous_post)
    expected_post.update(
        {
            "planned_operation_file": expected_name,
            "planned_operation_sha256": _overlay.sha256_bytes(
                _overlay.canonical_json_bytes(expected_plan)
            ),
        }
    )
    if (
        plan != expected_plan
        or post != expected_post
        or post.get("planned_operation_file") != expected_name
    ):
        raise PostRegistrationError("POST_REGISTRATION_PLAN_BINDING_INVALID")
    return plan, operation, capability


def _operation_plan_payload(
    *,
    state: Mapping[str, Any],
    operation: Mapping[str, Any],
    capability: PrivateVisionCapabilityBinding,
    capability_authority_sha256: str,
    overlay_tip: Mapping[str, Any],
    module_sha256: str,
) -> dict[str, Any]:
    post = _post_state(state)
    request_reference, asset_reference = _vision_references(state, operation)
    return {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "record_kind": "M3_OPERATION_PLAN",
        "module_sha256": module_sha256,
        "operation_id": operation["operation_id"],
        "platform": operation["platform"],
        "repeat_index": operation["repeat_index"],
        "capability": _capability_payload(capability),
        "capability_authority_sha256": capability_authority_sha256,
        "normalized_sha256": post["normalized_sha256"],
        "request_reference": request_reference,
        "normalized_asset_reference": asset_reference,
        "vision_policy_reference": VISION_POLICY_REFERENCE,
        "overlay_tip": dict(overlay_tip),
        "provider_calls_added": 0,
        "db_mutations": 0,
        "admission": 0,
    }


def _read_and_verify_completed_result(
    *,
    root: Path,
    state: Mapping[str, Any],
    operation: Mapping[str, Any],
    capability: PrivateVisionCapabilityBinding,
    expected_overlay_controller_sha256: str,
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
    expected_post_registration_controller_sha256: str,
) -> dict[str, Any]:
    operation_id = cast(str, operation["operation_id"])
    post = _post_state(state)
    completed = post.get("completed_operations")
    if not isinstance(completed, list) or operation_id not in completed:
        raise PostRegistrationError("POST_REGISTRATION_COMPLETED_OPERATION_MISSING")
    plan_path = _record_path(
        root,
        f"post-registration-operation-{operation_id}.plan.json",
    )
    plan = _read_canonical_json(plan_path, "POST_REGISTRATION_PLAN_NOT_CANONICAL")
    overlay_tip = plan.get("overlay_tip")
    if not isinstance(overlay_tip, dict):
        raise PostRegistrationError("POST_REGISTRATION_PLAN_TIP_INVALID")
    _verify_tip_in_root(
        root=root,
        tip=overlay_tip,
        maximum_sequence=cast(int, state["sequence"]),
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    expected_plan = _operation_plan_payload(
        state=state,
        operation=operation,
        capability=capability,
        capability_authority_sha256=_capability_authority_sha256(
            capability,
            expected_capability_authority_sha256_by_platform,
        ),
        overlay_tip=overlay_tip,
        module_sha256=expected_post_registration_controller_sha256,
    )
    if plan != expected_plan:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_BINDING_INVALID")
    result_path = _record_path(
        root,
        f"post-registration-operation-{operation_id}.result.json",
    )
    result = _read_canonical_json(
        result_path,
        "POST_REGISTRATION_RESULT_NOT_CANONICAL",
    )
    _verify_operation_result_record(
        result=result,
        plan=plan,
        operation=operation,
        capability=capability,
        expected_post_registration_controller_sha256=(expected_post_registration_controller_sha256),
    )
    return result


def _verify_operation_result_record(
    *,
    result: Mapping[str, Any],
    plan: Mapping[str, Any],
    operation: Mapping[str, Any],
    capability: PrivateVisionCapabilityBinding,
    expected_post_registration_controller_sha256: str,
) -> None:
    expected_keys = {
        "schema_version",
        "record_kind",
        "module_sha256",
        "operation_id",
        "platform",
        "repeat_index",
        "plan_sha256",
        "capability",
        "request_reference",
        "provider_run_reference",
        "safety_policy_reference",
        "safety_outcome",
        "safety_reason_code",
        "observations",
        "transformation_matrix",
        "bbox_area",
        "rotation_degrees",
        "timestamp",
        "db_mutations",
        "provider_calls_added",
        "admission",
    }
    if (
        set(result) != expected_keys
        or result.get("schema_version") != POST_REGISTRATION_SCHEMA
        or result.get("record_kind") != "M3_OPERATION_RESULT"
        or result.get("module_sha256") != expected_post_registration_controller_sha256
        or any(
            result.get(key) != operation[key]
            for key in ("operation_id", "platform", "repeat_index")
        )
        or result.get("plan_sha256") != _overlay.sha256_bytes(_overlay.canonical_json_bytes(plan))
        or result.get("capability") != _capability_payload(capability)
        or result.get("request_reference") != plan.get("request_reference")
        or result.get("db_mutations") != 0
        or result.get("provider_calls_added") != 0
        or result.get("admission") != 0
    ):
        raise PostRegistrationError("POST_REGISTRATION_RESULT_BINDING_INVALID")
    _validate_timestamp(
        _required_text(result, "timestamp", "POST_REGISTRATION_RESULT_TIMESTAMP_INVALID")
    )
    for key in (
        "request_reference",
        "provider_run_reference",
        "safety_policy_reference",
        "safety_reason_code",
    ):
        _validate_port_reference(
            _required_text(result, key, "POST_REGISTRATION_RESULT_REFERENCE_INVALID"),
            "POST_REGISTRATION_RESULT_REFERENCE",
        )
    if result.get("safety_outcome") not in {"passed", "rejected"}:
        raise PostRegistrationError("POST_REGISTRATION_RESULT_SAFETY_INVALID")
    _validate_result_observations(result.get("observations"))
    matrix = result.get("transformation_matrix")
    if (
        not isinstance(matrix, list)
        or len(matrix) != 16
        or not all(_is_finite_number(value) for value in matrix)
        or not _is_finite_number(result.get("bbox_area"))
        or not 0.0 <= float(result["bbox_area"]) <= 1.0
        or not _is_finite_number(result.get("rotation_degrees"))
    ):
        raise PostRegistrationError("POST_REGISTRATION_RESULT_NUMERIC_INVALID")


def _verify_operation_failure_record(
    *,
    result: Mapping[str, Any],
    plan: Mapping[str, Any],
    operation: Mapping[str, Any],
    capability: PrivateVisionCapabilityBinding,
    expected_post_registration_controller_sha256: str,
) -> None:
    expected = {
        "schema_version": POST_REGISTRATION_SCHEMA,
        "record_kind": "M3_OPERATION_FAILURE",
        "module_sha256": expected_post_registration_controller_sha256,
        "operation_id": operation["operation_id"],
        "platform": operation["platform"],
        "repeat_index": operation["repeat_index"],
        "plan_sha256": _overlay.sha256_bytes(_overlay.canonical_json_bytes(plan)),
        "capability": _capability_payload(capability),
        "request_reference": plan["request_reference"],
        "reason_code": result.get("reason_code"),
        "timestamp": result.get("timestamp"),
        "db_mutations": 0,
        "provider_calls_added": 0,
        "admission": 0,
    }
    if result != expected or result.get("reason_code") not in {
        "POST_REGISTRATION_OPERATION_EVIDENCE_BINDING_INVALID",
        "POST_REGISTRATION_VISION_REQUEST_BUILD_FAILED",
    }:
        raise PostRegistrationError("POST_REGISTRATION_FAILURE_RESULT_INVALID")
    _validate_timestamp(
        _required_text(
            result,
            "timestamp",
            "POST_REGISTRATION_FAILURE_RESULT_TIMESTAMP_INVALID",
        )
    )


def _validate_canonical_vision_result(result: SyntheticVisionResult) -> None:
    if (
        type(result.safety) is not ProviderSafetyFact
        or type(result.cost) is not ProviderCostFact
        or type(result.provenance) is not ProviderProvenanceFact
        or type(result.observations) is not tuple
        or result.safety.outcome not in {"passed", "rejected"}
        or type(result.cost.amount_micros) is not int
        or result.cost.amount_micros < 0
        or result.cost.currency not in {"CNY", "USD"}
        or result.cost.status not in {"estimated", "final"}
        or result.provenance.retention_status not in {"not_retained", "contractually_bounded"}
        or result.provenance.output_rights
        not in {"internal_evaluation_only", "synthetic_release_permitted"}
    ):
        raise PostRegistrationError("POST_REGISTRATION_VISION_RESULT_TYPE_INVALID")
    for value in (
        result.safety.policy_reference,
        result.safety.reason_code,
        result.provenance.provider_reference,
        result.provenance.model_reference,
        result.provenance.model_version_reference,
        result.provenance.policy_reference,
    ):
        _validate_port_reference(value, "POST_REGISTRATION_VISION_RESULT_REFERENCE")
    references: list[str] = []
    for observation in result.observations:
        if (
            type(observation) is not FaceObservation
            or type(observation.landmarks) is not FaceLandmarkSet
            or type(observation.landmarks.landmarks) is not tuple
            or type(observation.pose) is not PoseEstimate
            or type(observation.geometry_measurements) is not tuple
        ):
            raise PostRegistrationError("POST_REGISTRATION_OBSERVATION_TYPE_INVALID")
        _validate_port_reference(
            observation.observation_reference,
            "POST_REGISTRATION_OBSERVATION_REFERENCE",
        )
        references.append(observation.observation_reference)
        codes: list[str] = []
        for landmark in observation.landmarks.landmarks:
            if type(landmark) is not FaceLandmark:
                raise PostRegistrationError("POST_REGISTRATION_LANDMARK_TYPE_INVALID")
            _validate_port_reference(
                landmark.landmark_code,
                "POST_REGISTRATION_LANDMARK_CODE",
            )
            codes.append(landmark.landmark_code)
            if not all(
                _is_finite_number(value) and 0.0 <= float(value) <= 1.0
                for value in (landmark.x, landmark.y, landmark.confidence)
            ):
                raise PostRegistrationError("POST_REGISTRATION_LANDMARK_VALUE_INVALID")
        if not codes or len(codes) > 512 or len(set(codes)) != len(codes):
            raise PostRegistrationError("POST_REGISTRATION_LANDMARK_SET_INVALID")
        if (
            not all(
                _is_finite_number(value)
                for value in (
                    observation.pose.yaw_degrees,
                    observation.pose.pitch_degrees,
                    observation.pose.roll_degrees,
                    observation.pose.confidence,
                )
            )
            or not 0.0 <= float(observation.pose.confidence) <= 1.0
        ):
            raise PostRegistrationError("POST_REGISTRATION_POSE_VALUE_INVALID")
        measurement_codes: list[str] = []
        for measurement in observation.geometry_measurements:
            if type(measurement) is not GeometryMeasurement:
                raise PostRegistrationError("POST_REGISTRATION_MEASUREMENT_TYPE_INVALID")
            _validate_port_reference(
                measurement.measurement_code,
                "POST_REGISTRATION_MEASUREMENT_CODE",
            )
            _validate_port_reference(
                measurement.measurement_version,
                "POST_REGISTRATION_MEASUREMENT_VERSION",
            )
            measurement_codes.append(measurement.measurement_code)
            if (
                not _is_finite_number(measurement.value)
                or not -10_000.0 <= float(measurement.value) <= 10_000.0
                or not _is_finite_number(measurement.confidence)
                or not 0.0 <= float(measurement.confidence) <= 1.0
            ):
                raise PostRegistrationError("POST_REGISTRATION_MEASUREMENT_VALUE_INVALID")
        if len(set(measurement_codes)) != len(measurement_codes):
            raise PostRegistrationError("POST_REGISTRATION_MEASUREMENT_CODE_DUPLICATE")
    if len(set(references)) != len(references):
        raise PostRegistrationError("POST_REGISTRATION_OBSERVATION_REFERENCE_DUPLICATE")


def _validate_result_observations(value: object) -> None:
    if not isinstance(value, list) or len(value) > 16:
        raise PostRegistrationError("POST_REGISTRATION_RESULT_OBSERVATIONS_INVALID")
    references: list[str] = []
    for observation in value:
        if not isinstance(observation, dict) or set(observation) != {
            "observation_reference",
            "landmarks",
            "pose",
        }:
            raise PostRegistrationError("POST_REGISTRATION_RESULT_OBSERVATION_INVALID")
        reference = _required_text(
            observation,
            "observation_reference",
            "POST_REGISTRATION_RESULT_OBSERVATION_REFERENCE_INVALID",
        )
        _validate_port_reference(reference, "POST_REGISTRATION_RESULT_OBSERVATION_REFERENCE")
        references.append(reference)
        landmarks = observation.get("landmarks")
        pose = observation.get("pose")
        if not isinstance(landmarks, list) or not 0 < len(landmarks) <= 512:
            raise PostRegistrationError("POST_REGISTRATION_RESULT_LANDMARKS_INVALID")
        codes: list[str] = []
        for landmark in landmarks:
            if not isinstance(landmark, dict) or set(landmark) != {
                "landmark_code",
                "x",
                "y",
                "confidence",
            }:
                raise PostRegistrationError("POST_REGISTRATION_RESULT_LANDMARK_INVALID")
            code = _required_text(
                landmark,
                "landmark_code",
                "POST_REGISTRATION_RESULT_LANDMARK_CODE_INVALID",
            )
            _validate_port_reference(code, "POST_REGISTRATION_RESULT_LANDMARK_CODE")
            codes.append(code)
            if not all(
                _is_finite_number(landmark.get(field)) and 0.0 <= float(landmark[field]) <= 1.0
                for field in ("x", "y", "confidence")
            ):
                raise PostRegistrationError("POST_REGISTRATION_RESULT_LANDMARK_VALUE_INVALID")
        if len(set(codes)) != len(codes):
            raise PostRegistrationError("POST_REGISTRATION_RESULT_LANDMARK_CODE_DUPLICATE")
        if not isinstance(pose, dict) or set(pose) != {
            "yaw_degrees",
            "pitch_degrees",
            "roll_degrees",
            "confidence",
        }:
            raise PostRegistrationError("POST_REGISTRATION_RESULT_POSE_INVALID")
        if not all(_is_finite_number(pose.get(field)) for field in pose):
            raise PostRegistrationError("POST_REGISTRATION_RESULT_POSE_VALUE_INVALID")
        if not 0.0 <= float(pose["confidence"]) <= 1.0:
            raise PostRegistrationError("POST_REGISTRATION_RESULT_POSE_CONFIDENCE_INVALID")
    if len(set(references)) != len(references):
        raise PostRegistrationError("POST_REGISTRATION_RESULT_OBSERVATION_DUPLICATE")


def _qa_reason(results: list[dict[str, Any]]) -> str | None:
    by_platform: dict[str, list[dict[str, Any]]] = {platform: [] for platform in _PLATFORMS}
    for result in results:
        platform = result.get("platform")
        if platform not in by_platform:
            return "POST_REGISTRATION_RESULT_PLATFORM_INVALID"
        by_platform[cast(str, platform)].append(result)
        observations = result.get("observations")
        if (
            not isinstance(observations, list)
            or len(observations) != 1
            or result.get("safety_outcome") != "passed"
        ):
            return "POST_REGISTRATION_FACE_OR_SAFETY_GATE_FAILED"
        observation = observations[0]
        landmarks = observation.get("landmarks") if isinstance(observation, dict) else None
        pose = observation.get("pose") if isinstance(observation, dict) else None
        matrix = result.get("transformation_matrix")
        if (
            not isinstance(landmarks, list)
            or len(landmarks) != 478
            or not isinstance(pose, dict)
            or not isinstance(matrix, list)
            or len(matrix) != 16
        ):
            return "POST_REGISTRATION_LANDMARK_OR_MATRIX_GATE_FAILED"
        codes = [
            landmark.get("landmark_code") for landmark in landmarks if isinstance(landmark, dict)
        ]
        values = [
            landmark.get(field)
            for landmark in landmarks
            if isinstance(landmark, dict)
            for field in ("x", "y", "confidence")
        ]
        if (
            len(codes) != 478
            or len(set(codes)) != 478
            or len(values) != 1434
            or not all(_is_finite_number(value) for value in values)
        ):
            return "POST_REGISTRATION_LANDMARK_VALUE_GATE_FAILED"
        numeric_values = cast(list[int | float], values)
        if not all(0.0 <= float(value) <= 1.0 for value in numeric_values):
            return "POST_REGISTRATION_LANDMARK_VALUE_GATE_FAILED"
        if not all(_is_finite_number(value) for value in matrix):
            return "POST_REGISTRATION_MATRIX_VALUE_GATE_FAILED"
        pose_values = [
            pose.get("yaw_degrees"),
            pose.get("pitch_degrees"),
            pose.get("roll_degrees"),
            pose.get("confidence"),
        ]
        if not all(_is_finite_number(value) for value in pose_values):
            return "POST_REGISTRATION_POSE_GATE_FAILED"
        numeric_pose_values = cast(list[int | float], pose_values)
        if any(abs(float(value)) > 10.0 for value in numeric_pose_values[:3]):
            return "POST_REGISTRATION_POSE_GATE_FAILED"
        if not _is_finite_number(result.get("bbox_area")) or float(result["bbox_area"]) < 0.1:
            return "POST_REGISTRATION_OCCUPANCY_GATE_FAILED"
    if any(len(entries) != _REPEATS_PER_PLATFORM for entries in by_platform.values()):
        return "POST_REGISTRATION_RESULT_CARDINALITY_FAILED"
    for entries in by_platform.values():
        entries.sort(key=lambda entry: cast(int, entry["repeat_index"]))
        if [entry["repeat_index"] for entry in entries] != list(
            range(1, _REPEATS_PER_PLATFORM + 1)
        ):
            return "POST_REGISTRATION_RESULT_CARDINALITY_FAILED"
        landmark_codes = [
            [item["landmark_code"] for item in entry["observations"][0]["landmarks"]]
            for entry in entries
        ]
        if any(codes != landmark_codes[0] for codes in landmark_codes[1:]):
            return "POST_REGISTRATION_LANDMARK_CODE_REPEATABILITY_FAILED"
        landmark_span = max(
            _max_span(
                [
                    float(entry["observations"][0]["landmarks"][landmark_index][field])
                    for entry in entries
                ]
            )
            for landmark_index in range(478)
            for field in ("x", "y", "confidence")
        )
        matrix_span = max(
            _max_span([float(entry["transformation_matrix"][index]) for entry in entries])
            for index in range(16)
        )
        if landmark_span > 0.000001 or matrix_span > 0.000001:
            return "POST_REGISTRATION_SAME_PLATFORM_REPEATABILITY_FAILED"
    left, right = by_platform[_PLATFORMS[0]], by_platform[_PLATFORMS[1]]
    for index in range(_REPEATS_PER_PLATFORM):
        left_landmarks = left[index]["observations"][0]["landmarks"]
        right_landmarks = right[index]["observations"][0]["landmarks"]
        if [value["landmark_code"] for value in left_landmarks] != [
            value["landmark_code"] for value in right_landmarks
        ]:
            return "POST_REGISTRATION_CROSS_PLATFORM_LANDMARK_CODE_FAILED"
        if (
            _max_abs_difference(
                [
                    float(point[field])
                    for point in left_landmarks
                    for field in ("x", "y", "confidence")
                ],
                [
                    float(point[field])
                    for point in right_landmarks
                    for field in ("x", "y", "confidence")
                ],
            )
            > 0.00005
            or _max_abs_difference(
                [float(value) for value in left[index]["transformation_matrix"]],
                [float(value) for value in right[index]["transformation_matrix"]],
            )
            > 0.0005
            or abs(float(left[index]["bbox_area"]) - float(right[index]["bbox_area"])) > 0.00001
            or abs(float(left[index]["rotation_degrees"]) - float(right[index]["rotation_degrees"]))
            > 0.01
        ):
            return "POST_REGISTRATION_CROSS_PLATFORM_PARITY_FAILED"
    return None


def _all_operations(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    output_id = _required_text(state, "overlay_output_id", "POST_REGISTRATION_OUTPUT_ID_MISSING")
    return [
        {
            "operation_id": f"{output_id}-M3-{platform.split('_')[0].upper()}-{repeat:02d}",
            "platform": platform,
            "repeat_index": repeat,
        }
        for platform in _PLATFORMS
        for repeat in range(1, _REPEATS_PER_PLATFORM + 1)
    ]


def _current_context(
    *, receipt_path: Path, expected_overlay_controller_sha256: str
) -> dict[str, Any]:
    verified = _overlay.verify_overlay(
        receipt_path, expected_controller_sha256=expected_overlay_controller_sha256
    )
    return {
        "receipt_path": receipt_path,
        "receipt": cast(dict[str, Any], verified["receipt"]),
        "event": cast(dict[str, Any], verified["event"]),
        "state": cast(dict[str, Any], verified["state"]),
    }


def _post_state(state: Mapping[str, Any]) -> dict[str, Any]:
    value = state.get("post_registration")
    if not isinstance(value, dict) or value.get("schema_version") != POST_REGISTRATION_SCHEMA:
        raise PostRegistrationError("POST_REGISTRATION_STATE_BINDING_MISSING")
    return value


def _durable_failure_reason(post: Mapping[str, Any]) -> str | None:
    fields = {"failure_result_file", "failure_result_sha256", "failure_reason_code"}
    present = fields & set(post)
    if not present:
        return None
    if present != fields:
        raise PostRegistrationError("POST_REGISTRATION_INFRA_FAILURE_EVIDENCE_INVALID")
    reason = _required_text(
        post, "failure_reason_code", "POST_REGISTRATION_INFRA_FAILURE_EVIDENCE_INVALID"
    )
    if reason not in {
        "POST_REGISTRATION_OPERATION_EVIDENCE_BINDING_INVALID",
        "POST_REGISTRATION_VISION_REQUEST_BUILD_FAILED",
    }:
        raise PostRegistrationError("POST_REGISTRATION_INFRA_FAILURE_EVIDENCE_INVALID")
    return reason


def _counters(state: Mapping[str, Any]) -> dict[str, int]:
    counters = state.get("counters")
    if not isinstance(counters, dict):
        raise PostRegistrationError("POST_REGISTRATION_COUNTERS_MISSING")
    return cast(dict[str, int], counters)


def _record_path(root: Path, name: str) -> Path:
    return _overlay._safe_child(root / "records", name)


def _tip_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "receipt_sha256": _overlay.sha256_bytes(_overlay.canonical_json_bytes(receipt)),
        "state_sha256": receipt["state_sha256"],
        "event_sha256": receipt["event_sha256"],
        "controller_sha256": receipt["controller_sha256"],
    }


def _capability_payload(capability: PrivateVisionCapabilityBinding) -> dict[str, str]:
    return {
        "capability_id": capability.capability_id,
        "platform": capability.platform,
        "runtime_sha256": capability.runtime_sha256,
        "model_sha256": capability.model_sha256,
        "manifest_version": capability.manifest_version,
        "manifest_sha256": capability.manifest_sha256,
        "qa_policy_version": capability.qa_policy_version,
        "qa_policy_sha256": capability.qa_policy_sha256,
        "zero_egress_evidence_id": capability.zero_egress_evidence_id,
        "zero_egress_evidence_sha256": capability.zero_egress_evidence_sha256,
        "approved_scope": capability.approved_scope,
    }


def _redacted_post_binding(post: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in post.items()
        if key.endswith("_sha256")
        or key in {"schema_version", "decode_performed", "completed_operations"}
    }


def _required_text(value: Mapping[str, Any], key: str, code: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise PostRegistrationError(code)
    return result


def _require_empty_directory(path: Path) -> None:
    _overlay._require_plain_directory(path)
    if next(path.iterdir(), None) is not None:
        raise PostRegistrationError("POST_REGISTRATION_SUCCESSOR_DIRECTORY_NOT_EMPTY")


def _validate_timestamp(value: str) -> None:
    _overlay._validate_timestamp(value)


def _validate_digest(value: str, field: str) -> None:
    _overlay._validate_digest(value, field)


def _validate_lower_digest(value: object, field: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise PostRegistrationError(f"{field}_INVALID")


def _external_verification_authority(
    *,
    expected_registered_receipt_sha256: str,
    expected_registered_state_sha256: str,
    expected_registered_event_sha256: str,
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
) -> _ExternalVerificationAuthority:
    for value, field in (
        (expected_registered_receipt_sha256, "EXPECTED_REGISTERED_RECEIPT_SHA256"),
        (expected_registered_state_sha256, "EXPECTED_REGISTERED_STATE_SHA256"),
        (expected_registered_event_sha256, "EXPECTED_REGISTERED_EVENT_SHA256"),
    ):
        _validate_lower_digest(value, field)
    if set(expected_capability_authority_sha256_by_platform) != set(_PLATFORMS):
        raise PostRegistrationError("POST_REGISTRATION_CAPABILITY_SET_INVALID")
    capability_authority = {
        platform: expected_capability_authority_sha256_by_platform[platform]
        for platform in _PLATFORMS
    }
    for value in capability_authority.values():
        _validate_lower_digest(
            value,
            "POST_REGISTRATION_EXPECTED_CAPABILITY_AUTHORITY_SHA256",
        )
    return _ExternalVerificationAuthority(
        registered_receipt_sha256=expected_registered_receipt_sha256,
        registered_state_sha256=expected_registered_state_sha256,
        registered_event_sha256=expected_registered_event_sha256,
        capability_authority_sha256_by_platform=MappingProxyType(capability_authority),
    )


def _terminal_tip_authority(
    *,
    expected_receipt_sha256: str,
    expected_state_sha256: str,
    expected_event_sha256: str,
) -> _TerminalTipAuthority:
    for value, field in (
        (expected_receipt_sha256, "EXPECTED_TERMINAL_RECEIPT_SHA256"),
        (expected_state_sha256, "EXPECTED_TERMINAL_STATE_SHA256"),
        (expected_event_sha256, "EXPECTED_TERMINAL_EVENT_SHA256"),
    ):
        _validate_lower_digest(value, field)
    return _TerminalTipAuthority(
        receipt_sha256=expected_receipt_sha256,
        state_sha256=expected_state_sha256,
        event_sha256=expected_event_sha256,
    )


def _optional_terminal_tip_authority(
    *,
    expected_receipt_sha256: str | None,
    expected_state_sha256: str | None,
    expected_event_sha256: str | None,
) -> _TerminalTipAuthority | None:
    values = (expected_receipt_sha256, expected_state_sha256, expected_event_sha256)
    if values == (None, None, None):
        return None
    if any(value is None for value in values):
        raise PostRegistrationError("POST_REGISTRATION_TERMINAL_TIP_AUTHORITY_PARTIAL")
    return _terminal_tip_authority(
        expected_receipt_sha256=cast(str, expected_receipt_sha256),
        expected_state_sha256=cast(str, expected_state_sha256),
        expected_event_sha256=cast(str, expected_event_sha256),
    )


def _validate_port_reference(value: object, field: str) -> None:
    if not isinstance(value, str) or _PORT_REFERENCE.fullmatch(value) is None:
        raise PostRegistrationError(f"{field}_INVALID")


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _context_path(context: Mapping[str, Any]) -> Path:
    value = context.get("receipt_path")
    if not isinstance(value, Path) or not value.is_absolute():
        raise PostRegistrationError("POST_REGISTRATION_CONTEXT_PATH_INVALID")
    return value


def _latest_receipt_path(
    *,
    anchor_receipt_path: Path,
    expected_overlay_controller_sha256: str,
) -> Path:
    anchor = _current_context(
        receipt_path=anchor_receipt_path,
        expected_overlay_controller_sha256=expected_overlay_controller_sha256,
    )
    sequence = cast(int, cast(dict[str, Any], anchor["receipt"])["sequence"])
    maximum = sequence + _MAX_POST_REGISTRATION_TRANSITIONS
    current = anchor_receipt_path
    while sequence < maximum:
        candidate = _overlay._safe_child(
            current.parent,
            _overlay._receipt_name(sequence + 1),
        )
        if candidate.is_symlink():
            raise PostRegistrationError("POST_REGISTRATION_RECEIPT_SYMLINK_REJECTED")
        if not candidate.exists():
            return current
        verified = _current_context(
            receipt_path=candidate,
            expected_overlay_controller_sha256=expected_overlay_controller_sha256,
        )
        if cast(dict[str, Any], verified["receipt"]).get("sequence") != sequence + 1:
            raise PostRegistrationError("POST_REGISTRATION_RECEIPT_SEQUENCE_INVALID")
        current = candidate
        sequence += 1
    overflow = _overlay._safe_child(
        current.parent,
        _overlay._receipt_name(sequence + 1),
    )
    if overflow.exists() or overflow.is_symlink():
        raise PostRegistrationError("POST_REGISTRATION_RECEIPT_BOUND_EXCEEDED")
    return current


def _ensure_no_next_receipt(
    context: Mapping[str, Any],
    *,
    error_code: str = "POST_REGISTRATION_STALE_CURRENT_TIP",
) -> None:
    receipt_path = _context_path(context)
    receipt = cast(dict[str, Any], context["receipt"])
    next_path = _overlay._safe_child(
        receipt_path.parent,
        _overlay._receipt_name(cast(int, receipt["sequence"]) + 1),
    )
    if next_path.exists() or next_path.is_symlink():
        raise PostRegistrationError(error_code)


def _verify_tip_in_root(
    *,
    root: Path,
    tip: Mapping[str, Any],
    maximum_sequence: int,
    expected_overlay_controller_sha256: str,
    verified_history: _VerifiedReceiptHistory | None = None,
) -> Path:
    if set(tip) != {
        "receipt_sha256",
        "state_sha256",
        "event_sha256",
        "controller_sha256",
    }:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_TIP_INVALID")
    for key in ("receipt_sha256", "state_sha256", "event_sha256", "controller_sha256"):
        _validate_lower_digest(tip.get(key), f"POST_REGISTRATION_PLAN_TIP_{key.upper()}")
    if tip.get("controller_sha256") != expected_overlay_controller_sha256:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_TIP_CONTROLLER_INVALID")
    candidate = (
        verified_history.paths_by_tip.get(_tip_key(tip)) if verified_history is not None else None
    )
    if candidate is None:
        for sequence in range(maximum_sequence + 1):
            possible = _overlay._safe_child(root, _overlay._receipt_name(sequence))
            if possible.is_symlink():
                raise PostRegistrationError("POST_REGISTRATION_RECEIPT_SYMLINK_REJECTED")
            if possible.exists() and _overlay.sha256_file(possible) == tip["receipt_sha256"]:
                candidate = possible
                break
    if candidate is None:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_TIP_NOT_IN_CHAIN")
    receipt, _event, _state = _overlay._verify_receipt(
        candidate,
        expected_controller_sha256=expected_overlay_controller_sha256,
    )
    if _tip_payload(receipt) != tip:
        raise PostRegistrationError("POST_REGISTRATION_PLAN_TIP_BINDING_INVALID")
    return candidate


def _tip_key(tip: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        cast(str, tip["receipt_sha256"]),
        cast(str, tip["state_sha256"]),
        cast(str, tip["event_sha256"]),
        cast(str, tip["controller_sha256"]),
    )


def _read_canonical_json(path: Path, code: str) -> dict[str, Any]:
    value = _overlay._read_json(path)
    if _overlay._read_plain_file_bytes(path) != _overlay.canonical_json_bytes(value):
        raise PostRegistrationError(code)
    return value


def _vision_references(state: Mapping[str, Any], operation: Mapping[str, Any]) -> tuple[str, str]:
    normalized_sha256 = _required_text(
        _post_state(state),
        "normalized_sha256",
        "POST_REGISTRATION_NORMALIZED_DIGEST_MISSING",
    )
    _validate_lower_digest(
        normalized_sha256,
        "POST_REGISTRATION_NORMALIZED_SHA256",
    )
    operation_id = _required_text(
        operation,
        "operation_id",
        "POST_REGISTRATION_OPERATION_ID_MISSING",
    )
    request_digest = _overlay.sha256_bytes(f"{normalized_sha256}\n{operation_id}".encode("ascii"))
    return f"request-{request_digest[:48]}", f"asset-{normalized_sha256[:48]}"


def _capability_authority_sha256(
    capability: PrivateVisionCapabilityBinding,
    expected_capability_authority_sha256_by_platform: Mapping[str, str],
) -> str:
    expected = expected_capability_authority_sha256_by_platform.get(capability.platform)
    _validate_lower_digest(
        expected,
        "POST_REGISTRATION_EXPECTED_CAPABILITY_AUTHORITY_SHA256",
    )
    actual = _overlay.sha256_bytes(_overlay.canonical_json_bytes(_capability_payload(capability)))
    if actual != expected:
        raise PostRegistrationError("POST_REGISTRATION_CAPABILITY_AUTHORITY_MISMATCH")
    return actual


def _assert_overlay_pin(expected: str) -> None:
    _validate_digest(expected, "EXPECTED_OVERLAY_CONTROLLER_SHA256")
    if _overlay.sha256_file(Path(_overlay.__file__)) != expected:
        raise PostRegistrationError("POST_REGISTRATION_OVERLAY_SOURCE_PIN_MISMATCH")


def _assert_module_pin(expected: str) -> None:
    _validate_digest(expected, "EXPECTED_POST_REGISTRATION_CONTROLLER_SHA256")
    if _overlay.sha256_file(Path(__file__)) != expected:
        raise PostRegistrationError("POST_REGISTRATION_MODULE_SOURCE_PIN_MISMATCH")


def _max_span(values: list[float]) -> float:
    return max(values) - min(values) if values else math.inf


def _max_abs_difference(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return math.inf
    return max((abs(a - b) for a, b in zip(left, right, strict=True)), default=math.inf)
