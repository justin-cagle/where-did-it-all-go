"""Unit tests for app.security — pure functions, no DB required.

Coverage targets:
  - password.py: hash, verify, needs_rehash
  - totp.py:     generate_secret, verify_code, provisioning_uri
  - jwt.py:      issue_access_token, validate_access_token, has_step_up

Hypothesis property tests:
  - JWT round-trip (issue → validate, any valid UUID pair)
  - Password hash round-trip (hash → verify always True)
  - Incorrect password never verifies
"""

import uuid
from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.security import jwt as jwt_service
from app.security import password as pwd_service
from app.security import totp as totp_service
from app.security.jwt import InvalidTokenError

_SECRET = "test-jwt-secret-not-for-production"  # pragma: allowlist secret

# ---------------------------------------------------------------------------
# Password tests
# ---------------------------------------------------------------------------


def test_hash_password_returns_string() -> None:
    h = pwd_service.hash_password("s3cr3t!")
    assert isinstance(h, str)
    assert h.startswith("$argon2")


def test_hash_password_different_each_call() -> None:
    pw = "same-password"
    assert pwd_service.hash_password(pw) != pwd_service.hash_password(pw)


def test_verify_password_correct() -> None:
    h = pwd_service.hash_password("hunter2")
    assert pwd_service.verify_password("hunter2", h) is True


def test_verify_password_wrong() -> None:
    h = pwd_service.hash_password("hunter2")
    assert pwd_service.verify_password("wrong", h) is False


def test_needs_rehash_fresh_hash_is_false() -> None:
    h = pwd_service.hash_password("pw")
    assert pwd_service.needs_rehash(h) is False


@given(st.text(min_size=1, max_size=72))
@settings(max_examples=50)
def test_password_hash_round_trip(plain: str) -> None:
    """hash → verify always returns True for the same password."""
    h = pwd_service.hash_password(plain)
    assert pwd_service.verify_password(plain, h) is True


@given(st.text(min_size=1, max_size=72), st.text(min_size=1, max_size=72))
@settings(max_examples=50)
def test_different_passwords_do_not_verify(p1: str, p2: str) -> None:
    """Two different passwords must not cross-verify (except by collision)."""
    if p1 == p2:
        return  # not a useful test case
    h = pwd_service.hash_password(p1)
    assert pwd_service.verify_password(p2, h) is False


# ---------------------------------------------------------------------------
# TOTP tests
# ---------------------------------------------------------------------------


def test_generate_secret_is_base32_string() -> None:
    s = totp_service.generate_secret()
    assert isinstance(s, str)
    assert len(s) >= 16


def test_verify_code_valid() -> None:
    import pyotp  # type: ignore[import-untyped]

    secret = totp_service.generate_secret()
    current_code = pyotp.TOTP(secret).now()
    assert totp_service.verify_code(secret, current_code) is True


def test_verify_code_invalid() -> None:
    secret = totp_service.generate_secret()
    assert totp_service.verify_code(secret, "000000") is False


def test_provisioning_uri_format() -> None:
    secret = totp_service.generate_secret()
    uri = totp_service.provisioning_uri(secret, "user@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "user%40example.com" in uri or "user@example.com" in uri


# ---------------------------------------------------------------------------
# JWT tests
# ---------------------------------------------------------------------------


def test_issue_access_token_returns_string() -> None:
    token = jwt_service.issue_access_token(
        user_id=uuid.uuid4(),
        household_id=None,
        is_app_admin=False,
        secret=_SECRET,
    )
    assert isinstance(token, str)
    assert token.count(".") == 2  # header.payload.signature


def test_validate_access_token_round_trip() -> None:
    uid = uuid.uuid4()
    hid = uuid.uuid4()
    token = jwt_service.issue_access_token(
        user_id=uid,
        household_id=hid,
        is_app_admin=True,
        secret=_SECRET,
    )
    claims = jwt_service.validate_access_token(token, _SECRET)
    assert claims["sub"] == str(uid)
    assert claims["household_id"] == str(hid)
    assert claims["is_app_admin"] is True


def test_validate_access_token_null_household() -> None:
    token = jwt_service.issue_access_token(
        user_id=uuid.uuid4(),
        household_id=None,
        is_app_admin=False,
        secret=_SECRET,
    )
    claims = jwt_service.validate_access_token(token, _SECRET)
    assert claims["household_id"] is None


def test_validate_wrong_secret_raises() -> None:
    token = jwt_service.issue_access_token(
        user_id=uuid.uuid4(),
        household_id=None,
        is_app_admin=False,
        secret=_SECRET,
    )
    with pytest.raises(InvalidTokenError):
        jwt_service.validate_access_token(token, "wrong-secret")


def test_validate_tampered_token_raises() -> None:
    token = jwt_service.issue_access_token(
        user_id=uuid.uuid4(),
        household_id=None,
        is_app_admin=False,
        secret=_SECRET,
    )
    # Flip the last character of the signature
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(InvalidTokenError):
        jwt_service.validate_access_token(tampered, _SECRET)


def test_validate_expired_token_raises() -> None:
    uid = uuid.uuid4()
    token = jwt_service.issue_access_token(
        user_id=uid,
        household_id=None,
        is_app_admin=False,
        secret=_SECRET,
        ttl=-1,  # already expired
    )
    with pytest.raises(InvalidTokenError):
        jwt_service.validate_access_token(token, _SECRET)


def test_has_step_up_false_by_default() -> None:
    token = jwt_service.issue_access_token(
        user_id=uuid.uuid4(),
        household_id=None,
        is_app_admin=False,
        secret=_SECRET,
    )
    claims = jwt_service.validate_access_token(token, _SECRET)
    assert jwt_service.has_step_up(claims) is False


def test_has_step_up_true_when_granted() -> None:
    uid = uuid.uuid4()
    token = jwt_service.issue_step_up_token(
        user_id=uid,
        household_id=None,
        is_app_admin=True,
        secret=_SECRET,
    )
    claims = jwt_service.validate_access_token(token, _SECRET)
    assert jwt_service.has_step_up(claims) is True


def test_token_expiry_returns_future_datetime() -> None:
    token = jwt_service.issue_access_token(
        user_id=uuid.uuid4(),
        household_id=None,
        is_app_admin=False,
        secret=_SECRET,
    )
    claims = jwt_service.validate_access_token(token, _SECRET)
    expiry = jwt_service.token_expiry(claims)
    assert expiry > datetime.now(tz=UTC)


@given(
    user_id=st.uuids(),
    household_id=st.one_of(st.none(), st.uuids()),
    is_app_admin=st.booleans(),
)
@settings(max_examples=50)
def test_jwt_round_trip_property(
    user_id: uuid.UUID,
    household_id: uuid.UUID | None,
    is_app_admin: bool,
) -> None:
    """issue → validate always recovers the original claims."""
    token = jwt_service.issue_access_token(
        user_id=user_id,
        household_id=household_id,
        is_app_admin=is_app_admin,
        secret=_SECRET,
    )
    claims = jwt_service.validate_access_token(token, _SECRET)
    assert claims["sub"] == str(user_id)
    assert claims["is_app_admin"] == is_app_admin
    if household_id is None:
        assert claims["household_id"] is None
    else:
        assert claims["household_id"] == str(household_id)


# ---------------------------------------------------------------------------
# Idle timeout sliding window (pure logic test — no DB)
# ---------------------------------------------------------------------------


def test_timedelta_from_ttl() -> None:
    from datetime import timedelta

    assert jwt_service.timedelta_from_ttl(1800) == timedelta(seconds=1800)
