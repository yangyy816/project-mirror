from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, cast

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
from mirror_api.demo_analysis_dependencies import accepted_demo_analysis_configuration
from mirror_api.demo_analysis_service import DemoAnalysisService
from mirror_api.demo_analysis_task_contract import (
    DemoAnalysisDispatcher,
    DemoAnalysisTaskMessage,
)
from mirror_api.demo_editing_asset_loader import LocalDemoAssetByteLoader
from mirror_api.demo_editing_commands import DemoEditingCommandService
from mirror_api.demo_editing_runtime import DemoEditingRuntime as DemoEditingApplication
from mirror_api.demo_editing_storage import DemoLocalPrivateObjectStorage
from mirror_api.demo_editing_task_contract import (
    DemoEditingDispatcher,
    DemoEditingOperation,
    DemoEditingTaskMessage,
)
from mirror_api.demo_editing_verifier_adapter import DemoDeterministicEditVerifier
from mirror_api.demo_profile_commands import DemoProfileCommandService
from mirror_api.demo_profile_service import DemoProfileCompilationService
from mirror_api.demo_profile_task_contract import (
    DemoProfileDispatcher,
    DemoProfileTaskMessage,
)
from mirror_api.geometry_dependencies import create_geometry_transform_provider
from mirror_api.ingestion.service import IngestionService
from mirror_api.ingestion.task_contract import IngestionDispatcher, IngestionTaskMessage
from mirror_api.providers.base import (
    ImageGenerationProvider,
    SyntheticObjectStorageProvider,
)
from mirror_api.providers.mock import (
    MockImageGenerationProvider,
    MockSyntheticObjectStorageProvider,
)
from mirror_api.providers.synthetic_local import LocalSyntheticRawStorageProvider
from mirror_api.providers.synthetic_normalized_local import LocalSyntheticNormalizedStorageProvider
from mirror_api.providers.synthetic_variant_local import LocalSyntheticVariantStorageProvider
from mirror_api.providers.tencent import (
    TencentImageCandidateProvider,
    TencentSyntheticObjectStorageCandidateProvider,
)
from mirror_api.storage_dependencies import create_object_storage_provider
from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.m4_orchestration_service import SyntheticM4OrchestrationService
from mirror_api.synthetic_dataset.normalization_service import SyntheticNormalizationService
from mirror_api.synthetic_dataset.orchestration_service import SyntheticM3OrchestrationService
from mirror_api.synthetic_dataset.raw_storage import SyntheticRawStorageService
from mirror_api.synthetic_dataset.task_contract import (
    SyntheticGenerationDispatcher,
    SyntheticGenerationTaskMessage,
    SyntheticM3Dispatcher,
    SyntheticM4Dispatcher,
    SyntheticNormalizationTaskMessage,
    SyntheticQATaskMessage,
    SyntheticTransformTaskMessage,
)
from mirror_api.synthetic_dataset.transform_service import SyntheticTransformService
from mirror_api.upload_control.types import ConsentRequirement
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from mirror_worker.asset_deletion import AssetDeletionTaskExecutor
from mirror_worker.cleanup import SqlAlchemyIngestionCleanup
from mirror_worker.data_rights import AccountDeletionTaskExecutor, DataExportTaskExecutor
from mirror_worker.demo_analysis import DemoAnalysisTaskExecutor
from mirror_worker.demo_analysis_runtime import DeferredDemoAnalysisRuntime
from mirror_worker.demo_profile import DemoProfileTaskExecutor
from mirror_worker.ingestion import (
    IngestionMaintenance,
    IngestionReconciler,
    IngestionTaskExecutor,
)
from mirror_worker.synthetic_generation import (
    SyntheticGenerationReconciler,
    SyntheticGenerationTaskExecutor,
)
from mirror_worker.synthetic_m3 import SyntheticM3Reconciler, SyntheticM3TaskExecutor
from mirror_worker.synthetic_m4 import SyntheticM4Reconciler, SyntheticM4TaskExecutor


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


@dataclass(frozen=True)
class SyntheticM3Runtime:
    engine: AsyncEngine
    application: SyntheticM3OrchestrationService


@dataclass(frozen=True)
class SyntheticM4Runtime:
    engine: AsyncEngine
    application: SyntheticM4OrchestrationService


