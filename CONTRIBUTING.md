# Contributing

Job Search Tool is a local-first Python package with a React frontend and
Docker as the primary deployment path. Keep changes small, tested, and aligned
with the installed package entrypoints.

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/job-search-tool.git
cd job-search-tool
uv sync --locked
npm --prefix frontend install
cp config/settings.example.yaml config/settings.yaml
```

## Run Locally

```bash
uv run job-search once
uv run job-search scheduler
uv run job-search-web
```

Docker development uses the local-build override:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

## Quality Bar

Run the same checks CI runs before opening a PR:

```bash
uv run pre-commit run --all-files
uv run mypy src/job_search_tool --ignore-missing-imports
uv run pytest
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
docker compose config
docker compose -f docker-compose.yml -f docker-compose.dev.yml config
```

## Project Layout

```text
src/job_search_tool/          Python package and runtime entrypoints
src/job_search_tool/web/      Unified FastAPI app, REST API, and MCP mount
src/job_search_tool/defaults/ Packaged default configuration template
frontend/                     React dashboard source
config/                       User-facing example configuration
tests/                        Unit, integration, API, MCP, Docker, docs tests
docs/user/                    Operator documentation
docs/developer/               Architecture, testing, release notes
docker/                       Container entrypoint
```

## Contribution Rules

- Use `uv.lock` and `frontend/package-lock.json` as dependency sources of truth.
- Do not add generated runtime state, frontend builds, or local databases to Git.
- Add or update tests for behavior changes.
- Keep dashboard, API, MCP, and scheduler behavior consistent through the shared
  application layer under `src/job_search_tool/application/`.
- Treat `config/settings.example.yaml` and the packaged default template as a
  synchronized public contract.
