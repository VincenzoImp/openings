"""Compare frozen contexts with the current Profile, policy, instructions, templates and Career.

Contexts stay immutable. This module only reads what they recorded and reports which
inputs changed since, so an agent can deliberately prepare a new context and new
document revisions.

A context records the versions it froze and, in ``context_inputs.parts``, a short hash
of each part: each Profile part, each policy item and each template's content. The
report compares only what documents use: the Profile parts of a CV or letter header
and summary, and the confirmed items of the policy sections ``eligibility``,
``writing`` and ``facts``. Profile ``metadata``, ``preferences`` and ``roles`` and the
``decision`` section are frozen as well, but choosing jobs is their purpose, so editing
them leaves every Draft current. A writing item scoped to the CV or the letter
concerns that document only.
"""

from __future__ import annotations

import hashlib
import json

from .career import DEFAULT_PROFILE
from .db import encode
from .snapshots import payload_text

INPUT_KINDS = ("profile", "policy", "instructions", "template", "knowledge", "claim")

# Each Profile part with its plain name and the fields it covers.
PROFILE_PARTS = {
    "name": ("Name", ("name",)),
    "headline": ("Headline", ("headline",)),
    "contact": ("Contact details", ("email", "phone", "location")),
    "links": ("Links", ("links",)),
    "summary": ("Summary", ("summary",)),
    "preferences": ("Preferences", ("preferences",)),
    "roles": ("Target roles", ("roles",)),
    "metadata": ("Metadata", ("metadata",)),
}
# The parts a CV or letter uses. Preferences and roles became decision items of the
# policy in 0.19 and metadata holds free-form extension values; documents use neither.
DOCUMENT_PROFILE_PARTS = ("name", "headline", "contact", "links", "summary")
# Decision items shortlist and dismiss jobs; documents use the other sections.
DOCUMENT_POLICY_SECTIONS = ("eligibility", "writing", "facts")
# An item's content: what a write changes when it unconfirms an item (policy.CONTENT_FIELDS).
POLICY_ITEM_FIELDS = ("label", "statement", "value", "value_type", "scope", "rule")
# A template's content; its name and default flag do not reach a document.
TEMPLATE_FIELDS = ("kind", "tex", "guidance", "rules")
# The document kind a writing scope concerns; "all" concerns every kind.
SCOPE_KINDS = {"cv": "resume", "letter": "cover_letter"}
# Bump when the stored parts change shape: rows of another format are derived again.
PARTS_FORMAT = 1
LABEL_CHARS = 120

_CONTEXT_INPUTS = (
    "SELECT ?1,?2,"
    "json_extract(?3,'$.profile.version'),"
    "json_extract(?3,'$.instructions.version'),"
    "(SELECT json_group_array(json_array(json_extract(value,'$.id'),json_extract(value,'$.version'),json_extract(value,'$.name')))"
    " FROM json_each(?3,'$.templates')),"
    "(SELECT json_group_array(json_array(json_extract(value,'$.id'),json_extract(value,'$.version'),json_extract(value,'$.title')))"
    " FROM json_each(?3,'$.knowledge')),"
    "(SELECT json_group_array(json_array(json_extract(value,'$.id'),json_extract(value,'$.version'),substr(json_extract(value,'$.text'),1,120)))"
    " FROM json_each(?3,'$.claims')),"
    # The policy section versions a context froze, {"decision":3,...}. A context from
    # before schema 10 froze no policy and keeps NULL.
    "CASE WHEN json_type(?3,'$.policy')='object' THEN"
    " (SELECT json_group_object(key,json_extract(value,'$.version')) FROM json_each(?3,'$.policy')) END,"
    "?4"
)
_COLUMNS = (
    "context_id,created_at,profile_version,instructions_version,templates,knowledge,claims,"
    "policy,parts"
)
_UNSPLIT = {"format": PARTS_FORMAT, "profile": None, "policy": None, "templates": {}}


def digest(value) -> str:
    """A short hash of one value's canonical JSON: enough to tell two versions apart."""
    return hashlib.sha256(encode(value).encode()).hexdigest()[:16]


def profile_hashes(profile: dict) -> dict:
    """The hash of every Profile part; a field the Profile lacks counts as its default."""
    return {
        part: digest({name: profile.get(name, DEFAULT_PROFILE[name]) for name in names})
        for part, (_, names) in PROFILE_PARTS.items()
    }


def policy_item_hash(item: dict) -> str:
    return digest({name: item.get(name) for name in POLICY_ITEM_FIELDS})


