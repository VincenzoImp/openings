#!/bin/sh
#
# Start `openings web` for the Playwright suite: a throwaway data directory,
# settings with every network source and the embedding model disabled, and the
# dashboard served from frontend/dist (run `npm run build` first).
#
#   sh e2e/serve.sh <port> [api-token]

set -eu

PORT="$1"
TOKEN="${2:-}"
FRONTEND_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
ROOT_DIR="$(dirname -- "$FRONTEND_DIR")"
DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/openings-e2e-XXXXXX")"

mkdir -p "$DATA_DIR/config"
uv run --project "$ROOT_DIR" python - "$ROOT_DIR/config/settings.example.yaml" "$DATA_DIR/config/settings.yaml" <<'PY'
import sys
import yaml

source, target = sys.argv[1:3]
with open(source, encoding="utf-8") as handle:
    settings = yaml.safe_load(handle)
settings["profile"]["name"] = "E2E"
settings["sources"]["jobspy"]["enabled"] = False
settings["scheduler"]["run_on_startup"] = False
settings["embeddings"]["enabled"] = False
settings["notifications"]["enabled"] = False
with open(target, "w", encoding="utf-8") as handle:
    yaml.safe_dump(settings, handle, sort_keys=False)
PY

export OPENINGS_DATA_DIR="$DATA_DIR"
export OPENINGS_CONFIG="$DATA_DIR/config/settings.yaml"
export OPENINGS_WEB_LISTEN_PORT="$PORT"
export OPENINGS_FRONTEND_DIST="$FRONTEND_DIR/dist"
if [ -n "$TOKEN" ]; then
  export OPENINGS_API_TOKEN="$TOKEN"
fi

cleanup() {
  rm -rf "$DATA_DIR"
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR"
uv run --project "$ROOT_DIR" openings web
