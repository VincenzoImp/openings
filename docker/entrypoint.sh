#!/bin/sh
#
# First-run entrypoint for the job-search-tool container.
#
# On every start:
#   - Ensures the /data subtree exists (config, db, chroma, results, logs).
#   - On first run (no settings.yaml), scaffolds one from the bundled template
#     and prints a friendly hint explaining what to edit.
#   - Hands control over to the container command (scheduler, streamlit, ...).
#
# Override the root with JOB_SEARCH_DATA_DIR if you don't want /data.

set -eu

: "${JOB_SEARCH_DATA_DIR:=/data}"
: "${JOB_SEARCH_TEMPLATE_PATH:=/opt/job-search-tool/defaults/settings.example.yaml}"
export JOB_SEARCH_DATA_DIR JOB_SEARCH_TEMPLATE_PATH

SETTINGS="$JOB_SEARCH_DATA_DIR/config/settings.yaml"

mkdir -p \
  "$JOB_SEARCH_DATA_DIR/config" \
  "$JOB_SEARCH_DATA_DIR/db" \
  "$JOB_SEARCH_DATA_DIR/chroma" \
  "$JOB_SEARCH_DATA_DIR/results" \
  "$JOB_SEARCH_DATA_DIR/logs"

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
