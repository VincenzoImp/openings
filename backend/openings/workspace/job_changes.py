"""Job changes: ingest, corrections, triage and permanent deletion."""

import hashlib
import json
from urllib.parse import urlsplit

from .. import events
from ..actors import current_actor
from ..common import check_version, new_id, now
from ..db import collect_unused, encode
from ..errors import DomainError
from ..idempotency import fingerprint, remember, replay
from ..identities import job_identities, normalize_url
from ..job_signals import store_text_signals
from ..models import JobInput, JobPatch
from ..posting import posting_complete
from ..retention import REFRESH_EVENT, REFRESH_FIELDS, observation_payload


class JobChanges:
    """Adding, correcting, triaging and forgetting jobs."""

    def replayed_job(self, key, digest):
        """The job an earlier request with this idempotency key gave, or None."""
        if not key:
            return None
        with self.db.transaction() as c:
            job_id = replay(c, "jobs", key, digest)
        if job_id is None:
            return None
        return {**self.get_job(job_id), "created": False}

    def ingest_job(self, value, defer_signals=False, digest=None):
        """Store a posting as a new job or as a refresh of the job it identifies.

        A new job gets its text signals in the same transaction, then its duplicate
        (``SignalService.after_ingest``). A caller holding the
        database lock passes ``defer_signals`` and runs that step after releasing it.
        A request with an idempotency key gives the same job when retried; ``digest``
        is the fingerprint of the request as sent, before a URL was read.
        """
        value = value if isinstance(value, JobInput) else JobInput.model_validate(value)
        digest = digest or fingerprint(value)
        replayed = self.replayed_job(value.idempotency_key, digest)
        if replayed:
            return replayed
        data = value.model_dump(exclude={"idempotency_key"})
        if not value.url and not value.posting.strip():
            raise DomainError(422, "job_content", "Provide a job URL or posting text.")
        url = normalize_url(value.url)
        aliases = job_identities(url, value.source_key)
        identity = aliases[0] if aliases else "manual:" + new_id()
        title = value.title.strip() or "Untitled opportunity"
        company = value.company.strip() or (urlsplit(url).hostname or "Unknown company")
        data.update(title=title, company=company, url=url)
        with self.db.transaction() as c:
            placeholders = ",".join("?" for _ in aliases) or "NULL"
            matches = c.execute(
                f"SELECT DISTINCT jobs.* FROM jobs JOIN job_identities i ON i.job_id=jobs.id WHERE i.identity IN ({placeholders})",
                aliases,
            ).fetchall()
            if len(matches) > 1:
                raise DomainError(
                    409,
                    "identity_conflict",
                    "These exact identities belong to different jobs. Merge the verified duplicates before importing this posting.",
                    {"job_ids": sorted(row["id"] for row in matches)},
                )
            prior = matches[0] if matches else None
            job_id = prior["id"] if prior else new_id()
            stamp = now()
            if prior is None:
                c.execute(
                    "INSERT INTO jobs(id,title,company,location,url,posting,metadata,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        job_id,
                        title,
                        company,
                        value.location,
                        url,
                        value.posting,
                        encode(value.metadata),
                        stamp,
                        stamp,
                    ),
                )
                events.record(
                    c, "job_added", payload={"title": title, "company": company}, job_id=job_id
                )
                store_text_signals(c, job_id, title, value.posting, 1, stamp)
            else:
                overrides = json.loads(prior["overrides"])
                updates = {}
                preserve_body = (
                    not overrides.get("posting")
                    and posting_complete(prior["posting"], prior["metadata"], prior["overrides"])
                    and not posting_complete(value.posting, value.metadata, {})
                )
                for key in ("title", "company", "location", "url", "posting", "metadata"):
                    incoming = data[key]
                    if preserve_body and key == "posting":
                        incoming = prior["posting"]
                    elif preserve_body and key == "metadata":
                        # A failed detail refresh or a search preview cannot replace
                        # an archived full body. Keep the incoming raw observation.
                        incoming = dict(incoming)
                        previous_metadata = json.loads(prior["metadata"])
                        for field in ("description_complete", "description_status"):
                            incoming.pop(field, None)
                            if field in previous_metadata:
                                incoming[field] = previous_metadata[field]
                    if (
                        key in overrides
                        or not incoming
                        or (key == "title" and not value.title)
                        or (key == "company" and not value.company)
                    ):
                        continue
                    old = json.loads(prior[key]) if key == "metadata" else prior[key]
                    if old != incoming:
                        updates[key] = encode(incoming) if key == "metadata" else incoming
                if updates:
                    c.execute(
                        "UPDATE jobs SET "
                        + ",".join(k + "=?" for k in updates)
                        + ",version=version+1,content_version=content_version+1,updated_at=? WHERE id=?",
                        (*updates.values(), stamp, job_id),
                    )
                    # A re-sighting is recorded on the observation (last_seen_at) only.
                    visible = [key for key in updates if key in REFRESH_FIELDS]
                    if visible:
                        events.record(c, REFRESH_EVENT, payload={"fields": visible}, job_id=job_id)
                    if "title" in updates or "posting" in updates:
                        self._refresh_text_signals(c, job_id)
            c.executemany(
                "INSERT OR IGNORE INTO job_identities(identity,job_id) VALUES(?,?)",
                [(key, job_id) for key in aliases],
            )
            # Identity aliases contain no posting bodies. Update the observation
            # already matching this exact posting rather than adding another.
            observation = c.execute(
                "SELECT id FROM postings WHERE job_id=? AND (identity=? OR (?<>'' AND url=?) OR (? IS NOT NULL AND json_extract(payload,'$.source_key')=?)) ORDER BY first_seen_at,id LIMIT 1",
                (job_id, identity, url, url, value.source_key, value.source_key),
            ).fetchone()
            content_hash = hashlib.sha256(encode(data).encode()).hexdigest()
            kept = encode(observation_payload(data))
            if observation:
                # Seen again: a posting the source had stopped listing is listed again.
                c.execute(
                    "UPDATE postings SET source_id=coalesce(source_id,?),url=?,payload=?,content_hash=?,last_seen_at=?,unlisted_at=NULL WHERE id=?",
                    (value.source_id, url, kept, content_hash, stamp, observation["id"]),
                )
            else:
                c.execute(
                    "INSERT INTO postings(id,job_id,source_id,identity,url,payload,content_hash,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        new_id(),
                        job_id,
                        value.source_id,
                        identity,
                        url,
                        kept,
                        content_hash,
                        stamp,
                        stamp,
                    ),
                )
            remember(c, "jobs", value.idempotency_key, digest, job_id)
        if prior is None and not defer_signals:
            self.signals.after_ingest(job_id)
        result = self.get_job(job_id)
        result["created"] = prior is None
        return result

    @staticmethod
    def _refresh_text_signals(conn, job_id):
        """Text signals follow the title and posting; the duplicate stays."""
        row = conn.execute(
            "SELECT title,posting,content_version FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        store_text_signals(conn, job_id, row[0], row[1], row[2])

    def update_job(self, job_id, value):
        value = value if isinstance(value, JobPatch) else JobPatch.model_validate(value)
        changes = value.model_dump(exclude_unset=True, exclude={"expected_version"})
        changes = {k: v for k, v in changes.items() if v is not None}
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            check_version(row, value.expected_version)
            overrides = json.loads(row["overrides"])
            actual = {}
            for key, val in changes.items():
                val = normalize_url(val) if key == "url" else val
                previous = json.loads(row[key]) if key == "metadata" else row[key]
                if previous != val:
                    actual[key] = encode(val) if key == "metadata" else val
                    overrides[key] = True
            if "url" in actual:
                aliases = job_identities(actual["url"])
                if (
                    aliases
                    and c.execute(
                        "SELECT 1 FROM job_identities WHERE job_id<>? AND identity IN ("
                        + ",".join("?" for _ in aliases)
                        + ") LIMIT 1",
                        (job_id, *aliases),
                    ).fetchone()
                ):
                    raise DomainError(
                        409,
                        "identity_conflict",
                        "This URL belongs to another archived job. Merge the verified duplicates before changing the URL.",
                    )
            if actual:
                material = any(
                    k in actual for k in ("title", "company", "location", "posting", "metadata")
                )
                c.execute(
                    "UPDATE jobs SET "
                    + ",".join(k + "=?" for k in actual)
                    + ",overrides=?,version=version+1,content_version=content_version+?,updated_at=? WHERE id=?",
                    (*actual.values(), encode(overrides), int(material), now(), job_id),
                )
                if "url" in actual:
                    c.executemany(
                        "INSERT OR IGNORE INTO job_identities(identity,job_id) VALUES(?,?)",
                        [(key, job_id) for key in job_identities(actual["url"])],
                    )
                if "title" in actual or "posting" in actual:
                    self._refresh_text_signals(c, job_id)
                events.record(c, "job_edited", payload={"fields": list(actual)}, job_id=job_id)
        return self.job_summary(job_id)

    def set_triage(self, job_id, triage, expected_version, reason=None):
        """Set new/shortlisted/dismissed. A dismissal records who made it and, optionally, why.

        Shortlisting starts the job's application and undoing it removes that
        application while it is empty, in the same transaction (``shortlist.py``).
        """
        if triage not in {"new", "shortlisted", "dismissed"}:
            raise DomainError(422, "triage", "Unknown job disposition.")
        if reason and triage != "dismissed":
            raise DomainError(422, "triage_reason", "A reason goes with a dismissal only.")
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            check_version(row, expected_version)
            if row["triage"] != triage:
                if row["triage"] == "shortlisted":
                    self.leave_shortlist(c, job_id)
                self._triage(c, row, triage, current_actor(), reason=reason or "")
                if triage == "shortlisted":
                    self.start_from_shortlist(c, job_id)
            elif triage == "dismissed" and reason is not None and reason != row["dismissed_reason"]:
                c.execute(
                    "UPDATE jobs SET dismissed_reason=?,version=version+1,updated_at=? WHERE id=?",
                    (reason, now(), job_id),
                )
                events.record(
                    c, "job_edited", payload={"fields": ["dismissed_reason"]}, job_id=job_id
                )
        return self.job_summary(job_id)

    def _triage(self, conn, row, triage, actor, reason=""):
        """Move a job to another triage state, keeping the record of a dismissal."""
        stamp = now()
        if triage == "dismissed":
            conn.execute(
                "UPDATE jobs SET triage=?,dismissed_at=?,dismissed_by=?,"
                "dismissed_reason=?,version=version+1,updated_at=? WHERE id=?",
                (
                    triage,
                    stamp,
                    actor.label,
                    reason,
                    stamp,
                    row["id"],
                ),
            )
            conn.execute(
                "UPDATE tasks SET state='cancelled',updated_at=? WHERE job_id=? AND state IN ('queued','running')",
                (stamp, row["id"]),
            )
        else:
            conn.execute(
                "UPDATE jobs SET triage=?,dismissed_at=NULL,dismissed_by=NULL,dismissed_reason='',"
                "version=version+1,updated_at=? WHERE id=?",
                (triage, stamp, row["id"]),
            )
        payload = {"from": row["triage"], "to": triage}
        events.record(conn, "triage_changed", payload=payload, job_id=row["id"], actor=actor)

    def forget_job(self, job_id, expected_version, collect=True):
        """Delete a job; bulk callers pass collect=False and collect blobs once."""
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            check_version(row, expected_version)
            c.execute(
                "DELETE FROM transfer_grants WHERE json_extract(payload,'$.job_id')=?", (job_id,)
            )
            c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
            if collect:
                collect_unused(c)
            # The job's own history is deleted with it; this record keeps only its id.
            events.record(c, "job_forgotten", subject=("job", job_id))
        return {"deleted": True, "id": job_id}
