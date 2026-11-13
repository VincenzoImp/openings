"""Synthetic jobs with ingest signals for the browser-test workspace and the docs.

Two saved searches and two company boards, jobs in English, German, French and
Italian, a likely duplicate of a job with an application, a posting a board no
longer lists, postings that require German (hidden by the spoken-languages filter,
never dismissed), dismissals by the agent and by the owner, and a question for the
owner about one job. Everything is fictional.
"""

import json

from openings.actors import OWNER, acting_as, token_actor
from openings.common import new_id, now

ENGLISH_DATA = (
    "Northstar Labs builds data tools for energy networks. The forecasting team is looking "
    "for a data engineer in Zurich. You will build and run the pipelines that feed our load "
    "forecasts, model measurement data in PostgreSQL and work with analysts on data quality. "
    "We look for three years of data engineering with Python and SQL, experience with a "
    "workflow scheduler and clear written English. German is a plus. We offer a yearly "
    "learning budget, flexible hours and a quiet office near the station."
)
POSTINGS = {
    "harbor": (
        "Wir bauen die Zahlungsplattform der Harbor Bank weiter und suchen Verstärkung für "
        "unser Team in Zürich. Deine Aufgaben: Du entwickelst Dienste in Kotlin, du "
        "verbesserst unsere Schnittstellen und du arbeitest eng mit dem Betrieb zusammen. "
        "Dein Profil: mehrjährige Erfahrung mit verteilten Systemen. Englischkenntnisse sind "
        "von Vorteil. Wir bieten flexible Arbeitszeiten und ein modernes Büro."
    ),
    "cedar_cloud": (
        "You will run the cloud accounts of Cedar Systems, automate them with Terraform and "
        "help our developers ship safely. We are looking for experience with Kubernetes and "
        "a calm way of working during incidents. Fluent English is required; German is "
        "welcome but not needed. We offer hybrid work in Zurich."
    ),
    "cedar_devops": (
        "Cedar Systems sucht eine Person für den Betrieb unserer Plattform. Du automatisierst "
        "Deployments, verbesserst das Monitoring und unterstützt unsere Teams. Voraussetzungen: "
        "Erfahrung mit Linux und Ansible, fließend Deutsch (C1) und gute Englischkenntnisse."
    ),
    "harbor_geneva": (
        "Vous développez les services de paiement de la Harbor Bank à Genève. Vous concevez "
        "des API, vous écrivez des tests et vous participez aux choix techniques de l'équipe. "
        "Votre profil : cinq ans d'expérience en Java. Français et anglais courants exigés."
    ),
    "fjord": (
        "Fjord Analytics helps retailers understand their stores. As an analytics engineer "
        "you model data in dbt, build dashboards and work with our customers' analysts. We "
        "look for strong SQL and fluent English. The role is remote within Europe."
    ),
    "orbit_sre": (
        "Orbit Works runs a scheduling product for clinics. You will keep it available, "
        "improve our monitoring and take part in an on-call rotation that includes nights "
        "once a month. We look for experience with Go or Python and fluent English."
    ),
    "orbit_junior": (
        "Join Orbit Works as a junior data analyst. You will prepare weekly reports, clean "
        "data and learn from senior analysts. Fluent English is required."
    ),
    "lumen_manager": (
        "Lumen Health is looking for an engineering manager for two product teams in Basel. "
        "You will hire, coach and plan with product managers. Fluent English is required."
    ),
    "lumen_platform": (
        "Lumen Health runs its platform on Kubernetes. As a platform engineer you will build "
        "the paved road our developers use every day. Fluent English is required."
    ),
    "alpine": (
        "Siamo un'azienda di Lugano che sviluppa software per la logistica. Cerchiamo uno "
        "sviluppatore backend che si occupi delle nostre API e della qualità del codice. "
        "Requisiti: esperienza con Python e ottima conoscenza dell'inglese. Offriamo un "
        "contratto a tempo indeterminato e due giorni di lavoro da remoto."
    ),
}


def agent_actor(app):
    with acting_as(OWNER):
        tokens = app.state.auth.list_tokens()["items"]
    token = next(item for item in tokens if item["name"] == "career-agent")
    return token_actor(token["id"], token["name"], token["kind"])


