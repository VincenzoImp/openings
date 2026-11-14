"""Duplicate candidates: labelled benchmark, signals, confidence tiers and one-job scoring."""

import pytest
from fastapi.testclient import TestClient

from duplicate_benchmark import (
    benchmark_jobs,
    grouped_pairs,
    legacy_groups,
    precision_recall,
    true_pairs,
)
from openings import duplicates
from openings.app import create_app
from openings.duplicate_signals import (
    apply_targets,
    compare_location,
    compare_title,
    job_features,
    normalize_company,
    reference_ids,
)
from openings.duplicates import (
    DEFAULT_MIN_CONFIDENCE,
    HIGH_CONFIDENCE,
    DuplicateIndex,
    score_pair,
)
from openings.errors import DomainError
from openings.workspace import Workspace, identity

TEXT = " ".join(
    f"Plan dependable warehouse routes and review supplier change number {index} with care."
    for index in range(12)
)
OTHER_TEXT = " ".join(
    f"Draft quarterly budgets and reconcile ledger entry number {index} for the audit."
    for index in range(12)
)


def features(**job):
    return job_features({"id": job.pop("id", "x"), "posting": TEXT, **job})


def groups_at(workspace, min_confidence):
    result = workspace.duplicate_jobs({"min_confidence": min_confidence, "limit": 100})
    assert result["total"] == len(result["items"])
    return result["items"]


# The labelled benchmark (duplicate_benchmark.py) seeds 122 jobs; the tests that use it
# are marked `performance` and run weekly and with `pytest -m performance`.
@pytest.fixture(scope="module")
def benchmark(tmp_path_factory):
    workspace = Workspace(tmp_path_factory.mktemp("benchmark") / "workspace.sqlite")
    records = {}
    for item in benchmark_jobs():
        job = workspace.ingest_job(item["job"])
        assert job["created"], item["job"]["url"]
        records[job["id"]] = item
        # Collection time is part of the fixture: a re-opened vacancy arrives months later.
        with workspace.db.transaction() as connection:
            connection.execute(
                "UPDATE jobs SET created_at=? WHERE id=?", (item["collected"], job["id"])
            )
    return workspace, records


@pytest.mark.performance
def test_benchmark_precision_and_recall(benchmark):
    """Pairwise precision and recall on the labelled benchmark (122 records, 51
    vacancies, 101 true duplicate pairs).

    Measured when this test was written:

    =============================  =========  ======
    grouping                       precision  recall
    =============================  =========  ======
    before confidence scores         0.523    0.802
    high tier (>= 0.85)              0.977    0.851
    default (>= 0.5)                 0.950    0.950
    every candidate (0)              0.428    1.000
    =============================  =========  ======

    The two false pairs of the high tier are the ``team!`` near-miss, which no text
    signal can separate. The default tier also shows the re-opened vacancy.
    """
    workspace, records = benchmark
    labels = {job_id: item["vacancy"] for job_id, item in records.items()}
    assert len(labels) >= 120 and len(true_pairs(labels)) == 101

    rows = [{"id": job_id, **item["job"]} for job_id, item in records.items()]
    before = legacy_groups(rows)
    old_precision, old_recall = precision_recall(before, labels)
    assert (round(old_precision, 3), round(old_recall, 3)) == (0.523, 0.802)

    measured = {
        threshold: precision_recall(
            [group["job_ids"] for group in groups_at(workspace, threshold)], labels
        )
        for threshold in (HIGH_CONFIDENCE, DEFAULT_MIN_CONFIDENCE, 0)
    }
    high_precision, high_recall = measured[HIGH_CONFIDENCE]
    assert high_precision >= 0.95, f"high-tier precision {high_precision:.3f}, required 0.95"
    assert high_recall >= old_recall, f"high-tier recall {high_recall:.3f} < {old_recall:.3f}"
    precision, recall = measured[DEFAULT_MIN_CONFIDENCE]
    assert recall >= old_recall, f"default recall {recall:.3f} < earlier {old_recall:.3f}"
    assert precision >= 0.9, f"default precision {precision:.3f}, earlier {old_precision:.3f}"
    assert measured[0][1] >= old_recall
    assert {key: (round(p, 3), round(r, 3)) for key, (p, r) in measured.items()} == {
        HIGH_CONFIDENCE: (0.977, 0.851),
        DEFAULT_MIN_CONFIDENCE: (0.95, 0.95),
        0: (0.428, 1.0),
    }
    # Nothing the earlier rule suggested is lost when every candidate is requested.
    everything = grouped_pairs(group["job_ids"] for group in groups_at(workspace, 0))
    assert grouped_pairs(before) <= everything


