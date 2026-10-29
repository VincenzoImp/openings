# Collector transport

Collectors return normalized job records to the shared archive. Each saved search
has one query/location; each company source has one explicit board/feed.

Use `DiscoveryService.fetch_bytes` or an instance `ProviderBudget` for every public
HTTP request, including previews, manual URL imports, redirects and detail pages.
The gate validates public destinations, counts attempts and records responses.
It shares persisted provider windows/cooldowns across runs and honors Retry-After.
Long waits defer a task; cancellation and partial results remain visible.

Do not bypass the gate with a new HTTP client, silently retry a blocked response,
or turn challenge/error pages into successful empty searches. Keep listing/detail
limits bounded and preserve already collected records when later requests fail.

The attributed [JobSpy subset](../_vendor/jobspy/PROVENANCE.md) uses an explicit
per-instance transport hook. Review that seam and the acquisition tests when
upgrading it; no global client monkeypatch is used. See the
[architecture guide](../../../docs/developer/architecture.md) for queue and service boundaries.
