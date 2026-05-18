"""Create admin module tables.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-18 00:00:00.000000

Creates:
  - admin_notification       (notifications for app admins)
  - admin_smtp_config        (single-row SMTP config, singleton enforced)
  - admin_backup_config      (single-row backup config, singleton enforced)
  - admin_backup_run         (backup run log)
  - admin_read_only_state    (single-row read-only toggle, seeded enabled=false)
  - admin_setting            (key/value runtime config overrides)
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e5f6a7b8c9d0"  # pragma: allowlist secret
down_revision = "d4e5f6a7b8c9"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_notification",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "notification_type",
            sa.String(40),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_admin_notification_read_created",
        "admin_notification",
        ["read", "created_at"],
    )

    op.create_table(
        "admin_smtp_config",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("host_enc", sa.Text(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default=sa.text("587")),
        sa.Column("username_enc", sa.Text(), nullable=False),
        sa.Column("password_enc", sa.Text(), nullable=False),
        sa.Column("from_address", sa.Text(), nullable=False),
        sa.Column("use_tls", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "configured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "configured_by_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_test_success", sa.Boolean(), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("CREATE UNIQUE INDEX uq_admin_smtp_config_singleton ON admin_smtp_config ((true))")

    op.create_table(
        "admin_backup_config",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("s3_endpoint_enc", sa.Text(), nullable=True),
        sa.Column("s3_bucket", sa.Text(), nullable=True),
        sa.Column("s3_access_key_enc", sa.Text(), nullable=True),
        sa.Column("s3_secret_key_enc", sa.Text(), nullable=True),
        sa.Column(
            "s3_path_prefix",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'wdiag-backups'"),
        ),
        sa.Column(
            "local_retention_days", sa.Integer(), nullable=False, server_default=sa.text("30")
        ),
        sa.Column("s3_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "configured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "configured_by_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_admin_backup_config_singleton ON admin_backup_config ((true))"
    )

    op.create_table(
        "admin_backup_run",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("s3_path", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(16), nullable=False),
        sa.Column(
            "triggered_by_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_admin_backup_run_started_at", "admin_backup_run", ["started_at"])

    op.create_table(
        "admin_read_only_state",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "enabled_by_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_admin_read_only_state_singleton ON admin_read_only_state ((true))"
    )

    import uuid as _uuid

    seed_id = str(_uuid.uuid4())
    op.execute(
        sa.text("INSERT INTO admin_read_only_state (id, enabled) VALUES (:id, false)").bindparams(
            id=seed_id
        )
    )

    op.create_table(
        "admin_setting",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_by_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("households_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("admin_setting")
    op.drop_index("uq_admin_read_only_state_singleton", table_name="admin_read_only_state")
    op.drop_table("admin_read_only_state")
    op.drop_index("ix_admin_backup_run_started_at", table_name="admin_backup_run")
    op.drop_table("admin_backup_run")
    op.drop_index("uq_admin_backup_config_singleton", table_name="admin_backup_config")
    op.drop_table("admin_backup_config")
    op.drop_index("uq_admin_smtp_config_singleton", table_name="admin_smtp_config")
    op.drop_table("admin_smtp_config")
    op.drop_index("ix_admin_notification_read_created", table_name="admin_notification")
    op.drop_table("admin_notification")
