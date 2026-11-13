"""Ingest signals of a job and the policy rules that act on them.

Four signals, all deterministic and without a model:

- ``language``: the language the posting is written in (``language_signals``);
- ``required`` and ``welcome``: languages the posting states as required (groups,
  one language of a group is enough) or as an advantage;
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
jobs collected earlier.

**Rules.** A ``decision`` policy item with a rule acts only while it is enabled
and confirmed by the owner. Rules act once, when their signal arrives for a job
nobody has triaged: at ingest for the text and duplicate signals, and when a
collection run finds a posting no longer listed. They never act on jobs already
reviewed, so restoring a job keeps it restored. A ``dismiss`` rule dismisses the
job as the system, with the rule's item id and label on the job's dismissal and
the item id in the ``triage_changed`` event; a ``flag`` rule only records that it
matched. The first matching dismiss rule in policy order wins.
"""

from __future__ import annotations

import json
import logging
import threading

from .actors import pop_actor
from .collectors.catalog import COMPANY_KINDS
from .common import encode, now
from .duplicates import confidence_tier
from .language_signals import FORMAT, NAMES, fold, text_signals
from .posting import matches_filters

LOG = logging.getLogger(__name__)

# Mirrored in schema.sql; the 11 -> 12 migration creates the same objects.
SCHEMA = """
CREATE TABLE IF NOT EXISTS job_signals (
 job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
 format INTEGER NOT NULL, content_version INTEGER NOT NULL,
 language TEXT, language_confidence REAL,
 required TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(required)),
 welcome TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(welcome)),
 duplicate_checked INTEGER NOT NULL DEFAULT 0 CHECK(duplicate_checked IN (0,1)),
 duplicate_of TEXT REFERENCES jobs(id) ON DELETE SET NULL, duplicate_confidence REAL,
 distinct_from TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(distinct_from)),
 rules TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(rules)),
 computed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS job_signals_duplicate ON job_signals(duplicate_of);
CREATE INDEX IF NOT EXISTS job_signals_language ON job_signals(language);
CREATE INDEX IF NOT EXISTS postings_unlisted ON postings(job_id) WHERE unlisted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS jobs_dismissed_rule ON jobs(dismissed_rule_id) WHERE dismissed_rule_id IS NOT NULL;
"""
# Columns schema 12 adds to existing tables, in the order schema.sql lists them.
JOB_COLUMNS = (
    "dismissed_at TEXT",
    "dismissed_by_kind TEXT",
    "dismissed_by_id TEXT",
    "dismissed_by_name TEXT",
    "dismissed_by_token_kind TEXT",
    "dismissed_rule_id TEXT",
    "dismissed_rule_label TEXT",
    "dismissed_reason TEXT NOT NULL DEFAULT ''",
)
POSTING_COLUMNS = ("unlisted_at TEXT",)
# The compact signals of a job in list queries (one primary-key read per row).
SIGNALS_SQL = (
    "(SELECT json_object('format',s.format,'language',s.language,'language_confidence',"
    "s.language_confidence,'required',json(s.required),'welcome',json(s.welcome),"
    "'duplicate_checked',s.duplicate_checked,'duplicate_of',s.duplicate_of,"
    "'duplicate_confidence',s.duplicate_confidence,'rules',json(s.rules)) "
    "FROM job_signals s WHERE s.job_id={alias}.id)"
)
UNLISTED_SQL = (
    "(SELECT max(p.unlisted_at) FROM postings p WHERE p.job_id={alias}.id "
    "AND p.unlisted_at IS NOT NULL)"
)
DISMISSAL_COLUMNS = (
    "dismissed_at",
    "dismissed_by_kind",
    "dismissed_by_id",
    "dismissed_by_name",
    "dismissed_by_token_kind",
    "dismissed_rule_id",
    "dismissed_rule_label",
    "dismissed_reason",
)
# Who dismissed a job, as the Dismissed tab groups it.
DISMISSED_BY = {
    "rule": "j.dismissed_rule_id IS NOT NULL",
    "agent": "j.dismissed_rule_id IS NULL AND j.dismissed_by_kind='token' "
    "AND j.dismissed_by_token_kind='agent'",
    "owner": "j.dismissed_rule_id IS NULL AND (j.dismissed_by_kind='owner' OR "
    "(j.dismissed_by_kind='token' AND coalesce(j.dismissed_by_token_kind,'owner')='owner'))",
}
# Without a record (dismissed before 0.21 without an event) the conditions above
# are NULL, not false: coalesce so that those jobs count as other.
DISMISSED_BY["other"] = (
    "NOT (" + " OR ".join(f"coalesce(({sql}),0)" for sql in DISMISSED_BY.values()) + ")"
)
SIGNAL_FILTERS = {
    "likely_duplicate": "EXISTS(SELECT 1 FROM job_signals s WHERE s.job_id=j.id "
    "AND s.duplicate_of IS NOT NULL)",
    "no_longer_listed": "EXISTS(SELECT 1 FROM postings p WHERE p.job_id=j.id "
    "AND p.unlisted_at IS NOT NULL)",
    "language_required": "EXISTS(SELECT 1 FROM job_signals s WHERE s.job_id=j.id "
    "AND s.required<>'[]')",
    "flagged": "EXISTS(SELECT 1 FROM job_signals s, json_each(s.rules) r WHERE s.job_id=j.id "
    "AND json_extract(r.value,'$.action')='flag')",
    "pending": "NOT EXISTS(SELECT 1 FROM job_signals s WHERE s.job_id=j.id)",
}
# A job nobody has reviewed: in the Inbox, without an application or a triage change.
UNTOUCHED_SQL = (
    "j.triage='inbox' AND NOT EXISTS(SELECT 1 FROM applications a WHERE a.job_id=j.id) "
    "AND NOT EXISTS(SELECT 1 FROM events e WHERE e.job_id=j.id AND e.kind='triage_changed')"
)
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
            "welcome": [],
            "duplicate_checked": False,
            "duplicate": None,
            "no_longer_listed": unlisted_at is not None,
            "unlisted_at": unlisted_at,
            "rules": [],
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
        "welcome": data["welcome"],
        "duplicate_checked": bool(data["duplicate_checked"]),
        "duplicate": duplicate,
        "no_longer_listed": unlisted_at is not None,
        "unlisted_at": unlisted_at,
        "rules": data["rules"],
    }


