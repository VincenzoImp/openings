# Companies and manual offers

**Companies** watches explicit employer boards or feeds. It does not search every
job site or guess which employers you want. Supported source kinds are Greenhouse,
Lever, Ashby and RSS/Atom. Unsupported career pages can still supply manual offers.

Paste a board/feed URL and select **Preview**. Review the detected platform,
company and results, add title/location filters, then save. Sources start paused.
Enable an interval or a daily time with an IANA timezone when ready. **Run now**
queues one collection even for a paused source. Pause stops future scheduled runs;
existing archived jobs remain.

The same operations are available through `/api/v1/sources` and `sources_*` MCP
tools. Preview does not save a source or import offers. Tasks show collection
progress and failures; one failed source does not empty the archive.

## Manual input

Use **Add job** for a URL, pasted posting or structured fields. REST `POST /jobs`
and MCP `job_ingest` use the same ingestion path as collection. URL extraction
reads public HTTP(S) pages; a login, JavaScript-only site or blocked page may need
you to paste the full description instead. An incomplete posting is retained for
correction and is not a useful scoring input.

Repeated identities update the known job without resetting triage or application
history. Manually corrected fields remain authoritative. If two distinct URLs
represent one role, verify them before using explicit Merge.

## Triage versus application progress

| Field | Values and meaning |
|---|---|
| Job triage | Inbox, Saved, Dismissed. Dismissed stays remembered and can be restored. |
| Application | Draft, Applied, Interview, Offer, Closed. Each attempt has its own history. |
| Closed outcome | Accepted, Rejected, Not pursued. |
| Forget | Deletes the job, identities and all job-owned applications/documents. A future collection can add it as new. |

Creating documents never changes an application to Applied. Reapplying creates
another attempt attached to the same job. Job availability is separate from your
application outcome.
