# Application documents and tracking

An application holds its notes, form questions, answers, prepared contexts,
document revisions and progress. A job can have one open application at a time
and retain earlier closed attempts.

## Prepare the library

In **Career**, store your profile, stable [career entries](career.md) and approved
claims. In **Policy**, state your [rules and facts](policy.md) once. In
**Templates**, add one or more CV or letter templates with their source, assets
and rules: typed limits (pages, bullets per entry, bullet length), a list of
rule statements and guidance. Set a default for each kind of document.
**General instructions** apply across templates; template guidance adds specific rules.

![Templates with the list by kind and the Rules tab: guidance, limits, rule statements and other settings](../images/templates.png)

The synthetic templates in `examples/` provide starting points.

A template can define a one-page engineering CV, a longer research CV or another
layout. Your external agent fills it using the selected facts and instructions.

## Start an application

Review new jobs in **Jobs**, which opens on the **Inbox** queue. Choose **Shortlist** to save an opportunity for
later, or **Dismiss** to reject it reversibly. Inbox and Shortlist contain only
jobs without application attempts. Shortlist is your ready-to-prepare queue.

![Shortlist of selected jobs awaiting application preparation](../images/shortlist.png)

From Shortlist, open a job and choose **Start application**. This creates an
application in **Preparing** (`draft` in REST/MCP) and removes the job from
Shortlist automatically. Add its questions or notes and prepare documents in
**Applications**. Saving a job creates no application; collecting jobs does not
start preparation.

The job shows its application stage and opens the existing attempt when one is
already underway. After closing an attempt, you can deliberately start another.
Keep the application in **Preparing** while preparing files. Prepare a context with
the selected templates and relevant career entries or claims.

The context freezes the posting, profile, approved claims, instructions, questions,
templates and exact asset bytes. Later edits affect newly prepared contexts;
existing documents retain the material used to write them.

In the application, **Documents** comes first. Expand **Prepare with your agent**
to prepare or download a frozen context. The chooser supports search and selecting
or clearing matching entries, claims and templates. Claims follow their owning
entries: excluding an entry also excludes its claims. Omitted entry/claim selections
use all eligible material; an explicitly empty selection includes none. An empty
template selection uses your defaults.

## Write, compile and upload

Connect an [external agent through MCP](agents.md), or work manually. Ask it to
read the prepared context, write the CV, cover letter and answers, compile LaTeX
on its computer, and upload PDF and source files to the appropriate document
revision. It uses its own model access and tools.

For manual work, create the document in the application and upload its files.
Keep each PDF with the source revision that produced it. Form answers have both
an archived document revision and live application answers; update the live answers
when you want to reuse them in the application form.

![Application workspace with document revisions](../images/documents.png)

## Review and submit

Open the uploaded PDF and check wording, dates, layout and page count. Approve the
reviewed revision when ready. An expanded revision with a `.tex` source shows
whether its saved content appears in that source. When they differ, the
differing values are listed and approval becomes **Approve with differences**,
for intentional cases only; otherwise save a corrected revision or upload the
matching source. For changed content, create a new revision and upload
its new files. Approved revisions keep their content and attachments fixed.

Cards and the document list distinguish **Needs PDF**, **PDF to review** and
**Approved PDF** using current revisions and their own attachments. Form-answer
and other content-only revisions can show **Content saved** without requiring a PDF.
These labels
describe stored files and review, not submission or an automatic quality check.
**Built on older inputs** marks an application whose current revisions use a
context frozen before a later change to the Profile, general guidance, a selected
template, Career entry or claim. The application's Documents tab lists what
changed. Frozen contexts never change; to refresh, prepare a new context and save
new revisions.
Click a filename to preview a supported PDF, image or text file; use **Details**
for its hash and metadata. Unsupported formats remain downloadable.

Editing a form question keeps compatible live answers. If a changed type, option
or limit makes an answer invalid, the editor shows the saved answer and requires
an explicit choice before clearing it. Frozen contexts and document revisions stay
unchanged.

## Mark ready and submit

**Ready** is a stored step inside Preparing: someone, you or your agent, judged
the application complete. In the application, **Mark ready** is available once
every current revision has its PDF and is approved and no blocking requirement is
unresolved; otherwise the panel names what is missing. The application shows who
marked it and when, and **Not ready** removes the mark.

![Application marked ready by the agent, with who marked it and when](../images/application-ready.png)

The mark describes exactly what was judged, so Openings clears it when that
changes: a new document revision or context, a deleted revision, a file added to
a current revision, a blocking requirement added or reopened, or the application
leaving Preparing. The History tab records each clearing with its reason and who
caused it. Mark the application ready again after reviewing the change.

**Ready to apply** above the list is your queue: it shows how many Preparing
applications are marked ready and lists them longest-waiting first. Submit
through the employer's portal, then record **Applied**. Marking ready, preparing
documents or uploading a PDF never submits anything and leaves the application
in its current stage.

## Follow progress

