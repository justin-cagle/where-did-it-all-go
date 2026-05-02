"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import AnyUrl, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: PostgresDsn

    # Redis (worker queue + cache)
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")  # type: ignore[assignment]

    # Master key for field-level encryption of sensitive data.
    # Never logged. Loaded once at startup; rotatable via re-key procedure.
    # Key custody mode is configurable — see security.md.
    master_key: str

    # App
    debug: bool = False
    log_level: str = "INFO"
    allowed_origins: list[str] = ["http://localhost:5173"]

    # Observability — OpenTelemetry (optional; unset disables tracing)
    otel_exporter_otlp_endpoint: AnyUrl | None = None

    # Backup — local volume always; S3 is optional
    backup_s3_endpoint: str | None = None
    backup_s3_bucket: str | None = None
    backup_s3_access_key: str | None = None
    backup_s3_secret_key: str | None = None
    backup_encryption_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
