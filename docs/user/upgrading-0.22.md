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

## Documents (#164)

A CV or letter revision (`kind` `resume` or `cover_letter`) is now its uploaded
`.tex` source and the PDF built from it, the claim and Career entry ids it cites
and an optional note. It no longer stores free-form `content`: the server reads
its text from the source, without a TeX runtime, for review, search and the
comparison between revisions. The structured content and the attached source
used to be two copies of one text that drifted apart; the check that found the
drift afterwards, and its override, are gone with it. Form answers (`answers`)
and `other` documents keep structured `content`: there the structure is the
document.

### What the upgrade does

- Every revision keeps its id, title, chain (`previous_id`), frozen context,
  review state, version and dates, and every file its id, bytes, SHA-256, name
  and media type. Approved revisions stay approved with the same files.
- A CV or letter's `content` moves, unchanged, to `legacy_content`, which is
  read-only; `content` becomes empty. Empty content (`{}`) becomes no legacy
  content. Nothing is deleted.
- The claim and Career entry ids that content cited (`claim_ids`, and
  `evidence_ids` or `knowledge_ids`) are copied to the revision's `claim_ids`
  and `knowledge_ids`.
- The text of every revision with a `.tex` source is derived from that source
  and stored. A revision with several sources (possible before 0.22) gets the
  text of each, in file-name order.
- Files gain `source_sha256`, which stays empty for every existing file: a PDF
  uploaded before 0.22 did not name its source.

On a synthetic workspace of 1,000 applications with 4,000 CV and letter
revisions and about 8,000 revision files, on a laptop, the step took 0.8 s; a
small host takes several times longer.

### For clients that wrote `content`

| Before 0.22 | From 0.22 |
|---|---|
| `documents_create` / `POST /documents` with `content` for a CV or letter | Create the revision without `content`; sending it is refused with `422 content_not_accepted`. Then upload its `.tex` source and its PDF. |
| Evidence ids inside `content` (`evidence_ids`, `claim_ids`) | `claim_ids` and `knowledge_ids` on the revision, checked against its frozen context (or, without one, against existing Career entries and approved claims). |
| — | `note`: an optional note on the revision (at most 5,000 characters). |
| PDF and source uploaded in any order, any number | Upload the one `.tex` source (UTF-8) first, then the one PDF, whose reservation names `source_sha256`, the SHA-256 of that source. |
| `content` in `documents_get` / `GET /documents/{id}` | `text`, derived from the source (null without one), `source_sha256`, `claim_ids`, `knowledge_ids`, `note`; `legacy_content` for content saved before 0.22, else null. Form answers still return `content`. |
| `documents_consistency` / `GET /documents/{id}/consistency` | Removed. `documents_compare` / `GET /documents/{id}/comparison` compares the text of two revisions line by line. |
| `allow_content_mismatch` on `documents_review`, `409 content_mismatch` | Removed; sending the field is refused (`422`). A CV or letter is approved only with its source (`409 source_required`) and its PDF (`409 pdf_required`). |
| `q` on `documents_list` searched titles | `q` searches titles, notes and the derived text. |
| File records | Also return `source_sha256` (null for every file but a PDF that named its source). |

New refusals of an upload to a CV or letter revision:

| Code | Meaning |
|---|---|
| `422 source_required` | The PDF reservation has no `source_sha256` |
| `409 source_required` | The revision has no source yet: upload it first |
| `409 source_mismatch` | `source_sha256` is not the revision's source; compile that source, or create a new revision for the other one |
| `409 source_exists`, `409 pdf_exists` | The revision already has its source or PDF; a changed document is a new revision |
| `422 source_encoding` | The source is not UTF-8 |
| `422 pdf_media_type` | A `.pdf` sent with another media type |
| `422 source_sha256` | `source_sha256` on a file that is not a PDF |

The agent workflow becomes: `documents_create` (title, context, `previous_id`,
`claim_ids`, `knowledge_ids`, `note`), `files_reserve_upload` for `cv.tex` and
the raw PUT, `files_reserve_upload` for `cv.pdf` with `source_sha256` and the
raw PUT, `documents_get` to read the derived `text`, then `documents_review`.
The shipped skills `prepare-shortlist` and `openings-workspace` describe it.

### Revisions saved before 0.22

A draft CV or letter that had only content and no source keeps it as
`legacy_content` but cannot be approved: have the agent save a new revision
with its source and PDF. A draft with a source and a PDF can still be approved;
its PDF shows that it named no source. In the dashboard, an open revision shows
the content saved with it before 0.22 under a closed heading, read-only.

### Dashboard

The review page shows each CV and letter as its PDF, with a switch to the text
read from its source. In the Documents tab an open revision shows that text,
its note, the source and the PDF it was built from, and **Compare with revision
N** for the changes since the revision it replaces. **Add a document** and
**New revision** ask a CV or letter for its `.tex` source and its PDF. **Approve
with differences** is gone.
