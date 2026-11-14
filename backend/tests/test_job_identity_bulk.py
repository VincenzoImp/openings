"""Read-only identity lookup, duplicate candidates and bulk application changes."""

import pytest
from pydantic import ValidationError

from openings.duplicate_signals import normalize_company, normalize_title, posting_fingerprint

BODY = " ".join(
    f"Design reliable Python services and review practical API change number {index}."
    for index in range(30)
)


def ingest(workspace, url, title="Backend Engineer", company="Example Labs", **extra):
    return workspace.ingest_job(
        {"url": url, "title": title, "company": company, "posting": BODY, **extra}
    )


def count(workspace, table):
    return workspace.db.one(f"SELECT count(*) n FROM {table}")["n"]


def test_resolve_matches_identities_without_ingesting_and_reports_conflicts(workspace):
    job = ingest(
        workspace,
        "https://jobs.lever.co/example/abc-123?utm_source=feed",
        source_key="linkedin:4242",
    )
    attempt = workspace.create_application({"job_id": job["id"]})
    before = (count(workspace, "jobs"), count(workspace, "postings"), count(workspace, "events"))

    by_url = workspace.resolve_jobs({"url": "https://JOBS.lever.co/example/abc-123/#apply"})
    assert by_url["url"] == "https://jobs.lever.co/example/abc-123"
    assert [item["id"] for item in by_url["items"]] == [job["id"]]
    match = by_url["items"][0]
    assert "lever:example:abc-123" in match["matched_by"] and "job_url" in match["matched_by"]
    assert match["triage"] == "shortlisted" and match["application"]["id"] == attempt["id"]
    assert match["applications"] == [
        {
            "id": attempt["id"],
            "status": "shortlisted",
            "outcome": None,
            "version": attempt["version"],
            "applied_at": None,
        }
    ]
    assert not by_url["identity_conflict"]

    by_key = workspace.resolve_jobs({"source_key": "linkedin:4242"})
    assert by_key["items"][0]["matched_by"] == ["linkedin:4242"]
    assert workspace.resolve_jobs({"url": "https://example.test/unknown"})["items"] == []
    after = (count(workspace, "jobs"), count(workspace, "postings"), count(workspace, "events"))
    assert after == before

    # A URL and a source key that name two different jobs are a conflict.
    other = ingest(workspace, "https://example.test/careers/2")
    result = workspace.resolve_jobs(
        {"url": "https://example.test/careers/2", "source_key": "linkedin:4242"}
    )
    assert {item["id"] for item in result["items"]} == {job["id"], other["id"]}
    assert result["identity_conflict"]


def test_a_concurrent_retry_of_an_ingest_gives_the_same_job(workspace, monkeypatch):
    posting = {"title": "Synthetic engineer", "posting": BODY, "idempotency_key": "ingest-1"}
    first = workspace.ingest_job(posting)
    # The check before the write saw no key: another request was still writing it.
    monkeypatch.setattr(workspace, "replayed_job", lambda *_: None)
    again = workspace.ingest_job(posting)
    assert (again["id"], again["created"]) == (first["id"], False)


def test_normalization_signals():
    assert normalize_title("Senior Backend Engineer (m/w/d)") == "senior backend engineer"
    assert normalize_title("Senior  Backend-Engineer [f/m/x]") == "senior backend engineer"
    assert normalize_company("Example Labs GmbH") == normalize_company("example labs")
    assert normalize_company("Inc") == "inc"
    assert posting_fingerprint("Too short.") is None
    assert posting_fingerprint(BODY) == posting_fingerprint(BODY.upper().replace(".", " ."))


