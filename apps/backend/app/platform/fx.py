"""FX rate model — daily rates, lazily populated.

A rate row is only inserted when an account or transaction in that currency
first appears (lazy population). No pre-populating all ISO currencies.

Use cases:
  - Current revaluation of foreign-currency balances.
  - Goal progress calculations across currencies.
  - Net worth rollup to household.home_currency.

Constraints:
  - Daily granularity only — no intraday rates.
  - One row per (rate_date, from_currency, to_currency) pair.
  - Higher numeric precision than monetary amounts (10 dp vs 4 dp).

For projections: foreign-currency amounts project flat by default
(no rate movement assumed). User-configurable per recurrence.
"""

from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import TimestampMixin, UUIDPrimaryKeyMixin
from app.platform.money import FX_RATE_TYPE


class FxRate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "platform_fx_rate"

    rate_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    from_currency: Mapped[str] = mapped_column(sa.String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(sa.String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(FX_RATE_TYPE, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint(
            "rate_date",
            "from_currency",
            "to_currency",
            name="uq_platform_fx_rate_date_pair",
        ),
        sa.Index("ix_platform_fx_rate_date", "rate_date"),
        sa.Index("ix_platform_fx_rate_currencies", "from_currency", "to_currency"),
    )

    def __repr__(self) -> str:
        return f"FxRate(date={self.rate_date}, {self.from_currency}/{self.to_currency}={self.rate})"
