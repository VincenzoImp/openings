# Contributing

Openings is a Python package with a React dashboard, shipped as one Docker
image. Keep changes small and tested, and keep the three surfaces (dashboard,
REST, MCP) consistent by routing every write through the application service.

## Setup

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
uv sync --locked
npm --prefix frontend install
cp config/settings.example.yaml settings.yaml
```

## Run locally

```bash
export OPENINGS_DATA_DIR=./data OPENINGS_CONFIG=./settings.yaml
uv run openings run          # one collection
uv run openings scheduler    # keep collecting
uv run openings web          # dashboard, /api and /mcp on :8501
npm --prefix frontend run dev  # dashboard with hot reload, proxied to :8501
```

Docker from the local checkout:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

## Quality bar

CI runs exactly this; run it before opening a pull request:

```bash
uv run pre-commit run --all-files
uv run mypy src/openings
uv run pytest --cov=openings --cov-fail-under=60
npm --prefix frontend run quality
docker compose config
sh docker/smoke.sh
```

## Layout

```text
src/openings/              package: config, models, database, scoring, pipeline
src/openings/sources/      jobspy, ats/{greenhouse,lever,ashby,smartrecruiters}, rss, adzuna, manual
src/openings/application/  the service every surface calls; attachments on disk
src/openings/web/          FastAPI app: /api routes, /mcp tools, static dashboard
src/openings/defaults/     packaged copy of config/settings.example.yaml
frontend/                  dashboard (React, Vite, Tailwind, TanStack)
config/                    the annotated example configuration
tests/                     pytest suite, including docs and packaging guards
docs/user, docs/developer  operator and contributor documentation
docker/                    entrypoint and smoke test
```

## Rules

- `uv.lock` and `frontend/package-lock.json` are the dependency sources of
  truth.
- No generated state in Git: no databases, builds, attachments or logs.
- Behaviour changes come with tests. `tests/test_docs.py` guards the docs
  against drift, `tests/test_settings_reference.py` keeps the packaged
  example identical to `config/settings.example.yaml`.
- Nothing in code, defaults or docs assumes a country, language, currency or
  board. Those are user configuration.
- No compatibility layers for earlier products; Openings starts at 0.1.0.
