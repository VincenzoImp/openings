"""Deterministic signals of one job for duplicate detection: normalized company and
title, places, requisition ids, apply targets and a bounded sketch of the posting text.

Nothing here reads the database, a model or the network.
"""

import hashlib
import re
import unicodedata
import zlib
from array import array
from bisect import bisect_right
from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlsplit

from .identities import normalize_url

REPOST_DAYS = 60


def _vocabulary(text):
    return frozenset(text.split())


# Gender/inclusion markers such as "(m/f/d)" or "(w/m/x)" do not change a vacancy.
_MARKER = re.compile(r"[(\[]\s*(?:[mwfdxhi*]\s*[/|,]\s*)+[mwfdxhi*]\s*[)\]]")
_LEGAL = {
    "ab",
    "ag",
    "as",
    "bv",
    "co",
    "corp",
    "corporation",
    "gmbh",
    "inc",
    "kg",
    "limited",
    "llc",
    "ltd",
    "nv",
    "oy",
    "plc",
    "pty",
    "sa",
    "sarl",
    "sas",
    "se",
    "spa",
    "srl",
}
_LEGAL_MORE = _vocabulary("aps bvba cie eg ev kgaa llp lp ltda oyj sagl sl slu ug")
# Generic corporate words: "Example Group" and "Example Holding AG" are "Example".
_CORPORATE = {"group", "gruppe", "groupe", "gruppo", "holding", "holdings", "international"}
# Country names in English, German, French and Italian, for locations and for
# company suffixes such as "Example Switzerland" or "Example Deutschland GmbH".
_COUNTRIES = {
    code: names.split("|")
    for code, names in {
        "AT": "austria|osterreich|oesterreich|autriche",
        "AU": "australia|australien|australie",
        "BE": "belgium|belgien|belgique|belgio|belgie",
        "CA": "canada|kanada",
        "CH": "switzerland|schweiz|suisse|svizzera",
        "CZ": "czechia|czech republic|tschechien",
        "DE": "germany|deutschland|allemagne|germania",
        "DK": "denmark|danemark|danimarca|danmark",
        "ES": "spain|spanien|espagne|spagna|espana",
        "FI": "finland|finnland|finlande|finlandia",
        "FR": "france|frankreich|francia",
        "GB": "united kingdom|uk|great britain|england|vereinigtes konigreich|royaume uni|regno unito",
        "IE": "ireland|irland|irlande|irlanda",
        "IN": "india|indien|inde",
        "IT": "italy|italien|italie|italia",
        "JP": "japan|japon|giappone",
        "LI": "liechtenstein",
        "LU": "luxembourg|luxemburg|lussemburgo",
        "NL": "netherlands|niederlande|pays bas|paesi bassi|nederland|holland",
        "NO": "norway|norwegen|norvege|norvegia|norge",
        "PL": "poland|polen|pologne|polonia|polska",
        "PT": "portugal|portogallo",
        "SE": "sweden|schweden|suede|svezia|sverige",
        "SG": "singapore|singapur|singapour",
        "US": "united states|united states of america|usa|us|vereinigte staaten|etats unis|stati uniti",
    }.items()
}
_COUNTRY_CODE = {name: code for code, names in _COUNTRIES.items() for name in names}
_COUNTRY_SUFFIX = {name for name in _COUNTRY_CODE if " " not in name and name != "us"} | {
    "ch",
    "de",
    "europe",
    "emea",
    "dach",
}
# Local names of a few large European cities, so "Genf" and "Geneva" agree.
_EXONYMS = {
    local: name
    for name, locals_ in {
        "basel": "bale|basilea",
        "bern": "berne|berna",
        "brussels": "bruxelles|brussel",
        "cologne": "koln|koeln",
        "copenhagen": "kobenhavn|kopenhagen",
        "florence": "firenze|florenz",
        "geneva": "genf|geneve|ginevra",
        "lausanne": "losanna",
        "lisbon": "lisboa|lissabon",
        "lucerne": "luzern|lucerna",
        "milan": "milano|mailand",
        "munich": "munchen|muenchen|monaco di baviera",
        "prague": "praha|prag",
        "rome": "roma|rom",
        "turin": "torino",
        "vienna": "wien|vienne",
        "warsaw": "warszawa|warschau",
        "zurich": "zuerich|zurigo",
    }.items()
    for local in locals_.split("|")
}
_REMOTE = re.compile(
    r"\b(?:remote|remoto|home ?office|teletravail|telearbeit|anywhere|worldwide|work from home)\b"
)
_PLACE_SPLIT = re.compile(r"[,;/|•·()\[\]+&]|\s[-–]\s|\b(?:or|and|und|oder|ou|et)\b")
_PLACE_NOISE = _vocabulary(
    "area greater region metropolitan metro city canton kanton of the district bezirk raum "
    "grossraum hq office onsite hybrid hybride ibrido fully da europe europa emea dach eu"
)
_SENIORITY = _vocabulary(
    "junior jr senior sr lead principal staff intern internship trainee graduate entry mid "
    "associate head director vp werkstudent werkstudentin praktikant praktikantin praktikum "
    "stagiaire stage stagista tirocinio apprenti azubi i ii iii iv 1 2 3 4 5"
)
# Words that decorate a title without changing the vacancy.
_TITLE_NOISE = _vocabulary(
    "remote hybrid homeoffice home office full part time fulltime parttime vollzeit teilzeit "
    "temps plein partiel tempo pieno parziale permanent unbefristet cdi new neu urgent "
    "in at im bei a de"
)
_REFERENCE_PREFIX = re.compile(r"^(?:JR|REQ|REF|JOB|ID|R)(?=\d+$)")
_LABELLED_REFERENCE = re.compile(
    r"\b(?:(?:job|req|requisition|position|posting|vacancy|stellen|referenz|ref|reference)"
    r"[\s\-]?(?:id|no\.?|nr\.?|number|nummer|code|#)"
    r"|requisition|reference|referenz|kennziffer|référence|réf\.|riferimento|rif\.|ref\.)"
    r"\s*[:#]?\s*([a-z]{0,6}[\-_/]?\d[\w\-/]{1,18})"
)  # matched against lower-cased text: case-insensitive matching is several times slower
_TITLE_REFERENCE = re.compile(
    r"(?<![\w])(?:(?:jr|req|ref|id|r)[\-_ #:.]{0,2}(\d{3,})|#\s?(\d{3,})|(\d{5,}))(?![\w])",
    re.IGNORECASE,
)

