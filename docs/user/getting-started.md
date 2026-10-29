# Setup

Install Docker with Compose v2, then follow the README's clone/build commands.
`docker compose up -d --build` builds the dashboard and core from the checkout.
No Python, Node, AI account or TeX installation is needed on the host.

## First run

1. Open `http://127.0.0.1:8080` and choose an owner password of at least 10 characters.
   Alternatively set `OPENINGS_PASSWORD` in `.env` before the first start.
2. In **Career**, enter your profile/preferences, then add detailed experience,
   projects or courses. Approve reusable claims you want an agent to select.
   Import accepts reviewed JSON or plain-text notes; it does not infer facts.
3. In **Templates**, add a LaTeX template and optional supporting files. Set a
   default and adjust general/per-template writing instructions. Synthetic
   `examples/career.json`, `examples/resume.tex` and `examples/cover-letter.tex`
   are available as starting examples.
4. Add an offer in **Inbox**, or configure a saved search or company feed in **Collection**
   and preview it before enabling its schedule. Scoring remains off until configured separately.
5. Create an application and connect an [external agent](agents.md), or upload
   documents manually. Review files before recording an application as Applied.

All changes are stored immediately in SQLite. No YAML application configuration
is required. `.env` controls installation settings, not your career or sources.

## Another device on your LAN

Edit `.env`, substituting your server's actual address:

```dotenv
OPENINGS_BIND=0.0.0.0
OPENINGS_PORT=8080
OPENINGS_PUBLIC_URL=http://192.168.1.50:8080
```

Run `docker compose up -d` after edits. The public URL must match the origin used
by agents: it controls MCP host checks and relative file-transfer links. Set the
owner password before opening the binding to other devices. Use HTTPS through a
trusted reverse proxy for access across untrusted networks.

The core binds inside the container on port 8080. `OPENINGS_PORT` in Compose
changes only the host port; update `OPENINGS_PUBLIC_URL` when changing it.

## Optional local scorer

1. Set `SCORER_API_KEY` to a random secret in `.env`.
2. Run `docker compose --profile local up -d --build`.
3. In **Settings → Scoring**, select local/Laya, URL `http://scorer:8000`, model
   `english`, context 2048 and the same API key. Use a 600-second timeout for a
   cold model start. Test the connection, then enable scoring.

Starting the container does not enable scoring. The first test downloads the
pinned model into the disposable `model-cache` volume and loads it on CPU.
The service has no published host port. See [Scoring](scoring.md) for constraints
and remote mode. Set scoring off before stopping it:

```bash
docker compose --profile local stop scorer
```

## Storage and startup checks

The `workspace` volume holds `/data/openings.sqlite` and SQLite's live journal
files. It contains your profile, postings, templates, settings and document bytes.
The core runs as UID/GID 10001; a bind-mounted `/data` directory must be writable
by that identity. Use the default named volume for the simplest installation.

```bash
docker compose ps
docker compose logs --tail=100 openings
curl --fail http://127.0.0.1:8080/health
```

The health endpoint checks the core and SQLite. An idle scorer is healthy before
its model has loaded. Do not treat health alone as a model-quality check.

For upgrades, take a [backup](operations.md), update the checkout and run
`docker compose up -d --build`. This rewrite starts with a fresh workspace;
there is no migration from the previous product. The version is 0.5.0 because
stable public API/data-format compatibility is not yet promised.
