"""Agent runs with stored reports, questions for the owner and the attributed change log."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import Query
from pydantic import Field, field_validator, model_validator

from .actors import current_actor, describe, describe_row
from .common import check_version, encode, new_id, now
from .errors import DomainError, conflict, missing
from .models import Input, normalized_date

# An open run without a write or progress note for this long is reported as
# interrupted. The stored status stays open: a later write by the same token
# attaches to the run and makes it current again.
RUN_IDLE_SECONDS = 2 * 3600

SubjectType = Literal["job", "application", "knowledge"]
SUBJECT_COLUMNS = {"job": "job_id", "application": "application_id", "knowledge": "knowledge_id"}
RunStatus = Literal["open", "finished", "interrupted"]


class RunStart(Input):
    workflow: str = Field(
        min_length=1,
        max_length=100,
        description="Workflow or skill name, for example review-inbox.",
    )
    scope: str = Field(
        default="",
        max_length=4000,
        description="The owner's request, the cohort and anything deliberately left out.",
    )
    supersede: bool = Field(
        default=False,
        description="Mark this token's open run as interrupted and start a new one instead of returning run_open.",
    )
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class RunUpdate(Input):
    expected_version: int = Field(ge=1)
    note: str | None = Field(
        default=None, max_length=4000, description="Progress note: where the run stands."
    )
    scope: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def nonempty(self):
        if self.note is None and self.scope is None:
            raise ValueError("Provide a progress note or a scope.")
        return self


class NotDone(Input):
    item: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=2000)
    subject_type: SubjectType | None = None
    subject_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def whole_reference(self):
        if (self.subject_type is None) != (self.subject_id is None):
            raise ValueError("Provide subject_type and subject_id together.")
        return self


class RunCheck(Input):
    check: str = Field(min_length=1, max_length=1000)
    verified: bool = Field(
        default=True, description="False when the check could not be carried out."
    )


class RunFinish(Input):
    expected_version: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=8000)
    changes: str = Field(
        default="",
        max_length=8000,
        description="The agent's own account of the changes. Counts by kind are added by the server.",
    )
    not_done: list[NotDone] = Field(default_factory=list, max_length=200)
    checks: list[RunCheck] = Field(default_factory=list, max_length=100)
    limits: str = Field(
        default="",
        max_length=4000,
        description="Statement of limits, for example that nothing was submitted.",
    )
    method: str = Field(
        default="", max_length=8000, description="What the workflow or the product lacked."
    )


class RunQuery(Input):
    status: RunStatus | None = None
    workflow: str | None = Field(default=None, max_length=100)
    token_id: str | None = Field(default=None, max_length=100)
    started_since: str | None = None
    started_until: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @field_validator("started_since", "started_until")
    @classmethod
    def valid_date(cls, value, info):
        return normalized_date(value, end=info.field_name == "started_until")


class QuestionAsk(Input):
    question: str = Field(min_length=1, max_length=2000)
    why: str = Field(
        default="", max_length=4000, description="Why the answer matters and what it unblocks."
    )
    subject_type: SubjectType | None = Field(
        default=None, description="knowledge is a Career entry. Omit for a general question."
    )
    subject_id: str | None = Field(default=None, max_length=100)
    choices: list[str] = Field(default_factory=list, max_length=12)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("choices")
    @classmethod
    def distinct_choices(cls, values):
        cleaned = [value.strip() for value in values]
        if any(not 1 <= len(value) <= 300 for value in cleaned):
            raise ValueError("Each choice needs 1 to 300 characters.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Choices must be distinct.")
        return cleaned

    @model_validator(mode="after")
    def whole_reference(self):
        if (self.subject_type is None) != (self.subject_id is None):
            raise ValueError("Provide subject_type and subject_id together.")
        return self


class QuestionAnswer(Input):
    expected_version: int = Field(ge=1)
    answer: str = Field(default="", max_length=8000)
    choice: str | None = Field(default=None, max_length=300)


class QuestionWithdraw(Input):
    expected_version: int = Field(ge=1)


class QuestionQuery(Input):
    state: Literal["open", "answered", "withdrawn"] | None = None
    subject_type: SubjectType | None = None
    subject_id: str | None = Field(default=None, max_length=100)
    run_id: str | None = Field(default=None, max_length=100)
    answered_since: str | None = Field(
        default=None,
        description="Only questions answered at or after this time, oldest answer first.",
    )
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @field_validator("answered_since")
    @classmethod
    def valid_date(cls, value):
        return normalized_date(value)

    @model_validator(mode="after")
    def whole_reference(self):
        if self.subject_id is not None and self.subject_type is None:
            raise ValueError("Provide subject_type when filtering by subject_id.")
        if self.answered_since and self.state not in (None, "answered"):
            raise ValueError("answered_since lists answered questions only.")
        return self


class EventQuery(Input):
    run_id: str | None = Field(default=None, max_length=100)
    subject_type: str | None = Field(default=None, max_length=50)
    subject_id: str | None = Field(default=None, max_length=100)
    job_id: str | None = Field(default=None, max_length=100)
    application_id: str | None = Field(default=None, max_length=100)
    actor: Literal["owner", "token", "system", "unknown"] | None = None
    token_id: str | None = Field(default=None, max_length=100)
    kind: str | None = Field(default=None, max_length=100)
    since: str | None = None
    until: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @field_validator("since", "until")
    @classmethod
    def valid_date(cls, value, info):
        return normalized_date(value, end=info.field_name == "until")

    @model_validator(mode="after")
    def whole_reference(self):
        if self.subject_id is not None and self.subject_type is None:
            raise ValueError("Provide subject_type when filtering by subject_id.")
        return self


def _label(*parts):
    return " · ".join(part for part in parts if part)


class ActivityService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db

    # Changes

    def list_events(self, value: EventQuery | None = None) -> dict:
        """List recorded changes, newest first, each with its actor, run and subject."""
        value = value if isinstance(value, EventQuery) else EventQuery.model_validate(value or {})
        where, params = [], []
        for column, item in (
            ("e.run_id", value.run_id),
            ("e.job_id", value.job_id),
            ("e.application_id", value.application_id),
            ("e.kind", value.kind),
            ("e.actor_id", value.token_id),
        ):
            if item is not None:
                where.append(column + "=?")
                params.append(item)
        if value.subject_type is not None:
            where.append("e.subject_type=?")
            params.append(value.subject_type)
            if value.subject_id is not None:
                where.append("e.subject_id=?")
                params.append(value.subject_id)
        if value.actor == "unknown":
            where.append("e.actor_kind IS NULL")
        elif value.actor:
            where.append("e.actor_kind=?")
            params.append(value.actor)
        for item, operator in ((value.since, ">="), (value.until, "<=")):
            if item:
                where.append("e.created_at" + operator + "?")
                params.append(item)
        with self.db.connect() as conn:
            return self._events(conn, where, params, value.limit, value.offset)

    def _events(self, conn, where, params, limit, offset):
        clause = " WHERE " + " AND ".join(where) if where else ""
        rows = conn.execute(
            "SELECT e.*,j.title AS job_title,j.company AS job_company FROM events e "
            "LEFT JOIN jobs j ON j.id=e.job_id" + clause + " ORDER BY e.created_at DESC "
            "LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        total = conn.execute("SELECT count(*) FROM events e" + clause, params).fetchone()[0]
        items = [self.workspace.event_record(row) for row in rows]
        labels = self._subject_labels(conn, items)
        for item in items:
            subject = item["subject"]
            job = _label(item.pop("job_title"), item.pop("job_company"))
            subject["label"] = labels.get((subject["type"], subject["id"])) or job
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @staticmethod
    def _subject_labels(conn, items):
        """Current names of the changed records on this page; deleted records have none."""
        queries = {
            "knowledge": "SELECT id,title,organization FROM knowledge WHERE id IN ({})",
            "claim": "SELECT c.id,k.title,k.organization FROM claims c JOIN knowledge k ON k.id=c.knowledge_id WHERE c.id IN ({})",
            "template": "SELECT id,name,'' FROM templates WHERE id IN ({})",
            "source": "SELECT id,name,'' FROM sources WHERE id IN ({})",
            "question": "SELECT id,substr(question,1,120),'' FROM questions WHERE id IN ({})",
            "collection_run": "SELECT id,source_name,'' FROM collection_runs WHERE id IN ({})",
        }
        wanted = {}
        for item in items:
            subject = item["subject"]
            if subject["type"] in queries and subject["id"]:
                wanted.setdefault(subject["type"], set()).add(subject["id"])
        labels = {}
        for kind, identifiers in wanted.items():
            sql = queries[kind].format(",".join("?" for _ in identifiers))
            for row in conn.execute(sql, sorted(identifiers)):
                labels[(kind, row[0])] = _label(row[1], row[2])
        return labels

    # Runs

    @staticmethod
    def _cutoff():
        moment = datetime.now(UTC) - timedelta(seconds=RUN_IDLE_SECONDS)
        return moment.isoformat(timespec="microseconds")

    @staticmethod
    def _counts(conn, run_id):
        return {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT kind,count(*) FROM events WHERE run_id=? GROUP BY kind ORDER BY kind",
                (run_id,),
            )
        }

    def _run(self, conn, row, *, full=False):
        if row is None:
            missing("Run")
        row = dict(row)
        stored = row.pop("status")
        idle = stored == "open" and row["last_activity_at"] < self._cutoff()
        report = json.loads(row.pop("report"))
        # A closed run keeps the counts it had when it ended; an open one is counted live.
        counts = (
            self._counts(conn, row["id"]) if stored == "open" else json.loads(row["change_counts"])
        )
        row.pop("change_counts")
        row.pop("idempotency_key")
        result = {
            **row,
            "status": "interrupted" if idle else stored,
            "interruption": "no_activity"
            if idle
            else "superseded"
            if stored == "interrupted"
            else None,
            "actor": describe("token", row.pop("token_id"), row.pop("token_name")),
            "change_counts": counts,
            "changes_total": sum(counts.values()),
            "questions_count": conn.execute(
                "SELECT count(*) FROM questions WHERE run_id=?", (row["id"],)
            ).fetchone()[0],
            "summary": report.get("summary", ""),
        }
        for key in ("token_id", "token_name"):
            result.pop(key, None)
        if full:
            result["report"] = report or None
        return result

    @staticmethod
    def _token_actor(action):
        actor = current_actor()
        if actor.kind != "token":
            raise DomainError(
                403,
                "run_actor",
                f"Only an API token can {action} a run. Dashboard sessions have no runs.",
            )
        return actor

    def start_run(self, value: RunStart) -> dict:
        """Open a run for the calling token. Its later writes attach to the run until it is finished."""
        value = value if isinstance(value, RunStart) else RunStart.model_validate(value)
        actor = self._token_actor("open")
        run_id, stamp, superseded = new_id(), now(), None
        with self.db.transaction() as conn:
            if value.idempotency_key:
                old = conn.execute(
                    "SELECT * FROM runs WHERE idempotency_key=?", (value.idempotency_key,)
                ).fetchone()
                if old:
                    if old["token_id"] != actor.id or old["workflow"] != value.workflow:
                        conflict("This idempotency key was used for another run.")
                    return self._run(conn, old, full=True)
            current = conn.execute(
                "SELECT * FROM runs WHERE token_id=? AND status='open'", (actor.id,)
            ).fetchone()
            if current:
                if not value.supersede:
                    raise DomainError(
                        409,
                        "run_open",
                        "This token already has an open run. Finish it, or start with supersede=true to mark it interrupted.",
                        {"run": self._run(conn, current)},
                    )
                superseded = current["id"]
                conn.execute(
                    "UPDATE runs SET status='interrupted',ended_at=?,superseded_by=?,change_counts=?,version=version+1,updated_at=? WHERE id=?",
                    (stamp, run_id, encode(self._counts(conn, superseded)), stamp, superseded),
                )
            conn.execute(
                "INSERT INTO runs(id,token_id,token_name,workflow,scope,idempotency_key,started_at,last_activity_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    actor.id,
                    actor.name,
                    value.workflow.strip(),
                    value.scope,
                    value.idempotency_key,
                    stamp,
                    stamp,
                    stamp,
                ),
            )
            result = self._run(
                conn, conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone(), full=True
            )
        return {**result, "superseded_run_id": superseded}

    def _own_open_run(self, conn, run_id, expected_version, action):
        actor = self._token_actor(action)
        row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            missing("Run")
        if row["token_id"] != actor.id:
            raise DomainError(403, "run_owner", "This run belongs to another API token.")
        if row["status"] != "open":
            raise DomainError(
                409,
                "run_closed",
                "This run has already ended. Start a new run.",
                {"status": row["status"], "current_version": row["version"]},
            )
        check_version(row, expected_version)
        return row

    def update_run(self, run_id: str, value: RunUpdate) -> dict:
        """Record a progress note or correct the scope of the calling token's open run."""
        value = value if isinstance(value, RunUpdate) else RunUpdate.model_validate(value)
        with self.db.transaction() as conn:
            row = self._own_open_run(conn, run_id, value.expected_version, "update")
            stamp = now()
            conn.execute(
                "UPDATE runs SET note=?,scope=?,version=version+1,last_activity_at=?,updated_at=? WHERE id=?",
                (
                    row["note"] if value.note is None else value.note,
                    row["scope"] if value.scope is None else value.scope,
                    stamp,
                    stamp,
                    run_id,
                ),
            )
        return self.get_run(run_id)

    def finish_run(self, run_id: str, value: RunFinish) -> dict:
        """Close the calling token's open run with its report. Change counts come from the recorded events."""
        value = value if isinstance(value, RunFinish) else RunFinish.model_validate(value)
        with self.db.transaction() as conn:
            self._own_open_run(conn, run_id, value.expected_version, "finish")
            counts = self._counts(conn, run_id)
            not_done = []
            for item in value.not_done:
                entry = item.model_dump()
                # A reference to a record that no longer exists stays in the report without a name.
                entry["label"] = (
                    self._subject(conn, item.subject_type, item.subject_id, required=False)[1]
                    if item.subject_type
                    else ""
                )
                not_done.append(entry)
            report = {
                "summary": value.summary,
                "changes": {
                    "text": value.changes,
                    "counts": counts,
                    "total": sum(counts.values()),
                },
                "not_done": not_done,
                "checks": [item.model_dump() for item in value.checks],
                "limits": value.limits,
                "method": value.method,
            }
            stamp = now()
            conn.execute(
                "UPDATE runs SET status='finished',report=?,change_counts=?,ended_at=?,version=version+1,last_activity_at=?,updated_at=? WHERE id=?",
                (encode(report), encode(counts), stamp, stamp, stamp, run_id),
            )
        return self.get_run(run_id)

    def get_run(self, run_id: str, changes_limit: int = 50, changes_offset: int = 0) -> dict:
        """Read one run with its report, the questions it asked and a page of the changes it made."""
        if not 1 <= changes_limit <= 200 or changes_offset < 0:
            raise DomainError(
                422, "pagination", "Limit must be 1–200 and offset must be nonnegative."
            )
        with self.db.connect() as conn:
            result = self._run(
                conn, conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone(), full=True
            )
            result["changes"] = self._events(
                conn, ["e.run_id=?"], [run_id], changes_limit, changes_offset
            )
            result["questions"] = [
                self._question(row)
                for row in conn.execute(
                    self._QUESTIONS + " WHERE q.run_id=? ORDER BY q.created_at", (run_id,)
                )
            ]
        return result

    def list_runs(self, value: RunQuery | None = None) -> dict:
        """List runs, newest first, by status, workflow, token or start time. Reports are read with the run."""
        value = value if isinstance(value, RunQuery) else RunQuery.model_validate(value or {})
        where, params = [], []
        if value.status == "open":
            where.append("status='open' AND last_activity_at>=?")
            params.append(self._cutoff())
        elif value.status == "interrupted":
            where.append("(status='interrupted' OR (status='open' AND last_activity_at<?))")
            params.append(self._cutoff())
        elif value.status:
            where.append("status=?")
            params.append(value.status)
        for column, item in (("workflow", value.workflow), ("token_id", value.token_id)):
            if item is not None:
                where.append(column + "=?")
                params.append(item)
        for item, operator in ((value.started_since, ">="), (value.started_until, "<=")):
            if item:
                where.append("started_at" + operator + "?")
                params.append(item)
        clause = " WHERE " + " AND ".join(where) if where else ""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs" + clause + " ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (*params, value.limit, value.offset),
            ).fetchall()
            total = conn.execute("SELECT count(*) FROM runs" + clause, params).fetchone()[0]
            return {"items": [self._run(conn, row) for row in rows], "total": total}

    # Questions for the owner

    _QUESTIONS = (
        "SELECT q.*,j.title AS job_title,j.company AS job_company,a.job_id AS application_job_id,"
        "aj.title AS application_title,aj.company AS application_company,"
        "k.title AS knowledge_title,k.organization AS knowledge_organization FROM questions q "
        "LEFT JOIN jobs j ON j.id=q.job_id LEFT JOIN applications a ON a.id=q.application_id "
        "LEFT JOIN jobs aj ON aj.id=a.job_id LEFT JOIN knowledge k ON k.id=q.knowledge_id"
    )

    @staticmethod
    def _subject(conn, subject_type, subject_id, *, required=True):
        """The owning job (for the timeline) and the current name of a question subject."""
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
                missing(
                    {"job": "Job", "application": "Application", "knowledge": "Career knowledge"}[
                        subject_type
                    ]
                )
            return None, ""
        return row[0], _label(row[1], row[2])

    @staticmethod
    def _question(row):
        if row is None:
            missing("Question")
        row = dict(row)
        kind = row.pop("subject_type")
        snapshot = row.pop("subject_label")
        references = {key: row.pop(column) for key, column in SUBJECT_COLUMNS.items()}
        live = {
            "job": _label(row.pop("job_title"), row.pop("job_company")),
            "application": _label(row.pop("application_title"), row.pop("application_company")),
            "knowledge": _label(row.pop("knowledge_title"), row.pop("knowledge_organization")),
        }
        application_job = row.pop("application_job_id")
        row["subject"] = (
            {
                "type": kind,
                "id": references[kind],
                # The name at the time of asking outlives the record it named.
                "label": live[kind] if references[kind] else snapshot,
                "deleted": references[kind] is None,
                "job_id": references["job"] if kind == "job" else application_job,
            }
            if kind
            else None
        )
        row["choices"] = json.loads(row["choices"])
        row["asked_by"] = describe_row(row, "asked_by")
        resolved = describe_row(row, "resolved_by") if row["resolved_by_kind"] else None
        stamp = row.pop("resolved_at")
        for name in ("answered", "withdrawn"):
            current = row["state"] == name
            row[name + "_by"] = resolved if current else None
            row[name + "_at"] = stamp if current else None
        for prefix in ("asked_by", "resolved_by"):
            for suffix in ("kind", "id", "name"):
                row.pop(f"{prefix}_{suffix}")
        row.pop("idempotency_key")
        return row

    def _read_question(self, conn, question_id):
        return self._question(
            conn.execute(self._QUESTIONS + " WHERE q.id=?", (question_id,)).fetchone()
        )

    def get_question(self, question_id: str) -> dict:
        """Read one question for the owner with its state, answer and version."""
        with self.db.connect() as conn:
            return self._read_question(conn, question_id)

    def ask_question(self, value: QuestionAsk) -> dict:
        """Ask the owner a question tied to a job, an application, a Career entry or nothing. It joins the caller's open run."""
        value = value if isinstance(value, QuestionAsk) else QuestionAsk.model_validate(value)
        actor = current_actor()
        question_id, stamp = new_id(), now()
        with self.db.transaction() as conn:
            if value.idempotency_key:
                old = conn.execute(
                    "SELECT id,question,asked_by_kind,asked_by_id FROM questions WHERE idempotency_key=?",
                    (value.idempotency_key,),
                ).fetchone()
                if old:
                    if (old["question"], old["asked_by_kind"], old["asked_by_id"]) != (
                        value.question,
                        actor.kind,
                        actor.id,
                    ):
                        conflict("This idempotency key was used for another question.")
                    return self._read_question(conn, old["id"])
            job_id, label = (
                self._subject(conn, value.subject_type, value.subject_id)
                if value.subject_type
                else (None, "")
            )
            references = {
                column: value.subject_id if key == value.subject_type else None
                for key, column in SUBJECT_COLUMNS.items()
            }
            conn.execute(
                "INSERT INTO questions(id,subject_type,job_id,application_id,knowledge_id,subject_label,question,why,choices,asked_by_kind,asked_by_id,asked_by_name,run_id,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    question_id,
                    value.subject_type,
                    references["job_id"],
                    references["application_id"],
                    references["knowledge_id"],
                    label,
                    value.question,
                    value.why,
                    encode(value.choices),
                    *actor.columns(),
                    self.workspace.open_run_id(conn, actor),
                    value.idempotency_key,
                    stamp,
                    stamp,
                ),
            )
            self._question_event(
                conn, "question_asked", question_id, job_id, references["application_id"]
            )
            return self._read_question(conn, question_id)

    def _question_event(self, conn, kind, question_id, job_id, application_id):
        self.workspace.event(
            kind,
            job_id,
            application_id,
            {"question_id": question_id},
            conn,
            subject=("question", question_id),
        )

    def _resolve(self, conn, row, kind, state, answer="", choice=None):
        actor = current_actor()
        stamp = now()
        conn.execute(
            "UPDATE questions SET state=?,answer=?,answer_choice=?,resolved_by_kind=?,resolved_by_id=?,resolved_by_name=?,resolved_at=?,version=version+1,updated_at=? WHERE id=?",
            (state, answer, choice, *actor.columns(), stamp, stamp, row["id"]),
        )
        job_id = row["job_id"]
        if row["application_id"]:
            job_id = conn.execute(
                "SELECT job_id FROM applications WHERE id=?", (row["application_id"],)
            ).fetchone()[0]
        self._question_event(conn, kind, row["id"], job_id, row["application_id"])
        return self._read_question(conn, row["id"])

    def answer_question(self, question_id: str, value: QuestionAnswer) -> dict:
        """Answer an open question, or correct an earlier answer, with free text and/or one of its choices."""
        value = value if isinstance(value, QuestionAnswer) else QuestionAnswer.model_validate(value)
        answer = value.answer.strip()
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
            if row is None:
                missing("Question")
            if row["state"] == "withdrawn":
                raise DomainError(
                    409,
                    "question_withdrawn",
                    "This question was withdrawn and no longer needs an answer.",
                    {"state": row["state"], "current_version": row["version"]},
                )
            check_version(row, value.expected_version)
            if value.choice is not None and value.choice not in json.loads(row["choices"]):
                raise DomainError(422, "answer_choice", "Select one of the listed choices.")
            if not answer and value.choice is None:
                raise DomainError(422, "answer_required", "Write an answer or select a choice.")
            return self._resolve(conn, row, "question_answered", "answered", answer, value.choice)

    def withdraw_question(self, question_id: str, value: QuestionWithdraw) -> dict:
        """Withdraw an open question that no longer needs an answer. The record stays readable."""
        value = (
            value if isinstance(value, QuestionWithdraw) else QuestionWithdraw.model_validate(value)
        )
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
            if row is None:
                missing("Question")
            if row["state"] != "open":
                raise DomainError(
                    409,
                    "question_closed",
                    "Only an open question can be withdrawn.",
                    {"state": row["state"], "current_version": row["version"]},
                )
            check_version(row, value.expected_version)
            return self._resolve(conn, row, "question_withdrawn", "withdrawn")

    def list_questions(self, value: QuestionQuery | None = None) -> dict:
        """List questions for the owner by state, subject or run. answered_since returns answers given since a time."""
        value = (
            value if isinstance(value, QuestionQuery) else QuestionQuery.model_validate(value or {})
        )
        where, params = [], []
        state = "answered" if value.answered_since else value.state
        if state:
            where.append("q.state=?")
            params.append(state)
        if value.answered_since:
            where.append("q.resolved_at>=?")
            params.append(value.answered_since)
        if value.subject_type:
            where.append("q.subject_type=?")
            params.append(value.subject_type)
            if value.subject_id is not None:
                where.append(f"q.{SUBJECT_COLUMNS[value.subject_type]}=?")
                params.append(value.subject_id)
        if value.run_id is not None:
            where.append("q.run_id=?")
            params.append(value.run_id)
        clause = " WHERE " + " AND ".join(where) if where else ""
        order = "q.resolved_at" if value.answered_since else "q.created_at DESC"
        with self.db.connect() as conn:
            rows = conn.execute(
                self._QUESTIONS + clause + f" ORDER BY {order} LIMIT ? OFFSET ?",
                (*params, value.limit, value.offset),
            ).fetchall()
            total = conn.execute("SELECT count(*) FROM questions q" + clause, params).fetchone()[0]
        return {"items": [self._question(row) for row in rows], "total": total}


