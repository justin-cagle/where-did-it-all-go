"""SimpleFIN bridge client.

Fetches accounts and transactions from the SimpleFIN bridge API.
Access URL format: https://<token>@bridge.simplefin.org/simplefin

Credentials in SyncConfig.credentials (after decryption):
  {"access_url": "https://<token>@bridge.simplefin.org/simplefin"}

SimpleFIN amounts are string decimals. Negative = debit (money leaving account).
Dates are Unix timestamps (seconds since epoch) in UTC; we extract the UTC date.

Never log the access_url — it contains the authentication token.
"""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx
import structlog

from app.ingest.parsers import ParsedTransaction

logger = structlog.get_logger(__name__)

# Maps SimpleFIN amount sign to transaction direction.
# Negative amount = debit (money out of account).
_TIMEOUT_SECONDS = 30


def _parse_amount(raw: str) -> tuple[Decimal, str]:
    """Parse SimpleFIN amount string. Returns (abs_amount, direction)."""
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"unparseable SimpleFIN amount: {raw!r}") from exc
    if value < Decimal(0):
        return -value, "debit"
    return value, "credit"


def _timestamp_to_date(ts: int | float) -> datetime:
    return datetime.fromtimestamp(ts, tz=UTC)


async def fetch_transactions(
    access_url: str,
    start_date: datetime,
    end_date: datetime,
) -> list[ParsedTransaction]:
    """Fetch transactions from SimpleFIN for all accounts at the access URL.

    start_date and end_date are passed as Unix timestamps. Returns all
    transactions across all accounts at this access URL.

    Raises httpx.HTTPStatusError on non-2xx responses.
    Never logs access_url.
    """
    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())
    url = f"{access_url}/accounts"
    params = {"start-date": str(start_ts), "end-date": str(end_ts)}

    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    results: list[ParsedTransaction] = []
    for account in data.get("accounts", []):
        simplefin_account_id = str(account.get("id", ""))
        currency = str(account.get("currency", "USD")).upper()
        for txn in account.get("transactions", []):
            raw_id = txn.get("id")
            if not raw_id:
                continue

            raw_amount = str(txn.get("amount", "0"))
            try:
                amount, direction = _parse_amount(raw_amount)
            except ValueError:
                logger.warning("simplefin.parse_amount_failed", external_id=raw_id)
                continue

            posted_ts = txn.get("posted")
            if posted_ts is None:
                logger.warning("simplefin.missing_posted", external_id=raw_id)
                continue

            posted_dt = _timestamp_to_date(int(posted_ts))
            posted_date = posted_dt.date()

            description = str(txn.get("description") or txn.get("payee") or "")

            results.append(
                ParsedTransaction(
                    external_id=str(raw_id),
                    amount=amount,
                    currency=currency,
                    direction=direction,
                    posted_date=posted_date,
                    occurred_at=posted_date,
                    description=description,
                    merchant_name=txn.get("payee") or None,
                    transaction_type_hint=None,
                    source_account_id=simplefin_account_id or None,
                )
            )

    logger.info("simplefin.fetch_complete", count=len(results))
    return results
