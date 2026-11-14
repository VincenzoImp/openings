"""Ready, computed: the one definition used by lists, reads, counts and filters.

An application is Ready when it is Shortlisted, every document kind it requires
(``required_documents``, CV and letter by default) has a current complete revision
and no blocking employer requirement is unresolved. A revision is current when no
revision replaces it (no other revision names it as ``previous_id``) and complete
when its PDF is stored. ``missing`` names what is lacking: ``cv``, ``letter`` and
``requirement:<id>`` for each unresolved blocking requirement. Nothing about Ready
is stored, so it can never disagree with the documents.
"""

import json

DOCUMENT_KINDS = ("cv", "letter")

# The kinds a new application requires unless it says otherwise.
DEFAULT_REQUIRED = ["cv", "letter"]

# A current complete revision of kind ``{kind}`` of the application ``app``.
_COMPLETE = (
    "EXISTS(SELECT 1 FROM documents d WHERE d.application_id=app.id AND d.kind={kind} "
    "AND NOT EXISTS(SELECT 1 FROM documents child WHERE child.previous_id=d.id) "
    "AND EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id "
    "AND f.media_type='application/pdf'))"
)

# A required document kind without a current complete revision.
MISSING_DOCUMENTS_SQL = (
    "EXISTS(SELECT 1 FROM json_each(app.required_documents) k WHERE NOT "
    + _COMPLETE.format(kind="k.value")
    + ")"
)

BLOCKED_SQL = (
    "EXISTS(SELECT 1 FROM json_each(app.requirements) r WHERE json_extract(r.value,'$.blocking') "
    "AND NOT coalesce(json_extract(r.value,'$.resolved'),0))"
)

READY_SQL = f"(app.status='shortlisted' AND NOT {MISSING_DOCUMENTS_SQL} AND NOT {BLOCKED_SQL})"


def canonical_documents(kinds):
    """The stored form of required document kinds: distinct, in the order cv, letter."""
    return [kind for kind in DOCUMENT_KINDS if kind in set(kinds)]


def readiness(conn, rows):
    """Ready and missing of each application row (id, status, required_documents, requirements).

    One query reads the kinds with a current complete revision for the whole page.
    """
    result = {}
    if not rows:
        return result
    ids = [row["id"] for row in rows]
    marks = ",".join("?" for _ in ids)
    complete = {identifier: set() for identifier in ids}
    for application_id, kind in conn.execute(
        "SELECT DISTINCT d.application_id,d.kind FROM documents d "
        f"WHERE d.application_id IN ({marks}) AND d.kind IN ('cv','letter') "
        "AND NOT EXISTS(SELECT 1 FROM documents child WHERE child.previous_id=d.id) "
        "AND EXISTS(SELECT 1 FROM files f WHERE f.document_id=d.id "
        "AND f.media_type='application/pdf')",
        ids,
    ):
        complete[application_id].add(kind)
    for row in rows:
        required = _decoded(row["required_documents"])
        requirements = _decoded(row["requirements"])
        missing = [kind for kind in required if kind not in complete[row["id"]]]
        missing += [
            f"requirement:{item.get('id')}"
            for item in requirements
            if isinstance(item, dict) and item.get("blocking") and not item.get("resolved")
        ]
        result[row["id"]] = {
            "ready": row["status"] == "shortlisted" and not missing,
            "missing": missing,
        }
    return result


def _decoded(value):
    return json.loads(value) if isinstance(value, str) else value or []
