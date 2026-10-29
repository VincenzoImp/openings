# Feasibility

Measured 2026-10-29. Only synthetic content was used.

## 1. A portable database and one service contract

[Contract prototype](../../experiments/next/contract.py),
[schema](../../experiments/next/schema.sql),
[tests](../../experiments/next/test_contract.py).

**12 tests pass:** rich evidence/claims and layered prompts survive context
creation; inputs remain frozen after profile edits; ingestion, requests and
submission are idempotent; invalid/unapproved evidence and excessive bullet
length are rejected; REST/MCP read the same state; a SQLite backup contains PDF
bytes and passes `integrity_check`.

This proves a narrow boundary. It does not implement production auth, task
leases, complete typed MCP discovery, historical migration or the full UI.
Referential checks do not prove a generated sentence is true.
The experimental status enum predates the simplified triage/application rules
in DESIGN.md; it is not the final production schema.

## 2. User LaTeX → PDF

[Rendering probe](../../experiments/next/render_probe.py) uses a synthetic template,
escaped content and Tectonic 0.17.0. Compilation succeeded; warm compilation
with only cached packages also succeeded. See [cold result](evidence/latex-probe.json)
and [offline result](evidence/latex-offline-probe.json), with their example PDFs.

Cold setup included package downloads; it took about 124 seconds. Cached
compilation took about 0.22 seconds on this host. These are not 2-core server
benchmarks. The confirmed product now compiles through the external agent and
stores PDF/source files; there is no server renderer. This probe demonstrates
external compilation only, not containment of hostile TeX or the production
document round trip.

## 3. CPU decision models

Same 14 intentionally simple yes/no diagnostics, one request at a time, two CPU
inference threads, Apple Silicon/macOS. No GPU. No production dataset or model
tuning. The threshold 0.5 is diagnostic, not a chosen deployment threshold.

| Engine | Correct diagnostics | Median short request | Observed memory |
|---|---:|---:|---|
| jevos-v5 / OpenVINO INT8 | 11/14 | 0.192 s | RSS observations roughly 3.6–4.8 GiB; not continuous peak sampling. |
| Laya English / PyTorch eager | 10/14 | 0.074 s | Sampled peak RSS about 2.57 GiB including loading. |

Raw inputs, outputs, pinned model/engine versions and timings:
[jevos](evidence/jevos-probe.json), [Laya](evidence/laya-probe.json).
jevos assets were checked against the author's release checksums.

jevos failed the chef/programmer contrast, A1/C1 and one relevant-experience
case. Laya failed the chef/programmer contrast, relevant experience, the
salary-floor check and missing evidence. A high
reported probability did not prevent errors. jevos latency also grew to about
3.7 s at 788 input tokens and 19.7 s at 3,788 tokens on this host.

**Laya English is the working baseline**, chosen for lower measured memory and
latency. It is not production-validated. Local CPU inference is feasible; reliable
fit assessment within the whole 4 GiB installation is still a release gate.
Test selected/quantized runtimes on low-power x86 and ARM; do not extrapolate
Mac speed or RSS. Keep the core usable with external scoring and an unscored state.

Next evaluation: hold out synthetic and public examples covering role relevance,
negation, missing facts, language levels, skill-specific experience, geography,
long contexts and malicious posting instructions. Keep prompt-development cases
separate. Report errors/abstentions, not just a single accuracy number.

### Real HTTP score smoke check

The installed Laya 0.4.17 HTTP server was started on localhost with CPU/two
threads, only English preloaded, one loaded checkpoint and one concurrent request.
Three synthetic five-level `score` requests returned valid 0–4 responses;
an unauthenticated request was rejected with 401. The process was stopped after
the probe. [Requests, responses and versions](evidence/laya-http-probe.json).

Direct/partial/unrelated examples returned 3.6408 / 1.8768 / 1.659. Median HTTP
latency was about 0.131 s, sampled peak RSS about 2.65 GiB on this Mac. This
proves a real HTTP score round trip for that runtime; three short examples do
not validate ranking accuracy, complete contexts or remote/target deployment.

## 4. Codex integration

Codex CLI 0.165.0 is present. Official documentation supports noninteractive
structured output and app-server integration. The app-server initialization
handshake succeeded. [Evidence](evidence/codex-protocol.json).

No paid inference, account lookup or credential extraction was performed.
The current scope uses external MCP/REST agents for documents, with no internal
generative endpoint or embedded runner. End-to-end production submission and
review remain untested. The handshake is historical integration evidence only.

## Reproduce

```sh
cd experiments/next
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python render_probe.py --only-cached --out /tmp/latex-probe.json
```

Rendering needs an installed Tectonic and cached packages. jevos additionally
needs the pinned author binary/weights, running with two threads; run
`decision_probe.py --out /tmp/jevos-probe.json`. Laya needs `laya==0.4.17`,
PyTorch and psutil in a separate environment; run `laya_probe.py --out /tmp/laya-probe.json`.
Weights and environments are not repository artifacts. SHA revisions are in the probes.

## Final preflight review

