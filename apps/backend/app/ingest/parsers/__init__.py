"""Parser output types shared across all ingest parsers."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class ParsedTransaction:
    """Normalized transaction as parsed from any source before DB write.

    external_id: source-provided dedup ID (FITID, SimpleFIN ID). None for CSV
      rows without a unique ID.
    direction: "debit" (money out) or "credit" (money in).
    transaction_type_hint: optional type from source (e.g. OFX TRNTYPE mapped
      to our enum strings). None means classification pipeline decides.
    """

    amount: Decimal
    currency: str
    direction: str
    posted_date: date
    occurred_at: date
    description: str
    external_id: str | None = None
    merchant_name: str | None = None
    transaction_type_hint: str | None = None
