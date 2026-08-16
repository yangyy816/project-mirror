from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api.models import (
    GenerationBatch,
    GenerationItem,
    Job,
    JobAttempt,
    ProviderCostEvent,
    SyntheticGenerationEvidence,
    SyntheticPromptTemplate,
    SyntheticSourceObject,
    SyntheticSourceObjectDeletionEvidence,
)
from mirror_api.synthetic_dataset.generation_types import (
    GenerationBatchCreate,
    ProviderCostInput,
)


class GenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert_batch_if_absent(
        self,
        *,
        batch_id: str,
        command: GenerationBatchCreate,
        now: datetime,
    ) -> bool:
        inserted = await self.session.scalar(
            insert(GenerationBatch)
            .values(
                id=batch_id,
                schema_version="mirror.synthetic-dataset/GenerationBatch/v1",
                idempotency_key_hash=command.idempotency_key_hash,
                generation_policy_id=command.generation_policy_id,
                prompt_template_id=command.prompt_template_id,
                provider_reference=command.provider_reference,
                model_reference=command.model_reference,
                model_version_reference=command.model_version_reference,
                pricing_snapshot_reference=command.pricing_snapshot_reference,
                output_media_type=command.output_media_type,
                output_width=command.output_width,
                output_height=command.output_height,
                output_max_bytes=command.output_max_bytes,
                item_count=command.item_count,
                currency=command.currency,
                hard_budget_micros=command.hard_budget_micros,
                per_item_ceiling_micros=command.per_item_ceiling_micros,
                retry_ceiling=command.retry_ceiling,
                concurrency_ceiling=command.concurrency_ceiling,
                status="DRAFT",
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=[GenerationBatch.idempotency_key_hash])
            .returning(GenerationBatch.id)
        )
        return inserted is not None

    async def locked_batch(self, batch_id: str) -> GenerationBatch | None:
        return cast(
            GenerationBatch | None,
            await self.session.scalar(
                select(GenerationBatch).where(GenerationBatch.id == batch_id).with_for_update()
            ),
        )

    async def locked_batch_by_idempotency(self, key_hash: str) -> GenerationBatch | None:
        return cast(
            GenerationBatch | None,
            await self.session.scalar(
                select(GenerationBatch)
                .where(GenerationBatch.idempotency_key_hash == key_hash)
                .with_for_update()
            ),
        )

    async def items(self, batch_id: str, *, lock: bool = False) -> tuple[GenerationItem, ...]:
        statement = (
            select(GenerationItem)
            .where(GenerationItem.batch_id == batch_id)
            .order_by(GenerationItem.ordinal)
        )
        if lock:
            statement = statement.with_for_update()
        return tuple((await self.session.scalars(statement)).all())

    async def locked_item(self, item_id: str) -> GenerationItem | None:
        return cast(
            GenerationItem | None,
            await self.session.scalar(
                select(GenerationItem).where(GenerationItem.id == item_id).with_for_update()
            ),
        )

    async def item(self, item_id: str) -> GenerationItem | None:
        return cast(
            GenerationItem | None,
            await self.session.scalar(select(GenerationItem).where(GenerationItem.id == item_id)),
        )

    async def locked_job(self, job_id: str) -> Job | None:
        return cast(
            Job | None,
            await self.session.scalar(select(Job).where(Job.id == job_id).with_for_update()),
        )

    async def locked_attempt(self, attempt_id: str) -> JobAttempt | None:
        return cast(
            JobAttempt | None,
            await self.session.scalar(
                select(JobAttempt).where(JobAttempt.id == attempt_id).with_for_update()
            ),
        )

    async def locked_attempt_for_lease(self, *, job_id: str, lease_token: str) -> JobAttempt | None:
        return cast(
            JobAttempt | None,
            await self.session.scalar(
                select(JobAttempt)
                .where(JobAttempt.job_id == job_id, JobAttempt.lease_token == lease_token)
                .with_for_update()
            ),
        )

    async def generating_count(self, batch_id: str) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(GenerationItem)
            .where(GenerationItem.batch_id == batch_id, GenerationItem.status == "GENERATING")
        )
        return int(value or 0)

    async def locked_requested_item(self, batch_id: str) -> GenerationItem | None:
        return cast(
            GenerationItem | None,
            await self.session.scalar(
                select(GenerationItem)
                .where(
                    GenerationItem.batch_id == batch_id,
                    GenerationItem.status == "REQUESTED",
                )
                .order_by(GenerationItem.ordinal)
                .limit(1)
                .with_for_update(skip_locked=True)
            ),
        )

    async def locked_retry_item(self, batch_id: str) -> GenerationItem | None:
        return cast(
            GenerationItem | None,
            await self.session.scalar(
                select(GenerationItem)
                .join(Job, Job.id == GenerationItem.job_id)
                .where(
                    GenerationItem.batch_id == batch_id,
                    GenerationItem.status == "GENERATING",
                    Job.status == "pending",
                )
                .order_by(GenerationItem.ordinal)
                .limit(1)
                .with_for_update(of=GenerationItem, skip_locked=True)
            ),
        )

    async def prompt_template(self, prompt_template_id: str) -> SyntheticPromptTemplate | None:
        return cast(
            SyntheticPromptTemplate | None,
            await self.session.scalar(
                select(SyntheticPromptTemplate).where(
                    SyntheticPromptTemplate.id == prompt_template_id,
                    SyntheticPromptTemplate.approval_status == "APPROVED",
                )
            ),
        )

    async def post_cost_if_absent(
        self, *, event_id: str, cost: ProviderCostInput, created_at: datetime
    ) -> bool:
        inserted = await self.session.scalar(
            insert(ProviderCostEvent)
            .values(
                id=event_id,
                schema_version="mirror.synthetic-dataset/ProviderCostEvent/v1",
                generation_item_id=cost.item_id,
                job_attempt_id=cost.job_attempt_id,
                event_kind=cost.event_kind,
                currency=cost.currency,
                amount_micros=cost.amount_micros,
                pricing_snapshot_reference=cost.pricing_snapshot_reference,
                occurred_at=cost.occurred_at,
                created_at=created_at,
            )
            .on_conflict_do_nothing(index_elements=[ProviderCostEvent.job_attempt_id])
            .returning(ProviderCostEvent.id)
        )
        return inserted is not None

    async def cost_for_attempt(self, attempt_id: str) -> ProviderCostEvent | None:
        return cast(
            ProviderCostEvent | None,
            await self.session.scalar(
                select(ProviderCostEvent).where(ProviderCostEvent.job_attempt_id == attempt_id)
            ),
        )

    async def item_spend(self, item_id: str) -> int:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(ProviderCostEvent.amount_micros), 0)).where(
                ProviderCostEvent.generation_item_id == item_id
            )
        )
        return int(value or 0)

    async def raw_chain(
        self, item_id: str
    ) -> tuple[SyntheticSourceObject, SyntheticGenerationEvidence, ProviderCostEvent] | None:
        row = (
            await self.session.execute(
                select(SyntheticSourceObject, SyntheticGenerationEvidence, ProviderCostEvent)
                .join(
                    SyntheticGenerationEvidence,
                    (SyntheticGenerationEvidence.generation_item_id == item_id)
                    & (
                        SyntheticGenerationEvidence.job_attempt_id
                        == SyntheticSourceObject.job_attempt_id
                    ),
                )
                .join(
                    ProviderCostEvent,
                    (ProviderCostEvent.generation_item_id == item_id)
                    & (ProviderCostEvent.job_attempt_id == SyntheticSourceObject.job_attempt_id),
                )
                .where(SyntheticSourceObject.generation_item_id == item_id)
            )
        ).one_or_none()
        if row is None:
            return None
        return row.tuple()

    async def lock_storage_reference(self, storage_reference: str) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:reference, 0))"),
            {"reference": storage_reference},
        )

    async def source_by_storage_reference(
        self, storage_reference: str
    ) -> SyntheticSourceObject | None:
        return cast(
            SyntheticSourceObject | None,
            await self.session.scalar(
                select(SyntheticSourceObject).where(
                    SyntheticSourceObject.storage_reference == storage_reference
                )
            ),
        )

    async def expired_source_ids(self, *, now: datetime, limit: int) -> tuple[str, ...]:
        has_evidence = (
            select(SyntheticSourceObjectDeletionEvidence.id)
            .where(
                SyntheticSourceObjectDeletionEvidence.source_object_id == SyntheticSourceObject.id
            )
            .exists()
        )
        return tuple(
            (
                await self.session.scalars(
                    select(SyntheticSourceObject.id)
                    .where(
                        SyntheticSourceObject.retention_expires_at <= now,
                        ~has_evidence,
                    )
                    .order_by(SyntheticSourceObject.retention_expires_at, SyntheticSourceObject.id)
                    .limit(limit)
                )
            ).all()
        )

    async def locked_source(self, source_id: str) -> SyntheticSourceObject | None:
        return cast(
            SyntheticSourceObject | None,
            await self.session.scalar(
                select(SyntheticSourceObject)
                .where(SyntheticSourceObject.id == source_id)
                .with_for_update()
            ),
        )

    async def source_deletion_evidence(
        self, source_id: str
    ) -> SyntheticSourceObjectDeletionEvidence | None:
        return cast(
            SyntheticSourceObjectDeletionEvidence | None,
            await self.session.scalar(
                select(SyntheticSourceObjectDeletionEvidence).where(
                    SyntheticSourceObjectDeletionEvidence.source_object_id == source_id
                )
            ),
        )

    async def generation_reconciliation_rows(
        self, *, now: datetime, limit: int
    ) -> tuple[tuple[GenerationItem, Job], ...]:
        rows = (
            await self.session.execute(
                select(GenerationItem, Job)
                .join(Job, Job.id == GenerationItem.job_id)
                .join(GenerationBatch, GenerationBatch.id == GenerationItem.batch_id)
                .where(
                    GenerationBatch.status.in_(("QUEUED", "RUNNING")),
                    GenerationItem.status.in_(("REQUESTED", "GENERATING")),
                    (
                        (GenerationBatch.cancel_requested_at.is_(None) & (Job.status == "pending"))
                        | ((Job.status == "leased") & (Job.lease_expires_at <= now))
                    ),
                )
                .order_by(GenerationBatch.created_at, GenerationItem.ordinal)
                .limit(limit)
            )
        ).all()
        return tuple((row[0], row[1]) for row in rows)
