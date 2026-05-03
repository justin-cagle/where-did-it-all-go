"""Transactions module.

Owns: Transaction, SplitAllocation; deduplication; transfer pairing;
refund pairing; payment groups.

Public interface (consumed by other modules via their service layer):
  - create_transaction — used by ingest module to record imported transactions
  - get_transaction — used for cross-module reads
  - list_transactions — used for cross-module reporting
  - process_dedup — called by ingest after creating a transaction
  - score_dedup_confidence, normalize_description — pure helpers
  - validate_split_amounts, VALID_TRANSITIONS — pure invariants
"""

from app.transactions.enums import (
    DedupResolution,
    GroupType,
    TransactionDirection,
    TransactionState,
    TransactionType,
)
from app.transactions.models import (
    DeduplicationLog,
    PaymentGroup,
    SplitAllocation,
    Transaction,
)
from app.transactions.service import (
    VALID_TRANSITIONS,
    ConflictError,
    InvalidTransitionError,
    NotFoundError,
    ValidationError,
    check_refund_pairable,
    create_transaction,
    get_transaction,
    list_transactions,
    normalize_description,
    process_dedup,
    score_dedup_confidence,
    validate_split_amounts,
)

__all__ = [  # noqa: RUF022 — grouped by category for readability
    # Enums
    "DedupResolution",
    "GroupType",
    "TransactionDirection",
    "TransactionState",
    "TransactionType",
    # Models
    "DeduplicationLog",
    "PaymentGroup",
    "SplitAllocation",
    "Transaction",
    # Service — pure helpers
    "VALID_TRANSITIONS",
    "check_refund_pairable",
    "normalize_description",
    "score_dedup_confidence",
    "validate_split_amounts",
    # Service — DB functions
    "ConflictError",
    "InvalidTransitionError",
    "NotFoundError",
    "ValidationError",
    "create_transaction",
    "get_transaction",
    "list_transactions",
    "process_dedup",
]
