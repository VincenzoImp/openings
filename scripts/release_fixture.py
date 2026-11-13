"""Write the real workspace fixture of a released schema from that release's own seed.

    uv run python scripts/release_fixture.py --tag v0.23.1

A temporary worktree at the tag runs the tag's synthetic seed: the browser-test
workspace of ``backend/tests/dashboard_server.py`` and then the external-agent
round trip of ``backend/tests/agent_roundtrip.py`` on the same file (it needs
the ``tectonic`` executable). A few values that only older upgrades produced and
no service writes any more (``documents.legacy_content``, upgrade-copied notes,
estimated response days, keys on records) are then set on synthetic rows. The
file is written as an SQL dump (``backend/tests/fixtures/workspace-<schema>.sql.gz``)
and the worktree is removed. Everything in it is fictional.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Runs inside the tag's worktree and environment: seed, fill the gaps, dump.
DRIVER = r"""
import contextlib, gzip, sqlite3, sys, tempfile
from pathlib import Path
import uvicorn

work, out = Path(sys.argv[1]), Path(sys.argv[2])
fixed = lambda *args, **kwargs: contextlib.nullcontext(str(work))
import dashboard_server, agent_roundtrip
dashboard_server.tempfile = type("T", (), {"TemporaryDirectory": staticmethod(fixed)})
agent_roundtrip.tempfile = dashboard_server.tempfile
uvicorn.run = lambda *args, **kwargs: None
dashboard_server.main()
# A context that froze files: one file on a Career entry and on the default template.
import hashlib
from openings.app import create_app
from openings.documents import ContextCreate
app = create_app(work / "workspace.sqlite", start_worker=False)
with app.state.workspace.db.transaction() as conn:
    for column, table, where in (("knowledge_id", "knowledge", "1=1"),
                                 ("template_id", "templates", "is_default=1")):
        body = f"Synthetic {table} attachment.".encode()
        digest = hashlib.sha256(body).hexdigest()
        conn.execute("INSERT OR IGNORE INTO blobs(sha256,content,size) VALUES(?,?,?)",
                     (digest, body, len(body)))
        conn.execute(f"INSERT INTO files(id,sha256,name,media_type,size,{column},created_at) "
                     f"SELECT 'synthetic-{table}-file',?,'attachment.txt','text/plain',?,id,"
                     f"'2026-11-01T08:00:00+00:00' FROM {table} WHERE {where} "
                     "ORDER BY rowid LIMIT 1", (digest, len(body)))
    application = conn.execute("SELECT id FROM applications WHERE id NOT IN "
                               "(SELECT application_id FROM contexts) ORDER BY rowid").fetchone()[0]
app.state.documents.prepare_context(ContextCreate(application_id=application))
sys.argv = ["agent_roundtrip"]
try:
    agent_roundtrip.main()
except SystemExit:
    pass  # its checks assume an empty workspace; every write has happened
path = work / "workspace.sqlite"
with contextlib.closing(sqlite3.connect(path)) as conn:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for table in ("applications", "runs", "questions", "requests", "policy_items",
                  "responses", "contexts"):
        conn.execute(f"UPDATE {table} SET idempotency_key='synthetic-{table}-key' "
                     f"WHERE rowid=(SELECT min(rowid) FROM {table})")
    conn.execute("UPDATE documents SET legacy_content=json_object('summary',"
                 "'Synthetic content saved before 0.22.') WHERE rowid=(SELECT min(rowid) "
                 "FROM documents WHERE kind IN ('resume','cover_letter'))")
    conn.execute("UPDATE notes SET origin='upgrade' WHERE rowid=(SELECT min(rowid) FROM notes)")
    conn.execute("UPDATE responses SET estimated=1,origin='upgrade' "
                 "WHERE rowid=(SELECT min(rowid) FROM responses)")
    conn.commit()
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
out.write_bytes(gzip.compress(text.encode(), mtime=0))
print(f"Schema {version} fixture: {out} ({out.stat().st_size} bytes)")
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="the release tag, for example v0.23.0")
    parser.add_argument("--schema", type=int, default=14, help="the schema of that release")
    args = parser.parse_args()
    out = ROOT / "backend/tests/fixtures" / f"workspace-{args.schema}.sql.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
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
