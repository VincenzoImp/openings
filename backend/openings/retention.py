"""What the workspace keeps of routine collection work, and for how long.

A source refresh that only sights a posting again leaves no event; one that changes
what the owner reads leaves one ``job_refreshed`` event naming the changed fields.
An observation keeps the two provider values the archive reads, not the provider's
whole response. Finished collection runs and tasks older than the retention period
are removed in small batches, except the most recent runs of every source.
"""

import logging
import os
from datetime import datetime, timedelta

from .common import now

LOG = logging.getLogger(__name__)
# Job fields the owner reads; a refresh that changes none of them is a re-sighting.
REFRESH_FIELDS = ("title", "company", "location", "posting")
REFRESH_EVENT = "job_refreshed"
DEFAULT_RETENTION_DAYS = 90
# Finished runs kept for every source whatever their age: "last run" and run history.
KEPT_RUNS_PER_SOURCE = 20
# One pass removes at most this many runs, tasks and events of each kind.
PRUNE_BATCH = 500
# Days an idempotency key keeps answering retries before it is forgotten.
IDEMPOTENCY_KEY_DAYS = 30
_FINISHED = "('succeeded','failed','cancelled')"


def observation_payload(data):
    """The part of an ingested posting an observation keeps.

    ``source_key`` finds the observation again at the next refresh, and
    ``raw.job_url_direct`` is the employer's own apply link a job board reported,
    read by duplicate scoring. Title, text and metadata live on the job.
    """
    kept = {}
    direct = (data.get("raw") or {}).get("job_url_direct")
    if direct is not None:
        kept["raw"] = {"job_url_direct": direct}
    if data.get("source_key") is not None:
        kept["source_key"] = data["source_key"]
    return kept


def retention_days():
    """Days finished collection work is kept (``OPENINGS_RETENTION_DAYS``); 0 keeps everything."""
    try:
        return max(0, int(os.environ.get("OPENINGS_RETENTION_DAYS") or DEFAULT_RETENTION_DAYS))
    except ValueError:
        LOG.warning(
            "OPENINGS_RETENTION_DAYS is not a number; using %d days.", DEFAULT_RETENTION_DAYS
        )
        return DEFAULT_RETENTION_DAYS


def prune_idempotency_keys(db, days=IDEMPOTENCY_KEY_DAYS, batch=PRUNE_BATCH):
    """Forget one bounded batch of idempotency keys older than ``days``; return how many.

    A retry comes within minutes or hours of its first request; after a month the
    key only takes room. The records the keys point to stay.
    """
    cutoff = (datetime.fromisoformat(now()) - timedelta(days=days)).isoformat(
        timespec="microseconds"
    )
    with db.transaction() as conn:
        return conn.execute(
            "DELETE FROM idempotency_keys WHERE (scope,key) IN (SELECT scope,key FROM "
            "idempotency_keys WHERE created_at<? ORDER BY created_at LIMIT ?)",
            (cutoff, batch),
        ).rowcount


def prune(db, days=None, keep=KEPT_RUNS_PER_SOURCE, batch=PRUNE_BATCH):
    """Remove one bounded batch of old finished collection work; report what was removed.

    A run is finished when none of its tasks is queued or running, so work in
    progress and its checkpoint are never touched. Job and application history is
    never removed: only records of runs and tasks that no longer exist, written
    outside an agent run, go with them.
    """
    days = retention_days() if days is None else days
    removed = {"runs": 0, "tasks": 0, "events": 0, "keys": 0, "more": False}
    removed["keys"] = prune_idempotency_keys(db, batch=batch)
    removed["more"] = removed["keys"] >= batch
    if days <= 0:
        return removed
    cutoff = (datetime.fromisoformat(now()) - timedelta(days=days)).isoformat(
        timespec="microseconds"
    )
    with db.transaction() as conn:
        runs = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM (SELECT r.id,r.source_id,r.created_at,ROW_NUMBER() OVER "
                "(PARTITION BY r.source_id ORDER BY r.created_at DESC,r.id DESC) AS position "
                "FROM collection_runs r WHERE NOT EXISTS(SELECT 1 FROM tasks t WHERE "
                "t.run_id=r.id AND t.state NOT IN " + _FINISHED + ")) "
                "WHERE created_at<? AND (source_id IS NULL OR position>?) "
                "ORDER BY created_at,id LIMIT ?",
                (cutoff, keep, batch),
            )
        ]
        if runs:
            marks = ",".join("?" for _ in runs)
            removed["tasks"] = conn.execute(
                f"SELECT count(*) FROM tasks WHERE run_id IN ({marks})", runs
            ).fetchone()[0]
            conn.execute(f"DELETE FROM collection_runs WHERE id IN ({marks})", runs)
            removed["runs"] = len(runs)
        # Finished tasks that belong to no run.
        loose = conn.execute(
            "DELETE FROM tasks WHERE id IN (SELECT id FROM tasks WHERE run_id IS NULL AND "
            "state IN " + _FINISHED + " AND updated_at<? ORDER BY updated_at LIMIT ?)",
            (cutoff, batch),
        ).rowcount
        removed["tasks"] += loose
        events = 0
        for kind, table in (("collection_run", "collection_runs"), ("task", "tasks")):
            events += conn.execute(
                "DELETE FROM events WHERE id IN (SELECT e.id FROM events e WHERE "
                "e.subject_type=? AND e.created_at<? AND e.job_id IS NULL AND "
                "e.application_id IS NULL AND e.run_id IS NULL AND NOT EXISTS("
                f"SELECT 1 FROM {table} s WHERE s.id=e.subject_id) LIMIT ?)",
                (kind, cutoff, batch),
            ).rowcount
        removed["events"] = events
        removed["more"] = removed["more"] or len(runs) >= batch or loose >= batch or events >= batch
    if removed["runs"] or removed["tasks"] or removed["events"]:
        LOG.info(
            "Pruned %d collection runs, %d tasks and %d of their records older than %d days.",
            removed["runs"],
            removed["tasks"],
            removed["events"],
            days,
        )
    return removed
