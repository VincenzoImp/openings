# Profile, career entries and highlights

The **Profile** is your CV material: a header (name, headline, location, email,
phone and links), a summary, and **career entries** with their **highlights**.
A template and your writing rules determine how they appear in an application
document. Your rules and preferences are not part of the Profile: they live in
[Preferences](preferences.md).

An **entry** holds stable facts: kind, title, optional organization, dates,
location, an optional description and skill tags. A **highlight** belongs to one
entry and holds reusable wording, one CV bullet. An entry can have no
highlights, one or several.

| Kind | Entry title | Organization | Example highlight |
|---|---|---|---|
| Experience | Backend Engineer | Example Co | Reduced ingestion latency by 30%. |
| Education | MSc in Computer Science | Example University | Researched reliable stream processing. |
| Publication | Measuring Public Data Pipelines | Example Conference | Evaluated 40 public datasets. |
| Skill | Languages | — | Python, Go, SQL |

## Reading and editing

**Profile** reads like a finished CV: the header, the summary, then
**Experience**, **Education**, **Projects** and **Other** (awards,
publications, languages and the other kinds), and the **Skills** of every entry
together. Empty fields are not shown. On a wide screen an **On this page** list
beside the CV jumps to each part; on a phone the same list is behind the
**Jump to** button.

Each block is changed on purpose. Point at it (or tap it on a phone) and choose
**Edit**: the block becomes its form, in place on a wide screen and as a
full-screen sheet on a phone. **Save** (⌘↵ or Ctrl+Enter) stores it, **Cancel**
(Esc) leaves it. One block is open at a time; opening another, cancelling or
leaving the page with unsaved changes asks first. **Add experience** (and the
add button of each part) opens an empty entry in its part. A new entry is placed
by its dates, newest first. **…** → **Delete permanently…** removes an entry with
its highlights and files after a dialog that lists them.

![Profile read as a CV, with experience, highlights and skills](../images/career.png)

## Highlights

A highlight is a draft until you approve it; only approved highlights reach an
application. One that is not approved yet shows **Not approved** and
**Approve**. A ★ means **Always include in my CV**: the highlight is in the CV
unless the job gives a reason to leave it out (the API field `always_include`).
In an entry's form you add, reword, approve, star and remove highlights, and
reorder them by dragging the handle or with its **Move up** and **Move down**.
Highlights you write in the dashboard are approved. Anything else an agent wants
to keep about a highlight goes in its `metadata` in the API; the dashboard does
not show or edit metadata. An entry's location is stored as `location` in the
entry's metadata.

Files attached to an entry (a certificate, a reference) are shown under it;
attach or remove them in its form.

## Import CV text

**Import CV text** reads pasted text or Markdown, or a dropped `.txt` or `.md`
file: headings name the parts (Experience, Education, Projects, Skills…), a
sub-heading or a bold line starts an entry, a line with dates gives its dates
and place, and bullets become its highlights. The preview shows the entries and
highlights found; nothing is stored until you choose **Add**. The header fills
only fields that are still empty. Your agent can also read a PDF CV for you.

## Dates and ordering

Each date has a year and an optional month. A start alone is a single date; an
end or **Present** makes a period. Unknown dates stay empty. Entry dates never
fall back to the record's modification date. Entries keep the order of their
`position`; highlights keep theirs.

## Skills

Skill tags associate capabilities with their supporting entries. Enter them with
commas or Enter; case-insensitive duplicates are removed while preserving the
first spelling and order. Tags do not infer proficiency or experience length.
You can also create Skill entries such as **Languages** or **Infrastructure**.

## API and agents

REST and MCP expose the same fields and validation. Entry fields `organization`,
`dates`, `skills` and `position` are structured fields, separate from free-form
`metadata`. Do not repeat them inside metadata. A highlight's `always_include` is
typed in the same way; other selection hints of an agent stay in metadata.

```json
{
  "kind": "experience",
  "title": "Backend Engineer",
  "organization": "Example Co",
  "dates": {"kind": "period", "start": "2023-09", "end": null, "current": true},
  "skills": ["Python", "SQL"],
  "narrative": ""
}
```

A single date uses `{"kind":"single","start":"2025"}`. Send `dates: null`
to clear dates in a versioned update. Omit unchanged fields. Highlights also expose
`position`; approved highlights can be cited by document revisions.

A document revision records the highlights and career entries it cites. Later edits
affect new revisions; existing revisions never change. Review generated wording
and files before recording a submission.

Target roles and what you rule out are statements in [Preferences](preferences.md).

If a block was saved elsewhere while you edited it, Save says **Changed
elsewhere** and keeps your draft: **Keep editing** saves your changes over the
newer version (fields you did not change keep their new values), **Reload**
shows the stored record instead.
