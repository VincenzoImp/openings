# Dashboard design

Status: **proposed**, waiting for the maintainer's approval (owner checkpoint 2,
issue #150). It designs the dashboard for the product accepted in the
[redesign proposal](proposal-redesign.md); issue #135 implements it.

The design has three parts: the information architecture, a design system, and
static [prototypes](prototypes/index.html) of every main screen. Open
`docs/developer/prototypes/index.html` in a browser: the prototypes are plain HTML
with synthetic data, work offline, and have working tabs, themes and density.

## Principles

1. **Start from the owner's three questions.** What do I apply to, what did the
   agent do, what needs my decision. The first screen answers all three.
2. **The agent is visible.** Every change shows who made it. Runs and questions are
   places, not notes.
3. **One screen per job to be done.** Reviewing an application shows the posting,
   the CV and the letter together, with the actions that end the task.
4. **Structured data has a structured editor.** No JSON text boxes.
5. **Calm and dense.** Warm neutral surfaces, one accent, colour only for meaning,
   text always beside colour. Lists first, cards only for grouping.

## Information architecture

Navigation has three groups. On narrow screens a bottom bar holds Today,
Applications, Jobs and Activity; the rest is under More.

| Group | Screen | Purpose | Replaces |
|---|---|---|---|
| Work | **Today** | Ready to apply, needs your decision, since your last visit, waiting for a reply | Overview |
| Work | **Applications** | The pipeline with Ready as a stage; list and board; **Insights** tab | Applications, Overview funnel |
| Work | **Application review** | Posting, CV and letter side by side; download, mark applied or close; answers, requirements, timeline, inputs | The application drawer and its tabs |
| Work | **Jobs** | To review, Shortlist, Dismissed, All; signals; duplicates inside the job | Inbox, Shortlist, Possible duplicates |
| Work | **Activity** | Questions, runs with their reports, the timeline of all changes | New |
| Library | **Career** | Profile and the Career record with typed claim fields | Career |
| Library | **Policy** | Decision rules, eligibility, writing rules, facts | Profile metadata JSON, parts of Career |
| Library | **Templates** | Sources, typed rules, assets, preview | Templates |
| System | **Collection** | Sources, yield, runs and tasks, providers | Collection, tasks in Settings |
| System | **Settings** | Agent access and tokens, skills, backup, workspace | Settings |
| | **Onboarding** | First run: connect an agent, watch the record being built | New |

What changes for someone who knows 0.15:

- **Overview disappears.** Its funnel becomes the pipeline strip on Today and the
  Insights tab.
- **Inbox and Shortlist merge into Jobs.** In an agent-operated workspace the
  review queue belongs to the agent, and the page says so.
- **The application drawer becomes a page:** one review screen plus four
  secondary tabs (answers, requirements, timeline, inputs).
- **Ready is a stage** you can see and count, not a filter.
- **Possible duplicates** is no longer a separate list of hundreds of groups. A
  likely duplicate is a signal on the job, with the candidate beside it.
- **Tasks move** from Settings to Collection, next to the runs that created them.
- **Policy is new**, and Profile metadata is no longer edited as JSON.

## Screens

| Screen | Prototype | What to look at |
|---|---|---|
| Today | [today.html](prototypes/today.html) | The summary sentence; one primary action; questions answered in place |
| Application review | [review.html](prototypes/review.html) | Three panes; "before you send" banner; who wrote each revision; one pane at a time on a phone with a fixed action bar |
| Applications | [applications.html](prototypes/applications.html) | Stage chips; recording an employer response; Insights with a small-sample state |
| Jobs | [jobs.html](prototypes/jobs.html) | Signals as tags; a rule's dismissals with Restore; duplicate decision inside the job |
| Activity | [activity.html](prototypes/activity.html) | A run report; an interrupted run; questions tied to their subject |
| Career | [career.html](prototypes/career.html) | Typed claim fields; key/value editor for remaining metadata |
| Policy | [policy.html](prototypes/policy.html) | Statement lists; a rule that acts on a signal; staleness per section |
| Templates | [templates.html](prototypes/templates.html) | Typed limits and rule statements |
| Collection | [collection.html](prototypes/collection.html) | Yield per source |
| Settings | [settings.html](prototypes/settings.html) | Token kinds; a readable skill with local notes |
| Onboarding | [onboarding.html](prototypes/onboarding.html) | The agent's progress as a checklist |

