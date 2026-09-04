"""Composition-only dependencies for the profile-guided Geometry Demo flow."""

from __future__ import annotations

from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mirror_api.demo_editing_dependencies import get_demo_editing_commands
from mirror_api.demo_image_feedback_service import DemoImageFeedbackService
from mirror_api.demo_job_service import DemoJobService
from mirror_api.demo_profile_geometry_acceptance import DemoProfileGeometryAcceptanceFacade
from mirror_api.demo_reference_profile_dependencies import (
    get_demo_reference_profile_coordinator,
    get_demo_reference_profile_service,
)
from mirror_api.demo_self_transfer_acceptance import (
    DemoSteppedSelfTransferAcceptanceCoordinator,
)
from mirror_api.demo_self_transfer_service import DemoSelfTransferService


def get_demo_profile_geometry_acceptance_facade(
    request: Request,
) -> DemoProfileGeometryAcceptanceFacade:
    infrastructure = request.app.state.auth_infrastructure
    sessions = cast(async_sessionmaker[AsyncSession], infrastructure.sessions)
    transfer = DemoSelfTransferService(session_factory=sessions)
    reference_service = get_demo_reference_profile_service(request)
    reference_coordinator = get_demo_reference_profile_coordinator(request)
    return DemoProfileGeometryAcceptanceFacade(
        session_factory=sessions,
        editing=get_demo_editing_commands(request),
        transfer=transfer,
        acceptance=DemoSteppedSelfTransferAcceptanceCoordinator(
            session_factory=sessions,
            feedback=DemoImageFeedbackService(session_factory=sessions),
            transfer=transfer,
            reference_service=reference_service,
            reference_coordinator=reference_coordinator,
        ),
        jobs=DemoJobService(session_factory=sessions),
    )


__all__ = ["get_demo_profile_geometry_acceptance_facade"]
