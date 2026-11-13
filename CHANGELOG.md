# Changelog

## 0.21.0 — 2026-11-13

Jobs that explain themselves, rules that act on them, and the System screens on the new design.

- **Signals on every job**, computed without a model: posting language, required and welcome languages, a likely duplicate of an earlier job (decide Same vacancy or Different inside the job; `POST /jobs/{id}/distinct`), and "no longer listed" for company-board postings. The job field `availability` is deprecated and no longer shown.
- **Policy rules act:** once enabled and confirmed by you, a decision rule on a signal dismisses or flags new jobs nobody has touched, when their signal arrives. Each dismissal names its rule and can be restored; duplicates are never merged. Each rule shows how many jobs waiting for review it would match (`POST /policy/rules/preview`, MCP `policy_rule_preview`).
- **Yield:** Collection → Yield shows, per source and search, what was collected, kept, applied to, answered and dismissed, and by whom (`GET /collection/yield`, MCP `collection_yield`).
- **Jobs** is rebuilt: To review, Shortlist, Dismissed and All, each beside the selected job; dismiss with a reason and restore; bulk actions; Add a job looks the address up first. `GET /jobs` filters by signal, language, dismissal and rule; dismissals take a `reason`.
- **Skill local notes:** up to 2,000 characters per skill, versioned and attributed, added after the shipped text whenever an agent reads the skill (REST, `skill_get`, MCP prompts); the shipped text is never changed. `skills.notes.read` and `skills.notes.update` on REST and MCP; agent tokens may write them. The dashboard shows each skill's text, reference files and notes, and a run report's Method section can be added to the notes.
- **Collection** is rebuilt with Sources (a typed form instead of JSON), Runs and tasks, Providers and Yield. **Settings** is rebuilt with Agent access, Skills, Backup and restore, and Workspace; owner-only parts are marked. Old links keep working.
- The runs list includes each run's method section; `/workspace` and `workspace_info` report the schema version.
- Fixed: reading the workspace's storage size could fail while the write-ahead log was being checkpointed.

**After upgrading:** open Policy to enable the rules you want; none acts until you do. The signals of existing jobs are computed in the background in the first minutes after start; until then a job shows no signals.

