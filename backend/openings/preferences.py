"""Preferences: what the owner wants, in their own words, and two plain settings.

Five sections hold short statements (plain text, Markdown allowed):

- ``looking_for``: what I'm looking for;
- ``ruled_out``: what I rule out;
- ``facts``: facts about me (eligibility, availability, salary, ...);
- ``writing``: writing rules for documents, each for ``all`` documents, the ``cv``
  or the ``letter``;
- ``working_with_me``: instructions the agent follows.

Nothing here is typed or applied automatically: an agent reads the statements and
applies them. A write replaces one whole section and names the section's version.

Two values are typed because the product itself uses them, and live in the
``workspace`` setting: ``no_reply_days`` (the no-reply period of applications) and
``spoken_languages`` (the "hide jobs requiring languages I don't speak" filter).
"""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from . import events
from .actors import current_actor
from .common import encode, now
from .errors import DomainError, conflict
from .job_signals import normalize_languages
from .models import Input, NonBlank

SECTIONS = ("looking_for", "ruled_out", "facts", "writing", "working_with_me")
SECTION_TITLES = {
    "looking_for": "What I'm looking for",
    "ruled_out": "What I rule out",
    "facts": "Facts about me",
    "writing": "Writing rules",
    "working_with_me": "Working with me",
}
SECTION_DESCRIPTIONS = {
    "looking_for": "Roles, places, companies and conditions that make a job worth a look.",
    "ruled_out": "What makes a job not worth applying to.",
    "facts": "What employers ask about: eligibility, availability, notice, salary.",
    "writing": "How CVs and letters are written. Each rule is for all documents, the CV or the letter.",
    "working_with_me": "Instructions the agent follows when it works for you.",
}
Section = Literal["looking_for", "ruled_out", "facts", "writing", "working_with_me"]
Scope = Literal["all", "cv", "letter"]
MAX_TEXT = 2000
MAX_ITEMS = 200

SETTINGS_KEY = "workspace"
DEFAULT_REPLY_DAYS = 30
SETTINGS_DEFAULTS = {"no_reply_days": DEFAULT_REPLY_DAYS, "spoken_languages": []}
_CODE = re.compile(r"^[a-z]{2}$")


class PreferenceItem(Input):
    text: NonBlank = Field(min_length=1, max_length=MAX_TEXT, description="In the owner's words.")
    scope: Scope | None = Field(
        default=None,
        description="writing only: all, cv or letter; all when omitted.",
    )


class PreferencesUpdate(Input):
    """The whole new list of a section's statements, in order."""

    expected_version: int = Field(ge=0, strict=True, description="The section's current version.")
    items: list[PreferenceItem] = Field(
        max_length=MAX_ITEMS,
        description=f"The whole section, in order (each at most {MAX_TEXT} characters).",
    )


class SettingsUpdate(Input):
    """Omitted settings stay as they are."""

    expected_version: int = Field(
        ge=0, strict=True, description="The settings' version (0 before the first save)."
    )
    no_reply_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        strict=True,
        description="Days without an answer after which an application is overdue.",
    )
    spoken_languages: list[str] | None = Field(
        default=None,
        max_length=50,
        description="ISO 639-1 codes such as en or de.",
    )

    @field_validator("spoken_languages")
    @classmethod
    def codes(cls, value):
        if value is None:
            return value
        codes = normalize_languages([item for item in value if item.strip()])
        wrong = [code for code in codes if not _CODE.match(code)]
        if wrong:
            raise ValueError(
                "Use ISO 639-1 codes such as en, de or it; unknown: " + ", ".join(wrong) + "."
            )
        return codes

    @model_validator(mode="after")
    def no_nulls(self):
        for key in self.model_fields_set & {"no_reply_days", "spoken_languages"}:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null; omit it to keep the current value.")
        return self


def section_name(section):
    if section not in SECTIONS:
        raise DomainError(
            404, "not_found", "Preferences have the sections " + ", ".join(SECTIONS) + "."
        )
    return section


def _section_row(conn, section):
    row = conn.execute(
        "SELECT section,items,version,updated_at,updated_by FROM preference_sections WHERE section=?",
        (section,),
    ).fetchone()
    if row is None:  # a database written by hand; the schema inserts all five
        conn.execute("INSERT INTO preference_sections(section) VALUES(?)", (section,))
        return _section_row(conn, section)
    return row


