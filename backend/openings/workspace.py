"""Core archive operations, shared by the dashboard, REST and MCP."""

import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .common import check_version, new_id, now
from .db import Database, decode_record, encode
from .errors import DomainError, conflict, missing
from .models import ApplicationInput, ApplicationPatch, JobInput, JobPatch, NoteInput


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

    def _job(self, row):
        if not row:
            missing("Job")
        row = decode_record(row, ("metadata", "overrides"))
        score = self.db.one(
            "SELECT * FROM assessments WHERE job_id=? ORDER BY created_at DESC LIMIT 1",
            (row["id"],),
        )
        row["assessment"] = decode_record(score, ("payload",))
        row["score"] = score["score"] if score else None
        row["score_outdated"] = bool(
            score
            and (
                score["job_version"] != row["content_version"]
                or score["profile_version"] != self.scoring_profile_version()
                or score["config_version"]
                != int(self.get_settings("scoring_config_revision", 0)["data"])
            )
        )
        row["complete"] = bool(row["posting"].strip())
        return row

    def get_job(self, job_id):
        return self._job(self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,)))

    def list_jobs(self, q="", triage=None, company=None, limit=50, offset=0, sort="newest"):
        limit, offset = min(max(int(limit), 1), 200), max(int(offset), 0)
        conditions, args = [], []
        if triage:
            conditions.append("triage=?")
            args.append(triage)
        if company:
            conditions.append("company=?")
            args.append(company)
        if q.strip():
            terms = re.findall(r"\w+", q)
            if terms:
                conditions.append("rowid IN (SELECT rowid FROM jobs_fts WHERE jobs_fts MATCH ?)")
                args.append(" AND ".join('"' + term + '"*' for term in terms[:15]))
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        total = self.db.one("SELECT count(*) AS n FROM jobs" + where, args)["n"]
        order = {
            "oldest": "created_at ASC",
            "company": "company,title",
            "title": "title",
            "score": "(SELECT score FROM assessments WHERE job_id=jobs.id ORDER BY created_at DESC LIMIT 1) DESC",
            "fit": "(SELECT score FROM assessments WHERE job_id=jobs.id ORDER BY created_at DESC LIMIT 1) DESC",
        }.get(sort, "created_at DESC")
        items = [
            self._job(r)
            for r in self.db.all(
                "SELECT * FROM jobs" + where + " ORDER BY " + order + " LIMIT ? OFFSET ?",
                [*args, limit, offset],
            )
        ]
        return {"items": items, "total": total}

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
            for table in ("postings", "applications", "events", "notes", "assessments", "tasks"):
                c.execute(f"UPDATE {table} SET job_id=? WHERE job_id=?", (target_id, source_id))
            c.execute("UPDATE files SET job_id=? WHERE job_id=?", (target_id, source_id))
            c.execute("DELETE FROM jobs WHERE id=?", (source_id,))
            c.execute(
                "UPDATE jobs SET version=version+1,content_version=content_version+1,updated_at=? WHERE id=?",
                (now(), target_id),
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

    def list_applications(self, status=None, limit=100, offset=0):
        where, args = (" WHERE status=?", [status]) if status else ("", [])
        rows = self.db.all(
            "SELECT id FROM applications" + where + " ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (*args, min(max(limit, 1), 200), max(offset, 0)),
        )
        return {
            "items": [self.get_application(r["id"]) for r in rows],
            "total": self.db.one("SELECT count(*) n FROM applications" + where, args)["n"],
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
                    "SELECT id FROM applications WHERE idempotency_key=?", (value.idempotency_key,)
                ).fetchone()
                if old:
                    return self.get_application(old["id"])
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
            if status == "applied" and not row["applied_at"] and "applied_at" not in changes:
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
        by_id = {q["id"]: q for q in questions}
        for key, answer in answers.items():
            if key not in by_id:
                raise DomainError(
                    422, "answer_question", "An answer references an unknown question."
                )
            question = by_id[key]
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

    def overview(self, since=None):
        apps = self.db.all(
            "SELECT * FROM applications" + (" WHERE created_at>=?" if since else ""),
            (since,) if since else (),
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
        sent = 0
        for app in apps:
            events = self.db.all("SELECT payload FROM events WHERE application_id=?", (app["id"],))
            observed = {json.loads(e["payload"]).get("to") for e in events}
            if app["applied_at"]:
                observed.add("applied")
            if "applied" not in observed:
                continue
            sent += 1
            reached = [i for i, s in enumerate(stages) if s in observed or app["status"] == s]
            highest = max(reached, default=0)
            for i in range(highest + 1):
                funnel[i]["count"] += 1
            outcome = (app["outcome"] or "not_pursued") if app["status"] == "closed" else "waiting"
            funnel[highest]["outcomes"][outcome] += 1
        jobs = [self._job(r) for r in self.db.all("SELECT * FROM jobs WHERE triage!='dismissed'")]
        return {
            "sent": sent,
            "interviews": funnel[1]["count"],
            "offers": funnel[2]["count"],
            "active": sum(a["status"] not in {"draft", "closed"} for a in apps),
            "drafts": sum(a["status"] == "draft" for a in apps),
            "inbox": sum(j["triage"] == "inbox" for j in jobs),
            "outdated": sum(j["score_outdated"] for j in jobs),
            "incomplete": sum(not j["complete"] for j in jobs),
            "funnel": funnel,
            "activity": [
                decode_record(r, ("payload",))
                for r in self.db.all(
                    "SELECT events.*,jobs.title,jobs.company FROM events LEFT JOIN jobs ON jobs.id=events.job_id ORDER BY events.created_at DESC LIMIT 12"
                )
            ],
        }
