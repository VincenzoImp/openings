import zipfile
from io import BytesIO

import pytest

from openings.application.jobs import VectorStoreUnavailableError
from openings.application.models import AddJobCommand
from openings.db import JobQuery
from openings.models import AttachmentKind, JobStatus, NoteKind
from tests.conftest import make_job


def add(service, **overrides):
    fields = {"title": "Backend Engineer", "company": "Acme", "location": "Remote"}
    fields.update(overrides)
    return service.add_job(AddJobCommand(**fields))


def test_add_job_scores_labels_notes_and_defaults_to_shortlisted(service):
    result = add(service, description="Python and PostgreSQL", labels=("x",), note="hello")
    assert result.success and result.message == "created"
    detail = service.get_job_detail(result.job_ids[0])
    assert detail.job.status is JobStatus.SHORTLISTED
    assert detail.job.relevance_score == 35
    assert detail.labels == ["x"] and detail.notes[0].body == "hello"
    assert detail.explain.score == 35
    assert [event.kind.value for event in detail.events][:2] == ["ingested", "status"]


def test_add_job_on_existing_merges_fields_and_keeps_status_and_score(service):
    first = add(
        service, description="Python and PostgreSQL", job_url="https://linkedin.com/jobs/view/1"
    )
    service.set_status(first.job_ids, JobStatus.APPLIED)
    second = add(service, job_url="https://linkedin.com/jobs/view/1", job_level="senior")
    assert second.message == "updated" and second.job_ids == first.job_ids
    job = service.get_job(first.job_ids[0])
    assert job.status is JobStatus.APPLIED
    assert job.description == "Python and PostgreSQL"  # not overwritten by nothing
    assert job.job_level == "senior"
    assert job.relevance_score == 35


def test_add_job_refuses_blacklisted_identity(service):
    created = add(service)
    service.blacklist_jobs(created.job_ids)
    refused = add(service)
    assert refused.success is False and "blacklisted" in refused.message
    assert refused.job_ids == created.job_ids


def test_add_job_requires_title_and_company(service):
    assert service.add_job(AddJobCommand(title=" ", company="x", location="")).success is False


def test_update_job_rescores(service):
    job_id = add(service, description="nothing relevant").job_ids[0]
    assert service.get_job(job_id).relevance_score == 25
    updated = service.update_job(job_id, {"description": "python postgresql", "bogus": 1})
    assert updated.relevance_score == 35
    assert service.update_job("missing", {"title": "x"}) is None


def test_blacklist_keeps_material_and_restore_returns_previous_status(service, data_dir):
    job_id = add(service).job_ids[0]
    service.set_status([job_id], JobStatus.APPLIED)
    service.add_attachment(job_id, kind=AttachmentKind.CV, filename="cv.pdf", content=b"%PDF")
    service.blacklist_jobs([job_id], note="closed")
    assert service.get_job(job_id).status is JobStatus.BLACKLISTED
    assert service.list_jobs(JobQuery()).total == 0
    assert service.list_jobs(JobQuery(statuses=("blacklisted",))).total == 1
    assert len(service.get_job_detail(job_id).attachments) == 1
    restored = service.unblacklist_jobs([job_id, "nope"])
    assert restored.affected_count == 1
    assert service.get_job(job_id).status is JobStatus.APPLIED


def test_delete_jobs_removes_files(service, data_dir):
    job_id = add(service).job_ids[0]
    service.add_attachment(job_id, kind=AttachmentKind.CV, filename="cv.pdf", content=b"%PDF")
    assert (data_dir / "attachments" / job_id).is_dir()
    assert service.delete_jobs([job_id]).affected_count == 1
    assert not (data_dir / "attachments" / job_id).exists()


def test_merge_jobs_moves_files(service, data_dir):
    primary = add(service, job_url="https://linkedin.com/jobs/view/1").job_ids[0]
    other = add(
        service, title="Backend Engineer (mirror)", job_url="https://ch.indeed.com/viewjob?jk=1"
    ).job_ids[0]
    attachment = service.add_attachment(
        other, kind=AttachmentKind.CV, filename="cv.pdf", content=b"%PDF"
    )
    result = service.merge_jobs(primary, [other])
    assert result.success and result.affected_count == 1
    assert (data_dir / "attachments" / primary / attachment.stored_name).is_file()
    assert not (data_dir / "attachments" / other).exists()
    assert service.get_job(other) is None
    assert service.merge_jobs("missing", [primary]).success is False


def test_notes_and_attachments_lifecycle(service):
    job_id = add(service).job_ids[0]
    note = service.add_note(job_id, NoteKind.QA, "Because.", "Why?")
    assert service.update_note(job_id, note.id, body="Better.").body == "Better."
    with pytest.raises(ValueError):
        service.add_note(job_id, NoteKind.NOTE, "   ")
    with pytest.raises(ValueError):
        service.update_note(job_id, note.id, body=" ")
    assert service.delete_note(job_id, note.id) is True
    assert service.delete_note(job_id, note.id) is False

    attachment = service.add_attachment(
        job_id, kind=AttachmentKind.CV, filename="../cv.pdf", content=b"%PDF", note="v1"
    )
    assert attachment.size_bytes == 4 and attachment.filename == "../cv.pdf"
    found = service.get_attachment_file(job_id, attachment.id)
    assert found and found[1].read_bytes() == b"%PDF"
    renamed = service.update_attachment(job_id, attachment.id, kind=AttachmentKind.OTHER, note="v2")
    assert renamed.kind is AttachmentKind.OTHER
    entries, total = service.list_attachments(kind=AttachmentKind.OTHER)
    assert total == 1 and entries[0].job_title == "Backend Engineer"
    assert service.delete_attachment(job_id, attachment.id) is True
    assert service.get_attachment_file(job_id, attachment.id) is None
    assert (
        service.add_attachment("0" * 64, kind=AttachmentKind.CV, filename="x", content=b"1") is None
    )


