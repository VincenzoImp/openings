"""The documentation stays short, linked and in one vocabulary.

User docs are at most 10,000 words, the README at most 1,000, CONTRIBUTING at most 80
lines and the architecture guide at most 150. Every relative link and image resolves,
every image in docs/images is embedded, the MCP endpoint is spelled `/mcp/`, and no
removed tool name or earlier vocabulary appears outside the changelog.
"""

import re
from pathlib import Path

try:  # the table of removed names is deleted with the 0.25 release
    from openings.removed import TOOLS
except ImportError:
    TOOLS = {}

ROOT = Path(__file__).resolve().parents[2]
USER_DOCS = sorted((ROOT / "docs" / "user").glob("*.md"))
PAGES = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "developer" / "architecture.md",
    ROOT / "examples" / "operator-workspace" / "README.md",
    *USER_DOCS,
]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
# Words of the earlier product that the screen, REST, MCP and docs no longer use.
RETIRED = ("inbox", "cover_letter", "default_in_cv", "knowledge_", "claims_", "responses_")


def words(path):
    return len(path.read_text().split())


def test_the_docs_fit_their_limits():
    assert sum(words(path) for path in USER_DOCS) <= 10_000
    assert words(ROOT / "README.md") <= 1_000
    assert len((ROOT / "CONTRIBUTING.md").read_text().splitlines()) <= 80
    assert len((ROOT / "docs/developer/architecture.md").read_text().splitlines()) <= 150


def test_every_relative_link_and_image_resolves_and_every_image_is_used():
    missing = []
    for page in PAGES:
        for target in LINK.findall(page.read_text()):
            if re.match(r"[a-z]+:|#", target):
                continue
            path = (page.parent / target.split("#")[0]).resolve()
            if not path.exists():
                missing.append(f"{page.relative_to(ROOT)} -> {target}")
    assert not missing, missing
    # Every image in docs/images is embedded.
    embedded = {
        (page.parent / target).resolve()
        for page in PAGES
        for target in LINK.findall(page.read_text())
        if not re.match(r"[a-z]+:|#", target)
    }
    unused = [
        path.name
        for path in sorted((ROOT / "docs" / "images").iterdir())
        if path.resolve() not in embedded
    ]
    assert not unused, unused


def test_every_anchor_names_a_heading():
    def slug(heading):
        text = re.sub(r"[^\w\s-]", "", heading.lower().replace("`", ""))
        return re.sub(r"\s+", "-", text.strip())

    bad = []
    for page in PAGES:
        for target in LINK.findall(page.read_text()):
            if re.match(r"[a-z]+:", target) or "#" not in target:
                continue
            name, anchor = target.split("#", 1)
            path = page if not name else (page.parent / name).resolve()
            if path.suffix != ".md" or not path.exists():
                continue
            headings = re.findall(r"^#+ (.+)$", path.read_text(), re.MULTILINE)
            if anchor not in {slug(heading) for heading in headings}:
                bad.append(f"{page.relative_to(ROOT)} -> {target}")
    assert not bad, bad


def test_one_vocabulary_and_the_mcp_endpoint_with_its_slash():
    names = [name for name in TOOLS if "_" in name]
    found = []
    for page in PAGES:
        text = page.read_text()
        assert not re.search(r"/mcp(?![/\w])", text), page
        for name in names:
            if re.search(rf"\b{re.escape(name)}\b", text):
                found.append(f"{page.relative_to(ROOT)}: {name}")
        for word in RETIRED:
            if word in text.lower():
                found.append(f"{page.relative_to(ROOT)}: {word}")
    assert not found, found
