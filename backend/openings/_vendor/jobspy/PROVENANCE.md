# JobSpy 1.4.1 transport subset

Upstream: [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy), MIT;
copyright and permission notice are preserved in LICENSE. Source is the
`python-jobspy==1.4.1` PyPI wheel, SHA256
`8b5ace6c3d19612868d739673d4fcdb8f6f8b428984d44174668dc7ed0599cea`.
Wheel URL: https://files.pythonhosted.org/packages/99/3e/87d79b04f946da7c8d2ee84add5098cf88e6b32d373df6ff384ccff5cbf5/python_jobspy-1.4.1-py3-none-any.whl

Only shared models/utilities and the LinkedIn, Indeed and Glassdoor providers
are included. Openings directly consumes typed JobPost records; the dataframe,
CLI, MCP server and unrelated providers are omitted. No global `jobspy` package
or global HTTP monkeypatch is used.

Local changes:

- Namespace imports under `openings._vendor.jobspy`.
- `Scraper(transport=None)` explicitly accepts an instance transport.
- `create_session(..., transport=None)` attaches that transport to its new
  instance. `RotatingProxySession.request` delegates through it, covering every
  search, location lookup and detail HTTP attempt and response, including errors.
- All three provider session constructors supply `self.transport`.
- Remove LinkedIn's random inter-page sleep; the shared persisted Openings gate
  now spaces every HTTP attempt, including detail fetches. Provider endpoints and parsers remain upstream-derived.
- Disable implicit environment proxy/auth configuration on the new sessions.
  The transport bounds decoded response bodies to 8 MiB: synchronous streaming
  for requests, a bounded receive callback for curl without a background queue.

- Provider pagination and pending detail rows are checkpointed after each page or
  detail batch. Resumed tasks reuse that progress and fresh archived descriptions.
- LinkedIn requests newest-first ordering (`sortBy=DD`). Indeed cursor values are
  JSON-escaped; its upstream relevance ordering remains unchanged.

Future upgrades must explicitly review this seam, reproduce the transport tests
and bounded live provider checks, and update the pinned source hash and notice.
