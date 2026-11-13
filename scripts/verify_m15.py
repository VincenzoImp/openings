"""Aggregates of a schema-14 workspace copy for the 0.24 upgrade rehearsal.

    uv run python scripts/verify_m15.py /private/copy/openings.sqlite [--upgrade]

Prints numbers only: row counts, non-default counts of columns, states and
sizes. It never prints a record's content (no text, names, labels or ids), so
its output can be kept in the plan log. The database is opened read-only.

With ``--upgrade`` the copy is also upgraded, in a private temporary folder that
is removed afterwards: the time it took, the archive counts and the sizes.

Each change of the unreleased migration adds the aggregates of the columns it
drops or folds to ``PLANNED`` (or a block to ``extra``).
"""

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from openings.migrations import m15

# Aggregates the removals of 0.24 depend on: (label, SQL returning one number).
PLANNED = (
    # #209 agent collaboration layer
    ("runs", "SELECT count(*) FROM runs"),
    ("events with a run", "SELECT count(*) FROM events WHERE run_id IS NOT NULL"),
    ("notes with a run", "SELECT count(*) FROM notes WHERE run_id IS NOT NULL"),
    ("skill note versions", "SELECT count(*) FROM skill_notes"),
    ("skills with notes", "SELECT count(DISTINCT skill) FROM skill_notes"),
    # #213 Preferences
    (
        "policy items with a typed value",
        "SELECT count(*) FROM policy_items WHERE value IS NOT NULL",
    ),
    ("policy items with a rule", "SELECT count(*) FROM policy_items WHERE rule IS NOT NULL"),
    ("policy items with an enabled rule", "SELECT count(*) FROM policy_items WHERE enabled=1"),
    (
        "policy decision items whose rule dismisses",
        (
            "SELECT count(*) FROM policy_items WHERE section='decision' AND rule IS NOT NULL "
            "AND json_extract(rule,'$.action')='dismiss'"
        ),
    ),
    ("policy items not confirmed", "SELECT count(*) FROM policy_items WHERE confirmed_at IS NULL"),
    ("policy items with a note", "SELECT count(*) FROM policy_items WHERE note<>''"),
    ("policy items with an origin", "SELECT count(*) FROM policy_items WHERE origin IS NOT NULL"),
    (
        "policy items labelled no reply",
        (
            "SELECT count(*) FROM policy_items WHERE lower(label) LIKE '%no reply%' "
            "OR lower(label) LIKE '%no response%'"
        ),
    ),
    (
        "jobs dismissed by a rule",
        (
            "SELECT count(*) FROM jobs WHERE dismissed_rule_id IS NOT NULL "
            "OR dismissed_rule_label IS NOT NULL"
        ),
    ),
    (
        "jobs dismissed by a rule without a reason",
        "SELECT count(*) FROM jobs WHERE dismissed_rule_label IS NOT NULL AND dismissed_reason=''",
    ),
    ("job signals with matched rules", "SELECT count(*) FROM job_signals WHERE rules<>'[]'"),
    (
        "template rule statements",
        (
            "SELECT coalesce(sum(json_array_length(rules,'$.statements')),0) FROM templates "
            "WHERE json_valid(rules) AND json_type(rules,'$.statements')='array'"
        ),
    ),
    (
        "general instructions characters",
        (
            "SELECT coalesce(sum(length(json_extract(data,'$.general'))),0) FROM settings "
            "WHERE key='instructions' AND json_valid(data)"
        ),
    ),
    (
        "policy items longer than 2000 characters as text",
        "SELECT count(*) FROM policy_items WHERE length(label)+length(statement)+length(note)>1900",
    ),
    (
        "policy items per section above 200",
        (
            "SELECT count(*) FROM (SELECT section FROM policy_items GROUP BY section "
            "HAVING count(*)>200)"
        ),
    ),
    (
        "language rules (spoken languages)",
        (
            "SELECT count(*) FROM policy_items WHERE section='decision' AND json_valid(rule) "
            "AND json_extract(rule,'$.signal')='language_required' "
            "AND json_extract(rule,'$.condition.operator')='not_in'"
        ),
    ),
    # #214 applications and documents
    (
        "applications with a stored Ready mark",
        "SELECT count(*) FROM applications WHERE ready_at IS NOT NULL",
    ),
    (
        "shortlisted jobs without an open application",
        (
            "SELECT count(*) FROM jobs j WHERE triage='saved' AND NOT EXISTS(SELECT 1 FROM "
            "applications a WHERE a.job_id=j.id AND a.status<>'closed')"
        ),
    ),
    (
        "CV and letter revisions with a PDF (complete in 0.24)",
        (
            "SELECT count(*) FROM documents d WHERE kind IN ('resume','cover_letter') AND "
            "EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id AND f.media_type='application/pdf')"
        ),
    ),
    (
        "CV and letter revisions without a PDF",
        (
            "SELECT count(*) FROM documents d WHERE kind IN ('resume','cover_letter') AND NOT "
            "EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id AND f.media_type='application/pdf')"
        ),
    ),
    (
        "revisions with a PDF and no text",
        (
            "SELECT count(*) FROM documents d WHERE text IS NULL AND EXISTS(SELECT 1 FROM files f "
            "WHERE f.document_id=d.id AND f.media_type='application/pdf')"
        ),
    ),
    ("responses", "SELECT count(*) FROM responses"),
    # #215 contexts and staleness
    ("contexts", "SELECT count(*) FROM contexts"),
    ("documents with a context", "SELECT count(*) FROM documents WHERE context_id IS NOT NULL"),
    (
        "documents with legacy content",
        "SELECT count(*) FROM documents WHERE legacy_content IS NOT NULL",
    ),
    ("legacy content bytes", "SELECT total(length(legacy_content)) FROM documents"),
    (
        "context bytes (frames and snapshot parts)",
        (
            "SELECT (SELECT total(length(frame)) FROM contexts)+(SELECT total(length(content)) "
            "FROM snapshot_parts)"
        ),
    ),
    ("context files", "SELECT count(*) FROM context_parts WHERE file_id IS NOT NULL"),
    (
        "blob bytes referenced only by context files",
        (
            "SELECT total(b.size) FROM blobs b WHERE EXISTS(SELECT 1 FROM snapshot_parts p WHERE "
            "p.blob=b.sha256) AND NOT EXISTS(SELECT 1 FROM files f WHERE f.sha256=b.sha256)"
        ),
    ),
    # #211 secondary features
    (
        "claims with a role other than supporting",
        "SELECT count(*) FROM claims WHERE role<>'supporting'",
    ),
    ("claims with a group", "SELECT count(*) FROM claims WHERE \"group\"<>''"),
    (
        "claims whose metadata already has role or group",
        (
            "SELECT count(*) FROM claims WHERE json_valid(metadata) AND (json_type(metadata,'$.role') "
            "IS NOT NULL OR json_type(metadata,'$.group') IS NOT NULL)"
        ),
    ),
    ("claims always in the CV", "SELECT count(*) FROM claims WHERE default_in_cv=1"),
    ("job signals with welcome languages", "SELECT count(*) FROM job_signals WHERE welcome<>'[]'"),
)

