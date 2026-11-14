"""Synthetic labelled benchmark for duplicate-vacancy candidates.

Every company, person, posting and requisition here is invented. Postings are
assembled from small sentence pools (English, with a few German, French and
Italian vacancies) so the fixture stays readable; the labels are explicit.

Each row of ``VACANCIES`` is one real-world vacancy and lists the records a
workspace collected for it. Records of one row are true duplicates of each other;
records of different rows never are. ``near`` names the row a near-miss resembles
and ``kind`` says why it is still another vacancy:

- ``city``: same employer, title and template text, another city.
- ``requisition``: same employer, title, city and text, another requisition id.
- ``team``: same employer, title and city, another team (``team!`` marks the one
  pair that no text signal can tell apart; it is expected to score high).
- ``seniority``: same employer, city and nearly the same text, another level.
- ``reopened``: the same employer advertised the role again months later with the
  same text and a new posting id. It is labelled a different vacancy: it is a new
  hiring round the owner may apply to again, so it must never reach the high tier,
  although showing it for review at the default threshold is acceptable.
- ``collision``: an unrelated employer whose text happens to share a numeric id.
"""

import random
from itertools import combinations

from openings.common import now
from openings.duplicate_signals import job_features, words
from openings.duplicates import DEFAULT_MIN_CONFIDENCE, confidence_tier
from openings.errors import missing
from openings.identities import job_identities, normalize_url

ROLE = {
    "en": [
        "You will {verb} {topic} together with the {team} team.",
        "Our {team} team relies on you to {verb} {topic} every week.",
        "In this role you {verb} {topic} and explain the trade-offs to colleagues in {city}.",
        "You take ownership of {topic} from the first idea to daily operation.",
        "A typical week includes time to {verb} {topic} and to review work from peers.",
        "You report to the head of {team} and help plan the next quarter.",
        "We expect you to {verb} {topic} with care for cost, safety and clarity.",
        "You document decisions about {topic} so that new colleagues can follow them.",
        "Together with partners outside {company} you {verb} {topic} for our customers.",
        "You mentor two colleagues and keep {topic} simple enough to hand over.",
    ],
    "de": [
        "Sie verantworten {topic} gemeinsam mit dem Team {team}.",
        "Zu Ihren Aufgaben gehört es, {topic} zuverlässig zu betreuen und weiterzuentwickeln.",
        "Sie arbeiten am Standort {city} eng mit Kolleginnen und Kollegen aus dem Bereich {team} zusammen.",
        "Sie dokumentieren Entscheidungen zu {topic} nachvollziehbar für neue Teammitglieder.",
        "Sie bringen mehrjährige Erfahrung mit {topic} und eine abgeschlossene Ausbildung mit.",
        "Wir bieten Ihnen bei {company} flexible Arbeitszeiten, Weiterbildung und ein faires Gehalt.",
        "Sie berichten an die Leitung {team} und planen das kommende Quartal mit.",
        "Sehr gute Deutschkenntnisse und gute Englischkenntnisse runden Ihr Profil ab.",
    ],
    "fr": [
        "Vous prenez en charge {topic} avec l'équipe {team}.",
        "Vos missions consistent à faire évoluer {topic} de manière fiable et durable.",
        "Vous travaillez sur notre site de {city} en lien étroit avec l'équipe {team}.",
        "Vous documentez les décisions concernant {topic} pour les nouveaux collègues.",
        "Vous avez plusieurs années d'expérience avec {topic} et une formation achevée.",
        "Chez {company}, nous offrons des horaires flexibles, de la formation et un salaire équitable.",
        "Vous rendez compte à la direction {team} et participez à la planification du trimestre.",
        "Une très bonne maîtrise du français et de bonnes connaissances en anglais sont attendues.",
    ],
    "it": [
        "Ti occuperai di {topic} insieme al team {team}.",
        "Le tue attività consistono nel far evolvere {topic} in modo affidabile e sostenibile.",
        "Lavorerai nella nostra sede di {city} a stretto contatto con il team {team}.",
        "Documenterai le decisioni su {topic} per i nuovi colleghi.",
        "Hai diversi anni di esperienza con {topic} e un percorso di studi completato.",
        "In {company} offriamo orari flessibili, formazione continua e una retribuzione equa.",
        "Riporterai alla direzione {team} e parteciperai alla pianificazione del trimestre.",
        "Sono richieste un'ottima conoscenza dell'italiano e una buona conoscenza dell'inglese.",
    ],
}
VERBS = [
    "design",
    "improve",
    "maintain",
    "measure",
    "review",
    "plan",
    "automate",
    "simplify",
    "test",
    "migrate",
]
ABOUT = [
    "{company} builds dependable products for customers in twelve countries.",
    "We are a team of about three hundred people who value plain language and steady delivery.",
    "Founded by practitioners, {company} reinvests most of its income in product quality.",
    "We work in small groups, write decisions down and review them every quarter.",
    "Our offices are quiet, close to public transport and open to hybrid schedules.",
    "We publish salary bands internally and review them once a year.",
]
REQUIREMENTS = [
    "You have worked with {topic} in production for at least {years} years.",
    "You write clearly and can summarise a technical decision on one page.",
    "You are comfortable discussing {topic} with people outside your own field.",
    "A degree is welcome, and proven experience counts just as much.",
    "You speak English fluently; another European language is an advantage.",
]
BENEFITS = [
    "We offer twenty-eight days of holiday, a training budget and a pension contribution.",
    "Remote days are agreed inside each team, and equipment is provided by {company}.",
    "Parents receive paid leave beyond the legal minimum and a gradual return.",
    "Send your CV; a cover letter is optional and no photograph is needed.",
]
FOOTER = (
    "Show more. Show less. This listing was imported automatically from the employer. "
    "Report this job if it looks wrong. Sign in to save this job, set an alert and "
    "see how you compare with other applicants on this board."
)
LONG_FOOTER = (
    FOOTER + " Equal opportunity notice: applications are welcome from everybody regardless of "
    "age, origin, gender, belief or disability. Reasonable adjustments are available at "
    "every stage of the process on request. Agencies: unsolicited profiles are not "
    "accepted and no fee is owed for them. By applying you agree that your details are "
    "kept for twelve months and then deleted. Similar searches, salaries in your area "
    "and career advice articles are listed below this advertisement for registered members."
)

