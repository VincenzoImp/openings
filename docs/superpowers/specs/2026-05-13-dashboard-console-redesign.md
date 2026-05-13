# Dashboard Console Redesign Spec

## Goal

Build a production-grade Job Search Console where the dashboard, REST API, and
MCP tools expose the same operational capabilities over one application layer.
The dashboard must support fast triage, deep filtering, safe bulk operations,
cleanup, semantic search, export, and analysis without duplicating business
logic in the frontend.

## Non-Negotiable Constraints

- Dashboard, REST API, and MCP must remain capability-equivalent for every
  operation that changes or exports job state.
- The dashboard uses one primary component library: HeroUI. Tailwind is used
  for layout and utility styling. Custom CSS is limited to global base imports
  and unavoidable browser reset rules.
- Dashboard business logic stays thin. Commands and queries live in the shared
  application layer, then surface through REST and MCP adapters.
- Blacklist and permanent delete are distinct operations.
- Destructive operations require explicit confirmation in the dashboard and
  clear command names in REST/MCP.
- Docker E2E smoke must validate API, MCP, and dashboard serving on the built
  image.

## Product Model

### Active Jobs

Active jobs are records in the `jobs` table. They can be listed, searched,
filtered, saved, marked applied, blacklisted, exported, or permanently deleted.

### Blacklisted Jobs

Blacklisted jobs are records in the `deleted_jobs` table. A blacklisted job is
not simply deleted; it is a rule saying "do not save this job again if future
searches rediscover it." The dashboard must include a blacklist view where users
can inspect blacklist entries and remove them from the blacklist.

Existing blacklisted entries only store `job_id`, `title`, `company`,
`location`, and `blacklisted_at`. The redesign keeps that shape to avoid an
unnecessary schema expansion in the first pass. Unblacklisting removes the block
rule; it does not restore the old active job record. If the job appears again in
a future search, it can be saved again.

### Permanent Delete

Permanent delete removes active job records without adding them to the blacklist.
If the same job appears in a future search, it can be inserted again. This is a
separate command from blacklist.

## Information Architecture

The dashboard uses a dense operational layout:

- Left navigation: top-level workspaces and saved views.
- Main work area: filtered queue or specialized view.
- Right inspector: selected job details, metadata, actions, and similar jobs.
- Contextual action bar: appears when rows are selected.

Primary views:

- `Jobs`: full active-job triage surface.
- `Saved`: saved/bookmarked jobs, same table controls as Jobs.
- `Applied`: application tracking, same table controls as Jobs.
- `Blacklist`: blocked jobs with unblacklist and purge workflows.
- `Cleanup`: preview, candidates, and controlled cleanup execution.
- `Analytics`: score/source/company/location/job-type summaries.

Saved views are frontend presets over server filters:

- Open jobs: not bookmarked and not applied.
- High score: relevance score >= 40.
- Low score cleanup candidates: below configured save threshold when available,
  otherwise below a dashboard-selected threshold.
- Remote jobs.
- Recently seen.

## Dashboard Feature Set

### Filtering And Search

The Jobs/Saved/Applied views expose:

- free-text search across title, company, location, description
- semantic search query
- score min/max
- site multi-select
- company text filter
- location text filter
- job type multi-select
- remote state
- status: all, open, saved, applied
- salary min/max
- date posted / first seen / last seen filters
- sort: score, date, company, title, salary
- page size

Backend filtering is the source of truth for large datasets. The frontend may
use already-returned rows for presentation details, but every primary filter in
this section gets a REST query parameter, MCP argument, and database-backed
implementation before the redesign is considered complete.

### Row And Bulk Actions

Active job actions:

- save / unsave
- mark applied / mark unapplied
- blacklist
- permanent delete
- open job URL
- export selected

Bulk active job actions:

- save selected / unsave selected
- mark selected applied / mark selected unapplied
- blacklist selected
- permanently delete selected
- export selected

Blacklist actions:

- list blacklist entries
- unblacklist selected
- purge blacklist older than N days
- purge all blacklist entries with confirmation

Cleanup actions:

- preview configured cleanup
- show cleanup candidate counts
- run configured cleanup
- run selected manual cleanup actions where supported:
  - delete active jobs below score threshold
  - delete stale active jobs
  - purge blacklist older than N days

### Inspector

The job inspector includes:

- title, company, location, site, score
- saved/applied state
- salary, job type, remote, date posted, first seen, last seen
- full description
- source URL
- quick actions
- similar jobs section backed by vector search when available

## Shared Application Capabilities

All capabilities are exposed from `JobApplicationService`.

Queries:

