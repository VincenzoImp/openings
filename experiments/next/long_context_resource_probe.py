"""One genuine near-full 2048-token CPU inference, resource-only synthetic stress."""

import json
import os
import platform
import threading
import time
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
import psutil
import torch
from laya import Agent
from laya.common import build_sequence
from scoring_context_probe import PIN, PROFILE_ENGINEER, JOB_ENGINEER, COMMON, QUESTION


def main():
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    process = psutil.Process()
    samples = []
    stop = threading.Event()
    phase = ["loading"]

    def sample():
        while not stop.wait(0.02):
            samples.append((phase[0], process.memory_info().rss / 1024**2))

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    record = {
        "purpose": "one near-full 2048-token resource-only synthetic request; no accuracy conclusion",
        "host": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "device": "cpu",
            "threads": 2,
        },
        "model": "convaiinnovations/laya",
        "revision": PIN,
        "laya": "0.4.17",
        "torch": torch.__version__,
        "max_len": 2048,
        "head_max_len": 192,
        "questions": QUESTION,
    }
    try:
        started = time.perf_counter()
        agent = Agent("convaiinnovations/laya", revision=PIN, device="cpu", backend="eager")
        record["load_seconds"] = time.perf_counter() - started
        record["after_load_rss_mib"] = process.memory_info().rss / 1024**2
        job_head, job_tail = JOB_ENGINEER.rsplit("\nMandatory requirement", 1)
        prefix = (
            "Candidate profile:\n"
            + PROFILE_ENGINEER.format(german="C1")
            + "\n\nJob posting:\n"
            + job_head
            + "\n\nAdditional employer information for resource stress:\n"
        )
        suffix = "\nMandatory requirement" + job_tail
        words = (COMMON + " " + COMMON + " " + COMMON + " " + COMMON).split()
        q = QUESTION["fit"]
        internal = {"t": "score", "ins": q["instructions"], "crit": q["criteria"]}

        def payload(n):
            state = prefix + " ".join(words[:n]) + suffix
            ids, _, stats = build_sequence(
                agent.tok,
                state,
                internal,
                max_len=10000,
                head_max_len=192,
                return_truncation_stats=True,
            )
            return state, len(ids), stats

        lo, hi = 0, len(words)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if payload(mid)[1] <= 1920:
                lo = mid
            else:
                hi = mid - 1
        state, tokens, preflight = payload(lo)
        assert 1800 <= tokens <= 1950, (tokens, lo)
        record["state"] = state
        record["preflight_sequence_tokens"] = tokens
        record["preflight_state_stats"] = preflight
        phase[0] = "request"
        started = time.perf_counter()
        result = agent.predict(state, QUESTION, max_len=2048)
        elapsed = time.perf_counter() - started
        assert result["usage"]["input_tokens"] == tokens
        assert result["usage"]["truncated"] is False
        phase[0] = "finished"
        record["result"] = result
        record["elapsed_seconds"] = elapsed
        record["after_request_rss_mib"] = process.memory_info().rss / 1024**2
        record["summary"] = {
            "actual_sequence_tokens": tokens,
            "truncated": False,
            "state_tokens_dropped": result["usage"]["state_tokens_dropped"],
            "load_peak_rss_mib": max(v for p, v in samples if p == "loading"),
            "request_peak_rss_mib": max(
                [v for p, v in samples if p == "request"] + [record["after_request_rss_mib"]]
            ),
            "total_sampled_peak_rss_mib": max(v for _, v in samples),
            "elapsed_seconds": elapsed,
            "qualification": "Mac arm64, one model process and one request; no whole-stack/x86 guarantee",
        }
        Path(__file__).with_name("long-context-resource-probe.json").write_text(
            json.dumps(record, indent=2) + "\n"
        )
        print(json.dumps(record["summary"], indent=2), flush=True)
    finally:
        stop.set()
        thread.join()


if __name__ == "__main__":
    main()
