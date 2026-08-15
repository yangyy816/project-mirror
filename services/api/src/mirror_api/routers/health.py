from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from mirror_api.config import Settings, get_settings
from mirror_api.dependencies import DependencyStatus, probe_dependencies
from mirror_api.schemas import HealthResponse, VersionResponse

router = APIRouter(tags=["system"])


@router.get("/health/live", response_model=HealthResponse)
async def live(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="live",
        version=settings.app_version,
        dependencies={"database": "not_checked", "redis": "not_checked"},
    )


@router.get("/health/ready", response_model=HealthResponse)
async def ready(
    settings: Settings = Depends(get_settings),
    dependency_status: DependencyStatus = Depends(probe_dependencies),
) -> HealthResponse | JSONResponse:
    payload = HealthResponse(
        status="ready" if dependency_status.ready else "limited",
        version=settings.app_version,
        dependencies={
            "database": "available" if dependency_status.database == "available" else "unavailable",
            "redis": "available" if dependency_status.redis == "available" else "unavailable",
        },
    )
    if dependency_status.ready:
        return payload
    return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))


@router.get("/version", response_model=VersionResponse)
async def version(settings: Settings = Depends(get_settings)) -> VersionResponse:
    return VersionResponse(version=settings.app_version)
