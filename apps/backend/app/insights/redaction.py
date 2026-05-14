"""Redaction layer for AI data sharing.

Treated as security-critical code. Full test coverage required.

Public API:
    redact(data, level, *, household_salt="")

Data schema (structured dict passed by insight generators):
    {
        "period":           {"year": int, "month": int},
        "household_name":   str,
        "categories": [
            {
                "name":       str,
                "total":      str,   # Decimal serialized as string
                "count":      int,
                "currency":   str,
                "direction":  str,   # "up" | "down" | "stable"
                "change_pct": float | None,
            }
        ],
        "transactions": [
            {
                "amount":     str,   # Decimal as string
                "currency":   str,
                "date":       str,   # "YYYY-MM-DD"
                "direction":  str,
                "merchant":   str,
                "description": str,
                "category":   str,
                "account_id": str,
            }
        ],
        "accounts": [
            {
                "id":             str,
                "name":           str,
                "account_number": str,
                "balance":        str,
                "currency":       str,
            }
        ],
        "income_sources": [
            {
                "name":     str,
                "total":    str,
                "currency": str,
                "count":    int,
            }
        ],
        "patterns": {
            "spending_direction": str,
            "change_pct":         float | None,
        },
    }
"""

import hashlib
from typing import Any


class RedactionError(Exception):
    """Raised when redaction is misconfigured or called with level=disabled."""


def redact(
    data: dict[str, Any],
    level: str,
    *,
    household_salt: str = "",
) -> dict[str, Any]:
    """Apply redaction to data based on the ai_data_sharing level.

    Args:
        data: Structured dict from an insight generator.
        level: AiDataSharing enum value as string.
        household_salt: Used to hash merchant names deterministically per household.

    Returns:
        Redacted copy of data. The original is never mutated.

    Raises:
        RedactionError: If level is "disabled" (caller should never reach here)
            or if level is unrecognised.
    """
    if level == "disabled":
        raise RedactionError(
            "redact() called with level='disabled'; provider should not be invoked "
            "for households with ai_data_sharing=disabled"
        )
    if level == "full":
        return dict(data)
    if level == "generalizations_only":
        return _generalizations_only(data)
    if level == "aggregates_only":
        return _aggregates_only(data, household_salt)
    if level == "redacted":
        return _redacted(data, household_salt)
    raise RedactionError(f"unknown ai_data_sharing level: {level!r}")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _hash_merchant(merchant: str, household_salt: str) -> str:
    """SHA-256 hash of merchant + household salt. One-way, household-scoped."""
    payload = f"{household_salt}:{merchant}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _generalizations_only(data: dict[str, Any]) -> dict[str, Any]:
    """Strip all amounts, merchants, account names, dates beyond month.

    Keep: category names, period (month/year), directional patterns, counts.
    """
    result: dict[str, Any] = {}

    # Keep period (month/year only)
    if "period" in data:
        result["period"] = {
            "year": data["period"].get("year"),
            "month": data["period"].get("month"),
        }

    # Keep category names, direction, counts — strip amounts and change_pct
    if "categories" in data:
        result["categories"] = [
            {
                "name": cat.get("name", ""),
                "count": cat.get("count", 0),
                "direction": cat.get("direction", ""),
            }
            for cat in data["categories"]
        ]

    # Strip all transactions
    result["transactions"] = []

    # Strip all accounts
    result["accounts"] = []

    # Strip all income sources
    result["income_sources"] = []

    # Keep spending direction only — strip change_pct
    if "patterns" in data:
        result["patterns"] = {
            "spending_direction": data["patterns"].get("spending_direction", ""),
        }

    return result


def _aggregates_only(data: dict[str, Any], _household_salt: str) -> dict[str, Any]:
    """Keep category-level totals and counts; hash merchants; strip transaction detail."""
    result: dict[str, Any] = {}

    if "period" in data:
        result["period"] = dict(data["period"])

    # Full category aggregates — amounts allowed at category level
    if "categories" in data:
        result["categories"] = [
            {
                "name": cat.get("name", ""),
                "total": cat.get("total", "0"),
                "count": cat.get("count", 0),
                "currency": cat.get("currency", ""),
                "direction": cat.get("direction", ""),
                "change_pct": cat.get("change_pct"),
            }
            for cat in data["categories"]
        ]

    # Strip individual transactions — aggregate only
    result["transactions"] = []

    # Strip account detail — no names or numbers
    result["accounts"] = []

    # Strip income source names
    if "income_sources" in data:
        result["income_sources"] = [
            {
                "total": src.get("total", "0"),
                "currency": src.get("currency", ""),
                "count": src.get("count", 0),
                # name stripped — cannot identify income sources
            }
            for src in data["income_sources"]
        ]

    if "patterns" in data:
        result["patterns"] = dict(data["patterns"])

    return result


def _redacted(data: dict[str, Any], household_salt: str) -> dict[str, Any]:
    """Keep transaction-level structure; strip account numbers, descriptions, user/income names."""
    result: dict[str, Any] = {}

    if "period" in data:
        result["period"] = dict(data["period"])

    if "categories" in data:
        result["categories"] = [
            {
                "name": cat.get("name", ""),
                "total": cat.get("total", "0"),
                "count": cat.get("count", 0),
                "currency": cat.get("currency", ""),
                "direction": cat.get("direction", ""),
                "change_pct": cat.get("change_pct"),
            }
            for cat in data["categories"]
        ]

    # Transaction-level detail — strip PII, hash merchants
    if "transactions" in data:
        result["transactions"] = [
            {
                "amount": txn.get("amount", "0"),
                "currency": txn.get("currency", ""),
                "date": txn.get("date", ""),
                "direction": txn.get("direction", ""),
                "merchant_hash": _hash_merchant(txn.get("merchant", ""), household_salt),
                # description stripped
                # account_id stripped
                "category": txn.get("category", ""),
            }
            for txn in data["transactions"]
        ]

    # Strip account identifiers — no names, numbers, or IDs
    result["accounts"] = []

    # Strip income source names
    if "income_sources" in data:
        result["income_sources"] = [
            {
                "total": src.get("total", "0"),
                "currency": src.get("currency", ""),
                "count": src.get("count", 0),
            }
            for src in data["income_sources"]
        ]

    if "patterns" in data:
        result["patterns"] = dict(data["patterns"])

    return result
