# Contributing

Read the [architecture](docs/developer/architecture.md) and relevant
[user guide](docs/README.md) before changing behavior. Keep shared
services useful through the dashboard, REST and MCP. Code, UI and documentation
are English; public examples/screenshots contain synthetic data only. Participation
follows the [code of conduct](CODE_OF_CONDUCT.md); report vulnerabilities privately
as described in [SECURITY.md](SECURITY.md).

Open an issue with the bug or feature form before large changes. Pull requests use
the template's checklist: tests, dashboard/REST/MCP parity, synthetic fixtures and
updated documentation.

## Run locally

Requires Python 3.14+, Node 26 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked --python 3.14
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
```

## Verify a change

```bash
uv run ruff check backend
uv run ruff format --check backend
uv run pytest
python3 scripts/bump_version.py --check
npm --prefix frontend run build
npm --prefix frontend run budget
npm --prefix frontend run format:check
npm --prefix frontend test
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

Browser regressions start a disposable synthetic workspace with acquisition workers
disabled. Build the dashboard first, then run:

```bash
cd frontend
npx playwright install chromium webkit
npm run test:e2e
```

The four projects cover Chromium and WebKit at desktop/mobile widths. A fifth,
`chromium-performance`, starts its own workspace of 5,000 jobs and 500
applications and fails when the Applications list takes 300 ms or more to show
200 rows (the median of seven loads). CI runs Chromium at both widths and the
performance project. Browser binaries are development tools, outside the core.

### Dashboard budgets

The [dashboard design](docs/developer/dashboard-design.md) sets budgets that CI
checks:

- **Size.** `npm --prefix frontend run budget` reads the build and fails when the
  first screen's compressed JavaScript exceeds 110 kB, a later screen adds more
  than 40 kB, or the stylesheets exceed 15 kB. A page that cannot meet its budget
  yet gets a named, temporary allowance in `frontend/scripts/budget.mjs` with the
  stage that removes it; never raise a budget.
- **Accessibility.** `frontend/tests/accessibility.spec.ts` runs axe on every
  screen in both themes at both widths: no serious or critical finding against
  WCAG 2.2 AA. Add a new screen or tab to its list. Fix a finding in the shell or
  a component; a finding inside a page that a later stage rebuilds may be listed
  as an exclusion for that rule and that part of the page, with its stage.
- **Contrast.** `frontend/tests/contrast.test.mjs` computes the contrast of every
  token pair in the design document's colour table from
  `frontend/src/design/tokens.css`. Change a colour in both places.
- **Keyboard.** `frontend/tests/shell.spec.ts` operates the navigation, the More
  sheet, the theme and the density from the keyboard alone;
  `frontend/tests/today.spec.ts` answers a question on Today,
  `frontend/tests/activity.spec.ts` moves through the Activity tabs and opens a
  run's report, `frontend/tests/applications.spec.ts` goes from Today's
  Review to Mark applied and records an employer response the same way,
  `frontend/tests/system.spec.ts` moves through the Collection tabs and switches
  scheduled collection, revokes tokens, and `frontend/tests/skills.spec.ts`
  opens a skill and saves its local notes.

The browser tests run on the synthetic workspace of
`backend/tests/dashboard_server.py` and `backend/tests/today_fixtures.py`. The
four projects share one server, so a test that changes data makes its own
records and reads the numbers it compares from the API.

Screens use the components in `frontend/src/design` and add no global styles.

Each run starts its own server on a free local port, so runs in several checkouts
or worktrees can overlap. Set `OPENINGS_E2E_PORT` to choose the port, for example
`OPENINGS_E2E_PORT=18084 npm run test:e2e`. The run gives its server a one-time
token and stops before the first test if the port is already in use or the server
that answers there is not the one it started.

### Parity matrix

