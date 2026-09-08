# MCP server

`openings web` mounts an MCP server at `/mcp` (streamable HTTP). It exposes
the same application service as the REST API and the dashboard, so an agent
sees and changes exactly what you see.

## Connect

```json
{
  "mcpServers": {
    "openings": { "type": "http", "url": "http://127.0.0.1:8501/mcp" }
  }
}
```

If `OPENINGS_API_TOKEN` is set, `/mcp` requires it like `/api`: send
`Authorization: Bearer <token>` (or `X-Openings-Token`). Requests without it
are answered `401`.

DNS-rebinding protection allows `localhost`, `127.0.0.1` and `[::1]` on any
port. From another device, list the host and origin the client uses:

```dotenv
OPENINGS_WEB_ALLOWED_HOSTS=192.168.1.10:8501
OPENINGS_WEB_ALLOWED_ORIGINS=http://192.168.1.10:8501
```

## Tools

Every tool returns JSON text. Job identifiers are the 64-character `job_id`.
Filters take plural lists (`statuses`, `sources`, `labels`, `job_types`,
`locations`); without `statuses`, blacklisted jobs are left out.

### Read

| Tool | Returns |
|------|---------|
| `list_jobs` | summaries with the same filters as `GET /api/jobs`, `sort`, `direction`, `limit`, `offset` |
| `get_job` | the full job: posting, `explain`, `postings`, labels, notes, attachments, events; `include_raw=false` drops the raw payload, `max_description_chars` trims the description |
| `search_similar` | semantic neighbours of a `query` or of a `job_id` (`n_results`, `min_score`, `source`, `statuses`) |
| `get_statistics` | totals, by status, today's new and seen, average score, blacklisted, attachments, notes |
| `get_score_distribution` | `[bin_start, count]` pairs |
| `get_facets` | distinct values with counts; `limit`, `q` to search a value |
| `list_labels` | every label with its count |
| `list_blacklist` | blacklisted jobs with `text`, `company`, `location`, pagination |
| `list_sources` | configured sources with active job counts and the last run per source |
| `list_runs` | recent collection runs with per-source counts and failures |
| `list_attachments` | attachments across jobs by `kind` and `statuses` |
| `get_attachment` | one attachment as base64 (up to 5 MB) with its metadata |
| `get_settings` | a summary of the live configuration |
| `get_settings_reference` | the annotated `settings.yaml` reference |

### Write

| Tool | Effect |
|------|--------|
| `add_job` | add a posting from digested fields; scored live; default status `shortlisted`; a known URL updates the existing job; refuses blacklisted jobs |
| `update_job` | edit posting fields; the job is rescored |
| `set_status` | move jobs to `new`, `shortlisted`, `applied`, `interviewing`, `offer`, `rejected`, `withdrawn`, with an optional note on the timeline |
| `add_labels`, `remove_labels`, `rename_label` | free tags |
| `add_note`, `update_note`, `delete_note` | `kind` `note` or `qa` (question in `title`, answer in `body`), markdown |
| `add_attachment` | file as base64 with `kind` `cv`, `cover_letter`, `form_answers`, `other` and an optional note |
| `update_attachment`, `delete_attachment` | change kind, note or file name; remove |
| `blacklist_jobs`, `unblacklist_jobs` | hide a job and block its re-ingestion; restore it to its previous status |
| `merge_jobs` | fold duplicate jobs (mirrors on other boards) into one, keeping every posting, note and file |
| `delete_jobs` | delete rows and files without blacklisting |
| `run_now` | ask the scheduler to collect now |
| `preview_cleanup`, `run_cleanup` | the configured retention |
| `export_jobs` | CSV or JSON by ids or filters; `limit=0` for every match |

## A typical agent session

1. `list_jobs(statuses=["new"], min_score=20, sort="score")` to triage the
   inbox; `blacklist_jobs` the noise, `set_status(..., "shortlisted")` the
   rest.
2. `get_job(job_id, include_raw=false)` for the posting text and the score
   breakdown; `search_similar(job_id=...)` for postings you already handled.
3. Tailor the material, then `add_attachment(job_id, "cv.pdf", <base64>,
   kind="cv")` and `add_note(job_id, answer, kind="qa", title=question)`.
4. `set_status([job_id], "applied", note="submitted through the careers page")`.
5. For a posting the crawler did not see: read the page, then `add_job` with
   the digested fields and the URL.

Attachments and notes are the user's own material. Agents should never send
them anywhere the user did not ask for.