def dismissal_record(row):
    """Who dismissed a job, when, why and through which rule; None unless dismissed."""
    values = {name: row.pop(name, None) for name in DISMISSAL_COLUMNS}
    if row.get("triage") != "dismissed":
        return None
    by = pop_actor(
        {
            f"dismissed_by_{suffix}": values[f"dismissed_by_{suffix}"]
            for suffix in ("kind", "id", "name", "token_kind")
        },
        "dismissed_by",
    )
    rule = (
        {"item_id": values["dismissed_rule_id"], "label": values["dismissed_rule_label"] or ""}
        if values["dismissed_rule_id"]
        else None
    )
    category = (
        "rule"
        if rule
        else "agent"
        if by["kind"] == "token" and by["token_kind"] == "agent"
        else "owner"
        if by["kind"] == "owner" or (by["kind"] == "token")
        else "other"
    )
    return {
        "at": values["dismissed_at"],
        "by": by,
        "category": category,
        "rule": rule,
        "reason": values["dismissed_reason"] or "",
    }


def store_text_signals(conn, job_id, title, posting, content_version, stamp=None):
    """Compute and store the text signals of one job, keeping its duplicate and rules."""
    found = text_signals(title, posting)
    conn.execute(
        "INSERT INTO job_signals(job_id,format,content_version,language,language_confidence,"
        "required,welcome,computed_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET "
        "format=excluded.format,content_version=excluded.content_version,"
        "language=excluded.language,language_confidence=excluded.language_confidence,"
        "required=excluded.required,welcome=excluded.welcome,computed_at=excluded.computed_at",
        (
            job_id,
            FORMAT,
            content_version,
            found["language"],
            found["language_confidence"],
            encode(found["required"]),
            encode(found["welcome"]),
            stamp or now(),
        ),
    )
    return found


# Rules -----------------------------------------------------------------------


def active_rules(conn):
    """Enabled, owner-confirmed decision rules, in policy order."""
    return [
        {"item_id": row[0], "label": row[1], **json.loads(row[2])}
        for row in conn.execute(
            "SELECT id,label,rule FROM policy_items WHERE section='decision' AND rule IS NOT NULL "
            "AND enabled=1 AND confirmed_at IS NOT NULL ORDER BY position,created_at,id"
        )
    ]


