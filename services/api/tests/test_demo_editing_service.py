from __future__ import annotations

import hashlib
import io
from dataclasses import replace

import pytest
from PIL import Image

from mirror_api.demo_editing_service import (
    ArtifactState,
    DemoEditingService,
    DemoEditingServiceError,
    EditArtifact,
    EditingSessionCommand,
    EditPlanCommand,
    ExecutionCommand,
    MaterializationEvidence,
    MaterializedObject,
    Promotion,
)
from mirror_api.demo_effect_verifier import (
    EffectVerificationInput,
    EffectVerificationResult,
    EffectVerifierPolicy,
    VerificationStatus,
    verify_effect,
)
from mirror_api.demo_operation_graph import (
    OperationEngine,
    OperationSpec,
    OperationType,
    PreserveKey,
)


def _id(char: str) -> str:
    return char * 32


def _digest(char: str) -> str:
    return char * 64


def _source() -> bytes:
    output = io.BytesIO()
    with Image.new("RGB", (12, 10), (20, 40, 60)) as image:
        image.save(output, format="JPEG", quality=93)
    return output.getvalue()


def _spec() -> OperationSpec:
    parameters = {"exposure_ev_milli": 100}
    return OperationSpec(
        engine=OperationEngine.RASTER,
        operation_type=OperationType.EXPOSURE,
        parameters=parameters,
        preserve=(PreserveKey.IDENTITY_REFERENCE_FRAME,),
        expected_effect={"effect_type": "EXPOSURE", "target_region": "FULL_IMAGE", **parameters},
    )


def _command() -> ExecutionCommand:
    source = _source()
    return ExecutionCommand(
        actor_id=_id("a"),
        session_id=_id("b"),
        operation_id=_id("c"),
        operation_digest=_digest("d"),
        execution_job_binding_id=_id("e"),
        formal_job_attempt_id=_id("f"),
        source_asset_id=_id("1"),
        source_asset_sha256=hashlib.sha256(source).hexdigest(),
        source_bytes=source,
        operation=_spec(),
        engine_version="raster-v1",
        engine_digest=_digest("2"),
        config_digest=_digest("3"),
    )


class _Storage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put_if_absent(self, *, key: str, content: bytes, sha256: str) -> None:
        assert hashlib.sha256(content).hexdigest() == sha256
        existing = self.objects.setdefault(key, content)
        if existing != content:
            raise RuntimeError("conflict")

    async def read(self, *, key: str) -> bytes | None:
        return self.objects.get(key)

    async def promote_from_quarantine(self, *, key: str, artifact_id: str, sha256: str) -> str:
        content = self.objects[key]
        assert hashlib.sha256(content).hexdigest() == sha256
        published_key = f"demo-published/v1/{artifact_id}/{sha256}"
        self.objects.setdefault(published_key, content)
        return published_key

    async def discard_published(self, *, key: str, sha256: str) -> None:
        content = self.objects.get(key)
        if content is not None:
            assert hashlib.sha256(content).hexdigest() == sha256
            del self.objects[key]


class _Repository:
    def __init__(self) -> None:
        self.artifact: EditArtifact | None = None
        self.promotions = 0
        self.rejections = 0
        self.transitions: list[tuple[str, str, str, str, str]] = []
        self.sessions = 0
        self.plans = 0

    async def create_editing_session(self, command: EditingSessionCommand) -> str:
        self.sessions += 1
        return _id("7")

    async def persist_plan(self, command: EditPlanCommand) -> str:
        self.plans += 1
        return _id("8")

    async def reserve_execution(self, command: ExecutionCommand, object_key: str) -> EditArtifact:
        if self.artifact is None:
            self.artifact = EditArtifact(
                artifact_id=_id("9"),
                actor_id=command.actor_id,
                session_id=command.session_id,
                operation_id=command.operation_id,
                execution_job_binding_id=command.execution_job_binding_id,
                formal_job_attempt_id=command.formal_job_attempt_id,
                private_object_key=object_key,
                state=ArtifactState.RESERVED,
            )
        return self.artifact

    async def append_materialized(
        self, artifact: EditArtifact, materialized: MaterializedObject
    ) -> EditArtifact:
        self.artifact = replace(
            artifact,
            state=ArtifactState.MATERIALIZED,
            materialized=MaterializationEvidence(
                sha256=materialized.sha256,
                byte_size=len(materialized.content),
                width=materialized.width,
                height=materialized.height,
                mime_type=materialized.mime_type,
                engine_digest=materialized.engine_digest,
                config_digest=materialized.config_digest,
            ),
        )
        return self.artifact

    async def append_rejected(
        self,
        artifact: EditArtifact,
        verification: object,
        materialized: MaterializedObject,
        **_: str | None,
    ) -> EditArtifact:
        self.rejections += 1
        self.artifact = replace(artifact, state=ArtifactState.REJECTED)
        return self.artifact

    async def promote_pass(
        self,
        artifact: EditArtifact,
        verification: object,
        materialized: MaterializedObject,
        published_storage_key: str,
        **_: str | None,
    ) -> Promotion:
        assert published_storage_key.startswith("demo-published/v1/")
        self.promotions += 1
        self.artifact = replace(artifact, state=ArtifactState.PROMOTED)
        return Promotion(_id("4"), _id("5"), _id("6"), _id("0"))

    async def create_transition(
        self,
        *,
        actor_id: str,
        session_id: str,
        source_image_version_id: str,
        target_image_version_id: str,
        transition: str,
    ) -> str:
        self.transitions.append(
            (actor_id, session_id, source_image_version_id, target_image_version_id, transition)
        )
        return _id("a" if transition == "RESTORE" else "b")


