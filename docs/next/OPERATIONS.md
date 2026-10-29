# Logical operation inventory — Openings 0.5.0

This is the final integration contract for one domain service shared by Dashboard, REST and MCP. The matrix records the intended human location and exact route/tool names; release verification must still exercise those controls. Machine-readable source: [operation-inventory.json](operation-inventory.json). All REST paths below are relative to `/api/v1`. Bootstrap, transport and immutable-record exceptions are explicit below.

Lists return `{items,total}` with `limit` (1–200) and nonnegative `offset`. Dashboard career/document lists request `summary=true`; agents that need all narratives, template source or document content can retain the existing detail-oriented default or fetch one record. Knowledge summaries carry a bounded narrative preview and claim/file counts; claims carry bounded text and evidence title; templates omit TeX/guidance/rules; documents omit content/files and carry revision/file counts. Contexts never return payloads in lists. File lists never return bytes.

Profile `links` is a list of string-valued objects and `metadata` is a finite JSON object. Evidence and claims expose arbitrary finite `metadata`; template `rules` preserves arbitrary finite keys, with `max_bullet_chars` (20–5000), `max_bullets` (1–100), and `max_pages` (1–30) validated when present. Dashboard exposes these variable fields through Advanced JSON. All eight evidence kinds are editable. Nonnullable PATCH fields reject explicit null: omit unchanged fields and clear with empty strings/lists/objects. Versioned edits/deletes preserve optimistic concurrency.

## Archive

| Logical operation | REST | MCP tool | Dashboard location |
|---|---|---|---|
| Read workspace identity and workflow | `GET /workspace` | `workspace_info` | Settings: workspace information |
| Read supported logical operations and transport exceptions | `GET /capabilities` | `capabilities_get` | Settings: capabilities/help |
| Read submitted-attempt funnel and activity for a period<br>since/until select the submitted-attempt cohort; counts are independent of loaded pages. | `GET /overview` | `overview_get` | Overview: period selector and funnel |
| Search/filter/sort paginated job summaries<br>q, triage, company, location, source, remote, job_type, score_min/max, score_state, created_since/until, sort, limit, offset; includes facets. | `GET /jobs` | `jobs_search` | Inbox: search, filters, pagination |
| Read full posting, metadata and source provenance | `GET /jobs/{job_id}` | `job_get` | Inbox: job detail |
| Import a URL, pasted posting or structured job<br>One deduplicated ingestion service; URL fetch is bounded and may contact an external site. | `POST /jobs` | `job_ingest` | Inbox: Add job |
| Correct job fields and metadata<br>expected_version prevents lost updates. | `PATCH /jobs/{job_id}` | `job_update` | Inbox: edit job |
| Save, dismiss or restore one job | `POST /jobs/{job_id}/triage` | `job_triage` | Inbox: Save, Dismiss, Restore |
| Save/dismiss/restore/forget/rescore selected jobs<br>At most 200 versioned items, with per-item results/errors; rescore remains explicit and bounded. | `POST /jobs/bulk` | `jobs_bulk` | Inbox: selection toolbar |
| Merge verified duplicate jobs and retain history<br>Both record versions are required. | `POST /jobs/{job_id}/merge` | `job_merge` | Inbox: merge duplicate |
| Permanently forget job-owned data and identities<br>Future acquisition is new; deletion includes attempts, snapshots and owned files. | `DELETE /jobs/{job_id}` | `job_forget` | Inbox: Forget |
| List job notes | `GET /jobs/{job_id}/notes` | `notes_list` | Inbox: notes |
| Read one note and its version | `GET /notes/{note_id}` | `note_get` | Inbox: note editor |
| Add a job note with optional application association | `POST /jobs/{job_id}/notes` | `note_add` | Inbox/Applications: add note |
| Edit a note with version protection | `PATCH /notes/{note_id}` | `note_update` | Inbox/Applications: edit note |
| Delete one note | `DELETE /notes/{note_id}` | `note_delete` | Inbox/Applications: remove note |

## Collection and scoring

