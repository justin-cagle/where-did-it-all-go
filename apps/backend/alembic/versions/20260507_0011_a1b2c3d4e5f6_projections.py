"""Projections domain tables.

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-07 00:00:00.000000

Adds:
  - projections_scenario        what-if scenario (saved or transient)
  - projections_run             projection run metadata + cache
  - projections_event           projected cash-flow events
  - projections_breach_event    balance/limit/goal breach events
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision = "f1a2b3c4d5e6"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projections_scenario",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column(
            "overrides",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("base_run_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "saved",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_projections_scenario_household",
        "projections_scenario",
        ["household_id"],
    )
    op.create_index(
        "ix_projections_scenario_household_saved",
        "projections_scenario",
        ["household_id", "saved"],
    )

    op.create_table(
        "projections_run",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("scenario_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("horizon_months", sa.Integer, nullable=False),
        sa.Column("inputs_hash", sa.Text, nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_projections_run_household",
        "projections_run",
        ["household_id"],
    )
    op.create_index(
        "ix_projections_run_cache_key",
        "projections_run",
        ["household_id", "inputs_hash", "as_of_date", "horizon_months", "scenario_id"],
    )

    op.create_table(
        "projections_event",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("scenario_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("account_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_date", sa.Date, nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("confidence", sa.String(8), nullable=False),
        sa.Column("source_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["projections_run.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_projections_event_run", "projections_event", ["run_id"])
    op.create_index(
        "ix_projections_event_household_date",
        "projections_event",
        ["household_id", "event_date"],
    )
    op.create_index(
        "ix_projections_event_run_account",
        "projections_event",
        ["run_id", "account_id", "event_date"],
    )

    op.create_table(
        "projections_breach_event",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("breach_type", sa.String(24), nullable=False),
        sa.Column("breach_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=4, asdecimal=True), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["projections_run.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_projections_breach_run",
        "projections_breach_event",
        ["run_id"],
    )
    op.create_index(
        "ix_projections_breach_household",
        "projections_breach_event",
        ["household_id"],
    )


def downgrade() -> None:
    op.drop_table("projections_breach_event")
    op.drop_table("projections_event")
    op.drop_table("projections_run")
    op.drop_table("projections_scenario")
