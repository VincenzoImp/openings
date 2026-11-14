# Getting started

This page takes you from nothing to your first application, by hand, without an
agent. [How it works](how-it-works.md) explains the words used here.

## Install

You need Docker with Compose v2. The host needs no Python, Node or TeX.

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
docker compose up -d
```

Check that it runs:

```bash
docker compose ps
curl --fail http://127.0.0.1:8080/health
```

Every setting has a default. To change one, copy `.env.example` to `.env` first
(see [Configuration](configuration.md)). To reach Openings from other devices,
see [Operations](operations.md#reach-it-from-other-devices).

## Set up your workspace

Open **http://127.0.0.1:8080** and choose an owner password of at least 10
characters (or set `OPENINGS_PASSWORD` in `.env` before the first start). A new
installation then opens the **setup guide**, four short steps about you:

1. **About you.** Your name, the roles you are after and where (saved as
   statements under Preferences, *What I'm looking for*), and the languages you
   speak. Only the name is required.
2. **Find jobs.** A search, prefilled from step 1, that you can **Test**
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

The navigation has three groups: **Today**, **Jobs** and **Applications** for the
daily work; **You** (Profile, Preferences, Templates) for what Openings knows
about you; **Workspace** (Sources, Settings) for the rest.

**Today** shows what is ready to send, what needs attention, applications waiting
for a reply and new jobs. When nothing needs you, it says so.

## Add your first job

1. Choose **Add job** (the **+** button, or `n`). Paste the job's URL, or enter
   the title, company and the whole posting. If a job with that address exists,
   it is shown instead of a copy. When a page cannot be read, paste the text
   yourself.
2. In **Jobs**, the **New** tab lists jobs waiting for a decision. Select one to
   read it beside the list. Choose **Shortlist** (`s`) to pursue it, or
   **Dismiss** (`d`) to set it aside; the next job is shown at once, every
   decision can be undone (`z`), and a dismissal's toast offers
   **Add reason**. Dismissed jobs stay under **Dismissed** and can be
   restored (`r`).

![Jobs to review beside the selected job, with its labels, posting and timeline](../images/jobs.png)

Shortlisting starts the job's application. Undoing it removes that application
while nothing has been added to it.

## Add a source

Jobs can also arrive by themselves. Under **Sources**, choose **Add source**: a
**Search** (a query and a place on LinkedIn, Indeed or Glassdoor), a **Company
careers page** or an **RSS feed**. **Test** shows the first results and saves
nothing. **Save** adds the source, and it is checked on the schedule.
[Jobs and sources](jobs-and-sources.md) explains every setting.

## Prepare your first application

You can do this without an agent or LaTeX. Have your CV and letter ready as PDFs.

1. Open **Applications** and select the application you just started. Its page
   says what is missing and has a slot for the CV and one for the letter.
2. Drop each PDF on its slot, or choose **Upload PDF**. If you built it from
   LaTeX, add the `.tex` source too.
3. If the employer sets conditions, such as a required reference, add them under
   **Requirements** and mark the ones that must be settled first as **Blocking**.
4. When both documents are stored and nothing blocks the application, the page
   becomes the **Ready** page and Today lists it under **Ready to apply**.
5. Choose **Download CV + Letter**, then **Apply on employer's site**.
6. Back in Openings, choose **Mark applied**. **Undo** is offered, and the next
   Ready application opens.

![The Ready page: before you send, the posting, the CV and the letter, and Mark applied](../images/ready.png)

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
each. Synthetic examples are in the [`examples/`](../../examples/README.md) folder.

## Optional: an agent

If you want an agent to triage jobs and write documents, follow
[Work with an agent](agents.md). Back up before you upgrade: see
[Operations](operations.md).
