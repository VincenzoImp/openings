# Upgrading to 0.23

0.23 removes what 0.19 to 0.22 deprecated: the tool names before 0.22, the
flat list arguments, the application `note` field, deletes without
`expected_version`, the job `availability` field and the Profile `preferences`
and `roles`. Every name and field it removes had its replacement in 0.22, so a
client that already follows [Upgrading to 0.22](upgrading-0.22.md) changes
nothing. A client written for 0.21 must make the changes below; an earlier
name, a removed field or a flat argument is now refused, never ignored.

The database upgrades itself to schema 14 when 0.23 first opens it, in one
transaction, and keeps every value the removed fields held. A release before
0.23 cannot open the upgraded file, so make a backup first. From 0.21 or
earlier, the same start also runs 0.22's upgrade: read its guide too.

## What the upgrade does

- **Job availability.** Each job whose `availability` was set by hand (`open`,
  `closed`, anything but the default `unknown` or empty) gets one note on the
  job, in its timeline, with the value exactly as stored:

  ```text
  Availability (recorded by hand before 0.23): closed

  0.23 removed this field. Whether the source still lists the posting is the No longer listed signal.
  ```

  The note's `origin` is `upgrade`; it is not pinned. Its author and run are
  those of the last recorded change that set the field (an edit naming
  `availability`), and its time is that change's, else the job's last change;
  a change recorded before 0.17 has no author ("unknown (before 0.17)"). The
  upgrade compares every note with the value byte for byte before it drops the
  column.
- **Profile preferences and roles.** 0.19 copied both texts into unconfirmed
  **Decision** items of the [policy](policy.md). Before removing the fields,
  the upgrade checks that a policy item holds each non-empty text: its
  statement (or a text value) is the same text, ignoring differences of
  spacing, in any section. A text no item holds, because it was written or
  edited after 0.19 or its item was edited or removed, becomes a new
  unconfirmed Decision item, labelled **Preferences** or **Target roles**, at
  the end of the section, with the origin "Copied from Profile preferences
  (roles) when 0.23 removed the field"; the section's version moves on by one.
  The upgrade checks every text again, then removes the two fields. The
  Profile's other values, its version and its time do not change.
- **Nothing else changes.** The upgrade writes no change record. Pinned notes,
  documents, files and every other row keep their values. Frozen contexts are
  not touched: a context frozen before 0.23 keeps the Profile `preferences` and
  `roles` it froze (they never made a document stale), and every context keeps
  `application.note` and `instructions.application_note`, which a new context
  still fills from the pinned note.
- **Restore** accepts a backup of schema 5 to 14; an older one is upgraded the
  same way on a copy, and the uploaded file is not changed.

On a synthetic workspace of 25,000 jobs with postings of about 3,000
characters, 400 of them with an availability value, on a laptop, the step took
0.4 s; a small host takes several times longer.

## Tool names

