"""Shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest
import yaml

# JobSpy is only imported inside the jobspy source at call time; keep the
# module importable in environments where the scraper is not installed.
sys.modules.setdefault("jobspy", MagicMock())

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SETTINGS = ROOT / "config" / "settings.example.yaml"


def minimal_settings() -> dict:
    """The smallest configuration that exercises scoring meaningfully."""
    return {
        "sources": {
            "jobspy": {
                "enabled": False,
                "locations": ["Remote"],
                "queries": {"core": ["software engineer"]},
            }
        },
        "scoring": {
            "save_threshold": 0,
            "notify_threshold": 20,
            "weights": {"role": 25, "stack": 10, "penalty": -40},
            "keywords": {
                "role": ["software engineer", "backend"],
                "stack": ["python", "postgresql"],
                "penalty": ["10+ years"],
            },
        },
        "vector_search": {"enabled": False, "embed_on_save": False, "backfill_on_startup": False},
        "notifications": {"enabled": False},
    }


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "data"
    (directory / "config").mkdir(parents=True)
    return directory


@pytest.fixture
def settings_dict() -> dict:
    return minimal_settings()


@pytest.fixture
def config(data_dir: Path, settings_dict: dict):
    from openings.config import parse_config

    return parse_config(settings_dict, data_dir=data_dir)


@pytest.fixture
def settings_file(data_dir: Path, settings_dict: dict) -> Path:
    path = data_dir / "config" / "settings.yaml"
    path.write_text(yaml.safe_dump(settings_dict), encoding="utf-8")
    return path


@pytest.fixture
def env(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path, settings_file: Path
) -> Generator[Path, None, None]:
    """Point the process at the temp data directory and reset every singleton."""
    from openings import config as config_module
    from openings import database as database_module
    from openings.web import service as service_module

    monkeypatch.setenv("OPENINGS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OPENINGS_CONFIG", str(settings_file))
    monkeypatch.setenv("OPENINGS_WEB_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("OPENINGS_WEB_ALLOWED_ORIGINS", "http://testserver")
    monkeypatch.delenv("OPENINGS_API_TOKEN", raising=False)
    monkeypatch.setattr(config_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", settings_file)
    config_module.set_config(None)
    database_module.close_database()
    service_module.reset_service()
    yield data_dir
    service_module.reset_service()
    database_module.close_database()
    config_module.set_config(None)


@pytest.fixture
def db(data_dir: Path):
    from openings.database import JobDatabase

    database = JobDatabase(data_dir / "db" / "openings.db")
    yield database
    database.close()


def make_job(**overrides):
    from openings.models import Job

    fields = {
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Remote",
        "source": "linkedin",
        "job_url": "https://example.com/jobs/1",
        "description": "Python services with PostgreSQL.",
        "relevance_score": 35,
    }
    fields.update(overrides)
    return Job.from_row(fields)


@pytest.fixture
def job():
    return make_job()


@pytest.fixture
def jobs():
    return [
        make_job(),
        make_job(
            title="Data Engineer", company="Beta", location="Berlin, Germany", relevance_score=15
        ),
        make_job(
            title="Sales Manager",
            company="Gamma",
            location="Remote",
            relevance_score=-40,
            source="greenhouse",
        ),
    ]


@pytest.fixture
def service(env: Path):
    from openings.web.service import get_service

    return get_service()


@pytest.fixture
def client(env: Path):
    from fastapi.testclient import TestClient

    from openings.web.app import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