Screenshots at 1440×1000 and 390×844 are in [prototypes/screens](prototypes/screens).
Regenerate them with `node docs/developer/prototypes/screenshots.mjs`; the script
also fails on a script error or horizontal overflow at five widths.

![Today](prototypes/screens/today-desktop-light.png)

![Application review](prototypes/screens/review-desktop-light.png)

## Design system

The tokens and components are in [prototypes/prototype.css](prototypes/prototype.css).
#135 moves them into the dashboard unchanged.

### Colour

Semantic tokens, with a light and a dark value each. Text pairs reach WCAG AA
(4.5:1) on every surface they are used on; the lowest ratios are listed.

| Token | Use | Light | Dark | Lowest contrast (light / dark) |
|---|---|---|---|---|
| `--bg`, `--surface`, `--card` | Shell, page, raised content | `#ebe8e0`, `#f6f4ee`, `#fffdf9` | `#1a1c17`, `#21231d`, `#292b24` | |
| `--ink` | Content | `#23241e` | `#ecece0` | 12.8 / 12.0 |
| `--ink-2` | Secondary text | `#5c5e54` | `#b9bcab` | 5.4 / 7.4 |
| `--ink-3` | Captions on surface or card | `#696b60` | `#9da18f` | 4.9 / 5.4 |
| `--accent` | Primary action, selection | `#4d6340` | `#b9cfa3` | 5.4 / 6.5 |
| `--ready` | Ready, approved, finished | `#3a6335` | `#a9d19b` | 5.7 / 7.1 |
| `--attention` | Deadline near, interrupted, empty | `#7a5200` | `#e6c27a` | 5.7 / 7.0 |
| `--danger` | Blocking, overdue, destructive | `#94483b` | `#e0a79a` | 5.2 / 6.0 |
| `--info` | Advice before an action | `#3d5a73` | `#a9c4dc` | 5.9 / 6.8 |
| `--agent` | Anything the agent did | `#5b4b8a` | `#c3b6ea` | 6.1 / 6.7 |
| `--control` | Border of buttons and inputs (needs 3:1) | `#85877a` | `#858972` | 3.1 / 3.0 |

0.15 fails this target in the light theme: secondary text is 4.0:1 on the page and
caption text 2.5:1. Caption text (`--ink-3`) is not used on soft backgrounds;
secondary text is used there.

Rules: one accent; colour never carries meaning alone (a tag always has text);
the agent colour is used only for attribution.

### Type, space and density

- **Type:** system sans for interface text, Georgia for page titles and large
  numbers, system monospace for source. Six sizes: 12, 13, 14 (body), 16, 20, 28 px.
  No font is downloaded: the dashboard works offline.
- **Space:** multiples of 4 px (4, 8, 12, 16, 24, 32, 48). Radius 8 px for cards,
  5 px for controls.
- **Density:** comfortable by default (44 px rows) and compact (36 px), chosen by
  the owner and remembered. Touch targets stay at least 44 px on narrow screens.
- **Layout:** one breakpoint at 860 px. Below it the sidebar becomes the bottom
  bar, columns stack, and side-by-side panes become a switch.

### Components

Button (primary, default, quiet, danger; two sizes), tag, count, card, list row,
table, tabs, segmented switch, field, switch, banner, actor chip, question,
statement list (policy items, rules, requirements), key/value editor, pipeline
strip, stat and rate bar, paper preview, split view with a detail panel, stepper,
fixed action bar, dialog, toast, empty and error states.

Each component is built once in #135 with its states (default, hover, focus,
disabled, loading, error) and its keyboard behaviour, and no page file exceeds
about 400 lines.

### Words

Short, concrete and direct: "6 applications are ready for you", not "Readiness
overview". Buttons name the result ("Mark applied", "Close 3 as no reply"). The
agent's text is shown as the agent's, with its name. Stages keep their names;
"Draft" is called Preparing, as today.

## Budgets

**Accessibility: WCAG 2.2 AA.**

- Automated checks (axe) on every screen, in both themes and at both widths, with
  no serious or critical finding. Run in CI with the browser tests.
