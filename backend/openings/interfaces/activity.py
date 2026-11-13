"""REST routes and MCP tools of activity."""

from typing import Annotated

from fastapi import Query
from mcp.types import ToolAnnotations

from ..activity import (
    ActivityService,
    EventQuery,
    QuestionAnswer,
    QuestionAsk,
    QuestionQuery,
    QuestionWithdraw,
    RunFinish,
    RunQuery,
    RunStart,
    RunUpdate,
)
from .registry import Operation, Param, Route, Tool, bind_mcp, bind_rest, query_model

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(destructiveHint=False, openWorldHint=False)

OPERATIONS = (
    Operation(
        "events.list",
        "events",
        "list",
        "Agent activity",
        "List recorded changes with actor, run and subject",
        params=(query_model(EventQuery),),
        call=lambda s, value: s.list_events(value),
        rest=(Route("GET", "/events", "events_list"),),
        tool=Tool(
            "events_list",
            READ,
            "List recorded changes, newest first, with actor, run (run_id, run_workflow) and subject. Filter by run_id, job_id, application_id, subject, subject_types (several kinds of record), actor, kind or time.",
        ),
    ),
    Operation(
        "runs.list",
        "runs",
        "list",
        "Agent activity",
        "List agent runs by status, workflow, token or start time",
        params=(query_model(RunQuery),),
        call=lambda s, value: s.list_runs(value),
        rest=(Route("GET", "/runs", "runs_list"),),
        tool=Tool(
            "runs_list",
            READ,
            "List agent runs, newest first, by status (open, finished, interrupted), workflow, token, start time or active_since (last activity). An open run without recent activity is reported as interrupted.",
        ),
    ),
    Operation(
        "runs.start",
        "runs",
        "start",
        "Agent activity",
        "Open an agent run for the calling API token",
        params=(Param("value", RunStart),),
        call=lambda s, value: s.start_run(value),
        rest=(Route("POST", "/runs", "runs_start", status_code=201),),
        tool=Tool(
            "runs_start",
            WRITE,
            "Open an agent run (workflow name and scope). Later writes by this token attach to it automatically. One open run per token: a second start returns run_open naming the open run unless supersede=true.",
        ),
    ),
    Operation(
        "runs.read",
        "runs",
        "get",
        "Agent activity",
        "Read an agent run with its report, questions and changes",
        params=(
            Param("run_id", str),
            Param("changes_limit", int, 50, rest=(Annotated[int, Query(ge=1, le=200)], 50)),
            Param("changes_offset", int, 0, rest=(Annotated[int, Query(ge=0)], 0)),
        ),
        call=lambda s, run_id, changes_limit, changes_offset: s.get_run(
            run_id, changes_limit, changes_offset
        ),
        rest=(Route("GET", "/runs/{run_id}", "runs_get"),),
        tool=Tool(
            "runs_get",
            READ,
            "Read one agent run: status, stored report, questions asked and a page of the changes it made.",
        ),
    ),
    Operation(
        "runs.update",
        "runs",
        "update",
        "Agent activity",
        "Record a progress note on the calling token's open run",
        params=(Param("run_id", str), Param("value", RunUpdate)),
        call=lambda s, run_id, value: s.update_run(run_id, value),
        rest=(Route("PATCH", "/runs/{run_id}", "runs_update"),),
        tool=Tool(
            "runs_update",
            WRITE,
            "Record a progress note or correct the scope of this token's open run, using its current version.",
        ),
    ),
    Operation(
        "runs.finish",
        "runs",
        "finish",
        "Agent activity",
        "Close the calling token's run with its report",
        params=(Param("run_id", str), Param("value", RunFinish)),
        call=lambda s, run_id, value: s.finish_run(run_id, value),
        rest=(Route("POST", "/runs/{run_id}/finish", "runs_finish"),),
        tool=Tool(
            "runs_finish",
            WRITE,
            "Close this token's open run with its report: summary, changes, not done, checks, limits and method. Change counts by kind are derived from the recorded events.",
        ),
    ),
    Operation(
        "questions.list",
        "questions",
        "list",
        "Agent activity",
        "List questions for the owner by state, subject, run or answer time",
        params=(query_model(QuestionQuery),),
        call=lambda s, value: s.list_questions(value),
        rest=(Route("GET", "/questions", "questions_list"),),
        tool=Tool(
            "questions_list",
            READ,
            "List questions for the owner by state, subject or run. answered_since returns the answers given at or after a time, oldest first.",
        ),
    ),
    Operation(
        "questions.ask",
        "questions",
        "ask",
        "Agent activity",
        "Ask the owner a question tied to a job, application, Career entry or nothing",
        params=(Param("value", QuestionAsk),),
        call=lambda s, value: s.ask_question(value),
        rest=(Route("POST", "/questions", "questions_ask", status_code=201),),
        tool=Tool(
            "questions_ask",
            WRITE,
            "Ask the owner a question tied to a job, an application, a Career entry (knowledge) or nothing, with why it matters and optional choices. Use an idempotency key for retries.",
        ),
    ),
    Operation(
        "questions.read",
        "questions",
        "get",
        "Agent activity",
        "Read one question for the owner",
        params=(Param("question_id", str),),
        call=lambda s, question_id: s.get_question(question_id),
        rest=(Route("GET", "/questions/{question_id}", "questions_get"),),
        tool=Tool(
            "questions_get",
            READ,
            "Read one question for the owner with its state, answer, who asked and who answered.",
        ),
    ),
    Operation(
        "questions.answer",
        "questions",
        "answer",
        "Agent activity",
        "Answer a question for the owner",
        access="owner",
        params=(Param("question_id", str), Param("value", QuestionAnswer)),
        call=lambda s, question_id, value: s.answer_question(question_id, value),
        rest=(Route("POST", "/questions/{question_id}/answer", "questions_answer"),),
        tool=Tool(
            "questions_answer",
            WRITE,
            "Record the owner's answer (text and/or one of the choices) using the question's current version. Owner only: an agent token is refused with forbidden; an owner token records an answer only when the owner gave it.",
        ),
    ),
    Operation(
        "questions.withdraw",
        "questions",
        "withdraw",
        "Agent activity",
        "Withdraw an open question",
        params=(Param("question_id", str), Param("value", QuestionWithdraw)),
        call=lambda s, question_id, value: s.withdraw_question(question_id, value),
        rest=(Route("POST", "/questions/{question_id}/withdraw", "questions_withdraw"),),
        tool=Tool(
            "questions_withdraw",
            WRITE,
            "Withdraw an open question that no longer needs an answer, using its current version. The record stays readable.",
        ),
    ),
)


def register_api(router, activity: ActivityService):
    bind_rest(router, OPERATIONS, activity)


def register_mcp(mcp, activity: ActivityService):
    bind_mcp(mcp, OPERATIONS, activity)
