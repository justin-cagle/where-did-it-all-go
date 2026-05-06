"""Enumerations for the classification domain."""

from enum import StrEnum


class RuleMode(StrEnum):
    AUTO_APPLY = "auto_apply"
    SUGGEST = "suggest"


class IncomeSourceSubType(StrEnum):
    PAYROLL = "payroll"
    BONUS = "bonus"
    RSU = "rsu"
    REIMBURSEMENT = "reimbursement"


class VariabilityModel(StrEnum):
    FIXED = "fixed"
    RANGE = "range"
    HISTORICAL_DISTRIBUTION = "historical_distribution"


class StrictnessMode(StrEnum):
    STRICT = "strict"
    BEST_GUESS = "best_guess"
    SILENT = "silent"
