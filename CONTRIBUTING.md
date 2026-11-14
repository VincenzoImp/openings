# Contributing

Read the [architecture](docs/developer/architecture.md) and the relevant
[user guide](docs/README.md) before changing behavior. Code, UI and docs are
English; examples and fixtures are synthetic. Participation follows the
[code of conduct](CODE_OF_CONDUCT.md); report vulnerabilities privately as in
[SECURITY.md](SECURITY.md). Open an issue before large changes.

## Run locally

Python 3.14+, Node 26 and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked --python 3.14
npm --prefix frontend ci && npm --prefix frontend run build
uv run openings --database data/development.sqlite   # http://127.0.0.1:8080
npm --prefix frontend run dev                        # hot reload; proxies /api and /mcp/
```

Never commit databases, credentials, personal documents or machine-specific files.

## Invariants

- Business logic lives in shared services; the dashboard, REST and MCP expose the
  same operations. Parity runs one way: every dashboard action is a REST operation,
  and every non-owner operation is an MCP tool or names one.
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

Add focused invariant tests and walk a complete workflow. For dashboard changes,
check populated desktop and mobile views and keyboard access. Browser tests (`cd
frontend && npx playwright install chromium webkit && npm run test:e2e`) use
disposable synthetic workspaces; flaky tests fail. `nightly.yml` runs WebKit and
the time budgets (`uv run pytest -m performance`). Never raise a budget to pass.

- **Types:** after changing an operation or model, run `npm --prefix frontend run
  api:gen` and commit `frontend/src/api/schema.d.ts`.
- **MCP budget:** `test_mcp_budget.py` caps the tool list; add a tool last.
- **Docs:** `test_docs.py` caps `docs/user` at 10,000 words and checks links and
  vocabulary. Screenshots: `npm --prefix frontend run screenshots -- --docs`.
- **Schema:** change `schema.sql`, the unreleased migration and its tests together;
  regenerate the fixture at release time with `scripts/release_fixture.py`.

## Releases

Record user-visible changes under `## Unreleased` in [CHANGELOG.md](CHANGELOG.md):
behavior, not implementation, with any schema change and its upgrade and restore
consequences. To release, set every version at once, check the locks, rename the
heading to `## X.Y.Z — date`, commit, and tag `vX.Y.Z` on `main`:

```bash
python3 scripts/bump_version.py X.Y.Z && uv lock --check
npm --prefix frontend install --package-lock-only --ignore-scripts
```

The release workflow builds and smoke-tests both images, publishes
`vincenzoimp/openings:X.Y.Z` after CI and creates the GitHub Release from the
changelog section. Check the weekly workflow on `main` first.

## Repository settings

`main` is protected by a ruleset: pull requests only, required checks `backend`,
`frontend`, `e2e` and `container (amd64)` passing on a branch up to date with
`main`, no force-push, deletion or bypass; no review is required. A change that
renames those jobs updates the ruleset (`gh api repos/VincenzoImp/openings/rulesets`).
