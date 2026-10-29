"""One bounded rubric/question-shape check, not held-out validation."""

import json
import os
import time
import threading
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
import psutil
import torch
from laya import Agent
from scoring_context_probe import PIN, CASES

QUESTIONS = {
    "fit": {
        "type": "score",
        "instructions": "Rate candidate suitability for this job. Read mandatory requirements, including the end of the posting. Explicitly missing mandatory qualifications must lower the rating, even when other skills fit.",
        "criteria": [
            "No match: unrelated profession, missing required license, or explicitly insufficient mandatory language level",
            "Low match: core mandatory professional experience is missing",
            "Partial match: some useful experience but an important requirement is missing or unknown",
            "Strong match: mandatory core background is evidenced with only minor optional gaps",
            "Very strong match: relevant professional experience and all stated mandatory qualifications are clearly evidenced",
        ],
    },
    "mandatory_match": {
        "type": "noul",
        "instructions": "Does this candidate satisfy the job mandatory professional qualifications, technical experience and language level? If a mandatory qualification is explicitly absent or insufficient, answer false.",
    },
    "language_match": {
        "type": "noul",
        "instructions": "Does the candidate meet the mandatory German language level in the posting? C1 satisfies C1; A1 is below C1.",
    },
}


def main():
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    process = psutil.Process()
    samples = []
    stop = threading.Event()

    def sample():
        while not stop.wait(0.05):
            samples.append(process.memory_info().rss / 1024**2)

    t = threading.Thread(target=sample, daemon=True)
    t.start()
    record = {
        "purpose": "development-only question shape comparison",
        "model_revision": PIN,
        "max_len": 1024,
        "questions": QUESTIONS,
        "cases": [],
    }
    try:
        agent = Agent("convaiinnovations/laya", revision=PIN, device="cpu", backend="eager")
        for name, profile, job in CASES:
            started = time.perf_counter()
            r = agent.predict({"candidate": profile, "posting": job}, QUESTIONS, max_len=1024)
            record["cases"].append(
                {"id": name, "result": r, "elapsed_seconds": time.perf_counter() - started}
            )
            print(
                name,
                {k: round(v.get("score", v.get("noul")), 4) for k, v in r["answers"].items()},
                r["usage"],
                flush=True,
            )
        record["sampled_peak_rss_mib"] = max(samples)
        Path(__file__).with_name("question-shape-probe.json").write_text(
            json.dumps(record, indent=2) + "\n"
        )
        print("peak MiB", max(samples), flush=True)
    finally:
        stop.set()
        t.join()


if __name__ == "__main__":
    main()
