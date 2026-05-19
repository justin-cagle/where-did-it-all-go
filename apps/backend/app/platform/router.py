"""FastAPI routes for platform-level FX and currency endpoints.

Routes:
  GET /api/v1/currencies          -- list supported currencies (public, no auth)
  GET /api/v1/fx-rates            -- FX rate lookup (auth required)
"""

from datetime import date
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.platform.fx import FXRateUnavailableError, get_rate, get_supported_currencies

router = APIRouter(tags=["platform"])

_DbSession = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CurrencyOut(BaseModel):
    code: str
    name: str


class FXRateOut(BaseModel):
    from_currency: str
    to_currency: str
    date: date
    rate: str
    source: str
    is_approximate: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/currencies", response_model=list[CurrencyOut])
async def list_currencies(session: _DbSession) -> list[CurrencyOut]:
    """Return all currencies supported by the Frankfurter API.

    No auth required. Cached in Redis for 24 hours.
    """
    currencies = await get_supported_currencies(session)
    return [CurrencyOut(code=c["code"], name=c["name"]) for c in currencies]


@router.get("/fx-rates", response_model=FXRateOut)
async def get_fx_rate(
    session: _DbSession,
    from_currency: Annotated[str, Query(min_length=3, max_length=3)],
    to_currency: Annotated[str, Query(min_length=3, max_length=3)],
    rate_date: Annotated[date, Query(alias="date")],
) -> FXRateOut:
    """Look up an FX rate for a currency pair and date.

    Requires authentication. Stores the rate if fetched from Frankfurter.
    Returns is_approximate=true when using a fallback rate.
    """
    from_c = from_currency.upper()
    to_c = to_currency.upper()

    # Determine source from DB row if already cached
    source = "identity"
    is_approx = False
    rate_val = None

    if from_c == to_c:
        rate_val = "1.00000000"
    else:
        try:
            from app.platform.fx import FxRate

            existing = await session.execute(
                sa.select(FxRate).where(
                    FxRate.rate_date == rate_date,
                    FxRate.from_currency == from_c,
                    FxRate.to_currency == to_c,
                )
            )
            existing_row = existing.scalar_one_or_none()

            rate_decimal, is_approx = await get_rate(from_c, to_c, rate_date, session)
            rate_val = str(rate_decimal)

            if is_approx:
                source = "fallback"
            elif existing_row is not None:
                source = existing_row.source
            else:
                source = "frankfurter"

        except FXRateUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

    return FXRateOut(
        from_currency=from_c,
        to_currency=to_c,
        date=rate_date,
        rate=rate_val or "1.00000000",
        source=source,
        is_approximate=is_approx,
    )
