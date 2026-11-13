"""Shipped agent workflow skills, served read-only over REST and MCP.

A served ``SKILL.md`` ends with the workspace's local notes for that skill
(``skill_notes.serve``); reference files are served as shipped.
"""

import os
import re
from pathlib import Path
from typing import Annotated

from fastapi import Query

from . import skill_notes
from .errors import DomainError
from .skill_notes import SkillNotesInput, SkillNotesService

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
SKILL_FILE = "SKILL.md"


def skills_directory() -> Path:
    default = Path(__file__).resolve().parents[2] / "skills"
    return Path(os.environ.get("OPENINGS_SKILLS", default))


def _title(text: str) -> str:
    """The first Markdown heading after any front matter, or an empty string."""
    match = HEADING.search(FRONTMATTER.sub("", text, count=1))
    return match.group(1).strip() if match else ""


class SkillLibrary:
    """Read Agent Skills directories: <name>/SKILL.md plus Markdown references."""

    def __init__(self, directory: Path | None = None):
        self.directory = (directory or skills_directory()).resolve()

    def _metadata(self, path: Path):
        match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
        fields = {}
        for line in (match.group(1) if match else "").splitlines():
            key, _, value = line.partition(":")
            if value:
                fields[key.strip()] = value.strip()
        return fields

    def _files(self, root: Path):
        return sorted(str(path.relative_to(root)) for path in root.rglob("*.md") if path.is_file())

    def list(self):
        if not self.directory.is_dir():
            return []
        items = []
        for path in sorted(self.directory.glob("*/SKILL.md")):
            fields = self._metadata(path)
            root = path.parent
            files = self._files(root)
            details = []
            for name in files:
                data = (root / name).read_bytes()
                details.append(
                    {
                        "path": name,
                        "bytes": len(data),
                        "title": _title(data.decode("utf-8", errors="replace")),
                    }
                )
            items.append(
                {
                    "name": fields.get("name", root.name),
                    "description": fields.get("description", ""),
                    "files": files,
                    "file_details": details,
                }
            )
        return items

    def read(self, name: str, path: str = SKILL_FILE):
        root = (self.directory / name).resolve()
        target = (root / path).resolve()
        if (
            root.parent != self.directory
            or not (root / SKILL_FILE).is_file()
            or not target.is_relative_to(root)
            or target.suffix != ".md"
            or not target.is_file()
        ):
            raise DomainError(404, "not_found", "Skill file was not found.")
        return {
            "name": name,
            "path": str(target.relative_to(root)),
            "content": target.read_text(encoding="utf-8"),
        }


def list_skills(library: SkillLibrary, notes: SkillNotesService) -> dict:
    """Every shipped skill with its reference files and the version of its local notes."""
    summaries = notes.summaries()
    return {
        "items": [{**item, "local_notes": summaries.get(item["name"])} for item in library.list()]
    }


def read_skill(
    library: SkillLibrary,
    notes: SkillNotesService,
    name: str,
    path: str = SKILL_FILE,
    local_notes: bool = True,
) -> dict:
    """A skill file as served: SKILL.md ends with the local notes unless local_notes is false."""
    result = library.read(name, path)
    note = notes.current(name) if result["path"] == SKILL_FILE else None
    if note and local_notes:
        result["content"] = skill_notes.serve(result["content"], note)
    if note:
        note = {key: value for key, value in note.items() if key != "text"}
    return {**result, "local_notes": note}


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
