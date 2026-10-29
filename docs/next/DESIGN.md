# Design and workflow

Scope: [PRODUCT.md](PRODUCT.md). Build fresh Python/FastAPI, SQLite and React/Vite
code on `codex/openings-next`; old repositories are read-only references.
All shipped material is English; user data keeps its chosen language. Use only
synthetic public fixtures.

## Shared services

Dashboard calls REST. REST and MCP validate typed inputs and invoke the same
operations: jobs/search/triage, profile/evidence/claims, templates/assets/prompts,
sources/schedules, scoring/rescoring, application history, context preparation,
files/revisions, export and backup/restore. Include manual and batch operations.
MCP describes actual tools/resources; REST publishes OpenAPI. Lists are paginated;
files are fetched separately. No live database-file writes or SQL API.

Use a modular monolith, one bounded worker and optional scoring service.
SQLite owns persistent data; no Redis, vector database, agent SDK or workflow
platform is needed. Authentication/session/API-token boundaries apply equally
to REST and MCP. The skill is optional workflow guidance, not business logic.

## Ingestion and companies

Dashboard Add job, REST, MCP and collectors invoke one ingestion operation.
Accept URL, pasted posting text or structured fields. URL import tries supported
ATS/static extraction; on failure retain an incomplete entry with a paste-text
action. Collection/storage require no generative model. Score only complete jobs.

Resolve stable ATS requisition IDs and normalized URLs. Remove known tracking
parameters while preserving meaningful IDs. Similar titles/companies alone do
not justify merging. A duplicate returns the existing identity and preserves
triage, notes, corrections, applications and files. Cross-source identity must
be verified or explicitly merged.

Keep source snapshots separate from user corrections. Refreshes preserve reviewed
edits; unchanged effective content triggers no inference. New/materially changed,
complete, non-dismissed jobs are scored if enabled. Scoring failure never rolls
back acquisition. Source failure neither erases jobs nor proves they are closed.

Companies: add → paste career/ATS URL → identify supported board → preview →
save/enable. Allow correcting the board ID, role/location filters, schedule,
pause and Run now. Show last success/errors. Implement fresh narrow clients,
starting with Greenhouse, Lever and Ashby, using verified protocols and old
code as references. Unsupported sites use explicit setup or manual import.

## State and deletion

| Object | Values | Meaning |
|---|---|---|
| Job triage | `inbox`, `saved`, `dismissed` | To review, kept for action, set aside. |
| Application attempt | `draft`, `applied`, `interview`, `offer`, `closed` | Progress of an attempt; closed optionally records accepted/rejected/not_pursued and a note. |
| Source availability | `open`, `closed`, `unknown` | Source facts, independent of user triage. |

Dismissal is reversible, survives collection/import and excludes automatic
scoring. A duplicate dismissed job stays dismissed; restore explicitly returns
it to Inbox. Preparing an application saves its job; restore dismissed jobs first.
Dismissal does not claim that a sent application was withdrawn. Uploading a CV
never marks an attempt applied. Allow corrections without requiring every stage.

Forget permanently removes the job, aliases, assessments, applications, notes,
documents and job-owned run/idempotency payloads. Preview the impact. Remove
unreferenced bytes, preserve shared profile/template assets. Retire in-flight
work so late results cannot resurrect a deleted identity. Keep no suppression
tombstone: later acquisition can create a new job. Independent backups remain
independent. SQLite reuses freed pages; physical compaction is explicit.

There is no legacy importer, old-schema migration or compatibility layer.

## Career, templates and external agents

Separate detailed evidence, reusable approved/draft claims, and wording used
for an application. Agents may select claims or write new bullets from narrative
evidence. New facts remain profile proposals until reviewed. Evidence references
establish provenance, not truth.

Users manage multiple LaTeX packages/assets/defaults. Instructions combine an
editable general layer, optional template append and application note. Typed
constraints may cover bullet/answer lengths, page targets and required sections.
Store arbitrary user TeX for the agent; do not require conversion to a proprietary
slot format in the initial release.

Context preparation performs no inference. Freeze the job, selected evidence/
claims, template/assets, instructions and form questions under a context ID.
Use hashes/revision references for large files. An agent fetches this context,
writes CV/letter/answers, compiles externally and submits content plus PDF/source
files. Profile/template edits affect new contexts, not old applications.
Resolve stored general/template/application instructions in the service; callers
do not have to rediscover or resend those strings for every preparation request.

