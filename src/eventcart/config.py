"""Runtime configuration for EventCart."""

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from os import getenv


class EventTransport(StrEnum):
    NATS = "nats"
    POSTGRES = "postgres"


@dataclass(frozen=True)
class Settings:
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite+pysqlite:///./eventcart.db"
    redis_url: str = "redis://redis:6379/0"
    nats_url: str = "nats://nats:4222"
    event_transport: EventTransport = EventTransport.NATS
    service_name: str = "eventcart-api"
    otel_exporter_otlp_endpoint: str | None = None


@lru_cache
def get_settings() -> Settings:
    event_transport = EventTransport(
        getenv("EVENTCART_EVENT_TRANSPORT", Settings.event_transport)
    )
    return Settings(
        environment=getenv("EVENTCART_ENV", Settings.environment),
        log_level=getenv("EVENTCART_LOG_LEVEL", Settings.log_level),
        database_url=getenv("DATABASE_URL", Settings.database_url),
        redis_url=getenv("REDIS_URL", Settings.redis_url),
        nats_url=getenv("NATS_URL", Settings.nats_url),
        event_transport=event_transport,
        service_name=getenv("EVENTCART_SERVICE_NAME", Settings.service_name),
        otel_exporter_otlp_endpoint=getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
    )
