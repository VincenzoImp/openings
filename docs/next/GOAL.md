# Openings 1.0 execution brief

## Start and resume

This is a prepared execution brief. Production implementation awaits the user's
explicit start signal. When that signal arrives, create the requested persistent
goal using this objective and the actual checkout path; reuse an existing active
goal rather than creating another. No token budget was requested.

Work on `codex/openings-next`. Read `README.md`, `STATE.json`, `PRODUCT.md`,
`DESIGN.md` and `PLAN.md` in this directory. STATE.json is the current checkpoint;
PLAN.md defines tasks and acceptance. After a restart/compaction, inspect state
and Git/worktree status and continue the recorded next task. Do not restart the
research or infer completion from a screenshot, prototype or passing unit suite.

## Objective

Deliver a complete, release-ready **Openings 1.0** as a fresh implementation:
an English self-hosted job-search workspace, portable SQLite including files,
shared dashboard/REST/MCP operations, career knowledge/templates/instructions,
manual and scheduled company-feed ingestion, optional local/remote AI scoring,
deliberate rescoring, application tracking, external-agent document preparation
and uploads, list/Kanban/Sankey views, Docker setup and consistent backup/restore.

The frozen feature set is in PRODUCT.md; complete it rather than deferring core
features into an unspecified later release. No legacy importer/schema compatibility,
empirical scoring, internal AI generation/chat/login, server TeX, email/calendar,
portal submission or semantic-search/embedding stack. External agents compile
PDFs and upload PDF plus sources; guidance and knowledge remain stored in SQLite.
Use old projects and experiments as references, not the production scaffold.

## Execution

Begin **M1.1**: fresh scaffold, minimal initial SQLite schema/version and shared
DTO/service contracts. Agree shared contracts before parallel implementation.
The root agent owns integration, schema/API decisions, scope and final checks.
Delegate independent frontend, source/scoring and career/MCP/document tasks to
focused agents in separate task branches/worktrees. Avoid simultaneous ownership
of schema, lockfiles and shared contracts. Merge useful vertical slices promptly.

Use a few meaningful commits per coherent increment, not one per edit. Issues/PRs
are optional coordination aids. Do not create administrative work that delays a
working flow. Keep temporary worktrees/branches free of unintegrated changes
before removing them.

After meaningful batches: exercise the implemented flow, note defects, fix them,
review scope/time/resource drift, and update PLAN.md/STATE.json with the next task.
Use a small defect list with concrete reproduction and status. Routine corrections
do not need new user approval; request missing information only when necessary.

## Evidence and completion

Prefer real UI/REST/MCP/external-agent walkthroughs plus a few data-invariant
tests. No coverage target or exhaustive test-per-function work. Check dedupe,
state preservation, forget/late results, frozen context, exact file revisions
and online backup/restore. Test desktop/mobile and inspect actual screens.

Scoring is advisory. The measured Laya English preset uses one question,
`max_len=2048`, two threads and one checkpoint; it still makes known language/
qualification mistakes. Preserve off/remote modes and detect truncation. Measure
the actual core plus scorer under 2 CPU / 4 GiB before claiming target support.

Completion requires every agreed feature working through its intended surfaces,
a practical external-agent PDF/source round trip, fresh Docker installation,
portable restore, resource evidence, concise English docs and a clean releasable
branch. Do not mark the goal complete while required work remains. Record actual
limitations honestly; production tests cannot be replaced by preflight probes.
