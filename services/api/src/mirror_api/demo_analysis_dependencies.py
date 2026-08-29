from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings
from mirror_api.demo_analysis_coordinator import DemoAnalysisCoordinator
from mirror_api.demo_analysis_dispatcher import (
    CeleryDemoAnalysisDispatcher,
    RecoverablePendingDemoAnalysisDispatcher,
)
from mirror_api.demo_analysis_service import DemoAnalysisConfiguration, DemoAnalysisService
from mirror_api.demo_analysis_task_contract import DemoAnalysisDispatcher
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_measurement_quality import (
    MEASUREMENT_CONFIG_DIGEST,
    RUNTIME_MANIFEST_DIGEST,
    VISION_MODEL_MANIFEST_DIGEST,
)


@dataclass(frozen=True)
class DemoAnalysisInfrastructure:
    coordinator: DemoAnalysisCoordinator
    jobs: DemoJobService


def accepted_demo_analysis_configuration() -> DemoAnalysisConfiguration:
    """Pin D03 creation to the accepted M3 measurement/runtime authority."""

    return DemoAnalysisConfiguration(
        analyzer_version="demo-face-observation-v1",
        runtime_manifest_digest=RUNTIME_MANIFEST_DIGEST,
        model_manifest_digest=VISION_MODEL_MANIFEST_DIGEST,
        observation_config_digest=MEASUREMENT_CONFIG_DIGEST,
        baseline_aggregation_version="demo-baseline-median-v1",
        measurement_version="demo-face-height-normalized-v1",
        self_state_ontology_version="demo-self-state-ontology-v1",
        self_state_derivation_version="demo-self-state-derivation-v1",
    )


def create_demo_analysis_infrastructure(
    *,
    settings: Settings,
    sessions: async_sessionmaker[AsyncSession],
) -> DemoAnalysisInfrastructure:
    dispatcher: DemoAnalysisDispatcher
    if settings.task_runner == "celery":
        dispatcher = CeleryDemoAnalysisDispatcher(redis_url=settings.redis_url)
    else:
        dispatcher = RecoverablePendingDemoAnalysisDispatcher()
    service = DemoAnalysisService(
        session_factory=sessions,
        configuration=accepted_demo_analysis_configuration(),
    )
    jobs = DemoJobService(session_factory=sessions)
    return DemoAnalysisInfrastructure(
        coordinator=DemoAnalysisCoordinator(
            service=service,
            jobs=jobs,
            dispatcher=dispatcher,
        ),
        jobs=jobs,
    )


def get_demo_analysis_coordinator(request: Request) -> DemoAnalysisCoordinator:
    return cast(
        DemoAnalysisCoordinator,
        request.app.state.demo_analysis_infrastructure.coordinator,
    )


def get_demo_job_service(request: Request) -> DemoJobService:
    return cast(DemoJobService, request.app.state.demo_analysis_infrastructure.jobs)
