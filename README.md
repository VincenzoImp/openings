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
| **Semantic Search** | ChromaDB's built-in ONNX embedder (`all-MiniLM-L6-v2`) for natural language job search — no PyTorch required |
| **Bookmarks & Actions** | Bookmark, apply/unapply, and delete jobs directly from dashboard with persistent blacklist support |

### Technical Features

| Feature | Description |
|---------|-------------|
| **Parallel Execution** | ThreadPoolExecutor with configurable worker count |
| **Rate Limit Prevention** | Per-site throttling with jitter to avoid detection |
| **Fuzzy Matching** | Post-filter validation using fuzzy string matching |
| **Retry Logic** | Exponential backoff with tenacity for transient failures |
| **Dynamic Rescoring** | Automatic rescoring of existing jobs when criteria change |
| **CI/CD Pipeline** | GitHub Actions with test matrix, security audit, Docker build |
| **Comprehensive Testing** | 355+ pytest tests covering all core functionality |
| **Vector Embeddings** | Local ONNX embeddings via ChromaDB's default function — no torch runtime |

---

## Architecture

### System Overview

```
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                                JOB SEARCH TOOL                                   ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                  ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                            📄 CONFIGURATION                                │  ║
║  │    settings.yaml: queries, scoring, keywords, schedule, vector_search     │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║                                       │                                          ║
║                                       ▼                                          ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                          ⏰ SCHEDULER (APScheduler)                        │  ║
║  │              Single-shot mode  OR  Continuous (every N hours)              │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║                                       │                                          ║
║                     ┌─────────────────┼─────────────────┐                        ║
║                     ▼                 ▼                 ▼                        ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                        🔍 PARALLEL SEARCH ENGINE                           │  ║
║  │                                                                            │  ║
║  │    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐    │  ║
║  │    │  Indeed  │  │ LinkedIn │  │Glassdoor │  │  Google  │  │   ...   │    │  ║
║  │    └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘    │  ║
║  │         │             │             │             │             │          │  ║
║  │         └─────────────┴─────────────┴─────────────┴─────────────┘          │  ║
║  │                                     │                                      │  ║
║  │                      ┌──────────────┴──────────────┐                       │  ║
║  │                      │   🛡️ THROTTLING + JITTER    │                       │  ║
║  │                      │    (Rate limit prevention)  │                       │  ║
║  │                      └──────────────┬──────────────┘                       │  ║
║  └─────────────────────────────────────┼──────────────────────────────────────┘  ║
║                                        ▼                                         ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                      ⚙️ PROCESSING PIPELINE (scoring.py)                   │  ║
║  │                                                                            │  ║
║  │   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐              │  ║
║  │   │ Deduplication │───▶│    Scoring    │───▶│   Filtering   │              │  ║
║  │   │  (SHA256 ID)  │    │  (Keywords +  │    │  (Threshold)  │              │  ║
║  │   └───────────────┘    │   Weights)    │    └───────────────┘              │  ║
║  │                        └───────────────┘           │                       │  ║
║  └────────────────────────────────────────────────────┼───────────────────────┘  ║
║                                                       ▼                          ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                             💾 DATA LAYER                                  │  ║
║  │                                                                            │  ║
║  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌────────────┐  │  ║
║  │  │    SQLite DB   │  │ Vector Store │  │  CSV / Excel  │  │  Dashboard │  │  ║
║  │  │ (Primary Store)│  │  (ChromaDB)  │  │  (exporter)   │  │ (Streamlit)│  │  ║
║  │  │               │  │              │  │              │  │            │  │  ║
║  │  │ • All jobs    │  │ • Embeddings │  │ • all_jobs   │  │ • Semantic │  │  ║
║  │  │ • first_seen  │◄─┤ • Semantic   │  │ • relevant   │  │   search   │  │  ║
║  │  │ • last_seen   │  │   search     │  │   .csv/.xlsx │  │ • Bookmark │  │  ║
║  │  │ • applied     │  │ • Similarity │  │              │  │ • Bulk ops │  │  ║
║  │  │ • bookmarked  │  │   ranking    │  │              │  │ • Charts   │  │  ║
║  │  └───────┬───────┘  └──────────────┘  └──────────────┘  └────────────┘  │  ║
║  │          │                                                               │  ║
║  └──────────┼───────────────────────────────────────────────────────────────┘  ║
║             ▼                                                                    ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                         📬 NOTIFICATION SYSTEM                             │  ║
║  │                                                                            │  ║
║  │   ┌─────────────────┐      ┌──────────────────────────────────────────┐   │  ║
║  │   │   New Jobs Only │─────▶│               TELEGRAM                   │   │  ║
║  │   │  (score >= min) │      │                                          │   │  ║
║  │   └─────────────────┘      │  🔔 Job Search Tool - New Jobs Found     │   │  ║
║  │                            │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━          │   │  ║
║  │                            │  🆕 New Jobs  │  🏆 Top Jobs Overall     │   │  ║
║  │                            │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━          │   │  ║
║  │                            │  1️⃣ Backend Engineer                     │   │  ║
║  │                            │     🏢 TechCorp   📍 Remote              │   │  ║
║  │                            │     ⭐ Score: 48  [View →]               │   │  ║
║  │                            └──────────────────────────────────────────┘   │  ║
║  └────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                  ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
```

