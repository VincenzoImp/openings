from datetime import date, timedelta, timezone

import numpy as np
import pytest

from openings.db import JobQuery
from openings.models import AttachmentKind, EventKind, JobStatus, NoteKind, RunSummary, utcnow
from tests.conftest import make_job


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


def test_upsert_inserts_with_posting_and_ingested_event(db, job):
    result = db.upsert_jobs([job])
    assert result.new_ids == [job.job_id] and not result.updated_ids
    stored = db.get_job(job.job_id)
    assert stored.status is JobStatus.NEW
    assert stored.postings_count == 1
    postings = db.list_postings(job.job_id)
    assert postings[0].key == "linkedin:1000001" and postings[0].source == "linkedin"
    assert [event.kind for event in db.list_events(job.job_id)] == [EventKind.INGESTED]


def test_upsert_refreshes_known_posting_without_touching_status(db, job):
    db.upsert_jobs([job])
    db.set_status([job.job_id], JobStatus.APPLIED)
    later = make_job(description="Updated text", relevance_score=50, last_seen=date.today())
    result = db.upsert_jobs([later])
    assert result.updated_ids == [job.job_id] and not result.new_ids
    stored = db.get_job(job.job_id)
    assert stored.status is JobStatus.APPLIED
    assert stored.description == "Updated text"
    assert stored.relevance_score == 50
    assert stored.postings_count == 1


def test_upsert_attaches_cross_board_mirror_as_second_posting(db, job):
    db.upsert_jobs([job])
    mirror = make_job(source="indeed", job_url="https://ch.indeed.com/viewjob?jk=abc")
    result = db.upsert_jobs([mirror])
    assert result.updated_ids == [job.job_id] and result.new_postings == [job.job_id]
    assert db.count_jobs() == 1
    sources = {posting.source for posting in db.list_postings(job.job_id)}
    assert sources == {"linkedin", "indeed"}
    assert any(event.kind is EventKind.POSTING for event in db.list_events(job.job_id))


def test_same_source_same_title_different_url_stays_separate(db, job):
    db.upsert_jobs([job])
    other = make_job(job_url="https://www.linkedin.com/jobs/view/1000009")
    result = db.upsert_jobs([other])
    assert result.new_ids and result.new_ids[0] != job.job_id
    assert db.count_jobs() == 2


def test_identity_only_rows_dedupe_by_identity(db):
    first = make_job(job_url=None, source="manual")
    second = make_job(job_url=None, source="manual", description="again")
    result = db.upsert_jobs([first, second])
    assert len(result.new_ids) == 1
    assert db.count_jobs() == 1
    assert db.get_job(first.identity) is not None


def test_upsert_never_resurrects_blacklisted(db, job):
    db.upsert_jobs([job])
    db.set_status([job.job_id], JobStatus.BLACKLISTED)
    result = db.upsert_jobs([make_job(description="back again")])
    assert result.skipped_blacklisted == 1 and not result.updated_ids
    assert db.get_job(job.job_id).description == "Python services with PostgreSQL."
    assert db.count_jobs() == 0  # blacklisted rows are not active


def test_find_job_by_key_or_identity(db, job):
    db.upsert_jobs([job])
    assert db.find_job(job.posting_key, job.identity).job_id == job.job_id
    assert db.find_job(None, job.identity).job_id == job.job_id
    assert db.find_job("linkedin:999", "nope") is None


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def test_set_status_records_event_and_skips_noops(db, job):
    db.upsert_jobs([job])
    assert db.set_status([job.job_id], JobStatus.SHORTLISTED, note="worth it") == [job.job_id]
    assert db.set_status([job.job_id], JobStatus.SHORTLISTED) == []
    events = db.list_events(job.job_id)
    assert events[-1].summary == "Status new -> shortlisted: worth it"
    assert events[-1].data == {"from": "new", "to": "shortlisted", "note": "worth it"}
    assert db.get_job(job.job_id).status_changed_at.tzinfo is not None


def test_previous_statuses_remember_where_a_blacklisted_job_was(db, job):
    db.upsert_jobs([job])
    db.set_status([job.job_id], JobStatus.APPLIED)
    db.set_status([job.job_id], JobStatus.BLACKLISTED)
    assert db.previous_statuses([job.job_id]) == {job.job_id: "applied"}


def test_update_job_changes_fields_identity_and_score(db, job):
    db.upsert_jobs([job])
    updated = db.update_job(job.job_id, {"title": "Platform Engineer", "bogus": 1}, score=77)
    assert updated.title == "Platform Engineer" and updated.relevance_score == 77
    assert updated.identity != job.identity
    assert db.list_events(job.job_id)[-1].kind is EventKind.UPDATED
    assert db.update_job("missing", {"title": "x"}) is None


