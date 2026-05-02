"""Platform module — shared foundation for all domain modules.

Owns: money/Decimal handling, FX rate management, time abstractions, UUIDs,
common types. All domain modules may import from platform; platform may NOT
import from any domain module (enforced by import-linter).
"""

from app.platform.db import (
    EffectiveDatedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.platform.fx import FxRate
from app.platform.ids import new_uuid
from app.platform.money import (
    CURRENCY_TYPE,
    FX_RATE_TYPE,
    MONEY_TYPE,
    MoneyDecimal,
)
from app.platform.time import utcnow

__all__ = [
    "CURRENCY_TYPE",
    "FX_RATE_TYPE",
    "MONEY_TYPE",
    "EffectiveDatedMixin",
    "FxRate",
    "MoneyDecimal",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "new_uuid",
    "utcnow",
]
