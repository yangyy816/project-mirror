from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_questionnaire_service import DemoQuestionnaireService


@dataclass(frozen=True)
class DemoQuestionnaireInfrastructure:
    service: DemoQuestionnaireService


def create_demo_questionnaire_infrastructure(
    *, sessions: async_sessionmaker[AsyncSession]
) -> DemoQuestionnaireInfrastructure:
    return DemoQuestionnaireInfrastructure(
        service=DemoQuestionnaireService(session_factory=sessions)
    )


def get_demo_questionnaire_service(request: Request) -> DemoQuestionnaireService:
    return cast(
        DemoQuestionnaireService,
        request.app.state.demo_questionnaire_infrastructure.service,
    )
