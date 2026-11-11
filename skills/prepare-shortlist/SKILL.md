---
name: prepare-shortlist
description: Prepare job-specific CV and cover-letter drafts for Openings Shortlist jobs, using current evidence and frozen template rules, with resumable document and PDF checks before the owner applies manually.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Prepare Shortlist

Use this workflow to prepare CVs and letters for every Shortlist job, as routine
work under the [operating mandate](../openings-workspace/references/operating-mandate.md), or to resume that preparation.
A readiness audit is read-only. Preparation creates or completes Draft
applications and marks each complete one ready; it never submits online, sends
employer messages or marks Applied.
The owner submits each ready Draft manually and then marks it Applied or closes it.

Read [Openings workspace](../openings-workspace/SKILL.md) for transport, exact
schemas, contexts, document revisions, transfers and review. Use
[Career claims](../career-claims/SKILL.md) for writing. Personal preferences and
all document-selection rules come from current Openings records and templates.

## Run and questions

Open a run before the first write: `runs_start` with `workflow: "prepare-shortlist"` and the scope; writes made
with this token then attach to the run. First read the owner's answers given
since the previous run (`questions_list` with `answered_since`) and act on them.
Then read the owner's open requests (`requests_list` with `state: "open"`): take
the ones in this workflow's scope (`requests_take`), do the work, and report on
each with `requests_complete` and a short result, or `requests_decline` and the
reason. Leave requests for other workflows open. A request never authorises
submitting an application, contacting an employer or recording Applied.
Ask each new question as a record tied to its job, application or Career entry
(`questions_ask`), not only in chat. Close the run with `runs_finish` and the
stored [run report](../openings-workspace/references/run-report.md).

## Scope and checkpoint

Snapshot the requested actionable Shortlist IDs before creating applications.
A created application leaves that queue, even while incomplete. An optional local log can record cohort IDs and pending steps, but must not be
required to resume. On each run, read server applications with Draft status as
well as the actionable Shortlist. Inspect their contexts, revision leaves and
files to recover progress from the database. Keep an already complete compatible
Draft unchanged; do not generate another application or documents just to rerun.

For each job, read the full posting, current Profile/preferences, Career evidence,
general guidance and both selected templates. Check its application attempts.
Resume the intended open Draft or the attempt returned by a concurrent-creation
conflict. Use an idempotency key for retryable creation. Do not reset other stages
or start another attempt after Closed without the requested authority.

A resumed run includes its incomplete cohort applications even though they are
no longer in actionable Shortlist. If the task log is unavailable, recover only
Drafts whose ownership and requested scope can be established from server data;
report an ambiguous case rather than create a duplicate or alter an unrelated one.

## Duplicate preflight

Before any application creation, use the shared
[vacancy identity check](../openings-workspace/references/job-deduplication.md).
Compare the requested cohort with existing job records and application attempts,
including ones outside Shortlist. Resolve only verified duplicates within scope.
Reuse the canonical record and its Draft; a different job ID is not permission to
prepare or apply for the same vacancy again. Leave ambiguous groups unresolved
and report them while independent jobs continue.

## Order and employer requirements

Work through the cohort in a deliberate order: live deadlines first, then the
strongest fit with the Profile policy, then the rest. A large cohort is prepared
in that order so a partial run still leaves the most valuable Drafts complete.
For existing Drafts, `applications_list` with `sort: "deadline"` or
`sort: "priority"` gives that order, and `readiness` (`none`, `missing_pdf`,
`unreviewed`, `blocked`, `reviewed`, `ready`) finds the ones that still need work:
`reviewed` passes every check but is not yet marked ready. Record a
known closing date as the application `deadline` and the agreed order as
`priority` (1 highest to 5); never invent either.

Before freezing inputs for a job, run the
[employer requirements preflight](../openings-workspace/references/employer-requirements.md).
A blocking requirement, such as a ban on AI-written applications or a mandatory
item that Career evidence cannot supply, stops document work for that job; record
it as a blocking entry in the application `requirements` and report it. Expired postings are reported, not prepared.

