# Optional CPU scorer

This separate service provides fit classification for Openings. The core and
HTTP supervisor never import PyTorch; one child process loads the pinned Laya
English model on demand. It uses at most two CPU threads and handles one ordinal
question per request. No model is downloaded until a score is requested.

## Connect

Start the Compose `local` profile as described in [Setup](../docs/user/getting-started.md).
In Openings, use provider `laya`, served model `english` and URL
`http://scorer:8000`. Configure the same `SCORER_API_KEY` in the service and app.
The service exposes `POST /v1/systemone`, the text/JSON score subset Openings uses;
an arbitrary OpenAI chat endpoint is not compatible.

The default context is 2048 tokens, including the rubric and score levels. The
service uses the checkpoint tokenizer to reserve that question, bound candidate
and job details, and keep the posting prefix that fits. It returns preparation
metadata and the prepared text when handling an Openings context. Original archived
postings are unaffected. Oversized rubrics or levels return a configuration error.

Dependency versions are locked in `constraints.txt`; the image installs its
separately pinned CPU PyTorch wheel from the official PyTorch index.

## Configuration

| Variable | Default |
|---|---|
| `SCORER_MODEL` | `convaiinnovations/laya` |
| `SCORER_REVISION` | `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851` |
| `SCORER_MAX_CONTEXT` | `2048` |
| `SCORER_THREADS` | `2`, bounded to 1–2 |
| `SCORER_API_KEY` | Empty; set a key for bearer authentication |
| `SCORER_IDLE_UNLOAD` | `120` seconds, minimum 15 |
| `SCORER_REQUEST_TIMEOUT` | `600` seconds, bounded to 5–600 |

`GET /health` reports idle/loaded state. Idle unloading or `POST /v1/unload`
releases the child process after active work settles; cached weights remain on
disk. Selecting an unserved model does not download additional checkpoints.

Scores are advisory, with possible language/qualification errors. The
[user scoring guide](../docs/user/scoring.md) covers freshness, remote mode and
[resource limits and CPU compatibility](../docs/user/scoring.md#resources-and-cpu-compatibility).
The default scorer cap is 1.5 CPU / 3584 MiB; the core adds 0.5 CPU / 512 MiB.
These container limits do not establish minimum host requirements. A compatible
scorer can run on another machine, or the application can run with scoring disabled.
