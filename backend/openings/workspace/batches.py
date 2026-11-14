"""Batch reads and writes of jobs and applications, as an agent works: many records per call.

Reads take up to 20 ids and report the ids they did not find. Writes take items
that each succeed or fail on their own (``common.run_items``) and need no version:
triage, stage and replies are reversible and guarded by the same rules as one
change (one non-Closed application per job, a reply sets the stage, no
Shortlisted after a reply). A write's result per item is small: the record's id,
version and the fields the server derived.
"""

from ..common import run_items
from ..errors import DomainError
from ..models import (
    ApplicationFields,
    ApplicationIds,
    ApplicationsCreate,
    ApplicationsUpdate,
    JobIds,
    JobTriage,
    LinkInput,
    ReplyChange,
)


def _found(read, ids):
    """``read(id)`` for each distinct id; ids that do not exist are listed apart."""
    items, unknown = [], []
    for identifier in dict.fromkeys(ids):
        try:
            items.append(read(identifier))
        except DomainError as error:
            if error.status != 404:
                raise
            unknown.append(identifier)
    return {"items": items, "missing": unknown}


def _application_echo(application, **extra):
    keys = ("id", "version", "job_id", "status", "outcome", "ready", "missing")
    return {key: application.get(key) for key in keys} | extra


class BatchOperations:
    """jobs_get, jobs_triage, jobs_link, applications_get/create/update."""

    def read_jobs(self, value: JobIds):
        def read(job_id):
            job = self.get_job(job_id)
            job["notes"] = self.list_notes(job_id)["items"]
            return job

        return _found(read, value.ids)

    def triage_jobs(self, value: JobTriage):
        def apply(item):
            reason = (item.reason or "").strip() or None
            if item.to == "dismissed" and not reason:
                raise DomainError(
                    422, "triage_reason", "Give every dismissal a reason the owner will read."
                )
            if reason and item.to != "dismissed":
                raise DomainError(422, "triage_reason", "A reason goes with dismissed only.")
            job = self.set_triage(item.job_id, item.to, None, reason)
            application = job.get("application") or {}
            return {
                "version": job["version"],
                "triage": job["triage"],
                "application_id": application.get("id") if item.to == "shortlisted" else None,
            }

        return run_items(self.db, value.items, lambda item: item.job_id, apply)

    def link_jobs(self, job_id, value: LinkInput):
        """Decide a likely duplicate: merge job_id into other_id, or mark them different."""
        if value.decision == "different":
            self.mark_distinct(job_id, value.other_id)
            return self.job_summary(job_id)
        if value.expected_version is None:
            raise DomainError(
                422,
                "validation",
                "Some fields need attention.",
                [
                    {
                        "field": ["expected_version"],
                        "message": "Merging needs job_id's version.",
                        "type": "missing",
                    }
                ],
            )
        self.merge_jobs(job_id, value.other_id, value.expected_version, value.other_version)
        return self.job_summary(value.other_id)

    def read_applications(self, value: ApplicationIds):
        def read(application_id):
            application = self.get_application(application_id, compact_job=True)
            documents = self.documents.list_documents(application_id=application_id, limit=200)
            application["documents"] = documents["items"]
            notes = self.list_notes(application["job_id"])["items"]
            application["notes"] = [
                note for note in notes if note["application_id"] == application_id
            ]
            return application

        return _found(read, value.ids)

    def create_applications(self, value: ApplicationsCreate):
        """Start an application per job; a job's open application is returned, not doubled.

        Shortlisting a job already started its application: then the item's
        required_documents, priority, deadline, questions and requirements are set on
        it while it is Shortlisted (``created`` false).
        """
        fields = {"required_documents", "priority", "deadline", "questions", "requirements"}

        def apply(item):
            try:
                return _application_echo(self.create_application(item), created=True)
            except DomainError as error:
                if error.code != "application_in_progress":
                    raise
                existing, status = error.details["application_id"], error.details["status"]
            given = item.model_dump(exclude_unset=True, include=fields)
            if given and status == "shortlisted":
                application = self.update_application(existing, ApplicationFields(**given))
            else:
                application = self.get_application(existing, compact_job=True)
            return _application_echo(application, created=False)

        return run_items(self.db, value.items, lambda item: None, apply)

    def update_applications(self, value: ApplicationsUpdate):
        def apply(item):
            if item.reply is not None and item.reply_fix is not None:
                raise DomainError(
                    422, "reply", "Record a new reply or correct one, not both in one item."
                )
            changes = item.model_dump(
                exclude_unset=True,
                exclude={"application_id", "stage", "applied_on", "reply", "reply_fix"},
            )
            if item.stage is not None:
                changes["status"] = item.stage
            if item.applied_on is not None:
                changes["applied_at"] = item.applied_on
            if item.reply is not None:
                changes["reply"] = ReplyChange(**item.reply.model_dump(exclude_unset=True))
            if item.reply_fix is not None:
                fix = item.reply_fix.model_dump(exclude_unset=True, exclude={"reply_id", "delete"})
                changes["reply"] = ReplyChange(
                    id=item.reply_fix.reply_id, remove=item.reply_fix.delete, **fix
                )
            application = self.update_application(item.application_id, ApplicationFields(**changes))
            last = application.get("last_reply") or {}
            return _application_echo(application, last_reply=last.get("kind"))

        return run_items(self.db, value.items, lambda item: item.application_id, apply)
