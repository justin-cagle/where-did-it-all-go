"""Shared ARQ worker configuration."""

from arq.connections import RedisSettings

from app.config import get_settings


def get_redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(str(settings.redis_url))