| Logical operation | REST | MCP tool | Dashboard location |
|---|---|---|---|
| Read global collection state and status | `GET /collection` | `collection_get` | Settings/Collection: automatic collection |
| Enable or pause automatic collection globally<br>Preserves per-source settings; manual ingestion remains available. | `PATCH /collection` | `collection_update` | Settings/Collection: automatic collection |
| Read provider capabilities, policies and runtime<br>Runtime, cooldown and capability/version are read-only. | `GET /providers` | `providers_list` | Settings: provider budgets |
| Edit versioned provider HTTP policy<br>Flat policy fields: enabled, min_interval_seconds, max_requests_per_hour/day/run; expected_version required. | `PATCH /providers/{provider_id}` | `providers_update` | Settings: provider budgets |
| List saved searches/company feeds and health | `GET /sources` | `sources_list` | Collection: Saved searches and Companies tabs |
| Read full source configuration | `GET /sources/{source_id}` | `sources_get` | Collection: source editor |
| Preview a source without storing jobs<br>Uses the same per-HTTP budgets/cooldowns as scheduled and manual collection; bounded diagnostic/estimate response. | `POST /sources/preview` | `sources_preview` | Collection: source preview |
| Save a typed search or company/feed source<br>New sources are individually paused; one query/location per JobSpy source, no implicit Cartesian product. | `POST /sources` | `sources_create` | Collection: add saved search/company |
| Edit source configuration, schedule or enabled state | `PATCH /sources/{source_id}` | `sources_update` | Collection: edit/pause source |
| Delete a source while retaining archived jobs | `DELETE /sources/{source_id}` | `sources_delete` | Collection: remove source |
| Queue one immediate collection<br>Honors provider budgets. JobSpy queues one task per selected provider and returns task_ids. | `POST /sources/{source_id}/run` | `sources_run` | Collection: Run now |
| Enable/pause/run/delete selected sources<br>Versioned items and per-item outcomes. | `POST /sources/bulk` | `sources_bulk` | Collection: selection toolbar |
| Read optional scorer configuration and criteria<br>API key is never returned. | `GET /scoring` | `scoring_get` | Settings: scoring |
| Edit disabled/local/remote scorer, rubric and criteria<br>Relevant changes mark existing scores outdated; no implicit full rescore. | `PATCH /scoring` | `scoring_update` | Settings: scoring and criteria |
| Test current/draft scoring endpoint<br>Contacts configured optional scorer; no document generation. | `POST /scoring/test` | `scoring_test` | Settings: test scorer |
| Read exact compact scoring input and omissions | `GET /scoring/context/{job_id}` | `scoring_context` | Inbox: score details |
| Queue bounded selected/outdated rescoring | `POST /scoring/rescore` | `scoring_rescore` | Settings/Inbox: explicit rescore |
| List/filter paginated collection and scoring tasks<br>state, kind, source_id, job_id, limit, offset; source/job labels accompany IDs. | `GET /tasks` | `tasks_list` | Settings: tasks/activity |
| Read task progress, result and diagnostics | `GET /tasks/{task_id}` | `tasks_get` | Settings: task detail |
| Cancel queued/running work | `POST /tasks/{task_id}/cancel` | `tasks_cancel` | Settings: cancel task |
| Explicitly retry failed/cancelled work | `POST /tasks/{task_id}/retry` | `tasks_retry` | Settings: retry task |

## Career and templates

