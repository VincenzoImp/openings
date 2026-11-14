"""Notes on a job or on one of its applications, with their author, run and pin.

A note's scope is its job, or one application of that job when
``application_id`` is set. Each note records who wrote it and, for a token with
an open run, that run. A job and an application each have at most one pinned
note (partial unique indexes); pinning a note unpins the one pinned in its
scope, and both changes are recorded. The application's pinned note is its
standing guidance.
"""

from ..actors import current_actor, pop_actor
from ..common import check_version, new_id, now
from ..errors import DomainError, missing
from ..idempotency import fingerprint, remember, replay
from ..models import NoteInput, NotePatch, NotePin

NOTE_SELECT = "SELECT n.*,r.workflow AS run_workflow FROM notes n LEFT JOIN runs r ON r.id=n.run_id"


def note_record(row):
    """A note as returned by reads: scope, author, run and pin."""
    if row is None:
        missing("Note")
    row = dict(row)
    record = {
        "id": row["id"],
        "job_id": row["job_id"],
        "application_id": row["application_id"],
        "scope": "application" if row["application_id"] else "job",
        "body": row["body"],
        "version": row["version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "author": pop_actor(row, "author"),
        "run": {"id": row["run_id"], "workflow": row.get("run_workflow")}
        if row["run_id"]
        else None,
        "pinned": row["pinned_at"] is not None,
        "pinned_at": row["pinned_at"],
    }
    return record


class Notes:
    """Reading, writing and pinning notes."""

    def list_notes(self, job_id):
        """Every note of a job and its applications: pinned notes first, then newest first."""
        self.get_job(job_id)
        rows = self.db.all(
            NOTE_SELECT + " WHERE n.job_id=? ORDER BY n.pinned_at IS NULL,n.created_at DESC,n.id",
            (job_id,),
        )
        return {"items": [note_record(row) for row in rows], "total": len(rows)}

    def get_note(self, note_id):
        return note_record(self.db.one(NOTE_SELECT + " WHERE n.id=?", (note_id,)))

    def add_note(self, job_id, value):
        value = value if isinstance(value, NoteInput) else NoteInput.model_validate(value)
        self.get_job(job_id)
        if value.application_id and self.get_application(value.application_id)["job_id"] != job_id:
            raise DomainError(422, "note_owner", "Application belongs to a different job.")
        digest = fingerprint({**value.model_dump(mode="json"), "job_id": job_id})
        with self.db.transaction() as c:
            note_id = replay(c, "notes", value.idempotency_key, digest)
            if note_id is None:
                note_id = self.insert_note(
                    c, job_id, value.application_id, value.body, value.pinned
                )
                remember(c, "notes", value.idempotency_key, digest, note_id)
        return self.get_note(note_id)

    def insert_note(self, conn, job_id, application_id, body, pinned=False):
        """Write a note by the current actor, in its open run, and record it."""
        actor = current_actor()
        note_id, stamp = new_id(), now()
        if pinned:
            self._unpin_scope(conn, job_id, application_id, note_id)
        conn.execute(
            "INSERT INTO notes(id,job_id,application_id,body,created_at,updated_at,author_kind,"
            "author_id,author_name,author_token_kind,run_id,pinned_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                note_id,
                job_id,
                application_id,
                body,
                stamp,
                stamp,
                *actor.columns(),
                self.open_run_id(conn, actor),
                stamp if pinned else None,
            ),
        )
        self.event(
            "note_added",
            job_id,
            application_id,
            {"pinned": True} if pinned else None,
            conn,
            subject=("note", note_id),
        )
        return note_id

    def delete_note(self, note_id, expected_version):
        """Delete a note with its current version."""
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
            if row is None:
                missing("Note")
            check_version(row, expected_version)
            c.execute("DELETE FROM notes WHERE id=?", (note_id,))
            self.event(
                "note_deleted",
                row["job_id"],
                row["application_id"],
                conn=c,
                subject=("note", note_id),
            )
        return {"deleted": True}

    def update_note(self, note_id, value):
        value = value if isinstance(value, NotePatch) else NotePatch.model_validate(value)
        with self.db.transaction() as connection:
            row = connection.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
            check_version(row, value.expected_version)
            self.edit_note_body(connection, row, value.body)
        return self.get_note(note_id)

    def edit_note_body(self, conn, row, body):
        if row["body"] == body:
            return
        conn.execute(
            "UPDATE notes SET body=?,version=version+1,updated_at=? WHERE id=?",
            (body, now(), row["id"]),
        )
        self.event(
            "note_edited",
            row["job_id"],
            row["application_id"],
            {"version": row["version"] + 1},
            conn,
            subject=("note", row["id"]),
        )

    def pin_note(self, note_id, value):
        """Pin a note (unpinning the one pinned in its scope) or unpin it, with its version."""
        value = value if isinstance(value, NotePin) else NotePin.model_validate(value)
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
            check_version(row, value.expected_version)
            if value.pinned and row["pinned_at"] is None:
                self._unpin_scope(conn, row["job_id"], row["application_id"], note_id)
                self._set_pin(conn, row, now(), "note_pinned")
            elif not value.pinned and row["pinned_at"] is not None:
                self._set_pin(conn, row, None, "note_unpinned")
        return self.get_note(note_id)

    def _set_pin(self, conn, row, stamp, kind, payload=None):
        conn.execute(
            "UPDATE notes SET pinned_at=?,version=version+1,updated_at=? WHERE id=?",
            (stamp, now(), row["id"]),
        )
        self.event(
            kind,
            row["job_id"],
            row["application_id"],
            {"version": row["version"] + 1, **(payload or {})},
            conn,
            subject=("note", row["id"]),
        )

    def _unpin_scope(self, conn, job_id, application_id, replaced_by):
        """Unpin the note pinned in a scope, before another note takes the pin."""
        row = self._pinned_row(conn, job_id, application_id)
        if row is not None:
            self._set_pin(conn, row, None, "note_unpinned", {"replaced_by": replaced_by})

    @staticmethod
    def _pinned_row(conn, job_id, application_id):
        if application_id:
            return conn.execute(
                "SELECT * FROM notes WHERE application_id=? AND pinned_at IS NOT NULL",
                (application_id,),
            ).fetchone()
        return conn.execute(
            "SELECT * FROM notes WHERE job_id=? AND application_id IS NULL AND pinned_at IS NOT NULL",
            (job_id,),
        ).fetchone()

    def pinned_application_notes(self, conn, application_ids):
        """The pinned note of each application, or None."""
        result = dict.fromkeys(application_ids)
        if not application_ids:
            return result
        marks = ",".join("?" for _ in application_ids)
        for row in conn.execute(
            NOTE_SELECT + f" WHERE n.application_id IN ({marks}) AND n.pinned_at IS NOT NULL",
            list(application_ids),
        ):
            result[row["application_id"]] = note_record(row)
        return result
