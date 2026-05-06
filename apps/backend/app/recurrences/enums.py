"""Enumerations for the recurrences domain."""

from enum import StrEnum


class Cadence(StrEnum):
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    ANNUAL = "annual"
    CUSTOM_CRON = "custom_cron"


class RecurrenceKind(StrEnum):
    DETECTED = "detected"
    DECLARED = "declared"


class AmountStrategy(StrEnum):
    FIXED = "fixed"
    LAST_N_AVERAGE = "last_n_average"
    MANUAL_ESTIMATE = "manual_estimate"
    EXTERNAL_SIGNAL = "external_signal"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class ExceptionType(StrEnum):
    SKIP = "skip"
    AMOUNT_CHANGE = "amount_change"
    DATE_SHIFT = "date_shift"


class MatchStatus(StrEnum):
    MATCHED = "matched"
    DEVIATED = "deviated"
    MISSED = "missed"
    DISMISSED = "dismissed"
