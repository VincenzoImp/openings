---
name: maintain-workspace
title: Keep your workspace safe and tidy
summary: Have backups and exports taken and checked, stale items tidied away reversibly, records deleted only when you ask, and an agent run undone.
example: Take a backup, then undo what you did yesterday.
description: Back up, export, tidy and clean up an Openings workspace - "back up my workspace", "export my records", "clean up old jobs", "delete these permanently", "undo what you did yesterday". Prefers what can be undone, backs up before deleting and checks every result.
---

# Keep your workspace safe and tidy

Read [openings](../openings/SKILL.md) first and call `workspace_context`.

## Backup

1. `workspace_backup`, then run its `curl` line within two minutes.
2. Check the copy: `sqlite3 <file> 'PRAGMA integrity_check'` must print ok.
3. Keep as many copies as the owner says, where they say. Never in Git or a
   shared folder: a backup holds personal data and documents. An agent's copy
   holds no credentials.

The server already keeps daily backups on its own disk; this is the copy
elsewhere. A scheduled run can take one, as
[run-job-search](../run-job-search/SKILL.md) says.

## Export

`workspace_backup` with kind export gives the records as JSON, without file
bytes or credentials, the same way: run the `curl` line and check that the
file parses.

## Tidy, reversibly first

- Shortlisted applications past their deadline or no longer listed: check the
  posting, then close them as not pursued with a note.
- Pause sources that bring nothing useful.
- Leave dismissed jobs in place: they are the memory that keeps collection
  from showing the same vacancy as new again.

## Delete permanently

Only on the owner's request, or a standing instruction naming the scope.

1. List exactly what goes, and how many.
2. State the consequences:
   - a deleted job returns as New when a source finds it again;
   - deleting a job deletes its applications, documents and files;
   - deleting the newest revision makes the previous one current;
   - deleting a revision of a sent application loses what the employer got.
3. Take a backup first, as above, when more than a few records go.
4. Delete with each record's version (`jobs_delete`, `applications_delete`,
   `documents_delete`) and check every result.

## Undo a run

1. Find what the run did: `changes_list` with actor agent:<token name> and
   since, or with the batch_id of one call.
2. Jobs it dismissed: `jobs_list` with triage dismissed and that batch_id (or
   dismissed_by and dismissed_since), then `jobs_triage` them to new.
3. Jobs it shortlisted: `jobs_triage` to new while their applications are
   empty, else close the applications as not pursued.
4. Applications it changed: undo each as the core skill's critical actions
   say (back to Shortlisted, reply_fix, reopen).
5. Revisions it made: delete them only when the owner asks.

Report what could not be undone.

## Report back

The backup or export file, its size and check; what was tidied, deleted or
undone, with counts; the consequences the owner accepted; what could not be
undone.