# State columns whose values are fixed vocabulary, never free text.
STATES = (
    (
        "questions by state and subject",
        (
            "SELECT state, job_id IS NOT NULL OR application_id "
            "IS NOT NULL OR knowledge_id IS NOT NULL, count(*) FROM questions GROUP BY 1,2"
        ),
    ),
    (
        "requests by state and subject",
        (
            "SELECT state, job_id IS NOT NULL OR application_id "
            "IS NOT NULL OR knowledge_id IS NOT NULL, count(*) FROM requests GROUP BY 1,2"
        ),
    ),
    ("runs by status", "SELECT status, count(*) FROM runs GROUP BY 1"),
    ("applications by status", "SELECT status, count(*) FROM applications GROUP BY 1"),
    ("jobs by triage", "SELECT triage, count(*) FROM jobs GROUP BY 1"),
    (
        "documents by kind and review state",
        "SELECT kind, review_state, count(*) FROM documents GROUP BY 1,2",
    ),
    ("policy items by section", "SELECT section, count(*) FROM policy_items GROUP BY 1"),
    ("responses by kind", "SELECT kind, count(*) FROM responses GROUP BY 1"),
    ("event actors", "SELECT actor_kind, actor_token_kind, count(*) FROM events GROUP BY 1,2"),
    ("note authors", "SELECT author_kind, author_token_kind, count(*) FROM notes GROUP BY 1,2"),
    ("api tokens by kind", "SELECT kind, count(*) FROM api_tokens GROUP BY 1"),
)

# Ready as 0.24 computes it right after the upgrade (every application requires CV and
# letter): a Draft whose current CV and letter revisions both have a PDF and that has
# no unresolved blocking requirement (#214). "ready" counts both directions.
_LEAF = (
    "EXISTS(SELECT 1 FROM documents d WHERE d.application_id=a.id AND d.kind='{kind}' AND NOT "
    "EXISTS(SELECT 1 FROM documents c WHERE c.previous_id=d.id) AND EXISTS(SELECT 1 FROM files "
    "f WHERE f.document_id=d.id AND f.media_type='application/pdf'))"
)
COMPUTED_READY = (
    "a.status='draft' AND "
    + _LEAF.format(kind="resume")
    + " AND "
    + _LEAF.format(kind="cover_letter")
    + " AND NOT EXISTS(SELECT 1 FROM json_each(a.requirements) r WHERE "
    "json_extract(r.value,'$.blocking') AND NOT coalesce(json_extract(r.value,'$.resolved'),0))"
)


