# Testing

## Python

```bash
uv run pytest                                   # whole suite
uv run pytest --cov=openings --cov-fail-under=60
uv run pytest tests/test_web_api.py -k lifecycle
```

`tests/conftest.py` provides a temporary data directory, a minimal
configuration, an `env` fixture that points the process at both and resets
every singleton, a `service` and a `client` (FastAPI `TestClient` with MCP
DNS-rebinding hosts allowed). Sources are tested with patched HTTP helpers,
never against the network.

Guards worth knowing:

- `tests/test_docs.py`: the docs mention the `openings` commands and never
  the previous product's names or state vocabulary.
- `tests/test_settings_reference.py`: `src/openings/defaults/settings.example.yaml`
  is byte-identical to `config/settings.example.yaml`.
- `tests/test_docker_compose.py`, `tests/test_github_workflows.py`,
  `tests/test_project_meta.py`: packaging and CI stay aligned with the
  entrypoints.

## Frontend

```bash
npm --prefix frontend run quality   # lint, format check, typecheck, vitest, build
npm --prefix frontend run test -- --watch
```

Tests mock `fetch` through `src/test/mockApi.ts` and render views inside the
query and toast providers (`src/test/render.tsx`). Virtualized lists get a
fixed viewport from `src/test/setup.ts`.

## End to end

```bash
sh docker/smoke.sh
```

Builds the image, starts `openings web` with a token, adds a posting through
the API, uploads an attachment, changes status, reads the job back, and runs
`add_job` and `set_status` through MCP.

## Static checks

```bash
uv run pre-commit run --all-files
uv run mypy src/openings
```
