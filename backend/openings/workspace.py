"""Core archive operations, shared by the dashboard, REST and MCP."""

import hashlib
import json
import math
import re
from urllib.parse import urlsplit

from .actors import current_actor, describe_row
from .common import (
    check_version,
    new_id,
    now,
)
from .db import Database, decode_record, encode
from .duplicates import candidate_groups, posting_fingerprint, posting_similarity
from .errors import DomainError, conflict, missing
from .identities import job_identities, normalize_url
from .models import (
    ApplicationBulk,
    ApplicationInput,
    ApplicationPatch,
    ApplicationReady,
    DuplicateQuery,
    JobBulk,
    JobInput,
    JobPatch,
    JobResolve,
    NoteInput,
    NotePatch,
)
from .posting import posting_complete, posting_complete_sql
from .staleness import application_staleness

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


COLLECT_BLOBS = "DELETE FROM blobs WHERE sha256 NOT IN (SELECT sha256 FROM files)"


class Workspace:
    def __init__(self, path):
        self.db = Database(path)
        self.discovery = None

    def get_settings(self, key, default=None):
        row = self.db.one("SELECT * FROM settings WHERE key=?", (key,))
        return (
            {"data": json.loads(row["data"]), "version": row["version"]}
            if row
            else {"data": default if default is not None else {}, "version": 0}
        )

    def set_settings(self, key, data, expected_version=None):
        with self.db.transaction() as c:
            row = c.execute("SELECT version FROM settings WHERE key=?", (key,)).fetchone()
            version = row["version"] if row else 0
            if expected_version is not None and expected_version != version:
                conflict(details={"current_version": version})
            if row and self.get_settings(key)["data"] == data:
                return {"data": data, "version": version}
            c.execute(
                "INSERT INTO settings(key,data,version,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=excluded.version,updated_at=excluded.updated_at",
                (key, encode(data), version + 1, now()),
            )
        return {"data": data, "version": version + 1}

    def event(
        self,
        kind,
        job_id=None,
        application_id=None,
        payload=None,
        conn=None,
        *,
        subject=None,
        actor=None,
    ):
        """Record one change with its actor and, for a token with an open run, that run.

        ``subject`` is ``(type, id)`` of the changed record; it defaults to the
        application or job. Payloads hold identifiers, field names and versions,
        never record content.
        """
        if conn is None:
            with self.db.transaction() as connection:
                return self.event(
                    kind, job_id, application_id, payload, connection, subject=subject, actor=actor
                )
        actor = actor or current_actor()
        stamp, run_id = now(), self.open_run_id(conn, actor)
        if run_id:
            conn.execute("UPDATE runs SET last_activity_at=? WHERE id=?", (stamp, run_id))
        if subject is None:
            subject = (
                ("application", application_id)
                if application_id
                else ("job", job_id)
                if job_id
                else (None, None)
            )
        conn.execute(
            "INSERT INTO events(id,job_id,application_id,kind,payload,created_at,subject_type,subject_id,actor_kind,actor_id,actor_name,run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id(),
                job_id,
                application_id,
                kind,
                encode(payload or {}),
                stamp,
                *subject,
                *actor.columns(),
                run_id,
            ),
        )
        return None

    @staticmethod
    def open_run_id(conn, actor):
        """The open run of a token actor; the owner session and the system have none."""
        if actor.kind != "token":
            return None
        run = conn.execute(
            "SELECT id FROM runs WHERE token_id=? AND status='open'", (actor.id,)
        ).fetchone()
        return run["id"] if run else None

    @staticmethod
    def event_record(row):
        """An event as returned by history reads: decoded payload, subject and actor."""
        item = decode_record(row, ("payload",))
        kind = item.pop("subject_type", None)
        identifier = item.pop("subject_id", None)
        if kind is None:
            # Events from before schema 8 belong to their application or job.
            kind, identifier = (
                ("application", item.get("application_id"))
                if item.get("application_id")
                else ("job", item.get("job_id"))
                if item.get("job_id")
                else (None, None)
            )
        item["subject"] = {"type": kind, "id": identifier}
        item["actor"] = describe_row(item)
        for key in ("actor_kind", "actor_id", "actor_name"):
            item.pop(key, None)
        return item

    @staticmethod
    def _note(row):
        if row is None:
            missing("Note")
        row = dict(row)
        row["author"] = describe_row(row, "author")
        for key in ("author_kind", "author_id", "author_name"):
            row.pop(key)
        return row

    @staticmethod
    def _job_columns():
        columns = [
            f"j.{key} AS j_{key}"
            for key in (
                "id",
                "title",
                "company",
                "location",
                "url",
                "triage",
                "availability",
                "metadata",
                "content_version",
                "version",
                "created_at",
                "updated_at",
            )
        ]
        columns += [
            "substr(j.posting,1,240) AS j_posting_preview",
            posting_complete_sql() + " AS j_complete",
            "(SELECT json_object('id',id,'status',status,'outcome',outcome,'version',version) FROM applications WHERE job_id=j.id ORDER BY (status='closed'),created_at DESC,id DESC LIMIT 1) AS j_application",
            "(SELECT count(*) FROM applications WHERE job_id=j.id) AS j_application_count",
        ]
        return ",".join(columns)

    @staticmethod
    def _compact_job(row):
        result = {key[2:]: value for key, value in dict(row).items() if key.startswith("j_")}
        result["metadata"] = json.loads(result["metadata"])
        result["complete"] = bool(result["complete"])
        result["application"] = json.loads(result["application"]) if result["application"] else None
        result["source"] = (
            result["metadata"].get("source") or result["metadata"].get("ats") or "manual"
        )
        for field in ("is_remote", "job_type", "salary", "date_posted", "workplace_type"):
            if field in result["metadata"]:
                result[field] = result["metadata"][field]
        return result

    def _job(self, row):
        if not row:
            missing("Job")
        row = decode_record(row, ("metadata", "overrides"))
        with self.db.connect() as connection:
            row["postings"] = [
                dict(posting)
                for posting in connection.execute(
                    "SELECT id,source_id,identity,url,first_seen_at,last_seen_at FROM postings WHERE job_id=? ORDER BY first_seen_at",
                    (row["id"],),
                )
            ]
            application = connection.execute(
                "SELECT id,status,outcome,version,(SELECT count(*) FROM applications WHERE job_id=?) AS application_count FROM applications WHERE job_id=? ORDER BY (status='closed'),created_at DESC,id DESC LIMIT 1",
                (row["id"], row["id"]),
            ).fetchone()
            row["application"] = dict(application) if application else None
            row["application_count"] = (
                row["application"].pop("application_count") if application else 0
            )
        row["complete"] = posting_complete(row["posting"], row["metadata"], row["overrides"])
        return row

    def get_job(self, job_id):
        return self._job(self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,)))

    def job_summary(self, job_id):
        """Return the compact list-item shape of one job: no full posting or observations."""
        row = self.db.one("SELECT " + self._job_columns() + " FROM jobs j WHERE j.id=?", (job_id,))
        if not row:
            missing("Job")
        return self._compact_job(row)

    @staticmethod
    def _job_filters(
        q="",
        triage=None,
        company=None,
        location=None,
        source=None,
        remote=None,
        job_type=None,
        created_since=None,
        created_until=None,
        complete=None,
        queue=None,
    ):
        conditions, args = [], []
        if triage == "active":
            conditions.append("j.triage!='dismissed'")
        elif triage:
            if triage not in ("inbox", "saved", "dismissed"):
                raise DomainError(422, "triage", "Choose inbox, saved or dismissed.")
            conditions.append("j.triage=?")
            args.append(triage)
        if queue is not None:
            if queue not in {"inbox", "shortlist", "applications", "dismissed"}:
                raise DomainError(
                    422, "queue", "Choose inbox, shortlist, applications or dismissed."
                )
            if queue in {"inbox", "shortlist"}:
                conditions.append(
                    "j.triage=? AND NOT EXISTS (SELECT 1 FROM applications WHERE job_id=j.id)"
                )
                args.append("inbox" if queue == "inbox" else "saved")
            elif queue == "applications":
                conditions.append("EXISTS (SELECT 1 FROM applications WHERE job_id=j.id)")
            else:
                conditions.append("j.triage='dismissed'")
        if company:
            conditions.append("j.company=?")
            args.append(company)
        if location:
            conditions.append("j.location LIKE ?")
            args.append("%" + location + "%")
        source_sql = "coalesce(json_extract(j.metadata,'$.source'),json_extract(j.metadata,'$.ats'),'manual')"
        if source:
            conditions.append(source_sql + "=?")
            args.append(source)
        if remote is not None:
            conditions.append("json_extract(j.metadata,'$.is_remote')=?")
            args.append(int(remote))
        if complete is not None:
            conditions.append(posting_complete_sql() + "=?")
            args.append(int(complete))
        if job_type:
            conditions.append("json_extract(j.metadata,'$.job_type')=?")
            args.append(job_type)
        for value, operator in ((created_since, ">="), (created_until, "<=")):
            if value:
                conditions.append("j.created_at" + operator + "?")
                args.append(value)
        terms = re.findall(r"\w+", q)
        if terms:
            conditions.append("j.rowid IN (SELECT rowid FROM jobs_fts WHERE jobs_fts MATCH ?)")
            args.append(" AND ".join('"' + term + '"*' for term in terms[:15]))
        return (" WHERE " + " AND ".join(conditions)) if conditions else "", args

    def list_jobs(
        self,
        q="",
        triage=None,
        company=None,
        limit=50,
        offset=0,
        sort="newest",
        location=None,
        source=None,
        remote=None,
        job_type=None,
        created_since=None,
        created_until=None,
        complete=None,
        queue=None,
        include_facets=False,
    ):
        limit, offset = min(max(int(limit), 1), 200), max(int(offset), 0)
        with self.db.connect() as connection:
            where, args = self._job_filters(
                q,
                triage,
                company,
                location,
                source,
                remote,
                job_type,
                created_since,
                created_until,
                complete,
                queue,
            )
            base = " FROM jobs j"
            order = {
                "oldest": "j.created_at ASC",
                "company": "j.company,j.title",
                "title": "j.title",
            }.get(sort, "j.created_at DESC")
            rows = connection.execute(
                "SELECT "
                + self._job_columns()
                + base
                + where
                + " ORDER BY "
                + order
                + ",j.id LIMIT ? OFFSET ?",
                (*args, limit, offset),
            ).fetchall()
            total = connection.execute("SELECT count(*)" + base + where, args).fetchone()[0]
            result = {"items": [self._compact_job(row) for row in rows], "total": total}
            if not include_facets:
                return result
            facets = {}
            for name, expression in (
                ("companies", "j.company"),
                ("locations", "j.location"),
                (
                    "sources",
                    "coalesce(json_extract(j.metadata,'$.source'),json_extract(j.metadata,'$.ats'),'manual')",
                ),
                ("job_types", "json_extract(j.metadata,'$.job_type')"),
            ):
                facet_rows = connection.execute(
                    "SELECT DISTINCT "
                    + expression
                    + " value"
                    + base
                    + where
                    + " ORDER BY value LIMIT 200",
                    args,
                )
                facets[name] = [r[0] for r in facet_rows if r[0] not in (None, "")]
        return {**result, "facets": facets}

    def ingest_job(self, value):
        value = value if isinstance(value, JobInput) else JobInput.model_validate(value)
        data = value.model_dump()
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
                self.event(
                    "job_added", job_id, payload={"title": title, "company": company}, conn=c
                )
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
                    self.event("posting_updated", job_id, payload={"fields": list(updates)}, conn=c)
            c.executemany(
                "INSERT OR IGNORE INTO job_identities(identity,job_id) VALUES(?,?)",
                [(key, job_id) for key in aliases],
            )
            # Identity aliases contain no posting bodies. Update the observation
            # already matching this exact posting rather than cloning its raw data.
            observation = c.execute(
                "SELECT id FROM postings WHERE job_id=? AND (identity=? OR (?<>'' AND url=?) OR (? IS NOT NULL AND json_extract(payload,'$.source_key')=?)) ORDER BY first_seen_at,id LIMIT 1",
                (job_id, identity, url, url, value.source_key, value.source_key),
            ).fetchone()
            content_hash = hashlib.sha256(encode(data).encode()).hexdigest()
            if observation:
                c.execute(
                    "UPDATE postings SET source_id=coalesce(source_id,?),url=?,payload=?,content_hash=?,last_seen_at=? WHERE id=?",
                    (value.source_id, url, encode(data), content_hash, stamp, observation["id"]),
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
                        encode(data),
                        content_hash,
                        stamp,
                        stamp,
                    ),
                )
        result = self.get_job(job_id)
        result["created"] = prior is None
        return result

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
                self.event("job_edited", job_id, payload={"fields": list(actual)}, conn=c)
        return self.job_summary(job_id)

    def set_triage(self, job_id, triage, expected_version):
        if triage not in {"inbox", "saved", "dismissed"}:
            raise DomainError(422, "triage", "Unknown job disposition.")
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            check_version(row, expected_version)
            if row["triage"] != triage:
                c.execute(
                    "UPDATE jobs SET triage=?,version=version+1,updated_at=? WHERE id=?",
                    (triage, now(), job_id),
                )
                self.event(
                    "triage_changed", job_id, payload={"from": row["triage"], "to": triage}, conn=c
                )
            if triage == "dismissed":
                c.execute(
                    "UPDATE tasks SET state='cancelled',updated_at=? WHERE job_id=? AND state IN ('queued','running')",
                    (now(), job_id),
                )
        return self.job_summary(job_id)

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
                c.execute(COLLECT_BLOBS)
            # The job's own history is deleted with it; this record keeps only its id.
            self.event("job_forgotten", conn=c, subject=("job", job_id))
        return {"deleted": True, "id": job_id}

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
                    "availability",
                    "complete",
                    "version",
                    "created_at",
                    "application",
                    "application_count",
                )
            }
            item["applications"] = attempts.get(job["id"], [])
            items.append(item)
        return items

    def duplicate_jobs(self, value=None):
        """Candidate duplicate groups for review. Never merges or changes records."""
        value = (
            value
            if isinstance(value, DuplicateQuery)
            else DuplicateQuery.model_validate(value or {})
        )
        with self.db.connect() as connection:
            connection.create_function(
                "posting_fingerprint", 1, posting_fingerprint, deterministic=True
            )
            if (
                value.job_id
                and not connection.execute(
                    "SELECT 1 FROM jobs WHERE id=?", (value.job_id,)
                ).fetchone()
            ):
                missing("Job")
            rows = connection.execute(
                "SELECT id,title,company,location,created_at,"
                "posting_fingerprint(substr(posting,1,50000)) AS fingerprint FROM jobs"
            ).fetchall()
            fingerprints = {row["id"]: row["fingerprint"] for row in rows}
            created = {row["id"]: row["created_at"] for row in rows}
            groups = candidate_groups(rows, value.match_location)
            if value.job_id:
                groups = [group for group in groups if value.job_id in group["ids"]]
            if value.queue:
                where, args = self._job_filters(queue=value.queue)
                in_queue = {
                    row[0] for row in connection.execute("SELECT j.id FROM jobs j" + where, args)
                }
                groups = [group for group in groups if in_queue.intersection(group["ids"])]
            with_attempts = {
                row[0] for row in connection.execute("SELECT DISTINCT job_id FROM applications")
            }
            # Groups with application history first, then larger, then newest.
            groups.sort(
                key=lambda group: (max(created[i] for i in group["ids"]), min(group["ids"])),
                reverse=True,
            )
            groups.sort(
                key=lambda group: (
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
            # then any attempt, then saved interest, then the oldest record.
            reference = min(
                items,
                key=lambda item: (
                    not any(a["status"] != "closed" for a in item["applications"]),
                    not item["applications"],
                    item["triage"] != "saved",
                    item["created_at"],
                    item["id"],
                ),
            )
            for item in items:
                item["posting_hash"] = fingerprints[item["id"]]
                item["similarity"] = posting_similarity(
                    postings[reference["id"]], postings[item["id"]]
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
                    "signals": group["signals"],
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
                "SELECT id FROM applications WHERE job_id IN (?,?) AND status<>'closed'",
                (source_id, target_id),
            ).fetchall()
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
            for table in ("postings", "applications", "events", "notes", "tasks", "questions"):
                c.execute(f"UPDATE {table} SET job_id=? WHERE job_id=?", (target_id, source_id))
            c.execute("UPDATE files SET job_id=? WHERE job_id=?", (target_id, source_id))
            c.execute("DELETE FROM jobs WHERE id=?", (source_id,))
            c.execute(
                "UPDATE jobs SET version=version+1,content_version=?,updated_at=? WHERE id=?",
                (next_content, now(), target_id),
            )
            c.execute(
                "UPDATE events SET subject_id=? WHERE subject_type='job' AND subject_id=?",
                (target_id, source_id),
            )
            self.event("jobs_merged", target_id, payload={"previous_id": source_id}, conn=c)
        return self.get_job(target_id)

    def list_notes(self, job_id):
        self.get_job(job_id)
        rows = self.db.all("SELECT * FROM notes WHERE job_id=? ORDER BY created_at DESC", (job_id,))
        return {"items": [self._note(row) for row in rows], "total": len(rows)}

    def add_note(self, job_id, value):
        value = value if isinstance(value, NoteInput) else NoteInput.model_validate(value)
        self.get_job(job_id)
        if value.application_id and self.get_application(value.application_id)["job_id"] != job_id:
            raise DomainError(422, "note_owner", "Application belongs to a different job.")
        note_id, stamp = new_id(), now()
        with self.db.transaction() as c:
            c.execute(
                "INSERT INTO notes(id,job_id,application_id,body,created_at,updated_at,author_kind,author_id,author_name) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    note_id,
                    job_id,
                    value.application_id,
                    value.body,
                    stamp,
                    stamp,
                    *current_actor().columns(),
                ),
            )
            self.event(
                "note_added", job_id, value.application_id, conn=c, subject=("note", note_id)
            )
        return self.get_note(note_id)

    def delete_note(self, note_id):
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
            if row is None:
                missing("Note")
            c.execute("DELETE FROM notes WHERE id=?", (note_id,))
            self.event(
                "note_deleted",
                row["job_id"],
                row["application_id"],
                conn=c,
                subject=("note", note_id),
            )
        return {"deleted": True}

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
            row["stale_inputs"] = application_staleness(connection, [application_id])[
                application_id
            ]["inputs"]
        return row

    @staticmethod
    def _ready_by(row):
        """Replace the stored actor columns with who marked the application ready."""
        row["ready_by"] = describe_row(row, "ready_by") if row["ready_at"] else None
        for key in ("ready_by_kind", "ready_by_id", "ready_by_name"):
            row.pop(key)
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
    ):
        conditions, args = [], []
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
        for value, operator in ((ready_since, ">="), (ready_until, "<=")):
            if value:
                conditions.append("app.ready_at" + operator + "?")
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
            if outcome not in ("accepted", "rejected", "not_pursued"):
                raise DomainError(422, "application_outcome", "Choose a valid application outcome.")
            conditions.append("app.outcome=?")
            args.append(outcome)
        if company:
            conditions.append("j.company=?")
            args.append(company)
        if q.strip():
            conditions.append("(j.title LIKE ? OR j.company LIKE ? OR app.note LIKE ?)")
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
            projection = "app.id,app.job_id,app.status,app.outcome,app.version,app.applied_at,app.created_at,app.updated_at,"
            projection += "app.priority,app.deadline,"
            projection += "app.ready_at,app.ready_by_kind,app.ready_by_id,app.ready_by_name,"
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
            preparation = self._application_preparation(connection, [row["id"] for row in rows])
            staleness = application_staleness(connection, [row["id"] for row in rows])
        items = []
        for raw in rows:
            item = self._ready_by(
                {key: value for key, value in dict(raw).items() if not key.startswith("j_")}
            )
            item["job"] = self._compact_job(raw)
            item["preparation"] = preparation[item["id"]]
            item["stale_inputs"] = staleness[item["id"]]["inputs"]
            items.append(item)
        return {
            "items": items,
            "total": total,
            "stage_counts": counts,
            "ready_count": ready_count,
        }

    def delete_application(self, application_id, expected_version, collect=True):
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM applications WHERE id=?", (application_id,)
            ).fetchone()
            check_version(row, expected_version)
            owned = "SELECT id FROM documents WHERE application_id=? UNION SELECT id FROM contexts WHERE application_id=?"
            owned_files = "SELECT id FROM files WHERE document_id IN (SELECT id FROM documents WHERE application_id=?) OR context_id IN (SELECT id FROM contexts WHERE application_id=?)"
            connection.execute(
                "DELETE FROM transfer_grants WHERE json_extract(payload,'$.owner_id') IN ("
                + owned
                + ") OR json_extract(payload,'$.file_id') IN ("
                + owned_files
                + ")",
                (application_id,) * 4,
            )
            connection.execute("DELETE FROM applications WHERE id=?", (application_id,))
            if collect:
                connection.execute(COLLECT_BLOBS)
            self.event(
                "application_deleted",
                row["job_id"],
                payload={"application_id": application_id},
                conn=connection,
                subject=("application", application_id),
            )
        return {"deleted": True, "id": application_id}

    def get_note(self, note_id):
        return self._note(self.db.one("SELECT * FROM notes WHERE id=?", (note_id,)))

    def update_note(self, note_id, value):
        value = value if isinstance(value, NotePatch) else NotePatch.model_validate(value)
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
            check_version(row, value.expected_version)
            if row["body"] != value.body:
                connection.execute(
                    "UPDATE notes SET body=?,version=version+1,updated_at=? WHERE id=?",
                    (value.body, now(), note_id),
                )
                self.event(
                    "note_edited",
                    row["job_id"],
                    row["application_id"],
                    {"version": row["version"] + 1},
                    connection,
                    subject=("note", note_id),
                )
        return self.get_note(note_id)

    def _bulk(self, items, apply, deleting):
        """Run each versioned item on its own; collect orphaned blobs once per run."""
        results = []
        try:
            for item in items:
                try:
                    with self.db.lock:
                        result = apply(item)
                    results.append({"id": item.id, "ok": True, "result": result})
                except DomainError as error:
                    results.append(
                        {
                            "id": item.id,
                            "ok": False,
                            "error": {
                                "code": error.code,
                                "message": error.message,
                                "status": error.status,
                                "details": error.details,
                            },
                        }
                    )
        finally:
            if deleting and any(result["ok"] for result in results):
                self.db.collect_blobs()
        succeeded = sum(item["ok"] for item in results)
        return {
            "items": results,
            "total": len(results),
            "succeeded": succeeded,
            "failed": len(results) - succeeded,
        }

    def bulk_jobs(self, value):
        value = value if isinstance(value, JobBulk) else JobBulk.model_validate(value)

        def apply(item):
            row = self.db.one("SELECT id,version FROM jobs WHERE id=?", (item.id,))
            check_version(row, item.expected_version)
            if value.action == "forget":
                self.forget_job(item.id, item.expected_version, collect=False)
                return {"deleted": True}
            updated = self.set_triage(item.id, value.action, item.expected_version)
            return {"triage": updated["triage"], "version": updated["version"]}

        return self._bulk(value.items, apply, value.action == "forget")

    def bulk_applications(self, value):
        """Close with an outcome, reopen to a stage, mark or unmark ready, or delete versioned attempts."""
        value = (
            value if isinstance(value, ApplicationBulk) else ApplicationBulk.model_validate(value)
        )

        def apply(item):
            row = self.db.one("SELECT id,status,version FROM applications WHERE id=?", (item.id,))
            if row is None:
                missing("Application")
            check_version(row, item.expected_version)
            if value.action == "delete":
                self.delete_application(item.id, item.expected_version, collect=False)
                return {"deleted": True}
            if value.action in {"mark_ready", "unmark_ready"}:
                updated = self.set_ready(
                    item.id,
                    ApplicationReady(
                        expected_version=item.expected_version, ready=value.action == "mark_ready"
                    ),
                )
                return {
                    "job_id": updated["job_id"],
                    "readiness": updated["readiness"],
                    "ready_at": updated["ready_at"],
                    "version": updated["version"],
                }
            if value.action == "reopen" and row["status"] != "closed":
                raise DomainError(
                    409,
                    "application_open",
                    "Only a Closed application can be reopened.",
                    {"status": row["status"]},
                )
            patch = (
                {"status": "closed", "outcome": value.outcome}
                if value.action == "close"
                else {"status": value.status}
            )
            updated = self.update_application(
                item.id, ApplicationPatch(expected_version=item.expected_version, **patch)
            )
            return {
                "job_id": updated["job_id"],
                "status": updated["status"],
                "outcome": updated["outcome"],
                "version": updated["version"],
            }

        return self._bulk(value.items, apply, value.action == "delete")

    def create_application(self, value):
        value = (
            value if isinstance(value, ApplicationInput) else ApplicationInput.model_validate(value)
        )
        with self.db.transaction() as c:
            job = c.execute("SELECT * FROM jobs WHERE id=?", (value.job_id,)).fetchone()
            if not job:
                missing("Job")
            if value.idempotency_key:
                old = c.execute(
                    "SELECT id,job_id FROM applications WHERE idempotency_key=?",
                    (value.idempotency_key,),
                ).fetchone()
                if old:
                    if old["job_id"] != value.job_id:
                        conflict("This idempotency key already belongs to another job.")
                    return self.get_application(old["id"])
            if job["triage"] == "dismissed":
                conflict("Restore the dismissed job before preparing an application.")
            self._check_active_application(c, value.job_id)
            self.validate_answers([q.model_dump() for q in value.questions], {})
            record_id, stamp = new_id(), now()
            c.execute(
                "INSERT INTO applications(id,job_id,note,questions,priority,deadline,requirements,created_at,updated_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    record_id,
                    value.job_id,
                    value.note,
                    encode([q.model_dump() for q in value.questions]),
                    value.priority,
                    value.deadline,
                    encode(
                        self.normalize_requirements([r.model_dump() for r in value.requirements])
                    ),
                    stamp,
                    stamp,
                    value.idempotency_key,
                ),
            )
            c.execute(
                "UPDATE jobs SET triage='saved',version=version+1,updated_at=? WHERE id=?",
                (stamp, value.job_id),
            )
            self.event("application_created", value.job_id, record_id, {"status": "draft"}, c)
        return self.get_application(record_id)

    @staticmethod
    def _check_active_application(connection, job_id, excluding=None):
        active = connection.execute(
            "SELECT id,status FROM applications WHERE job_id=? AND status<>'closed' AND (? IS NULL OR id<>?) LIMIT 1",
            (job_id, excluding, excluding),
        ).fetchone()
        if active:
            raise DomainError(
                409,
                "application_in_progress",
                f"This job already has an active application ({active['id']}). Continue it or close it before starting another.",
                {"application_id": active["id"], "status": active["status"]},
            )

    def update_application(self, application_id, value):
        value = (
            value if isinstance(value, ApplicationPatch) else ApplicationPatch.model_validate(value)
        )
        changes = value.model_dump(exclude_unset=True, exclude={"expected_version"})
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
            check_version(row, value.expected_version)
            status = changes.get("status") or row["status"]
            if row["status"] == "closed" and status != "closed":
                self._check_active_application(c, row["job_id"], excluding=application_id)
            if status == "closed":
                outcome = changes.get("outcome", row["outcome"])
                if not outcome:
                    raise DomainError(
                        422, "application_outcome", "Choose an outcome when closing an application."
                    )
                changes["outcome"] = outcome
            else:
                if changes.get("outcome"):
                    raise DomainError(
                        422, "application_outcome", "Close the application to record an outcome."
                    )
                changes["outcome"] = None
            questions = (
                changes.get("questions")
                if changes.get("questions") is not None
                else json.loads(row["questions"])
            )
            answers = (
                changes.get("answers")
                if changes.get("answers") is not None
                else json.loads(row["answers"])
            )
            self.validate_answers(questions, answers)
            if "requirements" in changes:
                # Store every requirement field, including defaults the caller omitted.
                changes["requirements"] = self.normalize_requirements(
                    [item.model_dump() for item in value.requirements]
                )
            if (
                (
                    status in {"applied", "interview", "offer"}
                    or (status == "closed" and changes["outcome"] == "accepted")
                )
                and not row["applied_at"]
                and "applied_at" not in changes
            ):
                changes["applied_at"] = now()
            actual = {}
            for key, val in changes.items():
                if key == "status" and val is None:
                    continue
                structured = key in {"questions", "answers", "requirements"}
                previous = json.loads(row[key]) if structured else row[key]
                if previous != val:
                    actual[key] = encode(val) if structured else val
            if actual:
                c.execute(
                    "UPDATE applications SET "
                    + ",".join(k + "=?" for k in actual)
                    + ",version=version+1,updated_at=? WHERE id=?",
                    (*actual.values(), now(), application_id),
                )
                self.event(
                    "application_updated",
                    row["job_id"],
                    application_id,
                    {"from": row["status"], "to": status, "fields": list(actual)},
                    c,
                )
                # Ready is a judgement on a Preparing attempt without blocking requirements.
                if status != "draft":
                    self.clear_ready(c, application_id, "left_preparing")
                elif "requirements" in actual and any(
                    item["blocking"] and not item["resolved"] for item in changes["requirements"]
                ):
                    self.clear_ready(c, application_id, "blocking_requirement")
        return self.get_application(application_id, compact_job=True)

    def set_ready(self, application_id, value):
        """Mark a Preparing application ready to apply, or clear the mark.

        Marking is refused while a derived readiness check fails; the error names it.
        """
        value = (
            value if isinstance(value, ApplicationReady) else ApplicationReady.model_validate(value)
        )
        with self.db.transaction() as c:
            row = c.execute(
                f"SELECT app.*,{READINESS_SQL} AS readiness,{REQUIREMENT_COUNTS_SQL} FROM applications app WHERE app.id=?",
                (application_id,),
            ).fetchone()
            if row is None:
                missing("Application")
            check_version(row, value.expected_version)
            if not value.ready:
                self.clear_ready(c, application_id, "unmarked")
            elif row["ready_at"] is None:
                details = {
                    "readiness": row["readiness"],
                    "status": row["status"],
                    "blocking_requirements": row["blocking_requirements"],
                    "current_version": row["version"],
                }
                if row["status"] != "draft":
                    raise DomainError(
                        409,
                        "application_not_ready",
                        "Only a Preparing application can be marked ready.",
                        {"check": "stage", **details},
                    )
                if row["readiness"] in NOT_READY:
                    raise DomainError(
                        409,
                        "application_not_ready",
                        NOT_READY[row["readiness"]],
                        {"check": row["readiness"], **details},
                    )
                stamp = now()
                c.execute(
                    "UPDATE applications SET ready_at=?,ready_by_kind=?,ready_by_id=?,ready_by_name=?,version=version+1,updated_at=? WHERE id=?",
                    (stamp, *current_actor().columns(), stamp, application_id),
                )
                self.event("application_marked_ready", row["job_id"], application_id, conn=c)
        return self.get_application(application_id, compact_job=True)

    def clear_ready(self, conn, application_id, reason):
        """Clear the stored Ready step once its judgement no longer holds, recording why.

        Every shared service that changes what Ready was judged on calls this in its
        own transaction. Returns whether the application was ready.
        """
        row = conn.execute(
            "SELECT job_id FROM applications WHERE id=? AND ready_at IS NOT NULL", (application_id,)
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            "UPDATE applications SET ready_at=NULL,ready_by_kind=NULL,ready_by_id=NULL,ready_by_name=NULL,version=version+1,updated_at=? WHERE id=?",
            (now(), application_id),
        )
        self.event(
            "application_ready_cleared",
            row["job_id"],
            application_id,
            {"reason": reason, "automatic": reason != "unmarked"},
            conn,
        )
        return True

    @staticmethod
    def normalize_requirements(requirements):
        """Give each requirement a stable identifier and reject duplicate identifiers."""
        seen = set()
        for requirement in requirements:
            requirement["id"] = requirement.get("id") or new_id()[:12]
            if requirement["id"] in seen:
                raise DomainError(422, "requirement_id", "Requirement IDs must be unique.")
            seen.add(requirement["id"])
        return requirements

    @staticmethod
    def validate_answers(questions, answers):
        if not isinstance(questions, list) or not isinstance(answers, dict):
            raise DomainError(
                422, "answer_state", "Questions must be an array and answers an object."
            )
        by_id = {q["id"]: q for q in questions}
        if len(by_id) != len(questions):
            raise DomainError(422, "question_id", "Question IDs must be unique.")
        for key, answer in answers.items():
            if key not in by_id:
                raise DomainError(
                    422, "answer_question", "An answer references an unknown question."
                )
            question = by_id[key]
            if answer is None:
                continue
            kind = question.get("type", "text")
            if kind == "number" and (
                isinstance(answer, bool)
                or not isinstance(answer, (int, float))
                or not math.isfinite(answer)
            ):
                raise DomainError(422, "answer_number", "A numeric answer must be a finite number.")
            if kind == "text" and not isinstance(answer, str):
                raise DomainError(422, "answer_text", "A text answer must be text.")
            if question.get("max_length") and len(str(answer)) > question["max_length"]:
                raise DomainError(
                    422, "answer_length", f"Answer exceeds the limit for {question['label']}."
                )
            if question.get("type") == "choice" and answer not in question.get("options", []):
                raise DomainError(422, "answer_choice", "Select one of the listed choices.")
            if question.get("type") == "boolean" and not isinstance(answer, bool):
                raise DomainError(422, "answer_boolean", "A yes/no answer must be true or false.")

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
                "outcomes": {"waiting": 0, "rejected": 0, "not_pursued": 0, "accepted": 0},
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
                self.event_record(r)
                for r in self.db.all(
                    "SELECT events.*,jobs.title,jobs.company FROM events LEFT JOIN jobs ON jobs.id=events.job_id ORDER BY events.created_at DESC LIMIT 12"
                )
            ],
        }
