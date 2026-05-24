"""Add avatar_url to households_user.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d6e7f8a9b0c1"  # pragma: allowlist secret
down_revision = "c5d6e7f8a9b0"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "households_user",
        sa.Column("avatar_url", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("households_user", "avatar_url")
