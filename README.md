# Openings

**Your job search workspace.** Collect offers from companies you choose, keep
career evidence and templates, and track each application with its exact documents.
One portable SQLite database stores the workspace, including PDF and source files.

- **Inbox:** add a URL, paste a posting, or collect scheduled company feeds.
- **Career:** edit your profile, detailed experience, approved claims and supporting files.
- **Templates:** keep multiple LaTeX templates, assets and editable writing instructions.
- **Applications:** independent attempts, list/Kanban, document revisions, PDF previews
  and a funnel based on recorded progress.
- **Optional scoring:** a separate CPU model or compatible remote service. Disabled
  by default; profile edits mark old scores outdated without launching a mass rescore.
- **Three interfaces:** dashboard for manual work, REST for scripts, MCP for external agents.

An external agent uses your stored knowledge and templates to prepare CVs, letters
and form answers, compiles files on its own machine, then uploads the results.
Openings includes no generative AI subscription, internal chat or server TeX compiler.

## Install

Requires Docker Engine/Desktop with Compose v2.

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
cp .env.example .env
docker compose up -d --build
```

Open **http://127.0.0.1:8080** and set the owner password. Start with Career and
Templates, add a job, then create an application. Synthetic examples are included;
your personal information belongs in the running workspace, never in the repository.

The default installation runs one model-free container. Collection starts only
for enabled sources. [Setup](docs/user/getting-started.md) covers LAN access,
optional local scoring and first use.

## Daily workflow

1. Preview and enable the companies you want to watch, or add an offer manually.
2. Save or dismiss offers. Dismiss keeps their history; **Forget** permanently removes it.
3. Create a draft application. An MCP agent reads a frozen context containing your
   profile, evidence, instructions, selected templates and questions.
4. Review the generated content and uploaded PDF/source files. Revisions keep exact
   file associations; a changed source never silently inherits an older PDF.
5. Record Applied, Interview, Offer or Closed yourself or through your agent.
   Saving documents does not send an application or mark it applied.

## Guides

[Setup](docs/user/getting-started.md) · [Company sources](docs/user/sources.md) ·
[Scoring](docs/user/scoring.md) · [REST API](docs/user/api.md) ·
[Agents and MCP](docs/user/agents.md) · [Backup and operations](docs/user/operations.md)

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changes](CHANGELOG.md)

Openings 1.0 is a fresh implementation. Older Openings databases and configuration
are not supported. Gmail, Calendar, portal submission and semantic search are
outside this release. The optional classifier is advisory and can make mistakes.

The Compose resource budget is 2 CPU cores / 4 GiB combined with local scoring;
core-only or remote scoring avoids loading a model on this machine. Hardware and
context limits are described in the [scoring guide](docs/user/scoring.md).

[MIT](LICENSE).
