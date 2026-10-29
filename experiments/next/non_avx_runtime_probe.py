"""Disposable no-AVX CPU-wheel feasibility check; no model or system changes."""

import json
import os
import platform
import resource
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.request
import venv
from pathlib import Path

WHEEL = "https://download-r2.pytorch.org/whl/cpu/torch-2.15.0%2Bcpu-cp313-cp313-manylinux_2_28_x86_64.whl#sha256=0f6f69701b2d38ddc412364dfb92e2e13e74960d33fa3573b4930ced626e81c7"
CAP_MIB = 650
OPS = """import json,torch
from torch.nn import functional as F
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
print(json.dumps({'stage':'import','torch':torch.__version__,'cpu_capability':torch.backends.cpu.get_cpu_capability(),'intraop_threads':torch.get_num_threads()}),flush=True)
x=torch.linspace(-3,3,1024,dtype=torch.float32)
operations={
'matmul':lambda:torch.mm(torch.ones(128,128),torch.ones(128,128)),
'sin':lambda:torch.sin(x),
'cos':lambda:torch.cos(x),
'gelu':lambda:F.gelu(x),
'layer_norm':lambda:F.layer_norm(torch.randn(8,32),[32]),
'sdpa':lambda:F.scaled_dot_product_attention(torch.ones(1,2,64,32),torch.ones(1,2,64,32),torch.ones(1,2,64,32),dropout_p=0.0)
}
for name,call in operations.items():
 print(json.dumps({'stage':name+':start'}),flush=True)
 output=call()
 assert torch.isfinite(output).all().item()
 print(json.dumps({'stage':name,'shape':list(output.shape),'finite':True,'sum':float(output.sum())}),flush=True)
"""


def proc_rss_mib(pid):
    try:
        with open("/proc/" + str(pid) + "/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1024**2
    except (FileNotFoundError, ProcessLookupError):
        return 0.0


def run_capped(args, env, log_path, wall_seconds):
    def setup():
        os.nice(15)
        resource.setrlimit(resource.RLIMIT_CPU, (90, 95))
        allowed = os.sched_getaffinity(0)
        os.sched_setaffinity(0, {min(allowed)})

    started = time.monotonic()
    peak = 0.0
    reason = None
    with open(log_path, "w") as log:
        child = subprocess.Popen(
            args,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=setup,
        )
        while child.poll() is None:
            peak = max(peak, proc_rss_mib(child.pid))
            if peak >= CAP_MIB:
                reason = "memory cap"
                os.killpg(child.pid, signal.SIGKILL)
                break
            if time.monotonic() - started > wall_seconds:
                reason = "wall timeout"
                os.killpg(child.pid, signal.SIGKILL)
                break
            time.sleep(0.05)
        code = child.wait()
    return {
        "exit_code": code,
        "seconds": round(time.monotonic() - started, 3),
        "sampled_peak_rss_mib": round(peak, 3),
        "stopped_reason": reason,
    }, Path(log_path).read_text()


def main():
    flags = []
    for line in open("/proc/cpuinfo"):
        if line.startswith("flags"):
            flags = line.split(":", 1)[1].split()
            break
    record = {
        "purpose": "target non-AVX CPU runtime import/kernel smoke only, no model inference",
        "host": {
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "isa": {k: k in flags for k in ["sse4_2", "avx", "avx2", "avx512f"]},
        },
        "cpu_wheel": WHEEL,
        "limits": {
            "single_cpu_affinity": True,
            "nice": 15,
            "thread_environment": 1,
            "rss_stop_mib": CAP_MIB,
            "install_wall_seconds": 150,
            "operations_wall_seconds": 30,
        },
        "cpu_capability_override": None,
    }
    tmp = Path(tempfile.mkdtemp(prefix="openings-cpu-probe-"))
    try:
        venv.EnvBuilder(with_pip=False, symlinks=True).create(tmp / "env")
        with (
            urllib.request.urlopen("https://bootstrap.pypa.io/pip/pip.pyz", timeout=20) as source,
            open(tmp / "pip.pyz", "wb") as dest,
        ):
            shutil.copyfileobj(source, dest)
        py = str(tmp / "env/bin/python")
        env = {k: v for k, v in os.environ.items() if not k.startswith("PIP_")}
        env.update(
            {
                "PIP_CONFIG_FILE": os.devnull,
                "PYTHONNOUSERSITE": "1",
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "NUMEXPR_NUM_THREADS": "1",
                "TMPDIR": str(tmp),
            }
        )
        install, log = run_capped(
            [
                py,
                str(tmp / "pip.pyz"),
                "install",
                "--index-url",
                "https://pypi.org/simple",
                "--only-binary=:all:",
                "--no-cache-dir",
                "--disable-pip-version-check",
                "--progress-bar",
                "off",
                "--quiet",
                WHEEL,
            ],
            env,
            tmp / "install.log",
            150,
        )
        record["install"] = install
        if install["exit_code"]:
            record["install_error"] = log[-2200:].replace(str(tmp), "<temporary-probe>")
        else:
            result, log = run_capped([py, "-c", OPS], env, tmp / "operations.log", 30)
            record["operations"] = result
            record["operation_events"] = []
            warnings = []
            for line in log.splitlines():
                try:
                    record["operation_events"].append(json.loads(line))
                except json.JSONDecodeError:
                    warnings.append(line.replace(str(tmp), "<temporary-probe>"))
            record["runtime_diagnostics"] = "\n".join(warnings)[-1800:]
    except Exception as error:
        record["setup_error"] = str(error).replace(str(tmp), "<temporary-probe>")
    finally:
        shutil.rmtree(tmp)
        record["temporary_directory_removed"] = not tmp.exists()
    print(json.dumps(record, indent=2), flush=True)


if __name__ == "__main__":
    main()