class _Verifier:
    def __init__(self, status: str = "PASS") -> None:
        self.status = status

    async def __call__(
        self, command: ExecutionCommand, materialized: MaterializedObject
    ) -> EffectVerificationResult:
        policy = EffectVerifierPolicy(
            target_tolerance_ppm=1,
            structural_drift_thresholds_ppm={"jaw_width": 1},
            locked_drift_thresholds_ppm={},
            non_target_drift_threshold_ppm=1,
            allowed_media_types=("image/jpeg", "image/png"),
        )
        return verify_effect(
            policy,
            EffectVerificationInput(
                source_asset_id=command.source_asset_id,
                result_asset_id=_id("d"),
                target_dimension_key="jaw_width",
                operation_digest=command.operation_digest,
                requested_delta_ppm=0,
                measured_delta_ppm=0,
                structural_drifts_ppm={"jaw_width": 0},
                locked_drifts_ppm={},
                non_target_drift_ppm=0,
                artifact_status=self.status,
                artifact_codes=(),
                original_before_sha256=command.source_asset_sha256,
                original_after_sha256=command.source_asset_sha256,
                result_bytes=materialized.content,
                declared_result_sha256=materialized.sha256,
                decode_valid=True,
                width=materialized.width,
                height=materialized.height,
                media_type=materialized.mime_type,
            ),
        )


def _service(
    repo: _Repository,
    storage: _Storage,
    verifier: _Verifier,
    transition_dispatcher: object | None = None,
) -> DemoEditingService:
    return DemoEditingService(
        repository=repo,
        storage=storage,
        verifier=verifier,
        transition_dispatcher=transition_dispatcher,
    )


def _restore_command() -> ExecutionCommand:
    source = _source()
    target_id, target_digest = _id("7"), _digest("8")
    parameters = {
        "target_image_version_id": target_id,
        "target_image_version_digest": target_digest,
    }
    return ExecutionCommand(
        actor_id=_id("a"),
        session_id=_id("b"),
        operation_id=_id("c"),
        operation_digest=_digest("d"),
        execution_job_binding_id=_id("e"),
        formal_job_attempt_id=_id("f"),
        source_asset_id=_id("1"),
        source_asset_sha256=hashlib.sha256(source).hexdigest(),
        source_bytes=source,
        operation=OperationSpec(
            engine=OperationEngine.RASTER,
            operation_type=OperationType.RESTORE,
            parameters=parameters,
            preserve=(PreserveKey.TARGET_VERSION_BYTES,),
            expected_effect={
                "effect_type": "RESTORE",
                "target_region": "VERSION_CONTENT",
                "target_image_version_digest": target_digest,
            },
        ),
        engine_version="restore-v1",
        engine_digest=_digest("2"),
        config_digest=_digest("3"),
        parent_job_id=_id("4"),
        parent_job_attempt_id=_id("5"),
    )


class _TransitionDispatcher:
    def __init__(self) -> None:
        self.commands: list[ExecutionCommand] = []

    async def __call__(self, command: ExecutionCommand) -> MaterializedObject:
        self.commands.append(command)
        content = b"synthetic-only-restored-bytes"
        return MaterializedObject(
            content=content,
            sha256=hashlib.sha256(content).hexdigest(),
            width=12,
            height=10,
            mime_type="image/png",
            engine_digest=command.engine_digest,
            config_digest=command.config_digest,
        )