- Keyboard: every action reachable and operable; focus visible; dialogs and the
  mobile navigation contain focus. The review flow has a keyboard-only test.
- A unit test asserts the contrast of every token pair in the table above.

**Performance**, measured in CI on a synthetic workspace of 25,000 jobs (5,000
before stage 4) and 500 applications:

| Budget | Target | 0.15.2 |
|---|---|---|
| Applications list, 200 rows, time to interactive after navigation | under 300 ms | not measured |
| Jobs to review, 200 rows with their signals, time to interactive | under 300 ms | not measured |
| JavaScript for the first screen, compressed | at most 110 kB | 126 kB (one bundle, 440 kB raw) |
| Any later screen's own JavaScript, compressed | at most 40 kB | part of the one bundle |
| Stylesheet, compressed | at most 15 kB | 12.4 kB |
| Long lists | virtualised above 100 rows | paginated |

The issue quoted 385 kB for the current bundle; it is 440 kB today. The budget is
set on compressed size per screen, with screens loaded on demand.

## Implementation stages for #135

Each stage ships on its own; old and new screens coexist until stage 7. Every
stage has browser tests on Chromium and WebKit at both widths, regenerated
documentation screenshots and a regenerated parity matrix.

| Stage | Content | Needs |
|---|---|---|
| 1. Foundation | Tokens and components, the new navigation around the existing pages, screens loaded on demand, accessibility checks and budgets in CI | |
| 2. Today and Activity | Home screen; questions, runs and timeline | #149, #160 |
| 3. Applications | Pipeline with Ready; the review-and-apply page; employer responses and Insights when available | #160; #151 for Insights |
| 4. Jobs | Triage tabs, bulk actions, duplicate decision inside the job; signals when available | #145, #166 for signals |
| 5. Library | Career with typed claim fields and the key/value editor; Policy; Templates with typed rules | #163 |
| 6. System | Collection with yield and tasks; Settings with token kinds and readable skills | #161, #166, #168 |
| 7. Onboarding and removal | First-run flow; the old pages and stylesheet are deleted; the parity matrix has no gap | #136 follows |

A stage whose backend issue is not ready ships with what exists and gains the rest
when that issue lands; the table says which parts those are.

### Implemented

**Stage 1, Foundation.**

- `frontend/src/design` holds the tokens (`tokens.css`, the single source, with
  the values of the table above), the element defaults, the shell styles and the
  core components: button, tag, count, card, list row, tabs, segmented switch,
  field, switch, banner, actor chip, empty state, action bar, dialog and toast.
  The remaining components of the list above are added by the stage that first
  uses them.
- `frontend/src/shell` holds the navigation (three groups; bottom bar and More
  sheet up to 860 px), the top bar with theme and density, the agent's status
  line, the routes and the screens loaded on demand.
- The pages written before the design system kept their own stylesheet,
  `frontend/src/legacy.css`, whose rules applied only inside `.legacy`. Each
  rebuilt page left that wrapper; stage 4 deleted the file with the last of
  them.
- Until its stage, Jobs opens the existing Inbox and Shortlist pages; `#jobs`
  is an alias. Every earlier route works.
- Checks: `npm run budget` (first screen, each later screen, stylesheet),
  axe on every screen in both themes at both widths, the contrast of every pair
  of the colour table, and a keyboard-only test of the shell. The performance
  check of the Applications list belongs to stage 3; the browser test server
  already takes `OPENINGS_E2E_JOBS` and `OPENINGS_E2E_APPLICATIONS` for it.

**Stage 2, Today and Activity.**

- **Today** (`pages/Today.tsx`, `pages/today/`) is the first screen; `#overview`
  is its alias and keeps its period (`#overview?since=…` opens
  `#today?since=…`). The summary sentence counts the stored Ready queue, the
  open questions, the Preparing applications blocked by a requirement and the
  applications in Applied longer than the no-reply period. That period is the
  number in the Policy decision item labelled "No reply" (the example policy
  says 45 days), and 30 days without one. Ready to apply lists the queue by
  deadline, then priority; Needs your decision answers questions in place;
  the pipeline strip counts Preparing (without the Ready ones), Ready, Applied,
  Interview and Offer, each a link to Applications. The prototype's "Close 3 as
  no reply" waits for the `no_response` outcome (#151); Record replies opens
  Applied filtered by `applied_until`. A blocked application links to its
  requirements; the prototype's "I will write it myself" and "Do not pursue"
  belong to the review page of stage 3, as does the Review link (it opens the
  application until then).
