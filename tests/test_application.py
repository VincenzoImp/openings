import pytest

from openings.application.attachments import AttachmentStore, AttachmentTooLarge, safe_filename
from openings.application.models import AddJobCommand
from openings.database import JobQuery
from openings.models import AttachmentKind, JobStatus, NoteKind


def test_safe_filename_strips_paths():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("my cv (final).pdf") == "my_cv_final_.pdf"
    assert safe_filename("") == "attachment"


def test_attachment_store_round_trip(tmp_path):
    store = AttachmentStore(tmp_path, max_bytes=10)
    job_id = "a" * 64
    stored, digest, size = store.save(job_id, "cv.pdf", b"12345")
    assert store.path(job_id, stored).read_bytes() == b"12345"
    assert size == 5 and len(digest) == 64
    with pytest.raises(AttachmentTooLarge):
        store.save(job_id, "big.pdf", b"x" * 11)
    with pytest.raises(ValueError):
        store.save(job_id, "empty", b"")
    store.delete(job_id, stored)
    assert not (tmp_path / job_id).exists()


def test_add_job_scores_shortlists_labels_and_notes(service):
    result = service.add_job(
        AddJobCommand(
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            description="Python and PostgreSQL",
            labels=("seed",),
            note="found by hand",
        )
    )
    assert result.success and result.message == "created"
    detail = service.get_job_detail(result.job_ids[0])
    assert detail.job.status is JobStatus.SHORTLISTED
    assert detail.job.source == "manual"
    assert detail.explain.score == 35
    assert detail.labels == ["seed"]
    assert [note.body for note in detail.notes] == ["found by hand"]
    assert [event.kind.value for event in detail.events] == ["ingested", "status", "label", "note"]


def test_add_job_updates_existing_and_refuses_blacklisted(service):
    first = service.add_job(AddJobCommand(title="T", company="C", location="L"))
    second = service.add_job(
        AddJobCommand(title="T", company="C", location="L", description="more")
    )
    assert second.message == "updated"
    service.blacklist_jobs(first.job_ids)
    third = service.add_job(AddJobCommand(title="T", company="C", location="L"))
    assert third.success is False
    assert "blacklisted" in third.message


def test_add_job_requires_title_and_company(service):
    assert service.add_job(AddJobCommand(title=" ", company="C", location="L")).success is False


def test_attachments_are_removed_with_the_job(service, env):
    job_id = service.add_job(AddJobCommand(title="T", company="C", location="L")).job_ids[0]
    attachment = service.add_attachment(
        job_id, kind=AttachmentKind.CV, filename="cv.pdf", content=b"pdf"
    )
    found = service.get_attachment_file(job_id, attachment.id)
    assert found is not None and found[1].is_file()
    service.delete_jobs([job_id])
    assert not (env / "attachments" / job_id).exists()


def test_notes_require_body(service):
    job_id = service.add_job(AddJobCommand(title="T", company="C", location="L")).job_ids[0]
    with pytest.raises(ValueError):
        service.add_note(job_id, NoteKind.NOTE, "   ")
    note = service.add_note(job_id, NoteKind.QA, "Because.", "Why?")
    assert service.delete_note(job_id, note.id) is True


def test_list_sources_counts_active_jobs(service):
    service.add_job(AddJobCommand(title="T", company="C", location="L"))
    sources = {source.name: source for source in service.list_sources()}
    assert sources["manual"].active_jobs == 1
    assert sources["jobspy"].enabled is False


def test_export_csv_and_json_and_full_export(service):
    for index in range(3):
        service.add_job(AddJobCommand(title=f"T{index}", company="C", location="L", labels=("x",)))
    csv_result = service.export_jobs(query=JobQuery(limit=2), fmt="csv")
    assert csv_result.row_count == 2 and csv_result.total == 3
    assert csv_result.content.decode().startswith("job_id,title")
    full = service.export_jobs(query=JobQuery(limit=0), fmt="json")
    assert full.row_count == 3
    assert b'"labels": "x"' in full.content


def test_cleanup_preview_and_run_respect_protection(service):
    job_id = service.add_job(
        AddJobCommand(title="T", company="C", location="L", status=JobStatus.NEW)
    ).job_ids[0]
    service.set_status([job_id], JobStatus.APPLIED)
    preview = service.preview_cleanup()
    assert preview.protected == 1
    assert service.run_cleanup().total_deleted == 0
