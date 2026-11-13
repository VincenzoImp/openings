# Openings

[![CI](https://img.shields.io/github/actions/workflow/status/VincenzoImp/openings/ci.yml?branch=main&label=CI)](https://github.com/VincenzoImp/openings/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/VincenzoImp/openings?sort=semver)](https://github.com/VincenzoImp/openings/releases/latest)
[![Docker image](https://img.shields.io/docker/v/vincenzoimp/openings?sort=semver&label=docker)](https://hub.docker.com/r/vincenzoimp/openings)
[![License: MIT](https://img.shields.io/github/license/VincenzoImp/openings)](LICENSE)

A self-hosted job search workspace. Collect offers, keep your career knowledge and
templates together, and let your own AI agent prepare applications that you review
and submit. Jobs, documents and file bytes live in one portable SQLite database.

**[Start with Docker](#start-with-docker)** · [Connect an agent](#connect-an-agent) ·
[Documentation](docs/README.md) · [Changelog](CHANGELOG.md)

![Today: applications ready to apply, the agent's questions, the pipeline, what happened since the last visit and replies to record](docs/images/today.png)

## Features

- **Collect:** scheduled keyword/location searches on LinkedIn, Indeed and Glassdoor,
  or selected company boards (Greenhouse, Lever, Ashby, Workday and more) and RSS
  feeds. Role, location and `exclude_titles` filters skip noise before it reaches
  your Inbox. You can also add any job by URL or pasted text.
- **Triage:** review the Inbox, keep jobs on a Shortlist or dismiss them; dismissed
  jobs stay remembered. **Possible duplicates** groups one vacancy collected from
  several sources so you can merge verified copies; bulk actions work on up to 200 jobs.
- **Decide once:** a **Policy** of short statements holds your rules for
  shortlisting and dismissing, the facts employers ask about and your writing
  rules. Your agent proposes items; they count after you confirm them.
- **Prepare:** store your Profile, Career entries, approved claims with typed
  selection fields, LaTeX templates with typed rules and writing instructions. Each application freezes the exact context its CV,
  cover letter and form answers were written from, with PDF/source revisions and review.
- **Plan:** give applications a priority, a deadline and the employer's requirements
  (authorship rules, attachments, references, language, eligibility). Filter by
  readiness (blocked, no documents, missing PDF, needs review, reviewed, ready) and
  sort by deadline or priority. Close, reopen or delete applications in bulk.
- **Hand over:** an application is marked **Ready** once its documents are approved
  and nothing blocks it. Its review page shows the posting, CV and letter side by
  side with the open requirements; download both PDFs, apply on the employer's
  site and **Mark applied**. A later change to the documents clears the mark.
- **Stay consistent:** applications built on older inputs are flagged after a
  change to a part their documents use (Profile header and summary, confirmed
  policy items, templates, Career), naming the part, and review checks a document's content against its
  `.tex` source.
- **Track:** follow applications through Preparing, Ready, Applied, Interview,
  Offer and Closed as a list or a board. Record the employer's rejection,
  interview or offer with its date, and close the ones that never answered as
  **No reply** after a period your Policy sets.
- **Learn:** **Insights** shows which applications get answers: response, interview
  and offer rates and the time to an answer by role family, seniority, source,
  location and month, withheld for samples too small to read.
- **See what the agent did:** every change records who made it. An agent works in
  runs with a stored report, and asks you questions that you answer under **Activity**.
- **Tell the agent what to do next:** write a request under **Activity**, or
  **Ask your agent** on a job or an application. The agent picks it up at its next
  run and reports the result.
- **Automate:** the dashboard, REST API and MCP share one service layer and the same
  operations.

![The review page: the posting, CV and letter side by side with their PDFs, the place in the Ready queue and Mark applied](docs/images/review.png)

## Agent-operated

Openings works best when your own AI agent runs it. The server ships
[workflow skills](skills/) and serves them to any connected agent (`skills_list`,
`skill_get` and one MCP prompt per skill). With them, an agent reviews new jobs
against your policy, prepares a CV and letter for every shortlisted job, records
employer requirements, tunes searches and keeps your Career record current. You
answer its questions, apply to the prepared Drafts and mark them Applied.

The agent uses its own model access and tools and never submits applications for
you. Read [Agent-operated job search](docs/user/agent-operated.md).

![Collect jobs, organize career knowledge, prepare documents with your agent, and track applications](docs/images/workflow.svg)

## Start with Docker

Requires Docker with Compose v2. Published images support Linux amd64 and arm64.

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
cp .env.example .env
docker compose pull
docker compose up -d --no-build
```

Open **http://127.0.0.1:8080**, choose an owner password and add your first job in
**Jobs**. Set up **Collection** when you want scheduled searches; new sources start
paused. Build your **Career** and **Templates** library before preparing documents.

The Compose limit is **0.5 CPU / 512 MiB**; allow host resources beyond this
container budget. [Setup and first use](docs/user/getting-started.md) covers LAN
access, storage and upgrades.

## Connect an agent

1. In **Settings → Agent access**, create an agent token and copy the configuration
   for Claude Code, Codex or another MCP client. An agent token cannot change
   your password, manage tokens or restore a backup. The endpoint is
   `http://127.0.0.1:8080/mcp` with `Authorization: Bearer <token>`.
2. Ask the agent to load the `setup-openings` skill to onboard your career,
   templates and first searches.
3. For a persistent setup, copy the
   [operator workspace template](examples/operator-workspace/README.md): it holds the
   operating mandate and generates MCP configuration for six clients.

[Agents and MCP](docs/user/agents.md) explains the tools, transfers and state rules.

![Settings → Agent access with the API tokens and the client configuration](docs/images/agent-access.png)

## Documentation

[Collection](docs/user/sources.md) · [Career](docs/user/career.md) ·
[Applications](docs/user/applications.md) · [Agents and MCP](docs/user/agents.md) ·
[REST API](docs/user/api.md) · [Operations](docs/user/operations.md)

![Applications: stage chips with their counts, the plan, documents and the employer's answer for each, and the next action](docs/images/applications.png)

## Project

[Contributing](CONTRIBUTING.md) · [Code of conduct](CODE_OF_CONDUCT.md) ·
[Architecture](docs/developer/architecture.md) · [Security](SECURITY.md) ·
[Changelog](CHANGELOG.md) · [MIT license](LICENSE)
