# MCP Server

The MCP server exposes job-search tools to MCP-compatible hosts. It shares the
same SQLite database and vector store used by the scheduler, dashboard, and API.

## Start

Docker Compose:

```bash
docker compose --profile mcp up -d
```

Local Python:

```bash
uv run job-search-mcp
```

Default endpoint:

```text
http://127.0.0.1:3001/mcp
```

## Transport

The MCP server exposes streamable HTTP at `/mcp`.

## LAN Use

Compose binds MCP to `127.0.0.1` by default. To use it from another device on a
trusted LAN:

```dotenv
JOB_SEARCH_MCP_BIND=0.0.0.0
```

Then configure your MCP host with:

```text
http://<machine-ip>:3001/mcp
```

MCP tools can read and mutate job state, including bookmarks, applied state, and
deletions. Do not expose the port to untrusted networks.

## Tools

Read tools:

- `list_jobs`
- `get_job`
- `search_similar`
- `get_statistics`
- `get_score_distribution`
- `get_settings_documentation`

Write tools:

- `bookmark_job`
- `apply_job`
- `delete_job`
- `delete_jobs_below_score`

`get_settings_documentation` is generated from the packaged settings template,
which is kept in sync with `config/settings.example.yaml`. The MCP server does
not read private profile data from the user's live `settings.yaml` for prompt
context.
