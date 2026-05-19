"""FastAPI routes for instance-level settings.

Routes:
  GET /api/v1/settings/instance-info  -- public, no auth required
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["settings"])


class DemoCredentials(BaseModel):
    email: str
    password: str


class InstanceInfoOut(BaseModel):
    aio_mode: bool
    version: str
    demo_credentials: DemoCredentials | None


@router.get("/settings/instance-info", response_model=InstanceInfoOut)
async def get_instance_info() -> InstanceInfoOut:
    """Return instance metadata. No authentication required.

    Used by the login page to detect AIO/demo mode and show credentials.
    """
    settings = get_settings()
    demo: DemoCredentials | None = None
    if settings.aio_mode:
        demo = DemoCredentials(email="admin@wdiag.local", password="admin")  # noqa: S106
    return InstanceInfoOut(
        aio_mode=settings.aio_mode,
        version=settings.app_version,
        demo_credentials=demo,
    )
