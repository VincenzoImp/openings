"""Generate backend/openings/operation-inventory.json from the operation declarations.

The declarations in backend/openings/interfaces/ give each operation's identity,
REST routes, MCP tool and access; interfaces/inventory-notes.json gives the order,
the dashboard locations and the remarks. The same run writes the tables of
earlier tool names and deprecated arguments in docs/user/upgrading-0.22.md.

Usage, from the repository root:

    uv run python scripts/inventory.py            # regenerate the inventory and tables
    uv run python scripts/inventory.py --check    # fail when either is out of date
    uv run python scripts/inventory.py --aliases  # print the tables
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "backend/openings/operation-inventory.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when the file is stale")
    parser.add_argument("--aliases", action="store_true", help="print the upgrade tables")
    arguments = parser.parse_args()
    sys.path.insert(0, str(ROOT / "backend"))
    from openings.interfaces import (
        GUIDE_PATH,
        inventory_text,
        upgrade_tables,
        with_upgrade_tables,
    )

    guide_file = ROOT / GUIDE_PATH

    if arguments.aliases:
        print(upgrade_tables())
        return
    text, guide = inventory_text(), with_upgrade_tables(guide_file.read_text())
    if arguments.check:
        if INVENTORY.read_text() != text or guide_file.read_text() != guide:
            raise SystemExit(
                "operation-inventory.json or the tables of docs/user/upgrading-0.22.md are out "
                "of date: run `uv run python scripts/inventory.py`."
            )
        return
    INVENTORY.write_text(text)
    guide_file.write_text(guide)


if __name__ == "__main__":
    main()
