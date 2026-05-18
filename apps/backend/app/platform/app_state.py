"""Application-level state shared across modules without circular imports."""

from __future__ import annotations

from datetime import UTC, datetime

_started_at: datetime | None = None


def set_started_at(dt: datetime) -> None:
    global _started_at
    _started_at = dt


def get_started_at() -> datetime:
    return _started_at if _started_at is not None else datetime.now(tz=UTC)
