"""FastAPI dependency functions for the admin module."""

from app.households.deps import AppAdmin, CurrentUser, StepUpUser

__all__ = ["AppAdmin", "CurrentUser", "StepUpUser"]

AdminUser = AppAdmin
