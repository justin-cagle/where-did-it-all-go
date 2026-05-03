"""SQLAlchemy base mixins shared by all domain models.

Every user-facing model composes these mixins as needed:

    class Account(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
        __tablename__ = "accounts_account"
        ...

Mixin summary:
    UUIDPrimaryKeyMixin  — app-side UUIDv7 primary key
    TimestampMixin       — created_at / updated_at (TIMESTAMPTZ UTC)
    SoftDeleteMixin      — archived_at / archived_by + automatic query filter
    EffectiveDatedMixin  — effective_from / effective_to for versioned entities

Soft-delete filter:
    Registered once at module import time on the SQLAlchemy Session class.
    All ORM SELECT statements automatically exclude archived rows unless the
    query passes execution_options(include_archived=True).
"""

import uuid
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Mapped, ORMExecuteState, Session, mapped_column, with_loader_criteria

from app.platform.ids import new_uuid
from app.platform.time import utcnow

# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class UUIDPrimaryKeyMixin:
    """App-side generated UUIDv7 primary key.

    Time-ordered for B-tree index locality. Not enumerable.
    Generated in Python (not via a DB default) so the ID is available
    immediately after object construction, before the INSERT is issued.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )


class TimestampMixin:
    """Immutable created_at and auto-bumping updated_at.

    Both columns are TIMESTAMPTZ stored as UTC. Never use TIMESTAMP WITHOUT
    TIME ZONE — see data-layer.md for the full rationale.

    updated_at is set by SQLAlchemy's onupdate hook. For belt-and-suspenders
    enforcement (raw SQL, alembic data migrations), domain table migrations
    may also attach the shared update_updated_at_column() DB trigger.
    """

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.text("NOW()"),
    )


class SoftDeleteMixin:
    """Soft delete: archived_at + archived_by.

    Default ORM queries exclude archived rows automatically (see filter below).
    To query including archived rows:
        session.execute(select(MyModel), execution_options={"include_archived": True})

    Hard delete is admin-tool-only and rare (e.g., GDPR erasure).
    """

    archived_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    archived_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
    )


class EffectiveDatedMixin:
    """Versioning via effective-dated rows (budgets, debt plans, APR history).

    Current version: WHERE effective_to IS NULL.

    Creating a new version:
        1. Set effective_to on the current row (= new version's effective_from - 1 day).
        2. Insert a new row with effective_from = today, effective_to = NULL.

    History is append-only — existing rows are never rewritten, only closed.
    """

    effective_from: Mapped[date] = mapped_column(sa.Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(sa.Date, nullable=True)


# ---------------------------------------------------------------------------
# Global soft-delete filter
# Registered on the Session CLASS so it applies to every session in the process,
# including async sessions (which wrap a sync Session internally).
# ---------------------------------------------------------------------------


def _apply_soft_delete_filter(state: ORMExecuteState) -> None:
    """Automatically exclude archived rows from all ORM SELECT statements.

    Skipped when:
      - The statement is not a SELECT (INSERT/UPDATE/DELETE pass through).
      - The statement is a relationship load (SQLAlchemy internal; criteria
        applied at the entity level already handles filtering).
      - The query was issued with execution_options(include_archived=True).
    """
    if (
        state.is_select
        and not state.is_column_load
        and not state.is_relationship_load
        and not state.execution_options.get("include_archived", False)
    ):
        state.statement = state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.archived_at.is_(None),  # type: ignore[attr-defined]
                include_aliases=True,
            )
        )


# Register on the Session CLASS (not an instance) so it applies to every session
# in the process, including async sessions.
# event.listen() call form keeps pyright happy — the function IS referenced here.
event.listen(Session, "do_orm_execute", _apply_soft_delete_filter)


# Suppress the unused-import warning for callers who import this module purely
# to trigger filter registration (the side effect is the point).
__all__: list[Any] = [
    "EffectiveDatedMixin",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
]
