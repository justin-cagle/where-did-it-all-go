"""CSV transaction parser.

Configurable column mapping and sign convention. Configuration is stored in
SyncConfig.credentials (encrypted) and passed in decrypted as a dict.

Config schema (all keys required unless noted):
  {
    "column_mapping": {
      "date":        "Date",          # column header name for transaction date
      "amount":      "Amount",        # column header name for amount
      "description": "Description",   # column header name for description
      "merchant":    "Merchant",      # optional — merchant/payee column
      "currency":    "Currency"       # optional — per-row currency override
    },
    "date_format":   "%m/%d/%Y",      # strptime format for date column
    "amount_sign":   "positive_is_debit" | "positive_is_credit",
    "default_currency": "USD"         # optional, defaults to "USD"
  }

Amount sign convention:
  positive_is_debit:  +100 = $100 debit, -100 = $100 credit
  positive_is_credit: +100 = $100 credit, -100 = $100 debit
"""

import csv
import io
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.ingest.parsers import ParsedTransaction


class CsvParseError(Exception):
    """Raised when the CSV config is invalid or the file cannot be parsed."""


def _parse_row_date(raw: str, fmt: str) -> date:
    try:
        return datetime.strptime(raw.strip(), fmt).date()
    except ValueError as exc:
        raise CsvParseError(f"cannot parse date {raw!r} with format {fmt!r}") from exc


def _parse_row_amount(raw: str, sign_convention: str) -> tuple[Decimal, str]:
    """Parse CSV amount string. Returns (abs_amount, direction)."""
    cleaned = raw.strip().replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise CsvParseError(f"cannot parse amount {raw!r}") from exc

    if sign_convention == "positive_is_debit":
        if value >= Decimal(0):
            return value, "debit"
        return -value, "credit"
    elif sign_convention == "positive_is_credit":
        if value >= Decimal(0):
            return value, "credit"
        return -value, "debit"
    else:
        raise CsvParseError(
            f"unknown amount_sign convention: {sign_convention!r}. "
            "Expected 'positive_is_debit' or 'positive_is_credit'."
        )


def parse_csv(content: bytes, config: dict[str, Any]) -> list[ParsedTransaction]:
    """Parse CSV bytes using the provided column-mapping config.

    Skips rows with missing or unparseable required fields. Raises CsvParseError
    when the config is structurally invalid or mandatory columns are absent.
    """
    mapping: dict[str, str] = config.get("column_mapping", {})
    date_fmt: str = config.get("date_format", "%Y-%m-%d")
    sign_convention: str = config.get("amount_sign", "positive_is_debit")
    default_currency: str = str(config.get("default_currency", "USD")).upper()

    date_col = mapping.get("date")
    amount_col = mapping.get("amount")
    description_col = mapping.get("description")
    merchant_col = mapping.get("merchant")
    currency_col = mapping.get("currency")

    if not date_col or not amount_col or not description_col:
        raise CsvParseError("column_mapping must include 'date', 'amount', and 'description'")

    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    results: list[ParsedTransaction] = []
    for row in reader:
        date_raw = row.get(date_col, "").strip()
        amount_raw = row.get(amount_col, "").strip()
        description = row.get(description_col, "").strip()

        if not date_raw or not amount_raw or not description:
            continue

        try:
            posted_date = _parse_row_date(date_raw, date_fmt)
            amount, direction = _parse_row_amount(amount_raw, sign_convention)
        except CsvParseError:
            continue

        merchant = row.get(merchant_col, "").strip() if merchant_col else None
        currency_raw = row.get(currency_col, "").strip() if currency_col else None
        currency = currency_raw.upper() if currency_raw else default_currency

        # CSV rows have no source-provided unique ID; generate a stable one from
        # the row content so idempotent re-imports still dedup correctly.
        stable_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{posted_date}|{amount}|{currency}|{direction}|{description}",
            )
        )

        results.append(
            ParsedTransaction(
                external_id=stable_id,
                amount=amount,
                currency=currency,
                direction=direction,
                posted_date=posted_date,
                occurred_at=posted_date,
                description=description,
                merchant_name=merchant or None,
                transaction_type_hint=None,
            )
        )

    return results
