"""Application changes: one open attempt per job, stages, responses, Ready and deletion."""

import json
import math

from ..actors import current_actor
from ..common import check_version, new_id, now
from ..db import encode
from ..errors import DomainError, conflict, missing
from ..idempotency import fingerprint, remember, replay
from ..models import ApplicationInput, ApplicationPatch, ApplicationReady
from ..outcomes import not_sent, record_response, today
from ..snapshots import collect_unused
from .applications import NOT_READY, READINESS_SQL, REQUIREMENT_COUNTS_SQL


class ApplicationChanges:
    """Creating, progressing, marking ready and deleting applications."""

    def delete_application(self, application_id, expected_version, collect=True):
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM applications WHERE id=?", (application_id,)
            ).fetchone()
            check_version(row, expected_version)
            owned = "SELECT id FROM documents WHERE application_id=? UNION SELECT id FROM contexts WHERE application_id=?"
            owned_files = "SELECT id FROM all_files WHERE document_id IN (SELECT id FROM documents WHERE application_id=?) OR context_id IN (SELECT id FROM contexts WHERE application_id=?)"
            connection.execute(
                "DELETE FROM transfer_grants WHERE json_extract(payload,'$.owner_id') IN ("
                + owned
                + ") OR json_extract(payload,'$.file_id') IN ("
                + owned_files
                + ")",
                (application_id,) * 4,
            )
            connection.execute("DELETE FROM applications WHERE id=?", (application_id,))
            if collect:
                collect_unused(connection)
            self.event(
                "application_deleted",
                row["job_id"],
                payload={"application_id": application_id},
                conn=connection,
                subject=("application", application_id),
            )
        return {"deleted": True, "id": application_id}

    def create_application(self, value):
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
                conflict("Restore the dismissed job before preparing an application.")
            self._check_active_application(c, value.job_id)
            self.validate_answers([q.model_dump() for q in value.questions], {})
            record_id, stamp = new_id(), now()
            c.execute(
                "INSERT INTO applications(id,job_id,questions,priority,deadline,requirements,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    record_id,
                    value.job_id,
                    encode([q.model_dump() for q in value.questions]),
                    value.priority,
                    value.deadline,
                    encode(
                        self.normalize_requirements([r.model_dump() for r in value.requirements])
                    ),
                    stamp,
                    stamp,
                ),
            )
            remember(c, "applications", value.idempotency_key, digest, record_id)
            c.execute(
                "UPDATE jobs SET triage='saved',version=version+1,updated_at=? WHERE id=?",
                (stamp, value.job_id),
            )
            self.event("application_created", value.job_id, record_id, {"status": "draft"}, c)
        return self.get_application(record_id)

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
        changes = value.model_dump(
            exclude_unset=True, exclude={"expected_version", "response_date", "response_note"}
        )
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
            check_version(row, value.expected_version)
            status = changes.get("status") or row["status"]
            if row["status"] == "closed" and status != "closed":
                self._check_active_application(c, row["job_id"], excluding=application_id)
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
            if (
                (
                    status in {"applied", "interview", "offer"}
                    or (status == "closed" and changes["outcome"] == "accepted")
                )
                and not row["applied_at"]
                and "applied_at" not in changes
            ):
                changes["applied_at"] = now()
            sent = changes.get("applied_at", row["applied_at"])
            if changes["outcome"] == "no_response" and not sent:
                raise DomainError(
                    409,
                    "application_not_sent",
                    "Only an application recorded as sent can be closed as no reply.",
                )
            answered = self._stage_responses(c, row, status, changes["outcome"])
            given = value.response_date is not None or value.response_note is not None
            if given and not answered:
                raise DomainError(
                    422,
                    "application_response",
                    "response_date and response_note apply only to a change that records an "
                    "employer response: moving to Interview or Offer, or closing as rejected or "
                    "accepted.",
                )
            if answered and not sent:
                # A Draft closed as rejected was never sent: no employer answered it.
                if given:
                    raise not_sent()
                answered = []
            actual = {}
            for key, val in changes.items():
                if key == "status" and val is None:
                    continue
                structured = key in {"questions", "answers", "requirements"}
                previous = json.loads(row[key]) if structured else row[key]
                if previous != val:
                    actual[key] = encode(val) if structured else val
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
                # Ready is a judgement on a Preparing attempt without blocking requirements.
                if status != "draft":
                    self.clear_ready(c, application_id, "left_preparing")
                elif "requirements" in actual and any(
                    item["blocking"] and not item["resolved"] for item in changes["requirements"]
                ):
                    self.clear_ready(c, application_id, "blocking_requirement")
            for kind in answered:
                record_response(
                    self,
                    c,
                    row,
                    kind,
                    value.response_date or today(),
                    value.response_note or "",
                )
        return self.get_application(application_id, compact_job=True)

    @staticmethod
    def _stage_responses(conn, row, status, outcome):
        """The employer responses a stage change records.

        Reaching Interview from Preparing or Applied is an interview invitation;
        reaching Offer from an earlier stage is an offer; closing as rejected is a
        rejection; closing as accepted is an offer unless one is on record.
        """
        before, previous = row["status"], row["outcome"]
        kinds = []
        if status == "interview" and before in {"draft", "applied"}:
            kinds.append("interview")
        if status == "offer" and before in {"draft", "applied", "interview"}:
            kinds.append("offer")
        if status == "closed" and (before, previous) != ("closed", outcome):
            if outcome == "rejected":
                kinds.append("rejection")
            elif (
                outcome == "accepted"
                and not conn.execute(
                    "SELECT 1 FROM responses WHERE application_id=? AND kind='offer'", (row["id"],)
                ).fetchone()
            ):
                kinds.append("offer")
        return kinds

    def set_ready(self, application_id, value):
        """Mark a Preparing application ready to apply, or clear the mark.

        Marking is refused while a derived readiness check fails; the error names it.
        """
        value = (
            value if isinstance(value, ApplicationReady) else ApplicationReady.model_validate(value)
        )
        with self.db.transaction() as c:
            row = c.execute(
                f"SELECT app.*,{READINESS_SQL} AS readiness,{REQUIREMENT_COUNTS_SQL} FROM applications app WHERE app.id=?",
                (application_id,),
            ).fetchone()
            if row is None:
                missing("Application")
            check_version(row, value.expected_version)
            if not value.ready:
                self.clear_ready(c, application_id, "unmarked")
            elif row["ready_at"] is None:
                details = {
                    "readiness": row["readiness"],
                    "status": row["status"],
                    "blocking_requirements": row["blocking_requirements"],
                    "current_version": row["version"],
                }
                if row["status"] != "draft":
                    raise DomainError(
                        409,
                        "application_not_ready",
                        "Only a Preparing application can be marked ready.",
                        {"check": "stage", **details},
                    )
                if row["readiness"] in NOT_READY:
                    raise DomainError(
                        409,
                        "application_not_ready",
                        NOT_READY[row["readiness"]],
                        {"check": row["readiness"], **details},
                    )
                stamp = now()
                c.execute(
                    "UPDATE applications SET ready_at=?,ready_by_kind=?,ready_by_id=?,ready_by_name=?,ready_by_token_kind=?,version=version+1,updated_at=? WHERE id=?",
                    (stamp, *current_actor().columns(), stamp, application_id),
                )
                self.event("application_marked_ready", row["job_id"], application_id, conn=c)
        return self.get_application(application_id, compact_job=True)

    def clear_ready(self, conn, application_id, reason):
        """Clear the stored Ready step once its judgement no longer holds, recording why.

        Every shared service that changes what Ready was judged on calls this in its
        own transaction. Returns whether the application was ready.
        """
        row = conn.execute(
            "SELECT job_id FROM applications WHERE id=? AND ready_at IS NOT NULL", (application_id,)
        ).fetchone()
        if row is None:
            return False
        conn.execute(
            "UPDATE applications SET ready_at=NULL,ready_by_kind=NULL,ready_by_id=NULL,ready_by_name=NULL,ready_by_token_kind=NULL,version=version+1,updated_at=? WHERE id=?",
            (now(), application_id),
        )
        self.event(
            "application_ready_cleared",
            row["job_id"],
            application_id,
            {"reason": reason, "automatic": reason != "unmarked"},
            conn,
        )
        return True

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
