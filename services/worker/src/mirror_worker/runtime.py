from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from mirror_api.account_deletion.service import AccountDeletionService
from mirror_api.asset_deletion.service import AssetDeletionService
from mirror_api.asset_deletion.task_contract import AssetDeletionTaskMessage
from mirror_api.config import Settings, get_settings
from mirror_api.data_export.service import DataExportService
from mirror_api.data_rights.coordinator import DataRightsCoordinator
from mirror_api.data_rights.task_contract import (
    AccountDeletionTaskMessage,
    DataExportTaskMessage,
    DataRightsDispatcher,
)
from mirror_api.ingestion.service import IngestionService
from mirror_api.ingestion.task_contract import IngestionDispatcher, IngestionTaskMessage
from mirror_api.providers.base import ImageGenerationProvider, SyntheticObjectStorageProvider
from mirror_api.providers.mock import (
    MockImageGenerationProvider,
    MockSyntheticObjectStorageProvider,
)
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.providers.tencent import (
    TencentImageCandidateProvider,
    TencentSyntheticObjectStorageCandidateProvider,
)
from mirror_api.storage_dependencies import create_object_storage_provider
from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.raw_storage import SyntheticRawStorageService
from mirror_api.synthetic_dataset.task_contract import (
    SyntheticGenerationDispatcher,
    SyntheticGenerationTaskMessage,
)
from mirror_api.upload_control.types import ConsentRequirement
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from mirror_worker.asset_deletion import AssetDeletionTaskExecutor
from mirror_worker.cleanup import SqlAlchemyIngestionCleanup
from mirror_worker.data_rights import AccountDeletionTaskExecutor, DataExportTaskExecutor
from mirror_worker.ingestion import (
    IngestionMaintenance,
    IngestionReconciler,
    IngestionTaskExecutor,
)
from mirror_worker.synthetic_generation import (
    SyntheticGenerationReconciler,
    SyntheticGenerationTaskExecutor,
)


@dataclass(frozen=True)
class IngestionRuntime:
    engine: AsyncEngine
    application: IngestionService
    cleanup: SqlAlchemyIngestionCleanup
    asset_deletion: AssetDeletionService
    data_export: DataExportService
    account_deletion: AccountDeletionService


@dataclass(frozen=True)
class SyntheticGenerationRuntime:
    engine: AsyncEngine
    application: GenerationBatchService
    provider: ImageGenerationProvider
    storage: SyntheticObjectStorageProvider
    raw_storage: SyntheticRawStorageService


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
    data_export = DataExportService(
        session_factory=sessions,
        storage=storage,
        hmac_keyring=dict(settings.auth_hmac_keyring),
        hmac_active_kid=settings.auth_hmac_active_kid,
        retention_seconds=settings.data_export_retention_seconds,
    )
    account_deletion = AccountDeletionService(
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
        data_export=data_export,
        account_deletion=account_deletion,
    )


def create_synthetic_generation_runtime(settings: Settings) -> SyntheticGenerationRuntime:
    provider: ImageGenerationProvider
    if settings.image_generation_provider == "mock":
        provider = MockImageGenerationProvider()
    elif settings.image_generation_provider == "tencent_candidate":
        provider = TencentImageCandidateProvider()
    else:
        raise RuntimeError("synthetic generation provider is not enabled")
    storage: SyntheticObjectStorageProvider
    if settings.synthetic_storage_provider == "mock":
        storage = MockSyntheticObjectStorageProvider()
    elif settings.synthetic_storage_provider == "local":
        storage = LocalSyntheticRawStorageProvider(root=settings.local_storage_root)
    elif settings.synthetic_storage_provider == "tencent_candidate":
        storage = TencentSyntheticObjectStorageCandidateProvider()
    else:
        raise RuntimeError("synthetic raw storage provider is not enabled")
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    application = GenerationBatchService(session_factory=sessions)
    return SyntheticGenerationRuntime(
        engine=engine,
        application=application,
        provider=provider,
        storage=storage,
        raw_storage=SyntheticRawStorageService(session_factory=sessions, storage=storage),
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


async def run_data_export_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str]:
    runtime = create_ingestion_runtime(settings or get_settings())
    try:
        result = await DataExportTaskExecutor(runtime.data_export).execute(
            DataExportTaskMessage.from_message(message)
        )
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_account_deletion_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str]:
    runtime = create_ingestion_runtime(settings or get_settings())
    try:
        result = await AccountDeletionTaskExecutor(runtime.account_deletion).execute(
            AccountDeletionTaskMessage.from_message(message)
        )
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_data_export_cleanup(
    *, limit: int = 100, settings: Settings | None = None
) -> tuple[str, ...]:
    runtime = create_ingestion_runtime(settings or get_settings())
    try:
        return await runtime.data_export.cleanup_expired(limit=limit)
    finally:
        await runtime.engine.dispose()


async def run_data_rights_reconciliation(
    *,
    dispatcher: DataRightsDispatcher,
    request_id: str,
    limit: int = 100,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    runtime = create_ingestion_runtime(settings or get_settings())
    try:
        coordinator = DataRightsCoordinator(
            exports=runtime.data_export,
            account_deletions=runtime.account_deletion,
            dispatcher=dispatcher,
        )
        return await coordinator.reconcile(request_id=request_id, limit=limit)
    finally:
        await runtime.engine.dispose()


async def run_synthetic_generation_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str]:
    runtime = create_synthetic_generation_runtime(settings or get_settings())
    try:
        result = await SyntheticGenerationTaskExecutor(
            application=runtime.application,
            provider=runtime.provider,
            storage=runtime.storage,
            raw_storage=runtime.raw_storage,
        ).execute(SyntheticGenerationTaskMessage.from_message(message))
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_synthetic_generation_reconciliation(
    *,
    dispatcher: SyntheticGenerationDispatcher,
    limit: int = 100,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    runtime = create_synthetic_generation_runtime(settings or get_settings())
    try:
        return await SyntheticGenerationReconciler(
            application=runtime.application,
            dispatcher=dispatcher,
        ).execute(limit=limit)
    finally:
        await runtime.engine.dispose()


async def run_synthetic_raw_cleanup(
    *, limit: int = 100, settings: Settings | None = None
) -> tuple[str, ...]:
    runtime = create_synthetic_generation_runtime(settings or get_settings())
    try:
        results = await runtime.raw_storage.cleanup_expired(limit=limit)
        return tuple(result.source_object_id for result in results)
    finally:
        await runtime.engine.dispose()
