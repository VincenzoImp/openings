#!/usr/bin/env bash
# Smoke-test a built image on an empty workspace, from the root of the checkout
# it was built from:
#
#   scripts/smoke_image.sh openings:ci amd64
#
# It starts the image with the Compose limits, as UID 10001, and checks health
# and the version, the image labels, that personal data needs a session, the first-run setup, the
# served skills and dashboard (without the gallery), and that the installed
# package is the checkout's. Then it starts `demo` read-only, without
# capabilities, and checks the printed sign-in link (once), the printed agent
# token over MCP, and that nothing is written to /data.
set -euo pipefail

image="$1"
arch="$2"
name="openings-smoke"
port=18080
url="http://127.0.0.1:$port"
demo="openings-smoke-demo"
demo_url="http://127.0.0.1:18081"
work="$(mktemp -d)"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml)"
description="$(sed -n 's/^description = "\(.*\)"$/\1/p' pyproject.toml)"
export VERSION="$version" DESCRIPTION="$description" WORK="$work"

docker volume create "$name" > /dev/null
docker volume create "$demo" > /dev/null
trap 'docker logs "$name"; docker logs "$demo" 2> /dev/null || true; docker rm -f "$name" "$demo" > /dev/null 2>&1 || true; docker volume rm "$name" "$demo"; rm -rf "$work"' EXIT
docker run -d --name "$name" --init --cpus=0.5 --memory=512m --platform "linux/$arch" \
  --publish "127.0.0.1:$port:8080" --mount "source=$name,target=/data" "$image"
for _ in {1..60}; do
  if curl --silent --fail "$url/health" > "$work/health.json"; then break; fi
  sleep 1
done
python3 -c "import json,os; h=json.load(open(os.environ['WORK']+'/health.json')); assert h['status']=='ok' and h['version']==os.environ['VERSION'], h"
# Every OCI label is set; the version and the description are the checkout's.
docker image inspect "$image" --format '{{json .Config.Labels}}' > "$work/labels.json"
python3 - <<'PY'
import json, os

labels = json.load(open(os.environ["WORK"] + "/labels.json")) or {}
oci = "org.opencontainers.image."
keys = [oci + key for key in (
    "title", "description", "url", "documentation", "source", "authors", "vendor",
    "licenses", "base.name", "version", "revision", "created",
)] + ["io.modelcontextprotocol.server.name"]
missing = [key for key in keys if not labels.get(key)]
assert not missing, f"Missing image labels: {missing}"
assert labels[oci + "version"] == os.environ["VERSION"], labels[oci + "version"]
assert labels[oci + "description"] == os.environ["DESCRIPTION"], labels[oci + "description"]
PY
test "$(docker exec "$name" id -u)" = 10001
docker exec "$name" test -f /data/openings.sqlite

test "$(curl --silent --output /dev/null --write-out '%{http_code}' "$url/api/v1/career/profile")" = 401
curl --silent --fail "$url/api/v1/auth/setup" --header 'Content-Type: application/json' \
  --cookie-jar "$work/cookie" --data '{"password":"synthetic-smoke-password"}' --output /dev/null
get() { curl --silent --fail --cookie "$work/cookie" "$url/api/v1/$1" --output "$work/$2"; }
get capabilities capabilities.json
python3 -c "import json,os; p=json.load(open(os.environ['WORK']+'/capabilities.json')); assert p['version']==os.environ['VERSION'] and p['operations']"
get skills skills.json
python3 -c "import json,os,pathlib; served={s['name'] for s in json.load(open(os.environ['WORK']+'/skills.json'))['items']}; shipped={p.parent.name for p in pathlib.Path('skills').glob('*/SKILL.md')}; assert served==shipped and served, (served, shipped)"
curl --silent --fail "$url/" --output "$work/index.html"
grep -q '<div id="root"></div>' "$work/index.html"
docker exec "$name" test ! -e /app/frontend/ui.html   # the gallery is not shipped

# Every tracked file of the package is installed byte for byte.
docker exec "$name" python -c "from pathlib import Path; import hashlib,json,openings; p=Path(openings.__file__).parent; print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts}))" > "$work/hashes.json"
python3 - <<'PY'
import hashlib, json, os, subprocess
from pathlib import Path

installed = json.load(open(os.environ["WORK"] + "/hashes.json"))
for name in subprocess.check_output(["git", "ls-files", "backend/openings"], text=True).split():
    path = Path(name)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert installed[str(path.relative_to("backend/openings"))] == digest, name
PY

# The demo: a temporary workspace in a read-only container that contacts no job site.
docker run -d --name "$demo" --init --read-only --tmpfs /tmp --cap-drop ALL \
  --platform "linux/$arch" --publish "127.0.0.1:18081:8080" \
  --mount "source=$demo,target=/data" "$image" demo
for _ in {1..60}; do
  if curl --silent --fail "$demo_url/health" > "$work/demo-health.json"; then break; fi
  sleep 1
done
python3 -c "import json,os; h=json.load(open(os.environ['WORK']+'/demo-health.json')); assert h['status']=='ok' and h['demo'] is True, h"
docker logs "$demo" > "$work/demo.log" 2>&1
link="$(sed -n 's|^  http://127.0.0.1:8080\(/api/v1/auth/demo?ticket=.*\)$|\1|p' "$work/demo.log")"
token="$(sed -n 's/^  export OPENINGS_TOKEN=//p' "$work/demo.log")"
grep -qF "openings http://127.0.0.1:8080/mcp/ --header 'Authorization: Bearer \${OPENINGS_TOKEN}'" "$work/demo.log"
status() { curl --silent --output /dev/null --write-out '%{http_code}' "$demo_url$link"; }
test "$(status)" = 303   # the printed link signs in once
test "$(status)" = 401
mcp() {
  curl --silent --fail "$demo_url/mcp/" --header "Authorization: Bearer $token" \
    --header 'Accept: application/json, text/event-stream' \
    --header 'Content-Type: application/json' --data "$1"
}
mcp '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}' > /dev/null
mcp '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' > "$work/tools.json"
python3 -c "import json,os; t=json.load(open(os.environ['WORK']+'/tools.json'))['result']['tools']; assert 44<=len(t)<=45, len(t)"
test -z "$(docker exec "$demo" ls -A /data)"
echo "Smoke passed: $image ($arch, $version)"
