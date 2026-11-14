# Setup and first use

Install Docker with Compose v2, then start the published images:

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
cp .env.example .env
docker compose pull
docker compose up -d --no-build
```

Images support Linux amd64 and arm64. Docker Compose pins the release; the host
needs no Python, Node or TeX installation. [Contributing](../../CONTRIBUTING.md)
covers local builds.

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

## Finding your way

The navigation has three groups. **Work** holds Today, Applications, Jobs (the
tabs New, Dismissed and All, each with the selected job beside the list; after
you shortlist or dismiss a job, the next one is shown, and every decision can
be undone). **Library** holds Career, Preferences and Templates. **System** holds
Collection and Settings. The number beside Applications counts the
applications ready to apply.

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

You talk to your agent in its own chat; **Settings › Skills** lists what you can
ask it. How your applications fare is under **Applications**, **Stats**.

On a phone the bottom bar shows the four Work destinations and **More**, which
opens Library and System. The top bar switches between the light and dark theme;
the choice is remembered in the browser, and the theme follows the system until
you choose one.

## Your first job

1. Sign in at `http://127.0.0.1:8080` (see above for the first start).
2. In **Jobs** (it opens on **New**), choose **Add a job**. Paste a URL
   or enter the title, company and full posting. The address is looked up first:
   a job already in your workspace is shown instead of a copy. If URL extraction
   cannot obtain the text, paste it yourself.
3. Select the job to read its posting and signals beside the list, then choose
   **Shortlist** (`s`) or **Dismiss** (`d`); `j` and `k` move between jobs and
   `z` undoes. Shortlisting starts the job's application in stage Shortlisted,
   needing a CV and a letter; undoing it removes that application while
   nothing has been added to it. Dismissing keeps the job's identity and
   history; its toast offers **Add reason**. Dismissed jobs are restored from
   the Dismissed tab (`r`), where a filter shows who dismissed them.
4. In **Collection**, add a saved search or company board, preview it, then enable
   its schedule. New sources start paused.
5. Add [career entries and claims](career.md), templates and writing rules.
   Follow [Application documents](applications.md) to prepare and review files.

![Jobs to review beside the selected job, with its signals, posting and timeline](../images/jobs.png)

Career data, search settings and files live in SQLite. Configure them in the
dashboard, REST or MCP. `.env` controls installation settings such as the host
address and image selection. Search settings need no YAML file.

## Deployment modes and resources

The single `openings` container has a Compose budget of **0.5 CPU / 512 MiB**.
This is an enforced container limit, not a measured host requirement. Allow
resources for the operating system, Docker and other services.

## LAN access

Edit `.env` with the address clients can reach:

```dotenv
OPENINGS_BIND=0.0.0.0
OPENINGS_PORT=8080
OPENINGS_PUBLIC_URL=http://openings.example:8080
```

Replace `openings.example` with your hostname or LAN address. Run
`docker compose up -d --no-build` after edits. The public URL controls MCP host
checks and relative file-transfer links; it must match the client origin. Set the
owner password before opening access to other devices. Use HTTPS through a
trusted reverse proxy across untrusted networks.

Behind a reverse proxy, list the proxy's address as seen by the container in
`.env`, so sign-in limits and secure cookies use each browser's real address:

```dotenv
OPENINGS_TRUSTED_PROXIES=172.18.0.2
```

Use comma-separated IP addresses or CIDR ranges. When it is empty (the default),
`X-Forwarded-For` and `X-Forwarded-Proto` are ignored and all proxied clients
share the proxy's sign-in limit. Trust only proxies that overwrite these headers.

The core listens on port 8080 inside its container. `OPENINGS_PORT` changes the
host port; update `OPENINGS_PUBLIC_URL` to match.

## Storage and checks

The `workspace` volume holds `/data/openings.sqlite`, live journals and all uploaded
file bytes. The core runs as UID/GID 10001. A bind-mounted `/data` directory must be
writable by that identity; the default named volume handles this automatically.

```bash
docker compose ps
docker compose logs --tail=100 openings
curl --fail http://127.0.0.1:8080/health
```

Health checks the core and SQLite. [Operations](operations.md) covers
backups, restore and service lifecycle. Before upgrading, read the release notes:
pre-1.0 releases can change APIs and database format. A release upgrades the
workspace to its format automatically on start; back up before upgrading.
Workspaces older than 0.23 must be opened once with 0.23 first; release history
is in [CHANGELOG.md](../../CHANGELOG.md).
