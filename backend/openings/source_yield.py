"""Yield of each collection source: what it collected and what became of those jobs.

A job belongs to the source that first collected it: the observation with a source
that was seen first. Every job is counted once, so the rows add up to the total.
Jobs without such an observation (added by URL or pasted, or collected by a source
that was removed since) form one row of their own.

For the jobs a source collected in the period (by the time the job was added):

- ``collected``: all of them;
- ``to_review``: still in the Inbox, without an application;
- ``shortlisted``: kept, in the Shortlist or with an application of any outcome;
- ``applied``: with an application that was sent (as Insights counts it: a sent
  date, a sent stage or an employer response);
- ``responded``, ``interviews``, ``offers``: with an employer response, an
  interview or offer response, an offer response (``replies``);
- ``dismissed``: dismissed now, split by who dismissed them (an agent token, the
  owner, other);
- ``likely_duplicates`` and ``no_longer_listed``: jobs with those ingest signals.

``kept_rate`` is shortlisted over collected; it is withheld (``null``) for a source
that collected fewer than ``min_sample`` jobs in the period.
"""

import json

from pydantic import Field, field_validator, model_validator

from .insights import source_kind, source_name
from .job_signals import DISMISSED_BY
from .models import Input, normalized_date

DEFAULT_MIN_SAMPLE = 10
KIND_LABELS = {
    "search": "Search",
    "company": "Company board",
    "feed": "Feed",
    "manual": "Added by hand",
}
COUNTS = (
    "collected",
    "to_review",
    "shortlisted",
    "applied",
    "responded",
    "interviews",
    "offers",
    "dismissed",
    "likely_duplicates",
    "no_longer_listed",
)


class YieldQuery(Input):
    since: str | None = Field(
        default=None, description="Only jobs collected (added) at or after this time."
    )
    until: str | None = Field(
        default=None, description="Only jobs collected (added) at or before this time."
    )
    min_sample: int = Field(
        default=DEFAULT_MIN_SAMPLE,
        ge=1,
        le=1000,
        description="The fewest collected jobs a kept rate needs; below it kept_rate is null with withheld.",
    )

    @field_validator("since", "until")
    @classmethod
    def valid_date(cls, value, info):
        return normalized_date(value, end=info.field_name == "until")

    @model_validator(mode="after")
    def valid_range(self):
        if self.since and self.until and self.since > self.until:
            raise ValueError("The start date must not follow the end date.")
        return self


# One row per job, with the source that first collected it and what became of it.
_JOBS = """
WITH first AS (
 SELECT job_id, source_id FROM (
  SELECT job_id, source_id, row_number() OVER (PARTITION BY job_id ORDER BY first_seen_at, id) AS n
  FROM postings WHERE source_id IS NOT NULL) WHERE n = 1),
attempts AS (
 SELECT job_id, max(applied_at IS NOT NULL OR status IN ('applied','interview','offer')) AS sent
 FROM applications GROUP BY job_id),
answers AS (
 SELECT a.job_id, max(r.kind IN ('interview','offer')) AS interview, max(r.kind = 'offer') AS offer
 FROM replies r JOIN applications a ON a.id = r.application_id GROUP BY a.job_id)
SELECT f.source_id AS source_id,
 coalesce(json_extract(j.metadata,'$.source'), json_extract(j.metadata,'$.ats'), 'manual') AS provider,
 count(*) AS collected,
 sum(j.triage = 'new' AND t.job_id IS NULL) AS to_review,
 sum(j.triage = 'shortlisted' OR t.job_id IS NOT NULL) AS shortlisted,
 sum(coalesce(t.sent, 0) OR r.job_id IS NOT NULL) AS applied,
 sum(r.job_id IS NOT NULL) AS responded,
 sum(coalesce(r.interview, 0)) AS interviews,
 sum(coalesce(r.offer, 0)) AS offers,
 sum(j.triage = 'dismissed') AS dismissed,
 {dismissed_by},
 sum(EXISTS(SELECT 1 FROM job_signals s WHERE s.job_id = j.id AND s.duplicate_of IS NOT NULL)) AS likely_duplicates,
 sum(EXISTS(SELECT 1 FROM postings p WHERE p.job_id = j.id AND p.unlisted_at IS NOT NULL)) AS no_longer_listed
FROM jobs j
LEFT JOIN first f ON f.job_id = j.id
LEFT JOIN attempts t ON t.job_id = j.id
LEFT JOIN answers r ON r.job_id = j.id
{where}
GROUP BY f.source_id, provider
"""


