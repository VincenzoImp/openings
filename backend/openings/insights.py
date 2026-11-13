"""Outcome insights: how employers answered the applications the owner sent.

Only employer responses count. The sample is the sent applications: those with
``applied_at``, in Applied, Interview or Offer, or with a recorded response.
Drafts and attempts closed without being sent are counted apart (``excluded``),
and jobs an agent dismissed never had an application, so neither is ever read
as an employer signal.

For each sent application: it got an answer when it has any response; it led to
an interview when it has an interview or an offer response; it got an offer when
it has an offer response. Its time to the first answer is the day of its first
response minus the day of ``applied_at`` (never below zero); one without
``applied_at`` has no time and is counted as ``undated``. A rate is withheld
(``null``, with the reason) when fewer than ``min_sample`` applications were
sent; the median and the shares of the time table when fewer than ``min_sample``
answers have a time.

Applications are grouped by the role family and seniority read from the job
title (a fixed keyword mapping in English, German, French and Italian, below),
the first part of the job location, the kind and name of the collection source
that first found the job, and the month of ``applied_at``.
"""

import json
import re
import statistics
import unicodedata
from collections import defaultdict
from datetime import date

from pydantic import Field, field_validator, model_validator

from .collectors.catalog import COMPANY_KINDS
from .models import Input, normalized_date
from .outcomes import no_reply_cutoff, no_reply_period

DEFAULT_MIN_SAMPLE = 5

