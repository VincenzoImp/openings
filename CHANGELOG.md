# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-08

First release of Openings: a configurable job crawler, archive and application
tracker you run yourself, agent-operable through MCP. Openings supersedes
job-search-tool; it reads none of its configuration or data.

### Added

- One YAML file (`settings.yaml`) owns intake and scoring: sources, queries,
  locations, keyword categories with signed weights, save and notify
  thresholds, scheduler interval, notifications, retention. Unknown keys fail
  at boot; secrets can be indirected through `$ENV_VAR`; the web process
  reloads the file when it changes.
- Sources behind one canonical shape: job boards through JobSpy, company
  career feeds on Greenhouse, Lever, Ashby and SmartRecruiters, RSS and Atom
  feeds, the Adzuna API, and postings added by hand or by an agent. Every
  source is isolated per task so one failure never empties a run; feeds take
  location, title and age filters; employment types share one vocabulary.
- One job, many postings: a posting is identified by its canonical URL, the
  same opening seen on another board becomes a second posting of the job, and
  duplicates can be merged with their material.
- A job is the opening plus the application built around it: one status
  (`new`, `shortlisted`, `applied`, `interviewing`, `offer`, `rejected`,
  `withdrawn`, `blacklisted`), free labels, notes and form answers, file
  attachments (CV, cover letter, form answers, other), and an append-only
  timeline in UTC. Every status except `new` is protected from retention.
  Blacklisting hides a job and blocks its re-ingestion without deleting
  anything; it can be restored.
- A `runs` table with per-source counts and failures for every collection,
  a run-now request, and a Telegram digest sent only when something is new.
- Local semantic search on a built-in sentence model (ONNX), vectors in the
  database: "similar postings" and free-text search by meaning.
- REST API under `/api`, MCP tools under `/mcp` (same token as the API), and
  a dashboard, all served by one process and all calling the same service;
  one zip per application with the posting, notes, timeline and files.
- Dashboard built around triage, on phone, tablet and desktop in light and
  dark: Inbox (new postings, bulk actions, filters kept in the URL, semantic
  search with `~`), Pipeline (every status as a column), Companies, Runs,
  System, and a job page with Posting, Application and Activity tabs.
  Keyboard shortcuts throughout (`?` lists the active ones).
- Score explanation per job: which categories matched and what each weighed.
- CLI: `openings run`, `openings scheduler`, `openings web`,
  `openings healthcheck`. Docker image `vincenzoimp/openings` with a
  two-service Compose file. Unit, integration, Playwright and Docker smoke
  tests in CI.
