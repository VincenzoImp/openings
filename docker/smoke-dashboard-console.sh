#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
IMAGE="${IMAGE:-job-search-tool:dashboard-console}"
PORT="${PORT:-18651}"
TOKEN="${JOB_SEARCH_API_TOKEN:-smoke-token}"
CONTAINER="${CONTAINER:-job-search-dashboard-smoke}"
WORK_DIR="$(mktemp -d)"
DATA_DIR="$WORK_DIR/data"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT INT TERM

mkdir -p "$DATA_DIR/config" "$DATA_DIR/db" "$DATA_DIR/chroma" "$DATA_DIR/results" "$DATA_DIR/logs"
cp "$ROOT_DIR/config/settings.example.yaml" "$DATA_DIR/config/settings.yaml"
chmod -R 0777 "$DATA_DIR"

docker build -t "$IMAGE" "$ROOT_DIR"

python3 - "$DATA_DIR/db/jobs.db" <<'PY'
from datetime import date
import hashlib
import sqlite3
import sys
import unicodedata

db_path = sys.argv[1]


def job_id(title, company, location):
    parts = []
    for value in (title, company, location):
        normalized = unicodedata.normalize("NFKC", value or "")
        normalized = " ".join(normalized.split())
        parts.append(normalized.casefold())
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


rows = [
    {
        "title": "Backend Python Engineer",
        "company": "Acme Labs",
        "location": "Remote",
        "job_url": "https://example.com/backend",
        "site": "linkedin",
        "job_type": "fulltime",
        "is_remote": 1,
        "description": "Python APIs and data pipelines.",
        "min_amount": 90000,
        "max_amount": 130000,
        "currency": "EUR",
        "relevance_score": 44,
    },
    {
        "title": "Frontend Developer",
        "company": "Widget Inc",
        "location": "New York",
        "job_url": "https://example.com/frontend",
        "site": "indeed",
        "job_type": "contract",
        "is_remote": 0,
        "description": "React dashboard work.",
        "min_amount": 70000,
        "max_amount": 90000,
        "currency": "EUR",
        "relevance_score": 31,
    },
]

with sqlite3.connect(db_path) as conn:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            job_url TEXT,
            site TEXT,
            job_type TEXT,
            is_remote BOOLEAN,
            job_level TEXT,
            description TEXT,
            date_posted DATE,
            min_amount REAL,
            max_amount REAL,
            currency TEXT,
            company_url TEXT,
            first_seen DATE NOT NULL,
            last_seen DATE NOT NULL,
            relevance_score INTEGER DEFAULT 0,
            applied BOOLEAN DEFAULT FALSE,
            bookmarked BOOLEAN DEFAULT FALSE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deleted_jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            blacklisted_at TEXT NOT NULL
        )
        """
    )
    today = date.today().isoformat()
    for row in rows:
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, title, company, location, job_url, site, job_type,
                is_remote, job_level, description, date_posted, min_amount,
                max_amount, currency, company_url, first_seen, last_seen,
                relevance_score, applied, bookmarked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id(row["title"], row["company"], row["location"]),
                row["title"],
                row["company"],
                row["location"],
                row["job_url"],
                row["site"],
                row["job_type"],
                row["is_remote"],
                None,
                row["description"],
                today,
                row["min_amount"],
                row["max_amount"],
                row["currency"],
                None,
                today,
                today,
                row["relevance_score"],
                0,
                0,
            ),
        )
PY
chmod -R 0777 "$DATA_DIR"

docker run -d --rm \
  --name "$CONTAINER" \
  -p "127.0.0.1:$PORT:8501" \
  -e JOB_SEARCH_API_TOKEN="$TOKEN" \
  -e JOB_SEARCH_WEB_ALLOWED_HOSTS="127.0.0.1:$PORT,localhost:$PORT" \
  -e JOB_SEARCH_WEB_ALLOWED_ORIGINS="http://127.0.0.1:$PORT,http://localhost:$PORT" \
  -v "$DATA_DIR:/data" \
  "$IMAGE" job-search-web >/dev/null

BASE_URL="http://127.0.0.1:$PORT"

for _ in $(seq 1 60); do
  if curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

python3 - "$BASE_URL" "$TOKEN" <<'PY'
import json
import sys
import urllib.error
import urllib.request

base_url, token = sys.argv[1], sys.argv[2]


def request(path, *, method="GET", body=None, token_required=True, headers=None):
    payload = None if body is None else json.dumps(body).encode()
    req_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        req_headers["Content-Type"] = "application/json"
    if token_required:
        req_headers["X-Job-Search-Token"] = token
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=payload,
        headers=req_headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return json.loads(raw.decode())
        return raw.decode()


health = request("/health", token_required=False)
assert health["jobs_count"] == 2, health

html = request("/", token_required=False, headers={"Accept": "text/html"})
assert "Job Search" in html or "root" in html

jobs = request("/api/jobs?sites=indeed&job_types=contract&sort=title")
assert jobs["total"] == 1, jobs
job_id = jobs["items"][0]["job_id"]

facets = request("/api/jobs/facets")
assert facets["sites"], facets

bookmark = request(
    "/api/jobs/bookmark",
    method="POST",
    body={"job_ids": [job_id], "bookmarked": True},
)
assert bookmark["affected_count"] == 1, bookmark

exported = request(
    "/api/export/jobs",
    method="POST",
    body={"job_ids": [job_id], "format": "json"},
)
assert any(item["job_id"] == job_id for item in exported), exported

blacklist = request("/api/blacklist", method="POST", body={"job_ids": [job_id]})
assert blacklist["affected_count"] == 1, blacklist

listed = request("/api/blacklist")
assert listed["total"] == 1, listed

removed = request("/api/blacklist/remove", method="POST", body={"job_ids": [job_id]})
assert removed["affected_count"] == 1, removed

cleanup = request("/api/cleanup/delete-below-score", method="POST", body={"score": 0})
assert "affected_count" in cleanup, cleanup


def mcp(payload, session_id=None):
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        f"{base_url}/mcp/",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode(), response.headers.get("Mcp-Session-Id")


init_text, session = mcp(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "1"},
        },
    }
)
assert "serverInfo" in init_text, init_text
assert session, "MCP session id missing"

mcp({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
tools_text, _ = mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session)
assert "list_blacklisted_jobs" in tools_text, tools_text

call_text, _ = mcp(
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "get_facets", "arguments": {}},
    },
    session,
)
assert "sites" in call_text, call_text
PY

printf '%s\n' "Dashboard console smoke passed at $BASE_URL"
