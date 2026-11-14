"""Employer responses to sent applications, and the no-reply period.

A response is what an employer did about an application the owner sent: a
``rejection``, an ``interview`` invitation, an ``offer`` or ``other`` (any other
answer, such as a request for more documents). It has the day it arrived, an
optional note and who recorded it. Only an application recorded as sent (with
``applied_at``, or in Applied, Interview or Offer) can have responses, so a Draft
the owner closed without applying never counts as an employer signal.

Moving an application to Interview or Offer, or closing it as rejected (or as
accepted without an offer on record), records the matching response through
``Workspace.update_application``; ``record_response`` is shared by both paths.
The date stays correctable here.

"No reply" is not a response but an outcome, ``no_response``, closed after the
no-reply period: the setting ``no_reply_days`` (``no_reply_period``), 30 days by
default.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import Field, field_validator, model_validator

from . import events
from .actors import current_actor
from .common import new_id, now
from .errors import DomainError, conflict, missing
from .idempotency import fingerprint, remember, replay
from .models import Input, Versioned, past_day
from .preferences import no_reply_days

ResponseKind = Literal["rejection", "interview", "offer", "other"]

SENT_SQL = "(app.applied_at IS NOT NULL OR app.status IN ('applied','interview','offer'))"


def today():
    """Today's calendar day in UTC, the default day of a response or a closing."""
    return datetime.now(UTC).date().isoformat()


class ResponseInput(Input):
    kind: ResponseKind = Field(
        description="rejection, interview (an invitation), offer or other (any other employer answer)."
    )
    date: str = Field(
        default_factory=today,
        description="The day the employer responded: YYYY-MM-DD, not in the future; today when omitted.",
    )
    note: str = Field(default="", max_length=2000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("date")
    @classmethod
    def valid_day(cls, value):
        return past_day(value)


class ResponsePatch(Versioned):
    kind: ResponseKind | None = None
    date: str | None = Field(
        default=None,
        description="The corrected day (YYYY-MM-DD, not in the future).",
    )
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("date")
    @classmethod
    def valid_day(cls, value):
        return past_day(value)

    @model_validator(mode="after")
    def no_nulls(self):
        for key in self.model_fields_set & {"kind", "date", "note"}:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null; omit it to keep the existing value.")
        return self


def response_record(row):
    """A response as returned by reads; created_by and updated_by are actor labels."""
    return dict(row)


def responses_of(conn, application_ids):
    """Responses per application, newest day first."""
    result = {identifier: [] for identifier in application_ids}
    if not application_ids:
        return result
    marks = ",".join("?" for _ in application_ids)
    for row in conn.execute(
        f"SELECT r.*,a.job_id FROM responses r JOIN applications a ON a.id=r.application_id "
        f"WHERE r.application_id IN ({marks}) ORDER BY r.date DESC,r.created_at DESC,r.id",
        list(application_ids),
    ):
        result[row["application_id"]].append(response_record(row))
    return result


def last_responses(conn, application_ids):
    """The newest response of each application: kind, date and count; None without one."""
    result = dict.fromkeys(application_ids)
    if not application_ids:
        return result
    marks = ",".join("?" for _ in application_ids)
    for row in conn.execute(
        "SELECT application_id,id,kind,date,count FROM (SELECT r.application_id,r.id,"
        "r.kind,r.date,count(*) OVER (PARTITION BY r.application_id) AS count,"
        "row_number() OVER (PARTITION BY r.application_id ORDER BY r.date DESC,r.created_at DESC,"
        f"r.id) AS position FROM responses r WHERE r.application_id IN ({marks})) WHERE position=1",
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
        "Record the application as sent (Applied) before recording an employer response.",
    )


def record_response(workspace, conn, application, kind, day, note=""):
    """Insert one response in the caller's transaction, with its event.

    Returns the new id, or None when a response of this kind already exists for
    that day (a stage change never records the same answer twice).
    """
    if (
        kind != "other"
        and conn.execute(
            "SELECT 1 FROM responses WHERE application_id=? AND kind=? AND date=?",
            (application["id"], kind, day),
        ).fetchone()
    ):
        return None
    response_id, stamp, by = new_id(), now(), current_actor().label
    conn.execute(
        "INSERT INTO responses(id,application_id,kind,date,note,created_by,updated_by,"
        "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            response_id,
            application["id"],
            kind,
            day,
            note,
            by,
            by,
            stamp,
            stamp,
        ),
    )
    events.record(
        conn,
        "response_added",
        subject=("response", response_id),
        payload={"kind": kind, "date": day},
        job_id=application["job_id"],
        application_id=application["id"],
    )
    return response_id