**Database schema 12 (additive).** A schema 5–11 workspace is upgraded automatically at start in one transaction: skill notes, job signals, dismissal records (filled from each job's last dismissal event) and listing observations. Restore accepts schema 12 and upgrades a copy of an older backup. A schema 12 workspace cannot be opened by 0.20 or earlier: back up before upgrading.

## 0.20.0 — 2026-11-13

What employers answered, what it tells you, and one page to review and send an application.

- **Employer responses:** record an interview, rejection, offer or other answer with its date and note, from the Applications list, the review page or the API (`/applications/{id}/responses`, `/responses/{id}`; MCP `responses_*`). Moving a sent application to Interview or Offer, or closing it as Rejected, records the matching response.
- **No reply:** the `no_response` outcome with `concluded_on`. The no-reply period comes from the Policy's "No reply" decision item (30 days without one); `GET /applications?no_reply_due=true` lists applications past it, and Today and Insights close them after listing them.
- **Insights** (`GET /insights`, MCP `insights_get`): response, interview and offer rates and the time to a first answer for sent applications, by role family, seniority, location, source and month. A rate is withheld below a minimum sample (default 5). Role family and seniority come from fixed English, German, French and Italian keyword tables.
- **Review page** for each application: posting, CV and letter side by side, Before you send, Download, Mark applied, Not pursuing and the place in the Ready queue; answers, requirements, timeline, inputs, documents and details in tabs. Old application links open it.
- **Applications** is rebuilt as a pipeline (Preparing, Ready, Applied, Interview, Offer, Closed) with a list, a board and bulk actions. Progress moved from Today to Applications → Insights.
- **Staleness by part:** "Built on older inputs" now compares only what documents use: the Profile name, headline, contact, links and summary; confirmed eligibility, writing and fact items of the policy; the instructions, and each frozen template, Career entry and claim by content. Profile metadata, preferences and roles, positions, names, default flags, claim selection fields, free-form metadata and whitespace-only edits no longer mark a Draft stale, and a change undone is current again. Reports and the dashboard name each changed part; a writing rule scoped to the CV or the letter only affects that document.
- Fixed: a frozen context with an unreadable payload no longer stops the workspace from opening.

**Database schema 11 (additive).** A schema 5–10 workspace is upgraded automatically at start in one transaction. The upgrade adds the `responses` table, rebuilds `applications` for `no_response` and `concluded_on` (every row, index and trigger kept, references checked before committing), records one response for each application already in Interview or Offer and each sent rejected one (marked estimated when no stage event dates it), and stores content hashes of every frozen context's inputs. Restore accepts schema 11 and upgrades a copy of an older backup. A schema 11 workspace cannot be opened by 0.19 or earlier: back up before upgrading.

## 0.19.0 — 2026-11-13

Your decisions in your own words, and a first screen that tells you what to do next.

- **Today** replaces Overview as the first screen: a one-line summary of what waits for you; the applications ready to apply, by deadline and priority; the agent's questions, answered in place, and applications blocked by a requirement; the pipeline; what the agent and collection did since your last visit; and applications waiting longer than your policy's no-reply period (30 days without one). The former Overview numbers are under Progress. `#overview` links open Today.
- **Policy**, a new Library screen with `policy_*` operations on REST and MCP: your decision rules, eligibility facts, writing rules and other confirmed facts as short statements in four sections, each with its own version. Items an agent writes are proposals until you confirm them; only you confirm an item or switch on a rule.
- A decision item can carry a rule on a collection signal (`language_required`, `posting_language`, `likely_duplicate`, `no_longer_listed`). Rules are stored and validated; they are not applied at collection yet.
- A prepared context freezes the policy sections with their versions (`payload.policy`); earlier contexts are unchanged.
- **Claims** have typed selection fields: `default_in_cv`, `role` (`core`, `supporting`, `bench`) and `group`. Template `rules` gain `statements`, a typed list of rule statements beside the limits.
- **Career and Templates** are rebuilt on the new design. Free-form metadata and the rest of template rules are edited as key/value rows instead of JSON text. Earlier links keep working.
- **Activity** is rebuilt with Questions, Requests, Runs and a Timeline that filters changes by who, kind of record, period and run; run reports count changes by kind with links to the records.
- The application list filters by applied time (`applied_since`, `applied_until`), the run list by last activity (`active_since`) and the change list by several kinds of record (`subject_types`); changes, questions and requests name their run's workflow (`run_workflow`).
- Skills read and maintain the policy and the typed claim fields. `examples/policy.json` is a synthetic policy.
- Profile `preferences` and `roles` are deprecated in favour of Decision items; they are still stored, returned and writable.

**After upgrading:** open Policy. Each top-level Profile metadata key has been copied into an unconfirmed Facts item, and `preferences` and `roles` into unconfirmed Decision items. Confirm, edit or move them (or let your agent sort them and ask you); nothing was removed from the Profile.

**Database schema 10 (additive).** A schema 5–9 workspace is upgraded automatically at start in one transaction; the Profile, every Career entry, claim, template and frozen context keep every value. A claim metadata key `default_in_cv`, `role` or `group` with a valid value is copied to the typed field. Restore accepts schema 10 and upgrades a copy of an older backup. A schema 10 workspace cannot be opened by 0.18 or earlier: back up before upgrading.

## 0.18.0 — 2026-11-11

A much smaller database and the first stage of the new dashboard.

- **Smaller database:** frozen application contexts are stored as shared content-addressed parts, so each Career entry, claim, template, Profile, job and instruction text is kept once instead of once per context. Context reads, signatures, file ids and links are unchanged, byte for byte. On a real workspace with 670 contexts the file shrank from 535 MiB to 269 MiB together with the cleanup below.
- **Less noise in the change log:** a source refresh no longer writes a `posting_updated` event. Seeing a posting again updates its `last_seen_at`; a refresh that changes the title, company, location or posting text records one `job_refreshed` event naming the changed fields.
- **Stored observations:** postings keep only the source key and the employer's apply link instead of the provider's full response. Identity lookup, duplicate candidates, job sources and run summaries are unchanged. In the JSON export, `postings[].payload` contains only those two values.
- **Retention:** finished collection runs and tasks are removed after 90 days (`OPENINGS_RETENTION_DAYS`, `0` keeps everything). The 20 most recent finished runs of each source, queued and running work, and all job and application history are kept.
- **Restore limit from free space:** restoring needs 3 × the backup + the current database + 64 MiB free on the data volume. `OPENINGS_MAX_RESTORE_MB` is now an optional upper bound, unset by default. A backup that does not fit is refused before upload with `413 backup_size` and the sizes in the error details. `GET /workspace` and `workspace_info` return `storage` (database size, free space, restore limit, retention); Settings → Workspace shows it.
- **New dashboard shell:** navigation in three groups (Work, Library, System), a bottom bar with More on phones, and a top bar with theme and density. Inbox and Shortlist are under Jobs. All earlier links keep working. The pages themselves are redesigned in the following releases.
- **Readable in both themes:** text meets WCAG AA contrast and buttons and inputs have a visible border. The theme follows the system until you choose one; compact density is new and remembered.
- **Navigation shows what waits for you:** the number of applications ready to apply and of open questions, and the agent's name while a run is open.
- **Faster start of the dashboard:** screens load on demand; the first screen needs 90 kB of compressed JavaScript instead of 133 kB.
- **Duplicates after a restart:** the server prepares duplicate scoring in the background at start. On a small host the first listing after a restart took about 18 seconds.
- **Context lists** with `summary=true` read stored columns instead of parsing every payload (about 150 ms to 2 ms for 100 contexts).

**Database schema 9 (storage only).** A schema 5–8 workspace is upgraded automatically at start in one transaction; every context is compared with its stored form before the old copy is dropped, and nothing changes if one differs. Restore accepts schema 9 and upgrades a copy of an older backup. A schema 9 workspace or backup cannot be opened by 0.17 or earlier: back up before upgrading.

**Operators.** After the upgrade, and at any start when at least a quarter of the file and `OPENINGS_COMPACT_MIN_MB` (default 32) are free, the database file is rewritten without free space. This needs free disk on the data volume of about twice the new database size plus 64 MiB; without it the step is skipped with a log message and retried at the next start. An interruption leaves the previous file intact. Remove `OPENINGS_MAX_RESTORE_MB` from `.env` unless you want a cap.

## 0.17.0 — 2026-11-11

The owner and the agent can now hand work to each other inside the product: every change says who made it, an agent's runs and reports are stored, and questions and requests travel in both directions.

- **Who made each change:** every change records the dashboard session, a named API token (kept after the token is revoked, with its kind) or the system. Application history, the overview activity and notes show it; `GET /events` / `events_list` list all changes by run, record, actor or time. Changes that left no trace before (Profile, instructions, Career entries, claims, templates, notes, contexts, documents, files, sources, collection settings, tokens, restore) now leave an entry with identifiers, changed field names and versions only.
- **Agent runs:** an agent opens a run (`runs_start`, `POST /runs`) with a workflow and scope; its writes are attached automatically, and it closes the run with a stored report (summary, changes with server-derived counts, not done, checks, limits, method). One open run per token; a run never closed is shown as interrupted with the changes it made.
- **Questions for the owner:** records tied to a job, an application, a Career entry or nothing, with optional choices. Answer them under Activity; an agent reads answers given since a time (`questions_list` with `answered_since`).
- **Requests for the agent:** write an instruction under Activity → Requests, or with Ask your agent on a job or an application. The agent reads open requests at the start of its next run, takes them and reports a result or a reason; you can withdraw a request until it is finished. REST `/requests`, MCP `requests_*`. A request never authorises submitting an application, contacting an employer or recording Applied.
- **Ready is a stored step:** mark a Preparing application ready once every current revision has an approved PDF and no blocking requirement is open; otherwise the mark is refused and names the failed check. It is cleared, with a recorded reason, when a revision, context or blocking requirement changes or the application leaves Preparing. Applications has a Ready to apply queue, a badge, sorting by ready time and bulk Mark ready (`POST /applications/{id}/ready`, `application_ready`).
- **Scoped API tokens:** a token is `owner` or `agent`. An agent token runs the job search but is refused (403, REST and MCP) for the owner password, token management, restoring a backup, answering a question for the owner, and writing or withdrawing a request. Existing tokens are owner tokens and keep full access. A backup downloaded with an agent token omits the owner password hash, the session secret and the API tokens; it still restores completely.
- **Duplicate candidates:** `jobs_duplicates` scores each group from apply links and ATS posting ids, requisition ids, location, nearly identical posting text and company names without legal and country suffixes. Groups carry `confidence`, `tier` and `reasons` and are listed most confident first; nothing is merged automatically.
- **Dashboard:** new Activity page (Questions, Requests, Runs, Changes) with an open-question count in the navigation; Possible duplicates shows confidence and reasons.
- **Skills:** every workflow opens a run, reads the owner's answers and open requests, asks questions as records, marks finished Drafts ready and closes the run with the stored report.
- **MCP:** upgraded to the MCP Python SDK 2.3. The server also answers protocol revision 2026-07-28, reports the Openings version as its server version, and no longer includes internal exception text in unexpected tool errors.

**Changed behaviour**

- `readiness=ready` now means the stored Ready step. An application whose checks pass without the mark reports the new value `reviewed`. After upgrading, mark existing finished Drafts ready (bulk Mark ready in Applications, or let the agent do it).
- `jobs_duplicates` hides low-confidence groups by default; pass `min_confidence=0` for every candidate, including records that share only a company and title.

**Database schema 8.** A schema 5, 6 or 7 workspace is upgraded automatically at start in one transaction; existing records are kept, and earlier changes show the actor "unknown (before 0.17)". Restore accepts a schema 8 backup and upgrades a copy of an older one. A schema 8 workspace or backup cannot be opened by 0.16 or earlier: back up before upgrading.

## 0.16.0 — 2026-11-11

Platform release for the redesign: a newer runtime, stricter outbound connections and the groundwork to change the product safely. No workflow, REST or MCP contract changes.

- **Python 3.14:** the container image now runs Python 3.14 (previously 3.12); CI tests the same version, and running from source requires Python 3.14 or later.
- **DNS rebinding:** LinkedIn, Indeed and Glassdoor searches connect only to the address that passed the public-address check, on every request and redirect hop, matching URL imports; TLS still verifies the host name.
- **URL imports:** a job location given as plain text in a page's structured data is read correctly instead of producing a row of separators.
- **Parity matrix:** `docs/developer/parity.md` is generated from the operation inventory, the REST/MCP contract, the dashboard source and browser tests. It shows each operation's REST route, MCP tool and real dashboard path, and lists every gap.
- **Product proposal:** `docs/developer/proposal-redesign.md` records the accepted decisions for the redesign and their order.
- **Development:** TypeScript 7 for the dashboard, Ruff's default lint rules, and tests for the collection worker and URL fetching (98% and 100% line coverage).

Workspace schema remains **7**. Upgrading from 0.15 needs no action.

## 0.15.2 — 2026-11-10

Security hardening at the edges, a release pipeline that publishes exactly what it tested, and a repository that is easier to start with and contribute to.

- **Sign-in behind a reverse proxy:** `OPENINGS_TRUSTED_PROXIES` (IPs or CIDRs, default none) lets the server see real client addresses only from listed proxies, so each client gets its own sign-in limit and forwarded headers from anyone else are ignored. A global backoff spaces sign-ins after repeated failures across all clients (1 s doubling to 5 s; 429 `login_backoff` with `Retry-After` beyond 30 s); a successful sign-in resets it. API and MCP tokens are unaffected.
- **DNS rebinding:** URL fetches for job and feed imports resolve the host, require every address to be public and connect to the checked address on every redirect hop; TLS still verifies the host name.
- **Operational grants:** export, backup and restore grants use their own signing salt and work once (a reuse returns 401 `transfer_used`). Request a new grant for each retry.
- **Release pipeline:** each architecture is built natively, pushed by digest and smoke-tested from the registry; only those digests form the multi-arch image, tagged `X.Y.Z` and `X.Y`. The GitHub Release is created from this changelog section with the image digest.
- **Repository:** current screenshots (including agent access, application planning, requirements and duplicates), a README with badges and a current feature list, issue and pull request templates, a Code of Conduct, Dependabot for uv, npm, GitHub Actions and Docker, `ruff format --check` in CI, `scripts/bump_version.py` with a CI version-consistency check, and dated changelog headings.

**Deployers behind a reverse proxy** should set `OPENINGS_TRUSTED_PROXIES` to the proxy's address as the container sees it; without it all clients share one sign-in limit, as before. Workspace schema remains **7**.

## 0.15.1 — 2026-11-10

- Fix slow application lists: staleness now reads input versions recorded once per immutable context instead of parsing every frozen context payload per request (200 Drafts on a real 538 MB workspace: 260 ms to 21 ms; about 3.6 s to well under a second on a one-CPU container). Existing contexts are summarized at the first start, in about a second.

No schema version change: the derived `context_inputs` table is created automatically and rebuilt when missing.

## 0.15.0 — 2026-11-10

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

## 0.14.0 — 2026-11-10

- Ship the complete agent workflow skills: setup and onboarding, Inbox review, Shortlist preparation, source management, Career maintenance, application tracking, interview preparation and evidence-based writing, with shared references (operating mandate, employer requirements, vacancy identity, run report, tool reference).
- Serve the shipped skills to connected agents: `skills_list`, `skill_get` and one MCP prompt per skill, plus `GET /api/v1/skills` (the image now includes `skills/` at `OPENINGS_SKILLS`).
- Add an [operator workspace template](examples/operator-workspace/README.md): operating mandate, MCP configuration for six clients from one URL, a launcher that checks the token and sets `OPENINGS_URL`, and a script that fetches the server's skills.
- `setup-openings` checks for a LaTeX compiler on the agent's machine and offers a synthetic trial with the bundled examples.
- Settings → Agent access shows copy-ready MCP configuration for Claude Code, Codex and JSON clients, and lists the available skills.
- Add the [agent-operated job search](docs/user/agent-operated.md) guide: the agent runs and improves the search; the owner applies to prepared Drafts and records Applied.
- Career claims and Prepare Shortlist present the strongest truthful case and never volunteer gaps in application documents.

No database change: workspace schema remains 6.

## 0.13.0 — 2026-11-10

- Add indexes for document revision leaves, activity, notes, job/source tasks, postings and file cascades; application lists on a large workspace drop from ~500 ms to ~20 ms. Indexes are created automatically at startup; schema remains 6.
- Add `exclude_titles` source filters: whole-word terms that skip matching titles before role and location filters, in REST, MCP and the source forms.
- Run synchronous MCP tools in worker threads so a slow tool no longer stalls REST, the dashboard or `/health`.
- Return structured MCP errors (`code`, `status`, `message`, `details`) matching REST; version conflicts include `current_version` on both interfaces.
- Enforce request size limits on the bytes actually received, including chunked bodies without `Content-Length`: 40 MiB for API requests and 16 KiB for sign-in/setup routes.
- Write backup, restore-upload and rollback copies beside the database on the data volume instead of the container's temp directory, and remove copies left by a crash at startup.
- Raise the default `OPENINGS_MAX_RESTORE_MB` from 512 to 2048 and recreate current indexes after a restore.
- Remove the SQLite WAL sidecar files of temporary backup and restore copies with the copies themselves.

Workspace schema remains 6. New indexes are created automatically at startup; existing data and frozen snapshots require no migration.

## 0.12.0 — 2026-11-05

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

## 0.11.0 — 2026-11-04

- Give Inbox and Shortlist distinct actionable queues, excluding all jobs with application history.
- Add direct Shortlist navigation and name application preparation clearly as Preparing.
- Keep closed attempts, documents and deliberate later attempts in Applications; restore known workaround dismissals explicitly.
- Remove fit scoring, its UI, REST/MCP operations, queue work and optional container.
- Align API/MCP contracts, agent guidance, user documentation and populated screenshots.

Schema 5 upgrades automatically to schema 6, preserving jobs, applications, file
ownership and immutable snapshots. Back up before upgrading. Restores require
schema 6; upgrade a copy of an older schema-5 backup before restoring it.


## 0.10.0 — 2026-10-31

- Archive automatic results only after usable posting text is available; resume pending details from collection checkpoints.
- Simplify provider settings to enable/pause and request spacing, with automatic server cooldowns.
- Retrieve descriptions automatically and identify sources that cannot supply them.
- Show shortlist membership and application progress together, with direct removal and Start/Continue actions.
- Enforce one open application per job, explicit closing outcomes and versioned job/application deletion.
- Align job-specific application lookup, field clearing and bulk failure handling across dashboard, REST and MCP.
- Refresh English guides and populated screenshots, including the workspace overview.

This release uses workspace schema 5. APIs and stored source/provider settings use
the current contract; earlier workspace formats require separate conversion.

## 0.9.1 — 2026-10-31

- Show and validate only acquisition options supported by each ATS adapter.
- Align native source, bulk and run controls with discovered configuration schemas.
- Report metadata-only descriptions as unavailable and the collection as partial.
- Explain unavailable public Ashby boards and avoid automatic retries for their 404 responses.
- Identify provider-budget waits clearly in collection progress.

Workspace format remains schema 4. Saved company configurations must match their
current adapter schema; remove options that the adapter does not use.

## 0.9.0 — 2026-10-30

- Resume portal pagination and missing descriptions across bounded collection batches.
- Freeze each collection run with its settings, optional overrides and cumulative progress.
- Schedule multiple daily local times or intervals and configure sources in bulk.
- Align source version checks, run controls and configuration discovery across interfaces.
- Score newly discovered incomplete jobs once their description becomes available.
- Keep location filters from widening a specific geography to unrestricted remote work.
- Simplify collection to JobSpy searches and supported company ATS/feed adapters.
- Refresh Collection controls and English guides with populated product screenshots.

This release uses schema 4. Installation-specific conversion remains outside the application.

## 0.8.0 — 2026-10-30

- Separate career titles, organizations, partial dates, skill tags and ordering.
- Support single dates, periods and Present without requiring descriptions.
- Manage related claims from an entry and distinguish entries by organization.
- Show career dates and content previews on cards; search by organization.
- Identify saved searches by query/location and compact template choices.
- Preserve structured career facts and order in REST, MCP and frozen contexts.

This release uses schema 3. Earlier database formats require separate conversion
outside the application.

## 0.7.0 — 2026-10-30

- Fit long postings into the scorer token budget, retain original text and show shortened input.
- Preserve dismissed jobs across changed URLs and report conflicting source identities.
- Refresh cached ATS descriptions within request caps; filter Greenhouse listings before loading details.
- Require the current document version for approval, including concurrent attachment changes.
- Protect dashboard drafts and refreshed edits; repair bulk selection and explicit closure outcomes.
- Page source cards and load attachment lists when opened.
- Reject redirects that would bypass another provider's request policy.

Document approval now requires `expected_version`. This release uses schema 2;
earlier database formats require separate conversion outside the application.

## 0.6.2 — 2026-10-30

- Display structured compensation ranges and preserve existing salary text.
- Keep scorer dependency layers reusable across version changes.

## 0.6.1 — 2026-10-30

- Remove manual fit assessments from the dashboard, REST and MCP.

## 0.6.0 — 2026-10-30

- Record external fit reviews with scores, reasoning and frozen context through the dashboard, REST and MCP.
- Choose whether automatic scoring includes updated jobs or only new arrivals.
- Use an explicit compact scoring profile without duplicating detailed career evidence.
- Organize awards and publications as career knowledge categories.
- Display exact numeric scores consistently with filters.

## 0.5.4 — 2026-10-30

- Accept MCP requests at the endpoint advertised by the dashboard, with or without a trailing slash.

## 0.5.3 — 2026-10-30

- Exclude partial previews and punctuation-only placeholders from scoring; align completeness filters and counts.
- Read JobCloud template descriptions and preserve complete postings during bounded source refreshes.
- Export large archives as a consistent snapshot with complete JSON and bounded memory use.

## 0.5.2 — 2026-10-30

- Show saved scoring state and keep Save visible while editing; report skipped scoring requests.
- Repair source edits, document refresh, context retry and application history in the dashboard.
- Match new-search defaults across interfaces and link overview counts to filtered results.
- Generalize public documentation and clarify container resource budgets.

## 0.5.1 — 2026-10-29

- Restore join.com company listings and posting details for its current page data.
- Keep source configuration and scheduling responsive with hundreds of saved searches.

## 0.5.0 — 2026-10-29

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
