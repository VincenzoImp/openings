"""Upgrades start only from the previous schema, against a real fixture, with frozen code."""

import ast
import sys
from pathlib import Path

from openings import migrations
from openings.db import SCHEMA_VERSION

PACKAGE = Path(migrations.__file__).parent
FIXTURES = Path(__file__).with_name("fixtures")


def test_exactly_one_migration_from_the_previous_schema_with_its_real_fixture():
    assert set(migrations.MIGRATIONS) == {SCHEMA_VERSION - 1}
    assert set(migrations.CONVERSIONS) == {SCHEMA_VERSION - 1}
    assert (FIXTURES / f"workspace-{SCHEMA_VERSION - 1}.sql.gz").is_file()


def test_migrations_import_only_the_standard_library():
    for path in PACKAGE.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                # Relative imports stay inside the package; nothing from openings.
                assert node.level <= 1, (path.name, node.module)
                names = [node.module] if node.level == 0 else []
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                continue
            for name in names:
                assert name.split(".")[0] in sys.stdlib_module_names, (path.name, name)
