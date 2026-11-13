"""REST routes and MCP tools of activity."""

from typing import Annotated

from fastapi import Query

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
        """List recorded changes, newest first, with actor, run (run_id, run_workflow) and subject. Filter by run_id, job_id, application_id, subject, subject_types (several kinds of record), actor, kind or time."""
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
        """List agent runs, newest first, by status (open, finished, interrupted), workflow, token, start time or active_since (last activity). An open run without recent activity is reported as interrupted."""
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
        """Record the owner's answer (text and/or one of the choices) using the question's current version. Owner only: an agent token is refused with forbidden; an owner token records an answer only when the owner gave it."""
        return activity.answer_question(question_id, value)

    @mcp.tool(annotations=write)
    def questions_withdraw(question_id: str, value: QuestionWithdraw) -> dict:
        """Withdraw an open question that no longer needs an answer, using its current version. The record stays readable."""
        return activity.withdraw_question(question_id, value)
