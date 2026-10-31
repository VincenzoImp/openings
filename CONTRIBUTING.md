# Contributing

Read the [architecture](docs/developer/architecture.md) and relevant
[user guide](docs/README.md) before changing behavior. Keep shared
services useful through the dashboard, REST and MCP. Code, UI and documentation
are English; public examples/screenshots contain synthetic data only.

## Run locally

Requires Python 3.12+, Node 24 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked --python 3.12
npm --prefix frontend ci
npm --prefix frontend run build
uv run openings --database data/development.sqlite
```

Open `http://127.0.0.1:8080`. For frontend hot reload, run
`npm --prefix frontend run dev` separately; Vite proxies `/api` and `/mcp` to the
backend. Never commit development databases or credentials.

To build Docker images locally, give them local names:

```bash
OPENINGS_IMAGE=openings:local docker compose up -d --build
# Include the optional scorer:
OPENINGS_IMAGE=openings:local OPENINGS_SCORER_IMAGE=openings-scorer:local \
  docker compose --profile local up -d --build
```

## Verify a change

```bash
uv run ruff check backend
uv run pytest
npm --prefix frontend run build
npm --prefix frontend run format:check
npm --prefix frontend audit --audit-level=moderate
docker compose config
```

Use focused invariant checks and complete user workflows. For dashboard changes,
check populated lists, desktop/mobile layouts, keyboard access, unsaved edits and
loading/error states. For data changes, check versions, deletion/cancellation,
frozen contexts, exact revision/file associations and backup consistency. Collection
changes need a resume-after-deferral workflow, cumulative counts and a source edit
that leaves queued snapshots unchanged. Check that incomplete automatic candidates
stay outside the archive, then enter once after their text arrives. Exercise one
open application per job, explicit closure outcomes and versioned deletion through
REST/MCP and the dashboard. Keep HTTP attempts inside the shared gate.

The manual MCP/file/backup driver requires an external Tectonic executable:

```bash
uv run python backend/tests/agent_roundtrip.py --tectonic /path/to/tectonic
```

## Project layout

| Path | Purpose |
|---|---|
| `backend/openings` | Shared SQLite services, REST, MCP, collection, worker and authentication |
| `frontend` | React dashboard calling REST |
| `scorer` | Optional separate CPU classifier, never imported by the core |
| `examples` | Synthetic career data and LaTeX templates |
| `skills/openings-workspace` | Optional external-agent workflow guidance |
| `docs/user` | Setup, workflow and operator guides |
| `docs/developer` | Architecture and extension boundaries |

`uv.lock` and `frontend/package-lock.json` are authoritative. Keep personal data,
model caches, deployment files, one-off importers and development work notes out of
the public tree. Preserve upstream notices for vendored code.

## Releases

CI checks backend/frontend, dependency audits, an installed wheel and native Linux
amd64/arm64 core images. Container smoke checks authentication, nonroot startup
and packaged source/resource hashes.

The release workflow publishes versioned core/scorer images to Docker Hub for a pushed
`vX.Y.Z` tag, or a manual run with **publish** enabled. The requested version must
match `pyproject.toml`; publication waits for CI. The versioned tags are
`vincenzoimp/openings:X.Y.Z` and `vincenzoimp/openings:scorer-X.Y.Z`. Branch/PR
checks do not publish.
Before a release, review the changelog and a practical collection → application →
external-agent documents → review → backup/restore workflow. Hardware claims need
measurements with a stated platform and workload. Distinguish observed resource
use, container limits and host requirements.
