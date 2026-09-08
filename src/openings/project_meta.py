"""Project metadata helpers."""

from __future__ import annotations

import tomllib
from importlib import metadata
from pathlib import Path

PROJECT_NAME = "openings"
FALLBACK_VERSION = "1.0.0"
ROOT_DIR = Path(__file__).resolve().parents[2]


def get_project_version() -> str:
    """Installed package version, falling back to pyproject metadata."""
    try:
        return metadata.version(PROJECT_NAME)
    except metadata.PackageNotFoundError:
        pyproject = ROOT_DIR / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            return str(data["project"]["version"])
        return FALLBACK_VERSION
