from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from mirror_api.asset_deletion.service import AssetDeletionService
from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage
from mirror_api.config import Settings, get_settings
from mirror_api.ingestion.service import IngestionService
from mirror_api.ingestion.task_contract import IngestionDispatcher, IngestionTaskMessage
from mirror_api.storage_dependencies import create_object_storage_provider
from mirror_api.upload_control.types import ConsentRequirement
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from mirror_worker.asset_deletion import AssetDeletionTaskExecutor
from mirror_worker.cleanup import SqlAlchemyIngestionCleanup
from mirror_worker.ingestion import (
    IngestionMaintenance,
    IngestionReconciler,
    IngestionTaskExecutor,
)


@dataclass(frozen=True)
class IngestionRuntime:
    engine: AsyncEngine
    application: IngestionService
    cleanup: SqlAlchemyIngestionCleanup
    asset_deletion: AssetDeletionService


def _requirement(settings: Settings) -> ConsentRequirement:
    configured = settings.facial_data_purpose
    return ConsentRequirement(
        consent_type=configured.consent_type,
        purpose_code=configured.purpose_code,
        purpose_version=configured.purpose_version,
        policy_code=configured.policy_code,
        policy_version=configured.policy_version,
        policy_digest=configured.policy_digest,
        operations=configured.operations,
    )


def create_ingestion_runtime(settings: Settings) -> IngestionRuntime:
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    storage = create_object_storage_provider(settings)
    deletion = AssetDeletionService(
        session_factory=sessions,
        storage=storage,
        hmac_keyring=dict(settings.auth_hmac_keyring),
        hmac_active_kid=settings.auth_hmac_active_kid,
    )
    return IngestionRuntime(
        engine=engine,
        application=IngestionService(
            session_factory=sessions,
            storage=storage,
            requirement=_requirement(settings),
            hmac_keyring=settings.auth_hmac_keyring,
            hmac_active_kid=settings.auth_hmac_active_kid,
        ),
        cleanup=SqlAlchemyIngestionCleanup(session_factory=sessions, storage=storage),
        asset_deletion=deletion,
    )


async def run_ingestion_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str]:
    runtime = create_ingestion_runtime(settings or get_settings())
    try:
        result = await IngestionTaskExecutor(runtime.application, runtime.cleanup).execute(
            IngestionTaskMessage.from_message(message)
        )
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_reconciliation(
    *,
    dispatcher: IngestionDispatcher,
    request_id: str,
    limit: int = 100,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    runtime = create_ingestion_runtime(settings or get_settings())
    try:
        return await IngestionReconciler(runtime.application, dispatcher).execute(
            request_id=request_id, limit=limit
        )
    finally:
        await runtime.engine.dispose()


async def run_cleanup_sweep(
    *, limit: int = 100, settings: Settings | None = None
) -> dict[str, int]:
    runtime = create_ingestion_runtime(settings or get_settings())
    try:
        result = await IngestionMaintenance(runtime.cleanup).execute(limit=limit)
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_asset_deletion_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str]:
    runtime = create_ingestion_runtime(settings or get_settings())
    try:
        result = await AssetDeletionTaskExecutor(runtime.asset_deletion).execute(
            AssetDeletionTaskMessage.from_message(message)
        )
        return asdict(result)
    finally:
        await runtime.engine.dispose()
