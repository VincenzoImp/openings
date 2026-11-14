"""Shortlisting a job starts its application; undoing it removes only an empty one."""

import sqlite3
import threading

import pytest

from openings.documents import DocumentService
from openings.errors import DomainError
from openings.workspace import Workspace


def add(workspace, title="Synthetic engineer"):
    return workspace.ingest_job({"title": title, "company": "Example", "posting": "Build APIs."})


def open_applications(workspace, job_id):
    return workspace.db.all(
        "SELECT * FROM applications WHERE job_id=? AND status<>'closed'", (job_id,)
    )


def test_shortlisting_and_starting_an_application_are_one_act(workspace):
    job = add(workspace)
    job = workspace.set_triage(job["id"], "shortlisted", job["version"])
    [application] = open_applications(workspace, job["id"])
    assert (application["status"], application["from_shortlist"]) == ("shortlisted", 1)
    assert job["application"]["id"] == application["id"]
    read = workspace.get_application(application["id"])
    assert read["required_documents"] == ["cv", "letter"] and read["from_shortlist"] is True
    created = workspace.db.all(
        "SELECT payload FROM events WHERE kind='application_created' AND application_id=?",
        (application["id"],),
    )
    assert len(created) == 1
    # Shortlisting again is no change; a second application is refused by the service.
    again = workspace.set_triage(job["id"], "shortlisted", job["version"])
    assert len(open_applications(workspace, job["id"])) == 1 and again["version"] == job["version"]
    with pytest.raises(DomainError) as refused:
        workspace.create_application({"job_id": job["id"]})
    assert refused.value.code == "application_in_progress"
    # ... and by SQLite.
    with pytest.raises(sqlite3.IntegrityError), workspace.db.transaction() as conn:
        conn.execute(
            "INSERT INTO applications(id,job_id,created_at,updated_at) VALUES('x',?,'t','t')",
            (job["id"],),
        )
    # Bulk shortlisting starts one per job.
    others = [add(workspace, f"Role {number}") for number in range(3)]
    result = workspace.bulk_jobs(
        {
            "action": "shortlisted",
            "items": [{"id": item["id"], "expected_version": item["version"]} for item in others],
        }
    )
    assert result["succeeded"] == 3
    assert all(len(open_applications(workspace, item["id"])) == 1 for item in others)
    # The reverse: starting an application shortlists its job.
    job = add(workspace, "Started")
    application = workspace.create_application(
        {"job_id": job["id"], "required_documents": ["letter"]}
    )
    assert workspace.get_job(job["id"])["triage"] == "shortlisted"
    assert application["required_documents"] == ["letter"]
    assert application["from_shortlist"] is False