### Detailed Execution Flow

```
                                 ╔═══════════════════╗
                                 ║      STARTUP      ║
                                 ╚═════════╤═════════╝
                                           │
                     ┌─────────────────────┼─────────────────────┐
                     ▼                     ▼                     ▼
          ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
          │  Load settings   │  │  Connect to DB   │  │ Init Vector Store│
          │ (settings.yaml)  │  │   (jobs.db)      │  │   (ChromaDB)     │
          └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
                   │                     │                     │
                   └─────────────────────┼─────────────────────┘
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │         STARTUP-ONLY TASKS              │
                    │  ┌───────────────────────────────────┐  │
                    │  │ 1. Recalculate scores (scoring.py)│  │
                    │  │ 2. Backfill vector embeddings     │  │
                    │  │    (embed missing jobs into       │  │
                    │  │     ChromaDB if backfill_on_startup)│  │
                    │  └───────────────────────────────────┘  │
                    └───────────────────┬─────────────────────┘
                                        │
                   ┌────────────────────┴────────────────────┐
                   ▼                                         ▼
        ╔════════════════════╗                  ╔════════════════════╗
        ║  SINGLE-SHOT MODE  ║                  ║   SCHEDULED MODE   ║
        ║  scheduler: false  ║                  ║  scheduler: true   ║
        ║  Run once and exit ║                  ║  Run every N hours ║
        ╚═════════╤══════════╝                  ╚═════════╤══════════╝
                  │                                       │
                  └──────────────────┬────────────────────┘
                                     ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                              🔄 SEARCH CYCLE                                ║◄──┐
╠══════════════════════════════════════════════════════════════════════════════╣   │
║                                                                              ║   │
║  ┌────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 1. CLEANUP OLD JOBS (if database.cleanup_enabled: true)                │  ║   │
║  │    Delete jobs with last_seen > cleanup_days ago                       │  ║   │
║  │    Sync deletions from vector store                                    │  ║   │
║  └────────────────────────────────────────────────────────────────────────┘  ║   │
║                                       │                                      ║   │
║                                       ▼                                      ║   │
║  ┌────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 2. PARALLEL SEARCH                                                     │  ║   │
║  │                                                                        │  ║   │
║  │    For each (query, location) combination:                             │  ║   │
║  │                                                                        │  ║   │
║  │    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │  ║   │
║  │    │ Worker 1 │  │ Worker 2 │  │ Worker 3 │  │ Worker 4 │  (parallel) │  ║   │
║  │    │ "python" │  │"backend" │  │ "data"   │  │  "devops"│             │  ║   │
║  │    └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘             │  ║   │
║  │         │             │             │             │                    │  ║   │
║  │         ▼             ▼             ▼             ▼                    │  ║   │
║  │    ┌───────────────────────────────────────────────────────────────┐   │  ║   │
║  │    │                   THROTTLING (per-site delays)                │   │  ║   │
║  │    │    LinkedIn: 3.0s  │  Indeed: 1.0s  │  Glassdoor: 1.5s       │   │  ║   │
║  │    │                   + random jitter (±30%)                     │   │  ║   │
║  │    └───────────────────────────────────────────────────────────────┘   │  ║   │
║  └────────────────────────────────────────────────────────────────────────┘  ║   │
║                                       │                                      ║   │
║                                       ▼                                      ║   │
║  ┌────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 3. COMBINE & DEDUPLICATE                                               │  ║   │
║  │    job_id = SHA256(title + company + location) → 64-char unique hash   │  ║   │
║  └────────────────────────────────────────────────────────────────────────┘  ║   │
║                                       │                                      ║   │
║                                       ▼                                      ║   │
║  ┌────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 4. CALCULATE RELEVANCE SCORES (scoring.py)                             │  ║   │
║  │                                                                        │  ║   │
║  │    For each job:                                                       │  ║   │
║  │    ┌──────────────────────────────────────────────────────────────┐    │  ║   │
║  │    │  text = title + description + company + location             │    │  ║   │
║  │    │  for category in scoring.keywords:                           │    │  ║   │
║  │    │      if any keyword matches → score += weights[category]     │    │  ║   │
║  │    └──────────────────────────────────────────────────────────────┘    │  ║   │
║  └────────────────────────────────────────────────────────────────────────┘  ║   │
║                                       │                                      ║   │
║                                       ▼                                      ║   │
║  ┌────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 5. FILTER BY THRESHOLD                                                 │  ║   │
║  │    Keep only jobs where: score >= scoring.threshold                    │  ║   │
║  └────────────────────────────────────────────────────────────────────────┘  ║   │
║                                       │                                      ║   │
║              ┌────────────────────────┼────────────────────────┐              ║   │
║              ▼                        ▼                        ▼              ║   │
║  ┌──────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐    ║   │
║  │  6a. SAVE TO DB  │  │ 6b. EMBED IN VECTOR  │  │ 6c. SAVE CSV/EXCEL  │    ║   │
║  │                  │  │     STORE (ChromaDB)  │  │    (exporter.py)    │    ║   │
║  │  UPSERT logic:   │  │                      │  │                      │    ║   │
║  │  • New → INSERT  │  │  ChromaDB ONNX embeds │  │  • all_jobs.csv     │    ║   │
║  │  • Old → UPDATE  │  │  job text into vectors│  │  • relevant.xlsx    │    ║   │
║  │  (last_seen,     │  │  for semantic similar-│  │                      │    ║   │
║  │   score)         │  │  ity search (default) │  │                      │    ║   │
║  └────────┬─────────┘  └──────────────────────┘  └──────────────────────┘    ║   │
║           │                                                                   ║   │
║           ▼                                                                   ║   │
║  ┌────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 7. IDENTIFY NEW JOBS                                                   │  ║   │
║  │    New = jobs where first_seen = today (never seen before)             │  ║   │
║  └────────────────────────────────────────────────────────────────────────┘  ║   │
║                                       │                                      ║   │
║                                       ▼                                      ║   │
║  ┌────────────────────────────────────────────────────────────────────────┐  ║   │
║  │ 8. SEND TELEGRAM NOTIFICATION                                          │  ║   │
║  │                                                                        │  ║   │
║  │    🆕 New Jobs (score >= min_score_for_notification)                    │  ║   │
║  │    🏆 Top Jobs Overall (from entire database)                          │  ║   │
║  │    Chunked messages (10 jobs per msg to avoid 4096 char limit)         │  ║   │
║  └────────────────────────────────────────────────────────────────────────┘  ║   │
║                                       │                                      ║   │
╠═══════════════════════════════════════╧══════════════════════════════════════╣   │
║                              CYCLE COMPLETE                                  ║   │
║                                                                              ║   │
║    Scheduled mode? ───────────────────────────────▶ Wait N hours ────────────╫───┘
║         │                                                                    ║
║         ▼                                                                    ║
║    Single-shot mode? ─────────────────────────────▶ EXIT                     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
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

### Option 1: Docker Hub Image (Recommended)

```bash
# Clone the repository
git clone https://github.com/VincenzoImp/job-search-tool.git
cd job-search-tool

