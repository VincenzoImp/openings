"""Job identity: URL lookup, duplicate candidates, distinct marks and explicit merges."""

import json
import logging
import threading
import time

from .. import events
from ..actors import current_actor
from ..common import check_version, now
from ..db import encode
from ..duplicate_signals import job_features, posting_similarity
from ..duplicates import DEFAULT_MIN_CONFIDENCE, HIGH_CONFIDENCE, DuplicateIndex, confidence_tier
from ..errors import DomainError, missing
from ..identities import job_identities, normalize_url
from ..models import DuplicateQuery, JobResolve

LOG = logging.getLogger(__name__)


class JobIdentity:
    """Resolving, comparing and merging jobs; nothing here merges on its own."""

    def mark_distinct(self, job_id, other_id):
        """Record that a job flagged as a likely duplicate is a different vacancy.

        Clears the flag and remembers the pair, so the flag does not return when
        signals are computed again. Nothing else changes; merging is ``merge_jobs``.
        """
        if job_id == other_id:
            raise DomainError(422, "distinct", "Choose a different job.")
        with self.db.transaction() as c:
            for record in (job_id, other_id):
                if not c.execute("SELECT 1 FROM jobs WHERE id=?", (record,)).fetchone():
                    missing("Job")
            changed = False
            # Either job may carry the flag against the other.
            for first, second in ((job_id, other_id), (other_id, job_id)):
                row = c.execute(
                    "SELECT duplicate_of,distinct_from FROM job_signals WHERE job_id=?", (first,)
                ).fetchone()
                if row is None:
                    continue
                known = json.loads(row["distinct_from"])
                if second in known and row["duplicate_of"] != second:
                    continue
                c.execute(
                    "UPDATE job_signals SET distinct_from=?,duplicate_of=CASE WHEN duplicate_of=? "
                    "THEN NULL ELSE duplicate_of END,duplicate_confidence=CASE WHEN duplicate_of=? "
                    "THEN NULL ELSE duplicate_confidence END WHERE job_id=?",
                    (encode(sorted({*known, second})), second, second, first),
                )
                changed = True
            if changed:
                events.record(c, "duplicate_cleared", payload={"other_id": other_id}, job_id=job_id)
        return self.job_summary(job_id)

    def resolve_jobs(self, value):
        """Find archived jobs for a URL or source key without ingesting anything."""
        value = value if isinstance(value, JobResolve) else JobResolve.model_validate(value)
        url = normalize_url(value.url)
        aliases = job_identities(url, value.source_key)
        matched = {}
        with self.db.connect() as connection:
            placeholders = ",".join("?" for _ in aliases)
            for row in connection.execute(
                f"SELECT job_id,identity FROM job_identities WHERE identity IN ({placeholders})",
                aliases,
            ):
                matched.setdefault(row["job_id"], set()).add(row["identity"])
            if url:
                for sql, label in (
                    ("SELECT id AS job_id FROM jobs WHERE url=?", "job_url"),
                    ("SELECT job_id FROM postings WHERE url=?", "posting_url"),
                ):
                    for row in connection.execute(sql, (url,)):
                        matched.setdefault(row["job_id"], set()).add(label)
            items = self._job_summaries(connection, list(matched))
        for item in items:
            item["matched_by"] = sorted(matched[item["id"]])
        return {
            "url": url,
            "identities": aliases,
            "items": items,
            "total": len(items),
            "identity_conflict": len(items) > 1,
        }

    def _job_summaries(self, connection, job_ids):
        """Compact job rows plus every attempt's id/status/outcome/version."""
        if not job_ids:
            return []
        placeholders = ",".join("?" for _ in job_ids)
        rows = connection.execute(
            "SELECT "
            + self._job_columns()
            + f" FROM jobs j WHERE j.id IN ({placeholders}) ORDER BY j.created_at,j.id",
            job_ids,
        ).fetchall()
        attempts = {}
        for row in connection.execute(
            "SELECT id,job_id,status,outcome,version,applied_at FROM applications "
            f"WHERE job_id IN ({placeholders}) ORDER BY created_at DESC,id DESC",
            job_ids,
        ):
            attempt = dict(row)
            attempts.setdefault(attempt.pop("job_id"), []).append(attempt)
        items = []
        for row in rows:
            job = self._compact_job(row)
            item = {
                key: job.get(key)
                for key in (
                    "id",
                    "title",
                    "company",
                    "location",
                    "url",
                    "source",
                    "triage",
                    "complete",
                    "version",
                    "created_at",
                    "application",
                    "application_count",
                    "signals",
                    "dismissal",
                )
            }
            item["applications"] = attempts.get(job["id"], [])
            items.append(item)
        return items

    def _duplicate_index(self, connection):
        """Duplicate features of every job; only new or changed jobs are read again."""
        stamps = {
            row[0]: tuple(row)[1:]
            for row in connection.execute(
                "SELECT j.id,j.version,j.updated_at,j.created_at,"
                "(SELECT count(*) FROM job_identities i WHERE i.job_id=j.id) "
                "FROM jobs j ORDER BY j.rowid"
            )
        }
        with self._duplicates_lock:
            known, features, index = self._duplicates
            stale = [job_id for job_id, stamp in stamps.items() if known.get(job_id) != stamp]
            if index is not None and not stale and len(known) == len(stamps):
                return index
            features = {
                job_id: features[job_id] for job_id in stamps if known.get(job_id) == stamps[job_id]
            }
            features.update(self._read_features(connection, stale))
            index = DuplicateIndex(features[job_id] for job_id in stamps if job_id in features)
            self._duplicates = (stamps, features, index)
            return index

    @staticmethod
    def _read_features(connection, job_ids):
        """Duplicate features of these jobs, read from the database."""
        features = {}
        for start in range(0, len(job_ids), 400):
            chunk = job_ids[start : start + 400]
            placeholders = ",".join("?" for _ in chunk)
            identities, urls = {}, {}
            for job_id, identity in connection.execute(
                f"SELECT job_id,identity FROM job_identities WHERE job_id IN ({placeholders})",
                chunk,
            ):
                identities.setdefault(job_id, []).append(identity)
            # The employer's own apply link, when a job board reported one.
            for job_id, url in connection.execute(
                "SELECT job_id,json_extract(payload,'$.raw.job_url_direct') FROM postings "
                f"WHERE job_id IN ({placeholders}) AND instr(payload,'job_url_direct')",
                chunk,
            ):
                if isinstance(url, str):
                    urls.setdefault(job_id, []).append(url)
            for row in connection.execute(
                "SELECT id,title,company,location,url,substr(posting,1,50000) AS posting,"
                f"metadata,created_at FROM jobs WHERE id IN ({placeholders})",
                chunk,
            ):
                job = dict(row)
                job["metadata"] = json.loads(job["metadata"])
                job["identities"] = identities.get(job["id"], ())
                job["urls"] = urls.get(job["id"], ())
                features[job["id"]] = job_features(job)
        return features

    def earlier_duplicate(self, job_id):
        """The job collected earlier that this one most likely repeats: (id, confidence)."""
        return self.earlier_duplicates([job_id]).get(job_id)

    def earlier_duplicates(self, job_ids):
        """For each job, its most likely earlier copy at DEFAULT_MIN_CONFIDENCE or more.

        Uses the cached duplicate index (built once after a start) and adds the jobs
        it does not hold yet, so jobs collected in one run are compared with each
        other. Pairs the owner marked as different vacancies are skipped. Read-only.
        """
        with self._duplicates_lock:
            index = self._duplicates[2]
        if index is None:
            with self.db.connect() as connection:
                index = self._duplicate_index(connection)
        with self.db.connect() as connection:
            unknown = [job_id for job_id in job_ids if job_id not in index.jobs]
            fresh = self._read_features(connection, unknown)
            stamps = {}
            if unknown:
                placeholders = ",".join("?" for _ in unknown)
                stamps = {
                    row[0]: tuple(row)[1:]
                    for row in connection.execute(
                        "SELECT j.id,j.version,j.updated_at,j.created_at,"
                        "(SELECT count(*) FROM job_identities i WHERE i.job_id=j.id) "
                        f"FROM jobs j WHERE j.id IN ({placeholders})",
                        unknown,
                    )
                }
            placeholders = ",".join("?" for _ in job_ids)
            distinct = {
                row[0]: set(json.loads(row[1]))
                for row in connection.execute(
                    f"SELECT job_id,distinct_from FROM job_signals WHERE job_id IN ({placeholders})",
                    job_ids,
                )
            }
        found = {}
        for job_id in job_ids:
            features = fresh.get(job_id) or index.jobs.get(job_id)
            if features is None:
                continue
            order = (features.created_at, job_id)
            for other, evidence in index.matches(features, DEFAULT_MIN_CONFIDENCE, limit=25):
                candidate = index.jobs.get(other)
                if (
                    candidate is None
                    or other in distinct.get(job_id, ())
                    or (candidate.created_at, other) >= order
                ):
                    continue
                found[job_id] = (other, evidence.score)
                break
        if fresh:
            with self._duplicates_lock:
                known, cached, current = self._duplicates
                if current is index:
                    for job_id, features in fresh.items():
                        if job_id in stamps and job_id not in index.jobs:
                            index.add(features)
                            cached[job_id] = features
                            known[job_id] = stamps[job_id]
        return found

    def reset_duplicates(self):
        """Forget the cached duplicate index, after the jobs were replaced (a restore)."""
        with self._duplicates_lock:
            self._duplicates = ({}, {}, None)

    def warm_duplicates(self, delay=0.0):
        """Build the duplicate features in the background, so the first request does not wait.

        On a small host the first build takes many seconds for a few thousand
        jobs. A request that arrives meanwhile waits for this build instead of
        starting its own.
        """

        def build():
            if delay:
                time.sleep(delay)
            try:
                # Text signals of jobs collected before schema 12 first: they are cheap
                # and lists show them. Then the index, then the duplicate signals.
                self.signals.backfill(duplicates=False)
                with self.db.connect() as connection:
                    self._duplicate_index(connection)
                self.signals.backfill()
            except Exception:
                LOG.exception("Duplicate and signal warm-up failed")

        thread = threading.Thread(target=build, name="duplicate-warmup", daemon=True)
        thread.start()
        return thread

    def likely_duplicates(self, job, min_confidence=DEFAULT_MIN_CONFIDENCE, limit=5):
        """Archived jobs most likely to be the same vacancy as one job, best first.

        `job` is an archived job ID, or the fields of a posting that is not archived
        yet (title, company, location, url, posting, metadata, source_key, raw).
        Read-only: a signal for review, never a merge.
        """
        with self.db.connect() as connection:
            index = self._duplicate_index(connection)
        if isinstance(job, str):
            features = index.jobs.get(job) or missing("Job")
        else:
            url = normalize_url(job.get("url") or "")
            features = job_features(
                {
                    **job,
                    "id": None,
                    "url": url,
                    "identities": job_identities(url, job.get("source_key")),
                    "urls": [(job.get("raw") or {}).get("job_url_direct")],
                    "created_at": job.get("created_at") or now(),
                }
            )
        return [
            {
                "job_id": job_id,
                "confidence": evidence.score,
                "tier": confidence_tier(evidence.score),
                "reasons": {
                    "matched": list(evidence.matched),
                    "conflicts": list(evidence.conflicts),
                },
            }
            for job_id, evidence in index.matches(features, min_confidence, limit)
        ]

    def duplicate_jobs(self, value=None):
        """Candidate duplicate groups for review. Never merges or changes records."""
        value = (
            value
            if isinstance(value, DuplicateQuery)
            else DuplicateQuery.model_validate(value or {})
        )
        with self.db.connect() as connection:
            if (
                value.job_id
                and not connection.execute(
                    "SELECT 1 FROM jobs WHERE id=?", (value.job_id,)
                ).fetchone()
            ):
                missing("Job")
            index = self._duplicate_index(connection)
            groups = index.groups(value.min_confidence, value.match_location)
            if value.job_id:
                groups = [group for group in groups if value.job_id in group["ids"]]
            if value.triage:
                where, args = self._job_filters(triage=value.triage)
                in_queue = {
                    row[0] for row in connection.execute("SELECT j.id FROM jobs j" + where, args)
                }
                groups = [group for group in groups if in_queue.intersection(group["ids"])]
            with_attempts = {
                row[0] for row in connection.execute("SELECT DISTINCT job_id FROM applications")
            }
            # Most confident first, then application history, larger and newest groups.
            groups.sort(
                key=lambda group: (
                    max(index.jobs[i].created_at for i in group["ids"]),
                    min(group["ids"]),
                ),
                reverse=True,
            )
            groups.sort(
                key=lambda group: (
                    -group["confidence"],
                    not with_attempts.intersection(group["ids"]),
                    -len(group["ids"]),
                )
            )
            page = groups[value.offset : value.offset + value.limit]
            ids = [job_id for group in page for job_id in group["ids"]]
            summaries = {item["id"]: item for item in self._job_summaries(connection, ids)}
            postings = {}
            if ids:
                placeholders = ",".join("?" for _ in ids)
                postings = {
                    row[0]: row[1]
                    for row in connection.execute(
                        f"SELECT id,substr(posting,1,50000) FROM jobs WHERE id IN ({placeholders})",
                        ids,
                    )
                }
        result = []
        for group in page:
            items = [summaries[job_id] for job_id in group["ids"]]
            # Prefer the record a merge would most likely keep: an open attempt,
            # then any attempt, then a shortlisted job, then the oldest record.
            reference = min(
                items,
                key=lambda item: (
                    not any(a["status"] != "closed" for a in item["applications"]),
                    not item["applications"],
                    item["triage"] != "shortlisted",
                    item["created_at"],
                    item["id"],
                ),
            )
            for item in items:
                item["posting_hash"] = index.jobs[item["id"]].fingerprint
                item["similarity"] = posting_similarity(
                    postings[reference["id"]], postings[item["id"]]
                )
                evidence = index.evidence(reference["id"], item["id"])
                item["confidence"] = None if item is reference else evidence.score
                item["reasons"] = (
                    None
                    if item is reference
                    else {
                        "matched": list(evidence.matched),
                        "conflicts": list(evidence.conflicts),
                    }
                )
            hashes = {item["posting_hash"] for item in items}
            open_attempts = [
                attempt["id"]
                for item in items
                for attempt in item["applications"]
                if attempt["status"] != "closed"
            ]
            result.append(
                {
                    "job_ids": [item["id"] for item in items],
                    "signals": group["matched"],
                    "confidence": group["confidence"],
                    "tier": confidence_tier(group["confidence"]),
                    "reasons": {"matched": group["matched"], "conflicts": group["conflicts"]},
                    "size": len(items),
                    "identical_postings": len(hashes) == 1 and None not in hashes,
                    "reference_id": reference["id"],
                    "open_application_ids": open_attempts,
                    "merge_blocked": len(open_attempts) > 1,
                    "items": [reference] + [item for item in items if item is not reference],
                }
            )
        return {
            "items": result,
            "total": len(groups),
            "limit": value.limit,
            "offset": value.offset,
            "min_confidence": value.min_confidence,
            "tiers": {"high": HIGH_CONFIDENCE, "medium": DEFAULT_MIN_CONFIDENCE},
        }

    def merge_jobs(self, source_id, target_id, expected_version, target_version):
        if source_id == target_id:
            raise DomainError(422, "merge", "Choose a different target job.")
        with self.db.transaction() as c:
            for record_id, version in ((source_id, expected_version), (target_id, target_version)):
                check_version(
                    c.execute("SELECT * FROM jobs WHERE id=?", (record_id,)).fetchone(), version
                )
            active = c.execute(
                "SELECT * FROM applications WHERE job_id IN (?,?) AND status<>'closed' "
                "ORDER BY job_id=?",
                (source_id, target_id, target_id),
            ).fetchall()
            # Both jobs were shortlisted: an application still empty gives way.
            empty = [row for row in active if not self.application_work(c, row)]
            if len(active) > 1 and empty:
                self.remove_application(c, empty[0])
                active = [row for row in active if row["id"] != empty[0]["id"]]
            if len(active) > 1:
                raise DomainError(
                    409,
                    "application_in_progress",
                    "Close one active application before merging these jobs.",
                    {"application_ids": [row["id"] for row in active]},
                )
            next_content = c.execute(
                "SELECT max(content_version)+1 FROM jobs WHERE id IN (?,?)",
                (source_id, target_id),
            ).fetchone()[0]
            c.execute(
                "UPDATE tasks SET state='cancelled',updated_at=? WHERE job_id IN (?,?) AND state IN ('queued','running')",
                (now(), source_id, target_id),
            )
            c.execute(
                "UPDATE transfer_grants SET payload=json_set(payload,'$.job_id',?,'$.owner_id',CASE WHEN json_extract(payload,'$.owner_type')='job' THEN ? ELSE json_extract(payload,'$.owner_id') END) WHERE json_extract(payload,'$.job_id')=?",
                (target_id, target_id, source_id),
            )
            c.execute(
                "INSERT OR IGNORE INTO job_identities(identity,job_id) SELECT identity,? FROM job_identities WHERE job_id=?",
                (target_id, source_id),
            )
            c.execute("DELETE FROM job_identities WHERE job_id=?", (source_id,))
            c.execute("UPDATE posting_details SET job_id=? WHERE job_id=?", (target_id, source_id))
            # One pinned note per job: the kept job's pin stays, the merged one's is unpinned.
            kept = self._pinned_row(c, target_id, None)
            if kept is not None:
                self._unpin_scope(c, source_id, None, kept["id"])
            for table in (
                "postings",
                "applications",
                "events",
                "notes",
                "tasks",
            ):
                c.execute(f"UPDATE {table} SET job_id=? WHERE job_id=?", (target_id, source_id))
            c.execute("UPDATE files SET job_id=? WHERE job_id=?", (target_id, source_id))
            # A job flagged as a copy of the merged record is now a copy of the one kept.
            c.execute(
                "UPDATE job_signals SET duplicate_of=CASE WHEN job_id=? THEN NULL ELSE ? END,"
                "duplicate_confidence=CASE WHEN job_id=? THEN NULL ELSE duplicate_confidence END "
                "WHERE duplicate_of=?",
                (target_id, target_id, target_id, source_id),
            )
            c.execute("DELETE FROM jobs WHERE id=?", (source_id,))
            c.execute(
                "UPDATE jobs SET version=version+1,content_version=?,updated_at=? WHERE id=?",
                (next_content, now(), target_id),
            )
            # A job with an open application is shortlisted.
            target = c.execute("SELECT * FROM jobs WHERE id=?", (target_id,)).fetchone()
            if active and target["triage"] != "shortlisted":
                self._triage(c, target, "shortlisted", current_actor())
            c.execute(
                "UPDATE job_signals SET content_version=?,duplicate_of=CASE WHEN duplicate_of=? "
                "THEN NULL ELSE duplicate_of END WHERE job_id=?",
                (next_content, source_id, target_id),
            )
            c.execute(
                "UPDATE events SET subject_id=? WHERE subject_type='job' AND subject_id=?",
                (target_id, source_id),
            )
            events.record(c, "jobs_merged", payload={"previous_id": source_id}, job_id=target_id)
        return self.get_job(target_id)
