"""FastAPI dependency composition for D09 image feedback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_image_feedback_service import DemoImageFeedbackService


@dataclass(frozen=True)
class DemoImageFeedbackInfrastructure:
    service: DemoImageFeedbackService


def create_demo_image_feedback_infrastructure(
    *, sessions: async_sessionmaker[AsyncSession]
) -> DemoImageFeedbackInfrastructure:
    return DemoImageFeedbackInfrastructure(
        service=DemoImageFeedbackService(session_factory=sessions)
    )


def get_demo_image_feedback_service(request: Request) -> DemoImageFeedbackService:
    return cast(
        DemoImageFeedbackService,
        request.app.state.demo_image_feedback_infrastructure.service,
    )


__all__ = [
    "DemoImageFeedbackInfrastructure",
    "create_demo_image_feedback_infrastructure",
    "get_demo_image_feedback_service",
]