The 30 names before 0.22, kept as deprecated aliases in 0.22, are gone: calling
one returns `Unknown tool`. Call the name on the right; it takes the arguments
of [0.22](upgrading-0.22.md#one-argument-shape): identifiers flat, a delete's
`expected_version` flat, and everything else in `value`.

| Before 0.22 | From 0.22, the only name in 0.23 | What to change |
|---|---|---|
| `application_create` | `applications_create` | the name |
| `application_delete` | `applications_delete` | the name |
| `application_get` | `applications_get` | the name |
| `application_history` | `applications_history` | the name |
| `application_prepare_context` | `contexts_create` | the name |
| `application_ready` | `applications_ready` | the name |
| `application_staleness` | `staleness_get` | the name |
| `application_update` | `applications_update` | the name |
| `applications_staleness` | `staleness_list` | the name; `status`, `stale_only`, `limit` and `offset` go in `value` |
| `career_get_profile` | `profile_get` | the name |
| `career_update_profile` | `profile_update` | the name |
| `collection_yield` | `sources_yield` | the name |
| `job_distinct` | `jobs_distinct` | the name |
| `job_forget` | `jobs_delete` | the name |
| `job_get` | `jobs_get` | the name |
| `job_ingest` | `jobs_create` | the name |
| `job_merge` | `jobs_merge` | the name |
| `job_triage` | `jobs_triage` | the name |
| `job_update` | `jobs_update` | the name |
| `jobs_search` | `jobs_list` | the name |
| `note_add` | `notes_create` | the name |
| `note_delete` | `notes_delete` | the name, and send the note's `expected_version` |
| `note_get` | `notes_get` | the name |
| `note_update` | `notes_update` | the name |
| `responses_add` | `responses_create` | the name |
| `responses_remove` | `responses_delete` | the name |
| `skill_get` | `skills_get` | the name; `local_notes` goes in `value` (`name` and `path` stay flat) |
| `token_create` | `tokens_create` | the name |
| `token_revoke` | `tokens_revoke` | the name |
| `workspace_restore_upload` | `workspace_restore` | the name |

REST paths did not change.

## Lists take their filters in `value`

These tools accepted their filters, page and options as flat arguments beside
`value` in 0.22. In 0.23 they take them inside `value` only:

| Tool | Move into `value` |
|---|---|
| `knowledge_list` | `q`, `kind`, `limit`, `offset`, `summary` |
| `claims_list` | `knowledge_id`, `approved`, `limit`, `offset`, `summary`, `q` |
| `templates_list` | `kind`, `limit`, `offset`, `summary`, `q` |
| `contexts_list` | `application_id`, `limit`, `offset`, `summary`, `q` |
| `documents_list` | `application_id`, `kind`, `limit`, `offset`, `summary`, `q`, `review_state` |
| `files_list` | `owner_type`, `owner_id`, `limit`, `offset`, `summary`, `q`, `media_type`, `application_id` |
| `collection_runs_list` | `limit`, `offset`, `source_id`, `state`, `summary` |
| `sources_list` | `limit`, `offset`, `summary` |
| `tasks_list` | `limit`, `offset`, `state`, `kind`, `source_id`, `job_id` |
| `runs_get` | `changes_limit`, `changes_offset` (`run_id` stays flat) |

For example `knowledge_list({"q": "Python", "summary": false})` becomes
`knowledge_list({"value": {"q": "Python", "summary": false}})`.

Every tool now refuses an argument it does not take, with `422 validation` and
one detail per argument (`field`, `type: "extra_forbidden"`), so a filter
passed beside `value` can no longer be dropped silently and return an
unfiltered list.

## The application note is the pinned note

| Before | 0.23 |
|---|---|
| `note` on `applications_get` / `GET /applications/{id}` | Removed. Read `pinned_note` (the note, or null); its `body` is the text. |
| `note` on `applications_create` / `POST /applications` | Refused (`422 validation`). Create the application, then `notes_create` / `POST /jobs/{job_id}/notes` with `{"body": ..., "application_id": ..., "pinned": true}`. |
| `note` on `applications_update` / `PATCH /applications/{id}` | Refused (`422 validation`). Edit the text with `notes_update` / `PATCH /notes/{id}`; unpin with `notes_pin` / `POST /notes/{id}/pin` and `"pinned": false`; add a new pinned note with `notes_create`. |

`q` on the application list still searches the pinned notes, and a new frozen
context still carries the pinned note as `application.note` and
`instructions.application_note`.

## Deletes require `expected_version`

| Delete | REST | MCP |
|---|---|---|
| Note | `DELETE /notes/{id}?expected_version=N` | `notes_delete(note_id, expected_version)` |
| Document revision | `DELETE /documents/{id}?expected_version=N` | `documents_delete(document_id, expected_version)` |
| File | `DELETE /files/{id}?expected_version=1` | `files_delete(file_id, expected_version)` |

Without it the delete is refused with `422 validation` and nothing is deleted.
A stale version returns `409 conflict` with `details.current_version`. A file
never changes, so its version is always 1.

## The job `availability` field

| Before | 0.23 |
|---|---|
| `availability` on job reads (`jobs_get`, `jobs_list`, `GET /jobs`, `GET /jobs/{id}`) | Removed. Read `signals.no_longer_listed`; a value set by hand is in the job's timeline as a note. |
| `availability` on `jobs_update` / `PATCH /jobs/{id}` | Refused (`422 validation`). Write a note with `notes_create` when you want to record it. |

## Profile `preferences` and `roles`

| Before | 0.23 |
|---|---|
| `preferences` and `roles` on `profile_get` / `GET /career/profile` | Removed. Read the Decision items with `policy_get` / `GET /policy/decision`. |
| `preferences` and `roles` on `profile_update` / `PATCH /career/profile` | Refused (`422 validation`). Add or edit Decision items with `policy_add` / `POST /policy/decision/items` and `policy_update` / `PATCH /policy/items/{id}`; an agent's item is a proposal until the owner confirms it. |
| A `profile` with `preferences` or `roles` in `career_preview_import` / `career_import` (`POST /career/import/preview`, `POST /career/import`) | Refused (`422 import_validation`, naming the field). Remove them from the imported profile and add them as Decision items. |

The dashboard's Profile no longer shows **Target roles and preferences, kept
from earlier versions**; the texts are in **Policy → Decision**.

## What to change

- Call the `<resource>_<verb>` names; pass list filters, pages and read options
  inside `value`.
- Read and write the application's guidance as its pinned note.
- Send `expected_version` with every delete.
- Drop `availability` from job writes and read `signals.no_longer_listed`.
- Keep target roles and preferences in the policy's Decision section.
- After upgrading, open **Policy → Decision** to sort any item the upgrade
  copied (marked as copied when 0.23 removed the field).
