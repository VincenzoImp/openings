"""Upgrades of a workspace file written by the previous release.

Exactly one migration exists at a time: from the previous schema to the current
one (``SCHEMA_VERSION - 1``). An older workspace upgrades through the release that
introduced the schema after its own (the error message names it). Each migration
is a frozen module that imports only the standard library, so later changes to
the product never change what an old upgrade does; at the next schema change it
is deleted and replaced (CONTRIBUTING.md, the "Schema" rule).

``MIGRATIONS`` maps the schema a migration starts from to its in-place upgrade,
``CONVERSIONS`` to the copy of a file into a new one (restoring an uploaded
backup) and ``recover`` resolves the files an interrupted upgrade left.
"""

from . import m15
from .m15 import UpgradeError

MIGRATIONS = {m15.FROM_VERSION: m15.upgrade}
CONVERSIONS = {m15.FROM_VERSION: m15.convert}
recover = m15.recover

__all__ = ["CONVERSIONS", "MIGRATIONS", "UpgradeError", "recover"]
