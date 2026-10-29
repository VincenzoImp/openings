# Delivery plan

Current scope: [PRODUCT.md](PRODUCT.md). Next task **M1.1**. Production implementation is authorized and in progress. Update this file and STATE.json after each usable increment with
what works, a concise check/result, remaining issues and the exact next task.

## R0: completed research

Repository comparison, SQLite/context/API-MCP prototypes, external LaTeX
compilation and two CPU decision probes are done. Scope reviews R0.7/R0.8 fixed
triage/deletion, rescoring, external-only document generation, English release
material, Kanban/Sankey and optional local/remote scoring. Historical Codex and
renderer experiments are evidence, not production dependencies.

| ID | Result |
|---|---|
| R0.1 | Local repository/workflow comparison and pinned revisions. |
| R0.2 | Initial requirements; later scope decisions are consolidated in PRODUCT.md. |
| R0.3 | SQLite/frozen-context/REST-MCP/backup prototype: 12 tests passed. |
| R0.4 | Synthetic external LaTeX compilation, including cached offline execution. |
| R0.5 | CPU model probes, Codex handshake and real local scoring HTTP smoke. |
| R0.6 | Gate still open: target-device resources and real-job quality/context. |
| R0.7 | Triage, forget, ingestion and rescoring behavior review. |
| R0.8 | Agent-only documents, external compilation, English release, feature map and skill draft. |
| R0.9 | Final frozen scope, browser preview, live MCP/file proof, full-context and non-AVX runtime checks, resumable execution brief. |

Local scoring still needs real-job quality/context and target-device resource
verification. Do not hide that gate by shipping a different empirical score.

## M1: fresh foundation and archive

- **M1.1 next:** replace the branch's production scaffold with fresh backend/UI
  code, the smallest relational/typed-JSON initial schema and a schema version. Keep
  old projects available separately; do not build on experimental SQL blindly.
- **M1.2:** SQLite files/hashes, consistent backup/restore and bounded transfers.
- **M1.3:** shared URL/text/structured ingestion, duplicate resolution, corrections,
  text search/filters, notes, triage, application attempts/history and forget.
- **M1.4:** authenticated REST and self-describing typed MCP using the same service.
- **M1.5:** English Dossier-inspired shell, Inbox/detail/manual forms, Applications
  list and initial Kanban, including loading/empty/error states and keyboard paths.

**Show it working:** fresh install → add job from UI and MCP → find same job
through REST → update state/note → dismiss/re-import/restore → forget/re-import
→ restore a backup with matching attachment bytes. Check dedupe, concurrency
and destructive-data boundaries with a few automated invariant tests.

## M2: career workspace

- **M2.1:** profile, detailed experiences/projects/courses/facts, evidence files
  and approved/draft reusable claims; manual editing and previewed text/JSON import.
- **M2.2:** multiple LaTeX packages/assets/defaults, general document instructions,
  template append, application note and typed content limits; UI/REST/MCP parity.
- **M2.3:** immutable context/revision references and useful synthetic examples.

**Show it working:** enter/import a synthetic career, revise knowledge and
instructions through two interfaces, retrieve a template package with its assets.
Previously frozen material remains readable. No TeX compiler or AI key required.

## M3: collection and optional scoring

- **M3.1:** Companies URL → supported board → preview → enable; filters, schedule,
  pause, Run now, last result/errors. Write fresh narrow ATS/feed clients using
  verified protocols. Start Greenhouse/Lever/Ashby; only claim checked adapters.
- **M3.2:** one persisted bounded collection/scoring queue, checkpoints, cancellation
  and recovery. A failed source/scorer does not block successful acquisition.
- **M3.3:** scoring off/local/remote settings, explicit served model, connection
  probe and a minimal System One HTTP adapter. Optional local model image/process;
  one pinned checkpoint, one inference request at a time, two threads maximum.
- **M3.4:** editable rubric, result/input revisions, Outdated indicators, selected/
  outdated rescoring and optional capped periodic rescoring. Edits enqueue nothing.
- **M3.5:** assess the lightweight Laya baseline on complete job/profile contexts
  and ordinal fit. Measure startup/steady memory and CPU on intended hardware.