- **Since your last visit.** A visit lasts while Today keeps being opened and
  ends after 30 minutes without it (`pages/today/visit.ts`, unit-tested). The
  list counts from the end of the previous visit, so a reload or a look at a run
  changes nothing and it moves on only after a real absence. The browser keeps
  it in `localStorage` (`openings-today-visit`); without storage, or on the first
  visit, Today shows the last 7 days and says so. Runs count when their last
  activity is in the window (`runs?active_since=`); the collection line is
  derived from the newest 100 collection runs.
- **Progress**, the old Overview's numbers and stage table for a period, stays
  on Today as its last card until stage 3 moves it to Applications, Insights.
  The old SVG funnel, the "In progress" total and the "Add job" button of
  Overview are gone: Add job stays in Jobs and the pipeline strip counts the
  stages.
- **Activity** (`pages/Activity.tsx`, `pages/activity/`) has the tabs
  Questions (open, answered and withdrawn side by side), Requests (the form
  beside the list, filtered by state), Runs (the list beside the report,
  filtered by status; one pane at a time on a phone) and Timeline (by day, with
  filters by who, kind of record, period and run, 30 per page). Every earlier
  link works: `section=changes` opens the timeline, `state=answered` scrolls to
  the answered questions, `run=` opens a report.
- Backend reads added for these screens: `applied_since`/`applied_until` on
  the application list, `active_since` on the run list, `subject_types` on the
  change list, and `run_workflow` on changes, questions and requests.
- Components added to `frontend/src/design`: question with its answer controls
  (`Question.tsx`), pipeline strip and stats (`Pipeline.tsx`), filter chips and
  filter bar (`Chips.tsx`), report section, count list, day heading and
  timeline entry (`Report.tsx`), with their styles in `activity.css`. The
  Overview and Activity rules of `legacy.css` are deleted.
- The browser-test workspace (`backend/tests/today_fixtures.py`) adds ready
  applications with deadlines, a blocked one, sent applications of several
  ages, finished, interrupted and open runs with reports, questions with and
  without choices, requests in every state and collection runs.

**Stage 3, Applications.**

- **Applications** (`pages/Applications.tsx`, `pages/applications/`) has the
  tabs Pipeline and Insights. The pipeline counts six stage chips (Preparing
  without the Ready ones, Ready, Applied, Interview, Offer, Closed), searches,
  filters by readiness and outcome, sorts, and shows a list or a board. The list
  is an ARIA grid of rows (`role="table"`, `row`, `cell`) instead of a `<table>`,
  so that a row can stack into labelled cells under 860 px and still be read as
  a table; rows use `content-visibility: auto`. Selection acts in bulk: close as
  no reply, close with an outcome, reopen, mark ready, not ready, delete.
  **Record response** opens a form under the row; **Close N as no reply** lists
  the applications before closing them. Today's "Close N as no reply" and
  Waiting card use the `no_reply_due` filter and the shared no-reply period
  (`outcomes.no_reply_period`), so the period has one definition.
- **Review** (`pages/Review.tsx`, `pages/review/`) is the application's page,
  `#review?application=…&tab=…`: the posting, CV and letter side by side with
  their PDFs (one at a time on a phone), the place in the Ready queue in
  Today's order with Next, Before you send, Download CV and letter, Open the
  posting, Mark applied (refused with the reason when the application is no
  longer Ready) and Not pursuing. The tabs Answers (one control per question,
  never raw JSON), Requirements, Timeline (responses, changes, notes), Inputs
  (contexts, staleness), Documents and Details keep every capability of the old
  drawer. `#applications?application=…&detail=…` and the old `#overview?since=`
  link are rewritten by the shell (`canonicalHash`).
- **Insights** moved Progress there from Today. Rates come from
  `GET /insights`; a group below the minimum sample (5) shows its counts and
  "Too few to show a rate".
- Components added to `frontend/src/design`: grid table (`Grid.tsx`), rate bar
  (`Rate.tsx`), panes with a switch (`Panes.tsx`) and the response form
  (`ResponseForm.tsx`), with their styles in `data.css`. The old Applications
  page, its drawer and their rules in `legacy.css` are deleted.
