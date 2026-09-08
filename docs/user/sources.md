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

| ATS | Careers URL | Feed used |
|-----|-------------|-----------|
| Greenhouse | `boards.greenhouse.io/<slug>` (or `job-boards.greenhouse.io/<slug>`) | `boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true` |
| Lever | `jobs.lever.co/<slug>` | `api.lever.co/v0/postings/<slug>?mode=json` |
| Ashby | `jobs.ashbyhq.com/<slug>` | `api.ashbyhq.com/posting-api/job-board/<slug>` |
| SmartRecruiters | `careers.smartrecruiters.com/<Company>` | `api.smartrecruiters.com/v1/companies/<Company>/postings` |

Companies whose careers site is built on one of these but served from their
own domain still work: open a posting, look at the network requests or the
"apply" link for the ATS domain and slug.

Probe a feed before adding it:

```bash
curl -s 'https://boards-api.greenhouse.io/v1/boards/<slug>/jobs' | head -c 300
```

`locations` and `titles` are lists of substrings matched case-insensitively
against the posting's location and title; omit them to keep everything. A
posting without a location passes the location filter and lets scoring
decide. SmartRecruiters listings are filtered before their details are
fetched, and details are fetched only for postings not already stored, so a
narrow list keeps the run short.

Workday, SAP SuccessFactors and JavaScript-rendered careers pages are not
supported; add those postings by hand or through an agent.

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
