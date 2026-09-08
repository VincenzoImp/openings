"""Tests for generated settings reference documentation."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_settings_reference_uses_current_example_defaults():
    from openings.settings_reference import get_settings_reference

    text = get_settings_reference()
    assert "hours_old: 72" in text
    assert "country_indeed:" in text
    assert "max_workers: 3" in text
    assert "interval_hours: 12" in text
    assert "max_jobs: 20" in text


def test_bundled_settings_template_matches_root_template():
    root_template = (ROOT / "config" / "settings.example.yaml").read_text(encoding="utf-8")
    bundled_template = (
        resources.files("openings.defaults")
        .joinpath("settings.example.yaml")
        .read_text(encoding="utf-8")
    )

    assert bundled_template == root_template
