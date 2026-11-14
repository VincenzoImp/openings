"""The operator workspace template ships client adapters generated from its MCP definition."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "examples" / "operator-workspace"
SYNC = ".agents/scripts/sync.py"


def test_template_adapters_match_its_mcp_definition():
    subprocess.run([sys.executable, SYNC, "--check"], cwd=TEMPLATE, check=True)


def test_url_option_rewrites_every_client_adapter_and_needs_https(tmp_path):
    workspace = tmp_path / "workspace"
    shutil.copytree(TEMPLATE, workspace, symlinks=True)
    # Plain HTTP is only accepted for localhost.
    result = subprocess.run(
        [sys.executable, SYNC, "--url", "http://openings.example"],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "HTTPS" in result.stderr
    subprocess.run(
        [sys.executable, SYNC, "--url", "https://openings.example/"], cwd=workspace, check=True
    )
    assert (
        json.loads((workspace / ".mcp.json").read_text())["mcpServers"]["openings"]["url"]
        == "https://openings.example/mcp/"
    )
    assert 'url = "https://openings.example/mcp/"' in (workspace / ".codex/config.toml").read_text()
    assert (
        'bearer_token_env_var = "OPENINGS_TOKEN"' in (workspace / ".codex/config.toml").read_text()
    )
    subprocess.run([sys.executable, SYNC, "--check"], cwd=workspace, check=True)
