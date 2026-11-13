"""Local notes for a shipped skill: short, versioned text kept per workspace.

Skills ship with the server and match its version; a workspace never edits them.
Instead it keeps local notes for a skill, appended under their own heading
whenever the skill is served (``skills_get`` and ``GET /skills/{name}``, and the
skill's MCP prompt), all through :func:`serve`. The shipped text is never
modified or stored here.

Each save is a new immutable row (``skill_notes``: skill, version, text, who
wrote it, when), so the current notes are the highest version and the earlier
versions are the history. A save names the version it replaces
(``expected_version``, 0 for the first one) and leaves one attributed
``skill_notes_updated`` event whose payload holds the skill and the version,
never the text. Saving the same text again is no change.

Who may write: any authenticated actor, the owner's dashboard session, an owner
token and an agent token alike. The agent is the one that discovers what a
workflow lacks while running it; notes stay in this workspace, are served only
to its agents, never change the shipped text, and every version is attributed
(the served section names who wrote it), so the owner sees each change and
restores any earlier version from the dashboard. Personal criteria still belong
to the owner's Preferences, not to skill notes.
"""

from __future__ import annotations

from pydantic import Field

from .actors import current_actor, describe, pop_actor
from .common import now
from .errors import DomainError, conflict
from .models import Input

MAX_LENGTH = 2000
HISTORY = 50

HEADING = "## Local notes for this workspace"


def normalize(text: str) -> str:
    """Line endings as LF, no trailing whitespace and no blank lines around the text.

    An empty result clears the notes.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def serve(content: str, note: dict | None) -> str:
    """The skill text as served: the shipped text, then the local notes under their heading."""
    if not note or not note.get("text"):
        return content
    who = (note.get("updated_by") or {}).get("label") or "unknown"
    day = (note.get("updated_at") or "")[:10]
    return (
        f"{content.rstrip()}\n\n---\n\n{HEADING}\n\n"
        f"Written in this workspace (version {note['version']}, {day} by {who}). "
        "They add to the shipped skill above for this workspace only; the operating "
        "mandate and the owner's Preferences still apply.\n\n"
        f"{note['text']}\n"
    )


class SkillNotesInput(Input):
    expected_version: int = Field(
        ge=0, description="The current version of the notes; 0 when the skill has none yet."
    )
    text: str = Field(
        max_length=MAX_LENGTH,
        description="The whole notes text (at most 2000 characters). Empty clears the notes.",
    )


def _version(row):
    row = dict(row)
    return {
        "version": row["version"],
        "text": row["text"],
        "created_at": row["created_at"],
        "created_by": pop_actor(row, "created_by"),
    }


class SkillNotesService:
    def __init__(self, workspace, library):
        self.workspace = workspace
        self.db = workspace.db
        self.library = library

    def _known(self, name: str):
        if name not in {item["name"] for item in self.library.list()}:
            raise DomainError(404, "not_found", "Skill was not found.")

    def _read(self, conn, name: str) -> dict:
        rows = conn.execute(
            "SELECT * FROM skill_notes WHERE skill=? ORDER BY version DESC LIMIT ?",
            (name, HISTORY),
        ).fetchall()
        total = conn.execute("SELECT count(*) FROM skill_notes WHERE skill=?", (name,)).fetchone()[
            0
        ]
        versions = [_version(row) for row in rows]
        current = versions[0] if versions else None
        return {
            "skill": name,
            "text": current["text"] if current else "",
            "version": current["version"] if current else 0,
            "max_length": MAX_LENGTH,
            "updated_at": current["created_at"] if current else None,
            "updated_by": current["created_by"] if current else None,
            "versions": versions,
            "versions_total": total,
        }

    def get(self, name: str) -> dict:
        """The current local notes of a skill with its earlier versions, newest first."""
        self._known(name)
        with self.db.connect() as conn:
            return self._read(conn, name)

    def current(self, name: str) -> dict | None:
        """The current notes without history, or None when the skill has none."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM skill_notes WHERE skill=? ORDER BY version DESC LIMIT 1", (name,)
            ).fetchone()
        if row is None:
            return None
        version = _version(row)
        return {
            "version": version["version"],
            "text": version["text"],
            "updated_at": version["created_at"],
            "updated_by": version["created_by"],
            "length": len(version["text"]),
        }

    def summaries(self) -> dict:
        """The current version of every skill's notes, by skill name, for the list."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT n.* FROM skill_notes n JOIN (SELECT skill,max(version) AS version "
                "FROM skill_notes GROUP BY skill) m ON m.skill=n.skill AND m.version=n.version"
            ).fetchall()
        return {
            row["skill"]: {
                "version": row["version"],
                "updated_at": row["created_at"],
                "updated_by": describe(
                    row["created_by_kind"],
                    row["created_by_id"],
                    row["created_by_name"],
                    row["created_by_token_kind"],
                ),
                "length": len(row["text"]),
            }
            for row in rows
        }

    def update(self, name: str, value: SkillNotesInput) -> dict:
        """Replace a skill's local notes with a new version, naming the version it replaces."""
        value = (
            value if isinstance(value, SkillNotesInput) else SkillNotesInput.model_validate(value)
        )
        self._known(name)
        text = normalize(value.text)
        with self.db.transaction() as conn:
            current = conn.execute(
                "SELECT version,text FROM skill_notes WHERE skill=? ORDER BY version DESC LIMIT 1",
                (name,),
            ).fetchone()
            version = current["version"] if current else 0
            if value.expected_version != version:
                conflict(details={"current_version": version})
            if text == (current["text"] if current else ""):
                return self._read(conn, name)
            version += 1
            conn.execute(
                "INSERT INTO skill_notes(skill,version,text,created_by_kind,created_by_id,"
                "created_by_name,created_by_token_kind,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (name, version, text, *current_actor().columns(), now()),
            )
            self.workspace.event(
                "skill_notes_updated",
                payload={"skill": name, "version": version},
                conn=conn,
                subject=("skill", name),
            )
            return self._read(conn, name)
