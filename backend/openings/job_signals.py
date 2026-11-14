"""Ingest signals of a job: labels and filters, never an automatic dismissal.

Four signals, all deterministic and without a model:

- ``language``: the language the posting is written in (``language_signals``);
- ``required``: languages the posting states as required (groups, one language of
  a group is enough); a language stated only as an advantage is not required;
- ``duplicate``: the earlier job this one most likely repeats, with the confidence
  of ``duplicates.score_pair`` (at least ``DEFAULT_MIN_CONFIDENCE``). A flag only:
  nothing is merged;
- ``no_longer_listed``: a company board that lists its whole board stopped listing
  the posting. It is an observation (``postings.unlisted_at``), cleared when the
  posting is seen again; search results never say that a posting is gone.

The text signals are stored in ``job_signals`` (derived, rebuildable: a row of
another ``language_signals.FORMAT`` is computed again) when a job is collected or
its title or posting changes. The duplicate is computed once, when the job is
collected (or by the backfill for jobs collected before schema 12), against the
jobs collected earlier. Signals label jobs and filter lists; they never dismiss a job.
"""

from __future__ import annotations

import json
import logging
import threading

from .collectors.catalog import COMPANY_KINDS
from .common import encode, now
from .duplicates import confidence_tier
from .language_signals import FORMAT, NAMES, fold, text_signals
from .posting import matches_filters

LOG = logging.getLogger(__name__)

# The compact signals of a job in list queries (one primary-key read per row).
SIGNALS_SQL = (
    "(SELECT json_object('format',s.format,'language',s.language,'language_confidence',"
    "s.language_confidence,'required',json(s.required),"
    "'duplicate_checked',s.duplicate_checked,'duplicate_of',s.duplicate_of,"
    "'duplicate_confidence',s.duplicate_confidence) "
    "FROM job_signals s WHERE s.job_id={alias}.id)"
)
UNLISTED_SQL = (
    "(SELECT max(p.unlisted_at) FROM postings p WHERE p.job_id={alias}.id "
    "AND p.unlisted_at IS NOT NULL)"
)
DISMISSAL_COLUMNS = ("dismissed_at", "dismissed_by", "dismissed_reason")
# Who dismissed a job (its actor label), as the Dismissed tab groups it. A job
# dismissed without a record (before 0.21) counts as system.
DISMISSED_BY = {
    "agent": "j.dismissed_by LIKE 'agent:%'",
    "owner": "j.dismissed_by='owner'",
    "system": "coalesce(j.dismissed_by,'system')='system'",
}


def dismissed_by_category(label):
    """owner, agent or system for an actor label (None counts as system)."""
    if label and label.startswith("agent:"):
        return "agent"
    return "owner" if label == "owner" else "system"


SIGNAL_FILTERS = {
    "likely_duplicate": "EXISTS(SELECT 1 FROM job_signals s WHERE s.job_id=j.id "
    "AND s.duplicate_of IS NOT NULL)",
    "no_longer_listed": "EXISTS(SELECT 1 FROM postings p WHERE p.job_id=j.id "
    "AND p.unlisted_at IS NOT NULL)",
    "language_required": "EXISTS(SELECT 1 FROM job_signals s WHERE s.job_id=j.id "
    "AND s.required<>'[]')",
    "pending": "NOT EXISTS(SELECT 1 FROM job_signals s WHERE s.job_id=j.id)",
}
_BATCH = 200


def signal_record(raw, unlisted_at=None):
    """The signals of a job as reads return them; ``computed`` is false until stored."""
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not data:
        return {
            "computed": False,
            "language": None,
            "language_confidence": None,
            "required": [],
            "duplicate_checked": False,
            "duplicate": None,
            "no_longer_listed": unlisted_at is not None,
            "unlisted_at": unlisted_at,
        }
    duplicate = None
    if data.get("duplicate_of"):
        confidence = data["duplicate_confidence"]
        duplicate = {
            "job_id": data["duplicate_of"],
            "confidence": confidence,
            "tier": confidence_tier(confidence),
        }
    return {
        "computed": True,
        "language": data["language"],
        "language_confidence": data["language_confidence"],
        "required": data["required"],
        "duplicate_checked": bool(data["duplicate_checked"]),
        "duplicate": duplicate,
        "no_longer_listed": unlisted_at is not None,
        "unlisted_at": unlisted_at,
    }


def dismissal_record(row):
    """Who dismissed a job, when and why; None unless dismissed."""
    values = {name: row.pop(name, None) for name in DISMISSAL_COLUMNS}
    if row.get("triage") != "dismissed":
        return None
    return {
        "at": values["dismissed_at"],
        "by": values["dismissed_by"],
        "category": dismissed_by_category(values["dismissed_by"]),
        "reason": values["dismissed_reason"] or "",
    }


