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
| **Comprehensive Testing** | 483 pytest tests covering all core functionality |
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
║  │   ┌───────────────┐    ┌───────────────┐    ┌────────────────────┐         │  ║
║  │   │ Deduplication │───▶│    Scoring    │───▶│    Partitioning    │         │  ║
║  │   │  (SHA256 ID)  │    │  (Keywords +  │    │ save_threshold /   │         │  ║
║  │   └───────────────┘    │   Weights)    │    │ notify_threshold   │         │  ║
║  │                        └───────────────┘    └────────────────────┘         │  ║
║  │                                                     │                       │  ║
║  └────────────────────────────────────────────────────┼───────────────────────┘  ║
║                                                       ▼                          ║
║  ┌────────────────────────────────────────────────────────────────────────────┐  ║
║  │                             💾 DATA LAYER                                  │  ║
║  │                                                                            │  ║
║  │  ┌───────────────┐  ┌───────────────┐  ┌────────────────┐ ┌────────────┐│  ║
║  │  │    SQLite DB   │  │ Vector Store │  │ Dashboard UI   │ │  On-demand ││  ║
║  │  │ (Primary Store)│  │  (ChromaDB)  │  │  (Streamlit)   │ │   exports  ││  ║
║  │  │               │  │              │  │                │ │ (exporter) ││  ║
║  │  │ • All jobs    │  │ • Embeddings │  │ • Semantic srch│ │            ││  ║
║  │  │ • first_seen  │◄─┤ • Semantic   │  │ • Bookmark/Apply││• CSV/Excel ││  ║
║  │  │ • last_seen   │  │   search     │  │ • Database tab │ │  from DB   ││  ║
║  │  │ • applied     │  │ • Similarity │  │ • Smart cleanup│ │  tab only  ││  ║
║  │  │ • bookmarked  │  │   ranking    │  │ • Charts       │ │            ││  ║
║  │  └───────┬───────┘  └──────────────┘  └────────────────┘ └────────────┘│  ║
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
        ║  main.py once      ║                  ║  main.py scheduler ║
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
║  │ 1. RETENTION RECONCILIATION (runs once per boot, not per cycle)        │  ║   │
║  │    db.reconcile_with_config(config) applies:                           │  ║   │
║  │      • database.retention.max_age_days       → delete_stale_jobs       │  ║   │
║  │      • database.retention.purge_blacklist_after_days → purge_blacklist │  ║   │
║  │    Bookmarked & applied jobs are protected at the SQL level.           │  ║   │
║  │    Vector store is synced to match.                                    │  ║   │
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
║  │ 5. PARTITION BY THRESHOLDS (scoring.partition_by_thresholds)           │  ║   │
║  │    to_save   = score >= scoring.save_threshold                         │  ║   │
║  │    to_notify = score >= scoring.notify_threshold   (notify ≥ save)     │  ║   │
║  └────────────────────────────────────────────────────────────────────────┘  ║   │
║                                       │                                      ║   │
║                   ┌───────────────────┴───────────────────┐                  ║   │
║                   ▼                                       ▼                  ║   │
║  ┌──────────────────────────┐           ┌──────────────────────────────┐    ║   │
║  │  6a. SAVE to_save → DB   │           │  6b. EMBED in VECTOR STORE   │    ║   │
║  │                          │           │       (ChromaDB, ONNX)       │    ║   │
║  │  UPSERT logic:           │           │                              │    ║   │
║  │  • exclude_blacklisted() │           │  Embeds to_save rows into    │    ║   │
║  │  • New → INSERT          │           │  vectors for semantic search │    ║   │
║  │  • Old → UPDATE          │           │                              │    ║   │
║  │    (last_seen, score)    │           │  (No automatic CSV/Excel —   │    ║   │
║  │                          │           │   exports are on-demand from │    ║   │
║  │                          │           │   the dashboard Database tab)│    ║   │
║  └────────┬─────────────────┘           └──────────────────────────────┘    ║   │
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
║  │    🆕 New Jobs (score >= scoring.notify_threshold)                      │  ║   │
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
| **Database** | `database.py` | SQLite CRUD, deduplication, retention reconciliation (WAL mode) |
| **Configuration** | `config.py` | YAML loading, validation, type safety |
| **Scoring** | `scoring.py` | Relevance scoring engine |
| **Exporter** | `exporter.py` | On-demand CSV/Excel export (dashboard Database tab only) |
| **Dashboard** | `dashboard.py` | Unified Job Search Hub with semantic search |
| **Vector Store** | `vector_store.py` | ChromaDB semantic search |
| **Vector Commands** | `vector_commands.py` | Embedding backfill and sync |
| **Service Layer** | `job_service.py` | Shared DB/VS init, record serialization, filtering |
| **REST API** | `api_server.py` | FastAPI adapter for programmatic access |
| **MCP Server** | `mcp_server.py` | MCP adapter for LLMs (DB access + config knowledge) |

