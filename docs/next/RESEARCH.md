# Research notes

Inspected local source; exact revisions are in [repositories.json](evidence/repositories.json).
Most integrations are narrow service clients. The bounded JobSpy 1.4.1 subset is
vendored with its MIT license and [patch/provenance notes](../../backend/openings/_vendor/jobspy/PROVENANCE.md);
its explicit per-instance transport is wired to persisted HTTP budgets.

| Project | Approach | Decision |
|---|---|---|
| [Openings](https://github.com/VincenzoImp/openings) | Archive/service shared by REST/MCP/UI; many feed adapters; deterministic ranking. | Keep company ATS feeds, service boundary and job/posting distinction. Remove empirical ranking and add career/document domain. |
| [Dossier](https://github.com/AienTech/dossier) | Profile → structured content units → server-rendered PDF; background tasks and version history. | Retain the content/presentation separation as an idea; do not flatten rich evidence into CV bullets. Its PDF engine is HTML/Chromium, not LaTeX. |
| [JobApply](https://github.com/romit-23/jobapply) | Structured profile, narrow LLM output, SQLite ledger, staged generation; LaTeX templates. | Freeze context and reuse successful stages. Avoid its default public HTTP TeX compilation and unnecessary orchestration dependencies. |
| [JobNavigator](https://github.com/vesaias/JobNavigator) | Broad scraping, persona/Q&A, document review, CLI/API providers and portal extension. | Valuable form-answer and persona model. Its broad deployment/feature surface exceeds this first release. Provider code is evidence of implementation, not authority for authentication policy. |
| [Reactive Resume](https://github.com/reactive-resume/reactive-resume) | Typed resume schema, templates, PDF library, API/MCP and polished editing. | Learn the structured rendering/editing boundary. The inspected v6 main differs from older indexed v5 documentation; read current code. No reason to adopt the full monorepo. |
| [RenderCV](https://github.com/rendercv/rendercv) | Validated career data + design settings + Jinja templates → Typst/PDF. | Strong example of deterministic rendering and customizable templates. Typst is an alternative, not a transparent replacement for users' LaTeX. |
| [ApplyKit](https://github.com/wihlarkop/applykit) | Atomic requirements linked to career evidence; separate fit, confidence and eligibility; immutable corrections. | Keep evidence and missing facts distinguishable from fit. User chose one indicative AI score; do not adopt its scoring formula. |
| [Career Compass](https://github.com/benskamps/career-compass-mcp) | Agent-facing knowledge/evidence, reusable skills and form answers; local YAML. | Confirms an external agent can own inference while the product owns knowledge. Our source of truth remains SQLite and shared services. |

## Decision-model shortlist

| Candidate | Mechanism and constraint | Current conclusion |
|---|---|---|
| [TypeSafe Jev](https://docs.typesafe.ai/concepts/system-one) | Hosted typed Choice/Score/Noul decisions rather than prose generation. | Optional remote adapter. Official documentation does not provide a local weight download. Do not confuse similarly named GitHub sites with the model owner. |
| [jevos](https://github.com/feder-cr/jev) | Local OpenVINO INT8 decision model; native binary and GGUF alternative. | CPU candidate, tested. Three diagnostic errors and high observed Mac RSS prevent selecting it blindly. |
| [Laya](https://github.com/NandhaKishorM/laya) | Encoder with decision heads; English/multilingual checkpoints, CPU and ONNX paths. | CPU candidate, tested. Four diagnostic errors. ONNX INT8 is not an automatic fix: the exporter itself documents accuracy drift. |
| [AnyJev](https://github.com/nokia-applied-research/AnyJev) | Reads constrained next-token probabilities; optional rotation/prior correction; GGUF backend. | Flexible quantized-model experiment. Corrections can require multiple passes; a small base model is not guaranteed to reason correctly. |
| [jevify](https://github.com/Mintzs/jevify) | Shared-context question branching around an existing decoder LLM. | Its prominent speed results are CUDA laptop measurements. Current engine does not support quantized wrappers; not the default for 4 GiB. |
| [GLiClass](https://github.com/Knowledgator/GLiClass) | Zero-shot labels scored together by an encoder. | Suitable alternative for role/category routing; not automatically a full profile/requirement judge. Not run here. |

Conclusion: use a replaceable decision adapter and an application-specific
evaluation set. Fourteen diagnostics are enough to reject a blanket reliability
claim, not enough to rank models for production. Do not transfer vendor GPU
latency, memory claims or general benchmark scores onto a low-power CPU.

The user prioritizes low RAM and CPU. Laya English is now the measured baseline
over jevos. Baseline whole-stack Linux measurements passed, while final integration
measurements remain separate evidence; score quality is still advisory. Avoid a
multi-checkpoint router.
The author's [multilingual card](https://huggingface.co/convaiinnovations/laya-multilingual)
reports a smaller 322M model but also weak ordinal scores; size alone does not
establish suitability. Validate long job/profile inputs before shipping.

## Provider integration

- [Codex noninteractive mode](https://learn.chatgpt.com/docs/non-interactive-mode):
  existing CLI authentication, JSON events and schema-constrained output.
- [Codex app-server](https://learn.chatgpt.com/docs/app-server):
  an official integration surface with login flows and persistent turns.
  The local protocol handshake was tested; no inference, account data or tokens read.
- [Claude programmatic CLI](https://code.claude.com/docs/en/headless):
  structured output exists; runtime flags affect authentication/config loading.
- [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview):
  the official product-integration guidance specifies API authentication unless
  separately approved; do not promise an embedded claude.ai subscription login.

Current first-release scope is external-agent MCP/REST for document preparation
and compilation. The earlier generative endpoint/CLI integration proposal is
superseded; no internal model runner or login is needed. API endpoint configuration
now concerns the optional scorer only. A user running their own assistant against
MCP is different from embedding its login into the product.

The inspected Laya and jevos HTTP servers implement the TypeSafe
`/v1/systemone` request family. This is useful shared wire format, not proof of
universal interchangeability: actual model selection, limits and confidence
fields differ. See [the bounded adapter contract](AI.md#shared-protocol-bounded-compatibility).
Laya's current server defaults may preload multiple checkpoints; the bundled
deployment must explicitly select one and bound concurrency.

## Name

Keep **Openings** during the rebuild and improve its descriptor, README and
GitHub topics. The name already fits discovery and applications. ApplyKit is
already used by relevant projects. No search establishes universal name or
domain availability. Branding does not justify delaying the core workflow.
