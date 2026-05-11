# Architecture

Job Search Tool is a local-first, single-user automation system packaged under
`src/job_search_tool`. Docker, local `uv run` commands, CI, and release images
all execute installed entrypoints.

## Runtime Surfaces

| Surface | Module | Role |
|---------|--------|------|
| CLI scheduler | `job_search_tool.main` | scheduled or one-shot job collection |
| Web server | `job_search_tool.web.app` | React dashboard, REST API, MCP mount, health |
| REST routes | `job_search_tool.web.api` | JSON automation under `/api` |
| MCP tools | `job_search_tool.web.mcp` | streamable HTTP tools under `/mcp` |
| Dashboard | `frontend/` | browser UI built into the Docker image |

The scheduler remains a separate process from the web server. Dashboard, REST,
and MCP behavior share the application layer in
`job_search_tool.application.jobs`.

## Data Flow

1. Load `settings.yaml`.
2. Search configured query/site/location combinations through JobSpy.
3. Post-filter and deduplicate results.
4. Score rows with configured keyword weights.
5. Partition rows by `save_threshold` and `notify_threshold`.
6. Save accepted rows to SQLite.
7. Embed saved rows into ChromaDB when vector search is enabled.
8. Notify about new rows above `notify_threshold`.

## Web Flow

1. `job-search-web` starts FastAPI on port 8501.
2. `/` serves the built React dashboard.
3. `/api/*` routes call `JobApplicationService`.
4. `/mcp` mounts FastMCP streamable HTTP tools over the same service layer.
5. `/health` reports process readiness and current job count.

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
MCP tools can generate settings documentation without depending on a source
checkout. Tests assert both copies stay synchronized.
