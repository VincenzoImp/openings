"""Tests for Docker Compose deployment descriptors."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_all_runtime_services_mount_settings_yaml():
    """Every runtime role must receive the required settings.yaml bind mount."""
    compose = _load_yaml("docker-compose.yml")
    services = compose["services"]
    required = "./settings.yaml:/data/config/settings.yaml:ro"

    for name in ("scheduler", "web"):
        assert required in services[name]["volumes"], name


def test_runtime_services_use_installed_entrypoints():
    """Compose should exercise package entrypoints, not source-file paths."""
    compose = _load_yaml("docker-compose.yml")
    services = compose["services"]

    assert services["scheduler"]["command"] == ["job-search", "scheduler"]
    assert services["web"]["command"] == ["job-search-web"]


def test_docker_image_does_not_ship_legacy_command_wrappers():
    """The image should expose package entrypoints without root-level shims."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "docker/compat" not in dockerfile
    assert not list((ROOT / "docker" / "compat").glob("*.py"))


def test_published_ports_are_localhost_by_default():
    """Published ports should stay local unless the user opts into LAN exposure."""
    compose = _load_yaml("docker-compose.yml")
    services = compose["services"]

    assert services["web"]["ports"] == [
        "${JOB_SEARCH_WEB_BIND:-127.0.0.1}:${JOB_SEARCH_WEB_PORT:-8501}:8501"
    ]


def test_dev_override_covers_all_runtime_services():
    """Local rebuild override must apply to every runtime service."""
    override = _load_yaml("docker-compose.dev.yml")

    assert set(override["services"]) == {"scheduler", "web"}
