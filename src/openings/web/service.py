"""The service the web process hands to every route and tool."""

from __future__ import annotations

from openings.application.jobs import JobApplicationService
from openings.runtime import get_runtime


def get_service() -> JobApplicationService:
    return get_runtime().service
