from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from mirror_api.logging import OperationalEvent, emit_operational_event

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
LOCAL_UPLOAD_PATH = re.compile(r"^/_local/private-upload/[^/]+$")
LOCAL_DOWNLOAD_PATH = re.compile(r"^/_local/private-download/[^/]+$")
logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LocalUploadAccessLogRedactionMiddleware(BaseHTTPMiddleware):
    """Remove local upload/download grant handles before access logging."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        path = request.scope["path"]
        if LOCAL_UPLOAD_PATH.fullmatch(path) or LOCAL_DOWNLOAD_PATH.fullmatch(path):
            operation = "private-upload" if "private-upload" in path else "private-download"
            redacted = f"/_local/{operation}/[redacted]"
            request.scope["path"] = redacted
            request.scope["raw_path"] = redacted.encode("ascii")
            request.scope["query_string"] = b""
        return response


class OperationalEventMiddleware(BaseHTTPMiddleware):
    """Emit one payload-free, route-template-based event for every API request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            self._emit(request=request, status_code=500, started=started, outcome="failed")
            raise
        self._emit(
            request=request,
            status_code=response.status_code,
            started=started,
            outcome="succeeded" if response.status_code < 400 else "rejected",
        )
        return response

    @staticmethod
    def _emit(*, request: Request, status_code: int, started: float, outcome: str) -> None:
        route = request.scope.get("route")
        route_template = getattr(route, "path", "/unmatched")
        if not isinstance(route_template, str) or not route_template.startswith("/"):
            route_template = "/unmatched"
        request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
        emit_operational_event(
            logger,
            OperationalEvent(
                event_name="http.request.completed",
                outcome=outcome,
                request_id=str(request_id),
                operation="http_request",
                duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
                status_code=status_code,
                method=request.method,
                route_template=route_template,
            ),
        )