def rule_matches(rule, signals):
    """True when a rule's condition holds for a job's signals (``signal_record`` shape)."""
    condition = rule["condition"]
    operator, value = condition["operator"], condition["value"]
    signal = rule["signal"]
    if signal == "posting_language":
        language = signals["language"]
        if language is None:
            return False
        return (language in normalize_languages(value)) == (operator == "in")
    if signal == "language_required":
        wanted = set(normalize_languages(value))
        groups = [set(group) for group in signals["required"]]
        if operator == "in":
            # The posting needs one of these languages and accepts no other in its place.
            return any(group <= wanted for group in groups)
        # The posting needs a language outside the list.
        return any(not group & wanted for group in groups)
    if signal == "likely_duplicate":
        duplicate = signals["duplicate"]
        return duplicate is not None and duplicate["confidence"] >= value
    if signal == "no_longer_listed":
        return signals["no_longer_listed"] == value
    return False


def matched_rules(rules, signals, signal_names):
    """The rules of ``signal_names`` that match, and the first matching dismiss rule."""
    matched = [
        {"item_id": rule["item_id"], "label": rule["label"], "action": rule["action"]}
        for rule in rules
        if rule["signal"] in signal_names and rule_matches(rule, signals)
    ]
    dismiss = next((rule for rule in matched if rule["action"] == "dismiss"), None)
    return matched, dismiss


def normalize_languages(values):
    """Language codes of a rule's values: "English" and "en" are both en."""
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


def backfill_unlisted(conn):
    """Schema 11 to 12: postings missed by the last complete run of each board.

    The last succeeded collection task of every company source that inspected the
    whole board (not capped) is read back: an observation of that board that the
    run did not see again (``last_seen_at`` before the run started) is no longer
    listed since the task finished.
    """
    marked = 0
    for snapshot, started_at, finished_at in conn.execute(
        "SELECT r.source_snapshot,json_extract(t.result,'$.started_at'),t.updated_at "
        "FROM tasks t JOIN collection_runs r ON r.id=t.run_id "
        "WHERE t.kind='collect' AND t.state='succeeded' AND t.source_id IS NOT NULL "
        "AND json_valid(t.result) AND json_extract(t.result,'$.started_at') IS NOT NULL "
        "AND coalesce(json_extract(t.result,'$.candidate_capped'),0)=0 "
        "AND coalesce(json_extract(t.result,'$.result_capped'),0)=0 "
        "AND t.rowid=(SELECT t2.rowid FROM tasks t2 WHERE t2.source_id=t.source_id "
        "AND t2.kind='collect' AND t2.state='succeeded' ORDER BY t2.updated_at DESC,t2.rowid DESC LIMIT 1)"
    ).fetchall():
        try:
            source = json.loads(snapshot)
        except ValueError:
            continue
        if isinstance(source, dict):
            marked += len(unlist_missing(conn, source, started_at, finished_at))
    return marked


def backfill_dismissals(conn):
    """Schema 11 to 12: who dismissed each dismissed job, from its last dismissal event."""
    conn.execute(
        "UPDATE jobs SET (dismissed_at,dismissed_by_kind,dismissed_by_id,dismissed_by_name,"
        "dismissed_by_token_kind)=(SELECT e.created_at,e.actor_kind,e.actor_id,e.actor_name,"
        "e.actor_token_kind FROM events e WHERE e.job_id=jobs.id AND e.kind='triage_changed' "
        "AND json_valid(e.payload) AND json_extract(e.payload,'$.to')='dismissed' "
        "ORDER BY e.created_at DESC,e.rowid DESC LIMIT 1) WHERE triage='dismissed'"
    )


def migrate(conn):
    """Schema 11 to 12: signal storage, the dismissal record and listing observations.

    Additive. Existing rows keep every value; the new job columns are filled for
    dismissed jobs from their last dismissal event, and postings a board stopped
    listing are marked from its last complete run. The text and duplicate signals
    of existing jobs are computed after the upgrade (``SignalService.backfill``).
    """
    for column in JOB_COLUMNS:
        conn.execute("ALTER TABLE jobs ADD COLUMN " + column)
    for column in POSTING_COLUMNS:
        conn.execute("ALTER TABLE postings ADD COLUMN " + column)
    # executescript would commit the surrounding upgrade, so run each statement.
    for statement in SCHEMA.split(";\n"):
        if statement.strip():
            conn.execute(statement)
    backfill_dismissals(conn)
    backfill_unlisted(conn)