def test_duplicate_groups_are_annotated_filtered_and_read_only(workspace):
    linkedin = ingest(
        workspace, "https://www.linkedin.com/jobs/view/1", metadata={"source": "linkedin"}
    )
    indeed = ingest(
        workspace,
        "https://www.indeed.com/viewjob?jk=2",
        title="Backend Engineer (m/f/d)",
        company="Example Labs GmbH",
        metadata={"source": "indeed"},
    )
    ats = ingest(
        workspace,
        "https://jobs.lever.co/example/3",
        title="Platform Engineer",
        metadata={"source": "lever"},
    )
    other_city = ingest(
        workspace,
        "https://www.glassdoor.com/job/4",
        location="Berlin",
        posting="Different short body.",
    )
    unrelated = ingest(
        workspace, "https://example.test/5", title="Designer", posting="Brand design work."
    )
    attempt = workspace.create_application({"job_id": ats["id"]})
    before = (count(workspace, "jobs"), count(workspace, "events"))

    # Shared text under another title, or company and title alone, stay in the low
    # tier, hidden unless asked for.
    likely = workspace.duplicate_jobs({})
    assert likely["total"] == 1 and likely["min_confidence"] == 0.5
    assert set(likely["items"][0]["job_ids"]) == {linkedin["id"], indeed["id"]}
    assert likely["items"][0]["tier"] == "medium"

    result = workspace.duplicate_jobs({"min_confidence": 0})
    assert result["total"] == 1 and result["limit"] == 20
    group = result["items"][0]
    expected = {linkedin["id"], indeed["id"], ats["id"], other_city["id"]}
    assert set(group["job_ids"]) == expected and unrelated["id"] not in group["job_ids"]
    assert group["signals"] == ["company", "company_title", "posting_text"]
    assert group["confidence"] == 0.32 and group["tier"] == "low"
    assert group["reasons"] == {"matched": group["signals"], "conflicts": []}
    assert group["reference_id"] == ats["id"] and group["items"][0]["id"] == ats["id"]
    assert group["open_application_ids"] == [attempt["id"]] and not group["merge_blocked"]
    assert not group["identical_postings"]
    by_id = {item["id"]: item for item in group["items"]}
    assert by_id[indeed["id"]]["similarity"] == 1.0
    assert by_id[ats["id"]]["confidence"] is None and by_id[ats["id"]]["reasons"] is None
    assert by_id[indeed["id"]]["confidence"] == 0.32
    assert by_id[indeed["id"]]["reasons"] == {
        "matched": ["posting_text", "company"],
        "conflicts": [],
    }
    assert by_id[other_city["id"]]["similarity"] is None
    assert by_id[ats["id"]]["applications"][0]["status"] == "shortlisted"
    assert by_id[linkedin["id"]]["source"] == "linkedin"

    by_location = workspace.duplicate_jobs({"match_location": True, "min_confidence": 0})
    assert other_city["id"] not in by_location["items"][0]["job_ids"]
    assert workspace.duplicate_jobs({"job_id": unrelated["id"]})["total"] == 0
    assert workspace.duplicate_jobs({"job_id": indeed["id"]})["total"] == 1
    assert workspace.duplicate_jobs({"job_id": other_city["id"]})["total"] == 0
    assert workspace.duplicate_jobs({"triage": "new"})["total"] == 1
    assert workspace.duplicate_jobs({"triage": "dismissed"})["total"] == 0
    assert workspace.duplicate_jobs({"offset": 1})["items"] == []
    assert workspace.duplicate_jobs({"min_confidence": 0.85})["total"] == 0
    assert (count(workspace, "jobs"), count(workspace, "events")) == before


def test_duplicate_groups_flag_blocked_merges(workspace):
    first = ingest(workspace, "https://example.test/a")
    second = ingest(workspace, "https://example.test/b")
    for job in (first, second):
        workspace.create_application({"job_id": job["id"]})
    group = workspace.duplicate_jobs({})["items"][0]
    assert group["identical_postings"] and group["merge_blocked"]
    assert len(group["open_application_ids"]) == 2


