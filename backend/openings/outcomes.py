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
no-reply period: the number in the policy's decision item labelled "No reply"
(``no_reply_period``), or 30 days.
"""

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .actors import current_actor, pop_actor
from .common import new_id, now
from .errors import DomainError, conflict, missing
from .models import Input, Versioned, past_day

ResponseKind = Literal["rejection", "interview", "offer", "other"]
DEFAULT_REPLY_DAYS = 30
_NO_REPLY_LABEL = re.compile(r"\bno[\s-]?(reply|response)\b", re.IGNORECASE)
_DAYS = re.compile(r"^\s*(\d{1,4})(\s*days?)?\s*$", re.IGNORECASE)

SENT_SQL = "(app.applied_at IS NOT NULL OR app.status IN ('applied','interview','offer'))"


def today():
    """Today's calendar day in UTC, the default day of a response or a closing."""
    return datetime.now(UTC).date().isoformat()


class ResponseInput(Input):
    kind: ResponseKind = Field(
        description="rejection, interview (an invitation), offer or other (any other employer answer)."
    )
    date: str = Field(description="The day the employer responded: YYYY-MM-DD, not in the future.")
    note: str = Field(default="", max_length=2000)
    idempotency_key: str | None = Field(default=None, max_length=100)

    @field_validator("date")
    @classmethod
    def valid_day(cls, value):
        return past_day(value)


class ResponsePatch(Versioned):
    kind: ResponseKind | None = None
    date: str | None = Field(
        default=None,
        description="The corrected day (YYYY-MM-DD, not in the future); clears estimated.",
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
    """A response as returned by reads."""
    row = dict(row)
    row["estimated"] = bool(row["estimated"])
    row["created_by"] = pop_actor(row, "created_by")
    row["updated_by"] = pop_actor(row, "updated_by")
    row.pop("idempotency_key", None)
    return row


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
    """The newest response of each application: kind, date, estimated; None without one."""
    result = dict.fromkeys(application_ids)
    if not application_ids:
        return result
    marks = ",".join("?" for _ in application_ids)
    for row in conn.execute(
        "SELECT application_id,id,kind,date,estimated,count FROM (SELECT r.application_id,r.id,"
        "r.kind,r.date,r.estimated,count(*) OVER (PARTITION BY r.application_id) AS count,"
        "row_number() OVER (PARTITION BY r.application_id ORDER BY r.date DESC,r.created_at DESC,"
        f"r.id) AS position FROM responses r WHERE r.application_id IN ({marks})) WHERE position=1",
        list(application_ids),
    ):
        result[row[0]] = {
            "id": row[1],
            "kind": row[2],
            "date": row[3],
            "estimated": bool(row[4]),
            "count": row[5],
        }
    return result


def reply_days(value):
    """The number of days a policy value states: 45, "45" or "45 days"; None otherwise."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and float(value).is_integer():
        days = int(value)
    elif isinstance(value, str) and (match := _DAYS.match(value)):
        days = int(match.group(1))
    else:
        return None
    return days if 1 <= days <= 3650 else None


def no_reply_period(conn):
    """The no-reply period: the policy's "No reply" decision item with a number of days.

    A confirmed item comes before a proposal, then the section's order. Without
    one the period is 30 days. ``confirmed`` tells an agent whether the owner set
    the rule under which it may close applications as no_response.
    """
    for row in conn.execute(
        "SELECT id,label,value,confirmed_at FROM policy_items WHERE section='decision' "
        "AND value IS NOT NULL ORDER BY confirmed_at IS NULL,position,created_at,id"
    ):
        if not _NO_REPLY_LABEL.search(row[1] or ""):
            continue
        days = reply_days(json.loads(row[2]))
        if days is not None:
            return {
                "days": days,
                "source": "policy",
                "item_id": row[0],
                "confirmed": row[3] is not None,
            }
    return {"days": DEFAULT_REPLY_DAYS, "source": "default", "item_id": None, "confirmed": False}


def no_reply_cutoff(days):
    """Applications sent before this time have waited longer than ``days``."""
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="microseconds")


def not_sent():
    return DomainError(
        409,
        "application_not_sent",
        "Record the application as sent (Applied) before recording an employer response.",
    )


def record_response(
    workspace, conn, application, kind, day, note="", origin="manual", idempotency_key=None
):
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
    response_id, stamp, actor = new_id(), now(), current_actor()
    conn.execute(
        "INSERT INTO responses(id,application_id,kind,date,note,origin,"
        "created_by_kind,created_by_id,created_by_name,created_by_token_kind,"
        "updated_by_kind,updated_by_id,updated_by_name,updated_by_token_kind,"
        "idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            response_id,
            application["id"],
            kind,
            day,
            note,
            origin,
            *actor.columns(),
            *actor.columns(),
            idempotency_key,
            stamp,
            stamp,
        ),
    )
    workspace.event(
        "response_added",
        application["job_id"],
        application["id"],
        {"kind": kind, "date": day, "origin": origin},
        conn,
        subject=("response", response_id),
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
        with self.db.transaction() as conn:
            if value.idempotency_key:
                old = conn.execute(
                    "SELECT id,application_id,kind,date FROM responses WHERE idempotency_key=?",
                    (value.idempotency_key,),
                ).fetchone()
                if old:
                    if tuple(old)[1:] != (application_id, value.kind, value.date):
                        conflict("This idempotency key was used for another response.")
                    return self._read(conn, old["id"])
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
                idempotency_key=value.idempotency_key,
            )
            return self._read(conn, response_id)

    def update_response(self, response_id, value):
        """Correct a response's kind, day or note with its version; a corrected day is no longer estimated."""
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
            if "date" in actual:
                actual["estimated"] = 0
            conn.execute(
                "UPDATE responses SET "
                + ",".join(key + "=?" for key in actual)
                + ",updated_by_kind=?,updated_by_id=?,updated_by_name=?,updated_by_token_kind=?,"
                "version=version+1,updated_at=? WHERE id=?",
                (*actual.values(), *current_actor().columns(), now(), response_id),
            )
            self.workspace.event(
                "response_edited",
                current["job_id"],
                current["application_id"],
                {"fields": fields, "version": current["version"] + 1},
                conn,
                subject=("response", response_id),
            )
            return self._read(conn, response_id)

    def remove_response(self, response_id, expected_version):
        """Delete a response recorded by mistake, with its version."""
        with self.db.transaction() as conn:
            current = self._read(conn, response_id)
            if current["version"] != expected_version:
                conflict(details={"current_version": current["version"]})
            conn.execute("DELETE FROM responses WHERE id=?", (response_id,))
            self.workspace.event(
                "response_removed",
                current["job_id"],
                current["application_id"],
                {"kind": current["kind"], "date": current["date"]},
                conn,
                subject=("response", response_id),
            )
        return {"deleted": True, "id": response_id}

