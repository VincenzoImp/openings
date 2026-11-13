"""Application reads: derived readiness, preparation summaries, lists and history."""

from ..actors import pop_actor
from ..db import decode_record
from ..errors import DomainError, missing
from ..models import OUTCOMES
from ..outcomes import last_responses, no_reply_cutoff, no_reply_period, responses_of
from ..staleness import application_staleness, stale_summary

# Current revision leaves only; a parent's PDF or approval never counts for its child.
_LEAVES = (
    "SELECT 1 FROM documents d WHERE d.application_id=app.id "
    "AND NOT EXISTS(SELECT 1 FROM documents child WHERE child.previous_id=d.id)"
)


_UNRESOLVED = "SELECT 1 FROM json_each(app.requirements) r WHERE NOT coalesce(json_extract(r.value,'$.resolved'),0)"


READINESS_SQL = (
    "CASE WHEN EXISTS(" + _UNRESOLVED + " AND json_extract(r.value,'$.blocking')) THEN 'blocked' "
    "WHEN NOT EXISTS(" + _LEAVES + ") THEN 'none' "
    "WHEN EXISTS("
    + _LEAVES
    + " AND d.kind IN ('resume','cover_letter') AND NOT EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id AND f.media_type='application/pdf')) THEN 'missing_pdf' "
    "WHEN EXISTS(" + _LEAVES + " AND d.review_state<>'approved') THEN 'unreviewed' "
    # Every check passes: "reviewed" until someone marks the application ready.
    "WHEN app.ready_at IS NULL THEN 'reviewed' ELSE 'ready' END"
)


READINESS = ("blocked", "none", "missing_pdf", "unreviewed", "reviewed", "ready")


# Why an application whose checks fail cannot be marked ready, by derived readiness.
NOT_READY = {
    "blocked": "Resolve every blocking requirement before marking this application ready.",
    "none": "Save the application documents before marking this application ready.",
    "missing_pdf": "Attach a PDF to every current CV and cover letter revision before marking this application ready.",
    "unreviewed": "Approve every current document revision before marking this application ready.",
}


REQUIREMENT_COUNTS_SQL = (
    "(SELECT count(*) FROM json_each(app.requirements) r WHERE NOT coalesce(json_extract(r.value,'$.resolved'),0)) AS open_requirements,"
    "(SELECT count(*) FROM json_each(app.requirements) r WHERE NOT coalesce(json_extract(r.value,'$.resolved'),0) AND json_extract(r.value,'$.blocking')) AS blocking_requirements"
)


