"""Enumerations for the goals domain."""

from enum import StrEnum


class GoalType(StrEnum):
    SAVINGS_TARGET = "savings_target"
    PURCHASE = "purchase"
    DEBT_PAYOFF = "debt_payoff"
    NET_WORTH = "net_worth"
    CATEGORY_REDUCTION = "category_reduction"
    EMERGENCY_FUND = "emergency_fund"
    RECURRING_CONTRIBUTION = "recurring_contribution"
    MINIMUM_BALANCE = "minimum_balance"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class FundingStrategy(StrEnum):
    DEDICATED_ACCOUNT = "dedicated_account"
    VIRTUAL_ALLOCATION = "virtual_allocation"


class CompletionPolicy(StrEnum):
    ARCHIVE_ON_COMPLETE = "archive_on_complete"
    PROMPT_ON_COMPLETE = "prompt_on_complete"
    AUTO_EXTEND = "auto_extend"
    AUTO_CLONE = "auto_clone"
    CONVERT_TO_RECURRING = "convert_to_recurring"


class FundingSourceType(StrEnum):
    ACCOUNT = "account"
    INCOME_STREAM = "income_stream"
    HOUSEHOLD_SURPLUS = "household_surplus"


class ContributionType(StrEnum):
    MANUAL = "manual"
    TAG_DRIVEN = "tag_driven"
    RECURRING_RULE = "recurring_rule"


class BurnUpStatus(StrEnum):
    AHEAD = "ahead"
    ON_TRACK = "on_track"
    BEHIND = "behind"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"
