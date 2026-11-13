"""Document revisions: creation, evidence, comparison and deletion.

A CV or letter revision (``SOURCE_KINDS``) is its PDF and an optional TeX source,
the evidence it cites and an optional note. Creating it returns one-shot upload
grants; it is incomplete until its PDF is stored, then complete and immutable
(``sources.py``). Its readable text comes from the source, else from the PDF. Form
answers and other documents keep structured content. Content stored on a CV or
letter before 0.22 is kept read-only as ``legacy_content``.
"""

from __future__ import annotations

import difflib
import hashlib
import json

from ..career.records import _get, _page
from ..common import check_version, encode, new_id, now
from ..errors import DomainError, missing
from ..idempotency import fingerprint, remember, replay
from .models import SOURCE_KINDS, DocumentCreate, UploadReservation
from .pdf import pdf_text
from .sources import PDF, refresh_text, source_hash, store_pdf_text
from .text import is_tex_source

# Columns of a revision summary; the full record adds content, text and evidence.
SUMMARY_COLUMNS = "id,application_id,context_id,kind,title,previous_id,text_from,version,created_at"
TEX = "application/x-tex"


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
        """Create a new revision; previous_id links the revision it replaces. A CV or letter (cv, letter) takes no content: give pdf (name, size, optional sha256) and, optionally, its TeX source inline (source) or as a file (source_file). The result's uploads holds one-shot grants (pdf, and source for source_file): PUT the exact bytes to each url with its headers, the source first. The revision is incomplete until its PDF is stored, then complete and immutable; Ready counts only complete revisions. Text comes from the source, else from the PDF. Form answers and other kinds keep structured content. Never marks the application sent."""
        source_kind = value.kind in SOURCE_KINDS
        if source_kind and value.content is not None:
            raise DomainError(
                422,
                "content_not_accepted",
                "A CV or letter revision is its PDF and optional TeX source: create the revision "
                "without content and upload the files with the grants it returns.",
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
                # that revision has no file yet.
                old = conn.execute(
                    "SELECT id FROM documents d WHERE application_id=? AND context_id IS ? AND kind=? "
                    "AND title=? AND content=? AND previous_id IS ? AND note=? AND claim_ids=? "
                    "AND knowledge_ids=?"
                    + (
                        " AND NOT EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id)"
                        if source_kind and value.source is None
                        else " AND 0"
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
                    if value.source is not None:
                        self._store_inline_source(conn, document_id, value.kind, value.source)
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
                remember(conn, "documents", value.idempotency_key, digest, document_id)
            uploads = self._create_grants(conn, document_id, value) if source_kind else None
        result = self.get_document(document_id)
        if uploads is not None:
            result["uploads"] = uploads
        return result

    @staticmethod
    def _store_inline_source(conn, document_id, kind, source):
        """Store an inline TeX source as the revision's source file and derive its text."""
        data = source.encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        conn.execute(
            "INSERT OR IGNORE INTO blobs(sha256,content,size) VALUES(?,?,?)",
            (digest, data, len(data)),
        )
        conn.execute(
            "INSERT INTO files(id,sha256,name,media_type,size,document_id,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (new_id(), digest, f"{kind}.tex", TEX, len(data), document_id, now()),
        )
        refresh_text(conn, document_id)

    def _create_grants(self, conn, document_id, value):
        """One-shot grants for the files the create declared and the revision still lacks."""
        document = _get(conn, "documents", document_id, "Document revision")
        names = {
            row[0]
            for row in conn.execute("SELECT name FROM files WHERE document_id=?", (document_id,))
        }
        uploads = {"pdf": None, "source": None}
        if any(name.lower().endswith(".pdf") for name in names):
            return uploads
        if value.source_file is not None and value.source_file.name not in names:
            uploads["source"] = self.upload_grant(
                conn,
                UploadReservation(
                    owner_type="document",
                    owner_id=document_id,
                    media_type=TEX,
                    **value.source_file.model_dump(),
                ),
            )
        if value.pdf is not None:
            source = source_hash(conn, document_id) or (
                value.source_file.sha256 if value.source_file else None
            )
            uploads["pdf"] = self.upload_grant(
                conn,
                UploadReservation(
                    owner_type="document",
                    owner_id=document["id"],
                    media_type=PDF,
                    source_sha256=source,
                    **value.pdf.model_dump(),
                ),
            )
        return uploads

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
        complete = {
            row["document_id"]
            for row in self.db.all(
                f"SELECT DISTINCT document_id FROM files WHERE document_id IN ({placeholders}) "
                "AND media_type=?",
                (*ids, PDF),
            )
        }
        items = []
        for row in rows:
            result = dict(row)
            result["revision_number"] = revisions[result["id"]]
            # A CV or letter is complete once its PDF is stored; other kinds always are.
            result["complete"] = result["kind"] not in SOURCE_KINDS or result["id"] in complete
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
        """Read a revision: for a CV or letter whether it is complete (its PDF stored), its readable text and where it came from (text_from: tex or pdf), the evidence it cites, its note and files (a PDF built from a source names its source_sha256); for other kinds its structured content."""
        row = self.db.one("SELECT * FROM documents WHERE id=?", (document_id,))
        if not row:
            missing("Document revision")
        if self._read_pdf_text(row):
            row = self.db.one("SELECT * FROM documents WHERE id=?", (document_id,))
        return self._document_records([row])[0]

    def _read_pdf_text(self, row) -> bool:
        """Read the text of a PDF-only revision stored without one (first read after an upgrade).

        A PDF without readable text is tried once per process. Returns whether text was stored.
        """
        if row["kind"] not in SOURCE_KINDS or row["text"] is not None:
            return False
        if row["id"] in self._unreadable:
            return False
        with self.db.connect() as conn:
            if source_hash(conn, row["id"]) is not None:
                return False
            blob = conn.execute(
                "SELECT b.content FROM files f JOIN blobs b ON b.sha256=f.sha256 "
                "WHERE f.document_id=? AND f.media_type=? ORDER BY f.created_at LIMIT 1",
                (row["id"], PDF),
            ).fetchone()
        if blob is None:
            return False
        text = pdf_text(bytes(blob[0]))
        if text is None:
            self._unreadable.add(row["id"])
            return False
        with self.db.transaction() as conn:
            store_pdf_text(conn, row["id"], text)
        return True

    def list_documents(
        self,
        application_id: str = "",
        kind: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = True,
        q: str = "",
    ) -> dict:
        """List revisions by application and kind (cv, letter, answers, other), each with complete (a CV or letter whose PDF is stored); q searches titles, notes and readable text. summary=true (default) omits text, content and file entries; summary=false includes them."""
        _page(limit, offset)
        where, params = [], []
        if application_id:
            where.append("application_id=?")
            params.append(application_id)
        if kind:
            where.append("kind=?")
            params.append(kind)
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
        """Compare a revision's text with another revision's (by default the one it replaces), line by line. CV and letter revisions compare their readable text (from the source, else the PDF); form answers compare their content as text."""
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
                self.workspace.event(
                    "document_deleted",
                    application["job_id"],
                    document["application_id"],
                    {"document_id": document_id, "kind": document["kind"]},
                    conn,
                    subject=("document", document_id),
                )
        self.db.collect_blobs()
        return {"deleted": True, "id": document_id}
