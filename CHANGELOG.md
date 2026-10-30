# Changelog

## 0.5.3

- Exclude partial previews and punctuation-only placeholders from scoring; align completeness filters and counts.
- Read JobCloud template descriptions and preserve complete postings during bounded source refreshes.
- Export large archives as a consistent snapshot with complete JSON and bounded memory use.

## 0.5.2

- Show saved scoring state and keep Save visible while editing; report skipped scoring requests.
- Repair source edits, document refresh, context retry and application history in the dashboard.
- Match new-search defaults across interfaces and link overview counts to filtered results.
- Generalize public documentation and clarify container resource budgets.

## 0.5.1

- Restore join.com company listings and posting details for its current page data.
- Keep source configuration and scheduling responsive with hundreds of saved searches.

## 0.5.0

A fresh job-search workspace with one portable SQLite database and shared
English dashboard, REST and MCP interfaces. Previous Openings configuration and
databases are not compatible; this release starts a new workspace.

- Saved LinkedIn/Indeed/Glassdoor searches through pinned JobSpy 1.4.1, selected
  company ATS/feed monitoring, shared per-request provider limits/cooldowns,
  deduplication, corrections, text search and reversible triage.
- Detailed career evidence, approved claims, template packages/assets/defaults and
  editable general/template/application instructions.
- Optional separate CPU or remote AI scoring; disabled by default, visible stale
  results and deliberate bounded rescoring. No empirical fallback.
- Independent application attempts, Kanban/list, recorded-history funnel, frozen
  preparation contexts and exact document/PDF/source revisions.
- External-agent workflow with scoped byte transfers, manual review, owner auth,
  revocable API tokens and consistent SQLite backup/restore.
- Compact paginated lists, archive/source bulk actions, explicit task controls,
  provider policies, agent tokens, password updates and scoped JSON export.
- Docker core with no model runtime, optional local scorer and Linux amd64/arm64
  image build workflow.

Document generation and LaTeX compilation belong to the external agent. No internal
AI chat/account integration, server compiler, email/calendar or portal submission.
