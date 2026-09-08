"""Container health check: imports, configuration, database, writable directories."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openings.runtime import Runtime


def check_imports() -> bool:
    try:
        import jobspy  # noqa: F401
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import pandas  # noqa: F401
        import tokenizers  # noqa: F401
        import yaml  # noqa: F401

        return True
    except ImportError as exc:
        print(f"Import error: {exc}", file=sys.stderr)
        return False


def check_config(runtime: Runtime) -> bool:
    try:
        runtime.config(reload=True)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"Config error: {exc}", file=sys.stderr)
        return False


def check_database(runtime: Runtime) -> bool:
    try:
        return isinstance(runtime.db.get_statistics(), dict)
    except Exception as exc:  # noqa: BLE001
        print(f"Database error: {exc}", file=sys.stderr)
        return False


def check_directories(runtime: Runtime) -> bool:
    try:
        config = runtime.config()
        for directory in (
            config.database_path.parent,
            config.models_dir,
            config.logs_dir,
            config.attachments_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".healthcheck"
            probe.touch()
            probe.unlink()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"Directory error: {exc}", file=sys.stderr)
        return False


def main(runtime: Runtime | None = None) -> int:
    if runtime is None:
        from openings.runtime import get_runtime

        runtime = get_runtime()
    checks = (
        ("imports", check_imports),
        ("config", lambda: check_config(runtime)),
        ("database", lambda: check_database(runtime)),
        ("directories", lambda: check_directories(runtime)),
    )
    healthy = True
    for name, check in checks:
        ok = check()
        print(f"{'OK  ' if ok else 'FAIL'} {name}")
        healthy = healthy and ok
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
