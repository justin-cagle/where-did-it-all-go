"""household invitation table

Revision ID: 5c8b2d4e7f1a
Revises: 3a7e9f2b1c4d
Create Date: 2026-05-19

Changes:
- households_invitation: new table with token, status, email, role, expiry, email fields
- Indexes: token (unique), (invited_email, status), (household_id, status)
- Partial unique index: (household_id, invited_email) WHERE status = 'pending'
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# pragma: allowlist secret
revision: str = "5c8b2d4e7f1a"  # pragma: allowlist secret
down_revision: str | None = "3a7e9f2b1c4d"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "households_invitation",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("household_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("invited_email", sa.Text(), nullable=False),
        sa.Column("invited_by_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households_household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_id"],
            ["households_user.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by_id"],
            ["households_user.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_households_invitation_token",
        "households_invitation",
        ["token"],
        unique=True,
    )
    op.create_index(
        "ix_households_invitation_email_status",
        "households_invitation",
        ["invited_email", "status"],
    )
    op.create_index(
        "ix_households_invitation_household_status",
        "households_invitation",
        ["household_id", "status"],
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_households_invitation_pending "
            "ON households_invitation (household_id, invited_email) "
            "WHERE status = 'pending'"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_households_invitation_pending"))
    op.drop_index("ix_households_invitation_household_status", table_name="households_invitation")
    op.drop_index("ix_households_invitation_email_status", table_name="households_invitation")
    op.drop_index("ix_households_invitation_token", table_name="households_invitation")
    op.drop_table("households_invitation")
