"""Enumerations for the debts domain."""

from enum import StrEnum


class DebtPlanMethod(StrEnum):
    AVALANCHE = "avalanche"
    SNOWBALL = "snowball"
    CUSTOM = "custom"
    NONE = "none"
