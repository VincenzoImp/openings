# Dashboard

The dashboard is built for triage: get through new postings fast, keep the
ones you are pursuing in view, and keep the application material with the
job. Press `?` anywhere for the shortcut list.

## Views

| Key | View | What it shows |
|-----|------|---------------|
| `1` | Inbox | jobs in status `new`, by score; a dot marks postings first seen after your previous visit |
| `2` | Pipeline | one column per status from `shortlisted` to `withdrawn`; move cards with the keyboard or by dragging |
| `3` | Companies | configured sources with their active job counts, and every employer with a stored posting |
| `4` | Runs | every collection run: duration, totals, per-source counts, errors |
| `5` | System | statistics, score distribution, retention, blacklist, export, API token |

The Inbox toolbar filters by text, source and minimum score and sorts by
score, date, first seen, last update, company, title or salary. Filters are
sent to the API, so they work on the whole archive, not the loaded page.

## Job page

Open a job with `Enter` or a click. Three tabs:

- **Posting**: the description as markdown, the score breakdown (each matched
  category and its weight), source, dates, salary, links, the raw source
  payload.
- **Application**: attachments (drop files, pick the kind: CV, cover letter,
  form answers, other), form questions with your answers, free notes.
- **Activity**: the timeline: ingestion, status changes, labels, notes,
  attachments.

The header holds the status selector, labels, the link to the posting, and
blacklist and delete actions.

## Keyboard

| Key | Action |
|-----|--------|
| `j` / `k` | next / previous job |
| `Enter` | open the job page |
| `o` | open the posting in a new tab |
| `s` | shortlist |
| `a` | mark applied |
| `x` | blacklist (asks first) |
| `l` | edit labels |
| `/` | search |
| `n` | add a posting by hand |
| `←` / `→` | previous / next Pipeline column |
| `[` / `]` | move the job one status back / forward (Pipeline) |
| `Esc` | close a dialog, leave the job page |
| `?` | shortcut help |

## Access token

When the server sets `OPENINGS_API_TOKEN`, the dashboard asks for it once and
keeps it in the browser's local storage. Change or clear it in System.
