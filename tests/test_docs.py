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


def test_the_spelled_out_ats_count_matches_the_registry():
    """Prose counts drift silently; the previous release left "nine ATS" behind
    in three files and a "Three of these" in front of five paragraphs."""
    from openings.config import KNOWN_ATS

    words = {
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
        11: "eleven",
        12: "twelve",
        13: "thirteen",
        14: "fourteen",
        15: "fifteen",
        16: "sixteen",
    }
    expected = words[len(KNOWN_ATS)]
    stale = {count: word for count, word in words.items() if count != len(KNOWN_ATS)}

    root = Path(__file__).resolve().parents[1]
    for name in ("README.md", "CONTRIBUTING.md"):
        text = (root / name).read_text(encoding="utf-8").lower()
        for word in stale.values():
            assert f"{word} applicant tracking" not in text, f"{name} says {word}"
        if "applicant tracking system" in text:
            assert f"{expected} applicant tracking" in text, f"{name} has no current count"


def test_every_adapter_has_a_row_in_the_sources_table():
    from openings.sources.ats import FETCHERS

    root = Path(__file__).resolve().parents[1]
    table = (root / "docs" / "user" / "sources.md").read_text(encoding="utf-8")
    missing = [name for name in FETCHERS if f"| `{name}` |" not in table]
    assert not missing, f"sources.md table has no row for {missing}"


def test_getting_started_is_reachable_from_the_readme():
    """Nine of ten docs used to be link dead-ends; the entry point at least
    must be linked from the front page."""
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "user" / "getting-started.md").exists()
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "docs/user/getting-started.md" in readme
