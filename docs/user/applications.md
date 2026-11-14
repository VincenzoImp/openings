# Applications

An application is your attempt to get one job. It holds the documents, the
employer's requirements, form answers, notes and replies. A job has at most one
open application and can keep earlier closed ones.

## Stages

Shortlisting a job starts its application in **Shortlisted**. From there:
**Applied**, **Interview**, **Offer** and **Closed**. **Applications** counts each
stage and also **Ready**, the Shortlisted applications that are ready to send.
Search by role or company, filter, and sort by deadline, priority, the day it was
sent or the last change.

Closing needs an outcome: **Accepted**, **Rejected**, **Not pursued** or **No
reply**. A closed application stays in the list with its history and files. You
can start a new attempt for the job, but never two open ones at once.

![Applications: stage counts, the plan, documents and replies, and the next action](../images/applications.png)

Select rows to **Close as no reply**, **Close...** with an outcome, **Reopen...** or
**Delete...** together. Each application succeeds or fails on its own, and a
failure is named without stopping the others.

## Ready

Ready is computed. A Shortlisted application is Ready when every document it
requires has a complete current revision and no blocking requirement is open. The
required documents are a CV and a letter unless you untick one under **Details**.
Where something is missing, the application says what, for example "Missing:
letter" or an open blocking requirement. Today lists Ready applications by closest
deadline, then priority.

Ready follows the records. Add a blocking requirement, or a new revision still
without its PDF, and the application is not Ready until that is settled. Ready
does not judge the content, and preparing documents never sends anything.

## Review and apply

An application opens on its own page from Today's **Review**, a row of the list or
a link. The posting, CV and letter stand side by side with their PDFs. A switch
above a document shows its readable text instead. On a phone one shows at a time.

![The review page: the posting, the CV and the letter with their PDFs, and Mark applied](../images/review.png)

The page says where the application stands, and for a Ready one its place in
Today's order. **Before you send** lists unresolved requirements and required
questions without an answer.

- **Download CV and letter** saves both PDFs; **Open the posting** opens the
  employer's page.
- **Mark applied** records that you sent it: the stage becomes Applied, with the
  time (correctable under **Details**). Only you do this. The next Ready
  application opens, and **Undo** is offered for six seconds. It returns the
  application to Shortlisted while no reply is recorded.
- **Not pursued** closes it and keeps everything.

Tabs below hold the rest: **Answers**, **Requirements**, **Timeline**,
**Documents** and **Details**.

## Documents

A CV or letter revision is a **PDF**, and optionally the **LaTeX source** it was
built from. You need no LaTeX: a PDF alone is complete. Choose **Upload PDF** in a
slot of the review page, or **Add a document** under **Documents**; give a title
and the PDF, and the `.tex` source if you have it. A revision is incomplete until
its PDF is stored, then complete and fixed: its files never change. To change a
document, save a new revision.

- **Readable text** comes from the source when there is one, otherwise from the
  PDF, without running TeX. It is used to search and to **Compare** a revision
  with the previous one (lines removed and added). A PDF with no readable text is
  still complete.
- A PDF uploaded with a source must have been built from that source, or it is
  refused.
- Each revision can record the career entries and highlights it uses.
- Form answers and other documents are text, not PDFs.

Your agent can write and upload revisions the same way; see
[Work with an agent](agents.md). Files are limited to 20 MiB each.

## Requirements and form answers

**Requirements** record the employer's conditions: authorship rules (such as no
AI-written applications), attachments, references, format, language, eligibility
and dates. Mark one **Blocking** when the application must not go out until it is
settled, then **Resolved** with a note once you decide. They belong to the
application, so refreshing the job does not remove them.

**Answers** keep one control per question of the employer's form, so you can copy
the answers across. Changing a question keeps compatible answers; if the change
makes one invalid, you are asked before it is cleared.

## Plan

Give an application a **priority** (P1 highest to P5) and the employer's
**deadline** under **Details**. Rows show them, and a past deadline on an
application still Shortlisted is marked overdue.

## Replies

When the employer answers, choose **Record reply** on the row or the page, say what
happened, the date it arrived (today by default, never in the future) and an
optional note. One action records the reply and moves the stage:

| Reply | Stage |
|---|---|
| Interview | Interview |
| Offer | Offer |
| Rejection | Closed, Rejected |
| Other (for example a request for references) | unchanged |

Correct or remove a wrongly recorded reply from the **Timeline**; that never moves
the stage. Only applications you marked applied can have replies.

**No reply** is a way to close. The period is **Count an application as no reply
after [30] days** in [Preferences](profile-preferences-templates.md#settings).
Today's **Waiting for a reply** lists Applied applications without a reply for
longer, with **Close as no reply** one by one or for all. Nothing closes by itself,
and an agent closes them only when you ask.

## Notes and history

The **Timeline** shows replies, then the notes and changes of the application and
its job, newest first, each with who made it: "by you", "by <token name>" for an
agent, or "by job sources". Filter by kind, who, scope and period. Add a note at
the top; a job and an application each have one **pinned** note, listed first. The
application's pinned note is its standing guidance, edited under **Details**, and
your agent reads it first.

## Stats

**Applications › Stats** counts the applications you sent in the last 90 days, 12
months or all time: the share that got a reply or led to an interview, the median
days to a reply, the funnel, and replies by source once two sources each have five
sent applications.

## Delete

| Action | Result |
|---|---|
| Close | Records the outcome; keeps documents and history. |
| Delete application | Removes that attempt and its documents and files; keeps the job. Deleting the last one returns the job to New. |
| Forget job | Removes the job and everything it owns. See [Jobs and sources](jobs-and-sources.md). |
