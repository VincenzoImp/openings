#!/usr/bin/env bash
# Audit the locked runtime Python dependencies and the dashboard's npm
# dependencies for known advisories. Needs uv and npm.
set -euo pipefail

requirements="$(mktemp)"
trap 'rm -f "$requirements"' EXIT
uv export --locked --no-dev --no-emit-project --no-hashes --output-file "$requirements"
uvx --from pip-audit==2.10.1 pip-audit --requirement "$requirements" --no-deps --disable-pip
npm --prefix frontend audit --audit-level=moderate
