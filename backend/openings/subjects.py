"""The optional subject of a question or a request: a job, an application or a Career entry.

Both records reference their subject with ``ON DELETE SET NULL`` and keep its
name at the time of writing, so they stay readable after the subject is deleted
and follow a job through a merge.
"""

from typing import Literal

from .errors import missing

SubjectType = Literal["job", "application", "knowledge"]
SUBJECT_COLUMNS = {"job": "job_id", "application": "application_id", "knowledge": "knowledge_id"}
SUBJECT_NAMES = {"job": "Job", "application": "Application", "knowledge": "Career knowledge"}


def label(*parts):
    return " · ".join(part for part in parts if part)


def select(table, alias):
    """Rows of ``table`` joined with the current names of their subjects."""
    return (
        f"SELECT {alias}.*,j.title AS job_title,j.company AS job_company,a.job_id AS application_job_id,"
        "aj.title AS application_title,aj.company AS application_company,"
        f"k.title AS knowledge_title,k.organization AS knowledge_organization FROM {table} {alias} "
        f"LEFT JOIN jobs j ON j.id={alias}.job_id LEFT JOIN applications a ON a.id={alias}.application_id "
        f"LEFT JOIN jobs aj ON aj.id=a.job_id LEFT JOIN knowledge k ON k.id={alias}.knowledge_id"
    )


def resolve(conn, subject_type, subject_id, *, required=True):
    """The owning job (for the timeline) and the current name of a subject."""
    if subject_type == "job":
        row = conn.execute(
            "SELECT id AS job_id,title,company FROM jobs WHERE id=?", (subject_id,)
        ).fetchone()
    elif subject_type == "application":
        row = conn.execute(
            "SELECT j.id AS job_id,j.title,j.company FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?",
            (subject_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT NULL AS job_id,title,organization FROM knowledge WHERE id=?", (subject_id,)
        ).fetchone()
    if row is None:
        if required:
            missing(SUBJECT_NAMES[subject_type])
        return None, ""
    return row[0], label(row[1], row[2])


def references(subject_type, subject_id):
    """The three reference columns of a new record; at most one is set."""
    return {
        column: subject_id if key == subject_type else None
        for key, column in SUBJECT_COLUMNS.items()
    }


def pop(row):
    """Remove the subject columns of a joined row and return the subject, or None."""
    kind = row.pop("subject_type")
    snapshot = row.pop("subject_label")
    ids = {key: row.pop(column) for key, column in SUBJECT_COLUMNS.items()}
    live = {
        "job": label(row.pop("job_title"), row.pop("job_company")),
        "application": label(row.pop("application_title"), row.pop("application_company")),
        "knowledge": label(row.pop("knowledge_title"), row.pop("knowledge_organization")),
    }
    application_job = row.pop("application_job_id")
    if not kind:
        return None
    return {
        "type": kind,
        "id": ids[kind],
        # The name at the time of writing outlives the record it named.
        "label": live[kind] if ids[kind] else snapshot,
        "deleted": ids[kind] is None,
        "job_id": ids["job"] if kind == "job" else application_job,
    }


def timeline(conn, row):
    """The job and application whose history shows a change to this stored record."""
    job_id = row["job_id"]
    if row["application_id"]:
        job_id = conn.execute(
            "SELECT job_id FROM applications WHERE id=?", (row["application_id"],)
        ).fetchone()[0]
    return job_id, row["application_id"]


def add_filter(alias, subject_type, subject_id, where, params):
    """Add a subject filter to a list query."""
    if subject_type:
        where.append(f"{alias}.subject_type=?")
        params.append(subject_type)
        if subject_id is not None:
            where.append(f"{alias}.{SUBJECT_COLUMNS[subject_type]}=?")
            params.append(subject_id)
