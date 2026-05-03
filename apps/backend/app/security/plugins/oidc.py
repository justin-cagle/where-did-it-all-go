"""OIDC auth plugin stub.

This plugin is a reference stub for external IdP authentication (Keycloak,
Authentik, etc.). It always returns None (skip), deferring to the local
auth plugin. A real implementation would validate the OIDC callback and
issue app tokens.
"""

from app.security import hooks


class OidcAuthPlugin:
    """Pluggy implementation: OIDC flow (stub — always skips)."""

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
        """Not implemented: OIDC uses a redirect flow, not a credential check."""
        return None
