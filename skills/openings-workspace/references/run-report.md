# Run report, questions for the owner and resume note

Every workflow that changes Openings works inside a run. The run, its report
and the questions asked are stored in Openings, so the owner reads them in the
dashboard under **Activity** and the next run reads them over MCP or REST.
Server records stay authoritative; the report explains what this run did.

## Open the run

1. Read the answers given since the previous run:
   `questions_list({"value": {"answered_since": "<start of the previous run>"}})`.
   `runs_list` gives that start time. Act on the answers first. Record an answer
   that is a lasting fact in the Profile or the Career record, so the same
   question is never asked twice.
2. Call `runs_start` with the workflow name and the scope: the owner's request,
   the cohort snapshot (count and how it was selected) and anything deliberately
   left out. Use an idempotency key for retries.
3. A token has one open run. `run_open` names a run that was never closed: read
   it with `runs_get` to see what it changed, continue that work, then start
   with `supersede: true`. The earlier run is kept and marked interrupted.

While the run is open, every write made with the same token is attached to it.
No other tool takes a run argument. Parallel workers share the run or use their
own tokens. `runs_update` stores a short progress note; use it before a long
step so an interrupted run shows where it stopped. A run asked only to inspect
or report needs no run record.

## Ask questions as records

Ask with `questions_ask`, not only in chat: the question, why the answer
matters, the subject (`job`, `application`, `knowledge` for a Career entry, or
none) and, when the answer is a choice, the choices. Ask only for facts or
decisions that block or materially improve a result. Leave the affected record
unchanged and continue the rest of the work. Withdraw a question that no longer
needs an answer with `questions_withdraw`. The answer belongs to the owner, who
gives it in the dashboard. An agent token cannot call `questions_answer`
(`forbidden`): when the owner answers in conversation, act on the answer, record
a lasting fact in the Profile or the Career record, and ask the owner to confirm
the question in **Activity** or withdraw it with a note of where the fact went.
With an owner token, record an answer only when the owner gave it to you directly.

## Close the run

Call `runs_finish` with the run's current `expected_version` and the report:

1. **summary**: what the run achieved, in two or three sentences.
2. **changes**: your account of the changes with record IDs, for example saved,
   dismissed, Drafts created or completed, revisions approved, sources changed.
   Openings adds the counts by kind from the recorded changes; do not count by
   hand.
3. **not_done**: each remaining record as `item` and precise `reason`
   (unresolved fact, employer requirement, failed check, conflict, missing
   capability), with `subject_type` and `subject_id` when it is a job, an
   application or a Career entry.
4. **checks**: what was verified (final queue query, file hashes, PDF checks),
   and with `verified: false` what could not be verified.
5. **limits**: no application submitted, no employer contacted, no Applied
   recorded, unless the owner explicitly did or reported that.
6. **method**: what the workflow or the product lacked during this run.

Use server reads at the end of the run, not the plan. Read the stored run back
with `runs_get` and give the owner its summary and the open questions in chat as
well.

## Resume note

Keep a small note in the operator workspace's ignored local space when work may span
sessions: date, request, run ID, cohort IDs, completed IDs and the next step. It
must be optional: a new run recovers progress from server state, the earlier
run's recorded changes and its progress note. Do not store secrets, tokens or
full documents in it.
