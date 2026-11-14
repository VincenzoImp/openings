# Applications

An application holds its notes, form questions, answers, document
revisions, progress and the employer's answers. A job can have one open
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

Review new jobs in **Jobs**, which opens on the **New** tab (the tabs are
**New**, **Shortlisted**, **Dismissed** and **All**). Select a job to read it
beside the list, then choose **Shortlist** or **Dismiss…** to reject it
reversibly with an optional reason. **Dismissed** shows each job's reason and
who dismissed it; the **By agent** filter lists the jobs your agent dismissed,
and **Restore** moves a selection back to New in one action.

![Shortlist of selected jobs awaiting application preparation](../images/shortlist.png)

**Shortlist** is the one way to say "I want this job": it starts the job's
application in stage **Shortlisted** (`shortlisted` in REST/MCP), needing a CV
and a letter. Collecting jobs does not start preparation. Undoing a shortlist
(back to New, or dismissing the job) removes that application while nothing has
been added to it; once it has documents, notes, replies, requirements or
answers, close it instead. Closing an application never changes the job's tab,
and deleting a job's last application returns the job to New. The job shows its
application stage and opens the existing attempt. After closing an attempt, you
can deliberately start another.

## The pipeline

**Applications** has two tabs, **Pipeline** and **Stats**. The pipeline counts
every stage with a chip: **Shortlisted**, **Ready** (the Shortlisted applications
that are Ready, see below), **Applied**, **Interview**, **Offer** and
**Closed**. Search by role or company, filter by outcome, and sort by deadline,
priority, the time it was sent or the last change.

