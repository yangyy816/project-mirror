from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.config import Settings, get_settings
from mirror_api.demo_editing_asset_loader import LocalDemoAssetByteLoader
from mirror_api.demo_questionnaire_media import DemoQuestionnaireMediaService
from mirror_api.demo_questionnaire_service import DemoQuestionnaireService
from mirror_api.errors import APIError


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


def get_demo_questionnaire_media_service(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> DemoQuestionnaireMediaService:
    if (
        settings.app_env not in {"development", "test", "ci"}
        or settings.synthetic_storage_provider != "local"
    ):
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DEMO_QUESTIONNAIRE_MEDIA_RUNTIME_UNAVAILABLE",
            message="Demo 问卷图片运行环境当前不可用。",
            details={"track": "DEMO_PROTOTYPE"},
        )
    infrastructure = request.app.state.auth_infrastructure
    sessions = cast(async_sessionmaker[AsyncSession], infrastructure.sessions)
    questionnaires = get_demo_questionnaire_service(request)
    return DemoQuestionnaireMediaService(
        session_factory=sessions,
        asset_loader=LocalDemoAssetByteLoader(root=settings.local_storage_root),
        questionnaire_service=questionnaires,
    )
