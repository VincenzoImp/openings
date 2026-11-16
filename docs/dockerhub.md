# Openings

**Every new job, filtered, prepared and ranked. You just apply.**

A self-hosted job-search app. New jobs arrive every day from the searches and
companies you choose, without duplicates. Your own AI agent (Claude Code, Codex,
any MCP client) shortlists them, writes a tailored CV and letter, and ranks them.
You apply, best first. Everything also works by hand in the dashboard and over a
REST API.

![Openings: new jobs arrive, the agent prepares the applications, you apply best first](https://raw.githubusercontent.com/VincenzoImp/openings-job-search/main/docs/images/demo.gif)

1. **Fresh jobs, no duplicates.** From LinkedIn, Indeed and Glassdoor searches
   (no login), company careers pages on 12 hiring platforms, the Hacker News "Who
   is hiring?" thread and RSS feeds.
2. **Your agent prepares.** It shortlists by fit and writes a tailored CV and
   letter for each application.
3. **You apply, best first.** Ready applications are ranked by priority and
   deadline. Openings never sends anything to an employer.

One container, one SQLite file, no account, no telemetry. Source, documentation
and issues: [github.com/VincenzoImp/openings-job-search](https://github.com/VincenzoImp/openings-job-search).

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
skips the code. `curl http://127.0.0.1:8080/health` tells you it runs.

## Connect your agent

In **Settings › API & agents**, create an agent token, then:

```bash
export OPENINGS_TOKEN=<your agent token>
claude mcp add --transport http openings http://127.0.0.1:8080/mcp/ \
  --header 'Authorization: Bearer ${OPENINGS_TOKEN}'
```

Claude Code can instead install the plugin with the MCP connection and the
skills: `/plugin marketplace add VincenzoImp/openings-job-search`, then
`/plugin install openings@openings-job-search`. Codex and other clients:
[Work with an agent](https://github.com/VincenzoImp/openings-job-search/blob/main/docs/user/agents.md).

## Tags

| Tag | Meaning |
|---|---|
| `X.Y.Z`, such as `0.28.0` | One release, never moved. |
| `X.Y`, such as `0.28` | The newest patch of that minor release. The Compose file pins it, so `docker compose pull` brings fixes. |
| `latest` | The newest final release. |

Every tag is a multi-arch image for **linux/amd64** and **linux/arm64**, about
70 MB. The same image, with the same tags and digest, is mirrored at
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
