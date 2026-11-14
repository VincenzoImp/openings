# Job search agent workspace

This directory is where an AI agent works on the owner's Openings workspace.
Openings holds everything about the job search: the Profile and career entries,
Preferences, templates, jobs and applications. This directory holds only the
connection setup.

## How to work

Start every session with the `workspace_context` tool of the `openings` MCP
server, then read the core skill `openings` and the skill for the task with
`skills_get` (or the server's prompts and `openings://skills/...` resources).
The skills match the server's version.

| The owner asks | Skill |
|---|---|
| Set up the workspace, import a CV | `setup-openings` |
| Go through the new jobs | `triage-jobs` |
| Prepare CVs and letters for shortlisted jobs | `prepare-applications` |
| Record a reply, "I applied", what is waiting | `track-applications` |
| Update the Profile, career entries, highlights or templates | `maintain-career` |
| Add, tune or pause job sources | `manage-sources` |
| Prepare for an interview | `prepare-interview` |

The owner's own instructions for you live in Openings, under Preferences ›
Working with me and Writing rules, not in this file: they override the skills'
defaults, never the hard limits in the `openings` skill. You never submit an
application, contact an employer or mark one applied unless the owner says they
applied, and you never invent career facts.

## Directory boundary

Keep personal evidence, documents and secrets out of Git; Openings is
authoritative. Use the ignored `.local/` directory for temporary files such as
compiled PDFs. `OPENINGS_TOKEN` lives only in the client's environment; use an
agent token.

- `.agents/mcp.json`: the canonical MCP server definition.
- `.agents/scripts/sync.py`: sets the server URL and generates client adapters
  (`.mcp.json`, `.codex/`, `.cursor/`, `.vscode/`, `.gemini/`, `opencode.json`).
  Never edit the generated files; edit `.agents/` and run it again.
- `.agents/scripts/launch.py`: starts any client with the URL, CA and a checked token.
- `.agents/scripts/fetch_skills.py`: copies the server's skills to `.agents/skills/`.