# Optional on Linux: align container writes with your host user
export JOB_SEARCH_UID=$(id -u)
export JOB_SEARCH_GID=$(id -g)

# Start from the published Docker Hub image
cp .env.example .env
docker compose pull

# Scaffold editable config/settings.yaml from the bundled template
docker compose run --rm init-config

# Edit configuration with your preferences
# nano config/settings.yaml

# Run the default stack: single-shot search + dashboard
docker compose up

# Or run continuously with scheduler instead of single-shot
docker compose --profile scheduler up scheduler dashboard -d

# Dashboard is available at http://localhost:8501
```

`docker compose up` starts both `jobsearch` (single-shot) and `dashboard` by default — no profile flags needed. The `jobsearch` and `scheduler` services force the expected runtime mode via `JOB_SEARCH_MODE`, so Compose behaves consistently even if `scheduler.enabled` differs inside `config/settings.yaml`.

### Two Docker image variants

The project publishes **two variants** of the Docker image from the same tag family:

| Variant | Tag example | Contents | Size |
|---|---|---|---|
| **Dashboard** (default) | `vincenzoimp/job-search-tool:latest` | Full stack, includes Streamlit UI | larger |
| **Core** (slim) | `vincenzoimp/job-search-tool:latest-core` | No Streamlit (~200 MB smaller) | smaller |

`docker-compose.yml` automatically wires headless services (`jobsearch`, `scheduler`, `analyze`, `init-config`) to the **core** image, and the `dashboard` service to the **dashboard** image. You get the weight savings for free without needing to think about it. Override either via `JOB_SEARCH_CORE_IMAGE` / `JOB_SEARCH_DASHBOARD_IMAGE` env vars.

To build locally, pick the variant via `--build-arg VARIANT=core|dashboard`:

```bash
docker build -t job-search-tool .                               # dashboard (default)
docker build --build-arg VARIANT=core -t job-search-tool:core . # core (slim)
```

### Compose Services

- `init-config`: Creates `config/settings.yaml` and `config/settings.example.yaml` from the bundled image template (core image)
- `jobsearch`: Runs a single search cycle and exits — **starts by default** (core image)
- `dashboard`: Starts the Streamlit UI on port `8501` — **starts by default** (dashboard image)
- `scheduler`: Keeps the application running with APScheduler (opt-in via `--profile scheduler`, core image)
- `analyze`: Runs the analysis utilities against the existing database (opt-in via `--profile analyze`, core image)

### Option 2: Standalone Docker Compose (No Clone)

If you want the clean Compose workflow without cloning this repository, create an empty folder and add this minimal `docker-compose.yml`:

```yaml
name: job-search-tool

