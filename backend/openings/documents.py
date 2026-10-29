"""Frozen application context, immutable documents and bounded SQLite file transfers."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
import secrets
from typing import Any, Literal
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import Field, field_validator

from .career import DEFAULT_GUIDANCE, DEFAULT_PROFILE, Input, _get, _page, _setting
from .common import decode_record, encode, new_id, now
from .errors import DomainError, conflict, missing


OwnerType = Literal["knowledge", "template", "document", "context", "job"]
OWNER_COLUMNS = {
    name: f"{name}_id" for name in ["knowledge", "template", "document", "context", "job"]
}
OWNER_TABLES = {
    "knowledge": "knowledge",
    "template": "templates",
    "document": "documents",
    "context": "contexts",
    "job": "jobs",
}


class ContextCreate(Input):
    application_id: str
    template_id: str | None = None
    template_ids: list[str] = Field(default_factory=list, max_length=20)
    knowledge_ids: list[str] | None = Field(default=None, max_length=500)
    claim_ids: list[str] | None = Field(default=None, max_length=1000)
    note: str = Field(default="", max_length=20000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class DocumentCreate(Input):
    application_id: str
    context_id: str | None = None
    kind: Literal["resume", "cover_letter", "answers", "other"] = "resume"
    title: str = Field(default="", max_length=300)
    content: dict[str, Any] = Field(default_factory=dict)
    previous_id: str | None = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value):
        try:
            encoded = json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("Content must contain finite JSON values.") from error
        if len(encoded) > 1000000:
            raise ValueError("Structured content exceeds the 1 MB limit.")
        return value


class ReviewUpdate(Input):
    review_state: Literal["approved"] = "approved"
    expected_review_state: Literal["draft", "approved"] | None = None


class UploadReservation(Input):
    owner_type: Literal["knowledge", "template", "document", "job"]
    owner_id: str
    name: str = Field(min_length=1, max_length=500)
    media_type: str = Field(default="application/octet-stream", min_length=1, max_length=200)
    size: int = Field(gt=0, strict=True)
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")

    @field_validator("name")
    @classmethod
    def safe_relative_name(cls, value):
        value = value.replace("\\", "/")
        path = PurePosixPath(value)
        if (
            not path.name
            or path.is_absolute()
            or ":" in path.parts[0]
            or any(part in {"..", "."} for part in path.parts)
            or "\x00" in value
        ):
            raise ValueError("Use a relative file name without parent-directory segments.")
        if any(ord(character) < 32 for character in value):
            raise ValueError("Control characters are not permitted in file names.")
        return value

    @field_validator("media_type")
    @classmethod
    def valid_media_type(cls, value):
        if any(ord(character) < 32 or ord(character) > 126 for character in value):
            raise ValueError("Invalid media type.")
        return value


class DocumentService:
    def __init__(self, workspace, max_file_bytes: int = 20 * 1024 * 1024):
        self.workspace = workspace
        self.db = workspace.db
        self.max_file_bytes = max_file_bytes
        self._upload_slots = asyncio.Semaphore(2)

    def prepare_context(self, value: ContextCreate) -> dict:
        """Freeze job, career evidence, approved claims, templates/assets and stored instructions for an external agent. Use an idempotency key for retries."""
        request = value.model_dump(exclude={"idempotency_key"})
        with self.db.transaction() as conn:
            if value.idempotency_key:
                existing = conn.execute(
                    "SELECT * FROM contexts WHERE idempotency_key=?", (value.idempotency_key,)
                ).fetchone()
                if existing:
                    frozen = json.loads(existing["payload"])
                    if frozen.get("request") != request:
                        conflict("This idempotency key was used for another preparation request.")
                    return self._context_record(dict(existing))
            application = _get(conn, "applications", value.application_id, "Application")
            job = _get(conn, "jobs", application["job_id"], "Job")
            if job["triage"] == "dismissed":
                conflict("Restore this dismissed job before preparing an application.")
            application = decode_record(application, ["questions", "answers"])
            job = decode_record(job, ["metadata", "overrides"])
            profile = _setting(conn, "profile", DEFAULT_PROFILE)
            instructions = _setting(conn, "instructions", {"general": DEFAULT_GUIDANCE})
            knowledge = [
                decode_record(dict(row), ["metadata"])
                for row in conn.execute("SELECT * FROM knowledge ORDER BY created_at,id")
            ]
            if value.knowledge_ids is not None:
                requested = set(value.knowledge_ids)
                if requested - {row["id"] for row in knowledge}:
                    raise DomainError(
                        422, "unknown_evidence", "Selected career evidence was not found."
                    )
                knowledge = [row for row in knowledge if row["id"] in requested]
            knowledge_ids = {row["id"] for row in knowledge}
            claims = [
                decode_record(dict(row), ["metadata"])
                for row in conn.execute(
                    "SELECT * FROM claims WHERE approved=1 ORDER BY created_at,id"
                )
                if row["knowledge_id"] in knowledge_ids
            ]
            for claim in claims:
                claim["approved"] = bool(claim["approved"])
            if value.claim_ids is not None:
                selected = set(value.claim_ids)
                if selected - {row["id"] for row in claims}:
                    raise DomainError(
                        422,
                        "unapproved_claim",
                        "Selected claims must be approved and belong to the selected evidence.",
                    )
                claims = [row for row in claims if row["id"] in selected]
            selected_templates = list(
                dict.fromkeys(
                    ([value.template_id] if value.template_id else []) + value.template_ids
                )
            )
            if selected_templates:
                selected = {
                    row["id"]: dict(row)
                    for row in conn.execute(
                        "SELECT * FROM templates WHERE id IN ("
                        + ",".join("?" for _ in selected_templates)
                        + ")",
                        selected_templates,
                    )
                }
                if len(selected) != len(selected_templates):
                    missing("Template")
                templates = [selected[template_id] for template_id in selected_templates]
            else:
                templates = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT * FROM templates WHERE is_default=1 ORDER BY kind,id"
                    )
                ]
            if not templates:
                raise DomainError(
                    422,
                    "template_required",
                    "Add or select a template before preparing the application context.",
                )
            templates = [decode_record(row, ["rules"]) for row in templates]
            for template in templates:
                template["is_default"] = bool(template["is_default"])
            context_id, timestamp = new_id(), now()
            assets = []
            for owner_type, identifiers in [
                ("knowledge", [row["id"] for row in knowledge]),
                ("template", [row["id"] for row in templates]),
            ]:
                if not identifiers:
                    continue
                column = OWNER_COLUMNS[owner_type]
                for raw in conn.execute(
                    f"SELECT * FROM files WHERE {column} IN ("
                    + ",".join("?" for _ in identifiers)
                    + f") ORDER BY {column},name,id",
                    identifiers,
                ):
                    original = dict(raw)
                    owner_id = original[column]
                    copied_id = new_id()
                    copied_name = f"{owner_type}/{owner_id}/{original['name']}"
                    assets.append(
                        {
                            "id": copied_id,
                            "sha256": original["sha256"],
                            "name": original["name"],
                            "path": copied_name,
                            "media_type": original["media_type"],
                            "size": original["size"],
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "original_file_id": original["id"],
                            "url": f"/api/v1/files/{copied_id}/content",
                        }
                    )
            snapshot = {
                "request": request,
                "profile": {**DEFAULT_PROFILE, **profile["data"], "version": profile["version"]},
                "job": job,
                "application": application,
                "knowledge": knowledge,
                "claims": claims,
                "templates": templates,
                "instructions": {
                    "general": instructions["data"].get("general", DEFAULT_GUIDANCE),
                    "version": instructions["version"],
                    "template_append": {row["id"]: row["guidance"] for row in templates},
                    "application_note": "\n\n".join(
                        part for part in [application["note"], value.note] if part
                    ),
                },
                "questions": application["questions"],
                "files": assets,
            }
            encoded = encode(snapshot)
            signature = hashlib.sha256(encoded.encode()).hexdigest()
            conn.execute(
                "INSERT INTO contexts(id,application_id,payload,signature,idempotency_key,created_at) VALUES(?,?,?,?,?,?)",
                (
                    context_id,
                    value.application_id,
                    encoded,
                    signature,
                    value.idempotency_key,
                    timestamp,
                ),
            )
            for asset in assets:
                conn.execute(
                    "INSERT INTO files(id,sha256,name,media_type,size,context_id,created_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        asset["id"],
                        asset["sha256"],
                        asset["path"],
                        asset["media_type"],
                        asset["size"],
                        context_id,
                        timestamp,
                    ),
                )
            if job["triage"] != "saved":
                conn.execute(
                    "UPDATE jobs SET triage='saved',version=version+1,updated_at=? WHERE id=?",
                    (timestamp, job["id"]),
                )
        return self.get_context(context_id)

    def _context_record(self, row):
        row = decode_record(row, ["payload"])
        row["resource_uri"] = f"openings://contexts/{row['id']}"
        return row

    def get_context(self, context_id: str) -> dict:
        """Read one immutable application context. File entries contain metadata/URLs rather than binary bytes."""
        row = self.db.one("SELECT * FROM contexts WHERE id=?", (context_id,))
        if not row:
            missing("Application context")
        return self._context_record(row)

    def list_contexts(
        self,
        application_id: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
    ) -> dict:
        """List frozen contexts without payloads. Search the associated job's title/company; summary=true includes file/document counts."""
        _page(limit, offset)
        where, params = [], []
        if application_id:
            where.append("application_id=?")
            params.append(application_id)
        if q:
            where.append(
                "EXISTS(SELECT 1 FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=contexts.application_id AND (j.title LIKE ? OR j.company LIKE ?))"
            )
            params.extend([f"%{q}%", f"%{q}%"])
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = "id,application_id,signature,created_at"
        if summary:
            columns += (
                ",(SELECT COUNT(*) FROM files WHERE context_id=contexts.id) AS file_count"
                ",(SELECT COUNT(*) FROM documents WHERE context_id=contexts.id) AS document_count"
            )
        rows = self.db.all(
            f"SELECT {columns} FROM contexts{clause} ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return {
            "items": rows,
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM contexts{clause}", params)["n"],
        }

    def _validate_content(self, content, context, kind):
        if not context:
            return
        snapshot = context["payload"]
        evidence = {row["id"] for row in snapshot["knowledge"]}
        claims = {row["id"]: row for row in snapshot["claims"]}
        templates = [row for row in snapshot["templates"] if row["kind"] == kind]
        rules = templates[0].get("rules", {}) if templates else {}

        def walk(item):
            if isinstance(item, dict):
                supplied_evidence = item.get("evidence_ids", item.get("knowledge_ids"))
                if supplied_evidence is not None:
                    if (
                        not isinstance(supplied_evidence, list)
                        or any(not isinstance(key, str) for key in supplied_evidence)
                        or not set(supplied_evidence) <= evidence
                    ):
                        raise DomainError(
                            422,
                            "unknown_evidence",
                            "Content cites evidence outside its frozen context.",
                        )
                supplied_claims = item.get("claim_ids")
                if supplied_claims is not None:
                    if (
                        not isinstance(supplied_claims, list)
                        or any(not isinstance(key, str) for key in supplied_claims)
                        or not set(supplied_claims) <= claims.keys()
                    ):
                        raise DomainError(
                            422,
                            "unapproved_claim",
                            "Content cites unapproved claims or claims outside its frozen context.",
                        )
                    if supplied_evidence is not None and any(
                        claims[key]["knowledge_id"] not in supplied_evidence
                        for key in supplied_claims
                    ):
                        raise DomainError(
                            422, "claim_evidence", "A claim does not belong to its cited evidence."
                        )
                if "bullets" in item and isinstance(item["bullets"], list):
                    bullets = item["bullets"]
                    if rules.get("max_bullets") and len(bullets) > rules["max_bullets"]:
                        raise DomainError(
                            422,
                            "bullet_limit",
                            "Content exceeds the selected template's bullet-count limit.",
                        )
                    for bullet in bullets:
                        text = (
                            bullet
                            if isinstance(bullet, str)
                            else bullet.get("text", "")
                            if isinstance(bullet, dict)
                            else ""
                        )
                        if not isinstance(text, str):
                            raise DomainError(
                                422, "bullet_text", "Structured bullet text must be a string."
                            )
                        if rules.get("max_bullet_chars") and len(text) > rules["max_bullet_chars"]:
                            raise DomainError(
                                422,
                                "bullet_limit",
                                "A bullet exceeds the selected template's character limit.",
                            )
                for child in item.values():
                    walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)

        walk(content)
        if kind == "answers":
            answers = content.get("answers", {})
            if isinstance(answers, dict):
                for question in snapshot.get("questions", []):
                    answer = answers.get(question.get("id"))
                    if answer is None:
                        continue
                    maximum = question.get("max_length", question.get("max_chars"))
                    if maximum and isinstance(answer, str) and len(answer) > maximum:
                        raise DomainError(
                            422,
                            "answer_limit",
                            f"Answer '{question.get('label', question.get('id'))}' exceeds its character limit.",
                        )
                    options = question.get("options", [])
                    allowed = [
                        option.get("value", option.get("label"))
                        if isinstance(option, dict)
                        else option
                        for option in options
                    ]
                    if allowed and answer not in allowed:
                        raise DomainError(
                            422, "answer_choice", "An answer is not one of the permitted choices."
                        )

    def create_document(self, value: DocumentCreate) -> dict:
        """Store draft structured content as a new immutable revision; previous_id links an earlier version. Never marks the application sent."""
        content = encode(value.content)
        with self.db.transaction() as conn:
            application = _get(conn, "applications", value.application_id, "Application")
            previous = (
                _get(conn, "documents", value.previous_id, "Document revision")
                if value.previous_id
                else None
            )
            if previous and (
                previous["application_id"] != value.application_id or previous["kind"] != value.kind
            ):
                raise DomainError(
                    422,
                    "revision_parent",
                    "A previous revision must belong to the same application and document kind.",
                )
            context_id = value.context_id or (previous["context_id"] if previous else None)
            context = None
            if context_id:
                context = self._context_record(
                    _get(conn, "contexts", context_id, "Application context")
                )
                if context["application_id"] != application["id"]:
                    raise DomainError(
                        422, "context_application", "The context belongs to another application."
                    )
            self._validate_content(value.content, context, value.kind)
            old = conn.execute(
                "SELECT id FROM documents WHERE application_id=? AND context_id IS ? AND kind=? AND title=? AND content=? AND previous_id IS ? ORDER BY created_at LIMIT 1",
                (
                    value.application_id,
                    context_id,
                    value.kind,
                    value.title,
                    content,
                    value.previous_id,
                ),
            ).fetchone()
            if old:
                document_id = old["id"]
            else:
                document_id = new_id()
                conn.execute(
                    "INSERT INTO documents(id,application_id,context_id,kind,title,content,previous_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        document_id,
                        value.application_id,
                        context_id,
                        value.kind,
                        value.title,
                        content,
                        value.previous_id,
                        now(),
                    ),
                )
        return self.get_document(document_id)

    def _document_records(self, rows, *, summary=False):
        if not rows:
            return []
        ids = [row["id"] for row in rows]
        placeholders = ",".join("?" for _ in ids)
        # Resolve every revision chain and file association for this page in two
        # bounded queries rather than one query per document, parent and file list.
        revisions = {
            row["id"]: row["n"]
            for row in self.db.all(
                "WITH RECURSIVE lineage(id,previous_id,n) AS ("
                f"SELECT id,previous_id,1 FROM documents WHERE id IN ({placeholders}) "
                "UNION ALL SELECT lineage.id,d.previous_id,lineage.n+1 "
                "FROM lineage JOIN documents d ON d.id=lineage.previous_id WHERE lineage.n<10000) "
                "SELECT id,MAX(n) AS n FROM lineage GROUP BY id",
                ids,
            )
        }
        files = {record_id: [] for record_id in ids}
        if summary:
            counts = {
                row["document_id"]: row["n"]
                for row in self.db.all(
                    f"SELECT document_id,COUNT(*) AS n FROM files WHERE document_id IN ({placeholders}) GROUP BY document_id",
                    ids,
                )
            }
        else:
            for row in self.db.all(
                f"SELECT * FROM files WHERE document_id IN ({placeholders}) ORDER BY created_at,name,id",
                ids,
            ):
                files[row["document_id"]].append(self._file_record(row))
        items = []
        for row in rows:
            result = dict(row) if summary else decode_record(row, ["content"])
            result.update(revision_number=revisions[result["id"]], version=1)
            if summary:
                result["file_count"] = counts.get(result["id"], 0)
            else:
                result["files"] = files[result["id"]]
            items.append(result)
        return items

    def get_document(self, document_id: str) -> dict:
        """Read a document revision, review state and attached file metadata."""
        row = self.db.one("SELECT * FROM documents WHERE id=?", (document_id,))
        if not row:
            missing("Document revision")
        return self._document_records([row])[0]

    def list_documents(
        self,
        application_id: str = "",
        kind: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
        review_state: Literal["draft", "approved"] | None = None,
    ) -> dict:
        """List revisions by application/kind/review state/title. summary=true omits structured content and file entries; retrieve a revision for exact content/files."""
        _page(limit, offset)
        where, params = [], []
        if application_id:
            where.append("application_id=?")
            params.append(application_id)
        if kind:
            where.append("kind=?")
            params.append(kind)
        if review_state is not None:
            if review_state not in {"draft", "approved"}:
                raise DomainError(422, "review_state", "Use draft or approved review state.")
            where.append("review_state=?")
            params.append(review_state)
        if q:
            where.append("title LIKE ?")
            params.append(f"%{q}%")
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = (
            "id,application_id,context_id,kind,title,previous_id,review_state,created_at"
            if summary
            else "*"
        )
        rows = self.db.all(
            f"SELECT {columns} FROM documents{clause} ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return {
            "items": self._document_records(rows, summary=summary),
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM documents{clause}", params)["n"],
        }

    def review_document(self, document_id: str, value: ReviewUpdate) -> dict:
        """Approve exact document content/files; future changes require a new revision."""
        with self.db.transaction() as conn:
            row = _get(conn, "documents", document_id, "Document revision")
            if (
                value.expected_review_state is not None
                and row["review_state"] != value.expected_review_state
            ):
                conflict("The document review state changed. Reload it before approving.")
            conn.execute("UPDATE documents SET review_state='approved' WHERE id=?", (document_id,))
        return self.get_document(document_id)

    def delete_document(self, document_id: str) -> dict:
        """Permanently remove one document revision and its attached files; other versions remain."""
        with self.db.transaction() as conn:
            _get(conn, "documents", document_id, "Document revision")
            application = conn.execute(
                "SELECT applications.job_id FROM applications JOIN documents ON documents.application_id=applications.id WHERE documents.id=?",
                (document_id,),
            ).fetchone()
            rows = conn.execute("SELECT token_hash,payload FROM transfer_grants").fetchall()
            for row in rows:
                if (
                    json.loads(row["payload"]).get("owner_type") == "document"
                    and json.loads(row["payload"]).get("owner_id") == document_id
                ):
                    conn.execute(
                        "DELETE FROM transfer_grants WHERE token_hash=?", (row["token_hash"],)
                    )
            conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
            if application:
                conn.execute(
                    "INSERT INTO events(id,job_id,kind,payload,created_at) VALUES(?,?,?,?,?)",
                    (
                        new_id(),
                        application["job_id"],
                        "document_deleted",
                        encode({"document_id": document_id}),
                        now(),
                    ),
                )
        self.db.collect_blobs()
        return {"deleted": True, "id": document_id}

    def _owner(self, conn, owner_type, owner_id, *, writable=False):
        if owner_type not in OWNER_COLUMNS:
            raise DomainError(422, "owner_type", "Unsupported file owner type.")
        row = _get(conn, OWNER_TABLES[owner_type], owner_id, "File owner")
        if writable and owner_type == "context":
            conflict("Frozen context files are immutable.")
        if writable and owner_type == "document" and row["review_state"] != "draft":
            conflict(
                "Approved documents are immutable. Create a new revision before uploading files."
            )
        if owner_type == "job":
            return row, row["id"]
        if owner_type in {"document", "context"}:
            application = _get(conn, "applications", row["application_id"], "Application")
            return row, application["job_id"]
        return row, None

    def _file_record(self, row):
        result = {
            key: row[key] for key in ["id", "sha256", "name", "media_type", "size", "created_at"]
        }
        for owner, column in OWNER_COLUMNS.items():
            if row.get(column) is not None:
                result.update(owner_type=owner, owner_id=row[column])
                break
        result["url"] = f"/api/v1/files/{row['id']}/content"
        return result

    def get_file(self, file_id: str) -> dict:
        """Read immutable file metadata and its authenticated content URL, not binary bytes."""
        row = self.db.one("SELECT * FROM files WHERE id=?", (file_id,))
        if not row:
            missing("File")
        return self._file_record(row)

    def list_files(
        self,
        owner_type: OwnerType | None = None,
        owner_id: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
        media_type: str = "",
        application_id: str = "",
    ) -> dict:
        """List file metadata by owner, name/media type or application context/revisions. Metadata is always compact, including with summary=true; fetch bytes through a scoped HTTP transfer."""
        _page(limit, offset)
        if owner_id and not owner_type:
            raise DomainError(422, "file_owner", "Provide owner_type when filtering by owner_id.")
        where, params = [], []
        if owner_type:
            if owner_type not in OWNER_COLUMNS:
                raise DomainError(422, "owner_type", "Unsupported file owner type.")
            if owner_id:
                where.append(f"{OWNER_COLUMNS[owner_type]}=?")
                params.append(owner_id)
            else:
                where.append(f"{OWNER_COLUMNS[owner_type]} IS NOT NULL")
        if q:
            where.append("name LIKE ?")
            params.append(f"%{q}%")
        if media_type:
            where.append("media_type=?")
            params.append(media_type)
        if application_id:
            where.append(
                "(document_id IN (SELECT id FROM documents WHERE application_id=?) OR context_id IN (SELECT id FROM contexts WHERE application_id=?))"
            )
            params.extend([application_id, application_id])
        clause = " WHERE " + " AND ".join(where) if where else ""
        rows = self.db.all(
            f"SELECT * FROM files{clause} ORDER BY created_at,name,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return {
            "items": [self._file_record(row) for row in rows],
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM files{clause}", params)["n"],
        }

    def _new_grant(self, conn, payload, method):
        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        conn.execute("DELETE FROM transfer_grants WHERE expires_at<?", (now(),))
        conn.execute(
            "INSERT INTO transfer_grants(token_hash,payload,method,expires_at) VALUES(?,?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), encode(payload), method, expires),
        )
        return {
            "url": "/api/v1/transfers",
            "method": method,
            "headers": {"X-Transfer-Token": token},
            "expires_at": expires,
            "max_bytes": payload.get("size"),
        }

    def reserve_upload(self, value: UploadReservation) -> dict:
        """Reserve a short-lived bounded PUT transfer for one owner/name/size. Send raw bytes using returned URL/headers; SHA-256 is optional and verified when supplied."""
        if value.size > self.max_file_bytes:
            raise DomainError(
                413, "file_size", f"Files must be at most {self.max_file_bytes} bytes."
            )
        with self.db.transaction() as conn:
            _, job_id = self._owner(conn, value.owner_type, value.owner_id, writable=True)
            payload = value.model_dump()
            payload["sha256"] = value.sha256.lower() if value.sha256 else None
            payload["job_id"] = job_id
            return self._new_grant(conn, payload, "PUT")

    def reserve_download(self, file_id: str) -> dict:
        """Obtain a short-lived GET transfer for one existing file; resolve its URL against this workspace origin."""
        with self.db.transaction() as conn:
            row = _get(conn, "files", file_id, "File")
            descriptor = self._file_record(row)
            _, job_id = self._owner(conn, descriptor["owner_type"], descriptor["owner_id"])
            return self._new_grant(
                conn, {"file_id": file_id, "job_id": job_id, "size": row["size"]}, "GET"
            )

    def _grant(self, token, method, conn=None):
        if not token:
            raise DomainError(401, "transfer_token", "A valid transfer token is required.")
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = (
            (
                dict(raw)
                if (
                    raw := conn.execute(
                        "SELECT * FROM transfer_grants WHERE token_hash=?", (token_hash,)
                    ).fetchone()
                )
                else None
            )
            if conn is not None
            else self.db.one("SELECT * FROM transfer_grants WHERE token_hash=?", (token_hash,))
        )
        if not row or row["expires_at"] <= now():
            raise DomainError(401, "transfer_token", "This transfer token is invalid or expired.")
        if row["method"] != method:
            raise DomainError(
                403, "transfer_method", "The transfer token does not permit this operation."
            )
        return row, json.loads(row["payload"])

    async def upload(self, request: Request):
        async with self._upload_slots:
            return await self._upload(request)

    async def _upload(self, request: Request):
        token = request.headers.get("X-Transfer-Token", "")
        _, scope = self._grant(token, "PUT")
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > min(scope["size"], self.max_file_bytes):
                raise DomainError(413, "file_size", "Uploaded bytes exceed the reserved size.")
            data.extend(chunk)
        if len(data) != scope["size"]:
            raise DomainError(422, "file_size", "Uploaded bytes do not match the reserved size.")
        actual_sha = hashlib.sha256(data).hexdigest()
        if scope.get("sha256") and actual_sha != scope["sha256"]:
            raise DomainError(422, "file_hash", "Uploaded bytes do not match the declared SHA-256.")
        if scope["media_type"].split(";", 1)[0] == "application/pdf" and not data.startswith(
            b"%PDF-"
        ):
            raise DomainError(422, "pdf_header", "The uploaded file is not a PDF.")
        with self.db.transaction() as conn:
            grant, current = self._grant(token, "PUT", conn)
            self._owner(conn, current["owner_type"], current["owner_id"], writable=False)
            if grant["used"]:
                file_id = current.get("file_id")
                existing = _get(conn, "files", file_id, "Completed upload") if file_id else None
                if existing and existing["sha256"] == actual_sha:
                    return self._file_record(existing)
                conflict("This upload grant was already used.")
            self._owner(conn, current["owner_type"], current["owner_id"], writable=True)
            column = OWNER_COLUMNS[current["owner_type"]]
            old = conn.execute(
                f"SELECT * FROM files WHERE {column}=? AND name=?",
                (current["owner_id"], current["name"]),
            ).fetchone()
            if old and old["sha256"] != actual_sha:
                conflict(
                    "A different file already uses this name. Create a document revision or remove the mutable asset first."
                )
            if old:
                file_id = old["id"]
            else:
                file_id = new_id()
                conn.execute(
                    "INSERT OR IGNORE INTO blobs(sha256,content,size) VALUES(?,?,?)",
                    (actual_sha, bytes(data), len(data)),
                )
                conn.execute(
                    f"INSERT INTO files(id,sha256,name,media_type,size,{column},created_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        file_id,
                        actual_sha,
                        current["name"],
                        current["media_type"],
                        len(data),
                        current["owner_id"],
                        now(),
                    ),
                )
                if current["owner_type"] in {"template", "knowledge"}:
                    conn.execute(
                        f"UPDATE {OWNER_TABLES[current['owner_type']]} SET version=version+1,updated_at=? WHERE id=?",
                        (now(), current["owner_id"]),
                    )
            current["file_id"] = file_id
            conn.execute(
                "UPDATE transfer_grants SET used=1,payload=? WHERE token_hash=?",
                (encode(current), grant["token_hash"]),
            )
            result = _get(conn, "files", file_id, "File")
        return self._file_record(result)

    def file_response(self, file_id: str, inline: bool = True):
        row = self.db.one("SELECT * FROM files WHERE id=?", (file_id,))
        if not row:
            missing("File")
        media_type = row["media_type"].split(";", 1)[0]
        disposition = (
            "inline"
            if inline and media_type in {"application/pdf", "image/png", "image/jpeg", "image/webp"}
            else "attachment"
        )
        filename = quote(PurePosixPath(row["name"]).name, safe="")

        def chunks():
            with self.db.connect() as conn:
                blob_row = conn.execute(
                    "SELECT rowid AS blob_rowid FROM blobs WHERE sha256=?", (row["sha256"],)
                ).fetchone()
                if not blob_row:
                    return
                with conn.blobopen(
                    "blobs", "content", blob_row["blob_rowid"], readonly=True
                ) as blob:
                    while chunk := blob.read(64 * 1024):
                        yield chunk

        return StreamingResponse(
            chunks(),
            media_type=media_type,
            headers={
                "Content-Length": str(row["size"]),
                "Content-Disposition": f"{disposition}; filename*=UTF-8''{filename}",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
                "Content-Security-Policy": "sandbox; default-src 'none'; frame-ancestors 'self'",
            },
        )

    def download(self, request: Request):
        _, payload = self._grant(request.headers.get("X-Transfer-Token", ""), "GET")
        return self.file_response(payload["file_id"], inline=False)

    def delete_file(self, file_id: str) -> dict:
        """Delete a live knowledge/template/job asset. Immutable context/document files require deleting the owning document instead."""
        with self.db.transaction() as conn:
            row = _get(conn, "files", file_id, "File")
            descriptor = self._file_record(row)
            if descriptor["owner_type"] in {"document", "context"}:
                conflict(
                    "Revision/context files are immutable. Delete the entire document or create a new revision."
                )
            conn.execute("DELETE FROM files WHERE id=?", (file_id,))
            if descriptor["owner_type"] in {"knowledge", "template"}:
                conn.execute(
                    f"UPDATE {OWNER_TABLES[descriptor['owner_type']]} SET version=version+1,updated_at=? WHERE id=?",
                    (now(), descriptor["owner_id"]),
                )
            for grant in conn.execute("SELECT token_hash,payload FROM transfer_grants").fetchall():
                if json.loads(grant["payload"]).get("file_id") == file_id:
                    conn.execute(
                        "DELETE FROM transfer_grants WHERE token_hash=?", (grant["token_hash"],)
                    )
        self.db.collect_blobs()
        return {"deleted": True, "id": file_id}