def test_merge_jobs_moves_everything(db, job):
    other = make_job(
        title="Backend Engineer (Indeed)",
        source="indeed",
        job_url="https://ch.indeed.com/viewjob?jk=zzz",
    )
    db.upsert_jobs([job, other])
    db.add_labels([other.job_id], ["mirror"])
    db.add_note(other.job_id, NoteKind.NOTE, "from the mirror")
    db.add_attachment(
        other.job_id,
        kind=AttachmentKind.CV,
        filename="cv.pdf",
        stored_name="x-cv.pdf",
        sha256="0" * 64,
        size_bytes=4,
    )
    result = db.merge_jobs(job.job_id, [other.job_id, "unknown"])
    assert result.merged_ids == [other.job_id]
    assert result.moved_attachments == [(other.job_id, "x-cv.pdf")]
    assert db.get_job(other.job_id) is None
    assert {p.source for p in db.list_postings(job.job_id)} == {"linkedin", "indeed"}
    assert db.get_labels(job.job_id) == ["mirror"]
    assert len(db.list_notes(job.job_id)) == 1 and len(db.list_attachments(job.job_id)) == 1
    assert db.list_events(job.job_id)[-1].kind is EventKind.MERGED
    assert db.merge_jobs("missing", [job.job_id]) is None


def test_delete_jobs_cascades(db, job):
    db.upsert_jobs([job])
    db.add_note(job.job_id, NoteKind.NOTE, "x")
    assert db.delete_jobs([job.job_id, "nope"]) == 1
    assert db.get_job(job.job_id) is None
    assert db.list_notes(job.job_id) == []


def test_rescore_all_skips_blacklisted(db, config, job):
    other = make_job(
        title="Other", job_url="https://www.linkedin.com/jobs/view/2", relevance_score=0
    )
    db.upsert_jobs([make_job(relevance_score=0), other])
    db.set_status([other.job_id], JobStatus.BLACKLISTED)
    assert db.rescore_all(config) == 1
    assert db.get_job(job.job_id).relevance_score == 35


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded(db, jobs):
    db.upsert_jobs(jobs)
    db.set_status([jobs[1].job_id], JobStatus.APPLIED)
    db.set_status([jobs[2].job_id], JobStatus.BLACKLISTED)
    db.add_labels([jobs[0].job_id], ["seed"])
    db.add_note(jobs[1].job_id, NoteKind.QA, "Because of the platform", title="Why?")
    return jobs


def test_query_excludes_blacklisted_by_default(db, seeded):
    listed, total = db.query_jobs(JobQuery())
    assert total == 2 and {job.status for job in listed} == {JobStatus.NEW, JobStatus.APPLIED}
    only, total = db.query_jobs(JobQuery(statuses=("blacklisted",)))
    assert total == 1 and only[0].job_id == seeded[2].job_id


def test_query_filters(db, seeded):
    assert db.query_jobs(JobQuery(labels=("seed",)))[1] == 1
    assert db.query_jobs(JobQuery(without_labels=True))[1] == 1
    assert db.query_jobs(JobQuery(has_attachments=False))[1] == 2
    assert db.query_jobs(JobQuery(text="platform"))[1] == 1  # found in a note
    assert db.query_jobs(JobQuery(company="beta"))[1] == 1
    assert db.query_jobs(JobQuery(sources=("linkedin",)))[1] == 2
    assert db.query_jobs(JobQuery(min_score=20))[1] == 1
    assert db.query_jobs(JobQuery(status_changed_from=date.today().isoformat()))[1] == 2


def test_query_sorting_and_direction(db, seeded):
    by_score = db.query_jobs(JobQuery(sort="score"))[0]
    assert [job.relevance_score for job in by_score] == [35, 15]
    ascending = db.query_jobs(JobQuery(sort="score", direction="asc"))[0]
    assert [job.relevance_score for job in ascending] == [15, 35]
    by_company = db.query_jobs(JobQuery(sort="company"))[0]
    assert [job.company for job in by_company] == ["Acme", "Beta"]


def test_query_pagination_and_counts(db, seeded):
    page, total = db.query_jobs(JobQuery(limit=1, offset=1))
    assert total == 2 and len(page) == 1
    assert page[0].notes_count in (0, 1)


def test_statistics_distribution_facets(db, seeded):
    stats = db.get_statistics()
    assert stats["total_jobs"] == 2 and stats["blacklisted"] == 1
    assert stats["by_status"]["applied"] == 1 and stats["notes"] == 1
    assert db.get_score_distribution(10) == [[10, 1], [30, 1]]
    facets = db.get_facets()
    assert {item["value"] for item in facets["companies"]} == {"Acme", "Beta"}
    assert facets["labels"] == [{"value": "seed", "count": 1}]
    assert db.get_facets(q="ac")["companies"] == [{"value": "Acme", "count": 1}]


