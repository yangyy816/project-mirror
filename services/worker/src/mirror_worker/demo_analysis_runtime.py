"""Fail-closed D03 runtime boundary used until a task-scoped M3 handle exists."""

from __future__ import annotations

from mirror_api.demo_analysis_service import (
    DemoAnalysisReservation,
    DemoAnalysisRuntimeEvidence,
)

from mirror_worker.demo_analysis import DemoAnalysisRuntimeFailed


class DeferredDemoAnalysisRuntime:
    """Expose no fake observations while runtime replay is intentionally deferred."""

    async def observe(self, reservation: DemoAnalysisReservation) -> DemoAnalysisRuntimeEvidence:
        del reservation
        raise DemoAnalysisRuntimeFailed("M3_RUNTIME_REPLAY_NOT_CURRENTLY_MATERIALIZED")
