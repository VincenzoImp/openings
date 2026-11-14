# Openings

[![CI](https://img.shields.io/github/actions/workflow/status/VincenzoImp/openings/ci.yml?branch=main&label=CI)](https://github.com/VincenzoImp/openings/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/VincenzoImp/openings?sort=semver)](https://github.com/VincenzoImp/openings/releases/latest)
[![Docker image](https://img.shields.io/docker/v/vincenzoimp/openings?sort=semver&label=docker)](https://hub.docker.com/r/vincenzoimp/openings)
[![License: MIT](https://img.shields.io/github/license/VincenzoImp/openings)](LICENSE)

Your private job-search desk: collect job postings, keep your career record and
documents in one place, send applications and track the answers. It runs on your
computer or server, and everything lives in one SQLite file.

![Today: applications ready to apply, the pipeline and replies to record](docs/images/today.png)

## What it does

- **Finds jobs.** Scheduled searches on LinkedIn, Indeed and Glassdoor, company
  boards (Greenhouse, Lever, Ashby, Workday and more) and RSS feeds. You can also
  add any job by URL or pasted text.
- **Helps you decide.** Read each new job beside its posting, shortlist it or
  dismiss it with a reason. Dismissals can be restored. Labels show the
  posting's language and likely duplicates; nothing is dismissed automatically.
- **Keeps your record.** Profile, career entries, highlights, CV and letter
  templates, and Preferences: what you want, what you rule out and your writing
  rules, in your own words.
- **Gets applications ready.** Upload your own CV and letter as PDFs (the LaTeX
  source is optional). An application is Ready when its documents are there and
  nothing blocks it. You send it on the employer's site and press **Mark applied**.
- **Tracks the outcome.** Record each reply, close the silent ones as No reply
  and see how many applications got an answer.

You can use all of this by hand. If you want help, your own AI agent can do the
slow parts for you through MCP: triage, tailored documents, keeping sources
healthy. See [Work with an agent](docs/user/agents.md).

## What you need

| | Needed for |
|---|---|
| Docker with Compose v2 | Running Openings (images for amd64 and arm64) |
| A browser | The dashboard |
| An MCP agent client with its own model, such as Claude Code or Codex (optional) | Agent help. **Openings has no AI of its own: nothing happens until you ask your agent.** |
| A shell on the agent's machine (optional) | The agent uploads PDFs with `curl` |
| `pdflatex` on the agent's machine (optional) | Only if the agent builds CVs from LaTeX; PDFs you make yourself need nothing |

## Install

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
cp .env.example .env
docker compose pull
docker compose up -d --no-build
```

Open **http://127.0.0.1:8080**, choose an owner password and add your first job
under **Jobs**. [Getting started](docs/user/getting-started.md) walks through
your first application.

## Connect an agent (optional)

1. In **Settings › Agent access**, create an agent token and copy it once.
2. Put it in the environment variable `OPENINGS_TOKEN`, then copy the shown
   configuration for Claude Code, Codex or another client into your agent. The
   address is `http://127.0.0.1:8080/mcp/`.
3. Tell your agent: **"Set up my Openings workspace."**

An agent token cannot change your password, manage tokens or restore a backup.
[Work with an agent](docs/user/agents.md) covers what the agent can and cannot
do, and how to review its changes.

## Documentation

[How it works](docs/user/how-it-works.md) · [Getting started](docs/user/getting-started.md) ·
[Jobs and sources](docs/user/jobs-and-sources.md) · [Applications](docs/user/applications.md) ·
[Profile, Preferences and Templates](docs/user/profile-preferences-templates.md) ·
[Agent](docs/user/agents.md) · [REST API](docs/user/api.md) ·
[Operations](docs/user/operations.md) · [Configuration](docs/user/configuration.md)

## Project

[Contributing](CONTRIBUTING.md) · [Architecture](docs/developer/architecture.md) ·
[Code of conduct](CODE_OF_CONDUCT.md) · [Security](SECURITY.md) ·
[Changelog](CHANGELOG.md) · [MIT license](LICENSE)
