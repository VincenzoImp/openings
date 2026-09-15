# Getting started

Start to finish: from a fresh clone to a database collecting the jobs you
actually want. Expect about half an hour, most of it spent deciding what you
are looking for rather than typing.

The hard part of this tool is not installing it. It is the configuration, and
specifically three decisions nobody can make for you: which words describe the
work you want, which employers to watch, and where the line is between a job
worth seeing and noise. This page walks through all three in the order that
works.

## Before you start

- Docker Engine with Compose v2.24 or newer. The Compose file uses the long
  form of `env_file`, which older versions reject with a schema error.
- About 200 MB of disk. The first run downloads a sentence-embedding model of
  roughly 90 MB into `models/`, which is what makes semantic search work.
- Nothing else. No API key is required for any source that is on by default.

## 1. Get the files

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
cp config/settings.example.yaml settings.yaml
```

The example file is the annotated reference: every key it contains is set to
its default, and every key is explained in place. You will edit it in the next
three steps and it will keep being the document you come back to.

## 2. Say what work you want

Open `settings.yaml` and edit `sources.jobspy`. This is the broad net: board
searches run for every combination of query and location, so keep both lists
short at first.

```yaml
sources:
  jobspy:
    enabled: true
    locations: ["Berlin, Germany"]
    queries:
      core: ["backend engineer", "platform engineer"]
```

Two queries against one location is a run of a few minutes. Twenty queries
against six locations is a run of an hour, so grow this list only once you can
see what it returns.

## 3. Say which jobs are worth seeing

This is `scoring`, and it is the part that decides whether the tool is useful
or just another inbox. A posting's score is the sum of the weights of every
category whose terms it matches. Nothing is normalized: the numbers mean what
you make them mean, so their relationship to each other is what matters.

```yaml
scoring:
  save_threshold: 0
  notify_threshold: 20
  weights:
    role: 25              # the work you want
    stack: 15             # tools you actually have
    language_required: -60  # a hard blocker, big enough to sink everything else
  keywords:
    role: ["backend engineer", "platform engineer"]
    stack: ["python", "go", "postgresql"]
    language_required: ["fluent in german", "deutsch erforderlich"]
```

A configuration that works usually looks like this:

- **Four to eight categories.** More than that and you cannot predict what a
  score means, which is the whole point of having one.
- **Positive weights between 5 and 30**, with the one category that describes
  your actual job at the top. A role matching only "nice to have" categories
  should not out-score one matching the core.
- **Negative weights large enough to dominate.** A blocker is not a small
  penalty: if a language you do not speak is a hard requirement, its weight
  should be bigger than every positive combined, so no amount of good fit
  rescues it.
- **`save_threshold: 0` on the first day.** Let everything in, look at what
  arrives, and raise it once you can see where the noise sits.

Then tune it with evidence rather than by feel:

```bash
docker compose exec scheduler openings rescore --dry-run
curl -s localhost:8501/api/distribution | jq
```

`rescore --dry-run` reports what a scoring edit would change without writing.
`/api/distribution` is the histogram of the scores you already have; a good
`notify_threshold` usually sits where that histogram thins out.

One caution worth reading twice. **`save_threshold` is applied retroactively.**
Every start of `openings run` or `openings scheduler` rescores the archive and
then deletes jobs still in status `new` that now fall below it. Raising the
threshold therefore throws away stored postings. Check
`GET /api/cleanup/preview` first. Anything you have moved out of `new` —
shortlisted, applied, anything with your files attached — is never touched.

## 4. Add the employers you care about

Board searches miss a lot. An employer's own applicant tracking system does
not, and this tool reads thirteen of them directly, with complete descriptions
and exact locations.

Find the slug in the company's careers URL and add it:

```yaml
sources:
  companies:
    - name: "Example"
      ats: "greenhouse"
      slug: "example"
      locations: ["Berlin", "Remote"]
```

Start with five employers you would genuinely work for. Then, when you want
reach rather than precision, work from the community-maintained slug lists:
**[Sources → Finding companies to add](sources.md#finding-companies-to-add)**
names the three lists worth using and shows how to screen tens of thousands of
slugs down to the ones that post where you live. That section is the answer to
"how do I find companies to put in here", and it is worth reading before you
add the sixth.

One rule: screen by location, not by name. Companies are fetched one at a time
on every run, so a board that never posts near you costs a request forever and
returns nothing.

## 5. Start it

```bash
docker compose up -d
open http://127.0.0.1:8501
```

The first run starts immediately. Watch it in the **Runs** view: every source
reports how many rows it returned and any error it hit, which is the fastest
way to learn that a slug is wrong or a query is too narrow.

## 6. Read the first run, then tune

Look at the **Inbox**, sorted by score, and ask two questions.

**Is anything good scoring low?** Your `role` terms are too narrow, or the
words you used are not the words employers use. Add the words they actually
write.

**Is anything bad scoring high?** You are missing a negative category. Add one
that names the thing you never want, and give it a weight large enough to sink
a posting on its own.

Every job shows which categories matched and what each contributed, so you are
never guessing at why a number came out the way it did.

Repeat this two or three times over the first few days. After that the
configuration mostly stops changing, and the tool becomes the thing you check
once a day rather than the thing you tune.

## Where to go next

| You want to | Read |
| --- | --- |
| Understand every configuration key | [Configuration](configuration.md) |
| Add more sources, or find employers to add | [Sources](sources.md) |
| Know what the dashboard can do | [Dashboard](dashboard.md) |
| Run it properly: backups, retention, recovery | [Operations](operations.md) |
| Drive it from a script | [REST API](api.md) |
| Drive it from an AI agent | [MCP server](mcp.md) |
| Deploy it somewhere other than your laptop | [Docker](docker.md) |
