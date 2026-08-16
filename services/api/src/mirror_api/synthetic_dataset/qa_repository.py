"""Persistence helpers for existing M3 append-only QA authority."""

from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mirror_api.models import (
    SyntheticQAMeasurement,
    SyntheticQAPolicy,
    SyntheticQAReviewDecision,
    SyntheticQARun,
)


class SyntheticQARepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def locked_run(self, run_id: str) -> SyntheticQARun | None:
        return cast(
            SyntheticQARun | None,
            await self._session.scalar(
                select(SyntheticQARun)
                .where(SyntheticQARun.id == run_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ),
        )

    async def evidence(
        self, run_id: str
    ) -> tuple[list[SyntheticQAMeasurement], list[SyntheticQAReviewDecision]]:
        measurements = list(
            (
                await self._session.scalars(
                    select(SyntheticQAMeasurement).where(SyntheticQAMeasurement.qa_run_id == run_id)
                )
            ).all()
        )
        reviews = list(
            (
                await self._session.scalars(
                    select(SyntheticQAReviewDecision).where(
                        SyntheticQAReviewDecision.qa_run_id == run_id
                    )
                )
            ).all()
        )
        return measurements, reviews

    async def policy_for_run(self, run: SyntheticQARun) -> SyntheticQAPolicy | None:
        return cast(
            SyntheticQAPolicy | None,
            await self._session.scalar(
                select(SyntheticQAPolicy)
                .where(SyntheticQAPolicy.id == run.qa_policy_id)
                .execution_options(populate_existing=True)
            ),
        )

    def add(self, value: object) -> None:
        self._session.add(value)

    async def flush(self) -> None:
        await self._session.flush()

    @staticmethod
    def is_terminal(run: SyntheticQARun) -> bool:
        return run.status in {"PASSED", "REJECTED", "FAILED"}
