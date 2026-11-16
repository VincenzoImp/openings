"""The shipped skills: the set, their size budgets, live tool names, and how they are served."""

import re
from pathlib import Path

import pytest

from openings.errors import DomainError
from openings.skills import SkillLibrary

ROOT = Path(__file__).resolve().parents[2] / "skills"
CORE = "openings"
# Bytes per skill, its SKILL.md alone; references have their own budget. 0.28 raised
# the core skill for standing instructions, critical actions and runs without the
# owner, and the task skills for the enforced rules and workflows they lacked.
BUDGETS = {
    "openings": 6_500,
    "triage-jobs": 6_000,
    "prepare-applications": 7_000,
    "review-applications": 5_000,
    "track-applications": 4_500,
    "maintain-career": 5_000,
    "manage-sources": 4_000,
    "prepare-interview": 3_000,
    "setup-openings": 5_000,
    "run-job-search": 5_000,
    "maintain-workspace": 4_000,
}
REFERENCES = {
    "openings/references/server-rules.md": 3_000,
    "prepare-applications/references/writing.md": 5_000,
}
# Eleven skills and two references; 0.28 added three skills and the server rules.
TOTAL = 60_000
# What one workflow reads: the core skill, its own skill and at most one reference.
WORKFLOW = 16_000
TOOL_NAME = re.compile(r"`([a-z]+(?:_[a-z]+)+)`")
# Concepts removed in 0.24 that a skill must not send an agent looking for.
REMOVED_CONCEPTS = re.compile(
    r"\b(run report|local notes?|operating mandate|frozen context|staleness|"
    r"approve the (cv|letter|document)|claim_ids|knowledge_ids)\b",
    re.IGNORECASE,
)
FRONTMATTER = ("name", "description", "title", "summary", "example")


def files():
    return sorted(path for path in ROOT.rglob("*") if path.is_file())


def test_exactly_the_shipped_skills_and_references_are_within_budget():
    assert {path.relative_to(ROOT).as_posix() for path in files()} == {
        f"{name}/SKILL.md" for name in BUDGETS
    } | set(REFERENCES)
    sizes = {path.relative_to(ROOT).as_posix(): path.stat().st_size for path in files()}
    for name, budget in BUDGETS.items():
        assert sizes[f"{name}/SKILL.md"] <= budget, (name, sizes[f"{name}/SKILL.md"])
    for path, budget in REFERENCES.items():
        assert sizes[path] <= budget, (path, sizes[path])
    assert sum(sizes.values()) <= TOTAL, sum(sizes.values())
    for name in BUDGETS:
        references = [size for path, size in sizes.items() if path.startswith(f"{name}/ref")]
        own = sizes[f"{name}/SKILL.md"] if name != CORE else 0
        read = sizes[f"{CORE}/SKILL.md"] + own + max(references, default=0)
        assert read <= WORKFLOW, (name, read)
    # Every skill has the frontmatter the dashboard lists.
    items = {item["name"]: item for item in SkillLibrary(ROOT).list()}
    assert set(items) == set(BUDGETS)
    for name, item in items.items():
        for field in FRONTMATTER:
            assert item.get(field), (name, field)
    assert items["prepare-applications"]["files"] == ["SKILL.md", "references/writing.md"]
    assert items["openings"]["files"] == ["SKILL.md", "references/server-rules.md"]


def test_every_workflow_reads_the_core_skill_and_reports_back():
    for name in BUDGETS:
        text = (ROOT / name / "SKILL.md").read_text()
        assert "## Report back" in text, name
        assert "workspace_context" in text, name
        if name != CORE:
            assert "](../openings/SKILL.md)" in text, name
    core = (ROOT / CORE / "SKILL.md").read_text()
    for limit in ("Never submit", "Never invent career facts", "Applied only when the owner"):
        assert limit in core
    # Standing instructions lift a default, never a hard limit; runs never wait.
    for section in ("## Standing instructions", "## Critical actions", "## Runs without the owner"):
        assert section in core
    assert "](references/server-rules.md)" in core


def test_skills_name_only_live_tools_and_no_removed_concepts(mcp):
    live = {tool["name"] for tool in mcp.rpc("tools/list")["tools"]}
    for path in files():
        text = path.read_text()
        for name in TOOL_NAME.findall(text):
            # Shell commands in backticks are not tools.
            if "_" in name and name not in {"pdflatex", "pdftotext"}:
                assert name in live, (path.name, name)
        found = REMOVED_CONCEPTS.search(text)
        assert not found, (path.relative_to(ROOT), found and found.group(0))


def test_skills_and_the_agent_round_trip_use_no_retired_word():
    # Unlike the docs check, quoted trigger phrases count too: an agent repeats them.
    texts = [*files(), Path(__file__).with_name("agent_roundtrip.py")]
    found = [path.name for path in texts if "inbox" in path.read_text().lower()]
    assert not found, found


def test_library_rejects_paths_outside_a_skill_and_unknown_skills():
    library = SkillLibrary(ROOT)
    # A link to another skill's file reads that skill's file.
    linked = library.read("maintain-career", "../prepare-applications/references/writing.md")
    assert (linked["name"], linked["path"]) == ("prepare-applications", "references/writing.md")
    for path in (
        "../../skills/openings/SKILL.md",
        "../missing/SKILL.md",
        "../openings/../../README.md",
        "/etc/passwd",
        "references/missing.md",
        "SKILL.txt",
    ):
        with pytest.raises(DomainError):
            SkillLibrary(ROOT).read("prepare-applications", path)
    with pytest.raises(DomainError):
        SkillLibrary(ROOT).read("..", "README.md")


def test_skills_over_rest(client):
    listed = client.get("/api/v1/skills").json()["items"]
    assert {item["name"] for item in listed} == set(BUDGETS)
    assert {"title", "summary", "example"} <= set(listed[0])
    skill = client.get("/api/v1/skills/triage-jobs").json()
    assert skill["content"].startswith("---\nname: triage-jobs")
    reference = client.get("/api/v1/skills/prepare-applications/files/references/writing.md")
    assert reference.status_code == 200
    assert client.get("/api/v1/skills/review-inbox").status_code == 404


def test_skills_over_mcp_as_tool_prompts_and_resources(mcp):
    index, error = mcp.call("skills_get")
    assert error is None and {item["name"] for item in index["items"]} == set(BUDGETS)
    body, error = mcp.call("skills_get", {"name": "setup-openings"})
    assert error is None and "# Set up your workspace" in body["content"]
    body, error = mcp.call(
        "skills_get", {"name": "prepare-applications", "path": "references/writing.md"}
    )
    assert error is None and body["content"].startswith("# Writing")

    prompts = {prompt["name"]: prompt for prompt in mcp.rpc("prompts/list")["prompts"]}
    assert set(prompts) == set(BUDGETS)
    assert all(not prompt.get("arguments") for prompt in prompts.values())
    prompt = mcp.rpc("prompts/get", {"name": "triage-jobs"})["messages"][0]["content"]["text"]
    assert prompt.startswith("Follow the Openings `triage-jobs` skill")
    assert "# Go through new jobs" in prompt

    resources = {item["uri"] for item in mcp.rpc("resources/list")["resources"]}
    assert {f"openings://skills/{name}" for name in BUDGETS} <= resources
    assert "openings://skills/prepare-applications/references/writing.md" in resources
    assert "openings://skills/openings/references/server-rules.md" in resources
    read = mcp.rpc("resources/read", {"uri": "openings://skills/openings"})
    assert read["contents"][0]["text"].startswith("---\nname: openings")
