# Agent-operated job search

Openings is built to be run by your own AI agent. You install the workspace and
connect an agent; the agent then runs the search and keeps improving it. Your
part stays small: tell it facts and preferences, answer its focused questions in its chat,
apply to the applications it makes Ready, and mark each one Applied or close it.

## What the agent does

With the [workflow skills](../../skills/) and the
[operating mandate](../../skills/openings-workspace/references/operating-mandate.md),
an agent can, without waiting for each request:

| Area | Skill |
|---|---|
| Install, connect and onboard: career record, Profile, Preferences, templates, searches | [setup-openings](../../skills/setup-openings/SKILL.md) |
| Review new jobs and shortlist credible ones under your Preferences | [review-inbox](../../skills/review-inbox/SKILL.md) |
| Prepare the CV and letter of every Shortlisted application until it is Ready, with PDF checks | [prepare-shortlist](../../skills/prepare-shortlist/SKILL.md) |
| Keep searches and monitored companies effective; reduce noise | [manage-sources](../../skills/manage-sources/SKILL.md) |
| Improve your Career record, claims, CV MASTER and letter template | [maintain-career](../../skills/maintain-career/SKILL.md) |
| Prioritize Ready applications, find expired ones, record what you report | [track-applications](../../skills/track-applications/SKILL.md) |
| Prepare you for interviews from the documents the employer received | [prepare-interview](../../skills/prepare-interview/SKILL.md) |
| Write factual, evidence-based wording | [career-claims](../../skills/career-claims/SKILL.md) |
| Connection, versions, transfers, shared references | [openings-workspace](../../skills/openings-workspace/SKILL.md) |

The agent never submits an application, contacts an employer or records Applied
on its own, and never invents career facts. Your preferences live in
[Preferences](preferences.md) and the Career record; applications you close are
not read as preferences. The agent records what you tell it, for example an
answer you gave, in your words under **Library → Preferences**, where you can
edit or delete it.

## Set it up

An agent with shell access can do most of this for you with
[setup-openings](../../skills/setup-openings/SKILL.md); you choose the owner
password and create the API token yourself.

1. [Install Openings](getting-started.md) and create an **Agent** token in
   Settings. An agent token runs the whole search but cannot change your
   password, manage tokens or restore a backup
   (see [token kinds](agents.md#token-kinds)).
2. Give your agent the skills. A connected agent gets them from the server
   itself: `skills_list` and `skills_get` tools, and one MCP prompt per skill,
   always matching the running version. Clients that support
   [Agent Skills](https://agentskills.io/specification) can also load the
   repository's `skills/` directory.
3. Connect the agent to MCP at `<origin>/mcp` with `Authorization: Bearer <token>`.
   **Settings › API & agents** shows ready-to-copy configuration for Claude Code,
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
   record and your rules and preferences in Preferences, in your words, asks
   what is missing, and then runs the workflows above.

## See what the agent did

Every change in Openings records who made it: **owner** (you in the dashboard or
with an owner token), **agent:<token name>** (an agent token) or **system**
(collection and other background work). All the changes of one REST request or
MCP tool call share one batch id, so a bulk triage of 50 jobs is one batch.

- The history of a job or an application says, for each change, "by you",
  "by <token name>" or "by job sources".
- **Jobs › Dismissed** shows each dismissed job with its reason and who
  dismissed it. The **By agent** filter lists the agent's dismissals; select
  them and choose **Restore** to move them back to New in one action.
- Scripts can read the change log with `events_list` (`GET /events`), filtered
  by actor, batch and time (see [the API](api.md#the-change-log)).

Give each agent its own agent token: its name is what you see next to each
change.

## Working with the agent

Talk to the agent in its own chat and ask for anything in plain language: "what
should I apply to today?", "add these companies", "I got an interview at X",
"make the CV stronger for data roles". **Settings › API & agents** lists what you can
ask your agent, with an example phrase for each skill. Between conversations, a
scheduled or recurring agent session can review new jobs and prepare
applications. The agent reports in the chat what changed, what is left and which
facts it needs from you. Standing instructions for how it should work ("never
prepare consultancy roles") belong in **Preferences › Working with me**.

Changes stay reversible: records keep versions, contexts and document revisions
are immutable, and the agent backs up before broad changes. You can narrow the
mandate at any time in the operator workspace instructions.
