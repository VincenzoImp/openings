"""Compile the example CV and letter templates with Tectonic, the engine the skills name first.

    python3 scripts/compile_examples.py [--tectonic /path/to/tectonic]

Each template must compile to a PDF. Tectonic fetches the packages it needs
on the first run, so the check needs the network once; it is not part of CI.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
TEMPLATES = ("cv.tex", "letter.tex")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tectonic", default=shutil.which("tectonic") or "")
    args = parser.parse_args()
    if not args.tectonic:
        sys.exit("Tectonic was not found: install it (https://tectonic-typesetting.github.io).")
    failed = []
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        for name in TEMPLATES:
            source = folder / name
            source.write_text((EXAMPLES / name).read_text())
            result = subprocess.run(
                [args.tectonic, "--untrusted", "--outdir", str(folder), str(source)],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            pdf = source.with_suffix(".pdf")
            ok = result.returncode == 0 and pdf.exists() and pdf.read_bytes().startswith(b"%PDF-")
            print(f"{name}: {'ok' if ok else 'failed'}")
            if not ok:
                failed.append(name)
                print(result.stdout[-2000:], result.stderr[-2000:], sep="\n")
    if failed:
        sys.exit(f"Did not compile: {', '.join(failed)}")


if __name__ == "__main__":
    main()
