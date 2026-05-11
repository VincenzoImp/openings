# Testing

Install dependencies:

```bash
uv sync
```

Run the full suite:

```bash
uv run pytest
```

Run local quality checks:

```bash
uv run pre-commit run --all-files
uv run mypy src/job_search_tool --ignore-missing-imports
```

Targeted examples:

```bash
uv run pytest tests/test_api_server.py -q
uv run pytest tests/test_mcp_server.py -q
uv run pytest tests/test_docker_compose.py -q
```

## Test Policy

- Add tests before behavior changes.
- Keep API/MCP tests focused on adapter behavior; shared filtering and
  serialization belong in `test_job_service.py`.
- Use real temporary SQLite databases for persistence behavior.
- Mock external network scraping and notification delivery.
- Keep Docker Compose validation in tests so deployment drift is caught before
  release.

## CI

CI runs:

- pre-commit and mypy,
- pytest on Python 3.11 and 3.12,
- dependency audit,
- Docker image build and Compose/profile validation for pull requests.
