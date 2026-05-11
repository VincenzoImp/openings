# Architecture

Job Search Tool is a local-first, single-user automation system packaged under
`src/job_search_tool`. Docker, local `uv run` commands, CI, and release images
all execute the same installed entrypoints.

## Runtime Surfaces

| Surface | Module | Role |
|---------|--------|------|
| CLI scheduler | `job_search_tool.main` | scheduled or one-shot job collection |
| Dashboard | `job_search_tool.dashboard` | human review and curation |
| REST API | `job_search_tool.api_server` | programmatic local automation |
| MCP | `job_search_tool.mcp_server` | LLM tool integration |

The dashboard, API, and MCP adapter share common behavior through
`job_search_tool.job_service`.

## Data Flow

1. Load `settings.yaml`.
2. Search configured query/site/location combinations through JobSpy.
3. Post-filter and deduplicate results.
4. Score rows with configured keyword weights.
5. Partition rows by `save_threshold` and `notify_threshold`.
6. Save accepted rows to SQLite.
7. Embed saved rows into ChromaDB when vector search is enabled.
8. Notify about new rows above `notify_threshold`.

## Persistence

`JOB_SEARCH_DATA_DIR` owns all runtime state:

- `config/settings.yaml`
- `db/jobs.db`
- `chroma/`
- `results/`
- `logs/search.log`

Docker defaults this root to `/data`. Local development defaults to the repo
root unless overridden.

## Configuration Contract

`config/settings.example.yaml` is the user-facing configuration reference. The
same template is also packaged under `job_search_tool.defaults` so installed
API and MCP entrypoints can generate settings documentation without depending
on a source checkout. Tests assert both copies stay synchronized.

## Current Documentation

The deeper system audit lives in `docs/developer/current-system/`. It documents
current behavior, known risks, and the problem model.