@dataclass(frozen=True)
class DemoAnalysisRuntime:
    engine: AsyncEngine
    application: DemoAnalysisService
    runtime: DeferredDemoAnalysisRuntime


@dataclass(frozen=True)
class DemoProfileRuntime:
    engine: AsyncEngine
    application: DemoProfileCompilationService
    commands: DemoProfileCommandService


@dataclass(frozen=True)
class DemoEditingRuntime:
    engine: AsyncEngine
    application: DemoEditingApplication
    commands: DemoEditingCommandService


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


def create_synthetic_m3_runtime(settings: Settings) -> SyntheticM3Runtime:
    """Only deterministic local synthetic namespaces are available to the M3 worker."""
    if settings.synthetic_storage_provider != "local":
        raise RuntimeError("M3 normalization requires local synthetic storage in this environment")
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    normalizer = SyntheticNormalizationService(
        session_factory=sessions,
        raw_storage=LocalSyntheticRawStorageProvider(root=settings.local_storage_root),
        normalized_storage=LocalSyntheticNormalizedStorageProvider(
            root=settings.local_storage_root
        ),
    )
    return SyntheticM3Runtime(
        engine=engine,
        application=SyntheticM3OrchestrationService(
            session_factory=sessions,
            normalizer=normalizer,
        ),
    )


def create_synthetic_m4_runtime(settings: Settings) -> SyntheticM4Runtime:
    """Compose only the accepted private synthetic transform and local namespaces."""
    if settings.synthetic_storage_provider != "local":
        raise RuntimeError("M4 transform requires local synthetic storage in this environment")
    transform = create_geometry_transform_provider(settings)
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = SyntheticTransformService(
        session_factory=sessions,
        transform=transform,
        normalized_storage=LocalSyntheticNormalizedStorageProvider(
            root=settings.local_storage_root
        ),
        variant_storage=LocalSyntheticVariantStorageProvider(root=settings.local_storage_root),
    )
    return SyntheticM4Runtime(
        engine=engine,
        application=SyntheticM4OrchestrationService(
            session_factory=sessions,
            transforms=service,
        ),
    )


def create_demo_analysis_runtime(settings: Settings) -> DemoAnalysisRuntime:
    """Compose D03 authority while keeping the ephemeral M3 handle fail-closed."""

    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return DemoAnalysisRuntime(
        engine=engine,
        application=DemoAnalysisService(
            session_factory=sessions,
            configuration=accepted_demo_analysis_configuration(),
        ),
        runtime=DeferredDemoAnalysisRuntime(),
    )


def create_demo_profile_runtime(settings: Settings) -> DemoProfileRuntime:
    """Compose the deterministic P5 compiler with PostgreSQL authority only."""

    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return DemoProfileRuntime(
        engine=engine,
        application=DemoProfileCompilationService(session_factory=sessions),
        commands=DemoProfileCommandService(session_factory=sessions),
    )


