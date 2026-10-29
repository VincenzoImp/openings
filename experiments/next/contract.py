"""Feasibility contract, not the production application.

The same use cases are called by HTTP and MCP. SQLite owns narrative,
claims, template policy, frozen generation inputs, drafts and PDF bytes.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Profile(Input):
    name: str = Field(min_length=1, max_length=200)
    headline: str = Field(max_length=300)


class Evidence(Input):
    profile_id: str
    kind: Literal["experience", "project", "course", "fact"]
    title: str = Field(min_length=1, max_length=200)
    narrative: str = Field(min_length=1, max_length=30_000)


class Claim(Input):
    evidence_id: str
    text: str = Field(min_length=1, max_length=1_000)
    approved: bool = False


class Template(Input):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["resume", "cover_letter"] = "resume"
    tex: str = Field(min_length=1, max_length=100_000)
    max_bullet_chars: int = Field(default=180, ge=20, le=1000)
    prompt_append: str = Field(default="", max_length=5_000)


class Job(Input):
    source_key: str = Field(min_length=1, max_length=1000)
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=300)
    posting: str = Field(min_length=1, max_length=100_000)


class Prepare(Input):
    job_id: str
    profile_id: str
    template_id: str
    general_prompt: str = Field(min_length=1, max_length=10_000)
    application_note: str = Field(default="", max_length=5_000)
    idempotency_key: str = Field(min_length=1, max_length=100)


class Bullet(Input):
    text: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=10)
    claim_ids: list[str] = Field(default_factory=list, max_length=10)


class Draft(Input):
    bullets: list[Bullet] = Field(min_length=1, max_length=30)


class Workspace:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript(Path(__file__).with_name("schema.sql").read_text())

    def close(self):
        self.db.close()

    def _get(self, table, record_id):
        # Table names are fixed by code, never provided by a caller.
        row = self.db.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown {table}")
        return dict(row)

    def add_profile(self, value: Profile):
        record_id = uuid4().hex
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO profile(id,basics) VALUES(?,?)",
                (record_id, canonical(value.model_dump())),
            )
        return {"id": record_id}

    def add_evidence(self, value: Evidence):
        record_id = uuid4().hex
        with self.lock, self.db:
            self._get("profile", value.profile_id)
            self.db.execute(
                "INSERT INTO evidence(id,profile_id,kind,title,narrative) VALUES(?,?,?,?,?)",
                (record_id, value.profile_id, value.kind, value.title, value.narrative),
            )
        return {"id": record_id}

    def add_claim(self, value: Claim):
        record_id = uuid4().hex
        with self.lock, self.db:
            self._get("evidence", value.evidence_id)
            self.db.execute(
                "INSERT INTO claim(id,evidence_id,text,approved) VALUES(?,?,?,?)",
                (record_id, value.evidence_id, value.text, int(value.approved)),
            )
        return {"id": record_id}

    def add_template(self, value: Template):
        record_id = uuid4().hex
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO template(id,name,kind,tex,rules,prompt_append) VALUES(?,?,?,?,?,?)",
                (
                    record_id,
                    value.name,
                    value.kind,
                    value.tex,
                    canonical({"max_bullet_chars": value.max_bullet_chars}),
                    value.prompt_append,
                ),
            )
        return {"id": record_id}

    def ingest(self, value: Job):
        with self.lock, self.db:
            previous = self.db.execute(
                "SELECT id FROM job WHERE source_key=?", (value.source_key,)
            ).fetchone()
            record_id = previous["id"] if previous else uuid4().hex
            self.db.execute(
                "INSERT INTO job(id,source_key,title,company,posting) VALUES(?,?,?,?,?) "
                "ON CONFLICT(source_key) DO UPDATE SET title=excluded.title,company=excluded.company,posting=excluded.posting",
                (record_id, value.source_key, value.title, value.company, value.posting),
            )
        return {"id": record_id, "created": previous is None}

    def prepare(self, value: Prepare):
        with self.lock, self.db:
            profile = self._get("profile", value.profile_id)
            job = self._get("job", value.job_id)
            template = self._get("template", value.template_id)
            evidence = [
                dict(r)
                for r in self.db.execute(
                    "SELECT * FROM evidence WHERE profile_id=? ORDER BY id", (value.profile_id,)
                )
            ]
            claims = [
                dict(r)
                for r in self.db.execute(
                    "SELECT claim.* FROM claim JOIN evidence ON evidence.id=claim.evidence_id WHERE evidence.profile_id=? AND claim.approved=1 ORDER BY claim.id",
                    (value.profile_id,),
                )
            ]
            snapshot = {
                "profile": profile,
                "job": job,
                "template": template,
                "evidence": evidence,
                "claims": claims,
                "prompts": {
                    "general": value.general_prompt,
                    "template_append": template["prompt_append"],
                    "application_note": value.application_note,
                },
            }
            encoded = canonical(snapshot)
            previous = self.db.execute(
                "SELECT id,snapshot FROM run WHERE idempotency_key=?", (value.idempotency_key,)
            ).fetchone()
            if previous:
                if previous["snapshot"] != encoded:
                    raise ValueError("Idempotency key was used with different inputs")
                return self.get_run(previous["id"])
            application_id, run_id = uuid4().hex, uuid4().hex
            self.db.execute(
                "INSERT INTO application(id,job_id,profile_id) VALUES(?,?,?)",
                (application_id, value.job_id, value.profile_id),
            )
            self.db.execute(
                "INSERT INTO run(id,application_id,idempotency_key,snapshot,snapshot_hash) VALUES(?,?,?,?,?)",
                (run_id, application_id, value.idempotency_key, encoded, digest(encoded.encode())),
            )
            return self.get_run(run_id)

    def get_run(self, run_id):
        with self.lock:
            row = self._get("run", run_id)
            row["snapshot"] = json.loads(row["snapshot"])
            return row

    def submit(self, run_id: str, draft: Draft):
        with self.lock, self.db:
            run = self.get_run(run_id)
            snapshot = run["snapshot"]
            evidence = {item["id"] for item in snapshot["evidence"]}
            claims = {item["id"]: item for item in snapshot["claims"]}
            maximum = json.loads(snapshot["template"]["rules"])["max_bullet_chars"]
            for bullet in draft.bullets:
                if len(bullet.text) > maximum:
                    raise ValueError("Bullet exceeds the template's character limit")
                if not set(bullet.evidence_ids) <= evidence:
                    raise ValueError("Evidence is outside the frozen profile context")
                if not set(bullet.claim_ids) <= claims.keys():
                    raise ValueError("Claim is unapproved or outside the frozen profile context")
                if any(
                    claims[c]["evidence_id"] not in bullet.evidence_ids for c in bullet.claim_ids
                ):
                    raise ValueError("Claim does not belong to the cited evidence")
            content = canonical(draft.model_dump())
            content_hash = digest(content.encode())
            existing = self.db.execute(
                "SELECT id FROM artifact WHERE run_id=? AND content_hash=?", (run_id, content_hash)
            ).fetchone()
            if existing:
                return {"id": existing["id"], "review_state": "needs_review"}
            artifact_id = uuid4().hex
            self.db.execute(
                "INSERT INTO artifact(id,run_id,content,content_hash) VALUES(?,?,?,?)",
                (artifact_id, run_id, content, content_hash),
            )
            self.db.execute("UPDATE run SET state='review' WHERE id=?", (run_id,))
            return {"id": artifact_id, "review_state": "needs_review"}

    def attach_pdf(self, artifact_id: str, pdf: bytes):
        if not pdf.startswith(b"%PDF-") or len(pdf) > 10 * 1024 * 1024:
            raise ValueError("Expected a PDF up to 10 MiB")
        sha = digest(pdf)
        with self.lock, self.db:
            self._get("artifact", artifact_id)
            self.db.execute(
                "INSERT OR IGNORE INTO blob VALUES(?,?,?)", (sha, "application/pdf", pdf)
            )
            self.db.execute("UPDATE artifact SET blob_sha=? WHERE id=?", (sha, artifact_id))
        return {"sha256": sha}

    def backup(self, path: Path):
        with self.lock, sqlite3.connect(path) as target:
            self.db.backup(target)


def interfaces(workspace: Workspace):
    api = FastAPI(title="Openings next feasibility contract")
    mcp = FastMCP("openings-next-feasibility")

    def call(method, value):
        try:
            return method(value)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @api.post("/profiles")
    def add_profile(value: Profile):
        return call(workspace.add_profile, value)

    @api.post("/evidence")
    def add_evidence(value: Evidence):
        return call(workspace.add_evidence, value)

    @api.post("/claims")
    def add_claim(value: Claim):
        return call(workspace.add_claim, value)

    @api.post("/templates")
    def add_template(value: Template):
        return call(workspace.add_template, value)

    @api.post("/jobs")
    def ingest(value: Job):
        return call(workspace.ingest, value)

    @api.post("/runs")
    def prepare(value: Prepare):
        return call(workspace.prepare, value)

    @api.get("/runs/{run_id}")
    def get_run_http(run_id: str):
        return call(workspace.get_run, run_id)

    @api.post("/runs/{run_id}/drafts")
    def submit_http(run_id: str, draft: Draft):
        try:
            return workspace.submit(run_id, draft)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    # Same DTOs and service methods as REST; MCP never receives a raw SQL interface.
    for name, method, model in [
        ("add_profile", workspace.add_profile, Profile),
        ("add_evidence", workspace.add_evidence, Evidence),
        ("add_claim", workspace.add_claim, Claim),
        ("add_template", workspace.add_template, Template),
        ("ingest", workspace.ingest, Job),
        ("prepare", workspace.prepare, Prepare),
    ]:

        def register(tool_name, handler, dto):
            def tool(value: dict):
                return handler(dto.model_validate(value))

            mcp.add_tool(tool, name=tool_name)

        register(name, method, model)

    @mcp.tool()
    def get_run(run_id: str):
        return workspace.get_run(run_id)

    @mcp.tool()
    def submit(run_id: str, draft: dict):
        return workspace.submit(run_id, Draft.model_validate(draft))

    return api, mcp
