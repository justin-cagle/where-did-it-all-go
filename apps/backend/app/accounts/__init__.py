"""Accounts module.

Owns: Account, AccountGroup, DebtAccount, DebtBalance, ManualAccount entities;
balance reconciliation; account lifecycle.
"""

from app.accounts.enums import (
    ASSET_ACCOUNT_TYPES,
    LIABILITY_ACCOUNT_TYPES,
    AccountType,
    MinimumPaymentStrategy,
)
from app.accounts.models import Account, AccountGroup, DebtAccount, DebtBalance, ManualAccount
from app.accounts.service import (
    ConflictError,
    GroupCandidate,
    NotFoundError,
    ValidationError,
    add_account_to_group,
    add_debt_balance,
    archive_account,
    archive_account_group,
    create_account,
    create_account_group,
    create_debt_annotation,
    find_group_candidates,
    get_account,
    get_account_group,
    get_debt_annotation,
    list_account_groups,
    list_accounts,
    list_debt_balances,
    reconcile_balance,
    remove_account_from_group,
    update_account,
    update_account_group,
    update_debt_annotation,
    validate_balance,
)

__all__ = [
    "ASSET_ACCOUNT_TYPES",
    "LIABILITY_ACCOUNT_TYPES",
    # Models
    "Account",
    "AccountGroup",
    # Enums
    "AccountType",
    # Service errors
    "ConflictError",
    "DebtAccount",
    "DebtBalance",
    # Service operations
    "GroupCandidate",
    "ManualAccount",
    "MinimumPaymentStrategy",
    "NotFoundError",
    "ValidationError",
    "add_account_to_group",
    "add_debt_balance",
    "archive_account",
    "archive_account_group",
    "create_account",
    "create_account_group",
    "create_debt_annotation",
    "find_group_candidates",
    "get_account",
    "get_account_group",
    "get_debt_annotation",
    "list_account_groups",
    "list_accounts",
    "list_debt_balances",
    "reconcile_balance",
    "remove_account_from_group",
    "update_account",
    "update_account_group",
    "update_debt_annotation",
    "validate_balance",
]
