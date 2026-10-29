"""Run the same synthetic decisions on pinned Laya weights, CPU only."""

import argparse
import json
import platform
import statistics
import threading
import time
from pathlib import Path

import psutil
import torch
from laya import Agent

from decision_probe import CASES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    process = psutil.Process()
    memory = []
    done = threading.Event()

    def sample():
        while not done.wait(0.05):
            memory.append(process.memory_info().rss / 1024**2)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        started = time.perf_counter()
        revision = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
        agent = Agent("convaiinnovations/laya", revision=revision, device="cpu", backend="eager")
        record = {
            "purpose": "synthetic diagnostic, not domain validation",
            "host": {
                "os": platform.system(),
                "architecture": platform.machine(),
                "device": "cpu",
                "threads": 2,
            },
            "model": "convaiinnovations/laya",
            "revision": revision,
            "laya": "0.4.17",
            "torch": torch.__version__,
            "load_seconds_including_first_download": time.perf_counter() - started,
            "cases": [],
        }
        for key, state, question, expected in CASES:
            started = time.perf_counter()
            result = agent.predict(state, {"decision": {"type": "noul", "instructions": question}})
            elapsed = time.perf_counter() - started
            probability = result["answers"]["decision"]["noul"]
            record["cases"].append(
                {
                    "id": key,
                    "state": state,
                    "question": question,
                    "expected": expected,
                    "probability_yes": probability,
                    "correct_at_0_5": (probability >= 0.5) == expected,
                    "elapsed_seconds": elapsed,
                    "rss_mib": process.memory_info().rss / 1024**2,
                    "usage": result.get("usage"),
                }
            )
            print(key, round(probability, 4), round(elapsed, 3), flush=True)
        times = [c["elapsed_seconds"] for c in record["cases"]]
        record["summary"] = {
            "correct": sum(c["correct_at_0_5"] for c in record["cases"]),
            "total": len(CASES),
            "median_seconds": statistics.median(times),
            "max_seconds": max(times),
            "sampled_peak_rss_mib": max(memory),
            "qualification": "Same 14 simple diagnostics, no production validation or target-device benchmark",
        }
        args.out.write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record["summary"], indent=2))
    finally:
        done.set()
        thread.join()


if __name__ == "__main__":
    main()