def _empty():
    return {
        **dict.fromkeys(COUNTS, 0),
        "dismissed_by": dict.fromkeys(DISMISSED_BY, 0),
    }


def _add(target, row):
    for key in COUNTS:
        target[key] += row[key] or 0
    for key in DISMISSED_BY:
        target["dismissed_by"][key] += row["dismissed_by_" + key] or 0


def _rate(item, min_sample):
    enough = item["collected"] >= min_sample
    item["kept_rate"] = round(item["shortlisted"] / item["collected"], 4) if enough else None
    item["withheld"] = None if enough else "too_few_collected"
    return item


class YieldService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db

    def source_yield(self, value: YieldQuery | None = None) -> dict:
        """What each source and search collected, and how many were kept, applied to and answered."""
        value = value if isinstance(value, YieldQuery) else YieldQuery.model_validate(value or {})
        conditions, args = [], []
        for bound, operator in ((value.since, ">="), (value.until, "<=")):
            if bound:
                conditions.append("j.created_at" + operator + "?")
                args.append(bound)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        dismissed_by = ",".join(
            f"sum(j.triage = 'dismissed' AND {sql}) AS dismissed_by_{key}"
            for key, sql in DISMISSED_BY.items()
        )
        with self.db.connect() as conn:
            sources = {
                row["id"]: dict(row)
                for row in conn.execute(
                    "SELECT id,name,kind,config,enabled,last_run_at,last_error FROM sources "
                    "ORDER BY name,id"
                )
            }
            groups = conn.execute(
                _JOBS.format(dismissed_by=dismissed_by, where=where), args
            ).fetchall()
        rows = {}

        def row_of(source_id):
            if source_id not in rows:
                source = sources.get(source_id)
                if source is None:
                    rows[source_id] = {
                        "source_id": None,
                        "name": "Added by hand or by a removed source",
                        "kind": "manual",
                        "kind_label": KIND_LABELS["manual"],
                        "source_kind": None,
                        "enabled": None,
                        "last_run_at": None,
                        "last_error": None,
                        "providers": [],
                        **_empty(),
                    }
                else:
                    config = json.loads(source["config"] or "{}")
                    kind = source_kind(source["kind"], {})
                    rows[source_id] = {
                        "source_id": source_id,
                        "name": source["name"],
                        "kind": kind,
                        "kind_label": KIND_LABELS.get(kind, kind),
                        "source_kind": source["kind"],
                        "enabled": bool(source["enabled"]),
                        "last_run_at": source["last_run_at"],
                        "last_error": source["last_error"],
                        "providers": [],
                        "configured_providers": config.get("providers")
                        if source["kind"] == "jobspy"
                        else None,
                        **_empty(),
                    }
            return rows[source_id]

        for source_id in sources:
            row_of(source_id)
        for group in groups:
            source_id = group["source_id"] if group["source_id"] in sources else None
            item = row_of(source_id)
            _add(item, group)
            # A search reports what each job board gave it.
            if item["kind"] == "search" or source_id is None:
                provider = {
                    "provider": group["provider"],
                    "label": source_name(None, "search", {"source": group["provider"]})
                    if group["provider"] != "manual"
                    else "Added by hand",
                    **{key: group[key] or 0 for key in COUNTS},
                }
                known = next(
                    (p for p in item["providers"] if p["provider"] == group["provider"]), None
                )
                if known is None:
                    item["providers"].append(provider)
                else:
                    for key in COUNTS:
                        known[key] += provider[key]
        items = list(rows.values())
        total = {
            **_empty(),
            "name": "All sources",
            "sources": sum(item["source_id"] is not None for item in items),
        }
        for item in items:
            for key in COUNTS:
                total[key] += item[key]
            for key in DISMISSED_BY:
                total["dismissed_by"][key] += item["dismissed_by"][key]
            item["providers"].sort(key=lambda p: (-p["collected"], p["label"]))
            _rate(item, value.min_sample)
        _rate(total, value.min_sample)
        # Busiest sources first; the row without a source last.
        items.sort(key=lambda item: (item["source_id"] is None, -item["collected"], item["name"]))
        return {
            "period": {"since": value.since, "until": value.until},
            "min_sample": value.min_sample,
            "items": items,
            "total": total,
        }
