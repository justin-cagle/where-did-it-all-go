"""slowapi rate limiter singleton.

Import this module and call get_limiter() to access the shared Limiter
instance. Mount it on the FastAPI app in main.py:

    from app.security.ratelimit import get_limiter, rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    app.state.limiter = get_limiter()
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

Then decorate auth endpoints:
    @limiter.limit("10/minute")
    async def login(request: Request, ...): ...
"""

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler  # type: ignore[import-untyped]
from slowapi.util import get_remote_address  # type: ignore[import-untyped]

_limiter: Limiter | None = None


def get_limiter() -> Limiter:
    """Return the singleton rate limiter."""
    global _limiter
    if _limiter is None:
        _limiter = Limiter(key_func=get_remote_address)
    return _limiter


def get_household_id(request: Request) -> str:
    """Rate limit key: household_id from path params, fallback to IP."""
    hid = request.path_params.get("household_id")
    if hid:
        return str(hid)
    return get_remote_address(request)


rate_limit_exceeded_handler = _rate_limit_exceeded_handler