@pytest.mark.performance
def test_benchmark_near_misses_stay_out_of_the_high_tier(benchmark):
    workspace, records = benchmark
    wrong = {}
    for threshold in (HIGH_CONFIDENCE, DEFAULT_MIN_CONFIDENCE):
        kinds = set()
        for group in groups_at(workspace, threshold):
            assert group["confidence"] >= threshold
            vacancies = {records[job_id]["vacancy"] for job_id in group["job_ids"]}
            for job_id in group["job_ids"]:
                item = records[job_id]
                if item["near"] in vacancies:
                    kinds.add(item["kind"])
        wrong[threshold] = kinds
    # Another city, requisition, level or team, a re-opened vacancy and a colliding id
    # never reach the high tier; the undetectable team pair is the documented exception.
    assert wrong[HIGH_CONFIDENCE] == {"team!"}
    # A re-opened vacancy is shown for review at the default threshold, with the reason.
    assert wrong[DEFAULT_MIN_CONFIDENCE] == {"team!", "reopened"}
    reopened = next(
        group
        for group in groups_at(workspace, DEFAULT_MIN_CONFIDENCE)
        if any(records[job_id]["kind"] == "reopened" for job_id in group["job_ids"])
    )
    assert reopened["tier"] == "medium" and "posting_date" in reopened["reasons"]["conflicts"]


@pytest.mark.performance
def test_groups_are_ordered_by_confidence_with_reasons(benchmark):
    workspace, _records = benchmark
    groups = groups_at(workspace, 0)
    scores = [group["confidence"] for group in groups]
    assert scores == sorted(scores, reverse=True) and all(0 <= score <= 1 for score in scores)
    known = {
        "apply_target",
        "requisition_id",
        "posting_text",
        "near_identical_text",
        "similar_text",
        "company_title",
        "company",
        "similar_title",
        "title",
        "location",
        "seniority",
        "posting_date",
        "ambiguous",
    }
    for group in groups:
        assert group["tier"] == duplicates.confidence_tier(group["confidence"])
        assert group["signals"] == group["reasons"]["matched"] and group["signals"]
        assert set(group["signals"]) | set(group["reasons"]["conflicts"]) <= known
        for item in group["items"]:
            if item["id"] == group["reference_id"]:
                assert item["confidence"] is None and item["reasons"] is None
            else:
                assert 0 <= item["confidence"] <= 1
                assert set(item["reasons"]) == {"matched", "conflicts"}
    assert {group["tier"] for group in groups} == {"high", "medium", "low"}


def test_company_names_ignore_legal_corporate_and_country_suffixes():
    same = [
        "Norvane Robotics",
        "Norvane Robotics AG",
        "NORVANE ROBOTICS (Switzerland) AG",
        "Norvane Robotics Deutschland GmbH",
        "Norvane Robotics Group",
        "Norvane Robotics S.p.A.",
        "The Norvane Robotics Holding",
    ]
    assert {normalize_company(name) for name in same} == {"norvane robotics"}
    assert normalize_company("Société Générique Sàrl") == "societe generique"
    assert normalize_company("Switzerland") == "switzerland"
    assert normalize_company("Norvane Labs") != normalize_company("Norvane Robotics")


def test_requisition_ids_come_from_titles_and_labelled_text():
    assert reference_ids("Backend Engineer (R-48213)", "") == {"48213"}
    assert reference_ids("Backend Engineer - JR0020931", "") == {"20931"}
    assert reference_ids("Summer Internship 2026", "Reference: 2026 salary survey") == set()
    assert reference_ids("Engineer", "Requisition ID: R-48213\nJob ID 48213") == {"48213"}
    assert reference_ids("Ingenieur", "Referenznummer: LF-5521") == {"LF5521"}
    assert reference_ids("Gestionnaire", "Référence : FR-2291") == {"FR2291"}
    assert reference_ids("Ingegnere", "Rif. 2291-IT") == {"2291IT"}
    assert reference_ids("Engineer", "We reference 12 projects and job 3 of 5.") == set()


