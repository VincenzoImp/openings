import numpy as np
import yaml

from openings.embeddings import Embeddings, EmbeddingModel, job_text
from openings.models import JobStatus
from tests.conftest import make_job


def enabled_runtime(runtime, settings_dict):
    settings_dict["embeddings"] = {"enabled": True, "batch_size": 2}
    runtime.config_path.write_text(yaml.safe_dump(settings_dict))
    return runtime.config(reload=True)


def test_job_text_uses_title_company_location_and_description():
    text = job_text(make_job(description="x" * 5000))
    assert text.startswith("Backend Engineer\nAcme\nRemote\n")
    assert len(text) < 2100


def test_embed_backfill_search_and_similar(runtime, settings_dict, fake_embedding_model):
    config = enabled_runtime(runtime, settings_dict)
    db = runtime.db
    jobs = [
        make_job(),
        make_job(title="Data Engineer", job_url="https://linkedin.com/jobs/view/2"),
        make_job(title="Chef", company="Bistro", job_url="https://linkedin.com/jobs/view/3"),
    ]
    db.upsert_jobs(jobs)
    index = Embeddings(db, config)
    assert index.backfill() == 3
    assert index.backfill() == 0
    assert index.count() == 3

    hits = index.search(job_text(jobs[0]), n=2)
    assert hits[0][0] == jobs[0].job_id and hits[0][1] > 0.99
    similar = index.similar(jobs[0].job_id, n=5)
    assert jobs[0].job_id not in [job_id for job_id, _ in similar]
    assert len(similar) == 2

    db.set_status([jobs[2].job_id], JobStatus.BLACKLISTED)
    ids, matrix = db.embedding_matrix(index.model_name)
    assert len(ids) == 2 and matrix.shape[1] == 384
    assert index.search("", n=3) == []
    assert index.similar("missing", n=3) == []


def test_embed_jobs_skips_blacklisted(runtime, settings_dict, fake_embedding_model):
    config = enabled_runtime(runtime, settings_dict)
    job = make_job(status="blacklisted")
    runtime.db.upsert_jobs([job])
    assert Embeddings(runtime.db, config).embed_jobs([job]) == 0


def test_model_download_writes_files(tmp_path, monkeypatch):
    class FakeResponse:
        def __init__(self, payload: bytes):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            yield self.payload

    monkeypatch.setattr(
        "openings.embeddings.requests.get", lambda url, stream, timeout: FakeResponse(b"bytes")
    )
    model = EmbeddingModel(tmp_path / "models")
    model.ensure_downloaded()
    assert (tmp_path / "models" / "all-MiniLM-L6-v2" / "model.onnx").read_bytes() == b"bytes"
    assert (tmp_path / "models" / "all-MiniLM-L6-v2" / "tokenizer.json").is_file()
    # A second call does not download again.
    monkeypatch.setattr("openings.embeddings.requests.get", lambda *a, **k: 1 / 0)
    model.ensure_downloaded()


def test_runtime_reports_embedding_status(runtime, settings_dict, fake_embedding_model):
    assert runtime.embeddings is None and runtime.embeddings_status == "disabled"
    enabled_runtime(runtime, settings_dict)
    assert runtime.embeddings is not None
    assert runtime.embeddings_status == "ready"
    vector = runtime.embeddings.model.embed(["hello"])
    assert vector.shape == (1, 384) and np.isclose(np.linalg.norm(vector[0]), 1.0)
