"""Hand-written routes: bytes, streams, browser sessions and protocol plumbing.

Each is listed in ``TRANSPORT_ONLY`` with the reason it is not an operation
(``test_parity.py`` checks the list against the served routes). Routes removed
in 0.24 answer ``410 Gone`` with what replaces them (``removed.py``).
"""

import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from .. import __version__, backups
from ..actors import current_actor, require_owner
from ..auth import COOKIE, MAX_AGE
from ..db import SCHEMA_VERSION
from ..errors import DomainError
from ..operations import backup_file_for, restore_upload
from ..removed import ROUTES
from ..skills import SKILL_FILE, read_skill
from ..transfers import RecordsResponse, export_records
from .operation import API_PREFIX, capability_entries
from .system import PasswordInput

TRANSPORT_ONLY = (
    ("GET", "/auth/session", "Browser session state before sign-in; MCP uses a bearer token."),
    ("POST", "/auth/setup", "Sets the first owner password and signs the browser in."),
    ("POST", "/auth/login", "Signs the browser in with a session cookie."),
    ("POST", "/auth/logout", "Ends every browser session; API and MCP tokens stay valid."),
    ("GET", "/capabilities", "A small REST summary of the operations; tools/list serves MCP."),
    ("GET", "/backup", "Streams a SQLite backup, with a session, a token or a grant."),
    ("POST", "/backup/restore", "Owner only: receives a raw SQLite upload that replaces data."),
    ("GET", "/backups/{name}", "Owner only: streams a kept backup file."),
    ("GET", "/export", "Owner only: streams the JSON records, with a session, a token or a grant."),
    ("GET", "/examples", "Lists the shipped example files, not workspace records."),
    ("GET", "/examples/{name}", "Downloads a shipped example file."),
    ("PUT", "/transfers", "Receives raw file bytes under an upload grant (files_upload)."),
    ("GET", "/transfers", "Streams raw file bytes under a download grant."),
    ("GET", "/files/{file_id}/content", "Streams a file's bytes for the dashboard preview."),
    ("GET", "/skills/{name}/files/{path}", "A skill file by path, so relative links resolve."),
    ("GET", "/health", "Container liveness, outside the API and without authentication."),
    ("POST", "/mcp/", "The MCP streamable HTTP endpoint (tools/list, tools/call)."),
)
EXAMPLES = ("career.json", "preferences.json", "cv.tex", "letter.tex")


def _examples():
    default = Path(__file__).resolve().parents[3] / "examples"
    return Path(os.environ.get("OPENINGS_EXAMPLES", default))


