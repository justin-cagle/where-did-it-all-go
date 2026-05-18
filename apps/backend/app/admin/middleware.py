"""Read-only mode enforcement middleware.

Intercepts all mutating requests (POST/PATCH/PUT/DELETE) when read-only mode
is enabled. Exempt paths: /api/v1/admin/ (admin can disable) and /api/v1/auth/
(login/logout must work).

Redis is checked first (fast path). Falls back to DB if Redis unavailable.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

_MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})
_EXEMPT_PREFIXES = ("/api/v1/admin/", "/api/v1/auth/")
_READ_ONLY_KEY = "system:read_only_state"


class ReadOnlyMiddleware(BaseHTTPMiddleware):
    """Block mutating requests when system read-only mode is active."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in _MUTATING_METHODS:
            return await call_next(request)

        path = request.url.path
        for prefix in _EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        enabled, reason = await self._check_read_only(request)
        if enabled:
            return JSONResponse(
                status_code=503,
                content={
                    "type": "read_only_mode",
                    "title": "System is in read-only mode",
                    "detail": reason or "System is currently in read-only mode",
                    "status": 503,
                },
            )

        return await call_next(request)

    async def _check_read_only(self, _request: Request) -> tuple[bool, str | None]:
        from app.config import get_settings

        settings = get_settings()
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(str(settings.redis_url), decode_responses=True)  # type: ignore[misc]
            raw = await r.get(_READ_ONLY_KEY)
            await r.aclose()
            if raw is not None:
                data: dict[str, Any] = json.loads(raw)
                return bool(data.get("enabled", False)), data.get("reason")
            return False, None
        except Exception as exc:
            logger.debug("read_only_middleware.redis_unavailable", error=str(exc))

        try:
            from app.database import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                from app.admin.service import get_read_only_state

                row = await get_read_only_state(session)
                return row.enabled, row.reason
        except Exception:
            return False, None
