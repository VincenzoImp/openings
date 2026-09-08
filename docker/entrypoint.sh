#!/bin/sh
#
# Container entrypoint: create the data tree, require settings.yaml, hand over.
#
# The settings file is expected to be bind-mounted from the host as a file at
# /data/config/settings.yaml. There is no default and no auto-generation: the
# bundled settings.example.yaml documents the shape, it is not a runtime
# fallback.

set -eu

: "${OPENINGS_DATA_DIR:=/data}"
export OPENINGS_DATA_DIR

mkdir -p \
  "$OPENINGS_DATA_DIR/config" \
  "$OPENINGS_DATA_DIR/db" \
  "$OPENINGS_DATA_DIR/attachments" \
  "$OPENINGS_DATA_DIR/chroma" \
  "$OPENINGS_DATA_DIR/logs"

SETTINGS="$OPENINGS_DATA_DIR/config/settings.yaml"

if [ ! -f "$SETTINGS" ]; then
  cat >&2 <<EOF
============================================================
  openings: missing configuration
============================================================

Expected a settings file at:
  $SETTINGS

Create one from the reference and mount it:
  cp config/settings.example.yaml settings.yaml
  # edit settings.yaml, then
  docker compose up -d
EOF
  if [ -d "$SETTINGS" ]; then
    cat >&2 <<'EOF'

NOTE: the path above is a directory. Docker Compose creates one when the
host-side settings.yaml did not exist at the first `docker compose up`.
Remove it and try again:
  rm -rf ./settings.yaml
EOF
  fi
  exit 1
fi

exec "$@"