---

## Quick Start

You only need Docker. The layout is two files in a folder:

```
my-jobsearch/
├── docker-compose.yml
└── settings.yaml
```

The tool **requires** a valid `settings.yaml` — there is no default, no fallback, no auto-generated config. Three steps:

### 1. Get `settings.yaml`

Fetch the documented example template and edit it. Pick whichever source is more convenient:

```bash
mkdir my-jobsearch && cd my-jobsearch

# Option A — from the published Docker Hub image
docker run --rm --entrypoint cat vincenzoimp/job-search-tool:latest \
  /opt/job-search-tool/defaults/settings.example.yaml > settings.yaml

# Option B — directly from GitHub
curl -fsSL -o settings.yaml \
  https://raw.githubusercontent.com/VincenzoImp/job-search-tool/main/config/settings.example.yaml
```

Then edit it with any editor (`vim`, `nano`, VS Code, ...):

```bash
vim settings.yaml
```

Set at least `search`, `queries`, and `scoring`. Telegram notifications are disabled by default — enable them only if you have a bot token.

### 2. Drop this `docker-compose.yml` next to `settings.yaml`

```yaml
volumes:
  jobsearch-data:
    name: jobsearch-data

services:
  scheduler:
    image: vincenzoimp/job-search-tool:latest
    restart: unless-stopped
    command: ["python", "main.py", "scheduler"]
    volumes:
      - jobsearch-data:/data
      - ./settings.yaml:/data/config/settings.yaml:ro

  dashboard:
    image: vincenzoimp/job-search-tool:latest
    restart: unless-stopped
    command: ["python", "main.py", "dashboard"]
    ports: ["8501:8501"]
    volumes:
      - jobsearch-data:/data
      - ./settings.yaml:/data/config/settings.yaml:ro
```

### 3. Start

```bash
docker compose up -d
```

Open **http://localhost:8501** for the dashboard. The scheduler starts its first search immediately and then runs every `scheduler.interval_hours` (24 by default).

### Updating `settings.yaml` later

```bash
vim settings.yaml                  # edit on your host
docker compose restart scheduler   # the container re-reads it on restart
```

That's the whole maintenance loop. `settings.yaml` is bind-mounted as a read-only file, so the container picks up your changes on every restart — no `cp`, no `inject`, no `rebuild`.

### How the split works

| What | Where it lives | Who touches it |
|---|---|---|
| `settings.yaml` | A plain file on your host (`./settings.yaml`) | **You**, with any editor |
| SQLite database, ChromaDB vectors, CSV/Excel exports, logs | The Docker-managed named volume `jobsearch-data` | The container (non-root, UID 1000) |

The split is deliberate. The only thing you ever want to *edit* is `settings.yaml`, so it sits on the host in plain sight. Everything else is internal state Docker owns — no permission issues, no host-side `chown`, no UID/GID gymnastics. It's the same split the official `postgres` image uses for `postgresql.conf` vs. `PGDATA`.

### What you get

- **scheduler** — continuous search loop (`main.py scheduler`). `restart: unless-stopped` makes it survive crashes, reboots, and rate-limit retries automatically.
- **dashboard** — Streamlit UI on port `8501` (`main.py dashboard`). Reads the same SQLite database and vector store the scheduler writes to.
- **One image, one managed volume, one host file** — both services pull `vincenzoimp/job-search-tool:latest` (Docker downloads it once and shares layers).
- **Non-root everywhere** — both containers run as UID 1000 (`appuser`). The named volume inherits ownership from the image at first mount and `settings.yaml` is read-only, so there is never a permission issue regardless of your host's Docker daemon configuration.

