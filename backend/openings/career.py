"""Career evidence, reusable claims and user-owned template packages."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .common import check_version, decode_record, encode, new_id, now
from .errors import DomainError, conflict, missing


DEFAULT_PROFILE = {
    "name": "",
    "headline": "",
    "location": "",
    "email": "",
    "phone": "",
    "roles": "",
    "preferences": "",
    "summary": "",
    "scoring_summary": "",
    "links": [],
    "metadata": {},
}
DEFAULT_GUIDANCE = (
    "Use only the supplied career evidence. Never invent qualifications, dates or metrics. "
    "Select relevant approved claims or write accurate new wording from detailed evidence. "
    "Respect the template and answer limits; make missing facts visible."
)
SCORING_FIELDS = {
    "headline",
    "location",
    "roles",
    "preferences",
    "summary",
    "scoring_summary",
    "metadata",
}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("metadata", "rules", "links", check_fields=False)
    @classmethod
    def finite_json(cls, value):
        if value is not None:
            try:
                encoded = json.dumps(value, allow_nan=False)
            except (TypeError, ValueError) as error:
                raise ValueError("Use finite JSON values.") from error
            if len(encoded) > 1000000:
                raise ValueError("Structured metadata exceeds the 1 MB limit.")
        return value


class NonNullUpdate(Input):
    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError(
                "Omit unchanged fields; clear text with an empty string or use an empty list/object."
            )
        return value


class ProfileUpdate(NonNullUpdate):
    expected_version: int = Field(ge=0, strict=True)
    name: str | None = Field(default=None, max_length=200)
    headline: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=100)
    roles: str | None = Field(default=None, max_length=3000)
    preferences: str | None = Field(default=None, max_length=10000)
    summary: str | None = Field(default=None, max_length=20000)
    scoring_summary: str | None = Field(default=None, max_length=6000)
    links: list[dict[str, str]] | None = Field(default=None, max_length=50)
    metadata: dict[str, Any] | None = None


KnowledgeKind = Literal[
    "experience", "project", "course", "education", "fact", "skill", "language", "other"
]


class KnowledgeCreate(Input):
    kind: KnowledgeKind = "experience"
    title: str = Field(min_length=1, max_length=300)
    narrative: str = Field(default="", max_length=100000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeUpdate(NonNullUpdate):
    expected_version: int = Field(ge=1, strict=True)
    kind: KnowledgeKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    narrative: str | None = Field(default=None, max_length=100000)
    metadata: dict[str, Any] | None = None


class ClaimCreate(Input):
    knowledge_id: str
    text: str = Field(min_length=1, max_length=5000)
    approved: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimUpdate(NonNullUpdate):
    expected_version: int = Field(ge=1, strict=True)
    knowledge_id: str | None = None
    text: str | None = Field(default=None, min_length=1, max_length=5000)
    approved: bool | None = None
    metadata: dict[str, Any] | None = None


class TemplateCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["resume", "cover_letter"] = "resume"
    tex: str = Field(default="", max_length=1000000)
    guidance: str = Field(default="", max_length=20000)
    rules: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False

    @field_validator("rules")
    @classmethod
    def validate_rules(cls, value):
        return validate_rules(value)


class TemplateUpdate(NonNullUpdate):
    expected_version: int = Field(ge=1, strict=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Literal["resume", "cover_letter"] | None = None
    tex: str | None = Field(default=None, max_length=1000000)
    guidance: str | None = Field(default=None, max_length=20000)
    rules: dict[str, Any] | None = None
    is_default: bool | None = None

    @field_validator("rules")
    @classmethod
    def validate_rules(cls, value):
        return validate_rules(value) if value is not None else None


class InstructionsUpdate(Input):
    expected_version: int = Field(ge=0, strict=True)
    general: str = Field(max_length=30000)


class ImportPreview(Input):
    text: str = Field(min_length=1, max_length=500000)
    title: str = Field(default="Imported career notes", max_length=300)


class CareerImport(Input):
    knowledge: list[KnowledgeCreate] = Field(default_factory=list, max_length=200)
    profile: dict[str, Any] | None = None
    expected_profile_version: int | None = Field(default=None, ge=0, strict=True)


def validate_rules(value):
    for key, low, high in [
        ("max_bullet_chars", 20, 5000),
        ("max_bullets", 1, 100),
        ("max_pages", 1, 30),
    ]:
        if key in value and (
            isinstance(value[key], bool)
            or not isinstance(value[key], int)
            or not low <= value[key] <= high
        ):
            raise ValueError(f"{key} must be an integer between {low} and {high}.")
    return value


def values(value):
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_unset=True, exclude_none=True)
    return dict(value)


def _setting(conn, key, default):
    row = conn.execute("SELECT * FROM settings WHERE key=?", (key,)).fetchone()
    return (
        {"data": json.loads(row["data"]), "version": row["version"]}
        if row
        else {"data": default, "version": 0}
    )


def _write_setting(conn, key, data, version):
    conn.execute(
        "INSERT INTO settings(key,data,version,updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET data=excluded.data,version=excluded.version,updated_at=excluded.updated_at",
        (key, encode(data), version, now()),
    )


def _bump_scoring(conn):
    previous = _setting(conn, "scoring_profile_revision", 0)
    _write_setting(
        conn, "scoring_profile_revision", int(previous["data"]) + 1, previous["version"] + 1
    )


def _get(conn, table, record_id, label):
    # Table names are fixed internally, never client-controlled.
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
    if row is None:
        missing(label)
    return dict(row)


def _page(limit, offset):
    if not 1 <= limit <= 200 or offset < 0:
        raise DomainError(422, "pagination", "Limit must be 1–200 and offset must be nonnegative.")


class CareerService:
    def __init__(self, workspace):
        self.workspace = workspace
        self.db = workspace.db
        with self.db.transaction() as conn:
            for key, default in [
                ("profile", DEFAULT_PROFILE),
                ("instructions", {"general": DEFAULT_GUIDANCE}),
            ]:
                if not _setting(conn, key, None)["version"]:
                    _write_setting(conn, key, default, 1)

    def get_profile(self) -> dict:
        """Read the current single-user profile and version, including optional compact scoring summary."""
        setting = self.workspace.get_settings("profile", DEFAULT_PROFILE)
        return {**DEFAULT_PROFILE, **setting["data"], "version": setting["version"]}

    def _apply_profile(self, conn, data, expected):
        setting = _setting(conn, "profile", DEFAULT_PROFILE)
        if setting["version"] != expected:
            conflict()
        previous = {**DEFAULT_PROFILE, **setting["data"]}
        merged = {**previous, **data}
        if any(previous.get(key) != merged.get(key) for key in SCORING_FIELDS):
            _bump_scoring(conn)
        if previous != merged:
            _write_setting(conn, "profile", merged, expected + 1)

    def update_profile(self, value: ProfileUpdate) -> dict:
        """Edit current profile with optimistic version checking. Relevant changes mark scores outdated without launching inference."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            self._apply_profile(conn, data, expected)
        return self.get_profile()

    def get_instructions(self) -> dict:
        """Read stored general document-writing guidance and its version."""
        setting = self.workspace.get_settings("instructions", {"general": DEFAULT_GUIDANCE})
        return {
            "general": setting["data"].get("general", DEFAULT_GUIDANCE),
            "version": setting["version"],
        }

    def update_instructions(self, value: InstructionsUpdate) -> dict:
        """Save editable general CV/letter guidance; this does not change scoring or old contexts."""
        self.workspace.set_settings(
            "instructions", {"general": value.general}, value.expected_version
        )
        return self.get_instructions()

    def list_knowledge(
        self,
        q: str = "",
        kind: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
    ) -> dict:
        """Search career evidence. summary=true returns bounded previews/counts; get a record for its full narrative and metadata."""
        _page(limit, offset)
        where, params = [], []
        if q:
            where.append("(title LIKE ? OR narrative LIKE ?)")
            params += [f"%{q}%", f"%{q}%"]
        if kind:
            where.append("kind=?")
            params.append(kind)
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = (
            "id,kind,title,version,created_at,updated_at,substr(narrative,1,240) AS narrative_preview,"
            "(SELECT COUNT(*) FROM claims WHERE knowledge_id=knowledge.id) AS claim_count,"
            "(SELECT COUNT(*) FROM files WHERE knowledge_id=knowledge.id) AS file_count"
            if summary
            else "*"
        )
        rows = self.db.all(
            f"SELECT {columns} FROM knowledge{clause} ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        total = self.db.one(f"SELECT COUNT(*) AS n FROM knowledge{clause}", params)["n"]
        return {
            "items": rows if summary else [decode_record(row, ["metadata"]) for row in rows],
            "total": total,
        }

    def get_knowledge(self, knowledge_id: str) -> dict:
        """Read one detailed experience, project, course or factual evidence record."""
        row = self.db.one("SELECT * FROM knowledge WHERE id=?", (knowledge_id,))
        if not row:
            missing("Career knowledge")
        return decode_record(row, ["metadata"])

    def create_knowledge(self, value: KnowledgeCreate) -> dict:
        """Add detailed career evidence. Facts should come from the user, not a job posting."""
        record_id, timestamp = new_id(), now()
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO knowledge(id,kind,title,narrative,metadata,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (
                    record_id,
                    value.kind,
                    value.title,
                    value.narrative,
                    encode(value.metadata),
                    timestamp,
                    timestamp,
                ),
            )
            _bump_scoring(conn)
        return self.get_knowledge(record_id)

    def update_knowledge(self, knowledge_id: str, value: KnowledgeUpdate) -> dict:
        """Revise career evidence using its current version; prior frozen application contexts remain unchanged."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            row = _get(conn, "knowledge", knowledge_id, "Career knowledge")
            check_version(row, expected)
            previous = decode_record(row, ["metadata"])
            merged = {**previous, **data}
            if any(
                previous[key] != merged[key] for key in ["kind", "title", "narrative", "metadata"]
            ):
                conn.execute(
                    "UPDATE knowledge SET kind=?,title=?,narrative=?,metadata=?,version=version+1,updated_at=? WHERE id=?",
                    (
                        merged["kind"],
                        merged["title"],
                        merged["narrative"],
                        encode(merged["metadata"]),
                        now(),
                        knowledge_id,
                    ),
                )
                _bump_scoring(conn)
        return self.get_knowledge(knowledge_id)

    def delete_knowledge(self, knowledge_id: str, expected_version: int) -> dict:
        """Permanently delete a career record and its reusable claims/live assets; frozen contexts retain copies."""
        with self.db.transaction() as conn:
            check_version(
                _get(conn, "knowledge", knowledge_id, "Career knowledge"), expected_version
            )
            conn.execute("DELETE FROM knowledge WHERE id=?", (knowledge_id,))
            _bump_scoring(conn)
        self.db.collect_blobs()
        return {"deleted": True, "id": knowledge_id}

    def list_claims(
        self,
        knowledge_id: str = "",
        approved: bool | None = None,
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
    ) -> dict:
        """List reusable claims by evidence, approval or text. summary=true omits metadata and bounds wording previews."""
        _page(limit, offset)
        where, params = [], []
        if knowledge_id:
            where.append("knowledge_id=?")
            params.append(knowledge_id)
        if approved is not None:
            where.append("approved=?")
            params.append(int(approved))
        if q:
            where.append(
                "(text LIKE ? OR EXISTS(SELECT 1 FROM knowledge WHERE knowledge.id=claims.knowledge_id AND title LIKE ?))"
            )
            params.extend([f"%{q}%", f"%{q}%"])
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = (
            "id,knowledge_id,approved,version,created_at,updated_at,substr(text,1,240) AS text_preview,"
            "(SELECT title FROM knowledge WHERE knowledge.id=claims.knowledge_id) AS knowledge_title"
            if summary
            else "*"
        )
        rows = self.db.all(
            f"SELECT {columns} FROM claims{clause} ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        result = []
        for row in rows:
            row = row if summary else decode_record(row, ["metadata"])
            row["approved"] = bool(row["approved"])
            result.append(row)
        return {
            "items": result,
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM claims{clause}", params)["n"],
        }

    def get_claim(self, claim_id: str) -> dict:
        """Read a reusable claim and its evidence ID."""
        row = self.db.one("SELECT * FROM claims WHERE id=?", (claim_id,))
        if not row:
            missing("Claim")
        row = decode_record(row, ["metadata"])
        row["approved"] = bool(row["approved"])
        return row

    def create_claim(self, value: ClaimCreate) -> dict:
        """Create reusable claim wording tied to evidence. Approval defaults to false."""
        record_id, timestamp = new_id(), now()
        with self.db.transaction() as conn:
            _get(conn, "knowledge", value.knowledge_id, "Career knowledge")
            conn.execute(
                "INSERT INTO claims(id,knowledge_id,text,approved,metadata,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (
                    record_id,
                    value.knowledge_id,
                    value.text,
                    int(value.approved),
                    encode(value.metadata),
                    timestamp,
                    timestamp,
                ),
            )
            _bump_scoring(conn)
        return self.get_claim(record_id)

    def update_claim(self, claim_id: str, value: ClaimUpdate) -> dict:
        """Revise or approve a claim with version checking; document generation does not silently approve new facts."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            row = _get(conn, "claims", claim_id, "Claim")
            check_version(row, expected)
            previous = decode_record(row, ["metadata"])
            previous["approved"] = bool(previous["approved"])
            merged = {**previous, **data}
            _get(conn, "knowledge", merged["knowledge_id"], "Career knowledge")
            if any(
                previous[key] != merged[key]
                for key in ["knowledge_id", "text", "approved", "metadata"]
            ):
                conn.execute(
                    "UPDATE claims SET knowledge_id=?,text=?,approved=?,metadata=?,version=version+1,updated_at=? WHERE id=?",
                    (
                        merged["knowledge_id"],
                        merged["text"],
                        int(merged["approved"]),
                        encode(merged["metadata"]),
                        now(),
                        claim_id,
                    ),
                )
                _bump_scoring(conn)
        return self.get_claim(claim_id)

    def delete_claim(self, claim_id: str, expected_version: int) -> dict:
        """Permanently delete a reusable claim; existing application snapshots remain unchanged."""
        with self.db.transaction() as conn:
            check_version(_get(conn, "claims", claim_id, "Claim"), expected_version)
            conn.execute("DELETE FROM claims WHERE id=?", (claim_id,))
            _bump_scoring(conn)
        return {"deleted": True, "id": claim_id}

    def list_templates(
        self,
        kind: str = "",
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
    ) -> dict:
        """List template packages/defaults. summary=true omits TeX, guidance and rules; get the template before editing or compiling externally."""
        _page(limit, offset)
        where, params = [], []
        if kind:
            where.append("kind=?")
            params.append(kind)
        if q:
            where.append("(name LIKE ? OR guidance LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])
        clause = " WHERE " + " AND ".join(where) if where else ""
        columns = (
            "id,name,kind,is_default,version,created_at,updated_at,"
            "(SELECT COUNT(*) FROM files WHERE template_id=templates.id) AS file_count"
            if summary
            else "*"
        )
        rows = self.db.all(
            f"SELECT {columns} FROM templates{clause} ORDER BY is_default DESC,created_at,id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        items = []
        for row in rows:
            row = row if summary else decode_record(row, ["rules"])
            row["is_default"] = bool(row["is_default"])
            items.append(row)
        return {
            "items": items,
            "total": self.db.one(f"SELECT COUNT(*) AS n FROM templates{clause}", params)["n"],
        }

    def get_template(self, template_id: str) -> dict:
        """Read raw template source, guidance and typed limits; fetch attached assets separately."""
        row = self.db.one("SELECT * FROM templates WHERE id=?", (template_id,))
        if not row:
            missing("Template")
        row = decode_record(row, ["rules"])
        row["is_default"] = bool(row["is_default"])
        return row

    def create_template(self, value: TemplateCreate) -> dict:
        """Store a user template and optional rules. The first template of a kind becomes its default."""
        record_id, timestamp = new_id(), now()
        with self.db.transaction() as conn:
            is_default = (
                value.is_default
                or not conn.execute(
                    "SELECT 1 FROM templates WHERE kind=? AND is_default=1", (value.kind,)
                ).fetchone()
            )
            if is_default:
                conn.execute(
                    "UPDATE templates SET is_default=0,version=version+1,updated_at=? WHERE kind=? AND is_default=1",
                    (timestamp, value.kind),
                )
            conn.execute(
                "INSERT INTO templates(id,name,kind,tex,guidance,rules,is_default,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    record_id,
                    value.name,
                    value.kind,
                    value.tex,
                    value.guidance,
                    encode(value.rules),
                    int(is_default),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_template(record_id)

    def update_template(self, template_id: str, value: TemplateUpdate) -> dict:
        """Revise template source/default/guidance with optimistic version checking; old contexts stay frozen."""
        data = values(value)
        expected = data.pop("expected_version")
        with self.db.transaction() as conn:
            row = _get(conn, "templates", template_id, "Template")
            check_version(row, expected)
            previous = decode_record(row, ["rules"])
            previous["is_default"] = bool(previous["is_default"])
            merged = {**previous, **data}
            if any(
                previous[key] != merged[key]
                for key in ["name", "kind", "tex", "guidance", "rules", "is_default"]
            ):
                if merged["is_default"]:
                    conn.execute(
                        "UPDATE templates SET is_default=0,version=version+1,updated_at=? WHERE kind=? AND id<>? AND is_default=1",
                        (now(), merged["kind"], template_id),
                    )
                conn.execute(
                    "UPDATE templates SET name=?,kind=?,tex=?,guidance=?,rules=?,is_default=?,version=version+1,updated_at=? WHERE id=?",
                    (
                        merged["name"],
                        merged["kind"],
                        merged["tex"],
                        merged["guidance"],
                        encode(merged["rules"]),
                        int(merged["is_default"]),
                        now(),
                        template_id,
                    ),
                )
        return self.get_template(template_id)

    def delete_template(self, template_id: str, expected_version: int) -> dict:
        """Delete a live template and assets; prior application contexts retain their exact template/asset copies."""
        with self.db.transaction() as conn:
            row = _get(conn, "templates", template_id, "Template")
            check_version(row, expected_version)
            conn.execute("DELETE FROM templates WHERE id=?", (template_id,))
            if row["is_default"]:
                other = conn.execute(
                    "SELECT id FROM templates WHERE kind=? ORDER BY created_at,id LIMIT 1",
                    (row["kind"],),
                ).fetchone()
                if other:
                    conn.execute(
                        "UPDATE templates SET is_default=1,version=version+1,updated_at=? WHERE id=?",
                        (now(), other["id"]),
                    )
        self.db.collect_blobs()
        return {"deleted": True, "id": template_id}

    def preview_import(self, value: ImportPreview) -> dict:
        """Preview JSON or plain-text career import without modifying stored information."""
        try:
            data = json.loads(value.text)
        except json.JSONDecodeError:
            item = KnowledgeCreate(kind="other", title=value.title, narrative=value.text)
            return {
                "knowledge": [item.model_dump()],
                "warnings": ["Text is preserved as one narrative. Review before importing."],
            }
        if isinstance(data, list):
            data = {"knowledge": data}
        elif isinstance(data, dict) and "title" in data and "knowledge" not in data:
            data = {"knowledge": [data]}
        elif (
            isinstance(data, dict)
            and "knowledge" not in data
            and "profile" not in data
            and any(key in DEFAULT_PROFILE for key in data)
        ):
            data = {"profile": data}
        if not isinstance(data, dict) or not isinstance(data.get("knowledge", []), list):
            raise DomainError(
                422,
                "import_format",
                "Use a profile object, a JSON knowledge array, or an object with profile/knowledge fields.",
            )
        try:
            items = [
                KnowledgeCreate.model_validate(item).model_dump()
                for item in data.get("knowledge", [])
            ]
            result = {"knowledge": items}
            if data.get("profile") is not None:
                if not isinstance(data["profile"], dict):
                    raise DomainError(422, "import_format", "The profile must be a JSON object.")
                patch = ProfileUpdate.model_validate(
                    {**data["profile"], "expected_version": self.get_profile()["version"]}
                )
                result["profile"] = patch.model_dump(
                    exclude_unset=True, exclude={"expected_version"}
                )
                result["expected_profile_version"] = patch.expected_version
        except ValidationError as error:
            raise DomainError(
                422,
                "import_validation",
                "The import contains invalid career fields.",
                error.errors(include_context=False),
            ) from error
        result["warnings"] = [
            f"Field '{key}' is not imported; edit it explicitly in the workspace."
            for key in data
            if key not in {"knowledge", "profile"}
        ]
        if result.get("profile"):
            result["warnings"].append(
                "The previewed profile fields will replace those current fields only after confirmation."
            )
        return result

    def import_knowledge(self, value: CareerImport) -> dict:
        """Confirm a previewed career import: append narratives and optionally apply explicitly versioned profile fields."""
        profile_data = None
        if value.profile is not None:
            if value.expected_profile_version is None:
                raise DomainError(
                    422,
                    "profile_version",
                    "Confirm the profile version shown in the import preview.",
                )
            try:
                patch = ProfileUpdate.model_validate(
                    {**value.profile, "expected_version": value.expected_profile_version}
                )
                profile_data = values(patch)
                profile_data.pop("expected_version")
            except ValidationError as error:
                raise DomainError(
                    422,
                    "import_validation",
                    "The import contains invalid profile fields.",
                    error.errors(include_context=False),
                ) from error
        timestamp = now()
        identifiers = []
        with self.db.transaction() as conn:
            if profile_data is not None:
                self._apply_profile(conn, profile_data, value.expected_profile_version)
            for item in value.knowledge:
                record_id = new_id()
                conn.execute(
                    "INSERT INTO knowledge(id,kind,title,narrative,metadata,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        record_id,
                        item.kind,
                        item.title,
                        item.narrative,
                        encode(item.metadata),
                        timestamp,
                        timestamp,
                    ),
                )
                identifiers.append(record_id)
            if identifiers:
                _bump_scoring(conn)
        return {
            "profile": self.get_profile(),
            "items": [self.get_knowledge(record_id) for record_id in identifiers],
            "total": len(identifiers),
        }


def register_api(router, career: CareerService):
    @router.get("/career/profile")
    def get_profile():
        return career.get_profile()

    @router.patch("/career/profile")
    def update_profile(value: ProfileUpdate):
        return career.update_profile(value)

    @router.get("/career/knowledge")
    def list_knowledge(
        q: str = "", kind: str = "", limit: int = 100, offset: int = 0, summary: bool = False
    ):
        return career.list_knowledge(q, kind, limit, offset, summary)

    @router.post("/career/knowledge", status_code=201)
    def create_knowledge(value: KnowledgeCreate):
        return career.create_knowledge(value)

    @router.get("/career/knowledge/{knowledge_id}")
    def get_knowledge(knowledge_id: str):
        return career.get_knowledge(knowledge_id)

    @router.patch("/career/knowledge/{knowledge_id}")
    def update_knowledge(knowledge_id: str, value: KnowledgeUpdate):
        return career.update_knowledge(knowledge_id, value)

    @router.delete("/career/knowledge/{knowledge_id}")
    def delete_knowledge(knowledge_id: str, expected_version: int):
        return career.delete_knowledge(knowledge_id, expected_version)

    @router.get("/career/claims")
    def list_claims(
        knowledge_id: str = "",
        approved: bool | None = None,
        limit: int = 100,
        offset: int = 0,
        summary: bool = False,
        q: str = "",
    ):
        return career.list_claims(knowledge_id, approved, limit, offset, summary, q)

    @router.post("/career/claims", status_code=201)
    def create_claim(value: ClaimCreate):
        return career.create_claim(value)

    @router.get("/career/claims/{claim_id}")
    def get_claim(claim_id: str):
        return career.get_claim(claim_id)

    @router.patch("/career/claims/{claim_id}")
    def update_claim(claim_id: str, value: ClaimUpdate):
        return career.update_claim(claim_id, value)

    @router.delete("/career/claims/{claim_id}")
    def delete_claim(claim_id: str, expected_version: int):
        return career.delete_claim(claim_id, expected_version)

    @router.get("/templates")
    def list_templates(
        kind: str = "", limit: int = 100, offset: int = 0, summary: bool = False, q: str = ""
    ):
        return career.list_templates(kind, limit, offset, summary, q)

    @router.post("/templates", status_code=201)
    def create_template(value: TemplateCreate):
        return career.create_template(value)

    @router.get("/templates/{template_id}")
    def get_template(template_id: str):
        return career.get_template(template_id)

    @router.patch("/templates/{template_id}")
    def update_template(template_id: str, value: TemplateUpdate):
        return career.update_template(template_id, value)

    @router.delete("/templates/{template_id}")
    def delete_template(template_id: str, expected_version: int):
        return career.delete_template(template_id, expected_version)

    @router.get("/instructions")
    def get_instructions():
        return career.get_instructions()

    @router.patch("/instructions")
    def update_instructions(value: InstructionsUpdate):
        return career.update_instructions(value)

    @router.post("/career/import/preview")
    def preview_import(value: ImportPreview):
        return career.preview_import(value)

    @router.post("/career/import", status_code=201)
    def import_knowledge(value: CareerImport):
        return career.import_knowledge(value)


def register_mcp(mcp, career: CareerService):
    from mcp.types import ToolAnnotations

    for name, handler in [
        ("career_get_profile", career.get_profile),
        ("career_update_profile", career.update_profile),
        ("knowledge_list", career.list_knowledge),
        ("knowledge_get", career.get_knowledge),
        ("knowledge_create", career.create_knowledge),
        ("knowledge_update", career.update_knowledge),
        ("knowledge_delete", career.delete_knowledge),
        ("claims_list", career.list_claims),
        ("claims_get", career.get_claim),
        ("claims_create", career.create_claim),
        ("claims_update", career.update_claim),
        ("claims_delete", career.delete_claim),
        ("templates_list", career.list_templates),
        ("templates_get", career.get_template),
        ("templates_create", career.create_template),
        ("templates_update", career.update_template),
        ("templates_delete", career.delete_template),
        ("instructions_get", career.get_instructions),
        ("instructions_update", career.update_instructions),
        ("career_preview_import", career.preview_import),
        ("career_import", career.import_knowledge),
    ]:
        read_only = name.endswith(("_get", "_list")) or name in {
            "career_get_profile",
            "career_preview_import",
            "instructions_get",
        }
        mcp.add_tool(
            handler,
            name=name,
            annotations=ToolAnnotations(
                readOnlyHint=read_only,
                destructiveHint=name.endswith("_delete"),
                idempotentHint=read_only
                or name
                in {
                    "career_update_profile",
                    "instructions_update",
                    "knowledge_update",
                    "claims_update",
                    "templates_update",
                },
                openWorldHint=False,
            ),
        )
