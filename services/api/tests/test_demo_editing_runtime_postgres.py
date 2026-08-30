"""Real PostgreSQL admission and end-to-end D07 runtime checks."""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from PIL import Image
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_schema_authority_invariants import (
    _insert_demo_row,
    _insert_full_demo_graph,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)

from mirror_api.demo_editing_asset_loader import LocalDemoAssetByteLoader
from mirror_api.demo_editing_commands import (
    CreateDemoEditingSession,
    CreateDemoEditPlan,
    DemoEditingCommandAccepted,
    DemoEditingCommandService,
    ExecuteDemoEditPlan,
    RestoreDemoImageVersion,
)
from mirror_api.demo_editing_runtime import DemoEditingRuntime
from mirror_api.demo_editing_storage import (
    DemoEditingStorageError,
    DemoLocalPrivateObjectStorage,
)
from mirror_api.demo_editing_task_contract import DemoEditingOperation, DemoEditingTaskMessage
from mirror_api.demo_editing_verifier_adapter import DemoDeterministicEditVerifier
from mirror_api.demo_idempotency import DemoIdempotencyPayloadConflict
from mirror_api.demo_models import (
    DemoEditArtifact,
    DemoEditingSession,
    DemoIdentityConstraints,
    DemoImageVersion,
    DemoJobBinding,
    DemoToolRun,
    DemoVerificationResult,
)
from mirror_api.demo_operation_graph import OperationType
from mirror_api.models import Asset, Job, new_id, utcnow

pytestmark = pytest.mark.integration


class _FailOnceOriginalStorage(DemoLocalPrivateObjectStorage):
    def __init__(self, *, root: Path) -> None:
        super().__init__(root=root)
        self.failed = False

    async def store_original_snapshot(
        self, *, editing_session_id: str, content: bytes, sha256: str
    ) -> str:
        if not self.failed:
            self.failed = True
            raise DemoEditingStorageError(
                "STORAGE_WRITE_FAILED", "simulated recoverable storage interruption"
            )
        return await super().store_original_snapshot(
            editing_session_id=editing_session_id,
            content=content,
            sha256=sha256,
        )


@pytest.fixture
def postgres_session() -> Generator[Session]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url.replace("+asyncpg", "+psycopg"))
    with Session(engine) as db_session:
        _truncate_demo_authority(db_session)
        _truncate_formal_synthetic_fixture_authority(db_session)
        yield db_session
        db_session.rollback()
        _truncate_demo_authority(db_session)
        _truncate_formal_synthetic_fixture_authority(db_session)
    engine.dispose()


def _png(color: tuple[int, int, int]) -> bytes:
    output = io.BytesIO()
    with Image.new("RGB", (16, 12), color) as image:
        image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def _source_asset(session: Session, root: Path, *, color: tuple[int, int, int]) -> Asset:
    content = _png(color)
    digest = hashlib.sha256(content).hexdigest()
    storage_key = f"internal-synthetic/v1/normalized/{digest}"
    payload = root.joinpath(*storage_key.split("/"), "payload")
    payload.parent.mkdir(parents=True)
    payload.write_bytes(content)
    asset = Asset(
        id=new_id(),
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key=storage_key,
        mime_type="image/png",
        byte_size=len(content),
        width=16,
        height=12,
        sha256=digest,
        synthetic=True,
        is_ai_generated=True,
        is_ai_modified=False,
        deleted_at=None,
    )
    session.add(asset)
    session.commit()
    return asset


def _persistent_constraints(session: Session, graph: dict[str, Any]) -> None:
    actor = graph["actor"]
    self_state = graph["self_state"]
    source_event = graph["source_event"]
    _insert_demo_row(
        session,
        DemoIdentityConstraints,
        demo_actor_id=actor.id,
        demo_session_id=None,
        self_state_id=self_state.id,
        version=2,
        constraint_scope="PERSISTENT",
        source_event_digests=[source_event.content_digest],
        locks={"eyes": "PRESERVE"},
        bounds={"max_ppm": 100_000},
        prohibited_operations=[],
    )


def _message(
    actor_id: str,
    accepted: DemoEditingCommandAccepted,
    operation: DemoEditingOperation,
) -> DemoEditingTaskMessage:
    return DemoEditingTaskMessage(
        demo_actor_id=actor_id,
        job_id=accepted.job_id,
        operation=operation,
        request_id=accepted.request_id,
    )