class ApplicationReads:
    """Reading applications and their recorded events."""

    def get_application(self, application_id, compact_job=False):
        row = self.db.one(
            f"SELECT app.*,{READINESS_SQL} AS readiness,{REQUIREMENT_COUNTS_SQL} FROM applications app WHERE app.id=?",
            (application_id,),
        )
        if not row:
            missing("Application")
        row = self._ready_by(decode_record(row, ("questions", "answers", "requirements")))
        row["job"] = (self.job_summary if compact_job else self.get_job)(row["job_id"])
        row["documents_count"] = self.db.one(
            "SELECT count(*) n FROM documents WHERE application_id=?", (application_id,)
        )["n"]
        with self.db.connect() as connection:
            row["preparation"] = self._application_preparation(connection, [application_id])[
                application_id
            ]
            row.update(
                stale_summary(application_staleness(connection, [application_id])[application_id])
            )
            row["responses"] = responses_of(connection, [application_id])[application_id]
            row["last_response"] = last_responses(connection, [application_id])[application_id]
            pinned = self.pinned_application_notes(connection, [application_id])[application_id]
        row["pinned_note"] = pinned
        # Deprecated since 0.22, removed in 0.23: the pinned note's text.
        row["note"] = pinned["body"] if pinned else ""
        return row

    @staticmethod
    def _ready_by(row):
        """Replace the stored actor columns with who marked the application ready."""
        marked_by = pop_actor(row, "ready_by")
        row["ready_by"] = marked_by if row["ready_at"] else None
        return row

    @staticmethod
    def _application_preparation(connection, application_ids):
        """Summarize current revision leaves, never inheriting a parent's PDF/review."""
        result = {identifier: [] for identifier in application_ids}
        if not application_ids:
            return result
        placeholders = ",".join("?" for _ in application_ids)
        rows = connection.execute(
            "SELECT d.application_id,d.kind,COUNT(*) AS revisions,"
            "SUM(EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id AND f.media_type='application/pdf')) AS pdf,"
            "SUM(d.review_state='approved' AND EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id AND f.media_type='application/pdf')) AS approved "
            f"FROM documents d WHERE d.application_id IN ({placeholders}) "
            "AND NOT EXISTS(SELECT 1 FROM documents child WHERE child.previous_id=d.id) "
            "GROUP BY d.application_id,d.kind ORDER BY d.kind",
            application_ids,
        )
        for row in rows:
            item = dict(row)
            result[item.pop("application_id")].append(item)
        return result

    def list_applications(
        self,
        status=None,
        limit=100,
        offset=0,
        q="",
        outcome=None,
        company=None,
        sort="updated",
        job_id=None,
        readiness=None,
        ready_since=None,
        ready_until=None,
        applied_since=None,
        applied_until=None,
        ready=None,
        no_reply_due=None,
    ):
        conditions, args = [], []
        with self.db.connect() as connection:
            no_reply = no_reply_period(connection)
        due_sql = "(app.status='applied' AND app.applied_at IS NOT NULL AND app.applied_at<?)"
        cutoff = no_reply_cutoff(no_reply["days"])
        if no_reply_due is not None:
            conditions.append(due_sql if no_reply_due else "NOT " + due_sql)
            args.append(cutoff)
        if ready is not None:
            conditions.append("app.ready_at IS " + ("NOT NULL" if ready else "NULL"))
        if readiness:
            if readiness not in READINESS:
                raise DomainError(
                    422,
                    "application_readiness",
                    "Choose blocked, none, missing_pdf, unreviewed, reviewed or ready.",
                )
            if readiness == "ready":
                # The stored step first, so the partial index narrows the candidates.
                conditions.append("app.ready_at IS NOT NULL")
            conditions.append(f"({READINESS_SQL})=?")
            args.append(readiness)
        for column, value, operator in (
            ("ready_at", ready_since, ">="),
            ("ready_at", ready_until, "<="),
            ("applied_at", applied_since, ">="),
            ("applied_at", applied_until, "<="),
        ):
            if value:
                conditions.append("app." + column + operator + "?")
                args.append(value)
        if job_id is not None:
            conditions.append("app.job_id=?")
            args.append(job_id)
        if status:
            if status not in ("draft", "applied", "interview", "offer", "closed"):
                raise DomainError(422, "application_status", "Choose a valid application stage.")
            conditions.append("app.status=?")
            args.append(status)
        if outcome:
            if outcome not in OUTCOMES:
                raise DomainError(422, "application_outcome", "Choose a valid application outcome.")
            conditions.append("app.outcome=?")
            args.append(outcome)
        if company:
            conditions.append("j.company=?")
            args.append(company)
        if q.strip():
            conditions.append(
                "(j.title LIKE ? OR j.company LIKE ? OR EXISTS(SELECT 1 FROM notes n "
                "WHERE n.application_id=app.id AND n.pinned_at IS NOT NULL AND n.body LIKE ?))"
            )
            args.extend(["%" + q.strip() + "%"] * 3)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        base = " FROM applications app JOIN jobs j ON j.id=app.job_id"
        order = {
            "newest": "app.created_at DESC",
            "oldest": "app.created_at ASC",
            "company": "j.company,j.title",
            "stage": "app.status,app.updated_at DESC",
            "applied": "app.applied_at DESC",
            # Undated or unprioritized attempts follow the planned ones.
            "deadline": "app.deadline IS NULL,app.deadline,app.priority IS NULL,app.priority,app.updated_at DESC",
            "priority": "app.priority IS NULL,app.priority,app.deadline IS NULL,app.deadline,app.updated_at DESC",
            # The ready queue: longest waiting first, then everything not marked ready.
            "ready": "app.ready_at IS NULL,app.ready_at,app.updated_at DESC",
        }.get(sort, "app.updated_at DESC")
        with self.db.connect() as connection:
            projection = "app.id,app.job_id,app.status,app.outcome,app.version,app.applied_at,app.created_at,app.updated_at,app.concluded_on,"
            projection += "app.priority,app.deadline,"
            projection += "app.ready_at,app.ready_by_kind,app.ready_by_id,app.ready_by_name,"
            projection += "app.ready_by_token_kind,"
            projection += f"{READINESS_SQL} AS readiness,{REQUIREMENT_COUNTS_SQL},"
            projection += (
                "(SELECT count(*) FROM documents WHERE application_id=app.id) AS documents_count,"
            )
            projection += self._job_columns()
            rows = connection.execute(
                "SELECT "
                + projection
                + base
                + where
                + " ORDER BY "
                + order
                + ",app.id LIMIT ? OFFSET ?",
                (*args, min(max(int(limit), 1), 200), max(int(offset), 0)),
            ).fetchall()
            total = connection.execute("SELECT count(*)" + base + where, args).fetchone()[0]
            counts = {stage: 0 for stage in ("draft", "applied", "interview", "offer", "closed")}
            ready_count = 0
            for row in connection.execute(
                "SELECT app.status,count(*) n,count(app.ready_at) ready"
                + base
                + where
                + " GROUP BY app.status",
                args,
            ):
                counts[row["status"]] = row["n"]
                ready_count += row["ready"]
            identifiers = [row["id"] for row in rows]
            preparation = self._application_preparation(connection, identifiers)
            staleness = application_staleness(connection, identifiers)
            answers = last_responses(connection, identifiers)
            no_reply["due"] = connection.execute(
                "SELECT count(*) FROM applications app WHERE " + due_sql, (cutoff,)
            ).fetchone()[0]
        items = []
        for raw in rows:
            item = self._ready_by(
                {key: value for key, value in dict(raw).items() if not key.startswith("j_")}
            )
            item["job"] = self._compact_job(raw)
            item["preparation"] = preparation[item["id"]]
            item.update(stale_summary(staleness[item["id"]]))
            item["last_response"] = answers[item["id"]]
            items.append(item)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "stage_counts": counts,
            "ready_count": ready_count,
            "no_reply": no_reply,
        }

    def application_events(self, application_id):
        self.get_application(application_id)
        rows = [
            self.event_record(r)
            for r in self.db.all(
                "SELECT * FROM events WHERE application_id=? ORDER BY created_at DESC",
                (application_id,),
            )
        ]
        return {"items": rows, "total": len(rows)}