def test_bulk_applications_close_reopen_delete_and_validate_their_input(workspace):
    jobs = [ingest(workspace, f"https://example.test/{index}") for index in range(3)]
    attempts = [workspace.create_application({"job_id": job["id"]}) for job in jobs]
    closed = workspace.bulk_applications(
        {
            "action": "close",
            "outcome": "not_pursued",
            "items": [
                {"id": attempts[0]["id"], "expected_version": attempts[0]["version"]},
                {"id": attempts[1]["id"], "expected_version": attempts[1]["version"] + 5},
                {"id": "missing", "expected_version": 1},
            ],
        }
    )
    assert (closed["succeeded"], closed["failed"], closed["total"]) == (1, 2, 3)
    first = closed["items"][0]["result"]
    assert first["status"] == "closed" and first["outcome"] == "not_pursued"
    conflict = closed["items"][1]["error"]
    assert conflict["status"] == 409 and conflict["details"]["current_version"] == 1
    assert closed["items"][2]["error"]["code"] == "not_found"

    # Reopening must respect one non-Closed attempt per job.
    replacement = workspace.create_application({"job_id": jobs[0]["id"]})
    blocked = workspace.bulk_applications(
        {
            "action": "reopen",
            "status": "applied",
            "items": [
                {"id": attempts[0]["id"], "expected_version": first["version"]},
                {"id": attempts[2]["id"], "expected_version": attempts[2]["version"]},
            ],
        }
    )
    assert blocked["failed"] == 2
    assert blocked["items"][0]["error"]["code"] == "application_in_progress"
    assert blocked["items"][1]["error"]["code"] == "application_open"
    workspace.delete_application(replacement["id"], replacement["version"])
    reopened = workspace.bulk_applications(
        {
            "action": "reopen",
            "status": "applied",
            "items": [{"id": attempts[0]["id"], "expected_version": first["version"]}],
        }
    )["items"][0]["result"]
    assert reopened["status"] == "applied" and reopened["outcome"] is None
    assert workspace.get_application(attempts[0]["id"])["applied_at"]

    deleted = workspace.bulk_applications(
        {
            "action": "delete",
            "items": [
                {"id": attempts[0]["id"], "expected_version": reopened["version"]},
                {"id": attempts[2]["id"], "expected_version": attempts[2]["version"]},
            ],
        }
    )
    assert deleted["succeeded"] == 2
    assert workspace.list_applications(job_id=jobs[2]["id"])["total"] == 0
    assert workspace.get_job(jobs[2]["id"])["id"] == jobs[2]["id"]

    item = {"id": "a", "expected_version": 1}
    for invalid in (
        {"action": "close", "items": [item]},
        {"action": "reopen", "items": [item]},
        {"action": "delete", "outcome": "rejected", "items": [item]},
        {"action": "close", "status": "shortlisted", "outcome": "rejected", "items": [item]},
        {"action": "delete", "items": [item] * 2},
        {"action": "delete", "items": []},
    ):
        with pytest.raises(ValidationError):
            workspace.bulk_applications(invalid)


def store_blob(workspace, job_id, content):
    import hashlib

    from openings.common import new_id, now

    digest = hashlib.sha256(content).hexdigest()
    with workspace.db.transaction() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO blobs(sha256,content,size) VALUES(?,?,?)",
            (digest, content, len(content)),
        )
        connection.execute(
            "INSERT INTO files(id,sha256,name,size,job_id,created_at) VALUES(?,?,?,?,?,?)",
            (new_id(), digest, "note.txt", len(content), job_id, now()),
        )


def test_bulk_deletion_collects_orphan_blobs_once(workspace, monkeypatch):
    jobs = [ingest(workspace, f"https://example.test/{index}") for index in range(4)]
    for index, job in enumerate(jobs):
        store_blob(workspace, job["id"], f"synthetic file {index}".encode())
    calls = []
    original = workspace.db.collect_blobs
    monkeypatch.setattr(workspace.db, "collect_blobs", lambda: calls.append(1) or original())
    result = workspace.bulk_jobs(
        {
            "action": "forget",
            "items": [{"id": job["id"], "expected_version": job["version"]} for job in jobs[:3]],
        }
    )
    assert result["succeeded"] == 3 and len(calls) == 1
    assert count(workspace, "blobs") == 1

    attempts = [workspace.create_application({"job_id": jobs[3]["id"]})]
    calls.clear()
    workspace.bulk_applications(
        {
            "action": "close",
            "outcome": "rejected",
            "items": [{"id": attempts[0]["id"], "expected_version": attempts[0]["version"]}],
        }
    )
    assert calls == []
    failed = workspace.bulk_jobs(
        {"action": "forget", "items": [{"id": jobs[3]["id"], "expected_version": 99}]}
    )
    assert failed["failed"] == 1 and calls == []


def test_resolve_duplicates_and_bulk_routes_are_not_read_as_ids(client):
    """``/jobs/resolve``, ``/jobs/duplicates`` and ``/applications/bulk`` sit beside
    ``/{id}`` routes; the behaviour itself is tested on the services above."""
    first, second = (
        client.post(
            "/api/v1/jobs",
            json={"url": url, "title": "Data Engineer", "company": "Example", "posting": BODY},
        ).json()
        for url in ("https://example.test/one", "https://example.test/two")
    )
    resolved = client.get("/api/v1/jobs/resolve", params={"url": "https://example.test/one/"})
    assert [item["id"] for item in resolved.json()["items"]] == [first["id"]]
    groups = client.get("/api/v1/jobs/duplicates", params={"job_id": second["id"]}).json()
    assert set(groups["items"][0]["job_ids"]) == {first["id"], second["id"]}
    attempt = client.post("/api/v1/applications", json={"job_id": first["id"]}).json()
    bulk = client.post(
        "/api/v1/applications/bulk",
        json={
            "action": "close",
            "outcome": "rejected",
            "items": [{"id": attempt["id"], "expected_version": attempt["version"]}],
        },
    )
    assert bulk.status_code == 200 and bulk.json()["succeeded"] == 1
