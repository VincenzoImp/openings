"""Tests for project metadata helpers."""

from __future__ import annotations

from pathlib import Path
import tomllib


def test_project_version_matches_pyproject():
    from job_search_tool.project_meta import FALLBACK_VERSION, get_project_version

    pyproject = tomllib.loads(
        (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    )
    expected = pyproject["project"]["version"]
    assert FALLBACK_VERSION == expected
    assert get_project_version() == expected


def test_console_scripts_are_declared():
    pyproject = tomllib.loads(
        (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["scripts"] == {
        "job-search": "job_search_tool.main:main",
        "job-search-web": "job_search_tool.web.app:main",
        "job-search-healthcheck": "job_search_tool.healthcheck:main",
    }


def test_streamlit_runtime_dependency_is_removed():
    pyproject = tomllib.loads(
        (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert not any(
        dependency.startswith("streamlit")
        for dependency in pyproject["project"]["dependencies"]
    )
