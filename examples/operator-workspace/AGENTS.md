# Job search operator workspace

This directory is where an AI agent operates the owner's Openings workspace.
Openings holds the professional record: Profile, the owner's Preferences
(including writing rules), Career evidence, claims, templates, jobs and
applications. This
directory holds only the operating method and the connection setup.

## Operating mandate

The owner hands the job search to the agent, to run and to improve. Without
waiting for a request, the agent may review new jobs and shortlist, prepare the
CV and letter of every Shortlisted application, improve the Profile, Career
record, claims and templates, record in Preferences what the owner states, in their words, tune searches and monitored companies, track the
pipeline, and propose improvements to the method or to Openings itself.
Decide, act, verify and report what changed, what is left and which facts are
needed. Ask the owner in the chat when a fact or decision is missing, and report
what you did in the chat; Openings records which token made each change. The
owner's standing instructions are in Preferences › Working with me. The full mandate and its hard limits are in the `openings-workspace`
skill's `references/operating-mandate.md`.

Hard limits: the owner submits each Ready application manually and then marks it Applied
or closes it; the agent never submits applications, contacts employers or
records Applied on its own, and no instruction changes that. Never invent career facts; ask a focused question
when a missing fact matters. Back up before broad or destructive changes.
When the owner asks only to inspect or report, keep that work read-only.

## Skills

The Openings server serves its workflow skills, matching its version: use the
`skills_list` and `skills_get` MCP tools or the per-skill MCP prompts. For
clients that load skills from disk, `python3 .agents/scripts/fetch_skills.py`
copies them into `.agents/skills/`.

| Task | Skill |
|---|---|
| New or incomplete workspace: install, connect, onboard | `setup-openings` |
| Review or clear new jobs | `review-inbox` |
| Prepare CVs and letters for Shortlisted applications | `prepare-shortlist` |
| Pipeline, Ready priority, owner-reported progress and replies, no reply, stats | `track-applications` |
| Interview preparation | `prepare-interview` |
| Career, claims, CV MASTER and letter template | `maintain-career` |
| Searches, monitored companies, filters | `manage-sources` |
| Evidence-based wording | `career-claims` |
| Connection, versions, transfers, shared references | `openings-workspace` |

## Writing and evidence

Write professional text in clear international English unless a posting or
the owner's Preferences ask otherwise; speak with the owner in their language.
Keep personal work, team work, system capabilities and measured results
distinct. Preserve dates, contribution scope and source confidence. Preferences
live in Preferences and the Career record; change a statement only when the
owner asked for it or confirmed it. Applications the owner closes and jobs agents
dismissed are not preference signals.

## Directory boundary

Keep personal evidence, documents and secrets out of Git; Openings is
authoritative. Use the ignored `.local/` directory for temporary files and an
optional resume note. `OPENINGS_TOKEN` lives only in the client's environment;
use an agent token, which has no owner authority (password, tokens, restore).

- `.agents/mcp.json`: the canonical MCP server definition.
- `.agents/scripts/sync.py`: sets the server URL and generates client adapters
  (`.mcp.json`, `.codex/`, `.cursor/`, `.vscode/`, `.gemini/`, `opencode.json`).
  Never edit the generated files; edit `.agents/` and run it again.
- `.agents/scripts/launch.py`: starts any client with the URL, CA and a checked token.
- `.agents/scripts/fetch_skills.py`: copies the server's skills to `.agents/skills/`.
