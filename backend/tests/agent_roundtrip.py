"""Practical external-agent round trip against an isolated workspace over real HTTP.

An agent connects over MCP with an agent token and works as the skills describe:
the start read, a triage of 50 collected jobs in batches, CV and letter for one
shortlisted application (a TeX source compiled on the agent's machine and a
PDF-only letter, each uploaded with the PUT its revision returns), the computed
Ready, the owner's reply recorded on request, the change log of one batch and
the owner's correction read back as feedback. It also counts the calls each
task needs.

    uv run python backend/tests/agent_roundtrip.py [--tectonic /path/to/tectonic]

Without ``--tectonic`` the PDF is a small synthetic one (CI); with it the CV is
compiled from the shipped example template.
"""

import argparse
import asyncio
import hashlib
import json
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
import httpx2
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
from document_fixtures import text_pdf  # noqa: E402

from openings.app import create_app  # noqa: E402

JOBS = 50
SHORTLIST = 4
EXAMPLE_TEX = Path(__file__).resolve().parents[2] / "examples" / "cv.tex"


class Agent:
    """MCP calls that count themselves and unpack compact JSON results."""

    def __init__(self, session):
        self.session, self.calls = session, 0

    async def raw(self, name, arguments=None):
        self.calls += 1
        return await self.session.call_tool(name, arguments or {})

    async def __call__(self, name, arguments=None):
        result = await self.raw(name, arguments)
        if result.is_error:
            raise RuntimeError(f"{name}: {result.content[0].text}")
        return json.loads(next(item.text for item in result.content if item.type == "text"))


def error_of(result):
    return json.loads(result.content[0].text)["error"] if result.is_error else None


