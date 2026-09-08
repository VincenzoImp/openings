# Sources

Every source produces the same job object (title, company, location, URL,
description as markdown, posting date, type, remote flag, level, salary
fields, company URL, the raw payload). Scoring, deduplication, the blacklist
and notifications are shared. A job seen by two sources is one job.

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

`locations` is a list of substrings matched case-insensitively against the
posting's location; omit it to keep everything. SmartRecruiters listings are
filtered by location before their details are fetched, so a narrow list also
keeps the run short.

Workday, SAP SuccessFactors and JavaScript-rendered careers pages are not
supported; add those postings by hand or through an agent.

## Feeds (`sources.feeds`)

Any RSS or Atom feed. Title, link, description or content, publication date
and, when present, `company`/`author` and `location` fields are read. Many
boards, universities and public bodies publish one.

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
it) and is refused if its identity is blacklisted. The source is recorded as
`manual` unless the caller names another.
