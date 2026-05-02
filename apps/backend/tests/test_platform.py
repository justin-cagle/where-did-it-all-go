"""Unit tests for app.platform — pure functions, no DB connection required."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.platform.ids import new_uuid
from app.platform.money import MoneyDecimal, _reject_float_money
from app.platform.time import utcnow


def test_new_uuid_returns_uuid() -> None:
    assert isinstance(new_uuid(), uuid.UUID)


def test_new_uuid_is_unique() -> None:
    assert new_uuid() != new_uuid()


def test_utcnow_returns_aware_datetime() -> None:
    result = utcnow()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
    assert result.tzinfo == UTC


def test_reject_float_money_raises_on_float() -> None:
    with pytest.raises(ValueError, match="float is not permitted"):
        _reject_float_money(1.23)


def test_reject_float_money_accepts_decimal() -> None:
    assert _reject_float_money(Decimal("1.23")) == Decimal("1.23")


def test_reject_float_money_accepts_int() -> None:
    assert _reject_float_money(100) == 100


def test_reject_float_money_accepts_valid_string() -> None:
    assert _reject_float_money("19.99") == "19.99"


def test_reject_float_money_rejects_invalid_string() -> None:
    with pytest.raises(ValueError, match="Cannot parse"):
        _reject_float_money("not-a-number")


def test_money_decimal_annotation_rejects_float() -> None:
    from pydantic import BaseModel, ValidationError

    class M(BaseModel):
        amount: MoneyDecimal

    with pytest.raises(ValidationError):
        M(amount=1.5)  # type: ignore[arg-type]


def test_money_decimal_annotation_accepts_string() -> None:
    from pydantic import BaseModel

    class M(BaseModel):
        amount: MoneyDecimal

    m = M(amount="42.50")  # type: ignore[arg-type]
    assert m.amount == Decimal("42.50")