### Missing or invalid `settings.yaml`

If you run `docker compose up -d` before creating `settings.yaml`, both containers exit with a clear error message (plus a hint about the common "Docker compose created it as a directory because the file wasn't there yet" pitfall). Docker's `restart: unless-stopped` will keep retrying, so as soon as you add the file and `docker compose restart scheduler`, the stack recovers on its own.

### Back up and restore

```bash
# Config: a plain file, back it up however you like
cp settings.yaml settings.yaml.bak

# Database + vector store: standard Docker volume backup pattern
docker run --rm -v jobsearch-data:/data -v "$PWD:/backup" \
  alpine tar czf /backup/jobsearch-data.tgz -C /data .

# Restore
docker run --rm -v jobsearch-data:/data -v "$PWD:/backup" \
  alpine tar xzf /backup/jobsearch-data.tgz -C /data
```

### The `main.py` CLI

The same entry point handles all operating modes via subcommands:

```bash
python main.py                # scheduler (continuous loop, default)
python main.py scheduler      # same as above, explicit
python main.py once           # run a single search iteration and exit
python main.py dashboard      # replace the process with the Streamlit UI
```

Both inside the container and during local development this is the only entry point you need.

### Local Python (for development)

```bash
git clone https://github.com/VincenzoImp/job-search-tool.git
cd job-search-tool
uv sync --locked                                # installs all runtime + dev deps
cp config/settings.example.yaml config/settings.yaml
uv run python scripts/main.py                   # continuous scheduler
uv run python scripts/main.py once              # single-shot run
uv run python scripts/main.py dashboard         # streamlit UI on http://localhost:8501
```

In local development, `JOB_SEARCH_DATA_DIR` is unset and the project root is used as the root — `db/jobs.db`, `chroma/`, `results/`, `logs/search.log`, `config/settings.yaml` all live at the repo root.

### Local Docker build (developer workflow)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This rebuilds the single image from the local checkout and runs the two services against it.

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
  save_threshold: 0           # Minimum score to be persisted to the DB
  notify_threshold: 20        # Minimum score to trigger Telegram notifications
                              # (must be >= save_threshold; enforced at load time)

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
- A job is saved if its score is at least `save_threshold`, and only notified if it additionally reaches `notify_threshold`

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
    max_jobs_in_message: 50           # Maximum jobs per notification
    # Notification floor is scoring.notify_threshold (see above) — no per-channel override.
```

### Vector Search

```yaml
vector_search:
  enabled: true                 # Enable semantic search (default: true)
  embed_on_save: true           # Auto-embed new jobs
  default_results: 20           # Max semantic search results
  backfill_on_startup: true     # Embed existing jobs at startup
  batch_size: 100               # Embedding batch size
```

The ONNX embedder (bundled `all-MiniLM-L6-v2`) and the persistence path (`{JOB_SEARCH_DATA_DIR}/chroma`) are fixed — use `JOB_SEARCH_DATA_DIR` to relocate the tree.

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
   docker compose restart scheduler
   docker compose logs -f scheduler
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
- **Database Tab**: Health metrics, dynamic score-distribution histogram, four smart-cleanup cards (delete below score, delete stale, purge blacklist, apply `settings.yaml` retention now), on-demand CSV/Excel export, and a Danger zone with a "Full reset" button (the only path that bypasses bookmark/applied protection)
- **Pagination**: 20 jobs per page with navigation

Deleting a job from the dashboard is persistent: the job is removed from the active `jobs` table and its internal `job_id` is stored in a blacklist so future searches skip it automatically.

### Launch

The dashboard is part of the default Compose stack — it's already running at **http://localhost:8501** after `docker compose up -d`. To stop or restart it individually:

```bash
docker compose restart dashboard
docker compose logs -f dashboard
```

For local Python development:

```bash
uv run python scripts/main.py dashboard
```

### Bare `docker run` (no Compose)

Same split as the Compose path: `settings.yaml` is a host-side file bind-mounted into the container; everything else lives in the named volume `jobsearch-data`.

```bash
# 1. Fetch and edit the settings template
docker run --rm --entrypoint cat vincenzoimp/job-search-tool:latest \
  /opt/job-search-tool/defaults/settings.example.yaml > settings.yaml