| Logical operation | REST | MCP tool | Dashboard location |
|---|---|---|---|
| Read profile, links, metadata and version | `GET /career/profile` | `career_get_profile` | Career: profile |
| Edit profile/preferences/contact/scoring summary<br>links is a list of string-valued objects; metadata is an arbitrary finite JSON object. expected_version required. | `PATCH /career/profile` | `career_update_profile` | Career: profile and Advanced JSON |
| Search/filter paginated knowledge summaries<br>q searches title/narrative; kind filters evidence type. summary=true omits narrative/metadata and includes 240-character preview plus claim/file counts. Detail-oriented default is preserved. | `GET /career/knowledge` | `knowledge_list` | Career: evidence: list/search |
| Read full knowledge<br>All eight kinds: experience, project, course, education, fact, skill, language, other. Narrative and arbitrary finite metadata are available in detail/edit. | `GET /career/knowledge/{knowledge_id}` | `knowledge_get` | Career: evidence: detail |
| Create knowledge<br>All eight kinds: experience, project, course, education, fact, skill, language, other. Narrative and arbitrary finite metadata are available in detail/edit. | `POST /career/knowledge` | `knowledge_create` | Career: evidence: add |
| Edit knowledge with version protection<br>expected_version required. Omit unchanged fields; clear strings/lists/objects with empty values, never null. | `PATCH /career/knowledge/{knowledge_id}` | `knowledge_update` | Career: evidence: edit and Advanced JSON |
| Delete live knowledge<br>expected_version required. Frozen contexts retain their exact copies; knowledge deletion also removes its live claims/assets. | `DELETE /career/knowledge/{knowledge_id}` | `knowledge_delete` | Career: evidence: remove |
| Search/filter paginated claims summaries<br>q searches claim text/evidence title; knowledge_id and approved filter provenance/review state. summary=true omits metadata and returns a 240-character text preview. Detail-oriented default is preserved. | `GET /career/claims` | `claims_list` | Career: reusable claims: list/search |
| Read full claim<br>Claims retain knowledge_id provenance, approved flag and arbitrary finite metadata; new claims default unapproved. | `GET /career/claims/{claim_id}` | `claims_get` | Career: reusable claims: detail |
| Create claim<br>Claims retain knowledge_id provenance, approved flag and arbitrary finite metadata; new claims default unapproved. | `POST /career/claims` | `claims_create` | Career: reusable claims: add |
| Edit claim with version protection<br>expected_version required. Omit unchanged fields; clear strings/lists/objects with empty values, never null. | `PATCH /career/claims/{claim_id}` | `claims_update` | Career: reusable claims: edit and Advanced JSON |
| Delete live claim<br>expected_version required. Frozen contexts retain their exact copies; knowledge deletion also removes its live claims/assets. | `DELETE /career/claims/{claim_id}` | `claims_delete` | Career: reusable claims: remove |
| Search/filter paginated templates summaries<br>q searches package name/guidance; kind filters resume/cover_letter. summary=true omits TeX/guidance/rules and includes file_count. Detail-oriented default is preserved. | `GET /templates` | `templates_list` | Templates: packages/defaults: list/search |
| Read full template<br>Raw TeX, guidance, arbitrary finite rules and assets are user-owned; no server compilation. First template per kind becomes default. | `GET /templates/{template_id}` | `templates_get` | Templates: packages/defaults: detail |
| Create template<br>Raw TeX, guidance, arbitrary finite rules and assets are user-owned; no server compilation. First template per kind becomes default. | `POST /templates` | `templates_create` | Templates: packages/defaults: add |
| Edit template with version protection<br>expected_version required. Omit unchanged fields; clear strings/lists/objects with empty values, never null. | `PATCH /templates/{template_id}` | `templates_update` | Templates: packages/defaults: edit and Advanced JSON |
| Delete live template<br>expected_version required. Frozen contexts retain their exact copies; knowledge deletion also removes its live claims/assets. | `DELETE /templates/{template_id}` | `templates_delete` | Templates: packages/defaults: remove |
| Read general document writing instructions | `GET /instructions` | `instructions_get` | Templates: general instructions |
| Edit general document writing instructions<br>Template guidance and application notes append separately; prior contexts remain frozen. | `PATCH /instructions` | `instructions_update` | Templates: general instructions |
| Preview JSON/text career import without mutation | `POST /career/import/preview` | `career_preview_import` | Career: import preview |
| Confirm append-only evidence and optional versioned profile import<br>Profile replacement fields require expected_profile_version from preview. | `POST /career/import` | `career_import` | Career: confirm import |

## Applications and documents

| Logical operation | REST | MCP tool | Dashboard location |
|---|---|---|---|
| Search/filter/sort paginated application summaries<br>q, status, outcome, company, sort, limit, offset; stage_counts span all matching records. | `GET /applications` | `applications_list` | Applications: list/Kanban filters |
| Read full attempt, questions/answers and job | `GET /applications/{application_id}` | `application_get` | Applications: attempt detail |
| Create an independent draft attempt<br>Never submits a portal application or generates documents. | `POST /applications` | `application_create` | Inbox/Applications: create attempt |
| Record stage, outcome, questions/answers and application instructions<br>expected_version prevents lost updates; recorded state changes create lifecycle history. | `PATCH /applications/{application_id}` | `application_update` | Applications: progress and questions/answers |
| Delete one attempt and its owned history/files<br>Keeps the archived job and other attempts; removes owned contexts/documents and their transfers. | `DELETE /applications/{application_id}` | `application_delete` | Applications: delete attempt |
| Read immutable lifecycle history | `GET /applications/{application_id}/events` | `application_history` | Applications: history |
| List/filter compact frozen-context metadata<br>application_id, q (job title/company), summary, limit, offset. Full payloads never appear in list rows. | `GET /contexts` | `contexts_list` | Applications: prepared contexts |
| Read full frozen context and signature<br>Also MCP resource openings://contexts/{context_id}; contains exact evidence, approved claims, templates/assets and stored instructions. | `GET /contexts/{context_id}` | `contexts_get` | Applications: context detail |
| Prepare an immutable context for external generation<br>Select template_ids/knowledge_ids/claim_ids and note; optional idempotency_key. Unapproved/out-of-scope claims cannot enter context. | `POST /contexts` | `application_prepare_context` | Applications: prepare context |
| List/filter paginated revision summaries<br>application_id, kind, q (title), review_state, summary, limit, offset. summary=true returns file counts without content/files. | `GET /documents` | `documents_list` | Applications: documents/history |
| Read exact revision content, chain number and files | `GET /documents/{document_id}` | `documents_get` | Applications: revision detail and preview |
| Save content as a new immutable revision<br>previous_id links earlier content and inherits its context only; files are never inherited. Evidence provenance and template limits remain validated. | `POST /documents` | `documents_create` | Applications: add/edit content as a new revision |
| Approve the exact revision content/files<br>expected_review_state detects concurrent review changes. Approval blocks all further file uploads. | `POST /documents/{document_id}/review` | `documents_review` | Applications: Approve revision |
| Delete an entire revision and its files<br>Other revisions remain; deleting a parent clears its child previous_id. | `DELETE /documents/{document_id}` | `documents_delete` | Applications: delete revision |
| List/filter paginated file metadata<br>owner_type with optional owner_id, q (name), media_type, application_id (contexts/documents), summary, limit, offset; no bytes. | `GET /files` | `files_list` | Career/Templates/Applications/Inbox: assets and files |
| Read immutable file metadata and content URL | `GET /files/{file_id}` | `files_get` | Career/Templates/Applications/Inbox: file details |
| Upload exact raw bytes to a mutable owner<br>MCP reserves a scoped HTTP PUT grant, then the caller sends raw bytes; UI performs the same transfer. Size/SHA-256/PDF checks apply; no base64 tool input. | `POST /files/uploads`<br>`PUT /transfers` | `files_reserve_upload` | Career/Templates/Applications/Inbox: upload file |
| Download/preview exact file bytes<br>MCP returns a scoped HTTP GET grant; UI may use its authenticated content URL. Context copies preserve exact blob bytes. | `GET /files/{file_id}/content`<br>`POST /files/{file_id}/download`<br>`GET /transfers` | `files_reserve_download` | Career/Templates/Applications/Inbox: preview/download |
| Delete a live knowledge/template/job asset<br>Context/document file associations are immutable; delete a whole document revision or create another one. | `DELETE /files/{file_id}` | `files_delete` | Career/Templates/Inbox: remove asset |

