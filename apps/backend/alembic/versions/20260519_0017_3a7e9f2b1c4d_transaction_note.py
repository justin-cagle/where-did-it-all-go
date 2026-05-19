"""transaction note field

Revision ID: 3a7e9f2b1c4d
Revises: f6a7b8c9d0e1
Create Date: 2026-05-19

Changes:
- transactions_transaction: add note (text, nullable)
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# pragma: allowlist secret
revision: str = "3a7e9f2b1c4d"  # pragma: allowlist secret
down_revision: str | None = "f6a7b8c9d0e1"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions_transaction",
        sa.Column("note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE transactions_transaction DROP COLUMN IF EXISTS note"))
