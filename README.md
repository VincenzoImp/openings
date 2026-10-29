# Openings

**Find the right jobs. Keep your story ready. Let your agent handle the paperwork.**

A self-hosted job-search workspace: scheduled collection, career knowledge, tailored
application documents and progress tracking, in one portable SQLite database.

[Get started](docs/user/getting-started.md) · [Connect your agent](docs/user/agents.md) · [REST API](docs/user/api.md)

![Openings dashboard with application progress and a recorded journey](docs/images/overview.png)

![Collect jobs, organize your career context, prepare documents with your agent, and track applications](docs/images/workflow.svg)

## Everything around an application

| Find and organize | Prepare and follow through |
|---|---|
| **Saved searches:** choose keywords, location and LinkedIn, Indeed or Glassdoor. | **Career knowledge:** keep your profile, detailed experience, approved claims and evidence. |
| **Company watch:** follow selected company ATS boards or RSS/Atom feeds. | **Your templates:** multiple LaTeX packages, assets, defaults and editable writing rules. |
| **One inbox:** add a URL or posting yourself; search, filter, save, dismiss and update in bulk. | **Exact documents:** CVs, letters, form answers, PDF/source revisions and review history. |
| **Controlled automation:** schedules, global pause, request budgets, cooldowns and visible task results. | **Application tracking:** list/Kanban, independent attempts and a funnel based on recorded progress. |
| **Optional fit scoring:** a separate CPU classifier or compatible remote service. | **One portable archive:** SQLite stores records and file bytes; back up or move the workspace. |

### Your dashboard. Your scripts. Your agent.

Use the **dashboard** by hand, the **REST API** for scripts, or **MCP** with your
preferred external agent. They share the same application operations.

Your agent reads the saved job, career evidence, templates and instructions;
writes the CV, letter and form answers; compiles externally; then uploads the
exact PDF and source files. You review the result and record what you submitted.
An optional [agent skill](skills/openings-workspace/SKILL.md) teaches this workflow.
Your chosen agent supplies its own AI access and tools.

## Start with Docker

Requires Docker with Compose v2. Published [Docker Hub images](https://hub.docker.com/r/vincenzoimp/openings)
support Linux amd64 and arm64.

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
cp .env.example .env
docker compose pull
docker compose up -d --no-build
```

Open **http://127.0.0.1:8080** and set your owner password. Add your profile and a
template, then save a search in **Collection** or add a job in **Inbox**. New sources
start paused; enable the schedules you want. No AI account is needed to collect,
organize or track jobs. Optional scoring starts separately.

[Setup and LAN access](docs/user/getting-started.md) · [Search configuration](docs/user/sources.md) · [Scoring](docs/user/scoring.md) · [Backup and restore](docs/user/operations.md)

To build from source instead, follow [Development](CONTRIBUTING.md).

## A few useful boundaries

Scoring is advisory and disabled by default. Public portals can block requests or
change their pages; provider budgets are safeguards, not guaranteed access.
Google Jobs is unsupported. Paste the posting when URL extraction cannot read it.

Document generation and LaTeX compilation run in your external agent. Openings
tracks the work; sending applications and automating portals stay outside the app.
There is no built-in AI subscription, chat, server browser or TeX compiler.

Version **0.5.0** is a substantial rewrite. Previous databases/configuration are
not compatible, and stable API/data-format compatibility is not yet promised.
The default core loads no model; the optional local-scoring deployment has a
combined **2 CPU / 4 GiB** Compose budget. See the [hardware notes](docs/user/scoring.md).

[Contributing](CONTRIBUTING.md) · [Architecture](docs/developer/architecture.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md) · [MIT license](LICENSE)
