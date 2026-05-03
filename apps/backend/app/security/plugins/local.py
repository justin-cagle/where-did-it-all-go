"""Local auth plugin — username + password + optional TOTP.

This plugin receives already-loaded credential data from the households
service layer (which owns the User model and DB access). It performs only
cryptographic verification — no DB calls.
"""

from app.security import hooks
from app.security import password as pwd_service
from app.security import totp as totp_service


class LocalAuthPlugin:
    """Pluggy implementation: authenticate against a stored argon2 hash."""

    @hooks.hookimpl
    def authenticate_local(
        self,
        username: str,
        password: str,
        stored_hash: str,
        totp_code: str | None,
        totp_secret: str | None,
        totp_enabled: bool,
    ) -> bool | None:
        """Verify password and optionally TOTP.

        Returns True if all provided credentials are valid, False if any fail.
        Returns None if stored_hash is empty (user has no local password set).
        """
        if not stored_hash:
            return None  # user has no local password; skip this plugin

        if not pwd_service.verify_password(password, stored_hash):
            return False

        if totp_enabled:
            if not totp_code:
                return False
            if not totp_secret:
                return False
            if not totp_service.verify_code(totp_secret, totp_code):
                return False

        return True
