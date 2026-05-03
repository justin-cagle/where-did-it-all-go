"""httpOnly cookie helpers for access and refresh tokens.

Both tokens are stored as httpOnly, Secure, SameSite=Strict cookies.
Never localStorage — see security.md.
"""

from fastapi import Request, Response

_ACCESS_COOKIE = "access_token"
_REFRESH_COOKIE = "refresh_token"
_STEP_UP_COOKIE = "step_up_token"

_ACCESS_TTL = 900  # 15 min
_REFRESH_TTL = 60 * 60 * 24 * 30  # 30 days absolute expiry on the cookie


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    secure: bool = True,
) -> None:
    """Write access and refresh tokens as httpOnly cookies."""
    response.set_cookie(
        _ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=_ACCESS_TTL,
        path="/",
    )
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=_REFRESH_TTL,
        path="/api/v1/auth/refresh",
    )


def set_step_up_cookie(
    response: Response,
    *,
    step_up_token: str,
    secure: bool = True,
) -> None:
    """Write a short-lived step-up access token cookie (5 min)."""
    response.set_cookie(
        _STEP_UP_COOKIE,
        step_up_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=300,
        path="/api/v1",
    )


def clear_auth_cookies(response: Response) -> None:
    """Remove all auth cookies (logout)."""
    response.delete_cookie(_ACCESS_COOKIE, path="/")
    response.delete_cookie(_REFRESH_COOKIE, path="/api/v1/auth/refresh")
    response.delete_cookie(_STEP_UP_COOKIE, path="/api/v1")


def get_access_token(request: Request) -> str | None:
    """Extract the access token from the request cookie."""
    return request.cookies.get(_ACCESS_COOKIE)


def get_refresh_token(request: Request) -> str | None:
    """Extract the refresh token from the request cookie."""
    return request.cookies.get(_REFRESH_COOKIE)


def get_step_up_token(request: Request) -> str | None:
    """Extract the step-up token from the request cookie."""
    return request.cookies.get(_STEP_UP_COOKIE)
