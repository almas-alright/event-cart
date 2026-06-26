"""OpenTelemetry tracing setup."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from eventcart.config import Settings


def setup_tracing(app: FastAPI, settings: Settings) -> bool:
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        app.state.tracing_enabled = False
        return False

    resource = Resource.create({"service.name": settings.service_name})
    provider = TracerProvider(resource=resource)
    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(
            endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces"
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    app.state.tracing_enabled = True
    return True


def tracer(name: str) -> Any:
    try:
        from opentelemetry import trace
    except ImportError:
        return _NoOpTracer()
    return trace.get_tracer(name)


class _NoOpTracer:
    def start_as_current_span(self, _name: str) -> Any:
        return _NoOpSpan()


class _NoOpSpan:
    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None
