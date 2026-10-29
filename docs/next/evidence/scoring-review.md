# Scoring feasibility review

2026-10-29. Synthetic career/job data only. This is a bounded practical probe,
not a trained benchmark, target-device measurement or production implementation.

## Finding

A useful **indicative local ranking service is technically feasible** with the
cached Laya English checkpoint. The 512-token limit was a configurable default,
not a hard model ceiling. Full candidate/posting contexts of 759–851 state tokens
fit at `max_len=1024` without dropping any tokens. Relevant professions scored
above unrelated professions in both tested role pairs.

It remains unsuitable as an automatic hard-eligibility decision. An otherwise
identical candidate with German A1 scored slightly above the C1 candidate even
when the mandatory C1 requirement was visible at the end of the posting. A
stricter natural-language rubric did not fix this. This is a model limitation,
not a truncation problem. Keep the score advisory; no score-based deletion,
submission, or automatic rejection. No empirical fallback is needed or proposed.

## Measured configuration

- Model: `convaiinnovations/laya`, English checkpoint revision
  `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`.
- Runtime: Laya 0.4.17, PyTorch 2.15.0, eager FP32 CPU; two intra-op threads,
  one inter-op thread; one loaded `Agent`, no router or other checkpoints.
- Host: Apple Silicon/macOS. No GPU. Two inference threads do not establish
  performance on an old x86 CPU or prove a two-core Linux resource limit.
- One ordinal score question with five descriptive levels. The experiment also
  checked 512 and 2048 maximum sequence lengths on identical inputs.

| Limit | Full inputs truncated? | Median request | Max request |
|---|---|---:|---:|
| 512 | Yes: 359–451 state tokens dropped | 0.405 s | 0.452 s |
| 1024 | No | 0.830 s | 0.875 s |
| 2048 | No; outputs identical to 1024 | 0.829 s | 0.865 s |

Sampled peak process RSS including model loading and all eighteen requests:
**2568 MiB / 2.51 GiB**. The largest actual complete sequence was 963 tokens;
setting a 2048 ceiling did not pad every request to 2048. The separate near-capacity resource probe below addresses longer actual input;
none of these measurements establishes whole-application capacity.

| Contrast, at 1024 | Relevant/met score | Unrelated/unmet score |
|---|---:|---:|
| Python backend engineer versus chef | 2.8791 | 2.1138 |
| Registered nurse versus software engineer | 3.0836 | 2.6051 |
| Mandatory German C1, C1 versus A1 candidate | 2.8791 | 2.9407 |

Scores use the model's 0–4 scale. Differences demonstrate two relevance orderings,
not calibration or an accuracy percentage. A software engineer still received
2.6051 for a licensed nursing role: do not describe the numeric score as a
probability of eligibility or hiring.

## Bounded follow-up

A more explicit rubric widened the two profession contrasts, but the German
ordering remained wrong. Extra `noul` questions did not establish reliable
mandatory-qualification checking: the A1 candidate still received 0.8056 for an
all-mandatory-requirements question. The three-question request peak increased
to **3042 MiB / 2.97 GiB**. Prefer one fit question for the resource-constrained
preset instead of adding per-requirement questions and aggregation machinery.

The runtime warned about an out-of-range calibration temperature for choices
with 11+ options, outside this five-level score primitive. Preserve diagnostics;
do not use provider confidence as proof of correctness.

## Concrete recommendation

1. Keep Laya English as the lightweight local **indicative** preset, plus off and
   remote compatible endpoint modes. Do not introduce a larger model by default.
2. Use `max_len=2048` as the bounded working preset: the separate 1,920-token
   actual request below fit without truncation and peaked at 2.60 GiB. Keep one
   checkpoint and one request at a time. Validate the final deployed whole stack
   before guaranteeing 4-GiB support; 512 loses much of a normal posting.
