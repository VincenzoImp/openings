---
name: prepare-shortlist
description: Prepare the job-specific CV and letter of Openings Shortlisted applications, using current evidence and template rules, with resumable document and PDF checks until each is Ready and the owner applies manually.
compatibility: Requires access to the Openings MCP server or REST API, as described in the openings-workspace skill.
---

# Prepare Shortlist

Use this workflow to prepare CVs and letters for every Shortlisted application, as routine
work under the [operating mandate](../openings-workspace/references/operating-mandate.md), or to resume that preparation.
An audit of what is Ready is read-only. Preparation completes the required
documents of Shortlisted applications until each is Ready; it never submits
online, sends employer messages or marks Applied.
The owner submits each Ready application manually and then marks it Applied or closes it.

Read [Openings workspace](../openings-workspace/SKILL.md) for transport, exact
schemas, contexts, document revisions and transfers. Use
[Career claims](../career-claims/SKILL.md) for writing. Personal preferences and
all document-selection rules come from current Openings records: the owner's
Preferences (`preferences_get`), the typed claim fields and the templates.

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

Shortlisting a job starts its application in stage Shortlisted, so the cohort is
the Shortlisted applications that are not Ready (`applications_list` with
`stage: "shortlisted"`, or `needs: "documents"` for the ones missing a required
document; each row's `missing` names what is left). Snapshot the requested IDs
before writing. An optional local log can record cohort IDs and pending steps,
but must not be required to resume. Inspect their contexts, revision leaves and
files to recover progress from the database. Keep a Ready application whose
documents pass the checks unchanged; do not generate another application or
documents just to rerun.

For each job, read the full posting, the current Profile, the Preferences
(`looking_for` and `ruled_out` for fit, `facts` for what the employer asks,
`writing` for the documents, `working_with_me` for how to work), Career
evidence and both selected templates with their guidance. Check its
application attempts and read the job's timeline (`timeline_get` with `job_id`):
the pinned notes first, which are the owner's standing guidance for the job and
for each application; `applications_get` returns the application's pinned
note as `pinned_note`. Follow the `writing` rules whose scope is `all` or matches the document (`cv`, `letter`).
Resume the intended open Shortlisted application or the attempt returned by a
concurrent-creation conflict. Use an idempotency key for retryable creation. Do
not reset other stages or start another attempt after Closed without the
requested authority.

If the task log is unavailable, recover only applications whose ownership and
requested scope can be established from server data; report an ambiguous case
rather than create a duplicate or alter an unrelated one.

## Duplicate preflight

Before any application creation, use the shared
[vacancy identity check](../openings-workspace/references/job-deduplication.md).
Compare the requested cohort with existing job records and application attempts,
including ones outside the cohort. Resolve only verified duplicates within scope.
Reuse the canonical record and its application; a different job ID is not permission to
prepare or apply for the same vacancy again. Leave ambiguous groups unresolved
and report them while independent jobs continue.

## Order and employer requirements

Work through the cohort in a deliberate order: live deadlines first, then the
strongest fit with What I'm looking for, then the rest. A large cohort is prepared
in that order so a partial run still leaves the most valuable applications Ready.
`applications_list` with `sort: "deadline"` or `sort: "priority"` gives that
order, and `needs: "documents"` finds the ones that still need a document.
Record a
known closing date as the application `deadline` and the agreed order as
`priority` (1 highest to 5); never invent either. When the employer asks for
only a CV (or only a letter), set the application's `required_documents` with
`applications_update`; it defaults to both.

Before writing documents for a job, run the
[employer requirements preflight](../openings-workspace/references/employer-requirements.md).
A blocking requirement, such as a ban on AI-written applications or a mandatory
item that Career evidence cannot supply, stops document work for that job; record
it as a blocking entry in the application `requirements` and report it. Expired postings are reported, not prepared.

## Read and compose

Use Career claims' strongest-supported-account method to connect the relevant
experience and linked Projects to the role's needs before writing. Check
existing evidence before asking for facts; ask targeted questions when they can
materially improve the application. Carry newly confirmed facts into the
records through authorized Career maintenance or Preferences.

Read the live records the documents use: `applications_get` (with its
`pinned_note`), `jobs_get`, `profile_get`, `preferences_get`, the Career entries
and claims (`knowledge_list`, `claims_list`) and the CV/CL templates
(`templates_get`) with their guidance and assets. Note the `claim_ids` and
`knowledge_ids` the documents use; `documents_create` cites them.

Start the CV from MASTER. Keep an effective unchanged CV when appropriate.
Apply only the fixed-section, Skills and role-wording permissions in the
Writing rules and template guidance. New wording from allowed evidence stays in
this application's copy and uses its evidence links; it does not create an official bank claim.

Write a letter for the actual role and company, with supported reasons and
relevant examples. Present the strongest truthful case and never volunteer gaps
(see [Career claims](../career-claims/SKILL.md)); record gaps for the owner in
a note on the application instead (`notes_create` with `application_id`, not
pinned: the pinned note is the owner's standing guidance). Check the CV and letter together for consistent positioning,
attribution and personal details. Resolve every placeholder. Do not use the
general letter MASTER unchanged as if it addressed a specific employer.

## Render, check and attach

Compile changed sources with a compatible available tool. Reuse an existing
unchanged PDF only after checking its content, source references and compatibility.
Inspect full PDFs and extracted text, fixed content, required terms, line/page
geometry, links, factual scope and employer requirements. Use the template's
checker where supplied; it does not replace factual or visual review.

Find the intended current document leaf for each kind. When resuming, compare
it with the current records: refresh a leaf with a new revision when a later
change to the Profile, Preferences, a template or cited evidence matters. Reuse matching work;
complete missing steps on a compatible incomplete revision. Save changed output
as the appropriate new revision. A complete parent does not supply files to a
new child. Resolve concurrent branches explicitly.

A CV or letter revision is a PDF and, when you compiled it, the `.tex` source it
was built from, with the claim and Career entry ids it uses (`claim_ids`,
`knowledge_ids`) and an optional `note` on what changed. It has no `content`.
Because a revision becomes complete and immutable as soon as its PDF is stored,
and Ready counts complete revisions, finish the content, layout and PDF checks
before you create it. Then call `documents_create` with `pdf` (name, size,
SHA-256) and the source inline (`source`) or as `source_file`, and PUT the bytes
to the returned `uploads` grants, the source first. With a source, the PDF names
its SHA-256 (`source_sha256`) and Openings refuses a PDF that names another
source (`source_mismatch`), so upload the exact source you compiled. Read the
revision's `text` (from the source, or extracted from the PDF when there is
none) to check what the owner will read; `documents_compare` shows what changed
since the previous revision. When you change anything, save a new revision with
its own files. Verify upload sizes and hashes; a successful transfer is not a
PDF-quality check.

## Ready and handoff

Ready is computed, not marked: an application is Ready when it is Shortlisted,
every document in its `required_documents` has a current complete revision and
no blocking requirement is unresolved. Re-read the application: `ready` and
`missing` (for example `["letter"]` or `["requirement:<id>"]`) say what is
left; fix that step. The server checks files and blocking requirements only:
your content and layout checks come first. The application stays Shortlisted
until the owner marks it applied. The owner finds it under **Ready to apply**
on Today and opens its review page (`#review?application=APPLICATION_ID` in the
dashboard): the posting, CV and letter side by side, the requirements still
open and the form questions without an answer. From there the owner downloads
the PDFs, submits on the company site and chooses **Mark applied**. Point the
owner to that page when you report a Ready application. A new incomplete
revision or a new blocking requirement makes it not Ready again until the work
is finished. Do not finish a document while a question about it is open.

If a tool, source, upload or check fails, keep the actual revision incomplete.
Record the precise failed step and continue independent jobs where possible.
Do not delete the application, dismiss the job or create another attempt to hide
an error. On rerun, inspect server state and resume that step.

Report each application with its ID, CV/CL revision IDs, verified files and any
remaining problem. Separate Ready applications from incomplete ones and from those
blocked by employer requirements. Use the shared
[run report](../openings-workspace/references/run-report.md); state explicitly
that no application was submitted or marked Applied by this workflow.
