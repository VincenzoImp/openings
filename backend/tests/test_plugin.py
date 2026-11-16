"""The Claude Code plugin and its marketplace in the repository: the MCP connection
reads the token from the environment, and the plugin ships exactly skills/."""

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
PLUGIN = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
SKILLS = sorted(path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md"))
# The marketplace and plugin.json may only add skills through these keys.
COMPONENTS = {"skills", "commands", "agents", "hooks", "outputStyles", "workflows"}


def test_the_marketplace_lists_the_repository_as_one_plugin():
    assert re.fullmatch(r"[a-z0-9][a-z0-9._-]*", MARKETPLACE["name"])
    assert MARKETPLACE["owner"]["name"]
    [entry] = MARKETPLACE["plugins"]
    assert entry["name"] == PLUGIN["name"] == "openings"
    # The plugin is the repository root, so it ships the release's own skills/.
    assert entry["source"] == "./"
    assert "version" not in entry  # plugin.json's version is the one that counts


def test_the_plugin_version_is_the_release():
    with open(ROOT / "pyproject.toml", "rb") as file:
        assert PLUGIN["version"] == tomllib.load(file)["project"]["version"]


def test_the_mcp_server_reads_the_url_and_token_from_the_environment():
    assert PLUGIN["mcpServers"] == {
        "openings": {
            "type": "http",
            "url": "${OPENINGS_URL:-http://127.0.0.1:8080}/mcp/",
            "headers": {"Authorization": "Bearer ${OPENINGS_TOKEN}"},
        }
    }


def test_no_secret_in_the_manifests():
    for path in (ROOT / ".claude-plugin").iterdir():
        text = path.read_text()
        assert not re.search(r"op_[A-Za-z0-9_-]{16,}", text), path
        for value in re.findall(r'"Bearer ([^"]*)"', text):
            assert value == "${OPENINGS_TOKEN}", path


def test_the_skill_set_is_skills():
    # No manifest adds or replaces components, and no SKILL.md at the root would
    # turn the whole repository into one skill: Claude Code loads skills/ as is.
    assert not COMPONENTS & set(PLUGIN)
    assert not COMPONENTS & set(MARKETPLACE["plugins"][0])
    assert not (ROOT / "SKILL.md").exists()
    assert SKILLS
    for name in SKILLS:
        text = (ROOT / "skills" / name / "SKILL.md").read_text()
        assert re.search(rf"(?m)^name: {re.escape(name)}$", text), name
    for directory in ("commands", "agents", "hooks", "bin", "output-styles", "workflows"):
        assert not (ROOT / directory).exists(), directory
    assert not (ROOT / ".mcp.json").exists()
