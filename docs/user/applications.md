# Applications

An application holds its notes, form questions, answers, prepared contexts,
document revisions, progress and the employer's answers. A job can have one open
application at a time and retain earlier closed attempts.

## Prepare the library

In **Career**, store your profile, stable [career entries](career.md) and approved
claims. In **Preferences**, state [what you want and your writing rules](preferences.md)
once. In **Templates**, add one or more CV or letter templates with their
source, assets, guidance and typed limits (pages, bullets per entry, bullet
length). Set a default for each kind of document. Writing rules live in
Preferences, for all documents, the CV or the letter.

![Templates with the list by kind and the Rules tab](../images/templates.png)

The synthetic templates in `examples/` provide starting points.

A template can define a one-page engineering CV, a longer research CV or another
layout. Your external agent fills it using the selected facts and your writing rules.

## Start an application

Review new jobs in **Jobs**, which opens on the **To review** tab. Select a job
to read it beside the list, then choose **Shortlist** to save it for later, or
**Dismiss…** to reject it reversibly with an optional reason. To review and
Shortlist contain only jobs without application attempts. Shortlist is your
ready-to-prepare queue.

![Shortlist of selected jobs awaiting application preparation](../images/shortlist.png)

From Shortlist, select a job and choose **Start application**. This creates an
application in **Preparing** (`draft` in REST/MCP), removes the job from
Shortlist and opens the application's page. Saving a job creates no application;
collecting jobs does not start preparation. The job shows its application stage
and opens the existing attempt when one is already underway. After closing an
attempt, you can deliberately start another.

## The pipeline

**Applications** has two tabs, **Pipeline** and **Stats**. The pipeline counts
every stage with a chip: **Preparing**, **Ready** (a stage of its own: Preparing
counts only the applications not marked ready), **Applied**, **Interview**,
**Offer** and **Closed**. Search by role or company, filter by readiness or
outcome, and sort by deadline, priority, the time an application has been ready,
the time it was sent or the last change.

