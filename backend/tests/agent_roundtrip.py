"""Practical external-agent round trip against an isolated production workspace.

Requires the development environment and an external Tectonic executable.
The standalone-registration option supports module development before root integration;
normal execution requires the production app to register all services itself.
"""

import argparse
import asyncio
import hashlib
import json
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
import httpx2
import uvicorn
from fastapi import APIRouter
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from openings.app import create_app


def unpack(result):
    if result.is_error:
        raise RuntimeError(result.content[0].text)
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(item.text for item in result.content if item.type == "text"))


async def exercise(base, token, folder, tectonic):
    headers = {"Authorization": f"Bearer {token}"}
    checks = {}
    async with httpx.AsyncClient(headers=headers, timeout=30) as http:
        async with httpx.AsyncClient() as anonymous:
            checks["rest_requires_owner"] = (
                await anonymous.get(base + "/api/v1/career/profile")
            ).status_code == 401
        # Kept nested: merging the two contexts would re-indent the whole driver body.
        # The SDK client speaks httpx2; it takes its headers from the client it is given.
        async with httpx2.AsyncClient(headers=headers, timeout=30) as agent_http:  # noqa: SIM117
            async with Client(
                streamable_http_client(base + "/mcp/", http_client=agent_http)
            ) as session:
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                by_name = {tool.name: tool for tool in tools.tools}
                checks["typed_module_discovery"] = {
                    "profile_get",
                    "templates_create",
                    "contexts_create",
                    "files_reserve_upload",
                } <= names
                checks["career_file_tool_annotations"] = (
                    by_name["knowledge_list"].annotations.read_only_hint
                    and by_name["documents_get"].annotations.read_only_hint
                    and by_name["documents_delete"].annotations.destructive_hint
                    and not by_name["files_reserve_upload"].annotations.read_only_hint
                    and not by_name["files_reserve_upload"].annotations.open_world_hint
                )
                profile = unpack(await session.call_tool("profile_get", {}))
                unpack(
                    await session.call_tool(
                        "profile_update",
                        {
                            "value": {
                                "expected_version": profile["version"],
                                "name": "Alex Example",
                                "headline": "Backend engineer",
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
                tex = (Path(__file__).resolve().parents[2] / "examples/cv.tex").read_text()
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
                        "jobs_create",
                        {
                            "value": {
                                "title": "Backend engineer",
                                "company": "Example Co",
                                "posting": "Build Python APIs.",
                            }
                        },
                    )
                )
                job = unpack(
                    await session.call_tool(
                        "jobs_triage",
                        {
                            "job_id": job["id"],
                            "value": {"triage": "shortlisted", "expected_version": job["version"]},
                        },
                    )
                )
                checks["shortlist_starts_the_application"] = (
                    unpack(
                        await session.call_tool("jobs_list", {"value": {"triage": "shortlisted"}})
                    )["total"]
                    == 1
                    and job["application"]["status"] == "shortlisted"
                )
                second_start = await session.call_tool(
                    "applications_create", {"value": {"job_id": job["id"]}}
                )
                checks["one_open_application_per_job"] = second_start.is_error
                application = unpack(
                    await session.call_tool(
                        "applications_get", {"application_id": job["application"]["id"]}
                    )
                )
                checks["cv_and_letter_required_by_default"] = (
                    application["required_documents"] == ["cv", "letter"]
                    and application["missing"] == ["cv", "letter"]
                    and application["ready"] is False
                )
                # Standing guidance is the application's pinned note (the note field is gone).
                pinned = unpack(
                    await session.call_tool(
                        "notes_create",
                        {
                            "job_id": job["id"],
                            "value": {
                                "body": "Prefer technical detail.",
                                "application_id": application["id"],
                                "pinned": True,
                            },
                        },
                    )
                )
                removed = await session.call_tool(
                    "applications_update",
                    {
                        "application_id": application["id"],
                        "value": {"expected_version": application["version"], "note": "Gone"},
                    },
                )
                flat = await session.call_tool("knowledge_list", {"q": "Example API"})
                unversioned = await session.call_tool("notes_delete", {"note_id": pinned["id"]})
                gone = [
                    name
                    for name in ("documents_review", "applications_ready", "responses_create")
                    if name in names
                ]
                checks["removed_fields_and_tools_refused"] = (
                    removed.is_error
                    and flat.is_error
                    and unversioned.is_error
                    and "expected_version" in unversioned.content[0].text
                    and gone == []
                )
                context = unpack(
                    await session.call_tool(
                        "contexts_create",
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
                checks["pinned_note_in_context"] = (
                    context["payload"]["application"]["note"] == "Prefer technical detail."
                    and "roles" not in context["payload"]["profile"]
                )
                checks["stored_instructions_in_context"] = (
                    bool(context["payload"]["preferences"]["writing"]["items"])
                    and context["payload"]["instructions"]["template_append"][template["id"]]
                    == "Use concise evidence-backed bullets."
                )
                source = folder / "application.tex"
                source.write_text(context["payload"]["templates"][0]["tex"])
                subprocess.run(  # noqa: ASYNC221 - sequential manual driver
                    [tectonic, "--untrusted", "--outdir", str(folder), str(source)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=120,
                )
                pdf = source.with_suffix(".pdf").read_bytes()
                checks["external_compilation"] = pdf.startswith(b"%PDF-")
                refused = await session.call_tool(
                    "documents_create",
                    {
                        "value": {
                            "application_id": application["id"],
                            "kind": "cv",
                            "content": {"text": "Free-form wording."},
                        }
                    },
                )
                checks["cv_content_refused"] = refused.is_error and (
                    "content_not_accepted" in refused.content[0].text
                    or "optional TeX source" in refused.content[0].text
                )
                tex_bytes = source.read_bytes()
                tex_sha = hashlib.sha256(tex_bytes).hexdigest()

                def spec(name, data):
                    return {
                        "name": name,
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }

                async def put(grant, data):
                    response = await http.put(
                        urljoin(base, grant["url"]), headers=grant["headers"], content=data
                    )
                    if response.status_code >= 400:
                        return None, response.text
                    return response.json(), None

                document = unpack(
                    await session.call_tool(
                        "documents_create",
                        {
                            "value": {
                                "application_id": application["id"],
                                "context_id": context["id"],
                                "kind": "cv",
                                "title": "CV",
                                "claim_ids": [claim["id"]],
                                "knowledge_ids": [evidence["id"]],
                                "note": "Built from the synthetic template.",
                                "source_file": spec("application.tex", tex_bytes),
                                "pdf": spec("application.pdf", pdf),
                            }
                        },
                    )
                )
                checks["cv_has_no_content"] = "content" not in document
                checks["create_returns_grants"] = (
                    document["complete"] is False
                    and document["uploads"]["source"] is not None
                    and document["uploads"]["pdf"] is not None
                )
                _, early = await put(document["uploads"]["pdf"], pdf)
                checks["pdf_waits_for_its_source"] = bool(early) and "source" in early
                uploaded = []
                for kind, data in (("source", tex_bytes), ("pdf", pdf)):
                    stored, error = await put(document["uploads"][kind], data)
                    if error:
                        raise RuntimeError(error)
                    uploaded.append(stored)
                    download = unpack(
                        await session.call_tool("files_reserve_download", {"file_id": stored["id"]})
                    )
                    fetched = await http.get(
                        urljoin(base, download["url"]), headers=download["headers"]
                    )
                    checks["exact_" + stored["name"]] = fetched.content == data
                checks["pdf_names_its_source"] = uploaded[1]["source_sha256"] == tex_sha
                current = unpack(
                    await session.call_tool("documents_get", {"document_id": document["id"]})
                )
                checks["text_derived_from_source"] = (
                    current["source_sha256"] == tex_sha
                    and current["complete"] is True
                    and current["text_from"] == "tex"
                    and "Reduced API p95 latency by 20%" in (current["text"] or "")
                    and "\\" not in current["text"]
                    and current["claim_ids"] == [claim["id"]]
                )
                checks["complete_revision_is_immutable"] = (
                    await session.call_tool(
                        "files_reserve_upload",
                        {
                            "value": {
                                "owner_type": "document",
                                "owner_id": document["id"],
                                "name": "late.pdf",
                                "media_type": "application/pdf",
                                "size": len(pdf),
                            }
                        },
                    )
                ).is_error
                # A letter without TeX: the PDF alone, its text read from the PDF.
                letter = unpack(
                    await session.call_tool(
                        "documents_create",
                        {
                            "value": {
                                "application_id": application["id"],
                                "kind": "letter",
                                "pdf": spec("letter.pdf", pdf),
                            }
                        },
                    )
                )
                checks["letter_needs_no_source"] = letter["uploads"]["source"] is None
                _, error = await put(letter["uploads"]["pdf"], pdf)
                letter = unpack(
                    await session.call_tool("documents_get", {"document_id": letter["id"]})
                )
                checks["pdf_only_text_from_pdf"] = (
                    error is None
                    and letter["complete"]
                    and letter["text_from"] == "pdf"
                    and "Example" in (letter["text"] or "")
                )
                ready = unpack(
                    await session.call_tool("applications_list", {"value": {"stage": "ready"}})
                )
                checks["ready_is_computed"] = [item["id"] for item in ready["items"]] == [
                    application["id"]
                ] and ready["items"][0]["missing"] == []
                revised = unpack(
                    await session.call_tool(
                        "documents_create",
                        {
                            "value": {
                                "application_id": application["id"],
                                "previous_id": document["id"],
                                "kind": "cv",
                                "note": "Edited source awaiting a newly compiled PDF.",
                                "source": tex_bytes.decode().replace(
                                    "Linux.", "Linux, Kubernetes."
                                ),
                                "pdf": spec("application.pdf", pdf),
                            }
                        },
                    )
                )
                checks["revision_has_no_inherited_pdf"] = [
                    file["name"] for file in revised["files"]
                ] == ["cv.tex"] and not revised["complete"]
                checks["incomplete_revision_clears_ready"] = unpack(
                    await session.call_tool(
                        "applications_get", {"application_id": application["id"]}
                    )
                )["missing"] == ["cv"]
                _, mismatch = await put(revised["uploads"]["pdf"], pdf + b"\n")
                comparison = unpack(
                    await session.call_tool("documents_compare", {"document_id": revised["id"]})
                )
                checks["changed_source_compared"] = (
                    comparison["other_id"] == document["id"]
                    and (comparison["added"], comparison["removed"]) == (1, 1)
                    and [line["change"] for line in comparison["lines"] if line["change"] != "same"]
                    == ["removed", "added"]
                )
                checks["pdf_grant_bound_to_its_bytes"] = bool(mismatch)
                summaries = unpack(
                    await session.call_tool(
                        "documents_list",
                        {
                            "value": {
                                "application_id": application["id"],
                                "summary": True,
                                "limit": 1,
                            }
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
                    and summaries["total"] == 3
                    and "content" not in summaries["items"][0]
                    and "files" not in summaries["items"][0]
                    and summaries["items"][0]["revision_number"] == 2
                )
                checks["summary_filters_preserve_detail"] = (
                    unpack(
                        await session.call_tool(
                            "knowledge_list",
                            {"value": {"summary": True, "q": "Example API"}},
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
                            {"value": {"application_id": application["id"], "summary": True}},
                        )
                    )["items"][0]["document_count"]
                    == 2
                )
                current = unpack(
                    await session.call_tool(
                        "applications_get", {"application_id": application["id"]}
                    )
                )
                checks["files_do_not_mark_application_sent"] = (
                    current["status"] == "shortlisted" and current["applied_at"] is None
                )
                # The owner reports sending it and an interview invitation.
                for value in ({"status": "applied"}, {"reply": {"kind": "interview"}}):
                    current = unpack(
                        await session.call_tool(
                            "applications_update",
                            {
                                "application_id": application["id"],
                                "value": {"expected_version": current["version"], **value},
                            },
                        )
                    )
                checks["reply_moves_the_stage"] = current["status"] == "interview" and [
                    reply["kind"] for reply in current["replies"]
                ] == ["interview"]
                current = unpack(
                    await session.call_tool(
                        "applications_update",
                        {
                            "application_id": application["id"],
                            "value": {
                                "expected_version": current["version"],
                                "reply": {"kind": "rejection"},
                            },
                        },
                    )
                )
                checks["closing_keeps_the_shortlist"] = (
                    (current["status"], current["outcome"]) == ("closed", "rejected")
                    and unpack(
                        await session.call_tool("jobs_list", {"value": {"triage": "shortlisted"}})
                    )["total"]
                    == 1
                    and unpack(await session.call_tool("jobs_list", {"value": {"triage": "new"}}))[
                        "total"
                    ]
                    == 0
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
                            "SELECT content FROM blobs WHERE sha256=?", (uploaded[1]["sha256"],)
                        ).fetchone()[0]
                        == pdf
                    )
                    checks["backup_context_and_revisions"] = (
                        restored.execute("SELECT COUNT(*) FROM contexts").fetchone()[0] == 1
                        and restored.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 3
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
            from openings.interfaces import (
                career as career_interface,
                documents as documents_interface,
            )

            service = career.CareerService(app.state.workspace)
            files = documents.DocumentService(app.state.workspace)
            router = APIRouter(prefix="/api/v1")
            career_interface.register_api(router, service)
            documents_interface.register_api(router, files)
            career_interface.register_mcp(app.state.mcp, service)
            documents_interface.register_mcp(app.state.mcp, files)
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