def register_api(router, documents: DocumentService):
    @router.get("/contexts")
    def list_contexts(
        application_id: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
    ):
        return documents.list_contexts(application_id, limit, offset, summary, q)

    @router.post("/contexts", status_code=201)
    def prepare_context(value: ContextCreate):
        return documents.prepare_context(value)

    @router.get("/contexts/{context_id}")
    def get_context(context_id: str):
        return documents.get_context(context_id)

    @router.get("/documents")
    def list_documents(
        application_id: str = "",
        kind: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
        review_state: Literal["draft", "approved"] | None = None,
    ):
        return documents.list_documents(
            application_id, kind, limit, offset, summary, q, review_state
        )

    @router.post("/documents", status_code=201)
    def create_document(value: DocumentCreate):
        return documents.create_document(value)

    @router.get("/documents/{document_id}")
    def get_document(document_id: str):
        return documents.get_document(document_id)

    @router.post("/documents/{document_id}/review")
    def review_document(document_id: str, value: ReviewUpdate):
        return documents.review_document(document_id, value)

    @router.delete("/documents/{document_id}")
    def delete_document(document_id: str):
        return documents.delete_document(document_id)

    @router.get("/files")
    def list_files(
        owner_type: OwnerType | None = None,
        owner_id: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
        media_type: str = "",
        application_id: str = "",
    ):
        return documents.list_files(
            owner_type, owner_id, limit, offset, summary, q, media_type, application_id
        )

    @router.post("/files/uploads", status_code=201)
    def reserve_upload(value: UploadReservation):
        return documents.reserve_upload(value)

    @router.get("/files/{file_id}")
    def get_file(file_id: str):
        return documents.get_file(file_id)

    @router.get("/files/{file_id}/content")
    def get_file_content(file_id: str, inline: bool = True):
        return documents.file_response(file_id, inline)

    @router.post("/files/{file_id}/download")
    def reserve_download(file_id: str):
        return documents.reserve_download(file_id)

    @router.delete("/files/{file_id}")
    def delete_file(file_id: str):
        return documents.delete_file(file_id)

    @router.put("/transfers")
    async def upload(request: Request):
        return await documents.upload(request)

    @router.get("/transfers")
    def download(request: Request):
        return documents.download(request)


def register_mcp(mcp, documents: DocumentService):
    from mcp.types import ToolAnnotations

    for name, handler in [
        ("application_prepare_context", documents.prepare_context),
        ("contexts_get", documents.get_context),
        ("contexts_list", documents.list_contexts),
        ("documents_create", documents.create_document),
        ("documents_get", documents.get_document),
        ("documents_list", documents.list_documents),
        ("documents_review", documents.review_document),
        ("documents_delete", documents.delete_document),
        ("files_list", documents.list_files),
        ("files_get", documents.get_file),
        ("files_reserve_upload", documents.reserve_upload),
        ("files_reserve_download", documents.reserve_download),
        ("files_delete", documents.delete_file),
    ]:
        read_only = name.endswith(("_get", "_list"))
        mcp.add_tool(
            handler,
            name=name,
            annotations=ToolAnnotations(
                readOnlyHint=read_only,
                destructiveHint=name.endswith("_delete"),
                idempotentHint=read_only or name in {"documents_review", "documents_create"},
                openWorldHint=False,
            ),
        )

    @mcp.resource("openings://contexts/{context_id}")
    def context_resource(context_id: str) -> str:
        """Read an immutable application context, including stored template instructions."""
        return encode(documents.get_context(context_id))
