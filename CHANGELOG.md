# Changelog

## 0.15.0

- Plan applications: optional `priority` (1–5) and `deadline`, a structured list of employer `requirements` (authorship, attachments, references, format, language, eligibility, deadline, other; blocking and resolved flags), sorting by deadline or priority, and a readiness filter (`blocked`, `none`, `missing_pdf`, `unreviewed`, `ready`) in REST, MCP and the dashboard.
- Report applications built on older inputs: `application_staleness` and `applications_staleness` compare frozen contexts with the current Profile, instructions, templates and selected Career entries and claims; the dashboard marks them "Built on older inputs".
- Check document content against its `.tex` source: `documents_consistency`, and review approval refuses a mismatch (409 `content_mismatch`) unless `allow_content_mismatch` is set deliberately.
- Find repeated vacancies without ingesting: `jobs_resolve` (by URL or source identity) and `jobs_duplicates` (candidate groups by company and title or identical posting text, never merged automatically), with a Possible duplicates view and a merge shortcut in job details.
- Bulk actions for applications: `applications_bulk` closes with an outcome, reopens or deletes up to 200 versioned items; bulk forget and delete collect unused file data once per run.
- Smaller agent responses: facets in `jobs_search` only with `include_facets`, summary defaults for `documents_list`, `sources_list` and collection runs, and compact job summaries from triage and update results.
- Conflicts on Profile, instructions, collection settings and document review include `current_version`; bulk item errors include `details`.
- Logout revokes every browser session; API tokens are unaffected.
- After a version conflict from a button action, the dashboard reloads the affected data instead of retrying with a stale version.

**Schema 6 upgrades automatically to 7** on first start, in one transaction (new `applications.priority`, `deadline` and `requirements`). Schema 5 still upgrades through 6. Restore accepts schema 5–7 backups. Back up before upgrading: an older release cannot open a schema 7 workspace.

## 0.14.0

- Ship the complete agent workflow skills: setup and onboarding, Inbox review, Shortlist preparation, source management, Career maintenance, application tracking, interview preparation and evidence-based writing, with shared references (operating mandate, employer requirements, vacancy identity, run report, tool reference).
- Serve the shipped skills to connected agents: `skills_list`, `skill_get` and one MCP prompt per skill, plus `GET /api/v1/skills` (the image now includes `skills/` at `OPENINGS_SKILLS`).
- Add an [operator workspace template](examples/operator-workspace/README.md): operating mandate, MCP configuration for six clients from one URL, a launcher that checks the token and sets `OPENINGS_URL`, and a script that fetches the server's skills.
- `setup-openings` checks for a LaTeX compiler on the agent's machine and offers a synthetic trial with the bundled examples.
- Settings → Agent access shows copy-ready MCP configuration for Claude Code, Codex and JSON clients, and lists the available skills.
- Add the [agent-operated job search](docs/user/agent-operated.md) guide: the agent runs and improves the search; the owner applies to prepared Drafts and records Applied.
- Career claims and Prepare Shortlist present the strongest truthful case and never volunteer gaps in application documents.

No database change: workspace schema remains 6.

## 0.13.0

- Add indexes for document revision leaves, activity, notes, job/source tasks, postings and file cascades; application lists on a large workspace drop from ~500 ms to ~20 ms. Indexes are created automatically at startup; schema remains 6.
- Add `exclude_titles` source filters: whole-word terms that skip matching titles before role and location filters, in REST, MCP and the source forms.
- Run synchronous MCP tools in worker threads so a slow tool no longer stalls REST, the dashboard or `/health`.
- Return structured MCP errors (`code`, `status`, `message`, `details`) matching REST; version conflicts include `current_version` on both interfaces.
- Enforce request size limits on the bytes actually received, including chunked bodies without `Content-Length`: 40 MiB for API requests and 16 KiB for sign-in/setup routes.
- Write backup, restore-upload and rollback copies beside the database on the data volume instead of the container's temp directory, and remove copies left by a crash at startup.
- Raise the default `OPENINGS_MAX_RESTORE_MB` from 512 to 2048 and recreate current indexes after a restore.
- Remove the SQLite WAL sidecar files of temporary backup and restore copies with the copies themselves.

Workspace schema remains 6. New indexes are created automatically at startup; existing data and frozen snapshots require no migration.

## 0.12.0

- Clarify application cards with current revision PDF/review state and direct next actions; keep postings accessible inside the application.
- Make mobile applications start in a compact list, remember the chosen view, and expose stage totals and partial board pages.
- Prioritize posting text and triage in job details; group rare maintenance actions and make queue empty states actionable.
- Add searchable context selectors with evidence/claim dependencies and a compact mobile template chooser.
- Preserve compatible form answers and unfinished import text; add editor-local conflict recovery and deliberate note/file/question deletion.
- Preview supported files from filenames and keep exact metadata under Details.
- Fix cancelled-response crashes, nested dialog scroll locks, navigation focus, loading/selection races, sidebar counts, contrast and mobile chart overflow.
- Fix JSON export of undated career entries and snapshot file bytes before streaming across worker threads.
- Add synthetic desktop/mobile browser workflows for Chromium and WebKit, request regressions and exact revision/export/file invariants.

Workspace schema remains 6. Existing data and frozen snapshots require no migration.

## 0.11.0

- Give Inbox and Shortlist distinct actionable queues, excluding all jobs with application history.
- Add direct Shortlist navigation and name application preparation clearly as Preparing.
- Keep closed attempts, documents and deliberate later attempts in Applications; restore known workaround dismissals explicitly.
- Remove fit scoring, its UI, REST/MCP operations, queue work and optional container.
- Align API/MCP contracts, agent guidance, user documentation and populated screenshots.

Schema 5 upgrades automatically to schema 6, preserving jobs, applications, file
ownership and immutable snapshots. Back up before upgrading. Restores require
schema 6; upgrade a copy of an older schema-5 backup before restoring it.


## 0.10.0

- Archive automatic results only after usable posting text is available; resume pending details from collection checkpoints.
- Simplify provider settings to enable/pause and request spacing, with automatic server cooldowns.
- Retrieve descriptions automatically and identify sources that cannot supply them.
- Show shortlist membership and application progress together, with direct removal and Start/Continue actions.
- Enforce one open application per job, explicit closing outcomes and versioned job/application deletion.
- Align job-specific application lookup, field clearing and bulk failure handling across dashboard, REST and MCP.
- Refresh English guides and populated screenshots, including the workspace overview.

This release uses workspace schema 5. APIs and stored source/provider settings use
the current contract; earlier workspace formats require separate conversion.

## 0.9.1

- Show and validate only acquisition options supported by each ATS adapter.
- Align native source, bulk and run controls with discovered configuration schemas.
- Report metadata-only descriptions as unavailable and the collection as partial.
- Explain unavailable public Ashby boards and avoid automatic retries for their 404 responses.
- Identify provider-budget waits clearly in collection progress.

Workspace format remains schema 4. Saved company configurations must match their
current adapter schema; remove options that the adapter does not use.

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
