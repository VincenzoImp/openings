from datetime import date, datetime, timedelta

from openings.database import BlacklistQuery, JobDatabase, JobQuery
from openings.models import (
    AttachmentKind,
    BlacklistEntry,
    JobStatus,
    NoteKind,
    RunSummary,
    SourceRunStats,
)
from tests.conftest import make_job


def test_upsert_inserts_updates_and_records_ingest_event(db: JobDatabase, job):
    first = db.upsert_jobs([job])
    assert first.new_ids == [job.job_id] and first.updated_ids == []
    events = db.list_events(job.job_id)
    assert [event.kind.value for event in events] == ["ingested"]

    again = db.upsert_jobs([make_job(description="longer text", relevance_score=50)])
    assert again.updated_ids == [job.job_id]
    stored = db.get_job(job.job_id)
    assert stored is not None
    assert stored.description == "longer text"
    assert stored.relevance_score == 50
    assert len(db.list_events(job.job_id)) == 1


def test_upsert_never_touches_status(db: JobDatabase, job):
    db.upsert_jobs([job])
    db.set_status([job.job_id], JobStatus.APPLIED)
    db.upsert_jobs([make_job(relevance_score=99)])
    assert db.get_job(job.job_id).status is JobStatus.APPLIED


def test_upsert_skips_blacklisted(db: JobDatabase, job):
    db.upsert_jobs([job])
    assert db.blacklist_jobs([job.job_id]) == 1
    assert db.get_job(job.job_id) is None
    result = db.upsert_jobs([job])
    assert result.skipped_blacklisted == 1
    assert db.get_job(job.job_id) is None


def test_set_status_records_event_and_is_idempotent(db: JobDatabase, job):
    db.upsert_jobs([job])
    assert db.set_status([job.job_id], JobStatus.SHORTLISTED, note="looks good") == [job.job_id]
    assert db.set_status([job.job_id], JobStatus.SHORTLISTED) == []
    events = db.list_events(job.job_id)
    assert events[-1].summary == "Status new -> shortlisted: looks good"
    assert events[-1].data == {"from": "new", "to": "shortlisted"}
    stored = db.get_job(job.job_id)
    assert stored.status_changed_at is not None


def test_retention_only_touches_new_rows(db: JobDatabase, jobs, config):
    db.upsert_jobs(jobs)
    kept = jobs[2].job_id  # score -40, would be deleted
    db.set_status([kept], JobStatus.APPLIED)
    config.scoring.save_threshold = 10
    report = db.reconcile(config)
    assert report.deleted_below_score == 0  # jobs[1] has 15 >= 10; jobs[2] protected
    assert report.protected == 1
    assert db.get_job(kept) is not None

    config.scoring.save_threshold = 20
    report = db.reconcile(config)
    assert report.deleted_below_score == 1
    assert db.get_job(jobs[1].job_id) is None
    assert db.get_job(kept) is not None


def test_stale_deletion_respects_status(db: JobDatabase):
    old = make_job(title="Old", last_seen=date.today() - timedelta(days=40))
    protected = make_job(title="Old but mine", last_seen=date.today() - timedelta(days=40))
    db.upsert_jobs([old, protected])
    db.set_status([protected.job_id], JobStatus.INTERVIEWING)
    assert db.count_stale(30) == 1
    assert db.delete_stale(30) == 1
    assert db.get_job(protected.job_id) is not None


def test_query_filters_and_sorts(db: JobDatabase, jobs):
    db.upsert_jobs(jobs)
    db.set_status([jobs[0].job_id], JobStatus.SHORTLISTED)
    db.add_labels([jobs[0].job_id], ["priority"])

    page, total = db.query_jobs(JobQuery(statuses=("shortlisted",)))
    assert total == 1 and page[0].job_id == jobs[0].job_id

    page, total = db.query_jobs(JobQuery(labels=("PRIORITY",)))
    assert total == 1

    page, total = db.query_jobs(JobQuery(sources=("greenhouse",)))
    assert total == 1 and page[0].source == "greenhouse"

    page, total = db.query_jobs(JobQuery(text="berlin"))
    assert total == 1

    page, _ = db.query_jobs(JobQuery(sort="title"))
    assert [j.title for j in page] == ["Backend Engineer", "Data Engineer", "Sales Manager"]

    page, _ = db.query_jobs(JobQuery(min_score=0))
    assert all(j.relevance_score >= 0 for j in page)

    page, total = db.query_jobs(JobQuery(limit=1, offset=1))
    assert total == 3 and len(page) == 1


