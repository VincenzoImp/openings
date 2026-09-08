# Testing

## Python

```bash
uv run pytest                                   # whole suite
uv run pytest --cov=openings --cov-fail-under=80
uv run pytest tests/test_web_api.py -k lifecycle
uv run pytest tests/integration                 # the surfaces against one database
```

`tests/conftest.py` provides a temporary data directory, a minimal
configuration, a `runtime` fixture bound to both, a fake embedding model, a
`service` and a `client` (FastAPI `TestClient` with MCP DNS-rebinding hosts
allowed). Sources are tested with patched HTTP helpers, never against the
network.

`tests/integration/` checks that REST and MCP agree on the same database,
that two processes can write to it, and that exports and limits behave.

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
query, toast, hotkey and confirm providers (`src/test/render.tsx`). The
virtualized job list gets a fixed viewport from `src/test/setup.ts`.

## End to end

```bash
npm --prefix frontend run build
npm --prefix frontend run test:e2e         # Playwright
npm --prefix frontend run test:e2e:ui      # with the inspector
sh docker/smoke.sh                         # the built image, REST and MCP
```

Playwright (`frontend/e2e/`) starts two real `openings web` servers from
`e2e/serve.sh`, each on a temporary data directory with every network source
and the embedding model disabled, seeds them through the API
(`e2e/global-setup.ts`) and drives the built dashboard on a desktop viewport,
in dark mode, on an iPhone 12 and an iPad, plus a token-gated project. Every
view and dialog is checked with axe-core for serious and critical violations,
and every viewport for horizontal overflow. Install the browser once with
`npx playwright install chromium`.

`docker/smoke.sh` builds the image, starts `openings web` with a token, adds a
posting through the API, uploads an attachment, changes status, downloads the
bundle, merges a mirror, requests a run, checks that `/mcp` refuses requests
without the token, and runs `add_job`, `add_attachment`, `set_status` and
`get_job` through MCP.

## Static checks

```bash
uv run pre-commit run --all-files
uv run mypy src/openings
```
