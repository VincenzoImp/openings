# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.2] - 2026-09-16

### Fixed

- **`sources.jobcloud` collected nothing whenever `rows` was above 20.** The
  board refuses a larger page with HTTP 422 rather than truncating it, so the
  shipped example's `rows: 50` failed every single request and reported an
  empty source. `rows` is now clamped to the API's own limit, and the example
  and documentation no longer advertise a value that cannot work. Found in
  production: 48 tasks, 48 failures, 0 rows.
- **A filter on `status_changed_from` or `status_changed_to` returned nothing
  during the first hours of the day** in any timezone ahead of UTC.
  `status_changed_at` is stored as a UTC timestamp while the other date
  filters compare plain local dates, so "changed today" asked for a date the
  stored value would not reach until later. The timestamp is now converted
  before comparison.

## [0.4.1] - 2026-09-15

A review pass over the source layer before the repository goes public. Every
item here is a defect found by reading the code that 0.3.0 and 0.4.0 shipped,
not a new feature.

### Fixed

- **The Workday posting key captured the city instead of the requisition**, so
  every Workday opening at one employer in one city collapsed into a single
  job. Two roles in Zurich at the same company became one row, and the loss
  happened during collection, before the database could see it.
- **The Workable posting key never matched the URL the adapter builds.** The
  pattern required `/j/` immediately after the host, while the widget API
  returns `apply.workable.com/<slug>/j/<code>`, so one opening seen through
  both of its URLs stayed two postings — the exact defect 0.4.0 claimed to
  close.
- **The parity test that was supposed to catch both asserted only that a name
  existed in the table.** It never checked that a pattern matched a URL any
  adapter actually produces, nor that two distinct postings produced distinct
  keys. Replaced with a table of real posting URLs per adapter and two
  assertions: a known board must canonicalize, and two postings on one board
  must never share a key.
- **One company with an unexpected payload discarded every other source's rows
  in the same run.** `fetch_company` caught only `SourceError`, but a vendor
  that changes its payload shape raises `TypeError` or `AttributeError` inside
  the adapter, and the combined frame is built after the whole loop. The
  docstring promised isolation the code did not provide.
- **Three adapters stopped after the first page when the vendor's total was
  missing.** `offset >= int(payload.get("total") or 0)` is true at offset 0
  when the field is absent or renamed, so a board with hundreds of postings
  silently returned twenty and looked small. A short page is now the only end
  of a listing. Workday returned 79 rows instead of 20 after the fix.
- **Three adapters built a shared fallback URL** when a posting carried no id,
  which gave every such row the same posting key and merged them. The fallback
  is now `None`, so the key falls back to `source:external_id`.
- `sources.jobcloud` fetched the same descriptions on every run forever: it
  never received the `known` callback its own docstring said it used.
- The jobs.ch pattern matched any host ending in `jobs.ch`, including
  `alljobs.ch`.

### Changed

- **`locations` on a company source no longer means two different things
  depending on the ATS.** Seven adapters pre-filtered with a predicate that
  rejects a posting with no location, while `collect._keep` has always kept
  those and let scoring decide. One `location_kept` helper now backs both.
- **`is_remote` is three-valued again everywhere.** Nine adapters wrote
  `bool(x) or None`, which turns "the employer said this is not remote" into
  "we do not know", and the two are queried separately. One `remote_flag`
  helper keeps what the board stated and only ever infers `True` from a
  location.
- `sources.jobcloud` spaces its requests and no longer filters the board's own
  answers a second time. The board resolves a city to its commuting region, so
  filtering its results by city name again discarded the neighbouring towns the
  operator asked for by naming the city.
- An enabled `sources.jobcloud` with neither a query nor a location is now a
  configuration error instead of a download of the whole board.

### Added

- `docs/user/getting-started.md`: the path from clone to collecting, including
  how to write a scoring configuration that works and where to find the
  employers worth watching. The README now leads with it.
- `docs/user/troubleshooting.md`, collecting the symptoms that were scattered
  across four pages or absent: an edit that appears to do nothing, a run that
  collects nothing, `response is not XML`, `HTTP 429`, and jobs that disappear.
- A "What it does not do" section in the README.

### Notes

