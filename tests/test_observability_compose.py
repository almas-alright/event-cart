from pathlib import Path

import yaml


def test_compose_includes_observability_services() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    services = compose["services"]

    for service_name in ["otel-collector", "prometheus", "grafana", "jaeger"]:
        assert service_name in services

    assert "4318:4318" in services["otel-collector"]["ports"]
    assert "9090:9090" in services["prometheus"]["ports"]
    assert "3000:3000" in services["grafana"]["ports"]
    assert "16686:16686" in services["jaeger"]["ports"]


def test_observability_config_files_are_valid_yaml() -> None:
    for path in [
        "observability/otel-collector.yml",
        "observability/prometheus.yml",
        "observability/grafana-datasources.yml",
    ]:
        assert yaml.safe_load(Path(path).read_text())
