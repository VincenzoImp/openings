# Changelog

## 1.0.0

A fresh job-search workspace with one portable SQLite database and shared
English dashboard, REST and MCP interfaces. Previous Openings configuration and
databases are not compatible; this release starts a new workspace.

- Manual and scheduled Greenhouse/Lever/Ashby/RSS ingestion, explicit company watch,
  deduplication, corrections, text search and reversible triage.
- Detailed career evidence, approved claims, template packages/assets/defaults and
  editable general/template/application instructions.
- Optional separate CPU or remote AI scoring; disabled by default, visible stale
  results and deliberate bounded rescoring. No empirical fallback.
- Independent application attempts, Kanban/list, recorded-history funnel, frozen
  preparation contexts and exact document/PDF/source revisions.
- External-agent workflow with scoped byte transfers, manual review, owner auth,
  revocable API tokens and consistent SQLite backup/restore.
- Docker core with no model runtime, optional local scorer and Linux amd64/arm64
  image build workflow.

Document generation and LaTeX compilation belong to the external agent. No internal
AI chat/account integration, server compiler, email/calendar or portal submission.
