#!/bin/sh
#
# End-to-end smoke test: build the image, start `openings web` with a token,
# then drive the dashboard, the REST API and MCP through one job's life.
#
#   sh docker/smoke.sh
#
# Environment: IMAGE, PORT, CONTAINER, OPENINGS_API_TOKEN.

set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
IMAGE="${IMAGE:-openings:smoke}"
PORT="${PORT:-18651}"
TOKEN="${OPENINGS_API_TOKEN:-smoke-token}"
CONTAINER="${CONTAINER:-openings-smoke}"
WORK_DIR="$(mktemp -d)"
DATA_DIR="$WORK_DIR/data"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT INT TERM

mkdir -p "$DATA_DIR/config" "$DATA_DIR/db" "$DATA_DIR/attachments" "$DATA_DIR/chroma" "$DATA_DIR/logs"
cp "$ROOT_DIR/config/settings.example.yaml" "$DATA_DIR/config/settings.yaml"
chmod -R 0777 "$DATA_DIR"

docker build -t "$IMAGE" "$ROOT_DIR"

docker run -d --rm \
  --name "$CONTAINER" \
  -p "127.0.0.1:$PORT:8501" \
  -e OPENINGS_API_TOKEN="$TOKEN" \
  -e OPENINGS_WEB_ALLOWED_HOSTS="127.0.0.1:$PORT,localhost:$PORT" \
  -e OPENINGS_WEB_ALLOWED_ORIGINS="http://127.0.0.1:$PORT,http://localhost:$PORT" \
  -v "$DATA_DIR:/data" \
  "$IMAGE" openings web >/dev/null

BASE_URL="http://127.0.0.1:$PORT"

for _ in $(seq 1 60); do
  if curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

python3 - "$BASE_URL" "$TOKEN" <<'PY'
import base64
import json
import sys
import urllib.request
import uuid

base_url, token = sys.argv[1], sys.argv[2]


def request(path, *, method="GET", body=None, data=None, headers=None, auth=True):
    req_headers = {"Accept": "application/json", **(headers or {})}
    payload = data
    if body is not None:
        payload = json.dumps(body).encode()
        req_headers["Content-Type"] = "application/json"
    if auth:
        req_headers["X-Openings-Token"] = token
    req = urllib.request.Request(f"{base_url}{path}", data=payload, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        if "application/json" in response.headers.get("content-type", ""):
            return json.loads(raw.decode())
        return raw


def multipart(fields, file_field, filename, content):
    boundary = uuid.uuid4().hex
    lines = []
    for name, value in fields.items():
        lines += [f"--{boundary}", f'Content-Disposition: form-data; name="{name}"', "", value]
    lines += [
        f"--{boundary}",
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"',
        "Content-Type: application/octet-stream",
        "",
    ]
    body = "\r\n".join(lines).encode() + b"\r\n" + content + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


# Public surface without a token
health = request("/health", auth=False)
assert health["status"] == "ok", health
assert request("/api/dashboard/auth", auth=False)["token_required"] is True
html = request("/", auth=False, headers={"Accept": "text/html"}).decode()
assert '<div id="root"></div>' in html, html[:200]

# REST: add a posting, attach a file, record an answer, apply, read it back
created = request(
    "/api/jobs",
    method="POST",
    body={
        "title": "Backend Python Engineer",
        "company": "Acme Labs",
        "location": "Remote",
        "job_url": "https://example.com/backend",
        "description": "Python APIs and data pipelines with PostgreSQL.",
        "labels": ["smoke"],
    },
)
assert created["success"], created
job_id = created["job_ids"][0]

listed = request("/api/jobs?status=shortlisted&label=smoke")
assert listed["total"] == 1 and listed["items"][0]["job_id"] == job_id, listed

body, content_type = multipart({"kind": "cv", "note": "smoke"}, "file", "cv.pdf", b"%PDF-1.4 smoke")
attachment = request(
    f"/api/jobs/{job_id}/attachments", method="POST", data=body, headers={"Content-Type": content_type}
)
assert attachment["kind"] == "cv" and attachment["size_bytes"] == 14, attachment
downloaded = request(f"/api/jobs/{job_id}/attachments/{attachment['id']}")
assert downloaded == b"%PDF-1.4 smoke", downloaded

note = request(
    f"/api/jobs/{job_id}/notes",
    method="POST",
    body={"kind": "qa", "title": "Why us?", "body": "Because of the data platform."},
)
assert note["kind"] == "qa", note

moved = request("/api/jobs/status", method="POST", body={"job_ids": [job_id], "status": "applied", "note": "sent"})
assert moved["affected_count"] == 1, moved

detail = request(f"/api/jobs/{job_id}")
assert detail["status"] == "applied", detail["status"]
assert detail["labels"] == ["smoke"], detail["labels"]
assert len(detail["attachments"]) == 1 and len(detail["notes"]) == 1, detail
assert detail["explain"]["score"] > 0, detail["explain"]
assert any(event["kind"] == "status" for event in detail["events"]), detail["events"]

exported = request("/api/export/jobs", method="POST", body={"job_ids": [job_id], "format": "json"})
assert exported[0]["job_id"] == job_id, exported

facets = request("/api/jobs/facets")
assert facets["sources"][0]["value"] == "manual", facets
assert request("/api/runs") == []
assert request("/api/cleanup/preview")["protected"] == 1


# MCP: add a second posting and move it
def mcp(payload, session_id=None):
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(
        f"{base_url}/mcp/", data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode(), response.headers.get("Mcp-Session-Id")


def mcp_result(text):
    for line in text.splitlines():
        if line.startswith("data:"):
            message = json.loads(line[5:].strip())
            return json.loads(message["result"]["content"][0]["text"])
    return json.loads(json.loads(text)["result"]["content"][0]["text"])


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
assert "serverInfo" in init_text and session, init_text
mcp({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)

tools_text, _ = mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, session)
for name in ("add_job", "set_status", "add_attachment", "list_runs"):
    assert name in tools_text, name

added_text, _ = mcp(
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "add_job",
            "arguments": {"title": "Platform Engineer", "company": "Widget Inc", "location": "Berlin"},
        },
    },
    session,
)
added = mcp_result(added_text)
assert added["success"], added
second = added["job_ids"][0]

attached_text, _ = mcp(
    {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "add_attachment",
            "arguments": {
                "job_id": second,
                "filename": "letter.md",
                "content_base64": base64.b64encode(b"Dear team").decode(),
                "kind": "cover_letter",
            },
        },
    },
    session,
)
assert mcp_result(attached_text)["success"], attached_text

status_text, _ = mcp(
    {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "set_status", "arguments": {"job_ids": [second], "status": "interviewing"}},
    },
    session,
)
assert mcp_result(status_text)["affected_count"] == 1, status_text

got_text, _ = mcp(
    {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "get_job", "arguments": {"job_id": second}}},
    session,
)
got = mcp_result(got_text)
assert got["status"] == "interviewing" and got["attachments"][0]["kind"] == "cover_letter", got

stats = request("/api/stats")
assert stats["total_jobs"] == 2 and stats["by_status"]["applied"] == 1, stats
PY

printf '%s\n' "Smoke passed at $BASE_URL"
