"""Optional Bearer token authentication for Kiwi server."""

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


def _load_token() -> Optional[str]:
    token = os.environ.get("KIWI_TOKEN")
    if token:
        return token

    config_path = Path.cwd() / ".kiwi" / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            return config.get("server_token")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _unauthorized(detail: str = "Invalid or missing token") -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": detail})


class TokenAuthMiddleware(BaseHTTPMiddleware):
    OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        token = _load_token()
        if not token:
            return await call_next(request)

        if request.url.path in self.OPEN_PATHS:
            return await call_next(request)

        if request.url.path.startswith("/ws"):
            query_token = request.query_params.get("token")
            if query_token != token:
                return _unauthorized("Invalid token")
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            provided = auth_header[7:]
            if provided == token:
                return await call_next(request)

        return _unauthorized()