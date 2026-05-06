"""ARQ background jobs for the recurrences module.

recurrence_detection_sweep_job  -> worker-slow (daily sweep per household)
match_transaction_job            -> worker-fast (triggered on transaction ingest)

Both jobs are idempotent:
  - detection sweep skips groups with existing pending/confirmed candidates
  - match_transaction skips transactions that already have a RecurrenceMatch
"""

import uuid
from typing import Any

import structlog

from app.database import get_session_factory

logger = structlog.get_logger(__name__)


async def recurrence_detection_sweep_job(
    ctx: dict[str, Any],
    *,
    household_id: str,
) -> dict[str, Any]:
    """Run detect_recurrences + check_missed for one household.

    Scheduled daily per household by the platform scheduler.
    Idempotent: re-running is safe — duplicate candidates are skipped.
    """
    _ = ctx
    from app.recurrences import service

    hh_id = uuid.UUID(household_id)
    logger.info("recurrence_detection_sweep.start", household_id=household_id)

    factory = get_session_factory()

    async with factory() as session:
        new_candidates = await service.detect_recurrences(session, household_id=hh_id)
        new_misses = await service.check_missed(session, household_id=hh_id)
        await session.commit()

    logger.info(
        "recurrence_detection_sweep.complete",
        household_id=household_id,
        new_candidates=len(new_candidates),
        new_misses=len(new_misses),
    )
    return {
        "household_id": household_id,
        "new_candidates": len(new_candidates),
        "new_misses": len(new_misses),
    }


async def match_transaction_job(
    ctx: dict[str, Any],
    *,
    transaction_id: str,
    household_id: str,
) -> dict[str, Any]:
    """Match a single transaction against active recurrences.

    Triggered on transaction ingest (domain event). Idempotent.
    """
    _ = ctx
    from app.recurrences import service

    tx_id = uuid.UUID(transaction_id)
    hh_id = uuid.UUID(household_id)
    logger.info("match_transaction_job.start", transaction_id=transaction_id)

    factory = get_session_factory()

    async with factory() as session:
        result = await service.match_transaction(session, transaction_id=tx_id, household_id=hh_id)
        await session.commit()

    logger.info(
        "match_transaction_job.complete",
        transaction_id=transaction_id,
        matched=result.matched,
        status=str(result.status) if result.status else None,
    )
    return {
        "transaction_id": transaction_id,
        "matched": result.matched,
        "recurrence_id": str(result.recurrence_id) if result.recurrence_id else None,
        "status": str(result.status) if result.status else None,
    }
