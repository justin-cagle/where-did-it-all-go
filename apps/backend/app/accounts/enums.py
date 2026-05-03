"""Enumerations for the accounts domain."""

from enum import StrEnum


class AccountType(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    INVESTMENT = "investment"
    LOAN = "loan"
    LINE_OF_CREDIT = "line_of_credit"
    MANUAL = "manual"
    OTHER = "other"


class MinimumPaymentStrategy(StrEnum):
    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE_OF_BALANCE = "percentage_of_balance"
    FROM_STATEMENT = "from_statement"


ASSET_ACCOUNT_TYPES: frozenset[AccountType] = frozenset(
    {
        AccountType.CHECKING,
        AccountType.SAVINGS,
        AccountType.INVESTMENT,
        AccountType.MANUAL,
        AccountType.OTHER,
    }
)

LIABILITY_ACCOUNT_TYPES: frozenset[AccountType] = frozenset(
    {
        AccountType.CREDIT_CARD,
        AccountType.LOAN,
        AccountType.LINE_OF_CREDIT,
    }
)
