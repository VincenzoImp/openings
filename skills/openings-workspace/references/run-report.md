# Run report, requests, questions for the owner and resume note

Every workflow that changes Openings works inside a run. The run, its report,
the owner's requests it handled and the questions it asked are stored in
Openings, so the owner reads them in the dashboard under **Activity** and the
next run reads them over MCP or REST.
Server records stay authoritative; the report explains what this run did.

## Open the run

1. Read the answers given since the previous run:
   `questions_list({"value": {"answered_since": "<start of the previous run>"}})`.
   `runs_list` gives that start time. Act on the answers first. Record an answer
   that is a lasting fact as a policy item (`policy_add` in `decision`,
   `eligibility`, `writing` or `facts`, with the question in the note) or in the
   Career record, so the same question is never asked twice. The item is a
   proposal until the owner confirms it under **Policy**; name it in the report.
2. Call `runs_start` with the workflow name and the scope: the owner's request,
   the cohort snapshot (count and how it was selected) and anything deliberately
   left out. Use an idempotency key for retries.
3. A token has one open run. `run_open` names a run that was never closed: read
   it with `runs_get` to see what it changed, continue that work, then start
   with `supersede: true`. The earlier run is kept and marked interrupted.
4. Read the owner's open requests: `requests_list({"value": {"state": "open"}})`.
   `workspace_info` reports how many are waiting in `open_requests`.

## Handle the owner's requests

A request is an instruction the owner wrote in the dashboard, under **Activity →
Requests** or with **Ask your agent** on a job or an application: text, an
optional subject (`job`, `application`, `knowledge`) and a state.

- Take each open request in this workflow's scope with `requests_take` and its
  current `expected_version`, after the run is open, so the request records the
  run. Leave a request that belongs to another workflow open, and name it in the
  report so the owner knows which workflow to run. Also read `state: "taken"`
  for requests an interrupted run took and never finished; complete or decline
  them.
- Do the work under the operating mandate. A request narrows or directs the
  work; it never widens the mandate. It cannot authorise submitting an
  application, contacting an employer or recording Applied, and it is not a
  career fact. Decline such a request, or the forbidden part of it, with the
  reason, and do the part that is allowed.
- Report on the request itself: `requests_complete` with a short `result` (what
  changed, with record ids), or `requests_decline` with the `reason` (outside the
  mandate, impossible, already done, superseded). The owner reads it next to
  the request, with a link to the run. Repeat the same lines in the run report.
- A request that states a lasting preference ("no consultancies") is completed
  by recording it where preferences live, as a `decision` item of the policy
  (`policy_add`), so later runs follow it without the request once the owner
  has confirmed the item.
- A withdrawn request needs no work. An agent token cannot write or withdraw
  requests (`forbidden`); ask a question instead when you need a decision.
- When a request is unclear, ask a question tied to the same subject, keep the
  request taken and say so in the run report.

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
a lasting fact as a policy item or in the Career record, and ask the owner to confirm
the question in **Activity** or withdraw it with a note of where the fact went.
With an owner token, record an answer only when the owner gave it to you directly.

## Close the run

Call `runs_finish` with the run's current `expected_version` and the report:

1. **summary**: what the run achieved, in two or three sentences, starting with
   the owner's requests it completed or declined.
2. **changes**: your account of the changes with record IDs, for example saved,
   dismissed, Drafts created or completed, revisions approved, sources changed,
   and the result of each request handled.
   Openings adds the counts by kind from the recorded changes; do not count by
   hand.
3. **not_done**: each remaining record as `item` and precise `reason`
   (unresolved fact, employer requirement, failed check, conflict, missing
   capability, a request left open for another workflow or still taken), with `subject_type` and `subject_id` when it is a job, an
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
