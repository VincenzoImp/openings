#!/bin/sh
# Run the job search once, unattended, from this agent folder; cron, launchd and
# systemd call it. The scheduler's environment holds OPENINGS_TOKEN: one Agent
# token named for this schedule. The report goes to .local/reports/.
#
#   schedule/run-job-search.sh          # Claude Code
#   schedule/run-job-search.sh codex    # Codex
set -eu
cd "$(dirname "$0")/.."
: "${OPENINGS_TOKEN:?Set OPENINGS_TOKEN in the environment of the scheduler.}"
url="${OPENINGS_URL:-http://127.0.0.1:8080}"
prompt="Run my job search with the run-job-search skill."
mkdir -p .local/reports
report=".local/reports/$(date +%Y-%m-%d-%H%M).md"

case "${1:-claude}" in
  claude)
    # The same tools as .claude/settings.json; anything else is refused, not asked.
    exec claude -p "$prompt" \
      --allowedTools "mcp__openings__*,Bash(curl -fsS * '$url/*'),Bash(tectonic *),Bash(mkdir -p .local/*),Edit(/.local/**)" \
      >"$report" ;;
  codex)
    # Writes stay in this folder; curl needs the network to reach Openings.
    exec codex exec --sandbox workspace-write \
      -c sandbox_workspace_write.network_access=true \
      -o "$report" "$prompt" ;;
  *) echo "usage: $0 [claude|codex]" >&2; exit 2 ;;
esac