class SignalService:
    """Computes signals at ingest, applies rules and fills signals of older jobs."""

    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db
        self._backfill = threading.Lock()

    # Ingest -------------------------------------------------------------------

    def after_ingest(self, job_id, apply_rules=True):
        """Second step of ingesting a new job: its duplicate, then the rules.

        Runs outside the collector's database lock: building the duplicate index
        the first time after a start reads every job. ``apply_rules`` is false for
        a job the owner added in the dashboard: a rule never dismisses that.
        """
        duplicate = self.workspace.earlier_duplicate(job_id)
        with self.db.transaction() as conn:
            if not conn.execute("SELECT 1 FROM job_signals WHERE job_id=?", (job_id,)).fetchone():
                return  # deleted or merged meanwhile
            self._store_duplicate(conn, job_id, duplicate)
            row = conn.execute(
                "SELECT "
                + SIGNALS_SQL.format(alias="j")
                + ","
                + UNLISTED_SQL.format(alias="j")
                + " FROM jobs j WHERE j.id=?",
                (job_id,),
            ).fetchone()
            signals = signal_record(row[0], row[1])
            rules = active_rules(conn) if apply_rules else []
            if not rules:
                return
            matched, dismiss = matched_rules(
                rules, signals, {"posting_language", "language_required", "likely_duplicate"}
            )
            self._act(conn, job_id, matched, dismiss)

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

    def _act(self, conn, job_id, matched, dismiss):
        """Record matched rules on an untouched job and dismiss it for a dismiss rule."""
        if not matched:
            return
        untouched = conn.execute(
            "SELECT 1 FROM jobs j WHERE j.id=? AND " + UNTOUCHED_SQL, (job_id,)
        ).fetchone()
        if not untouched:
            return
        current = conn.execute("SELECT rules FROM job_signals WHERE job_id=?", (job_id,)).fetchone()
        known = json.loads(current[0]) if current else []
        merged = known + [rule for rule in matched if rule not in known]
        if current:
            conn.execute("UPDATE job_signals SET rules=? WHERE job_id=?", (encode(merged), job_id))
        if dismiss:
            self.workspace.dismiss_by_rule(conn, job_id, dismiss)

    def after_unlisted(self, job_ids):
        """Apply no_longer_listed rules to the untouched jobs a run found delisted."""
        if not job_ids:
            return
        with self.db.transaction() as conn:
            rules = [rule for rule in active_rules(conn) if rule["signal"] == "no_longer_listed"]
            if not rules:
                return
            for job_id in job_ids:
                matched, dismiss = matched_rules(
                    rules, {"no_longer_listed": True}, {"no_longer_listed"}
                )
                self._act(conn, job_id, matched, dismiss)

    # Backfill -----------------------------------------------------------------

    def backfill(self, stopping=None, duplicates=True):
        """Compute the signals jobs do not have yet, in short batches. Never applies rules.

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

    # Preview ------------------------------------------------------------------

    def preview(self, rule, sample=5):
        """How many Inbox jobs a rule matches now, without acting on any of them."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT j.id,"
                + SIGNALS_SQL.format(alias="j")
                + ","
                + UNLISTED_SQL.format(alias="j")
                + " FROM jobs j WHERE j.triage='inbox' AND NOT EXISTS("
                "SELECT 1 FROM applications a WHERE a.job_id=j.id) ORDER BY j.created_at DESC,j.id"
            ).fetchall()
            matched, pending = [], 0
            for job_id, raw, unlisted_at in rows:
                signals = signal_record(raw, unlisted_at)
                if not signals["computed"] and rule["signal"] != "no_longer_listed":
                    pending += 1
                    continue
                if (
                    rule["signal"] == "likely_duplicate"
                    and signals["computed"]
                    and not signals["duplicate_checked"]
                ):
                    pending += 1
                    continue
                if rule_matches(rule, signals):
                    matched.append(job_id)
            examples = self.workspace._job_summaries(conn, matched[:sample]) if matched else []
        return {
            "rule": rule,
            "matches": len(matched),
            "inbox": len(rows),
            "pending": pending,
            "examples": [
                {key: item[key] for key in ("id", "title", "company", "location", "created_at")}
                for item in examples
            ],
        }
