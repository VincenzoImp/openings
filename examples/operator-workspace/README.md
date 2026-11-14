# Operator workspace template

A small directory from which your AI agent runs your Openings job search. Copy
it, point it at your server, start your agent here, and let it work: it reads
the skills from your Openings server, onboards your career and keeps the search
going. You answer its questions in the chat, apply to the applications it makes Ready, and mark them
Applied or close them. See [Agent-operated job search](../../docs/user/agent-operated.md).

## Set up

Requires Python 3.9+ and an agent client with MCP support (for example Claude
Code, Codex, Cursor, VS Code with Copilot, Gemini CLI or opencode). To compile
CV and letter PDFs, the agent's machine also needs a LaTeX distribution with
`pdflatex` (for example TeX Live, MacTeX or TinyTeX).

```bash
cp -R examples/operator-workspace ~/job-search && cd ~/job-search
git init                                    # optional: keep your method under version control
python3 .agents/scripts/sync.py --url http://127.0.0.1:8080   # your Openings address
```

Create an **Agent** token in Openings under **Settings → Agent access**: it runs
the whole job search and cannot change your password, manage tokens or restore a
backup. Then start
your client through the launcher, which asks for the token once, checks it and
passes `OPENINGS_URL` and `OPENINGS_TOKEN` to the client without writing them:

```bash
python3 .agents/scripts/launch.py claude     # or codex, cursor, code, gemini, opencode
```

For a server behind a private certificate authority, put its CA certificate at
`certs/openings-ca.pem` or set `OPENINGS_CA_FILE`. For clients that load skills
from disk, run `python3 .agents/scripts/fetch_skills.py` from a launched shell.

## First session

Ask the agent to set up your workspace. It follows the `setup-openings` skill:
it builds your Profile and Career record from your CV or LinkedIn export, asks
about your target roles, places and constraints and records them in your
Preferences in your words, builds your CV and letter templates, adds searches
and companies to follow, and prepares a first application so you can see the
result.

Afterwards, ask in plain language: "empty my inbox", "prepare CV and letter
for every shortlisted job", "Northstar Labs replied", "update my profile from
this CV", "follow these companies". Tell the agent how you want it to work
under Preferences › Working with me in Openings; it reads that at the start of
every session.
