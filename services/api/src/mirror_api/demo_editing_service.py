"""D07-B application orchestration for private edit materialization.

This module owns no ORM mapping and imports no task adapter.  The central
integration layer supplies one PostgreSQL transaction-backed repository and a
private storage implementation.  Keeping those adapters injected makes the
storage-before-DB recovery rule explicit and prevents a worker retry from
silently publishing an unverified object.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, cast

from mirror_api.demo_d08_geometry_adapter import (
    GeometryAttemptExecutionEvidence,
    GeometryExecutionAuthority,
    GeometryJobAttemptBinding,
    GeometryStableMaterializationCore,
    operation_spec_digest,
)
from mirror_api.demo_effect_verifier import EffectVerificationResult, VerificationStatus
from mirror_api.demo_operation_graph import OperationEngine, OperationSpec, OperationType
from mirror_api.demo_raster_editor import RasterEditError, execute_raster_operation

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_FIXED18 = re.compile(r"^-?(?:0|[1-9][0-9]*)\.\d{18}$")
_GEOMETRY_METRICS_SCHEMA = "mirror.demo/D08GeometryVerificationMetrics/v1"
_GEOMETRY_THRESHOLDS_SCHEMA = "mirror.demo/D08GeometryVerificationThresholds/v1"
_MEASUREMENT_DIMENSIONS = (
    "cheekbone_width",
    "chin_height",
    "eye_spacing",
    "jaw_width",
    "mouth_width",
    "nose_width",
)


class DemoEditingServiceError(RuntimeError):
    """A fail-closed application error with a stable code."""

    def __init__(self, code: str, message: str, *, published_cleanup_safe: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.published_cleanup_safe = published_cleanup_safe


class ArtifactState(StrEnum):
    RESERVED = "RESERVED"
    MATERIALIZED = "MATERIALIZED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    CLEANED = "CLEANED"


@dataclass(frozen=True, slots=True)
class EditingSessionCommand:
    actor_id: str
    session_id: str
    source_asset_id: str
    source_asset_sha256: str
    desired_delta_profile_digest: str
    style_profile_digest: str
    identity_constraints_digest: str
    context_digest: str
    instruction_digest: str
    tool_registry_version: str


@dataclass(frozen=True, slots=True)
class EditPlanCommand:
    actor_id: str
    session_id: str
    editing_session_id: str
    input_image_version_id: str
    operation_specs: tuple[OperationSpec, ...]
    planner_version: str
    tool_registry_version: str


@dataclass(frozen=True, slots=True)
class ExecutionCommand:
    actor_id: str
    session_id: str
    operation_id: str
    operation_digest: str
    execution_job_binding_id: str
    formal_job_attempt_id: str
    source_asset_id: str
    source_asset_sha256: str
    source_bytes: bytes = field(repr=False)
    operation: OperationSpec
    engine_version: str
    engine_digest: str
    config_digest: str
    editing_session_id: str | None = None
    plan_id: str | None = None
    input_image_version_id: str | None = None
    root_source_asset_id: str | None = None
    geometry_authority: GeometryExecutionAuthority | None = None
    geometry_job_attempt: GeometryJobAttemptBinding | None = None
    parent_job_id: str | None = None
    parent_job_attempt_id: str | None = None


@dataclass(frozen=True, slots=True)
class MaterializationEvidence:
    sha256: str
    byte_size: int
    width: int
    height: int
    mime_type: str
    engine_digest: str
    config_digest: str


@dataclass(frozen=True, slots=True)
class EditArtifact:
    artifact_id: str
    actor_id: str
    session_id: str
    operation_id: str
    execution_job_binding_id: str
    formal_job_attempt_id: str
    private_object_key: str
    state: ArtifactState
    materialized: MaterializationEvidence | None = None


@dataclass(frozen=True, slots=True)
class MaterializedObject:
    content: bytes = field(repr=False)
    sha256: str
    width: int
    height: int
    mime_type: str
    engine_digest: str
    config_digest: str
    geometry_stable_core: GeometryStableMaterializationCore | None = None
    geometry_attempt_evidence: GeometryAttemptExecutionEvidence | None = None


@dataclass(frozen=True, slots=True)
class Promotion:
    asset_id: str
    asset_variant_id: str
    image_version_id: str
    verification_result_id: str


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    artifact_id: str
    state: ArtifactState
    verification_status: VerificationStatus | None
    promotion: Promotion | None
    replayed: bool


class PrivateObjectStorage(Protocol):
    async def put_if_absent(self, *, key: str, content: bytes, sha256: str) -> None: ...

    async def read(self, *, key: str) -> bytes | None: ...

    async def promote_from_quarantine(self, *, key: str, artifact_id: str, sha256: str) -> str: ...

    async def discard_published(self, *, key: str, sha256: str) -> None: ...


class GeometryDispatcher(Protocol):
    async def __call__(self, command: ExecutionCommand) -> MaterializedObject: ...


class TransitionDispatcher(Protocol):
    async def __call__(self, command: ExecutionCommand) -> MaterializedObject: ...


class EditVerifier(Protocol):
    async def __call__(
        self, command: ExecutionCommand, materialized: MaterializedObject
    ) -> EffectVerificationResult: ...


class DemoEditingRepository(Protocol):
    """Transaction-bound persistence port implemented by central ORM wiring."""

    async def create_editing_session(self, command: EditingSessionCommand) -> str: ...

    async def persist_plan(self, command: EditPlanCommand) -> str: ...

    async def reserve_execution(
        self, command: ExecutionCommand, object_key: str
    ) -> EditArtifact: ...

    async def append_materialized(
        self, artifact: EditArtifact, materialized: MaterializedObject
    ) -> EditArtifact: ...

    async def append_rejected(
        self,
        artifact: EditArtifact,
        verification: EffectVerificationResult,
        materialized: MaterializedObject,
        *,
        parent_job_id: str | None = None,
        parent_job_attempt_id: str | None = None,
    ) -> EditArtifact: ...

    async def promote_pass(
        self,
        artifact: EditArtifact,
        verification: EffectVerificationResult,
        materialized: MaterializedObject,
        published_storage_key: str,
        *,
        parent_job_id: str | None = None,
        parent_job_attempt_id: str | None = None,
    ) -> Promotion: ...

    async def create_transition(
        self,
        *,
        actor_id: str,
        session_id: str,
        source_image_version_id: str,
        target_image_version_id: str,
        transition: str,
    ) -> str: ...


class DemoEditingService:
    """Orchestrate reserve → private materialize → verify → terminal publication."""

    def __init__(
        self,
        *,
        repository: DemoEditingRepository,
        storage: PrivateObjectStorage,
        verifier: EditVerifier,
        geometry_dispatcher: GeometryDispatcher | None = None,
        transition_dispatcher: TransitionDispatcher | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._verifier = verifier
        self._geometry_dispatcher = geometry_dispatcher
        self._transition_dispatcher = transition_dispatcher

    async def create_editing_session(self, command: EditingSessionCommand) -> str:
        _validate_session_command(command)
        return await self._repository.create_editing_session(command)

    async def persist_plan(self, command: EditPlanCommand) -> str:
        _validate_plan_command(command)
        return await self._repository.persist_plan(command)

    async def execute(self, command: ExecutionCommand) -> ExecutionResult:
        _validate_execution_command(command)
        key = quarantine_object_key(command)
        artifact = await self._repository.reserve_execution(command, key)
        _validate_artifact_matches(artifact, command, key)
        if artifact.state is ArtifactState.PROMOTED:
            return ExecutionResult(
                artifact.artifact_id, artifact.state, VerificationStatus.PASS, None, True
            )
        if artifact.state in {
            ArtifactState.REJECTED,
            ArtifactState.CANCELLED,
            ArtifactState.CLEANED,
        }:
            return ExecutionResult(artifact.artifact_id, artifact.state, None, None, True)

        materialized = await self._recover_or_materialize(artifact, command)
        if artifact.state is ArtifactState.RESERVED:
            artifact = await self._repository.append_materialized(artifact, materialized)
        if artifact.state is not ArtifactState.MATERIALIZED:
            raise DemoEditingServiceError(
                "INVALID_ARTIFACT_STATE", "materialized artifact state is invalid"
            )

        verification = await self._verifier(command, materialized)
        if not isinstance(verification, EffectVerificationResult):
            raise DemoEditingServiceError("INVALID_VERIFIER_RESULT", "verifier result is invalid")
        _validate_verification_authority(verification, command, materialized)
        if verification.status is VerificationStatus.PASS:
            published_storage_key = await self._storage.promote_from_quarantine(
                key=artifact.private_object_key,
                artifact_id=artifact.artifact_id,
                sha256=materialized.sha256,
            )
            try:
                if command.parent_job_id is None:
                    promotion = await self._repository.promote_pass(
                        artifact,
                        verification,
                        materialized,
                        published_storage_key,
                    )
                else:
                    promotion = await self._repository.promote_pass(
                        artifact,
                        verification,
                        materialized,
                        published_storage_key,
                        parent_job_id=command.parent_job_id,
                        parent_job_attempt_id=command.parent_job_attempt_id,
                    )
            except DemoEditingServiceError as exc:
                if (
                    command.operation.engine is OperationEngine.GEOMETRY
                    and exc.published_cleanup_safe
                ):
                    await self._storage.discard_published(
                        key=published_storage_key, sha256=materialized.sha256
                    )
                raise
            return ExecutionResult(
                artifact.artifact_id, ArtifactState.PROMOTED, verification.status, promotion, False
            )
        if command.parent_job_id is None:
            rejected = await self._repository.append_rejected(
                artifact,
                verification,
                materialized,
            )
        else:
            rejected = await self._repository.append_rejected(
                artifact,
                verification,
                materialized,
                parent_job_id=command.parent_job_id,
                parent_job_attempt_id=command.parent_job_attempt_id,
            )
        return ExecutionResult(
            rejected.artifact_id, rejected.state, verification.status, None, False
        )

    async def restore(
        self,
        *,
        actor_id: str,
        session_id: str,
        source_image_version_id: str,
        target_image_version_id: str,
    ) -> str:
        return await self._transition(
            actor_id, session_id, source_image_version_id, target_image_version_id, "RESTORE"
        )

    async def rollback(
        self,
        *,
        actor_id: str,
        session_id: str,
        source_image_version_id: str,
        target_image_version_id: str,
    ) -> str:
        return await self._transition(
            actor_id, session_id, source_image_version_id, target_image_version_id, "ROLLBACK"
        )

    async def _transition(
        self,
        actor_id: str,
        session_id: str,
        source_image_version_id: str,
        target_image_version_id: str,
        transition: str,
    ) -> str:
        for value, name in (
            (actor_id, "actor_id"),
            (session_id, "session_id"),
            (source_image_version_id, "source_image_version_id"),
            (target_image_version_id, "target_image_version_id"),
        ):
            _require_id(value, name)
        return await self._repository.create_transition(
            actor_id=actor_id,
            session_id=session_id,
            source_image_version_id=source_image_version_id,
            target_image_version_id=target_image_version_id,
            transition=transition,
        )

    async def _recover_or_materialize(
        self, artifact: EditArtifact, command: ExecutionCommand
    ) -> MaterializedObject:
        existing = await self._storage.read(key=artifact.private_object_key)
        if artifact.state is ArtifactState.MATERIALIZED:
            if artifact.materialized is None:
                raise DemoEditingServiceError(
                    "MATERIALIZATION_EVIDENCE_MISSING", "artifact metadata is unavailable"
                )
            _validate_materialization_evidence(artifact.materialized, command)
            if (
                existing is None
                or hashlib.sha256(existing).hexdigest() != artifact.materialized.sha256
            ):
                raise DemoEditingServiceError(
                    "QUARANTINE_RECOVERY_FAILED", "materialized object does not match authority"
                )
            if command.operation.engine is OperationEngine.GEOMETRY:
                replay = await self._dispatch(command)
                _validate_materialized(replay, command)
                if existing != replay.content or len(existing) != artifact.materialized.byte_size:
                    raise DemoEditingServiceError(
                        "MATERIALIZATION_REPLAY_MISMATCH",
                        "geometry replay differs from stable surface",
                    )
                return replay
            recovered_materialization = MaterializedObject(
                content=existing,
                sha256=artifact.materialized.sha256,
                width=artifact.materialized.width,
                height=artifact.materialized.height,
                mime_type=artifact.materialized.mime_type,
                engine_digest=artifact.materialized.engine_digest,
                config_digest=artifact.materialized.config_digest,
            )
            _validate_materialized(recovered_materialization, command)
            if len(existing) != artifact.materialized.byte_size:
                raise DemoEditingServiceError(
                    "QUARANTINE_OBJECT_CONFLICT",
                    "private object size conflicts with materialization",
                )
            return recovered_materialization
        materialized = await self._dispatch(command)
        _validate_materialized(materialized, command)
        if existing is not None and existing != materialized.content:
            raise DemoEditingServiceError(
                "QUARANTINE_OBJECT_CONFLICT", "private object conflicts with reservation"
            )
        await self._storage.put_if_absent(
            key=artifact.private_object_key,
            content=materialized.content,
            sha256=materialized.sha256,
        )
        stored = await self._storage.read(key=artifact.private_object_key)
        if stored is None or hashlib.sha256(stored).hexdigest() != materialized.sha256:
            raise DemoEditingServiceError(
                "QUARANTINE_RECOVERY_FAILED", "private object was not durably written"
            )
        if stored != materialized.content:
            raise DemoEditingServiceError(
                "QUARANTINE_OBJECT_CONFLICT", "private object conflicts with reservation"
            )
        return materialized

    async def _dispatch(self, command: ExecutionCommand) -> MaterializedObject:
        if command.operation.operation_type in {
            OperationType.RESTORE,
            OperationType.ROLLBACK,
        }:
            if self._transition_dispatcher is None:
                raise DemoEditingServiceError(
                    "TRANSITION_RUNTIME_UNAVAILABLE",
                    "transition byte materializer is unavailable",
                )
            return await self._transition_dispatcher(command)
        if command.operation.engine is OperationEngine.RASTER:
            try:
                result = execute_raster_operation(command.source_bytes, command.operation)
            except RasterEditError as exc:
                raise DemoEditingServiceError(exc.code, str(exc)) from exc
            return MaterializedObject(
                result.png_bytes,
                result.output_sha256,
                result.width,
                result.height,
                result.mime_type,
                command.engine_digest,
                command.config_digest,
            )
        if command.operation.engine is OperationEngine.GEOMETRY:
            if self._geometry_dispatcher is None:
                raise DemoEditingServiceError(
                    "GEOMETRY_CAPABILITY_UNAVAILABLE", "geometry dispatcher is unavailable"
                )
            return await self._geometry_dispatcher(command)
        raise DemoEditingServiceError(
            "CAPABILITY_UNAVAILABLE", "operation engine cannot be executed"
        )


def quarantine_object_key(command: ExecutionCommand) -> str:
    """Stable, private key required for storage-before-DB retry recovery."""
    return (
        f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        f"{command.operation_id}/{command.formal_job_attempt_id}"
    )


def _validate_session_command(command: EditingSessionCommand) -> None:
    for value, name in (
        (command.actor_id, "actor_id"),
        (command.session_id, "session_id"),
        (command.source_asset_id, "source_asset_id"),
    ):
        _require_id(value, name)
    for value, name in (
        (command.source_asset_sha256, "source_asset_sha256"),
        (command.desired_delta_profile_digest, "desired_delta_profile_digest"),
        (command.style_profile_digest, "style_profile_digest"),
        (command.identity_constraints_digest, "identity_constraints_digest"),
        (command.context_digest, "context_digest"),
        (command.instruction_digest, "instruction_digest"),
    ):
        _require_digest(value, name)


def _validate_plan_command(command: EditPlanCommand) -> None:
    for value, name in (
        (command.actor_id, "actor_id"),
        (command.session_id, "session_id"),
        (command.editing_session_id, "editing_session_id"),
        (command.input_image_version_id, "input_image_version_id"),
    ):
        _require_id(value, name)
    if not command.operation_specs or any(
        not isinstance(item, OperationSpec) for item in command.operation_specs
    ):
        raise DemoEditingServiceError("INVALID_PLAN", "plan must contain typed operations")


def _validate_execution_command(command: ExecutionCommand) -> None:
    for value, name in (
        (command.actor_id, "actor_id"),
        (command.session_id, "session_id"),
        (command.operation_id, "operation_id"),
        (command.execution_job_binding_id, "execution_job_binding_id"),
        (command.formal_job_attempt_id, "formal_job_attempt_id"),
        (command.source_asset_id, "source_asset_id"),
    ):
        _require_id(value, name)
    for value, name in (
        (command.operation_digest, "operation_digest"),
        (command.source_asset_sha256, "source_asset_sha256"),
        (command.engine_digest, "engine_digest"),
        (command.config_digest, "config_digest"),
    ):
        _require_digest(value, name)
    if (
        not isinstance(command.operation, OperationSpec)
        or type(command.source_bytes) is not bytes
        or not command.source_bytes
    ):
        raise DemoEditingServiceError("INVALID_EXECUTION", "execution input is invalid")
    if hashlib.sha256(command.source_bytes).hexdigest() != command.source_asset_sha256:
        raise DemoEditingServiceError(
            "SOURCE_DIGEST_MISMATCH", "source bytes do not bind source authority"
        )
    if (command.parent_job_id is None) != (command.parent_job_attempt_id is None):
        raise DemoEditingServiceError(
            "INVALID_EXECUTION", "parent Job authority must be provided as a complete pair"
        )
    if command.parent_job_id is not None:
        _require_id(command.parent_job_id, "parent_job_id")
        assert command.parent_job_attempt_id is not None
        _require_id(command.parent_job_attempt_id, "parent_job_attempt_id")
        if command.operation.operation_type not in {
            OperationType.RESTORE,
            OperationType.ROLLBACK,
        }:
            raise DemoEditingServiceError(
                "INVALID_EXECUTION", "only a transition may carry a parent Job"
            )
    geometry_fields = (
        command.editing_session_id,
        command.plan_id,
        command.input_image_version_id,
        command.root_source_asset_id,
        command.geometry_authority,
        command.geometry_job_attempt,
    )
    if command.operation.engine is OperationEngine.GEOMETRY:
        if any(value is None for value in geometry_fields):
            raise DemoEditingServiceError(
                "GEOMETRY_AUTHORITY_MISSING", "geometry requires complete authority"
            )
        assert command.geometry_authority is not None
        assert command.geometry_job_attempt is not None
        if (
            command.geometry_authority.operation_id != command.operation_id
            or command.geometry_authority.operation_authority_digest != command.operation_digest
            or command.geometry_authority.operation_spec_digest
            != operation_spec_digest(command.operation)
            or command.geometry_authority.input_asset_id != command.source_asset_id
            or command.geometry_authority.input_asset_sha256 != command.source_asset_sha256
            or command.geometry_authority.editing_session_id != command.editing_session_id
            or command.geometry_authority.plan_id != command.plan_id
            or command.geometry_authority.input_image_version_id != command.input_image_version_id
            or command.geometry_authority.root_source_asset_id != command.root_source_asset_id
            or command.geometry_job_attempt.execution_job_binding_id
            != command.execution_job_binding_id
            or command.geometry_job_attempt.attempt_id != command.formal_job_attempt_id
        ):
            raise DemoEditingServiceError(
                "GEOMETRY_AUTHORITY_MISMATCH", "geometry authority does not match command"
            )
    elif any(value is not None for value in geometry_fields):
        raise DemoEditingServiceError(
            "GEOMETRY_AUTHORITY_FORBIDDEN", "non-geometry command carries geometry authority"
        )


def _validate_materialized(materialized: MaterializedObject, command: ExecutionCommand) -> None:
    if type(materialized.content) is not bytes or not materialized.content:
        raise DemoEditingServiceError("INVALID_MATERIALIZATION", "output content is invalid")
    _require_digest(materialized.sha256, "materialized sha256")
    if hashlib.sha256(materialized.content).hexdigest() != materialized.sha256:
        raise DemoEditingServiceError("RESULT_DIGEST_MISMATCH", "output digest mismatch")
    if (
        materialized.width <= 0
        or materialized.height <= 0
        or materialized.mime_type not in {"image/jpeg", "image/png"}
    ):
        raise DemoEditingServiceError("INVALID_MATERIALIZATION", "output metadata is invalid")
    if (
        materialized.engine_digest != command.engine_digest
        or materialized.config_digest != command.config_digest
    ):
        raise DemoEditingServiceError(
            "ENGINE_CONFIG_MISMATCH", "materialization must bind reserved engine/config"
        )
    if command.operation.engine is OperationEngine.GEOMETRY:
        core = materialized.geometry_stable_core
        evidence = materialized.geometry_attempt_evidence
        if core is None or evidence is None or command.geometry_authority is None:
            raise DemoEditingServiceError(
                "GEOMETRY_EVIDENCE_MISSING", "geometry materialization lacks typed evidence"
            )
        if (
            core.authority_digest != command.geometry_authority.authority_digest
            or core.operation_id != command.geometry_authority.operation_id
            or core.operation_authority_digest
            != command.geometry_authority.operation_authority_digest
            or core.operation_spec_digest != command.geometry_authority.operation_spec_digest
            or core.case_id != command.geometry_authority.fixed_case.case_id
            or core.case_record_digest != command.geometry_authority.fixed_case.case_record_digest
            or core.case_specification_digest
            != command.geometry_authority.fixed_case.case_specification_digest
            or core.case_binding_digest != command.geometry_authority.fixed_case.case_binding_digest
            or core.backend_candidate_id
            != command.geometry_authority.fixed_case.backend_candidate_id
            or core.backend_algorithm_version
            != command.geometry_authority.fixed_case.backend_algorithm_version
            or core.backend_runtime_manifest_digest
            != command.geometry_authority.fixed_case.backend_runtime_manifest_digest
            or core.backend_configuration_digest
            != command.geometry_authority.fixed_case.backend_configuration_digest
            or core.warp_plan_digest != command.geometry_authority.fixed_case.warp_plan_digest
            or core.input_image_version_id != command.geometry_authority.input_image_version_id
            or core.input_image_version_digest
            != command.geometry_authority.input_image_version_digest
            or core.input_asset_id != command.geometry_authority.input_asset_id
            or core.input_asset_sha256 != command.geometry_authority.input_asset_sha256
            or core.root_source_asset_id != command.geometry_authority.root_source_asset_id
            or core.root_source_asset_sha256 != command.geometry_authority.root_source_asset_sha256
            or core.result_sha256 != materialized.sha256
            or core.result_byte_size != len(materialized.content)
            or core.result_width != materialized.width
            or core.result_height != materialized.height
            or core.result_media_type != materialized.mime_type
            or core.engine_digest != materialized.engine_digest
            or core.config_digest != materialized.config_digest
            or evidence.stable_core_digest != core.stable_core_digest
            or evidence.authority_digest != core.authority_digest
            or evidence.job_attempt != command.geometry_job_attempt
            or evidence.operation_id != command.geometry_authority.operation_id
            or evidence.operation_authority_digest
            != command.geometry_authority.operation_authority_digest
            or evidence.operation_spec_digest != command.geometry_authority.operation_spec_digest
        ):
            raise DemoEditingServiceError(
                "GEOMETRY_EVIDENCE_MISMATCH", "geometry evidence does not match materialization"
            )
    elif (
        materialized.geometry_stable_core is not None
        or materialized.geometry_attempt_evidence is not None
    ):
        raise DemoEditingServiceError(
            "GEOMETRY_EVIDENCE_FORBIDDEN", "non-geometry materialization carries geometry evidence"
        )


def _validate_verification_authority(
    verification: EffectVerificationResult,
    command: ExecutionCommand,
    materialized: MaterializedObject,
) -> None:
    metrics = verification.authority_metrics
    thresholds = verification.authority_thresholds
    if command.operation.engine is not OperationEngine.GEOMETRY:
        if metrics is not None or thresholds is not None:
            raise DemoEditingServiceError(
                "GEOMETRY_VERIFICATION_FORBIDDEN",
                "non-geometry verification carries geometry authority",
            )
        return
    core = materialized.geometry_stable_core
    attempt = materialized.geometry_attempt_evidence
    if (
        core is None
        or attempt is None
        or not isinstance(metrics, Mapping)
        or not isinstance(thresholds, Mapping)
    ):
        raise DemoEditingServiceError(
            "GEOMETRY_VERIFICATION_EVIDENCE_MISSING",
            "geometry requires fresh typed verification evidence",
        )
    required_metrics = {
        "schema_version": _GEOMETRY_METRICS_SCHEMA,
        "authority_digest": core.authority_digest,
        "stable_core_digest": core.stable_core_digest,
        "attempt_receipt_digest": attempt.attempt_receipt_digest,
        "operation_id": core.operation_id,
        "operation_authority_digest": core.operation_authority_digest,
        "operation_spec_digest": core.operation_spec_digest,
        "case_id": core.case_id,
        "result_sha256": materialized.sha256,
    }
    required_thresholds = {
        "schema_version": _GEOMETRY_THRESHOLDS_SCHEMA,
        "policy_digest": verification.policy_digest,
        "repeat_count": 3,
        "target_min_abs_ppm": 10,
        "target_max_abs_ppm": 60_000,
        "max_control_drift_ppm": 20_000,
        "d08_verifier_policy_version": "d08-independent-geometry-verifier-v1",
    }
    if any(metrics.get(key) != value for key, value in required_metrics.items()) or any(
        thresholds.get(key) != value for key, value in required_thresholds.items()
    ):
        raise DemoEditingServiceError(
            "GEOMETRY_VERIFICATION_EVIDENCE_MISMATCH",
            "geometry verification does not match execution authority",
        )
    if verification.result_digest != materialized.sha256:
        raise DemoEditingServiceError(
            "GEOMETRY_VERIFICATION_RESULT_MISMATCH",
            "geometry verification result digest does not match bytes",
        )
    if verification.status is VerificationStatus.PASS and not _valid_geometry_pass_metrics(
        metrics, command
    ):
        raise DemoEditingServiceError(
            "GEOMETRY_VERIFICATION_EVIDENCE_INCOMPLETE",
            "publishable geometry verification lacks complete fresh repeat evidence",
        )


def _valid_geometry_pass_metrics(metrics: Mapping[str, object], command: ExecutionCommand) -> bool:
    authority = command.geometry_authority
    if authority is None:
        return False
    if (
        metrics.get("source_sha256") != authority.root_source_asset_sha256
        or metrics.get("source_asset_id") != authority.root_source_asset_id
        or metrics.get("source_ordinal") != authority.fixed_case.source_ordinal
        or metrics.get("case_ordinal") != authority.fixed_case.case_ordinal
        or metrics.get("dimension_key") != authority.dimension_key
        or metrics.get("direction") != authority.direction.value
        or metrics.get("magnitude_ppm") != authority.magnitude_ppm
        or metrics.get("source_result_digest_distinct") is not True
        or metrics.get("original_immutability_passed") is not True
        or metrics.get("decode_passed") is not True
        or metrics.get("artifact_passed") is not True
        or metrics.get("repeat_gate_passed") is not True
        or metrics.get("measurement_dimension_order") != list(_MEASUREMENT_DIMENSIONS)
    ):
        return False
    runtime_identity = metrics.get("runtime_identity")
    if not isinstance(runtime_identity, Mapping):
        return False
    for key in (
        "recipe_digest",
        "runtime_manifest_digest",
        "model_identity_digest",
        "model_config_digest",
        "weights_digest_or_no_weights",
        "topology_digest",
        "measurement_config_digest",
    ):
        if not _is_digest(runtime_identity.get(key)):
            return False
    if (
        runtime_identity.get("runtime_manifest_digest")
        != authority.fixed_case.backend_runtime_manifest_digest
        or runtime_identity.get("m4_algorithm_version")
        != authority.fixed_case.backend_algorithm_version
        or runtime_identity.get("network_policy") != "PUBLIC_INTERNET_EGRESS_DISABLED"
    ):
        return False
    group = metrics.get("repeat_group_validation")
    if (
        not isinstance(group, Mapping)
        or not group
        or any(value is not True for value in group.values())
    ):
        return False
    repeats = metrics.get("repeats")
    if not isinstance(repeats, list) or len(repeats) != 3:
        return False
    source_receipts: list[str] = []
    result_receipts: list[str] = []
    source_outputs: list[str] = []
    result_outputs: list[str] = []
    source_landmarks: list[str] = []
    result_landmarks: list[str] = []
    for repeat_index, raw in enumerate(repeats, start=1):
        if not isinstance(raw, Mapping) or raw.get("repeat_index") != repeat_index:
            return False
        digest_values: dict[str, str] = {}
        for key in (
            "source_output_digest",
            "source_receipt_digest",
            "source_landmark_digest",
            "source_observation_digest",
            "result_output_digest",
            "result_receipt_digest",
            "result_landmark_digest",
            "result_observation_digest",
        ):
            value = raw.get(key)
            if not _is_digest(value):
                return False
            digest_values[key] = cast(str, value)
        source_outputs.append(digest_values["source_output_digest"])
        source_receipts.append(digest_values["source_receipt_digest"])
        source_landmarks.append(digest_values["source_landmark_digest"])
        result_outputs.append(digest_values["result_output_digest"])
        result_receipts.append(digest_values["result_receipt_digest"])
        result_landmarks.append(digest_values["result_landmark_digest"])
        source_measurements = raw.get("source_measurements_fixed18")
        result_measurements = raw.get("result_measurements_fixed18")
        control_dimensions = raw.get("control_dimensions")
        control_drifts = raw.get("control_drifts_ppm")
        expected_controls = [
            key for key in _MEASUREMENT_DIMENSIONS if key != authority.dimension_key
        ]
        if (
            not isinstance(source_measurements, list)
            or len(source_measurements) != 6
            or any(
                not isinstance(value, str) or _FIXED18.fullmatch(value) is None
                for value in source_measurements
            )
            or not isinstance(result_measurements, list)
            or len(result_measurements) != 6
            or any(
                not isinstance(value, str) or _FIXED18.fullmatch(value) is None
                for value in result_measurements
            )
            or not isinstance(control_dimensions, list)
            or control_dimensions != expected_controls
            or not isinstance(control_drifts, list)
            or len(control_drifts) != 5
            or any(type(value) is not int or not 0 <= value <= 20_000 for value in control_drifts)
        ):
            return False
        signed_target = raw.get("signed_target_delta_ppm")
        if (
            type(signed_target) is not int
            or not 10 <= abs(signed_target) <= 60_000
            or (signed_target > 0) != (authority.direction.value == "INCREASE")
            or raw.get("max_control_drift_ppm") != max(control_drifts)
            or raw.get("max_control_dimension_key")
            != control_dimensions[control_drifts.index(max(control_drifts))]
            or any(
                raw.get(key) is not True
                for key in (
                    "direction_passed",
                    "target_minimum_passed",
                    "target_maximum_passed",
                    "control_drift_passed",
                    "observation_passed",
                )
            )
        ):
            return False
    return (
        len(set(source_receipts)) == 3
        and len(set(result_receipts)) == 3
        and len(set(source_outputs)) == 3
        and len(set(result_outputs)) == 3
        and len(set(source_landmarks)) == 1
        and len(set(result_landmarks)) == 1
    )


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _validate_materialization_evidence(
    evidence: MaterializationEvidence, command: ExecutionCommand
) -> None:
    _require_digest(evidence.sha256, "materialized sha256")
    if (
        type(evidence.byte_size) is not int
        or evidence.byte_size <= 0
        or type(evidence.width) is not int
        or evidence.width <= 0
        or type(evidence.height) is not int
        or evidence.height <= 0
        or evidence.mime_type not in {"image/jpeg", "image/png"}
    ):
        raise DemoEditingServiceError(
            "INVALID_MATERIALIZATION", "materialization evidence is invalid"
        )
    if (
        evidence.engine_digest != command.engine_digest
        or evidence.config_digest != command.config_digest
    ):
        raise DemoEditingServiceError(
            "ENGINE_CONFIG_MISMATCH", "materialization must bind reserved engine/config"
        )


def _validate_artifact_matches(artifact: EditArtifact, command: ExecutionCommand, key: str) -> None:
    if (
        artifact.actor_id != command.actor_id
        or artifact.session_id != command.session_id
        or artifact.operation_id != command.operation_id
        or artifact.execution_job_binding_id != command.execution_job_binding_id
        or artifact.formal_job_attempt_id != command.formal_job_attempt_id
        or artifact.private_object_key != key
    ):
        raise DemoEditingServiceError(
            "ARTIFACT_OWNERSHIP_MISMATCH", "reserved artifact does not bind execution authority"
        )


def _require_id(value: str, name: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise DemoEditingServiceError(
            "INVALID_ID", f"{name} must be 32 lowercase hexadecimal characters"
        )


def _require_digest(value: str, name: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise DemoEditingServiceError("INVALID_DIGEST", f"{name} must be a SHA-256 digest")
