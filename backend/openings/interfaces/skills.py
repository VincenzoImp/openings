"""REST routes and MCP tools of skills."""

from types import SimpleNamespace

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

from ..skill_notes import SkillNotesInput, SkillNotesService
from ..skills import SKILL_FILE, SkillLibrary, list_skills, read_skill
from .registry import (
    Operation,
    Param,
    Route,
    Surface,
    Tool,
    bind_mcp,
    bind_rest,
    query_model,
)


class SkillRead(BaseModel):
    """Whether SKILL.md ends with this workspace's local notes."""

    model_config = ConfigDict(extra="forbid")
    local_notes: bool = True


READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(destructiveHint=False, openWorldHint=False)

OPERATIONS = (
    Operation(
        "skills.list",
        "skills",
        "list",
        "Archive",
        "List shipped agent workflow skills",
        params=(),
        call=lambda s: list_skills(s.library, s.notes),
        rest=(Route("GET", "/skills", "skills_list"),),
        tool=Tool(
            READ,
            "List the workflow skills this server ships for agents operating Openings:\nsetup, Inbox review, Shortlist preparation, sources, Career maintenance,\ntracking, interviews and writing, with their reference files and the version\nof each skill's local notes. Read one with skills_get.",
        ),
    ),
    Operation(
        "skills.notes.read",
        "skill_notes",
        "get",
        "Archive",
        "Read a skill's local notes for this workspace with earlier versions",
        params=(Param("name", str),),
        call=lambda s, name: s.notes.get(name),
        rest=(Route("GET", "/skills/{name}/notes", "skill_notes_get"),),
        tool=Tool(
            READ,
            "Read a skill's local notes for this workspace: text, version, who wrote it and\nthe earlier versions, newest first.",
        ),
    ),
    Operation(
        "skills.notes.update",
        "skill_notes",
        "update",
        "Archive",
        "Replace a skill's local notes",
        params=(Param("name", str), Param("value", SkillNotesInput)),
        call=lambda s, name, value: s.notes.update(name, value),
        rest=(Route("PUT", "/skills/{name}/notes", "skill_notes_update"),),
        tool=Tool(
            WRITE,
            "Replace a skill's local notes (at most 2000 characters; empty clears them) using\ntheir current version (0 for the first notes). Record a lasting method gap of this\nworkspace here; personal criteria belong to the policy. Each save is a new,\nattributed version that the owner can read and restore.",
        ),
    ),
    Operation(
        "skills.read",
        "skills",
        "get",
        "Archive",
        "Read a skill or one of its reference files",
        params=(Param("name", str), Param("path", str, SKILL_FILE), query_model(SkillRead)),
        call=lambda s, name, path, value: read_skill(
            s.library, s.notes, name, path, (value or SkillRead()).local_notes
        ),
        rest=(
            Route(
                "GET",
                "/skills/{name}",
                "skill_get",
                params=(Param("name", str), query_model(SkillRead)),
                call=lambda s, name, value: read_skill(
                    s.library, s.notes, name, SKILL_FILE, value.local_notes
                ),
            ),
            Route(
                "GET",
                "/skills/{name}/files/{path:path}",
                "skill_file_get",
                params=(Param("name", str), Param("path", str), query_model(SkillRead)),
            ),
        ),
        tool=Tool(
            READ,
            "Read a skill's SKILL.md, or one of its listed reference files (path), as Markdown.\nSKILL.md ends with this workspace's local notes under \"Local notes for this\nworkspace\" (value.local_notes=false returns the shipped text alone). Relative links\ninside a skill resolve against that skill's directory.",
        ),
    ),
)


SURFACES = (Surface("prompt", "<skill name>"),)


def register_api(router, library: SkillLibrary, notes: SkillNotesService):
    bind_rest(router, OPERATIONS, SimpleNamespace(library=library, notes=notes))


def register_mcp(mcp, library: SkillLibrary, notes: SkillNotesService):
    bind_mcp(mcp, OPERATIONS, SimpleNamespace(library=library, notes=notes))

    # One prompt per shipped skill: the skill's instructions with its local notes.
    for item in library.list():
        mcp.prompt(name=item["name"], description=item["description"][:1024])(
            _prompt(library, notes, item["name"])
        )


def _prompt(library: SkillLibrary, notes: SkillNotesService, name: str):
    """The prompt of one skill: a function without parameters, so it declares no arguments."""

    def instructions() -> str:
        skill = read_skill(library, notes, name)["content"]
        return (
            f"Follow the Openings `{name}` skill below. Read referenced files with "
            f"skills_get(name, path); `../<skill>/...` links name another skill.\n\n{skill}"
        )

    instructions.__name__ = instructions.__qualname__ = name.replace("-", "_")
    return instructions
