"""Container health check: imports, configuration, database, writable directories."""

from __future__ import annotations

import sys


def check_imports() -> bool:
    try:
        import jobspy  # noqa: F401
        import pandas  # noqa: F401
        import yaml  # noqa: F401

        return True
    except ImportError as exc:
        print(f"Import error: {exc}", file=sys.stderr)
        return False


def check_config() -> bool:
    try:
        from openings.config import load_config

        load_config()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"Config error: {exc}", file=sys.stderr)
        return False


def check_database() -> bool:
    try:
        from openings.config import get_config
        from openings.database import get_database

        stats = get_database(get_config()).get_statistics()
        return isinstance(stats, dict)
    except Exception as exc:  # noqa: BLE001
        print(f"Database error: {exc}", file=sys.stderr)
        return False


def check_directories() -> bool:
    try:
        from openings.config import get_config

        config = get_config()
        for directory in (
            config.database_path.parent,
            config.chroma_path,
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


def main() -> int:
    checks = (
        ("imports", check_imports),
        ("config", check_config),
        ("database", check_database),
        ("directories", check_directories),
    )
    healthy = True
    for name, check in checks:
        ok = check()
        print(f"{'OK  ' if ok else 'FAIL'} {name}")
        healthy = healthy and ok
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
