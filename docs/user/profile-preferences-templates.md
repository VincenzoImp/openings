# Profile, Preferences and Templates

The **You** part of the navigation holds what Openings knows about you. You can
leave all of it empty and apply by hand. It matters when an agent writes your
documents: the agent reads it, and nothing in it acts on its own.

## Profile and career entries

**Profile** shows your name, headline, place, contact, summary and links, then your
**Career record**: entries listed by kind. Choose an entry to edit it beside the
list. **Add an entry** starts one, **Import** adds entries from text or JSON
after a preview, and a second tab searches every highlight.

An **entry** holds stable facts: a kind (experience, project, course, education,
award, publication, fact, skill, language or other), a title, an optional
organization, dates, skill tags and an optional description. A **highlight** is one
reusable sentence under an entry:

| Entry | Highlight |
|---|---|
| Experience: Backend Engineer, Example Co | Reduced ingestion latency by 30%. |
| Education: MSc in Computer Science | Researched reliable stream processing. |
| Skill: Languages | Python, Go, SQL |

![The career record grouped by kind, with one entry open beside the list](../images/career.png)

A highlight is a draft until you **Approve** it; only approved highlights reach an
application. A star marks **Always include in my CV**. Dates are none, a single
date or a period (year and optional month; **Present** for an open end); unknown
dates stay empty. Skill tags are comma-separated, with duplicates removed.
Facts and narratives are context for an agent; highlights are wording it may
reuse, not the only wording it may use.

Every document revision records which entries and highlights it used. Editing an
entry later never changes a stored revision.

## Preferences

**Preferences** hold what you want, in your own words. Your agent reads them when
it reviews jobs, writes documents and works with you, and asks you when they do
not cover a case.

| Section | Holds | Example |
|---|---|---|
| **What I'm looking for** | Roles, places, companies and conditions worth a look | "Data and platform roles, on site in Zurich or Basel, or remote within Europe." |
| **What I rule out** | What makes a job not worth applying to | "Agencies that hire for clients." |
| **Facts about me** | What employers ask about: eligibility, availability, notice, salary | "EU citizen with a Swiss B permit, valid until 2028-06-30." |
| **Writing rules** | How CVs and letters are written | "Never volunteer weaknesses or missing skills." |
| **Working with me** | Instructions the agent follows | "Never contact an employer for me." |

Each statement is plain text (Markdown allowed, up to 2,000 characters), and a
section holds up to 200. **Edit** a statement in place, **+ Add** one, reorder with
the arrows, and delete from the `...` menu. A writing rule applies to **All**
documents, the **CV** or the **Letter**. If the section changed in another session
while you were editing, the page shows the latest list and keeps your text; save
again.

Writing rules live only here: a template keeps its layout, guidance and limits.
Working with me is the one place for standing instructions to your agent. Synthetic
examples are in [`examples/preferences.json`](../../examples/preferences.json).

### Settings

Two values are typed, because Openings uses them itself:

- **Languages I speak:** the Jobs filter **Hide jobs requiring languages I don't
  speak** uses it. It only filters; it never dismisses a job.
- **Count an application as no reply after [30] days:** from 1 to 365. See
  [Applications](applications.md#replies).

## Templates

A **template** is a CV or letter layout your agent fills with your facts and
writing rules. Choose **Add a template** to paste LaTeX source or load a `.tex`
file. Each has four tabs:

- **Source:** the LaTeX.
- **Guidance:** notes for the agent, and limits: **Pages**, **Bullets per entry**
  and **Bullet length**. Any other key, such as `engine` or `date_format`, is free
  text.
- **Assets:** files the source needs, such as a class file or a logo.
- **Preview:** a sample of the layout.

Mark one template per kind as the **default**. A one-page engineering CV and a
longer research CV can both exist. The templates in `examples/` (`cv.tex`,
`letter.tex`) are synthetic starting points.

![Templates, listed by kind, with the source of one open](../images/templates.png)

Openings never compiles LaTeX. Your agent compiles on its own machine and uploads
the PDF. If you write your own documents, you need no template.

## REST and MCP

| Action | REST | MCP |
|---|---|---|
| Read Preferences, settings, profile and templates | `GET /workspace/context` | `workspace_context` |
| Replace one Preferences section | `PUT /preferences/{section}` | `preferences_update` |
| Change a setting | `PATCH /settings` | `settings_update` |
| Update the profile | `PATCH /career/profile` | `profile_update` |
| Read or save career entries | `/career/batch` | `career_get`, `career_save` |
| Save highlights | `POST /career/highlights` | `highlights_save` |
| Read or save templates | `/templates` | `templates_get`, `templates_save` |

The sections are `looking_for`, `ruled_out`, `facts`, `writing` and
`working_with_me`. A write replaces the whole section with `{"expected_version": N,
"items": [{"text": "..."}]}` (writing items also take `scope`: `all`, `cv` or
`letter`). A stale version returns `409 conflict` with `details.current_version`;
read again and merge. The import of career entries is owner-only: it is a
dashboard and REST action with a preview, not an MCP tool.