vim settings.yaml

# 2. Start the scheduler (continuous loop)
docker run -d --name jobsearch-scheduler \
  -v jobsearch-data:/data \
  -v "$PWD/settings.yaml:/data/config/settings.yaml:ro" \
  --restart unless-stopped \
  vincenzoimp/job-search-tool:latest

# 3. Start the dashboard (Streamlit UI on :8501)
docker run -d --name jobsearch-dashboard \
  -v jobsearch-data:/data \
  -v "$PWD/settings.yaml:/data/config/settings.yaml:ro" \
  -p 8501:8501 \
  --restart unless-stopped \
  vincenzoimp/job-search-tool:latest \
  python main.py dashboard
```

Both containers share the same `jobsearch-data` volume (Docker creates it on first mount) and the same host-side `settings.yaml`. If `./settings.yaml` doesn't exist when you run step 2 or step 3, both containers exit with the same "missing required configuration" error you'd get under Compose.

---

## API & MCP Server

Two optional services provide programmatic access to the job database.

| Service | Purpose | Port |
|---------|---------|------|
| **REST API** (`api_server.py`) | CRUD wrapper over the job database for scripts, automations, and external tools. Auto-docs at `/docs`. | 8502 |
| **MCP Server** (`mcp_server.py`) | Tool server for LLMs (Claude, etc.). Gives the model DB access and settings.yaml schema knowledge so it can act as a job search assistant. | 3001 |

### Enable via Docker Compose

Both services use Compose profiles and don't start by default:

```bash
# Start API only
docker compose --profile api up -d

# Start both API and MCP
docker compose --profile api --profile mcp up -d

# Default stack (scheduler + dashboard) is unaffected
docker compose up -d
```

### REST API quick start

```bash
# List top jobs
curl http://localhost:8502/jobs?limit=5&min_score=20

# Get a single job
curl http://localhost:8502/jobs/{job_id}

# Semantic search
curl "http://localhost:8502/jobs/search/semantic?q=python+backend&n_results=10"

# Bookmark a job
curl -X POST http://localhost:8502/jobs/{job_id}/bookmark

# Full API docs
open http://localhost:8502/docs
```

### MCP Server for Claude Code

Add to your `.claude/settings.json`:

```json
{
  "mcpServers": {
    "job-search-tool": {
      "url": "http://localhost:3001/sse"
    }
  }
}
```

Then ask Claude naturally: "Show me the top 10 jobs", "Bookmark that backend engineer role", "What does the scoring section in settings.yaml do?".

The MCP server does NOT read your `settings.yaml` or profile -- it has a built-in `get_settings_documentation` tool that returns the full schema reference. You provide your context in the conversation.

---

## Data Storage

State lives in two places:

| Kind | Location | Mount type |
|---|---|---|
| **Your `settings.yaml`** | A host file next to `docker-compose.yml` | Read-only file bind mount → `/data/config/settings.yaml` |
| **Database, vector store, results, logs** | Docker-managed volume `jobsearch-data` | Named volume → `/data` |

Inside the container the combined `/data` tree looks like this:

```
/data/
├── config/settings.yaml   # bind-mounted from ./settings.yaml (read-only)
├── db/jobs.db             # SQLite store (inside jobsearch-data)
├── chroma/                # ChromaDB vector store (inside jobsearch-data)
├── results/               # On-demand CSV/Excel exports from the dashboard (inside jobsearch-data)
└── logs/search.log        # rotating application log (inside jobsearch-data)
```

For local Python development `JOB_SEARCH_DATA_DIR` is unset so the repo root stands in for `/data` — all the subdirectories above materialise at the root of your checkout instead of inside the Docker volume.

### Back up and restore

```bash
# Snapshot the whole volume
docker run --rm -v jobsearch-data:/data -v "$PWD:/backup" \
  alpine tar czf /backup/jobsearch-data.tgz -C /data .

# Restore from a snapshot
docker run --rm -v jobsearch-data:/data -v "$PWD:/backup" \
  alpine tar xzf /backup/jobsearch-data.tgz -C /data
