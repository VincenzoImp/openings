# Quality, Operations, and Risks

## Quality Posture

The repository has a stronger quality posture than a typical personal utility
project.

Evidence from the codebase:

- explicit type hints throughout core modules
- meaningful unit coverage across modules
- integration tests covering score-partition-save-reconcile behavior
- API and MCP contract tests
- dashboard helper tests
- CI for lint, type check, runtime tests, security audit, and Docker build

This makes the project easier to trust, modify, and document.

## Testing Strategy

The test suite uses a layered approach:

- isolated unit tests for pure logic and validation
- mocked boundary tests for external integrations
- temporary real SQLite databases for integration behavior
- end-to-end API and MCP workflows against real temp databases

Important product invariants are explicitly tested:

- `notify_threshold >= save_threshold`
- dedupe and blacklist behavior
- score recalculation at startup
- retention idempotency
- protection of bookmarked/applied jobs
- notification eligibility based on current-run novelty

## Operational Packaging

### Docker image strategy

One image supports all process roles:

- scheduler
- dashboard
- API
- MCP server

This is operationally simple and well suited to a personal deployment model.

### Compose topology

Default composition:

- scheduler always on
- dashboard always on
- API optional
- MCP optional

The services share one data volume, which keeps the system coherent.

## Logging and Observability

The observability model is lightweight but thoughtful.

### Available signals

- structured console logs
- rotating file logs
- section headers for major runtime stages
- progress logging for multi-task search
- deduped third-party warnings
- basic database statistics
- dashboard metrics

### Missing signals

- no distributed tracing
- no structured metrics backend
- no per-run event log persisted as analytics data
- no explicit audit log for user actions
- no alerting beyond process failure or Telegram job messages

For the current deployment model, this is acceptable.
For a larger multi-user system, it would be insufficient.

## Security and Privacy Posture

### Positive properties

- local-first state reduces broad exposure
- Telegram token can be provided through environment variables
- Docker runs as a non-root user
- health checks verify writable state rather than assuming it
- CORS openness is acceptable for a personal tool

### Gaps relative to enterprise expectations

- no authentication or authorization
- no encryption strategy beyond whatever the environment already provides
- no secrets manager integration
- no compliance model
- no multi-tenant data isolation

Again, this is consistent with the actual product scope.

## Architectural Strengths

### 1. Strongly coherent problem framing

The product does not try to do too much.
Its features align around one loop: discover, rank, store, notify, curate.

### 2. Good threshold model

The save/notify split is a genuine product-quality improvement over single-cutoff
systems.

### 3. Explicit negative memory

Persistent blacklisting is simple but high leverage.

### 4. Protected cleanup

The SQL-level protection of bookmarked and applied jobs turns retention from a
dangerous background process into a usable maintenance tool.

### 5. Shared service layer for adapters

The extraction of `job_service.py` prevents drift across UI, API, and MCP.

## Architectural Risks and Limits

### 1. Scraping dependency fragility

The whole discovery layer depends on `JobSpy` and the continued accessibility of
scraped job boards.
Any upstream HTML or anti-bot change can degrade collection quality.

### 2. Identity approximation

The job ID model is operationally useful but semantically imperfect.
It is good enough for a personal archive, not for canonical labor-market data.

### 3. Simple scoring ceiling

Keyword substring matching is explainable and configurable, but it has hard
limits:

- no concept of term importance beyond category weight
- no semantic understanding
- no personalized learning from user feedback
- vulnerable to noisy descriptions

### 4. Tight orchestration coupling in `main.py`

`main.py` centrally knows about searching, saving, vector indexing, and
notifications.
That is manageable now, but it concentrates workflow policy in one place.

### 5. SQLite scalability boundary

SQLite is correct for the current product, but it creates natural limits for:

- concurrent writes,
- remote deployment patterns,
- multi-user access,
- analytical workloads,
- more complex workflow history.

### 6. Streamlit ceiling

The dashboard is fast to build and suitable for an internal operator console,
but it limits:

- richer interaction flows,
- collaborative behavior,
- design consistency at scale,
- offline-first patterns,
- complex stateful UX.

## Recommended Evolution Path for the Existing Project

If this repository were to keep evolving without a full rewrite, the best next
steps would be:

1. extract more workflow policy from `main.py` into a dedicated application
   service module,
2. persist search-run metadata and action logs,
3. introduce explainable scoring breakdowns per category,
4. upgrade semantic search from auxiliary convenience to a first-class ranking
   input,
5. add richer manual workflow state beyond `bookmarked` and `applied`,
6. consider a migration path from SQLite to Postgres only if multi-user or
   hosted operation becomes real.

## Bottom Line

This is a disciplined personal automation product with a sensible scope.
Its main risks come from source fragility, intentionally simple ranking, and the
limits of a single-user local-stack architecture, not from code chaos.
