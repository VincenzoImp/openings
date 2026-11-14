"""workspace_context: what an agent reads before it decides or writes, in one compact result.

One read returns the workspace identity, queue counts, settings, the profile, the
five Preferences sections, a summary of each career entry, the templates, the
shipped skills and ``feedback``: the owner's own changes, since this token's
previous ``workspace_context`` read, that touched agent work (a job an agent
triaged and the owner moved, an application an agent worked on and the owner
moved or answered, a revision an agent made and the owner deleted, any
Preferences edit). ``api_tokens.context_read_at`` keeps the time of the previous
read; ``feedback_since`` replaces it. The dashboard reads the same operation over
REST (without a token there is no previous read, so no feedback unless asked).
"""

import json
import os
from typing import Literal

from pydantic import Field

from . import __version__
from .actors import current_actor
from .common import now
from .events import label
from .models import Input, Since
from .outcomes import today
from .preferences import read_sections, settings_record
from .workspace.readiness import MISSING_DOCUMENTS_SQL

SUMMARY_CHARS = 200
FEEDBACK_LIMIT = 30
UPLOAD = (
    "Files are bytes over HTTP: PUT them to a grant's url with its headers (a shell with "
    "curl), GET downloads the same way."
)


class ContextQuery(Input):
    include: list[Literal["career_full", "templates_full"]] = Field(
        default_factory=list,
        description="career_full: full narratives and approved highlights; templates_full: TeX and guidance.",
    )
    feedback_since: Since | None = Field(
        default=None, description="Owner corrections since then (default: your previous read)."
    )


def _dates(value):
    """A career entry's dates as one short text: 2021-03..2024-06, 2022..present or 2020."""
    if not value:
        return None
    dates = json.loads(value)
    if dates.get("kind") == "single":
        return dates.get("start")
    end = "present" if dates.get("current") else dates.get("end")
    return f"{dates.get('start')}..{end}"


# Owner changes that answer agent work, by kind; ``{agent}`` is the agent's earlier change.
FEEDBACK_SQL = """
SELECT e.*, j.title AS job_title, j.company AS job_company,
 CASE WHEN e.kind='triage_changed' THEN (SELECT p.actor||char(31)||p.payload FROM events p
  WHERE p.job_id=e.job_id AND p.kind='triage_changed' AND p.created_at<e.created_at
  ORDER BY p.created_at DESC,p.rowid DESC LIMIT 1)
 WHEN e.kind='document_deleted' THEN (SELECT p.actor FROM events p WHERE p.kind='document_created'
  AND p.subject_type='document' AND p.subject_id=e.subject_id AND p.actor LIKE 'agent:%' LIMIT 1)
 WHEN e.application_id IS NOT NULL THEN (SELECT p.actor FROM events p
  WHERE p.application_id=e.application_id AND p.actor LIKE 'agent:%' AND p.created_at<e.created_at
  ORDER BY p.created_at DESC,p.rowid DESC LIMIT 1)
 END AS earlier
FROM events e LEFT JOIN jobs j ON j.id=e.job_id
WHERE e.actor='owner' AND e.created_at>? AND e.kind IN ('triage_changed','application_updated',
 'reply_added','reply_edited','reply_removed','document_deleted','preferences_updated')
ORDER BY e.created_at DESC,e.rowid DESC LIMIT ?
"""


def _feedback_item(row):
    payload = json.loads(row["payload"] or "{}")
    kind, earlier, reason = row["kind"], row["earlier"], None
    if kind == "preferences_updated":
        section = payload.get("section")
        return {
            "at": row["created_at"],
            "what": f"edited Preferences {section}",
            "subject": {"type": "preferences", "id": section},
        }
    if kind == "triage_changed":
        actor, _, previous = (earlier or "").partition(chr(31))
        if not actor.startswith("agent:"):
            return None
        earlier = actor
        reason = json.loads(previous or "{}").get("reason")
        what = f"moved the job from {payload.get('from')} to {payload.get('to')}"
    elif not earlier:
        return None
    elif kind == "application_updated":
        moved = payload.get("from") != payload.get("to")
        what = (
            f"moved the application from {payload.get('from')} to {payload.get('to')}"
            if moved
            else "edited the application: " + ", ".join(payload.get("fields") or [])
        )
    elif kind == "reply_added":
        what = f"recorded a reply ({payload.get('kind')})"
    elif kind == "document_deleted":
        what = f"deleted a {payload.get('kind')} revision"
    else:
        what = "corrected a reply" if kind == "reply_edited" else "removed a reply"
    subject = (
        {"type": "application", "id": row["application_id"]}
        if row["application_id"]
        else {"type": "job", "id": row["job_id"]}
    )
    subject["label"] = label(row["job_title"], row["job_company"])
    return {
        "at": row["created_at"],
        "what": what,
        "subject": subject,
        "agent": earlier,
        "reason_was": reason,
    }