def test_source_and_company_counts(db, seeded):
    assert db.source_counts() == {"linkedin": 2}
    assert db.company_source_counts()[("Acme", "linkedin")] == 1
    assert db.company_status_counts("beta") == {"applied": 1}


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------


def test_labels_notes_attachments(db, job):
    db.upsert_jobs([job])
    assert db.add_labels([job.job_id, "missing"], ["a", " b "]) == 2
    assert db.get_labels(job.job_id) == ["a", "b"]
    assert db.rename_label("a", "c") == 1 and db.get_labels(job.job_id) == ["b", "c"]
    assert db.delete_label("b") == 1
    assert db.remove_labels([job.job_id], ["c"]) == 1

    note = db.add_note(job.job_id, NoteKind.QA, "answer", title="question?")
    edited = db.update_note(job.job_id, note.id, body="better answer")
    assert edited.body == "better answer" and edited.updated_at is not None
    assert db.update_note(job.job_id, 999, body="x") is None
    assert db.delete_note(job.job_id, note.id) is True
    assert db.add_note("missing", NoteKind.NOTE, "x") is None

    attachment = db.add_attachment(
        job.job_id,
        kind=AttachmentKind.OTHER,
        filename="a.txt",
        stored_name="s-a.txt",
        sha256="0" * 64,
        size_bytes=1,
    )
    renamed = db.update_attachment(job.job_id, attachment.id, kind=AttachmentKind.CV, note="v2")
    assert renamed.kind is AttachmentKind.CV and renamed.note == "v2"
    rows, total = db.list_all_attachments(kind=AttachmentKind.CV)
    assert total == 1 and rows[0][1] == "Backend Engineer"
    assert db.stored_names([job.job_id]) == [(job.job_id, "s-a.txt")]
    assert db.delete_attachment(job.job_id, attachment.id).filename == "a.txt"


# ---------------------------------------------------------------------------
# Runs, retention, embeddings
# ---------------------------------------------------------------------------


def test_runs_open_finish_and_stale(db):
    summary = RunSummary(started_at=utcnow())
    db.start_run(summary)
    assert db.open_run().id == summary.id
    assert db.list_runs()[0].running is True
    summary.saved = 3
    summary.finish()
    db.finish_run(summary)
    stored = db.list_runs()[0]
    assert stored.saved == 3 and stored.running is False
    assert stored.started_at.tzinfo is not None
    crashed = RunSummary(started_at=utcnow() - timedelta(hours=3))
    db.start_run(crashed)
    assert db.open_run() is not None
    assert db.close_stale_runs() == 1
    assert db.open_run() is None
    closed = next(run for run in db.list_runs() if run.id == crashed.id)
    assert closed.success is False and closed.errors


def test_retention_only_touches_new(db, config, jobs):
    db.upsert_jobs(jobs)
    db.set_status([jobs[0].job_id], JobStatus.SHORTLISTED)
    old = make_job(
        title="Old",
        job_url="https://www.linkedin.com/jobs/view/3",
        last_seen=date.today() - timedelta(days=90),
    )
    db.upsert_jobs([old])
    assert db.count_stale(30) == 1 and db.count_below_score(20) == 2
    report = db.preview_reconcile(config)
    assert report.deleted_stale == 1 and report.protected == 1
    applied = db.reconcile(config)
    assert applied.deleted_below_score == 1  # the -40 row; save_threshold is 0
    assert applied.deleted_stale == 1
    assert db.delete_below_score(20) == 1
    assert db.get_job(jobs[0].job_id) is not None


def test_embeddings_store(db, jobs):
    db.upsert_jobs(jobs)
    db.set_status([jobs[2].job_id], JobStatus.BLACKLISTED)
    assert set(db.jobs_without_embedding("m")) == {jobs[0].job_id, jobs[1].job_id}
    vector = np.ones(4, dtype=np.float32)
    assert db.set_embeddings("m", [(jobs[0].job_id, vector), (jobs[2].job_id, vector)]) == 2
    ids, matrix = db.embedding_matrix("m")
    assert ids == [jobs[0].job_id] and matrix.shape == (1, 4)
    assert db.count_embeddings("m") == 2
    assert db.embedding_stamp("m")[0] == 2
    assert db.delete_embeddings([jobs[0].job_id]) == 1
    db.delete_jobs([jobs[2].job_id])
    assert db.count_embeddings("m") == 0


def test_reset_all(db, job):
    db.upsert_jobs([job])
    db.reset_all()
    assert db.count_jobs() == 0 and db.list_runs() == []


def test_timestamps_are_utc_aware(db, job):
    db.upsert_jobs([job])
    stored = db.get_job(job.job_id)
    assert stored.status_changed_at.tzinfo == timezone.utc