@pytest.mark.asyncio
async def test_pass_materializes_privately_then_promotes_once() -> None:
    repo, storage = _Repository(), _Storage()
    result = await _service(repo, storage, _Verifier()).execute(_command())
    assert result.state is ArtifactState.PROMOTED
    assert result.verification_status is VerificationStatus.PASS
    assert result.promotion is not None
    assert repo.promotions == 1 and repo.rejections == 0
    assert len(storage.objects) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["FAIL", "HUMAN_REVIEW"])
async def test_non_pass_never_promotes(status: str) -> None:
    repo, storage = _Repository(), _Storage()
    result = await _service(repo, storage, _Verifier(status)).execute(_command())
    assert result.state is ArtifactState.REJECTED
    assert result.promotion is None
    assert repo.promotions == 0 and repo.rejections == 1
    assert len(storage.objects) == 1


@pytest.mark.asyncio
async def test_duplicate_delivery_replays_terminal_artifact_without_reexecution() -> None:
    repo, storage = _Repository(), _Storage()
    service = _service(repo, storage, _Verifier())
    first = await service.execute(_command())
    second = await service.execute(_command())
    assert first.state is ArtifactState.PROMOTED
    assert second.replayed is True
    assert repo.promotions == 1


@pytest.mark.asyncio
async def test_conflicting_preexisting_object_fails_closed() -> None:
    repo, storage = _Repository(), _Storage()
    command = _command()
    key = (
        f"demo-quarantine/{command.actor_id}/{command.execution_job_binding_id}/"
        f"{command.operation_id}/{command.formal_job_attempt_id}"
    )
    storage.objects[key] = b"wrong-result"
    with pytest.raises(DemoEditingServiceError) as error:
        await _service(repo, storage, _Verifier()).execute(command)
    assert error.value.code == "QUARANTINE_OBJECT_CONFLICT"


@pytest.mark.asyncio
async def test_restore_execution_fails_closed_without_transition_dispatcher() -> None:
    repo, storage = _Repository(), _Storage()
    with pytest.raises(DemoEditingServiceError) as error:
        await _service(repo, storage, _Verifier()).execute(_restore_command())
    assert error.value.code == "TRANSITION_RUNTIME_UNAVAILABLE"
    assert repo.promotions == 0 and repo.rejections == 0


@pytest.mark.asyncio
async def test_restore_execution_only_uses_injected_transition_dispatcher() -> None:
    repo, storage, dispatcher = _Repository(), _Storage(), _TransitionDispatcher()
    command = _restore_command()
    result = await _service(repo, storage, _Verifier(), dispatcher).execute(command)
    assert result.state is ArtifactState.PROMOTED
    assert dispatcher.commands == [command]
    assert repo.promotions == 1 and repo.rejections == 0


@pytest.mark.asyncio
async def test_restore_and_rollback_delegate_to_new_version_authority() -> None:
    repo, storage = _Repository(), _Storage()
    service = _service(repo, storage, _Verifier())
    restored = await service.restore(
        actor_id=_id("a"),
        session_id=_id("b"),
        source_image_version_id=_id("c"),
        target_image_version_id=_id("d"),
    )
    rolled_back = await service.rollback(
        actor_id=_id("a"),
        session_id=_id("b"),
        source_image_version_id=_id("d"),
        target_image_version_id=_id("c"),
    )
    assert restored != rolled_back
    assert [item[-1] for item in repo.transitions] == ["RESTORE", "ROLLBACK"]


@pytest.mark.asyncio
async def test_editing_session_and_typed_plan_are_delegated_to_authority() -> None:
    repo, storage = _Repository(), _Storage()
    service = _service(repo, storage, _Verifier())
    session = await service.create_editing_session(
        EditingSessionCommand(
            _id("a"),
            _id("b"),
            _id("c"),
            _digest("d"),
            _digest("e"),
            _digest("f"),
            _digest("0"),
            _digest("1"),
            _digest("2"),
            "registry-v1",
        )
    )
    plan = await service.persist_plan(
        EditPlanCommand(
            _id("a"), _id("b"), session, _id("3"), (_spec(),), "planner-v1", "registry-v1"
        )
    )
    assert session == _id("7") and plan == _id("8")
    assert repo.sessions == 1 and repo.plans == 1
