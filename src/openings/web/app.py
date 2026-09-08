"""The web process: dashboard, REST API and MCP in one ASGI application."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.applications import Starlette

from openings.project_meta import get_project_version
from openings.web.api import public_router, router as api_router
from openings.web.mcp import create_mcp_app
from openings.web.service import get_db, logger, reset_service
from openings.web.static import dashboard_response, mount_frontend_assets

DEFAULT_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"


def get_cors_allowed_origins() -> list[str]:
    raw = os.environ.get("OPENINGS_WEB_ALLOWED_ORIGINS", "")
    return list(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))


@asynccontextmanager
async def lifespan(_app: FastAPI, mcp_app: Starlette) -> AsyncIterator[None]:
    db = get_db()
    logger.info("Web server ready | %d jobs", db.count_jobs())
    try:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
    finally:
        reset_service()


def create_app() -> FastAPI:
    mcp_app = create_mcp_app()
    app = FastAPI(
        title="Openings",
        version=get_project_version(),
        lifespan=lambda fastapi_app: lifespan(fastapi_app, mcp_app),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_allowed_origins(),
        allow_origin_regex=DEFAULT_CORS_ORIGIN_REGEX,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Openings-Token"],
    )
    app.include_router(public_router)
    app.include_router(api_router)
    app.mount("/mcp", mcp_app)
    mount_frontend_assets(app)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "jobs_count": get_db().count_jobs()}

    @app.get("/")
    def index() -> HTMLResponse:
        return dashboard_response()

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("OPENINGS_WEB_LISTEN_PORT", "8501")))


if __name__ == "__main__":
    main()
