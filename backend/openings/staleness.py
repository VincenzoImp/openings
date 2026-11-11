"""Compare frozen contexts with the current Profile, instructions, templates and Career records.

Contexts stay immutable. This module only reads the versions they recorded and reports
which inputs changed since, so an agent can deliberately prepare a new context and
new document revisions.
"""

from __future__ import annotations

import json

from .snapshots import payload_text

INPUT_KINDS = ("profile", "instructions", "template", "knowledge", "claim")

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
    # before schema 10 froze no policy and keeps NULL. The report does not compare
    # them yet; they are recorded so that it can (staleness by section).
    "CASE WHEN json_type(?3,'$.policy')='object' THEN"
    " (SELECT json_group_object(key,json_extract(value,'$.version')) FROM json_each(?3,'$.policy')) END"
)
_COLUMNS = (
    "context_id,created_at,profile_version,instructions_version,templates,knowledge,claims,policy"
)


def store_context_inputs(connection, context_id, created_at, payload):
    """Record the input versions one context froze; parsing its payload once keeps reads cheap."""
    connection.execute(
        f"INSERT OR IGNORE INTO context_inputs({_COLUMNS}) " + _CONTEXT_INPUTS,
        (context_id, created_at, payload),
    )


def backfill_context_inputs(connection, where="", params=()):
    """Derive the summaries missing for contexts, rebuilding each payload from its parts."""
    missing = connection.execute(
        "SELECT id,created_at FROM contexts WHERE id NOT IN (SELECT context_id FROM context_inputs)"
        + where,
        params,
    ).fetchall()
    for context_id, created_at in missing:
        store_context_inputs(
            connection, context_id, created_at, payload_text(connection, context_id)
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


def _setting_version(connection, key):
    row = connection.execute("SELECT version FROM settings WHERE key=?", (key,)).fetchone()
    return row["version"] if row else 0


def context_changes(connection, context_ids) -> dict[str, dict]:
    """Return {context_id: {created_at, changes}} for the given frozen contexts."""
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

    frozen = read()
    if len(frozen) < len(context_ids):
        # Contexts restored or created without a summary: derive them once.
        backfill_context_inputs(
            connection, f" AND id IN ({_placeholders(context_ids)})", context_ids
        )
        connection.commit()
        frozen = read()
    for row in frozen:
        for key in ("templates", "knowledge", "claims"):
            row[key] = json.loads(row[key] or "[]")
    current = {
        "profile": _setting_version(connection, "profile"),
        "instructions": _setting_version(connection, "instructions"),
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
    result = {}
    for row in frozen:
        changes = []
        for kind in ("profile", "instructions"):
            before = row[f"{kind}_version"] or 0
            if current[kind] != before:
                changes.append(
                    {
                        "input": kind,
                        "id": None,
                        "label": kind.capitalize(),
                        "state": "changed",
                        "frozen_version": before,
                        "current_version": current[kind],
                    }
                )
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
                elif live["version"] != version:
                    state = "changed"
                if state:
                    changes.append(
                        {
                            "input": kind,
                            "id": identifier,
                            "label": label or "",
                            "state": state,
                            "frozen_version": version,
                            "current_version": live["version"] if live else None,
                        }
                    )
        result[row["id"]] = {"created_at": row["created_at"], "changes": changes}
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
        changes = frozen["changes"] if frozen else []
        report["documents"].append(
            {
                "document_id": leaf["id"],
                "kind": leaf["kind"],
                "title": leaf["title"],
                "review_state": leaf["review_state"],
                "context_id": leaf["context_id"],
                "context_created_at": frozen["created_at"] if frozen else None,
                "status": "no_context" if not frozen else "stale" if changes else "current",
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
