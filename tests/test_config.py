from pathlib import Path

import pytest
import yaml

from openings.config import ConfigError, load_config, parse_config
from tests.conftest import EXAMPLE_SETTINGS, minimal_settings


def test_example_settings_parse_with_documented_defaults():
    config = parse_config(yaml.safe_load(EXAMPLE_SETTINGS.read_text()))
    assert config.sources.jobspy.sites == ["linkedin"]
    assert config.sources.jobspy.locations == ["Remote"]
    assert config.scoring.notify_threshold == 20
    assert config.scheduler.interval_hours == 12
    assert config.retention.max_age_days == 30
    assert config.attachments.max_size_mb == 20
    assert config.notifications.enabled is False


def test_packaged_template_matches_reference():
    packaged = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "openings"
        / "defaults"
        / "settings.example.yaml"
    )
    assert packaged.read_text() == EXAMPLE_SETTINGS.read_text()


def test_unknown_top_level_key_fails():
    data = minimal_settings()
    data["search"] = {}
    with pytest.raises(ConfigError, match="Unsupported configuration key: search"):
        parse_config(data)


def test_unknown_nested_key_fails_with_path():
    data = minimal_settings()
    data["sources"]["jobspy"]["hours"] = 3
    with pytest.raises(ConfigError, match="sources.jobspy.hours"):
        parse_config(data)


def test_notify_threshold_below_save_threshold_fails():
    data = minimal_settings()
    data["scoring"]["save_threshold"] = 30
    with pytest.raises(ConfigError, match="notify_threshold"):
        parse_config(data)


def test_keyword_category_without_weight_fails():
    data = minimal_settings()
    data["scoring"]["keywords"]["orphan"] = ["x"]
    with pytest.raises(ConfigError, match="orphan"):
        parse_config(data)


def test_keywords_are_lower_cased():
    data = minimal_settings()
    data["scoring"]["keywords"]["role"] = ["Software Engineer"]
    assert parse_config(data).scoring.keywords["role"] == ["software engineer"]


def test_all_queries_deduplicates_across_categories():
    data = minimal_settings()
    data["sources"]["jobspy"]["queries"] = {"a": ["x", "y"], "b": ["y", "z"]}
    assert parse_config(data).sources.jobspy.all_queries == ["x", "y", "z"]


def test_company_requires_known_ats_and_unique_slug():
    data = minimal_settings()
    data["sources"]["companies"] = [{"name": "A", "ats": "workday", "slug": "a"}]
    with pytest.raises(ConfigError, match="ats must be one of"):
        parse_config(data)
    data["sources"]["companies"] = [
        {"name": "A", "ats": "greenhouse", "slug": "a"},
        {"name": "B", "ats": "greenhouse", "slug": "A"},
    ]
    with pytest.raises(ConfigError, match="duplicates"):
        parse_config(data)


def test_company_parses_locations():
    data = minimal_settings()
    data["sources"]["companies"] = [
        {"name": "A", "ats": "Lever", "slug": "acme", "locations": ["Berlin", " Remote "]}
    ]
    company = parse_config(data).sources.companies[0]
    assert company.ats == "lever"
    assert company.locations == ["Berlin", "Remote"]


def test_feed_requires_http_url():
    data = minimal_settings()
    data["sources"]["feeds"] = [{"name": "x", "url": "ftp://nope"}]
    with pytest.raises(ConfigError, match="http"):
        parse_config(data)


def test_adzuna_enabled_requires_country_queries_and_keys(monkeypatch):
    data = minimal_settings()
    data["sources"]["adzuna"] = {"enabled": True, "country": "de", "queries": ["dev"]}
    with pytest.raises(ConfigError, match="app_id"):
        parse_config(data)
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    data["sources"]["adzuna"].update({"app_id": "$ADZUNA_APP_ID", "app_key": "$ADZUNA_APP_KEY"})
    adzuna = parse_config(data).sources.adzuna
    assert adzuna.app_id == "id" and adzuna.app_key == "key"


def test_secrets_resolve_from_environment(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    data = minimal_settings()
    data["notifications"] = {
        "enabled": True,
        "telegram": {"enabled": True, "bot_token": "$TELEGRAM_BOT_TOKEN", "chat_ids": [42]},
    }
    telegram = parse_config(data).notifications.telegram
    assert telegram.bot_token == "123:abc"
    assert telegram.chat_ids == ["42"]


def test_jobs_per_chunk_capped_at_fifteen():
    data = minimal_settings()
    data["notifications"] = {"telegram": {"jobs_per_chunk": 16}}
    with pytest.raises(ConfigError, match="at most 15"):
        parse_config(data)


def test_invalid_timezone_fails():
    data = minimal_settings()
    data["logging"] = {"timezone": "Mars/Olympus"}
    with pytest.raises(ConfigError, match="timezone"):
        parse_config(data)


def test_paths_derive_from_data_dir(tmp_path):
    config = parse_config(minimal_settings(), data_dir=tmp_path)
    assert config.database_path == tmp_path / "db" / "openings.db"
    assert config.attachments_dir == tmp_path / "attachments"
    assert config.log_file == tmp_path / "logs" / "openings.log"


def test_load_config_reports_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.yaml")


def test_load_config_reads_yaml(settings_file):
    config = load_config(settings_file)
    assert config.scoring.weights["role"] == 25


def test_feed_age_limits_parse_with_a_default():
    data = minimal_settings()
    data["sources"]["companies"] = [
        {"name": "A", "ats": "greenhouse", "slug": "acme", "max_age_days": 90},
        {"name": "B", "ats": "lever", "slug": "beta"},
    ]
    config = parse_config(data)
    assert config.sources.feed_max_age_days == 60
    assert config.sources.companies[0].max_age_days == 90
    assert config.sources.companies[1].max_age_days is None

    data["sources"]["feed_max_age_days"] = None
    assert parse_config(data).sources.feed_max_age_days is None

    data["sources"]["companies"][0]["max_age_days"] = 0
    with pytest.raises(ConfigError):
        parse_config(data)
