"""Agent runs with stored reports, questions for the owner and the attributed change log.

Requests for the agent, the other direction of the same exchange, live in
``agent_requests.py``; both use the subject helpers in ``subjects.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from . import subjects
from .actors import current_actor, describe, pop_actor, require_owner
from .agent_requests import REQUESTS, request_record
from .common import check_version, encode, new_id, now
from .errors import DomainError, missing
from .idempotency import fingerprint, remember, replay
from .models import Input, normalized_date
from .subjects import SubjectType

# An open run without a write or progress note for this long is reported as
# interrupted. The stored status stays open: a later write by the same token
# attaches to the run and makes it current again.
RUN_IDLE_SECONDS = 2 * 3600

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
        default="",
        max_length=8000,
        description="What the workflow or the product lacked during this run. The owner may turn it into local notes of the skill (skill_notes_update).",
    )


class RunQuery(Input):
    status: RunStatus | None = None
    workflow: str | None = Field(default=None, max_length=100)
    token_id: str | None = Field(default=None, max_length=100)
    started_since: str | None = None
    started_until: str | None = None
    active_since: str | None = Field(
        default=None,
        description="Only runs whose last activity (start, a change or the end) is at or after this time.",
    )
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @field_validator("started_since", "started_until", "active_since")
    @classmethod
    def valid_date(cls, value, info):
        return normalized_date(value, end=info.field_name == "started_until")


class RunRead(Input):
    """The page of a run's changes that runs_get returns."""

    changes_limit: int = Field(default=50, ge=1, le=200)
    changes_offset: int = Field(default=0, ge=0)


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
    subject_types: list[Annotated[str, Field(min_length=1, max_length=50)]] | None = Field(
        default=None,
        max_length=20,
        description="Changes to any of these kinds of record, for example document, context and file.",
    )
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
        if value.subject_types:
            kinds = sorted(set(value.subject_types))
            options = ["e.subject_type IN (" + ",".join("?" for _ in kinds) + ")"]
            params.extend(kinds)
            # Events from before schema 8 belong to their application or job.
            if "application" in kinds:
                options.append("(e.subject_type IS NULL AND e.application_id IS NOT NULL)")
            if "job" in kinds:
                options.append(
                    "(e.subject_type IS NULL AND e.application_id IS NULL AND e.job_id IS NOT NULL)"
                )
            where.append("(" + " OR ".join(options) + ")")
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
            "SELECT e.*,j.title AS job_title,j.company AS job_company,r.workflow AS run_workflow "
            "FROM events e LEFT JOIN jobs j ON j.id=e.job_id LEFT JOIN runs r ON r.id=e.run_id"
            + clause
            + " ORDER BY e.created_at DESC "
            "LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        total = conn.execute("SELECT count(*) FROM events e" + clause, params).fetchone()[0]
        items = [self.workspace.event_record(row) for row in rows]
        labels = self._subject_labels(conn, items)
        for item in items:
            subject = item["subject"]
            job = subjects.label(item.pop("job_title"), item.pop("job_company"))
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
            "request": "SELECT id,substr(text,1,120),'' FROM requests WHERE id IN ({})",
            "response": "SELECT r.id,j.title,j.company FROM responses r JOIN applications a ON a.id=r.application_id JOIN jobs j ON j.id=a.job_id WHERE r.id IN ({})",
            "collection_run": "SELECT id,source_name,'' FROM collection_runs WHERE id IN ({})",
        }
        wanted = {}
        for item in items:
            subject = item["subject"]
            if subject["type"] in queries and subject["id"]:
                wanted.setdefault(subject["type"], set()).add(subject["id"])
        labels = {}
        for item in items:
            subject = item["subject"]
            # A skill is named by its name; its notes have no row of their own to look up.
            if subject["type"] == "skill" and subject["id"]:
                labels[("skill", subject["id"])] = subject["id"]
        for kind, identifiers in wanted.items():
            sql = queries[kind].format(",".join("?" for _ in identifiers))
            for row in conn.execute(sql, sorted(identifiers)):
                labels[(kind, row[0])] = subjects.label(row[1], row[2])
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
        result = {
            **row,
            "status": "interrupted" if idle else stored,
            "interruption": "no_activity"
            if idle
            else "superseded"
            if stored == "interrupted"
            else None,
            "actor": describe(
                "token", row.pop("token_id"), row.pop("token_name"), row.pop("token_kind")
            ),
            "change_counts": counts,
            "changes_total": sum(counts.values()),
            "questions_count": conn.execute(
                "SELECT count(*) FROM questions WHERE run_id=?", (row["id"],)
            ).fetchone()[0],
            "requests_count": conn.execute(
                "SELECT count(*) FROM requests WHERE run_id=?", (row["id"],)
            ).fetchone()[0],
            "summary": report.get("summary", ""),
            # What the workflow lacked; the owner may turn it into a skill's local notes.
            "method": report.get("method", ""),
        }
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
        # The same key from another token is another run.
        digest = fingerprint({**value.model_dump(mode="json"), "by": actor.id})
        with self.db.transaction() as conn:
            replayed = replay(conn, "runs", value.idempotency_key, digest)
            if replayed:
                row = conn.execute("SELECT * FROM runs WHERE id=?", (replayed,)).fetchone()
                return self._run(conn, row, full=True)
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
                "INSERT INTO runs(id,token_id,token_name,token_kind,workflow,scope,started_at,last_activity_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    actor.id,
                    actor.name,
                    actor.token_kind,
                    value.workflow.strip(),
                    value.scope,
                    stamp,
                    stamp,
                    stamp,
                ),
            )
            remember(conn, "runs", value.idempotency_key, digest, run_id)
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
        """Read one run with its report, the questions it asked, the requests it handled and a page of the changes it made."""
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
            result["requests"] = [
                request_record(row)
                for row in conn.execute(
                    REQUESTS + " WHERE r.run_id=? ORDER BY r.created_at", (run_id,)
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
        for column, item, operator in (
            ("started_at", value.started_since, ">="),
            ("started_at", value.started_until, "<="),
            ("last_activity_at", value.active_since, ">="),
        ):
            if item:
                where.append(column + operator + "?")
                params.append(item)
        clause = " WHERE " + " AND ".join(where) if where else ""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs" + clause + " ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (*params, value.limit, value.offset),
            ).fetchall()
            total = conn.execute("SELECT count(*) FROM runs" + clause, params).fetchone()[0]
            return {
                "items": [self._run(conn, row) for row in rows],
                "total": total,
                "limit": value.limit,
                "offset": value.offset,
            }

    # Questions for the owner

    _QUESTIONS = subjects.select("questions", "q")
    _subject = staticmethod(subjects.resolve)

    @staticmethod
    def _question(row):
        if row is None:
            missing("Question")
        row = dict(row)
        row["subject"] = subjects.pop(row)
        row["choices"] = json.loads(row["choices"])
        row["asked_by"] = pop_actor(row, "asked_by")
        resolved = pop_actor(row, "resolved_by")
        if resolved["kind"] == "unknown":
            resolved = None
        stamp = row.pop("resolved_at")
        for name in ("answered", "withdrawn"):
            current = row["state"] == name
            row[name + "_by"] = resolved if current else None
            row[name + "_at"] = stamp if current else None
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
        # The same key from another writer is another question.
        digest = fingerprint({**value.model_dump(mode="json"), "by": [actor.kind, actor.id]})
        with self.db.transaction() as conn:
            replayed = replay(conn, "questions", value.idempotency_key, digest)
            if replayed:
                return self._read_question(conn, replayed)
            job_id, label = (
                self._subject(conn, value.subject_type, value.subject_id)
                if value.subject_type
                else (None, "")
            )
            references = subjects.references(value.subject_type, value.subject_id)
            conn.execute(
                "INSERT INTO questions(id,subject_type,job_id,application_id,knowledge_id,subject_label,question,why,choices,asked_by_kind,asked_by_id,asked_by_name,asked_by_token_kind,run_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                    stamp,
                    stamp,
                ),
            )
            remember(conn, "questions", value.idempotency_key, digest, question_id)
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
            "UPDATE questions SET state=?,answer=?,answer_choice=?,resolved_by_kind=?,resolved_by_id=?,resolved_by_name=?,resolved_by_token_kind=?,resolved_at=?,version=version+1,updated_at=? WHERE id=?",
            (state, answer, choice, *actor.columns(), stamp, stamp, row["id"]),
        )
        self._question_event(conn, kind, row["id"], *subjects.timeline(conn, row))
        return self._read_question(conn, row["id"])

    def answer_question(self, question_id: str, value: QuestionAnswer) -> dict:
        """Answer an open question, or correct an earlier answer, with free text and/or one of its choices.

        An answer is the owner's: the dashboard session or an owner token records it.
        """
        require_owner("answer a question for the owner")
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
        subjects.add_filter("q", value.subject_type, value.subject_id, where, params)
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
        return {
            "items": [self._question(row) for row in rows],
            "total": total,
            "limit": value.limit,
            "offset": value.offset,
        }