def test_apply_targets_recognise_ats_postings_and_url_forms():
    assert apply_targets("https://boards.greenhouse.io/norvane/jobs/7700101") == {
        "greenhouse:7700101"
    }
    assert apply_targets("https://norvane.example/careers/backend?gh_jid=7700101&utm_source=x") == {
        "greenhouse:7700101"
    }
    assert apply_targets("https://jobs.lever.co/norvane/abc-123/apply") == {"lever:abc-123"}
    assert apply_targets(
        "https://tessolar.wd3.myworkdayjobs.com/en-US/careers/job/Berlin/Product-Manager_JR-20931-1"
    ) == {"workday:tessolar:JR-20931"}
    assert apply_targets("http://www.solvanta.example/careers/data-manager/") == apply_targets(
        "https://solvanta.example/careers/data-manager?utm_campaign=spring"
    )
    assert apply_targets("https://solvanta.example/") == set() == apply_targets("not a url")


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("Zurich, Switzerland", "Zürich, ZH, Switzerland", "agree"),
        ("Geneva, Switzerland", "Genf, Schweiz", "agree"),
        ("Berlin / Munich", "München, Deutschland", "agree"),
        ("Frankfurt am Main", "Frankfurt, Germany", "agree"),
        ("Remote", "Remote", "agree"),
        ("Zurich, Switzerland", "Lausanne, Switzerland", "conflict"),
        ("Remote, Germany", "Remote, France", "conflict"),
        ("Vienna, Austria", "Vienna, United States", "conflict"),
        ("Remote", "Berlin, Germany", None),
        ("Remote (Berlin)", "Munich", None),
        ("Switzerland", "Zurich, Switzerland", None),
        ("", "Zurich", None),
    ],
)
def test_locations_agree_conflict_or_stay_unknown(first, second, expected):
    a, b = features(location=first), features(location=second)
    assert compare_location(a, b) == compare_location(b, a) == expected


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("Backend Engineer", "Backend Engineer (m/w/d)", "same"),
        ("Backend Engineer", "Backend Engineer – Zurich (80-100%)", "same"),
        ("Backend Engineer", "Backend Engineer (R-48213)", "same"),
        ("Backend Engineer", "Senior Backend Engineer", "seniority"),
        ("Embedded Engineer II", "Embedded Engineer III", "seniority"),
        ("Backend Engineer", "Backend Engineer Payments", "similar"),
        ("Backend Engineer", "Data Engineer", None),
    ],
)
def test_titles_are_compared_without_decoration(first, second, expected):
    a = features(title=first, location="Zurich, Switzerland")
    b = features(title=second, location="Zurich, Switzerland")
    assert compare_title(a, b) == compare_title(b, a) == expected


def test_company_and_title_alone_never_prove_a_duplicate():
    job = {"title": "Backend Engineer", "company": "Norvane Robotics"}
    place = {"location": "Zurich, Switzerland"}
    same_text = score_pair(features(**job, **place), features(**job, **place))
    assert same_text.score >= HIGH_CONFIDENCE and "posting_text" in same_text.matched

    no_text = score_pair(features(**job, posting=""), features(**job, posting=""))
    assert no_text.score < DEFAULT_MIN_CONFIDENCE and no_text.matched == ("company_title",)
    with_place = score_pair(features(**job, **place, posting=""), features(**job, **place))
    assert DEFAULT_MIN_CONFIDENCE <= with_place.score < HIGH_CONFIDENCE
    other_text = score_pair(features(**job, **place), features(**job, **place, posting=OTHER_TEXT))
    assert other_text.score < DEFAULT_MIN_CONFIDENCE and other_text.conflicts == ("posting_text",)

    other_city = score_pair(features(**job, **place), features(**job, location="Lausanne"))
    assert other_city.score < DEFAULT_MIN_CONFIDENCE and other_city.conflicts == ("location",)
    other_requisition = score_pair(
        features(**job, **place, posting=TEXT + " Requisition ID: R-48213"),
        features(**job, **place, posting=TEXT + " Requisition ID: R-48299"),
    )
    assert other_requisition.score < DEFAULT_MIN_CONFIDENCE
    assert other_requisition.conflicts == ("requisition_id",)
    other_posting = score_pair(
        features(**job, **place, url="https://boards.greenhouse.io/norvane/jobs/7700101"),
        features(**job, **place, url="https://boards.greenhouse.io/norvane/jobs/7700102"),
    )
    assert other_posting.score < DEFAULT_MIN_CONFIDENCE
    assert other_posting.conflicts == ("apply_target",)


