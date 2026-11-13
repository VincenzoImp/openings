"""A large synthetic workspace for the performance budget of the dashboard.

The dashboard's performance budget is measured on 5,000 jobs
and 500 applications. Writing them one by one through the services takes
minutes, so this writes the same rows the services would in one transaction:
jobs with their identities and observations, applications in every stage with
their stored Ready step, current CV and letter revisions with a PDF sharing one
blob, employer responses and the events of each stage change. Everything is
fictional.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from openings.common import new_id

PDF = b"%PDF-1.4\nSynthetic large-workspace PDF"
# The text a CV or letter derives from its source: about 2,500 characters.
DOCUMENT_TEXT = "\n".join(
    f"• Built reliable data services for team {index}, measured and documented."
    for index in range(32)
)
TITLES = (
    "Data Engineer",
    "Senior Backend Engineer",
    "Platform Engineer",
    "Analytics Engineer",
    "Machine Learning Engineer",
    "Software Engineer",
    "Site Reliability Engineer",
    "Frontend Developer",
)
COMPANIES = ("Example Labs", "Sample Grid", "Northstar Labs", "Fjord Analytics", "Cedar Systems")
LOCATIONS = ("Zurich, Switzerland", "Remote, Europe", "Basel, Switzerland", "Geneva, Switzerland")
STAGES = ("draft", "draft", "applied", "applied", "interview", "offer", "closed")


def stamp(moment):
    return moment.isoformat(timespec="microseconds")


def seed_signals(workspace):
    """Store ingest signals for every job without them, in bulk.

    ``SignalService.backfill`` computes them one job at a time, which takes
    seconds per thousand jobs. The large jobs share eight posting texts, so each
    text is analysed once and its signals stored for every job that uses it; one
    job in fifty is the likely duplicate of the job before it.
    """
    from openings.job_signals import FORMAT
    from openings.language_signals import text_signals

    found, rows, previous = {}, [], None
    with workspace.db.transaction() as conn:
        for index, (job_id, title, posting, version) in enumerate(
            conn.execute(
                "SELECT id,title,posting,content_version FROM jobs WHERE id NOT IN "
                "(SELECT job_id FROM job_signals) ORDER BY created_at,id"
            ).fetchall()
        ):
            key = (title.rsplit(" ", 1)[0], posting)
            if key not in found:
                found[key] = text_signals(*key)
            signals = found[key]
            duplicate = previous if index % 50 == 49 else None
            rows.append(
                (
                    job_id,
                    FORMAT,
                    version,
                    signals["language"],
                    signals["language_confidence"],
                    json.dumps(signals["required"]),
                    json.dumps(signals["welcome"]),
                    duplicate,
                    0.9 if duplicate else None,
                    stamp(datetime.now(UTC)),
                )
            )
            previous = job_id
        conn.executemany(
            "INSERT INTO job_signals(job_id,format,content_version,language,language_confidence,"
            "required,welcome,duplicate_checked,duplicate_of,duplicate_confidence,computed_at) "
            "VALUES(?,?,?,?,?,?,?,1,?,?,?)",
            rows,
        )


def seed_large(workspace, jobs, applications, sources=0):
    """Write ``jobs`` jobs and ``applications`` applications (on the first jobs).

    With ``sources``, that many company sources are created and four jobs in five
    are first observed by one of them, so source yield has something to count.
    """
    now = datetime.now(UTC)
    sha = hashlib.sha256(PDF).hexdigest()
    with workspace.db.transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO blobs(sha256,content,size) VALUES(?,?,?)",
            (sha, PDF, len(PDF)),
        )
        source_ids = [new_id() for _ in range(sources)]
        conn.executemany(
            "INSERT INTO sources(id,name,kind,config,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            [
                (
                    source_id,
                    f"{COMPANIES[index % len(COMPANIES)]} board {index}",
                    "greenhouse",
                    json.dumps({"board": f"synthetic{index}"}),
                    stamp(now),
                    stamp(now),
                )
                for index, source_id in enumerate(source_ids)
            ],
        )
        job_rows, identities, postings = [], [], []
        for index in range(jobs):
            job_id, created = new_id(), stamp(now - timedelta(minutes=jobs - index))
            url = f"https://example.test/large/{index}"
            title = TITLES[index % len(TITLES)]
            job_rows.append(
                (
                    job_id,
                    f"{title} {index:04d}",
                    COMPANIES[index % len(COMPANIES)],
                    LOCATIONS[index % len(LOCATIONS)],
                    url,
                    f"{title} for a synthetic team.\n\nResponsibilities\nBuild reliable services.",
                    "saved" if index < applications else ("dismissed" if index % 3 else "inbox"),
                    json.dumps({"source": "linkedin"}),
                    created,
                    created,
                )
            )
            identities.append(("url:" + url, job_id))
            source = source_ids[index % sources] if sources and index % 5 else None
            postings.append(
                (new_id(), job_id, source, "url:" + url, url, "{}", sha, created, created)
            )
        conn.executemany(
            "INSERT INTO jobs(id,title,company,location,url,posting,triage,metadata,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            job_rows,
        )
        conn.executemany("INSERT INTO job_identities(identity,job_id) VALUES(?,?)", identities)
        conn.executemany(
            "INSERT INTO postings(id,job_id,source_id,identity,url,payload,content_hash,first_seen_at,"
            "last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)",
            postings,
        )
        for index in range(applications):
            job_id = job_rows[index][0]
            status = STAGES[index % len(STAGES)]
            app_id = new_id()
            created = now - timedelta(days=60, minutes=index)
            applied = now - timedelta(days=5 + index % 55) if status != "draft" else None
            ready = status == "draft" and index % 2 == 0
            outcome = (
                ("rejected", "no_response", "not_pursued")[index % 3]
                if status == "closed"
                else None
            )
            if outcome == "not_pursued":
                applied = None
            conn.execute(
                "INSERT INTO applications(id,job_id,status,outcome,applied_at,created_at,updated_at,"
                "priority,deadline,ready_at,ready_by_kind,concluded_on) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    app_id,
                    job_id,
                    status,
                    outcome,
                    stamp(applied) if applied else None,
                    stamp(created),
                    stamp(now - timedelta(minutes=index)),
                    1 + index % 5 if status == "draft" else None,
                    (now + timedelta(days=index % 30)).date().isoformat()
                    if status == "draft"
                    else None,
                    stamp(now - timedelta(hours=index)) if ready else None,
                    "owner" if ready else None,
                    now.date().isoformat() if outcome == "no_response" else None,
                ),
            )
            conn.execute(
                "INSERT INTO events(id,job_id,application_id,kind,payload,created_at,subject_type,subject_id,actor_kind) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    new_id(),
                    job_id,
                    app_id,
                    "application_created",
                    json.dumps({"status": "draft"}),
                    stamp(created),
                    "application",
                    app_id,
                    "owner",
                ),
            )
            if status == "draft" and index % 4 == 3:
                continue  # some Drafts have no document yet
            for kind in ("resume", "cover_letter"):
                document_id = new_id()
                conn.execute(
                    "INSERT INTO documents(id,application_id,kind,title,text,review_state,created_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (
                        document_id,
                        app_id,
                        kind,
                        "CV" if kind == "resume" else "Letter",
                        f"{job_rows[index][2]}\n{DOCUMENT_TEXT}",
                        "approved" if ready or status != "draft" else "draft",
                        stamp(created),
                    ),
                )
                conn.execute(
                    "INSERT INTO files(id,sha256,name,media_type,size,document_id,created_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (
                        new_id(),
                        sha,
                        f"{kind}.pdf",
                        "application/pdf",
                        len(PDF),
                        document_id,
                        stamp(created),
                    ),
                )
            kind = {"interview": "interview", "offer": "offer", "closed": "rejection"}.get(status)
            if kind and applied and outcome != "no_response":
                conn.execute(
                    "INSERT INTO responses(id,application_id,kind,date,origin,created_by_kind,"
                    "updated_by_kind,created_at,updated_at) VALUES(?,?,?,?,'stage','owner','owner',?,?)",
                    (
                        new_id(),
                        app_id,
                        kind,
                        (applied + timedelta(days=4)).date().isoformat(),
                        stamp(now),
                        stamp(now),
                    ),
                )