class ResponseService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db

    @staticmethod
    def _read(conn, response_id):
        row = conn.execute(
            "SELECT r.*,a.job_id FROM responses r JOIN applications a ON a.id=r.application_id "
            "WHERE r.id=?",
            (response_id,),
        ).fetchone()
        if row is None:
            missing("Response")
        return response_record(row)

    @staticmethod
    def _application(conn, application_id):
        row = conn.execute(
            f"SELECT app.id,app.job_id,{SENT_SQL} AS sent FROM applications app WHERE app.id=?",
            (application_id,),
        ).fetchone()
        if row is None:
            missing("Application")
        return dict(row)

    @staticmethod
    def _duplicate(conn, application_id, kind, day, excluding=None):
        if kind == "other":
            return
        row = conn.execute(
            "SELECT id FROM responses WHERE application_id=? AND kind=? AND date=? "
            "AND (? IS NULL OR id<>?)",
            (application_id, kind, day, excluding, excluding),
        ).fetchone()
        if row:
            raise DomainError(
                409,
                "response_exists",
                "This application already has a response of this kind on that day.",
                {"response_id": row[0]},
            )

    def list_responses(self, application_id):
        """The employer responses of one application, newest day first."""
        with self.db.connect() as conn:
            self._application(conn, application_id)
            items = responses_of(conn, [application_id])[application_id]
        return {"items": items, "total": len(items)}

    def add_response(self, application_id, value):
        """Record an employer response to a sent application. It never moves the stage."""
        value = value if isinstance(value, ResponseInput) else ResponseInput.model_validate(value)
        digest = fingerprint({"application_id": application_id, **value.model_dump(mode="json")})
        with self.db.transaction() as conn:
            replayed = replay(conn, "responses", value.idempotency_key, digest)
            if replayed:
                return self._read(conn, replayed)
            application = self._application(conn, application_id)
            if not application["sent"]:
                raise not_sent()
            self._duplicate(conn, application_id, value.kind, value.date)
            response_id = record_response(
                self.workspace,
                conn,
                application,
                value.kind,
                value.date,
                value.note,
            )
            remember(conn, "responses", value.idempotency_key, digest, response_id)
            return self._read(conn, response_id)

    def update_response(self, response_id, value):
        """Correct a response's kind, day or note with its version."""
        value = value if isinstance(value, ResponsePatch) else ResponsePatch.model_validate(value)
        changes = value.model_dump(exclude_unset=True, exclude={"expected_version"})
        with self.db.transaction() as conn:
            current = self._read(conn, response_id)
            if current["version"] != value.expected_version:
                conflict(details={"current_version": current["version"]})
            actual = {key: val for key, val in changes.items() if current[key] != val}
            if not actual:
                return current
            kind = actual.get("kind", current["kind"])
            day = actual.get("date", current["date"])
            if "kind" in actual or "date" in actual:
                self._duplicate(conn, current["application_id"], kind, day, excluding=response_id)
            fields = sorted(actual)
            conn.execute(
                "UPDATE responses SET "
                + ",".join(key + "=?" for key in actual)
                + ",updated_by=?,version=version+1,updated_at=? WHERE id=?",
                (*actual.values(), current_actor().label, now(), response_id),
            )
            events.record(
                conn,
                "response_edited",
                subject=("response", response_id),
                payload={"fields": fields, "version": current["version"] + 1},
                job_id=current["job_id"],
                application_id=current["application_id"],
            )
            return self._read(conn, response_id)

    def remove_response(self, response_id, expected_version):
        """Delete a response recorded by mistake, with its version."""
        with self.db.transaction() as conn:
            current = self._read(conn, response_id)
            if current["version"] != expected_version:
                conflict(details={"current_version": current["version"]})
            conn.execute("DELETE FROM responses WHERE id=?", (response_id,))
            events.record(
                conn,
                "response_removed",
                subject=("response", response_id),
                payload={"kind": current["kind"], "date": current["date"]},
                job_id=current["job_id"],
                application_id=current["application_id"],
            )
        return {"deleted": True, "id": response_id}
