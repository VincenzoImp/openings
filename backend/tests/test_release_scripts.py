"""The maintainer scripts: one project description everywhere, Docker Hub texts within
Docker Hub's limits, and the traffic archive
(recorded API fixtures only, never a live call)."""

import datetime
import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = json.loads((Path(__file__).parent / "fixtures/traffic_archive.json").read_text())
TOKEN = "synthetic-token-never-written"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_package = load("check_package")
bump_version = load("bump_version")
traffic_archive = load("traffic_archive")


def copy_descriptions(tmp_path):
    for path in ["pyproject.toml", *(path for path, _ in check_package.DESCRIPTIONS)]:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / path, tmp_path / path)
    return tmp_path


def test_the_description_is_the_same_everywhere():
    assert "works it by your rules. You apply." in check_package.check_descriptions()


@pytest.mark.parametrize("path", [path for path, _ in check_package.DESCRIPTIONS])
def test_a_differing_description_fails(tmp_path, path):
    root = copy_descriptions(tmp_path)
    target = root / path
    target.write_text(target.read_text().replace("your own AI agent", "an AI agent"))
    with pytest.raises(SystemExit, match="differs"):
        check_package.check_descriptions(root)


def test_a_missing_description_fails(tmp_path):
    root = copy_descriptions(tmp_path)
    target = root / "Dockerfile"
    target.write_text(target.read_text().replace("image.description=", "image.summary="))
    with pytest.raises(SystemExit, match="expected one description"):
        check_package.check_descriptions(root)


def copy_docker_hub(tmp_path):
    for path in (check_package.HUB_OVERVIEW, check_package.HUB_WORKFLOW):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / path, tmp_path / path)
    return tmp_path


def test_the_docker_hub_texts_fit():
    size, short = check_package.check_docker_hub()
    assert 0 < size <= 25_000 and 0 < len(short) <= 100


def test_a_docker_hub_overview_over_25000_bytes_fails(tmp_path):
    root = copy_docker_hub(tmp_path)
    (root / check_package.HUB_OVERVIEW).write_text("x" * 25_001)
    with pytest.raises(SystemExit, match="over 25000"):
        check_package.check_docker_hub(root)
    (root / check_package.HUB_OVERVIEW).write_text("x" * 25_000)
    check_package.check_docker_hub(root)


@pytest.mark.parametrize(("short", "error"), [("x" * 101, "101 characters"), ("", "0 characters")])
def test_a_docker_hub_short_description_outside_1_to_100_characters_fails(tmp_path, short, error):
    root = copy_docker_hub(tmp_path)
    workflow = root / check_package.HUB_WORKFLOW
    text = workflow.read_text()
    text = re.sub(check_package.HUB_SHORT_PATTERN, f"          short-description: '{short}'", text)
    workflow.write_text(text)
    with pytest.raises(SystemExit, match=error):
        check_package.check_docker_hub(root)


def test_the_docker_hub_overview_is_synced_from_final_releases_only():
    workflow = (ROOT / check_package.HUB_WORKFLOW).read_text()
    job = workflow.split("\n  hub-description:\n", 1)[1].split("\n\n  release:\n", 1)[0]
    assert "needs.version.outputs.prerelease == 'false'" in job
    assert re.search(r"peter-evans/dockerhub-description@[0-9a-f]{40} # v", job)
    assert "readme-filepath: docs/dockerhub.md" in job
    assert "secrets.DOCKERHUB_DESCRIPTION_TOKEN" in job


def copy_versions(tmp_path, monkeypatch):
    for path in {path for path, _ in bump_version.LOCATIONS}:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / path, tmp_path / path)
    monkeypatch.setattr(bump_version, "ROOT", tmp_path)
    return tmp_path


def test_compose_pins_the_moving_minor_and_the_plugin_the_release(tmp_path, monkeypatch):
    assert bump_version.check() == 0
    root = copy_versions(tmp_path, monkeypatch)
    assert bump_version.bump("4.5.6") == 0
    assert "docker.io/vincenzoimp/openings:4.5}" in (root / "docker-compose.yml").read_text()
    assert json.loads((root / ".claude-plugin/plugin.json").read_text())["version"] == "4.5.6"
    compose = root / "docker-compose.yml"
    compose.write_text(compose.read_text().replace("openings:4.5}", "openings:4.4}"))
    assert bump_version.check() == 1


def fixtures(responses, calls):
    def fetch(url, headers):
        calls.append((url, headers))
        response = responses[url]  # an unknown URL fails: no live call
        return response["data"], response.get("next")

    return fetch


def run(output, day, responses, calls):
    now = datetime.datetime.fromisoformat(f"{day}T06:00:00+00:00")
    argv = ["--repository-id", "4242", "--docker-image", "example/openings", "--output", output]
    return traffic_archive.main([str(arg) for arg in argv], fixtures(responses, calls), now)


def test_traffic_archive_records_one_entry_a_day(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    output = tmp_path / "private" / "traffic.jsonl"
    responses = json.loads(json.dumps(FIXTURES))
    calls = []
    run(output, "2030-01-01", responses, calls)
    run(output, "2030-01-01", responses, calls)  # twice a day: no second entry
    responses["https://hub.docker.com/v2/repositories/example/openings/"]["data"]["pull_count"] = (
        1040
    )
    run(output, "2030-01-02", responses, calls)

    entries = [json.loads(line) for line in output.read_text().splitlines()]
    assert [entry["date"] for entry in entries] == ["2030-01-01", "2030-01-02"]
    first, second = entries
    assert first["repository_id"] == 4242
    assert first["views"]["count"] == 12 and first["clones"]["uniques"] == 2
    assert first["referrers"][0]["referrer"] == "example.com"
    assert first["paths"][0]["path"] == "/example/repo"
    assert [star["starred_at"] for star in first["stars"]] == [
        "2030-01-01T08:00:00Z",
        "2030-01-01T09:00:00Z",
    ]
    assert first["forks"] == [{"name": "sam-example/repo", "created_at": "2030-01-01T10:00:00Z"}]
    # Pull requests are not issues.
    assert first["issues"] == {
        "alex-example": {"open": 1, "closed": 1},
        "sam-example": {"open": 1, "closed": 0},
    }
    assert first["docker"] == {
        "image": "example/openings",
        "pull_count": 1000,
        "pull_count_delta": None,
    }
    assert second["docker"]["pull_count_delta"] == 40

    # The repository is addressed by id; Docker Hub never sees the GitHub token.
    for url, headers in calls:
        if url.startswith("https://api.github.com/"):
            assert url.startswith("https://api.github.com/repositories/4242/")
            assert headers["Authorization"] == f"Bearer {TOKEN}"
        else:
            assert "Authorization" not in headers
    assert TOKEN not in output.read_text()
    assert output.stat().st_mode & 0o077 == 0


def test_traffic_archive_stays_outside_the_checkout(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    assert not traffic_archive.OUTPUT.expanduser().resolve().is_relative_to(ROOT)
    with pytest.raises(SystemExit, match="outside"):
        run(ROOT / "traffic.jsonl", "2030-01-01", FIXTURES, [])
    assert not (ROOT / "traffic.jsonl").exists()