def register_transport(app, router, public_url):
    workspace, auth = app.state.workspace, app.state.auth

    def signed_in(request, password, setup=False):
        if setup:
            auth.setup(password)
        token, session = auth.login(password)
        response = JSONResponse(
            {"configured": True, "authenticated": True, "csrf_token": session["csrf"]}
        )
        secure = request.url.scheme == "https" or public_url.startswith("https://")
        response.set_cookie(
            COOKIE, token, max_age=MAX_AGE, httponly=True, secure=secure, samesite="strict"
        )
        return response

    @router.get("/auth/session", tags=["workspace"], openapi_extra={"security": []})
    def session(request: Request):
        """Read the browser session state and its CSRF token."""
        state = auth.session(request)
        return {
            "configured": auth.configured(),
            "authenticated": bool(state),
            "csrf_token": state["csrf"] if state else None,
        }

    @router.post("/auth/setup", tags=["workspace"], openapi_extra={"security": []})
    def setup(request: Request, value: PasswordInput):
        """Set the owner password once and sign the browser in."""
        return signed_in(request, value.password, True)

    @router.post("/auth/login", tags=["workspace"], openapi_extra={"security": []})
    def login(request: Request, value: PasswordInput):
        """Sign the browser in with the owner password."""
        return signed_in(request, value.password)

    @router.post("/auth/logout", tags=["workspace"])
    def logout():
        """Sign out every browser session; API and MCP tokens stay valid."""
        response = JSONResponse(auth.logout())
        response.delete_cookie(COOKIE, path="/")
        return response

    @router.get("/capabilities", tags=["workspace"])
    def capabilities():
        """Read the version, schema, this token's kind and each operation's route and access."""
        actor = current_actor()
        return {
            "version": __version__,
            "schema": SCHEMA_VERSION,
            "token_kind": actor.token_kind or ("session" if actor.kind == "owner" else None),
            "api_base": API_PREFIX,
            "operations": capability_entries(),
        }

    @router.get("/backup", tags=["workspace"], response_class=FileResponse)
    def backup():
        """Download a consistent SQLite backup with file bytes.

        With an agent token or its grant, the owner password hash, session secret and
        tokens are left out.
        """
        name = backup_file_for(workspace, current_actor())
        return FileResponse(
            name,
            media_type="application/vnd.sqlite3",
            filename="openings-backup.sqlite",
            background=BackgroundTask(workspace.db.remove_temp, name),
        )

    @router.post("/backup/restore", tags=["owner"], openapi_extra={"x-openings-access": "owner"})
    async def restore(request: Request):
        """Replace the workspace data with a SQLite backup (owner only).

        Send the raw file as application/vnd.sqlite3. Installation authentication stays.
        """
        require_owner("restore a backup")
        return await restore_upload(workspace, request.headers, request.stream())

    @router.get(
        "/backups/{name}",
        tags=["owner"],
        response_class=FileResponse,
        openapi_extra={"x-openings-access": "owner"},
    )
    def backup_file(name: str):
        """Download a kept backup or pre-upgrade copy (owner only)."""
        require_owner("download a kept backup")
        _, path = backups.find(workspace.db, name)
        return FileResponse(path, media_type="application/vnd.sqlite3", filename=path.name)

    @router.get("/export", tags=["owner"], openapi_extra={"x-openings-access": "owner"})
    def export():
        """Download the workspace records as JSON, without file bytes or credentials (owner only)."""
        require_owner("export the records")
        return RecordsResponse(export_records(workspace.db))

    @router.get("/examples", tags=["workspace"])
    def examples():
        """List the shipped example files."""
        directory = _examples()
        return {
            "items": [
                {"name": name, "url": "/api/v1/examples/" + name}
                for name in EXAMPLES
                if (directory / name).is_file()
            ]
        }

    @router.get("/examples/{name}", tags=["workspace"], response_class=FileResponse)
    def example_file(name: str):
        """Download a shipped example file."""
        path = _examples() / name
        if name not in EXAMPLES or not path.is_file():
            raise DomainError(404, "not_found", "Example not found.")
        return FileResponse(path, filename=name)

    @router.put("/transfers", tags=["files"], openapi_extra={"security": []})
    async def upload(request: Request):
        """Upload raw file bytes with a grant.

        The second step of files_upload or of a revision's uploads: PUT the exact bytes to
        the grant's url with its headers (X-Transfer-Token). Returns the file.
        """
        return await app.state.documents.upload(request)

    @router.get("/transfers", tags=["files"], openapi_extra={"security": []})
    def download(request: Request):
        """Download raw file bytes with a grant (X-Transfer-Token)."""
        return app.state.documents.download(request)

    @router.get("/files/{file_id}/content", tags=["files"])
    def file_content(file_id: str, inline: bool = True):
        """Read a file's bytes; inline=false downloads it."""
        return app.state.documents.file_response(file_id, inline)

    @router.get("/skills/{name}/files/{path:path}", tags=["workspace"])
    def skill_file(name: str, path: str):
        """Read a skill's reference file by path, as skills_get with path."""
        return read_skill(app.state.skills, name, path)

    @app.get("/health", tags=["workspace"], openapi_extra={"security": []})
    def health():
        """Report liveness, the last backup and the worker heartbeat."""
        workspace.db.one("SELECT 1")
        backup = backups.status(workspace.db)
        worker = workspace.worker
        age = worker.heartbeat_age() if worker else None
        body = {
            "status": "ok",
            "version": __version__,
            "backup": {key: backup[key] for key in ("last_at", "age_hours", "ok")},
            "worker": {"heartbeat_age_seconds": None if age is None else round(age, 1)},
        }
        # A stalled scheduler fails the container healthcheck; a restore restarts it.
        if worker and not workspace.maintenance and worker.stalled():
            return JSONResponse({**body, "status": "worker_stalled"}, status_code=503)
        return body

    for item in ROUTES:
        for route in item.routes:
            method, path = route.split(" ", 1)
            router.add_api_route(path, _gone(item), methods=[method], include_in_schema=False)


def _gone(item):
    def gone():
        raise DomainError(410, "removed", item.message, {"use": item.use})

    return gone


def register_prompts(mcp, library):
    """Each shipped skill as an MCP prompt (its instructions) and as resources.

    The resources are ``openings://skills/<name>`` for ``SKILL.md`` and
    ``openings://skills/<name>/<path>`` for a reference file, for clients that load
    resources instead of calling skills_get.
    """
    for item in library.list():
        name = item["name"]
        mcp.prompt(name=name, description=item["description"][:1024])(_prompt(library, name))
        for path in item["files"]:
            uri = f"openings://skills/{name}" + ("" if path == SKILL_FILE else f"/{path}")
            mcp.resource(
                uri,
                name=name if path == SKILL_FILE else f"{name}/{path}",
                description=item["summary"] if path == SKILL_FILE else None,
                mime_type="text/markdown",
            )(_resource(library, name, path))


def _resource(library, name, path):
    """A skill file, read when a client asks, so it always matches the shipped text."""

    def content() -> str:
        return read_skill(library, name, path)["content"]

    return content


def _prompt(library, name):
    """The prompt of one skill: a function without parameters, so it declares no arguments."""

    def instructions() -> str:
        skill = read_skill(library, name)["content"]
        return (
            f"Follow the Openings `{name}` skill below. Read referenced files with "
            f"skills_get(name, path); `../<skill>/...` links name another skill.\n\n{skill}"
        )

    instructions.__name__ = instructions.__qualname__ = name.replace("-", "_")
    return instructions