Use the list or Kanban view to move between **Preparing**, **Applied**, **Interview**,
**Offer** and **Closed**. Closing an attempt records **Accepted**, **Not selected**
or **Not pursued**; choose an outcome explicitly. Events retain the recorded
journey, including an interview before a later rejection. The overview funnel
follows those recorded stages. The submission date can be corrected or cleared.

On narrow screens the initial application view is a compact list. Choose **Board**
or **List** to remember a preference. Stage shortcuts filter the whole result set;
board columns show when only part of a stage is loaded and link to the full stage.

## Plan and track requirements

Each application can have a **priority** (P1 highest to P5 lowest) and the
employer's **deadline**, set under **Details**. Cards and list rows show them;
a past deadline on an application still in Preparing is marked overdue. Sort
Applications by **Deadline**, **Priority** or **Ready**, and filter by **readiness**:

| Readiness | REST/MCP value | Meaning |
|---|---|---|
| No documents | `none` | No document revision yet. |
| Missing PDF | `missing_pdf` | A current CV or cover letter revision has no PDF. |
| Needs review | `unreviewed` | Every current revision has its files but one is not approved. |
| Blocked by a requirement | `blocked` | An employer requirement is blocking and unresolved. |
| Reviewed, not marked ready | `reviewed` | Every check passes, but nobody marked the application ready. |
| Ready to apply | `ready` | Marked ready, and every check still passes. |

Readiness uses only the current revision of each document; an approved earlier
revision does not count. It does not check the content or submit anything.
Before version 0.17 `ready` meant that the checks passed; that state is now
`reviewed`, and `ready` is the stored step.

![Applications list sorted by deadline, with priority and deadline tags, readiness, a blocking requirement and the bulk action bar](../images/applications-planning.png)

**Requirements** records employer conditions: authorship rules (such as no
AI-written applications), attachments, references, format, language, eligibility
and dates. Mark a requirement **Blocking** when documents must not be prepared or
submitted until it is settled, and **Resolved** with a note once you decide.
Unresolved blocking requirements appear at the top of the application. They are
stored on the application, not in job details, so source refreshes of the job
continue.

![Application Requirements tab with a blocking authorship requirement and a resolved eligibility requirement](../images/requirements.png)

Open **Posting** in an application to read the job without leaving your current
filters. Rare job maintenance actions live under **Job details, sources & maintenance**.

![Application board showing compact cards across stages](../images/applications.png)

## Keep, dismiss or delete

| Action | Result |
|---|---|
| Shortlist | Keep an interesting job without starting an application. |
| Return to inbox | Reconsider a shortlisted job before starting preparation. |
| Close application | Record its outcome and retain documents and history. |
| Dismiss job | Hide it from active review and remember it during later collection. |
| Delete application | Remove that attempt and its documents/files; keep the job. |
| Forget job | Permanently remove the job, identities and owned application history/files. Future collection can find it again. |

Closing an application keeps it in Applications, including its history and
files. The **History** tab lists each recorded change with who made it: you in
the dashboard, a named API token or the system. Entries from before version
0.17 show "unknown (before 0.17)".

![Application history with a question asked by the agent and answered by the owner](../images/application-history.png)

Closing never returns the job to Inbox or Shortlist. To cancel preparation
without losing documents, close it as **Not pursued**. Deleting the final attempt
is permanent and deliberately returns a saved job to Shortlist; the confirmation
explains this. Other retained attempts keep it out of pending queues.

In the Applications **List** view, select attempts across pages to close them
with one outcome, reopen Closed attempts to a stage, mark them ready, or delete
them. Each attempt is checked separately; a failure, such as another open attempt
for the same job or a missing PDF, is listed without blocking the others.

The **Possible duplicates** tab beside Inbox groups records that probably
describe one vacancy, for example the same posting collected from several job
boards and the employer's site. Each group shows a confidence and the reasons
behind it: the same apply link or requisition ID, identical or nearly identical
text, the same company, role and location, and anything that speaks against it,
such as a different location, requisition, level or a posting published months
apart. Company names are compared without legal, corporate and country suffixes.

Choose **High confidence** to see only strong matches, **Medium and high** (the
default) to add probable ones, or **Every candidate** to include records that
share only a company and role; most of those are different vacancies. The tab
suggests a record to keep and never merges automatically. Open a job and expand
**Job details, sources & maintenance** to see its likely duplicates and merge a
verified copy.

![Possible duplicates at high confidence: one vacancy collected from three sources and another from two, with the reasons for each group](../images/duplicates.png)

Dismissing a job preserves its applications. Restore it before preparing new
documents. If you previously dismissed an applied job just to clear Shortlist,
find it under Dismissed and choose **Restore job**. REST/MCP can set `triage=saved`
with its current version. Do this only for known workaround dismissals; the job
remains in Applications and does not return to Inbox. A later attempt is always
explicit and respects the one-open-application rule.

Scripts and agents can perform the same workflow using the [REST API](api.md)
or [MCP tools](agents.md).
