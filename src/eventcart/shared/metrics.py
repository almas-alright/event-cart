"""Prometheus metrics helpers."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

REQUEST_COUNTER = Counter(
    "eventcart_http_requests_total",
    "Total HTTP requests handled by EventCart.",
    ["method", "path", "status_code"],
)


def record_http_request(*, method: str, path: str, status_code: int) -> None:
    REQUEST_COUNTER.labels(
        method=method,
        path=path,
        status_code=str(status_code),
    ).inc()


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