![Applications: stage chips with their counts, filters, and the list with plan tags, documents, the employer's answer and the next action](../images/applications.png)

Each row shows the role and company, the stage, the plan (priority, deadline and
a blocking requirement for an application being prepared; the day it was sent
otherwise), the state of the CV and letter, what the employer answered (or how
long the wait is, highlighted once it is longer than the no-reply period) and
the next action: **Review** a ready application, **Decide** on a blocking
requirement, **Answer** your agent's question, or **Record response** for one
that was sent.

Select rows (or every row shown) to act on them together: **Close as no reply**,
**Close…** with an outcome, **Reopen…** to a stage, **Mark ready**, **Not ready**
or **Delete…**. Each application is changed on its own; one that cannot be, such
as a Draft closed as no reply or a second open attempt for one job, is named
without stopping the others.

![Preparing applications sorted by deadline with two selected and the actions on them](../images/applications-planning.png)

## Review and apply

An application opens on its own page, from Today's **Review**, a row of the
list or any link to it. The posting, the current CV and the current letter stand
side by side with their PDFs; on a phone a switch shows one at a time and the
main actions stay in a bar at the bottom. A switch above the CV or the letter
shows, instead of its PDF, the text read from its source.

![The review page: tags, its place in the Ready queue, the posting, the CV and the letter with their PDFs, and Mark applied](../images/review.png)

Above them, the page says where the application stands: its stage, deadline and
priority, and for a ready one its place in the Ready queue in Today's order
(closest deadline first) with a link to the next one. **Before you send** names
the requirements that are not resolved and the required form questions without
an answer. The actions end the task:

- **Download CV and letter** saves both PDFs; **Open the posting** opens the
  employer's page.
- **Mark applied** records that you sent it: the application moves to Applied
  with the time, and its Ready history stays in the timeline. If the application
  is no longer ready (another session changed a document, for example), it is
  refused and says why; review it again.
  Once it is marked, the next Ready application opens, in Today's order, and
  the confirmation offers **Undo** for six seconds: it returns the application
  to Ready, without a sent day. After the last Ready application the page says
  **All sent** and links back to Today.
- **Not pursuing** closes it as Not pursued; its documents and history stay.

Below, six tabs hold the rest:

| Tab | What it holds |
|---|---|
| **Answers** | One control per form question, with the live answers; **Copy all**; add, edit and remove questions. |
| **Requirements** | The employer's conditions, each blocking or not and resolved or not, with your note. |
| **Timeline** | The employer's responses, then one list of the notes and changes of the application and of its job, the pinned notes first, with filters. |
| **Inputs** | The frozen copies of your record the documents were written from, their files, and what changed since. |
| **Documents** | Every document revision: open, approve, revise, add files, delete. |
| **Details** | Stage and outcome, priority, deadline, the time sent, the Ready step, the pinned note, requests for your agent, the job and deletion. |

## Write, compile and upload

Under **Inputs**, **Prepare a frozen copy** freezes the posting, profile, Preferences,
approved claims, questions, templates with their guidance and exact asset bytes for
your agent, and downloads it. The chooser supports search and selecting or
clearing matching entries, claims and templates. Claims follow their owning
entries: excluding an entry also excludes its claims. Omitted entry/claim
selections use all eligible material; an explicitly empty selection includes
none. An empty template selection uses your defaults. Later edits affect newly
prepared copies; existing documents keep the material used to write them.

Connect an [external agent through MCP](agents.md), or work manually. Ask it to
read the prepared context, write the CV, cover letter and answers, compile LaTeX
on its computer, and upload the source and the PDF built from it to the
appropriate document revision. It uses its own model access and tools.

A CV or letter revision is its `.tex` source and the PDF built from it, with an
optional note and the claims and Career entries it uses. Openings reads the text
from the source, without running TeX: that text is what you review, search and
compare between revisions; the PDF shows the layout. The PDF upload names the
source it was built from, and a PDF built from another source is refused. Form
answers keep their fields.

For manual work, choose **Add a document** under **Documents**: for a CV or a
letter, its title, the frozen copy it was written from, its `.tex` source and
its PDF; for form answers or another document, its text. Form answers have both
an archived document revision and live application answers; update the live
answers under **Answers** when you want to reuse them in the application form.

![The Documents tab with a revision open: the text read from its source, its source and PDF, the changes since the previous revision and its actions](../images/documents.png)

Open the PDF and check wording, dates, layout and page count. Approve the
reviewed revision when ready; a CV or letter needs its source and its PDF first.
**Compare with revision 1** (for the revision before the open one) lists the
lines removed and added since then, with the unchanged lines around them. For a
changed CV or letter, choose **New revision** and upload its new source and PDF.
Approved revisions keep their files fixed. A CV or letter saved before 0.22
also shows the content stored with it then, read-only. Click a file name to
preview a supported PDF, image or text file with its size and hash.

The list shows the state of the CV and letter from the current revisions:
**None**, **Written, without PDF**, **Written, not approved**, **CV approved,
letter not yet** or **CV and letter approved**. **Inputs changed** marks an
application whose current revisions use a frozen copy made before a later change
to something the documents use, and the line below names the first change, for
example "Profile summary and 2 more". The tab **Inputs** lists every change with
what happened to it: "Profile summary — changed", "“Available from February
2027.” — added · Facts about me". A writing rule for the CV only marks the CV
("CV only").

Only what documents use counts: the Profile's name, headline, contact details,
links and summary; the statements of Facts about me and Writing rules in
Preferences; the source, guidance and rules of the selected templates; the
text, dates and skills of the selected Career entries and the wording of their
claims. Editing Profile metadata, the other Preferences sections (what you are
looking for or rule out, working with me), the order of statements, a
template's name, the order of entries or claims, a claim's selection fields or
any free-form metadata leaves every Draft current, and so does changing spacing
or changing a part back. A frozen copy made before Preferences existed (0.24)
holds none of them; **Inputs** says that Preferences changes are not compared
for it. Frozen copies never change; to refresh, prepare a new one and
save new revisions.

Editing a form question keeps compatible live answers. If a changed type, option
or limit makes an answer invalid, the editor shows why and requires an explicit
choice before clearing it. Frozen copies and document revisions stay unchanged.

## Mark ready

**Ready** is a stored step inside Preparing: someone, you or your agent, judged
the application complete. Under **Details**, **Mark ready** is available once
every current revision has its PDF and is approved and no blocking requirement is
unresolved; otherwise it names what is missing. It shows who marked the
application and when, and **Not ready** removes the mark.

![Details of an application marked ready by the agent, with its plan, its pinned note, the request that led to it and the job](../images/application-ready.png)

The mark describes exactly what was judged, so Openings clears it when that
changes: a new document revision or frozen copy, a deleted revision, a file added
to a current revision, a blocking requirement added or reopened, or the
application leaving Preparing. The timeline records each clearing with its
reason and who caused it. Mark the application ready again after reviewing the
change. Marking ready, preparing documents or uploading a PDF never submits
anything.

## Record what the employer did

You send each application through the employer's portal yourself; then record
**Applied** (Mark applied on the review page, or the stage under Details). When
the employer answers, choose **Record response** on its row, or on its page:

![Recording an employer's rejection on an Applied row: the answer, its date and a note](../images/respond.png)

| Answer | What it records |
|---|---|
| **Interview** | An interview response, and the application moves to Interview (a second interview keeps it there). |
| **Rejection** | A rejection response, and the application closes as Rejected. |
| **Offer** | An offer response, and the application moves to Offer. |
| **No reply** | No response: the application closes as No reply on the day you concluded it. |
| **Other** | Another answer, such as a request for references; the stage does not change. |

The date is the day the answer arrived; it defaults to today and cannot be in
the future. Moving a stage under **Details**, or closing as Rejected, records the
matching response the same way, with the day you give. The **Timeline** lists
the responses with who recorded them; **Edit** corrects a day, kind or note and
**Remove** deletes one recorded by mistake without changing the stage. The
upgrade to 0.20 added one response to each application already in Interview or
Offer and each rejected one that was sent, dated by the stage change that moved
it there; a response marked **Estimated date** took the day of the
application's last change instead, so correct it if you know better.

**No reply** is a fourth way to close, with Accepted, Rejected and Not pursued.
The no-reply period is **Count an application as no reply after [30] days**
in [Preferences](preferences.md#settings), 30 days unless you change it. Today's
**Waiting for a reply** counts the Applied applications sent longer ago,
**Record replies** lists them and **Close N as no reply** closes them after
listing them. Your agent may close them too, but only
when you ask or say so under Working with me; otherwise it asks you.

## Stats

The **Stats** tab shows how employers answered the applications you sent, for
the **Last 90 days**, the **Last 12 months** or **All time** (by the day each
was sent; all time also counts sent applications without a date).

- **Applied:** the applications you sent: those with a sent date, in Applied,
  Interview or Offer, or with a reply. Drafts you never sent do not count.
- **Reply rate:** the share with any reply; **Interview rate:** the share with an
  interview or offer reply, or moved to Interview or Offer.
- **Median days to a reply:** the day of the first reply minus the day it was
  sent.
- **Funnel:** how many were sent, got a reply, reached an interview and an offer.
- **Replies by source** appears once at least two sources (the collection
  source that first found the job) have five or more sent applications each.

## Plan and track requirements

Each application can have a **priority** (P1 highest to P5 lowest) and the
employer's **deadline**, set under **Details**. Rows show them; a past deadline
on an application still in Preparing is marked overdue. Filter by **readiness**:

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

**Requirements** records employer conditions: authorship rules (such as no
AI-written applications), attachments, references, format, language, eligibility
and dates. Mark a requirement **Blocking** when documents must not be prepared or
submitted until it is settled, and **Resolved** with a note once you decide.
They are stored on the application, not in job details, so source refreshes of
the job continue.

![The Requirements tab with a blocking authorship requirement and a resolved eligibility requirement](../images/requirements.png)

The posting is beside the documents on the review page; **Job details** opens
the job with its notes, files and maintenance actions.

## Keep, dismiss or delete

| Action | Result |
|---|---|
| Shortlist | Keep an interesting job without starting an application. |
| Return to review | Reconsider a shortlisted job before starting preparation. |
| Close application | Record its outcome and retain documents and history. |
| Dismiss job | Hide it from active review and remember it during later collection. |
| Delete application | Remove that attempt and its documents/files; keep the job. |
| Forget job | Permanently remove the job, identities and owned application history/files. Future collection can find it again. |

Closing an application keeps it in Applications, including its history and
files. The **Timeline** lists the notes and recorded changes of the application
and of its job in one list, newest first, each with who made it: you in the
dashboard, a named API token (with the workflow of its run) or the system.
Entries from before version 0.17 show "unknown (before 0.17)". The job's own
entries carry a **Job** tag. Filter by kind (notes, changes, employer
responses), by who, by scope (this application or the job) and by period. Add a
note on the application at the top; each note can be pinned, edited or deleted.
The job's page shows the same timeline for the job and every application to it.

**Pinned notes.** A job and an application each have at most one pinned note,
listed first in its timeline; pinning another note unpins the previous one, and
unpinning keeps the note. The application's pinned note is its standing
guidance: edit it under **Details**, where it replaced the application note of
earlier versions. Your agent reads it first, and each new frozen copy of your
record includes it; copies made earlier keep the text they froze.

![The Timeline tab: an employer response, then the pinned note, a note on the job and the changes, each with who made it](../images/application-history.png)

Closing never returns the job to To review or Shortlist. To cancel preparation
without losing documents, close it as **Not pursued**. Deleting the final attempt
is permanent and deliberately returns a saved job to Shortlist. Other retained
attempts keep it out of pending queues.

A job collected after another that probably describes the same vacancy (the
same posting from several job boards and the employer's site) carries the
label **Possible duplicate** (the API also gives a confidence); the duplicate
filter of each tab lists them. The job shows **Is this the same vacancy?** with the
earlier job and the reasons: the same apply link or requisition ID, identical or
nearly identical text, the same company, role and location, and anything that
speaks against it, such as a different location, requisition, level or a
posting published months apart. Company names are compared without legal,
corporate and country suffixes.

**Merge into one job** opens the merge dialog; **Keep both** records that the
two jobs are separate vacancies, and the label does not return. Nothing is
merged automatically. **Merge with another job…** under **Details** merges the
job with any other job you choose.

Dismissing a job preserves its applications. Restore it before preparing new
documents. If you previously dismissed an applied job just to clear Shortlist,
find it under **Dismissed** and choose **Restore**. REST/MCP can set `triage=saved`
with its current version. Do this only for known workaround dismissals; the job
remains in Applications and does not return to To review. A later attempt is always
explicit and respects the one-open-application rule.

Scripts and agents can perform the same workflow using the [REST API](api.md)
or [MCP tools](agents.md).
