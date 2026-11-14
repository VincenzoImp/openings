# Getting started

This page takes you from nothing to your first application, by hand, without an
agent. [How it works](how-it-works.md) explains the words used here.

## Install

You need Docker with Compose v2. The host needs no Python, Node or TeX.

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
cp .env.example .env
docker compose pull
docker compose up -d --no-build
```

Open **http://127.0.0.1:8080** and choose an owner password of at least 10
characters (or set `OPENINGS_PASSWORD` in `.env` before the first start). To reach
Openings from other devices, see [Operations](operations.md#reach-it-from-other-devices).

## Set up your workspace

Open `http://127.0.0.1:8080` and choose an owner password of at least 10
characters (or set `OPENINGS_PASSWORD` in `.env` before the first start). A new
installation then opens the **setup guide**, four short steps about you:

1. **About you.** Your name, the roles you are after and where (saved as
   statements under Preferences, *What I'm looking for*), and the languages you
   speak. Only the name is required.
2. **Find jobs.** A saved search, prefilled from step 1, that you can **Test**
   before you save it; or one job added by its link.
3. **Your CV.** Paste your CV text and add the career entries read from it, or
   start from the example CV template.
4. **Done.** How every day works, and connecting an AI agent, which is
   optional: Openings has no AI of its own.

Find jobs and Your CV can be skipped. Until the workspace has a name and what
you look for, a job or a source, and a career entry or template, Today shows a
three-item **setup checklist** and the sidebar a **Finish setup** link. Both
are read from the workspace, so every browser shows the same state.

![The setup guide: About you, the first of four steps](../images/setup.png)

## Find your way

The navigation has three parts:

**Today** is the first screen: a greeting with one line of counts, then

- **Ready to apply:** the Ready applications, closest deadline first, with the
  priority as a glyph and the deadline in colour when it is near.
  **Start applying** opens the first one.
- **Needs attention:** Shortlisted applications due within a week that are not
  Ready, and Ready ones with an open requirement, each naming what is missing.
- **Waiting for a reply:** applications sent longer ago than the no-reply period
  (Preferences, 30 days unless you change it). On a row, **Record reply** (`r`)
  or **Close as no reply** (`c`); **Close all as no reply** closes them
  together. Closing is undone from the toast. Nothing closes by itself.
- **New jobs:** how many, the newest three and **Go through them**.
- The count of applications in each stage, each a link to its list.

When nothing needs you, Today says so.

## Add your first job

1. Choose **Add a job**. Paste the job's URL, or enter the title, company and the
   whole posting. If a job with that address exists, it is shown instead of a copy.
   When a page cannot be read, paste the text yourself.
2. In **Jobs**, the **New** tab lists jobs waiting for a decision. Select one to
   read it beside the list. Choose **Shortlist** to pursue it, or **Dismiss...**
   to set it aside with an optional reason. Dismissed jobs stay under
   **Dismissed** and can be restored.

![Jobs to review beside the selected job, with its signals, posting and timeline](../images/jobs.png)

Shortlisting starts the job's application. Undoing it removes that application
while nothing has been added to it.

## Add a source

Jobs can also arrive by themselves. Under **Sources**, choose **Add a search**
(a query and a place on LinkedIn, Indeed or Glassdoor) or **Add a company board**,
then **Preview results**. A preview saves nothing. Save the source and turn its
schedule on: new sources start paused. [Jobs and sources](jobs-and-sources.md)
explains every setting.

## Prepare your first application

You can do this without an agent or LaTeX. Have your CV and letter ready as PDFs.

1. Open **Applications** and select the application you just started. It opens
   on its own page: the posting, a slot for the CV and a slot for the letter.
2. In each slot, choose **Upload PDF**. Enter a title and choose the PDF. If you
   built it from LaTeX, add the `.tex` source too.
3. Open the **Requirements** tab if the employer sets conditions, such as a
   required reference. Add them and mark the ones that must be settled first as
   **Blocking**. Use **Answers** for the questions on the application form.
4. When both documents are stored and nothing blocks the application, the page
   says it is **Ready** and Today lists it under **Ready to apply**.
5. Choose **Download CV and letter**, then **Open the posting** and apply on the
   employer's site.
6. Back in Openings, choose **Mark applied**. You have six seconds to **Undo**.
   The next Ready application opens.

![The review page: the posting, the CV and the letter with their PDFs, and Mark applied](../images/review.png)

When the employer answers, choose **Record reply**, say what happened and give the
date. After the no-reply period (30 days unless you change it in
[Preferences](profile-preferences-templates.md#settings)) Today lists the
silent ones, and you can close them as **No reply**. Nothing closes by itself.

[Applications](applications.md) has the details.

## Fill in your record

Under **You**, add your **Profile** and career entries, state what you want in
**Preferences**, and add a CV and letter **Template** if an agent will write your
documents. None of this is needed to apply by hand.
[Profile, Preferences and Templates](profile-preferences-templates.md) explains
each. Synthetic examples are in the `examples/` folder.

## Optional: an agent

If you want an agent to triage jobs and write documents, follow
[Work with an agent](agents.md).

## Check that it runs

```bash
docker compose ps
curl --fail http://127.0.0.1:8080/health
```

Back up before you upgrade: see [Operations](operations.md).
