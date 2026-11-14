"""The shortlist starts the application: one verb for "I want this job".

Triage to ``shortlisted`` starts an application in stage Shortlisted when the job
has no open one (``from_shortlist``), in the triage's transaction; the partial
unique index ``applications_active_job`` keeps one open application per job under
concurrent calls. Undoing the shortlist (back to ``new`` or ``dismissed``) deletes
that application only while it is still empty; otherwise it is refused with
``application_has_work`` naming what exists. Closing an application never changes
its job's triage.
"""

from ..errors import DomainError


class Shortlist:
    """Starting and undoing the application of a shortlisted job."""

    def start_from_shortlist(self, conn, job_id):
        """Start a Shortlisted application unless the job has an open one."""
        if conn.execute(
            "SELECT 1 FROM applications WHERE job_id=? AND status<>'closed'", (job_id,)
        ).fetchone():
            return None
        return self.insert_application(conn, job_id, from_shortlist=True)

    @staticmethod
    def application_work(conn, application):
        """What an application holds beyond its start: names of the records it has."""
        work = []
        if not application["from_shortlist"]:
            work.append("started_separately")
        if application["status"] != "shortlisted":
            work.append("stage")
        for name, sql in (
            ("documents", "SELECT count(*) FROM documents WHERE application_id=?"),
            ("notes", "SELECT count(*) FROM notes WHERE application_id=?"),
            ("replies", "SELECT count(*) FROM replies WHERE application_id=?"),
            (
                "requirements",
                "SELECT json_array_length(requirements) FROM applications WHERE id=?",
            ),
            ("questions", "SELECT json_array_length(questions) FROM applications WHERE id=?"),
            (
                "answers",
                (
                    "SELECT count(*) FROM applications, json_each(applications.answers) "
                    "WHERE applications.id=?"
                ),
            ),
        ):
            if conn.execute(sql, (application["id"],)).fetchone()[0]:
                work.append(name)
        return work

    def leave_shortlist(self, conn, job_id):
        """Undo a shortlist: delete the open application it started while it is empty."""
        application = conn.execute(
            "SELECT * FROM applications WHERE job_id=? AND status<>'closed'", (job_id,)
        ).fetchone()
        if application is None:
            return
        work = self.application_work(conn, application)
        if work:
            raise DomainError(
                409,
                "application_has_work",
                "This job's application has work in it, so the shortlist cannot be undone. "
                "Close the application (or delete it deliberately) first.",
                {
                    "application_id": application["id"],
                    "stage": application["status"],
                    "work": work,
                },
            )
        self.remove_application(conn, application)
