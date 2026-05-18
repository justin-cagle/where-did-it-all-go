"""Bootstrap service — initial admin user creation on first startup.

Called from main.py lifespan before the app starts accepting requests.
Env vars are read once, used to create the user, then discarded. They
are never stored in the database and never appear in structured logs.
"""

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.households.models import User

logger = structlog.get_logger(__name__)


async def run_bootstrap(session: AsyncSession) -> None:
    """Ensure at least one admin user exists; refuse to start otherwise.

    - users > 0: bootstrap vars ignored, returns immediately.
    - users == 0 and vars set: creates admin, commits.
    - users == 0 and vars not set: logs CRITICAL, raises SystemExit(1).
    """
    from app.config import get_settings
    from app.households import service

    count_result = await session.execute(sa.select(sa.func.count()).select_from(User))
    count: int = count_result.scalar_one()

    if count > 0:
        logger.debug("bootstrap.skipped", reason="users_exist")
        return

    settings = get_settings()
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password

    if not email or not password:
        logger.critical(
            "bootstrap.refused",
            message=(
                "No users exist. Set BOOTSTRAP_ADMIN_EMAIL and "
                "BOOTSTRAP_ADMIN_PASSWORD to create the initial admin, "
                "then restart."
            ),
        )
        raise SystemExit(1)

    user = await service.create_user(
        session,
        email=email,
        display_name="Admin",
        password=password,
        is_app_admin=True,
    )
    await session.commit()
    logger.info("bootstrap.admin_created", email=user.email)