# Short or empty postings carry too little text to suggest a shared vacancy.
MIN_POSTING_WORDS = 60
_POSTING_CHARS = 50_000
_SHINGLE_WORDS = 3_000
_SKETCH = 128  # smallest shingle hashes kept per posting
_NO_LIMIT = 2**32

_LETTERS = str.maketrans({"ß": "ss", "ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d"})
_DOTTED = re.compile(r"(?<=\b\w)\.(?=\w\b)")  # "S.p.A." is "SpA"


def words(value):
    return re.findall(r"\w+", (value or "").lower())


def _fold(value):
    """Lower-case and strip accents: "Zürich" and "Zurich", "Société" and "Societe"."""
    text = unicodedata.normalize("NFKD", (value or "").lower().translate(_LETTERS))
    return "".join(character for character in text if not unicodedata.combining(character))


def normalize_title(value):
    return " ".join(words(_MARKER.sub(" ", (value or "").lower())))


def normalize_company(value):
    """Company name without legal, corporate and country suffixes."""
    tokens = words(_DOTTED.sub("", _fold(value)))
    while len(tokens) > 1 and (
        tokens[-1] in _LEGAL
        or tokens[-1] in _LEGAL_MORE
        or tokens[-1] in _CORPORATE
        or tokens[-1] in _COUNTRY_SUFFIX
    ):
        tokens.pop()
    if len(tokens) > 1 and tokens[0] == "the":
        tokens.pop(0)
    return " ".join(tokens)


def normalize_location(value):
    return " ".join(words(value))


def posting_fingerprint(posting):
    """Hash of the posting's words, ignoring case, punctuation and whitespace."""
    tokens = words((posting or "")[:_POSTING_CHARS])
    if len(tokens) < MIN_POSTING_WORDS:
        return None
    return hashlib.sha256(" ".join(tokens).encode()).hexdigest()[:16]


def _shingles(posting):
    tokens = words((posting or "")[:_POSTING_CHARS])[:_SHINGLE_WORDS]
    if len(tokens) < MIN_POSTING_WORDS:
        return set()
    return {tuple(tokens[i : i + 3]) for i in range(max(len(tokens) - 2, 0))}


def posting_similarity(first, second):
    """Jaccard similarity of three-word shingles, or None without usable text."""
    a, b = _shingles(first), _shingles(second)
    if not a or not b:
        return None
    return round(len(a & b) / len(a | b), 2)


