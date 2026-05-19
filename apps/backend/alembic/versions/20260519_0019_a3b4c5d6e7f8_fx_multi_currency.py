"""FX multi-currency: rate source/fetched_at, transaction FX fields, approx-fx flags

Revision ID: a3b4c5d6e7f8
Revises: 5c8b2d4e7f1a
Create Date: 2026-05-19

Additive-only migration. All new columns are nullable or have server defaults.
No backfill required -- existing rows treated as home-currency amounts.
"""

import sqlalchemy as sa

from alembic import op

revision = "a3b4c5d6e7f8"  # pragma: allowlist secret
down_revision = "5c8b2d4e7f1a"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # platform_fx_rate: add source + fetched_at
    # -------------------------------------------------------------------------
    op.add_column(
        "platform_fx_rate",
        sa.Column(
            "source",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'frankfurter'"),
        ),
    )
    op.add_column(
        "platform_fx_rate",
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # -------------------------------------------------------------------------
    # transactions_transaction: FX fields (all nullable -- no backfill)
    # -------------------------------------------------------------------------
    op.add_column(
        "transactions_transaction",
        sa.Column("fx_rate", sa.Numeric(precision=19, scale=8, asdecimal=True), nullable=True),
    )
    op.add_column(
        "transactions_transaction",
        sa.Column("fx_rate_date", sa.Date, nullable=True),
    )
    op.add_column(
        "transactions_transaction",
        sa.Column(
            "fx_rate_source",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
    )
    op.add_column(
        "transactions_transaction",
        sa.Column(
            "home_currency_amount",
            sa.Numeric(precision=19, scale=4, asdecimal=True),
            nullable=True,
        ),
    )
    op.add_column(
        "transactions_transaction",
        sa.Column("home_currency", sa.String(3), nullable=True),
    )

    # -------------------------------------------------------------------------
    # budgets_period_actual: has_approximate_fx flag
    # -------------------------------------------------------------------------
    op.add_column(
        "budgets_period_actual",
        sa.Column(
            "has_approximate_fx",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )

    # -------------------------------------------------------------------------
    # goals_snapshot: has_approximate_fx flag
    # -------------------------------------------------------------------------
    op.add_column(
        "goals_snapshot",
        sa.Column(
            "has_approximate_fx",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )


def downgrade() -> None:
    op.drop_column("goals_snapshot", "has_approximate_fx")
    op.drop_column("budgets_period_actual", "has_approximate_fx")
    op.drop_column("transactions_transaction", "home_currency")
    op.drop_column("transactions_transaction", "home_currency_amount")
    op.drop_column("transactions_transaction", "fx_rate_source")
    op.drop_column("transactions_transaction", "fx_rate_date")
    op.drop_column("transactions_transaction", "fx_rate")
    op.drop_column("platform_fx_rate", "fetched_at")
    op.drop_column("platform_fx_rate", "source")