def test_bundle_contains_posting_notes_and_files(service):
    job_id = add(service, description="Body text").job_ids[0]
    service.add_note(job_id, NoteKind.QA, "Because.", "Why?")
    service.add_attachment(job_id, kind=AttachmentKind.CV, filename="cv.pdf", content=b"%PDF")
    service.add_attachment(job_id, kind=AttachmentKind.OTHER, filename="cv.pdf", content=b"%PDF2")
    content, filename = service.build_bundle(job_id)
    assert filename.startswith("openings-acme-backend-engineer")
    with zipfile.ZipFile(BytesIO(content)) as archive:
        names = set(archive.namelist())
        assert {"posting.md", "notes.md", "timeline.md", "job.json"} <= names
        assert "attachments/cv.pdf" in names and "attachments/cv (2).pdf" in names
        assert "Why?" in archive.read("notes.md").decode()
    assert service.build_bundle("missing") is None


def test_list_sources_counts_by_source_and_company(service, settings_dict, runtime):
    settings_dict["sources"]["companies"] = [{"name": "Acme", "ats": "greenhouse", "slug": "acme"}]
    import yaml

    runtime.config_path.write_text(yaml.safe_dump(settings_dict))
    runtime.config(reload=True)
    add(service, source="greenhouse", job_url="https://boards.greenhouse.io/acme/jobs/1")
    add(
        service,
        title="Other",
        company="Acme",
        source="linkedin",
        job_url="https://linkedin.com/jobs/view/9",
    )
    sources = {source.name: source for source in service.list_sources()}
    assert sources["Acme"].active_jobs == 1
    assert sources["jobspy"].active_jobs == 1
    assert sources["manual"].active_jobs == 0


def test_settings_summary_and_run_status(service, data_dir):
    summary = service.settings_summary()
    assert summary["scoring"]["notify_threshold"] == 20
    assert summary["embeddings"]["status"] == "disabled"
    assert service.run_status() == {"running": False, "run": None, "requested": False}
    status = service.request_run()
    assert status["requested"] is True and (data_dir / "run-now").is_file()


def test_search_similar_unavailable_when_disabled(service):
    with pytest.raises(VectorStoreUnavailableError):
        service.search_similar("python")


def test_search_similar_with_fake_model(runtime, settings_dict, fake_embedding_model):
    import yaml

    settings_dict["embeddings"] = {"enabled": True}
    runtime.config_path.write_text(yaml.safe_dump(settings_dict))
    runtime.config(reload=True)
    service = runtime.service
    a = add(service, title="Python Backend Engineer", description="python").job_ids[0]
    b = add(service, title="Sales Lead", company="Beta", description="sales").job_ids[0]
    hits = service.search_similar("Python Backend Engineer\nAcme\nRemote\npython", n_results=2)
    assert [hit.job.job_id for hit in hits][0] == a
    assert hits[0].similarity > hits[1].similarity
    similar = service.search_similar(job_id=a, n_results=5)
    assert [hit.job.job_id for hit in similar] == [b]
    service.blacklist_jobs([b])
    assert service.search_similar(job_id=a) == []


def test_export_pages_everything_and_counts_material(service):
    for index in range(3):
        add(service, title=f"Job {index}", job_url=f"https://linkedin.com/jobs/view/{index}")
    exported = service.export_jobs(query=JobQuery(limit=0), fmt="json")
    assert exported.row_count == 3 and exported.total == 3
    csv_export = service.export_jobs(query=JobQuery(limit=2))
    assert csv_export.row_count == 2 and csv_export.total == 3
    assert b"attachments_count" in csv_export.content


def test_cleanup_dry_runs(service):
    job_id = add(service, status=JobStatus.NEW).job_ids[0]
    assert service.delete_below_score(100, dry_run=True).affected_count == 1
    assert service.get_job(job_id) is not None
    assert service.delete_stale(1, dry_run=True).affected_count == 0
    assert service.delete_below_score(100).affected_count == 1


def test_preview_and_run_cleanup(service):
    add(service)
    assert service.preview_cleanup().protected == 1
    assert service.run_cleanup().total_deleted == 0


def test_labels_rename_delete(service):
    job_id = add(service, labels=("old",)).job_ids[0]
    assert service.rename_label("old", "new").affected_count == 1
    assert service.get_job_detail(job_id).labels == ["new"]
    assert service.delete_label("new").affected_count == 1


def test_make_job_helper_matches_model(job):
    assert job.posting_key == "linkedin:1000001"
    assert make_job(job_url=None).posting_key is None
