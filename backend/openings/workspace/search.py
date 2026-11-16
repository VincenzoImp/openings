"""Text search over jobs and applications: which rows match ``q``, and in what order.

One definition for every reader: jobs_list and applications_list (REST and MCP)
and the dashboard's search all go through it. Each word must start a word of the
job's title, company, location or posting text (or of the application's pinned
note); a word that names a state (``dismissed``, ``interview``) also matches the
rows in that state. Ranked: the exact title, then a title holding the words in
order, then rows whose every word is in the title, company, location or state,
then the rest (words found only in the posting or a note).
"""

import re

MAX_TERMS = 15

# A job whose indexed title, company or posting matches (a column filter narrows it).
_FTS = "j.rowid IN (SELECT rowid FROM jobs_fts WHERE jobs_fts MATCH ?)"
# The location's words: separators become spaces, so each word follows one.
_LOCATION = (
    "(' '||lower(replace(replace(replace(replace(coalesce(j.location,''),"
    "',',' '),'/',' '),'(',' '),'-',' '))) LIKE ? ESCAPE '\\'"
)
_NOTE = (
    "EXISTS(SELECT 1 FROM notes n WHERE n.application_id=app.id AND n.pinned_at IS NOT NULL "
    "AND (' '||lower(n.body)) LIKE ? ESCAPE '\\')"
)

JOB_STATES = {
    "new": "j.triage='new'",
    "shortlisted": "j.triage='shortlisted'",
    "dismissed": "j.triage='dismissed'",
}


def search_terms(q):
    """The words of ``q``, lowercased, at most ``MAX_TERMS``."""
    return [word.lower() for word in re.findall(r"\w+", q or "")][:MAX_TERMS]


def _like(word):
    return "% " + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _states(word, states):
    """The states a word names: their name, its plural, or a start of three letters or more."""
    return [
        sql
        for name, sql in states.items()
        if (name.startswith(word) and (len(word) >= 3 or word == name))
        or (word.startswith(name) and len(word) <= len(name) + 1)
    ]


def search_sql(q, states, notes=False):
    """``(where, args, rank, rank_args)`` for ``q``, or ``None`` without a word.

    ``where`` keeps the rows where every word matches; ``rank`` orders them, best
    first, and goes before the list's own order.
    """
    words = search_terms(q)
    if not words:
        return None
    where, where_args, strong, strong_args = [], [], [], []
    for word in words:
        prefix = '"' + word + '"*'
        named = _states(word, states)
        heading = [_FTS, _LOCATION, *named]
        heading_args = ["{title company} : " + prefix, _like(word)]
        strong.append("(" + " OR ".join(heading) + ")")
        strong_args.extend(heading_args)
        anywhere = [_FTS, _LOCATION, *named] + ([_NOTE] if notes else [])
        where.append("(" + " OR ".join(anywhere) + ")")
        where_args.extend([prefix, _like(word)] + ([_like(word)] if notes else []))
    phrase = " ".join(words)
    rank = (
        "CASE WHEN lower(trim(j.title))=? THEN 0 "
        "WHEN (' '||lower(j.title)) LIKE ? ESCAPE '\\' THEN 1 "
        "WHEN " + " AND ".join(strong) + " THEN 2 ELSE 3 END"
    )
    return " AND ".join(where), where_args, rank, [phrase, _like(phrase), *strong_args]
