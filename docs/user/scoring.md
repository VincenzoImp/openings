# Optional AI scoring

Scoring classifies job fit. Document generation runs in your external agent.
The core works with scoring disabled; it has no keyword-based fallback score.
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

After testing, turn on **Enable AI scoring** and click **Save scoring settings**.
The saved-state message confirms whether scoring is active. Editing the switch
or fields leaves a draft until you save; **Discard changes** restores saved values.

Remote mode accepts a base URL, an explicit served model and an optional API key.
It requires the **System One score contract**, including typed ordinal answers;
an arbitrary OpenAI chat-completions endpoint is not interchangeable. The
connection test checks the required subset. The configured model must already
be served by that endpoint.

## Inputs and freshness

The input combines your role/preferences, career facts and the posting. When
**Compact scoring profile** is filled in, it replaces detailed knowledge and claims
for classification. Without it, selected career facts accompany your profile.
Document agents retain access to the full archive. The scoring-context view/API
reports omitted details.
Oversized inputs are rejected when the scorer reports truncation; they are not
silently scored as complete.

New complete jobs are queued when scoring is enabled. **Automatic rescoring of
changed postings** is on by default; turn it off to score only previously unseen
jobs automatically. Saving that switch does not queue or invalidate existing scores.
Known partial previews and punctuation-only placeholders stay archived without
scoring. Completing the posting through **Edit details**, REST or MCP makes it
eligible for explicit scoring, and for automatic scoring when update rescoring
is enabled. Source refreshes preserve that correction.
Relevant profile, rubric or model edits mark older results **Outdated** without
enqueuing the whole archive. Contact/template edits do not require rescoring.
Rescore selected jobs or request a bounded batch of unscored or outdated jobs.
Periodic rescoring is separately disabled by default and has a configurable batch cap.
Model scoring excludes dismissed jobs. Failed requests remain visible in Tasks for retry.

## Record an external review

Use **Record fit assessment** in a job's details to save a score, reviewer/source
and reasoning. It works with local scoring disabled. An external agent can read
`scoring_context` and submit `scoring_record_assessment`, or use
`GET /api/v1/scoring/context/{job_id}` and `POST /api/v1/scoring/assessments`.
The write requires the context signature; changed inputs require a fresh review.
The saved assessment retains its context and cancels pending inference for that
job. The job shows the reviewer and reasoning separately from model results.

Scores are numeric **0–100**, with higher values indicating better fit. The
classifier compares the posting against ordered criteria and maps its continuous
ordinal result onto that range. Filters use the stored numeric value. A score is
an indicative fit assessment, not a probability of an offer.

## Score limitations

Scores are indicative. The small English model can misunderstand language,
qualifications and missing information. Review the posting before making a
decision. Other input languages have not been established as a
supported quality baseline.

## Resources and CPU compatibility

The default Compose file enforces these limits:

| Container | CPU limit | Memory limit |
|---|---|---|
| Core | 0.5 CPU | 512 MiB |
| Optional local scorer | 1.5 CPU | 3584 MiB |
| Combined local stack | 2 CPU | 4 GiB |

These figures are enforced container budgets. Allow additional resources for the
operating system, Docker and other host services. Model loading, input length and
filesystem cache affect memory use; CPU and storage affect startup and inference
time. Actual usage and inference time vary with the host and input.

Check memory use and logs during a connection test and representative scoring
requests on your host. If local scoring is impractical, use a compatible remote
service or leave scoring disabled. Collection, documents and tracking work in all
three [deployment modes](getting-started.md#deployment-modes-and-resources).

The [scorer implementation notes](../../scorer/README.md) describe its exact
service subset.

Older x86 CPUs may be incompatible with native libraries in the scorer image.
An idle health check does not exercise the model; use the connection test to
verify inference. If an illegal-instruction failure is traced to Intel oneMKL
dispatch, [Intel documents an instruction cap](https://www.intel.com/content/www/us/en/docs/onemkl/developer-guide-linux/2026-0/instruction-set-specific-dispatch-on-intel-archs.html)
such as `MKL_ENABLE_INSTRUCTIONS=SSE4_2` for Intel processors supporting SSE4.2.
Apply it only to the scorer through a local Compose override when needed. It
controls oneMKL, so compatibility with the rest of the model runtime still needs
verification.
