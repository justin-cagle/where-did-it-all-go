"""Enumerations for the ingest module."""

from enum import StrEnum


class IngestProvider(StrEnum):
    SIMPLEFIN = "simplefin"
    OFX = "ofx"
    CSV = "csv"
    MANUAL = "manual"


class ImportSource(StrEnum):
    SIMPLEFIN = "simplefin"
    OFX_UPLOAD = "ofx_upload"
    CSV_UPLOAD = "csv_upload"
    STATEMENT = "statement"


class ImportStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncConfigStatus(StrEnum):
    ACTIVE = "active"
    WARNING = "warning"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    DISABLED = "disabled"


class AmountConvention(StrEnum):
    POSITIVE_IS_CREDIT = "positive_is_credit"
    POSITIVE_IS_DEBIT = "positive_is_debit"