# Role families, tried in this order on the folded title (lower case, no accents,
# punctuation as spaces); the first family with a matching phrase wins, otherwise
# "unknown". Each phrase is a regular expression matched as whole words. A
# specific family comes before a broader one: "Analytics Engineer" is Analytics,
# "Python Engineer" Backend, and a title with no family word (such as plain
# "Engineer") stays unknown.
ROLE_FAMILIES = (
    (
        "management",
        "Engineering management",
        (
            "engineering manager",
            "head of (engineering|data|technology|platform|software|development|it|product)",
            "director of (engineering|data|technology|software)",
            "vp (of )?engineering",
            "cto",
            "chief technology officer",
            "engineering lead(er)?",
            "entwicklungsleiter(in)?",
            "leiter(in)? (der )?(softwareentwicklung|entwicklung|it)",
            "it-leiter(in)?",
            "directeur (technique|informatique|de l'ingenierie)",
            "responsable (technique|du developpement|engineering)",
            "direttore (tecnico|it)",
            "responsabile (tecnico|dello sviluppo|engineering)",
        ),
    ),
    (
        "data_science",
        "Data science and ML",
        (
            "data scientist",
            "data science",
            "machine learning",
            "ml engineer",
            "mlops",
            "ai (engineer|researcher)",
            "deep learning",
            "nlp",
            "computer vision",
            "llm",
            "datenwissenschaftler(in)?",
            "maschinelles lernen",
            "kunstliche intelligenz",
            "scientifique des donnees",
            "apprentissage automatique",
            "intelligence artificielle",
            "scienziato dei dati",
            "apprendimento automatico",
            "intelligenza artificiale",
        ),
    ),
    (
        "analytics",
        "Analytics",
        (
            "data analyst",
            "analytics",
            "business intelligence",
            "bi (developer|engineer|analyst)",
            "reporting analyst",
            "datenanalyst(in)?",
            "datenanalyse",
            "analyste (de donnees|data|bi)",
            "analista (dati|di dati|bi)",
        ),
    ),
    (
        "data_engineering",
        "Data engineering",
        (
            "data engineer(ing)?",
            "data (platform|infrastructure)",
            "etl",
            "big data",
            "dateningenieur(in)?",
            "datenengineer(in)?",
            "datenplattform",
            "ingenieur (de )?donnees",
            "ingenieur data",
            "ingegnere (dei )?dati",
        ),
    ),
    (
        "platform",
        "Platform and reliability",
        (
            "devops",
            "dev ops",
            "site reliability",
            "sre",
            "platform engineer",
            "infrastructure",
            "cloud (engineer|architect)",
            "systems? engineer",
            "kubernetes",
            "system administrator",
            "sysadmin",
            "systemadministrator(in)?",
            r"plattform\w*",
            r"infrastruktur\w*",
            r"it-infrastruktur\w*",
            "ingenieur (cloud|systemes?|infrastructure)",
            "administrateur systemes?",
            "sistemista",
            r"ingegnere (cloud|di sistema|infrastruttur\w*)",
        ),
    ),
    (
        "security",
        "Security",
        (
            "security",
            r"cyber\w*",
            "infosec",
            "penetration tester",
            r"sicherheit\w*",
            "it-sicherheit",
            "securite",
            "sicurezza",
        ),
    ),
    ("mobile", "Mobile", ("ios", "android", "mobile", "flutter", "react native")),
    ("fullstack", "Full stack", ("full[ -]?stack",)),
    (
        "frontend",
        "Frontend",
        (
            "front[ -]?end",
            "ui (engineer|developer)",
            "web developer",
            "webentwickler(in)?",
            "frontend-entwickler(in)?",
            r"developpeur (web|front\w*)",
            r"sviluppatore (web|front\w*)",
        ),
    ),
    (
        "backend",
        "Backend",
        (
            "back[ -]?end",
            "backend-entwickler(in)?",
            "api (engineer|developer)",
            "(python|java|golang|go|rust|scala|kotlin|ruby|php) (engineer|developer)",
            r"developpeur (back\w*|python|java)",
            r"sviluppatore (back\w*|python|java)",
        ),
    ),
    (
        "qa",
        "Quality and testing",
        (
            "qa",
            "quality (assurance|engineer)",
            "test (engineer|automation)",
            "tester",
            "sdet",
            "testautomatisierung",
            "softwaretester(in)?",
            "testeur",
            "ingenieur (de )?test",
            "collaudatore",
        ),
    ),
    (
        "research",
        "Research",
        (
            "research(er)?",
            "scientist",
            "postdoc",
            "phd",
            "forscher(in)?",
            "forschung",
            "doktorand(in)?",
            "wissenschaftliche[rn]? mitarbeiter(in)?",
            "chercheu(r|se)",
            "recherche",
            "doctorant(e)?",
            "ricercat(ore|rice)",
            "ricerca",
            "dottorand(o|a)",
        ),
    ),
    (
        "product",
        "Product",
        (
            "product (manager|owner)",
            "produktmanager(in)?",
            "produktverantwortliche[r]?",
            "chef de produit",
            "responsable produit",
            "responsabile (di )?prodotto",
        ),
    ),
    ("design", "Design", ("designer", "ux", "user experience", "gestalter(in)?")),
    (
        "software",
        "Software engineering",
        (
            "software",
            "developer",
            "programmer",
            "coder",
            "product engineer",
            "softwareentwickler(in)?",
            "softwareingenieur(in)?",
            "entwickler(in)?",
            "informatiker(in)?",
            "developpeu(r|se)",
            "ingenieur logiciel",
            "programmeur",
            "sviluppat(ore|rice)",
            "programmatore",
            "ingegnere (del )?software",
        ),
    ),
)
# Seniority, tried in this order; the first level with a matching phrase wins,
# otherwise "unknown": most titles state none.
SENIORITY = (
    (
        "intern",
        "Intern or trainee",
        (
            "intern(ship)?",
            "trainee",
            "praktikum",
            "praktikant(in)?",
            "werkstudent(in)?",
            "working student",
            "stagiaire",
            "stage",
            "alternan(ce|t|te)",
            "apprentie?",
            "tirocinio",
            "tirocinante",
            "stagista",
            "apprendista",
        ),
    ),
    (
        "head",
        "Head or director",
        (
            "head of",
            "director",
            "vp",
            "vice president",
            "chief",
            "cto",
            "cio",
            "engineering manager",
            "leiter(in)?",
            "abteilungsleiter(in)?",
            "bereichsleiter(in)?",
            "directeur",
            "directrice",
            "direttore",
            "direttrice",
        ),
    ),
    (
        "lead",
        "Lead, staff or principal",
        (
            "lead",
            "staff",
            "principal",
            "team leader",
            "teamleiter(in)?",
            "chef d'equipe",
            "referente? technique",
            "caposquadra",
        ),
    ),
    (
        "senior",
        "Senior",
        (
            "senior",
            "sr",
            "snr",
            "experienced",
            "erfahrene[rn]?",
            "confirmee?",
            "experimentee?",
            "espert(o|a)",
        ),
    ),
    ("mid", "Mid-level", ("mid", "mid-level", "midlevel", "medior", "intermediate")),
    (
        "junior",
        "Junior",
        (
            "junior",
            "jr",
            "entry[ -]level",
            "graduate",
            "new grad",
            "berufseinsteiger(in)?",
            "einsteiger(in)?",
            "absolvent(in)?",
            "debutante?",
            "jeune diplomee?",
            "neolaureat(o|a)",
        ),
    ),
)


def _compile(table):
    return [
        (key, label, re.compile(r"\b(" + "|".join(phrases) + r")\b"))
        for key, label, phrases in table
    ]


