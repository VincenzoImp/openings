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
| Python | 3.10+ | Required by JobSpy library |
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

# 4. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 5. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 6. Create configuration
cp config/settings.example.yaml config/settings.yaml

# 7. Verify setup
pytest
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
# Single search
cd scripts && python main.py

# With Docker
docker compose up --build

# Dashboard
streamlit run scripts/dashboard.py
```

### Development Tools

```bash
# Type checking
mypy scripts/

# Linting
ruff check scripts/

# Formatting
black scripts/

# All tests
pytest

# Coverage report
pytest --cov=scripts --cov-report=html
```

---

## Code Standards

### Python Style

We follow PEP 8 with the following specifics:

| Aspect | Standard |
|--------|----------|
| Line length | 88 characters (Black default) |
| Quotes | Double quotes for strings |
| Imports | Sorted with isort, grouped |
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
├── conftest.py          # Shared fixtures
├── test_models.py       # Data model tests
├── test_config.py       # Configuration tests
├── test_database.py     # Database operation tests
└── test_scoring.py      # Scoring function tests
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
pytest

# Specific file
pytest tests/test_config.py

# Specific test
pytest tests/test_models.py::TestJob::test_job_id_generation

# With coverage
pytest --cov=scripts --cov-report=html

# Verbose output
pytest -v

# Stop on first failure
pytest -x
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
- [ ] All tests pass (`pytest`)
- [ ] Type check passes (`mypy scripts/`)
- [ ] Linting passes (`ruff check scripts/`)
- [ ] Documentation updated if needed

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

### Data Flow

```
Configuration → Search Engine → Scoring → Database → Notifications
                     ↑                        |
                     └── Deduplication ───────┘
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
