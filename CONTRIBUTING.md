# Contributing to Job Search Tool

Thank you for your interest in contributing to Job Search Tool! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.10 or higher (required by JobSpy library)
- Docker and Docker Compose (optional, but recommended)
- Git

### Development Setup

1. **Fork and clone the repository**

   ```bash
   git clone https://github.com/YOUR_USERNAME/job-search-tool.git
   cd job-search-tool
   ```

2. **Create a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Copy the configuration template**

   ```bash
   cp config/settings.example.yaml config/settings.yaml
   ```

5. **Run the tool to verify setup**

   ```bash
   cd scripts
   python main.py
   ```

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check existing issues to avoid duplicates.

When reporting a bug, include:

- A clear and descriptive title
- Steps to reproduce the issue
- Expected behavior vs actual behavior
- Your environment (OS, Python version, Docker version if applicable)
- Relevant log output from `logs/search.log`
- Your configuration (redact sensitive data like API tokens)

### Suggesting Features

Feature suggestions are welcome! Please include:

- A clear description of the feature
- The problem it solves or use case it enables
- Any implementation ideas you have
- Whether you'd be willing to implement it

### Pull Requests

1. **Create a branch** for your changes:

   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes** following the code style guidelines below

3. **Test your changes**:

   - Run a job search to verify functionality
   - Test with Docker: `docker-compose up --build`
   - If you modified the dashboard: `streamlit run scripts/dashboard.py`

4. **Commit your changes** with a descriptive message:

   ```bash
   git commit -m "Add feature: description of what you added"
   # or
   git commit -m "Fix: description of what you fixed"
   ```

5. **Push and create a Pull Request**:

   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style Guidelines

### Python

- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Add docstrings for public functions and classes
- Keep functions focused and single-purpose

### Configuration

- Add new settings to both `settings.example.yaml` and document them
- Use descriptive names and add comments explaining options
- Provide sensible defaults

### Documentation

- Update README.md for user-facing changes
- Update CLAUDE.md for developer/architecture changes
- Add entries to CHANGELOG.md for notable changes

## Project Structure

```
job-search-tool/
├── config/               # Configuration files
├── scripts/              # Python source code
│   ├── main.py           # Entry point
│   ├── search_jobs.py    # Core search logic
│   ├── scheduler.py      # Scheduling
│   ├── notifier.py       # Notifications
│   ├── dashboard.py      # Streamlit UI
│   ├── database.py       # SQLite persistence
│   ├── config.py         # Config loader
│   ├── logger.py         # Logging
│   └── models.py         # Data classes
├── tests/                # Test suite (pytest)
├── results/              # Output files (gitignored)
├── data/                 # Database (gitignored)
└── logs/                 # Log files (gitignored)
```

## Adding New Features

### Adding a New Scoring Category

1. Add keywords to `config/settings.example.yaml`:

   ```yaml
   scoring:
     keywords:
       my_category:
         - "keyword1"
         - "keyword2"
     weights:
       my_category: 10
   ```

2. The scoring logic in `search_jobs.py` dynamically reads from config, so no code changes needed!

### Adding a New Database Column

1. Add to `CREATE_TABLE` in `database.py`
2. Add migration statement to `MIGRATE_COLUMNS` list
3. Update relevant SQL queries
4. Update `JobDBRecord` dataclass in `models.py`
5. Update related methods in `database.py`

### Adding a New Notification Channel

1. Create a new class extending `BaseNotifier` in `notifier.py`
2. Implement the `send()` method
3. Add configuration in `config.py`
4. Register the notifier in `NotificationManager`

## Testing

The project has a comprehensive test suite with 60+ tests. Run tests before submitting:

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=scripts --cov-report=html

# Run specific test file
pytest tests/test_config.py -v
```

When testing your changes also:

- Run a full job search with various configurations
- Test the dashboard with sample data
- Verify Docker builds and runs correctly
- Check logs for any warnings or errors

## Questions?

If you have questions about contributing, feel free to:

- Open a GitHub issue with your question
- Check existing issues and discussions

Thank you for contributing!
