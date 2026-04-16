# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [7.1.2] - 2026-04-16

### Added

- **110 new tests** (373 → 483), bringing overall coverage from 82% to 87%:
  - `test_job_service.py` (23 tests): direct unit tests for the shared service layer — DB/VS singleton lifecycle, record serialization, filtering, sorting.
  - `test_integration.py` (9 tests): end-to-end pipeline tests with real databases (no mocking) — score→partition→save→reconcile cycle, bookmark/applied SQL protection, API and MCP full workflows, config-change simulation.
  - `test_main.py` (+25 tests): `_prepare_runtime` rescore+reconcile ordering, `run_job_search` with real scoring against temp DBs, notification data construction, `_cmd_once`/`_cmd_scheduler` lifecycle.
  - `test_database.py` (+19 tests): `reset_all` escape hatch, `reconcile_with_config` combinations, score distribution bins, preview count accuracy, batch blacklist operations.
  - `test_dashboard.py` (+34 tests): pure helper coverage (`_escape_html_text`, `_score_badge_html`, `_format_salary`, `_short_num`, `_days_ago`, `_filtered_jobs_csv_bytes`).

### Fixed

- `healthcheck.py`: added missing `from __future__ import annotations` (consistency with all other modules).
- `CLAUDE.md`: added `test_dashboard.py` to the test tree (was omitted).
- API server version string aligned to 7.1.1 (was still 7.1.0).

### Coverage

| Module | Before | After |
|--------|--------|-------|
| `main.py` | 58% | 89% |
| `job_service.py` | 75% | 99% |
| `database.py` | 82% | 90% |
| `dashboard.py` | 67% | 71% |
| **Overall** | **82%** | **87%** |

## [7.1.1] - 2026-04-16

### Changed

- **Shared service layer** (`scripts/job_service.py`): extracted DB/vector-store initialization, record serialization, job filtering, and sorting into a single module shared by the dashboard, REST API, and MCP server. All three frontends are now thin adapters over `job_service`, eliminating ~60 lines of duplicated logic and ensuring consistent behavior across surfaces.
- **`api_server.py`** and **`mcp_server.py`** refactored to import all data operations from `job_service` instead of reimplementing them locally. Pydantic models and endpoint/tool definitions remain in the adapters.
- **`dashboard.py`** now imports `record_to_dict` from `job_service` instead of maintaining its own copy.

### Fixed

- **MCP `_SETTINGS_DOCUMENTATION`**: `scoring.notify_threshold` default corrected from `0` to `20` (matched the actual `ScoringConfig` default).
- **MCP vector store init**: failures are now logged with a warning instead of being silently swallowed (`except Exception: pass` → proper logging via `job_service.get_vs()`).
- **API server version**: updated from hardcoded `"1.0.0"` to `"7.1.0"` to match the project version.
- **SQLite cross-thread crash**: `check_same_thread=False` added to `sqlite3.connect()` in `database.py` — FastAPI runs sync endpoints in a threadpool, so the connection must be shareable across threads. WAL mode already provides concurrency safety.
- **MCP server port**: `FastMCP` constructor now passes `host="0.0.0.0"` and `port=3001` explicitly. The default (`127.0.0.1:8000`) didn't match the `docker-compose.yml` mapping and wouldn't accept connections from outside the container.
- **CI workflow**: removed stale `AGENTS.md` entry from `paths-ignore` (file was deleted in v7.0.1).
- **README.md**: test count corrected from 375 to 373.

## [7.1.0] - 2026-04-16

### Added

- **REST API server** (`scripts/api_server.py`, FastAPI on port 8502) — programmatic CRUD access to the job database for scripts, automations, and external tools. Endpoints: `GET /jobs` (paginated, filterable by score/site/company/bookmark/applied), `GET /jobs/{id}`, `GET /jobs/search/semantic` (ChromaDB vector search), `GET /stats`, `GET /distribution`, `POST /jobs/{id}/bookmark`, `POST /jobs/{id}/apply`, `DELETE /jobs/{id}`, `DELETE /jobs/below-score/{N}`, `GET /health`. Auto-generated OpenAPI docs at `/docs`.
- **MCP server** (`scripts/mcp_server.py`, SSE transport on port 3001) — tools that let an LLM become a job search assistant. DB access tools: `list_jobs`, `get_job` (including full description for fit evaluation), `search_similar` (semantic search), `get_statistics`, `get_score_distribution`. Action tools: `bookmark_job`, `apply_job`, `delete_job`, `delete_jobs_below_score`. Knowledge tool: `get_settings_documentation` returns a comprehensive static reference (~3000 chars) of every `settings.yaml` section, field, type, default, and constraint — the MCP server does NOT read the user's actual settings file or profile; the user provides those in conversation and the LLM uses the tools + schema knowledge to advise.
- **Docker Compose profiles** for the new services: `api` and `mcp`. The existing `scheduler` and `dashboard` always start; the new services are opt-in via `docker compose --profile api --profile mcp up -d`. No change to the default UX.
- **Port override env vars**: `JOB_SEARCH_API_PORT` (default 8502) and `JOB_SEARCH_MCP_PORT` (default 3001), documented in `.env.example` alongside the existing `JOB_SEARCH_DASHBOARD_PORT`.
- **38 new tests** (20 API, 18 MCP) covering happy paths, error paths (404, 503, missing vector store), and toggle operations.

### Changed

- **`docker-compose.yml`** top comment updated to document all four services and the Compose profiles opt-in pattern.
- **`CONTRIBUTING.md`** test tree updated to reflect the current test suite (removed stale `test_report_generator.py` and `test_analyze_jobs.py`, added `test_api_server.py` and `test_mcp_server.py`).

### Dependencies

- `fastapi >= 0.115.0, < 1.0.0`
- `uvicorn >= 0.34.0, < 1.0.0`
- `mcp[cli] >= 1.0.0, < 2.0.0`

