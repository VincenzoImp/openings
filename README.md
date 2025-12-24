# Job Search Tool

Automated job search and analysis tool powered by the [JobSpy](https://github.com/speedyapply/JobSpy) library to aggregate positions from multiple job boards. Features parallel execution, relevance scoring, SQLite persistence, an interactive Streamlit dashboard, automated scheduling, and Telegram notifications.

## Features

- **Automated Scheduling**: Run searches at configurable intervals (e.g., every 24 hours)
- **Telegram Notifications**: Receive instant alerts when new relevant jobs are found
- **Multi-Site Scraping**: Search LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, and more simultaneously
- **Parallel Execution**: Concurrent searches with ThreadPoolExecutor (~3 min vs ~15 min sequential)
- **SQLite Persistence**: Track jobs across runs, identify new opportunities, mark as applied
- **YAML Configuration**: Fully customizable queries, scoring, and settings without code changes
- **Relevance Scoring**: Automatic scoring based on configurable keywords and weights
- **Interactive Dashboard**: Streamlit-based UI for filtering, sorting, and analyzing results
- **Excel Export**: Clickable links, colored headers, conditional formatting
- **Retry Logic**: Exponential backoff with tenacity for rate limit handling
- **Structured Logging**: File and console logs with rotation

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/VincenzoImp/job-search-tool.git
cd job-search-tool

# Copy example config and customize
cp config/settings.example.yaml config/settings.yaml
# Edit config/settings.yaml with your preferences

# Run once
docker-compose up --build

# Or run continuously with scheduler + notifications
docker-compose --profile scheduler up scheduler -d

# Launch interactive dashboard
docker-compose --profile dashboard up dashboard
# Open http://localhost:8501
```

### Using Local Python (3.10+)

```bash
pip install -r requirements.txt
cp config/settings.example.yaml config/settings.yaml
cd scripts && python main.py
```

## How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   JobSpy    │────▶│   Scoring   │────▶│   SQLite    │────▶│  Telegram   │
│  Scraper    │     │   Engine    │     │  Database   │     │    Bot      │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      ▲                                        │
      └────────────────────────────────────────┘
                   Deduplication
```

1. **Scrape**: JobSpy fetches listings from configured sites in parallel
2. **Score**: Each job gets a relevance score based on keyword matches
3. **Store**: SQLite tracks all jobs, identifies new vs already-seen
4. **Notify**: Telegram sends top new matches above score threshold

## Configuration

All settings are in `config/settings.yaml`. Copy from `settings.example.yaml` and customize. The configuration file is extensively documented with comments explaining every parameter.

### Search Settings

```yaml
search:
  results_wanted: 30        # Results per query per site (max ~1000)
  hours_old: 168            # 168 = 7 days, 720 = 30 days
  job_types:
    - "fulltime"
    - "contract"
  sites:
    - "indeed"              # Best coverage, minimal rate limiting
    - "linkedin"            # Global coverage, aggressive rate limiting
    - "glassdoor"           # Good company insights
  locations:
    - "Zurich, Switzerland"
    - "Remote"
  distance: 50              # Search radius in miles (~80 km)
  is_remote: false          # true = remote only
  linkedin_fetch_description: true  # Get full descriptions (slower)
```

### Search Queries

```yaml
queries:
  software_engineering:
    - "software engineer"
    - "backend developer"
    - "full-stack developer"
  data:
    - "data engineer"
    - "data scientist"
  # Add your own categories
```

**Query Syntax Tips** (especially for Indeed):
- Use `""` for exact match: `"software engineer"`
- Use `-` to exclude: `software -marketing -sales`
- Use `OR` for alternatives: `(python OR java OR c++)`
- Use `()` for grouping: `(senior OR lead) engineer`

### Relevance Scoring

```yaml
scoring:
  threshold: 10             # Minimum score to be "relevant"
  weights:
    primary_skills: 20      # Your main expertise
    technologies: 12        # Tech stack matches
    seniority_match: 10     # Level matching
  keywords:
    primary_skills:
      - "software engineer"
      - "backend"
    technologies:
      - "python"
      - "javascript"
      - "react"
```

### Parallelism & Retry

```yaml
parallel:
  max_workers: 5            # Concurrent searches (3-5 recommended)

retry:
  max_attempts: 3           # Retry failed requests
  base_delay: 2             # Initial delay (seconds)
  backoff_factor: 2         # Exponential multiplier
```

### Scheduler & Notifications

```yaml
scheduler:
  enabled: true             # Enable scheduled mode
  interval_hours: 24        # Run every 24 hours
  run_on_startup: true      # Run immediately when starting

notifications:
  enabled: true
  telegram:
    enabled: true
    bot_token: "YOUR_BOT_TOKEN"      # From @BotFather
    chat_ids: ["YOUR_CHAT_ID"]
    min_score_for_notification: 15   # Only notify high-score jobs
    max_jobs_in_message: 10          # Top 10 jobs in notification
```

## Setting Up Telegram Notifications

1. **Create a bot with @BotFather**:
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` and follow instructions
   - Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Get your chat_id**:
   - Start a chat with your new bot (send any message)
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Look for `"chat":{"id": YOUR_CHAT_ID}`

3. **Configure `config/settings.yaml`** with your bot_token and chat_id

4. **Start the scheduler**:
   ```bash
   docker-compose --profile scheduler up scheduler -d
   ```

### Notification Example

When new jobs are found, you'll receive a Telegram message like:

```
🔔 Job Search Tool - New Jobs Found
━━━━━━━━━━━━━━━━━━━━━

📊 Run Summary
• Date: 2025-12-23 09:00
• Total found: 150
• New: 12
• Avg score: 24.5

━━━━━━━━━━━━━━━━━━━━━

🏆 Top 5 New Jobs

1️⃣ Backend Engineer
   🏢 TechCorp Inc.
   📍 Berlin, Germany
   ⭐ Score: 48
   View Job →

2️⃣ Full Stack Developer
   🏢 Startup AG
   📍 Remote
   ⭐ Score: 42
   View Job →
...
```

## Output Files

### Database (`data/jobs.db`) - PRIMARY STORAGE

The SQLite database is the **core storage** used by the system for:
- Tracking all jobs seen across runs
- Identifying new vs already-seen jobs
- Determining which jobs to notify about
- Marking jobs as "applied"

### Results Directory (`results/`) - OPTIONAL

CSV/Excel files are optional exports for human review. Disable with:

```yaml
output:
  save_csv: false
  save_excel: false
```

When enabled (default), generates:

| File | Description |
|------|-------------|
| `all_jobs_YYYYMMDD_HHMMSS.csv` | All jobs found |
| `all_jobs_YYYYMMDD_HHMMSS.xlsx` | Excel with formatting |
| `relevant_jobs_YYYYMMDD_HHMMSS.csv` | Jobs above score threshold |
| `relevant_jobs_YYYYMMDD_HHMMSS.xlsx` | Excel with highlighting |

### Database Schema

| Column | Description |
|--------|-------------|
| `job_id` | Unique identifier (SHA256 hash) |
| `title`, `company`, `location` | Basic job info |
| `job_url` | Link to job posting |
| `site` | Source (indeed, linkedin, glassdoor) |
| `job_type` | fulltime, contract, internship, etc. |
| `is_remote` | Remote work available |
| `job_level` | Seniority level (LinkedIn) |
| `description` | Full job description |
| `date_posted` | When job was posted |
| `min_amount`, `max_amount`, `currency` | Salary information |
| `company_url` | Company page URL |
| `first_seen`, `last_seen` | Tracking dates |
| `relevance_score` | Calculated score |
| `applied` | Application status |

## Interactive Dashboard

The dashboard provides a powerful interface for analyzing and filtering job results.

### Features

- **Multiple data sources**: Load from CSV files or SQLite database
- **Comprehensive filtering**: Text search, job level, sites, companies, locations, job types, remote status, salary range, relevance score, date posted
- **Statistics view**: Total jobs, average score, top sources, remote jobs count
- **Interactive charts**: Jobs by source, score distribution
- **Sortable table**: Customize columns, sort by any field, clickable job links
- **Job details view**: Full description and metadata
- **Export**: Download filtered results as CSV or Excel

### Launch Dashboard

```bash
# Using Docker
docker-compose --profile dashboard up dashboard
# Open http://localhost:8501

# Using Local Python
cd scripts && streamlit run dashboard.py
```

## Data Sources

| Site | Coverage | Rate Limiting | Notes |
|------|----------|---------------|-------|
| **Indeed** | Best | Minimal | 100 jobs/page, supports all filters |
| **LinkedIn** | Global | Aggressive | 25 jobs/page, 3-7s delays, guest API |
| **Glassdoor** | Good | Moderate | GraphQL API, company insights |
| **Google Jobs** | Aggregator | Minimal | Requires specific query syntax |
| **ZipRecruiter** | USA/Canada | Moderate | North America only |
| **Bayt** | Middle East | Minimal | UAE, Saudi Arabia, etc. |
| **Naukri** | India | Minimal | India only |

### Supported Countries

| Region | Countries |
|--------|-----------|
| North America | USA, Canada |
| Europe | UK, Germany, France, Netherlands, Switzerland, Ireland, Spain, Italy, Austria, Belgium, Denmark, Finland, Norway, Sweden, Poland, Portugal |
| Asia | India, Singapore, Hong Kong, Japan, South Korea, China |
| Oceania | Australia, New Zealand |
| Middle East | UAE, Saudi Arabia, Israel |
| South America | Brazil, Argentina, Mexico |

## Known Limitations

### Indeed Filter Exclusivity

Indeed can only use ONE of these filters at a time:
- `hours_old` (date filtering)
- `job_type` + `is_remote`
- `easy_apply`

**We prioritize `hours_old` for fresh results.** If you need job type filtering, set `hours_old: null`.

### LinkedIn Rate Limiting

- Built-in delays: 3-7 seconds between requests
- Hard limit at ~1000 results
- Heavy rate limiting around 10th page
- `linkedin_fetch_description=True` doubles request count

### Glassdoor Issues

- "Location not parsed" errors for locations not in database
- 400/429 errors indicate rate limiting

## Troubleshooting

### Rate Limiting / Empty Results

1. Reduce `parallel.max_workers` to 3
2. Reduce `search.results_wanted` to 20
3. Increase `retry.base_delay` to 5
4. Run at different times of day
5. Consider using proxies for heavy usage

### Docker Issues

```bash
docker-compose down
docker system prune -f
docker-compose up --build
```

### Python Version

This tool requires Python 3.10+ (JobSpy library requirement). Check your version:

```bash
python3 --version
```

If below 3.10, use Docker instead.

## Database Queries

```bash
# Statistics
sqlite3 data/jobs.db "SELECT COUNT(*), AVG(relevance_score) FROM jobs"

# New jobs today
sqlite3 data/jobs.db "SELECT title, company FROM jobs WHERE first_seen = date('now')"

# Top jobs not yet applied
sqlite3 data/jobs.db "SELECT title, company, relevance_score FROM jobs WHERE applied = 0 ORDER BY relevance_score DESC LIMIT 10"

# Mark job as applied
sqlite3 data/jobs.db "UPDATE jobs SET applied = 1 WHERE job_id = 'abc123...'"

# Jobs by site
sqlite3 data/jobs.db "SELECT site, COUNT(*) FROM jobs GROUP BY site"

# Remote jobs
sqlite3 data/jobs.db "SELECT title, company FROM jobs WHERE is_remote = 1 ORDER BY relevance_score DESC"
```

## Project Structure

```
job-search-tool/
├── config/
│   ├── settings.yaml          # Your configuration (gitignored)
│   └── settings.example.yaml  # Example template with full documentation
├── scripts/
│   ├── main.py                # Unified entry point (scheduler + notifications)
│   ├── search_jobs.py         # Core job search with parallel execution
│   ├── scheduler.py           # APScheduler integration
│   ├── notifier.py            # Telegram notification system
│   ├── dashboard.py           # Streamlit interactive dashboard
│   ├── database.py            # SQLite persistence
│   ├── config.py              # Configuration loader
│   ├── logger.py              # Structured logging
│   └── models.py              # Type-safe dataclasses
├── templates/                  # Jinja2 templates for notifications
├── results/                    # CSV/Excel output (gitignored)
├── data/                       # SQLite database (gitignored)
├── logs/                       # Log files (gitignored)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── CLAUDE.md                   # Developer documentation
└── README.md
```

## License

MIT License

## Acknowledgments

- [JobSpy](https://github.com/speedyapply/JobSpy) - The underlying job scraping library
- [Streamlit](https://streamlit.io/) - Dashboard framework
- [APScheduler](https://apscheduler.readthedocs.io/) - Scheduling
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram integration
- [Pandas](https://pandas.pydata.org/) - Data manipulation
- [Tenacity](https://github.com/jd/tenacity) - Retry logic

## Support

- **JobSpy library issues**: https://github.com/speedyapply/JobSpy/issues
- **This project**: Open an issue on GitHub
