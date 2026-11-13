"""REST routes and MCP tools, one module per area, bound to the shared services.

Each area module declares its operations (``OPERATIONS``), and may declare
transport exemptions (``EXEMPTIONS``) and hand-registered MCP resources or
prompts (``SURFACES``). ``catalog`` collects them for ``/api/v1/capabilities``
and the interface tests.
"""

from . import (
    activity,
    agent_requests,
    career,
    core,
    discovery,
    documents,
    insights,
    preferences,
    skills,
    source_yield,
    system,
)

AREAS = (
    system,
    core,
    skills,
    career,
    documents,
    discovery,
    activity,
    agent_requests,
    preferences,
    insights,
    source_yield,
)


def catalog():
    """Every declared operation, exemption and surface, by area in registration order."""
    operations, exemptions, surfaces = [], [], []
    for area in AREAS:
        operations.extend(area.OPERATIONS)
        exemptions.extend(getattr(area, "EXEMPTIONS", ()))
        surfaces.extend(getattr(area, "SURFACES", ()))
    return operations, exemptions, surfaces
