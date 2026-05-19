"""FX rate model and service functions.

Rate rows are inserted lazily when a foreign-currency account or transaction
first appears. No pre-population of all ISO 4217 codes.

Rate lookup strategy (get_rate):
  1. Exact date in platform_fx_rate.
  2. Not found: fetch from Frankfurter, store, return (rate, False).
  3. Frankfurter unavailable: nearest prior rate within 30 days,
     return (rate, True) -- is_approximate=True.
  4. Still not found: raise FXRateUnavailableError.
  5. from_currency == to_currency: return (Decimal("1.0"), False) immediately.

Source enum values: "frankfurter" | "manual" | "fallback"
fx_rate_source on Transaction: above + "none" (home-currency transaction).
"""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import httpx
import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.platform.db import TimestampMixin, UUIDPrimaryKeyMixin
from app.platform.money import FX_RATE_TYPE

logger = structlog.get_logger(__name__)

_FRANKFURTER_BASE = "https://api.frankfurter.app"
_CURRENCIES_CACHE_KEY = "fx:currencies"
_CURRENCIES_TTL = 86_400  # 24 hours
_FALLBACK_LOOKBACK_DAYS = 30
_HTTP_TIMEOUT = 10.0


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class FxRate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "platform_fx_rate"

    rate_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    from_currency: Mapped[str] = mapped_column(sa.String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(sa.String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(FX_RATE_TYPE, nullable=False)
    source: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        default="frankfurter",
        server_default=sa.text("'frankfurter'"),
    )
    fetched_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=UTC),
        server_default=sa.text("NOW()"),
    )

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


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FXRateUnavailableError(Exception):
    """No rate available for the requested pair and date."""


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def get_rate(
    from_currency: str,
    to_currency: str,
    rate_date: date,
    session: AsyncSession,
) -> tuple[Decimal, bool]:
    """Return (rate, is_approximate).

    is_approximate=True when falling back to nearest prior stored rate.
    """
    from_c = from_currency.upper()
    to_c = to_currency.upper()

    if from_c == to_c:
        return Decimal("1.0"), False

    # 1. Exact date in DB
    exact = await _db_exact(session, from_c, to_c, rate_date)
    if exact is not None:
        return exact.rate, False

    # 2. Fetch from Frankfurter
    fetched = await _fetch_frankfurter_rate(from_c, to_c, rate_date)
    if fetched is not None:
        await _upsert_rate(session, from_c, to_c, rate_date, fetched, "frankfurter")
        return fetched, False

    # 3. Nearest prior stored rate (up to 30 days back)
    fallback = await _db_nearest_prior(session, from_c, to_c, rate_date)
    if fallback is not None:
        return fallback.rate, True

    raise FXRateUnavailableError(f"no FX rate available for {from_c}/{to_c} on {rate_date}")


async def convert(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    rate_date: date,
    session: AsyncSession,
) -> tuple[Decimal, bool]:
    """Return (converted_amount, is_approximate).

    Returns (amount, False) when currencies match.
    Rounds result to 4 decimal places (NUMERIC(19,4) precision).
    """
    from_c = from_currency.upper()
    to_c = to_currency.upper()

    if from_c == to_c:
        return amount, False

    rate, is_approx = await get_rate(from_c, to_c, rate_date, session)
    converted = (amount * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return converted, is_approx


async def fetch_and_store_rates(
    base_currency: str,
    target_currencies: list[str],
    rate_date: date,
    session: AsyncSession,
) -> None:
    """Fetch rates from Frankfurter and upsert to DB.

    Never raises -- logs failures and returns.
    """
    base = base_currency.upper()
    targets = [c.upper() for c in target_currencies if c.upper() != base]
    if not targets:
        return

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            date_str = rate_date.isoformat()
            url = f"{_FRANKFURTER_BASE}/{date_str}"
            resp = await client.get(url, params={"from": base})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "fx.fetch_and_store_rates.failed",
            base=base,
            date=str(rate_date),
            error=str(exc),
        )
        return

    rates_map: dict[str, object] = data.get("rates", {})
    for target in targets:
        if target not in rates_map:
            logger.warning(
                "fx.rate_not_in_response",
                base=base,
                target=target,
                date=str(rate_date),
            )
            continue
        try:
            rate_val = Decimal(str(rates_map[target]))
            await _upsert_rate(session, base, target, rate_date, rate_val, "frankfurter")
        except Exception as exc:
            logger.warning(
                "fx.upsert_failed",
                base=base,
                target=target,
                error=str(exc),
            )


