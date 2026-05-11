# MCP Server

MCP tools are mounted by the unified web server. They share the same SQLite
database and vector store used by the scheduler, dashboard, and REST API.

## Start

Docker Compose:

```bash
docker compose up -d
```

Local Python:

```bash
uv run job-search-web
```

Default endpoint:

```text
http://127.0.0.1:8501/mcp
```

## Transport

The MCP server exposes streamable HTTP at `/mcp`.

## LAN Use

The web server binds to `127.0.0.1` by default. To use MCP from another trusted
LAN device:

```dotenv
JOB_SEARCH_WEB_BIND=0.0.0.0
JOB_SEARCH_WEB_ALLOWED_HOSTS=192.168.1.10:8501
JOB_SEARCH_WEB_ALLOWED_ORIGINS=http://192.168.1.10:8501
```

Then configure your MCP host with:

```text
http://192.168.1.10:8501/mcp
```

MCP tools can read and mutate job state, including bookmarks, applied state, and
blacklisting. Do not expose the web port to untrusted networks.

## Tools

Read tools:

- `list_jobs`
- `get_job`
- `search_similar`
- `get_statistics`
- `get_score_distribution`
- `get_settings_documentation`

Write tools:

- `set_bookmarked`
- `set_applied`
- `blacklist_jobs`
- `preview_cleanup`
- `run_cleanup`

`get_settings_documentation` is generated from the packaged settings template,
which is kept in sync with `config/settings.example.yaml`. The MCP server does
not read private profile data from the user's live `settings.yaml` for prompt
context.
