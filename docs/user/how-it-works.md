# How it works

Openings is one workspace for one person's job search. Everything you do in the
dashboard can also be done by a script (the REST API) or by your AI agent (MCP),
with the same names. Only a few owner actions, such as the password, tokens and
restore, stay with you.

## The concepts

1. **Job.** A posting you might apply to: title, company, location, text and where it came from.
2. **Source.** A search, company careers page or RSS feed that collects jobs on a schedule. Jobs you add by hand have no source.
3. **Triage.** Where a job stands in review: **New**, **Shortlisted** or **Dismissed**. Dismissing keeps the job, remembers it and can be undone.
4. **Label.** A mark computed without a model: the posting's language, the languages it requires, a likely duplicate, or no longer listed. Labels describe and filter; they never dismiss.
5. **Application.** Your attempt to get one job. A job has at most one open application. Shortlisting a job starts it.
6. **Stage.** Where the application stands: **Shortlisted**, **Applied**, **Interview**, **Offer** or **Closed** (Accepted, Rejected, Not pursued or No reply).
7. **Ready.** Computed, never set by hand: a Shortlisted application whose required documents are complete and that no blocking requirement holds back.
8. **Document.** A CV, letter, set of form answers or other file for an application. A CV or letter is a PDF, with its LaTeX source if you have one. Each change is a new revision; a stored revision never changes.
9. **Requirement.** A condition from the employer, such as "no AI-written applications" or "references". A blocking one keeps the application from Ready until you resolve it.
10. **Reply.** What the employer did: interview, offer, rejection or other, with a date. Recording one also moves the stage.
11. **Profile and career entries.** Who you are, and your jobs, studies, publications and skills.
12. **Highlight.** One reusable sentence under a career entry. You approve it; a star means "always include in my CV".
13. **Template.** A CV or letter layout, with guidance and limits such as the number of pages.
14. **Preferences.** Five lists of plain statements: what you are looking for, what you rule out, facts about you, writing rules and how to work with you. Your agent reads them; nothing in them acts on its own.

## The daily loop

**New** jobs arrive, from your sources or by hand. You **shortlist** the ones you
want. For each, you or your agent **prepare** the CV and letter. When the
application shows **Ready**, you check it, send it on the employer's site and
choose **Mark applied**. Later you **record the reply**, or close the application
as **No reply**.

Only you mark an application applied. No agent, source or upload does.

## Who does what

| Surface | For | Contains |
|---|---|---|
| Dashboard | You, by hand | Everything you need to find, decide, prepare, send and track |
| REST API | Scripts and your own tools | All dashboard actions, plus the owner-only ones |
| MCP and skills | An external agent you talk to in its own chat | Everything the dashboard does, except owner-only actions |

Owner-only actions: the password, API tokens, restore, the records export, the
career import and downloading kept backups.

## Words

The word on screen is the word in REST, MCP and these pages: a job's **triage**
(New, Shortlisted, Dismissed), an application's **stage** (Shortlisted, Applied,
Interview, Offer, Closed), **Ready**, **CV** and **letter**, **career entry**,
**highlight**, **Preferences**, **reply** and **source**. The
[REST API](api.md#names) page lists the field names behind them.
