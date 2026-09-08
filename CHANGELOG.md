# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-09-08

The tracker becomes the archive: nothing is deleted by accident, every
opening keeps every posting of it, the dashboard works on every screen, and
the whole thing is verified end to end.

### Changed

- **Blacklisting is a status.** `blacklisted` jobs keep their notes, files
  and timeline, leave every list, facet, statistic and export unless asked
  for, are never refreshed or re-created by a run, and can be restored to the
  status they held before. The separate blacklist table is gone.
- **One job, many postings.** A posting is identified by its canonical URL
  (or `source:external_id`); a job id is the hash of its first posting. The
  same opening seen on another board becomes a second posting of the job.
  Two different postings from one source stay two jobs, and `merge_jobs`
  folds duplicates together with all their material.
- Timestamps are stored in UTC with an offset and rendered in
  `logging.timezone` in logs and digests.
- Semantic search runs on a built-in ONNX sentence model with vectors in the
  database; Chroma and its dependencies are gone. Both processes embed what
  they write. `vector_search` in `settings.yaml` is now `embeddings`.
- A run whose every task failed is recorded as failed and retried; the
  Telegram digest is skipped when nothing is new (`send_empty`).
- The web process reloads `settings.yaml` when the file changes.
- Filter parameters are plural everywhere (`statuses`, `sources`, `labels`,
  `job_types`, `locations`); `POST /api/jobs` returns `200` when it updates
  an existing posting; `add_job` merges fields into a known posting instead of
  overwriting its payload.
- Python 3.12 or newer.

### Added

- `/mcp` requires the same API token as `/api`.
- REST and MCP: `PATCH /jobs/{id}` and `update_job`, `PUT` notes and
  `update_note`, `PATCH` attachments and `update_attachment`, `GET
  /attachments` and `list_attachments`, `get_attachment`, `GET
  /jobs/{id}/bundle.zip`, `GET /jobs/{id}/similar` and `search_similar` by
  `job_id`, `POST /jobs/merge` and `merge_jobs`, `POST /runs`, `GET
  /runs/status` and `run_now`, `GET /settings` and `get_settings`, `GET
  /settings/reference`, label rename and delete, facets with `limit` and
  `q`, `direction` on sorts, `text` search over notes, `has_attachments` and
  `without_labels` filters, `status_changed_from/to`, dry-run counts for the
  cleanup routes, `postings_count`, `notes_count` and `attachments_count` in
  summaries, `include_raw` and `max_description_chars` on `get_job`.
- `titles` filters on company feeds and RSS feeds.
- Dashboard: design tokens with a dark theme, a phone layout with bottom
  tabs, bulk selection and actions, infinite scrolling, filters kept in the
  URL, semantic search with the `~` prefix, status changes with a note,
  editable postings, notes and answers, inline attachment previews, bundle
  download, merge, similar postings, a restorable blacklist, run-now with a
  live run status, retention dry-run confirmations, and a shortcut list
  generated from the active shortcuts.
- Playwright end-to-end suite against real servers on desktop, dark, iPhone
  and iPad viewports with axe-core checks; backend integration tests; the
  Docker smoke test covers the bundle, merge, run-now and the MCP token gate.

### Removed

- `retention.purge_blacklist_after_days`, `sources.jobspy.rate_limit_cooldown`
  and the `vector_search` section; the `/blacklist/purge` and
  `/cleanup/purge-blacklist` routes; dead helpers and the three process
  singletons, replaced by one `Runtime`.

## [0.1.0] - 2026-09-08

First release of Openings: a configurable job crawler, archive and application
tracker you run yourself, agent-operable through MCP. Openings supersedes
job-search-tool; it reads none of its configuration or data.

### Added

- One YAML file (`settings.yaml`) owns intake and scoring: sources, queries,
  locations, keyword categories with signed weights, save and notify
  thresholds, scheduler interval, notifications, retention. Unknown keys fail
  at boot; secrets can be indirected through `$ENV_VAR`.
- Sources behind one canonical shape: job boards through JobSpy, company
  career feeds on Greenhouse, Lever, Ashby and SmartRecruiters, RSS and Atom
  feeds, the Adzuna API, and postings added by hand. Every source is isolated
  per task so one failure never empties a run.
- A job is the canonical posting plus the application built around it: one
  status (`new`, `shortlisted`, `applied`, `interviewing`, `offer`,
  `rejected`, `withdrawn`), free labels, notes and form answers, file
  attachments (CV, cover letter, form answers, other), and an append-only
  timeline. Every status except `new` is protected from retention.
- A blacklist that deletes a posting and blocks its re-ingestion by identity.
- A `runs` table with per-source counts and failures for every collection.
- REST API under `/api`, MCP tools under `/mcp`, and a dashboard, all served
  by one process and all calling the same application service.
- Dashboard built around triage: Inbox (new postings, "since last visit"),
  Pipeline (one column per status, keyboard or drag to move), Companies,
  Runs, System, and a job page with Posting, Application and Activity tabs.
  Keyboard shortcuts throughout (`?` lists them).
- Score explanation per job: which categories matched and what each weighed.
- Optional local semantic search (Chroma, embedded, scheduler as sole writer).
- Telegram digest of new postings above the notify threshold.
- CLI: `openings run`, `openings scheduler`, `openings web`,
  `openings healthcheck`. Docker image `vincenzoimp/openings` with a
  two-service Compose file.