@pytest.mark.asyncio
async def test_command_admission_runtime_restore_and_replay_are_postgresql_authoritative(
    postgres_session: Session, tmp_path: Path
) -> None:
    graph = _insert_full_demo_graph(postgres_session, include_episode=False)
    _persistent_constraints(postgres_session, graph)
    source = _source_asset(postgres_session, tmp_path, color=(80, 120, 160))
    concurrent_source = _source_asset(postgres_session, tmp_path, color=(160, 120, 80))
    database_url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    commands = DemoEditingCommandService(session_factory=sessions)
    loader = LocalDemoAssetByteLoader(root=tmp_path)
    storage = DemoLocalPrivateObjectStorage(root=tmp_path)
    runtime = DemoEditingRuntime(
        session_factory=sessions,
        asset_loader=loader,
        storage=storage,
        verifier=DemoDeterministicEditVerifier(
            session_factory=sessions,
            asset_loader=loader,
        ),
    )
    actor_id = graph["actor"].id
    session_id = graph["session"].id
    try:
        create = CreateDemoEditingSession(
            actor_id,
            session_id,
            "d07-create-key",
            "d07-create-request",
            source_asset_id=source.id,
        )
        accepted = await commands.create_editing_session(create)
        replay = await commands.create_editing_session(
            CreateDemoEditingSession(
                actor_id,
                session_id,
                "d07-create-key",
                "different-request-id",
                source_asset_id=source.id,
            )
        )
        assert replay.replayed is True
        assert replay.job_id == accepted.job_id
        assert replay.target_id == accepted.target_id
        assert replay.request_id == accepted.request_id
        with pytest.raises(DemoIdempotencyPayloadConflict):
            await commands.create_editing_session(
                CreateDemoEditingSession(
                    actor_id,
                    session_id,
                    "d07-create-key",
                    "d07-conflict-request",
                    source_image_version_id=graph["image0"].id,
                )
            )

        concurrent = await asyncio.gather(
            *(
                commands.create_editing_session(
                    CreateDemoEditingSession(
                        actor_id,
                        session_id,
                        "d07-concurrent-key",
                        f"d07-concurrent-{index}",
                        source_asset_id=concurrent_source.id,
                    )
                )
                for index in range(2)
            )
        )
        assert len({item.job_id for item in concurrent}) == 1
        assert len({item.target_id for item in concurrent}) == 1
        assert sorted(item.replayed for item in concurrent) == [False, True]

        transient_runtime = DemoEditingRuntime(
            session_factory=sessions,
            asset_loader=loader,
            storage=_FailOnceOriginalStorage(root=tmp_path),
            verifier=DemoDeterministicEditVerifier(
                session_factory=sessions,
                asset_loader=loader,
            ),
        )
        deferred = await transient_runtime.run(
            _message(actor_id, accepted, "editing_session.create")
        )
        assert (deferred.status, deferred.result_code) == ("RUNNING", None)
        assert accepted.job_id in {
            candidate.job_id for candidate in await commands.reconciliation_candidates(limit=100)
        }
        initialized = await runtime.run(_message(actor_id, accepted, "editing_session.create"))
        assert (initialized.status, initialized.result_code) == (
            "COMPLETED",
            "EDITING_SESSION_INITIALIZED",
        )
        postgres_session.expire_all()
        create_job = postgres_session.get(Job, accepted.job_id)
        assert create_job is not None and create_job.attempt_count == 2
        initialized_replay = await runtime.run(
            _message(actor_id, accepted, "editing_session.create")
        )
        assert initialized_replay.replayed is True

        before_jobs = postgres_session.scalar(select(func.count()).select_from(Job))
        before_plans = postgres_session.scalar(select(func.count()).select_from(DemoJobBinding))
        with pytest.raises(ValueError, match="quantizes to zero"):
            await commands.create_edit_plan(
                CreateDemoEditPlan(
                    actor_id,
                    accepted.target_id,
                    OperationType.EXPOSURE,
                    0,
                    "d07-invalid-plan-key",
                    "d07-invalid-plan-request",
                )
            )
        postgres_session.expire_all()
        assert postgres_session.scalar(select(func.count()).select_from(Job)) == before_jobs
        assert (
            postgres_session.scalar(select(func.count()).select_from(DemoJobBinding))
            == before_plans
        )

        plan = await commands.create_edit_plan(
            CreateDemoEditPlan(
                actor_id,
                accepted.target_id,
                OperationType.EXPOSURE,
                250_000,
                "d07-plan-key",
                "d07-plan-request",
            )
        )
        assert (await runtime.run(_message(actor_id, plan, "edit_plan.create"))).status == (
            "COMPLETED"
        )
        postgres_session.expire_all()
        result_plan = postgres_session.get(type(graph["result_plan"]), plan.target_id)
        assert result_plan is not None
        execution = await commands.execute_edit_plan(
            ExecuteDemoEditPlan(
                actor_id,
                plan.target_id,
                "DETERMINISTIC_RASTER",
                result_plan.content_digest,
                "d07-execution-key",
                "d07-execution-request",
            )
        )
        executed = await runtime.run(_message(actor_id, execution, "edit_plan.execute"))
        assert executed.status == "COMPLETED"
        assert (
            await runtime.run(_message(actor_id, execution, "edit_plan.execute"))
        ).replayed is True

        postgres_session.expire_all()
        versions = postgres_session.scalars(
            select(DemoImageVersion)
            .where(DemoImageVersion.editing_session_id == accepted.target_id)
            .order_by(DemoImageVersion.sequence)
        ).all()
        assert [item.sequence for item in versions] == [0, 1]
        assert postgres_session.scalar(select(func.count()).select_from(DemoEditArtifact)) == 2
        assert (
            cast(int, postgres_session.scalar(select(func.count()).select_from(DemoToolRun))) >= 2
        )
        assert (
            cast(
                int,
                postgres_session.scalar(select(func.count()).select_from(DemoVerificationResult)),
            )
            >= 2
        )

        original, current = versions
        restore = await commands.restore_image_version(
            RestoreDemoImageVersion(
                actor_id,
                original.id,
                current.id,
                current.content_digest,
                "d07-restore-key",
                "d07-restore-request",
            )
        )
        restore_message = _message(actor_id, restore, "image_version.restore")
        parent_claim = await runtime._claim(restore_message)
        assert parent_claim is not None
        child_claim = await runtime._claim_restore_child(parent_claim)
        assert child_claim is not None

        postgres_session.rollback()
        postgres_session.execute(
            update(Job)
            .where(Job.id.in_((parent_claim.job_id, child_claim.job_id)))
            .values(lease_expires_at=utcnow() - timedelta(seconds=1))
        )
        postgres_session.commit()
        candidates = await commands.reconciliation_candidates()
        candidate_ids = {item.job_id for item in candidates}
        assert parent_claim.job_id in candidate_ids
        assert child_claim.job_id in candidate_ids
        child_replay = await runtime.run(
            DemoEditingTaskMessage(
                demo_actor_id=actor_id,
                job_id=child_claim.job_id,
                operation="edit_plan.execute",
                request_id=f"d07-restore-{parent_claim.job_id}",
            )
        )
        assert (child_replay.status, child_replay.replayed) == ("RUNNING", True)

        restored_result = await runtime.run(restore_message)
        assert restored_result.status == "COMPLETED"
        postgres_session.expire_all()
        restore_jobs = {
            item.id: item
            for item in postgres_session.scalars(
                select(Job).where(Job.id.in_((parent_claim.job_id, child_claim.job_id)))
            ).all()
        }
        assert restore_jobs[parent_claim.job_id].attempt_count == 2
        assert restore_jobs[child_claim.job_id].attempt_count == 2
        assert {item.status for item in restore_jobs.values()} == {"COMPLETED"}
        postgres_session.expire_all()
        restored = postgres_session.scalar(
            select(DemoImageVersion)
            .where(DemoImageVersion.editing_session_id == accepted.target_id)
            .order_by(DemoImageVersion.sequence.desc())
            .limit(1)
        )
        assert restored is not None
        assert restored.sequence == 2
        assert restored.version_kind == "RESTORED"
        assert restored.result_asset_sha256 == original.result_asset_sha256
        assert restored.result_asset_id not in {
            original.result_asset_id,
            current.result_asset_id,
        }
        assert (
            await runtime.run(_message(actor_id, restore, "image_version.restore"))
        ).replayed is True

        editing_rows = postgres_session.scalars(
            select(DemoEditingSession).where(
                DemoEditingSession.demo_actor_id == actor_id,
                DemoEditingSession.source_asset_id == source.id,
            )
        ).all()
        assert len(editing_rows) == 1
        assert (
            len(
                postgres_session.scalars(
                    select(DemoEditingSession).where(
                        DemoEditingSession.demo_actor_id == actor_id,
                        DemoEditingSession.source_asset_id == concurrent_source.id,
                    )
                ).all()
            )
            == 1
        )
    finally:
        await engine.dispose()
