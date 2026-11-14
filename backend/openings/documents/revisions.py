"""Document revisions: creation, evidence, review, comparison and deletion.

A CV or letter revision (``SOURCE_KINDS``) is its uploaded .tex source and PDF,
the evidence it cites and an optional note; its text is derived from the source
(``sources.py``). Form answers and other documents keep structured content.
Content stored on a CV or letter before 0.22 is kept read-only as
``legacy_content``.
"""

from __future__ import annotations

import difflib
import json
from typing import Literal

from .. import events
from ..career.records import _get, _page
from ..common import check_version, encode, new_id, now
from ..errors import DomainError, conflict, missing
from ..idempotency import fingerprint, remember, replay
from .models import SOURCE_KINDS, DocumentCreate, ReviewUpdate
from .sources import approval_problem
from .text import is_tex_source

# Columns of a revision summary; the full record adds content, text and evidence.
SUMMARY_COLUMNS = (
    "id,application_id,context_id,kind,title,previous_id,review_state,version,created_at"
)


def readable_lines(row) -> list[str]:
    """The lines a comparison reads: the derived text, else structured content as text."""
    if row.get("text") is not None:
        # Blank lines only separate paragraphs; they are not compared.
        return [line for line in row["text"].splitlines() if line.strip()]
    if row["kind"] in SOURCE_KINDS:
        return []
    lines = []

    def walk(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
        elif value is not None and value != "":
            text = value if isinstance(value, str) else json.dumps(value)
            lines.extend(f"{path}: {line}" if path else line for line in text.splitlines())

    walk(json.loads(row["content"] or "{}"), "")
    return lines


class RevisionOperations:
    """Creating, reading, reviewing, comparing and deleting document revisions."""

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

    @staticmethod
    def _validate_evidence(conn, context, claim_ids, knowledge_ids):
        """Cited claims and Career entries come from the frozen context, else exist now."""
        if context:
            claims = {row["id"] for row in context["payload"]["claims"]}
            entries = {row["id"] for row in context["payload"]["knowledge"]}
        else:

            def existing(table, ids, extra=""):
                if not ids:
                    return set()
                marks = ",".join("?" for _ in ids)
                return {
                    row[0]
                    for row in conn.execute(
                        f"SELECT id FROM {table} WHERE id IN ({marks}){extra}", ids
                    )
                }

            claims = existing("claims", claim_ids, " AND approved=1")
            entries = existing("knowledge", knowledge_ids)
        if not set(claim_ids) <= claims:
            raise DomainError(
                422,
                "unapproved_claim",
                "The revision cites unapproved claims or claims outside its frozen context.",
                {"claim_ids": sorted(set(claim_ids) - claims)},
            )
        if not set(knowledge_ids) <= entries:
            raise DomainError(
                422,
                "unknown_evidence",
                "The revision cites Career entries outside its frozen context.",
                {"knowledge_ids": sorted(set(knowledge_ids) - entries)},
            )

    def create_document(self, value: DocumentCreate) -> dict:
        """Create a new immutable draft revision; previous_id links the revision it replaces. A CV or letter (resume, cover_letter) takes no content: then upload its .tex source and the PDF built from it (files_reserve_upload with source_sha256). Form answers and other kinds keep structured content. Never marks the application sent."""
        source_kind = value.kind in SOURCE_KINDS
        if source_kind and value.content is not None:
            raise DomainError(
                422,
                "content_not_accepted",
                "A CV or letter revision is its .tex source and PDF: create the revision without "
                "content, then upload the source and the PDF built from it.",
            )
        content = encode({} if source_kind else value.content or {})
        claim_ids, knowledge_ids = encode(value.claim_ids), encode(value.knowledge_ids)
        digest = fingerprint(value)
        with self.db.transaction() as conn:
            document_id = replay(conn, "documents", value.idempotency_key, digest)
            if document_id is None:
                application = _get(conn, "applications", value.application_id, "Application")
                previous = (
                    _get(conn, "documents", value.previous_id, "Document revision")
                    if value.previous_id
                    else None
                )
                if previous and (
                    previous["application_id"] != value.application_id
                    or previous["kind"] != value.kind
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
                            422,
                            "context_application",
                            "The context belongs to another application.",
                        )
                if not source_kind:
                    self._validate_content(value.content or {}, context, value.kind)
                self._validate_evidence(conn, context, value.claim_ids, value.knowledge_ids)
                # A retry returns the revision it created: for a CV or letter, only while
                # that revision is still an empty draft.
                old = conn.execute(
                    "SELECT id FROM documents d WHERE application_id=? AND context_id IS ? AND kind=? "
                    "AND title=? AND content=? AND previous_id IS ? AND note=? AND claim_ids=? "
                    "AND knowledge_ids=?"
                    + (
                        " AND review_state='draft' AND NOT EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id)"
                        if source_kind
                        else ""
                    )
                    + " ORDER BY created_at LIMIT 1",
                    (
                        value.application_id,
                        context_id,
                        value.kind,
                        value.title,
                        content,
                        value.previous_id,
                        value.note,
                        claim_ids,
                        knowledge_ids,
                    ),
                ).fetchone()
                if old:
                    document_id = old["id"]
                else:
                    document_id = new_id()
                    conn.execute(
                        "INSERT INTO documents(id,application_id,context_id,kind,title,content,previous_id,"
                        "note,claim_ids,knowledge_ids,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            document_id,
                            value.application_id,
                            context_id,
                            value.kind,
                            value.title,
                            content,
                            value.previous_id,
                            value.note,
                            claim_ids,
                            knowledge_ids,
                            now(),
                        ),
                    )
                    events.record(
                        conn,
                        "document_created",
                        subject=("document", document_id),
                        payload={
                            "document_id": document_id,
                            "kind": value.kind,
                            "previous_id": value.previous_id,
                        },
                        job_id=application["job_id"],
                        application_id=value.application_id,
                    )
                    self.workspace.clear_ready(conn, value.application_id, "document_created")
                remember(conn, "documents", value.idempotency_key, digest, document_id)
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
            result = dict(row)
            result["revision_number"] = revisions[result["id"]]
            if summary:
                result["file_count"] = counts.get(result["id"], 0)
                items.append(result)
                continue
            content = result.pop("content")
            if result["kind"] not in SOURCE_KINDS:
                result["content"] = json.loads(content)
            for key in ("claim_ids", "knowledge_ids", "legacy_content"):
                if result[key] is not None:
                    result[key] = json.loads(result[key])
            result["files"] = files[result["id"]]
            sources = [
                file for file in result["files"] if is_tex_source(file["name"], file["media_type"])
            ]
            result["source_sha256"] = sources[0]["sha256"] if len(sources) == 1 else None
            items.append(result)
        return items

    def get_document(self, document_id: str) -> dict:
        """Read a revision: for a CV or letter its text derived from the .tex source, the evidence it cites, its note, review state and files (the PDF names its source_sha256); for other kinds its structured content."""
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
        """List revisions by application/kind/review state; q searches titles, notes and the text derived from sources. summary=true (default) omits text, content and file entries; summary=false includes them."""
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
            where.append("(title LIKE ? OR note LIKE ? OR text LIKE ?)")
            params.extend([f"%{q}%"] * 3)
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = SUMMARY_COLUMNS if summary else "*"
        rows = self.db.all(
            f"SELECT {columns} FROM documents{clause} ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return {
            "items": self._document_records(rows, summary=summary),
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM documents{clause}", params)["n"],
            "limit": limit,
            "offset": offset,
        }

    def compare_documents(self, document_id: str, other_id: str = "") -> dict:
        """Compare a revision's text with another revision's (by default the one it replaces), line by line. CV and letter revisions compare the text derived from their sources; form answers compare their content as text."""
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if not row:
                missing("Document revision")
            row = dict(row)
            other_id = other_id or row["previous_id"] or ""
            if not other_id:
                raise DomainError(
                    422,
                    "comparison_target",
                    "This revision replaces no earlier revision; name the revision to compare with.",
                )
            other = conn.execute("SELECT * FROM documents WHERE id=?", (other_id,)).fetchone()
            if not other:
                missing("Document revision")
            other = dict(other)
        if other["application_id"] != row["application_id"]:
            raise DomainError(
                422, "comparison_target", "Compare revisions of the same application."
            )
        before, after = readable_lines(other), readable_lines(row)
        lines, added, removed = [], 0, 0
        matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
        for tag, first, last, start, end in matcher.get_opcodes():
            if tag == "equal":
                lines.extend({"change": "same", "text": line} for line in after[start:end])
                continue
            lines.extend({"change": "removed", "text": line} for line in before[first:last])
            lines.extend({"change": "added", "text": line} for line in after[start:end])
            removed += last - first
            added += end - start
        return {
            "document_id": document_id,
            "other_id": other_id,
            "text": {
                "document": row["text"] is not None or row["kind"] not in SOURCE_KINDS,
                "other": other["text"] is not None or other["kind"] not in SOURCE_KINDS,
            },
            "added": added,
            "removed": removed,
            "lines": lines,
        }

    def review_document(self, document_id: str, value: ReviewUpdate) -> dict:
        """Approve the exact revision and its files; future changes require a new revision. A CV or letter needs its .tex source and the PDF built from it (409 source_required, pdf_required)."""
        with self.db.transaction() as conn:
            row = _get(conn, "documents", document_id, "Document revision")
            if row["version"] != value.expected_version:
                conflict(
                    "The document or its files changed. Reload it before approving.",
                    details={"current_version": row["version"]},
                )
            if row["review_state"] != "approved":
                problem = approval_problem(conn, row)
                if problem:
                    raise problem
                conn.execute(
                    "UPDATE documents SET review_state='approved',version=version+1 WHERE id=?",
                    (document_id,),
                )
                application = _get(conn, "applications", row["application_id"], "Application")
                events.record(
                    conn,
                    "document_reviewed",
                    subject=("document", document_id),
                    payload={
                        "document_id": document_id,
                        "kind": row["kind"],
                        "review_state": "approved",
                        "version": row["version"] + 1,
                    },
                    job_id=application["job_id"],
                    application_id=row["application_id"],
                )
        return self.get_document(document_id)

    def delete_document(self, document_id: str, expected_version: int) -> dict:
        """Permanently remove one document revision and its attached files, with its current expected_version; other revisions remain."""
        with self.db.transaction() as conn:
            document = _get(conn, "documents", document_id, "Document revision")
            check_version(document, expected_version)
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
                events.record(
                    conn,
                    "document_deleted",
                    subject=("document", document_id),
                    payload={"document_id": document_id, "kind": document["kind"]},
                    job_id=application["job_id"],
                    application_id=document["application_id"],
                )
                self.workspace.clear_ready(conn, document["application_id"], "document_deleted")
        self.db.collect_blobs()
        return {"deleted": True, "id": document_id}
