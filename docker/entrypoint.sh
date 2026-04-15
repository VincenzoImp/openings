#!/bin/sh
#
# Entrypoint for the job-search-tool container.
#
# Responsibilities:
#   - Ensure the /data subtree exists (config, db, chroma, results, logs).
#   - Require a user-provided settings.yaml at /data/config/settings.yaml.
#     There is no fallback and no auto-scaffolding; the bundled
#     settings.example.yaml is documentation, not a runtime default.
#   - Hand control over to the container command on success; exit 1 with a
#     clear, actionable error on failure.
#
# The settings.yaml is expected to be bind-mounted from the host as a file.
# The Compose file that ships with the project does exactly this.

set -eu

: "${JOB_SEARCH_DATA_DIR:=/data}"
export JOB_SEARCH_DATA_DIR

mkdir -p \
  "$JOB_SEARCH_DATA_DIR/config" \
  "$JOB_SEARCH_DATA_DIR/db" \
  "$JOB_SEARCH_DATA_DIR/chroma" \
  "$JOB_SEARCH_DATA_DIR/results" \
  "$JOB_SEARCH_DATA_DIR/logs"

SETTINGS="$JOB_SEARCH_DATA_DIR/config/settings.yaml"

# Missing entirely, or accidentally created as a directory by Docker Compose
# when the host-side ./settings.yaml didn't exist at the time of the first
# `docker compose up`. Both failure modes share the same root cause and the
# same remediation, so they share the same error output.
if [ ! -f "$SETTINGS" ]; then
  is_directory="no"
  if [ -d "$SETTINGS" ]; then
    is_directory="yes"
  fi

  cat >&2 <<EOF
============================================================
  job-search-tool: missing required configuration
============================================================

The tool will not start without a user-provided settings.yaml.
There is no default, no fallback, and no auto-generated file.

Expected location inside the container:
  $SETTINGS
EOF

  if [ "$is_directory" = "yes" ]; then
    cat >&2 <<'EOF'

NOTE: the path above is currently a directory, not a file. That
usually means you ran `docker compose up` before creating
./settings.yaml on the host — Docker Compose then created an
empty directory to satisfy the bind mount. Remove it and try
again:

  docker compose down
  rm -rf ./settings.yaml       # remove the bogus directory
EOF
  fi

  cat >&2 <<'EOF'

To create a valid settings.yaml on your host, fetch the
documented example template and edit it to your needs:

  # From the published Docker Hub image
  docker run --rm --entrypoint cat \
    vincenzoimp/job-search-tool:latest \
    /opt/job-search-tool/defaults/settings.example.yaml \
    > settings.yaml

  # Or directly from GitHub
  curl -fsSL -o settings.yaml \
    https://raw.githubusercontent.com/VincenzoImp/job-search-tool/main/config/settings.example.yaml

Then edit ./settings.yaml (queries, scoring, Telegram, ...)
and start the stack:

  docker compose up -d

============================================================
EOF
  exit 1
fi

exec "$@"
