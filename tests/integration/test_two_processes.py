"""The scheduler and the web process open the same file with separate connections."""

import threading

from openings.db import JobDatabase
from openings.models import JobStatus
from tests.conftest import make_job


def test_blacklist_from_one_connection_is_honoured_by_the_other(data_dir):
    scheduler_db = JobDatabase(data_dir / "db" / "openings.db")
    web_db = JobDatabase(data_dir / "db" / "openings.db")
    job = make_job()
    scheduler_db.upsert_jobs([job])
    web_db.set_status([job.job_id], JobStatus.BLACKLISTED)
    result = scheduler_db.upsert_jobs([make_job(description="fresh")])
    assert result.skipped_blacklisted == 1
    assert web_db.get_job(job.job_id).description == "Python services with PostgreSQL."
    scheduler_db.close()
    web_db.close()


def test_concurrent_writers_do_not_corrupt_state(data_dir):
    jobs = [
        make_job(title=f"Job {i}", job_url=f"https://linkedin.com/jobs/view/{i}")
        for i in range(200)
    ]
    writer_a = JobDatabase(data_dir / "db" / "openings.db")
    writer_b = JobDatabase(data_dir / "db" / "openings.db")
    errors: list[Exception] = []

    def ingest():
        try:
            for start in range(0, 200, 20):
                writer_a.upsert_jobs(jobs[start : start + 20])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def curate():
        try:
            for job in jobs[::7]:
                writer_b.set_status([job.job_id], JobStatus.SHORTLISTED)
                writer_b.add_labels([job.job_id], ["seen"])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=ingest), threading.Thread(target=curate)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == []
    assert writer_a.count_jobs() == 200
    shortlisted = writer_b.query_jobs(
        __import__("openings.db", fromlist=["JobQuery"]).JobQuery(
            statuses=("shortlisted",), limit=1000
        )
    )[1]
    assert shortlisted <= len(jobs[::7])
    writer_a.close()
    writer_b.close()
