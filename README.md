# Openings

[![CI](https://github.com/VincenzoImp/openings/actions/workflows/ci.yml/badge.svg)](https://github.com/VincenzoImp/openings/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-vincenzoimp%2Fopenings-brightgreen.svg)](https://hub.docker.com/r/vincenzoimp/openings)

A configurable job crawler, archive and application tracker you run yourself.
Agent-operable through MCP.

Openings collects postings from job boards, company career pages and feeds,
scores them against criteria you write in one YAML file, and keeps every job
and everything you build around it (status, labels, notes, form answers, CV
and cover letter files, timeline) in one local database. A dashboard, a REST
API and an MCP server operate on that database, so you, your scripts and your
AI agents work from the same state.

**The YAML owns intake and scoring; the database owns state.** A job's status
is never derived from configuration.

## Quick start

```bash
cp config/settings.example.yaml settings.yaml   # edit locations, queries, scoring
docker compose up -d
open http://127.0.0.1:8501
```

The same process serves the dashboard at `/`, the REST API at `/api` and the
MCP endpoint at `/mcp`. Ports bind to `127.0.0.1` by default.

## How it works

```text
sources ──▶ score ──▶ dedupe, drop blacklisted ──▶ upsert ──▶ notify
                                                     │
                     dashboard ◀── application ◀── SQLite ──▶ MCP
                     REST API  ◀── service                     agents
```

- **Sources** return one canonical shape: job boards through
  [JobSpy](https://github.com/speedyapply/JobSpy), company career feeds on
  Greenhouse, Lever, Ashby and SmartRecruiters, RSS and Atom feeds, the Adzuna
  API, and postings you add by hand or through an agent.
- **Scoring** is plain keyword matching over title, description, company and
  location: every category you define adds its weight, negative weights
  penalize, and each job page shows which categories matched.
- **Identity** is `sha256(title | company | location)`, so one opening seen on
  two sources merges into one job.
- **Status** is one value per job: `new`, `shortlisted`, `applied`,
  `interviewing`, `offer`, `rejected`, `withdrawn`. Only `new` rows are
  subject to retention; every other status is protected.
- **Blacklist** deletes a posting and blocks its re-ingestion.
- **Attachments, notes, form answers and events** hang off the job so the
  application you built for it stays with the posting.

## Commands

| Command | Role |
|---------|------|
| `openings scheduler` | collect on the configured interval (container default) |
| `openings run` | collect once and exit |
| `openings web` | dashboard, REST API and MCP endpoint on port 8501 |
| `openings healthcheck` | verify config, database and directories |

## Agents

Point an MCP client at `http://127.0.0.1:8501/mcp` (streamable HTTP):

```json
{ "mcpServers": { "openings": { "type": "http", "url": "http://127.0.0.1:8501/mcp" } } }
```

Read tools: `list_jobs`, `get_job`, `search_similar`, `get_statistics`,
`get_score_distribution`, `get_facets`, `list_blacklist`, `list_sources`,
`list_runs`, `get_settings_reference`. Write tools: `add_job`, `set_status`,
`add_labels`, `remove_labels`, `add_note`, `add_attachment`,
`delete_attachment`, `blacklist_jobs`, `unblacklist_jobs`, `delete_jobs`,
`preview_cleanup`, `run_cleanup`, `export_jobs`.

A typical agent flow: read a posting the crawler missed, `add_job` with the
digested fields, `add_attachment` with the tailored CV, `add_note` with the
form answers, `set_status applied`.

## Configuration

Everything about *what* to collect and *how* to rank it lives in
`settings.yaml`. The [annotated example](config/settings.example.yaml) is the
reference; unknown keys fail at boot and secrets can be written as
`$ENV_VAR`.

```yaml
sources:
  jobspy:
    sites: [linkedin]
    locations: ["Berlin, Germany", "Remote"]
    queries:
      core: ["backend engineer", "platform engineer"]
  companies:
    - { name: Example, ats: greenhouse, slug: example }
scoring:
  save_threshold: 0
  notify_threshold: 20
  weights: { role: 25, stack: 15, language_required: -60 }
  keywords:
    role: ["backend engineer", "platform engineer"]
    stack: ["python", "go", "postgresql"]
    language_required: ["fluent german", "deutsch erforderlich"]
```

See [Configuration](docs/user/configuration.md) and
[Sources](docs/user/sources.md).

## Documentation

- [Docker deployment](docs/user/docker.md)
- [Configuration](docs/user/configuration.md)
- [Sources](docs/user/sources.md)
- [Dashboard](docs/user/dashboard.md)
- [REST API](docs/user/api.md)
- [MCP server](docs/user/mcp.md)
- [Operations](docs/user/operations.md)
- [Architecture](docs/developer/architecture.md)
- [Testing](docs/developer/testing.md)
- [Release process](docs/developer/release.md)

## Development

```bash
uv sync
npm --prefix frontend install
cp config/settings.example.yaml settings.yaml
OPENINGS_DATA_DIR=./data OPENINGS_CONFIG=./settings.yaml uv run openings web
uv run pytest
npm --prefix frontend run quality
```

See [CONTRIBUTING](CONTRIBUTING.md).

## License

MIT.