```

### Primary Storage: SQLite Database

The SQLite database (at `db/jobs.db` inside the volume) is the primary storage mechanism:

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
docker compose exec scheduler sqlite3 /data/db/jobs.db "SELECT COUNT(*), AVG(relevance_score) FROM jobs"

# Today's new jobs
docker compose exec scheduler sqlite3 /data/db/jobs.db "SELECT title, company, relevance_score FROM jobs WHERE first_seen = date('now') ORDER BY relevance_score DESC"

# Top unapplied jobs
docker compose exec scheduler sqlite3 /data/db/jobs.db "SELECT title, company, relevance_score FROM jobs WHERE applied = 0 ORDER BY relevance_score DESC LIMIT 10"

# Mark job as applied
docker compose exec scheduler sqlite3 /data/db/jobs.db "UPDATE jobs SET applied = 1 WHERE job_id = 'your_job_id'"

# Distribution by source
docker compose exec scheduler sqlite3 /data/db/jobs.db "SELECT site, COUNT(*) as count FROM jobs GROUP BY site ORDER BY count DESC"

# Remote opportunities
docker compose exec scheduler sqlite3 /data/db/jobs.db "SELECT title, company FROM jobs WHERE is_remote = 1 ORDER BY relevance_score DESC LIMIT 20"
```

### On-demand Exports

The search pipeline never writes spreadsheets. Exports are produced exclusively
on demand from the dashboard's **Database** tab, which calls
`scripts/exporter.export_dataframe(df, output_dir, basename, fmt)` with the
currently filtered rows. Output files land under `{DATA_DIR}/results/` with a
user-chosen basename and format (`csv` or `excel`), and all cells are sanitized
against formula injection before being written.

There is no `output:` config section, no automatic `all_jobs_*.csv` /
`relevant_jobs_*.csv` generation, and no toggle to re-enable the old behavior.

---

## Troubleshooting

### Rate Limiting (empty results, HTTP 429)

Job boards aggressively rate-limit scraping traffic. Tune the throttling knobs in your `settings.yaml`:

```yaml
throttling:
  enabled: true
  default_delay: 2.5          # Increase delay
  site_delays:
    linkedin: 5.0             # LinkedIn is the most aggressive

parallel:
  max_workers: 2              # Reduce concurrency

search:
  results_wanted: 20          # Reduce per-query results
```

### Glassdoor: "location not parsed" (HTTP 400)

Glassdoor's API is strict about location string format and rejects many perfectly valid-looking inputs (e.g. `"New York, NY"`, `"San Francisco, CA"`) with a cryptic 400. The bundled default `settings.yaml` does **not** query Glassdoor for exactly this reason.

If you want Glassdoor coverage, test your location manually first on glassdoor.com and verify that the format you use in `search.locations` resolves cleanly. When it does, re-enable it:

```yaml
search:
  sites:
    - "indeed"
    - "linkedin"
    - "glassdoor"    # add back once your location format works
```

Duplicate `Glassdoor: location not parsed` errors inside a single run are automatically deduplicated in the logs — you'll see the first one and the rest are silently suppressed.

### `[Errno 113] No route to host` on Indeed / Glassdoor / Cloudflare CDNs

