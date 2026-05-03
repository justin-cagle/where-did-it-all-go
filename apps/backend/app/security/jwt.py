"""JWT issuance and validation via joserfc.

Access tokens: HS256 JWT, 15-minute lifetime.
Claims:
  sub           — user UUID (str)
  jti           — unique token ID (UUID4)
  iat           — issued-at (int epoch seconds)
  exp           — expiry (int epoch seconds)
  household_id  — active household UUID (str) | None
  is_app_admin  — bool
  step_up_until — int epoch seconds | None (short-lived elevation for admin ops)
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from joserfc import jwt
from joserfc.errors import BadSignatureError
from joserfc.jwk import OctKey

_ACCESS_TOKEN_TTL = 900  # 15 minutes
_STEP_UP_TTL = 300  # 5 minutes


class InvalidTokenError(Exception):
    """Raised when a token cannot be validated."""


def _build_key(secret: str) -> OctKey:
    """Derive a 32-byte HMAC key from the secret string."""
    raw = hashlib.sha256(secret.encode()).digest()
    return OctKey.import_key(raw)


def _now_epoch() -> int:
    return int(datetime.now(tz=UTC).timestamp())


def issue_access_token(
    *,
    user_id: uuid.UUID,
    household_id: uuid.UUID | None,
    is_app_admin: bool,
    secret: str,
    ttl: int = _ACCESS_TOKEN_TTL,
    step_up: bool = False,
) -> str:
    """Issue a signed JWT access token string."""
    now = _now_epoch()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + ttl,
        "household_id": str(household_id) if household_id else None,
        "is_app_admin": is_app_admin,
    }
    if step_up:
        payload["step_up_until"] = now + _STEP_UP_TTL

    key = _build_key(secret)
    return jwt.encode({"alg": "HS256"}, payload, key)


def validate_access_token(token: str, secret: str) -> dict[str, Any]:
    """Validate and decode an access token.

    Returns the claims dict on success.
    Raises InvalidTokenError on expired, tampered, or malformed tokens.
    """
    key = _build_key(secret)
    try:
        token_obj = jwt.decode(token, key)
    except BadSignatureError as exc:
        raise InvalidTokenError("invalid token signature") from exc
    except Exception as exc:
        raise InvalidTokenError(f"token decode failed: {exc}") from exc

    claims: dict[str, Any] = dict(token_obj.claims)

    # joserfc does not auto-validate exp — check it explicitly
    exp = claims.get("exp")
    if exp is None or _now_epoch() > int(exp):
        raise InvalidTokenError("token expired")

    return claims


def has_step_up(claims: dict[str, Any]) -> bool:
    """Return True if the claims contain a valid (not expired) step-up grant."""
    step_up_until = claims.get("step_up_until")
    if step_up_until is None:
        return False
    return _now_epoch() < int(step_up_until)


def issue_step_up_token(
    *,
    user_id: uuid.UUID,
    household_id: uuid.UUID | None,
    is_app_admin: bool,
    secret: str,
) -> str:
    """Issue a new access token with the step_up_until claim set."""
    return issue_access_token(
        user_id=user_id,
        household_id=household_id,
        is_app_admin=is_app_admin,
        secret=secret,
        step_up=True,
    )


def token_expiry(claims: dict[str, Any]) -> datetime:
    """Extract the expiry time from validated claims."""
    return datetime.fromtimestamp(int(claims["exp"]), tz=UTC)


def timedelta_from_ttl(ttl: int) -> timedelta:
    """Convert a TTL in seconds to a timedelta."""
    return timedelta(seconds=ttl)
