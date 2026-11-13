"""REST routes and MCP tools, one module per area, bound to the shared services.

Each area module declares its operations (``OPERATIONS``), and may declare
transport exemptions (``EXEMPTIONS``) and hand-registered MCP resources or
prompts (``SURFACES``). ``catalog`` collects them for the operation inventory
and the interface tests.
"""

import json
from pathlib import Path

from . import (
    activity,
    agent_requests,
    career,
    core,
    discovery,
    documents,
    insights,
    outcomes,
    policy,
    skills,
    source_yield,
    system,
)
from .registry import inventory

AREAS = (
    system,
    core,
    skills,
    career,
    documents,
    discovery,
    activity,
    agent_requests,
    policy,
    outcomes,
    insights,
    source_yield,
)
NOTES = Path(__file__).with_name("inventory-notes.json")


def catalog():
    """Every declared operation, exemption and surface, by area in registration order."""
    operations, exemptions, surfaces = [], [], []
    for area in AREAS:
        operations.extend(area.OPERATIONS)
        exemptions.extend(getattr(area, "EXEMPTIONS", ()))
        surfaces.extend(getattr(area, "SURFACES", ()))
    return operations, exemptions, surfaces


def inventory_document():
    """The operation inventory generated from the declarations and their remarks."""
    operations, exemptions, _ = catalog()
    return inventory(operations, exemptions, json.loads(NOTES.read_text()))


def inventory_text():
    return json.dumps(inventory_document(), indent=2) + "\n"