def register_api(router, activity: ActivityService):
    @router.get("/events")
    def events_list(value: Annotated[EventQuery, Query()]):
        return activity.list_events(value)

    @router.get("/runs")
    def runs_list(value: Annotated[RunQuery, Query()]):
        return activity.list_runs(value)

    @router.post("/runs", status_code=201)
    def runs_start(value: RunStart):
        return activity.start_run(value)

    @router.get("/runs/{run_id}")
    def runs_get(
        run_id: str,
        changes_limit: Annotated[int, Query(ge=1, le=200)] = 50,
        changes_offset: Annotated[int, Query(ge=0)] = 0,
    ):
        return activity.get_run(run_id, changes_limit, changes_offset)

    @router.patch("/runs/{run_id}")
    def runs_update(run_id: str, value: RunUpdate):
        return activity.update_run(run_id, value)

    @router.post("/runs/{run_id}/finish")
    def runs_finish(run_id: str, value: RunFinish):
        return activity.finish_run(run_id, value)

    @router.get("/questions")
    def questions_list(value: Annotated[QuestionQuery, Query()]):
        return activity.list_questions(value)

    @router.post("/questions", status_code=201)
    def questions_ask(value: QuestionAsk):
        return activity.ask_question(value)

    @router.get("/questions/{question_id}")
    def questions_get(question_id: str):
        return activity.get_question(question_id)

    @router.post("/questions/{question_id}/answer")
    def questions_answer(question_id: str, value: QuestionAnswer):
        return activity.answer_question(question_id, value)

    @router.post("/questions/{question_id}/withdraw")
    def questions_withdraw(question_id: str, value: QuestionWithdraw):
        return activity.withdraw_question(question_id, value)


