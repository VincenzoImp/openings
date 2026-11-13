"""Policy records as read: items, sections, the frozen policy and the signal registry."""

from __future__ import annotations

import json
import re

from ..actors import pop_actor
from ..errors import DomainError, conflict
from .models import SECTION_TITLES, SECTIONS, SIGNALS

ORIGIN_NOTES = {
    "profile_metadata": "Copied from Profile metadata in 0.19",
    "profile_preferences": "Copied from Profile preferences in 0.19",
    "profile_roles": "Copied from Profile roles in 0.19",
    "profile_preferences_removed": "Copied from Profile preferences when 0.23 removed the field",
    "profile_roles_removed": "Copied from Profile roles when 0.23 removed the field",
}


_ACTORS = ("created_by", "updated_by", "confirmed_by")


def label_from_key(key):
    """A readable label for a Profile metadata key: decision_policy -> Decision policy."""
    text = re.sub(r"[_\-\s]+", " ", str(key)).strip()
    return (text[:1].upper() + text[1:])[:200] or "Untitled"


def item_record(row):
    """A policy item as returned by reads."""
    row = dict(row)
    row["value"] = json.loads(row["value"]) if row["value"] is not None else None
    row["rule"] = json.loads(row["rule"]) if row["rule"] is not None else None
    row["enabled"] = bool(row["enabled"])
    row["confirmed"] = row["confirmed_at"] is not None
    for prefix in _ACTORS:
        actor = pop_actor(row, prefix)
        row[prefix] = None if actor["kind"] == "unknown" else actor
    origin, key = row.pop("origin"), row.pop("origin_key")
    row["origin"] = (
        {"source": origin, "key": key, "note": ORIGIN_NOTES.get(origin, "")} if origin else None
    )
    return row


def _items(conn, section):
    return [
        item_record(row)
        for row in conn.execute(
            "SELECT * FROM policy_items WHERE section=? ORDER BY position,created_at,id",
            (section,),
        )
    ]


def _section_row(conn, section):
    row = conn.execute("SELECT * FROM policy_sections WHERE section=?", (section,)).fetchone()
    if row is None:  # a database written by hand; the schema inserts all four
        conn.execute("INSERT INTO policy_sections(section) VALUES(?)", (section,))
        row = conn.execute("SELECT * FROM policy_sections WHERE section=?", (section,)).fetchone()
    return dict(row)


def section_record(conn, section):
    row = _section_row(conn, section)
    actor = pop_actor(row, "updated_by")
    items = _items(conn, section)
    return {
        "section": section,
        "description": SECTION_TITLES[section],
        "version": row["version"],
        "updated_at": row["updated_at"],
        "updated_by": None if actor["kind"] == "unknown" else actor,
        "items": items,
        "total": len(items),
        "unconfirmed": sum(not item["confirmed"] for item in items),
    }


def frozen_policy(conn):
    """The four sections as a context freezes them: version and items.

    Two queries for the whole policy: this runs for every prepared context. An
    item keeps what an agent writes from; an unconfirmed item says so.
    """
    versions = dict(
        tuple(row) for row in conn.execute("SELECT section,version FROM policy_sections")
    )
    frozen = {section: {"version": versions.get(section, 0), "items": []} for section in SECTIONS}
    for row in conn.execute(
        "SELECT section,id,label,statement,value,value_type,note,scope,rule,enabled,"
        "confirmed_at,origin,origin_key FROM policy_items ORDER BY section,position,created_at,id"
    ):
        section, value, rule, confirmed_at, origin = row[0], row[4], row[8], row[10], row[11]
        frozen[section]["items"].append(
            {
                "id": row[1],
                "label": row[2],
                "statement": row[3],
                "value": json.loads(value) if value is not None else None,
                "value_type": row[5],
                "note": row[6],
                "scope": row[7],
                "rule": json.loads(rule) if rule is not None else None,
                "enabled": bool(row[9]),
                "confirmed": confirmed_at is not None,
                "confirmed_at": confirmed_at,
                "origin": {"source": origin, "key": row[12], "note": ORIGIN_NOTES.get(origin, "")}
                if origin
                else None,
            }
        )
    return frozen


def signal_registry():
    return [
        {
            "signal": name,
            "label": signal["label"],
            "description": signal["description"],
            "operators": [
                {"operator": operator, "value_type": kind}
                for operator, kind in signal["operators"].items()
            ],
        }
        for name, signal in SIGNALS.items()
    ]


def _section_name(section):
    if section not in SECTIONS:
        raise DomainError(
            404,
            "not_found",
            "The policy has the sections decision, eligibility, writing and facts.",
        )
    return section


def _check(row, expected):
    if row["version"] != expected:
        conflict(details={"current_version": row["version"], "section": row["section"]})


def _shape(section, scope, rule, enabled):
    """The section-specific fields of an item, or a refusal."""
    if section != "writing" and scope is not None:
        raise DomainError(422, "policy_scope", "Only writing items have a scope.")
    if section != "decision" and rule is not None:
        raise DomainError(422, "policy_rule", "Only decision items carry a signal rule.")
    if enabled and rule is None:
        raise DomainError(422, "policy_rule", "Only an item with a signal rule can be enabled.")
    return ("all" if scope is None else scope) if section == "writing" else None
