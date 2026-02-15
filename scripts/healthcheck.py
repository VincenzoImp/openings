#!/usr/bin/env python3
"""
Health check script for Docker container.

Verifies that:
1. Required Python modules can be imported
2. Configuration can be loaded
3. Database can be connected
4. Required directories exist and are writable

Exit codes:
- 0: Healthy
- 1: Unhealthy
"""

import sys


def check_imports() -> bool:
    """Verify required modules can be imported."""
    try:
        import pandas  # noqa: F401
        import jobspy  # noqa: F401
        import yaml  # noqa: F401
        import sqlite3  # noqa: F401
        return True
    except ImportError as e:
        print(f"Import error: {e}", file=sys.stderr)
        return False


def check_config() -> bool:
    """Verify configuration can be loaded."""
    try:
        from config import load_config
        config = load_config()
        return config is not None
    except Exception as e:
        print(f"Config error: {e}", file=sys.stderr)
        return False


def check_database() -> bool:
    """Verify database connection works."""
    try:
        from config import get_config
        from database import get_database

        config = get_config()
        db = get_database(config)
        # Simple query to verify connection
        stats = db.get_statistics()
        return isinstance(stats, dict)
    except Exception as e:
        print(f"Database error: {e}", file=sys.stderr)
        return False


def check_directories() -> bool:
    """Verify required directories exist and are writable."""
    try:
        from config import get_config
        config = get_config()

        dirs_to_check = [
            config.results_path,
            config.data_path,
            config.log_path.parent,
        ]

        for dir_path in dirs_to_check:
            if not dir_path.exists():
                print(f"Directory missing: {dir_path}", file=sys.stderr)
                return False

            # Check writability by creating a temp file
            test_file = dir_path / ".healthcheck_test"
            try:
                test_file.touch()
                test_file.unlink()
            except PermissionError:
                print(f"Directory not writable: {dir_path}", file=sys.stderr)
                return False

        return True
    except Exception as e:
        print(f"Directory check error: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Run all health checks."""
    checks = [
        ("imports", check_imports),
        ("config", check_config),
        ("database", check_database),
        ("directories", check_directories),
    ]

    all_passed = True
    for name, check_func in checks:
        try:
            if check_func():
                print(f"✓ {name}: OK")
            else:
                print(f"✗ {name}: FAILED")
                all_passed = False
        except Exception as e:
            print(f"✗ {name}: ERROR - {e}")
            all_passed = False

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