x-job-search-base: &job-search-base
  user: "${JOB_SEARCH_UID:-1000}:${JOB_SEARCH_GID:-1000}"
  volumes:
    - ./config:/app/config
    - ./data:/app/data
    - ./results:/app/results
    - ./logs:/app/logs

x-job-search-core: &job-search-core
  <<: *job-search-base
  image: vincenzoimp/job-search-tool:latest-core

x-job-search-dashboard: &job-search-dashboard
  <<: *job-search-base
  image: vincenzoimp/job-search-tool:latest

services:
  init-config:
    <<: *job-search-core
    command: python bootstrap_config.py --write-settings
    restart: "no"

  jobsearch:
    <<: *job-search-core
    command: python main.py
    environment:
      JOB_SEARCH_MODE: single

  scheduler:
    <<: *job-search-core
    command: python main.py
    environment:
      JOB_SEARCH_MODE: scheduled
    profiles:
      - scheduler

  dashboard:
    <<: *job-search-dashboard
    command: streamlit run dashboard.py --server.address=0.0.0.0 --server.port=8501
    ports:
      - "8501:8501"
```

Then run:

```bash
mkdir -p config data results logs

# Optional on Linux: align container writes with your host user
export JOB_SEARCH_UID=$(id -u)
export JOB_SEARCH_GID=$(id -g)

