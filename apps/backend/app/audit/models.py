"""AuditEvent model — append-only audit log.

The DB enforces append-only via a trigger (see migration 20260502_0000_…).
The app role must never issue UPDATE or DELETE against this table.

Every change written by an automated subsystem (rule engine, recurrence
detection, refund pairing, transfer detection, AI suggestions) is reversible
by the user. Reversals write a NEW audit event referencing the original via
source_event_id — history is appended, never mutated.

delta follows RFC 6902 JSON Patch format:
    [{"op": "replace", "path": "/name", "value": "New Name"}]
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import UUIDPrimaryKeyMixin
from app.platform.time import utcnow


class ActorType(StrEnum):
    """Who caused the event. Values stored as lowercase strings in the DB."""

    USER = "user"
    SYSTEM = "system"
    AUTOMATION = "automation"


class AuditOperation(StrEnum):
    """What operation was performed. Values stored as lowercase strings in the DB.

    Uppercase member names avoid conflicts with str built-in methods
    (e.g. str.split, str.update do not exist, but being explicit is safer).
    """

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ARCHIVE = "archive"
    MERGE = "merge"
    SPLIT = "split"
    APPLY = "apply"
    ACCEPT = "accept"
    REJECT = "reject"


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """Append-only audit log entry.

    No SoftDeleteMixin — rows here are never archived or deleted.
    No TimestampMixin — occurred_at is the authoritative timestamp; there
    is no updated_at because this record is immutable after INSERT.

    household_id is nullable to accommodate system-level events that occur
    outside any household context (e.g., during migrations or bootstrap).
    The FK to households_household is added in the households migration.
    """

    __tablename__ = "audit_event"

    occurred_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("NOW()"),
    )

    # Who/what caused this event
    actor_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="user_id when actor_type = 'user'; NULL for system/automation",
    )
    actor_source: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="e.g. 'rule_engine', 'recurrence_detector', 'user_action'",
    )

    # What was affected
    household_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="FK to households_household added in households migration",
    )
    entity_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="e.g. 'transaction', 'budget', 'goal'",
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        comment="One of: create update delete archive merge split apply accept reject",
    )

    # What changed and why
    delta: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="RFC 6902 JSON Patch array describing the change",
    )
    rationale: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Human-readable reason; carried forward from Recommendation when accepted",
    )
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        nullable=True,
        comment="Links a reversal event to the original event it reverses",
    )

    __table_args__ = (
        # Primary query pattern: all events for a household, newest first
        sa.Index(
            "ix_audit_event_household_occurred",
            "household_id",
            "occurred_at",
            postgresql_ops={"occurred_at": "DESC"},
        ),
        # Secondary pattern: history for a specific entity
        sa.Index(
            "ix_audit_event_entity",
            "entity_type",
            "entity_id",
            "occurred_at",
            postgresql_ops={"occurred_at": "DESC"},
        ),
    )

    def __repr__(self) -> str:
        return (
            f"AuditEvent(id={self.id}, "
            f"op={self.operation}, "
            f"entity={self.entity_type}/{self.entity_id})"
        )
