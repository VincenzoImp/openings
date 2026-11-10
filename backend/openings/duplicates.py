"""Read-only duplicate candidates. Signals only suggest a review; nothing merges here."""

import hashlib
import re

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
# Short or empty postings carry too little text to suggest a shared vacancy.
MIN_POSTING_WORDS = 60
_POSTING_CHARS = 50_000
_SHINGLE_WORDS = 3_000


def words(value):
    return re.findall(r"\w+", (value or "").lower())


def normalize_title(value):
    return " ".join(words(_MARKER.sub(" ", (value or "").lower())))


def normalize_company(value):
    tokens = words(value)
    while len(tokens) > 1 and tokens[-1] in _LEGAL:
        tokens.pop()
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


def candidate_groups(rows, match_location=False):
    """Group rows by normalized company + title (and location), or identical text.

    Each row needs id, title, company, location and fingerprint. Returns lists of
    member IDs with the signals that joined them; groups have at least two jobs.
    """
    parent = {row["id"]: row["id"] for row in rows}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    buckets = {}
    for row in rows:
        title, company = normalize_title(row["title"]), normalize_company(row["company"])
        if title and company:
            key = (company, title)
            if match_location:
                key += (normalize_location(row["location"]),)
            buckets.setdefault(("company_title", key), []).append(row["id"])
        if row["fingerprint"]:
            buckets.setdefault(("posting_text", row["fingerprint"]), []).append(row["id"])
    signals = {}
    for (signal, _key), members in buckets.items():
        if len(members) < 2:
            continue
        for member in members[1:]:
            parent[find(member)] = find(members[0])
        signals.setdefault(members[0], set()).add(signal)
    groups = {}
    for row in rows:
        groups.setdefault(find(row["id"]), []).append(row["id"])
    found_signals = {}
    for member, kinds in signals.items():
        found_signals.setdefault(find(member), set()).update(kinds)
    return [
        {"ids": members, "signals": sorted(found_signals.get(root, ()))}
        for root, members in groups.items()
        if len(members) > 1
    ]
