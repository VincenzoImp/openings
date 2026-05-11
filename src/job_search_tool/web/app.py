"""Unified ASGI web server for Job Search Tool."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.applications import Starlette

from job_search_tool.job_service import close_db, get_db, logger
from job_search_tool.project_meta import get_project_version
from job_search_tool.web.api import public_router as public_api_router
from job_search_tool.web.api import router as api_router
from job_search_tool.web.mcp import create_mcp_app
from job_search_tool.web.static import dashboard_response, mount_frontend_assets


DEFAULT_CORS_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"


def _env_csv(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_cors_allowed_origins() -> list[str]:
    """Return exact browser origins allowed to call the API across origins."""
    return list(dict.fromkeys(_env_csv("JOB_SEARCH_WEB_ALLOWED_ORIGINS")))


@asynccontextmanager
async def lifespan(_app: FastAPI, mcp_app: Starlette) -> AsyncIterator[None]:
    db = get_db()
    logger.info("Web server ready | %d jobs", db.get_job_count())
    try:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
    finally:
        close_db()


def create_app() -> FastAPI:
    """Create the unified FastAPI application."""
    mcp_app = create_mcp_app()
    app = FastAPI(
        title="Job Search Tool Web",
        version=get_project_version(),
        lifespan=lambda fastapi_app: lifespan(fastapi_app, mcp_app),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_allowed_origins(),
        allow_origin_regex=DEFAULT_CORS_ORIGIN_REGEX,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Job-Search-Token"],
    )
    app.include_router(public_api_router)
    app.include_router(api_router)
    app.mount("/mcp", mcp_app)
    mount_frontend_assets(app)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "jobs_count": get_db().get_job_count()}

    @app.get("/")
    def index() -> HTMLResponse:
        return dashboard_response()

    return app


app = create_app()


def main() -> None:
    """Run the unified web server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8501)


if __name__ == "__main__":
    main()
