#!/bin/sh
set -eu

bootstrap_args="--quiet"
if [ "${JOB_SEARCH_BOOTSTRAP_CONFIG:-0}" = "1" ]; then
  bootstrap_args="$bootstrap_args --write-settings"
fi

if [ "$#" -ge 2 ] && [ "$1" = "python" ] && [ "$2" = "bootstrap_config.py" ]; then
  export JOB_SEARCH_SUPPRESS_CONFIG_HINT=1
fi

python bootstrap_config.py $bootstrap_args >/dev/null 2>&1 || true

settings_path="${JOB_SEARCH_CONFIG:-/app/config/settings.yaml}"
if [ ! -f "$settings_path" ] && [ "${JOB_SEARCH_SUPPRESS_CONFIG_HINT:-0}" != "1" ]; then
  echo "job-search-tool: no settings file found at $settings_path."
  echo "job-search-tool: using built-in defaults until you create one."
  echo "job-search-tool: run 'docker compose run --rm init-config' to scaffold a starter config."
fi

exec "$@"
