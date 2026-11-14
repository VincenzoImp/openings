"""Write the real workspace fixture of a released schema from that release's own seed.

    uv run python scripts/release_fixture.py --tag v0.24.2

A temporary worktree at the tag runs the tag's synthetic seed: the browser-test
workspace of ``backend/tests/dashboard_server.py`` and then the external-agent
round trip of ``backend/tests/agent_roundtrip.py`` on the same file. The file is
written as an SQL dump, ``backend/tests/fixtures/workspace-<schema>.sql.gz``, with
the schema read from the database itself, and the worktree is removed. Everything
in it is fictional. Tags from v0.24.0 (schema 15) on are supported.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Runs inside the tag's worktree and environment: seed, exercise, dump.
DRIVER = r"""
import contextlib, gzip, sqlite3, sys
from pathlib import Path

work, out = Path(sys.argv[1]), Path(sys.argv[2])
path = work / "workspace.sqlite"
import dashboard_server, agent_roundtrip
sys.argv = ["dashboard_server", "--seed", str(path)]
dashboard_server.main()
# The round trip opens the seeded file instead of a new one; its owner exists.
create_app = agent_roundtrip.create_app
def seeded(_path, **kwargs):
    app = create_app(path, **kwargs)
    app.state.auth.setup = lambda password: None
    return app
agent_roundtrip.create_app = seeded
sys.argv = ["agent_roundtrip"]
try:
    agent_roundtrip.main()
except SystemExit:
    pass  # its checks assume an empty workspace; every write has happened
with contextlib.closing(sqlite3.connect(path)) as conn:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.execute("PRAGMA journal_mode=DELETE")
    # A dump re-creates a virtual table through writable_schema, which a plain
    # executescript cannot load: create the search index first and rebuild it last.
    virtual = conn.execute(
        "SELECT name,sql FROM sqlite_master WHERE sql LIKE 'CREATE VIRTUAL TABLE%'"
    ).fetchall()
    skip = [f'INSERT INTO "{name}' for name, _ in virtual]  # and its shadow tables
    skip += [f"CREATE TABLE '{name}_" for name, _ in virtual]
    skip += ["PRAGMA writable_schema", "INSERT INTO sqlite_master"]
    statements = [s for s in conn.iterdump() if not s.startswith(tuple(skip))]
    assert statements[0] == "BEGIN TRANSACTION;" and statements[-1] == "COMMIT;"
    statements[1:1] = [sql + ";" for _, sql in virtual]
    statements[-1:-1] = [f"INSERT INTO {name}({name}) VALUES('rebuild');" for name, _ in virtual]
    text = "\n".join(statements) + f"\nPRAGMA user_version={version};\n"
target = out / f"workspace-{version}.sql.gz"
target.write_bytes(gzip.compress(text.encode(), mtime=0))
print(f"Schema {version} fixture: {target} ({target.stat().st_size} bytes)")
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="the release tag, for example v0.24.2")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "backend/tests/fixtures", help="the folder to write to"
    )
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="openings-fixture-") as temporary:
        source, work = Path(temporary) / "source", Path(temporary) / "work"
        work.mkdir()
        driver = Path(temporary) / "driver.py"
        driver.write_text(DRIVER)
        subprocess.run(
            ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(source), args.tag],
            check=True,
        )
        try:
            env = {**os.environ, "PYTHONPATH": str(source / "backend/tests")}
            env.pop("VIRTUAL_ENV", None)
            subprocess.run(
                ["uv", "run", "--locked", "python", str(driver), str(work), str(out)],
                cwd=source,
                env=env,
                check=True,
            )
        finally:
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(source)],
                check=False,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
