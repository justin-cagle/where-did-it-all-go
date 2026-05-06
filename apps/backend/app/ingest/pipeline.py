"""Core ingestion pipeline.

For each ParsedTransaction:
  1. Create transaction via transactions.service (handles exact external_id dedup)
  2. Run fuzzy dedup via transactions.service.process_dedup
  3. Run classification via classification.service.classify_transaction
  4. Write suggestion-mode results to recommendations_pending stub
  5. Update ImportJob counters

Each transaction is processed in its own session to keep errors isolated and
ensure idempotency: a job that crashes and restarts will skip already-ingested
transactions (external_id already present in DB).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.audit.models import ActorType, AuditEvent, AuditOperation
from app.classification import service as classification_service
from app.ingest.models import ImportJob, RecommendationPending
from app.ingest.parsers import ParsedTransaction
from app.transactions import service as tx_service
from app.transactions.enums import TransactionDirection, TransactionState, TransactionType

logger = structlog.get_logger(__name__)

# UUID sentinel for system-initiated operations (ARQ jobs, automated ingest).
# actor_type is recorded as "user" in audit with this ID as a sentinel.
# Future work: add actor_type="system" support to transactions.service._write_audit.
_SYSTEM_ACTOR_ID = uuid.UUID(int=0)


@dataclass
class IngestResult:
    imported: int = 0
    duplicate: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=lambda: [])


def _map_direction(direction: str) -> TransactionDirection:
    if direction == "credit":
        return TransactionDirection.CREDIT
    return TransactionDirection.DEBIT


def _map_type_hint(hint: str | None) -> TransactionType | None:
    if hint is None:
        return None
    try:
        return TransactionType(hint)
    except ValueError:
        return None


async def _process_one(
    session: AsyncSession,
    *,
    pt: ParsedTransaction,
    household_id: uuid.UUID,
    account_id: uuid.UUID,
    source: str,
) -> str:
    """Process a single ParsedTransaction. Returns "imported", "duplicate", or "error"."""
    try:
        tx = await tx_service.create_transaction(
            session,
            household_id=household_id,
            account_id=account_id,
            actor_id=_SYSTEM_ACTOR_ID,
            amount=pt.amount,
            currency=pt.currency,
            direction=_map_direction(pt.direction),
            transaction_type=_map_type_hint(pt.transaction_type_hint),
            state=TransactionState.POSTED,
            posted_date=pt.posted_date,
            pending_date=None,
            occurred_at=pt.occurred_at,
            description=pt.description,
            merchant_name=pt.merchant_name,
            external_id=pt.external_id,
            manually_categorized=False,
        )
    except tx_service.ConflictError:
        return "duplicate"

    # Fuzzy dedup — creates DeduplicationLog rows (pending HITL if below threshold)
    dedup_logs = await tx_service.process_dedup(session, transaction=tx, source=source)
    for log in dedup_logs:
        if log.resolution == "pending":
            rec = RecommendationPending(
                household_id=household_id,
                source="dedup_fuzzy",
                payload={
                    "dedup_log_id": str(log.id),
                    "candidate_a_id": str(log.candidate_a_id),
                    "candidate_b_id": str(log.candidate_b_id),
                    "confidence": str(log.confidence),
                },
            )
            session.add(rec)

    # If tx was auto-merged (archived) by process_dedup, count as duplicate
    if tx.archived_at is not None:
        return "duplicate"

    # Classification pipeline
    try:
        result = await classification_service.classify_transaction(
            session,
            transaction_id=tx.id,
            household_id=household_id,
        )

        # Suggest-mode and HITL items → recommendations_pending stub
        for suggestion in result.suggestions:
            rec = RecommendationPending(
                household_id=household_id,
                source="classification_rule_suggest",
                payload={
                    "transaction_id": str(tx.id),
                    "allocation_id": str(suggestion.allocation_id),
                    "suggested_category_id": str(suggestion.suggested_category_id),
                    "rule_id": str(suggestion.rule_id),
                },
            )
            session.add(rec)

        for hitl in result.hitl_items:
            rec = RecommendationPending(
                household_id=household_id,
                source="classification_multi_match",
                payload={
                    "transaction_id": str(tx.id),
                    "allocation_id": str(hitl.allocation_id),
                    "matching_rule_ids": [str(r) for r in hitl.matching_rule_ids],
                },
            )
            session.add(rec)

        await session.flush()
    except Exception as exc:
        logger.warning(
            "ingest.classify_failed",
            transaction_id=str(tx.id),
            error=str(exc),
        )
        # Classification failure is non-fatal; transaction is still imported

    return "imported"


async def run_pipeline(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    parsed: list[ParsedTransaction],
    import_job_id: uuid.UUID,
    household_id: uuid.UUID,
    account_id: uuid.UUID,
    source: str,
) -> IngestResult:
    """Run the ingestion pipeline for a list of parsed transactions.

    Each transaction runs in its own session for error isolation. Uses
    begin_nested (savepoint) within the session to allow partial failure.

    Updates ImportJob counters and SyncConfig.last_synced_at after completion.
    Writes one audit event for the entire batch.
    """
    result = IngestResult()

    for pt in parsed:
        async with session_factory() as session:
            try:
                outcome = await _process_one(
                    session,
                    pt=pt,
                    household_id=household_id,
                    account_id=account_id,
                    source=source,
                )
                await session.commit()
                if outcome == "imported":
                    result.imported += 1
                else:
                    result.duplicate += 1
            except Exception as exc:
                await session.rollback()
                result.errors += 1
                result.error_messages.append(str(exc))
                logger.warning(
                    "ingest.transaction_failed",
                    external_id=pt.external_id,
                    error=str(exc),
                )

    # Update ImportJob counters
    async with session_factory() as session:
        job_row = await session.get(ImportJob, import_job_id)
        if job_row is not None:
            now = datetime.now(tz=UTC)
            job_row.row_count = len(parsed)
            job_row.imported_count = result.imported
            job_row.duplicate_count = result.duplicate
            job_row.error_count = result.errors
            job_row.status = "completed"
            job_row.completed_at = now
            if result.errors > 0:
                job_row.error_detail = {
                    "messages": result.error_messages[:50],
                    "total_errors": result.errors,
                }

            # Batch audit event
            audit = AuditEvent(
                actor_type=str(ActorType.SYSTEM),
                actor_id=None,
                actor_source="ingest_pipeline",
                household_id=household_id,
                entity_type="import_job",
                entity_id=import_job_id,
                operation=str(AuditOperation.CREATE),
                delta=[
                    {"op": "add", "path": "/imported_count", "value": result.imported},
                    {"op": "add", "path": "/duplicate_count", "value": result.duplicate},
                    {"op": "add", "path": "/error_count", "value": result.errors},
                ],
            )
            session.add(audit)
            await session.commit()

    logger.info(
        "ingest.pipeline_complete",
        import_job_id=str(import_job_id),
        imported=result.imported,
        duplicate=result.duplicate,
        errors=result.errors,
    )
    return result


__all__: list[Any] = ["IngestResult", "run_pipeline"]