[docs/developer/parity.md](docs/developer/parity.md) is generated from the operation
inventory, the REST/MCP contract, the dashboard source and browser evidence. After
changing an operation, a route, a tool or the dashboard's REST calls, regenerate it;
`pytest` fails while it is out of date:

```bash
uv run python scripts/parity_matrix.py
```

After changing the browser tests, re-record which operations the dashboard really
called (needs the built dashboard and Playwright Chromium):

```bash
uv run python scripts/parity_matrix.py --e2e
```

Remarks that code cannot derive live in `docs/developer/parity-notes.json`.

### Documentation screenshots

`docs/images/*.png` come from a synthetic workspace (fictional people, companies
and documents) at 1440×1000 in the light theme. After a visible dashboard change,
build the dashboard, install Playwright Chromium and regenerate them:

```bash
npm --prefix frontend run build
(cd frontend && npx playwright install chromium)
uv run python scripts/docs_screenshots.py
```

The script serves a temporary database on a free local port, captures every image
and deletes the database. Check each image before committing; add new captures to
`scripts/docs_screenshots.mjs`.

### Agent round trip

The manual MCP/file/backup driver requires an external Tectonic executable:

```bash
uv run python backend/tests/agent_roundtrip.py --tectonic /path/to/tectonic
```

## Project layout

| Path | Purpose |
|---|---|
| `backend/openings` | Shared SQLite services, REST, MCP, collection, worker and authentication |
| `frontend` | React dashboard calling REST |
| `examples` | Synthetic career data and LaTeX templates |
| `skills/` | Agent workflow skills (Agent Skills format) and their shared references |
| `scripts/` | Release version tool, package smoke check, parity matrix and documentation screenshots |
| `docs/user` | Setup, workflow and operator guides |
| `docs/developer` | Architecture and extension boundaries |

`uv.lock` and `frontend/package-lock.json` are authoritative. Keep personal data,
model caches, deployment files, one-off importers and development work notes out of
the public tree. Preserve upstream notices for vendored code.

## Changelog

Record user-visible changes under an `## Unreleased` heading at the top of
[CHANGELOG.md](CHANGELOG.md), creating it with the first change after a release.
Describe behavior, not implementation, and state any database schema change with
its upgrade and restore consequences.

## Releases

CI checks formatting, backend/frontend tests, version consistency, dependency
audits, an installed wheel and native Linux amd64/arm64 core images. Container
smoke checks authentication, nonroot startup and packaged source/resource hashes.
Dependabot proposes weekly grouped updates for Python, npm, GitHub Actions and
Docker base images.

The version appears in `pyproject.toml`, `backend/openings/__init__.py`, the
`Dockerfile`, `docker-compose.yml`, `.env.example`, `frontend/package.json` and
both lock files. Set all of them at once, then check the locks:

```bash
python3 scripts/bump_version.py X.Y.Z
uv lock --check
npm --prefix frontend install --package-lock-only --ignore-scripts
python3 scripts/bump_version.py --check
```

Rename `## Unreleased` to `## X.Y.Z — YYYY-MM-DD` (the release date), commit,
then tag `vX.Y.Z` after the release commit is on `main`.

The release workflow publishes versioned core images to Docker Hub for a pushed
`vX.Y.Z` tag, or a manual run with **publish** enabled. The requested version must
match `pyproject.toml`; publication waits for CI. Each architecture is built on a
native runner, pushed by digest and smoke-tested from the registry; only those
digests are combined into the multi-arch image tagged `vincenzoimp/openings:X.Y.Z`
and `X.Y` (final releases only). The workflow then creates the GitHub Release for
an existing `vX.Y.Z` tag from the `## X.Y.Z` CHANGELOG section, adding the image
digest, so write that section before pushing the tag. Branch/PR checks do not publish.

Before a release, review the changelog and a practical collection → application →
external-agent documents → review → backup/restore workflow. Hardware claims need
measurements with a stated platform and workload. Distinguish observed resource
use, container limits and host requirements.
