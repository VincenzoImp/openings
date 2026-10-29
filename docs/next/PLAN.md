# Final integration plan — Openings 0.5.0

User approved implementation. Entry: README.md, GOAL.md, STATE.json and CONTRACTS.md.
Previous M1–M5 delivery is preserved in Git history; its review found missing broad
search and UX/parity defects. This final pass implements the reviewed corrections.

| Phase | Tasks | Completion evidence |
|---|---|---|
| F0 Contracts | Agree shared DTOs, ownership, schema, operation inventory and 0.5.0 version. | CONTRACTS and OPERATIONS describe logical parity and transport exceptions. |
| F1 Acquisition | JobSpy 1.4.1, explicit saved searches plus company/feed sources; real per-request provider budgets/cooldowns; global pause; source batch/tasks/diagnostics; fair collection/inference. | Guarded live portals, synthetic 429/restart, pause/resume, dedupe and one failing source. |
| F2 Shared services | Nullable/number validation, changed-job score successor, RSS/location and URL import quality; compact queries; complete shared CRUD/bulk/export/access parity. | Few invariant tests and same UI/REST/MCP workflows. |
| F3 Dashboard | Collection forms and provider policies; layout/dirty guard; bulk/filter/navigation; application totals; period controls; all operation surfaces. | Actual 1440/1920/390 px browser walkthrough, no lost edits, large archives and binary previews. |
| F4 Delivery | 0.5.0 docs/examples/skill, Docker and CI, resource/restore/agent regression, final PR review and cleanup. | Actual Linux 2 CPU / 4 GiB collector+scorer, amd64/arm64 startup, clean branch, resumable handoff. |

Work in isolated task worktrees. Root owns shared contracts and integration; delegate
collection, frontend, career/documents. Commit coherent slices. Keep diagnostics and
remaining defects in WORKLOG/STATE after meaningful batches. No per-function test
quota; practical proofs must catch real failures, not duplicate implementation.

No user production data/instance or main branch is modified. Release publication
remains an explicit action after a concrete verified candidate. Do not add semantic
search, internal AI generation, browser crawling or unrelated features in this pass.

## Completion

All F0–F4 phases pass. STATE.json and evidence/final-*.json record exact results,
source revisions and limitations. The user-facing delivery is PR 52 and the
synthetic local preview. No implementation work remains; merge/publication and
production deployment are separate owner actions.
