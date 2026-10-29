"""Practical external-agent round trip against an isolated production workspace.

Requires the development environment and an external Tectonic executable.
The standalone-registration option supports module development before root integration;
normal execution requires the production app to register all services itself.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
from urllib.parse import urljoin

from fastapi import APIRouter
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import uvicorn

from openings.app import create_app


def unpack(result):
    if result.isError:
        raise RuntimeError(result.content[0].text)
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(next(item.text for item in result.content if item.type == "text"))


async def exercise(base, token, folder, tectonic):
    headers = {"Authorization": f"Bearer {token}"}
    checks = {}
    async with httpx.AsyncClient(headers=headers, timeout=30) as http:
        async with httpx.AsyncClient() as anonymous:
            checks["rest_requires_owner"] = (
                await anonymous.get(base + "/api/v1/career/profile")
            ).status_code == 401
        async with streamablehttp_client(base + "/mcp/", headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                by_name = {tool.name: tool for tool in tools.tools}
                checks["typed_module_discovery"] = {
                    "career_get_profile",
                    "templates_create",
                    "application_prepare_context",
                    "files_reserve_upload",
                } <= names
                checks["career_file_tool_annotations"] = (
                    by_name["knowledge_list"].annotations.readOnlyHint
                    and by_name["documents_get"].annotations.readOnlyHint
                    and by_name["documents_delete"].annotations.destructiveHint
                    and not by_name["files_reserve_upload"].annotations.readOnlyHint
                    and not by_name["files_reserve_upload"].annotations.openWorldHint
                )
                profile = unpack(await session.call_tool("career_get_profile", {}))
                unpack(
                    await session.call_tool(
                        "career_update_profile",
                        {
                            "value": {
                                "expected_version": profile["version"],
                                "name": "Alex Example",
                                "roles": "Backend engineer",
                                "summary": "Built Python APIs and reduced latency by 20%.",
                            }
                        },
                    )
                )
                evidence = unpack(
                    await session.call_tool(
                        "knowledge_create",
                        {
                            "value": {
                                "kind": "project",
                                "title": "Example API",
                                "narrative": "Built Python APIs and reduced latency by 20%.",
                            }
                        },
                    )
                )
                claim = unpack(
                    await session.call_tool(
                        "claims_create",
                        {
                            "value": {
                                "knowledge_id": evidence["id"],
                                "text": "Reduced latency by 20%.",
                                "approved": True,
                            }
                        },
                    )
                )
                tex = (Path(__file__).resolve().parents[2] / "examples/resume.tex").read_text()
                template = unpack(
                    await session.call_tool(
                        "templates_create",
                        {
                            "value": {
                                "name": "Synthetic CV",
                                "tex": tex,
                                "guidance": "Use concise evidence-backed bullets.",
                                "rules": {"max_bullet_chars": 150},
                            }
                        },
                    )
                )
                job = unpack(
                    await session.call_tool(
                        "job_ingest",
                        {
                            "value": {
                                "title": "Backend engineer",
                                "company": "Example Co",
                                "posting": "Build Python APIs.",
                            }
                        },
                    )
                )
                application = unpack(
                    await session.call_tool(
                        "application_create",
                        {"value": {"job_id": job["id"], "note": "Prefer technical detail."}},
                    )
                )
                context = unpack(
                    await session.call_tool(
                        "application_prepare_context",
                        {
                            "value": {
                                "application_id": application["id"],
                                "template_id": template["id"],
                                "idempotency_key": "agent-preparation",
                            }
                        },
                    )
                )
                resource = await session.read_resource(context["resource_uri"])
                checks["context_resource"] = (
                    json.loads(resource.contents[0].text)["signature"] == context["signature"]
                )
                checks["stored_instructions_in_context"] = (
                    bool(context["payload"]["instructions"]["general"])
                    and context["payload"]["instructions"]["template_append"][template["id"]]
                    == "Use concise evidence-backed bullets."
                )
                source = folder / "application.tex"
                source.write_text(context["payload"]["templates"][0]["tex"])
                subprocess.run(
                    [tectonic, "--untrusted", "--outdir", str(folder), str(source)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=120,
                )
                pdf = source.with_suffix(".pdf").read_bytes()
                checks["external_compilation"] = pdf.startswith(b"%PDF-")
                document = unpack(
                    await session.call_tool(
                        "documents_create",
                        {
                            "value": {
                                "application_id": application["id"],
                                "context_id": context["id"],
                                "kind": "resume",
                                "title": "CV",
                                "content": {
                                    "bullets": [
                                        {
                                            "text": "Reduced latency by 20%.",
                                            "evidence_ids": [evidence["id"]],
                                            "claim_ids": [claim["id"]],
                                        }
                                    ]
                                },
                            }
                        },
                    )
                )
                uploaded = []
                for name, data, media in [
                    ("application.pdf", pdf, "application/pdf"),
                    ("application.tex", source.read_bytes(), "application/x-tex"),
                ]:
                    reservation = unpack(
                        await session.call_tool(
                            "files_reserve_upload",
                            {
                                "value": {
                                    "owner_type": "document",
                                    "owner_id": document["id"],
                                    "name": name,
                                    "media_type": media,
                                    "size": len(data),
                                    "sha256": hashlib.sha256(data).hexdigest(),
                                }
                            },
                        )
                    )
                    response = await http.put(
                        urljoin(base, reservation["url"]),
                        headers=reservation["headers"],
                        content=data,
                    )
                    response.raise_for_status()
                    stored = response.json()
                    uploaded.append(stored)
                    download = unpack(
                        await session.call_tool("files_reserve_download", {"file_id": stored["id"]})
                    )
                    fetched = await http.get(
                        urljoin(base, download["url"]), headers=download["headers"]
                    )
                    checks["exact_" + name] = fetched.content == data
                revised = unpack(
                    await session.call_tool(
                        "documents_create",
                        {
                            "value": {
                                "application_id": application["id"],
                                "previous_id": document["id"],
                                "kind": "resume",
                                "content": {
                                    "text": "Edited content awaiting a newly compiled PDF."
                                },
                            }
                        },
                    )
                )
                checks["revision_has_no_inherited_pdf"] = revised["files"] == []
                summaries = unpack(
                    await session.call_tool(
                        "documents_list",
                        {
                            "application_id": application["id"],
                            "summary": True,
                            "limit": 1,
                        },
                    )
                )
                rest_summaries = (
                    await http.get(
                        base + "/api/v1/documents",
                        params={
                            "application_id": application["id"],
                            "summary": "true",
                            "limit": 1,
                        },
                    )
                ).json()
                checks["rest_mcp_compact_document_page"] = (
                    summaries == rest_summaries
                    and summaries["total"] == 2
                    and "content" not in summaries["items"][0]
                    and "files" not in summaries["items"][0]
                    and summaries["items"][0]["revision_number"] == 2
                )
                checks["summary_filters_preserve_detail"] = (
                    unpack(
                        await session.call_tool(
                            "knowledge_list",
                            {
                                "summary": True,
                                "q": "Example API",
                            },
                        )
                    )["items"][0]["id"]
                    == evidence["id"]
                    and unpack(
                        await session.call_tool(
                            "templates_get",
                            {
                                "template_id": template["id"],
                            },
                        )
                    )["tex"]
                    == tex
                    and unpack(
                        await session.call_tool(
                            "contexts_list",
                            {
                                "application_id": application["id"],
                                "summary": True,
                            },
                        )
                    )["items"][0]["document_count"]
                    == 2
                )
                checks["files_do_not_mark_application_sent"] = (
                    unpack(
                        await session.call_tool(
                            "application_get", {"application_id": application["id"]}
                        )
                    )["status"]
                    == "draft"
                )
                response = await http.get(base + "/api/v1/backup")
                response.raise_for_status()
                backup = folder / "backup.sqlite"
                backup.write_bytes(response.content)
                with sqlite3.connect(backup) as restored:
                    checks["backup_integrity"] = (
                        restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                    )
                    checks["backup_foreign_keys"] = (
                        restored.execute("PRAGMA foreign_key_check").fetchall() == []
                    )
                    checks["backup_exact_pdf"] = (
                        restored.execute(
                            "SELECT content FROM blobs WHERE sha256=?", (uploaded[0]["sha256"],)
                        ).fetchone()[0]
                        == pdf
                    )
                    checks["backup_context_and_revisions"] = (
                        restored.execute("SELECT COUNT(*) FROM contexts").fetchone()[0] == 1
                        and restored.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 2
                    )
    return {
        "purpose": "new production-module MCP/REST/external-compilation/file/backup round trip",
        "checks": checks,
        "all_passed": all(checks.values()),
        "pdf_bytes": len(pdf),
        "tools_discovered": len(names),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--tectonic", default="tectonic")
    parser.add_argument("--standalone-registration", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        app = create_app(folder / "workspace.sqlite", start_worker=False)
        if args.standalone_registration:
            from openings import career, documents

            service = career.CareerService(app.state.workspace)
            files = documents.DocumentService(app.state.workspace)
            router = APIRouter(prefix="/api/v1")
            career.register_api(router, service)
            documents.register_api(router, files)
            career.register_mcp(app.state.mcp, service)
            documents.register_mcp(app.state.mcp, files)
            catchalls = [
                route for route in app.router.routes if getattr(route, "path", "") == "/{path:path}"
            ]
            app.router.routes = [route for route in app.router.routes if route not in catchalls]
            app.include_router(router)
            app.router.routes += catchalls
        if not app.state.auth.configured():
            app.state.auth.setup("synthetic-probe-password")
        token = app.state.auth.create_token("synthetic-agent-probe")["token"]
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
            record = asyncio.run(exercise(f"http://127.0.0.1:{port}", token, folder, args.tectonic))
            record["standalone_registration"] = args.standalone_registration
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
