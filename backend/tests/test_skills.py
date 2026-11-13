"""Shipped agent skills are readable over REST and MCP, with prompts per skill."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openings.app import create_app
from openings.errors import DomainError
from openings.skills import SkillLibrary

ROOT = Path(__file__).resolve().parents[2] / "skills"
SHIPPED = {path.parent.name for path in ROOT.glob("*/SKILL.md")}


def test_library_lists_every_shipped_skill_with_references():
    items = {item["name"]: item for item in SkillLibrary(ROOT).list()}
    assert set(items) == SHIPPED and "setup-openings" in items
    assert all(item["description"] for item in items.values())
    assert "references/operating-mandate.md" in items["openings-workspace"]["files"]


@pytest.mark.parametrize(
    "path", ["../review-inbox/SKILL.md", "/etc/passwd", "references/missing.md", "SKILL.txt"]
)
def test_library_rejects_paths_outside_a_skill(path):
    with pytest.raises(DomainError):
        SkillLibrary(ROOT).read("openings-workspace", path)


def test_unknown_skill_is_not_found():
    with pytest.raises(DomainError):
        SkillLibrary(ROOT).read("..", "README.md")


def test_skills_over_rest_and_mcp(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENINGS_SKILLS", str(ROOT))
    app = create_app(tmp_path / "skills.sqlite", start_worker=False)
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic agent")["token"]
    rest = {"Authorization": "Bearer " + token}
    mcp = {**rest, "Accept": "application/json, text/event-stream"}

    def rpc(method, params, ident):
        response = client.post(
            "/mcp/",
            headers=mcp,
            json={"jsonrpc": "2.0", "id": ident, "method": method, "params": params},
        )
        assert response.status_code == 200
        return response.json()["result"]

    with TestClient(app, base_url="http://localhost:8080") as client:
        listed = client.get("/api/v1/skills", headers=rest).json()["items"]
        assert {item["name"] for item in listed} == SHIPPED
        skill = client.get("/api/v1/skills/review-inbox", headers=rest).json()
        assert skill["content"].startswith("---\nname: review-inbox")
        reference = client.get(
            "/api/v1/skills/openings-workspace/files/references/run-report.md", headers=rest
        )
        assert reference.status_code == 200 and "# Run report" in reference.json()["content"]
        assert client.get("/api/v1/skills/nope", headers=rest).status_code == 404

        result = rpc(
            "tools/call", {"name": "skills_get", "arguments": {"name": "setup-openings"}}, 1
        )
        body = result.get("structuredContent") or json.loads(result["content"][0]["text"])
        assert "# Set up Openings" in body["content"]
        prompts = {p["name"] for p in rpc("prompts/list", {}, 2)["prompts"]}
        assert SHIPPED <= prompts
        prompt = rpc("prompts/get", {"name": "prepare-shortlist"}, 3)
        assert "# Prepare Shortlist" in prompt["messages"][0]["content"]["text"]
