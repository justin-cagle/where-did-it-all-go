"""Time abstractions for the data layer.

Two distinct timestamp semantics coexist in this codebase and must NEVER be compared
to each other or stored in the wrong column type (see data-layer.md):

  System-generated timestamps  →  TIMESTAMPTZ (UTC)
    Examples: created_at, updated_at, occurred_at on audit events, import time.
    Always use utcnow() to generate these.

  Bank-reported calendar dates  →  DATE (no timezone)
    Examples: posted_date, pending_date, occurred_at on transactions.
    Stored as the date the bank reported — no UTC conversion applied.
    If a source provides a full datetime with timezone, extract the date component
    in the source's timezone before storing; do NOT UTC-shift it.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current moment as a timezone-aware datetime in UTC.

    Use this for all system-generated timestamps. Never use datetime.utcnow()
    (returns naive datetime) or datetime.now() without a tz argument.
    """
    return datetime.now(tz=UTC)