def _text_features(posting):
    """Fingerprint and bottom-k sketch of the three-word shingles, in one pass."""
    tokens = words((posting or "")[:_POSTING_CHARS])
    if len(tokens) < MIN_POSTING_WORDS:
        return None, None
    fingerprint = hashlib.sha256(" ".join(tokens).encode()).hexdigest()[:16]
    tokens = tokens[:_SHINGLE_WORDS]
    hashes = {
        zlib.crc32(" ".join(shingle).encode()) for shingle in zip(tokens, tokens[1:], tokens[2:])
    }
    return fingerprint, array("I", sorted(hashes)[:_SKETCH])


def sketch_similarity(first, second):
    """Jaccard similarity estimated from two sketches; exact for short postings."""
    if not first or not second:
        return None
    # A full sketch holds every hash of its posting up to its largest value, so both
    # postings are completely known up to the smaller of those limits.
    limit = min(
        first[-1] if len(first) == _SKETCH else _NO_LIMIT,
        second[-1] if len(second) == _SKETCH else _NO_LIMIT,
    )
    shared = len(set(first).intersection(second))
    return shared / (bisect_right(first, limit) + bisect_right(second, limit) - shared)


def _reference(value):
    value = re.sub(r"[^A-Z0-9]", "", value.upper())
    value = _REFERENCE_PREFIX.sub("", value).lstrip("0")
    if sum(character.isdigit() for character in value) < 3 or re.fullmatch(r"(?:19|20)\d\d", value):
        return None
    return value


def reference_ids(title, posting):
    """Requisition or reference ids stated in the title or labelled in the text."""
    found = [next(filter(None, groups)) for groups in _TITLE_REFERENCE.findall(title or "")]
    found += _LABELLED_REFERENCE.findall((posting or "")[:_POSTING_CHARS].lower())[:5]
    return frozenset(filter(None, map(_reference, found)))


def apply_targets(url):
    """Keys naming where a posting is hosted: an ATS posting id, or the URL itself.

    Unlike ingestion identities these ignore the scheme, "www." and the board name,
    so they only suggest a shared vacancy.
    """
    try:
        parts = urlsplit(normalize_url(url))
        host = (parts.hostname or "").removeprefix("www.")
    except ValueError:
        return set()
    if not host:
        return set()
    path = [segment for segment in parts.path.split("/") if segment]
    keys = set()
    greenhouse = parse_qs(parts.query).get("gh_jid")
    if greenhouse and greenhouse[0].isdigit():
        keys.add("greenhouse:" + greenhouse[0])
    if host.endswith("greenhouse.io") and "jobs" in path[:-1]:
        keys.add("greenhouse:" + path[path.index("jobs") + 1])
    elif host in {"jobs.lever.co", "jobs.eu.lever.co"} and len(path) >= 2:
        keys.add("lever:" + path[1])
    elif host == "jobs.ashbyhq.com" and len(path) >= 2:
        keys.add("ashby:" + path[1])
    elif host.endswith(".myworkdayjobs.com") and path:
        match = re.search(r"_([A-Za-z]{0,4}-?\d{3,})(?:-\d+)?$", path[-1])
        if match:
            keys.add(f"workday:{host.split('.')[0]}:{match[1].upper()}")
    elif host == "jobs.smartrecruiters.com" and len(path) >= 2:
        match = re.match(r"\d{6,}", path[1])
        if match:
            keys.add("smartrecruiters:" + match[0])
    elif host == "apply.workable.com" and len(path) >= 3 and path[1] == "j":
        keys.add("workable:" + path[2].upper())
    elif ".jobs.personio." in host and len(path) >= 2 and path[0] == "job":
        keys.add(f"personio:{host.split('.')[0]}:{path[1]}")
    elif host.endswith(".recruitee.com") and len(path) >= 2 and path[0] == "o":
        keys.add(f"recruitee:{host.split('.')[0]}:{path[1].lower()}")
    elif host == "join.com" and len(path) >= 3 and path[0] == "companies":
        keys.add(f"join:{path[1]}:{path[2].split('-')[0]}")
    if not keys and path:
        keys.add(f"url:{host}/{'/'.join(path)}" + (f"?{parts.query}" if parts.query else ""))
    return keys


def _identity_targets(identity):
    kind, _, rest = identity.partition(":")
    if kind == "url":
        return apply_targets(rest)
    if kind in {"greenhouse", "lever", "ashby"} and rest:
        return {f"{kind}:{rest.rsplit(':', 1)[-1]}"}
    return set()


