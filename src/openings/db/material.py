"""Labels, notes and attachment metadata: what the user builds around a job."""

from __future__ import annotations

from typing import Any, Sequence

from openings.db.base import Store, chunks, placeholders, unique
from openings.models import (
    Attachment,
    AttachmentKind,
    EventKind,
    JobStatus,
    Note,
    NoteKind,
    utcnow,
)

_BLACKLISTED = JobStatus.BLACKLISTED.value


class MaterialMixin(Store):
    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def get_labels(self, job_id: str) -> list[str]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT label FROM job_labels WHERE job_id = ? ORDER BY label", (job_id,)
            ).fetchall()
        return [row["label"] for row in rows]

    def get_labels_for(self, job_ids: Sequence[str]) -> dict[str, list[str]]:
        ids = unique(job_ids)
        result: dict[str, list[str]] = {job_id: [] for job_id in ids}
        if not ids:
            return result
        with self._connection() as conn:
            for chunk in chunks(ids):
                rows = conn.execute(
                    "SELECT job_id, label FROM job_labels "
                    f"WHERE job_id IN ({placeholders(len(chunk))}) ORDER BY label",
                    list(chunk),
                ).fetchall()
                for row in rows:
                    result[row["job_id"]].append(row["label"])
        return result

    def add_labels(self, job_ids: Sequence[str], labels: Sequence[str]) -> int:
        clean_labels = [label.strip() for label in unique(labels)]
        ids = unique(job_ids)
        if not ids or not clean_labels:
            return 0
        added = 0
        with self._connection() as conn:
            for chunk in chunks(ids):
                existing = {
                    row["job_id"]
                    for row in conn.execute(
                        f"SELECT job_id FROM jobs WHERE job_id IN ({placeholders(len(chunk))})",
                        list(chunk),
                    ).fetchall()
                }
                for job_id in chunk:
                    if job_id not in existing:
                        continue
                    for label in clean_labels:
                        cursor = conn.execute(
                            "INSERT OR IGNORE INTO job_labels (job_id, label) VALUES (?, ?)",
                            (job_id, label),
                        )
                        if cursor.rowcount:
                            added += 1
                            self._insert_event(
                                conn,
                                job_id,
                                EventKind.LABEL,
                                f"Label added: {label}",
                                {"label": label, "action": "add"},
                            )
            conn.commit()
        return added

    def remove_labels(self, job_ids: Sequence[str], labels: Sequence[str]) -> int:
        ids = unique(job_ids)
        clean_labels = unique(labels)
        if not ids or not clean_labels:
            return 0
        removed = 0
        with self._connection() as conn:
            for job_id in ids:
                for label in clean_labels:
                    cursor = conn.execute(
                        "DELETE FROM job_labels WHERE job_id = ? AND label = ?", (job_id, label)
                    )
                    if cursor.rowcount:
                        removed += 1
                        self._insert_event(
                            conn,
                            job_id,
                            EventKind.LABEL,
                            f"Label removed: {label}",
                            {"label": label, "action": "remove"},
                        )
            conn.commit()
        return removed

    def rename_label(self, old: str, new: str) -> int:
        old, new = old.strip(), new.strip()
        if not old or not new or old == new:
            return 0
        with self._connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO job_labels (job_id, label) "
                "SELECT job_id, ? FROM job_labels WHERE label = ?",
                (new, old),
            )
            cursor = conn.execute("DELETE FROM job_labels WHERE label = ?", (old,))
            conn.commit()
        return cursor.rowcount

    def delete_label(self, label: str) -> int:
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM job_labels WHERE label = ?", (label.strip(),))
            conn.commit()
        return cursor.rowcount

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def add_note(
        self, job_id: str, kind: NoteKind, body: str, *, title: str | None = None
    ) -> Note | None:
        if not self._job_exists(job_id):
            return None
        now = utcnow()
        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO notes (job_id, kind, title, body, created_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, kind.value, title, body, now),
            )
            note_id = int(cursor.lastrowid or 0)
            label = (title or body.strip().splitlines()[0])[:80] if body.strip() else kind.value
            self._insert_event(
                conn,
                job_id,
                EventKind.NOTE,
                f"{'Q&A' if kind is NoteKind.QA else 'Note'} added: {label}",
                {"note_id": note_id, "kind": kind.value},
                now,
            )
            conn.commit()
        return Note(id=note_id, job_id=job_id, kind=kind, title=title, body=body, created_at=now)

    def update_note(
        self,
        job_id: str,
        note_id: int,
        *,
        body: str | None = None,
        title: str | None = None,
        kind: NoteKind | None = None,
    ) -> Note | None:
        assignments: list[str] = []
        params: list[Any] = []
        if body is not None:
            assignments.append("body = ?")
            params.append(body)
        if title is not None:
            assignments.append("title = ?")
            params.append(title or None)
        if kind is not None:
            assignments.append("kind = ?")
            params.append(kind.value)
        if not assignments:
            return self.get_note(job_id, note_id)
        now = utcnow()
        assignments.append("updated_at = ?")
        params.extend([now, job_id, note_id])
        with self._connection() as conn:
            cursor = conn.execute(
                f"UPDATE notes SET {', '.join(assignments)} WHERE job_id = ? AND id = ?", params
            )
            if cursor.rowcount:
                self._insert_event(
                    conn, job_id, EventKind.NOTE, "Note edited", {"note_id": note_id}, now
                )
            conn.commit()
        return self.get_note(job_id, note_id) if cursor.rowcount else None

    def get_note(self, job_id: str, note_id: int) -> Note | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE job_id = ? AND id = ?", (job_id, note_id)
            ).fetchone()
        return self.row_to_note(row) if row else None

    def list_notes(self, job_id: str) -> list[Note]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notes WHERE job_id = ? ORDER BY created_at ASC, id ASC", (job_id,)
            ).fetchall()
        return [self.row_to_note(row) for row in rows]

    def delete_note(self, job_id: str, note_id: int) -> bool:
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM notes WHERE job_id = ? AND id = ?", (job_id, note_id)
            )
            if cursor.rowcount:
                self._insert_event(
                    conn, job_id, EventKind.NOTE, "Note removed", {"note_id": note_id}
                )
            conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Attachments (metadata only; bytes live on disk)
    # ------------------------------------------------------------------

    def add_attachment(
        self,
        job_id: str,
        *,
        kind: AttachmentKind,
        filename: str,
        stored_name: str,
        sha256: str,
        size_bytes: int,
        note: str | None = None,
    ) -> Attachment | None:
        if not self._job_exists(job_id):
            return None
        now = utcnow()
        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO attachments (job_id, kind, filename, stored_name, sha256, "
                "size_bytes, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, kind.value, filename, stored_name, sha256, size_bytes, note, now),
            )
            attachment_id = int(cursor.lastrowid or 0)
            self._insert_event(
                conn,
                job_id,
                EventKind.ATTACHMENT,
                f"Attachment added ({kind.value}): {filename}",
                {"attachment_id": attachment_id, "kind": kind.value},
                now,
            )
            conn.commit()
        return Attachment(
            id=attachment_id,
            job_id=job_id,
            kind=kind,
            filename=filename,
            stored_name=stored_name,
            sha256=sha256,
            size_bytes=size_bytes,
            note=note,
            created_at=now,
        )

    def update_attachment(
        self,
        job_id: str,
        attachment_id: int,
        *,
        kind: AttachmentKind | None = None,
        note: str | None = None,
        filename: str | None = None,
    ) -> Attachment | None:
        assignments: list[str] = []
        params: list[Any] = []
        if kind is not None:
            assignments.append("kind = ?")
            params.append(kind.value)
        if note is not None:
            assignments.append("note = ?")
            params.append(note or None)
        if filename:
            assignments.append("filename = ?")
            params.append(filename)
        if not assignments:
            return self.get_attachment(job_id, attachment_id)
        params.extend([job_id, attachment_id])
        with self._connection() as conn:
            cursor = conn.execute(
                f"UPDATE attachments SET {', '.join(assignments)} WHERE job_id = ? AND id = ?",
                params,
            )
            conn.commit()
        return self.get_attachment(job_id, attachment_id) if cursor.rowcount else None

    def list_attachments(self, job_id: str) -> list[Attachment]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM attachments WHERE job_id = ? ORDER BY created_at ASC, id ASC",
                (job_id,),
            ).fetchall()
        return [self.row_to_attachment(row) for row in rows]

    def list_all_attachments(
        self,
        *,
        kind: AttachmentKind | None = None,
        statuses: Sequence[str] = (),
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[tuple[Attachment, str, str]], int]:
        """Attachments across jobs as ``(attachment, job title, company)`` plus the total."""
        where = [f"jobs.status != '{_BLACKLISTED}'"]
        params: list[Any] = []
        if kind is not None:
            where.append("attachments.kind = ?")
            params.append(kind.value)
        clean = unique(statuses)
        if clean:
            where[0] = f"jobs.status IN ({placeholders(len(clean))})"
            params.extend(status.lower() for status in clean)
        where_sql = "WHERE " + " AND ".join(where)
        with self._connection() as conn:
            total = int(
                conn.execute(
                    "SELECT COUNT(*) FROM attachments JOIN jobs ON jobs.job_id = attachments.job_id "
                    f"{where_sql}",
                    params,
                ).fetchone()[0]
            )
            rows = conn.execute(
                "SELECT attachments.*, jobs.title AS job_title, jobs.company AS job_company "
                "FROM attachments JOIN jobs ON jobs.job_id = attachments.job_id "
                f"{where_sql} ORDER BY attachments.created_at DESC, attachments.id DESC "
                "LIMIT ? OFFSET ?",
                [*params, max(1, int(limit)), max(0, int(offset))],
            ).fetchall()
        return [
            (self.row_to_attachment(row), row["job_title"], row["job_company"]) for row in rows
        ], total

    def get_attachment(self, job_id: str, attachment_id: int) -> Attachment | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM attachments WHERE job_id = ? AND id = ?", (job_id, attachment_id)
            ).fetchone()
        return self.row_to_attachment(row) if row else None

    def delete_attachment(self, job_id: str, attachment_id: int) -> Attachment | None:
        attachment = self.get_attachment(job_id, attachment_id)
        if attachment is None:
            return None
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM attachments WHERE job_id = ? AND id = ?", (job_id, attachment_id)
            )
            self._insert_event(
                conn,
                job_id,
                EventKind.ATTACHMENT,
                f"Attachment removed: {attachment.filename}",
                {"attachment_id": attachment_id},
            )
            conn.commit()
        return attachment

    def stored_names(self, job_ids: Sequence[str]) -> list[tuple[str, str]]:
        """``(job_id, stored_name)`` of every attachment of the given jobs."""
        found: list[tuple[str, str]] = []
        with self._connection() as conn:
            for chunk in chunks(unique(job_ids)):
                rows = conn.execute(
                    "SELECT job_id, stored_name FROM attachments "
                    f"WHERE job_id IN ({placeholders(len(chunk))})",
                    list(chunk),
                ).fetchall()
                found.extend((row["job_id"], row["stored_name"]) for row in rows)
        return found

    # ------------------------------------------------------------------

    def _job_exists(self, job_id: str) -> bool:
        with self._connection() as conn:
            return conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone() is not None
