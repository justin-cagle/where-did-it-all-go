"""Enums for the budgets domain."""

from enum import StrEnum


class BudgetPeriod(StrEnum):
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    ANNUAL = "annual"
    CUSTOM = "custom"


class BudgetMethod(StrEnum):
    ZERO_BASED = "zero_based"
    ENVELOPE = "envelope"
    FIFTY_THIRTY_TWENTY = "fifty_thirty_twenty"
    PERCENTAGE_BASED = "percentage_based"
    ROLLING_AVERAGE = "rolling_average"
    MANUAL = "manual"
    NONE = "none"


class ExpectedIncomeStrategy(StrEnum):
    FIXED = "fixed"
    FROM_INCOME_SOURCES = "from_income_sources"
    LAST_PERIOD_ACTUAL = "last_period_actual"
    ROLLING_AVERAGE = "rolling_average"
    MANUAL_PER_PERIOD = "manual_per_period"


class RolloverPolicy(StrEnum):
    NONE = "none"
    ACCUMULATE = "accumulate"
    ACCUMULATE_CAPPED = "accumulate_capped"
    DEBT_CARRY = "debt_carry"
    RESET_ON_OVERSPEND = "reset_on_overspend"


class BudgetLineStatus(StrEnum):
    UNDER = "under"
    ON_TRACK = "on_track"
    OVER = "over"


class BudgetRole(StrEnum):
    NEEDS = "needs"
    WANTS = "wants"
    SAVINGS = "savings"
    UNCATEGORIZED = "uncategorized"
