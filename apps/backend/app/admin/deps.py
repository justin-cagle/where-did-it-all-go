"""FastAPI dependency functions for the admin module."""

from typing import Annotated

from fastapi import Depends

from app.households.deps import AppAdmin, CurrentUser, StepUpUser
from app.households.models import User

__all__ = ["AppAdmin", "CurrentUser", "StepUpUser"]

AdminUser = Annotated[User, Depends(AppAdmin)]
