"""Frozen application contexts and the staleness of what they froze."""

from __future__ import annotations

import hashlib
import json

from ..career.models import DEFAULT_GUIDANCE, DEFAULT_PROFILE
from ..career.records import _get, _page, _setting
from ..common import decode_record, encode, new_id, now
from ..errors import DomainError, conflict, missing
from ..policy import frozen_policy
from ..snapshots import payload_text, store_context
from ..staleness import application_staleness, store_context_inputs
from .models import OWNER_COLUMNS, ContextCreate, StalenessStage


class ContextOperations:
    """Preparing, reading and listing contexts; staleness reports."""

    def prepare_context(self, value: ContextCreate) -> dict:
        """Freeze job, career evidence, approved claims, templates/assets and stored instructions for an external agent. Use an idempotency key for retries."""
        request = value.model_dump(exclude={"idempotency_key"})
        with self.db.transaction() as conn:
            if value.idempotency_key:
                existing = conn.execute(
                    "SELECT * FROM contexts WHERE idempotency_key=?", (value.idempotency_key,)
                ).fetchone()
                if existing:
                    record = self.context_record(conn, existing)
                    if record["payload"].get("request") != request:
                        conflict("This idempotency key was used for another preparation request.")
                    return record
            application = _get(conn, "applications", value.application_id, "Application")
            job = _get(conn, "jobs", application["job_id"], "Job")
            if job["triage"] == "dismissed":
                conflict("Restore this dismissed job before preparing an application.")
            application = decode_record(application, ["questions", "answers", "requirements"])
            # The application note frozen since 0.5 is its pinned note since 0.22.
            pinned = conn.execute(
                "SELECT body FROM notes WHERE application_id=? AND pinned_at IS NOT NULL",
                (application["id"],),
            ).fetchone()
            application["note"] = pinned["body"] if pinned else ""
            job = decode_record(job, ["metadata", "overrides"])
            profile = _setting(conn, "profile", DEFAULT_PROFILE)
            instructions = _setting(conn, "instructions", {"general": DEFAULT_GUIDANCE})
            knowledge = [
                decode_record(dict(row), ["metadata", "dates", "skills"])
                for row in conn.execute("SELECT * FROM knowledge ORDER BY position,created_at,id")
            ]
            if value.knowledge_ids is not None:
                requested = set(value.knowledge_ids)
                if requested - {row["id"] for row in knowledge}:
                    raise DomainError(
                        422, "unknown_evidence", "Selected career evidence was not found."
                    )
                knowledge = [row for row in knowledge if row["id"] in requested]
            knowledge_ids = {row["id"] for row in knowledge}
            claims = [
                decode_record(dict(row), ["metadata"])
                for row in conn.execute(
                    "SELECT * FROM claims WHERE approved=1 ORDER BY position,created_at,id"
                )
                if row["knowledge_id"] in knowledge_ids
            ]
            for claim in claims:
                claim["approved"] = bool(claim["approved"])
                claim["default_in_cv"] = bool(claim["default_in_cv"])
            if value.claim_ids is not None:
                selected = set(value.claim_ids)
                if selected - {row["id"] for row in claims}:
                    raise DomainError(
                        422,
                        "unapproved_claim",
                        "Selected claims must be approved and belong to the selected evidence.",
                    )
                claims = [row for row in claims if row["id"] in selected]
            selected_templates = list(
                dict.fromkeys(
                    ([value.template_id] if value.template_id else []) + value.template_ids
                )
            )
            if selected_templates:
                selected = {
                    row["id"]: dict(row)
                    for row in conn.execute(
                        "SELECT * FROM templates WHERE id IN ("
                        + ",".join("?" for _ in selected_templates)
                        + ")",
                        selected_templates,
                    )
                }
                if len(selected) != len(selected_templates):
                    missing("Template")
                templates = [selected[template_id] for template_id in selected_templates]
            else:
                templates = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT * FROM templates WHERE is_default=1 ORDER BY kind,id"
                    )
                ]
            if not templates:
                raise DomainError(
                    422,
                    "template_required",
                    "Add or select a template before preparing the application context.",
                )
            templates = [decode_record(row, ["rules"]) for row in templates]
            for template in templates:
                template["is_default"] = bool(template["is_default"])
            context_id, timestamp = new_id(), now()
            assets = []
            for owner_type, identifiers in [
                ("knowledge", [row["id"] for row in knowledge]),
                ("template", [row["id"] for row in templates]),
            ]:
                if not identifiers:
                    continue
                column = OWNER_COLUMNS[owner_type]
                for raw in conn.execute(
                    f"SELECT * FROM files WHERE {column} IN ("
                    + ",".join("?" for _ in identifiers)
                    + f") ORDER BY {column},name,id",
                    identifiers,
                ):
                    original = dict(raw)
                    owner_id = original[column]
                    copied_id = new_id()
                    copied_name = f"{owner_type}/{owner_id}/{original['name']}"
                    assets.append(
                        {
                            "id": copied_id,
                            "sha256": original["sha256"],
                            "name": original["name"],
                            "path": copied_name,
                            "media_type": original["media_type"],
                            "size": original["size"],
                            "owner_type": owner_type,
                            "owner_id": owner_id,
                            "original_file_id": original["id"],
                            "url": f"/api/v1/files/{copied_id}/content",
                        }
                    )
            snapshot = {
                "request": request,
                "profile": {**DEFAULT_PROFILE, **profile["data"], "version": profile["version"]},
                "job": job,
                "application": application,
                "knowledge": knowledge,
                "claims": claims,
                "templates": templates,
                "instructions": {
                    "general": instructions["data"].get("general", DEFAULT_GUIDANCE),
                    "version": instructions["version"],
                    "template_append": {row["id"]: row["guidance"] for row in templates},
                    "application_note": "\n\n".join(
                        part for part in [application["note"], value.note] if part
                    ),
                },
                "questions": application["questions"],
                "files": assets,
                # Each policy section with its version; an unconfirmed item says so.
                "policy": frozen_policy(conn),
            }
            encoded = encode(snapshot)
            signature = hashlib.sha256(encoded.encode()).hexdigest()
            conn.execute(
                "INSERT INTO contexts(id,application_id,signature,idempotency_key,created_at) VALUES(?,?,?,?,?)",
                (
                    context_id,
                    value.application_id,
                    signature,
                    value.idempotency_key,
                    timestamp,
                ),
            )
            # The payload's shared values and asset files are stored once, as parts.
            store_context(
                conn, context_id, encoded, [{**asset, "name": asset["path"]} for asset in assets]
            )
            store_context_inputs(conn, context_id, timestamp, encoded)
            if job["triage"] != "saved":
                conn.execute(
                    "UPDATE jobs SET triage='saved',version=version+1,updated_at=? WHERE id=?",
                    (timestamp, job["id"]),
                )
            self.workspace.event(
                "context_prepared",
                job["id"],
                value.application_id,
                {"context_id": context_id},
                conn,
                subject=("context", context_id),
            )
            self.workspace.clear_ready(conn, value.application_id, "context_prepared")
        return self.get_context(context_id)

    @staticmethod
    def context_record(conn, row):
        return {
            "id": row["id"],
            "application_id": row["application_id"],
            "payload": json.loads(payload_text(conn, row["id"], row["frame"])),
            "signature": row["signature"],
            "idempotency_key": row["idempotency_key"],
            "created_at": row["created_at"],
            "resource_uri": f"openings://contexts/{row['id']}",
        }

    def get_context(self, context_id: str) -> dict:
        """Read one immutable application context. File entries contain metadata/URLs rather than binary bytes."""
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM contexts WHERE id=?", (context_id,)).fetchone()
            if not row:
                missing("Application context")
            return self.context_record(conn, row)

    def list_contexts(
        self,
        application_id: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = True,
        q: str = "",
    ) -> dict:
        """List frozen contexts without payloads, by application_id; q searches the job's title and company. summary=true (the default) adds labels and file, document and evidence counts."""
        _page(limit, offset)
        where, params = [], []
        if application_id:
            where.append("application_id=?")
            params.append(application_id)
        if q:
            where.append(
                "EXISTS(SELECT 1 FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=contexts.application_id AND (j.title LIKE ? OR j.company LIKE ?))"
            )
            params.extend([f"%{q}%", f"%{q}%"])
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = "id,application_id,signature,created_at"
        if summary:
            columns += (
                ",job_title,company,note_preview,knowledge_count,claim_count,template_name,file_count"
                ",(SELECT COUNT(*) FROM documents WHERE context_id=contexts.id) AS document_count"
            )
        rows = self.db.all(
            f"SELECT {columns} FROM contexts{clause} ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return {
            "items": rows,
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM contexts{clause}", params)["n"],
            "limit": limit,
            "offset": offset,
        }

    def application_staleness(self, application_id: str) -> dict:
        """Report whether an application's current revision leaves were built on older inputs than documents use now, naming each changed part: Profile parts (name, headline, contact details, links, summary), confirmed policy items of eligibility, writing (by scope) and facts, general instructions, selected templates, Career entries and claims. Profile metadata, preferences, roles and decision items do not make documents stale. Read-only; contexts stay frozen."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id,status,version FROM applications WHERE id=?", (application_id,)
            ).fetchone()
            if not row:
                missing("Application")
            report = application_staleness(conn, [application_id])[application_id]
        return {"application_id": application_id, "status": row["status"], **report}

    def list_staleness(
        self,
        status: StalenessStage = "draft",
        stale_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List applications in one stage (default draft; "all" for every stage) whose current revisions were built on older inputs, with each changed part (as staleness_get). stale_only=false also lists current ones. Read-only."""
        _page(limit, offset)
        where, params = ("AND a.status=?", [status]) if status != "all" else ("", [])
        with self.db.connect() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT a.id,a.status,a.version,a.updated_at,j.id AS job_id,j.title,j.company "
                    "FROM applications a JOIN jobs j ON j.id=a.job_id "
                    f"WHERE EXISTS(SELECT 1 FROM documents d WHERE d.application_id=a.id) {where} "
                    "ORDER BY a.updated_at DESC,a.id",
                    params,
                )
            ]
            reports = application_staleness(conn, [row["id"] for row in rows])
        items = []
        for row in rows:
            report = reports[row["id"]]
            if not report["documents"] or (stale_only and not report["stale"]):
                continue
            items.append(
                {
                    "application_id": row["id"],
                    "status": row["status"],
                    "version": row["version"],
                    "job": {"id": row["job_id"], "title": row["title"], "company": row["company"]},
                    **report,
                }
            )
        return {
            "items": items[offset : offset + limit],
            "total": len(items),
            "limit": limit,
            "offset": offset,
        }