class ContextService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db

    def context(self, value: ContextQuery | None = None, origin=None) -> dict:
        value = value or ContextQuery()
        include = set(value.include)
        ws, actor = self.workspace, current_actor()
        token_id = actor.id if actor.kind == "token" else None
        since = value.feedback_since or self._previous_read(token_id)
        with self.db.connect() as conn:
            settings = settings_record(conn)
            sections = read_sections(conn)
            result = {
                "workspace": {
                    "version": __version__,
                    "origin": os.environ.get("OPENINGS_PUBLIC_URL") or origin,
                    "today": today(),
                    "you": actor.label,
                    "files": UPLOAD,
                },
                "counts": self._counts(conn),
                "settings": {
                    "no_reply_days": settings["no_reply_days"],
                    "spoken_languages": settings["spoken_languages"],
                    "version": settings["version"],
                },
                "profile": ws.career.get_profile(),
                "preferences": {
                    section["section"]: {
                        "version": section["version"],
                        "items": [
                            item if section["section"] == "writing" else item["text"]
                            for item in section["items"]
                        ],
                    }
                    for section in sections
                },
                "career": self._career(conn, full="career_full" in include),
                "templates": self._templates(conn, full="templates_full" in include),
            }
            result["feedback"] = (
                [
                    item
                    for row in conn.execute(FEEDBACK_SQL, (since, FEEDBACK_LIMIT))
                    if (item := _feedback_item(row))
                ]
                if since
                else []
            )
        collection = ws.discovery.get_collection()
        result["settings"]["collection"] = {
            "enabled": collection["enabled"],
            "version": collection["version"],
        }
        result["skills"] = [
            {"name": item["name"], "use": item["summary"] or item["description"][:200]}
            for item in ws.skills.list()
        ]
        if token_id:
            self.db.execute("UPDATE api_tokens SET context_read_at=? WHERE id=?", (now(), token_id))
        return result

    def _previous_read(self, token_id):
        if not token_id:
            return None
        row = self.db.one(
            "SELECT coalesce(context_read_at,created_at) AS at FROM api_tokens WHERE id=?",
            (token_id,),
        )
        return row["at"] if row else None

    def _counts(self, conn):
        jobs = conn.execute(
            "SELECT coalesce(sum(triage='new'),0),coalesce(sum(triage='shortlisted'),0),"
            "count(*) FROM jobs"
        ).fetchone()
        sources = conn.execute("SELECT count(*) FROM sources").fetchone()[0]
        stages = self.workspace.list_applications(limit=1)
        failing = conn.execute(
            "SELECT count(*) FROM sources s WHERE (SELECT t.state FROM tasks t WHERE "
            "t.source_id=s.id AND t.kind='collect' ORDER BY t.created_at DESC,t.id DESC LIMIT 1)"
            "='failed'"
        ).fetchone()[0]
        missing = conn.execute(
            "SELECT count(*) FROM applications app WHERE app.status='shortlisted' AND "
            + MISSING_DOCUMENTS_SQL
        ).fetchone()[0]
        counts = stages["stage_counts"]
        return {
            "new": jobs[0],
            "shortlisted": jobs[1],
            "ready": counts["ready"],
            "missing_documents": missing,
            "applied": counts["applied"],
            "interview": counts["interview"],
            "offer": counts["offer"],
            "reply_overdue": stages["no_reply"]["overdue"],
            "sources_failing": failing,
            # Setup facts: a job or a source exists.
            "jobs": jobs[2],
            "sources": sources,
        }

    @staticmethod
    def _career(conn, full):
        narrative = "narrative" if full else f"substr(narrative,1,{SUMMARY_CHARS + 1})"
        rows = conn.execute(
            f"SELECT k.id,k.kind,k.title,k.organization,k.dates,k.version,{narrative} AS text,"
            "(SELECT count(*) FROM claims c WHERE c.knowledge_id=k.id) AS highlights,"
            "(SELECT count(*) FROM claims c WHERE c.knowledge_id=k.id AND c.approved=1) "
            "AS approved FROM knowledge k ORDER BY k.position,k.created_at,k.id"
        ).fetchall()
        approved = {}
        if full:
            for row in conn.execute(
                "SELECT id,knowledge_id,text,always_include FROM claims WHERE approved=1 "
                "ORDER BY position,created_at,id"
            ):
                item = {"id": row["id"], "text": row["text"]}
                if row["always_include"]:
                    item["always_include"] = True
                approved.setdefault(row["knowledge_id"], []).append(item)
        items = []
        for row in rows:
            text = row["text"] or ""
            if not full and len(text) > SUMMARY_CHARS:
                text = text[:SUMMARY_CHARS].rstrip() + "…"
            item = {
                "id": row["id"],
                "version": row["version"],
                "kind": row["kind"],
                "title": row["title"],
                "organization": row["organization"],
                "dates": _dates(row["dates"]),
                "narrative" if full else "summary": text,
                "highlights": row["highlights"],
                "approved": row["approved"],
            }
            if full:
                item["approved_highlights"] = approved.get(row["id"], [])
            items.append(item)
        return items

    @staticmethod
    def _templates(conn, full):
        columns = ",tex,guidance" if full else ""
        rows = conn.execute(
            f"SELECT id,kind,name,is_default,version,rules{columns} FROM templates "
            "ORDER BY kind,is_default DESC,name,id"
        ).fetchall()
        items = []
        for row in rows:
            item = {
                "id": row["id"],
                "version": row["version"],
                "kind": row["kind"],
                "name": row["name"],
                "default": bool(row["is_default"]),
                "limits": json.loads(row["rules"] or "{}"),
            }
            if full:
                item["tex"], item["guidance"] = row["tex"], row["guidance"]
            items.append(item)
        return items