- Several documented statements were wrong and are corrected: only `openings
  run` and `openings scheduler` rescore at startup (not `openings web`);
  `notifications.enabled` gates the whole section and both it and
  `telegram.enabled` must be true; `sources.jobcloud` was missing from the
  configuration reference entirely; an invalid file on a live reload is logged
  and the previous configuration kept, which contradicts the "a typo is an
  error, not a silent no-op" rule that holds only at startup.
- `save_threshold` is applied retroactively and deletes stored jobs still in
  status `new` at every `run`/`scheduler` start. That was documented in two
  places but not on the page where the value is edited.
- The documentation guard now checks spelled-out counts and table rows, not
  just that each name appears somewhere.

## [0.4.0] - 2026-09-15

### Added

- Four more applicant tracking systems behind the existing `sources.companies`
  shape: **Oracle Cloud Recruiting**, **Personio**, **Recruitee** and
  **BreezyHR**. Thirteen are now supported. Oracle covers roughly 1,279 known
  corporate tenants; Personio covers the small and mid-size employers of the
  German-speaking market, a segment no aggregator reaches well.
- **JobCloud** (`sources.jobcloud`), a regional job board with a public search
  API. One engine serves several domains, so the host is configuration rather
  than a constant and a second board is a second entry, not new code.
- A canonical language line. Where a source reports language requirements
  structurally, the description gains one line, `Required languages: German
  (level 3), English (level 2)`. Keyword scoring otherwise has to guess at
  phrasings; this states what the employer filled in, in the same words every
  time. The tool reports the requirement and invents no scale; whether a
  language disqualifies a role stays a `scoring.keywords` decision.
- `http_get_xml` in `sources.base`, for the first source whose feed is XML in a
  schema of its own rather than RSS.

### Fixed

- **Postings on the 0.3.0 adapters deduped worse than they should have.**
  `canonical_url` had no pattern for workday, joincom, workable, rippling or
  bamboohr, so their postings fell back to generic URL normalization and the
  same opening seen twice could stay two jobs. Patterns added for those and for
  everything new here, and a test now asserts every registered adapter has one.
- Boards whose posting ids are only unique inside one tenant now include the
  host in their canonical key. Without it two employers' requisition 7 would
  collapse into a single job.
- A Workday posting with no `externalUrl` in its payload built a URL with a
  doubled `/job/job/` segment.

### Changed

- Posting keys are renormalized once at startup. Teaching `canonical_url` a new
  board changes the key its stored postings hash to, and without this pass the
  next collection would miss the key lookup, be refused by the identity
  fallback (which will not mirror onto a job already seen on that source) and
  store those openings again as new jobs. The pass is idempotent and reports
  the count it changed.

### Notes

- Personio's feed is public but the employer must switch it on; a tenant that
  never did answers with its career-site HTML, which surfaces as `response is
  not XML`. Personio also throttles non-browser clients hard, so an occasional
  `HTTP 429` in a run summary is the board, not the adapter.
- BreezyHR publishes no description anywhere public: the feed carries none and
  the posting page is client-rendered. Its postings arrive title-only and are
  scored on the title alone.
- XML from third-party hosts is refused when it declares a DTD or entities.
  Nothing this project reads needs one, and the parser expands internal
  entities.
- `sources.jobcloud` clamps `rows`, `max_pages` and `max_details` in code as
  well as in configuration. The board has thousands of result pages, and a
  generous setting should not become thousands of requests.
- Still unsupported, deliberately: iCIMS, SAP SuccessFactors, JazzHR, Jobvite,
  Teamtailor and softgarden. They publish no machine-readable feed, and a
  per-vendor scraper of tenant-themed markup breaks silently rather than
  loudly, which is the one failure mode this project's source layer is built to
  avoid.

## [0.3.0] - 2026-09-15

### Added

- Five more applicant tracking systems behind the existing `sources.companies`
  shape: **Workday**, **join.com**, **Workable**, **Rippling** and
  **BambooHR**. Nine are now supported. The reach matters more than the count:
  join.com is where most small and mid-size employers in the German-speaking
  market publish, and Workday is where the large corporates and several big
  technology employers sit. Neither was reachable before.
- `http_post_json` in `sources.base`. Workday's listing is a search request
  rather than a GET, and it is the first feed that needs a body.
