"""SQLAlchemy models for the admin domain.

Tables:
  admin_notification       -- instance-level notifications for app admins
  admin_smtp_config        -- single-row SMTP configuration (encrypted credentials)
  admin_backup_config      -- single-row backup configuration (encrypted S3 credentials)
  admin_backup_run         -- log of backup run attempts
  admin_read_only_state    -- single-row read-only mode toggle
  admin_setting            -- key/value store for runtime-overridable config
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.admin.enums import BackupStatus, BackupTrigger, NotificationType
from app.database import Base
from app.platform.ids import new_uuid
from app.platform.time import utcnow


class AdminNotification(Base):
    """Instance-level notification for all app admins."""

    __tablename__ = "admin_notification"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    notification_type: Mapped[str] = mapped_column(
        sa.Enum(NotificationType, name="notification_type", native_enum=False, length=40),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid(as_uuid=True), nullable=True)
    read: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("NOW()"),
    )

    __table_args__ = (sa.Index("ix_admin_notification_read_created", "read", "created_at"),)

    def __repr__(self) -> str:
        return f"AdminNotification(id={self.id}, type={self.notification_type!r})"


class SMTPConfig(Base):
    """Single-row SMTP configuration. Sensitive fields encrypted via security module."""

    __tablename__ = "admin_smtp_config"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    host_enc: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment='encrypted as {"_enc": "<fernet_token>"}',
    )
    port: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=587)
    username_enc: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment='encrypted as {"_enc": "<fernet_token>"}',
    )
    password_enc: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment='encrypted as {"_enc": "<fernet_token>"}',
    )
    from_address: Mapped[str] = mapped_column(sa.Text, nullable=False)
    use_tls: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    configured_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow
    )
    configured_by_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_test_success: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"SMTPConfig(id={self.id})"


class BackupConfig(Base):
    """Single-row backup configuration. S3 credentials encrypted."""

    __tablename__ = "admin_backup_config"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    s3_endpoint_enc: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="nullable; encrypted when set",
    )
    s3_bucket: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    s3_access_key_enc: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="encrypted when set",
    )
    s3_secret_key_enc: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="encrypted when set",
    )
    s3_path_prefix: Mapped[str] = mapped_column(sa.Text, nullable=False, default="wdiag-backups")
    local_retention_days: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=30)
    s3_enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    configured_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow
    )
    configured_by_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"BackupConfig(id={self.id})"


class BackupRun(Base):
    """Log entry for one backup attempt."""

    __tablename__ = "admin_backup_run"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        sa.Enum(BackupStatus, name="backup_status", native_enum=False, length=16),
        nullable=False,
        default=BackupStatus.RUNNING,
    )
    size_bytes: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    local_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    s3_path: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(
        sa.Enum(BackupTrigger, name="backup_trigger", native_enum=False, length=16),
        nullable=False,
    )
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (sa.Index("ix_admin_backup_run_started_at", "started_at"),)

    def __repr__(self) -> str:
        return f"BackupRun(id={self.id}, status={self.status!r})"


class ReadOnlyState(Base):
    """Single-row read-only mode toggle. Cached in Redis key 'system:read_only_state'."""

    __tablename__ = "admin_read_only_state"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    enabled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    enabled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"ReadOnlyState(enabled={self.enabled})"


class AdminSetting(Base):
    """Key/value runtime-overridable configuration. Env vars are the defaults."""

    __tablename__ = "admin_setting"

    key: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    value: Mapped[str] = mapped_column(sa.Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.text("NOW()"),
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("households_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"AdminSetting(key={self.key!r})"
