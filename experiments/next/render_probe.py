"""Compile a synthetic user template locally. This is not a hostile-TeX sandbox."""

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment


def digest(value):
    return hashlib.sha256(value).hexdigest()


def tex_escape(value):
    escapes = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(escapes.get(c, c) for c in str(value))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tectonic", default="tectonic")
    parser.add_argument("--only-cached", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    env = SandboxedEnvironment(
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        undefined=StrictUndefined,
        autoescape=False,
    )
    env.globals.clear()
    env.filters["tex"] = tex_escape
    template = Path(__file__).with_name("example.tex.j2").read_text()
    text = env.from_string(template).render(
        name="Alex Example",
        headline="Backend engineer",
        bullets=[
            {"text": "Built Python APIs and reduced latency by 20%."},
            {"text": "Maintained R&D integrations; handled names_like_this safely."},
        ],
    )
    assert r"20\%" in text and r"R\&D" in text and r"names\_like\_this" in text
    with tempfile.TemporaryDirectory(prefix="openings-tex-") as folder:
        work = Path(folder)
        (work / "resume.tex").write_text(text)
        start = time.perf_counter()
        command = [args.tectonic, "--untrusted", "--keep-logs"]
        if args.only_cached:
            command.append("--only-cached")
        result = subprocess.run(
            [*command, "resume.tex"],
            cwd=work,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
        )
        elapsed = time.perf_counter() - start
        if result.returncode:
            raise RuntimeError(result.stdout[-3000:])
        pdf = (work / "resume.pdf").read_bytes()
        assert pdf.startswith(b"%PDF-")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.with_suffix(".pdf").write_bytes(pdf)
        args.out.write_text(
            json.dumps(
                {
                    "template": "synthetic example.tex.j2",
                    "template_sha256": digest(template.encode()),
                    "tex_sha256": digest(text.encode()),
                    "pdf_sha256": digest(pdf),
                    "pdf_bytes": len(pdf),
                    "elapsed_seconds_including_package_fetch": elapsed,
                    "compiler": subprocess.check_output(
                        [args.tectonic, "--version"], text=True
                    ).strip(),
                    "input_escaping_checked": True,
                    "only_cached_packages": args.only_cached,
                    "real_model_used": False,
                    "limit": "Only trusted synthetic template. Production needs isolated rendering, bounded resources and preloaded packages.",
                },
                indent=2,
            )
            + "\n"
        )
        print("PDF compiled", len(pdf), "bytes", round(elapsed, 3), "seconds")


if __name__ == "__main__":
    main()