_FAMILIES = _compile(ROLE_FAMILIES)
_LEVELS = _compile(SENIORITY)
FAMILY_LABELS = {key: label for key, label, _ in ROLE_FAMILIES} | {"unknown": "Unknown"}
SENIORITY_LABELS = {key: label for key, label, _ in SENIORITY} | {"unknown": "Not stated"}
SOURCE_KINDS = {
    "search": "Searches",
    "company": "Company boards",
    "feed": "Feeds",
    "manual": "Added by hand",
}
DIMENSIONS = ("role_family", "seniority", "location", "source_kind", "source", "month")
TIME_BUCKETS = (
    ("within_7", "Within 7 days", 0, 7),
    ("within_14", "8 to 14 days", 8, 14),
    ("within_30", "15 to 30 days", 15, 30),
    ("after_30", "After 30 days", 31, None),
)


def fold(text):
    """Lower case without accents, with punctuation turned into spaces."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char)).lower()
    text = re.sub(r"[_|,;:()\[\]·•–—/]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _first(patterns, title):
    folded = fold(title)
    for key, _, pattern in patterns:
        if pattern.search(folded):
            return key
    return "unknown"


def role_family(title):
    """The role family of a job title, such as data_engineering; "unknown" when none matches."""
    return _first(_FAMILIES, title)


def seniority(title):
    """The seniority a job title states, such as senior; "unknown" when it states none."""
    return _first(_LEVELS, title)


def location_group(location):
    """The first part of a location ("Zurich, Switzerland" -> "Zurich"); "" when empty."""
    return re.sub(r"\s+", " ", (location or "").split(",")[0]).strip()


def source_kind(kind, metadata):
    """search, company, feed or manual, from the first collection source of the job."""
    if kind == "jobspy":
        return "search"
    if kind == "rss":
        return "feed"
    if kind in COMPANY_KINDS or kind == "auto":
        return "company"
    # No collection source (added by URL, or the source was removed): the job's
    # metadata still says where it was found.
    provider = str(metadata.get("source") or "").lower()
    if metadata.get("ats") or provider in COMPANY_KINDS:
        return "company"
    if provider == "rss":
        return "feed"
    if provider and provider != "manual":
        return "search"
    return "manual"


PROVIDER_NAMES = {
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "zip_recruiter": "ZipRecruiter",
    "google": "Google Jobs",
    "rss": "RSS",
}


def source_name(name, kind, metadata):
    """The collection source's name, else the board the job came from, else the kind."""
    if name:
        return name
    provider = str(metadata.get("ats") or metadata.get("source") or "").lower()
    if provider and provider != "manual":
        return PROVIDER_NAMES.get(provider, provider.replace("_", " ").title())
    return SOURCE_KINDS[kind]


class InsightsQuery(Input):
    min_sample: int = Field(
        default=DEFAULT_MIN_SAMPLE,
        ge=1,
        le=100,
        description="The fewest sent applications (and dated answers) a rate (and a median) needs; below it the value is null with withheld.",
    )
    applied_since: str | None = Field(
        default=None, description="Only applications sent (applied_at) at or after this time."
    )
    applied_until: str | None = Field(
        default=None, description="Only applications sent (applied_at) at or before this time."
    )

    @field_validator("applied_since", "applied_until")
    @classmethod
    def valid_date(cls, value, info):
        return normalized_date(value, end=info.field_name == "applied_until")

    @model_validator(mode="after")
    def valid_range(self):
        if self.applied_since and self.applied_until and self.applied_since > self.applied_until:
            raise ValueError("The start date must not follow the end date.")
        return self


def _rate(count, total, enough):
    return round(count / total, 4) if enough and total else None


def metrics(items, min_sample):
    """The counts and rates of a set of sent applications."""
    sent = len(items)
    responded = sum(bool(item["kinds"]) for item in items)
    interviews = sum(bool(item["kinds"] & {"interview", "offer"}) for item in items)
    offers = sum("offer" in item["kinds"] for item in items)
    days = [item["days"] for item in items if item["days"] is not None]
    enough = sent >= min_sample
    return {
        "sent": sent,
        "responded": responded,
        "interviews": interviews,
        "offers": offers,
        "rejections": sum("rejection" in item["kinds"] for item in items),
        "no_reply": sum(item["outcome"] == "no_response" for item in items),
        "waiting": sum(item["status"] == "applied" and not item["kinds"] for item in items),
        "response_rate": _rate(responded, sent, enough),
        "interview_rate": _rate(interviews, sent, enough),
        "offer_rate": _rate(offers, sent, enough),
        "withheld": None if enough else "too_few_sent",
        "median_days_to_response": statistics.median(days) if len(days) >= min_sample else None,
        "median_withheld": None if len(days) >= min_sample else "too_few_dated_answers",
        "timed": len(days),
        "undated": sum(bool(item["kinds"]) and item["days"] is None for item in items),
    }


