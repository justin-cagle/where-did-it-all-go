"""Pluggy hook specifications and plugin manager for auth providers.

Auth is the first committed plugin contract (see DECISIONS.md R5, domain-households.md).

Hook:
    authenticate_local — verify username+password+TOTP using stored credentials.
        firstresult=True: the first plugin returning non-None result wins.
        Returns True (authenticated), False (credentials wrong), or None (skip).

Usage:
    from app.security.hooks import get_plugin_manager
    pm = get_plugin_manager()
    ok = pm.hook.authenticate_local(
        username=email,
        password=plain_password,
        stored_hash=user.password_hash,
        totp_code=totp_code,
        totp_secret=user.totp_secret,
        totp_enabled=user.totp_enabled,
    )
"""

import pluggy

hookspec = pluggy.HookspecMarker("wdiag")
hookimpl = pluggy.HookimplMarker("wdiag")


class AuthSpec:
    """Pluggy hook specifications for the auth subsystem."""

    @hookspec(firstresult=True)
    def authenticate_local(
        self,
        username: str,
        password: str,
        stored_hash: str,
        totp_code: str | None,
        totp_secret: str | None,
        totp_enabled: bool,
    ) -> bool | None:
        """Attempt local (username+password+TOTP) authentication.

        Return True if credentials are valid, False if credentials are
        recognisably wrong (wrong password/TOTP), None to pass to the next
        plugin.
        """


def _build_plugin_manager() -> pluggy.PluginManager:
    # Deferred imports break the circular reference:
    # plugins/local.py imports hooks.hookimpl, so hooks.py must not import
    # plugins at module level.
    from app.security.plugins import local, oidc

    pm = pluggy.PluginManager("wdiag")
    pm.add_hookspecs(AuthSpec)
    pm.register(local.LocalAuthPlugin())
    pm.register(oidc.OidcAuthPlugin())
    return pm


_pm: pluggy.PluginManager | None = None


def get_plugin_manager() -> pluggy.PluginManager:
    """Return the singleton plugin manager (lazily initialised)."""
    global _pm
    if _pm is None:
        _pm = _build_plugin_manager()
    return _pm