docker compose pull
docker compose run --rm init-config

# Edit config/settings.yaml, then start the default stack (jobsearch + dashboard):
docker compose up
```

Headless services run on the slim `:latest-core` image; the dashboard runs on the full `:latest` image with Streamlit bundled. This is the cleanest no-clone setup because you still get `init-config`, `jobsearch`, `scheduler`, and `dashboard` as named services instead of remembering long `docker run` commands.

### Option 3: Local Python

```bash
# Clone and navigate
git clone https://github.com/VincenzoImp/job-search-tool.git
cd job-search-tool

# Install uv if needed: https://docs.astral.sh/uv/getting-started/installation/

# Create/sync the project environment from the lockfile
uv sync --locked --no-install-project

# Create configuration
cp config/settings.example.yaml config/settings.yaml

# Run the search
cd scripts && uv run python main.py

# Launch dashboard
uv run streamlit run dashboard.py
```

### Option 4: Local Docker Build (Developer Workflow)

```bash
# Build the image from your local checkout instead of Docker Hub
docker compose -f docker-compose.yml -f docker-compose.dev.yml build

# Then use the same services as the Docker Hub workflow
docker compose -f docker-compose.yml -f docker-compose.dev.yml up jobsearch
docker compose -f docker-compose.yml -f docker-compose.dev.yml up dashboard
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
  model_name: "all-MiniLM-L6-v2"  # Ignored: always uses ChromaDB's default ONNX embedder (~80 MB)
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
- **Inline Actions**: Mark applied, bookmark, delete-and-blacklist, open URL from each card
- **Bulk Operations**: Select multiple jobs for batch apply, bookmark, and delete actions
- **Analytics Tab**: Charts for source distribution, score breakdown, trends
- **Database Management**: Review database stats, export data, and manage blacklisted deletions
- **Pagination**: 20 jobs per page with navigation

Deleting a job from the dashboard is persistent: the job is removed from the active `jobs` table and its internal `job_id` is stored in a blacklist so future searches skip it automatically.

### Launch

```bash
# Docker Hub image
docker compose up dashboard
# Access at http://localhost:8501

# Local Python
cd scripts && uv run streamlit run dashboard.py
```

### Standalone Docker Compose Without Cloning

If you do not want to clone this repository, the cleanest Docker-only path is still Compose. Use the standalone `docker-compose.yml` example from the Quick Start section above, then run:

```bash
docker compose pull
docker compose run --rm init-config
docker compose up jobsearch
docker compose up dashboard
```

### Direct Docker Hub Usage

If you prefer `docker run` instead of Compose. For headless usage (no dashboard UI), prefer the slim `:latest-core` tag to save ~200 MB:

```bash
docker pull vincenzoimp/job-search-tool:latest-core

mkdir -p config data results logs

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/config:/app/config" \
  -v "$PWD/data:/app/data" \
  -v "$PWD/results:/app/results" \
  -v "$PWD/logs:/app/logs" \
  vincenzoimp/job-search-tool:latest-core \
  python bootstrap_config.py --write-settings

# Edit config/settings.yaml, then run the search
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/config:/app/config" \
  -v "$PWD/data:/app/data" \
  -v "$PWD/results:/app/results" \
  -v "$PWD/logs:/app/logs" \
  vincenzoimp/job-search-tool:latest-core
```

To run the Streamlit dashboard via `docker run`, swap `:latest-core` for `:latest` and add `-p 8501:8501 --entrypoint streamlit vincenzoimp/job-search-tool:latest run dashboard.py --server.address=0.0.0.0 --server.port=8501`.

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

Deleted jobs are also tracked in a separate `deleted_jobs` table. When you delete a job from the dashboard, the tool stores its internal `job_id` in that blacklist and future search runs will skip it instead of re-inserting it into `jobs`.

