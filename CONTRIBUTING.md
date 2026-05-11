# Contributing

Job Search Tool is a local-first Python package with Docker as the primary
deployment path. Keep changes small, tested, and aligned with the existing
package entrypoints.

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/job-search-tool.git
cd job-search-tool
uv sync --locked
cp config/settings.example.yaml config/settings.yaml
```

## Run Locally

```bash
uv run job-search once
uv run job-search dashboard
uv run job-search-api
uv run job-search-mcp
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
docker compose --profile api --profile mcp config
```

## Project Layout

```text
src/job_search_tool/          Python package and runtime entrypoints
src/job_search_tool/defaults/ Packaged default configuration template
config/                       User-facing example configuration
tests/                        Unit, integration, API, MCP, dashboard tests
docs/user/                    Operator documentation
docs/developer/               Architecture, testing, release notes
docker/                       Container entrypoint
```

## Contribution Rules

- Use `uv.lock` as the dependency source of truth.
- Do not add generated runtime state to Git.
- Add or update tests for behavior changes.
- Keep API, MCP, dashboard, and scheduler behavior consistent through the shared
  `job_search_tool.job_service` layer.
- Treat `config/settings.example.yaml` and the packaged default template as a
  synchronized public contract.
