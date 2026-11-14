"""Compare frozen contexts with the current Profile, Preferences, templates and Career.

Contexts stay immutable. This module only reads what they recorded and reports which
inputs changed since, so an agent can deliberately prepare a new context and new
document revisions.

A context records the versions it froze and, in ``context_inputs.parts``, a short hash
of each part: each Profile part, each Preferences statement and the content of each
template, Career entry and claim. The report compares only what documents use: the
Profile parts of a CV or letter header and summary, the statements of the
Preferences sections ``facts`` and ``writing``, a template's source, guidance and
rules, an entry's kind, title, organization, dates, skills and narrative, and a
claim's wording and entry. Profile ``metadata``, the other Preferences sections,
names, positions, default flags, claim selection fields and free-form metadata are
frozen as well but never make a document stale, and neither does a new version whose
content is the same. Text is compared with its runs of whitespace made single spaces,
except a template's source. A statement is identified by its content: an edited one
is reported as removed and added. A writing rule scoped to the CV or the letter
concerns that document only. Contexts frozen before 0.24 (with the rules and general
instructions of that time) compare only their Profile and records.
"""

from __future__ import annotations

import hashlib
import json

from .career import DEFAULT_PROFILE
from .db import encode
from .snapshots import payload_text

INPUT_KINDS = ("profile", "preferences", "template", "knowledge", "claim")

# Each Profile part with its plain name and the fields it covers.
PROFILE_PARTS = {
    "name": ("Name", ("name",)),
    "headline": ("Headline", ("headline",)),
    "contact": ("Contact details", ("email", "phone", "location")),
    "links": ("Links", ("links",)),
    "summary": ("Summary", ("summary",)),
    "metadata": ("Metadata", ("metadata",)),
}
# The parts a CV or letter uses. Metadata holds free-form extension values that
# documents do not use. (The preferences and roles parts that contexts frozen before
# 0.23 stored are never compared.)
DOCUMENT_PROFILE_PARTS = ("name", "headline", "contact", "links", "summary")
# The Preferences sections documents use.
DOCUMENT_SECTIONS = ("facts", "writing")
# The content of a frozen record that documents use, with the value a missing field
# counts as. Names, positions, default flags, claim selection fields (they rank claims
# for the next selection) and free-form metadata (provenance) do not reach a document.
RECORD_FIELDS = {
    "template": {"kind": None, "tex": "", "guidance": "", "rules": {}},
    "knowledge": {
        "kind": None,
        "title": "",
        "organization": "",
        "dates": None,
        "skills": [],
        "narrative": "",
    },
    "claim": {"knowledge_id": None, "text": ""},
}
# Where each kind is frozen in the payload and stored live, and its JSON columns.
RECORD_SOURCES = {
    "template": ("templates", "templates", ("rules",)),
    "knowledge": ("knowledge", "knowledge", ("dates", "skills")),
    "claim": ("claims", "claims", ()),
}
# The document kind a writing scope concerns; "all" concerns every kind.
SCOPE_KINDS = {"cv": "cv", "letter": "letter"}
# Bump when the stored parts change shape: rows of another format are derived again.
PARTS_FORMAT = 3
LABEL_CHARS = 120

_CONTEXT_INPUTS = (
    "SELECT ?1,?2,"
    "json_extract(?3,'$.profile.version'),"
    "(SELECT json_group_array(json_array(json_extract(value,'$.id'),json_extract(value,'$.version'),json_extract(value,'$.name')))"
    " FROM json_each(?3,'$.templates')),"
    "(SELECT json_group_array(json_array(json_extract(value,'$.id'),json_extract(value,'$.version'),json_extract(value,'$.title')))"
    " FROM json_each(?3,'$.knowledge')),"
    "(SELECT json_group_array(json_array(json_extract(value,'$.id'),json_extract(value,'$.version'),substr(json_extract(value,'$.text'),1,120)))"
    " FROM json_each(?3,'$.claims')),"
    "?4"
)
_COLUMNS = "context_id,created_at,profile_version,templates,knowledge,claims,parts"
_UNSPLIT = {
    "format": PARTS_FORMAT,
    "profile": None,
    "preferences": None,
    "templates": {},
    "knowledge": {},
    "claims": {},
}


def digest(value) -> str:
    """A short hash of one value's canonical JSON: enough to tell two versions apart."""
    return hashlib.sha256(encode(value).encode()).hexdigest()[:16]


# Source text, where spacing can matter; every other text is compared as prose.
VERBATIM = {"tex"}


def _content(fields):
    """Fields as compared: prose with its runs of whitespace made single spaces."""
    return {
        name: " ".join(value.split()) if isinstance(value, str) and name not in VERBATIM else value
        for name, value in fields.items()
    }