- `list_jobs(query) -> JobListResult`
- `get_job(job_id) -> JobRecord | None`
- `list_blacklisted_jobs(query) -> BlacklistResult`
- `get_statistics() -> Stats`
- `get_score_distribution(bin_size) -> list[tuple[int, int]]`
- `get_facets() -> Facets`
- `search_similar(query, filters) -> list[SemanticResult]`
- `export_jobs(query | ids, format) -> bytes`
- `preview_cleanup(config) -> CleanupPreview`

Commands:

- `set_bookmarked(job_ids, bookmarked) -> JobCommandResult`
- `set_applied(job_ids, applied) -> JobCommandResult`
- `blacklist_jobs(job_ids) -> JobCommandResult`
- `unblacklist_jobs(job_ids) -> JobCommandResult`
- `delete_jobs(job_ids) -> JobCommandResult`
- `delete_jobs_below_score(score) -> JobCommandResult`
- `delete_stale_jobs(days) -> JobCommandResult`
- `purge_blacklist(older_than_days | None) -> JobCommandResult`
- `run_cleanup(config) -> CleanupResult`

For backwards compatibility with existing internals, single-job REST routes stay
available. The application layer also supports list-based commands so bulk
operations are first-class.

## REST API Contract

Existing routes stay valid. New routes:

- `GET /api/jobs/facets`
- `POST /api/jobs/bookmark`
- `POST /api/jobs/applied`
- `POST /api/jobs/delete`
- `GET /api/blacklist`
- `POST /api/blacklist`
- `POST /api/blacklist/remove`
- `POST /api/blacklist/purge`
- `GET /api/export/jobs`
- `POST /api/export/jobs`
- `POST /api/cleanup/delete-below-score`
- `POST /api/cleanup/delete-stale`
- `POST /api/cleanup/purge-blacklist`

Existing single-job routes:

- `PUT /api/jobs/{job_id}/bookmark`
- `PUT /api/jobs/{job_id}/applied`
- `POST /api/jobs/blacklist`
- `GET /api/cleanup/preview`
- `POST /api/cleanup/run`

REST responses use consistent command envelopes:

```json
{
  "success": true,
  "affected_count": 3,
  "job_ids": ["..."],
  "message": null
}
```

## MCP Contract

MCP must expose tools matching the REST capability names:

- `list_jobs`
- `get_job`
- `list_blacklisted_jobs`
- `get_statistics`
- `get_score_distribution`
- `get_facets`
- `search_similar`
- `set_bookmarked`
- `set_applied`
- `blacklist_jobs`
- `unblacklist_jobs`
- `delete_jobs`
- `delete_jobs_below_score`
- `delete_stale_jobs`
- `purge_blacklist`
- `preview_cleanup`
- `run_cleanup`
- `export_jobs`
- `get_settings_documentation`

Tools return JSON strings, matching current MCP conventions.

## UI Components

Use HeroUI for:

- Button
- Card
- Chip
- Input
- Select
- Checkbox
- Tabs
- Modal/Dialog
- Table for non-virtualized lists such as blacklist entries and cleanup previews
- Dropdown/Menu
- Tooltip
- Spinner/Skeleton
- Pagination controls

Use TanStack Query for remote state and TanStack Table/Virtual for large active
job queues if HeroUI Table does not cover a required virtualized/server-backed
behavior without compromise. The visible controls and interactive primitives
still come from HeroUI.

Use Tailwind for:

- page layout
- grid/flex positioning
- spacing
- typography scale
- responsive behavior

Avoid:

- local custom Button/Input/Badge components
- decorative CSS backgrounds
- custom CSS component systems
- large handwritten CSS files

## Visual Direction

This is an operational tool, not a marketing page. The design should be quiet,
dense, legible, and professional:

- high information density
- restrained color
- clear destructive-action affordances
- predictable navigation
- no hero sections
- no decorative gradients/orbs
- no card-in-card layouts
- stable table dimensions

## Verification Matrix

Local verification:

- `./.venv/bin/pytest -q`
- `uv run mypy src/job_search_tool --ignore-missing-imports`
- `uv run pre-commit run --all-files`
- `npm --prefix frontend run quality`
- `npm --prefix frontend audit --audit-level=moderate`
- `docker compose config`
- `docker build -t job-search-tool:dashboard-console .`

E2E Docker smoke:

- build image
- start `job-search-web` with a seeded data directory
- assert `/health`
- assert token auth if configured
- call REST list/filter/action/export endpoints
- call MCP initialize/list-tools/call-tools flow over `/mcp`
- fetch dashboard HTML and static assets
- use Playwright against the running dashboard to verify:
  - token gate
  - job list renders
  - filters affect requests/results
  - selection enables bulk actions
  - inspector opens
  - save/apply/blacklist/delete flows update UI
  - blacklist view can unblacklist entries

## Rollout

This redesign ships as a minor release because it preserves the active-job
schema and existing routes. A future expansion from `deleted_jobs` to a full
archive table is out of scope for this spec and requires its own schema-change
release plan.
