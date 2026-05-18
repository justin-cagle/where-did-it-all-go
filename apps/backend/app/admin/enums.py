"""Enumerations for the admin domain."""

from enum import StrEnum


class NotificationType(StrEnum):
    UNASSIGNED_REGISTRATION = "unassigned_registration"
    SYSTEM_ERROR = "system_error"
    BACKUP_FAILED = "backup_failed"
    REGISTRATION_LIMIT_REACHED = "registration_limit_reached"


class BackupStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class BackupTrigger(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