Validate known IDs, applicable typed limits and file associations. Manual file
upload remains supported; missing evidence must not be shown as verified.
Uploads/requests are idempotent; changes create versions. Preserve successful
partial results. Edited source does not update an older PDF: show the new draft
separately from previous compiled bytes. Approval/export refer to exact artifacts.
Reapplications keep independent attempts and previous sent files.
Bind file bytes to an immutable content revision and its context. MCP can reserve
short-lived scoped HTTP transfers, keeping PDFs out of tool text and avoiding
exposure of the client's long-lived credential. Return object envelopes for
lists, including empty lists; the live SDK probe exposed this requirement.

Dashboard supports manual knowledge/template/prompt/document edits, upload,
preview, history and download. External agents provide generation and compilation.
MCP must be sufficient without a skill; the skill discovers advertised operations
and teaches context → preparation → submission → review. No internal generation
button, background auto-drafts, embedded login or chat is required.

## Optional scoring and rescoring

Use one indicative AI fit score and editable rubric with career facts, preferences
and job context. No empirical/keyword weights or fallback. A failed/incomplete/
disabled assessment is unscored, not zero. Decision models do not write reasons.

Choose disabled, bundled local service or remote compatible endpoint. Keep model
dependencies out of the core image. One local checkpoint, one request at a time,
at most two inference threads. Remote models need not fit local hardware.
Protocol/configuration boundaries are in [AI.md](AI.md).
The measured local preset uses one fit question and `max_len=2048`; this covers
the complete contexts tested so far. Inspect reported truncation and do not
present a chopped context as fully evaluated. Known model mistakes remain visible
limitations of an advisory score, not automatic eligibility decisions.

Store effective job/scoring-profile revisions, rubric, actual model/runtime and
context-builder version. Hash effective inputs to deduplicate work. Contact/
template/no-op edits do not invalidate scores. Test complete postings, preserve
supplied context/omissions and avoid silent loss of essential requirements.

| Event | Default behavior |
|---|---|
| New/materially changed complete job, scoring enabled | Queue once unless dismissed. |
| Feed timestamp-only change | No inference. |
| Relevant profile/preferences/rubric/endpoint/model edit | Prior scores become Outdated by revision comparison; enqueue nothing. |
| Explicit Update scores | Preview scope/count; process selected/outdated jobs in bounded batches. |
| Periodic rescoring enabled | Process outdated jobs on its capped schedule; off initially. |
| Scoring disabled/unavailable | Collection/manual use continue; preserve old results. |

Keep the old score/date until replacement succeeds. Freeze claimed work; coalesce
superseded queued requests before execution. Edits can make running results
outdated; late results cannot replace a newer current score. Disabling local
scoring stops new work and releases its model after active work is settled.
Endpoint changes do not silently download models into the core. Rescoring never
creates or regenerates application documents.

## Dashboard and funnel

Reference Dossier's warm surfaces, editorial headings, restrained controls and
generous previews. Build original components with keyboard access, contrast,
responsive layout and light/dark modes. Establish the shell in M1.

List/Kanban views share application state operations. Record timestamped stages
and outcomes, allowing corrections. Sankey shows where submitted attempts went
or stopped, with a period filter, counts and a text/table equivalent. Count
attempts, not jobs. Unknown imported history stays unknown; do not invent prior
stages or treat generated documents as sent applications. No calendar/email UI.

## Persistence and installation

Use relational ownership/lifecycle tables and validated JSON for variable data/
snapshots. Keep the schema small; no generic entity/attribute or policy framework.
Enable SQLite foreign keys, WAL, short transactions, busy timeout and optimistic
versions. Deduplicate attachment BLOBs by hash. Back up with SQLite's online API,
not a blind copy of a live WAL database. Models/caches are replaceable; connection
authentication is installation-specific. No personal data/secrets in Git/images.

Docker serves the core without model downloads, TeX, a GPU or runtime Node.
Optional local scoring runs separately and loads only when enabled. An external
scorer requires no local inference service. Verify the whole resource envelope,
including startup. Use a few invariant tests and real UI/REST/MCP/agent walks.