def test_concurrent_shortlist_and_start_leave_one_application(tmp_path):
    path = tmp_path / "concurrent.sqlite"
    workspace = Workspace(path)
    for _ in range(5):
        job = add(workspace)
        barrier, results = threading.Barrier(3), []

        def shortlist(job=job, barrier=barrier, results=results):
            barrier.wait()
            try:
                results.append(Workspace(path).set_triage(job["id"], "shortlisted", job["version"]))
            except DomainError as error:
                results.append(error)

        def start(job=job, barrier=barrier, results=results):
            barrier.wait()
            try:
                results.append(Workspace(path).create_application({"job_id": job["id"]}))
            except DomainError as error:
                results.append(error)

        threads = [threading.Thread(target=target) for target in (shortlist, start, start)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(open_applications(workspace, job["id"])) == 1
        assert workspace.get_job(job["id"])["triage"] == "shortlisted"
        assert all(isinstance(result, dict) or result.status == 409 for result in results), results


def test_undoing_a_shortlist_deletes_only_an_empty_application(workspace):
    for target in ("new", "dismissed"):
        job = add(workspace, f"Undone to {target}")
        job = workspace.set_triage(job["id"], "shortlisted", job["version"])
        application_id = job["application"]["id"]
        job = workspace.set_triage(job["id"], target, job["version"])
        assert job["triage"] == target and job["application"] is None
        assert workspace.db.one("SELECT count(*) n FROM applications")["n"] == 0
        deleted = workspace.db.all(
            "SELECT kind FROM events WHERE subject_type='application' AND subject_id=? "
            "ORDER BY rowid",
            (application_id,),
        )
        # The application's own events go with it; its deletion stays recorded.
        assert [row["kind"] for row in deleted] == ["application_deleted"]


WORK = {
    "note": ["notes"],
    "requirement": ["requirements"],
    "applied": ["stage"],
    "reply": ["stage", "replies"],
    "document": ["documents"],
    "started": ["started_separately"],
}


def test_undoing_a_shortlist_with_work_is_refused(workspace):
    documents = DocumentService(workspace)
    for work, names in WORK.items():
        job = add(workspace, f"With {work}")
        if work == "started":
            workspace.create_application({"job_id": job["id"]})
        else:
            job = workspace.set_triage(job["id"], "shortlisted", job["version"])
        job = workspace.get_job(job["id"])
        application = workspace.get_application(job["application"]["id"])
        version = application["version"]
        if work == "note":
            workspace.add_note(
                job["id"], {"body": "Synthetic.", "application_id": application["id"]}
            )
        elif work == "requirement":
            workspace.update_application(
                application["id"],
                {"expected_version": version, "requirements": [{"text": "Portfolio"}]},
            )
        elif work in {"applied", "reply"}:
            applied = workspace.update_application(
                application["id"], {"expected_version": version, "stage": "applied"}
            )
            if work == "reply":
                workspace.update_application(
                    application["id"],
                    {"expected_version": applied["version"], "reply": {"kind": "other"}},
                )
        elif work == "document":
            documents.create_document(
                {"application_id": application["id"], "kind": "answers", "content": {"a": 1}}
            )
        with pytest.raises(DomainError) as refused:
            workspace.set_triage(job["id"], "new", job["version"])
        assert (refused.value.status, refused.value.code) == (409, "application_has_work"), work
        assert refused.value.details["work"] == names
        assert refused.value.details["application_id"] == application["id"]
        assert workspace.get_job(job["id"])["triage"] == "shortlisted"
        assert len(open_applications(workspace, job["id"])) == 1


def test_closing_never_changes_triage_and_a_closed_application_is_kept(workspace):
    job = add(workspace)
    job = workspace.set_triage(job["id"], "shortlisted", job["version"])
    application = workspace.get_application(job["application"]["id"])
    workspace.update_application(
        application["id"],
        {"expected_version": application["version"], "stage": "closed", "outcome": "not_pursued"},
    )
    job = workspace.get_job(job["id"])
    assert job["triage"] == "shortlisted"
    dismissed = workspace.set_triage(job["id"], "dismissed", job["version"])
    assert dismissed["application"]["id"] == application["id"]
    counts = workspace.list_jobs(include_counts=True)["counts"]
    assert {key: counts[key] for key in ("all", "new", "shortlisted", "dismissed")} == {
        "all": 1,
        "new": 0,
        "shortlisted": 0,
        "dismissed": 1,
    }


def test_reopening_a_closed_application_follows_the_rules_of_a_start(workspace):
    job = add(workspace)
    job = workspace.set_triage(job["id"], "shortlisted", job["version"])
    application = workspace.update_application(
        job["application"]["id"],
        {
            "expected_version": workspace.get_application(job["application"]["id"])["version"],
            "stage": "closed",
            "outcome": "not_pursued",
        },
    )
    job = workspace.set_triage(job["id"], "dismissed", workspace.get_job(job["id"])["version"])
    reopen = {"expected_version": application["version"], "stage": "shortlisted"}
    with pytest.raises(DomainError, match="Restore the dismissed job"):
        workspace.update_application(application["id"], reopen)
    assert workspace.get_application(application["id"])["stage"] == "closed"
    # Restored to New, reopening shortlists the job again.
    workspace.set_triage(job["id"], "new", workspace.get_job(job["id"])["version"])
    workspace.update_application(application["id"], reopen)
    assert workspace.get_job(job["id"])["triage"] == "shortlisted"


def test_merging_two_shortlisted_jobs_keeps_the_application_with_work(workspace):
    first, second = add(workspace, "First"), add(workspace, "Second")
    first = workspace.set_triage(first["id"], "shortlisted", first["version"])
    second = workspace.set_triage(second["id"], "shortlisted", second["version"])
    kept = workspace.get_application(second["application"]["id"])
    workspace.add_note(second["id"], {"body": "Synthetic.", "application_id": kept["id"]})
    merged = workspace.merge_jobs(second["id"], first["id"], second["version"], first["version"])
    assert merged["triage"] == "shortlisted"
    [application] = open_applications(workspace, first["id"])
    assert application["id"] == kept["id"]
