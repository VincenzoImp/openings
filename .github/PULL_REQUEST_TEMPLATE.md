## Why

<!-- The problem or user workflow this change addresses. Link issues with "Fixes #123". -->

## What

<!-- The main changes, including any REST, MCP, schema or dashboard behavior. -->

## Checks

<!-- Commands you ran and their results; see CONTRIBUTING.md → Verify a change. -->

- [ ] `uv run ruff check backend scripts` and `uv run ruff format --check backend scripts`
- [ ] `uv run pytest -n auto` (and `-m performance` for hot paths or migrations)
- [ ] `npm --prefix frontend run build`, `npm --prefix frontend run format:check` and `npm --prefix frontend test`
- [ ] Browser workflows (`npm run test:e2e` in `frontend`) for dashboard changes
- [ ] `python3 scripts/bump_version.py --check` (releases only change versions with `scripts/bump_version.py`)

## Contract

- [ ] Business logic lives in shared services; new operations are declared in `interfaces/` with `operation-inventory.json` regenerated
- [ ] Parity: every operation has REST, MCP and a dashboard path a browser test uses; `docs/developer/parity.md` and `parity-e2e.json` are regenerated (`scripts/parity_matrix.py --e2e`), and any exemption in `parity-notes.json` states its reason (CONTRIBUTING → Parity)
- [ ] Versioned updates, immutable contexts/revisions, exact file ownership and deletion rules still hold
- [ ] Database changes include a migration, backup/restore handling and a CHANGELOG note on the schema
- [ ] Dashboard changes checked with populated data at desktop and mobile widths, keyboard access and loading/error states

## Public repository

- [ ] Tests, fixtures, examples and screenshots use synthetic data only; no databases, credentials or personal documents
- [ ] User docs, skills and CHANGELOG (Unreleased) are updated where behavior changes
