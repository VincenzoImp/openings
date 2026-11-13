"""Requests for the agent: owner instructions an agent reads at the start of its next run.

The mirror of questions for the owner. The owner writes a request, optionally
about a job, an application or a Career entry; an agent takes it, then completes
it with a result or declines it with a reason. The server runs no agent, so the
exchange is asynchronous. A request never widens what the operating mandate
allows: it cannot authorise submitting, contacting an employer or recording
Applied.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from . import subjects
from .actors import current_actor, pop_actor, require_owner
from .common import check_version, new_id, now
from .errors import DomainError, conflict, missing
from .models import Input, normalized_date
from .subjects import SubjectType

RequestState = Literal["open", "taken", "done", "declined", "withdrawn"]
REQUESTS = subjects.select("requests", "r")


class RequestCreate(Input):
    text: str = Field(
        min_length=1, max_length=4000, description="What the agent should do, in plain language."
    )
    subject_type: SubjectType | None = Field(
        default=None, description="knowledge is a Career entry. Omit for a general request."
    )
    subject_id: str | None = Field(default=None, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Write the request.")
        return value.strip()

    @model_validator(mode="after")
    def whole_reference(self):
        if (self.subject_type is None) != (self.subject_id is None):
            raise ValueError("Provide subject_type and subject_id together.")
        return self


class RequestVersion(Input):
    expected_version: int = Field(ge=1)


class RequestComplete(Input):
    expected_version: int = Field(ge=1)
    result: str = Field(
        min_length=1,
        max_length=8000,
        description="What was done, with record ids where useful. Shown to the owner.",
    )


class RequestDecline(Input):
    expected_version: int = Field(ge=1)
    reason: str = Field(
        min_length=1,
        max_length=8000,
        description="Why the request was not carried out, for example an operating-mandate limit.",
    )


class RequestQuery(Input):
    state: RequestState | None = None
    subject_type: SubjectType | None = None
    subject_id: str | None = Field(default=None, max_length=100)
    run_id: str | None = Field(default=None, max_length=100)
    updated_since: str | None = Field(
        default=None,
        description="Only requests written or changed at or after this time, oldest change first.",
    )
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @field_validator("updated_since")
    @classmethod
    def valid_date(cls, value):
        return normalized_date(value)

    @model_validator(mode="after")
    def whole_reference(self):
        if self.subject_id is not None and self.subject_type is None:
            raise ValueError("Provide subject_type when filtering by subject_id.")
        return self


def request_record(row):
    """A request as returned by reads: subject, actors, the run that handled it and the result."""
    if row is None:
        missing("Request")
    row = dict(row)
    row["subject"] = subjects.pop(row)
    row["created_by"] = pop_actor(row, "created_by")
    for prefix in ("taken_by", "resolved_by"):
        actor = pop_actor(row, prefix)
        row[prefix] = None if actor["kind"] == "unknown" else actor
    row.pop("idempotency_key")
    return row


class RequestService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db

    def _read(self, conn, request_id):
        return request_record(conn.execute(REQUESTS + " WHERE r.id=?", (request_id,)).fetchone())

    def _event(self, conn, kind, row):
        self.workspace.event(
            kind,
            *subjects.timeline(conn, row),
            {"request_id": row["id"]},
            conn,
            subject=("request", row["id"]),
        )

    @staticmethod
    def _agent(action):
        actor = current_actor()
        if actor.kind != "token":
            raise DomainError(
                403,
                "request_actor",
                f"Only an API token can {action} a request. In the dashboard, withdraw it instead.",
            )
        return actor

    @staticmethod
    def _row(conn, request_id, expected_version, states, action):
        row = conn.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
        if row is None:
            missing("Request")
        if row["state"] not in states:
            raise DomainError(
                409,
                "request_taken" if row["state"] == "taken" else "request_closed",
                f"This request is {row['state']} and cannot be {action}.",
                {
                    "state": row["state"],
                    "current_version": row["version"],
                    "run_id": row["run_id"],
                },
            )
        check_version(row, expected_version)
        return row

    def count_open(self) -> int:
        """Requests no agent has taken yet."""
        return self.db.one("SELECT count(*) n FROM requests WHERE state='open'")["n"]

    def get_request(self, request_id: str) -> dict:
        """Read one request for the agent with its state, result and version."""
        with self.db.connect() as conn:
            return self._read(conn, request_id)

    def list_requests(self, value: RequestQuery | None = None) -> dict:
        """List requests for the agent by state, subject or run. updated_since returns the ones written or changed since a time."""
        value = (
            value if isinstance(value, RequestQuery) else RequestQuery.model_validate(value or {})
        )
        where, params = [], []
        if value.state:
            where.append("r.state=?")
            params.append(value.state)
        if value.updated_since:
            where.append("r.updated_at>=?")
            params.append(value.updated_since)
        subjects.add_filter("r", value.subject_type, value.subject_id, where, params)
        if value.run_id is not None:
            where.append("r.run_id=?")
            params.append(value.run_id)
        clause = " WHERE " + " AND ".join(where) if where else ""
        order = "r.updated_at" if value.updated_since else "r.created_at DESC"
        with self.db.connect() as conn:
            rows = conn.execute(
                REQUESTS + clause + f" ORDER BY {order} LIMIT ? OFFSET ?",
                (*params, value.limit, value.offset),
            ).fetchall()
            total = conn.execute("SELECT count(*) FROM requests r" + clause, params).fetchone()[0]
        return {"items": [request_record(row) for row in rows], "total": total}

    def create_request(self, value: RequestCreate) -> dict:
        """Write a request for the agent about a job, an application, a Career entry or nothing.

        A request is the owner's: the dashboard session or an owner token writes it.
        """
        require_owner("write a request for the agent")
        value = value if isinstance(value, RequestCreate) else RequestCreate.model_validate(value)
        actor = current_actor()
        request_id, stamp = new_id(), now()
        with self.db.transaction() as conn:
            if value.idempotency_key:
                old = conn.execute(
                    "SELECT id,text,created_by_kind,created_by_id FROM requests WHERE idempotency_key=?",
                    (value.idempotency_key,),
                ).fetchone()
                if old:
                    if (old["text"], old["created_by_kind"], old["created_by_id"]) != (
                        value.text,
                        actor.kind,
                        actor.id,
                    ):
                        conflict("This idempotency key was used for another request.")
                    return self._read(conn, old["id"])
            _, label = (
                subjects.resolve(conn, value.subject_type, value.subject_id)
                if value.subject_type
                else (None, "")
            )
            references = subjects.references(value.subject_type, value.subject_id)
            conn.execute(
                "INSERT INTO requests(id,subject_type,job_id,application_id,knowledge_id,subject_label,text,created_by_kind,created_by_id,created_by_name,created_by_token_kind,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    request_id,
                    value.subject_type,
                    references["job_id"],
                    references["application_id"],
                    references["knowledge_id"],
                    label,
                    value.text,
                    *actor.columns(),
                    value.idempotency_key,
                    stamp,
                    stamp,
                ),
            )
            self._event(conn, "request_created", {"id": request_id, **references})
            return self._read(conn, request_id)

    def take_request(self, request_id: str, value: RequestVersion) -> dict:
        """Take an open request: the calling token will handle it. Its open run, when there is one, is recorded."""
        value = value if isinstance(value, RequestVersion) else RequestVersion.model_validate(value)
        actor = self._agent("take")
        with self.db.transaction() as conn:
            row = self._row(conn, request_id, value.expected_version, ("open",), "taken")
            stamp = now()
            conn.execute(
                "UPDATE requests SET state='taken',taken_by_kind=?,taken_by_id=?,taken_by_name=?,taken_by_token_kind=?,taken_at=?,run_id=?,version=version+1,updated_at=? WHERE id=?",
                (
                    *actor.columns(),
                    stamp,
                    self.workspace.open_run_id(conn, actor),
                    stamp,
                    request_id,
                ),
            )
            self._event(conn, "request_taken", row)
            return self._read(conn, request_id)

    def _resolve(self, conn, row, kind, state, result=""):
        actor = current_actor()
        stamp = now()
        # The run that finishes the work is the one the owner wants to open.
        run_id = self.workspace.open_run_id(conn, actor) or row["run_id"]
        conn.execute(
            "UPDATE requests SET state=?,result=?,run_id=?,resolved_by_kind=?,resolved_by_id=?,resolved_by_name=?,resolved_by_token_kind=?,resolved_at=?,version=version+1,updated_at=? WHERE id=?",
            (state, result, run_id, *actor.columns(), stamp, stamp, row["id"]),
        )
        self._event(conn, kind, row)
        return self._read(conn, row["id"])

    def complete_request(self, request_id: str, value: RequestComplete) -> dict:
        """Complete an open or taken request with the result of the work."""
        value = (
            value if isinstance(value, RequestComplete) else RequestComplete.model_validate(value)
        )
        self._agent("complete")
        with self.db.transaction() as conn:
            row = self._row(
                conn, request_id, value.expected_version, ("open", "taken"), "completed"
            )
            return self._resolve(conn, row, "request_completed", "done", value.result)

    def decline_request(self, request_id: str, value: RequestDecline) -> dict:
        """Decline an open or taken request with the reason it was not carried out."""
        value = value if isinstance(value, RequestDecline) else RequestDecline.model_validate(value)
        self._agent("decline")
        with self.db.transaction() as conn:
            row = self._row(conn, request_id, value.expected_version, ("open", "taken"), "declined")
            return self._resolve(conn, row, "request_declined", "declined", value.reason)

    def withdraw_request(self, request_id: str, value: RequestVersion) -> dict:
        """Withdraw a request the agent has not finished. The record stays readable.

        Withdrawing is the owner's, like writing the request.
        """
        require_owner("withdraw a request for the agent")
        value = value if isinstance(value, RequestVersion) else RequestVersion.model_validate(value)
        with self.db.transaction() as conn:
            row = self._row(
                conn, request_id, value.expected_version, ("open", "taken"), "withdrawn"
            )
            return self._resolve(conn, row, "request_withdrawn", "withdrawn")