def section_record(row):
    section = row[0]
    return {
        "section": section,
        "title": SECTION_TITLES[section],
        "description": SECTION_DESCRIPTIONS[section],
        "items": json.loads(row[1]),
        "version": row[2],
        "updated_at": row[3],
        "updated_by": row[4],
    }


def read_sections(conn):
    """Every section in display order."""
    rows = {
        row[0]: row
        for row in conn.execute(
            "SELECT section,items,version,updated_at,updated_by FROM preference_sections"
        )
    }
    return [
        section_record(rows[name] if name in rows else _section_row(conn, name))
        for name in SECTIONS
    ]


def settings_record(conn):
    """The two settings with their defaults and the setting's version."""
    row = conn.execute(
        "SELECT data,version,updated_at FROM settings WHERE key=?", (SETTINGS_KEY,)
    ).fetchone()
    data = json.loads(row[0]) if row else {}
    return {
        **SETTINGS_DEFAULTS,
        **{key: data[key] for key in SETTINGS_DEFAULTS if key in data},
        "version": row[1] if row else 0,
        "updated_at": row[2] if row else None,
    }


def spoken_languages(conn):
    return settings_record(conn)["spoken_languages"]


def no_reply_days(conn):
    """The no-reply period in days and where it comes from (``settings`` or ``default``)."""
    row = conn.execute("SELECT data FROM settings WHERE key=?", (SETTINGS_KEY,)).fetchone()
    days = json.loads(row[0]).get("no_reply_days") if row else None
    if isinstance(days, int) and not isinstance(days, bool) and days >= 1:
        return days, "settings"
    return DEFAULT_REPLY_DAYS, "default"


class PreferencesService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db

    def get_preferences(self) -> dict:
        """Read the owner's Preferences: the five sections with their statements and versions, and the settings (no-reply period, spoken languages)."""
        with self.db.connect() as conn:
            return {"sections": read_sections(conn), "settings": settings_record(conn)}

    def update_preferences(self, section: str, value: PreferencesUpdate) -> dict:
        """Replace a section's statements with the given list, naming the section's version."""
        section = section_name(section)
        value = (
            value
            if isinstance(value, PreferencesUpdate)
            else PreferencesUpdate.model_validate(value)
        )
        items = []
        for item in value.items:
            if section == "writing":
                items.append({"text": item.text, "scope": item.scope or "all"})
            elif item.scope is not None:
                raise DomainError(
                    422, "preferences_scope", "Only writing rules have a scope (all, cv or letter)."
                )
            else:
                items.append({"text": item.text})
        actor = current_actor()
        with self.db.transaction() as conn:
            row = _section_row(conn, section)
            if row[2] != value.expected_version:
                conflict(details={"current_version": row[2], "id": section, "section": section})
            if json.loads(row[1]) == items:
                return section_record(row)
            version = row[2] + 1
            conn.execute(
                "UPDATE preference_sections SET items=?,version=?,updated_at=?,updated_by=? "
                "WHERE section=?",
                (encode(items), version, now(), actor.label, section),
            )
            events.record(
                conn,
                "preferences_updated",
                subject=("preferences", section),
                payload={"section": section, "version": version, "items": len(items)},
            )
            return section_record(_section_row(conn, section))

    def update_settings(self, value: SettingsUpdate) -> dict:
        """Change the no-reply period or the spoken languages, naming the settings' version."""
        value = value if isinstance(value, SettingsUpdate) else SettingsUpdate.model_validate(value)
        changes = value.model_dump(exclude_unset=True, exclude={"expected_version"})
        with self.db.transaction() as conn:
            current = settings_record(conn)
            if current["version"] != value.expected_version:
                conflict(details={"current_version": current["version"], "id": "settings"})
            data = {key: current[key] for key in SETTINGS_DEFAULTS}
            merged = {**data, **changes}
            if merged == data:
                return current
            version = current["version"] + 1
            conn.execute(
                "INSERT INTO settings(key,data,version,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=excluded.version,"
                "updated_at=excluded.updated_at",
                (SETTINGS_KEY, encode(merged), version, now()),
            )
            events.record(
                conn,
                "settings_updated",
                subject=("settings", SETTINGS_KEY),
                payload={
                    "fields": sorted(key for key in merged if merged[key] != data[key]),
                    "version": version,
                },
            )
            return settings_record(conn)