**Show it working:** collect from a supported real public board, repeat without
new duplicates, interrupt/restart, switch scoring off, use a scorer on another
host, edit the profile without mass work, and explicitly rescore a small batch.
Publish actual limitations. A local preset only becomes supported after it meets
quality/context and 2-core/4-GiB whole-stack checks. Core/remote mode is tested
independently; weights fitting disk alone is no resource proof.

## M4: external-agent documents and reporting

- **M4.1:** prepare frozen application context with selected evidence, templates,
  rules, questions and file references; expose through REST/MCP.
- **M4.2:** submit structured CV/letter/answers and externally compiled PDF/source
  files; validate references/limits and preserve partial work. Manual uploads work.
- **M4.3:** versioned content/files, manual edits, previews, review and exact-byte
  export. Distinguish changed source from an older compiled PDF.
- **M4.4:** validate the supplied skill against the actual server; concise agent
  setup docs. No embedded login, generative endpoint or agent runner.
- **M4.5:** finish Kanban and add a Sankey funnel from recorded stage/outcome
  history, with period filter, counts and accessible table/text equivalent.

**Show it working:** a real external agent reads a synthetic profile/template,
prepares CV/letter/answers, compiles externally, uploads files and returns a
reviewable draft. A human edits/reviews/downloads it and records progress. Verify
reapplication, unknown imported history and attempt counts in Kanban/Sankey.

## M5: install, migrate and release

- **M5.1:** published pinned amd64/arm64 core image, optional scorer, simple Docker
  setup and guided profile/source/MCP configuration. Start with scoring disabled.
- **M5.2:** validate fresh empty/synthetic initialization and portable backup/restore;
  no legacy importer, old-schema migration or compatibility code.
- **M5.3:** fresh-host backup restore, upgrade smoke, responsive/accessibility
  checks and resource measurements with scoring on/off/remote.
- **M5.4:** concise English README/setup/API-MCP/agent docs and release notes;
  synthetic examples only. Keep invariant checks runnable in CI.

## Verification style

Prefer practical walkthroughs to a large test suite. No coverage percentage,
test-per-function rule or snapshots of implementation details. Keep a few checks
for deduplication/state preservation, stale/late inference, permanent forget,
frozen contexts and SQLite initialization/backup. Run relevant smoke checks after
changes; broaden only when failures or unresolved risks justify it.

Walkthrough cases: manual/ATS duplicate; incomplete URL; dismissed re-import;
forget during work; relevant versus cosmetic edits; explicit rescore scope;
late result; source/model failure; external document submission; independent
reapplication; context overflow; recorded-history funnel; backup restore.
These are planned acceptance cases, not claims of an implemented product.

## Outside this plan

Gmail/Calendar, sending/portal automation, built-in AI chat, automatic document
generation, embedded agent/provider login, server-side TeX compilation and a
semantic-search/embedding stack and legacy importer/compatibility. This is a
complete frozen release scope, not an MVP followed by planned feature additions.

## Working rules

Fresh codebase on this branch; old implementations stay as separate references.
Reuse knowledge of protocols/workflows, not the old configuration/scoring engine.
No Dossier code copied into the MIT project. A single local planning/feasibility checkpoint preserves this review. Production
implementation and publication await their authorized execution. Keep docs and state current.

## Orchestration and checkpoints

After the user's start signal, activate the prepared GOAL.md objective. First
stabilize M1's schema/DTO/service contracts, then run independent work in parallel:

| Owner | Isolated worktree responsibility |
|---|---|
| Root orchestrator | Shared contracts/schema, integration, scope, defect list and final practical checks. |
| Frontend agent | Seven dashboard areas, forms, list/Kanban/Sankey and actual REST binding. |
| Collection/scoring agent | Verified sources, scheduler/queue and optional local/remote scoring. |
| Career/agent agent | Knowledge/templates/instructions, frozen context, MCP/files and document versions. |

Use task branches based on the same integrated checkpoint. Shared schema,
lockfiles and API contracts have one owner. Integrate vertical slices before
branches drift. Prefer roughly 4–6 coherent implementation commits; fixes may
be folded into the relevant slice. PRs/issues are optional, not prerequisite work.

At meaningful integration points, run the current workflow, record defects and
fix them, review resource/scope/time drift, update state and continue. Do not run
a long pipeline after every small edit or continue indefinitely without checking.
Remove temporary worktrees only after their useful work is integrated.