- Checks: `e2e/applications.spec.ts` (keyboard review from Today to Mark
  applied, recording a response by keyboard, bulk no reply, board, old links)
  and the `chromium-performance` project (`e2e/performance.spec.ts`): 200 rows
  rendered in under 300 ms on 5000 jobs and 500 applications.

**Stage 4, Jobs.**

- **Jobs** (`pages/Jobs.tsx`, `pages/jobs/`) has the tabs **To review**,
  **Shortlist**, **Dismissed** and **All**, each a list beside the selected job
  (`Split`; one pane at a time under 860 px, with a switch back to the list).
  The address keeps the tab, the filters and the job: `#jobs?section=…&job=…`.
  A list has a search, a filter (Likely duplicate, No longer listed, Requires a
  language, Flagged by a rule, Signals pending, Text incomplete) and a sort; All
  adds **More filters** (company, place, source, work style, dates).
  Dismissed lists the most recently dismissed first, with chips by who
  dismissed (a policy rule, an agent, you, other) and a filter by rule. Rows
  show the signals as tags, with the languages the policy lists as "your
  languages"; a selection acts in bulk (up to 200 jobs, with the failures
  listed), and the dismissal dialog takes an optional reason. To review opens
  with who reviews it: the agent's last review-inbox run, what it changed and
  the jobs that arrived since (`AgentBanner.tsx`).
- **The selected job** (`Detail.tsx`) shows its actions (Shortlist, Start
  application, Return to review, Dismiss…, Restore, or the open application),
  the signals with the policy rules that matched, the dismissal with who, when
  and why, **Is this the same vacancy?** for a likely duplicate
  (`Duplicate.tsx`: the earlier job with confidence and reasons, **Same
  vacancy: merge** and **Different**), its attempts, the posting and the
  timeline of changes and notes (`JobTimeline.tsx`). **Details**
  (`JobMore.tsx`) folds away the maintenance: correct the job (`EditJob.tsx`,
  metadata in the key/value editor), sources with "No longer listed", possible
  copies at any confidence and merging with any job (`MergeDialog.tsx`), files,
  Ask your agent, and Forget. **Add a job** (`AddJob.tsx`) looks the address
  up first and opens the existing job instead of a copy.
- **Collection, Yield** (`pages/collection/Yield.tsx`) is the tab the stage 6
  layout left room for: per source and search, collected, to review,
  shortlisted, kept rate (withheld below 10), applied, answers and dismissed by
  whom, over 30 days, 90 days or all time; a notice names a source that collects
  much and keeps little; **Dismissed by your rules** opens each rule's
  dismissals in Jobs. Policy shows under each rule how many jobs to review it
  matches now (`policy/RuleMatches.tsx`).
- Old addresses are rewritten by the shell (`canonicalHash`): `#inbox`,
  `#shortlist`, `#inbox?queue=dismissed|all|duplicates`, the old drawer's
  `detail=` and `?job=` on any other screen open Jobs. Where each capability of
  the old pages went:

  | Old place | Now |
  |---|---|
  | Inbox queue | Jobs, To review |
  | Shortlist queue | Jobs, Shortlist |
  | Dismissed and All jobs queues | Jobs, Dismissed (by who, by rule, Restore) and All |
  | Possible duplicates tab: groups by confidence tier | The Likely duplicate signal filter; **Is this the same vacancy?** in the job; **Details**, **Possible copies and merging** at any confidence; `jobs_duplicates` over REST and MCP |
  | Filters: search, company, location, source, work style, dates, incomplete text | The list's search and filter (Text incomplete among the signals); **More filters** in All |
  | Bulk shortlist, dismiss, return, restore, forget | The selection bar of each tab; dismiss takes a reason |
  | Job drawer, Posting tab | The selected job's posting |
  | Job drawer, Notes and history | The job's timeline: changes and notes, add, edit, delete |
  | Job drawer, Files | **Details**, Files |
  | Job drawer, Edit (raw metadata JSON) | **Details**, Correct the job, metadata in the key/value editor |
  | Job drawer, Availability field | Removed from the dashboard: `availability` is deprecated, readable and writable over REST and MCP; the No longer listed signal replaces it |
  | Merge duplicate | **Same vacancy: merge**, or **Details**, Merge with another job |
  | Forget job | **Details**, Forget, and the selection bar |
  | Add job | **Add a job**, with the address looked up first |
  | Start application, open the application | The job's actions |
  | Ask your agent about a job | **Details**, Ask your agent |

