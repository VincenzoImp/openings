# REST API

Base URL: `http://127.0.0.1:8501/api`. Every route returns JSON except the
export and attachment downloads.

## Authentication

Without `OPENINGS_API_TOKEN` the API is open to whoever can reach the port.
With it, send the token as either header:

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
| `POST` | `/jobs` | add a posting by hand (`201`, `409` if blacklisted) |
| `GET` | `/jobs/{job_id}` | full job: posting, `explain`, labels, notes, attachments, events |
| `POST` | `/jobs/status` | `{job_ids, status, note?}` |
| `POST` | `/jobs/labels` | `{job_ids, labels}` add |
| `POST` | `/jobs/labels/remove` | `{job_ids, labels}` remove |
| `POST` | `/jobs/delete` | `{job_ids}` delete rows and their files |
| `GET` | `/jobs/facets` | distinct values with counts: statuses, sources, companies, locations, job types, labels |
| `GET` | `/jobs/search/semantic?q=` | vector search; `503` when the index is unavailable |

`GET /jobs` filters (repeat a key for several values): `status`, `source`,
`label`, `company`, `location`, `locations`, `job_type`, `remote`,
`min_score`, `max_score`, `min_salary`, `max_salary`, `date_posted_from/to`,
`first_seen_from/to`, `last_seen_from/to`, `text`, `sort` (`score`, `date`,
`first_seen`, `updated`, `company`, `title`, `salary`), `limit` (max 1000),
`offset`.

```bash
curl -s 'http://127.0.0.1:8501/api/jobs?status=new&min_score=20&sort=score&limit=20'
```

`POST /jobs` body: `title`, `company` (required), `location`, `job_url`,
`description` (markdown), `date_posted`, `job_type`, `is_remote`,
`job_level`, `min_amount`, `max_amount`, `currency`, `salary_interval`,
`company_url`, `source`, `external_id`, `status` (default `shortlisted`),
`labels`, `note`. The job is scored with the live configuration. Adding a
posting that already exists updates its fields and leaves its status alone.

## Notes and attachments

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/jobs/{job_id}/notes` | `{kind: note|qa, title?, body}` (`qa`: question in `title`, answer in `body`) |
| `DELETE` | `/jobs/{job_id}/notes/{note_id}` | |
| `POST` | `/jobs/{job_id}/attachments` | multipart: `file`, `kind` (`cv`, `cover_letter`, `form_answers`, `other`), `note?` |
| `GET` | `/jobs/{job_id}/attachments/{id}` | download |
| `DELETE` | `/jobs/{job_id}/attachments/{id}` | |

```bash
curl -s -F file=@cv.pdf -F kind=cv -F note='tailored' \
  http://127.0.0.1:8501/api/jobs/<job_id>/attachments
```

Uploads above `attachments.max_size_mb` return `413`.

## Blacklist

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/blacklist` | entries; `text`, `company`, `location`, `limit`, `offset` |
| `POST` | `/blacklist` | `{job_ids}`: delete the jobs and block re-ingestion |
| `POST` | `/blacklist/remove` | `{job_ids}`: lift the block (the row is not restored) |
| `POST` | `/blacklist/purge` | `{older_than_days?}` |

## Sources, runs, statistics

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/sources` | configured sources with active job counts |
| `GET` | `/runs?limit=` | collection runs, newest first, with per-source counts and errors |
| `GET` | `/stats` | totals, counts by status, today's new and seen, average score, blacklist size |
| `GET` | `/distribution?bin_size=` | `[bin_start, count]` pairs |

## Export and cleanup

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/export/jobs?format=csv|json&...` | same filters as `GET /jobs`; `limit=0` exports every match |
| `POST` | `/export/jobs` | `{format, job_ids}` or `{format, filters}` |
| `GET` | `/cleanup/preview` | what the configured retention would delete |
| `POST` | `/cleanup/run` | apply it |
| `POST` | `/cleanup/delete-below-score` | `{score}`; `new` rows only |
| `POST` | `/cleanup/delete-stale` | `{days}`; `new` rows only |
| `POST` | `/cleanup/purge-blacklist` | `{older_than_days?}` |

Export responses carry `X-Openings-Export-Rows` and
`X-Openings-Export-Total`.

## Health

`GET /health` (no token) reports the process, database and vector index
state; the container health check runs `openings healthcheck` separately.
