"""Money/Decimal types and SQLAlchemy column type constants.

Rules (DECISIONS.md R6):
  - NUMERIC(19, 4) for every monetary amount column.
  - Every money column has a sibling CHAR(3) currency column — no exceptions.
  - decimal.Decimal everywhere in Python. Never float for money.
  - MoneyDecimal rejects floats at Pydantic API boundaries.

Usage in SQLAlchemy models:
    amount:   Mapped[Decimal]  = mapped_column(MONEY_TYPE, nullable=False)
    currency: Mapped[str]      = mapped_column(CURRENCY_TYPE, nullable=False)

Usage in Pydantic schemas:
    amount: MoneyDecimal  # rejects float at API ingress
"""

from decimal import Decimal, InvalidOperation
from typing import Annotated

import sqlalchemy as sa
from pydantic.functional_validators import BeforeValidator

# ---------------------------------------------------------------------------
# SQLAlchemy column type constants
# ---------------------------------------------------------------------------

MONEY_TYPE = sa.Numeric(precision=19, scale=4, asdecimal=True)
"""NUMERIC(19,4) — use for every monetary amount column."""

CURRENCY_TYPE = sa.String(3)
"""CHAR(3) — ISO 4217 currency code. Paired with every MONEY_TYPE column."""

FX_RATE_TYPE = sa.Numeric(precision=19, scale=10, asdecimal=True)
"""NUMERIC(19,10) — higher precision for FX rates (e.g. 1.0874123456 USD/EUR)."""

# ---------------------------------------------------------------------------
# Pydantic validator — rejects floats at API boundaries
# ---------------------------------------------------------------------------


def _reject_float_money(v: object) -> object:
    """Reject float values for monetary fields before Pydantic coercion.

    Floats cannot represent monetary amounts exactly (0.1 + 0.2 ≠ 0.3 in IEEE 754).
    API callers must send Decimal-compatible values: numeric strings or JSON numbers
    without a fractional component that exceeds Decimal precision.
    """
    if isinstance(v, float):
        raise ValueError(
            "float is not permitted for monetary amounts — "
            'send a string ("12.34") or an integer instead'
        )
    if isinstance(v, str):
        try:
            Decimal(v)
        except InvalidOperation as exc:
            raise ValueError(f"Cannot parse {v!r} as a monetary amount") from exc
    return v


MoneyDecimal = Annotated[Decimal, BeforeValidator(_reject_float_money)]
"""Pydantic type for monetary fields. Accepts Decimal, str, int; rejects float.

Scale enforcement: MoneyDecimal does NOT quantize to 4dp at the Pydantic layer.
Decimal("1.12345") passes validation unchanged.  Scale is enforced at the DB
layer by NUMERIC(19,4) — SQLAlchemy / Postgres truncates or rounds on write.
Tests that verify scale behavior must go through a real DB write or must call
quantize() explicitly.
"""
