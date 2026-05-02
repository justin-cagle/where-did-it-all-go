"""Initial data layer: platform_fx_rate and audit_event.

Revision ID: 8a3f1c9e2b0d
Revises:
Create Date: 2026-05-02 00:00:00.000000

Creates:
  - update_updated_at_column()  DB function (reused by all subsequent table migrations)
  - platform_fx_rate             FX daily rate table
  - audit_event_append_only()   DB function (immutability enforcement)
  - audit_event                 Append-only audit log
  - tg_audit_event_append_only  BEFORE UPDATE OR DELETE trigger on audit_event

The audit_event trigger is the canonical enforcement of the append-only contract
(DECISIONS.md R4D). It fires before any UPDATE or DELETE and raises an exception,
making it impossible to mutate audit rows regardless of DB role.
For environments with proper role separation, additionally REVOKE UPDATE, DELETE
on audit_event from the app role.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "8a3f1c9e2b0d"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Shared DB function: auto-update updated_at on any row UPDATE.
    # Applied to platform_fx_rate here; subsequent table migrations
    # attach it with: CREATE TRIGGER tg_<table>_updated_at ...
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER
        LANGUAGE plpgsql AS
        $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$
        """
    )

    # ------------------------------------------------------------------
    # platform_fx_rate
    # Daily FX rates, lazily populated (only currencies that appear in
    # actual accounts/transactions). One row per (date, from, to) pair.
    # ------------------------------------------------------------------
    op.create_table(
        "platform_fx_rate",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("rate_date", sa.Date, nullable=False),
        sa.Column("from_currency", sa.String(3), nullable=False),
        sa.Column("to_currency", sa.String(3), nullable=False),
        # NUMERIC(19,10) — more decimal places than money amounts (4dp) because
        # exchange rates like 1.0874123456 need precision that 4dp would lose.
        sa.Column("rate", sa.Numeric(precision=19, scale=10), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_platform_fx_rate"),
        sa.UniqueConstraint(
            "rate_date",
            "from_currency",
            "to_currency",
            name="uq_platform_fx_rate_date_pair",
        ),
    )
    op.create_index("ix_platform_fx_rate_date", "platform_fx_rate", ["rate_date"])
    op.create_index(
        "ix_platform_fx_rate_currencies",
        "platform_fx_rate",
        ["from_currency", "to_currency"],
    )

    # Attach the shared updated_at trigger to platform_fx_rate
    op.execute(
        """
        CREATE TRIGGER tg_platform_fx_rate_updated_at
            BEFORE UPDATE ON platform_fx_rate
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # audit_event_append_only() — immutability enforcement function.
    # Prevents UPDATE and DELETE on audit_event at the database level.
    # This is a hard guarantee: it fires regardless of which DB role
    # (including superusers, unless they explicitly DISABLE TRIGGER).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_event_append_only()
        RETURNS TRIGGER
        LANGUAGE plpgsql AS
        $$
        BEGIN
            RAISE EXCEPTION
                'audit_event is append-only: % is not permitted. '
                'Write a new reversal event referencing source_event_id instead.',
                TG_OP;
        END;
        $$
        """
    )

    # ------------------------------------------------------------------
    # audit_event
    # Append-only audit log. Fields follow DECISIONS.md R4D exactly.
    # household_id is nullable here; the FK constraint to
    # households_household is added in the households migration.
    # ------------------------------------------------------------------
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        # Actor fields
        sa.Column(
            "actor_type",
            sa.String(16),
            nullable=False,
            comment="user | system | automation",
        ),
        sa.Column(
            "actor_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
            comment="user_id when actor_type = user; NULL otherwise",
        ),
        sa.Column(
            "actor_source",
            sa.Text,
            nullable=False,
            comment="e.g. rule_engine, recurrence_detector, user_action",
        ),
        # Scope
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
            comment="FK to households_household added in households migration",
        ),
        # Subject
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "operation",
            sa.String(16),
            nullable=False,
            comment="create|update|delete|archive|merge|split|apply|accept|reject",
        ),
        # Payload
        sa.Column(
            "delta",
            JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="RFC 6902 JSON Patch array",
        ),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column(
            "source_event_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
            comment="Links a reversal to the event it reverses",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_event"),
    )

    # Required indexes (DECISIONS.md R4D)
    op.create_index(
        "ix_audit_event_household_occurred",
        "audit_event",
        ["household_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_audit_event_entity",
        "audit_event",
        ["entity_type", "entity_id", sa.text("occurred_at DESC")],
    )

    # ------------------------------------------------------------------
    # Attach the append-only trigger to audit_event.
    # BEFORE UPDATE OR DELETE raises an exception, making the table
    # immutable at the database level (not just application policy).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TRIGGER tg_audit_event_append_only
            BEFORE UPDATE OR DELETE ON audit_event
            FOR EACH ROW EXECUTE FUNCTION audit_event_append_only()
        """
    )


def downgrade() -> None:
    # Drop in reverse dependency order

    op.execute("DROP TRIGGER IF EXISTS tg_audit_event_append_only ON audit_event")
    op.drop_index("ix_audit_event_entity", table_name="audit_event")
    op.drop_index("ix_audit_event_household_occurred", table_name="audit_event")
    op.drop_table("audit_event")
    op.execute("DROP FUNCTION IF EXISTS audit_event_append_only()")

    op.execute("DROP TRIGGER IF EXISTS tg_platform_fx_rate_updated_at ON platform_fx_rate")
    op.drop_index("ix_platform_fx_rate_currencies", table_name="platform_fx_rate")
    op.drop_index("ix_platform_fx_rate_date", table_name="platform_fx_rate")
    op.drop_table("platform_fx_rate")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
