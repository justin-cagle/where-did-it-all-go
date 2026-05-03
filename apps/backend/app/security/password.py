"""Password hashing via argon2-cffi (through passlib's CryptContext).

Never roll custom password hashing. argon2 is the winner of the Password
Hashing Competition and is the recommended algorithm for new systems.
"""

from passlib.context import CryptContext

_ctx = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plaintext password with argon2. Returns the encoded hash string."""
    return str(_ctx.hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored argon2 hash."""
    result: bool = _ctx.verify(plain, hashed)
    return result


def needs_rehash(hashed: str) -> bool:
    """Return True if the hash was produced with deprecated parameters."""
    result: bool = _ctx.needs_update(hashed)
    return result
