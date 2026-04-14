"""Tests for Docker config bootstrap helper."""

from pathlib import Path

from bootstrap_config import bootstrap_config, main


def test_bootstrap_config_creates_example_and_settings(tmp_path: Path) -> None:
    template = tmp_path / "settings.example.yaml"
    template.write_text("search:\n  results_wanted: 10\n", encoding="utf-8")

    settings_path = tmp_path / "config" / "settings.yaml"
    result = bootstrap_config(settings_path, template, write_settings=True)

    assert result.example_created is True
    assert result.settings_created is True
    assert result.example_path.read_text(encoding="utf-8") == template.read_text(
        encoding="utf-8"
    )
    assert settings_path.read_text(encoding="utf-8") == template.read_text(
        encoding="utf-8"
    )


def test_bootstrap_config_does_not_overwrite_existing_settings(tmp_path: Path) -> None:
    template = tmp_path / "settings.example.yaml"
    template.write_text("search:\n  results_wanted: 10\n", encoding="utf-8")

    settings_path = tmp_path / "config" / "settings.yaml"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("search:\n  results_wanted: 99\n", encoding="utf-8")

    result = bootstrap_config(settings_path, template, write_settings=True)

    assert result.settings_created is False
    assert (
        settings_path.read_text(encoding="utf-8")
        == "search:\n  results_wanted: 99\n"
    )


def test_bootstrap_main_returns_error_when_template_missing(tmp_path: Path) -> None:
    rc = main(
        [
            "--quiet",
            "--settings-path",
            str(tmp_path / "config" / "settings.yaml"),
            "--template-path",
            str(tmp_path / "missing.yaml"),
            "--write-settings",
        ]
    )

    assert rc == 1
