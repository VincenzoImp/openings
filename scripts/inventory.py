"""Generate backend/openings/operation-inventory.json from the operation declarations.

The declarations in backend/openings/interfaces/ give each operation's identity,
REST routes, MCP tool and access; interfaces/inventory-notes.json gives the order,
the dashboard locations and the remarks.

Usage, from the repository root:

    uv run python scripts/inventory.py           # regenerate the inventory
    uv run python scripts/inventory.py --check   # fail when it is out of date
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "backend/openings/operation-inventory.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when the file is stale")
    arguments = parser.parse_args()
    sys.path.insert(0, str(ROOT / "backend"))
    from openings.interfaces import inventory_text

    text = inventory_text()
    if arguments.check:
        if INVENTORY.read_text() != text:
            raise SystemExit(
                "operation-inventory.json is out of date: run `uv run python scripts/inventory.py`."
            )
        return
    INVENTORY.write_text(text)


if __name__ == "__main__":
    main()
