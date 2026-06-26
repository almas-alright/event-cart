import pytest

from eventcart.config import EventTransport, get_settings


def test_event_transport_defaults_to_nats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVENTCART_EVENT_TRANSPORT", raising=False)
    get_settings.cache_clear()

    try:
        assert get_settings().event_transport == EventTransport.NATS
    finally:
        get_settings.cache_clear()


def test_event_transport_can_select_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENTCART_EVENT_TRANSPORT", "postgres")
    get_settings.cache_clear()

    try:
        assert get_settings().event_transport == EventTransport.POSTGRES
    finally:
        get_settings.cache_clear()


def test_event_transport_rejects_invalid_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVENTCART_EVENT_TRANSPORT", "kafka")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError):
            get_settings()
    finally:
        get_settings.cache_clear()