## Workspace access and portability

| Logical operation | REST | MCP tool | Dashboard location |
|---|---|---|---|
| Download portable JSON records without file bytes<br>MCP obtains scoped HTTP download. Secrets are omitted; use SQLite backup for exact documents/assets. | `GET /export` | `workspace_export` | Settings: export records |
| Download a consistent SQLite backup including bytes<br>MCP obtains a short-lived scoped HTTP grant; bytes stay outside the tool response. | `GET /backup` | `workspace_backup` | Settings: download backup |
| Replace workspace data from a SQLite backup<br>MCP obtains a scoped raw HTTP upload grant. Validated restore preserves installation authentication and recent provider HTTP windows/later cooldowns; saved policies restore. No arbitrary SQL endpoint. | `POST /backup/restore` | `workspace_restore_upload` | Settings: restore backup |
| List owner API token metadata<br>Token secrets are not returned after creation. | `GET /tokens` | `tokens_list` | Settings: agent tokens |
| Create a named owner API token<br>Secret is returned once and has owner-level authority. | `POST /tokens` | `token_create` | Settings: create agent token |
| Revoke an owner API token<br>May revoke the caller token; subsequent requests require another valid credential. | `DELETE /tokens/{token_id}` | `token_revoke` | Settings: revoke agent token |
| Change owner password and rotate owner sessions<br>Retains API tokens; cookie caller must log in again. | `POST /auth/password` | `owner_password_update` | Settings: change password |

## Deliberate exceptions

| Concern | Behavior and reason |
|---|---|
| `auth.bootstrap_session` | Credential bootstrap and browser session transport precede authenticated domain tools; MCP uses bearer authentication. |
| `health.deployment` | Deployment liveness and service installation/startup are transport or operator concerns, not domain CRUD. |
| `mcp.transport` | MCP initialization/discovery/session/resource transport is protocol infrastructure; no simulated dashboard button or MCP wrapper is required. |
| `reference.examples` | Shipped static reference files are convenience downloads, not private workspace records; agents may use REST or repository examples. |
| `immutable.records` | Frozen contexts and lifecycle history have no arbitrary PATCH/DELETE. Document content changes create revisions; approved revisions stay immutable. Context deletion is scoped to deleting the owning application/job. |
| `binary.transfers` | Logical file actions are equivalent across interfaces; raw HTTP bytes use scoped grants rather than base64 MCP payloads. Backup/export use their own scoped operational grants. |

No generic database write, internal document generation, server TeX compilation, portal submission, email/calendar integration, legacy importer or invented history-edit operation is part of this contract. Optional scoring remains advisory and provenance/omissions remain visible. Provider cooldown/runtime and context signatures are read-only domain state.

Structured content validation checks supported evidence/claim references, bullet limits and question answer limits. It does not establish factual truth or verify the rendered PDF page count; external agents compile and inspect those artifacts.
