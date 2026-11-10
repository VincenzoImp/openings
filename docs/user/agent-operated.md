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
2. Give your agent the skills. Clients that support
   [Agent Skills](https://agentskills.io/specification) can load the `skills/`
   directory directly; otherwise point the agent at `skills/*/SKILL.md`.
3. Connect the agent to MCP at `<origin>/mcp` with `Authorization: Bearer <token>`
   (see [Agents and MCP](agents.md)). Set `OPENINGS_URL` and `OPENINGS_TOKEN` in
   the agent's environment for REST and file transfers; set `OPENINGS_CA_FILE`
   when the server uses a private certificate authority.
4. Keep a small operator workspace for the agent: a directory with an
   `AGENTS.md` (or your client's instruction file) that states the operating
   mandate and links the skills, plus ignored local space for temporary files.
   Keep personal data in Openings, not in that directory.
5. Start by telling the agent about your career. It records facts in the Career
   record and your preferences in the Profile, asks what is missing, and then
   runs the workflows above.

## Working with the agent

Ask for anything in plain language: "what should I apply to today?", "add these
companies", "I got an interview at X", "make the CV stronger for data roles".
Between requests, a scheduled or recurring agent session can review new jobs and
prepare Drafts. Each run ends with a short report of what changed, what is left
and which facts the agent needs from you.

Changes stay reversible: records keep versions, contexts and document revisions
are immutable, and the agent backs up before broad changes. You can narrow the
mandate at any time in the operator workspace instructions.
