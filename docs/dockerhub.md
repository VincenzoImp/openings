# Openings

**Set up your job search once. Your AI agent works it by your rules. You just apply.**

Openings is a self-hosted app that holds your job search: your career, your rules
in your own words, your CV and letter templates, the sources you watch and every
application. Your own AI agent reads all of it to bring in fresh jobs, decide each
one with a reason, write a tailored CV and letter as PDFs and rank them, and you
apply.

![Openings on the demo workspace: a Ready application with its PDFs, a Preferences line, Claude Code running the search, a dismissal that quotes the rule, Ready ranked best first, Mark applied](https://raw.githubusercontent.com/VincenzoImp/openings-job-search/main/docs/images/demo.gif)

## What Openings holds

- **Your career.** Your Profile holds your career entries and highlights; a ★
  means always in your CV, and only approved highlights are used.
- **Your rules.** Preferences hold what you look for, what you rule out, facts
  about you, writing rules and what your agent may do on its own.
- **Your templates.** Templates hold your own TeX for the CV and the letter, with
  a Preview and Limits on pages and bullets.
- **Your sources.** Sources hold LinkedIn, Indeed and Glassdoor searches (no
  login), careers pages on 12 hiring platforms, the Hacker News "Who is hiring?"
  thread, RSS feeds and job links. Each shows found · ever shortlisted · applied.
- **Your applications.** Openings tracks replies, follow-ups and deadlines, and
  your agent saves a brief on the application before each interview.

## How a day goes

**Every new job, filtered, prepared and ranked.**

1. **Openings brings in fresh jobs** from your searches and watched companies, on
   your schedule. Repeats are left out and likely copies are flagged.
2. **Your agent decides and prepares.** Your agent reads each job by your rules,
   dismisses with a reason and writes a CV and letter for the rest.
3. **You apply, best first.** Ready is ranked by priority, then deadline. You send
   each application yourself.

Change a line in your Preferences, and your agent's next decisions change with it.
Everything also works by hand in the dashboard and over a REST API. Source,
documentation and issues:
[github.com/VincenzoImp/openings-job-search](https://github.com/VincenzoImp/openings-job-search).

## Try the demo

A disposable workspace of fictional data. It contacts no job site, and
everything is deleted when it stops:

```bash
docker run --rm -p 127.0.0.1:8080:8080 vincenzoimp/openings demo
```

It prints a sign-in link that works once and an agent token for MCP.

## Run it

```bash
docker run -d --name openings -p 127.0.0.1:8080:8080 -v openings:/data --read-only --tmpfs /tmp --restart unless-stopped vincenzoimp/openings:latest
```

Or with Docker Compose, which also sets CPU and memory limits:

```bash
curl -fsSLO https://raw.githubusercontent.com/VincenzoImp/openings-job-search/main/docker-compose.yml && docker compose up -d
```

Open **http://127.0.0.1:8080** and choose an owner password. The first-run page
asks for the one-time setup code printed in the container log:

```bash
docker logs openings
```

With Compose, use `docker compose logs openings`. Setting `OPENINGS_PASSWORD`
skips the code. `curl -fsS http://127.0.0.1:8080/health` tells you it runs.

## Use with your agent

In **Settings › API & agents**, create an agent token and put it in your shell:
`export OPENINGS_TOKEN=<your agent token>`. Then install the Claude Code plugin,
with the MCP connection and the skills:

```text
/plugin marketplace add VincenzoImp/openings-job-search
/plugin install openings@openings-job-search
```

Without the plugin, Claude Code connects with:

```bash
claude mcp add --transport http openings http://127.0.0.1:8080/mcp/ \
  --header 'Authorization: Bearer ${OPENINGS_TOKEN}'
```

Codex and other clients: [Work with an agent](https://github.com/VincenzoImp/openings-job-search/blob/main/docs/user/agents.md).

## What stays yours

- **No submission.** Nothing in Openings can submit an application or contact an
  employer.
- **Attributed writes.** Every agent change carries its token's name, and
  non-destructive changes can be undone.
- **One SQLite file.** Your workspace lives in the `/data` volume, with a verified
  backup every day.
- **No account and no telemetry.** Openings contacts only the job sites your
  sources name.

## Tags

| Tag | Meaning |
|---|---|
| `X.Y.Z`, such as `0.28.0` | One release, never moved. |
| `X.Y`, such as `0.28` | The newest patch of that minor release. The Compose file pins it, so `docker compose pull` brings fixes. |
| `latest` | The newest final release. |

Every tag is a multi-arch image for **linux/amd64** and **linux/arm64**, under
100 MB. The same image, with the same tags and digest, is mirrored at
**`ghcr.io/vincenzoimp/openings`**. Images carry an SBOM and build provenance.

## Container

| | |
|---|---|
| Port | `8080` (bind it to `127.0.0.1` unless a reverse proxy is in front) |
| Volume | `/data`: the SQLite workspace, every uploaded document and the daily backups |
| User | UID/GID `10001`; a bind-mounted `/data` must be writable by it |
| Root filesystem | Runs read-only, with `/tmp` as a tmpfs |
| Settings | Environment variables, all optional: [Configuration](https://github.com/VincenzoImp/openings-job-search/blob/main/docs/user/configuration.md) |

To update, back up first, then `docker pull vincenzoimp/openings:latest` and run
the same `docker run` line again after `docker rm -f openings`, or
`docker compose pull && docker compose up -d`. The volume keeps your workspace,
and upgrades convert it automatically.

## Links

- [Getting started](https://github.com/VincenzoImp/openings-job-search/blob/main/docs/user/getting-started.md)
- [Operations: updates, backups, reverse proxy](https://github.com/VincenzoImp/openings-job-search/blob/main/docs/user/operations.md)
- [Changelog](https://github.com/VincenzoImp/openings-job-search/blob/main/CHANGELOG.md)
- [Security](https://github.com/VincenzoImp/openings-job-search/blob/main/SECURITY.md)
- License: MIT
