"""Shared fixtures."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import numpy as np
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
        "embeddings": {"enabled": False},
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
def runtime(monkeypatch: pytest.MonkeyPatch, data_dir: Path, settings_file: Path):
    """A process-wide runtime pointed at the temp data directory."""
    from openings.runtime import Runtime, set_runtime

    monkeypatch.setenv("OPENINGS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OPENINGS_CONFIG", str(settings_file))
    monkeypatch.setenv("OPENINGS_WEB_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("OPENINGS_WEB_ALLOWED_ORIGINS", "http://testserver")
    monkeypatch.delenv("OPENINGS_API_TOKEN", raising=False)
    instance = Runtime(data_dir=data_dir, config_path=settings_file)
    set_runtime(instance)
    yield instance
    set_runtime(None)


@pytest.fixture
def env(runtime) -> Generator[Path, None, None]:
    """The data directory of an installed runtime (kept for readability)."""
    yield runtime.data_dir


@pytest.fixture
def db(data_dir: Path):
    from openings.db import JobDatabase

    database = JobDatabase(data_dir / "db" / "openings.db")
    yield database
    database.close()


def fake_vector(text: str) -> np.ndarray:
    """A deterministic unit vector: identical texts are identical, others differ."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    generator = np.random.default_rng(seed)
    vector = generator.standard_normal(384).astype(np.float32)
    return vector / np.linalg.norm(vector)


@pytest.fixture
def fake_embedding_model(monkeypatch: pytest.MonkeyPatch):
    """Replace the ONNX model with a hash-based stand-in (no download, no runtime)."""
    from openings import embeddings as module

    def embed(self, texts, batch_size=32):
        return np.vstack([fake_vector(text) for text in texts])

    monkeypatch.setattr(module.EmbeddingModel, "embed", embed)
    monkeypatch.setattr(module.EmbeddingModel, "_load", lambda self: None)
    monkeypatch.setattr(module.EmbeddingModel, "ensure_downloaded", lambda self, timeout=0: None)
    return module


def make_job(**overrides):
    from openings.models import Job

    fields = {
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Remote",
        "source": "linkedin",
        "job_url": "https://www.linkedin.com/jobs/view/1000001",
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
            title="Data Engineer",
            company="Beta",
            location="Berlin, Germany",
            relevance_score=15,
            job_url="https://www.linkedin.com/jobs/view/1000002",
        ),
        make_job(
            title="Sales Manager",
            company="Gamma",
            location="Remote",
            relevance_score=-40,
            source="greenhouse",
            job_url="https://boards.greenhouse.io/gamma/jobs/77",
        ),
    ]


@pytest.fixture
def service(runtime):
    return runtime.service


@pytest.fixture
def client(runtime):
    from fastapi.testclient import TestClient

    from openings.web.app import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
