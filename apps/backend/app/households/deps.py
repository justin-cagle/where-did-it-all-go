"""FastAPI dependency functions for the households module.

These dependencies are injected into route handlers via FastAPI's
dependency injection system. They validate JWT tokens, load the
current user, and enforce role/step-up requirements.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.households import service
from app.households.models import User
from app.security import cookies as cookie_service
from app.security import jwt as jwt_service
from app.security.jwt import InvalidTokenError


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate the JWT from the access-token cookie.

    Raises HTTP 401 if the token is missing or invalid.
    """
    raw_token = cookie_service.get_access_token(request)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )

    settings = get_settings()
    try:
        claims = jwt_service.validate_access_token(raw_token, settings.jwt_secret)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token invalid or expired",
        ) from None

    import uuid

    user_id = uuid.UUID(str(claims["sub"]))
    user = await service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not found",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_app_admin(current_user: CurrentUser) -> User:
    """Dependency: actor must have the App Admin role."""
    if not current_user.is_app_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="App Admin role required",
        )
    return current_user


async def require_step_up(request: Request, current_user: CurrentUser) -> User:
    """Dependency: actor must have a valid step-up token in their access cookie.

    Step-up is granted by POST /api/v1/auth/step-up and encodes a
    step_up_until timestamp in the JWT claims.
    """
    raw_token = cookie_service.get_step_up_token(request)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="step-up authentication required",
            headers={"X-Step-Up-Required": "true"},
        )

    settings = get_settings()
    try:
        claims = jwt_service.validate_access_token(raw_token, settings.jwt_secret)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="step-up token invalid or expired",
            headers={"X-Step-Up-Required": "true"},
        ) from None

    if not jwt_service.has_step_up(claims):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="step-up token expired",
            headers={"X-Step-Up-Required": "true"},
        )
    return current_user


AppAdmin = Annotated[User, Depends(require_app_admin)]
StepUpUser = Annotated[User, Depends(require_step_up)]
