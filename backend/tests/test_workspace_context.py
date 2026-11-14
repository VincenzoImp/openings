"""workspace_context: the start read, its counts and summaries, and the owner's feedback."""

from context_fixtures import realistic
from openings.actors import OWNER, acting_as


def ok(result):
    value, error = result
    assert error is None, error
    return value


def test_the_start_read_summarises_the_workspace(app, mcp):
    realistic(app, entries=3, jobs=9)
    context = ok(mcp.call("workspace_context", {}))
    assert set(context) == {
        "workspace",
        "counts",
        "settings",
        "profile",
        "preferences",
        "career",
        "templates",
        "skills",
        "feedback",
    }
    # Since the token was made, the owner wrote Preferences: that is feedback for an agent.
    assert {item["what"].split()[0] for item in context["feedback"]} == {"edited"}
    assert context["workspace"]["you"] == "agent:Synthetic agent"
    assert context["counts"]["new"] == 0 and context["counts"]["shortlisted"] == 6
    assert context["counts"]["missing_documents"] == 6
    # The setup facts the dashboard's checklist reads.
    assert context["counts"]["jobs"] >= 6 and context["counts"]["sources"] >= 0
    assert context["settings"]["collection"]["enabled"] is True
    assert context["profile"]["name"] == "Alex Example" and context["profile"]["version"] == 2
    assert set(context["preferences"]) == {
        "looking_for",
        "ruled_out",
        "facts",
        "writing",
        "working_with_me",
    }
    # Every section's items have the shape preferences_update takes.
    assert context["preferences"]["facts"]["items"][0] == {
        "text": "EU citizen with a Swiss B permit."
    }
    assert context["preferences"]["writing"]["items"][0] == {
        "text": "At most two pages.",
        "scope": "cv",
    }
    entry = context["career"][0]
    assert entry["dates"] == "2010-03..2024-06" and len(entry["summary"]) <= 201
    assert (entry["highlights"], entry["approved"]) == (3, 2) and "narrative" not in entry
    assert [t["kind"] for t in context["templates"]] == ["cv", "letter"]
    assert (
        context["templates"][0]["limits"] == {"max_pages": 2}
        and "tex" not in context["templates"][0]
    )
    assert context["skills"] and all(item["name"] for item in context["skills"])

    full = ok(mcp.call("workspace_context", {"include": ["career_full", "templates_full"]}))
    assert len(full["career"][0]["approved_highlights"]) == 2
    assert full["career"][0]["narrative"].startswith("Led the design")
    assert full["templates"][0]["tex"].startswith("\\documentclass")


def test_feedback_lists_the_owners_corrections_of_agent_work_once(app, mcp):
    workspace = app.state.workspace
    listed = [workspace.ingest_job({"title": f"Role {n}", "posting": "Build."}) for n in range(3)]
    ok(mcp.call("workspace_context", {}))
    result = ok(
        mcp.call(
            "jobs_triage",
            {
                "items": [
                    {"job_id": listed[0]["id"], "to": "dismissed", "reason": "Requires German."},
                    {"job_id": listed[1]["id"], "to": "shortlisted"},
                ]
            },
        )
    )
    application_id = result["items"][1]["result"]["application_id"]
    with acting_as(OWNER):
        # The owner restores the dismissal, marks the application applied, edits Preferences
        # and dismisses a job no agent touched (not feedback).
        job = workspace.get_job(listed[0]["id"])
        workspace.set_triage(job["id"], "new", job["version"])
        application = workspace.get_application(application_id)
        workspace.update_application(
            application_id, {"expected_version": application["version"], "stage": "applied"}
        )
        app.state.preferences.update_preferences(
            "ruled_out", {"expected_version": 0, "items": [{"text": "German-only roles."}]}
        )
        job = workspace.get_job(listed[2]["id"])
        workspace.set_triage(job["id"], "dismissed", job["version"], "Mine.")
    feedback = ok(mcp.call("workspace_context", {}))["feedback"]
    assert [item["what"] for item in feedback] == [
        "edited Preferences ruled_out",
        "moved the application from shortlisted to applied",
        "moved the job from dismissed to new",
    ]
    restored = feedback[2]
    assert restored["reason_was"] == "Requires German."
    assert restored["agent"] == "agent:Synthetic agent" and restored["subject"]["label"].startswith(
        "Role 0"
    )
    # Read once: the next read starts after it, unless feedback_since asks again.
    assert "feedback" not in ok(mcp.call("workspace_context", {}))
    since = ok(mcp.call("workspace_context", {"feedback_since": "2000-01-01"}))["feedback"]
    assert len(since) == 3
