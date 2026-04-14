"""
Bootstrap Docker-friendly configuration files.

This helper copies the bundled settings template into the mounted config
directory so Docker users can start from a real file instead of editing the
image contents.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SETTINGS_PATH = Path(
    os.environ.get("JOB_SEARCH_CONFIG", "/app/config/settings.yaml")
)
DEFAULT_TEMPLATE_PATH = Path(
    os.environ.get(
        "JOB_SEARCH_TEMPLATE_PATH",
        "/opt/job-search-tool/defaults/settings.example.yaml",
    )
)


@dataclass(frozen=True)
class BootstrapResult:
    """Describe what the bootstrap process did."""

    example_path: Path
    settings_path: Path
    example_created: bool
    settings_created: bool


def bootstrap_config(
    settings_path: Path,
    template_path: Path,
    *,
    write_settings: bool = False,
) -> BootstrapResult:
    """Copy template files into the runtime config directory."""
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    config_dir = settings_path.parent
    config_dir.mkdir(parents=True, exist_ok=True)

    example_path = config_dir / "settings.example.yaml"
    example_created = False
    settings_created = False

    if not example_path.exists():
        shutil.copyfile(template_path, example_path)
        example_created = True

    if write_settings and not settings_path.exists():
        shutil.copyfile(template_path, settings_path)
        settings_created = True

    return BootstrapResult(
        example_path=example_path,
        settings_path=settings_path,
        example_created=example_created,
        settings_created=settings_created,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap config/settings.yaml from the bundled template."
    )
    parser.add_argument(
        "--settings-path",
        type=Path,
        default=DEFAULT_SETTINGS_PATH,
        help="Target settings.yaml path (default: %(default)s).",
    )
    parser.add_argument(
        "--template-path",
        type=Path,
        default=DEFAULT_TEMPLATE_PATH,
        help="Bundled template path (default: %(default)s).",
    )
    parser.add_argument(
        "--write-settings",
        action="store_true",
        help="Create settings.yaml if it does not exist yet.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-friendly status output.",
    )
    return parser.parse_args(argv)


def _print_summary(result: BootstrapResult, *, write_settings: bool) -> None:
    example_status = "created" if result.example_created else "kept existing"
    settings_status = "created" if result.settings_created else "kept existing"

    print(
        "Config template ready:",
        f"{result.example_path} ({example_status})",
        sep="\n- ",
    )
    if write_settings:
        print(
            "Runtime settings ready:",
            f"{result.settings_path} ({settings_status})",
            sep="\n- ",
        )
    else:
        print(
            "Runtime settings:",
            f"{result.settings_path} "
            "(not created automatically; built-in defaults stay active until you add it)",
            sep="\n- ",
        )
    print(
        "Next step:",
        f"edit {result.settings_path} and rerun the container stack.",
        sep="\n- ",
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = _parse_args(argv)

    try:
        result = bootstrap_config(
            args.settings_path,
            args.template_path,
            write_settings=args.write_settings,
        )
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not args.quiet:
        _print_summary(result, write_settings=args.write_settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
