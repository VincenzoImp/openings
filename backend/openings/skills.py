"""Shipped agent workflow skills, served read-only over REST and MCP."""

import os
import re
from pathlib import Path

from .errors import DomainError

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def skills_directory() -> Path:
    default = Path(__file__).resolve().parents[2] / "skills"
    return Path(os.environ.get("OPENINGS_SKILLS", default))


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
            items.append(
                {
                    "name": fields.get("name", path.parent.name),
                    "description": fields.get("description", ""),
                    "files": self._files(path.parent),
                }
            )
        return items

    def read(self, name: str, path: str = "SKILL.md"):
        root = (self.directory / name).resolve()
        target = (root / path).resolve()
        if (
            root.parent != self.directory
            or not (root / "SKILL.md").is_file()
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


def register_api(router, library: SkillLibrary):
    @router.get("/skills")
    def list_skills():
        return {"items": library.list()}

    @router.get("/skills/{name}")
    def read_skill(name: str):
        return library.read(name)

    @router.get("/skills/{name}/files/{path:path}")
    def read_skill_file(name: str, path: str):
        return library.read(name, path)


def register_mcp(mcp, library: SkillLibrary):
    from mcp.types import ToolAnnotations

    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    @mcp.tool(annotations=read_only)
    def skills_list() -> dict:
        """List the workflow skills this server ships for agents operating Openings:
        setup, Inbox review, Shortlist preparation, sources, Career maintenance,
        tracking, interviews and writing. Read one with skill_get."""
        return {"items": library.list()}

    @mcp.tool(annotations=read_only)
    def skill_get(name: str, path: str = "SKILL.md") -> dict:
        """Read a skill's SKILL.md, or one of its listed reference files, as Markdown.
        Relative links inside a skill resolve against that skill's directory."""
        return library.read(name, path)

    for item in library.list():
        name = item["name"]

        def instructions(name=name) -> str:
            skill = library.read(name)["content"]
            return (
                f"Follow the Openings `{name}` skill below. Read referenced files with "
                f"skill_get(name, path); `../<skill>/...` links name another skill.\n\n{skill}"
            )

        mcp.prompt(name=name, description=item["description"][:1024])(instructions)
