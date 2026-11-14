# Agent workspace (optional)

A ready folder to run your AI agent from, with the Openings connection set up
for six clients. Copy it, point it at your server and start your agent here. The
agent reads its skills from your Openings server, sets up your workspace and
keeps the search going. You answer its questions in the chat, send the
applications that are Ready, and mark them applied or close them. See
[Work with an agent](../../docs/user/agents.md). You do not need this folder to
use an agent.

## Set up

Requires Python 3.9+ and an agent client with MCP support (for example Claude
Code, Codex, Cursor, VS Code with Copilot, Gemini CLI or opencode). To compile
CV and letter PDFs from LaTeX, the agent's machine also needs `pdflatex` (for
example from TeX Live, MacTeX or TinyTeX).

```bash
cp -R examples/operator-workspace ~/job-search && cd ~/job-search
git init                                    # optional: keep your setup under version control
python3 .agents/scripts/sync.py --url http://127.0.0.1:8080   # your Openings address
```

Create an **Agent** token under **Settings › API & agents**. It can do the whole
job search but cannot change your password, manage tokens or restore a backup.
Then start your client through the launcher. It asks for the token once, checks
it and passes `OPENINGS_URL` and `OPENINGS_TOKEN` to the client without writing
them to disk:

```bash
python3 .agents/scripts/launch.py claude     # or codex, cursor, code, gemini, opencode
```

For a server behind a private certificate authority, put its CA certificate at
`certs/openings-ca.pem` or set `OPENINGS_CA_FILE`. Clients that load skills from
disk read them through the `.claude/skills` link: run
`python3 .agents/scripts/fetch_skills.py` from a launched shell to fetch them.

## First session

Ask the agent to set up your workspace. It follows the `setup-openings` skill:
it fills your Profile and career entries from your CV or LinkedIn export, asks
about your target roles, places and constraints and writes them to your
Preferences in your words, sets up your CV and letter templates, adds searches
and companies to follow, and prepares a first application so you can see the
result.

Afterwards, ask in plain language: "go through my new jobs", "prepare a CV and
letter for every shortlisted job", "Northstar Labs replied", "update my profile
from this CV", "follow these companies". Tell the agent how you want it to work
under **Preferences › Working with me** in Openings; it reads that at the start
of every session.
