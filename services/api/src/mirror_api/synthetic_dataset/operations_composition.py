"""Resource-scoped composition for the internal synthetic-dataset CLI.

This is the only P2-M7 module allowed to construct the SQLAlchemy engine/session boundary.  It
registers already accepted application backends and contains no query, raw SQL, Provider, storage,
task-runner, public API, or production enablement path.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mirror_api.synthetic_dataset.generation_service import GenerationBatchService
from mirror_api.synthetic_dataset.operations import (
    DatasetOperationKind,
    DatasetOperationRejected,
    SyntheticDatasetOperationService,
)
from mirror_api.synthetic_dataset.operations_integration import (
    CostSummaryOperationBackend,
    GenerationBatchOperationBackend,
)
from mirror_api.synthetic_dataset.operations_projection import PostgresCostSummaryReadModel

_MAX_DATABASE_URL_LENGTH = 4096
_DATABASE_URL_PREFIX = "postgresql+psycopg://"


@asynccontextmanager
async def compose_dataset_operation_service(
    database_url: str,
) -> AsyncIterator[SyntheticDatasetOperationService]:
    """Compose accepted backends and always dispose the task-scoped engine."""

    if (
        type(database_url) is not str
        or not database_url.startswith(_DATABASE_URL_PREFIX)
        or len(database_url) > _MAX_DATABASE_URL_LENGTH
    ):
        raise DatasetOperationRejected("operation_backend_unavailable")
    try:
        engine = create_async_engine(database_url, pool_pre_ping=True)
    except Exception:
        raise DatasetOperationRejected("operation_backend_unavailable") from None
    sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    generation_batches = GenerationBatchService(session_factory=sessions)
    batch_backend = GenerationBatchOperationBackend(generation_batches=generation_batches)
    cost_backend = CostSummaryOperationBackend(
        costs=PostgresCostSummaryReadModel(session_factory=sessions),
        logger=logging.getLogger("mirror.synthetic_dataset.cost_summary"),
    )
    service = SyntheticDatasetOperationService(
        backends={
            DatasetOperationKind.BATCH_STATUS: batch_backend,
            DatasetOperationKind.BATCH_CANCEL: batch_backend,
            DatasetOperationKind.COST_SUMMARY: cost_backend,
        }
    )
    try:
        yield service
    finally:
        await engine.dispose()
