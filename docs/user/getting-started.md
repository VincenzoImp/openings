# Setup

Install Docker with Compose v2, then use the published images:

```bash
git clone https://github.com/VincenzoImp/openings.git
cd openings
cp .env.example .env
docker compose pull
docker compose up -d --no-build
```

Compose pins `vincenzoimp/openings:0.5.1` and the optional
`vincenzoimp/openings:scorer-0.5.1`, for Linux amd64 and arm64. No Python, Node,
AI account or TeX installation is needed on the host. To build images yourself,
see [Contributing](../../CONTRIBUTING.md).

## First run

1. Open `http://127.0.0.1:8080` and choose an owner password of at least 10 characters.
   For unattended first setup, set `OPENINGS_PASSWORD` in `.env` before starting.
2. In **Career**, enter your profile/preferences and detailed experience, projects
   or courses. Approve reusable claims you want an agent to select. Import accepts
   reviewed JSON or plain-text notes; it does not infer facts.
3. In **Templates**, add a LaTeX template and optional assets, select defaults,
   and edit general/per-template writing instructions. Synthetic starting examples
   are included in `examples/` and available from the dashboard.
4. In **Collection → Saved searches**, choose a query, location, country and
   providers. In **Companies**, choose specific ATS boards/feeds, with optional
   title/location filters. Preview, then enable the sources/schedules you want.
   You can also add individual offers directly in **Inbox**.
5. Create an application and connect an [external agent](agents.md), or prepare and
   upload documents manually. Review the files before recording Applied.

Career data, search settings and files live in SQLite and are editable through the
dashboard, REST and MCP. No YAML application configuration is needed. `.env`
controls the installation address, image selection and other host settings.
New sources start paused; AI scoring is separately disabled until configured.

## LAN access

Edit `.env`, substituting the address clients can reach:

```dotenv
OPENINGS_BIND=0.0.0.0
OPENINGS_PORT=8080
OPENINGS_PUBLIC_URL=http://192.168.1.50:8080
```

Run `docker compose up -d --no-build` after edits. The public URL controls MCP
host checks and relative file-transfer links, so it must match the client origin.
Set the owner password before opening access to other devices. Use HTTPS through
a trusted reverse proxy across untrusted networks.

The core uses port 8080 inside its container. `OPENINGS_PORT` changes the host
port; update `OPENINGS_PUBLIC_URL` to match.

## Optional local scoring

1. Set `SCORER_API_KEY` to a random secret in `.env`.
2. Run `docker compose --profile local pull`, then
   `docker compose --profile local up -d --no-build`.
3. In **Settings → AI scoring**, select local/Laya, URL `http://scorer:8000`, model
   `english`, context 2048 and the same API key. Use a 600-second timeout for a
   cold model start. Test the connection, then enable scoring.

Starting the container does not enable scoring. The first test downloads the
pinned model into the disposable `model-cache` volume and loads it on CPU.
The scorer has no published host port. See [Scoring](scoring.md) for hardware and
remote mode. Turn scoring off before stopping it:

```bash
docker compose --profile local stop scorer
```

## Storage and checks

The `workspace` volume holds `/data/openings.sqlite`, live journals and all stored
file bytes. The core runs as UID/GID 10001; a bind-mounted `/data` directory must
be writable by that identity. The default named volume handles this automatically.

```bash
docker compose ps
docker compose logs --tail=100 openings
curl --fail http://127.0.0.1:8080/health
```

Health checks the core and SQLite. An idle scorer is healthy before loading a
model. For upgrades, take a [backup](operations.md), update the checkout/image tags,
then run `docker compose pull` and `docker compose up -d --no-build`.

Version 0.5.0 introduced a new database format; 0.4.x data/configuration
are not compatible. Patch releases in the 0.5 line share this workspace format. Stable public API/data-format compatibility is not yet promised.
