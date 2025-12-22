# Job Search Tool

Automated job search and analysis tool powered by the [JobSpy](https://github.com/speedyapply/JobSpy) library to aggregate positions from multiple job boards. Features parallel execution, relevance scoring, SQLite persistence, and an interactive Streamlit dashboard.

## Features

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

### Option 1: Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/VincenzoImp/job-search-tool.git
cd job-search-tool

# Copy example config and customize
cp config/settings.example.yaml config/settings.yaml
# Edit config/settings.yaml with your preferences

# Build and run job search
docker-compose up --build

# Run analysis
docker-compose --profile analyze up analyze

# Launch interactive dashboard
docker-compose --profile dashboard up dashboard
# Then open http://localhost:8501 in your browser

# Results saved in ./results/ and ./data/
```

### Option 2: Local Python (Requires Python 3.10+)

```bash
# Install dependencies
pip install -r requirements.txt

# Copy example config
cp config/settings.example.yaml config/settings.yaml

# Run job search
cd scripts
python search_jobs.py

# Analyze results
python analyze_jobs.py

# Launch dashboard
streamlit run dashboard.py
# Then open http://localhost:8501 in your browser
```

## Project Structure

```
job-search-tool/
├── config/
│   ├── settings.yaml          # Your configuration (gitignored)
│   └── settings.example.yaml  # Example configuration template
├── scripts/
│   ├── search_jobs.py         # Main job search (parallel execution)
│   ├── analyze_jobs.py        # Results analysis and reporting
│   ├── dashboard.py           # Interactive Streamlit dashboard
│   ├── config.py              # Configuration loader with validation
│   ├── logger.py              # Structured logging with rotation
│   ├── database.py            # SQLite persistence for job tracking
│   └── models.py              # Type-safe dataclasses
├── results/                    # CSV/Excel output (gitignored)
├── data/                       # SQLite database (gitignored)
├── logs/                       # Log files (gitignored)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── CLAUDE.md                   # Developer documentation
└── README.md
```

## Configuration

All settings are in `config/settings.yaml`. Copy from `settings.example.yaml` and customize.

The configuration file is extensively documented with comments explaining every parameter, including:
- All possible values and their meanings
- Known limitations and workarounds
- Site-specific behaviors
- Best practices and recommendations

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

## Output Files

### Results Directory (`results/`)

| File | Description |
|------|-------------|
| `all_jobs_YYYYMMDD_HHMMSS.csv` | All jobs found |
| `all_jobs_YYYYMMDD_HHMMSS.xlsx` | Excel with formatting |
| `relevant_jobs_YYYYMMDD_HHMMSS.csv` | Jobs above score threshold |
| `relevant_jobs_YYYYMMDD_HHMMSS.xlsx` | Excel with highlighting |

### Database (`data/jobs.db`)

SQLite database tracking all jobs with full details:

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

### Logs (`logs/search.log`)

Structured logs with timestamps, rotation, and levels (INFO, WARNING, ERROR).

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

**Using Docker:**
```bash
docker-compose --profile dashboard up dashboard
```

**Using Local Python:**
```bash
cd scripts
streamlit run dashboard.py
```

Then open http://localhost:8501 in your browser.

### Dashboard Filters

| Filter | Description |
|--------|-------------|
| Search | Text search in title, company, description |
| Job Level | LinkedIn seniority levels (Entry, Associate, Mid-Senior, etc.) |
| Job Sites | Filter by source (LinkedIn, Indeed, Glassdoor) |
| Job Type | fulltime, parttime, internship, contract |
| Remote Only | Show only remote positions |
| Salary Range | Min/max annual salary |
| Relevance Score | Minimum score threshold |
| Date Posted | Jobs after a specific date |
| Companies | Select specific companies |
| Hide Applied | Hide jobs marked as applied |

## Data Sources

The tool scrapes jobs from:

| Site | Coverage | Rate Limiting | Notes |
|------|----------|---------------|-------|
| **Indeed** | Best | Minimal | 100 jobs/page, supports all filters |
| **LinkedIn** | Global | Aggressive | 25 jobs/page, 3-7s delays, guest API |
| **Glassdoor** | Good | Moderate | GraphQL API, company insights |
| **Google Jobs** | Aggregator | Minimal | Requires specific query syntax |
| **ZipRecruiter** | USA/Canada | Moderate | North America only |
| **Bayt** | Middle East | Minimal | UAE, Saudi Arabia, etc. |
| **Naukri** | India | Minimal | India only |
| **BDJobs** | Bangladesh | Minimal | Bangladesh only |

## Supported Countries

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

### Rate Limiting

If you encounter errors or empty results:

1. Reduce `parallel.max_workers` to 3
2. Reduce `search.results_wanted` to 20
3. Increase `retry.base_delay` to 5
4. Run at different times of day
5. Consider using proxies for heavy usage

### Docker Issues

```bash
# Rebuild from scratch
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

### No Results Found

1. Check internet connection
2. Increase `search.hours_old` (e.g., 1440 for 60 days)
3. Reduce number of queries/locations
4. Try again later (sites may be blocking)

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

## Scheduled Searches

### Using Cron (Linux/Mac)

```bash
# Run daily at 9 AM
crontab -e
0 9 * * * cd /path/to/job-search-tool && docker-compose up
```

### Using launchd (Mac)

Create `~/Library/LaunchAgents/com.job-search-tool.daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.job-search-tool.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/docker-compose</string>
        <string>up</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/job-search-tool</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</dict>
</plist>
```

## Example Output

```
============================================================
  SEARCHING FOR JOBS
============================================================
12:00:01 | INFO | Total search tasks: 120
12:00:01 | INFO | Parallel workers: 5
12:00:05 | INFO | [1/120] (0%) Found 23 jobs: software engineer @ Zurich
12:00:07 | INFO | [2/120] (1%) Found 15 jobs: backend developer @ Remote
...
12:03:45 | INFO | Job search complete: 100 succeeded, 20 failed out of 120 total

============================================================
  TOP 10 MOST RELEVANT JOBS
============================================================
1. Senior Software Engineer
   Company: Tech Startup Inc
   Location: Zurich, Switzerland
   Relevance Score: 45

2. Backend Engineer - Python
   Company: FinTech Corp
   Location: Remote
   Relevance Score: 42
...

============================================================
  SEARCH COMPLETE
============================================================
12:03:48 | INFO | Duration: 3m 47s
12:03:48 | INFO | Total unique jobs: 187
12:03:48 | INFO | Highly relevant jobs: 45
12:03:48 | INFO | New jobs (first time seen): 12
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Acknowledgments

- [JobSpy](https://github.com/speedyapply/JobSpy) - The underlying job scraping library
- [Streamlit](https://streamlit.io/) - Dashboard framework
- [Pandas](https://pandas.pydata.org/) - Data manipulation
- [Tenacity](https://github.com/jd/tenacity) - Retry logic

## Support

- **JobSpy library issues**: https://github.com/speedyapply/JobSpy/issues
- **This project**: Open an issue on GitHub

---

**Good luck with your job search!**