- A "Finding companies to add" section in `docs/user/sources.md`. No ATS
  publishes a directory of its customers, so every list of board slugs is
  community-scraped; the three worth starting from are named and linked, with
  the caveat that roughly 40 percent of published slugs are dead or private
  and that a list should be screened against your own locations before it is
  configured. Companies are fetched sequentially, so a source list is a
  decision, not a dump.

### Notes

- Workday's slug is the whole board address, `host/site` (for example
  `abb.wd3.myworkdayjobs.com/External_Career_Page`), because the tenant, the
  datacenter number and the site name vary independently and cannot be derived
  from a company name. The adapter rejects a slug without a site rather than
  guessing.
- join.com publishes no documented API, so its adapter reads the JSON the page
  ships to the browser. That is a scrape, and it is written to fail loudly when
  the page shape changes rather than to quietly return nothing.
- Workday, join.com, Rippling and BambooHR carry no description in their
  listings, so each fetches details only for postings not already stored, and
  only for postings that survive the location filter, capped per run. Workable
  returns the whole board with the copy included and needs no second request.

## [0.2.0] - 2026-09-15

### Added

- Per-category matching options in `scoring.keywords`. A category can be
  written as a mapping with `terms` plus an optional `match_in` (any subset of
  `title`, `description`, `company`, `location`) and `whole_word` (match a
  term as a token, so `go` stops matching Google and Lugano). A category
  written as a bare list of terms is unchanged: all four fields, substring
  matching, identical scores.
- `openings rescore`, which recomputes every stored score against the current
  configuration, and `openings rescore --dry-run`, which reports the count and
  the before/after score distribution without writing, so a scoring change can
  be validated before it lands.

## [0.1.0] - 2026-09-08

First release of Openings: a configurable job crawler, archive and application
tracker you run yourself, agent-operable through MCP. Openings supersedes
job-search-tool; it reads none of its configuration or data.

### Added

- One YAML file (`settings.yaml`) owns intake and scoring: sources, queries,
  locations, keyword categories with signed weights, save and notify
  thresholds, scheduler interval, notifications, retention. Unknown keys fail
  at boot; secrets can be indirected through `$ENV_VAR`; the web process
  reloads the file when it changes.
- Sources behind one canonical shape: job boards through JobSpy, company
  career feeds on Greenhouse, Lever, Ashby and SmartRecruiters, RSS and Atom
  feeds, the Adzuna API, and postings added by hand or by an agent. Every
  source is isolated per task so one failure never empties a run; feeds take
  location, title and age filters; employment types share one vocabulary.
- One job, many postings: a posting is identified by its canonical URL, the
  same opening seen on another board becomes a second posting of the job, and
  duplicates can be merged with their material.
- A job is the opening plus the application built around it: one status
  (`new`, `shortlisted`, `applied`, `interviewing`, `offer`, `rejected`,
  `withdrawn`, `blacklisted`), free labels, notes and form answers, file
  attachments (CV, cover letter, form answers, other), and an append-only
  timeline in UTC. Every status except `new` is protected from retention.
  Blacklisting hides a job and blocks its re-ingestion without deleting
  anything; it can be restored.
- A `runs` table with per-source counts and failures for every collection,
  a run-now request, and a Telegram digest sent only when something is new.
- Local semantic search on a built-in sentence model (ONNX), vectors in the
  database: "similar postings" and free-text search by meaning.
- REST API under `/api`, MCP tools under `/mcp` (same token as the API), and
  a dashboard, all served by one process and all calling the same service;
  one zip per application with the posting, notes, timeline and files.
- Dashboard built around triage, on phone, tablet and desktop in light and
  dark: Inbox (new postings, bulk actions, filters kept in the URL, semantic
  search with `~`), Pipeline (every status as a column), Companies, Runs,
  System, and a job page with Posting, Application and Activity tabs.
  Keyboard shortcuts throughout (`?` lists the active ones).
- Score explanation per job: which categories matched and what each weighed.
- CLI: `openings run`, `openings scheduler`, `openings web`,
  `openings healthcheck`. Docker image `vincenzoimp/openings` with a
  two-service Compose file. Unit, integration, Playwright and Docker smoke
  tests in CI.
