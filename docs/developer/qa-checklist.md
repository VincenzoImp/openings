# Dashboard QA checklist

A manual pass over every screen and every action before a release that changes
the dashboard. Repeat it on the synthetic workspaces only. Never use a real
workspace or a live installation.

The automated tests cover what stays put (layout fit, axe, keys of Jobs and
gestures). This pass catches what they don't: what a person sees, reads and
expects. File each defect as its own issue in the release's milestone, labelled
`bug` or `ui` (plus `product` when the behavior needs a decision). Give repro
steps, the expected and the actual result, and a screenshot of the demo
workspace. Add a Playwright test when it is cheap. A test for a defect that is
not fixed yet uses `test.fail` and names its issue (see `frontend/tests/qa.spec.ts`).

## Set up

Build the dashboard, then seed and serve the two workspaces of the screenshots,
each in its own temporary folder and on a free port:

```bash
npm --prefix frontend ci && npm --prefix frontend run build
D=$(mktemp -d)
uv run python backend/tests/dashboard_server.py --seed $D/demo/snap.sqlite --demo
uv run python backend/tests/dashboard_server.py --seed $D/empty/snap.sqlite --empty
uv run python backend/tests/dashboard_server.py --snapshot $D/demo/snap.sqlite --port 18731 &
uv run python backend/tests/dashboard_server.py --snapshot $D/empty/snap.sqlite --port 18732 &
```

Each seed prints a JSON line with an owner session cookie. Add it to the browser
for `127.0.0.1`, or sign in with the synthetic password in
`dashboard_server.py`. These servers collect nothing, and their reset endpoint
(`/__e2e__/reset`) restores the seed between runs. Stop both servers and remove
`$D` afterwards.

`npm --prefix frontend run screenshots` writes the light and dark images of
every screen at 1440 and 390 px to `frontend/screenshots/` for a first look.

## The matrix

Every screen below is checked across:

| Axis | Values |
|---|---|
| Width | 390 (phone), 768 (narrow pane: one side of a split at a time), 1280, 1440, 1728, 1920, 2560 px |
| Theme | Light and dark (Account menu or palette › Theme) |
| Input | Mouse; keyboard only (Tab, Shift+Tab, Enter, Esc and the shortcuts); touch at 390 px |
| Data | Demo workspace; empty workspace; a loading state (throttle the network); an error state (stop the server and act) |

At each width and theme, check that:

- the page never scrolls sideways, and no text is clipped without an ellipsis;
- tabs, toolbars and action bars show every control, or show that they scroll;
- a line that wraps never starts or ends with a separator ("·");
- focus is visible on every control and moves in reading order; Esc closes
  the topmost dialog or menu, and focus returns to what opened it;
- touch targets are at least 44 px at 390 px;
- dark mode keeps contrast on badges, tones, disabled buttons and charts.

## Shell

- [ ] Sidebar: every item; the counts on Jobs and Applications; the Add job
      tooltip; Search; the Account menu (theme, keyboard shortcuts, sign out).
- [ ] Phone: the bottom bar, More, and the top bar of each screen (title,
      Search, the screen's own actions). A pushed detail hides the bottom bar.
- [ ] Keys: `g t`, `g j`, `g a`, `g p`, `n`, `/`, ⌘K, `?`. The skip link is
      the first Tab stop.
- [ ] Palette: empty (Go to, Actions, Theme), a query with jobs and
      applications, no match, Enter on each kind of result, Esc.
- [ ] Toasts: Undo with ⌘Z, close, several in a row, readable in both themes.
- [ ] Sign-in: wrong password, then the right one; sign out from the menu.

## Today

- [ ] Each section: Ready to apply (Start applying), Needs attention, Waiting
      for a reply (Close as no reply, the row's Record reply and close, then
      Undo), New jobs (Go through them), the stage links (including a stage with 0).
- [ ] Empty workspace: the setup checklist and its three buttons.
- [ ] Caught up: nothing to do.

## Jobs

- [ ] New, Dismissed and All; search (`/`, Esc, Clear search); Filter (each
      facet, the language switch, the phone sheet); Sort.
- [ ] Keys: `j`/`k`, arrows, Enter, `x`, Shift+J, Shift+click, Esc, `s`, `d`,
      `r` on Dismissed, `e`, `o`, ⌘Z. The selection never jumps to a job you have not seen.
- [ ] Row hover actions; bulk toolbar (Shortlist, Dismiss, More, Clear);
      dismiss reason from the toast.
- [ ] Detail: Previous/Next and "n of N", Open posting, More (Correct details,
      Merge, Sources of this job, Forget permanently), Notes and history.
- [ ] Add job: empty (disabled), an address, posting text, More details, Cancel.
- [ ] Phone: tap to push, Back to list, swipe left and right, long press, action bar.
- [ ] A job opened from the palette or Add job shows in the right section.

## Applications

- [ ] Every stage tab and All, at every width; search; Filter; Sort; List and
      Stats (90 days, 12 months, All time).
- [ ] Keys: `j`/`k`, Enter, `x`, Esc; bulk Close and Set priority.
- [ ] Application page, one per stage:
  - Shortlisted: upload CV and letter (button and drop), requirements (add,
    check, remove, a very long one), Notes and history, More.
  - Ready: the ready queue (`[` `]`), Mark applied (⇧↵), Sent today › change
    the day, the Check, Posting, CV and Letter panes (PDF and Text), the
    "All sent" end page, Undo.
  - Applied and Interview: Record reply (R), notes (Edit), Show all changes,
    sent documents (open, download).
  - Closed: outcome, reopen from More.
  - More: Change stage, Deadline and priority, Required documents, Close,
    Not pursuing, Delete permanently (Cancel only).

## Profile, Preferences, Templates

- [ ] Profile: On this page links; Edit header and summary (Esc keeps the
      text); add, edit and delete an entry; approve a highlight; Import CV text
      (empty, sample, Preview); skills; empty workspace.
- [ ] Preferences: add, edit and delete a line in each section; Languages I
      speak; the hide-unspoken switch; writing rules with their CV/Letter tags.
- [ ] Templates: list and detail; New template (each choice); Preview, Source,
      Files, Limits; Upload a sample PDF; More; phone back.

## Sources and Settings

- [ ] Sources: Add source for each kind (empty Save shows the errors; do not
      press Test against a live site), edit, pause, delete (Cancel only),
      Checked every, Check all now, Recent checks, More about automatic checks.
- [ ] Settings › Account: Change password (mismatch, too short), Theme, Open
      setup guide, Sign out.
- [ ] Settings › API & agents: New token (Agent and Full access), copy dialog,
      revoke; the agent switch and copy button.
- [ ] Settings › Data: Download backup, Restore (Cancel only), Export, storage,
      posting history, automatic backups.
- [ ] Settings › Advanced: request limits (edit a value and leave the field).

## Setup (empty workspace)

- [ ] About you: Continue without a name, languages, Continue.
- [ ] Find jobs: a search and a single job link; Back, Skip.
- [ ] Your CV: paste and Read it, the example template, Skip, Done.
- [ ] Reload on each step.

## Last pass

2026-11, 0.28.0 (#317): findings #415-417, #421-425, all fixed.
