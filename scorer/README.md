# Optional CPU scorer

The core app never imports PyTorch. This optional service loads one pinned Laya
English checkpoint on the first score request, uses at most two CPU threads and
accepts one ordinal question at a time. It downloads no model until requested.

It implements the text/JSON `POST /v1/systemone` score subset used by Openings,
not every feature of TypeSafe's API. Set Openings' provider to `laya`, model to
`english`, and the URL to this service. `SCORER_API_KEY` enables bearer auth.
The core sends `max_len=2048`; truncated inputs are rejected rather than scored.

Configuration: `SCORER_MODEL`, `SCORER_REVISION`, `SCORER_MAX_CONTEXT` (2048),
`SCORER_THREADS` (maximum 2), `SCORER_IDLE_UNLOAD` (120 seconds),
`SCORER_REQUEST_TIMEOUT` (600 seconds). Selecting an
unserved model never downloads arbitrary additional checkpoints. Idle unloading
or `POST /v1/unload` stops the single model process and releases its runtime memory;
the disposable cache remains on disk. The HTTP process never imports PyTorch.

Scores are advisory. Known language/qualification mistakes remain possible.
Measured model-only Mac memory is not proof of a complete 4-GiB installation;
see the root release measurements and limits. A stronger compatible scorer may
run on another host, or scoring may remain disabled.
