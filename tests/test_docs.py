"""Documentation drift guards."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOCS)


def test_docs_describe_the_openings_commands():
    text = _text()
    for needle in ("openings scheduler", "openings web", "openings run", "/api", "/mcp"):
        assert needle in text, needle


def test_docs_do_not_mention_the_previous_product_name():
    text = _text().lower()
    assert "job-search-tool" not in text.replace("supersedes job-search-tool", "")
    assert "job_search_tool" not in text
    assert "job-search-web" not in text


def test_docs_do_not_reference_removed_state_vocabulary():
    text = _text()
    for needle in ("set_bookmarked", "set_applied", "bookmarked=", "JOB_SEARCH_"):
        assert needle not in text, needle


def test_changelog_starts_at_one():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.1.0]" in changelog


def test_every_source_name_appears_in_the_docs_and_the_example():
    """One adapter touches ten files, six of them prose. This is the guard that
    makes the drift impossible rather than merely discouraged."""
    from openings.config import KNOWN_ATS

    root = Path(__file__).resolve().parents[1]
    targets = [
        root / "docs" / "user" / "sources.md",
        root / "docs" / "user" / "configuration.md",
        root / "config" / "settings.example.yaml",
    ]
    for target in targets:
        text = target.read_text(encoding="utf-8").lower()
        missing = [name for name in KNOWN_ATS if name not in text]
        assert not missing, f"{target.name} does not mention {missing}"