def time_table(items, min_sample):
    """How long the answered applications waited for their first answer."""
    days = [item["days"] for item in items if item["days"] is not None]
    enough = len(days) >= min_sample
    rows = []
    for key, label, low, high in TIME_BUCKETS:
        count = sum(low <= value and (high is None or value <= high) for value in days)
        rows.append(
            {"key": key, "label": label, "count": count, "share": _rate(count, len(days), enough)}
        )
    return rows


class InsightsService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db

    def insights(self, value: InsightsQuery | None = None) -> dict:
        """Response, interview and offer rates of sent applications, overall and by group."""
        value = (
            value if isinstance(value, InsightsQuery) else InsightsQuery.model_validate(value or {})
        )
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT app.id,app.status,app.outcome,app.applied_at,j.title,j.location,j.metadata,"
                "s.kind AS source_kind,s.name AS source_name FROM applications app "
                "JOIN jobs j ON j.id=app.job_id LEFT JOIN sources s ON s.id=(SELECT p.source_id "
                "FROM postings p WHERE p.job_id=j.id AND p.source_id IS NOT NULL "
                "ORDER BY p.first_seen_at,p.id LIMIT 1) ORDER BY app.created_at,app.id"
            ).fetchall()
            answers = defaultdict(list)
            for application_id, kind, day in conn.execute(
                "SELECT application_id,kind,date FROM responses"
            ):
                answers[application_id].append((kind, day))
            no_reply = no_reply_period(conn)
            no_reply["due"] = conn.execute(
                "SELECT count(*) FROM applications WHERE status='applied' "
                "AND applied_at IS NOT NULL AND applied_at<?",
                (no_reply_cutoff(no_reply["days"]),),
            ).fetchone()[0]
        excluded = {"preparing": 0, "closed_unsent": 0}
        sample = []
        for row in rows:
            responses = answers.get(row["id"], [])
            sent = (
                row["applied_at"] or row["status"] in {"applied", "interview", "offer"} or responses
            )
            if not sent:
                excluded["preparing" if row["status"] == "draft" else "closed_unsent"] += 1
                continue
            applied = row["applied_at"]
            if (value.applied_since or value.applied_until) and not applied:
                continue
            if value.applied_since and applied < value.applied_since:
                continue
            if value.applied_until and applied > value.applied_until:
                continue
            days = None
            if responses and applied:
                first = min(day for _, day in responses)
                days = max(0, (date.fromisoformat(first) - date.fromisoformat(applied[:10])).days)
            metadata = json.loads(row["metadata"] or "{}")
            metadata = metadata if isinstance(metadata, dict) else {}
            place = location_group(row["location"])
            kind = source_kind(row["source_kind"], metadata)
            sample.append(
                {
                    "status": row["status"],
                    "outcome": row["outcome"],
                    "kinds": {answer for answer, _ in responses},
                    "days": days,
                    "role_family": role_family(row["title"]),
                    "seniority": seniority(row["title"]),
                    "location": place.casefold() or "unknown",
                    "location_label": place or "Not stated",
                    "source_kind": kind,
                    "source": source_name(row["source_name"], kind, metadata),
                    "month": applied[:7] if applied else "unknown",
                }
            )
        return {
            "min_sample": value.min_sample,
            "period": {"applied_since": value.applied_since, "applied_until": value.applied_until},
            "overall": metrics(sample, value.min_sample),
            "time_to_response": time_table(sample, value.min_sample),
            "groups": {
                dimension: self._groups(sample, dimension, value.min_sample)
                for dimension in DIMENSIONS
            },
            "excluded": excluded,
            "no_reply": no_reply,
        }

    @staticmethod
    def _groups(sample, dimension, min_sample):
        grouped = defaultdict(list)
        labels = {}
        for item in sample:
            key = item[dimension]
            grouped[key].append(item)
            if dimension == "location":
                labels.setdefault(key, item["location_label"])
        result = []
        for key, items in grouped.items():
            label = {
                "role_family": FAMILY_LABELS.get(key, key),
                "seniority": SENIORITY_LABELS.get(key, key),
                "source_kind": SOURCE_KINDS.get(key, key),
                "location": labels.get(key, key),
                "month": "Not dated" if key == "unknown" else key,
            }.get(dimension, key)
            result.append({"key": key, "label": label, **metrics(items, min_sample)})
        if dimension == "month":
            result.sort(key=lambda group: (group["key"] == "unknown", group["key"]))
        else:
            result.sort(
                key=lambda group: (group["key"] == "unknown", -group["sent"], group["label"])
            )
        return result
