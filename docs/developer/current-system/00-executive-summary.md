# Current System Executive Summary

## What This Project Is

The repository is a local-first, single-user job discovery and triage system.
It is not a public jobs marketplace, not an ATS, and not a collaborative hiring
platform. It automates a personal workflow:

1. query several job sources,
2. collect listings,
3. rank them with simple configurable rules,
4. persist the useful ones,
5. notify the user about the most relevant new opportunities,
6. provide interfaces to review, curate, export, and search the stored corpus.

In implementation terms, it is a Python application built around `JobSpy`,
SQLite, Streamlit, APScheduler, Telegram, FastAPI, and ChromaDB.

## The Core Problem It Tries To Solve

The project exists because manual job search is structurally inefficient:

- opportunities are fragmented across many sources,
- search must be repeated regularly,
- the same listing appears many times,
- relevance is noisy and subjective,
- interesting jobs are easy to miss between runs,
- users need memory across days and weeks, not only a current page of results,
- attention is scarce, so alerts must be selective,
- once jobs are collected, the user still needs review, filtering, and curation
  tools.

The current product turns that recurring manual activity into an automated
 retrieval, scoring, storage, and review loop.

## Product Shape

The product has four surfaces over one shared data layer:

- CLI runtime for scheduled or one-shot collection
- Streamlit dashboard for human review and maintenance
- REST API for scripts and automation
- MCP server for LLM-assisted exploration and actions

All four surfaces operate over the same persistent state rooted at
`JOB_SEARCH_DATA_DIR`.

## Architectural Character

The design philosophy is strongly configuration-driven:

- search behavior lives in `settings.yaml`,
- scoring is data-driven rather than code-driven,
- operational paths are fixed and derived from a single data root,
- runtime behavior is mostly deterministic once config is loaded.

The project chooses simplicity over heavy infrastructure:

- SQLite instead of a network database,
- local vector persistence instead of an external embeddings service,
- one runtime image serving multiple process roles,
- a thin service layer shared by the UI, API, and MCP adapter.

## What It Does Well

- It solves a real repetitive workflow end-to-end.
- It keeps state across runs, which is essential for detecting novelty.
- It separates saving from notifying via `save_threshold` and
  `notify_threshold`.
- It gives the user active control through bookmarking, applying, deleting, and
  exports.
- It has meaningful test coverage across runtime, storage, dashboard helpers,
  API, MCP, and integration flows.
- It packages well for personal deployment through Docker Compose.

## What It Does Not Attempt

The current system deliberately does not try to be:

- a multi-user SaaS,
- a compliant enterprise-grade recruitment platform,
- a machine-learned recommendation engine,
- a resume optimization or application generation suite,
- a robust source ingestion platform with official partner APIs,
- a full workflow system spanning discovery to interview scheduling.

It is best understood as a high-quality personal job search automation tool.

## Main Product Abstractions

The repository revolves around a small number of core abstractions:

- `Search intent`: the combination of sites, locations, and configured query
  strings
- `Job identity`: a normalized SHA256 hash of title, company, and location
- `Relevance`: a score derived from keyword categories and weights
- `Persistence threshold`: the minimum score that justifies keeping a job
- `Notification threshold`: the higher minimum score that justifies interrupting
  the user
- `Blacklist`: explicit memory of deleted jobs that must not re-enter the
  active corpus
- `Retention`: automatic cleanup of stale or low-value jobs
- `Semantic index`: an auxiliary vector representation of the saved corpus

These abstractions matter more than the specific frameworks used to implement
them.

## Best One-Sentence Description

This repository is a configurable personal opportunity intelligence loop for
job search: ingest, normalize, score, store, notify, inspect, and curate.
