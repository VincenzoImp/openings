# Interface feasibility review

The proposed external-agent architecture is feasible. The remaining work is
ordinary application implementation, not an unresolved protocol dependency.
Keep the production code fresh; the imported experiment here is a proof fixture.

## Practical proof

`mcp_file_probe.py` starts a temporary real localhost HTTP server and uses the
MCP SDK client over Streamable HTTP, not direct calls into tool functions.
It discovers typed tools, prepares and reads a context resource, changes the
profile through REST, and confirms the old context stays frozen.

The client compiles a real synthetic PDF with Tectonic outside the server. MCP
grants bounded binary transfers for a particular content revision; the client
uploads and downloads PDF plus TeX byte-for-byte. A second content revision does
not inherit the previous PDF. A consistent SQLite backup includes both revisions,
the context and exact file bytes, passes integrity and foreign-key checks.
Missing owner credentials are rejected at both REST and MCP boundaries.

See `mcp-file-probe.json` for the result. All checks pass. No live user data,
credentials, external network service, commits or production deployment were used.

## Small concrete choices to preserve

- Bind each immutable PDF/source attachment to a **content revision and frozen
  context**, not merely a job or mutable current-document row. Manual source edits
  create a new draft whose PDF is missing until externally compiled/uploaded.
- Keep file bytes out of ordinary tool results. MCP reserves a short-lived,
  narrowly scoped transfer; raw HTTP moves bytes with declared size and SHA-256.
  This also works when a model cannot access its MCP client's secret header.
- Use typed object response envelopes, including lists. The first live attempt
  exposed that an empty bare-list tool result can have no text block in this SDK.
- Resolve stored general instructions, template append and application note
  inside context preparation. The old experiment accepts a general prompt as
  input; it does not yet prove those instructions are persisted in SQLite.
- One owner login plus separately revocable hashed bearer tokens is enough for
  the stated single-user product. Share authorization across REST/MCP; browser
  session/CSRF handling still needs production implementation. No embedded agent
  subscription login or OAuth account system is needed for this proof.

## Limits

This is not a real Codex/Claude session, dashboard, production auth scheme,
concurrency/load test or large-file benchmark. It proves SDK transport and the
file/context/backup boundary. It does not prove factual CV accuracy, complete
application features or target-device memory. Validate those during their
implementation milestones, with a practical agent walkthrough before release.

## Reproduce after copying

From `experiments/next` with its existing venv/dependencies and cached Tectonic
packages, place the probe there and run:

```sh
uv run python mcp_file_probe.py --contract-dir . --tectonic tectonic --out mcp-file-probe.json
```

The probe creates and removes temporary server/database/compiler files. Its JSON
evidence contains only synthetic metadata and hashes, not transfer grants or tokens.