def store_text_signals(conn, job_id, title, posting, content_version, stamp=None):
    """Compute and store the text signals of one job, keeping its duplicate."""
    found = text_signals(title, posting)
    conn.execute(
        "INSERT INTO job_signals(job_id,format,content_version,language,language_confidence,"
        "required,computed_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET "
        "format=excluded.format,content_version=excluded.content_version,"
        "language=excluded.language,language_confidence=excluded.language_confidence,"
        "required=excluded.required,computed_at=excluded.computed_at",
        (
            job_id,
            FORMAT,
            content_version,
            found["language"],
            found["language_confidence"],
            encode(found["required"]),
            stamp or now(),
        ),
    )
    return found


def normalize_languages(values):
    """Language codes: "English" and "en" are both en."""
    result = []
    for value in values:
        key = fold(value).strip()
        code = key if len(key) == 2 else NAMES.get(key, key)
        if code not in result:
            result.append(code)
    return result


# Collection: postings a whole board no longer lists ---------------------------


def board_prefix(source):
    """The identity prefix of a company board's postings, or None for other sources."""
    if source.get("kind") not in COMPANY_KINDS:
        return None
    config = source.get("config") or {}
    board = config.get("board") or config.get("host") or ""
    return f"{source['kind']}:{board}:" if board else None


def unlist_missing(conn, source, started_at, stamp):
    """Mark the board's postings not seen since ``started_at`` as no longer listed.

    Called after a collection task inspected the whole board: a posting of that
    board whose job still matches the source's filters and that the run did not
    see again is no longer listed. Returns the ids of the jobs newly marked.
    """
    prefix = board_prefix(source)
    if prefix is None:
        return []
    filters = (source.get("config") or {}).get("filters") or {}
    rows = conn.execute(
        "SELECT p.id,p.job_id,j.title,j.location FROM postings p JOIN jobs j ON j.id=p.job_id "
        "WHERE p.identity>=? AND p.identity<? AND p.unlisted_at IS NULL AND p.last_seen_at<?",
        (prefix, prefix + "￿", started_at),
    ).fetchall()
    marked = []
    for posting_id, job_id, title, location in rows:
        if not matches_filters({"title": title, "location": location}, filters):
            continue  # the filters changed: the run could not have seen it
        conn.execute("UPDATE postings SET unlisted_at=? WHERE id=?", (stamp, posting_id))
        if job_id not in marked:
            marked.append(job_id)
    return marked


class SignalService:
    """Computes signals at ingest and fills signals of older jobs."""

    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db
        self._backfill = threading.Lock()

    # Ingest -------------------------------------------------------------------

    def after_ingest(self, job_id):
        """Second step of ingesting a new job: its duplicate.

        Runs outside the collector's database lock: building the duplicate index
        the first time after a start reads every job.
        """
        duplicate = self.workspace.earlier_duplicate(job_id)
        with self.db.transaction() as conn:
            if not conn.execute("SELECT 1 FROM job_signals WHERE job_id=?", (job_id,)).fetchone():
                return  # deleted or merged meanwhile
            self._store_duplicate(conn, job_id, duplicate)

    @staticmethod
    def _store_duplicate(conn, job_id, duplicate):
        other, confidence = duplicate or (None, None)
        if (
            other is not None
            and not conn.execute("SELECT 1 FROM jobs WHERE id=?", (other,)).fetchone()
        ):
            other, confidence = None, None
        conn.execute(
            "UPDATE job_signals SET duplicate_checked=1,duplicate_of=?,duplicate_confidence=? "
            "WHERE job_id=?",
            (other, confidence, job_id),
        )

    # Backfill -----------------------------------------------------------------

    def backfill(self, stopping=None, duplicates=True):
        """Compute the signals jobs do not have yet, in short batches.

        First the text signals of jobs without a row (or with a row of another
        format), then the duplicate of every job not
        checked yet, against the jobs collected before it. Returns the counts.
        """
        counts = {"text": 0, "duplicates": 0}
        with self._backfill:
            while not (stopping and stopping.is_set()):
                with self.db.connect() as conn:
                    rows = conn.execute(
                        "SELECT j.id,j.title,substr(j.posting,1,100000),j.content_version "
                        "FROM jobs j LEFT JOIN job_signals s ON s.job_id=j.id "
                        "WHERE s.job_id IS NULL OR s.format<>? "
                        "ORDER BY j.rowid LIMIT ?",
                        (FORMAT, _BATCH),
                    ).fetchall()
                if not rows:
                    break
                computed = [(row[0], row[1], row[2], row[3]) for row in rows]
                stamp = now()
                with self.db.transaction() as conn:
                    for job_id, title, posting, version in computed:
                        store_text_signals(conn, job_id, title, posting, version, stamp)
                counts["text"] += len(computed)
            if not duplicates:
                return counts
            while not (stopping and stopping.is_set()):
                with self.db.connect() as conn:
                    ids = [
                        row[0]
                        for row in conn.execute(
                            "SELECT job_id FROM job_signals WHERE duplicate_checked=0 "
                            "ORDER BY rowid LIMIT ?",
                            (_BATCH,),
                        )
                    ]
                if not ids:
                    break
                found = self.workspace.earlier_duplicates(ids)
                with self.db.transaction() as conn:
                    for job_id in ids:
                        self._store_duplicate(conn, job_id, found.get(job_id))
                counts["duplicates"] += len(ids)
        return counts
