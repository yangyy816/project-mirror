from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
LOCAL_UPLOAD_PATH = re.compile(r"^/_local/private-upload/[^/]+$")
LOCAL_DOWNLOAD_PATH = re.compile(r"^/_local/private-download/[^/]+$")


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
