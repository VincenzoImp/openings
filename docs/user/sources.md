# Saved searches and company feeds

**Collection** has Saved searches and Companies tabs. Both save typed sources in
SQLite and use the same queue and provider budgets. New sources start paused.
Preview a source, review the results/diagnostics, then enable its interval or daily
schedule with an IANA timezone. Run now queues work for an individually paused
source; it still respects provider policy. Bulk controls enable, pause, run or delete
selected sources. Deleting a source retains its archived jobs.
Search and page the source list; bulk selection is limited to 200 sources.

## Source criteria

| Input | Search criteria | Where to configure |
|---|---|---|
| Saved search | One query, location, country and explicit portal selection | Collection → Saved searches |
| Company watch | A selected ATS board/feed; optional title and location filters | Collection → Companies |
| Manual job | The specific URL or posting you provide | Inbox → Add job |

For example, save `backend engineer` in `New York, NY` with LinkedIn and
Indeed selected. Create another saved search for `platform engineer` or another
location. Career preferences guide optional fit classification; the saved query
controls what is requested from a portal. Company sources read the chosen board
and apply their configured filters.

## Saved searches

The pinned JobSpy 1.4.1 integration searches LinkedIn, Indeed and Glassdoor.
Save one explicit query and location with a country and provider selection.
Create another source for a different query/location. Result count, age window,
remote/job type and description fetching are bounded settings. Country/provider
capabilities vary. Google Jobs is unsupported.

For REST/MCP, a `jobspy` source uses a configuration such as:

```json
{
  "query": "backend engineer",
  "location": "New York, NY",
  "country": "usa",
  "providers": ["linkedin", "indeed"],
  "results_wanted": 20,
  "hours_old": 72,
  "is_remote": false,
  "job_type": null,
  "fetch_description": true
}
```

Preview saves no jobs. It returns a request estimate and per-provider diagnostics;
redirects/errors can require extra attempts, so actual limits always apply. A saved
multi-provider search queues one task per provider, allowing other sources to progress.
JobCloud supports regional jobs.ch/jobup.ch search through an undocumented endpoint.
Adzuna is optional, disabled by default and requires owner-supplied credentials; its
results contain snippets.

## Company and feed sources

Supported source kinds include Greenhouse, Lever, Ashby, Recruitee, Personio,
Workable, Breezy, SmartRecruiters, BambooHR, Rippling, Workday, Oracle, join.com
and RSS/Atom. Paste a board/feed URL, preview and correct the typed configuration
if necessary. Some platforms use undocumented public endpoints that can change.
Breezy/snippet-only results can remain incomplete. Missing RSS locations stay unknown.
An error or blocked page is reported rather than treated as an empty successful search.
Detail requests respect each source's cap. Complete cached details become eligible
for refresh after 24 hours; older unchecked entries are considered first. Greenhouse
lists job metadata before requesting descriptions for matching roles.

## Provider safeguards and tasks

Settings lists each provider's capability/version, policy and read-only runtime.
The same persisted gate counts every HTTP attempt across preview, manual imports,
scheduled sources, redirects and supported vendor detail requests. Configure enabled
state, minimum spacing and hourly/daily/per-run caps. Retry-After seconds/date causes
a durable cooldown; restart, pause and older-backup restore do not reset recent usage.
Deferred tasks release the collection lane rather than sleeping for long periods.
Cross-provider redirects are rejected with the destination URL. Use that URL
directly so the request is checked against the correct provider policy.

The global automatic collection switch preserves individual settings. It stops
scheduled acquisition while explicit manual work remains available under the same
provider limits. Tasks show source/job labels, progress/errors and cancel/retry controls.
Collection can progress while the independent inference lane handles one score request.

These are local safeguards, not platform quota or access guarantees. A portal may
block public requests or change its pages. Do not interpret an empty/failed search
as proof that no jobs exist. Use the source diagnostics and manual input when needed.

## Manual input and state

Add job accepts a URL, pasted posting or structured fields. All interfaces and
collectors share the same deduplicated ingestion path. URL extraction supports
recognized ATS APIs and JobPosting JSON-LD. Generic, login, challenge and JavaScript
pages remain incomplete when full text cannot be established; paste the description.
There is no server browser crawler. Incomplete jobs are retained and excluded from
useful scoring until corrected.

Repeated identities preserve triage, corrections and application history. Distinct
URLs need verified identity or an explicit Merge before they become one job.
Inbox/Saved/Dismissed triage is separate from Draft/Applied/Interview/Offer/Closed
application progress. Dismissed jobs stay remembered; Forget deletes all job-owned
records/identities and permits later acquisition as new. Reapplications are independent
attempts. Saving documents never records an actual submission.
