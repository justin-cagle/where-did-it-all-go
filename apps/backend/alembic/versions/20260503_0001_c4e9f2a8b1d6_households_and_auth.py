"""Households and auth tables.

Revision ID: c4e9f2a8b1d6
Revises: 8a3f1c9e2b0d
Create Date: 2026-05-03 00:00:00.000000

Creates:
  - households_household    — top-level organizational unit
  - households_user         — application user
  - households_membership   — user ↔ household association with role
  - households_refresh_token — server-side opaque refresh tokens

Adds:
  - FK: audit_event.household_id → households_household.id
  - updated_at triggers on households_household, households_user, households_membership
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4e9f2a8b1d6"
down_revision: str | None = "8a3f1c9e2b0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # households_household
    # ------------------------------------------------------------------
    op.create_table(
        "households_household",
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "visibility_mode",
            sa.String(40),
            nullable=False,
            server_default="fully_shared",
        ),
        sa.Column(
            "home_currency",
            sa.String(3),
            nullable=False,
            server_default="USD",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_households_household"),
    )
    op.create_index("ix_households_household_name", "households_household", ["name"])
    op.execute(
        """
        CREATE TRIGGER tg_households_household_updated_at
            BEFORE UPDATE ON households_household
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # households_user
    # ------------------------------------------------------------------
    op.create_table(
        "households_user",
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column(
            "is_app_admin",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("totp_secret", sa.Text, nullable=True),
        sa.Column("totp_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id", name="pk_households_user"),
        sa.UniqueConstraint("email", name="uq_households_user_email"),
    )
    op.create_index("ix_households_user_email", "households_user", ["email"], unique=True)
    op.execute(
        """
        CREATE TRIGGER tg_households_user_updated_at
            BEFORE UPDATE ON households_user
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # households_membership
    # ------------------------------------------------------------------
    op.create_table(
        "households_membership",
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_household.id",
                ondelete="CASCADE",
                name="fk_households_membership_household",
            ),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_user.id",
                ondelete="CASCADE",
                name="fk_households_membership_user",
            ),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.PrimaryKeyConstraint("id", name="pk_households_membership"),
        sa.UniqueConstraint(
            "household_id",
            "user_id",
            name="uq_households_membership_hh_user",
        ),
    )
    op.create_index(
        "ix_households_membership_household",
        "households_membership",
        ["household_id"],
    )
    op.create_index("ix_households_membership_user", "households_membership", ["user_id"])
    op.execute(
        """
        CREATE TRIGGER tg_households_membership_updated_at
            BEFORE UPDATE ON households_membership
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # ------------------------------------------------------------------
    # households_refresh_token
    # ------------------------------------------------------------------
    op.create_table(
        "households_refresh_token",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_user.id",
                ondelete="CASCADE",
                name="fk_households_refresh_token_user",
            ),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "households_household.id",
                ondelete="CASCADE",
                name="fk_households_refresh_token_household",
            ),
            nullable=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "idle_timeout_seconds",
            sa.Integer,
            nullable=False,
            server_default="1800",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_households_refresh_token"),
        sa.UniqueConstraint("token_hash", name="uq_households_refresh_token_hash"),
    )
    op.create_index("ix_households_refresh_token_user", "households_refresh_token", ["user_id"])
    op.create_index(
        "ix_households_refresh_token_hash",
        "households_refresh_token",
        ["token_hash"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # Add FK: audit_event.household_id → households_household.id
    # Left as nullable + FK-free in the initial migration; now the
    # referenced table exists.
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_audit_event_household",
        "audit_event",
        "households_household",
        ["household_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_audit_event_household", "audit_event", type_="foreignkey")

    op.drop_index("ix_households_refresh_token_hash", table_name="households_refresh_token")
    op.drop_index("ix_households_refresh_token_user", table_name="households_refresh_token")
    op.drop_table("households_refresh_token")

    op.execute(
        "DROP TRIGGER IF EXISTS tg_households_membership_updated_at ON households_membership"
    )
    op.drop_index("ix_households_membership_user", table_name="households_membership")
    op.drop_index("ix_households_membership_household", table_name="households_membership")
    op.drop_table("households_membership")

    op.execute("DROP TRIGGER IF EXISTS tg_households_user_updated_at ON households_user")
    op.drop_index("ix_households_user_email", table_name="households_user")
    op.drop_table("households_user")

    op.execute("DROP TRIGGER IF EXISTS tg_households_household_updated_at ON households_household")
    op.drop_index("ix_households_household_name", table_name="households_household")
    op.drop_table("households_household")