def _places(value):
    """Place names, country codes and a remote flag from a free-text location."""
    text = _fold(value)
    remote = bool(_REMOTE.search(text))
    places, countries = set(), set()
    for part in _PLACE_SPLIT.split(_REMOTE.sub(" ", text)):
        name = " ".join(
            token for token in words(part) if token not in _PLACE_NOISE and not token.isdigit()
        )
        if name in _COUNTRY_CODE:
            countries.add(_COUNTRY_CODE[name])
        elif len(name) > 2:  # shorter parts are state or canton codes
            places.add(_EXONYMS.get(name, name))
    return frozenset(places), frozenset(countries), remote


def _day(value):
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            seconds = value / 1000 if value > 1e11 else value
            return datetime.fromtimestamp(seconds, UTC).date().toordinal()
        return date.fromisoformat(str(value)[:10]).toordinal()
    except ValueError, OverflowError, OSError:
        return None


class Features:
    """What one job contributes to duplicate scoring; small enough to keep cached."""

    __slots__ = (
        "company",
        "countries",
        "created",
        "created_at",
        "fingerprint",
        "id",
        "legacy",
        "location",
        "place_words",
        "places",
        "posted",
        "references",
        "remote",
        "seniority",
        "sketch",
        "targets",
        "title",
        "title_words",
    )


def job_features(job):
    """Features of a job mapping: id, title, company, location, url, posting and,
    optionally, metadata, created_at, identities and other known posting URLs."""
    features = Features()
    features.id = job.get("id")
    title, posting = job.get("title") or "", job.get("posting") or ""
    metadata = job.get("metadata") or {}
    legacy_title = normalize_title(title)
    # Requisition numbers in a title are compared as references, not as words.
    tokens = words(_fold(normalize_title(_TITLE_REFERENCE.sub(" ", title))))
    features.title = " ".join(tokens)
    features.title_words = frozenset(tokens)
    features.seniority = features.title_words & _SENIORITY
    features.company = normalize_company(job.get("company"))
    # The grouping key of releases before confidence scores; kept so that every
    # earlier candidate stays a candidate.
    legacy_company = words(job.get("company"))
    while len(legacy_company) > 1 and legacy_company[-1] in _LEGAL:
        legacy_company.pop()
    features.legacy = (
        (" ".join(legacy_company), legacy_title) if legacy_title and legacy_company else None
    )
    features.location = normalize_location(job.get("location"))
    features.places, features.countries, features.remote = _places(job.get("location"))
    features.place_words = frozenset(words(_fold(job.get("location"))))
    features.references = reference_ids(title, posting)
    targets = apply_targets(job.get("url") or "")
    for identity in job.get("identities") or ():
        targets |= _identity_targets(identity)
    for url in job.get("urls") or ():
        targets |= apply_targets(url or "")
    if metadata.get("ats") in {"greenhouse", "lever", "ashby"} and metadata.get("external_id"):
        targets.add(f"{metadata['ats']}:{metadata['external_id']}")
    features.targets = frozenset(targets)
    features.fingerprint, features.sketch = _text_features(posting)
    features.posted = next(
        filter(
            None, (_day(metadata.get(key)) for key in ("date_posted", "published_at", "posted_at"))
        ),
        None,
    )
    features.created_at = job.get("created_at") or ""
    features.created = _day(features.created_at)
    return features


def compare_location(a, b):
    """'agree', 'conflict' or None when the locations cannot be compared."""
    if a.countries and b.countries and not a.countries & b.countries:
        return "conflict"
    if a.places and b.places:
        for first in a.places:
            for second in b.places:
                x, y = set(first.split()), set(second.split())
                if x <= y or y <= x:
                    return "agree"
        return None if a.remote or b.remote else "conflict"
    if a.places or b.places:
        return None
    if a.countries & b.countries or (a.remote and b.remote):
        return "agree"
    return "agree" if a.location and a.location == b.location else None


def compare_title(a, b):
    """'same', 'similar', 'seniority' (same role, another level) or None."""
    if not a.title or not b.title:
        return None
    if a.title == b.title:
        return "same"
    decoration = a.place_words | b.place_words | _TITLE_NOISE
    first = {t for t in a.title_words if t not in decoration and not (t.isdigit() and len(t) > 1)}
    second = {t for t in b.title_words if t not in decoration and not (t.isdigit() and len(t) > 1)}
    if not first or not second:
        return None
    if first == second:
        return "same"
    if first - _SENIORITY == second - _SENIORITY:
        return "seniority"
    return "similar" if first <= second or second <= first else None


def posted_apart(a, b):
    """Published (or, when the source gave no date, first collected) far apart."""
    first, second = a.posted or a.created, b.posted or b.created
    return bool(first and second) and abs(first - second) > REPOST_DAYS
