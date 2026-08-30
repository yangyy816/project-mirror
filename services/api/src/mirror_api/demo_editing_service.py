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
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from mirror_api.demo_effect_verifier import EffectVerificationResult, VerificationStatus
from mirror_api.demo_operation_graph import OperationEngine, OperationSpec, OperationType
from mirror_api.demo_raster_editor import RasterEditError, execute_raster_operation

_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class DemoEditingServiceError(RuntimeError):
    """A fail-closed application error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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
    source_bytes: bytes
    operation: OperationSpec
    engine_version: str
    engine_digest: str
    config_digest: str
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
    content: bytes
    sha256: str
    width: int
    height: int
    mime_type: str
    engine_digest: str
    config_digest: str


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
        if verification.status is VerificationStatus.PASS:
            published_storage_key = await self._storage.promote_from_quarantine(
                key=artifact.private_object_key,
                artifact_id=artifact.artifact_id,
                sha256=materialized.sha256,
            )
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
