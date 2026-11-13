"""REST routes and MCP tools of skills."""

from typing import Annotated

from fastapi import Query

from ..skill_notes import SkillNotesInput, SkillNotesService
from ..skills import SKILL_FILE, SkillLibrary, list_skills, read_skill


def register_api(router, library: SkillLibrary, notes: SkillNotesService):
    @router.get("/skills")
    def skills_list():
        return list_skills(library, notes)

    @router.get("/skills/{name}/notes")
    def skill_notes_get(name: str):
        return notes.get(name)

    @router.put("/skills/{name}/notes")
    def skill_notes_update(name: str, value: SkillNotesInput):
        return notes.update(name, value)

    @router.get("/skills/{name}")
    def skill_get(name: str, local_notes: Annotated[bool, Query()] = True):
        return read_skill(library, notes, name, SKILL_FILE, local_notes)

    @router.get("/skills/{name}/files/{path:path}")
    def skill_file_get(name: str, path: str, local_notes: Annotated[bool, Query()] = True):
        return read_skill(library, notes, name, path, local_notes)


def register_mcp(mcp, library: SkillLibrary, notes: SkillNotesService):
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(destructiveHint=False, openWorldHint=False)

    @mcp.tool(annotations=read_only)
    def skills_list() -> dict:
        """List the workflow skills this server ships for agents operating Openings:
        setup, Inbox review, Shortlist preparation, sources, Career maintenance,
        tracking, interviews and writing, with their reference files and the version
        of each skill's local notes. Read one with skill_get."""
        return list_skills(library, notes)

    @mcp.tool(annotations=read_only)
    def skill_get(name: str, path: str = SKILL_FILE, local_notes: bool = True) -> dict:
        """Read a skill's SKILL.md, or one of its listed reference files, as Markdown.
        SKILL.md ends with this workspace's local notes under "Local notes for this
        workspace" (local_notes=false returns the shipped text alone). Relative links
        inside a skill resolve against that skill's directory."""
        return read_skill(library, notes, name, path, local_notes)

    @mcp.tool(annotations=read_only)
    def skill_notes_get(name: str) -> dict:
        """Read a skill's local notes for this workspace: text, version, who wrote it and
        the earlier versions, newest first."""
        return notes.get(name)

    @mcp.tool(annotations=write)
    def skill_notes_update(name: str, value: SkillNotesInput) -> dict:
        """Replace a skill's local notes (at most 2000 characters; empty clears them) using
        their current version (0 for the first notes). Record a lasting method gap of this
        workspace here; personal criteria belong to the policy. Each save is a new,
        attributed version that the owner can read and restore."""
        return notes.update(name, value)

    for item in library.list():
        name = item["name"]

        def instructions(name=name) -> str:
            skill = read_skill(library, notes, name)["content"]
            return (
                f"Follow the Openings `{name}` skill below. Read referenced files with "
                f"skill_get(name, path); `../<skill>/...` links name another skill.\n\n{skill}"
            )

        mcp.prompt(name=name, description=item["description"][:1024])(instructions)
