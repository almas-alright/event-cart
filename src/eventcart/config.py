"""Runtime configuration for EventCart."""

from dataclasses import dataclass
from functools import lru_cache
from os import getenv


@dataclass(frozen=True)
class Settings:
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite+pysqlite:///./eventcart.db"
    redis_url: str = "redis://redis:6379/0"
    nats_url: str = "nats://nats:4222"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        environment=getenv("EVENTCART_ENV", Settings.environment),
        log_level=getenv("EVENTCART_LOG_LEVEL", Settings.log_level),
        database_url=getenv("DATABASE_URL", Settings.database_url),
        redis_url=getenv("REDIS_URL", Settings.redis_url),
        nats_url=getenv("NATS_URL", Settings.nats_url),
    )
