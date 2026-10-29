"""Synthetic live MCP/HTTP proof, not production application code.

Run with the experiment venv and --contract-dir pointing to experiments/next.
Compiles on this client machine; the temporary server only stores bytes.
"""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time


def sha(data):
    return hashlib.sha256(data).hexdigest()


def serve(args):
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response
    from mcp.server.fastmcp import FastMCP
    import uvicorn

    sys.path.insert(0, os.environ["PROBE_CONTRACT_DIR"])
    from contract import Workspace, Profile, Evidence, Claim, Template, Job, Prepare, Draft

    workspace = Workspace(Path(args.database))
    profile = workspace.add_profile(Profile(name="Alex Example", headline="Backend engineer"))["id"]
    evidence = workspace.add_evidence(
        Evidence(
            profile_id=profile,
            kind="project",
            title="Example service",
            narrative="Built Python APIs; reduced latency by 20%.",
        )
    )["id"]
    claim = workspace.add_claim(
        Claim(evidence_id=evidence, text="Reduced latency by 20%.", approved=True)
    )["id"]
    template = workspace.add_template(
        Template(name="Example", tex="User LaTeX package", prompt_append="Use concise bullets.")
    )["id"]
    job = workspace.ingest(
        Job(
            source_key="manual:synthetic",
            title="Backend engineer",
            company="Example Co",
            posting="Build Python APIs.",
        )
    )["id"]
    seed = dict(profile=profile, evidence=evidence, claim=claim, template=template, job=job)
    workspace.db.execute(
        "CREATE TABLE file_version(id TEXT PRIMARY KEY,artifact_id TEXT NOT NULL REFERENCES artifact(id),kind TEXT NOT NULL,name TEXT NOT NULL,sha TEXT NOT NULL REFERENCES blob(sha256),UNIQUE(artifact_id,kind))"
    )
    workspace.db.commit()
    grants = {}
    mcp = FastMCP("synthetic-file-probe", stateless_http=True, json_response=True)

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield
        workspace.close()

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def auth(request: Request, call_next):
        if (
            request.url.path != "/transfer"
            and request.headers.get("authorization") != "Bearer " + os.environ["PROBE_TOKEN"]
        ):
            return JSONResponse({"error": "Unauthorized"}, 401)
        return await call_next(request)

    @app.get("/api/state")
    def state():
        return seed

    @app.put("/api/profile")
    def edit_profile():
        with workspace.lock, workspace.db:
            workspace.db.execute(
                "UPDATE profile SET basics=?,version=version+1 WHERE id=?",
                (json.dumps({"name": "Edited later"}), profile),
            )
        return {"updated": True}

    def grant(payload):
        key = secrets.token_urlsafe(24)
        grants[key] = {**payload, "expires": time.monotonic() + 120}
        return {"url": f"http://127.0.0.1:{args.port}/transfer?grant={key}", "expires_in": 120}

    @mcp.tool()
    def prepare_context(value: Prepare) -> dict:
        """Freeze job/profile/evidence/template instructions for an application."""
        return workspace.prepare(value)

    @mcp.tool()
    def submit_content(context_id: str, content: Draft) -> dict:
        """Create an immutable content revision; files bind to its returned ID."""
        return workspace.submit(context_id, content)

    @mcp.resource("openings://context/{context_id}")
    def context_resource(context_id: str) -> str:
        return json.dumps(workspace.get_run(context_id))

    @mcp.tool()
    def reserve_upload(
        artifact_id: str, kind: str, name: str, expected_sha: str, size: int
    ) -> dict:
        """Grant a bounded upload for one existing artifact and one expected file."""
        workspace._get("artifact", artifact_id)
        if (
            kind not in {"resume_pdf", "resume_source"}
            or not 0 < size <= 2 * 1024 * 1024
            or Path(name).name != name
        ):
            raise ValueError("Unsupported upload")
        return grant(
            dict(
                action="upload",
                artifact=artifact_id,
                kind=kind,
                name=name,
                sha=expected_sha,
                size=size,
            )
        )

    @mcp.tool()
    def files_for_revision(artifact_id: str) -> dict:
        """List metadata, not binary bytes; earlier PDFs stay on earlier revisions."""
        workspace._get("artifact", artifact_id)
        return {
            "files": [
                dict(row)
                for row in workspace.db.execute(
                    "SELECT * FROM file_version WHERE artifact_id=?", (artifact_id,)
                )
            ]
        }

    @mcp.tool()
    def download_file(file_id: str) -> dict:
        row = workspace._get("file_version", file_id)
        return grant(dict(action="download", sha=row["sha"]))

    @mcp.tool()
    def portable_backup() -> dict:
        """Create a consistent SQLite backup, including file bytes."""
        path = Path(args.database).with_name("portable.sqlite")
        workspace.backup(path)
        return grant(dict(action="backup", path=str(path)))

    @app.api_route("/transfer", methods=["GET", "PUT"])
    async def transfer(request: Request, grant: str):
        scope = grants.get(grant)
        if not scope or scope["expires"] < time.monotonic():
            return JSONResponse({"error": "Expired or invalid transfer"}, 401)
        if request.method == "GET" and scope["action"] in {"download", "backup"}:
            if scope["action"] == "backup":
                return Response(
                    Path(scope["path"]).read_bytes(), media_type="application/octet-stream"
                )
            row = workspace.db.execute(
                "SELECT content,media_type FROM blob WHERE sha256=?", (scope["sha"],)
            ).fetchone()
            return Response(bytes(row["content"]), media_type=row["media_type"])
        if request.method != "PUT" or scope["action"] != "upload":
            return JSONResponse({"error": "Wrong transfer operation"}, 403)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > scope["size"]:
                return JSONResponse({"error": "Size exceeded"}, 413)
        data = bytes(data)
        if len(data) != scope["size"] or sha(data) != scope["sha"]:
            return JSONResponse({"error": "Bytes do not match declared file"}, 422)
        with workspace.lock, workspace.db:
            old = workspace.db.execute(
                "SELECT * FROM file_version WHERE artifact_id=? AND kind=?",
                (scope["artifact"], scope["kind"]),
            ).fetchone()
            if old and old["sha"] != scope["sha"]:
                return JSONResponse({"error": "Create a new content revision"}, 409)
            if old:
                return dict(old)
            file_id = secrets.token_hex(12)
            media = "application/pdf" if scope["kind"] == "resume_pdf" else "application/x-tex"
            workspace.db.execute(
                "INSERT OR IGNORE INTO blob VALUES(?,?,?)", (scope["sha"], media, data)
            )
            workspace.db.execute(
                "INSERT INTO file_version VALUES(?,?,?,?,?)",
                (file_id, scope["artifact"], scope["kind"], scope["name"], scope["sha"]),
            )
        return {"id": file_id, "sha": scope["sha"]}

    app.mount("/agent", mcp.streamable_http_app())
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="error")