def create_demo_editing_runtime(settings: Settings) -> DemoEditingRuntime:
    """Compose the local synthetic D07 runtime without a Provider or public network."""

    if settings.storage_provider != "local" or settings.app_env not in {
        "development",
        "test",
        "ci",
    }:
        raise RuntimeError("Demo editing requires the local private Demo storage boundary")
    engine = create_async_engine(settings.database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    loader = LocalDemoAssetByteLoader(root=settings.local_storage_root)
    storage = DemoLocalPrivateObjectStorage(root=settings.local_storage_root)
    verifier = DemoDeterministicEditVerifier(
        session_factory=sessions,
        asset_loader=loader,
    )
    return DemoEditingRuntime(
        engine=engine,
        application=DemoEditingApplication(
            session_factory=sessions,
            asset_loader=loader,
            storage=storage,
            verifier=verifier,
            geometry_dispatcher=None,
        ),
        commands=DemoEditingCommandService(session_factory=sessions),
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


async def run_demo_analysis_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str | None]:
    runtime = create_demo_analysis_runtime(settings or get_settings())
    try:
        result = await DemoAnalysisTaskExecutor(
            application=runtime.application,
            runtime=runtime.runtime,
        ).execute(DemoAnalysisTaskMessage.from_message(message))
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_demo_analysis_reconciliation(
    *,
    dispatcher: DemoAnalysisDispatcher,
    limit: int = 100,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    runtime = create_demo_analysis_runtime(settings or get_settings())
    try:
        dispatched: list[str] = []
        for candidate in await runtime.application.reconciliation_candidates(limit=limit):
            message = DemoAnalysisTaskMessage(
                analysis_run_id=candidate.analysis_run_id,
                job_id=candidate.job_id,
                request_id=candidate.request_id,
            )
            dispatcher.dispatch_demo_analysis(message)
            dispatched.append(candidate.job_id)
        return tuple(dispatched)
    finally:
        await runtime.engine.dispose()


async def run_demo_profile_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str | None]:
    runtime = create_demo_profile_runtime(settings or get_settings())
    try:
        result = await DemoProfileTaskExecutor(application=runtime.application).execute(
            DemoProfileTaskMessage.from_message(message)
        )
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_demo_profile_reconciliation(
    *,
    dispatcher: DemoProfileDispatcher,
    limit: int = 100,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    runtime = create_demo_profile_runtime(settings or get_settings())
    try:
        dispatched: list[str] = []
        for candidate in await runtime.commands.reconciliation_candidates(limit=limit):
            message = DemoProfileTaskMessage(
                demo_actor_id=candidate.demo_actor_id,
                job_id=candidate.job_id,
                request_id=candidate.request_id,
            )
            dispatcher.dispatch_demo_profile(message)
            dispatched.append(candidate.job_id)
        return tuple(dispatched)
    finally:
        await runtime.engine.dispose()


async def run_demo_editing_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str | bool | None]:
    runtime = create_demo_editing_runtime(settings or get_settings())
    try:
        result = await runtime.application.run(DemoEditingTaskMessage.from_message(message))
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_demo_editing_reconciliation(
    *,
    dispatcher: DemoEditingDispatcher,
    limit: int = 100,
    settings: Settings | None = None,
) -> tuple[str, ...]:
    runtime = create_demo_editing_runtime(settings or get_settings())
    try:
        dispatched: list[str] = []
        for candidate in await runtime.commands.reconciliation_candidates(limit=limit):
            message = DemoEditingTaskMessage(
                demo_actor_id=candidate.demo_actor_id,
                job_id=candidate.job_id,
                operation=cast(DemoEditingOperation, candidate.endpoint_operation),
                request_id=candidate.request_id,
            )
            dispatcher.dispatch_demo_editing(message)
            dispatched.append(candidate.job_id)
        return tuple(dispatched)
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


async def run_synthetic_normalization_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str | None]:
    runtime = create_synthetic_m3_runtime(settings or get_settings())
    try:
        result = await SyntheticM3TaskExecutor(runtime.application).execute_normalization(
            SyntheticNormalizationTaskMessage.from_message(message)
        )
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_synthetic_qa_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str | None]:
    runtime = create_synthetic_m3_runtime(settings or get_settings())
    try:
        result = await SyntheticM3TaskExecutor(runtime.application).execute_qa(
            SyntheticQATaskMessage.from_message(message)
        )
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_synthetic_m3_reconciliation(
    *, dispatcher: SyntheticM3Dispatcher, limit: int = 100, settings: Settings | None = None
) -> tuple[str, ...]:
    runtime = create_synthetic_m3_runtime(settings or get_settings())
    try:
        return await SyntheticM3Reconciler(runtime.application, dispatcher).execute(limit=limit)
    finally:
        await runtime.engine.dispose()


async def run_synthetic_transform_message(
    message: dict[str, Any], *, settings: Settings | None = None
) -> dict[str, str | None]:
    runtime = create_synthetic_m4_runtime(settings or get_settings())
    try:
        result = await SyntheticM4TaskExecutor(runtime.application).execute(
            SyntheticTransformTaskMessage.from_message(message)
        )
        return asdict(result)
    finally:
        await runtime.engine.dispose()


async def run_synthetic_m4_reconciliation(
    *, dispatcher: SyntheticM4Dispatcher, limit: int = 100, settings: Settings | None = None
) -> tuple[str, ...]:
    runtime = create_synthetic_m4_runtime(settings or get_settings())
    try:
        return await SyntheticM4Reconciler(runtime.application, dispatcher).execute(limit=limit)
    finally:
        await runtime.engine.dispose()