def profile_hashes(profile: dict) -> dict:
    """The hash of every Profile part; a field the Profile lacks counts as its default."""
    return {
        part: digest(_content({name: profile.get(name, DEFAULT_PROFILE[name]) for name in names}))
        for part, (_, names) in PROFILE_PARTS.items()
    }


def statement_hash(item: dict) -> str:
    """The hash of one Preferences statement: its text and, for a writing rule, its scope."""
    return digest(_content({"text": item.get("text"), "scope": item.get("scope")}))


def _statements(sections) -> dict:
    """{section: {version, items: [[hash, label, scope], ...]}} of the sections documents use."""
    result = {}
    for section in DOCUMENT_SECTIONS:
        value = sections.get(section)
        if not isinstance(value, dict):
            continue
        result[section] = {
            "version": value.get("version"),
            "items": [
                [statement_hash(item), str(item.get("text") or "")[:LABEL_CHARS], item.get("scope")]
                for item in value.get("items") or ()
                if isinstance(item, dict)
            ],
        }
    return result


def record_hash(kind: str, record: dict) -> str:
    """The hash of what documents use of one template, Career entry or claim."""
    return digest(
        _content({name: record.get(name, default) for name, default in RECORD_FIELDS[kind].items()})
    )


def _record_hashes(kind, items):
    if not isinstance(items, list):
        return {}
    return {
        item["id"]: record_hash(kind, item)
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def frozen_parts(text: str) -> dict:
    """The part hashes of one payload; a payload that cannot be read keeps none of them."""
    try:
        data = json.loads(text)
    except ValueError:
        return dict(_UNSPLIT)
    if not isinstance(data, dict):
        return dict(_UNSPLIT)
    try:
        profile = data.get("profile")
        preferences = data.get("preferences")
        return {
            "format": PARTS_FORMAT,
            "profile": profile_hashes(profile) if isinstance(profile, dict) else None,
            "preferences": _statements(preferences) if isinstance(preferences, dict) else None,
            **{
                key: _record_hashes(kind, data.get(key))
                for kind, (key, _, _) in RECORD_SOURCES.items()
            },
        }
    except TypeError, ValueError, AttributeError:
        return dict(_UNSPLIT)


def store_context_inputs(connection, context_id, created_at, payload):
    """Record the inputs one context froze; parsing its payload once keeps reads cheap."""
    # A payload SQLite cannot read records no version, so it compares as changed.
    readable = connection.execute("SELECT json_valid(?)", (payload,)).fetchone()[0]
    connection.execute(
        f"INSERT OR IGNORE INTO context_inputs({_COLUMNS}) " + _CONTEXT_INPUTS,
        (context_id, created_at, payload if readable else "{}", encode(frozen_parts(payload))),
    )


def _has_parts_column(connection):
    return any(row[1] == "parts" for row in connection.execute("PRAGMA table_info(context_inputs)"))


def backfill_context_inputs(connection, context_ids=None):
    """Derive what is missing for contexts, rebuilding each payload from its parts.

    A context without a row gets one; a row without part hashes (written before they
    existed, or in another format) gets them from the same frozen payload.
    """
    if not _has_parts_column(connection):
        # A workspace written before part hashes: the table is derived, so it only grows.
        connection.execute("ALTER TABLE context_inputs ADD COLUMN parts TEXT")
    within, params = "", []
    if context_ids is not None:
        params = list(context_ids)
        within = f" IN ({_placeholders(params)})"
    missing = connection.execute(
        "SELECT id,created_at FROM contexts WHERE id NOT IN (SELECT context_id FROM context_inputs)"
        + (" AND id" + within if within else ""),
        params,
    ).fetchall()
    for context_id, created_at in missing:
        store_context_inputs(
            connection, context_id, created_at, payload_text(connection, context_id)
        )
    outdated = connection.execute(
        "SELECT context_id FROM context_inputs WHERE (parts IS NULL "
        "OR json_extract(parts,'$.format') IS NOT ?)"
        + (" AND context_id" + within if within else ""),
        [PARTS_FORMAT, *params],
    ).fetchall()
    for (context_id,) in outdated:
        connection.execute(
            "UPDATE context_inputs SET parts=? WHERE context_id=?",
            (encode(frozen_parts(payload_text(connection, context_id))), context_id),
        )


def _placeholders(values):
    return ",".join("?" for _ in values)


def _current_versions(connection, table, identifiers, extra=""):
    if not identifiers:
        return {}
    return {
        row["id"]: dict(row)
        for row in connection.execute(
            f"SELECT id,version{extra} FROM {table} WHERE id IN ({_placeholders(identifiers)})",
            list(identifiers),
        )
    }


def _setting(connection, key):
    row = connection.execute("SELECT data,version FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        return {}, 0
    try:
        data = json.loads(row["data"])
    except ValueError:
        data = {}
    return (data if isinstance(data, dict) else {}), row["version"]


def _current_preferences(connection):
    """The statements of the sections documents use, as ``_statements`` reads them."""
    return _statements(
        {
            row[0]: {"version": row[2], "items": json.loads(row[1])}
            for row in connection.execute(
                "SELECT section,items,version FROM preference_sections WHERE section IN "
                f"({_placeholders(DOCUMENT_SECTIONS)})",
                DOCUMENT_SECTIONS,
            )
        }
    )


def _change(kind, identifier, label, state, before, after, **more):
    return {
        "input": kind,
        "id": identifier,
        "label": label or "",
        "state": state,
        "frozen_version": before,
        "current_version": after,
        **more,
    }


def _profile_changes(row, parts, current):
    hashes, version = current
    frozen = parts.get("profile")
    before = row["profile_version"] or 0
    if frozen is None:
        # The frozen Profile could not be read by part: compare the whole version.
        return (
            []
            if version == before
            else [_change("profile", None, "Profile", "changed", before, version)]
        )
    return [
        _change("profile", part, PROFILE_PARTS[part][0], "changed", before, version)
        for part in DOCUMENT_PROFILE_PARTS
        if frozen.get(part) != hashes[part]
    ]


def _preference_changes(parts, current):
    """Statements added to or removed from facts and writing since the context froze them."""
    frozen = parts.get("preferences")
    if frozen is None:
        return []
    changes = []
    for section in DOCUMENT_SECTIONS:
        then, now = frozen.get(section) or {}, current.get(section) or {}
        before, after = then.get("version"), now.get("version", 0)
        then_items, now_items = then.get("items") or [], now.get("items") or []
        then_hashes = {item[0] for item in then_items}
        now_hashes = {item[0] for item in now_items}
        for state, items, other in (
            ("added", now_items, then_hashes),
            ("removed", then_items, now_hashes),
        ):
            for digest_, label, scope in items:
                if digest_ not in other:
                    changes.append(
                        _change(
                            "preferences",
                            f"{section}:{digest_}",
                            label,
                            state,
                            before,
                            after,
                            section=section,
                            _scopes={scope},
                        )
                    )
    return changes


def _concerns(change, kind):
    """Whether a change concerns one document kind: only a scoped writing item may not."""
    scopes = change.get("_scopes")
    if not scopes or None in scopes or "all" in scopes:
        return True
    return any(SCOPE_KINDS.get(scope) == kind for scope in scopes)


def _current_hashes(connection, kind, identifiers):
    """The content hashes of live records of one kind."""
    if not identifiers:
        return {}
    _, table, json_columns = RECORD_SOURCES[kind]
    names = ",".join(f'"{name}"' for name in RECORD_FIELDS[kind])
    result = {}
    for row in connection.execute(
        f"SELECT id,{names} FROM {table} WHERE id IN ({_placeholders(identifiers)})",
        list(identifiers),
    ):
        record = dict(row)
        for name in json_columns:
            if record[name] is not None:
                record[name] = json.loads(record[name])
        result[record.pop("id")] = record_hash(kind, record)
    return result


def context_changes(connection, context_ids) -> dict[str, dict]:
    """Return {context_id: {created_at, changes, comparison}} for the given frozen contexts.

    A Preferences change carries ``_scopes``, the writing scopes it concerns, until
    ``application_staleness`` applies them to each document kind.
    """
    context_ids = list(dict.fromkeys(identifier for identifier in context_ids if identifier))
    if not context_ids:
        return {}

    def read():
        return [
            dict(row, id=row["context_id"])
            for row in connection.execute(
                f"SELECT {_COLUMNS} FROM context_inputs WHERE context_id IN "
                f"({_placeholders(context_ids)})",
                context_ids,
            )
        ]

    def complete(row):
        try:
            return json.loads(row["parts"] or "null")["format"] == PARTS_FORMAT
        except TypeError, KeyError, ValueError:
            return False

    frozen = read()
    if len(frozen) < len(context_ids) or not all(map(complete, frozen)):
        # Contexts restored, created or stored without their summaries: derive them once.
        backfill_context_inputs(connection, context_ids)
        connection.commit()
        frozen = read()
    for row in frozen:
        for key in ("templates", "knowledge", "claims"):
            row[key] = json.loads(row[key] or "[]")
        row["parts"] = json.loads(row["parts"])
    profile, profile_version = _setting(connection, "profile")
    current = {
        "profile": (profile_hashes({**DEFAULT_PROFILE, **profile}), profile_version),
        "preferences": _current_preferences(connection)
        if any(row["parts"].get("preferences") is not None for row in frozen)
        else {},
        "template": _current_versions(
            connection, "templates", {item[0] for row in frozen for item in row["templates"]}
        ),
        "knowledge": _current_versions(
            connection, "knowledge", {item[0] for row in frozen for item in row["knowledge"]}
        ),
        "claim": _current_versions(
            connection,
            "claims",
            {item[0] for row in frozen for item in row["claims"]},
            ",approved",
        ),
    }
    # A record whose version moved may have changed only what documents do not use.
    hashes = {
        kind: _current_hashes(
            connection,
            kind,
            {
                identifier
                for row in frozen
                for identifier, version, _ in row[RECORD_SOURCES[kind][0]]
                if identifier in current[kind] and current[kind][identifier]["version"] != version
            },
        )
        for kind in RECORD_SOURCES
    }
    result = {}
    for row in frozen:
        parts = row["parts"]
        changes = _profile_changes(row, parts, current["profile"])
        changes += _preference_changes(parts, current["preferences"])
        for kind, (key, _, _) in RECORD_SOURCES.items():
            frozen_hashes = parts.get(key) or {}
            for identifier, version, label in row[key]:
                live = current[kind].get(identifier)
                state = None
                if live is None:
                    state = "deleted"
                elif kind == "claim" and not live["approved"]:
                    state = "unapproved"
                elif live["version"] != version and (
                    frozen_hashes.get(identifier) is None
                    or frozen_hashes[identifier] != hashes[kind].get(identifier)
                ):
                    state = "changed"
                if state:
                    changes.append(
                        _change(
                            kind,
                            identifier,
                            label,
                            state,
                            version,
                            live["version"] if live else None,
                        )
                    )
        result[row["id"]] = {
            "created_at": row["created_at"],
            "changes": changes,
            "comparison": {
                "profile": "whole" if parts.get("profile") is None else "parts",
                "preferences": "not_frozen" if parts.get("preferences") is None else "items",
            },
        }
    return result


def application_staleness(connection, application_ids) -> dict[str, dict]:
    """Report, per application, whether its current revision leaves use outdated contexts.

    A current leaf is a revision without a child revision. Leaves without a context have
    no recorded inputs and are reported with status ``no_context``.
    """
    application_ids = list(dict.fromkeys(application_ids))
    result = {
        identifier: {"stale": False, "inputs": [], "documents": [], "changes": []}
        for identifier in application_ids
    }
    if not application_ids:
        return result
    leaves = [
        dict(row)
        for row in connection.execute(
            "SELECT d.id,d.application_id,d.context_id,d.kind,d.title,d.created_at "
            f"FROM documents d WHERE d.application_id IN ({_placeholders(application_ids)}) "
            "AND NOT EXISTS(SELECT 1 FROM documents child WHERE child.previous_id=d.id) "
            "ORDER BY d.kind,d.created_at,d.id",
            application_ids,
        )
    ]
    contexts = context_changes(connection, [leaf["context_id"] for leaf in leaves])
    for leaf in leaves:
        report = result[leaf["application_id"]]
        frozen = contexts.get(leaf["context_id"]) if leaf["context_id"] else None
        changes = [
            {key: value for key, value in item.items() if key != "_scopes"}
            for item in (frozen["changes"] if frozen else [])
            if _concerns(item, leaf["kind"])
        ]
        report["documents"].append(
            {
                "document_id": leaf["id"],
                "kind": leaf["kind"],
                "title": leaf["title"],
                "context_id": leaf["context_id"],
                "context_created_at": frozen["created_at"] if frozen else None,
                "status": "no_context" if not frozen else "stale" if changes else "current",
                "comparison": frozen["comparison"] if frozen else None,
                "changes": changes,
            }
        )
        if changes:
            report["stale"] = True
            known = {(item["input"], item["id"]) for item in report["changes"]}
            report["changes"].extend(
                item for item in changes if (item["input"], item["id"]) not in known
            )
    for report in result.values():
        present = {item["input"] for item in report["changes"]}
        report["inputs"] = [kind for kind in INPUT_KINDS if kind in present]
    return result


# Changes an application summary names; the per-application report has them all.
SUMMARY_CHANGES = 3


def stale_summary(report: dict) -> dict:
    """The staleness fields of an application read or list item."""
    return {
        "stale_inputs": report["inputs"],
        "stale_changes": report["changes"][:SUMMARY_CHANGES],
        "stale_changes_total": len(report["changes"]),
    }
