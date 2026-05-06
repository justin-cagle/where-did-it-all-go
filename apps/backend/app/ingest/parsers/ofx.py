"""OFX/QFX parser.

Parses uploaded OFX 1.x (SGML) and OFX 2.x (XML) file bytes.

Date handling: extracts the first 8 characters of DTPOSTED (YYYYMMDD) as the
bank-reported calendar date WITHOUT timezone conversion. This preserves the
date as the bank intends it — see data-layer.md for the rationale.

OFX TRNTYPE values are mapped to our transaction_type hints where applicable.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.ingest.parsers import ParsedTransaction

# OFX TRNTYPE → our transaction_type hint (partial mapping; None = let classifier decide)
_TRNTYPE_MAP: dict[str, str] = {
    "DIRECTDEP": "payroll",
    "INT": "interest",
    "DIV": "dividend",
    "FEE": "fee",
    "SRVCHG": "fee",
    "XFER": "transfer",
}


def _extract_tag(block: str, tag: str) -> str | None:
    """Return the trimmed value of the first occurrence of tag in block."""
    m = re.search(rf"<{tag}>\s*([^<\r\n]+)", block, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _parse_dtposted(raw: str) -> date:
    """Parse OFX DTPOSTED to a date using only the first 8 characters (YYYYMMDD).

    Intentionally ignores time and timezone suffix to preserve the bank-reported
    calendar date without UTC conversion.
    """
    digits = raw.strip()[:8]
    if len(digits) < 8 or not digits.isdigit():
        raise ValueError(f"invalid DTPOSTED: {raw!r}")
    return date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))


def _parse_amount(raw: str) -> tuple[Decimal, str]:
    """Parse OFX TRNAMT. Negative = debit (money out), positive = credit."""
    try:
        value = Decimal(raw.strip())
    except InvalidOperation as exc:
        raise ValueError(f"unparseable OFX amount: {raw!r}") from exc
    if value < Decimal(0):
        return -value, "debit"
    return value, "credit"


def _find_blocks(text: str) -> list[str]:
    """Extract all STMTTRN block contents from OFX text (SGML and XML)."""
    # XML style: <STMTTRN>...</STMTTRN>
    xml_blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, re.DOTALL | re.IGNORECASE)
    if xml_blocks:
        return xml_blocks

    # SGML style: <STMTTRN>...<STMTTRN> or <STMTTRN>...</STMTTRNLIST>
    sgml_blocks = re.split(r"<STMTTRN>", text, flags=re.IGNORECASE)
    if len(sgml_blocks) > 1:
        results = []
        for raw in sgml_blocks[1:]:
            end = re.search(r"</STMTTRNLIST>|</STMTRS>|</CCSTMTRS>", raw, re.IGNORECASE)
            results.append(raw[: end.start()] if end else raw)
        return results

    return []


def parse_ofx(content: bytes) -> list[ParsedTransaction]:
    """Parse OFX/QFX file bytes. Returns list of ParsedTransaction.

    Skips transactions that are missing required fields (FITID, DTPOSTED, TRNAMT).
    Does not raise on individual parse errors — malformed rows are silently dropped.
    """
    text = content.decode("utf-8", errors="replace")
    blocks = _find_blocks(text)

    # Default currency: try to extract from the file
    currency_m = re.search(r"<CURDEF>\s*([A-Z]{3})", text, re.IGNORECASE)
    default_currency = currency_m.group(1).upper() if currency_m else "USD"

    results: list[ParsedTransaction] = []
    for block in blocks:
        fitid = _extract_tag(block, "FITID")
        dtposted_raw = _extract_tag(block, "DTPOSTED")
        trnamt_raw = _extract_tag(block, "TRNAMT")

        if not fitid or not dtposted_raw or not trnamt_raw:
            continue

        try:
            posted_date = _parse_dtposted(dtposted_raw)
            amount, direction = _parse_amount(trnamt_raw)
        except ValueError:
            continue

        name = _extract_tag(block, "NAME")
        memo = _extract_tag(block, "MEMO")
        trntype = _extract_tag(block, "TRNTYPE") or ""
        currency_tag = _extract_tag(block, "CURRENCY") or _extract_tag(block, "ORIGCURRENCY")
        currency = currency_tag.upper() if currency_tag else default_currency

        description = name or memo or fitid
        type_hint = _TRNTYPE_MAP.get(trntype.upper())

        results.append(
            ParsedTransaction(
                external_id=fitid,
                amount=amount,
                currency=currency,
                direction=direction,
                posted_date=posted_date,
                occurred_at=posted_date,
                description=description,
                merchant_name=name or None,
                transaction_type_hint=type_hint,
            )
        )

    return results
