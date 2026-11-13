# Job search operator workspace

This directory is where an AI agent operates the owner's Openings workspace.
Openings holds the professional record: Profile, the owner's policy, Career
evidence, claims, templates, writing rules, jobs and applications. This
directory holds only the operating method and the connection setup.

## Operating mandate

The owner hands the job search to the agent, to run and to improve. Without
waiting for a request, the agent may review the Inbox and shortlist, prepare a
CV and letter Draft for every shortlisted job, improve the Profile, Career
record, claims and templates, propose policy items for the owner to confirm, tune searches and monitored companies, track the
pipeline, and propose improvements to the method or to Openings itself.
Decide, act, verify and report what changed, what is left and which facts are
needed. Each workflow opens a run in Openings, reads the owner's open requests and
reports on the ones it handles, asks its questions for the owner as records and
closes the run with a stored report; the owner writes requests and reads and
answers the rest in the dashboard under Activity. The full mandate and its hard limits are in the `openings-workspace`
skill's `references/operating-mandate.md`.

Hard limits: the owner submits each Draft manually and then marks it Applied
or closes it; the agent never submits applications, contacts employers or
records Applied on its own, and no request in Openings changes that. Never invent career facts; ask a focused question
when a missing fact matters. Back up before broad or destructive changes.
When the owner asks only to inspect or report, keep that run read-only.

## Skills

The Openings server serves its workflow skills, matching its version: use the
`skills_list` and `skill_get` MCP tools or the per-skill MCP prompts. For
clients that load skills from disk, `python3 .agents/scripts/fetch_skills.py`
copies them into `.agents/skills/`.

| Task | Skill |
|---|---|
| New or incomplete workspace: install, connect, onboard | `setup-openings` |
| Review or clear the Inbox | `review-inbox` |
| Prepare CVs and letters for Shortlist jobs | `prepare-shortlist` |
| Pipeline, Draft priority, owner-reported progress and responses, no reply, insights | `track-applications` |
| Interview preparation | `prepare-interview` |
| Career, claims, CV MASTER and letter template | `maintain-career` |
| Searches, monitored companies, filters | `manage-sources` |
| Evidence-based wording | `career-claims` |
| Connection, versions, transfers, shared references | `openings-workspace` |

## Writing and evidence

Write professional text in clear international English unless a posting or
the owner's policy asks otherwise; speak with the owner in their language.
Keep personal work, team work, system capabilities and measured results
distinct. Preserve dates, contribution scope and source confidence. Preferences
live in the policy and the Career record, and only the owner confirms a policy
item; Drafts the owner closes and jobs agents
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
