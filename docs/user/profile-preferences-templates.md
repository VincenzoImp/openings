# Profile, Preferences and Templates

Write down your career, your rules and your document layouts here, once and in
your own words. Openings holds them under **You** in the navigation, and your
agent reads them to decide on jobs and write your documents. Nothing in them acts
on its own, and you can leave all of it empty and apply by hand.

## Profile and career entries

**Profile** reads like a finished CV: a header (name, headline, location,
email, phone and links), a summary, then **Experience**, **Education**,
**Projects** and **Other**, and the **Skills** of every entry together. Empty
fields are not shown. On a wide screen **On this page** jumps to each part; on a
phone the same list is behind **Jump to**.

You change one block at a time, on purpose:

- **Edit:** point at a block (or tap it) and choose **Edit**. The block becomes
  its form, in place on a wide screen and as a full-screen sheet on a phone;
  **Save** (⌘↵) stores it and **Cancel** (Esc) leaves it. One block is open at a
  time, and leaving unsaved changes asks first.
- **Add:** **Add experience** (and the add button of each part) opens an empty
  entry, placed by its dates.
- **Delete:** **…** → **Delete permanently…** removes an entry after a dialog that
  lists its highlights and files.
- **Conflicts:** if a block was saved elsewhere meanwhile, Save says **Changed
  elsewhere** and keeps your draft: **Keep editing** saves your changes (fields
  you did not touch keep their new values), **Reload** shows the stored record.

**Import CV text** reads pasted text or Markdown, or a dropped `.txt` or `.md`
file. Headings name the parts, a sub-heading starts an entry, a line with dates
gives its dates and place, and bullets become its highlights. Nothing is stored
until you confirm the preview, and the header fills only empty fields. Your agent
can also read a PDF CV for you.

An **entry** holds stable facts: a kind (experience, project, course, education,
award, publication, fact, skill, language or other), a title, an optional
organization, dates, a location, skill tags and an optional description. A
**highlight** is one reusable sentence under an entry, for example:

| Entry | Highlight |
|---|---|
| Experience: Backend Engineer, Example Co | Reduced ingestion latency by 30%. |
| Education: MSc in Computer Science | Researched reliable stream processing. |
| Skill: Languages | Python, Go, SQL |

![The Profile read as a CV: header, summary, experience with highlights, skills](../images/profile.png)

A highlight is a draft until you **Approve** it, and your agent's new highlights
show **Not approved**. Only approved highlights reach an application. A ★ marks
**Always include in my CV**.

In an entry's form you add, reword, approve, star, remove and reorder highlights
(drag the handle, or use **Move up** and **Move down**). Highlights you write
there are approved. Dates are none, a single date or a period (year and optional
month; **Present** for an open end), and unknown dates stay empty. Skill tags
are comma-separated, with duplicates removed.

Facts and descriptions give your agent context. Highlights are wording your
agent may reuse, not the only wording it may use. Every document revision
records which entries and highlights it used, and editing an entry later never
changes a stored revision.

## Preferences

**Preferences** hold what you want, in your own words. Your agent reads them to
review jobs, write documents and work with you, and asks you when they do not
cover a case. Change a line in your Preferences, and your agent's next decisions
change with it.

| Section | Holds | Example |
|---|---|---|
| **What I'm looking for** | Roles, places, companies and conditions worth a look | "Data and platform roles, hybrid in Berlin or Lisbon, or remote within the EU." |
| **What I rule out** | What makes a job not worth applying to | "Agencies that hire for clients." |
| **Facts about me** | What employers ask about: eligibility, availability, notice, salary | "Needs visa sponsorship to work in the UK." |
| **Writing rules** | How CVs and letters are written | "Never volunteer weaknesses or missing skills." |
| **Working with me** | What your agent may do on its own, and how | "Never contact an employer for me." |

Each statement is a line of plain text (up to 2,000 characters), and a section
holds up to 200. To work with the lines:

- **Edit** a line in place by pointing at it.
- **Move** or **delete** one from its `...` menu, with **Move to** another
  section and **Delete** (with Undo).
- **Add** one with **+ Add**; Enter saves it and opens the next.
- **Reorder** them by dragging a line's handle, or with Alt+↑/↓.

A writing rule applies to **All** documents, the **CV** or the **Letter**. An
empty section shows two gray examples. If the section changed in another session,
the page says so and keeps your text.

![Preferences, each section as lines of text](../images/preferences.png)

Writing rules live only here, while a template keeps its layout, guidance and
limits. Working with me is the one place for standing instructions to your agent.
Synthetic examples are in [`examples/preferences.json`](../../examples/preferences.json).

### Settings

Two values are typed, because Openings uses them itself:

- **Languages I speak:** the link **Hide new jobs that require another language**
  opens that Jobs filter and says how many new jobs it would hide. The filter
  never dismisses a job.
- **Count an application as no reply after [30] days:** from 1 to 365. See
  [Applications](applications.md#replies).

## Templates

A **template** is your own CV or letter layout in TeX, which your agent fills
with your facts and writing rules. Start from the example CV or letter (the
synthetic `cv.tex` and `letter.tex` in `examples/`), or upload a `.tex` file.
Each template has four tabs:

- **Preview:** a sample PDF you upload under Files.
- **Source:** the LaTeX, with line numbers; **Edit source** to change it.
- **Files:** what the source needs, such as fonts, images or a class file.
- **Limits:** **Pages**, **Bullets per entry** and **Bullet length**. Other rules,
  such as `engine`, and the template's guidance are set through the API.

Mark one template per kind as the **default**. The `...` menu renames,
duplicates, downloads the source or deletes the template permanently. A one-page
engineering CV and a longer research CV can both exist.

![Templates, listed by kind, with one open on Preview](../images/templates.png)

Openings never compiles LaTeX. Your agent compiles on its own machine and uploads
the PDF. If you write your own documents, you need no template.

## Use them from REST and MCP

| Action | REST | MCP |
|---|---|---|
| Read Preferences, settings, profile and templates | `GET /workspace/context` | `workspace_context` |
| Replace one Preferences section | `PUT /preferences/{section}` | `preferences_update` |
| Change a setting | `PATCH /settings` | `settings_update` |
| Update the profile | `PATCH /career/profile` | `profile_update` |
| Read or save career entries | `GET`, `POST /career/batch` | `career_get`, `career_save` |
| Save highlights | `POST /career/highlights/batch` | `highlights_save` |
| Read or save templates | `GET /templates/{template_id}`, `POST /templates/save` | `templates_get`, `templates_save` |

The sections are `looking_for`, `ruled_out`, `facts`, `writing` and
`working_with_me`. A write replaces the whole section with `{"expected_version": N,
"items": [{"text": "..."}]}`, and writing items also take `scope` (`all`, `cv` or
`letter`). A stale version returns `409 conflict` with `details.current_version`;
read again and merge. The import of career entries is owner-only, a dashboard
and REST action with a preview, not an MCP tool.
