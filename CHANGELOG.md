# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-12-23

### Added

- **Automated Scheduling**: Run job searches automatically at configurable intervals using APScheduler
- **Telegram Notifications**: Receive instant alerts when new relevant jobs are found
- **Unified Entry Point**: New `main.py` script that integrates scheduling and notifications
- **Report Generator**: Formatting utilities for notification messages
- **Jinja2 Templates**: Customizable message templates for Telegram notifications
- **Docker Scheduler Profile**: New `docker-compose --profile scheduler` for continuous execution

### Changed

- Updated documentation with scheduling and notification setup guides
- Improved Docker configuration with service profiles

## [1.0.0] - 2025-12-21

### Added

- **Multi-Site Scraping**: Search LinkedIn, Indeed, Glassdoor, Google Jobs, and more
- **Parallel Execution**: Concurrent searches using ThreadPoolExecutor
- **SQLite Persistence**: Track jobs across runs with full details
- **Relevance Scoring**: Customizable keyword-based scoring system
- **Interactive Dashboard**: Streamlit UI for exploring and filtering results
- **Excel Export**: Formatted output with clickable links and conditional formatting
- **YAML Configuration**: Fully customizable settings without code changes
- **Retry Logic**: Exponential backoff with tenacity for rate limit handling
- **Structured Logging**: File and console logs with rotation
- **Docker Support**: Containerized environment for cross-platform compatibility

[2.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/VincenzoImp/job-search-tool/releases/tag/v1.0.0
