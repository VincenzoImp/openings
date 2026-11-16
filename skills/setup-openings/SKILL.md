---
name: setup-openings
title: Set up your workspace
summary: Get connected, then have your career entries, Preferences, templates and first sources set up from your CV and a short interview.
example: Set up my Openings workspace from my CV.
description: Set up a new or empty Openings workspace for its owner - "set up my Openings workspace", "get me started". Checks the connection, uploads and TeX, builds the Profile and career entries from a CV, records Preferences and standing instructions from a short interview, creates templates, adds first sources and runs a first triage.
---

# Set up your workspace

Read [openings](../openings/SKILL.md) first. Do the steps in order; each uses
what the previous one recorded. Skip what is already done.

## 1. Check the connection

- Call `workspace_context`. If it fails, the owner needs a running server
  (the repository's getting-started guide) and an Agent token from Settings ›
  API & agents in your client's environment. Never ask for the token in chat.
  When it names you as the owner, suggest an Agent token: it can do all of
  this work.
- Check you have a shell with `curl`, then a TeX engine: `tectonic` first, a
  single binary that fetches packages on demand, so no TeX distribution is
  needed; offer to install it with the owner's agreement. `pdflatex` is fine
  too.
- Make the first upload early, such as the first template's PDF check: if
  curl cannot reach the grant's URL, the server needs OPENINGS_PUBLIC_URL set
  to an address this machine can reach.

## 2. Career entries

Ask for a CV, LinkedIn export or a description of their work, and follow
[maintain-career](../maintain-career/SKILL.md) to build the Profile, entries
and highlights. Ask about gaps that matter: dates, own role, results.

## 3. Preferences

Interview the owner briefly, a few questions at a time:

- What I'm looking for: roles, seniority, places, remote, company types;
- What I rule out: dealbreakers;
- Facts about me: work permit, availability, notice, languages, and a salary
  policy with its currency;
- Writing rules: tone, length, spelling, words to avoid, for the CV, the
  letter or both;
- Working with me:
  - what you may do without asking: dismiss, close as no reply after N days,
    delete, mark applied from their mailbox;
  - a priority rubric, or "you decide";
  - a cap of open applications per employer;
  - what to do when an employer bans AI-written applications;
  - the sending order (priority then deadline, or theirs);
  - whether to run on a schedule, and where reports go.

Record each answer as a separate item in their words with
`preferences_update`. Set the languages they speak and, if they say, the days
before an application counts as unanswered, with `settings_update`. Tell them
they can edit everything under Preferences.

## 4. Templates

Use the owner's own TeX CV and letter, with their files (class, fonts,
images), when they have them; otherwise write a clean one-page CV and a letter
template. Compile each with real content, check the PDF, and save it with
`templates_save`: guidance on what to tailor, and rules with limits such as
pages and the engine (tectonic). Upload its files with `files_upload` (owner
type template).

## 5. First sources

Follow [manage-sources](../manage-sources/SKILL.md): searches for the target
roles and places, and boards of companies they name, previewed before saving.

## 6. First results

Once jobs arrive, run [triage-jobs](../triage-jobs/SKILL.md), and prepare one
shortlisted application with
[prepare-applications](../prepare-applications/SKILL.md) so the owner sees a
real result. Then offer a scheduled run of
[run-job-search](../run-job-search/SKILL.md).

## Skills on disk

If the owner's client loads skills from a folder, offer to save these skills
there: read each with `skills_get` and write it, with its references, to that
folder (for example `.claude/skills/<name>/`), noting the workspace.version
they came from. Fetch them again after each upgrade; when the version differs
from the copy's, prefer `skills_get`.

## Report back

What is set up (entries, Preferences items, templates, sources); the open
questions about their career; and their part from now on: review Ready
applications, send them and tell you, or mark them Applied, when they do.
