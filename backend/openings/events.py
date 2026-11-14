"""The attributed change log: one event per change, with its actor label and batch.

``record`` is the only way a change is written: it reads the actor and the batch
of the current REST request or MCP tool call from the context (``actors.py``).
Payloads hold identifiers, field names and versions, never record content.
``list_events`` is an API-only read for scripts.
"""

from typing import Annotated

from pydantic import Field

from .actors import AGENT_PREFIX, current_actor, current_batch
from .common import new_id, now
from .db import decode_record, encode
from .errors import DomainError
from .models import Since, SubjectRef, Until

# Who wrote a row with an ``actor`` (or ``author``) label column, by filter value.
WHO = {
    "owner": "{column}='owner'",
    "agent": "{column} LIKE 'agent:%'",
    "system": "{column}='system'",
    "unknown": "{column} IS NULL",
}


def who_sql(who, column):
    """SQL and parameters for one actor filter: owner, agent, system, unknown or agent:<name>."""
    if who in WHO:
        return WHO[who].format(column=column), []
    if who.startswith(AGENT_PREFIX) and len(who) > len(AGENT_PREFIX):
        return f"{column}=?", [who]
    raise DomainError(
        422, "actor", "Choose owner, agent, system, unknown or agent:<token name>.", {"actor": who}
    )


def record(
    conn,
    kind,
    subject=None,
    payload=None,
    *,
    job_id=None,
    application_id=None,
    actor=None,
):
    """Record one change by the current actor in the current batch.

    ``subject`` is ``(type, id)`` of the changed record; it defaults to the
    application or job, whose timeline the event belongs to. ``actor`` replaces
    the current actor for a change made on someone's behalf (an upload with a
    transfer grant).
    """
    if subject is None:
        subject = (
            ("application", application_id)
            if application_id
            else ("job", job_id)
            if job_id
            else (None, None)
        )
    conn.execute(
        "INSERT INTO events(id,job_id,application_id,kind,payload,created_at,subject_type,"
        "subject_id,actor,batch_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            new_id(),
            job_id,
            application_id,
            kind,
            encode(payload or {}),
            now(),
            *subject,
            (actor or current_actor()).label,
            current_batch(),
        ),
    )


def event_record(row):
    """An event as reads return it: decoded payload, subject, actor label and batch."""
    item = decode_record(row, ("payload",))
    kind = item.pop("subject_type", None)
    identifier = item.pop("subject_id", None)
    if kind is None:
        # Events from before schema 8 belong to their application or job.
        kind, identifier = (
            ("application", item.get("application_id"))
            if item.get("application_id")
            else ("job", item.get("job_id"))
            if item.get("job_id")
            else (None, None)
        )
    item["subject"] = {"type": kind, "id": identifier}
    return item


def label(*parts):
    return " · ".join(part for part in parts if part)


class EventQuery(SubjectRef):
    actor: str | None = Field(
        default=None,
        max_length=200,
        description="owner, agent, agent:<token name>, system or unknown.",
    )
    batch_id: str | None = Field(
        default=None,
        max_length=100,
        description="The changes of one call (b_...) or of an agent run before 0.24 (run:...).",
    )
    include_system: bool = Field(
        default=False,
        description="Also the system's changes (left out unless actor=system).",
    )
    subject_types: list[Annotated[str, Field(min_length=1, max_length=50)]] | None = Field(
        default=None,
        max_length=20,
        description="Changes to these kinds of record, such as document and file.",
    )
    job_id: str | None = Field(default=None, max_length=100)
    application_id: str | None = Field(default=None, max_length=100)
    kind: str | None = Field(default=None, max_length=100)
    since: Since | None = None
    until: Until | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


# Current names of changed records, by subject type; deleted records have none.
_SUBJECT_LABELS = {
    "career": "SELECT id,title,organization FROM knowledge WHERE id IN ({})",
    "highlight": "SELECT c.id,k.title,k.organization FROM claims c JOIN knowledge k ON k.id=c.knowledge_id WHERE c.id IN ({})",
    "template": "SELECT id,name,'' FROM templates WHERE id IN ({})",
    "source": "SELECT id,name,'' FROM sources WHERE id IN ({})",
    "response": "SELECT r.id,j.title,j.company FROM responses r JOIN applications a ON a.id=r.application_id JOIN jobs j ON j.id=a.job_id WHERE r.id IN ({})",
    "collection_run": "SELECT id,source_name,'' FROM collection_runs WHERE id IN ({})",
}


class EventLog:
    def __init__(self, workspace):
        self.db = workspace.db

    def list_events(self, value: EventQuery | None = None) -> dict:
        """List recorded changes, newest first, each with its actor label, batch and subject."""
        value = value if isinstance(value, EventQuery) else EventQuery.model_validate(value or {})
        where, params = [], []
        for column, item in (
            ("e.batch_id", value.batch_id),
            ("e.job_id", value.job_id),
            ("e.application_id", value.application_id),
            ("e.kind", value.kind),
        ):
            if item is not None:
                where.append(column + "=?")
                params.append(item)
        if value.subject_type is not None:
            where.append("e.subject_type=?")
            params.append(value.subject_type)
            if value.subject_id is not None:
                where.append("e.subject_id=?")
                params.append(value.subject_id)
        if value.subject_types:
            kinds = sorted(set(value.subject_types))
            options = ["e.subject_type IN (" + ",".join("?" for _ in kinds) + ")"]
            params.extend(kinds)
            # Events from before schema 8 belong to their application or job.
            if "application" in kinds:
                options.append("(e.subject_type IS NULL AND e.application_id IS NOT NULL)")
            if "job" in kinds:
                options.append(
                    "(e.subject_type IS NULL AND e.application_id IS NULL AND e.job_id IS NOT NULL)"
                )
            where.append("(" + " OR ".join(options) + ")")
        if value.actor:
            sql, args = who_sql(value.actor, "e.actor")
            where.append(sql)
            params.extend(args)
        elif not value.include_system:
            where.append("coalesce(e.actor,'')<>'system'")
        for item, operator in ((value.since, ">="), (value.until, "<=")):
            if item:
                where.append("e.created_at" + operator + "?")
                params.append(item)
        clause = " WHERE " + " AND ".join(where) if where else ""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT e.*,j.title AS job_title,j.company AS job_company "
                "FROM events e LEFT JOIN jobs j ON j.id=e.job_id"
                + clause
                + " ORDER BY e.created_at DESC LIMIT ? OFFSET ?",
                (*params, value.limit, value.offset),
            ).fetchall()
            total = conn.execute("SELECT count(*) FROM events e" + clause, params).fetchone()[0]
            items = [event_record(row) for row in rows]
            labels = self._subject_labels(conn, items)
        for item in items:
            subject = item["subject"]
            job = label(item.pop("job_title"), item.pop("job_company"))
            subject["label"] = labels.get((subject["type"], subject["id"])) or job
        return {"items": items, "total": total, "limit": value.limit, "offset": value.offset}

    @staticmethod
    def _subject_labels(conn, items):
        wanted = {}
        for item in items:
            subject = item["subject"]
            if subject["type"] in _SUBJECT_LABELS and subject["id"]:
                wanted.setdefault(subject["type"], set()).add(subject["id"])
        labels = {}
        for kind, identifiers in wanted.items():
            sql = _SUBJECT_LABELS[kind].format(",".join("?" for _ in identifiers))
            for row in conn.execute(sql, sorted(identifiers)):
                labels[(kind, row[0])] = label(row[1], row[2])
        return labels
