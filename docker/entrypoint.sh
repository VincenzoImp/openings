#!/bin/sh
#
# First-run entrypoint for the job-search-tool container.
#
# The container runs as the unprivileged ``appuser`` (UID 1000). The Compose
# stack includes a one-shot ``init-data`` service that prepares the /data
# bind mount with the correct ownership before the scheduler and dashboard
# start, so this script can assume the /data subtree is writable.
#
# Responsibilities on every start:
#   - Make sure the /data subtree exists.
#   - On first run (no settings.yaml), scaffold one from the bundled template
#     and print a friendly hint explaining what to edit.
#   - Hand control over to the container command (scheduler, dashboard, ...).

set -eu

: "${JOB_SEARCH_DATA_DIR:=/data}"
: "${JOB_SEARCH_TEMPLATE_PATH:=/opt/job-search-tool/defaults/settings.example.yaml}"
export JOB_SEARCH_DATA_DIR JOB_SEARCH_TEMPLATE_PATH

mkdir -p \
  "$JOB_SEARCH_DATA_DIR/config" \
  "$JOB_SEARCH_DATA_DIR/db" \
  "$JOB_SEARCH_DATA_DIR/chroma" \
  "$JOB_SEARCH_DATA_DIR/results" \
  "$JOB_SEARCH_DATA_DIR/logs"

SETTINGS="$JOB_SEARCH_DATA_DIR/config/settings.yaml"
if [ ! -f "$SETTINGS" ]; then
  if [ ! -f "$JOB_SEARCH_TEMPLATE_PATH" ]; then
    echo "job-search-tool: settings template missing at $JOB_SEARCH_TEMPLATE_PATH" >&2
    exit 1
  fi
  cp "$JOB_SEARCH_TEMPLATE_PATH" "$SETTINGS"
  echo "job-search-tool: first run detected."
  echo "job-search-tool: wrote default settings to $SETTINGS"
  echo "job-search-tool: edit that file to configure queries, scoring, and (optionally) Telegram notifications, then restart the container."
fi

exec "$@"
