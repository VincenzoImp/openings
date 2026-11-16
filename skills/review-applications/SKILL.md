---
name: review-applications
title: Rank and review what is Ready
summary: Have your open applications ranked by priority, given a salary range with its basis, checked for employers you apply to too often, and fixed everywhere at once.
example: Rank my Ready applications and tell me what to send first.
description: Review the Openings application queue - "what should I send first?", "set priorities", "add a salary expectation", "too many applications at X", "check everything Ready", "fix this in every letter". Ranks, sets a sending order, recommends a salary with its basis, flags employer concentration and runs document fix passes.
---

# Rank and review what is Ready

Read [openings](../openings/SKILL.md) first and call `workspace_context`. This
works on Shortlisted applications, Ready or not; sent ones keep their
documents.

## 1. Read the queue

Page through `applications_list` with stage ready, then Shortlisted with
ready false. Read each with `applications_get` (requirements, answers, the
pinned note) and its posting with `jobs_get`, 20 at a time.

## 2. Still worth sending?

Close an application as not pursued only for a clear reason, with an unpinned
note giving it:

- the posting closed, expired or is past its deadline, confirmed on its page;
- a decisive mismatch with What I rule out or Facts about me, stated in the
  posting;
- a duplicate of another open application for the same vacancy;
- the employer accepts one application, and another is stronger.

Otherwise keep it, and follow Working with me (such as "shortlist
generously").

## 3. Priority and sending order

Use the owner's rubric from Working with me, else:

- 1: an excellent fit; the core work matches the record, the place and
  employer suit, nothing material missing;
- 2: a strong fit with minor gaps, or excellent in a less preferred place;
- 3: a good fit with moderate gaps;
- 4: a stretch: a notable gap, a domain shift, a lower level, relocation;
- 5: a long shot kept by a generous bar; an agency hiding the employer, unless
  the role is clearly worth it.

Within one employer, spread the priorities so the best comes first. Keep a
priority the owner set by hand (feedback, or `changes_list` with actor
owner). Set priorities with `applications_update` and the version read. The
sending order is priority, then the earlier deadline (`applications_list`
stage ready, sort priority).

## 4. Salary

Use only Facts about me (the owner's targets or policy) and the posting: a
stated band or scale, the job's metadata salary, a pay-transparency range.
Never invent a market figure; with no basis, ask. Give a range and a single
figure in the posting's currency, and store it in the application's `salary`
field with the version read, plus an unpinned note "Salary basis: ..." (key
salary-<application id>). Put salary into a document only when the employer
asks for it there.

## 5. Employers over the cap

Group the open applications by employer. Company names are exact matches, so
normalize them (Northstar, Northstar Labs) and count agencies apart. Over the
cap in Working with me (flag above 3 when there is none):

- rank within the employer and propose the ones to keep;
- close the weaker ones as not pursued only when the owner says so or a rule
  does, with a note naming the ones kept.

## 6. Fix documents everywhere

For "fix X in every letter" or a check of everything Ready:

- find the current revisions that contain it with `documents_list` and `q`;
- edit the TeX minimally; never restyle for taste;
- compile and check as [prepare-applications](../prepare-applications/SKILL.md)
  says, and store a new revision with previous_id;
- read the application again: it must still be Ready.

Never revise a sent application's documents. For a template change, use
prepare-applications "Redo after a change".

## Report back

Counts per step; the sending order with deadlines (priorities 1 and 2 by
name); closures with their reasons; salaries set and their basis; employers
over the cap; documents fixed; questions.
