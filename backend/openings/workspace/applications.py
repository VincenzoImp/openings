"""Application reads: computed Ready, preparation summaries, lists and history."""

from ..common import decode_record
from ..errors import DomainError, missing
from ..models import OUTCOMES
from ..outcomes import last_replies, no_reply_cutoff, no_reply_period, replies_of
from .readiness import MISSING_DOCUMENTS_SQL, READY_SQL, readiness

STAGES = ("shortlisted", "applied", "interview", "offer", "closed")

REQUIREMENT_COUNTS_SQL = (
    "(SELECT count(*) FROM json_each(app.requirements) r WHERE NOT coalesce(json_extract(r.value,'$.resolved'),0)) AS open_requirements,"
    "(SELECT count(*) FROM json_each(app.requirements) r WHERE NOT coalesce(json_extract(r.value,'$.resolved'),0) AND json_extract(r.value,'$.blocking')) AS blocking_requirements"
)

# Applied, without a reply, sent before the cutoff of the no-reply period.
REPLY_OVERDUE_SQL = (
    "(app.status='applied' AND app.applied_at IS NOT NULL AND app.applied_at<? "
    "AND NOT EXISTS(SELECT 1 FROM replies r WHERE r.application_id=app.id))"
)


class ApplicationReads:
    """Reading applications and their recorded events."""

    def get_application(self, application_id, compact_job=False):
        row = self.db.one(
            f"SELECT app.*,{REQUIREMENT_COUNTS_SQL} FROM applications app WHERE app.id=?",
            (application_id,),
        )
        if not row:
            missing("Application")
        with self.db.connect() as connection:
            row.update(readiness(connection, [row])[application_id])
        row = decode_record(row, ("questions", "answers", "requirements", "required_documents"))
        row["from_shortlist"] = bool(row["from_shortlist"])
        row["job"] = (self.job_summary if compact_job else self.get_job)(row["job_id"])
        row["documents_count"] = self.db.one(
            "SELECT count(*) n FROM documents WHERE application_id=?", (application_id,)
        )["n"]
        with self.db.connect() as connection:
            row["preparation"] = self._application_preparation(connection, [application_id])[
                application_id
            ]
            row["replies"] = replies_of(connection, [application_id])[application_id]
            row["last_reply"] = last_replies(connection, [application_id])[application_id]
            pinned = self.pinned_application_notes(connection, [application_id])[application_id]
        row["pinned_note"] = pinned
        row["stage"] = row.pop("status")
        return row

    @staticmethod
    def _application_preparation(connection, application_ids):
        """Current revisions by kind: how many, and how many are complete (PDF stored)."""
        result = {identifier: [] for identifier in application_ids}
        if not application_ids:
            return result
        placeholders = ",".join("?" for _ in application_ids)
        rows = connection.execute(
            "SELECT d.application_id,d.kind,COUNT(*) AS revisions,"
            "SUM(EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id AND f.media_type='application/pdf')) AS complete "
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
        stage=None,
        limit=100,
        offset=0,
        q="",
        outcome=None,
        company=None,
        sort="updated",
        job_id=None,
        needs=None,
        applied_since=None,
        applied_until=None,
    ):
        conditions, args = [], []
        with self.db.connect() as connection:
            no_reply = no_reply_period(connection)
        cutoff = no_reply_cutoff(no_reply["days"])
        if needs == "reply_overdue":
            conditions.append(REPLY_OVERDUE_SQL)
            args.append(cutoff)
        elif needs == "documents":
            conditions.append(f"app.status='shortlisted' AND {MISSING_DOCUMENTS_SQL}")
        elif needs is not None:
            raise DomainError(422, "application_needs", "Choose documents or reply_overdue.")
        for column, value, operator in (
            ("applied_at", applied_since, ">="),
            ("applied_at", applied_until, "<="),
        ):
            if value:
                conditions.append("app." + column + operator + "?")
                args.append(value)
        if job_id is not None:
            conditions.append("app.job_id=?")
            args.append(job_id)
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
        # Stage counts follow every filter but the stage itself.
        counted = " WHERE " + " AND ".join(conditions) if conditions else ""
        counted_args = list(args)
        if stage:
            if stage == "ready":
                conditions.append(READY_SQL)
            elif stage in STAGES:
                conditions.append("app.status=?")
                args.append(stage)
            else:
                raise DomainError(422, "application_stage", "Choose a valid application stage.")
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
        }.get(sort, "app.updated_at DESC")
        with self.db.connect() as connection:
            projection = "app.id,app.job_id,app.status,app.outcome,app.version,app.applied_at,app.created_at,app.updated_at,app.concluded_on,"
            projection += "app.priority,app.deadline,app.required_documents,app.requirements,"
            projection += f"{REQUIREMENT_COUNTS_SQL},"
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
            counts = dict.fromkeys(STAGES, 0)
            for row in connection.execute(
                "SELECT app.status,count(*) n" + base + counted + " GROUP BY app.status",
                counted_args,
            ):
                counts[row["status"]] = row["n"]
            counts["ready"] = connection.execute(
                "SELECT count(*)"
                + base
                + (counted + " AND " if counted else " WHERE ")
                + READY_SQL,
                counted_args,
            ).fetchone()[0]
            identifiers = [row["id"] for row in rows]
            ready = readiness(connection, rows)
            preparation = self._application_preparation(connection, identifiers)
            answers = last_replies(connection, identifiers)
            no_reply["overdue"] = connection.execute(
                "SELECT count(*) FROM applications app WHERE " + REPLY_OVERDUE_SQL, (cutoff,)
            ).fetchone()[0]
        items = []
        for raw in rows:
            item = decode_record(
                {key: value for key, value in dict(raw).items() if not key.startswith("j_")},
                ("required_documents",),
            )
            item.pop("requirements")
            item.update(ready[item["id"]])
            item["job"] = self._compact_job(raw)
            item["preparation"] = preparation[item["id"]]
            item["last_reply"] = answers[item["id"]]
            item["stage"] = item.pop("status")
            items.append(item)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "stage_counts": counts,
            "no_reply": no_reply,
        }
