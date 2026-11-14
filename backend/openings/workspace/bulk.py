"""Bulk changes of explicit, versioned jobs and applications with per-item results."""

from ..common import batch_result, check_version
from ..errors import DomainError, missing
from ..models import ApplicationBulk, ApplicationPatch, JobBulk


class BulkChanges:
    """Applying one action to many selected records."""

    def _bulk(self, items, apply, deleting):
        """Run each versioned item on its own; collect orphaned blobs once per run."""
        results = []
        try:
            for item in items:
                try:
                    with self.db.lock:
                        result = apply(item)
                    results.append({"id": item.id, "ok": True, "result": result})
                except DomainError as error:
                    results.append(
                        {
                            "id": item.id,
                            "ok": False,
                            "error": {
                                "code": error.code,
                                "message": error.message,
                                "status": error.status,
                                "details": error.details,
                            },
                        }
                    )
        finally:
            if deleting and any(result["ok"] for result in results):
                self.db.collect_blobs()
        return batch_result(results)

    def bulk_jobs(self, value):
        value = value if isinstance(value, JobBulk) else JobBulk.model_validate(value)

        def apply(item):
            row = self.db.one("SELECT id,version FROM jobs WHERE id=?", (item.id,))
            check_version(row, item.expected_version)
            if value.action == "forget":
                self.forget_job(item.id, item.expected_version, collect=False)
                return {"deleted": True}
            updated = self.set_triage(
                item.id,
                value.action,
                item.expected_version,
                reason=value.reason if value.action == "dismissed" else None,
            )
            return {"triage": updated["triage"], "version": updated["version"]}

        return self._bulk(value.items, apply, value.action == "forget")

    def bulk_applications(self, value):
        """Close with an outcome, reopen to a stage, or delete versioned attempts."""
        value = (
            value if isinstance(value, ApplicationBulk) else ApplicationBulk.model_validate(value)
        )

        def apply(item):
            row = self.db.one("SELECT id,status,version FROM applications WHERE id=?", (item.id,))
            if row is None:
                missing("Application")
            check_version(row, item.expected_version)
            if value.action == "delete":
                self.delete_application(item.id, item.expected_version, collect=False)
                return {"deleted": True}
            if value.action == "reopen" and row["status"] != "closed":
                raise DomainError(
                    409,
                    "application_open",
                    "Only a Closed application can be reopened.",
                    {"status": row["status"]},
                )
            patch = (
                {"status": "closed", "outcome": value.outcome}
                if value.action == "close"
                else {"status": value.status}
            )
            updated = self.update_application(
                item.id, ApplicationPatch(expected_version=item.expected_version, **patch)
            )
            return {
                "job_id": updated["job_id"],
                "status": updated["status"],
                "outcome": updated["outcome"],
                "version": updated["version"],
            }

        return self._bulk(value.items, apply, value.action == "delete")
