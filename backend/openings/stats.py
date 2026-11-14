"""Stats: how employers answered the applications the owner sent.

An application counts as sent when it has ``applied_at``, is in Applied,
Interview or Offer, or has an employer reply (``responses``). With a period of
``90d`` or ``12m`` only applications sent (``applied_at``) since then count;
``all`` counts every sent application.

For each sent application: it got a reply when it has any response; it reached
an interview when it has an interview or offer response or was ever moved to
Interview or Offer; it reached an offer when it has an offer response, was moved
to Offer or was accepted. Its days to the first reply are the day of its first
response minus the day of ``applied_at`` (never below zero).

Replies by source are returned only when at least ``MIN_SOURCES`` sources (the
source that first found each job) have ``MIN_PER_SOURCE`` sent applications each,
and then only for those sources: smaller groups say nothing.
"""

import statistics
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from pydantic import Field

from .models import Input

PERIODS = {"90d": 90, "12m": 365, "all": None}
MIN_SOURCES = 2
MIN_PER_SOURCE = 5
OTHER_SOURCE = "Added by hand or removed source"

_SENT = """
SELECT a.id,a.status,a.outcome,a.applied_at,
 (SELECT min(r.date) FROM responses r WHERE r.application_id=a.id) AS first_reply,
 EXISTS(SELECT 1 FROM responses r WHERE r.application_id=a.id
  AND r.kind IN ('interview','offer')) AS interview_reply,
 EXISTS(SELECT 1 FROM responses r WHERE r.application_id=a.id AND r.kind='offer') AS offer_reply,
 (SELECT group_concat(DISTINCT json_extract(e.payload,'$.to')) FROM events e
  WHERE e.application_id=a.id AND e.kind='application_updated') AS stages,
 (SELECT s.name FROM postings p JOIN sources s ON s.id=p.source_id WHERE p.job_id=a.job_id
  ORDER BY p.first_seen_at,p.id LIMIT 1) AS source
FROM applications a
WHERE (a.applied_at IS NOT NULL OR a.status IN ('applied','interview','offer')
 OR EXISTS(SELECT 1 FROM responses r WHERE r.application_id=a.id)) {period}
"""


class StatsQuery(Input):
    period: Literal["90d", "12m", "all"] = Field(
        default="90d",
        description="Applications sent in the last 90 days (90d), the last 12 months (12m) or ever (all).",
    )


def _rate(count, total):
    return round(count / total, 4) if total else None


def _offer(row):
    stages = (row["stages"] or "").split(",")
    return bool(
        row["offer_reply"]
        or row["status"] == "offer"
        or row["outcome"] == "accepted"
        or "offer" in stages
    )


def _interview(row):
    stages = (row["stages"] or "").split(",")
    return bool(
        row["interview_reply"] or row["status"] == "interview" or "interview" in stages
    ) or _offer(row)


def _days(row):
    if not (row["first_reply"] and row["applied_at"]):
        return None
    reply = date.fromisoformat(row["first_reply"])
    return max(0, (reply - date.fromisoformat(row["applied_at"][:10])).days)


class StatsService:
    def __init__(self, workspace):
        self.db = workspace.db

    def stats(self, value: StatsQuery | None = None) -> dict:
        """Applied count, reply and interview rates, median days to a reply and the funnel."""
        value = value if isinstance(value, StatsQuery) else StatsQuery.model_validate(value or {})
        days = PERIODS[value.period]
        since = (datetime.now(UTC).date() - timedelta(days=days)).isoformat() if days else None
        rows = self.db.all(
            _SENT.format(period="AND a.applied_at>=?" if since else ""),
            (since,) if since else (),
        )
        applied = len(rows)
        replied = sum(row["first_reply"] is not None for row in rows)
        interviews = sum(map(_interview, rows))
        offers = sum(map(_offer, rows))
        waits = [wait for wait in map(_days, rows) if wait is not None]
        by_source = {}
        for row in rows:
            counts = by_source.setdefault(row["source"] or OTHER_SOURCE, [0, 0])
            counts[0] += 1
            counts[1] += row["first_reply"] is not None
        enough = {name: counts for name, counts in by_source.items() if counts[0] >= MIN_PER_SOURCE}
        return {
            "period": value.period,
            "since": since,
            "applied": applied,
            "replied": replied,
            "reply_rate": _rate(replied, applied),
            "interviews": interviews,
            "interview_rate": _rate(interviews, applied),
            "median_days_to_reply": statistics.median(waits) if waits else None,
            "funnel": [
                {"stage": "applied", "count": applied},
                {"stage": "replied", "count": replied},
                {"stage": "interview", "count": interviews},
                {"stage": "offer", "count": offers},
            ],
            "by_source": [
                {"source": name, "applied": sent, "replied": got, "reply_rate": _rate(got, sent)}
                for name, (sent, got) in sorted(
                    enough.items(), key=lambda item: (-item[1][0], item[0])
                )
            ]
            if len(enough) >= MIN_SOURCES
            else None,
        }