def connect(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    return conn


def number(conn, sql):
    try:
        return conn.execute(sql).fetchone()[0]
    except sqlite3.Error as error:
        return f"n/a ({type(error).__name__})"


def tables(conn):
    return [
        row[1]
        for row in conn.execute("PRAGMA table_list")
        if row[0] == "main" and row[2] == "table" and not row[1].startswith("sqlite_")
    ]


def aggregates(path):
    out = {}
    with closing(connect(path)) as conn:
        out["schema"] = conn.execute("PRAGMA user_version").fetchone()[0]
        out["bytes"] = Path(path).stat().st_size
        out["tables"] = {
            name: number(conn, f'SELECT count(*) FROM "{name}"') for name in tables(conn)
        }
        # Every column: rows whose value differs from the column's default.
        columns = {}
        for name in tables(conn):
            for _, column, _, _, default, _ in conn.execute(f'PRAGMA table_info("{name}")'):
                columns[f"{name}.{column}"] = number(
                    conn,
                    f'SELECT count(*) FROM "{name}" WHERE "{column}" IS NOT '
                    f"{default if default is not None else 'NULL'}",
                )
        out["non_default"] = columns
        out["planned"] = {label: number(conn, sql) for label, sql in PLANNED}
        out["states"] = {
            label: [list(row) for row in conn.execute(sql).fetchall()] for label, sql in STATES
        }
        out["ready"] = {
            "stored and computed": number(
                conn,
                f"SELECT count(*) FROM applications a WHERE ready_at IS NOT NULL AND {COMPUTED_READY}",
            ),
            "stored, not computed": number(
                conn,
                f"SELECT count(*) FROM applications a WHERE ready_at IS NOT NULL AND NOT ({COMPUTED_READY})",
            ),
            "computed, not stored": number(
                conn,
                f"SELECT count(*) FROM applications a WHERE ready_at IS NULL AND {COMPUTED_READY}",
            ),
        }
    # What this build's migration drops or repairs, counted by the migration itself.
    with closing(sqlite3.connect("file::memory:", uri=True)) as conn:
        conn.executescript(m15.SCHEMA_SQL.read_text())
        conn.execute("ATTACH DATABASE ? AS old", (Path(path).resolve().as_uri() + "?mode=ro",))
        _, sections = m15._plan(conn)
        out["migration_archive"] = {s.name: m15._count(conn, s) for s in sections}
        out["migration_archive_estimated_bytes"] = int(
            sum(m15._estimate(conn, s) for s in sections)
        )
    return out


def rehearse(path):
    """Upgrade a copy in a private temporary folder; return timings and counts."""
    with tempfile.TemporaryDirectory(prefix="openings-rehearsal-") as folder:
        Path(folder).chmod(0o700)
        copy = Path(folder) / "openings.sqlite"
        shutil.copyfile(path, copy)
        start = time.monotonic()
        report = m15.upgrade(copy)
        seconds = round(time.monotonic() - start, 2)
        files = m15.files(copy)
        identical = files.pre_upgrade.read_bytes() == Path(path).read_bytes()
        return {
            "seconds": seconds,
            "pre_upgrade_identical": identical,
            "bytes": {p.name: p.stat().st_size for p in Path(folder).iterdir()},
            "copied": report["copied"],
            "created": report["created"],
            "archive": report["archive"],
            "after": after_upgrade(copy),
        }


# Aggregates of the upgraded copy, one block per change of the migration.
AFTER = (
    # #213 Preferences
    (
        "preference statements by section",
        "SELECT section, json_array_length(items) FROM preference_sections ORDER BY section",
    ),
    (
        "writing rules by scope",
        (
            "SELECT json_extract(i.value,'$.scope'), count(*) FROM preference_sections s, "
            "json_each(s.items) i WHERE s.section='writing' GROUP BY 1"
        ),
    ),
    (
        "preference statements longer than 2000 characters",
        (
            "SELECT count(*) FROM preference_sections s, json_each(s.items) i "
            "WHERE length(json_extract(i.value,'$.text'))>2000"
        ),
    ),
    (
        "settings no_reply_days set, spoken languages",
        (
            "SELECT json_type(data,'$.no_reply_days') IS NOT NULL, "
            "json_array_length(data,'$.spoken_languages') FROM settings WHERE key='workspace'"
        ),
    ),
)


def after_upgrade(path):
    with closing(connect(path)) as conn:
        return {label: [list(row) for row in conn.execute(sql)] for label, sql in AFTER}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("database", type=Path)
    parser.add_argument("--upgrade", action="store_true", help="also upgrade a private copy")
    args = parser.parse_args()
    result = aggregates(args.database)
    if args.upgrade:
        result["rehearsal"] = rehearse(args.database)
    print(json.dumps(result, indent=1, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
