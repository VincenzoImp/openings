# Contributing to Job Search Tool

Thank you for your interest in contributing to the Job Search Tool. This document provides guidelines and best practices for contributing to the project.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Architecture Overview](#architecture-overview)
- [Common Contribution Scenarios](#common-contribution-scenarios)

---

## Getting Started

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Recommended local version; CI runs on 3.11 and 3.12 |
| Docker | 20.10+ | Optional, recommended for testing |
| Git | 2.30+ | Version control |

### Initial Setup

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/job-search-tool.git
cd job-search-tool

# 3. Add upstream remote
git remote add upstream https://github.com/VincenzoImp/job-search-tool.git

# 4. Install uv if needed: https://docs.astral.sh/uv/getting-started/installation/

# 5. Create/sync the project environment from the lockfile
#    (includes streamlit for the dashboard test suite)
uv sync --locked

# 6. Create configuration for local Python runs. The Docker runtime
#    requires an explicit settings.yaml too, but it lives inside the
#    named volume and is managed via `docker volume` — this copy is only
#    for local `uv run python scripts/main.py ...` development.
cp config/settings.example.yaml config/settings.yaml

# 7. Verify setup
uv run pre-commit run --all-files
uv run mypy scripts/ --ignore-missing-imports
uv run pytest
```

---

## Development Environment

### Directory Structure

```
job-search-tool/
├── scripts/          # Python source code
├── tests/            # Test suite
├── config/           # Configuration files
├── results/          # Output (gitignored)
├── data/             # Database (gitignored)
└── logs/             # Logs (gitignored)
```

### Running the Application

```bash
# Continuous scheduler (default)
uv run python scripts/main.py
# Same, explicit subcommand
uv run python scripts/main.py scheduler
# Single-shot run (cron / CI)
uv run python scripts/main.py once
# Streamlit dashboard on http://localhost:8501
uv run python scripts/main.py dashboard

# Published Docker Hub image
docker compose pull
docker compose up -d                              # starts scheduler + dashboard

# Local build of the current checkout
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

### Development Tools

```bash
# Type checking
uv run mypy scripts/ --ignore-missing-imports

# Linting + formatting + repo hygiene
uv run pre-commit run --all-files

# All tests
uv run pytest

# Coverage report
uv run pytest --cov=scripts --cov-report=html
```

---

## Code Standards

### Python Style

We follow PEP 8 with the following specifics:

| Aspect | Standard |
|--------|----------|
| Line length | 88 characters (Ruff default) |
| Quotes | Double quotes for strings |
| Imports | Sorted with ruff, grouped |
| Docstrings | Google style |

### Type Hints

All public functions must have type hints:

```python
def calculate_score(job: dict, config: Config) -> int:
    """
    Calculate relevance score for a job.

    Args:
        job: Job data dictionary.
        config: Configuration object.

    Returns:
        Integer relevance score.
    """
    pass
```

### Docstrings

Use Google style docstrings:

```python
def function_name(param1: str, param2: int = 10) -> bool:
    """
    Brief description of function.

    Longer description if needed. Can span multiple lines
    and include additional context.

    Args:
        param1: Description of param1.
        param2: Description of param2. Defaults to 10.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is empty.
    """
    pass
```

### Error Handling

```python
# Specific exceptions
try:
    result = risky_operation()
except ConnectionError:
    logger.error("Network connection failed")
    raise
except ValueError as e:
    logger.warning(f"Invalid value: {e}")
    return default_value

# Avoid bare except
# BAD: except:
# GOOD: except Exception as e:
```

### Logging

```python
from logger import get_logger

logger = get_logger(__name__)

# Use appropriate levels
logger.debug("Detailed debugging info")
logger.info("General progress updates")
logger.warning("Something unexpected but handled")
logger.error("Error that needs attention")
```

---

## Testing Requirements

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures + global state reset
├── test_models.py       # Data model tests
├── test_config.py       # Configuration tests
├── test_database.py     # Database operation tests
├── test_scoring.py      # Scoring function tests
├── test_main.py         # Entry point tests
├── test_notifier.py     # Notification tests
├── test_scheduler.py    # Scheduler lifecycle tests
├── test_logger.py       # Logger tests
├── test_exporter.py     # CSV/Excel export tests
├── test_healthcheck.py  # Health check tests
├── test_report_generator.py  # Report generation tests
├── test_analyze_jobs.py      # Analysis utility tests
├── test_search_jobs.py       # Search engine tests
└── test_vector_store.py      # Vector store tests
```

### Writing Tests

```python
import pytest
from models import Job

class TestJob:
    """Tests for Job dataclass."""

    def test_job_id_generation(self):
        """Job ID should be SHA256 hash of title+company+location."""
        job = Job(
            title="Software Engineer",
            company="TechCorp",
            location="Remote",
        )
        assert len(job.job_id) == 64
        assert job.job_id.isalnum()

    def test_job_id_deterministic(self):
        """Same inputs should produce same job ID."""
        job1 = Job(title="Dev", company="Co", location="NYC")
        job2 = Job(title="Dev", company="Co", location="NYC")
        assert job1.job_id == job2.job_id

    @pytest.mark.parametrize("title,expected", [
        ("", "empty-title-hash"),
        ("Test", "valid-hash"),
    ])
    def test_edge_cases(self, title, expected):
        """Test edge cases for job ID generation."""
        # Test implementation
        pass
```

### Test Coverage

Aim for high coverage on critical modules:

| Module | Target Coverage |
|--------|-----------------|
| models.py | 95%+ |
| config.py | 90%+ |
| database.py | 85%+ |
| search_jobs.py | 80%+ |

### Running Tests

```bash
# All tests
uv run pytest

# Specific file
uv run pytest tests/test_config.py

# Specific test
uv run pytest tests/test_models.py::TestJob::test_job_id_generation

# With coverage
uv run pytest --cov=scripts --cov-report=html

# Verbose output
uv run pytest -v

# Stop on first failure
uv run pytest -x
```

---

## Pull Request Process

### Branch Naming

```
feature/description-of-feature
fix/description-of-bug
docs/what-was-documented
refactor/what-was-refactored
```

### Commit Messages

Follow conventional commits:

```
type(scope): brief description

Longer description if needed. Explain what and why,
not how (the code shows how).

Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### PR Checklist

Before submitting:

- [ ] Code follows style guidelines
- [ ] Type hints added for new functions
- [ ] Docstrings added for public functions
- [ ] Tests written for new functionality
- [ ] All tests pass (`uv run pytest`)
- [ ] Type check passes (`uv run mypy scripts/ --ignore-missing-imports`)
- [ ] Pre-commit passes (`uv run pre-commit run --all-files`)
- [ ] Documentation updated if needed
- [ ] Docker-related changes were sanity-checked with `docker compose config`

### Review Process

1. Open PR against `main` branch
2. Ensure CI checks pass
3. Request review from maintainers
4. Address feedback
5. Maintainer merges when approved

---

## Issue Guidelines

### Bug Reports

Include:

1. **Summary**: Brief description of the issue
2. **Environment**: OS, Python version, Docker version
3. **Steps to Reproduce**: Numbered list of steps
4. **Expected Behavior**: What should happen
5. **Actual Behavior**: What actually happens
6. **Logs**: Relevant output from `logs/search.log`
7. **Configuration**: Relevant settings (redact secrets)

### Feature Requests

Include:

1. **Problem Statement**: What problem does this solve?
2. **Proposed Solution**: How would it work?
3. **Alternatives Considered**: Other approaches?
4. **Implementation Notes**: Any technical considerations?

---

## Architecture Overview

### Core Modules

| Module | Responsibility |
|--------|---------------|
| `main.py` | Entry point, orchestration |
| `search_jobs.py` | Job search execution |
| `scheduler.py` | Periodic scheduling |
| `notifier.py` | Notification delivery |
| `database.py` | Data persistence |
| `config.py` | Configuration loading |
| `models.py` | Data structures |
| `scoring.py` | Relevance scoring |
| `exporter.py` | CSV/Excel export |
| `vector_store.py` | Semantic search |
| `vector_commands.py` | Vector backfill/sync |

### Data Flow

```
Configuration → Search Engine → Scoring → Database → Notifications
                     ↑                        |            ↓
                     └── Deduplication ───────┘      Vector Store
```

### Extension Points

1. **Notification Channels**: Implement `BaseNotifier`
2. **Scoring Categories**: Add to YAML config
3. **Job Sources**: Extend JobSpy integration
4. **Output Formats**: Add export functions

---

## Common Contribution Scenarios

### Adding a Scoring Category

No code changes needed:

```yaml
# config/settings.yaml
scoring:
  weights:
    new_category: 15
  keywords:
    new_category:
      - "keyword1"
      - "keyword2"
```

### Adding a Database Column

1. Add to `CREATE_TABLE` in `database.py`
2. Add to `MIGRATE_COLUMNS` list
3. Update SQL queries
4. Add to `JobDBRecord` dataclass
5. Update serialization methods
6. Add tests

### Adding a Notification Channel

1. Create class extending `BaseNotifier`:

```python
class SlackNotifier(BaseNotifier):
    async def send_notification(self, data: NotificationData) -> bool:
        # Implementation
        pass

    def is_configured(self) -> bool:
        return bool(self.config.webhook_url)
```

2. Add configuration dataclass
3. Register in `NotificationManager`
4. Add tests
5. Update documentation

### Adding a Configuration Option

1. Add to appropriate dataclass in `config.py`
2. Add parsing logic with validation
3. Add to `settings.example.yaml` with documentation
4. Add tests
5. Update CLAUDE.md

---

## Questions?

- **General questions**: Open a GitHub issue
- **Bug reports**: Use the bug report template
- **Feature requests**: Use the feature request template

Thank you for contributing!