![Applications: stage chips with their counts, filters, and the list with plan tags, documents, the employer's answer and the next action](../images/applications.png)

Each row shows the role and company, the stage, the plan (priority, deadline and
a blocking requirement for an application being prepared; the day it was sent
otherwise), the state of the CV and letter ("Missing: letter" names what Ready
still lacks), what the employer answered (or how long the wait is, highlighted
once it is longer than the no-reply period) and the next action: **Review** a
Ready application, **Decide** on a blocking requirement, or **Record reply** for
one that was sent.

Select rows (or every row shown) to act on them together: **Close as no reply**,
**Close…** with an outcome, **Reopen…** to a stage or **Delete…**. Each
application is changed on its own; one that cannot be, such as an application
never sent closed as no reply or a second open attempt for one job, is named
without stopping the others.

![Shortlisted applications sorted by deadline with two selected and the actions on them](../images/applications-planning.png)

## Review and apply

An application opens on its own page, from Today's **Review**, a row of the
list or any link to it. The posting, the current CV and the current letter stand
side by side with their PDFs; on a phone a switch shows one at a time and the
main actions stay in a bar at the bottom. A switch above the CV or the letter
shows, instead of its PDF, its readable text. An empty slot offers **Upload
PDF**, with the `.tex` source alongside if you have one.

![The review page: tags, its place among the Ready applications, the posting, the CV and the letter with their PDFs, and Mark applied](../images/review.png)

Above them, the page says where the application stands: its stage, deadline and
priority, and for a Ready one its place among the Ready applications in Today's
order (closest deadline first) with a link to the next one. **Before you send** names
the requirements that are not resolved and the required form questions without
an answer. The actions end the task:

- **Download CV and letter** saves both PDFs; **Open the posting** opens the
  employer's page.
- **Mark applied** records that you sent it: the application moves to Applied
  with the time, which you can correct under **Details**. Only you mark an
  application applied; your agent never does.
  Once it is marked, the next Ready application opens, in Today's order, and
  the confirmation offers **Undo** for six seconds: it returns the application
  to Shortlisted, without a sent day. Going back is possible while no reply is
  recorded. After the last Ready application the page says
  **All sent** and links back to Today.
- **Not pursuing** closes it as Not pursued; its documents and history stay.

Below, five tabs hold the rest:

| Tab | What it holds |
|---|---|
| **Answers** | One control per form question, with the live answers; **Copy all**; add, edit and remove questions. |
| **Requirements** | The employer's conditions, each blocking or not and resolved or not, with your note. |
| **Timeline** | The employer's replies, then one list of the notes and changes of the application and of its job, the pinned notes first, with filters. |
| **Documents** | Every document revision: open, revise, add files to an incomplete one, delete. |
| **Details** | Stage and outcome, priority, deadline, the time sent, the required documents and whether it is Ready, the pinned note, the job and deletion. |

## Write, compile and upload

Connect an [external agent through MCP](agents.md), or work manually. Ask it to
read the application with its pinned note, the posting, your Profile, Career,
claims, templates and Preferences, write the CV, letter and answers, compile LaTeX
on its computer, and upload the PDF with the source it was built from as a
document revision. It uses its own model access and tools.

A CV or letter revision is a PDF and, optionally, the `.tex` source it was built
from, with an optional note and the claims and Career entries it uses. You need
no LaTeX: a PDF alone is a complete revision. Openings reads the text from the
source when there is one, without running TeX, and otherwise extracts it from
the PDF; that text is what you search and compare between revisions, and the
PDF is the document you send. When a PDF has no readable text, the revision is
still complete. A PDF uploaded with a source names it, and a PDF built from
another source is refused. Form answers keep their fields.

For manual work, choose **Add a document** under **Documents**, or **Upload
PDF** in the CV or letter slot of the review page: for a CV or a letter, its
title, its PDF and optionally its `.tex` source; for form answers or another
document, its text. Form answers have both an archived document revision and
live application answers; update the live answers under **Answers** when you want to reuse them in the application form.

![The Documents tab with a revision open: the text read from its source, its source and PDF, the changes since the previous revision and its actions](../images/documents.png)

Open the PDF and check wording, dates, layout and page count. A CV or letter
revision is incomplete until its PDF is stored, then complete and fixed: its
files never change. **Compare with revision 1** (for the revision before the
open one) lists the lines removed and added since then, with the unchanged lines
around them. For a changed CV or letter, choose **New PDF** (or **New
revision**) and upload the new PDF and, if you have it, its source. Click a
file name to preview a supported PDF, image or text file with its size and hash.

The list shows the state of the CV and letter from the current revisions, and
"Missing: letter" (for example) when a required document has no complete
revision.

Editing a form question keeps compatible live answers. If a changed type, option
or limit makes an answer invalid, the editor shows why and requires an explicit
choice before clearing it. Document revisions stay unchanged.

## Ready

**Ready** is computed, never marked: a Shortlisted application is Ready when
every document it requires has a current complete revision (its PDF stored)
and no blocking requirement is unresolved. Under **Details**, **Required
documents** sets which documents count (CV and letter by default; untick one
when the employer asks only for the other). Details says whether the
application is Ready, and otherwise what is missing.

![Details of a Ready application, with its plan, its pinned note and the job](../images/application-ready.png)

Because Ready is computed, it always follows the records: a new revision that
is not complete yet, or a blocking requirement added or reopened, makes the
application not Ready until that is settled. Writing documents or uploading a
PDF never submits anything.

## Record what the employer did

You send each application through the employer's portal yourself; then choose
**Mark applied** on the review page. When the employer answers, choose **Record
reply** on its row, or on its page: say what happened, the date and an optional
note. One reply records the answer and moves the stage with it:

![Recording an employer's rejection on an Applied row: the answer, its date and a note](../images/respond.png)

| Reply | What it records |
|---|---|
| **Interview** | An interview reply, and the application moves to Interview (a second interview keeps it there). |
| **Rejection** | A rejection reply, and the application closes as Rejected. |
| **Offer** | An offer reply, and the application moves to Offer. |
| **Other** | Another answer, such as a request for references; the stage does not change. |

The date is the day the answer arrived; it defaults to today and cannot be in
the future. The **Timeline** lists the replies with who recorded them; **Correct
the reply** changes a day, kind or note and **Remove the reply** deletes one
recorded by mistake, neither changing the stage. The upgrade to 0.20 added one
reply to each application already in Interview or Offer and each rejected one
that was sent, dated by the stage change that moved it there; a reply marked
**Estimated date** took the day of the application's last change instead, so
correct it if you know better.

**No reply** is a fourth way to close, with Accepted, Rejected and Not pursued.
The no-reply period is **Count an application as no reply after [30] days**
in [Preferences](preferences.md#settings), 30 days unless you change it. Today's
**Waiting for a reply** lists the Applied applications without a reply sent
longer ago, with **Close as no reply** on each and for all of them; **Record
replies** opens them in the list. Nothing closes by itself. Your agent may close
them too, but only when you ask or say so under Working with me; otherwise it
asks you.

## Stats

The **Stats** tab shows how employers answered the applications you sent, for
the **Last 90 days**, the **Last 12 months** or **All time** (by the day each
was sent; all time also counts sent applications without a date).

- **Applied:** the applications you sent: those with a sent date, in Applied,
  Interview or Offer, or with a reply. Shortlisted applications you never sent
  do not count.
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
on an application still Shortlisted is marked overdue.

Ready uses only the current revision of each document; a complete earlier
revision does not count when a newer one is incomplete. It does not check the
content or submit anything. REST and MCP list the Shortlisted applications
missing a document with `needs=documents`, and return `missing` for each
(`cv`, `letter` or `requirement:<id>`).

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
| Shortlist | Start the job's application in stage Shortlisted. |
| Back to New | Reconsider a shortlisted job; its application is removed while it is still empty. |
| Close application | Record its outcome and retain documents and history. |
| Dismiss job | Hide it from active review and remember it during later collection. |
| Delete application | Remove that attempt and its documents/files; keep the job. |
| Forget job | Permanently remove the job, identities and owned application history/files. Future collection can find it again. |

Closing an application keeps it in Applications, including its history and
files. The **Timeline** lists the notes and recorded changes of the application
and of its job in one list, newest first, each with one plain phrase for who
made it: "by you", "by <token name>" for an agent token, or "by job sources".
Entries from before version 0.17 name nobody. The job's own
entries carry a **Job** tag. Filter by kind (notes, changes, employer
replies), by who, by scope (this application or the job) and by period. Add a
note on the application at the top; each note can be pinned, edited or deleted.
The job's page shows the same timeline for the job and every application to it.

**Pinned notes.** A job and an application each have at most one pinned note,
listed first in its timeline; pinning another note unpins the previous one, and
unpinning keeps the note. The application's pinned note is its standing
guidance: edit it under **Details**, where it replaced the application note of
earlier versions. Your agent reads it first, with the application.

![The Timeline tab: an employer reply, then the pinned note, a note on the job and the changes, each with who made it](../images/application-history.png)

Closing never changes the job's tab. To cancel preparation without losing
documents, close it as **Not pursued**. Deleting the final attempt is permanent
and returns the job to New.

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

Dismissing a job preserves its closed applications; an open one with work in
it must be closed first. Restore a dismissed job before preparing new documents:
find it under **Dismissed** and choose **Restore**. A later attempt is always
explicit and respects the one-open-application rule.

Scripts and agents can perform the same workflow using the [REST API](api.md)
or [MCP tools](agents.md).
