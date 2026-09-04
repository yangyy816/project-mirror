"""Real PostgreSQL admission and end-to-end D07 runtime checks."""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
from collections.abc import Generator
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from PIL import Image
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from test_demo_d02_generic_admission import _generic_admission_bundle
from test_demo_schema_authority_invariants import (
    _insert_actor,
    _insert_demo_row,
    _insert_full_demo_graph,
    _insert_session,
    _truncate_demo_authority,
    _truncate_formal_synthetic_fixture_authority,
)

from mirror_api.demo_d02_generic_admission_coordinator import D02GenericAdmissionCoordinator
from mirror_api.demo_editing_asset_loader import LocalDemoAssetByteLoader
from mirror_api.demo_editing_commands import (
    CreateDemoEditingSession,
    CreateDemoEditPlan,
    DemoEditingCommandAccepted,
    DemoEditingCommandAuthorityCorruption,
    DemoEditingCommandService,
    DemoEditingCommandUnavailable,
    DemoEditResultNotReady,
    DemoEditResultTerminal,
    ExecuteDemoEditPlan,
    RestoreDemoImageVersion,
)
from mirror_api.demo_editing_repository import (
    DemoEditingRepositoryError,
    SqlAlchemyDemoEditingRepository,
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
    D02SelectedSourceManifest,
    DemoEditArtifact,
    DemoEditArtifactEvent,
    DemoEditingSession,
    DemoIdentityConstraints,
    DemoImageVersion,
    DemoJobBinding,
    DemoPairScreeningReport,
    DemoToolRun,
    DemoVerificationResult,
)
from mirror_api.demo_operation_graph import OperationType
from mirror_api.models import Asset, Job, new_id, utcnow

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy() -> Any:
    if os.name == "nt":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


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
async def test_d02_generic_source_authority_is_required_and_revalidated(
    postgres_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D07 accepts only a complete public generic D02 SOURCE authority."""
    bundle = _generic_admission_bundle(postgres_session, tmp_path)
    database_url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        postgres_session.commit()
        await D02GenericAdmissionCoordinator(session_factory=sessions).admit(
            idempotency_key="d07-generic-source", bundle=bundle
        )
        actor = _insert_actor(postgres_session, actor_id="a" * 32)
        demo_session = _insert_session(postgres_session, actor, config={})
        source_id = cast(str, bundle.source_rows[0]["source_asset_id"])
        result_entry = next(
            entry
            for entry in cast(
                list[dict[str, object]],
                bundle.report_row["report_payload"]["asset_authority_manifest"],
            )
            if entry["asset_kind"] == "RESULT"
        )
        result_id = cast(str, result_entry["asset_id"])
        monkeypatch.setattr(
            "mirror_api.demo_editing_repository._is_d02_internal_asset",
            lambda asset: asset.id in {source_id, result_id},
        )
        repository = SqlAlchemyDemoEditingRepository(session_factory=sessions)
        commands = DemoEditingCommandService(session_factory=sessions)
        async with sessions() as session:
            source = await session.get(Asset, source_id)
            result = await session.get(Asset, result_id)
            assert source is not None and result is not None
            selected = await commands._source_asset(
                session,
                CreateDemoEditingSession(
                    actor.id,
                    demo_session.id,
                    "d07-d02-source-selection",
                    "d07-d02-source-selection-request",
                    source_asset_id=source.id,
                ),
                demo_session,
            )
            assert selected.id == source.id
            with pytest.raises(DemoEditingCommandUnavailable):
                await commands._source_asset(
                    session,
                    CreateDemoEditingSession(
                        actor.id,
                        demo_session.id,
                        "d07-d02-result-selection",
                        "d07-d02-result-selection-request",
                        source_asset_id=result.id,
                    ),
                    demo_session,
                )
            await repository._require_generic_d02_source_authority(session, source)
            with pytest.raises(DemoEditingRepositoryError) as result_rejected:
                await repository._require_generic_d02_source_authority(session, result)
            assert result_rejected.value.code == "D02_SOURCE_AUTHORITY_UNAVAILABLE"

        async with sessions() as session:
            source = await session.get(Asset, source_id)
            report = await session.get(DemoPairScreeningReport, cast(str, bundle.report_row["id"]))
            assert source is not None and report is not None
            tampered_report = deepcopy(report.report_payload)
            assets = cast(list[dict[str, object]], tampered_report["asset_authority_manifest"])
            tampered_report["asset_authority_manifest"] = assets[:-1]
            report.report_payload = tampered_report
            with session.no_autoflush:
                with pytest.raises(DemoEditingRepositoryError) as report_rejected:
                    await repository._require_generic_d02_source_authority(session, source)
            assert report_rejected.value.code == "D02_ADMISSION_UNAVAILABLE"
            await session.rollback()

        async with sessions() as session:
            source = await session.get(Asset, source_id)
            manifest = await session.get(
                D02SelectedSourceManifest, cast(str, bundle.selected_manifest["id"])
            )
            assert source is not None and manifest is not None
            manifest.canonical_payload = {
                **manifest.canonical_payload,
                "source_count": 3,
            }
            with session.no_autoflush:
                with pytest.raises(DemoEditingRepositoryError) as manifest_rejected:
                    await repository._require_generic_d02_source_authority(session, source)
            assert manifest_rejected.value.code == "D02_ADMISSION_UNAVAILABLE"
            await session.rollback()

        async with sessions() as session:
            source = await session.get(Asset, source_id)
            assert source is not None
            source.sha256 = hashlib.sha256(b"wrong-d02-source-sha").hexdigest()
            with session.no_autoflush:
                with pytest.raises(DemoEditingRepositoryError) as changed_rejected:
                    await repository._require_generic_d02_source_authority(session, source)
            assert changed_rejected.value.code == "D02_SOURCE_AUTHORITY_UNAVAILABLE"
            await session.rollback()
    finally:
        await engine.dispose()


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
        with pytest.raises(DemoEditResultNotReady):
            await commands.read_execution_result(
                demo_actor_id=actor_id,
                job_id=execution.job_id,
            )
        with pytest.raises(DemoEditingCommandUnavailable):
            await commands.read_execution_result(
                demo_actor_id=new_id(),
                job_id=execution.job_id,
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

        result_counts_before = (
            postgres_session.scalar(select(func.count()).select_from(Job)),
            postgres_session.scalar(select(func.count()).select_from(DemoEditArtifact)),
            postgres_session.scalar(select(func.count()).select_from(DemoToolRun)),
            postgres_session.scalar(select(func.count()).select_from(DemoVerificationResult)),
            postgres_session.scalar(select(func.count()).select_from(DemoEditArtifactEvent)),
            postgres_session.scalar(select(func.count()).select_from(DemoImageVersion)),
        )
        published = await commands.read_execution_result(
            demo_actor_id=actor_id,
            job_id=execution.job_id,
        )
        replayed_publication = await commands.read_execution_result(
            demo_actor_id=actor_id,
            job_id=execution.job_id,
        )
        postgres_session.expire_all()
        result_counts_after = (
            postgres_session.scalar(select(func.count()).select_from(Job)),
            postgres_session.scalar(select(func.count()).select_from(DemoEditArtifact)),
            postgres_session.scalar(select(func.count()).select_from(DemoToolRun)),
            postgres_session.scalar(select(func.count()).select_from(DemoVerificationResult)),
            postgres_session.scalar(select(func.count()).select_from(DemoEditArtifactEvent)),
            postgres_session.scalar(select(func.count()).select_from(DemoImageVersion)),
        )
        assert replayed_publication == published
        assert result_counts_after == result_counts_before
        assert published.job_id == execution.job_id
        assert published.session_id == session_id
        assert published.editing_session_id == accepted.target_id
        assert published.edit_plan_id == result_plan.id
        assert published.plan_digest == result_plan.content_digest
        assert published.version_kind == "EDITED"
        assert published.sequence == 1
        assert published.image_version_id == versions[1].id
        assert published.image_version_digest == versions[1].content_digest
        assert published.parent_image_version_id == versions[0].id
        assert published.result_asset_id == versions[1].result_asset_id
        assert published.result_asset_sha256 == versions[1].result_asset_sha256

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

        terminal_execution = await commands.execute_edit_plan(
            ExecuteDemoEditPlan(
                actor_id,
                plan.target_id,
                "DETERMINISTIC_RASTER",
                result_plan.content_digest,
                "d07-terminal-execution-key",
                "d07-terminal-execution-request",
            )
        )
        for terminal_status in ("REJECTED", "FAILED", "CANCELLED"):
            postgres_session.execute(
                update(Job)
                .where(Job.id == terminal_execution.job_id)
                .values(status=terminal_status, finalized_at=utcnow())
            )
            postgres_session.commit()
            with pytest.raises(DemoEditResultTerminal):
                await commands.read_execution_result(
                    demo_actor_id=actor_id,
                    job_id=terminal_execution.job_id,
                )

        postgres_session.execute(
            update(Job).where(Job.id == execution.job_id).values(payload={"invalid": True})
        )
        postgres_session.commit()
        with pytest.raises(DemoEditingCommandAuthorityCorruption):
            await commands.read_execution_result(
                demo_actor_id=actor_id,
                job_id=execution.job_id,
            )

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