The blacklist uses the same internal identifier used for deduplication: `SHA256(title + company + location)`. If a future posting changes enough to generate a different internal ID, it will be treated as a new job.

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
# Refresh the published image
docker compose pull
docker compose up jobsearch
```

```bash
# Full local rebuild (developer workflow)
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
docker system prune -f
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
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
├── docker/
│   └── entrypoint.sh              # Runtime bootstrap + Docker guidance
├── scripts/
│   ├── main.py                    # Unified entry point
│   ├── bootstrap_config.py        # Generate editable config for Docker users
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
├── tests/                          # 355+ pytest tests
│   ├── conftest.py                # Shared fixtures
│   ├── test_bootstrap_config.py   # Docker config bootstrap tests
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
├── .github/workflows/publish-main.yml
├── .github/workflows/publish-release.yml
├── results/                        # CSV/Excel output (gitignored)
├── data/                           # SQLite database (gitignored)
├── logs/                           # Log files (gitignored)
├── Dockerfile                      # Multi-stage build with OCI metadata
├── docker-compose.yml              # Docker Hub-first runtime stack
├── docker-compose.dev.yml          # Local-build override for developers
├── .pre-commit-config.yaml         # Ruff, trailing whitespace, etc.
├── pyproject.toml                  # Dependency metadata for uv
├── uv.lock                         # Locked dependency resolution for CI/Docker
├── requirements.txt                # Compatibility dependency mirror
├── requirements-dev.txt            # Compatibility dev dependency mirror
└── pytest.ini
```

### Docker Publishing

The repository includes two Docker Hub publishing workflows:

- `.github/workflows/publish-release.yml` is the automatic release path for version tags
- `.github/workflows/publish-main.yml` is a manual maintainer-only escape hatch for publishing the current `main` branch

Both workflows build a **matrix of two variants** from the same `Dockerfile` via `--build-arg VARIANT=core|dashboard`:

- **dashboard** (default, includes Streamlit UI) publishes under the unsuffixed tag family: `:latest`, `:vX.Y.Z`, `:vX.Y`, `:vX`, `:sha-<commit>`
- **core** (slim, no Streamlit, ~200 MB smaller) publishes under the `-core` suffixed tag family: `:latest-core`, `:vX.Y.Z-core`, `:vX.Y-core`, `:vX-core`, `:sha-<commit>-core`, plus the raw `:core` alias

Publishing policy:

- pull requests run the Docker smoke build in CI **for both variants in parallel**, and healthcheck each image — regressions in either build path are caught before merge
- pushes to `main` run validation jobs, but do not automatically republish Docker images
- version tags such as `v5.0.0` publish the full multi-arch release (`linux/amd64` + `linux/arm64`) **for both variants** and refresh both `:latest` and `:latest-core`
- `publish-main.yml` can be triggered manually when maintainers intentionally want a fresh `main` / `sha-*` image (both variants)
- workflow concurrency is enabled so older in-flight publishes on the same ref are cancelled automatically
- `uv.lock` is the dependency source of truth for CI and Docker image builds

Maintainers should configure:

- `DOCKERHUB_USERNAME` repository secret
- `DOCKERHUB_TOKEN` repository secret
- optional `DOCKERHUB_IMAGE` repository variable if you want a different image name than `vincenzoimp/job-search-tool`

### Running Tests

```bash
# Sync the locked development environment
uv sync --locked --no-install-project

# Run all tests
uv run pytest

# With coverage report
uv run pytest --cov=scripts --cov-report=html

# Specific test file
uv run pytest tests/test_config.py -v
```

### Code Quality

```bash
# Run pre-commit hooks (ruff lint + format, trailing whitespace, etc.)
uv run pre-commit run --all-files

# Type checking
uv run mypy scripts/ --ignore-missing-imports

# Linting
uv run ruff check scripts/

# Formatting
uv run ruff format scripts/
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
- [ChromaDB](https://www.trychroma.com/) - Vector database for semantic search, with built-in ONNX embedder (`all-MiniLM-L6-v2`)

---

## Support

- **JobSpy Issues**: [github.com/speedyapply/JobSpy/issues](https://github.com/speedyapply/JobSpy/issues)
- **This Project**: [Open an issue](https://github.com/VincenzoImp/job-search-tool/issues)
