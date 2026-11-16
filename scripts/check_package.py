"""Check that the project description is the same everywhere and that the Docker
Hub overview and short description fit Docker Hub's limits, then smoke an
installed wheel outside the checkout, using the current dev dependencies.

    python3 scripts/check_package.py              # the texts only
    python3 scripts/check_package.py dist/*.whl   # and the wheel
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Each copy of the description: the file and a pattern whose group holds it.
DESCRIPTIONS = [
    ("Dockerfile", r'org\.opencontainers\.image\.description="([^"]*)"'),
    (
        ".github/workflows/images.yml",
        r"'index:org\.opencontainers\.image\.description=([^']*)'",
    ),
    ("frontend/index.html", r'<meta\s+name="description"\s+content="([^"]*)"'),
]


def check_descriptions(root=ROOT):
    """Fail unless every copy equals the description in pyproject.toml."""
    with open(root / "pyproject.toml", "rb") as file:
        expected = tomllib.load(file)["project"]["description"]
    for path, pattern in DESCRIPTIONS:
        found = re.findall(pattern, (root / path).read_text(encoding="utf-8"))
        if len(found) != 1:
            raise SystemExit(f"{path}: expected one description, found {len(found)}")
        if html.unescape(found[0]) != expected:
            raise SystemExit(
                f"{path}: the description differs from pyproject.toml's:\n"
                f"  {found[0]}\n  {expected}"
            )
    return expected


# Docker Hub limits: the overview (docs/dockerhub.md) and the short description
# that images.yml syncs to the repository page.
HUB_OVERVIEW = "docs/dockerhub.md"
HUB_OVERVIEW_BYTES = 25_000
HUB_WORKFLOW = ".github/workflows/images.yml"
HUB_SHORT_PATTERN = r"(?m)^\s*short-description: '([^']*)'$"
HUB_SHORT_CHARACTERS = 100


def check_docker_hub(root=ROOT):
    """Fail unless the Docker Hub overview and short description fit their limits."""
    size = len((root / HUB_OVERVIEW).read_bytes())
    if size > HUB_OVERVIEW_BYTES:
        raise SystemExit(f"{HUB_OVERVIEW}: {size} bytes, over {HUB_OVERVIEW_BYTES}")
    found = re.findall(HUB_SHORT_PATTERN, (root / HUB_WORKFLOW).read_text(encoding="utf-8"))
    if len(found) != 1:
        raise SystemExit(f"{HUB_WORKFLOW}: expected one short description, found {len(found)}")
    if not found[0] or len(found[0]) > HUB_SHORT_CHARACTERS:
        raise SystemExit(
            f"{HUB_WORKFLOW}: the short description has {len(found[0])} characters, "
            f"not 1 to {HUB_SHORT_CHARACTERS}"
        )
    return size, found[0]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("wheel", type=Path, nargs="?")
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args()
    check_descriptions()
    check_docker_hub()
    if args.wheel is None:
        print("The description matches in every file, and the Docker Hub texts fit.")
        return
    wheel = args.wheel.resolve()
    repository = ROOT
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "backend/openings"], cwd=repository, text=True
    ).split("\0")
    with zipfile.ZipFile(wheel) as package:
        for name in filter(None, tracked):
            member = Path(name).relative_to("backend").as_posix()
            assert package.read(member) == (repository / name).read_bytes(), (
                f"Stale package: {name}"
            )
        for name in (
            "openings/schema.sql",
            "openings/_vendor/jobspy/LICENSE",
            "openings/_vendor/jobspy/PROVENANCE.md",
            # The demo workspace's CV and letter (openings.demo).
            "openings/demo/demo-cv.pdf",
            "openings/demo/demo-cv.tex",
            "openings/demo/demo-letter.pdf",
            "openings/demo/demo-letter.tex",
            "openings/demo/demo-letter-meridian.pdf",
            "openings/demo/demo-letter-fernhill.pdf",
        ):
            assert name in package.namelist(), f"Missing package resource: {name}"
    with tempfile.TemporaryDirectory(prefix="openings-installed-") as directory:
        target = Path(directory) / "site-packages"
        subprocess.run(
            [
                args.uv,
                "pip",
                "install",
                "--python",
                sys.executable,
                "--no-deps",
                "--target",
                str(target),
                str(wheel),
            ],
            check=True,
        )
        # Changing cwd and replacing PYTHONPATH prevents a source checkout from
        # masking missing wheel resources or an incorrectly packaged import.
        probe = """
import json
from importlib.metadata import version
from pathlib import Path
from fastapi.testclient import TestClient
import openings
from openings.app import create_app
assert Path(openings.__file__).resolve().is_relative_to(Path.cwd().resolve())
app = create_app(Path.cwd() / 'installed.sqlite', start_worker=False)
app.state.auth.setup('synthetic-package-password')
token = app.state.auth.create_token('synthetic-package-probe')['token']
with TestClient(app) as client:
    response = client.get('/api/v1/capabilities', headers={'Authorization': 'Bearer ' + token})
    response.raise_for_status()
    capabilities = response.json()
    assert capabilities['version'] == version('openings') == openings.__version__
    assert capabilities['operations']
    assert client.get('/health').json()['status'] == 'ok'
# The demo workspace seeds from the installed package data.
from openings.demo import seed_demo
demo = create_app(Path.cwd() / 'demo.sqlite', start_worker=False)
demo.state.auth.setup('synthetic-package-password')
seed_demo(demo)
files = demo.state.workspace.db.one("SELECT count(*) AS n FROM files")['n']
assert files
print(json.dumps({'installed_version': version('openings'),
                  'operation_count': len(capabilities['operations']),
                  'capabilities_status': response.status_code,
                  'demo_files': files,
                  'package_origin': str(Path(openings.__file__).resolve().relative_to(Path.cwd().resolve()))}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            check=False,
            cwd=directory,
            env={
                **os.environ,
                "PYTHONPATH": str(target),
                "OPENINGS_EXAMPLES": str(repository / "examples"),
            },
            text=True,
            capture_output=True,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr)
        result = json.loads(completed.stdout)
        result["source_files_verified"] = len(list(filter(None, tracked)))
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
