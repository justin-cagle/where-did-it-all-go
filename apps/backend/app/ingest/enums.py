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
