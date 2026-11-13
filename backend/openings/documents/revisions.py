"""Document revisions: validated content, review, consistency and deletion."""

from __future__ import annotations

import json
from typing import Literal

from ..career import _get, _page
from ..common import decode_record, encode, new_id, now
from ..consistency import compare as compare_content, is_tex_source
from ..errors import DomainError, conflict, missing
from .models import DocumentCreate, ReviewUpdate


class RevisionOperations:
    """Creating, reading, reviewing and deleting document revisions."""

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
                if supplied_evidence is not None and (
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
                context = self.context_record(
                    conn, _get(conn, "contexts", context_id, "Application context")
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
                self.workspace.event(
                    "document_created",
                    application["job_id"],
                    value.application_id,
                    {
                        "document_id": document_id,
                        "kind": value.kind,
                        "previous_id": value.previous_id,
                    },
                    conn,
                    subject=("document", document_id),
                )
                self.workspace.clear_ready(conn, value.application_id, "document_created")
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
            result.update(revision_number=revisions[result["id"]])
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
        summary: bool = True,
        q: str = "",
        review_state: Literal["draft", "approved"] | None = None,
    ) -> dict:
        """List revisions by application/kind/review state/title. summary=true (default) omits structured content and file entries; summary=false includes them; retrieve a revision for exact content/files."""
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
            "id,application_id,context_id,kind,title,previous_id,review_state,version,created_at"
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

    @staticmethod
    def _consistency(conn, row) -> dict:
        sources, names = [], []
        for file in conn.execute(
            "SELECT id,name,media_type,sha256 FROM files WHERE document_id=? ORDER BY name,id",
            (row["id"],),
        ).fetchall():
            if not is_tex_source(file["name"], file["media_type"]):
                continue
            blob = conn.execute(
                "SELECT content FROM blobs WHERE sha256=?", (file["sha256"],)
            ).fetchone()
            text = bytes(blob["content"]).decode("utf-8", "replace") if blob else ""
            sources.append((file["name"], text))
            names.append({"id": file["id"], "name": file["name"]})
        report = compare_content(json.loads(row["content"]), sources)
        return {"document_id": row["id"], "version": row["version"], "sources": names, **report}

    def check_consistency(self, document_id: str) -> dict:
        """Compare a revision's structured content text with its attached .tex source, ignoring case, whitespace, punctuation and LaTeX markup. Read-only; documents_review applies the same check."""
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if not row:
                missing("Document revision")
            return self._consistency(conn, dict(row))

    def review_document(self, document_id: str, value: ReviewUpdate) -> dict:
        """Approve exact document content/files; future changes require a new revision. Refuses with 409 content_mismatch when the attached .tex source disagrees with the structured content, unless allow_content_mismatch=true."""
        with self.db.transaction() as conn:
            row = _get(conn, "documents", document_id, "Document revision")
            if row["version"] != value.expected_version:
                conflict(
                    "The document or its files changed. Reload it before approving.",
                    details={"current_version": row["version"]},
                )
            if row["review_state"] != "approved" and not value.allow_content_mismatch:
                report = self._consistency(conn, row)
                if report["status"] == "mismatch":
                    first = report["mismatches"][0]
                    raise DomainError(
                        409,
                        "content_mismatch",
                        f"{report['reason']} First difference at {first['path']}: "
                        f'"{first["text"][:120]}". Save the matching content as a new revision '
                        "or upload the matching source; set allow_content_mismatch only for an "
                        "intentional difference.",
                        report,
                    )
            if row["review_state"] != "approved":
                conn.execute(
                    "UPDATE documents SET review_state='approved',version=version+1 WHERE id=?",
                    (document_id,),
                )
                application = _get(conn, "applications", row["application_id"], "Application")
                self.workspace.event(
                    "document_reviewed",
                    application["job_id"],
                    row["application_id"],
                    {
                        "document_id": document_id,
                        "kind": row["kind"],
                        "review_state": "approved",
                        "version": row["version"] + 1,
                    },
                    conn,
                    subject=("document", document_id),
                )
        return self.get_document(document_id)

    def delete_document(self, document_id: str) -> dict:
        """Permanently remove one document revision and its attached files; other versions remain."""
        with self.db.transaction() as conn:
            document = _get(conn, "documents", document_id, "Document revision")
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
                self.workspace.event(
                    "document_deleted",
                    application["job_id"],
                    document["application_id"],
                    {"document_id": document_id, "kind": document["kind"]},
                    conn,
                    subject=("document", document_id),
                )
                self.workspace.clear_ready(conn, document["application_id"], "document_deleted")
        self.db.collect_blobs()
        return {"deleted": True, "id": document_id}
