# Problem and Domain Model

## The Underlying Problem

At a domain level, the repository addresses a recurring decision-support
problem:

> A single user must continuously monitor heterogeneous external sources,
> extract potentially relevant opportunities, reduce noise, remember prior
> results, and focus their time on the best new items.

The domain is "job search", but the structure is broader than that. The same
shape appears in grants discovery, procurement sourcing, startup deal flow, and
 research watchlists.

## Why Job Search Is Hard

Job search is not just about finding postings. It is a compound workflow:

1. discover openings across fragmented channels,
2. map those openings to personal goals and constraints,
3. avoid duplicates and stale information,
4. remember what has already been seen,
5. keep only worthwhile opportunities,
6. escalate only the highest-value new opportunities,
7. maintain a working archive that can be reviewed later.

Most public job boards solve only step 1.
This project attempts to solve all seven for an individual operator.

## Actors in the Current System

### Primary human actor

- The job seeker, who configures the system, receives notifications, and
  curates the resulting database.

### Machine actors

- Job source aggregators and boards reached through `JobSpy`
- The scheduled runtime that launches searches
- The SQLite database storing active jobs and deleted jobs
- The vector store maintaining semantic embeddings
- The Telegram channel used as an attention-routing mechanism
- The Streamlit UI, REST API, and MCP server as access surfaces

## Core Domain Concepts

### Search Intent

The effective search intent is the Cartesian product of:

- configured query strings,
- configured locations,
- configured source sites,
- search filters such as age, remote-only, job types, and pagination.

The system does not model search intent as a first-class persisted entity, but
it exists conceptually and drives every run.

### Job Listing

A job listing is the raw opportunity record returned by an external source.
Fields include title, company, location, URL, description, compensation, and
source metadata.

In the current implementation, listings from multiple sources are normalized
into a common pandas-oriented structure and then into `Job` or `JobDBRecord`.

### Canonical Job Identity

Identity is derived from a normalized triple:

- title
- company
- location

Those values are Unicode-normalized, whitespace-collapsed, case-folded, joined,
and hashed with SHA256.

This is simple and deterministic, but it is also an approximation:

- two distinct roles with the same title/company/location may collapse,
- a role whose location string changes may become a new identity,
- source-native identifiers are not used as the primary key.

### Relevance

Relevance is a scalar integer score.
It is produced by matching configured keyword lists against the concatenated job
text.

Each category contributes its configured weight if any keyword in that category
matches. The model is additive and configuration-driven.

This means the score is:

- explainable,
- easy to tune,
- easy to test,
- not semantically deep,
- not personalized beyond manual keywords and weights.

### Persistence Threshold vs Notification Threshold

This is one of the most important domain abstractions in the repository.

- `save_threshold` answers: "Is this job worth keeping in the archive?"
- `notify_threshold` answers: "Is this job worth interrupting the user for?"

This split creates three zones:

- below save threshold: discard
- between save and notify threshold: persist but do not alert
- at or above notify threshold: persist and alert

That separation is the difference between a useful archive and a noisy notifier.

### Newness

The system distinguishes "new in this run" from "already known".
This is computed by comparing derived job IDs against the database and the
blacklist.

Newness is operationally critical because notifications are based on novel,
high-scoring jobs, not simply on high-scoring jobs.

### Blacklist

Deletion is not simple removal.
A deleted job is moved into a persistent blacklist table so future search runs
do not reintroduce it.

The blacklist acts as negative memory:

- it encodes user rejection,
- it prevents futile rediscovery,
- it makes curation durable across runs.

### Retention

Retention manages archive quality over time.
The current system supports:

- delete below score,
- delete stale jobs older than a configured age,
- purge old blacklist rows.

Bookmarked and applied jobs are protected in automatic delete paths.

### Manual State

The current system supports two manual state flags:

- `bookmarked`
- `applied`

These states are not used for ranking, but they are crucial for lifecycle and
protection:

- they survive rescoring,
- they protect jobs from automated cleanup,
- they support the dashboard and APIs.

### Semantic Index

The vector store is an auxiliary retrieval layer over persisted jobs.
It is not part of the source collection process itself.

It allows the user or an LLM to ask questions such as:

- "remote python backend jobs"
- "distributed systems roles"
- "roles similar to this query"

This adds fuzzy discovery over the curated archive, not over the open web.

## Domain Boundaries

The project boundary is narrower than the full hiring journey.

Inside the boundary:

- search automation
- relevance filtering
- storage and retention
- manual curation
- semantic lookup
- notification delivery
- lightweight programmatic access

Outside the boundary:

- resume authoring
- cover letter generation
- application submission
- interview prep
- salary negotiation
- recruiter CRM
- team collaboration
- employer-side workflows

## The Domain Model in One Table

| Concept | Meaning in the system | Why it matters |
|---|---|---|
| Search intent | What the user is looking for | Drives every scrape |
| Listing | Raw opportunity data | Base unit of discovery |
| Job identity | Stable local key | Enables dedupe and memory |
| Relevance score | Priority estimate | Separates noise from value |
| Save threshold | Archive boundary | Prevents low-signal storage |
| Notify threshold | Attention boundary | Prevents alert fatigue |
| Blacklist | Negative memory | Prevents resurfacing rejected jobs |
| Manual state | User judgement overlay | Preserves important items |
| Retention policy | Archive hygiene | Keeps the corpus useful |
| Semantic embedding | Fuzzy retrieval aid | Makes the archive explorable |

## Core Insight

The true product is not "job scraping".
The true product is "selective memory and prioritization over recurring external
opportunity streams".
