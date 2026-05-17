"""Add user_agent column to households_refresh_token.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-17 00:00:00.000000

Adds:
  - user_agent TEXT nullable column to households_refresh_token
    Stores the User-Agent header from the session that issued the token,
    used by GET /auth/sessions to display session info.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d4e5f6a7b8c9"  # pragma: allowlist secret
down_revision = "c3d4e5f6a7b8"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "households_refresh_token",
        sa.Column("user_agent", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("households_refresh_token", "user_agent")
