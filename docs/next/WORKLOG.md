# Current checkpoint

2026-10-29. Production execution awaits the user's start signal. Scope is frozen
for Openings 1.0; no legacy compatibility/importer or planned feature-growth phase.

## Completed review

- Independent UI, interface and scorer review work ran in isolated detached worktrees.
- Original dashboard preview built and inspected in Chromium on desktop/mobile.
- Live MCP/context/binary-file/SQLite backup round trip passed.
- Full-context and near-capacity local model probes resolved the configurable token limit.
- Execution brief, root agent instructions, phases and handoff state prepared.

## Findings and disposition

| ID | Finding | Disposition |
|---|---|---|
| UI-01 | Malformed CSS parentheses swallowed later layout rules. | Fixed; CSS parser and real desktop/mobile grid checks pass. |
| UI-02 | New application inherited an example PDF. | Fixed; new draft has an empty document state; verified in browser. |
| MCP-01 | Bare empty-list tool responses may have no text content. | Use typed object envelopes; exercised in live probe. |
| DATA-01 | PDF/source must belong to immutable content/context revisions. | Proven with exact-byte transfers and backup; production service must preserve it. |
| DATA-02 | Old experiment accepts general instructions as caller input. | New service resolves stored instructions; explicit M2/M4 requirement. |
| SCORE-01 | Default 512-token context truncates a normal posting. | Local preset uses bounded 2048; actual 1920-token request measured without truncation. |
| SCORE-02 | Laya can misjudge language/mandatory qualifications. | Known model limitation; advisory score, no eligibility automation or empirical fallback. |
| CPU-01 | Low-power target CPU has no AVX/AVX2. | CPU-only PyTorch import and required FP32 kernels passed on target; temporary environment removed. |

## Implementation checks still required

Actual dashboard/API binding and browser auth; a real external-agent session
against the finished MCP server; concurrency/large files/restore interruption;
Docker and Linux/x86 whole-stack memory/CPU. These depend on the application
being implemented and are explicit release acceptance, not hidden promises.

Next task after go: M1.1. Read STATE.json and GOAL.md; no new feature discovery
or legacy-refactor pass is needed. Add concise entries here at meaningful
integration checkpoints, not for every edit.

## M1 foundation started

User authorized execution; persistent goal active. Fresh backend/schema/auth and
shared archive DTO/services replaced the old backend/config/tests. REST and
MCP core operations share the service; no old application dependencies remain.
Core HTTP smoke plus seven data-invariant checks pass (dedupe/corrections,
material-content versions, optimistic edits, independent attempts, forget and
exact-byte online backup, owner/CSRF/token boundaries). Frontend, discovery and
career/documents build independently against this shared contract.

Next root work: complete operational backup/restore and integrate peer domains;
then exercise real MCP transport and frontend bindings. M1 is not yet complete.

## Production integration

Fresh archive/auth, career/templates/documents, seven-area React dashboard, ATS/feed collection, persisted worker and optional scorer are integrated. 18 invariant tests and 13 real HTTP/MCP/Tectonic/file/backup checks pass (68 typed tools). Actual browser flows cover profile/evidence/claims/templates, frozen contexts, immutable document revisions, PDF uploads, approval, owner tokens and portable restore; live Ashby preview/run collected 32 jobs. Root fixed scoped backup/restore, full streaming record export, direct-stage funnel counts and cross-job idempotency misuse.

Remaining release checks: actual model-driven agent session using the shipped skill, Docker install/restore and 2 CPU / 4 GiB whole-stack resource measurements, final integrated desktop/mobile inspection. No personal data or deployed installation was modified.

## Release candidate validation

All functional areas are integrated. 31 invariant cases pass; frontend build/audit
and locked core runtime audit are clean. Actual external Codex skill workflow
created tailored CV/letter/answers, compiled and inspected two one-page PDFs,
verified four exact PDF/source transfers, and preserved draft status/review.

Production Docker checks passed 21 cases including 206-record export and restore
on an independent empty installation with exact document bytes and distinct
owner authentication. Final core+scorer images ran in a 2 CPU / 4 GiB / no-swap Linux
ARM VM: 1913 tokens untruncated, core responsive, conservative combined cgroup
peaks ~2.80 GiB, no OOM, local disable releases model child. Overlong inputs fail
without replacing the previous score. API/MCP scoring controls and real ATS
collection also passed. Final UI checks cover desktop/mobile layout, real PDF
preview, Kanban/Sankey counts, nested modal keys, >200-record archives and
versioned deletes. Root corrected merge freshness/cancellation and non-destructive
MCP metadata; known certifi vulnerability fixed in locked dependencies.

Remaining: final GitHub CI builds for both core architectures, task-worktree
cleanup and delivery. No deployed instance, personal data, main branch, release
tag or published image has been changed.

Initialization also rejects an unrelated nonempty database before writing any schema; existing data remains untouched. No legacy conversion is attempted.

Push CI passed both architectures. The parallel PR run exposed an emulation-dependent ARM startup timeout under the half-CPU smoke budget; the final CI matrix uses native Linux ARM and x86 runners, retaining the same runtime limits. Final native checks are pending.
