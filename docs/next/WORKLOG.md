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
