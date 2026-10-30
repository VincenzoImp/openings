"""Core archive operations, shared by the dashboard, REST and MCP."""

import hashlib
import math
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .common import check_version, new_id, now
from .db import Database, decode_record, encode
from .errors import DomainError, conflict, missing
from .models import (
    ApplicationInput,
    ApplicationPatch,
    JobInput,
    JobPatch,
    NoteInput,
    NotePatch,
    JobBulk,
)


def normalize_url(url):
    if not url:
        return ""
    p = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
        and k.lower() not in {"gclid", "fbclid", "ref", "source"}
    ]
    return urlunsplit(
        (
            p.scheme.lower(),
            p.netloc.lower(),
            p.path.rstrip("/") or "/",
            urlencode(sorted(query)),
            "",
        )
    )


def posting_identity(url):
    p = urlsplit(url)
    parts = [s for s in p.path.split("/") if s]
    host = (p.hostname or "").lower()
    if (
        host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}
        and len(parts) >= 3
        and parts[1] == "jobs"
    ):
        return f"greenhouse:{parts[0]}:{parts[2]}"
    if host in {"jobs.lever.co", "jobs.eu.lever.co"} and len(parts) >= 2:
        return f"lever:{parts[0]}:{parts[1]}"
    if host == "jobs.ashbyhq.com" and len(parts) >= 2:
        return f"ashby:{parts[0]}:{parts[1]}"
    return "url:" + normalize_url(url) if url else None


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
                conflict()
            if row and self.get_settings(key)["data"] == data:
                return {"data": data, "version": version}
            c.execute(
                "INSERT INTO settings(key,data,version,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=excluded.version,updated_at=excluded.updated_at",
                (key, encode(data), version + 1, now()),
            )
        return {"data": data, "version": version + 1}

    def bump_scoring_profile(self):
        with self.db.transaction() as c:
            row = c.execute(
                "SELECT data,version FROM settings WHERE key='scoring_profile_revision'"
            ).fetchone()
            value = int(json.loads(row["data"])) + 1 if row else 1
            c.execute(
                "INSERT INTO settings(key,data,version,updated_at) VALUES('scoring_profile_revision',?,?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=excluded.version,updated_at=excluded.updated_at",
                (encode(value), value, now()),
            )
        return value

    def scoring_profile_version(self):
        return int(self.get_settings("scoring_profile_revision", 0)["data"])

    def scoring_profile(self):
        profile = self.get_settings("profile")["data"]
        return {
            "version": self.scoring_profile_version(),
            "profile": {
                k: v for k, v in profile.items() if k not in {"name", "email", "phone", "links"}
            },
            "knowledge": [
                decode_record(r, ("metadata",))
                for r in self.db.all("SELECT * FROM knowledge ORDER BY created_at")
            ],
            "claims": [
                decode_record(r, ("metadata",))
                for r in self.db.all("SELECT * FROM claims WHERE approved=1 ORDER BY created_at")
            ],
        }

    def event(self, kind, job_id=None, application_id=None, payload=None, conn=None):
        args = (new_id(), job_id, application_id, kind, encode(payload or {}), now())
        sql = "INSERT INTO events(id,job_id,application_id,kind,payload,created_at) VALUES(?,?,?,?,?,?)"
        if conn is not None:
            conn.execute(sql, args)
        else:
            self.db.execute(sql, args)

    @staticmethod
    def _revisions(connection):
        values = {
            row["key"]: json.loads(row["data"])
            for row in connection.execute(
                "SELECT key,data FROM settings WHERE key IN ('scoring_profile_revision','scoring_config_revision')"
            )
        }
        return int(values.get("scoring_profile_revision", 0)), int(
            values.get("scoring_config_revision", 0)
        )

    @staticmethod
    def _job_join():
        return " LEFT JOIN assessments a ON a.id=(SELECT id FROM assessments WHERE job_id=j.id ORDER BY created_at DESC,id DESC LIMIT 1) "

    @staticmethod
    def _job_columns(revisions):
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
        profile, config = revisions
        columns += [
            "substr(j.posting,1,240) AS j_posting_preview",
            "length(trim(j.posting))>0 AS j_complete",
            "a.score AS j_score",
            f"(a.id IS NOT NULL AND (a.job_version!=j.content_version OR a.profile_version!={profile} OR a.config_version!={config})) AS j_score_outdated",
        ]
        return ",".join(columns)

    @staticmethod
    def _compact_job(row):
        result = {key[2:]: value for key, value in dict(row).items() if key.startswith("j_")}
        result["metadata"] = json.loads(result["metadata"])
        result["complete"] = bool(result["complete"])
        result["score_outdated"] = bool(result["score_outdated"])
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
            raw = connection.execute(
                "SELECT * FROM assessments WHERE job_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            score = dict(raw) if raw else None
            profile, config = self._revisions(connection)
            row["postings"] = [
                dict(posting)
                for posting in connection.execute(
                    "SELECT id,source_id,identity,url,first_seen_at,last_seen_at FROM postings WHERE job_id=? ORDER BY first_seen_at",
                    (row["id"],),
                )
            ]
        row["assessment"] = decode_record(score, ("payload",))
        row["score"] = score["score"] if score else None
        row["score_outdated"] = bool(
            score
            and (
                score["job_version"] != row["content_version"]
                or score["profile_version"] != profile
                or score["config_version"] != config
            )
        )
        row["complete"] = bool(row["posting"].strip())
        return row

    def get_job(self, job_id):
        return self._job(self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,)))

    @staticmethod
    def _job_filters(
        q="",
        triage=None,
        company=None,
        location=None,
        source=None,
        remote=None,
        job_type=None,
        score_min=None,
        score_max=None,
        score_state="all",
        created_since=None,
        created_until=None,
        revisions=(0, 0),
        complete=None,
    ):
        conditions, args = [], []
        if triage == "active":
            conditions.append("j.triage!='dismissed'")
        elif triage:
            if triage not in ("inbox", "saved", "dismissed"):
                raise DomainError(422, "triage", "Choose inbox, saved or dismissed.")
            conditions.append("j.triage=?")
            args.append(triage)
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
            conditions.append("(length(trim(j.posting))>0)=?")
            args.append(int(complete))
        if job_type:
            conditions.append("json_extract(j.metadata,'$.job_type')=?")
            args.append(job_type)
        for value, operator in ((score_min, ">="), (score_max, "<=")):
            if value is not None:
                if not 0 <= value <= 100:
                    raise DomainError(422, "score_range", "Score bounds must be between 0 and 100.")
                conditions.append("a.score" + operator + "?")
                args.append(value)
        profile, config = revisions
        stale = f"(a.job_version!=j.content_version OR a.profile_version!={profile} OR a.config_version!={config})"
        if score_state == "unscored":
            conditions.append("a.id IS NULL")
        elif score_state in ("current", "outdated"):
            conditions.append(
                "a.id IS NOT NULL AND " + (stale if score_state == "outdated" else "NOT " + stale)
            )
        elif score_state != "all":
            raise DomainError(422, "score_state", "Choose all, current, outdated or unscored.")
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
        score_min=None,
        score_max=None,
        score_state="all",
        created_since=None,
        created_until=None,
        complete=None,
    ):
        limit, offset = min(max(int(limit), 1), 200), max(int(offset), 0)
        with self.db.connect() as connection:
            revisions = self._revisions(connection)
            where, args = self._job_filters(
                q,
                triage,
                company,
                location,
                source,
                remote,
                job_type,
                score_min,
                score_max,
                score_state,
                created_since,
                created_until,
                revisions,
                complete,
            )
            base = " FROM jobs j" + self._job_join()
            order = {
                "oldest": "j.created_at ASC",
                "company": "j.company,j.title",
                "title": "j.title",
                "score": "a.score DESC",
                "fit": "a.score DESC",
            }.get(sort, "j.created_at DESC")
            rows = connection.execute(
                "SELECT "
                + self._job_columns(revisions)
                + base
                + where
                + " ORDER BY "
                + order
                + ",j.id LIMIT ? OFFSET ?",
                (*args, limit, offset),
            ).fetchall()
            total = connection.execute("SELECT count(*)" + base + where, args).fetchone()[0]
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
        return {"items": [self._compact_job(row) for row in rows], "total": total, "facets": facets}

    def ingest_job(self, value):
        value = value if isinstance(value, JobInput) else JobInput.model_validate(value)
        data = value.model_dump()
        if not value.url and not value.posting.strip():
            raise DomainError(422, "job_content", "Provide a job URL or posting text.")
        url = normalize_url(value.url)
        identity = posting_identity(url) or value.source_key or "manual:" + new_id()
        if value.source_key and not url:
            identity = value.source_key
        title = value.title.strip() or "Untitled opportunity"
        company = value.company.strip() or (urlsplit(url).hostname or "Unknown company")
        data.update(title=title, company=company, url=url)
        changed = False
        with self.db.transaction() as c:
            prior = c.execute(
                "SELECT jobs.* FROM postings JOIN jobs ON jobs.id=postings.job_id WHERE postings.identity=? OR (?<>'' AND postings.url=?) LIMIT 1",
                (identity, url, url),
            ).fetchone()
            if prior is None and url:
                prior = c.execute("SELECT * FROM jobs WHERE url=?", (url,)).fetchone()
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
                changed = True
            else:
                overrides = json.loads(prior["overrides"])
                updates = {}
                for key in ("title", "company", "location", "url", "posting", "metadata"):
                    incoming = data[key]
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
                    changed = True
            content_hash = hashlib.sha256(encode(data).encode()).hexdigest()
            c.execute(
                "INSERT INTO postings(id,job_id,source_id,identity,url,payload,content_hash,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(identity) DO UPDATE SET last_seen_at=excluded.last_seen_at,payload=excluded.payload,content_hash=excluded.content_hash",
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
        if changed and self.discovery is not None:
            self.discovery.enqueue_job(job_id)
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
                self.event("job_edited", job_id, payload={"fields": list(actual)}, conn=c)
        if actual and self.discovery:
            self.discovery.enqueue_job(job_id)
        return self.get_job(job_id)

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
        return self.get_job(job_id)

    def forget_job(self, job_id):
        with self.db.transaction() as c:
            if not c.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
                missing("Job")
            c.execute(
                "DELETE FROM transfer_grants WHERE json_extract(payload,'$.job_id')=?", (job_id,)
            )
            c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
            c.execute("DELETE FROM blobs WHERE sha256 NOT IN (SELECT sha256 FROM files)")
        return {"deleted": True, "id": job_id}

    def merge_jobs(self, source_id, target_id, expected_version, target_version):
        if source_id == target_id:
            raise DomainError(422, "merge", "Choose a different target job.")
        with self.db.transaction() as c:
            for record_id, version in ((source_id, expected_version), (target_id, target_version)):
                check_version(
                    c.execute("SELECT * FROM jobs WHERE id=?", (record_id,)).fetchone(), version
                )
            next_content = c.execute(
                "SELECT max(v)+1 FROM (SELECT content_version v FROM jobs WHERE id IN (?,?) UNION ALL SELECT job_version v FROM assessments WHERE job_id IN (?,?))",
                (source_id, target_id, source_id, target_id),
            ).fetchone()[0]
            c.execute(
                "UPDATE tasks SET state='cancelled',updated_at=? WHERE job_id IN (?,?) AND state IN ('queued','running')",
                (now(), source_id, target_id),
            )
            c.execute(
                "UPDATE transfer_grants SET payload=json_set(payload,'$.job_id',?,'$.owner_id',CASE WHEN json_extract(payload,'$.owner_type')='job' THEN ? ELSE json_extract(payload,'$.owner_id') END) WHERE json_extract(payload,'$.job_id')=?",
                (target_id, target_id, source_id),
            )
            for table in ("postings", "applications", "events", "notes", "assessments", "tasks"):
                c.execute(f"UPDATE {table} SET job_id=? WHERE job_id=?", (target_id, source_id))
            c.execute("UPDATE files SET job_id=? WHERE job_id=?", (target_id, source_id))
            c.execute("DELETE FROM jobs WHERE id=?", (source_id,))
            c.execute(
                "UPDATE jobs SET version=version+1,content_version=?,updated_at=? WHERE id=?",
                (next_content, now(), target_id),
            )
            self.event("jobs_merged", target_id, payload={"previous_id": source_id}, conn=c)
        return self.get_job(target_id)

    def list_notes(self, job_id):
        self.get_job(job_id)
        rows = self.db.all("SELECT * FROM notes WHERE job_id=? ORDER BY created_at DESC", (job_id,))
        return {"items": rows, "total": len(rows)}

    def add_note(self, job_id, value):
        value = value if isinstance(value, NoteInput) else NoteInput.model_validate(value)
        self.get_job(job_id)
        if value.application_id and self.get_application(value.application_id)["job_id"] != job_id:
            raise DomainError(422, "note_owner", "Application belongs to a different job.")
        note_id, stamp = new_id(), now()
        self.db.execute(
            "INSERT INTO notes(id,job_id,application_id,body,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (note_id, job_id, value.application_id, value.body, stamp, stamp),
        )
        return self.db.one("SELECT * FROM notes WHERE id=?", (note_id,))

    def delete_note(self, note_id):
        if not self.db.execute("DELETE FROM notes WHERE id=?", (note_id,)):
            missing("Note")
        return {"deleted": True}

    def get_application(self, application_id):
        row = self.db.one("SELECT * FROM applications WHERE id=?", (application_id,))
        if not row:
            missing("Application")
        row = decode_record(row, ("questions", "answers"))
        row["job"] = self.get_job(row["job_id"])
        row["documents_count"] = self.db.one(
            "SELECT count(*) n FROM documents WHERE application_id=?", (application_id,)
        )["n"]
        return row

    def list_applications(
        self, status=None, limit=100, offset=0, q="", outcome=None, company=None, sort="updated"
    ):
        conditions, args = [], []
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
        base = " FROM applications app JOIN jobs j ON j.id=app.job_id" + self._job_join()
        order = {
            "newest": "app.created_at DESC",
            "oldest": "app.created_at ASC",
            "company": "j.company,j.title",
            "stage": "app.status,app.updated_at DESC",
            "applied": "app.applied_at DESC",
        }.get(sort, "app.updated_at DESC")
        with self.db.connect() as connection:
            projection = "app.id,app.job_id,app.status,app.outcome,app.version,app.applied_at,app.created_at,app.updated_at,"
            projection += (
                "(SELECT count(*) FROM documents WHERE application_id=app.id) AS documents_count,"
            )
            projection += self._job_columns(self._revisions(connection))
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
            for row in connection.execute(
                "SELECT app.status,count(*) n" + base + where + " GROUP BY app.status", args
            ):
                counts[row["status"]] = row["n"]
        items = []
        for raw in rows:
            item = {key: value for key, value in dict(raw).items() if not key.startswith("j_")}
            item["job"] = self._compact_job(raw)
            items.append(item)
        return {"items": items, "total": total, "stage_counts": counts}

    def delete_application(self, application_id, expected_version=None):
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
            connection.execute("DELETE FROM blobs WHERE sha256 NOT IN (SELECT sha256 FROM files)")
            self.event(
                "application_deleted",
                row["job_id"],
                payload={"application_id": application_id},
                conn=connection,
            )
        return {"deleted": True, "id": application_id}

    def get_note(self, note_id):
        row = self.db.one("SELECT * FROM notes WHERE id=?", (note_id,))
        if not row:
            missing("Note")
        return row

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
        return self.get_note(note_id)

    def bulk_jobs(self, value):
        value = value if isinstance(value, JobBulk) else JobBulk.model_validate(value)
        results = []
        for item in value.items:
            try:
                with self.db.lock:
                    row = self.db.one("SELECT id,version FROM jobs WHERE id=?", (item.id,))
                    check_version(row, item.expected_version)
                    if value.action == "forget":
                        self.forget_job(item.id)
                        result = {"deleted": True}
                    elif value.action == "rescore":
                        if self.discovery is None:
                            raise DomainError(
                                409, "scoring_unavailable", "Scoring is not configured."
                            )
                        from .discovery import RescoreRequest

                        result = self.discovery.queue_rescore(
                            RescoreRequest(job_ids=[item.id], outdated_only=False, limit=1)
                        )
                    else:
                        updated = self.set_triage(item.id, value.action, item.expected_version)
                        result = {"triage": updated["triage"], "version": updated["version"]}
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
                        },
                    }
                )
        succeeded = sum(item["ok"] for item in results)
        return {
            "items": results,
            "total": len(results),
            "succeeded": succeeded,
            "failed": len(results) - succeeded,
        }

    def create_application(self, value):
        value = (
            value if isinstance(value, ApplicationInput) else ApplicationInput.model_validate(value)
        )
        with self.db.transaction() as c:
            job = c.execute("SELECT * FROM jobs WHERE id=?", (value.job_id,)).fetchone()
            if not job:
                missing("Job")
            if job["triage"] == "dismissed":
                conflict("Restore the dismissed job before preparing an application.")
            if value.idempotency_key:
                old = c.execute(
                    "SELECT id,job_id FROM applications WHERE idempotency_key=?",
                    (value.idempotency_key,),
                ).fetchone()
                if old:
                    if old["job_id"] != value.job_id:
                        conflict("This idempotency key already belongs to another job.")
                    return self.get_application(old["id"])
            self.validate_answers([q.model_dump() for q in value.questions], {})
            record_id, stamp = new_id(), now()
            c.execute(
                "INSERT INTO applications(id,job_id,note,questions,created_at,updated_at,idempotency_key) VALUES(?,?,?,?,?,?,?)",
                (
                    record_id,
                    value.job_id,
                    value.note,
                    encode([q.model_dump() for q in value.questions]),
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

    def update_application(self, application_id, value):
        value = (
            value if isinstance(value, ApplicationPatch) else ApplicationPatch.model_validate(value)
        )
        changes = value.model_dump(exclude_unset=True, exclude={"expected_version"})
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
            check_version(row, value.expected_version)
            status = changes.get("status") or row["status"]
            changes["outcome"] = (
                (changes.get("outcome") or row["outcome"] or "not_pursued")
                if status == "closed"
                else None
            )
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
                previous = json.loads(row[key]) if key in {"questions", "answers"} else row[key]
                if previous != val:
                    actual[key] = encode(val) if key in {"questions", "answers"} else val
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
        return self.get_application(application_id)

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
            decode_record(r, ("payload",))
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
            "SELECT id,status,outcome,applied_at FROM applications WHERE id IN (" + cohort + ")",
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
        for event in self.db.all(
            "SELECT application_id,payload FROM events WHERE application_id IN (" + cohort + ")",
            bounds,
        ):
            observed_by_app.setdefault(event["application_id"], set()).add(
                json.loads(event["payload"]).get("to")
            )
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
            "SELECT count(*) n,coalesce(sum(triage='inbox'),0) inbox,coalesce(sum(length(trim(posting))=0),0) incomplete FROM jobs WHERE triage!='dismissed'"
        )
        outdated = self.db.one(
            "SELECT count(*) n FROM jobs j JOIN assessments a ON a.id=(SELECT id FROM assessments WHERE job_id=j.id ORDER BY created_at DESC LIMIT 1) WHERE j.triage!='dismissed' AND (a.job_version!=j.content_version OR a.profile_version!=? OR a.config_version!=?)",
            (
                self.scoring_profile_version(),
                int(self.get_settings("scoring_config_revision", 0)["data"]),
            ),
        )["n"]
        return {
            "sent": sent,
            "interviews": funnel[1]["count"],
            "offers": funnel[2]["count"],
            "active": sum(a["status"] not in {"draft", "closed"} for a in apps),
            "drafts": sum(a["status"] == "draft" for a in apps),
            "inbox": counts["inbox"],
            "outdated": outdated,
            "incomplete": counts["incomplete"],
            "funnel": funnel,
            "activity": [
                decode_record(r, ("payload",))
                for r in self.db.all(
                    "SELECT events.*,jobs.title,jobs.company FROM events LEFT JOIN jobs ON jobs.id=events.job_id ORDER BY events.created_at DESC LIMIT 12"
                )
            ],
        }
