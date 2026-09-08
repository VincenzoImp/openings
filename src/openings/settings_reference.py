"""The settings reference served to MCP clients, generated from the template."""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = ROOT_DIR / "config" / "settings.example.yaml"
BUNDLED_TEMPLATE = "settings.example.yaml"


def get_settings_template_path() -> Path:
    configured = os.environ.get("OPENINGS_TEMPLATE_PATH")
    return Path(configured) if configured else DEFAULT_TEMPLATE


def read_settings_template() -> str:
    """The template from the env override, the checkout, or the package data."""
    template_path = get_settings_template_path()
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return (
        resources.files("openings.defaults").joinpath(BUNDLED_TEMPLATE).read_text(encoding="utf-8")
    )


def get_settings_reference() -> str:
    template = read_settings_template()
    return (
        "# settings.yaml reference\n\n"
        "Generated from the bundled `config/settings.example.yaml`, the canonical "
        "list of supported keys and defaults.\n\n"
        "```yaml\n"
        f"{template.rstrip()}\n"
        "```\n"
    )
