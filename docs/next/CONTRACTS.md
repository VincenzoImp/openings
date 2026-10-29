# Final integration contracts (0.5.0)

User authorized this integration and autonomous execution. All shipped content is English.
The user wants logical operation parity across dashboard/REST/MCP, without forcing
transport/bootstrap/deployment details into meaningless UI or tools. One shared domain
implementation; no generic SQL endpoint, API-console substitute or new workflow framework.

## Ownership

Root: schema/models/workspace/api/app/auth/operations/fetching, dependencies/locks,
versions, integration and final checks. Collection agent: discovery.py, worker.py,
backend/openings/collectors/, vendor code/attribution, collection tests. Frontend agent:
frontend/ only. Career/documents agent: career.py, documents.py, corresponding tests,
OPERATIONS.md and operation inventory. Do not edit another owner's files concurrently.

## Root archive APIs

Existing URLs remain. Lists become compact; detail GET/tool retains full content.
`Job` list has `complete` and `posting_preview`; do not rely on full `posting` in rows.
Job detail includes `postings` provenance. `Job` list retains IDs, metadata, versions,
triage/availability, source/location/remote/job_type/salary/date, score/outdated.

- GET /jobs: q,triage,company,location,source,remote,job_type,score_min,score_max,
  score_state (all/current/outdated/unscored),created_since,created_until,sort,limit,offset.
  Returns items,total and small facets (companies,locations,sources,job_types).
- POST /jobs/bulk: {action: saved|dismissed|inbox|forget|rescore,
  items:[{id,expected_version}]}, max200. Per-item results/errors; no lost updates.
- GET/PATCH /notes/{id}; PATCH {body,expected_version}; DELETE remains.
- GET /applications: q,status,outcome,company,sort,limit,offset. Returns
  items,total,stage_counts across matching records, independent of loaded page.
  List has compact job, no full questions/answers/context/document bytes.
- DELETE /applications/{id}: delete one attempt and its owned history/files; keep job.
- GET /overview: since,until applies to submitted-attempt cohort; default all time.
- GET /export (records) and /backup (SQLite): authenticated transfers.
- POST /auth/password {password}: change owner password, retain API tokens,
  rotate owner sessions. Cookie caller must login again. Setup/login are bootstrap.
- /tokens GET/POST/DELETE also get MCP administration tools.

## Collection contract

Continue source CRUD /sources and source_* tools. Company and search sources are
one service and queue. `Source.kind=jobspy` uses config:
`{query,location,country,providers:[linkedin|indeed|glassdoor],results_wanted:20,
 hours_old:72,is_remote:false,job_type:null,fetch_description:true}`.
One explicit query/location per saved source; duplicate for variants. No implicit
keyword/location Cartesian product. Google is reported unsupported, not empty.
Direct company kinds plus RSS remain; add verified useful old ATS/regional sources
with narrow clients. Typed provider configuration, no arbitrary runtime code imports.

- GET/PATCH /collection: {enabled,version,...counts/status}; PATCH expected_version.
  Global automatic pause preserves individual settings and prevents scheduled work.
  Explicit manual import remains available. Run once still honors network budgets.
- GET /providers returns items/total including capability,policy,runtime/version.
- PATCH /providers/{id}: {expected_version, ...editable policy fields}.
  Policy includes enabled,min_interval_seconds,max_requests_per_hour,
  max_requests_per_day,max_requests_per_run. Runtime/cooldown is read-only.
- POST /sources/bulk {action:enable|pause|run|delete,items:[{id,expected_version}]}.
- /sources/preview must use provider budgets; return a request estimate and useful
  per-provider diagnostics. No jobs saved by preview. Keep previews bounded.
- GET /tasks: state,kind,source_id,job_id,limit,offset; add readable source/job labels.
  GET /tasks/{id}, POST cancel/retry all also exposed by MCP.
- Source responses include next_run_at and useful last outcome/counts.
- Scoring criteria array is editable in all interfaces; per-job scoring/context and
  explicit bounded selected/outdated rescoring remain.

Provider state uses the new `providers(id,policy JSON,runtime JSON,version,updated_at)`
table. Store global collection switch in settings key `collection` (default enabled
for configured sources; new sources individually paused). Reserve provider HTTP
attempts atomically, share limits across searches/preview/manual runs, honor
Retry-After date/seconds, persist cooldown, avoid long shared-worker sleep.
JobSpy1.4.1 must use a small explicit version-pinned per-instance transport hook;
vendor upstream MIT code with attribution/patch notes if necessary. No runtime
monkeypatch of global HTTP clients. Root adds dependency pins requested by agent.
One inference at a time; collection/scheduler must progress independently of scoring.

## Career/documents parity

Keep current URLs/tool schemas unless a correction is needed. Profile metadata/links,
knowledge/claim metadata, all knowledge kinds, template rules/assets/defaults,
editable instructions, contexts, document revisions/review/content, evidence/files
and applicable filters must be operable by all interfaces. Frozen contexts and approved
revisions stay immutable. Files use scoped HTTP transfers from MCP; the same
human action uses upload/download controls. No binary base64 in tool calls.
Lists should offer summaries/page filters rather than all full narratives/TeX/contexts.
Define `summary=true` list query where necessary to preserve detail-oriented callers.

## Dashboard

Rename Companies navigation to Collection; Saved searches / Companies tabs.
Career/Settings use actual available desktop width with meaningful groups;
mobile remains one column. Protect unsaved forms on navigation and refetch.
Target refreshes; use visible pagination/server filters and search debounce.
Inbox: filters above, selection+Save/Dismiss/Restore/Forget/Rescore bulk actions.
Applications: search/stage/outcome/sort, true global counts, URL-preserved object/filter
state, one-attempt delete with clear impact. Overview has a real period selector.
Settings: Collection control, scoring/criteria, provider budgets, agent tokens,
password/backup/export, task read/cancel/retry and diagnostics. Advanced JSON fields
may expose variable metadata without cluttering normal forms.

## Boundaries and acceptance

No internal generation/chat/TeX, browser crawler by default, paid credentials,
semantic/OpenSearch, Gmail/Calendar, portal submission or legacy importer.
31 prior checks are a baseline, not proof of new behavior. Verify reviewed failures,
logical operation matrix, guarded real portal batch, simulated429/restart/cooldown,
collection during slow scoring, practical desktop/mobile/large archive/dirty forms,
exact file/context/backup and combined Linux2CPU/4GiB plus native amd64/arm64 CI.