def template_hash(template: dict) -> str:
    return digest({name: template.get(name) for name in TEMPLATE_FIELDS})


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
        policy = data.get("policy")
        templates = data.get("templates")
        return {
            "format": PARTS_FORMAT,
            "profile": profile_hashes(profile) if isinstance(profile, dict) else None,
            # [id, hash, label, scope, confirmed] for each item of each section.
            "policy": {
                section: [
                    [
                        item["id"],
                        policy_item_hash(item),
                        str(item.get("label") or "")[:LABEL_CHARS],
                        item.get("scope"),
                        int(item.get("confirmed") is True),
                    ]
                    for item in value.get("items") or ()
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                ]
                for section, value in policy.items()
                if isinstance(value, dict)
            }
            if isinstance(policy, dict)
            else None,
            "templates": {
                item["id"]: template_hash(item)
                for item in templates
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            if isinstance(templates, list)
            else {},
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


def _current_policy(connection):
    """Section versions and the confirmed items of the sections documents use."""
    versions = dict(
        tuple(row) for row in connection.execute("SELECT section,version FROM policy_sections")
    )
    items = {}
    for row in connection.execute(
        "SELECT section,id,label,statement,value,value_type,scope,rule,confirmed_at "
        "FROM policy_items WHERE section IN "
        f"({_placeholders(DOCUMENT_POLICY_SECTIONS)}) ORDER BY section,position,created_at,id",
        DOCUMENT_POLICY_SECTIONS,
    ):
        item = dict(row)
        for name in ("value", "rule"):
            item[name] = json.loads(item[name]) if item[name] is not None else None
        items[item["id"]] = {
            "section": item["section"],
            "hash": policy_item_hash(item),
            "label": item["label"],
            "scope": item["scope"],
            "confirmed": item["confirmed_at"] is not None,
        }
    return versions, items


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


def _policy_changes(row, parts, current):
    versions, items = current
    frozen_sections = parts.get("policy")
    if frozen_sections is None:
        return []
    frozen_versions = json.loads(row["policy"] or "{}")
    frozen = {
        identifier: {
            "section": section,
            "hash": digest_,
            "label": label,
            "scope": scope,
            "confirmed": bool(confirmed),
        }
        for section in DOCUMENT_POLICY_SECTIONS
        for identifier, digest_, label, scope, confirmed in frozen_sections.get(section) or ()
    }

    def change(identifier, item, state, scopes):
        section = item["section"]
        return _change(
            "policy",
            identifier,
            item["label"],
            state,
            frozen_versions.get(section),
            versions.get(section, 0),
            section=section,
            _scopes=scopes,
        )

    changes = []
    for identifier, now in items.items():
        then = frozen.get(identifier)
        used_then = bool(then and then["confirmed"])
        if not now["confirmed"]:
            if used_then:
                changes.append(
                    change(identifier, now, "unconfirmed", {then["scope"], now["scope"]})
                )
        elif not used_then:
            changes.append(
                change(identifier, now, "confirmed" if then else "added", {now["scope"]})
            )
        elif then["hash"] != now["hash"]:
            changes.append(change(identifier, now, "changed", {then["scope"], now["scope"]}))
    for identifier, then in frozen.items():
        if then["confirmed"] and identifier not in items:
            changes.append(change(identifier, then, "removed", {then["scope"]}))
    return changes


def _concerns(change, kind):
    """Whether a change concerns one document kind: only a scoped writing item may not."""
    scopes = change.get("_scopes")
    if not scopes or None in scopes or "all" in scopes:
        return True
    return any(SCOPE_KINDS.get(scope) == kind for scope in scopes)


def context_changes(connection, context_ids) -> dict[str, dict]:
    """Return {context_id: {created_at, changes, comparison}} for the given frozen contexts.

    A policy change carries ``_scopes``, the writing scopes it concerns, until
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
        "policy": _current_policy(connection)
        if any(row["parts"].get("policy") is not None for row in frozen)
        else ({}, {}),
        "instructions": _setting(connection, "instructions")[1],
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
    # A template whose version moved may only have changed name or default flag.
    moved = {
        identifier
        for row in frozen
        for identifier, version, _ in row["templates"]
        if identifier in current["template"]
        and current["template"][identifier]["version"] != version
    }
    template_hashes = {
        row["id"]: template_hash(dict(row, rules=json.loads(row["rules"] or "{}")))
        for row in (
            connection.execute(
                f"SELECT id,kind,tex,guidance,rules FROM templates WHERE id IN ({_placeholders(moved)})",
                list(moved),
            )
            if moved
            else ()
        )
    }
    result = {}
    for row in frozen:
        parts = row["parts"]
        changes = _profile_changes(row, parts, current["profile"])
        changes += _policy_changes(row, parts, current["policy"])
        before = row["instructions_version"] or 0
        if current["instructions"] != before:
            changes.append(
                _change(
                    "instructions",
                    None,
                    "Instructions",
                    "changed",
                    before,
                    current["instructions"],
                )
            )
        frozen_templates = parts.get("templates") or {}
        for kind, key in (
            ("template", "templates"),
            ("knowledge", "knowledge"),
            ("claim", "claims"),
        ):
            for identifier, version, label in row[key]:
                live = current[kind].get(identifier)
                state = None
                if live is None:
                    state = "deleted"
                elif kind == "claim" and not live["approved"]:
                    state = "unapproved"
                elif live["version"] != version and not (
                    kind == "template"
                    and frozen_templates.get(identifier) is not None
                    and frozen_templates[identifier] == template_hashes.get(identifier)
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
                "policy": "not_frozen" if parts.get("policy") is None else "items",
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
            "SELECT d.id,d.application_id,d.context_id,d.kind,d.title,d.review_state,d.created_at "
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
                "review_state": leaf["review_state"],
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
