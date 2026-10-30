# Collector transport

Collectors emit normalized jobs through the shared ingestion service. A saved
search has one query/location and selected portals; a company source has one
supported ATS board or feed. Adapter-specific parsing stays inside the collector.

## HTTP and progress

Use `DiscoveryService.fetch_bytes` or the supplied `ProviderBudget` for every
public HTTP attempt, including previews, URL imports, redirects, listing pages
and details. The persisted gate validates destinations, records responses and
shares provider windows/cooldowns. A batch cap bounds worker work; rolling quotas
remain shared when the next batch resumes. Long waits defer the task.

`source['checkpoint']` contains durable pagination/detail state.
`source['on_checkpoint'](state)` persists progress, while `source['on_item'](item)`
ingests completed observations. Save enough progress to retry idempotently after
quota waits or interruption. Mark the checkpoint complete only after the bounded
listing/detail work is exhausted. Preserve successful records when a later
request fails.

Complete archived descriptions can be reused within the detail freshness window.
Keep metadata collection separate from optional detail requests so known jobs do
not spend the same detail budget repeatedly. Diagnostics should identify missing
text, coverage caps and provider failures. Challenge/error pages must remain
visible as failures.

## JobSpy subset

The attributed [JobSpy subset](../_vendor/jobspy/PROVENANCE.md) uses an explicit
per-instance transport hook. It carries resumable provider state and emits typed
records without a dataframe dependency or global HTTP monkeypatch.

When upgrading the subset, review its pinned source/notice, transport seam,
pagination state and description reuse. Exercise a page → deferred batch → resume
workflow and a bounded live request through the shared gate. See
[Architecture](../../../docs/developer/architecture.md) for service boundaries.
