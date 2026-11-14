# Examples

Synthetic files to try Openings with. Every name and fact in them is invented.
The server also serves them at `/api/v1/examples`.

| File | What it is | How to use it |
|---|---|---|
| `career.json` | Career entries of a fictional engineer | The body of the owner-only `POST /api/v1/career/import` |
| `preferences.json` | The five Preferences sections and the two settings | Each section's items are the body of `PUT /api/v1/preferences/{section}`; `settings` is the body of `PATCH /api/v1/settings` (add `expected_version`) |
| `cv.tex`, `letter.tex` | A one-page CV and a letter in LaTeX | **Templates › New template › Start from the example CV** (or letter) |
| `operator-workspace/` | A folder to run your AI agent from | See its [README](operator-workspace/README.md) |