def compile_cv(folder, tex, tectonic):
    """The CV PDF: compiled from its TeX source with Tectonic, or a synthetic PDF."""
    if not tectonic:
        return text_pdf("Alex Example", "Backend engineer", "Reduced API p95 latency by 20%.")
    source = folder / "cv.tex"
    source.write_text(tex)
    subprocess.run(
        [tectonic, "--untrusted", "--outdir", str(folder), str(source)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
    )
    return source.with_suffix(".pdf").read_bytes()


async def exercise(base, agent_token, owner_token, folder, tectonic):
    checks, counts = {}, {}
    owner = httpx.AsyncClient(headers={"Authorization": f"Bearer {owner_token}"}, timeout=30)
    async with owner, httpx.AsyncClient(timeout=30) as http:
        checks["rest_requires_a_token"] = (
            await http.get(base + "/api/v1/workspace/context")
        ).status_code == 401
        headers = {"Authorization": f"Bearer {agent_token}"}
        async with (
            httpx2.AsyncClient(headers=headers, timeout=60) as agent_http,
            Client(streamable_http_client(base + "/mcp/", http_client=agent_http)) as client,
        ):
            call = Agent(client)
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            instructions = client.instructions or ""
            checks["forty_four_tools_and_instructions"] = (
                44 <= len(tools) <= 45
                and "workspace_context" in instructions
                and "Never submit an application" in instructions
            )
            checks["no_owner_only_tool"] = not {
                "workspace_export",
                "career_import",
                "tokens_list",
            } & set(tools)
            checks["annotations"] = (
                tools["workspace_context"].annotations.read_only_hint
                and tools["jobs_triage"].annotations.destructive_hint is False
                and tools["jobs_delete"].annotations.destructive_hint is not False
                and tools["sources_run"].annotations.open_world_hint is not False
            )
            renamed = error_of(await call.raw("jobs_bulk", {}))
            checks["0_23_names_answer_their_replacement"] = (
                renamed["code"] == "renamed" and renamed["details"]["use"] == "jobs_triage"
            )
            wrapped = error_of(await call.raw("jobs_list", {"value": {"q": "x"}}))
            checks["flat_arguments_only"] = wrapped["code"] == "validation"

            # Setup the agent does once: profile, a career entry, a highlight, a template.
            context = await call("workspace_context")
            await call(
                "profile_update",
                {
                    "expected_version": context["profile"]["version"],
                    "name": "Alex Example",
                    "headline": "Backend engineer",
                },
            )
            entry = (
                await call(
                    "career_save",
                    {
                        "items": [
                            {
                                "kind": "project",
                                "title": "Example API",
                                "narrative": "Built Python APIs and reduced latency by 20%.",
                                "idempotency_key": "example-api",
                            }
                        ]
                    },
                )
            )["items"][0]
            highlight = (
                await call(
                    "highlights_save",
                    {
                        "items": [
                            {
                                "career_id": entry["id"],
                                "text": "Reduced API p95 latency by 20%.",
                                "approved": True,
                            }
                        ]
                    },
                )
            )["items"][0]
            await call(
                "templates_save",
                {
                    "name": "Synthetic CV",
                    "kind": "cv",
                    "tex": EXAMPLE_TEX.read_text(),
                    "guidance": "Concise, evidence first.",
                },
            )

            # "Empty my inbox using my criteria": the start read, one page, batched reads,
            # one batch of decisions.
            start = call.calls
            context = await call("workspace_context", {"include": ["career_full"]})
            page = await call("jobs_list", {"triage": "new", "limit": JOBS})
            ids = [item["id"] for item in page["items"]]
            postings = []
            for offset in range(0, len(ids), 20):
                postings += (await call("jobs_get", {"ids": ids[offset : offset + 20]}))["items"]
            decisions = [
                {"job_id": job["id"], "to": "shortlisted"}
                if "Python" in job["posting"]
                else {"job_id": job["id"], "to": "dismissed", "reason": "No Python in the role."}
                for job in postings
            ]
            triage = await call("jobs_triage", {"items": decisions})
            counts["triage_50_jobs"] = call.calls - start
            checks["triage_in_4_plus_n_over_20_calls"] = counts["triage_50_jobs"] <= 4 + JOBS / 20
            checks["triage_items_each_succeed"] = (
                page["total"] == JOBS
                and triage["succeeded"] == JOBS
                and sum(item["to"] == "shortlisted" for item in decisions) == SHORTLIST
            )
            shortlisted = [
                item["result"]["application_id"]
                for item in triage["items"]
                if item["result"].get("application_id")
            ]
            checks["shortlisting_starts_applications"] = len(shortlisted) == SHORTLIST
            changes = await call("changes_list", {"batch_id": triage["batch_id"], "limit": 200})
            checks["one_batch_per_call"] = changes["total"] >= JOBS and {
                item["actor"] for item in changes["items"]
            } == {"agent:synthetic-agent"}

            # Applications for the shortlisted jobs, in one call: they already exist.
            jobs = [item["job_id"] for item in decisions if item["to"] == "shortlisted"]
            created = await call(
                "applications_create",
                {
                    "items": [
                        {"job_id": job, "required_documents": ["cv", "letter"]} for job in jobs
                    ]
                },
            )
            checks["applications_create_returns_the_open_ones"] = sorted(
                item["id"] for item in created["items"]
            ) == sorted(shortlisted) and not any(
                item["result"]["created"] for item in created["items"]
            )
            application = (await call("applications_get", {"ids": [shortlisted[0]]}))["items"][0]
            checks["missing_cv_and_letter"] = application["missing"] == ["cv", "letter"]

            # "Prepare CV and letter for this application": two revisions, two PUTs.
            template = (await call("workspace_context", {"include": ["templates_full"]}))[
                "templates"
            ][0]
            tex = template["tex"]
            pdf = compile_cv(folder, tex, tectonic)
            letter_pdf = text_pdf("Dear hiring team,", "Alex Example applies.")
            checks["pdf_bytes"] = pdf.startswith(b"%PDF-")

            def spec(name, data):
                return {"name": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}

            async def put(grant, data):
                response = await http.put(
                    urljoin(base, grant["url"]), headers=grant["headers"], content=data
                )
                return response.status_code, response.json()

            start, puts = call.calls, 0
            cv = await call(
                "documents_create",
                {
                    "application_id": application["id"],
                    "kind": "cv",
                    "title": "CV",
                    "source": tex,
                    "pdf": spec("cv.pdf", pdf),
                    "highlight_ids": [highlight["id"]],
                    "career_ids": [entry["id"]],
                },
            )
            status, stored = await put(cv["uploads"]["pdf"], pdf)
            puts += 1
            checks["cv_pdf_names_its_source"] = (
                status == 200
                and stored["source_sha256"] == hashlib.sha256(tex.encode()).hexdigest()
            )
            checks["curl_line_given"] = cv["uploads"]["pdf"]["curl"].startswith("curl -fsS -X PUT")
            letter = await call(
                "documents_create",
                {
                    "application_id": application["id"],
                    "kind": "letter",
                    "pdf": spec("letter.pdf", letter_pdf),
                },
            )
            status, _ = await put(letter["uploads"]["pdf"], letter_pdf)
            puts += 1
            counts["prepare_cv_and_letter"] = {"mcp": call.calls - start, "put": puts}
            checks["prepare_in_2_calls_and_2_puts"] = counts["prepare_cv_and_letter"] == {
                "mcp": 2,
                "put": 2,
            }
            cv_read = await call("documents_get", {"document_id": cv["id"]})
            letter_read = await call("documents_get", {"document_id": letter["id"]})
            checks["text_from_source_and_from_pdf"] = (
                cv_read["complete"]
                and cv_read["text_from"] == "tex"
                and letter_read["complete"]
                and letter_read["text_from"] == "pdf"
                and "Alex Example" in letter_read["text"]
                and cv_read["highlight_ids"] == [highlight["id"]]
            )
            late = await call.raw(
                "files_upload",
                {
                    "owner_type": "document",
                    "owner_id": cv["id"],
                    "name": "late.pdf",
                    "media_type": "application/pdf",
                    "size": len(pdf),
                },
            )
            checks["complete_revision_is_immutable"] = error_of(late)["code"] == "revision_complete"
            download = await call("files_download", {"file_id": stored["id"]})
            fetched = await http.get(urljoin(base, download["url"]), headers=download["headers"])
            checks["exact_pdf_download"] = fetched.content == pdf
            ready = await call("applications_list", {"stage": "ready"})
            checks["ready_is_computed"] = [item["id"] for item in ready["items"]] == [
                application["id"]
            ]
            refused = await call.raw(
                "applications_update",
                {"items": [{"application_id": application["id"], "ready": True}]},
            )
            checks["ready_cannot_be_set"] = error_of(refused)["code"] == "validation"

            # The owner says they applied and got an interview invitation.
            sent = await call(
                "applications_update",
                {"items": [{"application_id": application["id"], "stage": "applied"}]},
            )
            replied = await call(
                "applications_update",
                {
                    "items": [
                        {
                            "application_id": application["id"],
                            "reply": {"kind": "interview", "note": "Call on Monday."},
                        }
                    ]
                },
            )
            checks["reply_moves_the_stage"] = (
                sent["items"][0]["result"]["status"] == "applied"
                and replied["items"][0]["result"]["status"] == "interview"
            )

            # The owner restores one dismissal; the agent reads it as feedback.
            dismissed = next(item for item in decisions if item["to"] == "dismissed")
            job = (await owner.get(f"{base}/api/v1/jobs/{dismissed['job_id']}")).json()
            restored = await owner.post(
                f"{base}/api/v1/jobs/{job['id']}/triage",
                json={"triage": "new", "expected_version": job["version"]},
            )
            feedback = (await call("workspace_context"))["feedback"]
            checks["owner_correction_is_feedback"] = restored.status_code == 200 and any(
                item["subject"]["id"] == job["id"]
                and item["reason_was"] == "No Python in the role."
                for item in feedback
            )

            backup = await call("workspace_backup")
            response = await http.get(urljoin(base, backup["url"]), headers=backup["headers"])
            path = folder / "backup.sqlite"
            path.write_bytes(response.content)
            with sqlite3.connect(path) as restored_db:
                checks["backup_integrity"] = (
                    restored_db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                    and restored_db.execute("PRAGMA foreign_key_check").fetchall() == []
                    and restored_db.execute("SELECT count(*) FROM api_tokens").fetchone()[0] == 0
                    and restored_db.execute(
                        "SELECT content FROM blobs WHERE sha256=?", (stored["sha256"],)
                    ).fetchone()[0]
                    == pdf
                )
    return {
        "purpose": "an external agent's MCP round trip: start read, batches, files, feedback",
        "compiled_with": "tectonic" if tectonic else "synthetic pdf",
        "calls": counts,
        "checks": checks,
        "all_passed": all(checks.values()),
    }


def seed(app):
    """Fifty collected jobs, four of them about Python, as a source would store them."""
    for number in range(JOBS):
        stack = "Python" if number < SHORTLIST else "Java"
        app.state.workspace.ingest_job(
            {
                "url": f"https://jobs.example.org/{number}",
                "title": f"Backend engineer {number}",
                "company": f"Example {number % 7}",
                "posting": f"Build {stack} services for a synthetic product team. " * 20,
            }
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--tectonic", default="", help="Compile the CV with this Tectonic.")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        app = create_app(folder / "workspace.sqlite", start_worker=False)
        app.state.auth.setup("synthetic-probe-password")
        agent = app.state.auth.create_token("synthetic-agent", "agent")["token"]
        owner = app.state.auth.create_token("synthetic-owner", "owner")["token"]
        seed(app)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.05)
            if not server.started:
                raise RuntimeError("Probe HTTP server did not start.")
            base = f"http://127.0.0.1:{port}"
            record = asyncio.run(exercise(base, agent, owner, folder, args.tectonic))
            if args.out:
                args.out.write_text(json.dumps(record, indent=2) + "\n")
            print(json.dumps(record, indent=2))
            if not record["all_passed"]:
                raise SystemExit(1)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
            if thread.is_alive():
                raise RuntimeError("Probe server did not stop.")


if __name__ == "__main__":
    main()
