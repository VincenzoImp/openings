"""Tests for GitHub Actions workflow maintenance."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _workflow(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _uses_versions(path: str) -> set[str]:
    workflow = _workflow(path)
    versions: set[str] = set()
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if isinstance(uses, str):
                versions.add(uses)
    return versions


def test_workflows_use_node24_ready_action_majors() -> None:
    """Keep hosted Actions clear of the Node.js 20 runtime deprecation."""
    uses = _uses_versions(".github/workflows/ci.yml") | _uses_versions(
        ".github/workflows/publish-release.yml"
    )

    assert "actions/upload-artifact@v6" in uses
    assert "docker/setup-qemu-action@v4" in uses
    assert "docker/setup-buildx-action@v4" in uses
    assert "docker/login-action@v4" in uses
    assert "docker/build-push-action@v7" in uses

    assert (
        not {
            "actions/upload-artifact@v4",
            "docker/setup-qemu-action@v3",
            "docker/setup-buildx-action@v3",
            "docker/login-action@v3",
            "docker/build-push-action@v6",
        }
        & uses
    )
