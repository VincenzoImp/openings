---
name: prepare-applications
title: Prepare CVs and letters
summary: Have a tailored CV and cover letter written, compiled and checked for each shortlisted job until it is Ready.
example: Prepare a CV and cover letter for every job on my shortlist.
description: Prepare the CV and cover letter of Openings applications from the owner's Career record, templates and Writing rules - "prepare CV and letter for every shortlisted job", "prepare the application for X", "redo the letter for Y". Compiles PDFs locally, uploads them and leaves each application Ready for the owner to send.
---

# Prepare CVs and letters

Read [openings](../openings/SKILL.md) first, and
[writing](references/writing.md) before you write. You prepare; the owner
reviews, sends and marks Applied.

## 1. Gather

- `workspace_context` with the full career and templates: Writing rules,
  Facts about me, approved highlights (★ always include) and each template's
  source, guidance and limits.
- The work: `applications_list` of Shortlisted applications missing a document,
  or the ones the owner named. Order them by deadline, then by fit. A job the
  owner names that has no open application gets one with
  `applications_create`; a Closed one is started again only when they ask.
  Skip applications that are already Ready unless asked to redo them.
- Check your tools: a shell to upload, and `pdflatex` (or the engine the
  template names) for TeX templates. Without a compiler, a PDF-only revision
  from another tool is fine when the owner has no TeX template; never upload
  an unchecked PDF.

## 2. Per application

Read it with `applications_get` (up to 20 at a time) and its job with
`jobs_get`. Follow its pinned note first: it is the owner's guidance.

**Employer requirements.** Before writing, look in the posting for:

- a ban on AI-written applications: stop, add it as a blocking requirement and
  tell the owner;
- attachments, references, transcripts, work samples: list those the owner must
  supply as requirements; never invent a referee;
- format: page limit, language, CV only, form questions; when no letter is
  wanted, require the CV alone;
- eligibility (work permit, degree, location) compared with Facts about me
  without inferring rights; an open question is a requirement, not a guess;
- a closing date: set the deadline; a closed posting is reported, not prepared.

Record them with `applications_update`. A blocking one keeps it from Ready
until the owner resolves it.

**Select.** Pick the three to five needs of the role, then the career entries
and approved highlights that answer them best. Start from ★ highlights unless
the job gives a reason to drop one. Keep each item under its real role and
dates.

**Write.** Fill the template following its guidance, the Writing rules for
that document and the writing reference. Keep the template's fixed parts. The
letter addresses this employer and role; the CV and letter tell one story with
the same facts.

**Compile and check.** Compile locally, then read the PDF itself:

- page count and template limits, nothing cut off or overflowing;
- every link works and points where it should;
- no placeholder, TODO or other company's name left;
- every claim traces to the record; nothing contradicts Facts about me;
- each Writing rule holds.

Fix and compile again until it passes.

**Store.** Call `documents_create` with the PDF's name and size, the TeX
source when you compiled one, the highlights and entries you used and, for a
redo, the revision it replaces. PUT the PDF with the returned grant (see
[openings](../openings/SKILL.md)). A revision is complete and final once its
PDF is stored: check before uploading, and make a new revision for any
change.

**Gaps.** What the record cannot support goes in an unpinned note on the
application for the owner, never into the documents.

## 3. Confirm Ready

Read the applications again: Ready is computed from complete documents and
open requirements, and each application says what is still missing. Fix what
you can; ask about the rest. Do not set any stage: Ready applications wait for the owner.

## Report back

In chat: the applications now Ready, by title and company, with any deadline;
those not Ready with the reason (a requirement for the owner, a missing fact,
a failed compile); the gaps you noted; and a reminder that the owner reviews,
sends and marks each one Applied.
