"""Replace admin_smtp_config.use_tls (bool) with tls_mode (text enum).

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-05-21 00:00:00.000000

Maps existing rows: use_tls=true -> 'ssl', use_tls=false -> 'none'.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b4c5d6e7f8a9"  # pragma: allowlist secret
down_revision = "a3b4c5d6e7f8"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_smtp_config",
        sa.Column("tls_mode", sa.Text(), nullable=False, server_default=sa.text("'ssl'")),
    )
    op.execute(
        "UPDATE admin_smtp_config SET tls_mode = CASE WHEN use_tls THEN 'ssl' ELSE 'none' END"
    )
    op.drop_column("admin_smtp_config", "use_tls")


def downgrade() -> None:
    op.add_column(
        "admin_smtp_config",
        sa.Column("use_tls", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.execute(
        "UPDATE admin_smtp_config SET use_tls = CASE WHEN tls_mode = 'ssl' THEN true ELSE false END"
    )
    op.drop_column("admin_smtp_config", "tls_mode")
