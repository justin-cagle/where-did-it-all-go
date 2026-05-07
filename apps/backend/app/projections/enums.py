"""Enumerations for the projections domain."""

from enum import StrEnum


class ProjectedEventType(StrEnum):
    RECURRENCE = "recurrence"
    BUDGET_SPEND = "budget_spend"
    DEBT_PAYMENT = "debt_payment"
    GOAL_CONTRIBUTION = "goal_contribution"
    INCOME = "income"
    BALANCE_BREACH = "balance_breach"
    GOAL_MILESTONE = "goal_milestone"


class ProjectedDirection(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class ProjectedConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ProjectionRunStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class BreachType(StrEnum):
    NEGATIVE_BALANCE = "negative_balance"
    CREDIT_LIMIT = "credit_limit"
    GOAL_REACHED = "goal_reached"
    DEBT_FREE = "debt_free"


class OverrideType(StrEnum):
    ADD_RECURRENCE = "add_recurrence"
    REMOVE_RECURRENCE = "remove_recurrence"
    CHANGE_INCOME = "change_income"
    CHANGE_EXTRA_DEBT_PAYMENT = "change_extra_debt_payment"
    CHANGE_GOAL_CONTRIBUTION = "change_goal_contribution"
    CHANGE_ACCOUNT_BALANCE = "change_account_balance"
