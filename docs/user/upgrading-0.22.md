# Upgrading to 0.22

0.22 is the breaking group of the redesign: it changes stored data and some REST
and MCP shapes. The database upgrades itself to schema 13 when 0.22 first opens
it, in one transaction; a release before 0.22 cannot open the upgraded file, so
make a backup first. Each section below lists what changed, what the upgrade
does and what scripts and agents must change.

## Timeline and notes (#165)

Free text lived in three places: job notes, application notes and the separate
`note` field of an application. Now a job and an application each have one
**timeline**: their notes and recorded changes in one list, with the scope of
each entry, filters and pages. The application's `note` field becomes the
application's **pinned note**.

### What the upgrade does

- Notes gain `run_id` (the run their author had open), `pinned_at` and `origin`
  (`manual`, or `upgrade` for a note the upgrade copied).
- Each application whose `note` is not empty gets one pinned note on that
  application with exactly the same text, byte for byte; the upgrade checks this
  before it continues. Its author and run are those of the last recorded change
  that set the text (the last update naming the `note` field, else the
  application's creation); a change recorded before 0.17 has no author, and the
  note reads "unknown (before 0.17)". Its time is the time of that change, else
  the application's last change.
- The `note` column of `applications` is then dropped. Nothing else changes, and
  the upgrade records no change of its own.
- Frozen contexts are not touched: a context frozen before 0.22 keeps the
  application note it froze, byte for byte. New contexts freeze the pinned note
  in the same places (`application.note` and `instructions.application_note`).
- Restore accepts a backup of schema 5 to 13; an older one is upgraded the same
  way on a copy, and the uploaded file is not changed.

### Dashboard

- The review page's **Timeline** tab shows the employer responses, then one
  list of the application's notes and changes and its job's (marked **Job**),
  with filters by kind (notes, changes, responses), by who (you, an agent, the
  system, not recorded), by scope and by period. Notes are added, pinned,
  edited and deleted there.
- The job's page shows the same timeline for the job and all its applications
  (application entries are marked **Application**).
- Under **Details**, the "Application note and writing guidance" field is now
  the **Pinned note** editor: save it, or unpin it (the note stays in the
  timeline).

### REST and MCP

| Before | 0.22 |
|---|---|
| — | `GET /jobs/{id}/timeline`, `GET /applications/{id}/timeline`, MCP `timeline_get(job_id \| application_id, value)`: notes and events in one list, pinned first, then newest first; filters `kinds` (`note`, `event`, `response`), `who` (`owner`, `agent`, `system`, `unknown`), `scope` (`job`, `application`), `since`, `until`; `limit`, `offset`; `counts` by kind. REST and MCP return identical entries. |
| — | `POST /notes/{id}/pin`, MCP `note_pin`: `{"expected_version", "pinned"}`. At most one pinned note per job and per application; pinning another unpins it. |
| `POST /jobs/{id}/notes`, `note_add`: `body`, `application_id` | Also `pinned`. |
| A note: `id`, `job_id`, `application_id`, `body`, `version`, `created_at`, `updated_at`, `author` | Also `scope`, `run` (`id`, `workflow`), `pinned`, `pinned_at`, `origin`. `notes_list` lists pinned notes first. |
| `application.note` on reads | Still returned, **deprecated**: the pinned note's text, or `""`. Read `pinned_note` (the note, or null) instead. |
| `note` on `application_create` / `POST /applications` | Still accepted, **deprecated**: a non-empty value creates the pinned note. |
| `note` on `application_update` / `PATCH /applications/{id}` | Still accepted, **deprecated**: it edits the pinned note, adds one when there is none, or unpins it when empty. It no longer changes the application's `version` and records `note_added`, `note_edited` or `note_unpinned` instead of `application_updated`. |
| `q` on the application list searched the `note` field | It searches the pinned notes. |
| — | Changes `note_pinned` and `note_unpinned` (payload: `version`, and `replaced_by` when another note took the pin). |

`application_history` and `GET /applications/{id}/events` still return the
application's events alone. Event payloads still hold identifiers, field names
and versions, never text.

### What to change

- Read `pinned_note` instead of `note`; write guidance with `note_add` (with
  `application_id` and `pinned: true`), `note_update` and `note_pin`. The
  deprecated `note` field is removed in 0.23.
- Agents read `timeline_get` instead of combining `notes_list` and
  `application_history`, and write their findings as ordinary notes: the
  pinned note is the owner's standing guidance. The shipped skills do this.
