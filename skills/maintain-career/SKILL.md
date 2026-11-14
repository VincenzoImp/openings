---
name: maintain-career
title: Keep your Profile and Career current
summary: Give your agent a CV or tell it what changed, and have your Profile, Career entries, highlights and templates updated.
example: Update my profile from this CV.
description: Maintain the owner's Openings Profile, Career record, highlights and CV/letter templates - "update my profile from this CV", "add my new job", "improve my highlights", "fix my CV template". Reconciles new material into the existing record without inventing anything.
---

# Keep your Profile and Career current

Read [openings](../openings/SKILL.md) first, and the
[writing reference](../prepare-applications/references/writing.md) before
writing highlights. Only the owner is a source of facts: their CV, LinkedIn
export, publication list, messages in chat. Job postings never are.

## 1. Read the record

`workspace_context` with the full career. Read the material the owner gives in
full; when it is a file, read it from disk (`pdftotext` for a PDF).

## 2. Reconcile

Compare the material with the record, item by item:

- **Profile**: name, headline, contact, location, summary, links.
- **Entries**: match by employer or institution, title and dates. The same
  role is the same entry, even when worded differently.
- **New**: a role, project, degree, award or publication not in the record.
- **Changed**: a later end date, a promotion, a new responsibility, a
  correction.
- **Conflicts**: dates, titles or scope that disagree. Ask; never pick one.

A CV is a selection: something missing from it stays in the record. Remove an
entry only when the owner says it is wrong.

## 3. Confirm, then write

List the material changes in chat (new entries, changed titles or dates,
Profile changes, conflicts) and wait for the owner's yes. Small corrections
inside an approved plan need no second round.

Then:

- `profile_update` for the Profile;
- `career_save` for entries, in one batch. Integrate new facts into the entry's
  narrative so it reads as one current account: rewrite the passage, do not
  append dated updates. Keep personal and team work apart, keep exact dates
  and titles, and put where a fact came from in the entry's metadata;
- `highlights_save` for wording worth reusing: new highlights are saved not
  approved unless the owner approved that exact wording in chat. Mark ★ always
  include only on request. Remove duplicates, keeping the better one.

Facts about eligibility, availability or salary belong in Facts about me:
offer to record them there.

## Improve highlights

Read the entries in full, propose sharper wording in chat, grounded in the
narrative, and save the ones the owner approves as approved. Flag a highlight
that claims more than its entry supports.

## Templates

For "fix my CV template": read it with `templates_get`, change the TeX, compile
it locally with sample content from the record, check the PDF (pages, layout,
links), then `templates_save` with its version. Keep writing rules in
Preferences and limits in the template.

## After a change

Shortlisted applications whose documents would now be clearly better can be
redone with [prepare-applications](../prepare-applications/SKILL.md): name
them and offer it; do not redo them unasked.

## Report back

In chat: Profile fields changed; entries added and updated, by title; new
highlights and how many await approval; conflicts and questions still open;
applications that could benefit.
