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

If `OPENINGS_API_TOKEN` is set, the MCP client must send it as
`Authorization: Bearer <token>`.

DNS-rebinding protection allows `localhost`, `127.0.0.1` and `[::1]` on any
port. From another device, list the host and origin the client uses:

```dotenv
OPENINGS_WEB_ALLOWED_HOSTS=192.168.1.10:8501
OPENINGS_WEB_ALLOWED_ORIGINS=http://192.168.1.10:8501
```

## Tools

Every tool returns JSON text. Job identifiers are the 64-character `job_id`.

### Read

| Tool | Returns |
|------|---------|
| `list_jobs` | summaries with `statuses`, `sources`, `labels`, `company`, `location`, `job_types`, `remote`, score and salary bounds, date ranges, `text`, `sort`, `limit`, `offset` |
| `get_job` | the full job: posting, `explain`, labels, notes, attachments, events |
| `search_similar` | semantic neighbours of a query (`n_results`, `min_score`, `source`) |
| `get_statistics` | totals, by status, today's new and seen, average score, blacklist size |
| `get_score_distribution` | `[bin_start, count]` pairs |
| `get_facets` | distinct values with counts |
| `list_blacklist` | entries with `text`, `company`, `location`, pagination |
| `list_sources` | configured sources with active job counts |
| `list_runs` | recent collection runs with per-source counts and failures |
| `get_settings_reference` | the annotated `settings.yaml` reference |

### Write

| Tool | Effect |
|------|--------|
| `add_job` | add a posting from digested fields; scored live; default status `shortlisted`; refuses blacklisted identities |
| `set_status` | move jobs to `new`, `shortlisted`, `applied`, `interviewing`, `offer`, `rejected`, `withdrawn`, with an optional note on the timeline |
| `add_labels`, `remove_labels` | free tags |
| `add_note` | `kind` `note` or `qa` (question in `title`, answer in `body`), markdown |
| `add_attachment` | file as base64 with `kind` `cv`, `cover_letter`, `form_answers`, `other` and an optional note |
| `delete_attachment` | |
| `blacklist_jobs`, `unblacklist_jobs` | suppress or lift by identity |
| `delete_jobs` | delete rows and files without blacklisting |
| `preview_cleanup`, `run_cleanup` | the configured retention |
| `export_jobs` | CSV or JSON by ids or filters; `limit=0` for every match |

## A typical agent session

1. `list_jobs(statuses=["new"], min_score=20, sort="score")` to triage the
   inbox; `blacklist_jobs` the noise, `set_status(..., "shortlisted")` the
   rest.
2. `get_job(job_id)` for the posting text and the score breakdown.
3. Tailor the material, then `add_attachment(job_id, "cv.pdf", <base64>,
   kind="cv")` and `add_note(job_id, answer, kind="qa", title=question)`.
4. `set_status([job_id], "applied", note="submitted through the careers page")`.
5. For a posting the crawler did not see: read the page, then `add_job` with
   the digested fields and the URL.

Attachments and notes are the user's own material. Agents should never send
them anywhere the user did not ask for.