### Architecture

The tool now has four surfaces over a single data layer:

| Service | Consumer | Protocol | Port | Profile |
|---------|----------|----------|------|---------|
| scheduler | (autonomous) | — | — | *(always on)* |
| dashboard | Human (browser) | Streamlit | 8501 | *(always on)* |
| api | Scripts, automations | REST/JSON | 8502 | `api` |
| mcp | Claude, LLMs | MCP/SSE | 3001 | `mcp` |

All four share the `jobsearch-data` Docker volume. SQLite WAL mode ensures concurrent readers don't block the scheduler's writes.

## [7.0.1] - 2026-04-16

Housekeeping release. No functional changes: v7.0.0 introduced the new scoring/retention/dashboard surface, this release finishes the job by removing the dead code and stale documentation that didn't get caught in the main refactor pass.

**-2235 lines, no new features, no config changes.** If you're already running v7.0.0, the upgrade is `docker compose pull && docker compose up -d` with no `settings.yaml` edits required.

### Removed

- **`scripts/report_generator.py`** and its test — dead code, only self-imported. Its Excel formatting helpers were already duplicated in `scripts/exporter.py`.
- **`scripts/analyze_jobs.py`** and its test — standalone CLI utility (ran via `python analyze_jobs.py` or `docker compose exec scheduler python analyze_jobs.py`) whose entire feature set is now covered by the dashboard's Database tab introduced in v7.0.0: company/location/keyword statistics are shown interactively, the score distribution is a live histogram, and filtering by company is a click on the main tab. Keeping a second implementation of the same thing on the CLI was just maintenance debt.
- **`AGENTS.md`** — stale duplicate of `CLAUDE.md` that still described the pre-v7 pipeline (`cleanup_old_jobs` per-iteration, `filter_relevant_jobs`, `save_results`, single `scoring.threshold`). It wasn't updated during the v7 refactor and had drifted ~15 documentation blocks away from reality. `CLAUDE.md` is now the single source of truth for developer documentation; if another agent tool needs its own file later, it can be recreated from `CLAUDE.md`.
- **`.github/workflows/publish-main.yml`** — manual-only (`workflow_dispatch`) Docker publish workflow that had never been triggered. `publish-release.yml` handles real releases (every `v*` tag, multi-arch, SBOM, provenance, semver tag tree); `publish-main.yml` was leftover pre-release infrastructure whose only effect on Docker Hub would have been a confusing `main` tag.
- **`SearchResult` dataclass** in `scripts/models.py` — unused since before v7 and not to be confused with `vector_store.SemanticSearchResult` which is live.
- **`mock_logger` fixture** in `tests/conftest.py` — defined at the top-level conftest but with zero consumers; `test_logger.py` has its own locally-scoped fixture of the same name.
- **`results/.gitkeep`** and **`data/.gitkeep`** — both directories are gitignored and created lazily at runtime (the `results/` directory is only created the first time a user triggers an export from the dashboard's Database tab).

### Changed

- **`README.md`**: flow diagrams rewritten for `save_threshold` / `notify_threshold` partitioning, the "SAVE CSV/EXCEL" box in the pipeline diagram is gone, the "Optional Exports" section is rewritten around dashboard on-demand exports, `min_score_for_notification` is gone from the YAML example (replaced with a pointer to `scoring.notify_threshold`), the Docker Publishing subsection only mentions `publish-release.yml`, and the test count moves from 361 to 335.
- **`CLAUDE.md`**: project tree no longer lists the removed modules; the "extracted to" note about `filter_relevant_jobs` / `save_results` now correctly reflects that one was split (into `score_jobs` + `partition_by_thresholds`) and the other was removed entirely; a new Dashboard section documents the Database tab's five subsections and the SQL-level bookmarked/applied protection invariant; the `SearchResult` stub is gone; test count updated.
- **`.dockerignore`**: dropped the `AGENTS.md` entry along with the file itself.

### Test plan

- `pytest`: 335 passed, 0 failed. The delta from v7.0.0 (375 tests) is exactly the sum of the deleted `test_report_generator.py` (15) + `test_analyze_jobs.py` (17) + 8 parameterized variants that lived inside them.
- `ruff check scripts/ tests/` clean.
- `ruff format scripts/ tests/` — no files reformatted.
- CI green on PR #8 before and after the release bump commit.

## [7.0.0] - 2026-04-15

This is a major release. The scoring pipeline, the database retention model, and the dashboard's database management surface have all been rebuilt around a single principle: **`settings.yaml` is the source of truth and the DB reconciles to it at every boot**. Breaking changes are intentional and there is no backwards-compatibility shim — migrating an old `settings.yaml` is a five-minute edit.

### Added

- **`scoring.save_threshold`** and **`scoring.notify_threshold`** — two independent thresholds that split the single `scoring.threshold` into "what enters the archive" (wide, default `0`) and "what triggers notifications and counts as relevant" (narrow, default `20`). The loader refuses configs where `notify_threshold < save_threshold`.
- **`database.retention`** block with `max_age_days` (default `30`) and `purge_blacklist_after_days` (default `90`). Applied at every boot by the new `reconcile_with_config` pass — no `cleanup_enabled` flag, no opt-in: if you don't want retention, raise the limits.
- **Reconciliation at boot** — after `recalculate_all_scores`, the tool now runs `db.reconcile_with_config(config)` which drops jobs below `save_threshold`, drops stale jobs, purges the blacklist, and syncs the vector store. Idempotent: running it twice in a row is a no-op. If anything was removed, a summary is pushed to Telegram (`🧹 Startup cleanup: X jobs removed`).
- **SQL-level protection invariant** — every DELETE query (except the explicit `reset_all` escape hatch) includes `AND bookmarked = 0 AND applied = 0`. Bookmarked and applied jobs are structurally immune to automatic cleanup, both at boot and from the dashboard's smart-cleanup controls. Not configurable.
- **Database retention primitives** in `scripts/database.py`: `delete_jobs_below_score`, `delete_stale_jobs` (renamed from `cleanup_old_jobs`/`delete_jobs_older_than`), `purge_blacklist`, `get_score_distribution`, `count_jobs_below_score`, `count_stale_jobs`, `count_blacklist_older_than`, `reconcile_with_config`, `reset_all`. Dedicated SQL index on `relevance_score` so score-based cleanups stay O(log n).
- **New Database tab in the Streamlit dashboard** — a full management surface with five sections:
  - **Health**: total jobs, bookmarked, applied, blacklisted, average score, DB size on disk.
  - **Score distribution**: dynamic histogram from `get_score_distribution`, with vertical reference lines drawn at both `save_threshold` and `notify_threshold`.
  - **Smart cleanup**: four cards with live preview counts before confirmation — *Delete below score N* (default = current `save_threshold`), *Delete stale older than N days*, *Purge blacklist older than N days*, and **Apply `settings.yaml` retention now** which calls `reconcile_with_config` against the live config and shows the `ReconciliationReport` in the UI.
  - **Export**: on-demand CSV/Excel of the currently filtered view.
  - **Danger zone**: Full reset with text-confirmed `DELETE` that truncates the `jobs` table, the `deleted_jobs` blacklist, and the ChromaDB collection in one shot (the only path that bypasses the bookmarked/applied invariant).
- **`ReconcileNotificationData`** + `format_reconcile_message` + `NotificationManager.send_reconcile_sync` in `scripts/notifier.py` for the startup cleanup summary.
- **`Partitions`** dataclass in `scripts/scoring.py` — the new `partition_by_thresholds(scored, config)` returns a `Partitions(scored, to_save, to_notify)` so the main flow reads as score → partition → save → embed → notify without any threshold arithmetic at the call site.

### Changed (BREAKING)

- **`scoring.threshold` is gone**. Replace with `scoring.save_threshold` + `scoring.notify_threshold`. Old single-threshold configs are rejected — the loader does not translate them.
- **`scoring.notify_threshold >= scoring.save_threshold` is enforced** as a hard error at load time. Notifying about jobs you don't even archive is nonsensical, so the loader treats it as a config bug, not a warning.
- **`database.cleanup_enabled`, `database.cleanup_days`, and `database.recalculate_scores_on_startup` are gone**. Score recalculation at boot is always on (it's cheap and deterministic). Age-based cleanup is always on via `database.retention.max_age_days`. There is no longer a knob to turn either feature off — set `max_age_days` to something large if you want "never expire".
- **`output:` section removed entirely**. The search pipeline no longer writes `all_jobs_*.csv` or `relevant_jobs_*.csv` on every run. CSV and Excel exports are available exclusively from the dashboard's Database tab, triggered on demand. The `results/` directory is created lazily the first time an export happens.
- **`telegram.min_score_for_notification` removed**. The notify threshold is a relevance concept owned by the scoring engine (`scoring.notify_threshold`), not a Telegram channel setting. The partition of new jobs to notify about is computed upstream by `partition_by_thresholds`; the notifier just receives an already-filtered list.
- **`filter_relevant_jobs` is gone**. It has been split into `score_jobs(df, config)` (adds the `relevance_score` column) and `partition_by_thresholds(scored, config)` (returns the `Partitions` dataclass). Callers that used to pull the single "relevant" frame now pull `to_save` and `to_notify` independently.
- **`cleanup_old_jobs` / `delete_jobs_older_than`** → renamed to `delete_stale_jobs`. **`filter_blacklisted_jobs`** → renamed to `exclude_blacklisted`.
- **Main flow rewritten**. `_prepare_runtime` now runs `rescore_all` → `reconcile_with_config` → vector-store sync → optional Telegram reconcile summary at every boot, for both `scheduler` and `once` modes. `run_job_search` is `search → score → partition → exclude_blacklisted → save → embed → notify(to_notify)` with zero CSV side effects.

### Removed

- `OutputConfig` dataclass and the entire `scripts/exporter.save_results` code path. `scripts/exporter.py` is reduced to a single `export_dataframe(df, output_dir, basename, fmt)` helper used only by the dashboard.
- Dead `main()` function in `scripts/search_jobs.py` (it duplicated the pipeline; there was only one real entry point).
- Automatic `all_jobs_*.csv` and `relevant_jobs_*.csv` files from the results folder on every scheduled run.

### Migration

For an existing v6 `settings.yaml`, five edits:

1. In `scoring:`, replace `threshold: N` with:
   ```yaml
   save_threshold: 0
   notify_threshold: N
   ```
   Pick `save_threshold: 0` for a wide archive (recommended) or raise it if you want the DB to stay narrow.
2. In `database:`, delete `cleanup_enabled`, `cleanup_days`, and `recalculate_scores_on_startup`, and replace with:
   ```yaml
   retention:
     max_age_days: 30        # use your old cleanup_days value here
     purge_blacklist_after_days: 90
   ```
3. Delete the entire `output:` section.
4. In `notifications.telegram:`, delete `min_score_for_notification`. If you had it set to a non-zero value, copy that value to `scoring.notify_threshold` instead — that preserves your existing notification bar exactly.
5. Restart the tool. The first boot will rescore every existing job and run reconciliation; expect a one-off cleanup Telegram message if any of your stored jobs fall below the new `save_threshold`, are stale beyond `max_age_days`, or belong to a purged blacklist entry. Bookmarked and applied jobs are protected.

### Why

Before this release, `scoring.threshold` did triple duty: it decided what got saved, what got exported, and what counted as "relevant" for notifications. That meant the dashboard could only ever show jobs that had already passed the single narrow filter — there was no room for exploration, no way to investigate borderline matches, and tuning the keywords meant permanently losing the jobs scored under the old pesi. On top of that, retention was a per-iteration age-based sweep that would happily delete a job you had just bookmarked.

The split fixes all of that in one pass. `save_threshold` makes the DB an archive you can actually browse; `notify_threshold` keeps Telegram focused on the jobs worth waking up for; reconciliation makes `settings.yaml` dichiarativo (edit the file, restart, the DB catches up); and the SQL-level bookmark/applied protection turns the dashboard's cleanup tools into something you can click confidently.

### Test plan

- 375 tests pass, 0 failures (+14 over the v6.0.8 baseline of 361). New coverage: `reconcile_with_config` idempotency, SQL-level bookmark/applied protection across every retention primitive, cross-section validation of `notify_threshold >= save_threshold`, `Partitions` carving, dashboard smart-cleanup preview counts, `ReconcileNotificationData` formatting.
- `ruff check` and `ruff format` both clean across `scripts/` and `tests/`.
- CI fully green on PR #7 (test 3.11, test 3.12, quality, security, docker).
- The Docker healthcheck step in `.github/workflows/ci.yml` now bind-mounts `config/settings.example.yaml` into `/data/config/settings.yaml` so `healthcheck.py` runs end-to-end against a real config through the entrypoint's boot guard — a pre-existing CI bug from v6.0.1 is also fixed as part of this release.

## [6.0.8] - 2026-04-15

### Changed

- **Hybrid volume layout** is now the canonical setup. `settings.yaml` lives on the host as a read-only file bind-mounted directly into each container at `/data/config/settings.yaml`; everything else (SQLite database, ChromaDB vector store, CSV/Excel exports, logs) stays in the Docker-managed named volume `jobsearch-data`. This replaces the v6.0.6/v6.0.7 "inject via `docker run alpine`" workflow which forced users through a one-shot helper container just to write a single file.
- **User-facing workflow collapses to three steps**: drop `settings.yaml` next to `docker-compose.yml`, drop the compose file, `docker compose up -d`. Updates are `vim settings.yaml && docker compose restart scheduler`. No `docker compose cp`, no `docker run alpine`, no `docker volume create` pre-step.
- **`docker-compose.yml`**: both services gain a second volume entry — `./settings.yaml:/data/config/settings.yaml:ro` — alongside the existing `jobsearch-data:/data` named volume. The named volume definition still uses `name: jobsearch-data` so the volume's real name is not prefixed by the Compose project.
- **`README.md` Quick Start rewritten** for the three-step flow. The "Bare `docker run` (no Compose)" section is simplified to match (the old step 2 "inject via alpine" is gone — a single `-v "$PWD/settings.yaml:..."` mount replaces it on each `docker run` invocation). The Data Storage section now has a two-row table that makes the split between the host-side config and the Docker-managed state explicit.
- **`docker/entrypoint.sh`**: the existing "missing settings.yaml" error path now also detects the common pitfall where Docker Compose auto-creates `./settings.yaml` as a directory (because the host file didn't exist at the time of the first `up`) and emits a targeted `rm -rf ./settings.yaml` recovery hint for that specific case.

### Why

`settings.yaml` is the only artefact the user ever wants to *edit*; the rest is state the tool manages. Keeping the config on the host as a plain file gives you editor-friendly workflows (`vim`, `nano`, `code`, diff against git, back up with `cp`) while the Docker-managed volume takes care of the non-trivial state with zero permission friction — no host-side `chown`, no UID/GID env vars, no `gosu`, no privileged init. It's the same split the official `postgres` image makes between `postgresql.conf` and `PGDATA`.

No code changes — the entrypoint refactor is purely the error-message extension. 361 tests still green.

## [6.0.7] - 2026-04-15

### Documentation

Full-repo coherence audit after the v4.4.0 → v6.0.6 release sprint. All of the following stale references that contradicted the v6.0.6 mandatory-config contract have been corrected:

- **`CLAUDE.md` / `AGENTS.md`**: project-tree comments on `settings.example.yaml` and `entrypoint.sh` no longer claim first-run auto-scaffolding; the "Execution Modes" table is rewritten to reflect the CLI subcommand-driven contract (no `scheduler.enabled` flag); the `main()` docstring matches the actual subcommand dispatch; total test count updated from `~324` to the real `361`.
- **`README.md`**: Quick Start and Bare-`docker run` sections carry the new mandatory settings.yaml flow end-to-end (no auto-scaffold wording anywhere); project-structure listing describes `settings.example.yaml` as "never copied into the user's volume" and `entrypoint.sh` as "requires user-supplied settings.yaml"; Test count bumps from `355+` / `350+` to `361`; the ASCII execution-flow diagram labels modes with `main.py once` / `main.py scheduler` instead of the removed `scheduler: true/false` flag; `docker compose cp` examples use the Compose service name (`scheduler`) instead of container names; Upgrade Troubleshooting section reframed around "refresh settings.yaml" (no "first-run scaffolding" recipe).
- **`CONTRIBUTING.md`**: the `cp config/settings.example.yaml config/settings.yaml` step is now explicitly scoped to local Python development, with an inline note that the Docker runtime requires injection into the named volume instead.

No code or Docker-image changes — the v6.0.6 and v6.0.7 images are functionally equivalent. Published Docker tags are refreshed so anyone pulling `:latest` at the new version reads the updated in-image docs and `settings.example.yaml` metadata.

## [6.0.6] - 2026-04-15

### Changed (BREAKING)

- **`settings.yaml` is now strictly required** — no default, no fallback, no auto-scaffolding. The entrypoint refuses to start either service if `/data/config/settings.yaml` is missing, exits with a clear actionable error message, and lets Docker's restart policy do the rest. `config/settings.example.yaml` remains a **documentation artefact**: it ships with the repo and inside the image purely to show the expected shape of a valid configuration, and is never copied into the user's data volume automatically.
- **`docker/entrypoint.sh` rewritten**: it creates the `/data/{config,db,chroma,results,logs}` subtree on every start, then requires `settings.yaml` to exist. The previous first-run "scaffold from template" behaviour from v6.0.0 is gone — it encouraged users to boot with generic placeholder queries and "Your Name" profile strings, which was never the intended UX.
- **`docker-compose.yml`**: volume declaration now uses `name: jobsearch-data` so Compose doesn't prefix it with the project name. This lets `docker volume create jobsearch-data` (used to pre-seed `settings.yaml`) and the Compose-managed volume reference the same underlying Docker volume.

### Quick Start (new mandatory-config flow)

```bash
# 1. Grab the documented template
docker run --rm --entrypoint cat \
  vincenzoimp/job-search-tool:latest \
  /opt/job-search-tool/defaults/settings.example.yaml > settings.yaml

# 2. Edit settings.yaml with your queries, scoring, and (optional) Telegram bot

# 3. Inject it into the named volume
docker volume create jobsearch-data
docker run --rm \
  -v jobsearch-data:/data \
  -v "$PWD/settings.yaml:/src.yaml:ro" \
  alpine sh -c 'mkdir -p /data/config && cp /src.yaml /data/config/settings.yaml'

# 4. Start the stack
docker compose up -d
```

Four explicit steps, zero magic. If you forget step 3 the containers fail loudly with an error message that tells you exactly what to do.

### Migration notes

- If you were relying on v6.0.5's auto-scaffolded default `settings.yaml` (generic Remote software-engineer queries, no Telegram), copy it out first with `docker compose cp` before upgrading, or use the new flow to inject your own.
- The `settings.example.yaml` file is no longer written to the volume by the container. Your existing `settings.example.yaml` inside the volume from older releases is harmless and can be deleted: `docker run --rm -v jobsearch-data:/data alpine rm /data/config/settings.example.yaml`.

## [6.0.5] - 2026-04-15

### Fixed

- **ChromaDB telemetry errors are actually silenced now**: v6.0.3 tried to disable them via the `ANONYMIZED_TELEMETRY=False` env var but the posthog client bundled with our ChromaDB pin ignores that variable and still fires `Failed to send telemetry event … capture() takes 1 positional argument but 3 were given` on every client call. `scripts/vector_store.py` now passes `Settings(anonymized_telemetry=False)` directly to `chromadb.PersistentClient`, which the library honours end-to-end.
- **JobSpy log dedupe actually deduplicates**: v6.0.4 installed the right `DedupeFilter` on the root logger, but JobSpy attaches its *own* StreamHandler to each per-site logger (`JobSpy:Indeed`, `JobSpy:Glassdoor`, ...) at import time, bypassing the root filter entirely. `scripts/logger.py` now strips those handlers during `setup_logging` and forces `propagate=True` so every JobSpy record flows through the root handler where the dedupe filter lives. Third-party noise is now collapsed per `(name, level, message)` tuple in practice, not just in theory.
- **Legacy-key deprecation warnings are one-shot**: `scheduler.enabled is ignored in v6+` used to fire twice per scheduler iteration (once during startup `load_config()`, once during `reload_config()` inside `run_job_search()`). They're now tracked in a per-process `_LEGACY_WARNED` set in `scripts/config.py` and emitted exactly once regardless of how many times the parser runs. Applies to `output.*`, `scheduler.enabled`, and `vector_search.{model_name,persist_dir}` legacy keys alike.

### Changed

- **`scripts/logger.py`**: new `_reroute_jobspy_loggers()` helper invoked by `setup_logging`. Pre-configures the nine known JobSpy per-site loggers (strip handlers, `propagate=True`, level `WARNING`) so they inherit the root handler's `DedupeFilter` and the uniform log format.
- **`scripts/config.py`**: new `_warn_legacy_once(section, message)` helper backed by a module-level set. Replaces the three ad-hoc `logger.warning(...)` call sites with a single one-shot implementation. Autouse pytest fixture in `conftest.py` snapshots and restores the set between tests so cross-test state leakage can't re-trigger warnings.

### Added

- **README Troubleshooting**: new "Upgrading within v6.x leaves stale settings in the named volume" section explaining why the `jobsearch-data` volume persists across upgrades and giving two reset recipes (nuclear `down -v` vs surgical `docker compose cp`).
- **Tests**: `test_legacy_enabled_key_warns_only_once`, `TestRerouteJobSpyLoggers.test_strips_existing_handlers_and_forces_propagation`, and `TestRerouteJobSpyLoggers.test_setup_logging_dedupes_duplicate_jobspy_records` — all three regressions discovered in v6.0.4 are now covered.

## [6.0.4] - 2026-04-15

### Changed

- **Cleaner Compose defaults**: the committed `docker-compose.yml` now uses project name `jobsearch`, named containers `jobsearch-scheduler` / `jobsearch-dashboard`, and network `jobsearch`. `docker ps` and `docker compose logs -f <service>` read cleanly without the `-<n>` replica suffix.
- **Network hardening baked into the default stack**:
  - `networks.default.enable_ipv6: false` prevents the class of `[Errno 113] No route to host` errors seen on hosts with broken dual-stack routing (LXC, home routers with half-configured IPv6, cloud VMs without a default v6 route). Python's `getaddrinfo` only returns IPv4 results inside the stack.
  - Explicit `dns: [1.1.1.1, 8.8.8.8]` on both services bypasses the embedded Docker DNS → host DNS chain that occasionally returns stale or unreachable upstream IPs.
- **Safer first-run template** (`config/settings.example.yaml`): default `sites` narrowed to `[indeed, linkedin]` (Glassdoor is opt-in because its API rejects many common location formats with HTTP 400 / `location not parsed`); default `locations` changed to `["Remote"]` with `is_remote: true` so a brand-new container runs clean without region-specific parsing quirks.

### Fixed

- **JobSpy log noise deduplicated**: replaced the broken `logging.getLogger("jobspy").setLevel(CRITICAL)` (which targeted a non-existent lowercase logger name) with a proper `DedupeFilter` attached to both our application handlers and a root-logger handler. Third-party loggers like `JobSpy:Glassdoor` used to fire the same `Glassdoor: location not parsed` error 24+ times per run; now only the first occurrence is emitted per `(logger_name, level, message)` tuple. The filter is generic and will also collapse repeated noise from other chatty libraries.
- **`job_search` logger no longer propagates**: application logs are now emitted only by our own handlers, preventing double-logging through the root handler we install for third-party capture.

### Added

- **README `Troubleshooting` section** rewritten with four actionable scenarios: rate limiting, Glassdoor `location not parsed`, `No route to host` / IPv6 diagnosis, and the local rebuild workflow. Includes a copy-pasteable `docker compose exec` diagnostic for network reachability.
- **`DedupeFilter` unit tests**: six regression tests covering first-occurrence pass, duplicate suppression, distinct messages, independent logger tracking, prefix scoping, and global dedupe.

## [6.0.3] - 2026-04-15

### Fixed

- **Scheduler never actually ran continuously** after v6.0.0: `JobSearchScheduler.start()` still consulted the legacy `config.scheduler.enabled` flag, and the bundled `settings.example.yaml` shipped with `scheduler.enabled: false` as the default. First-run containers happily scaffolded their settings, logged `"Scheduler disabled, running once and exiting"`, completed one search, and then died — losing the entire "unless-stopped continuous loop" promise of v6. The CLI subcommand (`python main.py scheduler`) now fully owns the mode selection and always runs the continuous loop.
- **ChromaDB telemetry noise**: silenced the `Failed to send telemetry event … capture() takes 1 positional argument but 3 were given` errors from ChromaDB's bundled posthog client via `ANONYMIZED_TELEMETRY=False` and `CHROMA_TELEMETRY_IMPL=none` environment variables baked into the image.

### Changed

- **`SchedulerConfig.enabled` removed**: the continuous/single-shot choice is expressed by the CLI subcommand alone. `settings.yaml` keys with `scheduler.enabled` are now ignored with a one-line deprecation warning.
- **`scripts/scheduler.py`**: `start()` unconditionally enters the continuous loop; the `_execute_job` retry-scheduling branches no longer double-check `config.scheduler.enabled` (they rely on the `self._scheduler` presence alone, which is already the canonical marker of continuous mode).
- **`config/settings.example.yaml`**: scheduler section is rewritten to document that the mode is chosen by the CLI and no longer exposes `enabled`.
- **Test suite**: `test_start_disabled_scheduler_runs_once` removed (the fallback it covered no longer exists); fixtures updated to construct `SchedulerConfig()` with defaults.

## [6.0.2] - 2026-04-15

### Fixed

- **First-run permission error on non-root containers**: the default `docker-compose.yml` now uses a Docker-managed named volume (`jobsearch-data`) instead of a `./data` host bind mount. On hosts where Docker creates `./data` as `root:root` (the common case when the Docker daemon itself runs as root — e.g. alpine-docker without userns-remap), the non-root container (`appuser`, UID 1000) would fail to write with `mkdir: cannot create directory '/data/config': Permission denied`. Named volumes inherit their ownership from the image, so the container writes to them without any host-side preparation.

### Changed

- **`docker-compose.yml`** switches from `./data:/data` bind mount to `jobsearch-data:/data` named volume. Both services still share the same volume, still run as `appuser`, still auto-scaffold `settings.yaml` on first boot.
- **`docker-compose.dev.yml`** follows the same pattern for the local-build override.
- **README Quick Start** updated: new compose snippet, `docker compose cp` workflow for editing `settings.yaml`, documented `docker run --rm -v jobsearch-data:/data alpine tar …` backup/restore recipe (the canonical Docker named-volume backup pattern).
- Standalone `docker run` examples in the README now create and reuse a named volume (`docker volume create jobsearch-data`) instead of mounting host paths.
- `.gitignore` excludes the whole `data/` directory tree so local dev state under the repo root never accidentally ends up in a commit.

## [6.0.1] - 2026-04-15

### Changed

- **Single Docker image**: the dashboard/core variant split from v5.0.0 is removed. One image tree, one tag family (`:latest`, `:vX.Y.Z`, `:vX.Y`, `:vX`, `:sha-<commit>`). Both Compose services pull the same image — Docker downloads it once and shares layers — and differ only by the command they run.
- **Unified CLI subcommands**: `scripts/main.py` now accepts subcommands:
  - `python main.py` / `python main.py scheduler` — continuous scheduler loop (default)
  - `python main.py once` — single-shot run (for cron / CI)
  - `python main.py dashboard` — `exec`-replaces the process with Streamlit on port 8501
  Replaces the v6.0.0 transient `--once` flag.
- **`docker-compose.yml`** uses explicit `command: ["python", "main.py", <subcommand>]` on both services.
- **Streamlit moved back to main dependencies** in `pyproject.toml`; the `[project.optional-dependencies] dashboard` extra is removed.
- **Dockerfile** simplified to a single target: no more `ARG VARIANT`, no more `builder-core` / `builder-dashboard` / `builder-final` stages.
- **CI + publish workflows** drop the `[dashboard, core]` matrix and build once per run.
- **README Quick Start** fixes a copy-paste bug from v6.0.0 where the dashboard service was missing a `command:` override and would have silently run a second scheduler instead of Streamlit.

### Removed

- Docker image tag families `:latest-core`, `:vX.Y.Z-core`, `:core`, `:sha-<commit>-core`.
- `--build-arg VARIANT` on the Dockerfile.
- `[project.optional-dependencies] dashboard` in `pyproject.toml`.
- CI matrix build of two variants in `.github/workflows/ci.yml`, `publish-release.yml`, `publish-main.yml`.

## [6.0.0] - 2026-04-15

### Changed (BREAKING)

- **Minimal two-service Compose stack**: `docker-compose.yml` collapses to two flat services — `scheduler` on `:latest-core` and `dashboard` on `:latest` — sharing a single `./data:/data` volume. YAML anchors, profiles, `init-config`, `jobsearch`, and `analyze` services are gone. `docker compose up -d` now starts the continuous scheduler and the dashboard together out of the box.
- **Single `/data` volume**: every persistent file now lives under one mount point with a fixed layout — `/data/config/settings.yaml`, `/data/db/jobs.db`, `/data/chroma/`, `/data/results/`, `/data/logs/search.log`. Users go from four bind mounts (`config/`, `data/`, `results/`, `logs/`) to **one**. Override the root with `JOB_SEARCH_DATA_DIR`.
- **First-run auto-bootstrap**: on startup, the container creates `/data/config/settings.yaml` from the bundled template if it is missing, scaffolds the `/data/{config,db,chroma,results,logs}` subtree, and logs a clear "edit me and restart" hint. The `init-config` service and `scripts/bootstrap_config.py` helper are removed — both obsolete.
- **Scheduler is the default mode**: `python main.py` now starts the continuous APScheduler loop by default. Use `python main.py --once` for a one-off single-shot run (cron, CI). The `JOB_SEARCH_MODE=single|scheduled` env variable is gone.
- **Fixed persistent paths**: `output.results_dir`, `output.data_dir`, `output.database_file`, `logging.file`, `vector_search.model_name`, and `vector_search.persist_dir` are removed from `settings.yaml`. They are silently accepted with a one-line warning to ease the transition. Use `JOB_SEARCH_DATA_DIR` to relocate the whole tree.
- **Dockerfile runs under `tini`** for clean SIGTERM propagation, declares `VOLUME /data`, and exports `JOB_SEARCH_DATA_DIR=/data` as a default env.
- **`.env.example` slimmed down**: dropped `JOB_SEARCH_IMAGE` / `JOB_SEARCH_CORE_IMAGE` / `JOB_SEARCH_DASHBOARD_IMAGE`, kept only the Telegram token, UID/GID, and dashboard port.
- **`docker-compose.dev.yml` rewritten**: rebuilds both variants (`core` and `dashboard`) from the local checkout via `--build-arg VARIANT=...`.

### Removed

- `scripts/bootstrap_config.py` and its tests — the entrypoint does the bootstrap inline.
- Compose services: `init-config`, `jobsearch`, `analyze`, all profile-gated services. Use `docker compose exec scheduler python analyze_jobs.py` for ad-hoc analysis.
- `scripts/main.py::_resolve_scheduled_mode` and the `JOB_SEARCH_MODE` env switch.
- `OutputConfig.results_dir` / `.data_dir` / `.database_file`, `LoggingConfig.file`, `VectorSearchConfig.model_name` / `.persist_dir`.
- `get_vector_store(persist_dir, model_name=...)` signature — the `model_name` parameter is gone (it was already a no-op since v4.4.0).

## [5.0.1] - 2026-04-15

### Documentation

- **Sync stale references** to match the v5.0.0 variant split and v4.4.0 ONNX embedder migration:
  - `README.md`: feature tables, ASCII execution-flow diagram, Docker Publishing section rewritten for the core/dashboard matrix, `docker run` examples updated to prefer `:latest-core` for headless usage, Acknowledgments cleaned of the removed `sentence-transformers` entry, test count refreshed.
  - `CONTRIBUTING.md`: dashboard launch command no longer references the removed `--profile dashboard`.
  - `.env.example`: replaces `JOB_SEARCH_IMAGE` with `JOB_SEARCH_CORE_IMAGE` and `JOB_SEARCH_DASHBOARD_IMAGE`.
  - `config/settings.example.yaml`: `vector_search` block now documents that `model_name` is ignored and describes the ONNX embedder.
  - `CLAUDE.md` / `AGENTS.md`: tech stack table, project tree comment on `Dockerfile`, internal changelog (v4.4.0 + v5.0.0 entries added), "Last Updated" date refreshed. `AGENTS.md` is now tracked alongside `CLAUDE.md`.
  - `scripts/dashboard.py`: "semantic search unavailable" hint no longer mentions the removed `sentence-transformers` package.

No functional or Docker-image changes — the v5.0.0 and v5.0.1 images are byte-for-byte equivalent aside from the `VERSION` build label.

## [5.0.0] - 2026-04-15

### Changed (BREAKING)

- **Two Docker image variants**: The project now publishes two variants from the same tag family:
  - `vincenzoimp/job-search-tool:X.Y.Z` (default, dashboard) — full stack with Streamlit UI, behaves like previous `:latest`.
  - `vincenzoimp/job-search-tool:X.Y.Z-core` — slim image, Streamlit removed (~200 MB smaller).
- **Dockerfile rewritten as variant-aware**: Single parameterized `runtime` stage, variant chosen at build time via `--build-arg VARIANT=core|dashboard` (default: `dashboard`). Replaces the previous single-target build.
- **`docker-compose.yml` wires each service to the right image**: `jobsearch`, `scheduler`, `analyze`, `init-config` → core image (`${JOB_SEARCH_CORE_IMAGE:-vincenzoimp/job-search-tool:latest-core}`); `dashboard` → dashboard image (`${JOB_SEARCH_DASHBOARD_IMAGE:-vincenzoimp/job-search-tool:latest}`). Headless services automatically benefit from the slim image without user intervention.
- **Dashboard runs by default**: `docker compose up` now starts `jobsearch` + `dashboard` out of the box. The `dashboard` profile has been removed (no longer needed). Old usage `docker compose --profile dashboard up dashboard` becomes `docker compose up dashboard`.
- **`JOB_SEARCH_IMAGE` env var removed**: Replaced by `JOB_SEARCH_CORE_IMAGE` and `JOB_SEARCH_DASHBOARD_IMAGE`. Users overriding the image via environment variable must update their setup.
- **`streamlit` moved to optional dependency** `[project.optional-dependencies] dashboard` in `pyproject.toml`. Local `uv sync` (with default dev group) still installs it for test suites; production core builds do not.
- **Pruned `.venv`** in builder stage: removes `__pycache__`, `*.pyc`, `*.pyo`, `*.pyi`, and bundled `tests/` directories from installed packages before the runtime copy. Saves ~50–100 MB on both image variants.
- **CI Docker smoke job** now builds both variants in a matrix and runs the healthcheck on each, so regressions in either build path are caught on PRs.

### Migration notes

- **`:latest` still works and still ships Streamlit** — no change for users pulling the default tag for a dashboard deployment.
- If you override the compose image via `JOB_SEARCH_IMAGE`, replace it with `JOB_SEARCH_CORE_IMAGE` (and optionally `JOB_SEARCH_DASHBOARD_IMAGE` for the dashboard service).
- If you had scripts doing `docker compose --profile dashboard up`, drop the flag — the dashboard is now a default service.

## [4.4.0] - 2026-04-15

### Changed

- **Lightweight Vector Search**: `JobVectorStore` now uses ChromaDB's built-in `DefaultEmbeddingFunction` (onnxruntime + bundled `all-MiniLM-L6-v2`) instead of `sentence-transformers`. Same embedding model, same search quality, no torch runtime.
- **Dependency Slimdown**: Removed `torch`, `sentence-transformers`, and `transformers` from runtime dependencies. Docker image size drops by roughly 2.5–3 GB (the previous lock also pulled the full CUDA stack — `nvidia-cublas`, `cudnn`, `nccl`, `triton`, etc. — despite `UV_TORCH_BACKEND=cpu`).
- **Dockerfile**: Removed the now-unused `UV_TORCH_BACKEND=cpu` build arg.

### Deprecated

- `vector_search.model_name` is now ignored — the store always uses the model bundled with ChromaDB's default embedder. A warning is logged if a non-default value is configured. The setting is retained for backward compatibility and will be removed in a future release.

## [4.3.2] - 2026-04-14

### Changed

- **Release Workflow Simplification**: Docker images now publish automatically from version tags only, while `publish-main.yml` is now a manual maintainer workflow and CI keeps the Docker smoke build on pull requests instead of every push to `main`
- **Release Documentation Alignment**: Updated the README and changelog so the documented release flow matches the actual GitHub Actions behavior

## [4.3.1] - 2026-04-14

### Changed

- **CI Pipeline Efficiency**: Split formatting/type checks out of the Python-version matrix, keep coverage on Python 3.11 only, skip docs-only runs, and cancel superseded in-flight CI runs
- **Docker CI Validation**: The Docker job now bootstraps a real config and runs the health check for the built image instead of masking failures

### Fixed

- **Dashboard CSV Safety**: Filtered dashboard CSV exports now reuse the shared spreadsheet sanitization path, preventing formula-injection regressions
- **Logger Handler Lifecycle**: Repeated logging setup now closes replaced handlers, avoiding file-descriptor leaks in long-lived scheduled runs
- **Telegram Delivery Reporting**: Notification success now reflects whether job chunks were actually delivered instead of treating partial failures as success
- **Stable Job IDs**: Internal job IDs now normalize trivial whitespace and Unicode spacing differences, and existing databases/blacklists are migrated automatically on startup
- **Dashboard Import Side Effects**: Importing `dashboard.py` no longer executes the Streamlit app outside `streamlit run`

## Earlier releases

Entries prior to v4.3.1 have been archived. The git history on `main` plus the tagged commits are the authoritative source for anything older.

[Unreleased]: https://github.com/VincenzoImp/job-search-tool/compare/v7.1.2...HEAD
[7.1.2]: https://github.com/VincenzoImp/job-search-tool/compare/v7.1.1...v7.1.2
[7.1.1]: https://github.com/VincenzoImp/job-search-tool/compare/v7.1.0...v7.1.1
[7.1.0]: https://github.com/VincenzoImp/job-search-tool/compare/v7.0.1...v7.1.0
[7.0.1]: https://github.com/VincenzoImp/job-search-tool/compare/v7.0.0...v7.0.1
[7.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.8...v7.0.0
[6.0.8]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.7...v6.0.8
[6.0.7]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.6...v6.0.7
[6.0.6]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.5...v6.0.6
[6.0.5]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.4...v6.0.5
[6.0.4]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.3...v6.0.4
[6.0.3]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.2...v6.0.3
[6.0.2]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.1...v6.0.2
[6.0.1]: https://github.com/VincenzoImp/job-search-tool/compare/v6.0.0...v6.0.1
[6.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v5.0.1...v6.0.0
[5.0.1]: https://github.com/VincenzoImp/job-search-tool/compare/v5.0.0...v5.0.1
[5.0.0]: https://github.com/VincenzoImp/job-search-tool/compare/v4.4.0...v5.0.0
[4.4.0]: https://github.com/VincenzoImp/job-search-tool/compare/v4.3.2...v4.4.0
[4.3.2]: https://github.com/VincenzoImp/job-search-tool/compare/v4.3.1...v4.3.2
[4.3.1]: https://github.com/VincenzoImp/job-search-tool/compare/v4.3.0...v4.3.1
