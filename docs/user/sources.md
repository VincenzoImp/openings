# Sources

Every source produces the same job object (title, company, location, URL,
description as markdown, posting date, type, remote flag, level, salary
fields, company URL, the raw payload). Scoring, deduplication, the blacklist
and notifications are shared.

A posting is identified by its URL (LinkedIn, Indeed, Glassdoor, Google and
the ATS feeds reduce to `board:id`; other URLs keep host, path and their
identifying query parameters) or, failing that, by `source:external_id`. A
job is the opening behind one or more postings: the same URL refreshes its
job; an unknown URL whose title, company and location match a job seen on
another source becomes a second posting of that job; anything else is a new
job. Two different postings from the same source stay two jobs, even with the
same title, and `merge_jobs` folds them together when you decide they are
one.

Employment types are folded into one vocabulary whatever the board calls
them: `fulltime`, `parttime`, `contract`, `internship`, `temporary`,
`volunteer`, else `other`.

Runs record per-source counts and failures (`Runs` view, `GET /api/runs`,
`list_runs`). One failing task never aborts the others.

## Job boards (`sources.jobspy`)

[JobSpy](https://github.com/speedyapply/JobSpy) scrapes public board search
pages: LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, Bayt, Naukri,
BDJobs. Boards rate-limit; the defaults (one site, three workers, four
seconds between LinkedIn calls) are conservative. Budget a run as
`queries x locations x job_types` requests and check the duration in Runs.
Google Jobs answers HTTP 429 to most unauthenticated clients.

## Company feeds (`sources.companies`)

Applicant tracking systems with a public JSON feed. No key, complete
descriptions, exact locations. Find the slug in the company's careers URL:

| ATS | `ats:` value | Careers URL | Feed used |
|-----|--------------|-------------|-----------|
| Greenhouse | `greenhouse` | `boards.greenhouse.io/<slug>` (or `job-boards.greenhouse.io/<slug>`) | `boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true` |
| Lever | `lever` | `jobs.lever.co/<slug>` | `api.lever.co/v0/postings/<slug>?mode=json` |
| Ashby | `ashby` | `jobs.ashbyhq.com/<slug>` | `api.ashbyhq.com/posting-api/job-board/<slug>` |
| SmartRecruiters | `smartrecruiters` | `careers.smartrecruiters.com/<Company>` | `api.smartrecruiters.com/v1/companies/<Company>/postings` |
| Workday | `workday` | `<host>.myworkdayjobs.com/<site>` | `POST <host>/wday/cxs/<tenant>/<site>/jobs` |
| join.com | `joincom` | `join.com/companies/<slug>` | the page's own `__NEXT_DATA__` payload |
| Workable | `workable` | `apply.workable.com/<slug>` | `apply.workable.com/api/v1/widget/accounts/<slug>?details=true` |
| Rippling | `rippling` | `ats.rippling.com/<slug>/jobs` | `api.rippling.com/platform/api/ats/v1/board/<slug>/jobs` |
| BambooHR | `bamboohr` | `<slug>.bamboohr.com/careers` | `<slug>.bamboohr.com/careers/list` |
| Oracle Cloud Recruiting | `oracle` | `<host>/hcmUI/CandidateExperience/.../sites/<site>` | `<host>/hcmRestApi/.../recruitingCEJobRequisitions` |
| Personio | `personio` | `<slug>.jobs.personio.de` | `<slug>.jobs.personio.de/xml` |
| Recruitee | `recruitee` | `<slug>.recruitee.com` | `<slug>.recruitee.com/api/offers/` |
| BreezyHR | `breezy` | `<slug>.breezy.hr` | `<slug>.breezy.hr/json` |

Companies whose careers site is built on one of these but served from their
own domain still work: open a posting, look at the network requests or the
"apply" link for the ATS domain and slug.

Three of these need more than a bare slug or carry a caveat worth knowing.

**Workday** and **Oracle Cloud Recruiting** take the whole board address,
`host/site` (for example `abb.wd3.myworkdayjobs.com/External_Career_Page` or
`eipb.fa.em2.oraclecloud.com/CX_5`), because the tenant, the datacenter and the
site name vary independently; copy it from the careers URL. Both refuse a slug
without a site rather than guessing at one.

**join.com** publishes no documented API, so its adapter reads the JSON the
page ships to the browser. That is a scrape: it fails loudly if join.com
changes its page shape, rather than silently returning nothing.

**Personio**'s feed is public but must be switched on by the employer
(Settings > Recruiting > Career page). A tenant that never enabled it answers
with the career site's HTML, which surfaces as `response is not XML`. Personio
also rate-limits non-browser clients aggressively; an occasional `HTTP 429` in
the run summary is the board throttling, not a broken adapter.

**BreezyHR** publishes no description anywhere public: the feed carries none and
the posting page is client-rendered. Its postings arrive with title, company,
location, salary and URL but no body, so they are scored on the title alone.
Set a lower `save_threshold` for a Breezy board, or expect to lose them.

### Finding companies to add

No ATS publishes a directory of its customers, so every list is
community-scraped. These are the ones worth starting from:

- [kalil0321/ats-scrapers](https://github.com/kalil0321/ats-scrapers) —
  `ats-companies/*.csv`, one file per ATS with name, slug and URL. The widest
  coverage: join.com (23.5k), Greenhouse (6k), BambooHR (5.6k), Workable (4.8k),
  Workday (3.5k), Ashby (3.4k), SmartRecruiters (2.7k), JazzHR, iCIMS, Oracle,
  Rippling, Paycom, Lever.
- [Feashliaa/job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator)
  — `data/*_companies.json` for Greenhouse, Ashby, Lever and Workday, refreshed
  daily by CI, plus the postings themselves.
- [blakegrudzien/find-jobs](https://github.com/blakegrudzien/find-jobs) — four
  plain `companies_*.txt` slug lists, small and easy to diff.

A slug list is a starting point, not an answer: roughly 40 percent of the
published slugs are dead or private, and of those that answer only a small
fraction post anywhere near you. Screen a list once, offline, against the
locations you would actually accept, and configure what survives. Adding
boards wholesale is the wrong move in any case: companies are fetched
sequentially each run.

Probe a feed before adding it:

```bash
curl -s 'https://boards-api.greenhouse.io/v1/boards/<slug>/jobs' | head -c 300
```

`locations` and `titles` are lists of substrings matched case-insensitively
against the posting's location and title; omit them to keep everything. A
posting without a location passes the location filter and lets scoring
decide. Postings older than `max_age_days` (or `sources.feed_max_age_days`)
by their own date are dropped, so long-lived boards do not flood the Inbox
with evergreen roles. SmartRecruiters listings are filtered before their details are
fetched, and details are fetched only for postings not already stored, so a
narrow list keeps the run short.

iCIMS, SAP SuccessFactors, JazzHR, Jobvite, Teamtailor, softgarden and other
JavaScript-rendered careers pages are not supported: they publish no machine-
readable feed, and a per-vendor scraper of themed markup breaks silently rather
than loudly. Add those postings by hand or through an agent.

## JobCloud (`sources.jobcloud`)

JobCloud runs several regional job boards from one engine, so the host is
configuration rather than a constant: `www.jobs.ch` and `www.jobup.ch` are the
same API, and a second configured source costs no code. The search is public
and needs no key.

```yaml
sources:
  jobcloud:
    enabled: true
    host: "www.jobs.ch"
    queries: ["software engineer", "data engineer"]
    locations: ["Zurich", "Bern"]
    rows: 50           # results per page
    max_pages: 3       # pages per query and location
    max_details: 100   # per-posting description fetches per run
```

The search returns a truncated preview, so the full copy needs one extra
request per posting; `max_details` caps that, and postings are deduplicated
across queries before any detail is fetched. `rows`, `max_pages` and
`max_details` are also clamped in code, because the board has thousands of
result pages and a generous setting should not become thousands of requests.

### The language line

Where JobCloud reports a language requirement structurally, the adapter
prepends one canonical line to the description:

```
Required languages: German (level 3), English (level 2)
```

The level is whatever the board reported; no scale is invented and no
judgement is made about whether a requirement disqualifies you. That is a
scoring decision, so match the line from your own configuration:

```yaml
scoring:
  keywords:
    language_required:
      terms: ["required languages: german"]
      match_in: ["description"]
```

Matching a field the employer filled in is far more reliable than hunting for
phrasings in free text, which is the usual way this goes wrong.

## Feeds (`sources.feeds`)

Any RSS or Atom feed. Title, link, description or content, publication date
and, when present, `company`/`author` and `location` fields are read. Many
boards, universities and public bodies publish one. `titles` keeps a broad
feed to the roles you want.

## Adzuna (`sources.adzuna`)

A keyed search API covering about twenty countries
([developer.adzuna.com](https://developer.adzuna.com)). Descriptions are
snippets, so scores are lower than for other sources of the same posting;
tune `weights` or the thresholds with that in mind. Set `app_id` and
`app_key` through environment variables.

## By hand (`manual`)

`POST /api/jobs`, the MCP tool `add_job`, or the dashboard's "Add posting"
create a job from digested fields. It is scored with the live configuration,
lands in the given status (default `shortlisted`, so retention never removes
it) and is refused if the job is blacklisted. A URL that is already known
updates that job's posting fields instead of creating a second one. The
source is recorded as `manual` unless the caller names another.