3. Check actual tokenizer usage and `usage.truncated`, not character counts.
   If essential context does not fit the configured ceiling, mark the assessment
   incomplete/unscored and allow a larger configured endpoint or explicit retry;
   never silently rank a chopped posting as if it were fully evaluated.
4. Preserve the supplied profile/job/rubric and context omissions. Use a bounded
   relevant profile projection, not the entire accumulated narrative knowledge
   base; the external document agent still has access to the rich full archive.
5. During integration, measure API/SQLite/worker plus local scorer startup and
   steady memory under the actual 4-GiB limit. The near-capacity probe leaves roughly 1.4 GiB
   of nominal headroom; it is not an end-to-end capacity guarantee.

No new model downloads, target-machine writes, provider calls or empirical score
formula were used. All probe processes have exited.

## Near-capacity 2048 resource probe

A separate process made **one actual 1,920-token request**, with a 2048 ceiling,
the same checkpoint, two CPU threads and one score question. The synthetic state
was extended with explicitly repeated employer information for resource stress;
this is not an additional accuracy experiment. The tokenizer preflight and runtime
usage agreed on 1,920 tokens, with **zero tokens dropped**.

- Model loading peak RSS: **2,663 MiB / 2.60 GiB**.
- Inference peak RSS: **2,604 MiB / 2.54 GiB**.
- One-request elapsed time: **2.394 s**.

This supports a bounded 2048 local preset on the measured Mac, rather than
restricting complete jobs to 512. It does not establish low-power x86 latency,
whole-stack Linux memory, input lengths beyond the ceiling or better accuracy.
The process exited. No new models were downloaded.

## Non-AVX target runtime compatibility

A separate disposable Linux environment tested the exact official
**PyTorch 2.15.0+cpu / Python 3.13 x86_64 wheel** on a CPU exposing SSE4.2 but
**no AVX or AVX2**. Installation used a temporary venv and PyPA pip zipapp,
without sudo, system-package changes, existing environments or model downloads.

Import and small FP32 **matmul, sin, cos, GELU, layer_norm and SDPA** all passed
with finite outputs. PyTorch reported CPU capability `DEFAULT`; no ISA override
or workaround was necessary. The process was pinned to one CPU, low priority
(nice 15), with one thread and a parent RSS/time monitor. Installation took
78.2 s / 157 MiB peak child RSS; the runtime/kernel probe took 5.0 s / 227 MiB.

The minimal environment lacked NumPy, producing a NumPy-integration warning;
the tested native Torch operations still succeeded. A full Laya environment
will install its required dependencies. This closes the immediate illegal-ISA
concern for the tested kernels, **not full ModernBERT throughput, memory or all
kernel paths**. The owned temporary directory was removed; an independent check
found no remaining probe directory. No production files/services were touched.

## Artifacts and reproduction

- `scoring_context_probe.py` and `scoring-context-probe.json`: complete synthetic
  profiles/postings, all outputs, usage/truncation, timings and sampled RAM.
- `question_shape_probe.py` and `question-shape-probe.json`: bounded rubric and
  typed-question diagnostic, development-only.
- `long_context_resource_probe.py` and `long-context-resource-probe.json`: one
  genuine near-capacity 2048 resource probe; imports fixtures from the first script.
- `non_avx_runtime_probe.py` and `non-avx-runtime-probe.json`: bounded disposable
  CPU-wheel/kernel smoke on the non-AVX Linux target, with cleanup.

Run with an environment containing Laya 0.4.17, CPU PyTorch 2.15.0 and psutil:

```sh
USE_TF=0 python scoring_context_probe.py
USE_TF=0 python question_shape_probe.py
USE_TF=0 python long_context_resource_probe.py
```

Set `HF_HOME` to an existing cache if desired. The first script downloads the
pinned model only if absent; probes here reused the already cached weights.
The code supports the exact per-call max-length override in the inspected
`laya/agent.py` and reports actual `state_tokens_dropped` from the runtime.
