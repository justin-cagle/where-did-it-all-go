"""Enumerations for the transactions domain."""

from enum import StrEnum


class TransactionDirection(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class TransactionType(StrEnum):
    PAYROLL = "payroll"
    REFUND = "refund"
    TRANSFER = "transfer"
    FEE = "fee"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    REGULAR = "regular"


class TransactionState(StrEnum):
    PENDING = "pending"
    POSTED = "posted"
    RECONCILED = "reconciled"


class GroupType(StrEnum):
    SPLIT_PURCHASE = "split_purchase"
    SPLIT_FUNDING = "split_funding"


class DedupResolution(StrEnum):
    MERGED = "merged"
    REJECTED = "rejected"
    PENDING = "pending"
