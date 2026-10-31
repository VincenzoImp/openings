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

## Your first job

1. Open `http://127.0.0.1:8080` and choose an owner password of at least 10 characters.
   For unattended setup, set `OPENINGS_PASSWORD` in `.env` before the first start.
2. In **Inbox**, choose **Add job**. Paste a URL or enter the title, company and full
   posting. If URL extraction cannot obtain the text, paste it yourself.
3. Open the job to inspect its description, add it to **Shortlist** or choose
   **Start application**. Starting creates a Draft and shortlists the job;
   an existing application opens instead. **Dismiss** keeps its identity and history.
4. In **Collection**, add a saved search or company board, preview it, then enable
   its schedule. New sources start paused.
5. Add [career entries and claims](career.md), templates and writing instructions.
   Follow [Application documents](applications.md) to prepare and review files.

![Populated job inbox with filters and compact role cards](../images/inbox.png)

Career data, search settings and files live in SQLite. Configure them in the
dashboard, REST or MCP. `.env` controls installation settings such as the host
address and image selection. Search settings need no YAML file.

## Deployment modes and resources

| Mode | Containers on this host | Compose resource limits |
|---|---|---|
| Core only | `openings` | 0.5 CPU / 512 MiB |
| Local scoring | `openings` and `scorer` | Core plus 1.5 CPU / 3584 MiB; 2 CPU / 4 GiB combined |
| Remote scoring | `openings`; scorer elsewhere | 0.5 CPU / 512 MiB here; remote service separate |

These are enforced container budgets. They do not establish minimum host
requirements or measured usage. Allow resources for the operating system, Docker
and other services. Local scoring also needs model cache space and enough memory
for loading and inference. See [scoring resources](scoring.md#resources-and-cpu-compatibility).

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

The core listens on port 8080 inside its container. `OPENINGS_PORT` changes the
host port; update `OPENINGS_PUBLIC_URL` to match.

## Optional local scoring

1. Set `SCORER_API_KEY` to a random secret in `.env`.
2. Run `docker compose --profile local pull`, then
   `docker compose --profile local up -d --no-build`.
3. In **Settings → AI scoring**, select local/Laya, URL `http://scorer:8000`, model
   `english`, context 2048 and the same API key. Allow a 600-second timeout for a
   cold model start. Test the connection, enable scoring and save the settings.
   Confirm the saved-state message says scoring is on.

The container starts separately from the scoring switch. The first test downloads
and loads the pinned model on CPU. Weights use the disposable `model-cache` volume;
the scorer has no published host port. [Scoring](scoring.md) covers remote mode,
input preparation and CPU compatibility.

To stop local inference, turn off scoring in Settings, save, then run:

```bash
docker compose --profile local stop scorer
```

## Storage and checks

The `workspace` volume holds `/data/openings.sqlite`, live journals and all uploaded
file bytes. The core runs as UID/GID 10001. A bind-mounted `/data` directory must be
writable by that identity; the default named volume handles this automatically.

```bash
docker compose ps
docker compose logs --tail=100 openings
curl --fail http://127.0.0.1:8080/health
```

Health checks the core and SQLite. An idle scorer can be healthy before loading a
model; its connection test verifies inference. [Operations](operations.md) covers
backups, restore and service lifecycle. Before upgrading, read the release notes:
pre-1.0 releases can change APIs and database format, and the app accepts its
current workspace format.