- `design/jobs.css` holds what Jobs adds: the job list and its tags, detail
  sections, the duplicate decision, choices and the yield table. Jobs was the
  last page written before the design system: the old Inbox, Shortlist,
  duplicate and drawer pages, `ui.tsx`, `files.tsx` and `legacy.css` are
  deleted, and every screen renders in `.screen`.
- Checks: `frontend/tests/jobs.spec.ts` (a job shortlisted and another
  dismissed with a reason and restored, by keyboard only; a rule's dismissal
  named and restored; a duplicate declared different and another merged; a job
  added by address finds the existing one; bulk actions with a failure; signals
  and the yield; the pane switch on a phone; notes, start and forget), axe on
  every tab, the job, the dialogs and the selection bar, the overflow check
  from 360 to 1600 px, and the `chromium-performance` project: the jobs to
  review, 200 rows with their signals, interactive in under 300 ms on 25,000
  jobs.

**Stage 5, Library.**

- **Policy** (`pages/Policy.tsx`, `pages/policy/`) is new: the four sections as
  statement lists with add, inline edit, reorder by buttons, remove after
  asking, confirm, move to a section, the switch of a rule on a signal, the
  version of each section and the sections panel. A version conflict reads the
  section again and keeps the unsaved text in the open form. The banner
  "changed since N Drafts" of the prototype is not built: staleness by part
  (#144) names each changed policy item in an application's Inputs tab and under
  its **Inputs changed** tag in the list. A rule shows that signals arrive later
  (#166) instead of counts.
- **Career** (`pages/Career.tsx`, `pages/career/`) and **Templates**
  (`pages/Templates.tsx`, `pages/templates/`) are rebuilt and the old pages and
  their rules in `legacy.css` are deleted. Career has the Profile with typed
  fields, the record grouped by kind beside the entry editor, claims with their
  typed selection fields as controls, and **All claims** for search across
  entries. Templates has the list by kind and the tabs Source, Rules, Assets
  and Preview; Preview shows a PDF uploaded as an asset, because the workspace
  does not compile TeX. Free-form metadata and the free-form rest of template
  rules are edited as rows. `#career?section=…` and
  `#templates?template=…&section=…` open the matching part.
- Components added to `frontend/src/design`: statement list
  (`Statement.tsx`), key/value editor with a read-only tree for nested values
  (`KeyValue.tsx`, logic in `kv.ts`), split view with a pane switch on narrow
  screens (`Split.tsx`), and in `library.css` the table that stacks on narrow
  screens, the form grid, source text and record-editor pieces.
  `frontend/src/library` holds what the three screens share: the assets table
  with its file dialog, the confirmation dialog, the pager and a reader that
  always shows the latest record (`useFresh`).
- A rebuilt screen renders in `.screen` instead of `.legacy`
  (`shell/routes.ts`, `REBUILT`).

**Stage 6, System.**

- **Collection** (`pages/Collection.tsx`, `pages/collection/`) has the switch of
  scheduled collection above three tabs, one file each so a later tab (the yield
  of each source, #166) is one more entry and one more file: **Sources**
  (`Sources.tsx`, `SourceRow.tsx`: saved searches and company boards in one table
  filtered by kind and text, on/off, providers, schedule, last run with its
  problems, Run once or Stop run, Edit, Run with options, Remove; a selection kept
  across pages for switch on, pause, run, run with options, configure and remove,
  with the failures listed and "Use current versions"), **Runs and tasks**
  (`Runs.tsx`, `RunRow.tsx`, `TaskRow.tsx`: runs filtered by state and source;
  **Tasks** opens a run's provider tasks, its timing and the settings it froze as
  a read-only tree; **All tasks** filters by kind and job; stop and retry) and
  **Providers** (`Providers.tsx`: the request gate of each provider, on/off and
  spacing saved per provider, its state, request counts, last answer and error).
  **Add a search** and **Add a company board** open the source form under the
  list (`SourceEditor.tsx`, `SourceFields.tsx`, `Schedule.tsx`): every setting
  has its own control, so `config` is no longer edited as JSON; configuration
  the form has no control for is kept as it is. Preview, run-only limits and
  bulk configuration keep their behaviour. The Yield tab came with stage 4
  (#166).
- **Settings** (`pages/Settings.tsx`, `pages/settings/`) has the tabs **Agent
  access** (tokens with their kinds and the open run of each, revoke after
  asking, the token form with the kind as a switch and the secret shown once,
  the client configuration for Claude Code, Codex or JSON with the MCP and REST
  addresses), **Skills** (below), **Backup and restore** (sizes and the restore
  limit, backup download, records export, the restore form that needs a file and
  the typed word RESTORE) and **Workspace** (version, schema, public address,
  data size, retention, sign out, password). Parts that need owner authority are
  marked **Owner only** (`OwnerOnly.tsx`): tokens, restore and the password.
- **Skills** (`Skills.tsx`, `SkillDetail.tsx`, `SkillNotes.tsx`) lists the
  served skills beside the opened one: its local notes (#168) with the version
  and who wrote it, a counter of the 2,000 characters, earlier versions to use
  again, and the method sections of the workflow's recent runs to add; the
  shipped text read-only; its reference files and the shared ones its text links
  to, each read in a dialog. A run report's Method section links to the notes
  of its workflow with `from_run=`, which offers that method as a note.
- Old addresses are rewritten by the shell (`canonicalHash`): `#settings?section=collection`
  opens Collection, Providers; `#settings?section=activity` (with
  `activity_view=tasks`) opens Runs and tasks; `#collection?section=searches`
  and `companies` open Sources filtered by kind; `#skills` opens Settings,
  Skills. Where each capability of the old pages went:

  | Old place | Now |
  |---|---|
  | Collection: Saved searches and Companies tabs, cards | Collection, Sources (one table, filtered by kind) |
  | Collection: source dialog with the raw JSON of `config` | The source form under the list, one control per setting |
  | Collection: Run with options, Configure, bulk actions, batch errors | The same, from the row or the selection bar |
  | Collection: View progress | "Runs of this search" in the row's last run |
  | Settings, Collection: provider request settings | Collection, Providers |
  | Settings, Activity: collection runs, all tasks, run details with raw JSON | Collection, Runs and tasks; a run's frozen settings as a tree |
  | Settings, Agent access: endpoint, client configuration, guide, API links | Settings, Agent access, Connect an agent |
  | Settings, Agent access: skills by name | Settings, Skills, with text, files and local notes |
  | Settings, Agent access: tokens | Settings, Agent access, Tokens (revoke asks first) |
  | Settings, Workspace: backup, export, restore, storage | Settings, Backup and restore |
  | Settings, Workspace: version, retention, sign out, password | Settings, Workspace |
  | Settings, Workspace: Appearance | The theme and density switches of the top bar |

- `design/system.css` holds what these screens add: the collection switch,
  selected and nested table rows, wrapping source text, the local notes panel
  and the provider and token forms. The old Collection and Settings pages
  (`Companies.tsx`, `CollectionForms.tsx`, `Settings.tsx`) and their rules in
  `legacy.css` are deleted.
- Checks: `frontend/tests/system.spec.ts` (a search added, switched on, run once,
  stopped, its runs and tasks, removed; bulk configuration and run-only limits;
  the source and provider editors' conflict recovery; the Collection tabs and
  the collection switch by keyboard; tokens and their refusal of owner
  operations; backup, export and the guarded restore) and
  `frontend/tests/skills.spec.ts` (a local note saved in the dashboard appears in the
  skill an agent reads over MCP and REST; versions and a conflict; a reference
  file; a run's method added as a note; the notes saved by keyboard). The axe
  and overflow checks cover every new tab.

## Not decided here

- Charts beyond simple rate bars. Insights starts with tables and bars.
- Figures the prototypes had to invent: the number of sent applications below
  which a rate is withheld (5 in the prototype) and the restore limit as a share of
  free space. The backend issues decide them.
- Tables that become stacked blocks on narrow screens must keep their meaning for
  screen readers; #135 decides between ARIA roles and a list.
- A command palette and keyboard shortcuts beyond standard navigation.
- Notifications outside the dashboard (email, push).
