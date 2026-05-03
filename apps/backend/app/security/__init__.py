"""Security module.

Owns: encryption key management (env_var / file / vault custody modes),
secret storage abstraction, privacy mode state.

Uses established, audited libraries only — never custom auth or crypto.
Libraries: cryptography, authlib, passlib/argon2-cffi.
"""

__all__: list[str] = []
