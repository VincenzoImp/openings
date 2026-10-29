# Product scope

Frozen release scope, 2026-10-29: **Openings 1.0**. Features are planned, not
production-implemented. This is a fresh codebase on an Openings branch, with no
legacy compatibility or importer. All shipped material is in English.

## Features by layer

| Layer | First-release responsibility |
|---|---|
| SQLite | Profile, detailed career knowledge, reusable claims, templates/assets, editable instructions, sources/schedules, jobs/postings, scores, application attempts/history and document bytes. |
| Application service | Validated ingestion, deduplication, corrections, lifecycle, context snapshots, document versions, exports and backup. One implementation for all interfaces. |
| REST | Authenticated, paginated operations and file transfer for scripts; actual contract documented with OpenAPI. No raw SQL. |
| MCP | The same capabilities for an external agent, including knowledge/template/prompt edits, job management, application context and document/file submission. Self-describing tools/resources. |
| Dashboard | Dossier-inspired Inbox/table/detail, Add job, Companies, Career, Templates, Applications Kanban/list, document preview/history, Sankey funnel and Settings/activity. Manual work calls REST. |
| Worker | Configured collection, normalization/storage, optional scoring and deliberate rescoring; bounded work, pause and useful errors. |
| Optional scorer | One bundled local model or a compatible endpoint elsewhere, with URL/model/credential settings. Independent of the core. |
| External agent | Read stored knowledge/rules/templates, write CV/letter/form answers, compile externally and save drafts/files using MCP or REST. |
| Optional skill | Teach the workflow and state rules. It supplies guidance, not missing product capabilities. |

## Features by delivery step

| Step | Usable increment |
|---|---|
| M1: archive | Fresh scaffold; SQLite/files/backup; URL/text/structured ingestion; text search/filters; triage, notes and application states; working REST/MCP; English UI shell and initial Kanban. |
| M2: career workspace | Profile and detailed experiences/projects/courses, evidence/claims, multiple LaTeX template packages/defaults/assets, editable general/template/application instructions. |
| M3: collection and scoring | Watched companies, verified ATS/feed clients, schedules/run-now/pause, optional local/remote AI scoring, editable rubric, outdated indicators and selected/batch rescoring. |
| M4: agent workflow and reporting | Frozen application context, structured answers, PDF/source uploads and revisions, review/download, a working agent skill, and Sankey funnel from recorded application history. |
| M5: release | Docker setup, restore on another host, resource measurements, practical walkthroughs and concise English release docs. |

## Useful switches

| Control | Behavior |
|---|---|
| Automatic collection | Off until sources are configured. Each source has enable/pause, schedule and Run now. |
| AI scoring | Off until configured. Select bundled local preset or remote URL/model. Off preserves jobs/results and stops new inference. |
| Periodic rescoring | Off. Explicit selected/outdated rescoring remains available when scoring is configured. |
| Search | Text search/filters are included and need no model. Semantic search is outside this release; no placeholder switch or embedding dependency. |

One model is loaded once locally. The local working preset is Laya English,
chosen for lower measured RAM/latency than jevos, not yet production-validated.
Users with stronger hardware may select another compatible hosted model;
changing a model name selects what that endpoint serves, not arbitrary core downloads.

## Product boundary

Document generation and PDF compilation run in the user's external agent.
The app manages knowledge, templates, instructions, content, PDF/source versions,
preview, review and tracking. No ChatGPT/Claude account is embedded in the app.

Gmail, Calendar, sending/portal automation, built-in AI chat, automatic document
generation and native generative-provider integrations are outside this plan.
Server-side TeX compilation is outside this plan; external compilation is the
confirmed choice. Kanban and Sankey are included.

## Dashboard structure

| Area | Main task |
|---|---|
| Overview | Submitted-attempt counts, Sankey journey, items needing attention and recent activity. |
| Inbox | Search/filter offers, full posting, URL/text import, save/dismiss/restore, notes and score freshness. |
| Applications | Kanban/list, progress/outcomes, PDF/source/answer versions, review, upload and download. |
| Companies | Supported ATS/feed setup, preview, enable/pause/schedule and collection health. |
| Career | Profile/preferences, detailed evidence, reusable claims and supporting files. |
| Templates | Packages/assets/defaults, general writing instructions and per-template append. |
| Settings | Local/remote/off scoring, rubric, deliberate rescoring, access tokens, backup/restore and diagnostics. |

See the [interactive design preview](preview/index.html): navigation and manual
interactions with synthetic browser data, not a production backend. No later
feature phase is promised; M1–M5 deliver the complete agreed release.
