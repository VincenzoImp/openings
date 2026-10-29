# Dashboard design preview

Original, offline HTML/CSS/JavaScript prototype. All records are synthetic.
Open `dashboard/index.html` in a browser or serve the folder locally. The small
PDF fixture is copied from the existing synthetic LaTeX feasibility output.
No dependencies, external fonts, network requests or backend are required.

## Working interactions

- Seven sidebar destinations: Overview, Inbox, Applications, Companies, Career,
  Templates and Settings, with desktop/mobile navigation and light/dark appearance.
- Overview counts and Sankey use the synthetic application's recorded stages.
  Initial fixture: 6 submitted attempts, 3 interviews, 2 offers, 1 accepted,
  1 rejected after applying and 4 still active. One additional attempt is a draft.
- Inbox triage tabs, search/company/sort filters, Add job, job detail/edit/notes,
  save/dismiss/restore and permanent forget. URL imports are not fetched; a URL-only
  entry stays incomplete. Repeated manually added URLs preserve identity.
- Applications Kanban/list, drag-and-drop stage changes, editable stage select,
  document/answer/history drawers, example PDF preview/download, PDF upload,
  filled-source download and synthetic context export. No document generation.
- Companies pause/enable, filtered job navigation, add board configuration and
  explicitly simulated Run now. No actual ATS is contacted.
- Editable profile/narrative evidence, reusable claim approval, template defaults,
  general/template guidance and source editing. Relevant profile changes mark
  existing scores outdated; no inference runs.
- Optional scorer off/local/remote controls, rubric/settings, example MCP endpoint
  and agent brief. All are demo configuration; no endpoint is contacted.
- Local browser persistence and reset; exported demo data is JSON, not SQLite.

## Design decisions

Warm paper-like surfaces and serif page titles reference Dossier's editorial
character. Code/layout are original; no Dossier components or CSS were copied.
The dashboard emphasizes legible job rows, calm state indicators, document context
and a direct primary action. Business actions use text; icon buttons have labels.
The chart has a counts table, dialogs trap focus, and reduced-motion is supported.

## Deliberate prototype limits

This demonstrates information architecture and interactions, not production
API/MCP/auth/database/collection/scoring behavior. Uploads are browser demo data;
the source example is illustrative. History corrections and arbitrary stage jumps
are basic and must be specified precisely in production. Company/job URLs use
synthetic organizations. Source/score errors and every empty/loading state are not
fully modeled. No legacy import, internal AI chat, generation button, server
compiler, semantic search, email or calendar feature is included.

Syntax checked with Node `--check`. Root performs actual desktop/mobile browser
QA and screenshot review before integrating this preview into the main plan.
