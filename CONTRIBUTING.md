# Contributing

Thanks for helping. Small fixes can go straight to a pull request; open an issue
first for larger changes. Read the [architecture](docs/developer/architecture.md)
and the relevant [user guide](docs/README.md) before changing behavior. Code, UI
and docs are in American English; examples and fixtures are synthetic.
Participation follows the [code of conduct](CODE_OF_CONDUCT.md); report
vulnerabilities privately as in [SECURITY.md](SECURITY.md).

## Run locally

Python 3.14+, Node 26 and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked --python 3.14
npm --prefix frontend ci && npm --prefix frontend run build
uv run openings --database data/development.sqlite   # http://127.0.0.1:8080
npm --prefix frontend run dev                        # hot reload; proxies /api and /mcp/
```

To run your own image, `docker build -t openings:dev .`, then set
`OPENINGS_IMAGE=openings:dev` in `.env` and `docker compose up -d`. Never commit
databases, credentials, personal documents or machine-specific files.

## Invariants

- Business logic lives in shared services; the dashboard, REST and MCP expose the
  same operations. Parity runs one way: every dashboard action is a REST operation,
  and every non-owner operation is an MCP tool or names one (`mcp=`).
- Keep version checks, document immutability, exact file ownership, reversible
  dismissal and deliberate permanent deletion. One non-Closed application per job,
  in services and SQLite; document work never submits an application.
- Incomplete automatic candidates stay in collection checkpoints; admit usable
  posting text before archive and count bookkeeping. Keep manual partial input.
- Every provider request goes through the shared persisted gate. SQLite stays
  portable; the core has no model, browser or TeX runtime.

## Check a change

```bash
uv run ruff check backend scripts && uv run ruff format --check backend scripts
uv run pytest -n auto                       # skips the performance marker
python3 scripts/bump_version.py --check && npm --prefix frontend run api:check
npm --prefix frontend run build && npm --prefix frontend run budget
npm --prefix frontend run format:check && npm --prefix frontend test
```

- **Tests:** test an invariant once, at the service, with the `conftest.py`
  fixtures (`test_parity.py` covers REST versus MCP), and walk a complete workflow.
- **Browser tests:** `npx --prefix frontend playwright install chromium`, then
  `npm --prefix frontend run test:e2e` (Chromium, desktop and phone, as CI). Their
  server seeds a synthetic workspace; `OPENINGS_E2E_JOBS` and
  `OPENINGS_E2E_APPLICATIONS` size it, `OPENINGS_E2E_PORT` fixes its port. Flaky
  tests fail. `test:e2e:all` runs the rest weekly (`weekly.yml`): WebKit and the
  large-workspace budget; `uv run pytest -m performance` the time budgets. Never
  raise a budget to pass.
- **Types:** after changing an operation or model, run `npm --prefix frontend run
  api:gen` and commit `frontend/src/api/schema.d.ts`.
- **MCP budget:** `test_mcp_budget.py` caps the tool list; add a tool last.
- **Docs:** `test_docs.py` caps `docs/user` at 10,000 words and checks links and
  vocabulary. Screenshots: `npm --prefix frontend run screenshots -- --docs`.
- **Schema:** change `schema.sql`, the unreleased migration and its tests together.

## Changelog

Record user-visible changes under `## Unreleased` in [CHANGELOG.md](CHANGELOG.md):
behavior, not implementation, with any schema change and its upgrade and restore
consequences. Releases and repository settings are in
[Maintaining](docs/developer/maintaining.md).