## Freeze and compose

Use Career claims' strongest-supported-account method to connect the relevant
experience and linked Projects to the role's needs before freezing inputs. Check
existing evidence before asking for facts; ask targeted questions when they can
materially improve the application. Carry newly confirmed facts into the frozen
inputs through the supported context mechanism and authorized Career maintenance.

Prepare a context with explicit CV/CL template IDs and the evidence/claims the
documents need. Use a consistent key for retries of the same request. Read the
returned frozen instructions, content and assets. Compare relevant inputs before
reusing a context; prepare a deliberate new context if different inputs are needed.

Start the CV from MASTER. Keep an effective unchanged CV when appropriate.
Apply only the fixed-section, Skills and role-wording permissions in the frozen
rules. New wording from allowed evidence stays in this application's copy and
uses its evidence links; it does not create an official bank claim.

Write a letter for the actual role and company, with supported reasons and
relevant examples. Present the strongest truthful case and never volunteer gaps
(see [Career claims](../career-claims/SKILL.md)); record gaps for the owner in
the application note instead. Check the CV and letter together for consistent positioning,
attribution and personal details. Resolve every placeholder. Do not use the
general letter MASTER unchanged as if it addressed a specific employer.

## Render, attach and review

Compile changed sources with a compatible available tool. Reuse an existing
unchanged PDF only after checking its content, source references and compatibility.
Inspect full PDFs and extracted text, fixed content, required terms, line/page
geometry, links, factual scope and employer requirements. Use the template's
checker where supplied; it does not replace factual or visual review.

Find the intended current document leaf for each kind. When resuming, check
`application_staleness`: a leaf built on older inputs is refreshed with a new
context and new revisions when the change matters. Reuse matching work;
complete missing steps on a compatible incomplete revision. Save changed output
as the appropriate new revision. An approved parent does not supply files or
approval to a new child. Resolve concurrent branches explicitly.

Keep the revision's structured `content` identical in wording to the uploaded
`.tex` source and its PDF: when you edit the source after saving content, save the
edited text as a new revision instead of uploading a diverging file. Run
`documents_consistency` before review; `documents_review` refuses a mismatch.
Upload exact source/PDF files and verify size and hashes. Download and validate
the actual PDFs; a successful transfer is not a PDF-quality check. Read the
post-upload document version, then mark document review approved only after the
agent checks pass. Do not attribute this review to a human.

## Readiness and handoff

Re-read the intended CV and CL leaves and their files. Both must match the chosen
context and content, report `consistent` from `documents_consistency`, have valid checked PDFs and exact sources, and have approved
review states. Only then mark the Draft ready: `application_ready` with the
application's current `expected_version`. Openings refuses with
`application_not_ready` and names the failed check (`blocked`, `none`,
`missing_pdf`, `unreviewed`) when the stored records disagree; fix that step
instead of retrying. The server checks files, review states and blocking
requirements only: your content, layout and consistency checks come first.
Ready is a stored step, not a stage. The application stays Draft; job interest
stays saved. The owner finds it under **Ready to apply**, submits on the company
site and records Applied. Openings clears the mark when a revision, context, file
or blocking requirement changes afterwards; after such rework, repeat the checks
and mark it ready again. Do not mark a Draft ready while a question about it is
open or its inputs are stale in a way that matters.

If a tool, source, upload or check fails, keep the actual Draft incomplete.
Record the precise failed step and continue independent jobs where possible.
Do not delete the application, dismiss the job or create another attempt to hide
an error. On rerun, inspect server state and resume that step.

Report each application with its ID, CV/CL revision IDs, verified files and any
remaining problem. Separate ready Drafts from incomplete ones and from those
blocked by employer requirements. Use the shared
[run report](../openings-workspace/references/run-report.md); state explicitly
that no application was submitted or marked Applied by this workflow.
