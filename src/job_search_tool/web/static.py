"""Static dashboard asset discovery and mounting."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


PACKAGE_STATIC_DIR = Path(__file__).with_name("static_assets")
DEFAULT_EXTERNAL_STATIC_DIR = Path("/opt/job-search-tool/frontend")


def get_frontend_static_dir() -> Path | None:
    """Return the first configured frontend build directory with index.html."""
    candidates = [
        Path(os.environ["JOB_SEARCH_FRONTEND_DIST"])
        if os.environ.get("JOB_SEARCH_FRONTEND_DIST")
        else None,
        PACKAGE_STATIC_DIR,
        DEFAULT_EXTERNAL_STATIC_DIR,
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "index.html").is_file():
            return candidate
    return None


def fallback_html() -> str:
    return (
        "<!doctype html><html><head><title>Job Search</title></head>"
        "<body><h1>Job Search Web</h1>"
        "<p>React dashboard assets are not built yet.</p></body></html>"
    )


def dashboard_html() -> str:
    """Return built dashboard HTML or a local-development fallback page."""
    static_dir = get_frontend_static_dir()
    if static_dir is None:
        return fallback_html()
    return (static_dir / "index.html").read_text(encoding="utf-8")


def mount_frontend_assets(app: FastAPI) -> None:
    """Mount built frontend assets when available."""
    static_dir = get_frontend_static_dir()
    if static_dir is None:
        return

    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


def dashboard_response() -> HTMLResponse:
    return HTMLResponse(dashboard_html())