# One block per vacancy:
#   key | company | title | location | language | team | requisition id
#     topics: what the role works on
#     near: <key of the vacancy it resembles> <kind>
#     <source> <text variant> [field=value | ...]     one line per collected record
# Text variants: same, reflow (whitespace, case, bullets), footer and long_footer
# (job-board boilerplate), reorder (sections), tracking (campaign text), preview (a
# short excerpt), truncate (the first half) and rewrite (a board's own summary).
# Fields replace the vacancy's value for that record; "-" removes it. `direct` adds
# the employer's apply link to a job-board record, `gh_jid` an ATS id to a site URL,
# and `posted` is the date the record was published and first collected.
VACANCIES = """
backend-zurich | Norvane Robotics | Backend Engineer | Zurich, Switzerland | en | Fleet Platform | R-48213
  topics: payment APIs; PostgreSQL schemas; event-driven services
  greenhouse same
  linkedin reflow company=Norvane Robotics AG | location=Zürich, ZH, Switzerland
  indeed footer direct
  glassdoor reorder title=Backend Engineer (m/w/d) | location=Zurich

backend-lausanne | Norvane Robotics | Backend Engineer | Lausanne, Switzerland | en | Fleet Platform | R-48214
  topics: payment APIs; PostgreSQL schemas; event-driven services
  near: backend-zurich city
  greenhouse same
  linkedin reflow requisition=-

backend-zurich-second | Norvane Robotics | Backend Engineer | Zurich, Switzerland | en | Fleet Platform | R-48299
  topics: payment APIs; PostgreSQL schemas; event-driven services
  near: backend-zurich requisition
  greenhouse same

data-bern | Alpenquell Analytics | Data Engineer | Bern, Switzerland | en | Data Platform | -
  topics: batch pipelines; warehouse models; data quality checks
  lever same
  linkedin tracking company=Alpenquell Analytics Switzerland
  indeed reflow location=Berne

senior-data-bern | Alpenquell Analytics | Senior Data Engineer | Bern, Switzerland | en | Data Platform | -
  topics: batch pipelines; warehouse models; data quality checks
  near: data-bern seniority
  lever same years=7
  linkedin reflow years=7

data-bern-other-employer | Brunnmatt Statistik | Data Engineer | Bern, Switzerland | en | Reporting | -
  topics: survey datasets; dashboards; open data portals
  company same
  linkedin footer

checkout-pm-berlin | Tessolar Payments | Product Manager, Checkout | Berlin, Germany | en | Checkout | JR-20931
  topics: checkout conversion; merchant onboarding; pricing experiments
  workday same
  linkedin footer title=Product Manager, Checkout - JR-20931
  glassdoor long_footer company=Tessolar Payments GmbH
  indeed same requisition=-

checkout-pm-munich | Tessolar Payments | Product Manager, Checkout | Munich, Germany | en | Checkout | JR-20932
  topics: checkout conversion; merchant onboarding; pricing experiments
  near: checkout-pm-berlin city
  workday same
  linkedin footer location=München, Deutschland

robotics-software-zurich | Norvane Robotics | Robotics Software Engineer | Zurich, Switzerland | en | Motion Planning | R-48377
  topics: motion planners; simulation runs; sensor drivers
  greenhouse same
  linkedin reflow company=Glimmerpath
  indeed footer company=Glimmerpath | direct

risk-analyst-berlin | Tessolar Payments | Risk Analyst | Berlin, Germany | en | Risk | -
  topics: chargeback rules; fraud reviews; risk reports
  company same
  linkedin same company=Paystrand
  glassdoor reflow company=Paystrand

lab-automation-basel | Haldrin Biotech | Lab Automation Scientist | Basel, Switzerland | en | Screening | -
  topics: liquid handlers; assay protocols; instrument schedules
  smartrecruiters same company=Haldrin Biotech (Switzerland) AG
  linkedin reflow company=Haldrin Biotech Group | location=Basel
  indeed footer location=Bâle, Suisse

logistics-hamburg | Lumafreight | Logistics Coordinator | Hamburg, Germany | de | Disposition | LF-5521
  topics: die Tourenplanung; Zollunterlagen; Lieferantengespräche
  personio same company=Lumafreight Deutschland GmbH
  linkedin reflow title=Logistics Coordinator (m/w/d)
  indeed preview location=Hamburg

logistics-hamburg-second | Lumafreight | Logistics Coordinator | Hamburg, Germany | de | Disposition | LF-5587
  topics: die Tourenplanung; Zollunterlagen; Lieferantengespräche
  near: logistics-hamburg requisition
  personio same company=Lumafreight Deutschland GmbH
  linkedin reflow

security-remote-germany | Corvane Security | Security Engineer | Remote, Germany | en | Detection | -
  topics: detection rules; incident drills; cloud audit logs
  ashby same
  linkedin tracking location=Deutschland (Remote)
  indeed footer location=Germany

security-remote-france | Corvane Security | Security Engineer | Remote, France | en | Detection | -
  topics: detection rules; incident drills; cloud audit logs
  near: security-remote-germany city
  ashby same
  linkedin tracking

claims-geneva | Marlfinch Insurance | Claims Specialist | Geneva, Switzerland | fr | Sinistres | FR-2291
  topics: les dossiers de sinistres; les expertises; les réclamations clients
  company same company=Marlfinch Insurance SA | location=Genève
  linkedin reflow company=Marlfinch Insurance Suisse
  indeed footer location=Genf, Schweiz | requisition=-

junior-claims-geneva | Marlfinch Insurance | Junior Claims Specialist | Geneva, Switzerland | fr | Sinistres | -
  topics: les dossiers de sinistres; les expertises; les réclamations clients
  near: claims-geneva seniority
  company same company=Marlfinch Insurance SA

electrical-milan | Bravenergia | Ingegnere Elettrico | Milan, Italy | it | Reti | 2291-IT
  topics: le cabine di trasformazione; i collaudi; i progetti di rete
  company same company=Bravenergia S.p.A. | location=Milano, Italia
  linkedin reflow company=Bravenergia Italia
  indeed footer location=Milano

frontend-lausanne | Atelier Lumivere | Développeur Frontend | Lausanne, Switzerland | fr | Web | -
  topics: les interfaces web; les tests d'accessibilité; la bibliothèque de composants
  join same
  linkedin reflow company=Atelier Lumivère Sàrl
  glassdoor reorder location=Lausanne, VD, Suisse

plc-munich | Kranwerk Maschinenbau | SPS-Programmierer (m/w/d) | Munich, Germany | de | Steuerungstechnik | -
  topics: SPS-Programme; Inbetriebnahmen; Schaltpläne
  recruitee same location=München
  linkedin reflow title=SPS-Programmierer | company=Kranwerk Maschinenbau GmbH
  indeed footer

plc-stuttgart | Kranwerk Maschinenbau | SPS-Programmierer (m/w/d) | Stuttgart, Germany | de | Steuerungstechnik | -
  topics: SPS-Programme; Inbetriebnahmen; Schaltpläne
  near: plc-munich city
  recruitee same
  linkedin reflow

frontend-berlin-munich | Quillonsoft | Frontend Engineer | Berlin / Munich | en | Design Systems | -
  topics: component libraries; design tokens; accessibility audits
  lever same
  linkedin footer location=Munich, Germany
  indeed reflow location=Berlin, Germany; Munich, Germany

frontend-hamburg | Quillonsoft | Frontend Engineer | Hamburg, Germany | en | Design Systems | -
  topics: component libraries; design tokens; accessibility audits
  near: frontend-berlin-munich city
  lever same
  linkedin footer

frontend-berlin-growth | Quillonsoft | Frontend Engineer | Berlin, Germany | en | Growth | -
  topics: signup funnels; pricing pages; experiment dashboards
  near: frontend-berlin-munich team
  lever same
  linkedin footer

clinical-data-vienna | Solvanta Health | Clinical Data Manager | Vienna, Austria | en | Biometrics | -
  topics: case report forms; data cleaning plans; study databases
  site same url=http://www.solvanta.example/careers/clinical-data-manager/
  site reflow url=https://solvanta.example/careers/clinical-data-manager
  linkedin footer location=Wien, Österreich | posted=2026-03-04

clinical-data-vienna-reopened | Solvanta Health | Clinical Data Manager | Vienna, Austria | en | Biometrics | -
  topics: case report forms; data cleaning plans; study databases
  near: clinical-data-vienna reopened
  linkedin footer location=Wien, Österreich | posted=2026-08-20

consultant-london | Pembervale Consulting | Senior Consultant | London, United Kingdom | en | Public Sector | -
  topics: service reviews; procurement plans; stakeholder workshops
  company same company=Pembervale Consulting Ltd
  linkedin truncate company=Pembervale Consulting UK | location=London
  glassdoor footer location=London, England, United Kingdom

devops-prague | Ostrelia Systems | DevOps Engineer | Prague, Czechia | en | Platform | -
  topics: deployment pipelines; cluster upgrades; on-call runbooks
  greenhouse same
  site reflow gh_jid | location=Praha
  linkedin footer location=Prague, Czech Republic

devops-prague-data | Ostrelia Systems | DevOps Engineer | Prague, Czechia | en | Data Infrastructure | -
  topics: stream processors; storage tiers; backup drills
  near: devops-prague team
  greenhouse same
  linkedin footer

gameplay-remote | Cindermoss Games | Gameplay Programmer | Remote | en | Combat | -
  topics: combat systems; animation state machines; controller input
  company same
  linkedin reflow

# The same advertisement is reused for a second opening in another team.
gameplay-remote-other-team | Cindermoss Games | Gameplay Programmer | Remote | en | Combat | -
  topics: combat systems; animation state machines; controller input
  near: gameplay-remote team!
  company tracking url=https://cindermoss.example/jobs/gameplay-programmer-2

fleet-analyst-copenhagen | Fjordlane Shipping | Fleet Analyst | Copenhagen, Denmark | en | Operations | -
  topics: voyage reports; fuel forecasts; port schedules
  lever same posted=2026-02-10
  linkedin footer location=København, Danmark | posted=2026-02-12
  indeed reorder

fleet-analyst-copenhagen-reopened | Fjordlane Shipping | Fleet Analyst | Copenhagen, Denmark | en | Operations | -
  topics: voyage reports; fuel forecasts; port schedules
  near: fleet-analyst-copenhagen reopened
  lever same posted=2026-09-01

credit-analyst-rome | Banca Meridiale | Analista Crediti | Rome, Italy | it | Crediti | -
  topics: le pratiche di fido; i bilanci aziendali; le relazioni di rischio
  company same location=Roma, Italia
  linkedin reflow company=Banca Meridiale S.p.A.
  indeed long_footer location=Roma

embedded-turin | Varnello Mobility | Embedded Engineer | Turin, Italy | en | Powertrain | -
  topics: motor controllers; CAN diagnostics; bootloaders
  workable same
  linkedin reflow title=Embedded Engineer – Turin (80-100%)
  indeed footer location=Torino, Italia | title=Embedded Engineer, Remote

embedded-turin-level-three | Varnello Mobility | Embedded Engineer III | Turin, Italy | en | Powertrain | -
  topics: motor controllers; CAN diagnostics; bootloaders
  near: embedded-turin seniority
  workable same years=9

# A board rewrote the advertisement: only employer and title remain.
recruiter-zurich | Norvane Robotics | Technical Recruiter | Zurich, Switzerland | en | People | -
  topics: hiring plans; interview panels; candidate feedback
  greenhouse same
  glassdoor rewrite

analytics-engineer-bern | Alpenquell Analytics | Analytics Engineer | Bern, Switzerland | en | Insights | -
  topics: metric definitions; semantic layers; finance reports
  lever same
  linkedin footer
  # A manual note with a short excerpt and no location.
  site preview location=

sre-berlin | Tessolar Payments | Site Reliability Engineer | Berlin, Germany | en | Reliability | JR-20988
  topics: service level objectives; capacity plans; incident reviews
  workday same
  linkedin tracking requisition=-
  indeed footer company=Tessolar Payments GmbH

sre-berlin-second | Tessolar Payments | Site Reliability Engineer | Berlin, Germany | en | Reliability | JR-20990
  topics: service level objectives; capacity plans; incident reviews
  near: sre-berlin requisition
  workday same
  indeed footer

qa-manager-basel | Haldrin Biotech | QA Manager | Basel, Switzerland | en | Quality | -
  topics: batch records; supplier audits; deviation reports
  smartrecruiters same
  linkedin long_footer company=Haldrin Biotech AG
  glassdoor reflow title=QA Manager (f/m/d)

support-lead-dublin | Wrenfield Software | Support Team Lead | Dublin, Ireland | en | Customer Care | REQ-0731
  topics: support queues; escalation paths; help centre articles
  ashby same
  linkedin reflow company=Wrenfield Software Limited
  indeed tracking title=Support Team Lead (REQ-0731) | requisition=-

accountant-luxembourg | Odalwick Holding | Fund Accountant | Luxembourg | en | Fund Services | -
  topics: net asset values; investor statements; audit requests
  company same company=Odalwick Holding S.A.
  linkedin footer company=Odalwick | location=Luxembourg, Luxembourg
  indeed reflow company=Odalwick Group

ux-researcher-amsterdam | Tindel & Roe | UX Researcher | Amsterdam, Netherlands | en | Research | -
  topics: interview studies; usability tests; research repositories
  join same
  linkedin reorder company=Tindel & Roe B.V.
  glassdoor tracking location=Amsterdam

nurse-educator-lyon | Clairmont Santé | Infirmier Formateur | Lyon, France | fr | Formation | -
  topics: les ateliers de simulation; les parcours d'intégration; les évaluations cliniques
  company same
  indeed footer company=Clairmont Sante SAS

ml-engineer-stockholm | Skarvik Labs | Machine Learning Engineer | Stockholm, Sweden | en | Forecasting | 48213
  topics: demand forecasts; feature stores; model monitoring
  near: backend-zurich collision
  greenhouse same
  linkedin footer location=Stockholm, Sverige

office-manager-madrid | Peralta Ibérica | Office Manager | Madrid, Spain | en | Workplace | -
  topics: visitor desks; supplier contracts; travel bookings
  company same
  linkedin reflow company=Peralta Iberica SL

hydrologist-oslo | Brekkvann | Hydrologist | Oslo, Norway | en | Reservoirs | -
  topics: inflow models; gauge stations; flood warnings
  company same

translator-remote | Lingarden | Technical Translator | Remote, Europe | en | Localisation | -
  topics: user manuals; term bases; release notes
  company same

planner-helsinki | Kaarnamo | Production Planner | Helsinki, Finland | en | Supply | -
  topics: weekly build plans; material forecasts; line changeovers
  company same
  linkedin footer company=Kaarnamo Oy

counsel-brussels | Vantrel Legal | Privacy Counsel | Brussels, Belgium | en | Privacy | -
  topics: processing records; vendor agreements; regulator queries
  company same location=Bruxelles, Belgique
  linkedin reflow
  indeed footer company=Vantrel Legal BV | location=Brussel
"""
COLLECTED = "2026-03-05"  # when a record without `posted` was first collected
# Near-miss kinds whose records reuse the advertisement text of the vacancy they resemble.
SHARED_TEXT = {"city", "requisition", "seniority", "reopened", "team!"}