def test_identifiers_join_records_across_company_names():
    employer = features(
        title="Robotics Software Engineer",
        company="Norvane Robotics",
        location="Zurich, Switzerland",
        url="https://boards.greenhouse.io/norvane/jobs/7700901",
    )
    board = features(
        title="Robotics Software Engineer (m/f/d)",
        company="Glimmerpath",
        location="Genf",
        posting=OTHER_TEXT,
        urls=["https://boards.greenhouse.io/norvane/jobs/7700901?utm_source=board"],
    )
    evidence = score_pair(employer, board)
    # A shared apply target outweighs a different location and different text.
    assert evidence.score >= HIGH_CONFIDENCE and evidence.matched[0] == "apply_target"
    assert set(evidence.conflicts) == {"location", "posting_text"}

    # A number shared by unrelated employers is not a requisition match on its own.
    first = features(title="Backend Engineer", company="Norvane", posting=TEXT + " Job ID: 48213")
    second = features(
        title="Hydrologist", company="Brekkvann", posting=OTHER_TEXT + " Job ID: 48213"
    )
    collision = score_pair(first, second)
    assert collision.matched == ("requisition_id",) and collision.score < DEFAULT_MIN_CONFIDENCE


def test_a_record_matching_two_different_vacancies_is_ambiguous():
    job = {"title": "Site Reliability Engineer", "company": "Tessolar", "location": "Berlin"}
    index = DuplicateIndex(
        [
            features(id="first", **job, posting=TEXT + " Requisition ID: JR-20988"),
            features(id="second", **job, posting=TEXT + " Requisition ID: JR-20990"),
            features(id="copy", **job, posting=TEXT + " Apply on the board."),
        ]
    )
    assert index.groups(HIGH_CONFIDENCE) == []
    assert index.evidence("copy", "first").conflicts == ("ambiguous",)
    assert index.evidence("copy", "first").score == duplicates.AMBIGUOUS_MATCH
    # The copy is shown with one requisition; the two requisitions are never joined.
    (group,) = index.groups(DEFAULT_MIN_CONFIDENCE)
    assert group["ids"] == ["first", "copy"] and group["conflicts"] == ["ambiguous"]
    assert group["confidence"] == duplicates.AMBIGUOUS_MATCH
    (everything,) = index.groups(0)
    assert everything["ids"] == ["first", "second", "copy"] and everything["confidence"] < 0.2
    assert everything["conflicts"] == ["ambiguous", "requisition_id"]


def test_large_blocks_stay_bounded_and_complete():
    index = DuplicateIndex(
        features(
            id=f"job-{number:04d}",
            title="Software Engineer",
            company="Norvane Robotics",
            location=f"City{number % 7}",
            posting=f"{TEXT} Team number {number}.",
        )
        for number in range(400)
    )
    # 400 records share a company and title: 79,800 pairs if every pair were scored.
    assert len(index.links()) < 400 * 4
    (group,) = index.groups(0)
    assert len(group["ids"]) == 400


@pytest.mark.performance
def test_one_job_is_scored_against_its_blocks_only(benchmark, monkeypatch):
    workspace, records = benchmark
    by_vacancy = {}
    for job_id, item in records.items():
        by_vacancy.setdefault(item["vacancy"], []).append(job_id)
    scored = []
    original = duplicates.score_pair
    monkeypatch.setattr(duplicates, "score_pair", lambda *args: scored.append(1) or original(*args))
    before = workspace.db.one("SELECT count(*) n, sum(version) v FROM jobs")

    archived = by_vacancy["backend-zurich"]
    found = workspace.likely_duplicates(archived[0])
    assert {item["job_id"] for item in found} == set(archived[1:])
    assert all(item["tier"] == "high" for item in found)
    assert found[0]["reasons"]["matched"][0] == "apply_target"
    assert len(scored) < len(records) / 4

    # The same posting seen on another board, before it is ingested.
    item = next(item for item in benchmark_jobs() if item["vacancy"] == "data-bern")
    incoming = {
        **item["job"],
        "url": "https://www.glassdoor.com/job-listing/data-engineer-JV_991.htm",
        "company": "Alpenquell Analytics AG",
        "source_key": "glassdoor:991",
        "metadata": {"source": "glassdoor", "date_posted": "2026-03-06"},
    }
    found = workspace.likely_duplicates(incoming)
    assert [records[match["job_id"]]["vacancy"] for match in found] == ["data-bern"] * 3
    assert found[0]["confidence"] >= HIGH_CONFIDENCE and found[0]["tier"] == "high"
    assert {match["job_id"] for match in workspace.likely_duplicates(incoming, 0, 50)} > {
        match["job_id"] for match in found
    }
    assert workspace.likely_duplicates({"title": "Beekeeper", "company": "Nowhere"}) == []
    assert workspace.db.one("SELECT count(*) n, sum(version) v FROM jobs") == before
    with pytest.raises(DomainError):
        workspace.likely_duplicates("absent")


