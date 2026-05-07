"""ARQ background job for the recommendations module.

expire_stale_recommendations_job  -> worker-slow (daily sweep)

Idempotent: re-running is safe — already-expired rows are skipped.
"""

from typing import Any

import structlog

from app.database import get_session_factory

logger = structlog.get_logger(__name__)


async def expire_stale_recommendations_job(ctx: dict[str, Any]) -> dict[str, Any]:
    """Set status=expired for all pending recommendations past their expires_at.

    Runs daily via worker-slow scheduler. Idempotent.
    """
    _ = ctx
    from app.recommendations import service

    factory = get_session_factory()
    async with factory() as session:
        expired = await service.expire_stale(session)
        await session.commit()

    logger.info("expire_stale_recommendations_job.complete", expired=len(expired))
    return {"expired": len(expired)}