async def get_supported_currencies(_session: AsyncSession) -> list[dict[str, str]]:
    """Return [{code, name}] from Redis cache or Frankfurter /currencies.

    Cached in Redis for 24 hours.
    """
    from app.config import get_settings

    redis_url = str(get_settings().redis_url)

    try:
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        r = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[reportUnknownMemberType]
        cached = await r.get(_CURRENCIES_CACHE_KEY)
        await r.aclose()
        if cached:
            return json.loads(cached)  # type: ignore[no-any-return]
    except Exception:  # noqa: S110
        pass

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(f"{_FRANKFURTER_BASE}/currencies")
            resp.raise_for_status()
            raw: dict[str, str] = resp.json()
        currencies = [{"code": code, "name": name} for code, name in sorted(raw.items())]
    except Exception as exc:
        logger.warning("fx.get_supported_currencies.failed", error=str(exc))
        return []

    try:
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        r = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[reportUnknownMemberType]
        await r.setex(_CURRENCIES_CACHE_KEY, _CURRENCIES_TTL, json.dumps(currencies))
        await r.aclose()
    except Exception:  # noqa: S110
        pass

    return currencies


def is_supported_currency(code: str) -> bool:
    """Synchronous check against Redis-cached currency list.

    Returns False when cache unavailable -- callers should not block on this.
    """
    from app.config import get_settings

    try:
        import redis  # type: ignore[import-untyped]

        r = redis.from_url(str(get_settings().redis_url), decode_responses=True)  # type: ignore[reportUnknownMemberType]
        cached = r.get(_CURRENCIES_CACHE_KEY)
        r.close()
        if cached:
            currencies: list[dict[str, str]] = json.loads(cached)  # type: ignore[arg-type]
            codes = {c["code"] for c in currencies}
            return code.upper() in codes
    except Exception:  # noqa: S110
        pass
    return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _db_exact(
    session: AsyncSession,
    from_c: str,
    to_c: str,
    rate_date: date,
) -> FxRate | None:
    result = await session.execute(
        sa.select(FxRate).where(
            FxRate.rate_date == rate_date,
            FxRate.from_currency == from_c,
            FxRate.to_currency == to_c,
        )
    )
    return result.scalar_one_or_none()


async def _db_nearest_prior(
    session: AsyncSession,
    from_c: str,
    to_c: str,
    rate_date: date,
) -> FxRate | None:
    cutoff = rate_date - timedelta(days=_FALLBACK_LOOKBACK_DAYS)
    result = await session.execute(
        sa.select(FxRate)
        .where(
            FxRate.from_currency == from_c,
            FxRate.to_currency == to_c,
            FxRate.rate_date < rate_date,
            FxRate.rate_date >= cutoff,
        )
        .order_by(FxRate.rate_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _fetch_frankfurter_rate(from_c: str, to_c: str, rate_date: date) -> Decimal | None:
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            url = f"{_FRANKFURTER_BASE}/{rate_date.isoformat()}"
            resp = await client.get(url, params={"from": from_c, "to": to_c})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            rates: dict[str, object] = data.get("rates", {})
            if to_c not in rates:
                return None
            return Decimal(str(rates[to_c]))
    except Exception as exc:
        logger.warning(
            "fx.frankfurter_fetch.failed",
            from_c=from_c,
            to_c=to_c,
            date=str(rate_date),
            error=str(exc),
        )
        return None


async def _upsert_rate(
    session: AsyncSession,
    from_c: str,
    to_c: str,
    rate_date: date,
    rate_val: Decimal,
    source: str,
) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    now = datetime.now(tz=UTC)
    stmt = (
        pg_insert(FxRate)
        .values(
            rate_date=rate_date,
            from_currency=from_c,
            to_currency=to_c,
            rate=rate_val,
            source=source,
            fetched_at=now,
        )
        .on_conflict_do_update(
            index_elements=["rate_date", "from_currency", "to_currency"],
            set_={"rate": rate_val, "source": source, "fetched_at": now},
        )
    )
    await session.execute(stmt)