def test_features_are_read_again_only_for_changed_jobs(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "workspace.sqlite")
    computed = []
    original = identity.job_features
    monkeypatch.setattr(
        identity, "job_features", lambda job: computed.append(job["id"]) or original(job)
    )
    # Each new job is read once, for its likely-duplicate signal at ingest.
    jobs = [
        workspace.ingest_job(
            {
                "url": f"https://example.test/{source}",
                "title": "Fleet Analyst",
                "company": "Fjordlane Shipping",
                "location": "Copenhagen",
                "posting": TEXT,
            }
        )
        for source in ("one", "two", "three")
    ]
    assert sorted(computed) == sorted(job["id"] for job in jobs)
    assert jobs[0]["signals"]["duplicate"] is None
    assert jobs[2]["signals"]["duplicate"]["job_id"] in {jobs[0]["id"], jobs[1]["id"]}
    computed.clear()
    assert workspace.duplicate_jobs({})["items"][0]["size"] == 3
    assert computed == []
    jobs = [workspace.get_job(job["id"]) for job in jobs]
    assert workspace.duplicate_jobs({"min_confidence": 0})["total"] == 1
    assert computed == []

    workspace.update_job(
        jobs[1]["id"], {"expected_version": jobs[1]["version"], "location": "Oslo, Norway"}
    )
    group = workspace.duplicate_jobs({})["items"][0]
    assert computed == [jobs[1]["id"]] and jobs[1]["id"] not in group["job_ids"]
    workspace.forget_job(jobs[2]["id"], jobs[2]["version"])
    assert workspace.duplicate_jobs({})["total"] == 0
    merged = workspace.duplicate_jobs({"min_confidence": 0})["items"][0]
    assert set(merged["job_ids"]) == {jobs[0]["id"], jobs[1]["id"]}
    assert merged["reasons"]["conflicts"] == ["location"]


def test_confidence_tiers_and_filter_over_rest(tmp_path):
    app = create_app(tmp_path / "rest.sqlite", start_worker=False)
    with TestClient(app) as client:
        owner = client.post("/api/v1/auth/setup", json={"password": "synthetic-password"}).json()
        client.headers["X-CSRF-Token"] = owner["csrf_token"]
        for path, location, text in (
            ("one", "Basel, Switzerland", TEXT),
            ("two", "Basel", TEXT + " Imported from the employer."),
            ("three", "Lausanne, Switzerland", TEXT),
            ("four", "Basel, Switzerland", OTHER_TEXT),
        ):
            created = client.post(
                "/api/v1/jobs",
                json={
                    "url": f"https://example.test/{path}",
                    "title": "QA Manager",
                    "company": "Haldrin Biotech",
                    "location": location,
                    "posting": text,
                },
            )
            assert created.status_code == 200
        default = client.get("/api/v1/jobs/duplicates").json()
        assert default["min_confidence"] == 0.5 and default["tiers"] == {
            "high": 0.85,
            "medium": 0.5,
        }
        assert [(group["tier"], group["size"]) for group in default["items"]] == [("high", 2)]
        high = client.get("/api/v1/jobs/duplicates", params={"min_confidence": 0.85}).json()
        assert high["items"] == default["items"]
        everything = client.get("/api/v1/jobs/duplicates", params={"min_confidence": 0}).json()
        assert [(group["tier"], group["size"]) for group in everything["items"]] == [("low", 4)]
        assert set(everything["items"][0]["reasons"]["conflicts"]) == {"location", "posting_text"}
        for invalid in ("1.5", "-0.1", "high"):
            response = client.get("/api/v1/jobs/duplicates", params={"min_confidence": invalid})
            assert response.status_code == 422
        schema = client.get("/api/openapi.json").json()
        parameters = schema["paths"]["/api/v1/jobs/duplicates"]["get"]["parameters"]
        assert "min_confidence" in {parameter["name"] for parameter in parameters}

    assert app.state.workspace.duplicate_jobs({"min_confidence": 0.85}) == high


def test_a_background_warm_up_spares_the_first_request(tmp_path, monkeypatch):
    workspace = Workspace(tmp_path / "workspace.sqlite")
    for source in ("one", "two"):
        workspace.ingest_job(
            {
                "url": f"https://example.test/{source}",
                "title": "Fleet Analyst",
                "company": "Fjordlane Shipping",
                "location": "Copenhagen",
                "posting": TEXT,
            }
        )
    workspace.warm_duplicates().join(timeout=10)
    computed = []
    original = identity.job_features
    monkeypatch.setattr(
        identity, "job_features", lambda job: computed.append(job["id"]) or original(job)
    )
    assert workspace.duplicate_jobs({})["items"][0]["size"] == 2
    assert computed == []
