# Changelog

## 0.9.0

- Resume portal pagination and missing descriptions across bounded collection batches.
- Freeze each collection run with its settings, optional overrides and cumulative progress.
- Schedule multiple daily local times or intervals and configure sources in bulk.
- Align source version checks, run controls and configuration discovery across interfaces.
- Score newly discovered incomplete jobs once their description becomes available.
- Keep location filters from widening a specific geography to unrestricted remote work.
- Simplify collection to JobSpy searches and supported company ATS/feed adapters.
- Refresh Collection controls and English guides with populated product screenshots.

This release uses schema 4. Installation-specific conversion remains outside the application.

## 0.8.0

- Separate career titles, organizations, partial dates, skill tags and ordering.
- Support single dates, periods and Present without requiring descriptions.
- Manage related claims from an entry and distinguish entries by organization.
- Show career dates and content previews on cards; search by organization.
- Identify saved searches by query/location and compact template choices.
- Preserve structured career facts and order in REST, MCP and frozen contexts.

This release uses schema 3. Earlier database formats require separate conversion
outside the application.

## 0.7.0

- Fit long postings into the scorer token budget, retain original text and show shortened input.
- Preserve dismissed jobs across changed URLs and report conflicting source identities.
- Refresh cached ATS descriptions within request caps; filter Greenhouse listings before loading details.
- Require the current document version for approval, including concurrent attachment changes.
- Protect dashboard drafts and refreshed edits; repair bulk selection and explicit closure outcomes.
- Page source cards and load attachment lists when opened.
- Reject redirects that would bypass another provider's request policy.

Document approval now requires `expected_version`. This release uses schema 2;
earlier database formats require separate conversion outside the application.

## 0.6.2

- Display structured compensation ranges and preserve existing salary text.
- Keep scorer dependency layers reusable across version changes.

## 0.6.1

- Remove manual fit assessments from the dashboard, REST and MCP.

## 0.6.0

- Record external fit reviews with scores, reasoning and frozen context through the dashboard, REST and MCP.
- Choose whether automatic scoring includes updated jobs or only new arrivals.
- Use an explicit compact scoring profile without duplicating detailed career evidence.
- Organize awards and publications as career knowledge categories.
- Display exact numeric scores consistently with filters.

## 0.5.4

- Accept MCP requests at the endpoint advertised by the dashboard, with or without a trailing slash.

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
