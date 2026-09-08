# REST API

Base URL: `http://127.0.0.1:8501/api`. Every route returns JSON except the
export, the attachment download and the bundle. Timestamps are ISO 8601 with
an offset (`2026-09-08T06:00:00+00:00`); dates are `YYYY-MM-DD`.

## Authentication

Without `OPENINGS_API_TOKEN` the API is open to whoever can reach the port.
With it, send the token as either header on `/api` and `/mcp`:

```text
Authorization: Bearer <token>
X-Openings-Token: <token>
```

`GET /api/dashboard/auth` is always public and returns
`{"token_required": true|false}` so clients can decide whether to prompt.

## Jobs

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/jobs` | list summaries, filtered and paginated |
| `POST` | `/jobs` | add a posting by hand (`201` created, `200` when the posting already existed and was updated, `409` if blacklisted) |
| `GET` | `/jobs/{job_id}` | full job: posting fields, `explain`, `postings`, labels, notes, attachments, events |
| `PATCH` | `/jobs/{job_id}` | edit posting fields (title, company, location, URL, description, dates, type, remote, level, salary, company URL); the job is rescored |
| `POST` | `/jobs/status` | `{job_ids, status, note?}` |
| `POST` | `/jobs/labels` | `{job_ids, labels}` add |
| `POST` | `/jobs/labels/remove` | `{job_ids, labels}` remove |
| `POST` | `/jobs/merge` | `{primary_id, other_ids}`: move postings, labels, notes, files and timeline into the primary job and delete the others |
| `POST` | `/jobs/delete` | `{job_ids}` delete rows and their files |
| `GET` | `/jobs/facets?limit=&q=` | distinct values with counts: statuses, sources, companies, locations, job types, labels |
| `GET` | `/jobs/search/semantic?q=` | semantic search (`n_results`, `min_score`, `source`, `statuses`); `503` when embeddings are unavailable |
| `GET` | `/jobs/{job_id}/similar?n_results=` | the nearest jobs by embedding |
| `GET` | `/jobs/{job_id}/bundle.zip` | the application as one archive: posting, notes, Q&A, timeline, `job.json`, every attachment |

Summaries carry `postings_count`, `notes_count` and `attachments_count`.

`GET /jobs` filters (repeat a key for several values): `statuses`, `sources`,
`labels`, `company`, `location`, `locations`, `job_types`, `remote`,
`min_score`, `max_score`, `min_salary`, `max_salary`, `date_posted_from/to`,
`first_seen_from/to`, `last_seen_from/to`, `status_changed_from/to`,
`has_attachments`, `without_labels`, `text` (title, company, location,
description and notes), `sort` (`score`, `date`, `first_seen`, `updated`,
`company`, `title`, `salary`), `direction` (`asc`, `desc`), `limit` (max
1000), `offset`. Without `statuses` every status except `blacklisted` is
listed; name it to include blacklisted jobs. Unknown statuses are `422`.

```bash
curl -s 'http://127.0.0.1:8501/api/jobs?statuses=new&min_score=20&sort=score&limit=20'
```

`POST /jobs` body: `title`, `company` (required), `location`, `job_url`,
`description` (markdown), `date_posted`, `job_type`, `is_remote`,
`job_level`, `min_amount`, `max_amount`, `currency`, `salary_interval`,
`company_url`, `source`, `external_id`, `status` (default `shortlisted`),
`labels`, `note`. The job is scored with the live configuration. Adding a
posting whose URL is already known merges the given fields into that job and
leaves its status alone.

## Notes and attachments

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/jobs/{job_id}/notes` | `{kind: note|qa, title?, body}` (`qa`: question in `title`, answer in `body`) |
| `PUT` | `/jobs/{job_id}/notes/{note_id}` | `{kind?, title?, body?}` |
| `DELETE` | `/jobs/{job_id}/notes/{note_id}` | |
| `POST` | `/jobs/{job_id}/attachments` | multipart: `file`, `kind` (`cv`, `cover_letter`, `form_answers`, `other`), `note?` |
| `GET` | `/jobs/{job_id}/attachments/{id}` | download; `?inline=true` for an inline disposition |
| `PATCH` | `/jobs/{job_id}/attachments/{id}` | `{kind?, note?, filename?}` |
| `DELETE` | `/jobs/{job_id}/attachments/{id}` | |
| `GET` | `/attachments?kind=&statuses=&limit=&offset=` | every attachment across jobs, with the job title and company |

```bash
curl -s -F file=@cv.pdf -F kind=cv -F note='tailored' \
  http://127.0.0.1:8501/api/jobs/<job_id>/attachments
```

Uploads above `attachments.max_size_mb` return `413`.

## Labels

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/labels` | every label with its job count |
| `POST` | `/labels/rename` | `{old, new}` |
| `POST` | `/labels/delete` | `{label}` |

## Blacklist

Blacklisting is a status. The job stays in the database with its notes,
files and timeline, disappears from every list, facet, statistic and export
unless `statuses` names it, and is never refreshed or re-created by a run.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/blacklist` | blacklisted jobs; `text`, `company`, `location`, `limit`, `offset` |
| `POST` | `/blacklist` | `{job_ids, note?}` |
| `POST` | `/blacklist/remove` | `{job_ids}`: restore each job to the status it held before |

## Sources, companies, runs

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/sources` | configured sources with active job counts and the last run's per-source result |
| `GET` | `/companies/{company}/statuses` | job counts by status for one employer |
| `GET` | `/runs?limit=` | collection runs, newest first, with per-source counts and errors; an open run has `running: true` |
| `GET` | `/runs/status` | `{running, run, requested}` |
| `POST` | `/runs` | ask the scheduler to collect now (`202`); it starts within 30 seconds |

## Statistics and settings

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/stats` | totals, counts by status, today's new and seen, average score, blacklisted, attachments, notes |
| `GET` | `/distribution?bin_size=` | `[bin_start, count]` pairs |
| `GET` | `/settings` | a summary of the live configuration: profile, thresholds, scheduler, sources, embeddings, limits |
| `GET` | `/settings/reference` | the annotated `settings.yaml` reference as text |

## Export and cleanup

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/export/jobs?format=csv|json&...` | same filters as `GET /jobs`; `limit=0` exports every match |
| `POST` | `/export/jobs` | `{format, job_ids}` or `{format, filters}` |
| `GET` | `/cleanup/preview` | what the configured retention would delete |
| `POST` | `/cleanup/run` | apply it |
| `POST` | `/cleanup/delete-below-score` | `{score, dry_run?}`; `new` rows only |
| `POST` | `/cleanup/delete-stale` | `{days, dry_run?}`; `new` rows only |

Export responses carry `X-Openings-Export-Rows` and
`X-Openings-Export-Total`. With `dry_run: true` the cleanup routes only count.

## Health

`GET /health` (no token) reports the process, database and embeddings state;
the container health check runs `openings healthcheck` separately.
