# Getting started

Go from nothing to your first application here, by hand and without an agent.
You need Docker, and the host needs no Python, Node or TeX.
[How it works](how-it-works.md) explains the words used here.

<!-- quick-start: README repeats these blocks; dockerhub.md carries the demo, run and Compose lines (test_docs.py) -->

## Look first

The demo is a disposable workspace of fictional data. It contacts no job site
and is deleted when it stops (Ctrl+C):

```bash
docker run --rm -p 127.0.0.1:8080:8080 vincenzoimp/openings demo
```

The demo prints a sign-in link that works once, an agent token with its `export`
line, and the lines that connect Claude Code and Codex. From a clone,
`uv run openings demo` does the same.

## Use it

One command runs Openings and keeps your workspace in the `openings` volume:

```bash
docker run -d --name openings -p 127.0.0.1:8080:8080 -v openings:/data --read-only --tmpfs /tmp --restart unless-stopped vincenzoimp/openings:latest
```

Or use Docker Compose v2, in a folder of its own. The Compose file adds CPU and
memory limits and log rotation. It pins the minor release, such as `0.28`, so
updates bring that release's fixes:

```bash
curl -fsSLO https://raw.githubusercontent.com/VincenzoImp/openings-job-search/main/docker-compose.yml && docker compose up -d
```

Settings go in a `.env` file beside it, as [Configuration](configuration.md)
lists. Check that Openings runs with `curl -fsS http://127.0.0.1:8080/health`.

## Find the setup code

Until an owner password exists, each start prints a one-time **setup code** in
the log. The setup page asks for it, so nobody else on your network can claim
the workspace first. Read it with one of these:

```bash
docker logs openings            # with docker run
docker compose logs openings    # with Docker Compose
```

The demo needs no code. If you set `OPENINGS_PASSWORD` before the first start,
no code is printed and that password is the owner's.

## Use another port

When port 8080 is taken, map another host port. Then tell Openings the address
that agents and upload links use:

```bash
docker run -d --name openings -p 127.0.0.1:18080:8080 -v openings:/data \
  -e OPENINGS_PUBLIC_URL=http://127.0.0.1:18080 \
  --read-only --tmpfs /tmp --restart unless-stopped vincenzoimp/openings:latest
```

With Compose, the address follows the port, for example:

```bash
OPENINGS_PORT=18080 docker compose up -d
```

## Run it on a server or NAS

Publish the port on the network, and set the address other devices use. Here
that address is `http://nas.local:8080`:

```bash
docker run -d --name openings -p 8080:8080 -v openings:/data \
  -e OPENINGS_PUBLIC_URL=http://nas.local:8080 \
  --read-only --tmpfs /tmp --restart unless-stopped vincenzoimp/openings:latest
```

With Compose, put these lines in `.env`, then run `docker compose up -d`:

```dotenv
OPENINGS_BIND=0.0.0.0
OPENINGS_PUBLIC_URL=http://nas.local:8080
```

Opened from an address the public URL does not cover, the dashboard names the
value to set. Claim the workspace with the setup code right away. Put HTTPS in
front before you reach it from outside your home network;
[Operations](operations.md#reach-it-from-other-devices) has a Caddy and a
Traefik example.

<!-- /quick-start -->

## Set up your workspace

Open **http://127.0.0.1:8080**, enter the setup code and choose an owner password
of at least 10 characters. A new installation then opens the **setup guide**, four
short steps about you:

1. **About you.** Your name, the roles and places you are after (saved under
   Preferences, *What I'm looking for*) and the languages you speak. Only the
   name is required.
2. **Find jobs.** A company's careers page, with **Title must include**
   prefilled from your roles; a LinkedIn search (with a country, Indeed and
   Glassdoor too); or one job by its link. **Test** shows what each finds.
3. **Your CV.** Paste your CV text and add the career entries read from it, or
   start from the example CV template.
4. **Done.** How a day goes, and how to connect an AI agent, which is optional.

You can skip Find jobs and Your CV, and the guide resumes at the first step not
done. Until setup is complete, Today shows a three-item **setup checklist** and
the sidebar a **Finish setup** link.

![The setup guide: About you, the first of four steps](../images/setup.png)

## Find your way

The navigation has three groups:

- **Today**, **Jobs** and **Applications** for the daily work;
- **You** (Profile, Preferences, Templates) for what Openings holds about you;
- **Workspace** (Sources, Settings) for the rest.

**Today** lists what is ready to apply, what needs attention, applications
waiting for a reply and new jobs. When nothing needs you, it says so.

## Add your first job

1. Choose **Add job** (the **+** button, or `n`). Paste the job's URL, or enter
   the title, company and the whole posting. If a job with that address exists,
   Openings shows it instead of making a copy. When a page cannot be read, paste
   the text yourself.
2. Open **Jobs › New** to see the jobs waiting for a decision. Select one to read
   it beside the list.
3. Choose **Shortlist** (`s`) to pursue it, or **Dismiss** (`d`) to set it aside.
   The next job opens at once, and `z` undoes any decision. A dismissal's toast
   offers **Add reason**.
4. Find dismissed jobs under **Dismissed**, and **Restore** (`r`) any of them.

![Jobs › New beside the selected job, with its labels, posting and timeline](../images/jobs.png)

Shortlisting starts the job's application. Undoing the shortlist removes that
application while nothing has been added to it.

## Add a source

Sources bring in jobs by themselves. Under **Sources**, choose **Add source** and
pick a kind:

- a **Search** (a query and a place on LinkedIn, Indeed or Glassdoor);
- a **Company careers page**;
- an **RSS feed**;
- **HN Who is hiring**.

**Test** shows the first results and saves nothing. **Save** adds the source;
Openings checks it at once, then on the schedule.
[Jobs and sources](jobs-and-sources.md) explains every setting.

## Prepare your first application

You need no agent and no LaTeX for this. Have your CV and letter ready as PDFs.

1. Open **Applications** and select the application you just started. Its page
   says what is missing, with a slot for the CV and one for the letter.
2. Drop each PDF on its slot, or choose **Upload PDF**. If you built it from
   LaTeX, add the `.tex` source too.
3. Add the employer's conditions, such as a required reference, under
   **Requirements**. Mark the ones to settle first as **Blocking**.
4. When both documents are stored and nothing blocks the application, the page
   becomes the **Ready** page. Today lists it under **Ready to apply**, best
   first: priority, then deadline.
5. Choose **Download CV + Letter**, then **Apply** to open the employer's site in
   a new tab, and send the application there.
6. Back in Openings, choose **Mark applied**. The toast offers **Undo**, and the
   next Ready application opens.

![The Ready page: the posting, the CV and letter as PDFs, Apply and Mark applied](../images/ready.png)

When the employer answers, choose **Record reply**, say what happened and give
the date. After the no-reply period, 30 days unless you change it in
[Preferences](profile-preferences-templates.md#settings), Today lists the silent
ones. You can close them as **No reply**; nothing closes by itself. Before an
interview, your agent can save a brief on the application.
[Applications](applications.md) has the details.

## Fill in your record

Under **You**, add your **Profile** and career entries, state what you want in
**Preferences**, and add a CV and letter **Template** if your agent will write
your documents. You need none of this to apply by hand.
[Profile, Preferences and Templates](profile-preferences-templates.md) explains
each. Synthetic examples are in the [`examples/`](../../examples/README.md) folder.

## Connect an agent

To have an agent triage jobs and write documents, follow
[Your agent in five minutes](agents.md#your-agent-in-five-minutes), starting on
the demo. Before you upgrade, take a backup as [Operations](operations.md#update)
describes.
