# Upgrading to 0.22

0.22 is the release of the redesign that changes the contract of REST, MCP and
stored data. The workspace upgrades itself when the server starts, in one
transaction; take a backup first. A restore of a backup from an earlier release
upgrades a copy, as before. A 0.22 workspace cannot be opened by an earlier
release: to go back, restore the backup you took before upgrading. Each section
says what changed for one area and what a client that used the old contract
does now.

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

### What the upgrade does to your data

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

### In the dashboard

The review page shows each CV and letter as its PDF, with a switch to the text
read from its source. In the Documents tab an open revision shows that text,
its note, the source and the PDF it was built from, and **Compare with revision
N** for the changes since the revision it replaces. **Add a document** and
**New revision** ask a CV or letter for its `.tex` source and its PDF. **Approve
with differences** is gone.
