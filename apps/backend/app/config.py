"""Application settings loaded from environment variables."""

import hashlib
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Self

from pydantic import AnyUrl, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    _PACKAGE_VERSION: str = _pkg_version("wdiag-backend")
except PackageNotFoundError:
    _PACKAGE_VERSION = "0.0.0-dev"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    # Database
    database_url: PostgresDsn

    # Redis (worker queue + cache)
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")  # type: ignore[assignment]

    # Master key for field-level encryption of sensitive data.
    # Never logged. Loaded once at startup; rotatable via re-key procedure.
    # Key custody mode is configurable — see security.md.
    master_key: str

    # JWT signing secret. If not set, derived from master_key via SHA-256
    # with domain separation ("wdiag:jwt:<master_key>"). Set JWT_SECRET
    # explicitly in production to maintain key separation.
    jwt_secret: str = ""

    # App
    debug: bool = False
    log_level: str = "INFO"
    allowed_origins: list[str] = ["http://localhost:5173"]

    # Observability — OpenTelemetry (optional; unset disables tracing)
    otel_exporter_otlp_endpoint: AnyUrl | None = None

    # Bootstrap — read once at startup, never stored or logged
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    # Registration control
    allow_registration: bool = False
    registration_limit: int | None = None
    unassigned_account_ttl_days: int = 7

    # App base URL — used to construct invite links
    app_base_url: str = "http://localhost:5173"

    # SMTP — all optional; SMTP is considered configured when smtp_host +
    # smtp_from_address are both set.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str | None = None
    smtp_use_tls: bool = True

    # Backup — local volume always; S3 is additional optional destination
    backup_s3_endpoint: str | None = None
    backup_s3_bucket: str | None = None
    backup_s3_access_key: str | None = None
    backup_s3_secret_key: str | None = None
    backup_encryption_key: str | None = None

    # AIO — set by entrypoint.sh; signals demo-mode banner on login page
    aio_mode: bool = False

    # Version — from package metadata (pyproject.toml); overridable via APP_VERSION env var
    app_version: str = _PACKAGE_VERSION

    @model_validator(mode="after")
    def _derive_jwt_secret(self) -> Self:
        """Derive JWT secret from master_key if not explicitly set."""
        if not self.jwt_secret:
            self.jwt_secret = hashlib.sha256(f"wdiag:jwt:{self.master_key}".encode()).hexdigest()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def smtp_configured() -> bool:
    """Return True when SMTP is minimally configured (host + from_address set)."""
    s = get_settings()
    return bool(s.smtp_host and s.smtp_from_address)
