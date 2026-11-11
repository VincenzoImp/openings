"""Schema 9: a workspace without the policy, typed claim fields and frozen policy versions."""

import sqlite3
from contextlib import closing

SCHEMA_TEN_TABLES = ("policy_items", "policy_sections")
SCHEMA_TEN_INDEXES = ("policy_items_section",)
SCHEMA_TEN_COLUMNS = {
    "claims": ("default_in_cv", "role", "group"),
    "context_inputs": ("policy",),
}


def make_schema_nine(path):
    """Remove what schema 10 added from a current workspace file, keeping every other value."""
    with closing(sqlite3.connect(path)) as conn:
        for index in SCHEMA_TEN_INDEXES:
            conn.execute(f"DROP INDEX {index}")
        for table in SCHEMA_TEN_TABLES:
            conn.execute(f"DROP TABLE {table}")
        for table, names in SCHEMA_TEN_COLUMNS.items():
            for name in names:
                conn.execute(f'ALTER TABLE {table} DROP COLUMN "{name}"')
        conn.execute("PRAGMA user_version=9")
        conn.commit()
        # Keep the whole database in the one file, as a downloaded backup is.
        conn.execute("PRAGMA journal_mode=DELETE")
