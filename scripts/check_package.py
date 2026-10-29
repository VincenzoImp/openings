"""Smoke an installed wheel outside the checkout, using the current dev dependencies."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    with zipfile.ZipFile(wheel) as package:
        for name in (
            "openings/schema.sql",
            "openings/operation-inventory.json",
            "openings/_vendor/jobspy/LICENSE",
            "openings/_vendor/jobspy/PROVENANCE.md",
        ):
            assert name in package.namelist(), f"Missing package resource: {name}"
        expected = json.loads(package.read("openings/operation-inventory.json"))
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
    inventory = response.json()
    assert inventory['version'] == version('openings') == openings.__version__ == '0.5.0'
    assert len(inventory['operations']) >= 84
    assert client.get('/health').json()['status'] == 'ok'
    print(json.dumps({'installed_version': version('openings'),
                      'operation_count': len(inventory['operations']),
                      'capabilities_status': response.status_code,
                      'package_origin': str(Path(openings.__file__).resolve().relative_to(Path.cwd().resolve()))}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=directory,
            env={**os.environ, "PYTHONPATH": str(target)},
            text=True,
            capture_output=True,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr)
        result = json.loads(completed.stdout)
        assert result["operation_count"] == len(expected["operations"])
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
