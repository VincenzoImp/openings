"""The maintainer scripts: one project description everywhere, and the traffic archive
(recorded API fixtures only, never a live call)."""

import datetime
import importlib.util
import json
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
traffic_archive = load("traffic_archive")


def copy_descriptions(tmp_path):
    for path in ["pyproject.toml", *(path for path, _ in check_package.DESCRIPTIONS)]:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / path, tmp_path / path)
    return tmp_path


def test_the_description_is_the_same_everywhere():
    assert "You just apply." in check_package.check_descriptions()


@pytest.mark.parametrize("path", [path for path, _ in check_package.DESCRIPTIONS])
def test_a_differing_description_fails(tmp_path, path):
    root = copy_descriptions(tmp_path)
    target = root / path
    target.write_text(target.read_text().replace("one SQLite file", "one database"))
    with pytest.raises(SystemExit, match="differs"):
        check_package.check_descriptions(root)


def test_a_missing_description_fails(tmp_path):
    root = copy_descriptions(tmp_path)
    target = root / "Dockerfile"
    target.write_text(target.read_text().replace("image.description=", "image.summary="))
    with pytest.raises(SystemExit, match="expected one description"):
        check_package.check_descriptions(root)


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
