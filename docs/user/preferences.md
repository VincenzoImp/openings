# Preferences

Preferences hold what you want, in your own words. Your agent reads them when it
reviews jobs, writes documents and works with you, and asks you when they do not
cover a case. Nothing in them acts on its own: no job is dismissed and no
document changes automatically. Open them under **Library → Preferences**.

## Sections

| Section | Holds | Example |
|---|---|---|
| **What I'm looking for** | Roles, places, companies and conditions worth a look | "Data and platform roles, on site in Zurich or Basel, or remote within Europe." |
| **What I rule out** | What makes a job not worth applying to | "Agencies that hire for clients." |
| **Facts about me** | What employers ask about: eligibility, availability, notice, salary | "EU citizen with a Swiss B permit, valid until 2028-06-30." |
| **Writing rules** | How CVs and letters are written, for all documents, the CV or the letter | "Never volunteer weaknesses or missing skills." |
| **Working with me** | Instructions the agent follows | "Never contact an employer for me." |

Each statement is plain text (Markdown allowed, up to 2,000 characters), up to
200 per section. Writing rules are the one place for rules about documents;
a template keeps only its source, files, guidance and limits.

## Editing

Each section lists its statements. **Edit** a statement in place and save it,
**+ Add** one at the end, change the order with the arrows and **Delete** from
the `…` menu, which asks first. A Writing rule has **Applies to**: All, CV or
Letter. If the section changed in another session while you were editing, the
page says so, shows the latest list and keeps your text; save again.

## Settings

Two values are typed because Openings uses them itself:

- **Languages I speak** (in Facts about me): the jobs filter **Hide jobs
  requiring languages I don't speak** leaves out jobs whose required languages
  are all outside this list. It only filters the list; it never dismisses a job.
- **Count an application as no reply after [30] days** (under Following up):
  the no-reply period of
  [applications](applications.md#record-what-the-employer-did), from 1 to 365
  days.

## REST and MCP

| Operation | REST | MCP |
|---|---|---|
| Read the sections and settings | `GET /preferences` | `preferences_get` |
| Replace one section | `PUT /preferences/{section}` | `preferences_update` |
| Change a setting | `PATCH /settings` | `settings_update` |

The sections are `looking_for`, `ruled_out`, `facts`, `writing` and
`working_with_me`. `GET /preferences` returns each with its `items`, `version`,
`updated_at` and `updated_by` (`owner`, `agent:<token name>` or `system`), and
`settings` with `no_reply_days`, `spoken_languages` (ISO 639-1 codes) and their
own `version`.

A write replaces the whole section: read it, edit the list and send it back
with the version you read. A stale version returns `409 conflict` with
`details.current_version`; read again and merge. Items are `{"text": ...}`,
and in `writing` also `scope` (`all`, `cv` or `letter`):

```json
{
  "expected_version": 4,
  "items": [
    {"text": "Never volunteer weaknesses or missing skills.", "scope": "all"},
    {"text": "Three paragraphs, under 200 words.", "scope": "letter"}
  ]
}
```

```json
{"expected_version": 2, "no_reply_days": 45, "spoken_languages": ["en", "it"]}
```

Writes record `preferences_updated` events (section, version, number of
statements) and `settings_updated` events (changed names, version), never the
text. A prepared application freezes the sections with their versions; the
record export and backups include them. Synthetic Preferences to try are in
[`examples/preferences.json`](../../examples/preferences.json).

## Upgrades

In 0.24 Policy became Preferences: the upgrade moves every former item, the
general instructions and template rule statements into these sections, sets
the no-reply period and spoken languages from the matching items, and keeps
the originals in an archive beside the database
(`openings.pre-0.24-archive.json` for `openings.sqlite`). Workspaces older than
0.23 must be opened once with 0.23 first; release history is in
[CHANGELOG.md](../../CHANGELOG.md).