### Actual MCP, files and portable context

The [live MCP probe](../../experiments/next/mcp_file_probe.py) starts a temporary
HTTP server and a real SDK Streamable HTTP client. One practical round trip
passed 15 checks: typed discovery/resources, frozen context after REST edits,
external Tectonic compilation, scoped binary PDF/source upload/download,
immutable content/file association and exact-byte SQLite backup/restore.
[Results](evidence/mcp-file-probe.json), [findings](evidence/interfaces-review.md).

This resolves the protocol/file-transfer uncertainty. It does not substitute
for production browser auth, large-file/concurrency checks or a real external
Codex/Claude session against the finished app. Stored instructions must be
assembled by the new service; the historical fixture accepts a prompt argument.

### Realistic and near-capacity scorer inputs

The 512-token context is configurable. At 1024, six realistic synthetic
profile/posting cases (up to 963 total tokens) had no truncation, median 0.83 s,
peak process RSS about 2.51 GiB. Relevant professions outranked unrelated ones;
mandatory German C1 versus A1 ordering remained wrong despite a stricter rubric.
[Full cases](evidence/scoring-context-probe.json),
[bounded follow-up](evidence/question-shape-probe.json).

A separate **1920-token** request at `max_len=2048` reported no dropped tokens,
took 2.39 s and peaked at **2.60 GiB including loading** on this Mac CPU/two-thread
run. This supports the bounded 2048 local preset, not a whole-stack Linux/x86
capacity guarantee. One fit question is preferable to three diagnostics that
raised memory without reliable eligibility checking.
[Near-capacity result](evidence/long-context-resource-probe.json),
[detailed review](evidence/scoring-review.md).

### Dashboard preview

The [interactive preview](preview/index.html) has seven original Dossier-inspired
screens, synthetic data, browser-only persistence and manual interaction flows.
A browser walkthrough passed **33 checks** over desktop and 390px mobile:
navigation, search, add/duplicate job, note, dismiss/restore/forget, application
stage/list/Kanban, contact versus relevant profile edits, scoring modes, theme
and no document-level overflow or JavaScript errors.
[Walkthrough result](evidence/dashboard-smoke.json).

The browser caught malformed CSS repeat/minmax declarations; fixed and parsed
again. New application drafts no longer inherit the example PDF. These are
preview fixes, not claims of an implemented production frontend. All API/model/
collection actions in the preview are explicitly simulated or absent.

### Target CPU runtime compatibility

The intended low-power x86 CPU exposes SSE4.2 but no AVX/AVX2. A disposable,
low-priority CPU-only PyTorch 2.15.0 environment successfully imported and ran
FP32 matmul, sin/cos, GELU, layer normalization and SDPA with `DEFAULT` dispatch;
no ISA override was needed. Operations took about 5 s and peaked at 227 MiB.
No model was downloaded or production service changed; the temporary directory
was removed. [Result](evidence/non-avx-runtime-probe.json).

This resolves the tested runtime/kernel compatibility question, not full-model
throughput. Linux amd64/arm64 CPU wheels were also verified in the official
index; use CPU-only wheels in a glibc-based image, keeping model dependencies
out of the core. [Package check](evidence/cpu-package-check.json),
[official installation guidance](https://pytorch.org/get-started/locally/).

## Production release validation

The actual production images ran together inside a clean Linux ARM64 VM with
2 CPUs, 4 GiB RAM and no swap. Compose enforced core 0.5 CPU / 512 MiB plus
scorer 1.5 CPU / 3584 MiB. An untruncated 1913-token request completed while the
core remained responsive. The sum of each container's measured cgroup memory
peaks was about 2.80 GiB, including charged filesystem cache; neither container
reported an OOM. These are measured container peaks, not an RSS estimate.
Disabling local scoring terminated the model child; remaining memory includes
reclaimable model-file cache. Low-power x86 throughput is not established by
this ARM virtual-machine measurement. The separate non-AVX kernel probe above
remains the target-CPU compatibility evidence.

The application/scorer images were rebuilt from final sources and restarted
with persisted data. A separate empty installation restored 206 jobs and exact
document bytes while retaining its own owner and rejecting the originating
installation's token. The 21 Docker workflow checks also covered concurrent
dedupe, optimistic edits, dismiss/forget, scoped transfers, a full export beyond
200 records, MCP origin and invalid restore handling.

An actual external Codex CLI session read the shipped skill and frozen context,
wrote tailored CV/letter/answers, compiled both PDFs externally, checked page
count/text, verified four uploaded/downloaded files by SHA-256, and left all
review/status fields in draft. Browser checks exercised the seven production
screens, populated Kanban/Sankey, actual PDF preview, modal keyboard behavior,
versioned deletion and archives beyond200 records on desktop/390px mobile.

Evidence: [Linux resources](evidence/production-linux-resources.json),
[context/overflow handling](evidence/production-context-limits.json),
[Docker workflow](evidence/production-docker-workflow.json),
[external Codex](evidence/external-codex-workflow.json),
[production MCP transport](evidence/production-agent-roundtrip.json).
