#!/usr/bin/env bash
# Smoke-test a built image on an empty workspace, from the root of the checkout
# it was built from:
#
#   scripts/smoke_image.sh openings:ci amd64
#
# It starts the image with the Compose limits, as UID 10001, and checks health
# and the version, that personal data needs a session, the first-run setup, the
# served skills and dashboard (without the gallery), and that the installed
# package is the checkout's.
set -euo pipefail

image="$1"
arch="$2"
name="openings-smoke"
port=18080
url="http://127.0.0.1:$port"
work="$(mktemp -d)"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml)"
export VERSION="$version" WORK="$work"

docker volume create "$name" > /dev/null
trap 'docker logs "$name"; docker rm -f "$name"; docker volume rm "$name"; rm -rf "$work"' EXIT
docker run -d --name "$name" --init --cpus=0.5 --memory=512m --platform "linux/$arch" \
  --publish "127.0.0.1:$port:8080" --mount "source=$name,target=/data" "$image"
for _ in {1..60}; do
  if curl --silent --fail "$url/health" > "$work/health.json"; then break; fi
  sleep 1
done
python3 -c "import json,os; h=json.load(open(os.environ['WORK']+'/health.json')); assert h['status']=='ok' and h['version']==os.environ['VERSION'], h"
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
echo "Smoke passed: $image ($arch, $version)"
