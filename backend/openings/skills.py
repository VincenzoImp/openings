"""Shipped agent workflow skills, served read-only and unchanged over REST and MCP.

Each ``SKILL.md`` front matter names the skill (``name``, ``description``) and
says, for the dashboard's "What you can ask your agent" list, what the owner can
ask in plain words: ``title``, a one-sentence ``summary`` and an ``example``
phrase.
"""

import os
import re
from pathlib import Path

from .errors import DomainError

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
                    "title": fields.get("title", ""),
                    "summary": fields.get("summary", ""),
                    "example": fields.get("example", ""),
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


def list_skills(library: SkillLibrary) -> dict:
    """Every shipped skill with what the owner can ask and its reference files."""
    items = library.list()
    return {"items": items, "total": len(items)}


def read_skill(library: SkillLibrary, name: str, path: str = SKILL_FILE) -> dict:
    """A skill file as shipped."""
    return library.read(name, path)
