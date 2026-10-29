# Collection integration evidence

Verified 2026-10-29 against the version-pinned vendored JobSpy1.4.1 subset.
One bounded preview: explicit `software engineer` / `New York, NY` / `usa`,
two results per LinkedIn/Indeed/Glassdoor provider, descriptions enabled,
default three-second minimum spacing per provider. All six jobs included
descriptions; seven HTTP200 attempts (3/1/3),14.203 seconds, zero saved jobs.
No retry, credential, browser, proxy or high-volume stress probe was used.
Google remains explicitly unsupported because the previous verified provider
could not expose usable job data. These observations are point-in-time evidence;
the configured safeguards are not platform quota guarantees.

The focused acquisition suite verifies the real three-provider session seam,
Retry-After seconds/date and restart persistence, redirect attempt accounting,
shared preview/manual/worker limits, global and individual pause, manual runs,
provider task splitting, cancellation, unknown RSS locations, bounded company
details, and collection while one slow inference is running. Material job edits
during inference queue one current successor. A stopped worker's stale result
cannot overwrite a new assessment, and its in-flight inference completes before
a successor begins. No additional model is loaded by a collection lane.
Explicit score tests/configuration checks share the same inference slot.
Network-capable MCP operations dispatch to threads; a held preview was verified
concurrently with a successful HTTP health request and another MCP read.

Additional company clients are narrow, bounded adaptations of verified endpoint
shapes from the prior Openings reference. Undocumented join.com, Workday,
Oracle and JobCloud shapes can change; malformed/challenge responses surface as
errors rather than successful empty results. Breezy has no public description,
and Adzuna returns snippets and requires explicitly supplied credentials; its
provider is disabled by default. Complete known company postings skip bounded
detail requests while retaining prior metadata and posting content.

A subsequent guarded live company batch used one result and at most one detail
per source. Recruitee/callista, SmartRecruiters/CERN, JobCloud/jobs.ch and
Workday/ABB each returned one job with its full posting. Oracle/CX_5 returned
one listing with details intentionally disabled. Personio's own board returned
a valid empty positions XML feed; the Workable self-board slug returned HTTP404,
correctly reported as an error. Twelve actual attempts were counted, including
two JobCloud301 redirects, against an estimate of ten before redirects. No
automatic retries or saved jobs. The bounded curl body hook was separately
reverified against Glassdoor: two jobs, full descriptions, three HTTP200s in
7.085 seconds. Synthetic local HTTP servers verified both requests and curl
reject an8MiB+1 response and retain exact integer response statuses/counts.

Manual URL integration entry points:

```python
provider = discovery.provider_for_url(url)
body = discovery.fetch_bytes(url, provider_id=provider, maximum=2 * 1024 * 1024)
```

`fetch_bytes(..., provider_id="manual")` also recognizes supported provider hosts.
It validates public URLs/DNS and every redirect and returns bytes. A
ProviderDeferred is a DomainError429 with `details.provider` and
`details.next_run_at`; HTTP failures remain useful DomainErrors. Low-level
`http_budget(provider, run_id=None, active=None)` exposes before/after/request
hooks for an explicit instance transport. Policy windows, reservations, run
counts and cooldowns live in the portable SQLite providers table. Pauses never
reset runtime, and neither manual runs nor previews bypass the gate.
