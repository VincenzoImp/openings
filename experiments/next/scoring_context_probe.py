"""Bounded realistic-context feasibility probe; synthetic content only."""

import json
import os
import platform
import statistics
import threading
import time
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
import psutil
import torch
from laya import Agent

PIN = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
PROFILE_ENGINEER = """Candidate profile. Alex Example is a backend software engineer with six years of professional experience. Since 2022 Alex has worked at Cedar Systems building Python services with FastAPI and Django, PostgreSQL data models and asynchronous workers. Previously Alex developed integrations and REST APIs at Northstar Tools. Project evidence includes improving query latency by 35 percent, designing idempotent event processing, supporting on-call incidents and reviewing security-sensitive changes. Alex writes unit and integration tests, uses Git, Docker and Linux, and documents architectural decisions. Alex has mentored two colleagues and collaborated with product managers. Education: BSc Computer Science. Desired next role: backend engineering with real product ownership, remote or hybrid work, and compensation above CHF 100000. English: C1. Work authorization: authorized to work in Switzerland. German: {german}. No healthcare qualifications or clinical license."""
PROFILE_CHEF = """Candidate profile. Jordan Example is a restaurant chef with ten years of experience in professional kitchens. Jordan manages menus, food safety, procurement, service quality, rosters and a team of cooks. Projects include reducing food waste by 25 percent and introducing a seasonal menu. Jordan has never programmed, built software services or used Python, databases or cloud infrastructure. Education: professional culinary diploma. English: C1. German: C1. Authorized to work in Switzerland. Desired role: senior culinary operations and kitchen leadership. No computer science or healthcare qualifications."""
PROFILE_NURSE = """Candidate profile. Morgan Example is a registered nurse with seven years of adult inpatient clinical experience. Morgan holds a current Swiss recognized nursing license and a Bachelor of Nursing. Work includes administering medication, monitoring vital signs, patient assessment, coordinating discharge and documenting care plans in electronic clinical records. Morgan has trained junior nurses and supported multidisciplinary teams on medical and surgical wards. Morgan holds current basic life support certification, speaks German at C1 and English at B2, and is authorized to work in Switzerland. Desired next role: registered nurse on an adult inpatient ward, with rotating shifts acceptable. No professional software engineering or programming experience."""

