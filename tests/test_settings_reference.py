"""Tests for generated settings reference documentation."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_settings_reference_uses_current_example_defaults():
    from job_search_tool.settings_reference import get_settings_reference

    text = get_settings_reference()
    assert "hours_old: 720" in text
    assert "country_indeed:" in text
    assert "max_workers: 3" in text
    assert "rate_limit_cooldown: 60.0" in text
    assert "max_jobs_in_message: 20" in text


def test_bundled_settings_template_matches_root_template():
    root_template = (ROOT / "config" / "settings.example.yaml").read_text(
        encoding="utf-8"
    )
    bundled_template = (
        resources.files("job_search_tool.defaults")
        .joinpath("settings.example.yaml")
        .read_text(encoding="utf-8")
    )

    assert bundled_template == root_template
