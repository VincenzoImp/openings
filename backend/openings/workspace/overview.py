"""The overview: funnel counts and activity from recorded application history."""

from ..events import event_record
from ..posting import posting_complete_sql


class Overview:
    """Reporting over recorded history."""

    def overview(self, since=None, until=None):
        conditions, bounds = [], []
        for value, operator in ((since, ">="), (until, "<=")):
            if value:
                conditions.append("coalesce(applied_at,created_at)" + operator + "?")
                bounds.append(value)
        cohort = "SELECT id FROM applications" + (
            " WHERE " + " AND ".join(conditions) if conditions else ""
        )
        apps = self.db.all(
            "SELECT id,status,outcome,applied_at,ready_at FROM applications WHERE id IN ("
            + cohort
            + ")",
            bounds,
        )
        stages = ["applied", "interview", "offer"]
        funnel = [
            {
                "stage": s,
                "count": 0,
                "outcomes": {
                    "waiting": 0,
                    "rejected": 0,
                    "not_pursued": 0,
                    "accepted": 0,
                    "no_response": 0,
                },
            }
            for s in stages
        ]
        observed_by_app = {}
        # Only stage changes carry a target stage; other application events are skipped
        # and the distinct stages are reduced in SQLite rather than row by row.
        for event in self.db.all(
            "SELECT DISTINCT application_id,json_extract(payload,'$.to') AS stage FROM events "
            "WHERE kind='application_updated' AND application_id IN (" + cohort + ")",
            bounds,
        ):
            observed_by_app.setdefault(event["application_id"], set()).add(event["stage"])
        sent = 0
        for app in apps:
            observed = set(observed_by_app.get(app["id"], ()))
            if app["applied_at"]:
                observed.add("applied")
            if app["outcome"] == "accepted":
                observed.add("offer")
            if "applied" not in observed:
                continue
            sent += 1
            reached = [i for i, s in enumerate(stages) if s in observed or app["status"] == s]
            highest = max(reached, default=0)
            for i in range(highest + 1):
                funnel[i]["count"] += 1
            outcome = (app["outcome"] or "not_pursued") if app["status"] == "closed" else "waiting"
            funnel[highest]["outcomes"][outcome] += 1
        counts = self.db.one(
            "SELECT count(*) n,coalesce(sum(triage='inbox' AND NOT EXISTS (SELECT 1 FROM applications WHERE job_id=j.id)),0) inbox,coalesce(sum(NOT "
            + posting_complete_sql()
            + "),0) incomplete FROM jobs j WHERE triage!='dismissed'"
        )
        return {
            "sent": sent,
            "interviews": funnel[1]["count"],
            "offers": funnel[2]["count"],
            "active": sum(a["status"] not in {"draft", "closed"} for a in apps),
            "drafts": sum(a["status"] == "draft" for a in apps),
            "ready": sum(a["status"] == "draft" and a["ready_at"] is not None for a in apps),
            "inbox": counts["inbox"],
            "incomplete": counts["incomplete"],
            "funnel": funnel,
            "activity": [
                event_record(r)
                for r in self.db.all(
                    "SELECT events.*,jobs.title,jobs.company FROM events LEFT JOIN jobs ON jobs.id=events.job_id ORDER BY events.created_at DESC LIMIT 12"
                )
            ],
        }