COMMON = """About Cedar Health Systems. We build services used by care providers and hospital operations teams. Our purpose is to make information reliable and accessible while respecting privacy. We are a stable organization with long term customer relationships and teams working across several countries. We value careful communication, sound professional judgment, useful documentation and willingness to learn from incidents. People here work with colleagues from different disciplines and make decisions close to the problem. We expect respectful debate, clear ownership and pragmatic improvements rather than unnecessary process.\n
How we work. The team starts with the needs of the people who use our services. We discuss expected outcomes before selecting an implementation and review work with the appropriate colleagues. We prefer manageable changes and clear handovers. Written records help the next person understand the context. We regularly review what is working and make small adjustments. You will have time to understand existing practices, ask questions and propose improvements. Managers give regular feedback and support professional development. We make room for different working styles while maintaining reliable cooperation.\n
Your development. During the first month you will meet the people you will work with, understand our routines and shadow experienced colleagues. Over the following months you will take responsibility for well-defined pieces of work. The team will help you learn our tools, terminology and standards. We offer training time and a yearly development conversation. You will be expected to share what you learn, identify risks early and ask for help when needed. We welcome experience from organizations of different sizes and people who can explain the reasoning behind their decisions.\n
Working environment and benefits. The position is full time and based in Switzerland, with hybrid arrangements where the work allows it. We offer a competitive salary, pension contributions, paid leave and support for continuing education. Our recruitment process includes an initial conversation, a role-specific discussion and an opportunity to meet future colleagues. Candidates will have time to ask questions about expectations, scheduling and the team. We assess applications fairly and can arrange reasonable adjustments. Please provide a clear account of relevant experience and practical examples of your work.\n
Application and hiring process. Applications are reviewed by the hiring manager and a colleague with relevant professional experience. We may ask for clarification about responsibilities or achievements rather than expecting a particular CV format. The process is intended to establish mutual understanding of the role and the environment. We do not require an unpaid project unrelated to the position. References may be requested at a later stage with the candidate's agreement. You will receive an update if the timeline changes. Before accepting an offer, candidates can discuss remaining questions about responsibilities, benefits and working arrangements."""
JOB_ENGINEER = (
    """Job: Senior Backend Engineer. Build production Python APIs and backend services. Required: at least five years of professional software engineering, Python, PostgreSQL, HTTP APIs, automated tests, Linux and collaborative code review. Responsibilities include designing reliable data flows, improving performance, resolving incidents and documenting design decisions. Experience with FastAPI or Django is useful. Salary CHF 110000 to 130000. Hybrid in Switzerland.\n"""
    + COMMON
    + """\nMandatory requirement stated at the end of this posting: German at CEFR C1 or above is required because this engineer directly supports German-speaking hospital customers. A1 or A2 is insufficient. Swiss work authorization is required."""
)
JOB_NURSE = (
    """Job: Registered Nurse, Adult Inpatient Ward. Provide direct nursing care, medication administration, patient monitoring, care planning and multidisciplinary handovers. Required: recognized nursing qualification, current Swiss recognized nursing license, at least three years of clinical nursing experience and current basic life support certification. Work includes rotating shifts and careful communication with patients and families.\n"""
    + COMMON
    + """\nMandatory requirements: German C1, current clinical nursing license and authorization to work in Switzerland. General hospital technology or software experience does not replace nursing qualifications."""
)
CASES = [
    ("backend_match", PROFILE_ENGINEER.format(german="C1"), JOB_ENGINEER),
    ("backend_unrelated", PROFILE_CHEF, JOB_ENGINEER),
    ("nurse_match", PROFILE_NURSE, JOB_NURSE),
    ("nurse_unrelated", PROFILE_ENGINEER.format(german="C1"), JOB_NURSE),
    ("german_tail_met", PROFILE_ENGINEER.format(german="C1"), JOB_ENGINEER),
    (
        "german_tail_not_met",
        PROFILE_ENGINEER.format(german="A1; beginner only, unable to work in German"),
        JOB_ENGINEER,
    ),
]
QUESTION = {
    "fit": {
        "type": "score",
        "instructions": "How well does this candidate match this job? Evaluate only stated career evidence and job requirements. Mandatory qualifications matter; missing or explicitly insufficient qualifications are gaps. Do not infer qualifications from unrelated experience.",
        "criteria": [
            "No relevant professional background for this role",
            "Low fit; lacks core mandatory background or qualifications",
            "Partial fit; meaningful overlap with important mandatory gaps",
            "Strong fit; core background with minor gaps",
            "Very strong fit; clear evidence for core experience and mandatory qualifications",
        ],
    }
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

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    record = {
        "purpose": "realistic synthetic whole-job/profile ordinal scoring, not production validation",
        "host": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "threads": 2,
            "device": "cpu",
        },
        "model": "convaiinnovations/laya",
        "revision": PIN,
        "laya": "0.4.17",
        "torch": torch.__version__,
        "questions": QUESTION,
        "cases": [],
    }
    try:
        started = time.perf_counter()
        agent = Agent("convaiinnovations/laya", revision=PIN, device="cpu", backend="eager")
        record["load_seconds"] = time.perf_counter() - started
        record["config"] = agent.cfg
        for limit in [512, 1024, 2048]:
            for name, profile, job in CASES:
                state = {"candidate": profile, "posting": job}
                started = time.perf_counter()
                before = len(samples)
                result = agent.predict(state, QUESTION, max_len=limit)
                elapsed = time.perf_counter() - started
                row = {
                    "id": name,
                    "max_len": limit,
                    "state": state,
                    "result": result,
                    "elapsed_seconds": elapsed,
                    "rss_mib": process.memory_info().rss / 1024**2,
                    "sampled_request_peak_mib": max(
                        samples[before:] or [process.memory_info().rss / 1024**2]
                    ),
                }
                record["cases"].append(row)
                print(
                    name,
                    limit,
                    round(result["answers"]["fit"]["score"], 3),
                    round(elapsed, 3),
                    result["usage"],
                    flush=True,
                )
        record["summary"] = {"sampled_peak_rss_mib": max(samples), "by_limit": {}}
        for limit in [512, 1024, 2048]:
            rows = [r for r in record["cases"] if r["max_len"] == limit]
            scores = {r["id"]: r["result"]["answers"]["fit"]["score"] for r in rows}
            record["summary"]["by_limit"][str(limit)] = {
                "median_seconds": statistics.median(r["elapsed_seconds"] for r in rows),
                "max_seconds": max(r["elapsed_seconds"] for r in rows),
                "any_truncated": any(r["result"]["usage"].get("truncated") for r in rows),
                "scores": scores,
                "comparisons": {
                    "backend_match_over_unrelated": scores["backend_match"]
                    > scores["backend_unrelated"],
                    "nurse_match_over_unrelated": scores["nurse_match"] > scores["nurse_unrelated"],
                    "tail_c1_over_a1": scores["german_tail_met"] > scores["german_tail_not_met"],
                },
            }
        Path(__file__).with_name("scoring-context-probe.json").write_text(
            json.dumps(record, indent=2) + "\n"
        )
        print(json.dumps(record["summary"], indent=2), flush=True)
    finally:
        stop.set()
        thread.join()


if __name__ == "__main__":
    main()
