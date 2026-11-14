"""Application changes: one open attempt per job, stages, Mark applied and its undo, deletion."""

import json
import math

from .. import events
from ..actors import current_actor
from ..common import check_version, new_id, now
from ..db import collect_unused, encode
from ..errors import DomainError, conflict, missing
from ..idempotency import fingerprint, remember, replay
from ..models import ApplicationInput, ApplicationPatch
from ..outcomes import today
from .readiness import canonical_documents

# Columns stored as JSON text.
STRUCTURED = {"questions", "answers", "requirements", "required_documents"}


class ApplicationChanges:
    """Creating, progressing and deleting applications."""

    def delete_application(self, application_id, expected_version, collect=True):
        """Delete an application; a shortlisted job left without any returns to New."""
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM applications WHERE id=?", (application_id,)
            ).fetchone()
            check_version(row, expected_version)
            self.remove_application(connection, row, collect=collect)
            job = connection.execute(
                "SELECT * FROM jobs WHERE id=? AND triage='shortlisted' AND NOT EXISTS("
                "SELECT 1 FROM applications WHERE job_id=jobs.id)",
                (row["job_id"],),
            ).fetchone()
            if job is not None:
                self._triage(connection, job, "new", current_actor())
        return {"deleted": True, "id": application_id}

    def remove_application(self, connection, row, collect=True):
        """Delete one application row with its owned records and grants, recording it."""
        application_id = row["id"]
        owned = "SELECT id FROM documents WHERE application_id=?"
        owned_files = "SELECT id FROM files WHERE document_id IN (SELECT id FROM documents WHERE application_id=?)"
        connection.execute(
            "DELETE FROM transfer_grants WHERE json_extract(payload,'$.owner_id') IN ("
            + owned
            + ") OR json_extract(payload,'$.file_id') IN ("
            + owned_files
            + ")",
            (application_id,) * 2,
        )
        connection.execute("DELETE FROM applications WHERE id=?", (application_id,))
        if collect:
            collect_unused(connection)
        events.record(
            connection,
            "application_deleted",
            subject=("application", application_id),
            payload={"application_id": application_id},
            job_id=row["job_id"],
        )

    def create_application(self, value):
        """Start an application in stage Shortlisted; its job becomes shortlisted."""
        value = (
            value if isinstance(value, ApplicationInput) else ApplicationInput.model_validate(value)
        )
        digest = fingerprint(value)
        with self.db.transaction() as c:
            replayed = replay(c, "applications", value.idempotency_key, digest)
            if replayed:
                return self.get_application(replayed)
            job = c.execute("SELECT * FROM jobs WHERE id=?", (value.job_id,)).fetchone()
            if not job:
                missing("Job")
            if job["triage"] == "dismissed":
                conflict("Restore the dismissed job before starting an application.")
            self._check_active_application(c, value.job_id)
            self.validate_answers([q.model_dump() for q in value.questions], {})
            record_id = self.insert_application(
                c,
                value.job_id,
                questions=[q.model_dump() for q in value.questions],
                priority=value.priority,
                deadline=value.deadline,
                requirements=self.normalize_requirements(
                    [r.model_dump() for r in value.requirements]
                ),
                required_documents=value.required_documents,
            )
            remember(c, "applications", value.idempotency_key, digest, record_id)
            if job["triage"] != "shortlisted":
                self._triage(c, job, "shortlisted", current_actor())
        return self.get_application(record_id)

    def insert_application(
        self,
        conn,
        job_id,
        *,
        questions=(),
        priority=None,
        deadline=None,
        requirements=(),
        required_documents=("cv", "letter"),
        from_shortlist=False,
    ):
        """Insert a Shortlisted application with its creation event; returns its id."""
        record_id, stamp = new_id(), now()
        conn.execute(
            "INSERT INTO applications(id,job_id,questions,priority,deadline,requirements,"
            "required_documents,from_shortlist,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                record_id,
                job_id,
                encode(list(questions)),
                priority,
                deadline,
                encode(list(requirements)),
                encode(canonical_documents(required_documents)),
                int(from_shortlist),
                stamp,
                stamp,
            ),
        )
        payload = {"status": "shortlisted"}
        if from_shortlist:
            payload["by"] = "shortlist"
        events.record(
            conn, "application_created", payload=payload, job_id=job_id, application_id=record_id
        )
        return record_id

    @staticmethod
    def _check_active_application(connection, job_id, excluding=None):
        active = connection.execute(
            "SELECT id,status FROM applications WHERE job_id=? AND status<>'closed' AND (? IS NULL OR id<>?) LIMIT 1",
            (job_id, excluding, excluding),
        ).fetchone()
        if active:
            raise DomainError(
                409,
                "application_in_progress",
                f"This job already has an active application ({active['id']}). Continue it or close it before starting another.",
                {"application_id": active["id"], "status": active["status"]},
            )

    def update_application(self, application_id, value):
        value = (
            value if isinstance(value, ApplicationPatch) else ApplicationPatch.model_validate(value)
        )
        changes = value.model_dump(exclude_unset=True, exclude={"expected_version", "reply"})
        reply = value.reply
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
            check_version(row, value.expected_version)
            moved = self.reply_stage(c, row, reply, changes)
            status = changes.get("status") or row["status"]
            if row["status"] == "closed" and status != "closed":
                self._check_active_application(c, row["job_id"], excluding=application_id)
            self._check_outcome(row, status, changes)
            if status == "shortlisted" and row["status"] != "shortlisted":
                self._undo_applied(c, row, changes)
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
            if "requirements" in changes:
                # Store every requirement field, including defaults the caller omitted.
                changes["requirements"] = self.normalize_requirements(
                    [item.model_dump() for item in value.requirements]
                )
            if "required_documents" in changes:
                changes["required_documents"] = canonical_documents(changes["required_documents"])
            if (
                (
                    status in {"applied", "interview", "offer"}
                    or (status == "closed" and changes["outcome"] == "accepted")
                )
                and status != row["status"]
                and not row["applied_at"]
                and "applied_at" not in changes
            ):
                # Mark applied: the time defaults to now and stays editable.
                changes["applied_at"] = now()
            sent = changes.get("applied_at", row["applied_at"])
            if changes["outcome"] == "no_response" and not sent:
                raise DomainError(
                    409,
                    "application_not_sent",
                    "Only an application recorded as sent can be closed as no reply.",
                )
            actual = {}
            for key, val in changes.items():
                if key == "status" and val is None:
                    continue
                structured = key in STRUCTURED
                previous = json.loads(row[key]) if structured else row[key]
                if previous != val:
                    actual[key] = encode(val) if structured else val
            reply_changed = reply is not None
            if actual or reply_changed:
                c.execute(
                    "UPDATE applications SET "
                    + "".join(k + "=?," for k in actual)
                    + "version=version+1,updated_at=? WHERE id=?",
                    (*actual.values(), now(), application_id),
                )
            # A reply that moves the stage is one change: its own event names the stage.
            fields = [key for key in actual if not (moved and key in moved)]
            if fields:
                events.record(
                    c,
                    "application_updated",
                    payload={"from": row["status"], "to": status, "fields": fields},
                    job_id=row["job_id"],
                    application_id=application_id,
                )
            if reply_changed:
                self.write_reply(c, row, reply, moved and {"from": row["status"], "to": status})
        return self.get_application(application_id, compact_job=True)

    @staticmethod
    def _check_outcome(row, status, changes):
        """An outcome belongs to a Closed application; no_response has its concluded day."""
        if status == "closed":
            outcome = changes.get("outcome", row["outcome"])
            if not outcome:
                raise DomainError(
                    422, "application_outcome", "Choose an outcome when closing an application."
                )
            changes["outcome"] = outcome
        else:
            if changes.get("outcome"):
                raise DomainError(
                    422, "application_outcome", "Close the application to record an outcome."
                )
            changes["outcome"] = None
        # The day "no reply" was concluded belongs to that outcome only.
        if changes["outcome"] == "no_response":
            changes["concluded_on"] = (
                changes.get("concluded_on")
                or (row["concluded_on"] if row["outcome"] == "no_response" else None)
                or today()
            )
        elif changes.get("concluded_on"):
            raise DomainError(
                422,
                "application_concluded_on",
                "concluded_on applies only to an application closed as no_response.",
            )
        else:
            changes["concluded_on"] = None

    @staticmethod
    def _undo_applied(conn, row, changes):
        """Back to Shortlisted (the undo of Mark applied): only without a reply."""
        replies = conn.execute(
            "SELECT count(*) FROM replies WHERE application_id=?", (row["id"],)
        ).fetchone()[0]
        if replies:
            raise DomainError(
                409,
                "application_has_replies",
                "This application has employer replies, so it cannot go back to Shortlisted. "
                "Remove a reply recorded by mistake first.",
                {"replies": replies},
            )
        if changes.get("applied_at"):
            raise DomainError(
                422,
                "application_applied_at",
                "A Shortlisted application has not been sent: omit applied_at.",
            )
        changes["applied_at"] = None

    @staticmethod
    def normalize_requirements(requirements):
        """Give each requirement a stable identifier and reject duplicate identifiers."""
        seen = set()
        for requirement in requirements:
            requirement["id"] = requirement.get("id") or new_id()[:12]
            if requirement["id"] in seen:
                raise DomainError(422, "requirement_id", "Requirement IDs must be unique.")
            seen.add(requirement["id"])
        return requirements

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
