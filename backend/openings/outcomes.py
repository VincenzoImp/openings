"""Employer replies to sent applications, and the no-reply period.

A reply is what an employer did about an application the owner sent: an
``interview`` invitation, a ``rejection``, an ``offer`` or ``other`` (any other
answer, such as a request for more documents). It has the day it arrived, an
optional note and who recorded it. Only an application recorded as sent (with
``applied_at``, or in Applied, Interview or Offer) can have replies, so an
application closed without being sent never counts as an employer signal.

Replies are written through ``Workspace.update_application`` only (its ``reply``):
recording one moves the stage when its kind implies it (``stage_after_reply``) in
the same transaction and with one event; a correction or removal never moves it.

"No reply" is not a reply but an outcome, ``no_response``, closed by hand after
the no-reply period: the setting ``no_reply_days`` (``no_reply_period``), 30 days by
default. Nothing closes an application automatically.
"""

from datetime import UTC, datetime, timedelta

from .actors import current_actor, pop_actor
from .common import new_id, now
from .errors import DomainError
from .preferences import no_reply_days

SENT_SQL = "(app.applied_at IS NOT NULL OR app.status IN ('applied','interview','offer'))"

# The stage a reply moves an application to, from the stages it moves it from. A
# Closed application without an answer (no_response) is reopened by a later reply.
_REPLY_STAGES = {
    "interview": ("interview", None, {"applied"}),
    "offer": ("offer", None, {"applied", "interview"}),
    "rejection": ("closed", "rejected", {"applied", "interview", "offer"}),
}


def today():
    """Today's calendar day in UTC, the default day of a reply or a closing."""
    return datetime.now(UTC).date().isoformat()


def stage_after_reply(status, outcome, kind):
    """(status, outcome) a new reply of ``kind`` moves the application to, or None."""
    if kind not in _REPLY_STAGES:
        return None
    target, result, sources = _REPLY_STAGES[kind]
    if status in sources or (status == "closed" and outcome == "no_response"):
        return target, result
    return None


def reply_record(row):
    """A reply as returned by reads."""
    row = dict(row)
    row["created_by"] = pop_actor(row, "created_by")
    row["updated_by"] = pop_actor(row, "updated_by")
    return row


def replies_of(conn, application_ids):
    """Replies per application, newest day first."""
    result = {identifier: [] for identifier in application_ids}
    if not application_ids:
        return result
    marks = ",".join("?" for _ in application_ids)
    for row in conn.execute(
        f"SELECT r.*,a.job_id FROM replies r JOIN applications a ON a.id=r.application_id "
        f"WHERE r.application_id IN ({marks}) ORDER BY r.date DESC,r.created_at DESC,r.id",
        list(application_ids),
    ):
        result[row["application_id"]].append(reply_record(row))
    return result


def last_replies(conn, application_ids):
    """The newest reply of each application: kind, date and count; None without one."""
    result = dict.fromkeys(application_ids)
    if not application_ids:
        return result
    marks = ",".join("?" for _ in application_ids)
    for row in conn.execute(
        "SELECT application_id,id,kind,date,count FROM (SELECT r.application_id,r.id,"
        "r.kind,r.date,count(*) OVER (PARTITION BY r.application_id) AS count,"
        "row_number() OVER (PARTITION BY r.application_id ORDER BY r.date DESC,r.created_at DESC,"
        f"r.id) AS position FROM replies r WHERE r.application_id IN ({marks})) WHERE position=1",
        list(application_ids),
    ):
        result[row[0]] = {
            "id": row[1],
            "kind": row[2],
            "date": row[3],
            "count": row[4],
        }
    return result


def no_reply_period(conn):
    """The no-reply period: ``{days, source}``, source ``settings`` or ``default`` (30 days)."""
    days, source = no_reply_days(conn)
    return {"days": days, "source": source}


def no_reply_cutoff(days):
    """Applications sent before this time have waited longer than ``days``."""
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="microseconds")


def not_sent():
    return DomainError(
        409,
        "application_not_sent",
        "Mark the application applied before recording an employer reply.",
    )


def duplicate_reply(conn, application_id, kind, day, excluding=None):
    """Refuse a second reply of one kind on one day (other replies may repeat)."""
    if kind == "other":
        return
    row = conn.execute(
        "SELECT id FROM replies WHERE application_id=? AND kind=? AND date=? "
        "AND (? IS NULL OR id<>?)",
        (application_id, kind, day, excluding, excluding),
    ).fetchone()
    if row:
        raise DomainError(
            409,
            "reply_exists",
            "This application already has a reply of this kind on that day.",
            {"reply_id": row[0]},
        )


def insert_reply(conn, application_id, kind, day, note=""):
    """Insert one reply in the caller's transaction; the caller records the event."""
    reply_id, stamp, actor = new_id(), now(), current_actor()
    conn.execute(
        "INSERT INTO replies(id,application_id,kind,date,note,"
        "created_by_kind,created_by_id,created_by_name,created_by_token_kind,"
        "updated_by_kind,updated_by_id,updated_by_name,updated_by_token_kind,"
        "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            reply_id,
            application_id,
            kind,
            day,
            note,
            *actor.columns(),
            *actor.columns(),
            stamp,
            stamp,
        ),
    )
    return reply_id
