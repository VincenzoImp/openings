"""Generate settings.yaml reference text from the canonical template."""

from __future__ import annotations

import os
from pathlib import Path
from importlib import resources


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE = ROOT_DIR / "config" / "settings.example.yaml"
BUNDLED_TEMPLATE = "settings.example.yaml"


def get_settings_template_path() -> Path:
    """Return the filesystem settings template path when one is available."""
    configured = os.environ.get("JOB_SEARCH_TEMPLATE_PATH")
    if configured:
        return Path(configured)
    return DEFAULT_TEMPLATE


def _read_settings_template() -> str:
    """Read the canonical settings template from env, checkout, or package data."""
    template_path = get_settings_template_path()
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")

    return (
        resources.files("job_search_tool.defaults")
        .joinpath(BUNDLED_TEMPLATE)
        .read_text(encoding="utf-8")
    )


def get_settings_reference() -> str:
    """Return settings reference documentation generated from the template."""
    template = _read_settings_template()
    return (
        "# settings.yaml Reference\n\n"
        "The following reference is generated from the bundled "
        "`config/settings.example.yaml` template, which is the canonical "
        "source for supported fields and defaults.\n\n"
        "```yaml\n"
        f"{template.rstrip()}\n"
        "```\n"
    )
