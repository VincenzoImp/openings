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

## The list

**Applications** shows every application by stage. One row of chips picks the
stage: **Shortlisted**, **Ready** (the Shortlisted applications that are Ready,
see below), **Applied**, **Interview**, **Offer**, **Closed** and **All**, each
with its count. Beside them are the search, **Filter** (priority, deadline,
source, outcome) and the order. The default order, **Needs action**, groups the
rows: Ready by deadline, then Shortlisted ones with a deadline, then sent ones
waiting longer than the no-reply period, then everything else by its last
change. The other orders are **Deadline**, **Last change** and **Applied date**.

![Applications: the stage chips, the rows grouped by what needs action, and List and Stats](../images/applications.png)

Each row shows the role and company, the stage as a glyph and one status phrase
that follows it ("Missing: letter", "Ready · due Fri", "Applied 12 Oct · no
reply 32 days", "Interview 4 Nov", "Closed · rejected"), and the priority as a
leading glyph. The row opens the application's page. Pointing at a row (or
moving to it with `j`/`k`) shows its action: **Apply** on a Ready one, **Record
reply** (`r`) on a sent one, and `…` with **Change stage…**, **Close…** or
**Reopen**, and **Delete permanently…**.

Pick rows with `x` or ⌘-click (shift-click for a range) to act on them
together. The bar offers only what is valid for every picked row: **Close as no
reply**, **Close…** with an outcome, **Reopen** and **Set priority…**. Each
application is changed on its own; one that cannot be is named without
stopping the others, and closing or reopening offers **Undo**.

## The application page

An application opens on its own page, from Today, a row of the list or any link
to it. Its head shows the role, company, place, stage, deadline and priority,
**Open posting** and `…` (**Change stage…**, **Deadline and priority…**,
**Required documents…**, **Close…**, **Delete permanently…**). What follows
depends on the stage.

**Shortlisted.** **What's missing** lists the CV and the letter (or "not
needed") and the requirements done. Each required document has a slot: drop
its PDF there, with its `.tex` source if you have one, or choose **Upload PDF**.
A filled slot shows the PDF (or its text) and `…`: **Replace…**, **Download**,
**Earlier versions**, **Show changes from previous version** and **Remove…**.
Requirements are listed inline: add one, tick it done, remove it; a blocking
one is marked. The main action settles the first missing item (**Upload CV**,
**Upload letter**, **Resolve requirements**); once nothing is missing the page
becomes the Ready page.

**Ready.** The posting, the CV and the letter stand side by side, each document
with a PDF/Text switch. Above them, **Before you send** lists the open
requirements (tick them there), the form's answers with a copy button each,
**Apply on employer's site** and **Download CV + Letter**. The page says its
place among the Ready applications in Today's order ("2 of 5 ready · Next: …");
`[` and `]` move between them. On a phone the parts are tabs: **Check**,
**Posting**, **CV**, **Letter**.

![The Ready page: before you send, the posting, the CV and the letter, and Mark applied](../images/review.png)

**Mark applied** (`⇧↵`) records that you sent it, today unless you pick another
day beside the button. Only you mark an application applied; your agent never
does. The next Ready application opens at once, and the confirmation offers
**Undo**, which returns the application to Shortlisted without a sent day.
After the last one the page says **All sent** with the number sent today and
**Back to Today**. If marking fails, the page stays and says why.
**Not pursuing** (in `…`) closes it as Not pursued.

**Applied, Interview, Offer.** The page starts with where it stands ("Applied
12 Oct · no reply for 32 days") and **Record reply**. Then come the notes
(read first, **Edit**), the history (replies, stage changes and notes, newest
first, with who made them; **Show all changes** adds every recorded change),
the documents that were sent, and the posting, requirements and answers folded.
`…` adds **Close as no reply**, **Withdraw** and, at Offer, **Accept offer**,
each with **Undo**.

**Closed.** The page says how it ended ("Rejected on 2 Nov after interview"),
then the notes, the history and the sent documents; `…` **Reopen**s it.

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

For manual work, upload the PDF in the CV or letter slot of the application
page, with its `.tex` source if you have one. A CV or letter revision is
incomplete until its PDF is stored, then complete and fixed: its files never
change. **Replace…** uploads a new version; **Show changes from previous
version** lists the lines removed and added; **Earlier versions** lists every
version with its download.

## Ready

**Ready** is computed, never marked: a Shortlisted application is Ready when
every document it requires has a current complete revision (its PDF stored)
and no blocking requirement is unresolved. **Required documents…** sets which
documents count (CV and letter by default; untick one when the employer asks
only for the other). The page of a Shortlisted application says what is
missing.

Because Ready is computed, it always follows the records: a new revision that
is not complete yet, or a blocking requirement added or reopened, makes the
application not Ready until that is settled. Writing documents or uploading a
PDF never submits anything.

## Record what the employer did

You send each application through the employer's portal yourself; then choose
**Mark applied** on its page. When the employer answers, choose **Record
reply** on its row or its page: what happened, the date and an optional note.
One reply records the answer and moves the stage with it:

| Reply | What it records |
|---|---|
| **Interview invitation** | An interview reply, and the application moves to Interview (a second interview keeps it there). |
| **Rejection** | A rejection reply, and the application closes as Rejected. |
| **Offer** | An offer reply, and the application moves to Offer. |
| **Other** | Another answer, such as a request for references; the stage does not change. |

The date is the day the answer arrived; it defaults to today and cannot be in
the future. The history lists the replies with who recorded them; a reply
recorded by mistake is corrected or removed through the API, neither changing
the stage. The upgrade to 0.20 added one
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

**Stats** (beside **List**) shows how employers answered the applications you sent, for
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
employer's **deadline**, set with **Deadline and priority…**. Rows show them; a past deadline
on an application still Shortlisted is marked overdue.

Ready uses only the current revision of each document; a complete earlier
revision does not count when a newer one is incomplete. It does not check the
content or submit anything. REST and MCP list the Shortlisted applications
missing a document with `needs=documents`, and return `missing` for each
(`cv`, `letter` or `requirement:<id>`).

**Requirements** records employer conditions: authorship rules (such as no
AI-written applications), attachments, references, format, language, eligibility
and dates. Mark a requirement **Blocking** when documents must not be prepared or
submitted until it is settled, and tick it once it is. They are stored on the
application, not in job details, so source refreshes of the job continue.

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
files. The history of the page lists the replies, stage changes and notes of
the application, newest first, each with one plain phrase for who made it: "by
you", "by <token name>" for an agent token, or "by job sources"; **Show all
changes** adds every recorded change, including the job's.

**Notes.** The application's note sits above its history: read first, **Edit**
to change it. It is the application's standing guidance, and your agent reads
it first, with the application.

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
merged automatically. **Merge with another job…** merges the job with any
other job you choose.

Dismissing a job preserves its closed applications; an open one with work in
it must be closed first. Restore a dismissed job before preparing new documents:
find it under **Dismissed** and choose **Restore**. A later attempt is always
explicit and respects the one-open-application rule.

Scripts and agents can perform the same workflow using the [REST API](api.md)
or [MCP tools](agents.md).