This happens when some Cloudflare anycast IPs are unreachable from your host — usually because IPv6 is half-configured (the container gets a v6 address but there's no functioning default v6 route) or because a firewall blackhole-drops certain ranges.

The default `docker-compose.yml` already mitigates the two most common causes:
- `networks.default.enable_ipv6: false` — the container stack never attempts IPv6 connectivity, so Python's `getaddrinfo` only returns v4 results.
- `dns: [1.1.1.1, 8.8.8.8]` — explicit public resolvers bypass the embedded Docker DNS → host DNS chain, which is a frequent source of stale or broken lookups.

If the error persists, run this diagnostic inside the container to see which Cloudflare IPs your host reaches:

```bash
docker compose exec scheduler python -c "
import socket
for host in ['apis.indeed.com', 'www.linkedin.com', 'www.glassdoor.com']:
    try:
        socket.create_connection((host, 443), 5).close()
        print(f'{host} OK')
    except Exception as e:
        print(f'{host} FAIL ({type(e).__name__}: {e})')
"
```

Persistent failures with `No route to host` point to a host-level networking problem (firewall, conntrack exhaustion, routing misconfiguration) that this tool cannot fix. Check `dmesg`, conntrack (`cat /proc/sys/net/netfilter/nf_conntrack_count`), and MTU.

### Upgrading with deprecated keys in your `settings.yaml`

`settings.yaml` is a host file next to `docker-compose.yml` — you own it, Docker doesn't. Upgrades that remove or rename keys (for example the old `scheduler.enabled` flag) emit a one-line deprecation warning in the logs rather than breaking. To fix them, just edit the file:

```bash
vim settings.yaml                  # remove the keys flagged by the warning
docker compose restart scheduler   # reload
```

If the database or vector store itself was built against an older schema and you want to start from a clean slate:

```bash
docker compose down -v             # removes the jobsearch-data volume and the DB with it
docker compose up -d               # fresh start, settings.yaml untouched
```

`docker compose down -v` only touches the Docker-managed volume — your host-side `settings.yaml` is never affected.

### Database locked

The SQLite store runs with WAL mode and `busy_timeout=5000` to handle concurrent access, but SQLite still allows only one writer at a time. If something is holding the write lock:

```bash
docker compose restart scheduler    # clean restart releases any stale lock
```

### Local Docker rebuild

When you change code or the `Dockerfile` and want to rebuild instead of pulling:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

### Python version (local development)

JobSpy requires Python 3.11+:

```bash
python3 --version
# If below 3.11, either upgrade or use the Docker stack instead.
```

---

## Development

### Project Structure

```
job-search-tool/
├── config/
│   └── settings.example.yaml      # Documented reference template (never copied into the user's volume)
├── docker/
│   └── entrypoint.sh              # Creates /data subtree and requires settings.yaml to exist
├── scripts/
│   ├── main.py                    # CLI entry point with `scheduler` / `once` / `dashboard` subcommands
│   ├── search_jobs.py             # Core search with parallel execution
│   ├── scheduler.py               # APScheduler integration
│   ├── notifier.py                # Telegram notifications
│   ├── dashboard.py               # Streamlit UI
│   ├── database.py                # SQLite persistence (WAL mode)
│   ├── config.py                  # Configuration loader + JOB_SEARCH_DATA_DIR resolver
│   ├── logger.py                  # Structured logging
│   ├── models.py                  # Type-safe dataclasses
│   ├── scoring.py                 # Relevance scoring engine
│   ├── exporter.py                # CSV/Excel export with sanitization
│   ├── vector_store.py            # ChromaDB vector store (ONNX embedder)
│   ├── vector_commands.py         # Vector backfill/sync
│   ├── job_service.py             # Shared service layer (DB/VS init, serialization, filtering)
│   ├── api_server.py              # REST API adapter (FastAPI, port 8502)
│   ├── mcp_server.py              # MCP server adapter for LLMs (SSE, port 3001)
│   └── healthcheck.py             # Docker health checks
├── tests/                          # 483 pytest tests
├── data/                           # Local dev state (gitignored): db/, chroma/, results/, logs/
├── .github/workflows/              # CI + publish-release
├── Dockerfile                      # Multi-stage build, single image, non-root, tini-init
├── docker-compose.yml              # 2 services, 1 image, 1 Docker-managed named volume
├── docker-compose.dev.yml          # Local-build override for developers
├── .pre-commit-config.yaml         # Ruff, trailing whitespace, etc.
├── pyproject.toml                  # Dependency metadata for uv
└── uv.lock                         # Locked dependency resolution for CI/Docker
```

### Docker Publishing

The repository publishes Docker Hub images exclusively from version tags:

- `.github/workflows/publish-release.yml` is the automatic release path for version tags, producing `:latest`, `:vX.Y.Z`, `:vX.Y`, `:vX`, and `:sha-<commit>`.

Publishing policy:

- pull requests run the Docker smoke build in CI and execute the healthcheck against the built image — regressions are caught before merge
- pushes to `main` run validation jobs, but do not automatically republish Docker images
- version tags (e.g. `v1.2.3`) publish the full multi-arch release (`linux/amd64` + `linux/arm64`) and refresh `:latest`
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