def seed_jobs(app):
    """Sources, jobs with signals and dismissals of every kind; returns the job ids by key."""
    workspace, activity = app.state.workspace, app.state.activity
    agent = agent_actor(app)
    sources = {}
    with workspace.db.transaction() as conn:
        for key, name, kind, config in (
            ("python", "Python engineer Zurich", "jobspy", {"providers": ["linkedin", "indeed"]}),
            ("data", "Data engineer remote Europe", "jobspy", {"providers": ["linkedin"]}),
            ("northstar", "Northstar Labs", "greenhouse", {"board": "northstar"}),
            ("fjord", "Fjord Analytics", "lever", {"board": "fjord"}),
        ):
            sources[key] = new_id()
            conn.execute(
                "INSERT INTO sources(id,name,kind,config,enabled,created_at,updated_at) "
                "VALUES(?,?,?,?,1,?,?)",
                (sources[key], name, kind, json.dumps(config), now(), now()),
            )

    def collect(key, title, company, location, posting, source, board="linkedin", **extra):
        url = (
            f"https://boards.greenhouse.io/northstar/jobs/{key}"
            if board == "greenhouse"
            else f"https://jobs.example.test/{board}/{key}"
        )
        return workspace.ingest_job(
            {
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "posting": posting,
                "source_id": sources[source],
                "metadata": {"source": board, **extra},
                **({"source_key": f"greenhouse:northstar:{key}"} if board == "greenhouse" else {}),
            }
        )

    ids = {}
    earlier = collect(
        "data-engineer",
        "Data Engineer",
        "Northstar Labs",
        "Zurich, Switzerland",
        ENGLISH_DATA,
        "northstar",
        board="greenhouse",
        ats="greenhouse",
    )
    ids["earlier"] = earlier["id"]
    workspace.create_application({"job_id": earlier["id"]})
    for key, title, company, location, posting, source, board in (
        (
            "lumen-platform",
            "Platform Engineer",
            "Lumen Health",
            "Basel, Switzerland",
            "lumen_platform",
            "python",
            "indeed",
        ),
        (
            "orbit-junior",
            "Junior Data Analyst",
            "Orbit Works",
            "Remote, Europe",
            "orbit_junior",
            "data",
            "linkedin",
        ),
        (
            "lumen-manager",
            "Engineering Manager",
            "Lumen Health",
            "Basel, Switzerland",
            "lumen_manager",
            "python",
            "linkedin",
        ),
        (
            "cedar-devops",
            "DevOps Engineer",
            "Cedar Systems",
            "Zurich, Switzerland",
            "cedar_devops",
            "python",
            "indeed",
        ),
        (
            "harbor-geneva",
            "Backend Engineer",
            "Harbor Bank",
            "Geneva, Switzerland",
            "harbor_geneva",
            "python",
            "linkedin",
        ),
        (
            "fjord",
            "Analytics Engineer",
            "Fjord Analytics",
            "Remote, Europe",
            "fjord",
            "fjord",
            "lever",
        ),
        (
            "alpine",
            "Sviluppatore backend",
            "Alpine Research",
            "Lugano, Switzerland",
            "alpine",
            "python",
            "indeed",
        ),
        (
            "orbit-sre",
            "Site Reliability Engineer",
            "Orbit Works",
            "Remote, Europe",
            "orbit_sre",
            "data",
            "linkedin",
        ),
        (
            "cedar-cloud",
            "Cloud Engineer",
            "Cedar Systems",
            "Zurich, Switzerland",
            "cedar_cloud",
            "python",
            "linkedin",
        ),
        (
            "harbor",
            "Backend Engineer, Payments",
            "Harbor Bank",
            "Zurich, Switzerland",
            "harbor",
            "python",
            "indeed",
        ),
    ):
        ids[key] = collect(key, title, company, location, POSTINGS[posting], source, board)["id"]
    ids["copy"] = collect(
        "grid-platform",
        "Data Engineer, Grid Platform",
        "Northstar Labs",
        "Zurich, Switzerland",
        ENGLISH_DATA,
        "data",
    )["id"]
    ids["incomplete"] = workspace.ingest_job(
        {
            "title": "Software Engineer, Data",
            "company": "Kestrel Robotics",
            "location": "Zurich, Switzerland",
            "url": "https://jobs.example.test/indeed/kestrel",
            "posting": "Kestrel Robotics is hiring a software engineer for its data team.",
            "source_id": sources["python"],
            "metadata": {"source": "indeed", "description_complete": False},
        }
    )["id"]
    # The board stopped listing one posting.
    with workspace.db.transaction() as conn:
        conn.execute("UPDATE postings SET unlisted_at=? WHERE job_id=?", (now(), ids["fjord"]))

    def triage(key, value, reason=None):
        job = workspace.get_job(ids[key])
        return workspace.set_triage(job["id"], value, job["version"], reason)

    with acting_as(agent):
        triage("lumen-platform", "saved")
        triage("orbit-junior", "dismissed", "Junior role; you look for mid to senior level.")
        activity.ask_question(
            {
                "question": "This role includes night on-call once a month. Shortlist it?",
                "why": "Your Preferences say nothing about on-call work at night.",
                "subject_type": "job",
                "subject_id": ids["orbit-sre"],
            }
        )
    with acting_as(OWNER):
        triage("lumen-manager", "dismissed", "Not looking for management roles this year.")
    return ids
