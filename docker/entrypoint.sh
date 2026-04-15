#!/bin/sh
#
# Entrypoint for the job-search-tool container.
#
# Responsibilities:
#   - Ensure the /data subtree exists (config, db, chroma, results, logs).
#   - Require a user-provided settings.yaml. There is no fallback and no
#     auto-scaffolding; the bundled settings.example.yaml is documentation,
#     not a runtime default.
#   - Hand control over to the container command on success; exit 1 with a
#     clear, actionable error on failure.
#
# Override the data root with ``JOB_SEARCH_DATA_DIR`` if you don't want
# ``/data``.

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

if [ ! -f "$SETTINGS" ]; then
  cat >&2 <<EOF
============================================================
  job-search-tool: missing required configuration
============================================================

The tool will not start without a user-provided settings.yaml.
There is no default, no fallback, and no auto-generated file.

Expected location:
  $SETTINGS

To create one, fetch the documented example template and edit
it to your needs. Pick whichever method is most convenient:

  # From the published Docker Hub image
  docker run --rm --entrypoint cat \\
    vincenzoimp/job-search-tool:latest \\
    /opt/job-search-tool/defaults/settings.example.yaml \\
    > settings.yaml

  # Or directly from GitHub
  curl -fsSL -o settings.yaml \\
    https://raw.githubusercontent.com/VincenzoImp/job-search-tool/main/config/settings.example.yaml

Then edit ./settings.yaml (queries, scoring, Telegram, ...)
and inject it into the named volume:

  docker run --rm \\
    -v jobsearch-data:/data \\
    -v "\$PWD/settings.yaml:/src.yaml:ro" \\
    alpine sh -c 'mkdir -p /data/config && cp /src.yaml /data/config/settings.yaml'

Finally:

  docker compose up -d

============================================================
EOF
  exit 1
fi

exec "$@"
