# Testing

Install dependencies:

```bash
uv sync
npm --prefix frontend install
```

Run the backend suite:

```bash
uv run pytest
```

Run frontend checks:

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Run local quality checks:

```bash
uv run pre-commit run --all-files
uv run mypy src/job_search_tool --ignore-missing-imports
```

Targeted examples:

```bash
uv run pytest tests/test_web_api.py -q
uv run pytest tests/test_web_mcp.py -q
uv run pytest tests/test_docker_compose.py -q
uv run pytest tests/test_documentation_runtime.py -q
```

## Test Policy

- Add tests before behavior changes.
- Keep API/MCP tests focused on adapter behavior; shared command/query behavior
  belongs in `tests/test_application_jobs.py`.
- Use real temporary SQLite databases for persistence behavior.
- Mock external network scraping and notification delivery.
- Keep Docker Compose and documentation validation in tests so deployment drift
  is caught before release.

## CI

CI runs:

- pre-commit and mypy,
- pytest on Python 3.11 and 3.12,
- dependency audit,
- Docker image build and unified web smoke tests for pull requests.
