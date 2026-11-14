# Contributing

Read the [architecture](docs/developer/architecture.md) and relevant
[user guide](docs/README.md) before changing behavior. Keep business logic in
shared services. Parity runs one way: every dashboard action is a REST operation,
and every operation that is not owner-only is also an MCP tool; REST and MCP may
offer more than the dashboard. Code, UI and documentation
are English; public examples/screenshots contain synthetic data only. Participation
follows the [code of conduct](CODE_OF_CONDUCT.md); report vulnerabilities privately
as described in [SECURITY.md](SECURITY.md).

Open an issue with the bug or feature form before large changes. Pull requests use
the template's checklist: tests, one-way parity, synthetic fixtures and updated
documentation.

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
backend. The design system of the new dashboard (`frontend/src/ui`) has a
gallery of every primitive at `http://127.0.0.1:5173/ui.html` on that server; the
dashboard does not link or serve it. Never commit development databases or
credentials.

To build Docker images locally, give them local names:

```bash
OPENINGS_IMAGE=openings:local docker compose up -d --build
```

## Verify a change

```bash
uv run ruff check backend scripts
uv run ruff format --check backend scripts
uv run pytest -n auto
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
`chromium-performance`, starts its own workspace of 25,000 jobs (with their
ingest signals) and 500 applications and fails when the Applications list or
the jobs to review take 300 ms or more to show 200 rows (the median of seven
loads). CI runs Chromium at both widths inside the official Playwright container
image, so it downloads no browsers; WebKit at both widths and the performance
project run weekly in `.github/workflows/nightly.yml`. The image tag in `ci.yml`
and `nightly.yml` must equal the `@playwright/test` version in the lock file; the
`e2e` job fails early when they differ. Browser binaries are development tools,
outside the core.

The global setup seeds one synthetic workspace into a snapshot file
(`backend/tests/dashboard_server.py --seed`) and signs the owner in once. Each
Playwright worker starts its own server on a private copy of that snapshot, on a
free port it reads from the server's output, and an automatic fixture restores
the copy (`POST /__e2e__/reset`, a route of the test server only) before every
test. Tests therefore run fully in parallel and in any order, and a test may
change anything. `frontend/tests/isolation.spec.ts` checks this. CI runs four
workers in each of two shards (`e2e (1)`, `e2e (2)`) with one retry, and a test
that passes only on its retry fails the run (`failOnFlakyTests`): a flaky test is
reported and fixed, never hidden or quarantined.

### Backend fixtures

`backend/tests/conftest.py` builds one fresh database at the current schema per
test session (per xdist worker) and copies it per test. Its fixtures are
`database_path`, `workspace`, `app` (owner password set), `client` (signed in as
the owner, with the CSRF header), `owner_token`, `agent_token` and `mcp` (an MCP
client with the agent token). Use them instead of building a workspace or an
application in a test module; `*_fixtures.py` modules keep only data builders.
The default run (`uv run pytest -n auto`) skips the `performance` marker.

### Backend time budgets

`backend/tests/test_performance_budgets.py` builds a synthetic workspace of
25,000 jobs with their ingest signals, 500 applications, 20 sources and 60 frozen
contexts in a few seconds, and fails when the median of five reads exceeds its
budget: the Applications list, the reads of Today, the New jobs list (with counts
and facets), text search, the staleness report, Stats (under 50 ms), the
sources with their counts and the timeline of a busy job and application. The budgets are about six
times the time measured on a laptop, so a slower CI runner passes and a real
regression does not. It is marked `performance`, which the default `pytest` run
deselects (`addopts` in `pyproject.toml`), together with the 500-context storage
benchmark and the labelled duplicate benchmark; run them with
`uv run pytest -m performance`. CI runs them weekly. Never raise a budget to make
a change pass: make the read faster, or explain in the pull request why it must
cost more.

### Dashboard budgets

The dashboard has budgets that CI checks:

- **Size.** `npm --prefix frontend run budget` reads the build and fails when the
  first screen's compressed JavaScript exceeds 110 kB, a later screen adds more
  than 40 kB, or the stylesheets exceed 15 kB. Never raise a budget: load the
  code later or make it smaller.
- **Accessibility.** `frontend/tests/accessibility.spec.ts` runs axe on every
  screen in both themes at both widths: no serious or critical finding against
  WCAG 2.2 AA. Add a new screen or tab to its list, and fix a finding where it
  is; there are no exclusions.
- **Contrast.** `frontend/tests/contrast.test.mjs` computes the contrast of every
  colour token on the backgrounds it is used on from
  `frontend/src/design/tokens.css` and holds it to WCAG AA.
- **Keyboard.** `frontend/tests/shell.spec.ts` operates the navigation, the More
  sheet and the theme from the keyboard alone;
  `frontend/tests/today.spec.ts` answers a question on Today,
  `frontend/tests/activity.spec.ts` moves through the Activity tabs and opens a
  run's report, `frontend/tests/applications.spec.ts` goes from Today's
  Review to Mark applied and records an employer reply the same way,
  `frontend/tests/system.spec.ts` moves through the Collection tabs and switches
  scheduled collection, revokes tokens, `frontend/tests/skills.spec.ts`
  opens a skill and saves its local notes, and `frontend/tests/setup.spec.ts`
  moves through the steps of the setup guide.

The browser tests run on the synthetic workspace of
`backend/tests/dashboard_server.py` and `backend/tests/today_fixtures.py`, and
each test starts from it unchanged.

Screens use the components in `frontend/src/design` and add no global styles.

Every server listens on a port the system chooses, so runs in several checkouts
or worktrees can overlap. To look at the synthetic workspace by hand, run
`uv run python backend/tests/dashboard_server.py --port 18084`.

### Screenshots for review

`npm --prefix frontend run screenshots` writes an image of every screen of the
seeded workspace, including key states (empty, populated, dialog open), at
1440×1000 and 390×844 in the light and dark themes to `frontend/screenshots/`
(not committed). The Screenshots workflow runs it on every pull request that
touches `frontend/` and uploads the `screenshots` artifact. Embed the images of
every changed screen in the pull request (before and after for a rebuilt
screen). Add a new screen or state with one line in
`frontend/tests/screenshots.spec.ts`. These images are for people to look at;
there is no pixel comparison.

### Parity

Parity runs one way: every dashboard action is a REST operation, and every
operation that is not owner-only is also an MCP tool. REST and MCP may offer
more than the dashboard, and an owner-only operation may be REST only.
`backend/tests/test_parity.py` computes this from the operation declarations in
`backend/openings/interfaces/`: every `/api/v1` route belongs to exactly one
operation or to a transport exemption with a one-line reason, and every
operation that is not owner-only has exactly one MCP tool with its name.

### Documentation screenshots

`docs/images/*.png` come from a synthetic workspace (fictional people, companies
and documents) at 1440×1000 in the light theme:
`npm --prefix frontend run screenshots -- --docs` rewrites the images that
`frontend/tests/screenshots.spec.ts` marks with a `docs` name. Check each image
before committing it.

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
| `scripts/` | Release version tool, package smoke check, release fixture and upgrade rehearsal |
| `docs/user` | Setup, workflow and operator guides |
| `docs/developer` | Architecture and extension boundaries |

`uv.lock` and `frontend/package-lock.json` are authoritative. Keep personal data,
model caches, deployment files, one-off importers and development work notes out of
the public tree. Preserve upstream notices for vendored code.

## Changing the schema

`backend/openings/schema.sql` is the whole layout of a new workspace and runs only
on a new file. A workspace of the previous schema is upgraded by the one migration
in `backend/openings/migrations/` (`MIGRATIONS` has exactly one key,
`SCHEMA_VERSION - 1`); any older workspace is refused with the release to open it
with first. A migration is frozen with its release: it imports only the standard
library and holds every statement it needs (`test_migration_policy.py`).

The 0.24 migration, `m15.py`, builds a new file from `schema.sql` and copies the
data in, so an upgraded workspace equals a new one (`test_upgrade.py` compares
them). **While its release is unreleased, change it instead of adding a version**
("edit the unreleased migration"), in the same pull request as the schema change:

- `schema.sql`: the new layout.
- `m15.TABLES`: a `Table` entry per changed table, with `columns` (an SQL
  expression over the schema-14 row `o` for each new or transformed column),
  `source` for a renamed table, `where` for rows that are not copied, or
  `fresh=True` for a new table.
- `m15.SECTIONS`: the archive section of every removed table or value that is not
  already archived automatically (a dropped column's non-default values go to
  `dropped_columns` by themselves; list a column in `NOT_ARCHIVED` only with a
  reason).
- `m15.FOLDS`: functions that create rows from removed data (notes, items), each
  returning the rows it created per table; `m15.INVARIANTS` for values the upgrade
  must keep.
- A block of data mapping assertions in `backend/tests/test_upgrade.py`, and the
  aggregates of the dropped or folded columns in `scripts/verify_m15.py`.

Before the release, run `scripts/verify_m15.py` on a private copy of a real
workspace (aggregates only; add `--upgrade` to time an upgrade of a copy).

**Fixtures.** `backend/tests/fixtures/workspace-<schema>.sql.gz` is a real
workspace written by the last release at the previous schema, from that release's
own synthetic seed (the browser-test workspace and the agent round trip, which
needs `tectonic`). Regenerate it at release time when the seed changed, and at the
next schema change for the new previous schema; then delete the older fixture:

```bash
uv run python scripts/release_fixture.py --tag v0.23.1 --schema 14
```

At the next schema change, delete `m15.py`, write the next migration (a new file
from `schema.sql` with the data copied in is the default), point `MIGRATIONS` at
it, and rename the user-visible files in it (`openings.pre-<release>.sqlite`).

## Changelog

Record user-visible changes under an `## Unreleased` heading at the top of
[CHANGELOG.md](CHANGELOG.md), creating it with the first change after a release.
Describe behavior, not implementation, and state any database schema change with
its upgrade and restore consequences.

## Releases

CI checks formatting, backend/frontend tests, version consistency, an installed
wheel and the core image (amd64 on pull requests; amd64 and arm64 on `main` and
in releases). Container smoke checks authentication, nonroot startup and packaged
source/resource hashes. The weekly workflow runs the performance tests, WebKit,
the large-workspace browser budget and the dependency audits; check its latest
run on `main` before each release. The release workflow audits dependencies
again and attaches an SBOM and provenance attestation to each image.
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

## Repository settings

`main` is protected by a branch ruleset: every change arrives through a pull
request whose required checks pass on a branch that is up to date with `main`;
force-pushes and deletion are blocked, and nobody, administrators included, can
bypass it. No review is required (single owner). The required checks are the job
names of `.github/workflows/ci.yml`: `backend`, `frontend`, `e2e` and
`container (amd64)`. `e2e` is a gate that passes only when every browser shard
(`e2e (1)`, `e2e (2)`) passed, so the number of shards can change without
touching the ruleset. A change that renames those jobs updates the ruleset in
the same pull request.

The ruleset was created with:

```bash
gh api --method POST repos/VincenzoImp/openings/rulesets --input - <<'JSON'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          {"context": "backend", "integration_id": 15368},
          {"context": "frontend", "integration_id": 15368},
          {"context": "e2e", "integration_id": 15368},
          {"context": "container (amd64)", "integration_id": 15368}
        ]
      }
    }
  ]
}
JSON
```

`15368` is the GitHub Actions app, so only Actions can report these checks. To
change the checks, find the ruleset id with
`gh api repos/VincenzoImp/openings/rulesets` and send the same body with
`gh api --method PUT repos/VincenzoImp/openings/rulesets/<id> --input -`.
