from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException

from mirror_api.auth_dependencies import create_auth_infrastructure
from mirror_api.config import get_settings
from mirror_api.errors import (
    APIError,
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from mirror_api.middleware import RequestIDMiddleware
from mirror_api.routers import auth_router, health_router, stubs_router
from mirror_api.schemas import add_foundation_contract_schemas


def create_app() -> FastAPI:
    settings = get_settings()
    auth_infrastructure = create_auth_infrastructure(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await auth_infrastructure.engine.dispose()
        if auth_infrastructure.redis_client is not None:
            await auth_infrastructure.redis_client.aclose()

    app = FastAPI(
        title="Project Mirror API",
        summary="Privacy-first foundation for a personal aesthetic photo editing agent.",
        version=settings.app_version,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.auth_infrastructure = auth_infrastructure
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "POST", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "Idempotency-Key",
            "X-CSRF-Token",
            "X-Device-ID",
            "X-Request-ID",
        ],
    )
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(APIError, api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(stubs_router)

    def custom_openapi() -> dict[str, object]:
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                summary=app.summary,
                routes=app.routes,
            )
            add_foundation_contract_schemas(schema)
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app


app = create_app()
