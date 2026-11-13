"""Notes retained with a job, optionally tied to one application attempt."""

from ..actors import current_actor, pop_actor
from ..common import check_version, new_id, now
from ..errors import DomainError, missing
from ..models import NoteInput, NotePatch


class Notes:
    """Reading and writing notes."""

    @staticmethod
    def _note(row):
        if row is None:
            missing("Note")
        row = dict(row)
        row["author"] = pop_actor(row, "author")
        return row

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
                "INSERT INTO notes(id,job_id,application_id,body,created_at,updated_at,author_kind,author_id,author_name,author_token_kind) VALUES(?,?,?,?,?,?,?,?,?,?)",
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
