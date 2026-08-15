from mirror_api.routers.auth import router as auth_router
from mirror_api.routers.health import router as health_router
from mirror_api.routers.ingestion import router as ingestion_router
from mirror_api.routers.local_upload import router as local_upload_router
from mirror_api.routers.stubs import router as stubs_router
from mirror_api.routers.upload_control import router as upload_control_router

__all__ = [
    "auth_router",
    "health_router",
    "ingestion_router",
    "local_upload_router",
    "stubs_router",
    "upload_control_router",
]
