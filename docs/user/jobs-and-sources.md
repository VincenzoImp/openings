# Jobs and sources

## Review jobs

**Jobs** has three tabs: **New**, **Dismissed** and **All**. Shortlisted jobs live
in Applications; in **All** they show their stage. Select a job to read its
posting, signals, notes and history beside the list. After each decision the
next job is shown, and every decision can be undone from its toast or with `z`.

- **Shortlist** (`s`) starts the job's application (stage Shortlisted). Undoing
  it removes that application only while it is empty. Once it has documents,
  notes, replies, requirements or answers, close the application instead.
- **Dismiss** (`d`) sets the job aside at once; its toast offers **Add reason**
  (up to 500 characters). Dismissed jobs keep their identity and history, so
  later collection does not bring them back as new. **Dismissed** shows who
  dismissed each job and why; the Filter menu narrows it to **You**,
  **An agent** or **Job sources**. **Restore** (`r`) returns a job, or a
  selection, to New.
- **Forget permanently…** in the job's `…` menu removes the job, its identities
  and its applications, notes and files after asking. Collection can find it
  again. This cannot be undone.

Closing an application never changes the job's tab. Deleting a job's last
application returns the job to New.

The keyboard does it all: `j` and `k` (or the arrows) move, `s`, `d` and `r`
decide, `z` undoes, `o` opens the posting, `e` corrects the details, Enter moves
to the job, `/` searches and `?` lists every shortcut. Select several jobs (`x`,
shift+`j`/`k`, or shift-click for a range) to shortlist, dismiss, restore or
forget them at once; each job succeeds or fails on its own. On a phone a job
opens full screen with **Dismiss** and **Shortlist** at the bottom; swipe a row
right to shortlist it or left to dismiss it.

## Add or correct a job

**Add job** (or `n`) takes a URL, or a title, company and the full posting. A job
already in the workspace is shown instead of a copy. When a page cannot be read, the
job stays marked **Text incomplete** until you paste the posting with
**Correct details** in the job's `…` menu. Edits you make are kept when a source
refreshes the job.

## Signals and filters

Each job carries labels computed without a model:

| Signal | Meaning |
|---|---|
| Posting language | The language the posting is written in. |
| Requires | The languages it requires; one language of a group is enough. A language mentioned only as a plus is not required. |
| Possible duplicate | It probably repeats an earlier job. |
| No longer listed | A company board stopped listing it. Set only when a run read the whole board. |

Signals label and filter; they never dismiss a job. Filter by language, signal,
source or who dismissed. List your languages under
[Preferences](profile-preferences-templates.md#settings), then switch on **Hide
jobs requiring languages I don't speak**: a job is hidden when one of its required
language groups has none you speak, and the count of hidden jobs is shown.

## Duplicates

A job that probably repeats an earlier one, such as one posting on several boards,
shows **Possibly the same job as** the earlier job, with the reasons: the same
apply link or requisition ID, the same text, or the same company, role and place,
and anything against it, such as a different place or level. Choose **Merge into
one job** to keep one job with both sources and timelines, or **Keep both** to
record that they are different. The label does not come back. Nothing merges
automatically. **Merge with another job…** in the job's `…` menu merges any two
jobs.

## Sources

**Sources** lists saved searches and company boards with their on/off switch,
schedule and last run, plus a master switch for scheduled collection. Settings are
stored in the workspace. New sources start paused. **Preview results** requests at
most three results per portal and saves nothing. A source can run once while
paused.

| Source | What it collects |
|---|---|
| Saved search | One query and place on LinkedIn, Indeed and Glassdoor |
| Company board | A Greenhouse, Lever, Ashby, Recruitee, Personio, Workable, SmartRecruiters, BambooHR, Rippling, Workday, Oracle or join.com board, or an RSS/Atom feed |
| Manual job | The URL or text you add under Jobs |

Breezy boards can be previewed but not collected automatically; add their postings
by hand.

### Saved searches

| Setting | Default and range |
|---|---|
| Query | Required. One saved search per query and place. |
| Location | Empty. Use a place the portal knows. |
| Country | Empty. Indeed and Glassdoor need one, such as `switzerland` or `uk`; LinkedIn uses the location alone. |
| Portals | All three; choose the ones you want. |
| Result limit | 20 per portal per run, 1 to 50. Known jobs count. |
| Age window | 72 hours, 1 to 8760. |
| Remote only, job type | Off, any. |

A query and a result limit do not guarantee complete coverage: portals sort by
relevance, round age filters and sometimes return incomplete results.

### Company boards

Paste the board or feed URL and preview it to see the detected service. The
result limit is 100 matching jobs per run (1 to 2000). Optional filters keep
matching **titles** and **locations** and skip **excluded role terms** such as
`sales`; any matching term in a group is enough, and unknown locations stay
visible for review. Lever boards have a region (`global` or `eu`). Company boards
can hold undated jobs, so the age window does not apply to them.

### Schedule

Choose an **interval** (default every 1440 minutes, 15 to 43200) or **daily
times**: one to twelve local `HH:MM` times and a time zone, such as `08:00, 16:00`
in `Europe/Berlin`. The first interval run waits one interval after enabling; use
**Run once** to collect now. Missed slots merge instead of queueing. The master
switch pauses all scheduled runs without losing settings; queued runs continue
until **Stop run**.

**Run with options** changes the age window or result limit for one run only. Select
several sources to enable, pause, run, change or delete them together; a change
applies only to the chosen fields. Deleting a source keeps the jobs it found.

### Runs and counts

Under **Runs and tasks**, each run shows its state and cumulative counts:
processed, new, already known, invalid, waiting for text and text unavailable. A
**Partial** run reached a limit or could not fetch some descriptions.

Automatic candidates enter your jobs only when usable posting text exists. Those
still waiting stay in the run's progress and resume by themselves.

Each source row shows what it found, such as "31 found, 9 shortlisted, 3 applied,
1 replied". A source that finds many jobs and few you keep is a candidate to
narrow or pause.

### Request limits

**Providers** shows the shared gate of each portal: on or off, and the minimum
spacing between requests (5 seconds by default). Every request obeys it:
previews, URL imports, scheduled and manual runs, redirects and detail pages. An
HTTP 429 pauses the provider until its retry time; the pause survives restarts.
A login page is reported as blocked. A portal can still block requests or change
its pages; paste the posting when a page cannot be read.

![Sources with saved searches, schedule summaries and results](../images/collection.png)

Source fields and defaults are read from the running server: REST
`GET /api/v1/sources/schemas`, or `collection_get` over MCP.