async def client(base, token, folder, tectonic):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    def unpack(result):
        if result.isError:
            raise RuntimeError(result.content[0].text)
        return json.loads(result.content[0].text)

    checks = {}
    headers = {"Authorization": "Bearer " + token}
    async with httpx.AsyncClient() as http:
        for _ in range(100):
            try:
                ready = await http.get(base + "/api/state", headers=headers)
                if ready.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.1)
        ready.raise_for_status()
        seed = ready.json()
        checks["rest_rejects_missing_auth"] = (
            await http.get(base + "/api/state")
        ).status_code == 401
        checks["mcp_rejects_missing_auth"] = (
            await http.post(base + "/agent/mcp", json={})
        ).status_code == 401
        async with streamablehttp_client(base + "/agent/mcp", headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                descriptions = {tool.name: tool.inputSchema for tool in tools.tools}
                checks["live_typed_tool_discovery"] = (
                    "properties" in descriptions["prepare_context"]
                    and "value" in descriptions["prepare_context"]["properties"]
                )
                request = dict(
                    job_id=seed["job"],
                    profile_id=seed["profile"],
                    template_id=seed["template"],
                    general_prompt="Use only supplied evidence.",
                    application_note="Prefer concise wording.",
                    idempotency_key="synthetic-context",
                )
                context = unpack(await session.call_tool("prepare_context", {"value": request}))
                again = unpack(await session.call_tool("prepare_context", {"value": request}))
                checks["prepare_is_idempotent"] = context["id"] == again["id"]
                resource = await session.read_resource(f"openings://context/{context['id']}")
                fetched = json.loads(resource.contents[0].text)
                await http.put(base + "/api/profile", headers=headers)
                resource = await session.read_resource(f"openings://context/{context['id']}")
                checks["context_survives_rest_profile_edit"] = fetched == json.loads(
                    resource.contents[0].text
                )
                content = {
                    "bullets": [
                        {
                            "text": "Reduced latency by 20%.",
                            "evidence_ids": [seed["evidence"]],
                            "claim_ids": [seed["claim"]],
                        }
                    ]
                }
                revision = unpack(
                    await session.call_tool(
                        "submit_content", {"context_id": context["id"], "content": content}
                    )
                )
                tex = b"\\documentclass{article}\n\\begin{document}\nAlex Example\\\\Backend engineer\\\\Reduced latency by 20\\%.\n\\end{document}\n"
                (folder / "resume.tex").write_bytes(tex)
                compile_result = subprocess.run(
                    [
                        tectonic,
                        "--untrusted",
                        "--only-cached",
                        "--outdir",
                        str(folder),
                        str(folder / "resume.tex"),
                    ],
                    capture_output=True,
                )
                if compile_result.returncode:
                    raise RuntimeError("External TeX compilation failed")
                pdf = (folder / "resume.pdf").read_bytes()
                checks["client_compiles_real_pdf"] = pdf.startswith(b"%PDF-")
                files = []
                for kind, name, data in [
                    ("resume_pdf", "resume.pdf", pdf),
                    ("resume_source", "resume.tex", tex),
                ]:
                    upload = unpack(
                        await session.call_tool(
                            "reserve_upload",
                            dict(
                                artifact_id=revision["id"],
                                kind=kind,
                                name=name,
                                expected_sha=sha(data),
                                size=len(data),
                            ),
                        )
                    )
                    response = await http.put(upload["url"], content=data)
                    response.raise_for_status()
                    files.append(response.json())
                    descriptor = unpack(
                        await session.call_tool("download_file", {"file_id": files[-1]["id"]})
                    )
                    restored = await http.get(descriptor["url"])
                    checks[kind + "_exact_bytes"] = restored.content == data
                    checks[kind + "_grant_rejects_wrong_method"] = (
                        await http.put(descriptor["url"], content=b"x")
                    ).status_code == 403
                content["bullets"][0]["text"] = "Built Python APIs."
                second = unpack(
                    await session.call_tool(
                        "submit_content", {"context_id": context["id"], "content": content}
                    )
                )
                newer_files = unpack(
                    await session.call_tool("files_for_revision", {"artifact_id": second["id"]})
                )
                checks["new_content_does_not_inherit_old_pdf"] = (
                    not newer_files["files"] and second["id"] != revision["id"]
                )
                backup = unpack(await session.call_tool("portable_backup", {}))
                backup_bytes = (await http.get(backup["url"])).content
                restored_path = folder / "restored.sqlite"
                restored_path.write_bytes(backup_bytes)
                with sqlite3.connect(restored_path) as database:
                    checks["portable_integrity"] = (
                        database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                    )
                    checks["portable_foreign_keys"] = not database.execute(
                        "PRAGMA foreign_key_check"
                    ).fetchall()
                    checks["portable_pdf_and_source_bytes"] = {
                        row[0] for row in database.execute("SELECT content FROM blob")
                    } == {pdf, tex}
                    checks["portable_revisions_and_context"] = (
                        database.execute("SELECT COUNT(*) FROM artifact").fetchone()[0] == 2
                        and database.execute("SELECT COUNT(*) FROM run").fetchone()[0] == 1
                    )
                return {
                    "purpose": "synthetic live MCP/HTTP feasibility proof, not production code",
                    "checks": checks,
                    "all_passed": all(checks.values()),
                    "tool_names": list(descriptions),
                    "pdf_bytes": len(pdf),
                    "source_bytes": len(tex),
                    "pdf_sha256": sha(pdf),
                    "source_sha256": sha(tex),
                    "backup_bytes": len(backup_bytes),
                    "limits": [
                        "No browser UI or real Codex/Claude invocation",
                        "Owner bearer plus short-lived scoped transfers only; no production session/OAuth implementation",
                        "Small files only, no concurrency/load/large-file benchmark",
                        "PDF correctness beyond successful local compilation is not certified",
                        "Imported experiment status enum is not the final product schema",
                    ],
                }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--database")
    parser.add_argument("--port", type=int)
    parser.add_argument("--contract-dir", type=Path)
    parser.add_argument("--tectonic", default="tectonic")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.serve:
        serve(args)
        return
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        token = secrets.token_urlsafe(24)
        environment = {
            **os.environ,
            "PROBE_CONTRACT_DIR": str(args.contract_dir.resolve()),
            "PROBE_TOKEN": token,
        }
        with tempfile.TemporaryFile() as log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    __file__,
                    "--serve",
                    "--database",
                    str(folder / "workspace.sqlite"),
                    "--port",
                    str(port),
                ],
                env=environment,
                stdout=log,
                stderr=log,
            )
            try:
                record = asyncio.run(
                    client(f"http://127.0.0.1:{port}", token, folder, args.tectonic)
                )
                args.out.write_text(json.dumps(record, indent=2) + "\n")
                print(json.dumps(record, indent=2))
                if not record["all_passed"]:
                    raise SystemExit(1)
            except Exception:
                log.seek(0)
                print(log.read().decode()[-2500:])
                raise
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    main()
