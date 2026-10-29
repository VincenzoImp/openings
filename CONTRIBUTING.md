# Contributing

Openings 0.5.0 is a fresh Python/React application. Keep dashboard, REST and MCP
operations on shared application services. Public examples and screenshots must
contain synthetic data only. Code, UI and repository documentation are English.

## Development

Requires Python 3.12+, Node 24 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked --python 3.12
npm --prefix frontend ci
npm --prefix frontend run build
uv run openings --database data/development.sqlite
```

The app serves on `http://127.0.0.1:8080`. For frontend hot reload, run
`npm --prefix frontend run dev` in another terminal; Vite proxies `/api` and `/mcp`
to the backend. Keep development databases out of Git.

```bash
uv run ruff check backend
uv run pytest
npm --prefix frontend run build
npm --prefix frontend audit --audit-level=moderate
docker compose config
```

Prefer a few meaningful invariant checks and practical UI/API/MCP walkthroughs
over large implementation-mirroring suites. Exercise a complete user flow after a
substantial change. The manual `backend/tests/agent_roundtrip.py` driver verifies
real MCP/file/backup transport and requires an external Tectonic executable:

```bash
uv run python backend/tests/agent_roundtrip.py --tectonic /path/to/tectonic
```

## Layout and boundaries

| Path | Responsibility |
|---|---|
| `backend/openings` | SQLite, shared services, REST, MCP, bounded worker and auth |
| `frontend` | Manual dashboard using REST |
| `scorer` | Optional separate CPU classification process; never imported by core |
| `examples` | Synthetic career data and user-owned-template examples |
| `skills/openings-workspace` | Optional external-agent workflow guidance |
| `docs/user` | Installation and operator contracts |
| `docs/next` | Implementation decisions, evidence and handoff state |

`uv.lock` and `frontend/package-lock.json` are authoritative. No legacy compatibility
layer, internal generative agent, server TeX, email/calendar or portal automation.
Review evidence references, forget/cancellation behavior, frozen contexts, exact
file revisions and backup consistency when relevant to a change.

## CI and releases

CI runs backend checks, frontend build/audit and core Docker builds for Linux
amd64/arm64. Docker smoke checks an empty workspace and nonroot runtime. Optional
scorer builds occur in the explicit image-release workflow.

Image publication runs only for a pushed `vX.Y.Z` tag or a manual release workflow
with **publish** enabled and a version matching `pyproject.toml`. It waits for CI,
then pushes versioned core/scorer images to GHCR; ordinary branch/PR builds do not
publish. Review practical integration/resource evidence and release notes before
tagging. A successful image build alone is not a target-hardware validation.
