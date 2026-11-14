"""One timeline per job and per application: attributed events and notes in one list.

A job's timeline holds everything recorded on the job and on each of its
applications; an application's timeline holds its own entries and its job's
(``scope`` says which), not those of the job's other applications. Each entry is
a note or an event, of kind ``note``, ``event`` or ``reply`` (an employer reply
recorded, corrected or removed; ``response`` events from before 0.24 count), with who
made it and the run. Pinned
notes come first, then everything newest first. ``note_added`` and
``note_edited`` events are not entries: the note itself is, with its author and
version. Event payloads hold identifiers, field names and versions, never text.
"""

from ..actors import describe
from ..db import decode_record
from ..errors import DomainError, missing
from ..models import TimelineQuery

# The owner is the dashboard session or an owner token (tokens before 0.17 had no kind).
WHO = {
    "owner": "(x.actor_kind='owner' OR (x.actor_kind='token' AND coalesce(x.actor_token_kind,'owner')='owner'))",
    "agent": "(x.actor_kind='token' AND x.actor_token_kind='agent')",
    "system": "x.actor_kind='system'",
    "unknown": "x.actor_kind IS NULL",
}

# note_added and note_edited are represented by the note entry itself.
_ENTRIES = (
    "SELECT 'event' AS type,CASE WHEN e.subject_type IN ('reply','response') THEN 'reply' ELSE 'event' END AS kind,"
    "e.id,e.created_at,e.job_id,e.application_id,e.actor_kind,e.actor_id,e.actor_name,"
    "e.actor_token_kind,e.run_id,NULL AS pinned_at,e.kind AS event_kind,e.payload,"
    "e.subject_type,e.subject_id,NULL AS body,NULL AS version,NULL AS updated_at "
    "FROM events e WHERE {events} AND e.kind NOT IN ('note_added','note_edited') "
    "UNION ALL "
    "SELECT 'note','note',n.id,n.created_at,n.job_id,n.application_id,n.author_kind,n.author_id,"
    "n.author_name,n.author_token_kind,n.run_id,n.pinned_at,NULL,NULL,NULL,NULL,n.body,n.version,"
    "n.updated_at FROM notes n WHERE {notes}"
)


def _entry(row):
    row = dict(row)
    application_id = row["application_id"]
    entry = {
        "type": row["type"],
        "kind": row["kind"],
        "id": row["id"],
        "created_at": row["created_at"],
        "scope": {
            "type": "application" if application_id else "job",
            "id": application_id or row["job_id"],
        },
        "job_id": row["job_id"],
        "application_id": application_id,
        "actor": describe(
            row["actor_kind"], row["actor_id"], row["actor_name"], row["actor_token_kind"]
        ),
        "run": {"id": row["run_id"], "workflow": row["run_workflow"]} if row["run_id"] else None,
        "note": None,
        "event": None,
    }
    if row["type"] == "note":
        entry["note"] = {
            "body": row["body"],
            "version": row["version"],
            "updated_at": row["updated_at"],
            "pinned": row["pinned_at"] is not None,
            "pinned_at": row["pinned_at"],
        }
    else:
        event = decode_record(row, ("payload",))
        subject = (
            {"type": event["subject_type"], "id": event["subject_id"]}
            if event["subject_type"]
            # Events from before schema 8 belong to their application or job.
            else {"type": entry["scope"]["type"], "id": entry["scope"]["id"]}
        )
        entry["event"] = {
            "kind": event["event_kind"],
            "payload": event["payload"],
            "subject": subject,
        }
    return entry


class Timeline:
    """Reading the timeline of a job or an application."""

    def timeline(self, job_id=None, application_id=None, value=None):
        """Notes and attributed events of a job or an application, pinned notes first, then newest first."""
        value = (
            value if isinstance(value, TimelineQuery) else TimelineQuery.model_validate(value or {})
        )
        if (job_id is None) == (application_id is None):
            raise DomainError(422, "timeline_scope", "Give either a job_id or an application_id.")
        with self.db.connect() as conn:
            if application_id is not None:
                row = conn.execute(
                    "SELECT job_id FROM applications WHERE id=?", (application_id,)
                ).fetchone()
                if row is None:
                    missing("Application")
                job_id = row["job_id"]
                # Its own entries and its job's, not those of the job's other applications.
                scope_sql = (
                    "({a}.application_id=? OR ({a}.job_id=? AND {a}.application_id IS NULL))"
                )
                scope_args = (application_id, job_id)
            else:
                if conn.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone() is None:
                    missing("Job")
                scope_sql, scope_args = "{a}.job_id=?", (job_id,)
            entries = _ENTRIES.format(events=scope_sql.format(a="e"), notes=scope_sql.format(a="n"))
            args = [*scope_args, *scope_args]
            where, params = [], []
            if value.who:
                where.append("(" + " OR ".join(WHO[who] for who in sorted(set(value.who))) + ")")
            if value.scope:
                where.append(
                    "x.application_id IS NOT NULL"
                    if value.scope == "application"
                    else "x.application_id IS NULL"
                )
            for item, operator in ((value.since, ">="), (value.until, "<=")):
                if item:
                    where.append("x.created_at" + operator + "?")
                    params.append(item)
            # Counts by kind follow every filter but the kind, for the filter chips.
            base = " FROM (" + entries + ") x"
            clause = " WHERE " + " AND ".join(where) if where else ""
            counts = {"note": 0, "event": 0, "reply": 0}
            for kind, count in conn.execute(
                "SELECT x.kind,count(*)" + base + clause + " GROUP BY x.kind", (*args, *params)
            ):
                counts[kind] = count
            if value.kinds:
                kinds = sorted(set(value.kinds))
                where.append("x.kind IN (" + ",".join("?" for _ in kinds) + ")")
                params.extend(kinds)
            clause = " WHERE " + " AND ".join(where) if where else ""
            total = conn.execute("SELECT count(*)" + base + clause, (*args, *params)).fetchone()[0]
            rows = conn.execute(
                "SELECT x.*,r.workflow AS run_workflow"
                + base
                + " LEFT JOIN runs r ON r.id=x.run_id"
                + clause
                + " ORDER BY x.pinned_at IS NULL,x.created_at DESC,x.id DESC LIMIT ? OFFSET ?",
                (*args, *params, value.limit, value.offset),
            ).fetchall()
        return {
            "scope": {
                "type": "application" if application_id else "job",
                "id": application_id or job_id,
                "job_id": job_id,
            },
            "items": [_entry(row) for row in rows],
            "total": total,
            "counts": counts,
            "limit": value.limit,
            "offset": value.offset,
        }