def register_mcp(mcp, activity: ActivityService):
    from mcp.types import ToolAnnotations

    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(destructiveHint=False, openWorldHint=False)

    @mcp.tool(annotations=read)
    def events_list(value: EventQuery | None = None) -> dict:
        """List recorded changes, newest first, with actor, run and subject. Filter by run_id, job_id, application_id, subject, actor, kind or time."""
        return activity.list_events(value)

    @mcp.tool(annotations=write)
    def runs_start(value: RunStart) -> dict:
        """Open an agent run (workflow name and scope). Later writes by this token attach to it automatically. One open run per token: a second start returns run_open naming the open run unless supersede=true."""
        return activity.start_run(value)

    @mcp.tool(annotations=write)
    def runs_update(run_id: str, value: RunUpdate) -> dict:
        """Record a progress note or correct the scope of this token's open run, using its current version."""
        return activity.update_run(run_id, value)

    @mcp.tool(annotations=write)
    def runs_finish(run_id: str, value: RunFinish) -> dict:
        """Close this token's open run with its report: summary, changes, not done, checks, limits and method. Change counts by kind are derived from the recorded events."""
        return activity.finish_run(run_id, value)

    @mcp.tool(annotations=read)
    def runs_get(run_id: str, changes_limit: int = 50, changes_offset: int = 0) -> dict:
        """Read one agent run: status, stored report, questions asked and a page of the changes it made."""
        return activity.get_run(run_id, changes_limit, changes_offset)

    @mcp.tool(annotations=read)
    def runs_list(value: RunQuery | None = None) -> dict:
        """List agent runs, newest first, by status (open, finished, interrupted), workflow, token or start time. An open run without recent activity is reported as interrupted."""
        return activity.list_runs(value)

    @mcp.tool(annotations=write)
    def questions_ask(value: QuestionAsk) -> dict:
        """Ask the owner a question tied to a job, an application, a Career entry (knowledge) or nothing, with why it matters and optional choices. Use an idempotency key for retries."""
        return activity.ask_question(value)

    @mcp.tool(annotations=read)
    def questions_list(value: QuestionQuery | None = None) -> dict:
        """List questions for the owner by state, subject or run. answered_since returns the answers given at or after a time, oldest first."""
        return activity.list_questions(value)

    @mcp.tool(annotations=read)
    def questions_get(question_id: str) -> dict:
        """Read one question for the owner with its state, answer, who asked and who answered."""
        return activity.get_question(question_id)

    @mcp.tool(annotations=write)
    def questions_answer(question_id: str, value: QuestionAnswer) -> dict:
        """Record the owner's answer (text and/or one of the choices) using the question's current version. Agents record an answer only when the owner gave it."""
        return activity.answer_question(question_id, value)

    @mcp.tool(annotations=write)
    def questions_withdraw(question_id: str, value: QuestionWithdraw) -> dict:
        """Withdraw an open question that no longer needs an answer, using its current version. The record stays readable."""
        return activity.withdraw_question(question_id, value)
