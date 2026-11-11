# Agent-operated job search

Openings is built to be run by your own AI agent. You install the workspace and
connect an agent; the agent then runs the search and keeps improving it. Your
part stays small: tell it facts and preferences, answer its focused questions,
apply to the Drafts it prepares, and mark each one Applied or close it.

## What the agent does

With the [workflow skills](../../skills/) and the
[operating mandate](../../skills/openings-workspace/references/operating-mandate.md),
an agent can, without waiting for each request:

| Area | Skill |
|---|---|
| Install, connect and onboard: career record, Profile policy, templates, searches | [setup-openings](../../skills/setup-openings/SKILL.md) |
| Review the Inbox and shortlist credible jobs under your Profile policy | [review-inbox](../../skills/review-inbox/SKILL.md) |
| Prepare a CV and letter Draft for every shortlisted job, with PDF checks | [prepare-shortlist](../../skills/prepare-shortlist/SKILL.md) |
| Keep searches and monitored companies effective; reduce noise | [manage-sources](../../skills/manage-sources/SKILL.md) |
| Improve your Career record, claims, CV MASTER and letter template | [maintain-career](../../skills/maintain-career/SKILL.md) |
| Prioritize ready Drafts, find stale or expired ones, record what you report | [track-applications](../../skills/track-applications/SKILL.md) |
| Prepare you for interviews from the documents the employer received | [prepare-interview](../../skills/prepare-interview/SKILL.md) |
| Write factual, evidence-based wording | [career-claims](../../skills/career-claims/SKILL.md) |
| Connection, versions, transfers, shared references | [openings-workspace](../../skills/openings-workspace/SKILL.md) |

The agent never submits an application, contacts an employer or records Applied
on its own, and never invents career facts. Your preferences live in the Profile
and Career records; Drafts you close are not read as preferences.

## Set it up

An agent with shell access can do most of this for you with
[setup-openings](../../skills/setup-openings/SKILL.md); you choose the owner
password and create the API token yourself.

1. [Install Openings](getting-started.md) and create an API token in Settings.
2. Give your agent the skills. A connected agent gets them from the server
   itself: `skills_list` and `skill_get` tools, and one MCP prompt per skill,
   always matching the running version. Clients that support
   [Agent Skills](https://agentskills.io/specification) can also load the
   repository's `skills/` directory.
3. Connect the agent to MCP at `<origin>/mcp` with `Authorization: Bearer <token>`.
   **Settings → Agent access** shows ready-to-copy configuration for Claude Code,
   Codex and JSON-based clients (see [Agents and MCP](agents.md)). Set `OPENINGS_URL` and `OPENINGS_TOKEN` in
   the agent's environment for REST and file transfers; set `OPENINGS_CA_FILE`
   when the server uses a private certificate authority.
4. Give the agent an operator workspace: copy
   [`examples/operator-workspace`](../../examples/operator-workspace/README.md),
   point it at your server with `sync.py --url`, and start your client with its
   `launch.py`. It states the operating mandate, generates MCP configuration for
   Claude Code, Codex, Cursor, VS Code, Gemini CLI and opencode, and keeps
   personal data out of Git. The agent's machine needs `pdflatex` to compile PDFs.
5. Start by asking the agent to set up your workspace, or to try it first with
   the synthetic example career. Then tell it about your career. It records facts in the Career
   record and your preferences in the Profile, asks what is missing, and then
   runs the workflows above.

## See what the agent did

Every change in Openings records who made it: you in the dashboard, a named API
token, or the system (collection). An agent works in **runs**. It opens a run
with the workflow name and scope, its changes are attached to that run, and it
closes the run with a report: summary, changes, what was not done and why,
checks, a statement of limits and what the workflow lacked. A run that was never
closed is shown as interrupted, with the changes it made.

When the agent needs a fact or a decision, it asks a **question** tied to the
job, application or Career entry concerned. Open **Activity** in the dashboard:

- **Questions** lists the open questions with an answer form; the navigation
  shows how many are open. The agent reads your answers at the start of its
  next run. You can change an answer or withdraw a question.
- **Runs** lists the runs; a run shows its report and every record it changed,
  with links.
- **Changes** lists every change with who made it.

![Activity with two open questions from the agent, one with answer choices](../images/activity-questions.png)

![A finished run with its stored report: scope, summary, changes, not done and checks](../images/activity-run.png)

Give each agent, and each parallel worker that should report separately, its
own API token: a token has one open run at a time and its name is what you see
next to each change.

## Working with the agent

Ask for anything in plain language: "what should I apply to today?", "add these
companies", "I got an interview at X", "make the CV stronger for data roles".
Between requests, a scheduled or recurring agent session can review new jobs and
prepare Drafts. Each run ends with a short report of what changed, what is left
and which facts the agent needs from you.

Changes stay reversible: records keep versions, contexts and document revisions
are immutable, and the agent backs up before broad changes. You can narrow the
mandate at any time in the operator workspace instructions.
