# Optional AI scoring

Scoring classifies job fit; it does not generate CVs or letters. The model-free
core works with scoring disabled. There is no keyword/empirical fallback score.
Existing scores remain visible when you turn scoring off. An in-flight request may
finish before the local model process releases its memory; no new inference is queued.

## Local and remote

The optional Compose `local` profile runs the pinned **Laya English** checkpoint
`55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, one model process and one inference
request at a time, with at most two CPU threads. It loads on demand and unloads
after 120 seconds idle. Weights stay in a disposable disk cache.

Configure local URL `http://scorer:8000`, provider `laya`, served model `english`,
context 2048 and the API key from `SCORER_API_KEY`. First download/loading can
be slow; a 600-second request timeout accommodates a cold start. The connection
test performs a real classification.

Remote mode accepts a base URL, an explicit served model and an optional API key.
It requires the **System One score contract**, including typed ordinal answers;
an arbitrary OpenAI chat-completions endpoint is not interchangeable. The
connection test checks the required subset. Changing the model name does not
download a model into the core. A stronger compatible service can run elsewhere.

## Inputs and freshness

The input combines your role/preferences, a compact career summary, selected
career facts and the posting. Use the optional profile **Scoring summary** for a
concise, user-authored classification profile; detailed evidence remains available
to document agents. The scoring-context view/API reports omitted details.
Oversized inputs are rejected when the scorer reports truncation; they are not
silently scored as complete.

New or materially changed complete jobs are queued when scoring is enabled.
Relevant profile, rubric or model edits mark older results **Outdated** without
enqueuing the whole archive. Contact/template edits do not require rescoring.
Rescore selected jobs or request an explicit bounded outdated batch. Periodic
rescoring is separately disabled by default and has a configurable batch cap.
Dismissed jobs are excluded. Failed requests remain visible in Tasks for retry.

## Limits

Scores are indicative. The small English model can misunderstand language,
qualifications and missing information; inspect the posting rather than using a
score as a rejection rule. Other input languages have not been established as a
supported quality baseline.

Compose allocates the core 0.5 CPU / 512 MiB and the scorer 1.5 CPU / 3584 MiB,
for a combined limit of 2 CPU / 4 GiB. These are enforced budgets, not a guarantee
for every host or profile length. Model startup, filesystem cache and other host
services also consume resources. If local scoring is impractical, keep it off or
use remote mode; collection, documents and tracking continue independently.

The [scorer implementation notes](../../scorer/README.md) describe its exact
service subset.

A reference measurement on Linux ARM64 with 2 CPUs / 4 GiB and no swap processed
an untruncated 1885-token classification in about 9 seconds. The conservative sum
of core/scorer cgroup peaks was about 2.90 GiB, including filesystem cache, with no
OOM; acquisition and API requests continued during inference. This is a measured
reference, not a low-power x86 speed guarantee. Disabling scoring lets an in-flight
request drain before releasing the model.
