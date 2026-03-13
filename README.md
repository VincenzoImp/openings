# Job Search Tool

[![CI](https://github.com/VincenzoImp/job-search-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/VincenzoImp/job-search-tool/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

An automated job search aggregation and analysis platform that collects listings from multiple job boards, applies intelligent relevance scoring, and delivers real-time notifications for matching opportunities.

Built on top of the [JobSpy](https://github.com/speedyapply/JobSpy) library, this tool provides enterprise-grade features including parallel execution, persistent storage, scheduled automation, and multi-channel notifications.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
  - [Search Settings](#search-settings)
  - [Query Definition](#query-definition)
  - [Relevance Scoring](#relevance-scoring)
  - [Scheduling and Notifications](#scheduling-and-notifications)
- [Telegram Integration](#telegram-integration)
- [Interactive Dashboard](#interactive-dashboard)
- [Data Storage](#data-storage)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Multi-Source Aggregation** | Simultaneously scrapes LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, and regional boards |
| **Intelligent Scoring** | Configurable keyword-based relevance scoring with weighted categories |
| **Persistent Tracking** | SQLite database tracks all jobs across runs, identifies new opportunities |
| **Automated Scheduling** | APScheduler-based periodic execution with configurable intervals |
| **Real-Time Notifications** | Telegram alerts for high-scoring new jobs |
| **Interactive Dashboard** | Streamlit-based UI for filtering, analysis, and export |
| **Semantic Search** | ChromaDB + sentence-transformers for natural language job search |
| **Bookmarks & Actions** | Bookmark, delete, and mark jobs as applied directly from dashboard |

### Technical Features

| Feature | Description |
|---------|-------------|
| **Parallel Execution** | ThreadPoolExecutor with configurable worker count |
| **Rate Limit Prevention** | Per-site throttling with jitter to avoid detection |
| **Fuzzy Matching** | Post-filter validation using fuzzy string matching |
| **Retry Logic** | Exponential backoff with tenacity for transient failures |
| **Dynamic Rescoring** | Automatic rescoring of existing jobs when criteria change |
| **CI/CD Pipeline** | GitHub Actions with test matrix, security audit, Docker build |
| **Comprehensive Testing** | 320+ pytest tests covering all core functionality |
| **Vector Embeddings** | Local sentence-transformer model for semantic similarity |

---

## Architecture

### System Overview

```
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                                JOB SEARCH TOOL                                    ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                   ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │                            📄 CONFIGURATION                                 │  ║
║  │         settings.yaml: queries, scoring, keywords, schedule, telegram       │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
║                                       │                                           ║
║                                       ▼                                           ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │                          ⏰ SCHEDULER (APScheduler)                         │  ║
║  │              Single-shot mode  OR  Continuous (every N hours)               │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
║                                       │                                           ║
║                     ┌─────────────────┼─────────────────┐                         ║
║                     ▼                 ▼                 ▼                         ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │                        🔍 PARALLEL SEARCH ENGINE                            │  ║
║  │                                                                             │  ║
║  │    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │  ║
║  │    │  Indeed  │  │ LinkedIn │  │Glassdoor │  │  Google  │  │   ...    │     │  ║
║  │    └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘     │  ║
║  │         │             │             │             │             │           │  ║
║  │         └─────────────┴─────────────┴─────────────┴─────────────┘           │  ║
║  │                                     │                                       │  ║
║  │                      ┌──────────────┴──────────────┐                        │  ║
║  │                      │   🛡️ THROTTLING + JITTER    │                        │  ║
║  │                      │    (Rate limit prevention)  │                        │  ║
║  │                      └──────────────┬──────────────┘                        │  ║
║  └─────────────────────────────────────┼───────────────────────────────────────┘  ║
║                                        ▼                                          ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │                          ⚙️ PROCESSING PIPELINE                             │  ║
║  │                                                                             │  ║
║  │   ┌───────────────┐     ┌───────────────┐     ┌───────────────┐             │  ║
║  │   │ Deduplication │────▶│    Scoring    │────▶│   Filtering   │             │  ║
║  │   │  (SHA256 ID)  │     │  (Keywords)   │     │  (Threshold)  │             │  ║
║  │   └───────────────┘     └───────────────┘     └───────────────┘             │  ║
║  │                                                       │                     │  ║
║  └───────────────────────────────────────────────────────┼─────────────────────┘  ║
║                                                          ▼                        ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │                             💾 DATA LAYER                                   │  ║
║  │                                                                             │  ║
║  │   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐           │  ║
║  │   │ SQLite Database │   │   CSV / Excel   │   │    Dashboard    │           │  ║
║  │   │ (Primary Store) │   │   (Optional)    │   │   (Streamlit)   │           │  ║
║  │   │                 │   │                 │   │                 │           │  ║
║  │   │  • All jobs     │   │ • all_jobs.csv  │   │  • Filters      │           │  ║
║  │   │  • first_seen   │   │ • relevant.xlsx │   │  • Charts       │           │  ║
║  │   │  • last_seen    │   │                 │   │  • Export       │           │  ║
║  │   │  • applied flag │   │                 │   │                 │           │  ║
║  │   └────────┬────────┘   └─────────────────┘   └─────────────────┘           │  ║
║  │            │                                                                │  ║
║  └────────────┼────────────────────────────────────────────────────────────────┘  ║
║               ▼                                                                   ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │                         📬 NOTIFICATION SYSTEM                              |  ║
║  │                                                                             │  ║
║  │   ┌─────────────────┐       ┌───────────────────────────────────────────┐   │  ║
║  │   │   New Jobs Only │──────▶│                TELEGRAM                   │   │  ║
║  │   │  (score >= min) │       │                                           │   │  ║
║  │   └─────────────────┘       │  🔔 Job Search Tool - New Jobs Found      │   │  ║
║  │                             │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━           │   │  ║
║  │                             │  📊 Run Summary                           │   │  ║
║  │                             │  • Total: 150  • New: 12                  │   │  ║
║  │                             │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━           │   │  ║
║  │                             │  1️⃣ Backend Engineer                      │   │  ║
║  │                             │     🏢 TechCorp   📍 Remote                │  │  ║
║  │                             │     ⭐ Score: 48  [View →]                │   │  ║
║  │                             └───────────────────────────────────────────┘   │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
```

### Detailed Execution Flow

```
                                 ╔═══════════════════╗
                                 ║      STARTUP      ║
                                 ╚═════════╤═════════╝
                                           │
                         ┌─────────────────┴─────────────────┐
                         ▼                                   ▼
              ┌────────────────────┐              ┌────────────────────┐
              │   Load settings    │              │   Connect to DB    │
              │  (settings.yaml)   │              │    (jobs.db)       │
              └─────────┬──────────┘              └─────────┬──────────┘
                        │                                   │
                        └─────────────────┬─────────────────┘
                                          ▼
                         ┌─────────────────────────────────┐
                         │      RECALCULATE SCORES         │
                         │  ┌───────────────────────────┐  │
                         │  │ Apply current config to   │  │◄── Only at startup
                         │  │ all existing jobs in DB   │  │    (not every cycle)
                         │  └───────────────────────────┘  │
                         └────────────────┬────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
         ╔════════════════════╗                    ╔════════════════════╗
         ║   SINGLE-SHOT MODE ║                    ║   SCHEDULED MODE   ║
         ║  scheduler: false  ║                    ║  scheduler: true   ║
         ║  Run once and exit ║                    ║  Run every N hours ║
         ╚══════════╤═════════╝                    ╚══════════╤═════════╝
                    │                                         │
                    └───────────────────┬─────────────────────┘
                                        ▼
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                              🔄 SEARCH CYCLE                                      ║◄──┐
╠═══════════════════════════════════════════════════════════════════════════════════╣   │
║                                                                                   ║   │
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 1. CLEANUP OLD JOBS (if database.cleanup_enabled: true)                     │  ║   │
║  │    Delete jobs with last_seen > cleanup_days ago                            │  ║   │
║  └─────────────────────────────────────────────────────────────────────────────┘  ║   │
║                                        │                                          ║   │
║                                        ▼                                          ║   │
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 2. PARALLEL SEARCH                                                          │  ║   │
║  │                                                                             │  ║   │
║  │    For each (query, location) combination:                                  │  ║   │
║  │                                                                             │  ║   │
║  │    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │  ║   │
║  │    │ Worker 1 │  │ Worker 2 │  │ Worker 3 │  │ Worker 4 │   (parallel)      │  ║   │
║  │    │ "python" │  │"backend" │  │ "data"   │  │  "devops"│                   │  ║   │
║  │    │  Zurich  │  │  Zurich  │  │  Remote  │  │  Remote  │                   │  ║   │
║  │    └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                   │  ║   │
║  │         │             │             │             │                         │  ║   │
║  │         ▼             ▼             ▼             ▼                         │  ║   │
║  │    ┌────────────────────────────────────────────────────────────────────┐   │  ║   │
║  │    │                    THROTTLING (per-site delays)                    │   │  ║   │
║  │    │     LinkedIn: 3.0s  │  Indeed: 1.0s  │  Glassdoor: 1.5s            │   │  ║   │
║  │    │                    + random jitter (±30%)                          │   │  ║   │
║  │    └────────────────────────────────────────────────────────────────────┘   │  ║   │
║  └─────────────────────────────────────────────────────────────────────────────┘  ║   │
║                                        │                                          ║   │
║                                        ▼                                          ║   │
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 3. COMBINE & DEDUPLICATE                                                    │  ║   │
║  │    job_id = SHA256(title + company + location)  →  64-char unique hash      │  ║   │
║  └─────────────────────────────────────────────────────────────────────────────┘  ║   │
║                                        │                                          ║   │
║                                        ▼                                          ║   │
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 4. CALCULATE RELEVANCE SCORES                                               │  ║   │
║  │                                                                             │  ║   │
║  │    For each job:                                                            │  ║   │
║  │    ┌─────────────────────────────────────────────────────────────────────┐  │  ║   │
║  │    │  text = title + description + company + location                    │  │  ║   │
║  │    │                                                                     │  │  ║   │
║  │    │  for category in scoring.keywords:                                  │  │  ║   │
║  │    │      if any keyword matches (case-insensitive):                     │  │  ║   │
║  │    │          score += weights[category]                                 │  │  ║   │
║  │    │                                                                     │  │  ║   │
║  │    │  Example: "blockchain" matched → +25, "python" matched → +15        │  │  ║   │
║  │    └─────────────────────────────────────────────────────────────────────┘  │  ║   │
║  └─────────────────────────────────────────────────────────────────────────────┘  ║   │
║                                        │                                          ║   │
║                                        ▼                                          ║   │
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 5. FILTER BY THRESHOLD                                                      │  ║   │
║  │    Keep only jobs where: score >= scoring.threshold                         │  ║   │
║  └─────────────────────────────────────────────────────────────────────────────┘  ║   │
║                                        │                                          ║   │
║                        ┌───────────────┴───────────────┐                          ║   │
║                        ▼                               ▼                          ║   │
║           ┌────────────────────────┐      ┌────────────────────────┐              ║   │
║           │    6a. SAVE TO DB      │      │  6b. SAVE CSV/EXCEL    │              ║   │
║           │                        │      │     (if enabled)       │              ║   │
║           │  UPSERT logic:         │      │                        │              ║   │
║           │  • New job → INSERT    │      │  • all_jobs.csv        │              ║   │
║           │  • Existing → UPDATE   │      │  • relevant_jobs.xlsx  │              ║   │
║           │    (last_seen, score)  │      │                        │              ║   │
║           └───────────┬────────────┘      └────────────────────────┘              ║   │
║                       │                                                           ║   │
║                       ▼                                                           ║   │
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 7. IDENTIFY NEW JOBS                                                        │  ║   │
║  │    New = jobs where first_seen = today (never seen before)                  │  ║   │
║  └─────────────────────────────────────────────────────────────────────────────┘  ║   │
║                                        │                                          ║   │
║                                        ▼                                          ║   │
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 8. SEND TELEGRAM NOTIFICATION                                               │  ║   │
║  │                                                                             │  ║   │
║  │    Filter:  score >= min_score_for_notification                             │  ║   │
║  │    Limit:   max_jobs_in_message                                             │  ║   │
║  │    Format:  Chunked messages (10 jobs per message to avoid 4096 char limit) │  ║   │
║  └─────────────────────────────────────────────────────────────────────────────┘  ║   │
║                                        │                                          ║   │
╠════════════════════════════════════════╧══════════════════════════════════════════╣   │
║                              CYCLE COMPLETE                                       ║   │
║                                                                                   ║   │
║    Scheduled mode?  ─────────────────────────────────────▶  Wait N hours  ────────╫───┘
║         │                                                                         ║
║         ▼                                                                         ║
║    Single-shot mode?  ─────────────────────────────────▶  EXIT                    ║
║                                                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
```

### Key Components

| Component | File | Responsibility |
|-----------|------|----------------|
| **Entry Point** | `main.py` | Orchestrates startup, scheduling, execution |
| **Search Engine** | `search_jobs.py` | Parallel scraping, scoring, filtering |
| **Scheduler** | `scheduler.py` | APScheduler wrapper, retry logic |
| **Notifications** | `notifier.py` | Telegram message formatting and sending |
| **Database** | `database.py` | SQLite CRUD, deduplication, cleanup (WAL mode) |
| **Configuration** | `config.py` | YAML loading, validation, type safety |
| **Scoring** | `scoring.py` | Relevance scoring engine |
| **Exporter** | `exporter.py` | CSV/Excel export with sanitization |
| **Dashboard** | `dashboard.py` | Unified Job Search Hub with semantic search |
| **Vector Store** | `vector_store.py` | ChromaDB semantic search |
| **Vector Commands** | `vector_commands.py` | Embedding backfill and sync |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose (recommended), OR
- Python 3.11 or higher

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/VincenzoImp/job-search-tool.git
cd job-search-tool

# Create configuration file
cp config/settings.example.yaml config/settings.yaml

# Edit configuration with your preferences
# nano config/settings.yaml

# Run a single search
docker compose up --build

# Or run continuously with scheduler
docker compose --profile scheduler up scheduler -d

# Launch the dashboard
docker compose --profile dashboard up dashboard
# Access at http://localhost:8501
```

### Option 2: Local Python

```bash
# Clone and navigate
git clone https://github.com/VincenzoImp/job-search-tool.git
cd job-search-tool

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create configuration
cp config/settings.example.yaml config/settings.yaml

# Run the search
cd scripts && python main.py

# Launch dashboard
streamlit run dashboard.py
```

---

## Configuration

All settings are defined in `config/settings.yaml`. The example file (`settings.example.yaml`) contains comprehensive documentation for every parameter.

### Search Settings

```yaml
search:
  results_wanted: 50          # Maximum results per query per site
  hours_old: 168              # Job posting age limit (168 = 7 days)

  job_types:                  # Filter by employment type
    - "fulltime"
    - "contract"
    - "internship"

  sites:                      # Job boards to search
    - "indeed"                # Best coverage, minimal rate limiting
    - "linkedin"              # Global reach, aggressive rate limiting
    - "glassdoor"             # Company insights included

  locations:                  # Geographic targets
    - "San Francisco, CA"
    - "New York, NY"
    - "Remote"

  distance: 50                # Search radius in miles (~80 km)
  is_remote: false            # Set true to search remote-only positions

  linkedin_fetch_description: true  # Fetch full job descriptions (slower)
```

### Query Definition

Queries are organized into logical categories for maintainability:

```yaml
queries:
  software_engineering:
    - "software engineer"
    - "backend developer"
    - "full-stack developer"

  data_science:
    - "data engineer"
    - "data scientist"
    - "machine learning engineer"

  devops:
    - "devops engineer"
    - "site reliability engineer"
    - "platform engineer"
```

**Query Syntax Tips** (especially for Indeed):
- Exact match: `"software engineer"` (with quotes)
- Exclusion: `software -marketing -sales`
- Alternatives: `(python OR java OR golang)`
- Grouping: `(senior OR lead) engineer`

### Relevance Scoring

The scoring system is fully configuration-driven with no hardcoded categories:

```yaml
scoring:
  threshold: 15               # Minimum score to be considered "relevant"

  weights:                    # Points awarded per category match
    primary_skills: 25        # High priority matches
    technologies: 15          # Tech stack alignment
    experience_level: 10      # Seniority matching
    locations: 5              # Preferred locations
    avoid: -30                # Negative scoring for unwanted terms

  keywords:
    primary_skills:
      - "software engineer"
      - "backend"
      - "distributed systems"

    technologies:
      - "python"
      - "kubernetes"
      - "postgresql"

    experience_level:
      - "junior"
      - "entry level"
      - "new grad"

    locations:
      - "remote"
      - "san francisco"

    avoid:                    # Penalize senior roles if targeting entry-level
      - "senior"
      - "10+ years"
      - "director"
```

**Scoring Behavior:**
- For each job, text is extracted from: title, description, company, location
- Each category is checked for keyword matches (case-insensitive)
- If ANY keyword from a category matches, that category's weight is added
- Final score determines if the job is "relevant" (score >= threshold)

**Dynamic Rescoring**: When you modify scoring criteria, existing jobs in the database are automatically rescored on the next run. No database reset required.

### Scheduling and Notifications

```yaml
scheduler:
  enabled: true               # Enable scheduled execution
  interval_hours: 24          # Run every 24 hours
  run_on_startup: true        # Execute immediately when started
  retry_on_failure: true      # Retry failed searches
  retry_delay_minutes: 30     # Wait before retry
  max_retries: 3              # Max consecutive retries (0 = unlimited)

notifications:
  enabled: true
  telegram:
    enabled: true
    bot_token: "YOUR_BOT_TOKEN"       # From @BotFather
    chat_ids:
      - "YOUR_CHAT_ID"                # Your Telegram user ID
    min_score_for_notification: 20    # Only notify for high-scoring jobs
    max_jobs_in_message: 50           # Maximum jobs per notification
```

### Vector Search

```yaml
vector_search:
  enabled: true                 # Enable semantic search (default: true)
  model_name: "all-MiniLM-L6-v2"  # Embedding model (~80MB)
  persist_dir: "data/chroma"   # ChromaDB storage
  embed_on_save: true          # Auto-embed new jobs
  default_results: 20          # Max semantic search results
  backfill_on_startup: true    # Embed existing jobs at startup
  batch_size: 100              # Embedding batch size
```

### Rate Limiting Prevention

```yaml
throttling:
  enabled: true               # Highly recommended
  default_delay: 1.5          # Seconds between requests
  site_delays:
    linkedin: 3.0             # LinkedIn is aggressive
    indeed: 1.0               # Indeed is lenient
    glassdoor: 1.5
  jitter: 0.3                 # Random variation (30%)
  rate_limit_cooldown: 30.0   # Pause after hitting rate limit

parallel:
  max_workers: 4              # Concurrent searches (3-5 recommended)
```

---

## Telegram Integration

### Setup Instructions

1. **Create a Telegram Bot**
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` and follow the prompts
   - Save the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Get Your Chat ID**
   - Start a conversation with your new bot (send any message)
   - Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find `"chat":{"id": YOUR_CHAT_ID}` in the response

3. **Configure the Tool**

   Option A - Environment variable (recommended):
   ```bash
   # Create a .env file (gitignored)
   echo 'TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz' > .env
   ```
   ```yaml
   # config/settings.yaml
   notifications:
     enabled: true
     telegram:
       enabled: true
       bot_token: "$TELEGRAM_BOT_TOKEN"   # References env var
       chat_ids:
         - "987654321"
   ```

   Option B - Direct value (not recommended for production):
   ```yaml
   notifications:
     enabled: true
     telegram:
       enabled: true
       bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
       chat_ids:
         - "987654321"
   ```

4. **Test the Integration**
   ```bash
   docker compose --profile scheduler up scheduler
   ```

### Notification Format

```
🔔 Job Search Tool - New Jobs Found
━━━━━━━━━━━━━━━━━━━━━

📊 Run Summary
• Date: 2025-12-31 09:00
• Total found: 150
• New: 12
• Avg score: 28.5

━━━━━━━━━━━━━━━━━━━━━

🏆 12 New Jobs (score ≥ 20)

1️⃣ Backend Engineer
   🏢 TechCorp Inc.
   📍 San Francisco, CA
   ⭐ Score: 48
   View Job →

2️⃣ Full Stack Developer
   🏢 Startup AG
   📍 Remote
   ⭐ Score: 42
   View Job →
...
```

---

## Interactive Dashboard

The Streamlit dashboard provides powerful analysis and filtering capabilities.

### Features

- **Semantic Search**: Natural language queries find conceptually similar jobs
- **Advanced Filtering**: Site, score range, job type, remote, date range, bookmarks
- **Card-Based Display**: Rich job cards with score badges, similarity indicators
- **Inline Actions**: Mark applied, bookmark, delete, open URL from each card
- **Bulk Operations**: Select multiple jobs for batch actions
- **Analytics Tab**: Charts for source distribution, score breakdown, trends
- **Database Management**: Delete old jobs, export data
- **Pagination**: 20 jobs per page with navigation

### Launch

```bash
# Docker
docker compose --profile dashboard up dashboard
# Access at http://localhost:8501

# Local
cd scripts && streamlit run dashboard.py
```

---

## Data Storage

### Primary Storage: SQLite Database

The SQLite database (`data/jobs.db`) is the primary storage mechanism:

| Column | Type | Description |
|--------|------|-------------|
| `job_id` | TEXT | Unique SHA256 hash (title + company + location) |
| `title` | TEXT | Job title |
| `company` | TEXT | Company name |
| `location` | TEXT | Job location |
| `job_url` | TEXT | Direct link to posting |
| `site` | TEXT | Source (indeed, linkedin, glassdoor) |
| `job_type` | TEXT | Employment type |
| `is_remote` | BOOLEAN | Remote work available |
| `description` | TEXT | Full job description |
| `date_posted` | DATE | Original posting date |
| `min_amount`, `max_amount` | REAL | Salary range |
| `currency` | TEXT | Salary currency |
| `first_seen` | DATE | First discovered |
| `last_seen` | DATE | Most recent occurrence |
| `relevance_score` | INTEGER | Calculated score |
| `applied` | BOOLEAN | Application tracking |
| `bookmarked` | BOOLEAN | Bookmark tracking |

### Useful Database Queries

```bash
# View statistics
sqlite3 data/jobs.db "SELECT COUNT(*), AVG(relevance_score) FROM jobs"

# Today's new jobs
sqlite3 data/jobs.db "SELECT title, company, relevance_score FROM jobs WHERE first_seen = date('now') ORDER BY relevance_score DESC"

# Top unapplied jobs
sqlite3 data/jobs.db "SELECT title, company, relevance_score FROM jobs WHERE applied = 0 ORDER BY relevance_score DESC LIMIT 10"

# Mark job as applied
sqlite3 data/jobs.db "UPDATE jobs SET applied = 1 WHERE job_id = 'your_job_id'"

# Distribution by source
sqlite3 data/jobs.db "SELECT site, COUNT(*) as count FROM jobs GROUP BY site ORDER BY count DESC"

# Remote opportunities
sqlite3 data/jobs.db "SELECT title, company FROM jobs WHERE is_remote = 1 ORDER BY relevance_score DESC LIMIT 20"
```

### Optional Exports

CSV and Excel exports are optional and controlled by configuration:

```yaml
output:
  save_csv: true              # Generate CSV files
  save_excel: true            # Generate formatted Excel files
```

When enabled, files are saved to `results/` with timestamps:
- `all_jobs_YYYYMMDD_HHMMSS.csv/xlsx` - All discovered jobs
- `relevant_jobs_YYYYMMDD_HHMMSS.csv/xlsx` - Jobs above score threshold

---

## Troubleshooting

### Rate Limiting (Empty Results, 429 Errors)

```yaml
# Adjust these settings in config/settings.yaml:
throttling:
  enabled: true
  default_delay: 2.5          # Increase delay
  site_delays:
    linkedin: 5.0             # LinkedIn needs more time

parallel:
  max_workers: 2              # Reduce concurrency

search:
  results_wanted: 20          # Reduce per-query results
```

### Docker Issues

```bash
# Full rebuild
docker compose down
docker system prune -f
docker compose up --build
```

### Database Locked

The database uses WAL mode and `busy_timeout=5000` to handle concurrent access, but SQLite still supports only one writer at a time:

```bash
# Stop any running processes
docker compose down

# Or wait for the current operation to complete
```

### Python Version

JobSpy requires Python 3.11+:

```bash
python3 --version
# If below 3.11, use Docker instead
```

---

## Development

### Project Structure

```
job-search-tool/
├── config/
│   ├── settings.yaml              # User configuration (gitignored)
│   └── settings.example.yaml      # Documented template
├── scripts/
│   ├── main.py                    # Unified entry point
│   ├── search_jobs.py             # Core search with parallel execution
│   ├── scheduler.py               # APScheduler integration
│   ├── notifier.py                # Telegram notifications
│   ├── dashboard.py               # Streamlit UI
│   ├── database.py                # SQLite persistence (WAL mode)
│   ├── config.py                  # Configuration loader + validation
│   ├── logger.py                  # Structured logging
│   ├── models.py                  # Type-safe dataclasses
│   ├── scoring.py                 # Relevance scoring (extracted from search_jobs.py)
│   ├── exporter.py                # CSV/Excel export
│   ├── vector_store.py            # ChromaDB vector store
│   ├── vector_commands.py         # Vector backfill/sync
│   └── healthcheck.py             # Docker health checks
├── tests/                          # 320+ pytest tests
│   ├── conftest.py                # Shared fixtures
│   ├── test_main.py               # Entry point tests
│   ├── test_config.py             # Configuration validation
│   ├── test_database.py           # Database CRUD
│   ├── test_notifier.py           # Notification tests
│   ├── test_scheduler.py          # Scheduler tests
│   ├── test_models.py             # Model tests
│   ├── test_scoring.py            # Scoring tests
│   ├── test_logger.py             # Logger tests
│   ├── test_exporter.py           # Exporter tests
│   ├── test_healthcheck.py        # Health check tests
│   ├── test_report_generator.py   # Report generator tests
│   ├── test_analyze_jobs.py       # Analysis tests
│   ├── test_search_jobs.py        # Search engine tests
│   └── test_vector_store.py       # Vector store tests
├── .github/workflows/ci.yml       # CI pipeline
├── results/                        # CSV/Excel output (gitignored)
├── data/                           # SQLite database (gitignored)
├── logs/                           # Log files (gitignored)
├── Dockerfile                      # Multi-stage build, non-root user
├── docker-compose.yml
├── .pre-commit-config.yaml         # Ruff, trailing whitespace, etc.
├── requirements.txt
├── requirements-dev.txt
└── pytest.ini
```

### Running Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# With coverage report
pytest --cov=scripts --cov-report=html

# Specific test file
pytest tests/test_config.py -v
```

### Code Quality

```bash
# Run pre-commit hooks (ruff lint + format, trailing whitespace, etc.)
pre-commit run --all-files

# Type checking
mypy scripts/

# Linting
ruff check scripts/

# Formatting
ruff format scripts/
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [JobSpy](https://github.com/speedyapply/JobSpy) - Core job scraping library
- [Streamlit](https://streamlit.io/) - Dashboard framework
- [APScheduler](https://apscheduler.readthedocs.io/) - Task scheduling
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram integration
- [Pandas](https://pandas.pydata.org/) - Data manipulation
- [Tenacity](https://github.com/jd/tenacity) - Retry logic
- [ChromaDB](https://www.trychroma.com/) - Vector database for semantic search
- [sentence-transformers](https://www.sbert.net/) - Text embedding models

---

## Support

- **JobSpy Issues**: [github.com/speedyapply/JobSpy/issues](https://github.com/speedyapply/JobSpy/issues)
- **This Project**: [Open an issue](https://github.com/VincenzoImp/job-search-tool/issues)