def _vacancies():
    rows = []
    for line in VACANCIES.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if not line.startswith(" "):
            key, company, title, location, language, team, requisition = (
                part.strip() for part in text.split("|")
            )
            rows.append(
                {
                    "key": key,
                    "company": company,
                    "title": title,
                    "location": location,
                    "language": language,
                    "team": team,
                    "requisition": None if requisition == "-" else requisition,
                    "near": None,
                    "kind": None,
                    "records": [],
                }
            )
        elif text.startswith("topics:"):
            rows[-1]["topics"] = [topic.strip() for topic in text[7:].split(";")]
        elif text.startswith("near:"):
            rows[-1]["near"], rows[-1]["kind"] = text[5:].split()
        else:
            source, variant, *fields = text.split(" ", 2)
            overrides = {}
            for field in fields[0].split("|") if fields else ():
                name, _, value = field.strip().partition("=")
                overrides[name] = True if not _ else None if value == "-" else value
            rows[-1]["records"].append((source, variant, overrides))
    return rows


def _slug(value):
    return "-".join(words(value))


def _posting(row, variant, overrides):
    company, title, topics, team = row["company"], row["title"], row["topics"], row["team"]
    seed = row["near"] if row["kind"] in SHARED_TEXT else row["key"]
    rng = random.Random(seed)
    city = row["location"].split(",")[0].split("/")[0].strip()
    years = overrides.get("years", 3)

    def fill(sentences, count):
        return [
            sentence.format(
                company=company,
                city=city,
                team=team,
                years=years,
                topic=topics[index % len(topics)],
                verb=rng.choice(VERBS),
            )
            for index, sentence in enumerate(rng.sample(sentences, count))
        ]

    language = row["language"]
    sections = [
        ("About us", fill(ABOUT, 4)),
        (title, fill(ROLE[language], 7 if language == "en" else 6)),
        ("Your profile", fill(REQUIREMENTS, 4)),
        ("What we offer", fill(BENEFITS, 3)),
    ]
    if variant == "rewrite":
        other = random.Random(seed + "/rewrite")
        highlights = [
            other.choice(ROLE["en"]).format(
                company=company, city=city, team=team, topic=topic, verb=other.choice(VERBS)
            )
            for topic in topics * 3
        ]
        sections = [
            ("Summary", [f"{company} is hiring a {title} in {city}."]),
            ("Highlights", highlights),
            ("Good to know", fill(BENEFITS, 4)),
        ]
    if variant == "reorder":
        sections = [sections[1], sections[2], sections[3], sections[0]]
    requisition = overrides.get("requisition", row["requisition"])
    label = {"de": "Referenznummer", "fr": "Référence", "it": "Rif."}.get(
        language, "Requisition ID"
    )
    blocks = [
        f"{heading}\n" + "\n".join(f"- {sentence}" for sentence in body)
        for heading, body in sections
    ]
    if requisition:
        blocks.append(f"{label}: {requisition}")
    text = "\n\n".join(blocks)
    if variant == "reflow":
        text = " ".join(text.replace("- ", "• ").split()).upper()
    elif variant == "footer":
        text += "\n\n" + FOOTER
    elif variant == "long_footer":
        text += "\n\n" + LONG_FOOTER
    elif variant == "tracking":
        text = text.replace("\n\n", "\n\n#LI-Hybrid\n", 1) + "\n\nsrc=feed_8841&cmp=spring"
    elif variant == "preview":
        text = " ".join(text.split()[:40]) + " …"
    elif variant == "truncate":
        text = " ".join(text.split()[: len(text.split()) * 11 // 20])
    return text


def benchmark_jobs():
    """Job inputs for ``Workspace.ingest_job`` with their explicit vacancy label."""
    jobs = []
    for number, row in enumerate(_vacancies(), start=1):
        board, slug = _slug(row["company"].split()[0]), _slug(row["title"])
        employer_url = None
        for copy, (source, variant, overrides) in enumerate(row["records"]):
            posting = 7_000_000 + number * 100 + copy
            url = {
                "greenhouse": f"https://boards.greenhouse.io/{board}/jobs/{posting}",
                "lever": f"https://jobs.lever.co/{board}/{posting:08d}-aaaa-bbbb-cccc-000000000000",
                "ashby": f"https://jobs.ashbyhq.com/{board}/{posting:08d}-1111-2222-3333-000000000000",
                "workday": f"https://{board}.wd3.myworkdayjobs.com/en-US/careers/job/{slug}_{row['requisition']}",
                "smartrecruiters": f"https://jobs.smartrecruiters.com/{board}/{posting}00000-{slug}",
                "personio": f"https://{board}.jobs.personio.de/job/{posting}",
                "recruitee": f"https://{board}.recruitee.com/o/{slug}-{posting}",
                "workable": f"https://apply.workable.com/{board}/j/{posting:X}F00D/",
                "join": f"https://join.com/companies/{board}/{posting}-{slug}",
                "company": f"https://{board}.example/jobs/{slug}-{posting}",
                "site": f"https://{board}.example/careers/{slug}",
                "linkedin": f"https://www.linkedin.com/jobs/view/{posting}?trk=public_jobs&refId=x{copy}",
                "indeed": f"https://www.indeed.com/viewjob?jk={posting:x}&from=serp",
                "glassdoor": f"https://www.glassdoor.com/job-listing/{slug}-JV_{posting}.htm",
            }[source]
            if overrides.get("gh_jid"):
                url = f"https://{board}.example/careers/{slug}?gh_jid={7_000_000 + number * 100}"
            url = overrides.get("url", url)
            employer_url = employer_url or url
            metadata = {"source": source}
            if "posted" in overrides:
                metadata["date_posted"] = overrides["posted"]
            job = {
                "url": url,
                "title": overrides.get("title", row["title"]),
                "company": overrides.get("company", row["company"]),
                "location": overrides.get("location", row["location"]) or "",
                "posting": _posting(row, variant, overrides),
                "metadata": metadata,
            }
            if source in {"linkedin", "indeed", "glassdoor"}:
                job["source_key"] = f"{source}:{posting}"
            if overrides.get("direct"):
                # A job board that reports the employer's own apply link.
                job["raw"] = {"job_url_direct": employer_url + "?utm_source=board&utm_medium=feed"}
            jobs.append(
                {
                    "vacancy": row["key"],
                    "near": row["near"],
                    "kind": row["kind"],
                    "collected": overrides.get("posted", COLLECTED) + "T08:00:00+00:00",
                    "job": job,
                }
            )
    return jobs


def true_pairs(labels):
    """Every pair of record ids labelled as the same vacancy."""
    return {
        frozenset(pair)
        for pair in combinations(sorted(labels), 2)
        if labels[pair[0]] == labels[pair[1]]
    }


def grouped_pairs(groups):
    return {frozenset(pair) for group in groups for pair in combinations(sorted(group), 2)}


def precision_recall(groups, labels):
    found, truth = grouped_pairs(groups), true_pairs(labels)
    correct = len(found & truth)
    return (correct / len(found) if found else 1.0), correct / len(truth)


def likely_duplicates(workspace, job, min_confidence=DEFAULT_MIN_CONFIDENCE, limit=5):
    """Archived jobs most likely to be the same vacancy as one job, best first.

    ``job`` is an archived job ID, or the fields of a posting not archived yet.
    """
    with workspace.db.connect() as connection:
        index = workspace._duplicate_index(connection)
    if isinstance(job, str):
        features = index.jobs.get(job) or missing("Job")
    else:
        url = normalize_url(job.get("url") or "")
        features = job_features(
            {
                **job,
                "id": None,
                "url": url,
                "identities": job_identities(url, job.get("source_key")),
                "urls": [(job.get("raw") or {}).get("job_url_direct")],
                "created_at": job.get("created_at") or now(),
            }
        )
    return [
        {
            "job_id": job_id,
            "confidence": evidence.score,
            "tier": confidence_tier(evidence.score),
            "reasons": {"matched": list(evidence.matched), "conflicts": list(evidence.conflicts)},
        }
        for job_id, evidence in index.matches(features, min_confidence, limit)
    ]
