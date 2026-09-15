# Troubleshooting

Symptoms first. Each entry says what you would see, why it happens, and what to
do about it.

## My edit to `settings.yaml` did nothing

Three different causes, in order of likelihood.

**The file was replaced rather than written.** `settings.yaml` is bind-mounted
as a single file. Editors that save atomically — write a temporary file, then
rename it over the original — replace the inode, and the container keeps
reading the old one forever. Everything looks correct on the host and nothing
changes inside. Either configure your editor to write in place, or
`docker compose restart` after editing.

**The edit was rejected and the previous configuration kept.** Unknown keys
fail at startup, but on a live reload an invalid file is logged and the running
configuration stays. Check `logs/openings.log` for a `ConfigError`.

**It was a scoring edit and you restarted the wrong container.** `openings run`
and `openings scheduler` rescore the archive at startup; `openings web` does
not. Restart the scheduler, or run `openings rescore` directly.

## The run finished and collected nothing

Open the **Runs** view: every source reports its own row count and its own
error, which usually names the cause.

If board searches returned nothing, the queries are probably too narrow or the
location string is not one the board recognizes. Try one query and one location
by hand first.

If a company returned nothing, the slug is wrong or the board has no postings
that pass its `locations` filter. Probe it directly — there is a `curl` recipe
per feed shape in [Sources](sources.md#finding-companies-to-add).

## A source says `response is not XML`

Personio's feed is public but the employer has to switch it on (Settings >
Recruiting > Career page). A tenant that never did answers with the career
site's HTML instead of the feed. Nothing to fix on this side; that employer is
not reachable this way.

## A source says `HTTP 429` or `HTTP 422`

The board is rate-limiting. Boards throttle aggressively against anything that
is not a browser, and shared egress addresses get throttled harder. The source
is reported as failed for that run and retried on the next one.

If it happens every run, ask for less: fewer queries, fewer locations, fewer
pages. The tool spaces its requests, but there is no setting that makes a board
enjoy being polled.

## LinkedIn returns nothing, or far less than the website shows

Board scraping is best-effort and rate-limited by design. The `jobspy` section
has throttling settings; the defaults are already conservative. A long run that
returns progressively fewer rows per query is the board deciding it has seen
enough of you, and waiting is the only fix.

## Jobs I had are gone

`save_threshold` is applied retroactively. Every start of `openings run` or
`openings scheduler` rescores the archive and then deletes jobs still in status
`new` that fall below it, so raising the threshold removes stored postings.

`retention.max_age_days` removes jobs in status `new` not seen for that long.

Both only ever touch status `new`. Anything you have shortlisted, applied to,
or attached files to is never deleted by either. Use
`GET /api/cleanup/preview` before changing either number.

## Compose created a directory called `settings.yaml`

Docker creates a directory when it is told to bind-mount a file that does not
exist. Remove the directory, create the file, start again:

```bash
docker compose down
rm -rf settings.yaml
cp config/settings.example.yaml settings.yaml
docker compose up -d
```

## The first start is slow, or `models/` is filling up

The first run downloads a sentence-embedding model of roughly 90 MB. That is
what makes semantic search and "similar jobs" work. It happens once.

If it fails, the tool keeps working: embeddings are optional and their absence
is reported on `/health`. Only semantic search is lost.

## `docker compose up` fails with a schema error

The Compose file uses the long form of `env_file`, which needs Compose v2.24 or
newer. `docker compose version` will tell you what you have.

## The API returns 401 but `/docs` still opens

That is current behaviour: `OPENINGS_API_TOKEN` gates `/api` and `/mcp`, while
the interactive OpenAPI pages (`/docs`, `/redoc`, `/openapi.json`) are served
without it. They expose the shape of the API, not its data. If that matters in
your deployment, do not publish the port: everything binds to `127.0.0.1` by
default, and putting this behind a reverse proxy with its own authentication is
the supported way to expose it.

## Something else

Runs, errors and per-source counts all live in the **Runs** view and in
`logs/openings.log`. A run that fails entirely is retried according to
`scheduler.retry_on_failure`. If the database itself looks wrong, the recovery
procedure is in [Operations](operations.md).