def test_labels_add_remove_and_facets(db: JobDatabase, job):
    db.upsert_jobs([job])
    assert db.add_labels([job.job_id], ["a", "b", "a"]) == 2
    assert db.get_labels(job.job_id) == ["a", "b"]
    assert db.remove_labels([job.job_id], ["a"]) == 1
    assert db.get_facets()["labels"] == [{"value": "b", "count": 1}]
    assert db.add_labels(["missing"], ["x"]) == 0


def test_notes_and_attachments_cascade_on_delete(db: JobDatabase, job):
    db.upsert_jobs([job])
    note = db.add_note(job.job_id, NoteKind.QA, "Because.", title="Why?")
    assert note is not None and note.kind is NoteKind.QA
    attachment = db.add_attachment(
        job.job_id,
        kind=AttachmentKind.CV,
        filename="cv.pdf",
        stored_name="x-cv.pdf",
        sha256="ab",
        size_bytes=3,
    )
    assert attachment is not None
    assert len(db.list_notes(job.job_id)) == 1
    assert len(db.list_attachments(job.job_id)) == 1
    assert db.delete_jobs([job.job_id]) == 1
    assert db.list_notes(job.job_id) == []
    assert db.list_attachments(job.job_id) == []
    assert db.list_events(job.job_id) == []


def test_delete_note_and_attachment(db: JobDatabase, job):
    db.upsert_jobs([job])
    note = db.add_note(job.job_id, NoteKind.NOTE, "hello")
    assert db.delete_note(job.job_id, note.id) is True
    assert db.delete_note(job.job_id, note.id) is False
    attachment = db.add_attachment(
        job.job_id,
        kind=AttachmentKind.OTHER,
        filename="a.txt",
        stored_name="s",
        sha256="h",
        size_bytes=1,
    )
    assert db.delete_attachment(job.job_id, attachment.id).id == attachment.id
    assert db.get_attachment(job.job_id, attachment.id) is None


def test_blacklist_listing_and_purge(db: JobDatabase, jobs):
    db.upsert_jobs(jobs)
    db.blacklist_jobs([jobs[0].job_id, jobs[1].job_id])
    entries, total = db.list_blacklist(BlacklistQuery(text="acme"))
    assert total == 1 and entries[0].company == "Acme"
    assert db.count_blacklist_older_than(1) == 0
    assert db.purge_blacklist(older_than_days=1) == 0
    assert db.unblacklist_jobs([jobs[0].job_id]) == 1
    _, total = db.list_blacklist(BlacklistQuery())
    assert total == 1
    assert db.purge_blacklist() == 1


def test_blacklist_identities_directly(db: JobDatabase):
    entry = BlacklistEntry("a" * 64, "T", "C", "L", datetime.now())
    assert db.blacklist_identities([entry]) == 1
    assert db.blacklisted_ids(["a" * 64]) == {"a" * 64}


def test_statistics_distribution_and_top(db: JobDatabase, jobs):
    db.upsert_jobs(jobs)
    stats = db.get_statistics()
    assert stats["total_jobs"] == 3
    assert stats["by_status"]["new"] == 3
    assert stats["new_today"] == 3
    distribution = db.get_score_distribution(10)
    assert sum(count for _, count in distribution) == 3
    assert [j.title for j in db.get_top_jobs(limit=1)] == ["Backend Engineer"]


def test_rescore_all_uses_current_config(db: JobDatabase, config):
    db.upsert_jobs([make_job(relevance_score=0)])
    changed = db.rescore_all(config)
    assert changed == 1
    job = next(iter(db.iter_jobs()))
    assert job.relevance_score == 35  # role 25 + stack 10


def test_runs_round_trip(db: JobDatabase):
    summary = RunSummary(
        started_at=datetime(2026, 9, 8, 6, 0), finished_at=datetime(2026, 9, 8, 6, 30)
    )
    summary.sources.append(
        SourceRunStats(name="linkedin", tasks=4, succeeded=3, failed=1, rows=12, errors=["x"])
    )
    summary.errors.append("linkedin: x")
    run_id = db.record_run(summary)
    runs = db.list_runs()
    assert runs[0].id == run_id
    assert runs[0].sources[0].rows == 12
    assert runs[0].errors == ["linkedin: x"]
    assert runs[0].duration_seconds == 1800.0


def test_reset_all_clears_everything(db: JobDatabase, job):
    db.upsert_jobs([job])
    db.blacklist_identities([BlacklistEntry("b" * 64, "T", "C", "L", datetime.now())])
    db.reset_all()
    assert db.count_jobs() == 0
    assert db.list_blacklist(BlacklistQuery())[1] == 0
