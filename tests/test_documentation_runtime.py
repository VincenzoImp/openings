"""Documentation drift checks for the current runtime topology."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CURRENT_DOCS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / ".env.example",
    *sorted((ROOT / "docs" / "user").glob("*.md")),
    *sorted((ROOT / "docs" / "developer").glob("*.md")),
]
REMOVED_RUNTIME_TOKENS = (
    "Streamlit",
    "streamlit",
    "job-search dashboard",
    "job-search-api",
    "job-search-mcp",
    "JOB_SEARCH_DASHBOARD",
    "JOB_SEARCH_API_BIND",
    "JOB_SEARCH_API_PORT",
    "JOB_SEARCH_MCP_BIND",
    "JOB_SEARCH_MCP_PORT",
    "--profile api",
    "--profile mcp",
    "127.0.0.1:8502",
    "127.0.0.1:3001",
)


def test_current_docs_describe_only_the_unified_web_runtime() -> None:
    """Current docs should not advertise removed standalone runtimes."""
    offenders: list[str] = []

    for path in CURRENT_DOCS:
        text = path.read_text(encoding="utf-8")
        for token in REMOVED_RUNTIME_TOKENS:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)}: {token}")

    assert offenders == []


def test_readme_points_users_at_the_web_entrypoint() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "job-search-web" in text
    assert "http://127.0.0.1:8501/mcp" in text
    assert "http://127.0.0.1:8501/api" in text
