# Collector transport

Collectors emit normalized jobs through the shared ingestion service. A saved
search has one query/location and selected portals; a company source has one
supported ATS board or feed. Adapter-specific parsing stays inside the collector.

## HTTP and progress

Use `DiscoveryService.fetch_bytes` or the supplied `ProviderBudget` for every
public HTTP attempt, including previews, URL imports, redirects, listing pages
and details. The persisted gate validates destinations, records responses and
shares request spacing and server cooldowns. Provider settings contain enable/pause
and the request interval. Internal bounded attempts yield without losing progress;
long waits defer the task and release the collection lane.

`source['checkpoint']` contains durable pagination/detail state.
`source['on_checkpoint'](state)` persists progress, while `source['on_item'](item)`
offers observations to the complete-text admission rule. Save enough progress to
retry idempotently after a cooldown or interruption. Mark the checkpoint complete only after the bounded
listing/detail work is exhausted. Preserve successful records when a later
request fails.

Complete archived descriptions can be reused within the detail freshness window.
Detail retrieval is automatic; keep pending candidates in the checkpoint until
usable text is available. The admission rule precedes archive/count bookkeeping,
so a header cannot consume the identity's later completed observation. Diagnostics
distinguish pending or unavailable text, coverage caps and provider-wide failures.
An access challenge must stop affected work instead of triggering empty detail
retries for every job. Metadata-only adapters expose `automatic_collection: false`
and support preview only.

## JobSpy subset

The attributed [JobSpy subset](../_vendor/jobspy/PROVENANCE.md) uses an explicit
per-instance transport hook. It carries resumable provider state and emits typed
records without a dataframe dependency or global HTTP monkeypatch.

When upgrading the subset, review its pinned source/notice, transport seam,
pagination state and description reuse. Exercise a page → deferred batch → resume
workflow and a bounded live request through the shared gate. See
[Architecture](../../../docs/developer/architecture.md) for service boundaries.
