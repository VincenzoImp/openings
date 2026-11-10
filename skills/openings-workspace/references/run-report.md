# Run report and resume note

Every workflow that reads or changes Openings ends with the same short report.
Server records stay authoritative; the report explains what this run did.

## Report

1. **Scope**: the owner's request, the cohort snapshot (count and how it was
   selected) and anything deliberately left out.
2. **Changes**: counts by action with record IDs, for example saved, dismissed,
   Drafts created or completed, revisions approved, sources changed.
3. **Not done**: each remaining record with the precise reason (unresolved fact,
   employer requirement, failed check, conflict, missing capability).
4. **Questions for the owner**: only facts or decisions that block or materially
   improve a result, each tied to its record.
5. **Checks**: what was verified (final queue query, file hashes, PDF checks) and
   what could not be verified.
6. **Statement of limits**: no application submitted, no employer contacted, no
   Applied recorded, unless the owner explicitly did or reported that.

Use counts from server reads at the end of the run, not from the plan.

## Resume note

Keep a small note in the operator workspace's ignored local space when work may span
sessions: date, request, cohort IDs, completed IDs and the next step. It must be
optional: a new run recovers progress from server state and uses the note only
to restore scope. Do not store secrets, tokens or full documents in it.
