---
name: prepare-applications
title: Prepare CVs and letters
summary: Have a tailored CV and letter written, compiled and checked for each shortlisted job until it is Ready, and redone after a template change.
example: Prepare a CV and letter for every job on my shortlist.
description: Prepare the CV and letter (cover letter) of Openings applications from the owner's career entries, templates and Writing rules - "prepare every shortlisted job", "prepare the application for X", "redo the letter for Y", "redo them with my new template". Compiles PDFs locally, uploads them and leaves each application Ready for the owner to apply.
---

# Prepare CVs and letters

Read [openings](../openings/SKILL.md) first, and
[writing](references/writing.md) before you write. You prepare; the owner
applies, best first.

## 1. Gather

- `workspace_context` with the full career and templates: Writing rules,
  Facts about me, approved highlights (★ always include) and each template's
  source, guidance and rules. Download a template's files (class, fonts,
  images, checks) with `files_download` beside its TeX, and follow any guide
  among them.
- The work: `applications_list` with needs documents, sort priority (priority,
  then deadline), or the ones the owner named. Give a missing priority as
  [review-applications](../review-applications/SKILL.md) says. Skip Ready
  ones unless asked to redo them. A named job without an open application:
  `applications_create`; a dismissed job: `jobs_triage` it shortlisted; a
  Closed application: reopen it only when the owner asks.
- Tools: a shell with `curl`, and `tectonic` (a single binary that fetches
  packages on demand; offer to install it) or `pdflatex`, unless a template's
  rules name another engine. Without TeX, a PDF from another tool is fine only
  when the owner has no TeX template; never upload an unchecked PDF.

## 2. Per application

Read it with `applications_get` (up to 20 at a time) and its job with
`jobs_get`. Follow its pinned note first: it is the owner's guidance.

**Still open?** A posting no longer listed, or with a passed closing date,
confirmed on its page, is closed: close the application as not pursued, with
an unpinned note giving the evidence, and prepare nothing.

**Employer requirements.** Before writing, record each with
`applications_update` and the version you read, by kind:

- authorship, an AI-use clause, quoted: when Working with me or Facts about
  me state the owner's policy, follow it and mark the requirement resolved,
  not blocking, with a note naming the policy. Without one, make it blocking,
  ask once, and offer to record the answer in Working with me;
- attachment (transcripts, work samples) and reference: blocking while the
  owner must supply them; never invent a referee;
- format (page limit, CV only, a form) and language: you meet them; when no
  letter is wanted, require the CV alone;
- eligibility (permit, degree, location) against Facts about me, without
  inferring rights: an open question is blocking;
- deadline: the closing date goes into deadline as well;
- other: blocking only when the owner must act before sending.

Information the owner should see at send time is not blocking.

**Select.** Pick the three to five needs of the role, then the career entries
and approved highlights that answer them best. Start from ★ highlights unless
the job gives a reason to drop one. Keep each item under its real role and
dates.

**Write.** Fill the template following its guidance, the Writing rules for
that document and the writing reference. Keep its fixed parts. The letter
addresses this employer and role; CV and letter tell one story.

**Compile and check.** Compile locally, then read the PDF itself:

- page count and template limits, nothing cut off or overflowing;
- every link works and points where it should;
- no placeholder, TODO or other company's name;
- every claim traces to the record; nothing contradicts Facts about me;
- each Writing rule holds.

**Store.** `documents_create` with the PDF's name, size and sha256, the TeX
source, the approved highlights and entries you used, for a redo previous_id,
and an idempotency key from the application, template version and replaced
revision (cv-<application id>-<template version>-<previous id or first>). PUT the source file first, then the
PDF, at once: from the create on, the new revision is current and Ready waits
for its PDF. On a failed upload, `documents_delete` the empty revision (the
previous one is current again) or create again with the same key for a new
grant. A stored revision is final; any change is a new one.

**Form questions.** Record them as the application's questions and draft
answers from the record, never inventing; answers replace the whole set, so
send every answer to keep. A long form can be an answers revision. The owner
submits them.

**Gaps.** What the record cannot support goes in an unpinned note, never into
the documents.

## 3. Confirm Ready

Read the applications again: Ready is computed, and each says what is
missing. Fix what you can; ask about the rest. Set no stage.

## Redo after a change

After a template or Writing rule changed, or on request, redo the Shortlisted
applications whose documents predate it, priority first:

- build each document from the current template, never by editing the old one;
  keep the old reasoning only where it is accurate and still the best case;
- store it with previous_id, and a note naming the template and its version;
- keep requirements, answers, priority and deadline as they are;
- read the application again and confirm it is Ready;
- never touch sent applications: their documents are what the employer got.

## Report back

The applications now Ready, by title and company, with deadlines; those not
Ready and why (a requirement, a missing fact, a failed compile); closed
postings; gaps noted; that the owner applies to Ready ones, best first.
