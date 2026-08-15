from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] | list[Any] | None = None


class APIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    body = ErrorEnvelope(
        code=exc.code,
        message=exc.message,
        request_id=_request_id(request),
        details=exc.details,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    body = ErrorEnvelope(
        code="request_validation_failed",
        message="请求参数不符合接口契约。",
        request_id=_request_id(request),
        details=list(exc.errors()),
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    body = ErrorEnvelope(
        code="http_error",
        message=str(exc.detail),
        request_id=_request_id(request),
        details={"status_code": exc.status_code},
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    del exc
    body = ErrorEnvelope(
        code="internal_error",
        message="服务发生未预期错误。",
        request_id=_request_id(request),
        details=None,
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


class JobAccepted(BaseModel):
    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    status: str = "accepted"
