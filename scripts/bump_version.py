"""Set or check the release version in every file that carries it.

Usage:
    python3 scripts/bump_version.py 0.16.0   # write the new version everywhere
    python3 scripts/bump_version.py --check  # fail when the files disagree

`pyproject.toml` is the reference for `--check`. The script uses only the
standard library and edits the lock files' own project entries in place.
"""

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = r"(?P<version>\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z.-]+)?)"

# Each pattern must match exactly once; the named group holds the version.
LOCATIONS = [
    ("pyproject.toml", rf'(?m)^version = "{VERSION}"$'),
    ("backend/openings/__init__.py", rf'(?m)^__version__ = "{VERSION}"$'),
    ("Dockerfile", rf"(?m)^ARG VERSION={VERSION}$"),
    ("docker-compose.yml", rf"vincenzoimp/openings:{VERSION}\}}"),
    (".env.example", rf"(?m)^# OPENINGS_IMAGE=docker\.io/vincenzoimp/openings:{VERSION}$"),
    ("frontend/package.json", rf'\A\{{\n  "name": "openings-dashboard",\n  "version": "{VERSION}"'),
    (
        "frontend/package-lock.json",
        rf'\A\{{\n  "name": "openings-dashboard",\n  "version": "{VERSION}"',
    ),
    (
        "frontend/package-lock.json",
        rf'\n    "": \{{\n      "name": "openings-dashboard",\n      "version": "{VERSION}"',
    ),
    ("uv.lock", rf'\n\[\[package\]\]\nname = "openings"\nversion = "{VERSION}"\n'),
]

FOLLOW_UP = """\
Next steps:
  uv lock --check                                   # uv.lock is consistent
  npm --prefix frontend install --package-lock-only --ignore-scripts
  git diff --stat
  Add a CHANGELOG.md heading for the release (see CONTRIBUTING.md)."""


def find(path, pattern):
    text = (ROOT / path).read_text(encoding="utf-8")
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise SystemExit(f"{path}: expected one version match, found {len(matches)}")
    return text, matches[0]


def current_versions():
    return [(path, find(path, pattern)[1]["version"]) for path, pattern in LOCATIONS]


def check():
    found = current_versions()
    expected = found[0][1]
    wrong = [(path, version) for path, version in found if version != expected]
    for path, version in wrong:
        print(f"{path}: {version} (pyproject.toml has {expected})", file=sys.stderr)
    if wrong:
        print("Run: python3 scripts/bump_version.py " + expected, file=sys.stderr)
        return 1
    print(f"Version {expected} is consistent in {len(found)} locations.")
    return 0


def bump(version):
    if not re.fullmatch(VERSION, version):
        raise SystemExit(f"Not a version: {version!r} (expected X.Y.Z)")
    for path, pattern in LOCATIONS:
        text, match = find(path, pattern)
        start, end = match.span("version")
        updated = text[:start] + version + text[end:]
        (ROOT / path).write_text(updated, encoding="utf-8")
    print(f"Set version {version} in {len(LOCATIONS)} locations.")
    print(FOLLOW_UP)
    return check()


def main():
    parser = argparse.ArgumentParser(description="Set or check the Openings release version.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("version", nargs="?", help="new version, for example 0.16.0")
    group.add_argument("--check", action="store_true", help="fail when versions disagree")
    args = parser.parse_args()
    return check() if args.check else bump(args.version)


if __name__ == "__main__":
    sys.exit(main())
