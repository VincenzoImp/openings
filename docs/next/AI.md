# Optional scoring and external agents

## External document preparation

The app stores knowledge, claims, templates/assets, editable prompts/rules,
application context and document versions. An external agent such as Claude Code
or Codex owns inference and uses its own configured account/provider.

1. Read the job and relevant profile/knowledge/template/rules through MCP.
2. Obtain a frozen application context.
3. Write CV/letter/form answers, compile externally and inspect the output.
4. Upload PDF, sources and structured content against that context.
5. Review/export in the dashboard; update application progress explicitly.

MCP is the interface; the [skill draft](../../skills/openings-workspace/SKILL.md)
teaches this workflow. Scripts can use the same operations through REST.
No generative endpoint, provider login, subscription token, agent SDK or embedded
CLI worker is needed in Openings. The confirmed first release has no server-side
TeX compiler. External compilation was already demonstrated with synthetic data;
the complete production MCP round trip remains untested.

Dossier's internal provider calls and Claude connector remain useful research,
not requirements to reproduce. See [research](RESEARCH.md).

## Optional scoring service

| Mode | Configuration | Resource effect |
|---|---|---|
| Disabled | Scoring off | Collection/search/tracking remain usable; no local model loaded. |
| Bundled local | Reviewed preset and optional service | One pinned checkpoint, CPU only, bounded concurrency. |
| Remote compatible service | Base URL, served model ID, optional API key | Inference uses that host; local app keeps only HTTP/client work. |

Working local preset: Laya English, revision
`55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, 421M ModernBERT-large + decision heads.
Short probes used a sampled peak 2.57 GiB, versus 3.6–4.8 GiB observed RSS for
jevos. The 512-token default is configurable. Complete ~963-token sequences fit
at 1024 without truncation; a near-capacity 1920-token sequence at 2048 took
2.39 s with a 2.60-GiB loading peak on this Mac/two-thread run. The bounded local
preset is therefore **2048 tokens, one question/checkpoint/request**. It makes
known language/qualification mistakes and remains advisory. Whole-stack target
measurements are still required. See [raw measurements](FEASIBILITY.md).

Users can host a stronger compatible model elsewhere. Choosing a model ID means
selecting what that server provides; it does not make arbitrary weights compatible.
No automatic multi-checkpoint router or hidden provider fallback.

## Shared protocol, bounded compatibility

TypeSafe Jev, jevos and Laya expose `POST /v1/systemone` with `model`, `state`
and named `questions`; answers can be `noul`, `choice` or `score`. Use a small
HTTP adapter and validate the subset we need, not an entire provider SDK.

First contract: text/JSON state and one fit `score` question with five ordered
text criteria. Validate a finite result in 0–4, retain the actual returned model
and map the scale to 0–100 for display. This is a model judgment, not keyword
weighting. Ignore optional extensions; retain raw metadata for diagnostics.

Compatibility is not universal. Model aliases, context limits, criterion limits,
errors and confidence semantics differ. Laya's server documents different
confidence semantics and a strict mode; jevos may accept Jev aliases without
changing its loaded model. Do not compare confidence thresholds across providers
or treat the requested model string as proof of the checkpoint used.
The local HTTP probe returned the generic name `laya-rl-agent`; also retain the
configured checkpoint/revision and available server metadata for provenance.

Test connection must run a small actual score request, validate its response
and report the returned model before enabling a provider. Pin the bundled
runtime/model, explicitly select English and prevent multi-model preloading.
Inspect the installed server version's controls rather than relying on its
resource-heavy defaults. A reachable health URL alone proves no score support.

A real localhost HTTP smoke check passed for the installed Laya server with
three synthetic five-level requests; see [measured evidence](FEASIBILITY.md#real-http-score-smoke-check).
Other providers and real job-fit quality remain to be checked.

No promises about every Jev-like repository. Other protocols require an explicit
adapter and a real compatibility check, outside the initial subset.

Sources: [TypeSafe API](https://docs.typesafe.ai/api/system-one),
[Score semantics](https://docs.typesafe.ai/primitives/score),
[Laya server](https://github.com/NandhaKishorM/laya/blob/main/laya/serve.py),
[jevos](https://github.com/feder-cr/jev).

The Laya preset sends its supported `max_len=2048` option. Generic System One
requests omit Laya-specific options; unsupported fields may be rejected by other
servers. Keep these small provider-profile differences in the HTTP adapter.
