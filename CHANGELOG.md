# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-08

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
