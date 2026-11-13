"""One name and one argument shape per operation (#167); the earlier names are gone (0.23)."""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError

from openings.actors import OWNER, acting_as
from openings.app import create_app
from openings.career import ClaimCreate, KnowledgeCreate
from openings.documents import DocumentCreate, UploadReservation
from openings.interfaces import catalog

ROOT = Path(__file__).resolve().parents[2]
# Resources that name one record of the workspace, or a mass noun, stay singular.
SINGULAR = {
    "capabilities",
    "career",
    "collection",
    "insights",
    "instructions",
    "knowledge",
    "overview",
    "owner_password",
    "policy",
    "profile",
    "staleness",
    "timeline",
    "workspace",
}
# The tool names before 0.22, kept as deprecated aliases in 0.22 and removed in 0.23.
REMOVED_NAMES = {
    "application_create": "applications_create",
    "application_delete": "applications_delete",
    "application_get": "applications_get",
    "application_history": "applications_history",
    "application_prepare_context": "contexts_create",
    "application_ready": "applications_ready",
    "application_staleness": "staleness_get",
    "application_update": "applications_update",
    "applications_staleness": "staleness_list",
    "career_get_profile": "profile_get",
    "career_update_profile": "profile_update",
    "collection_yield": "sources_yield",
    "job_distinct": "jobs_distinct",
    "job_forget": "jobs_delete",
    "job_get": "jobs_get",
    "job_ingest": "jobs_create",
    "job_merge": "jobs_merge",
    "job_triage": "jobs_triage",
    "job_update": "jobs_update",
    "jobs_search": "jobs_list",
    "note_add": "notes_create",
    "note_delete": "notes_delete",
    "note_get": "notes_get",
    "note_update": "notes_update",
    "responses_add": "responses_create",
    "responses_remove": "responses_delete",
    "skill_get": "skills_get",
    "token_create": "tokens_create",
    "token_revoke": "tokens_revoke",
    "workspace_restore_upload": "workspace_restore",
}
# The tools that took their filters or options as flat arguments before 0.22, and
# beside value in 0.22; from 0.23 only inside value (with these identifiers flat).
FLAT_BEFORE = {
    "knowledge_list": set(),
    "claims_list": set(),
    "templates_list": set(),
    "contexts_list": set(),
    "documents_list": set(),
    "files_list": set(),
    "collection_runs_list": set(),
    "sources_list": set(),
    "tasks_list": set(),
    "runs_get": {"run_id"},
}
# Where an earlier name may still appear: the upgrade guides that map it, the
# release history and the accepted proposal, which records the earlier state.
MAY_NAME_EARLIER = {
    "CHANGELOG.md",
    "docs/user/upgrading-0.22.md",
    "docs/user/upgrading-0.23.md",
    "docs/developer/proposal-redesign.md",
}
GUIDE = ROOT / "docs/user/upgrading-0.23.md"


async def call(mcp, name, arguments=None):
    result = await mcp.call_tool(name, arguments or {})
    return json.loads(result.content[0].text)


async def refused(mcp, name, arguments):
    with pytest.raises(ToolError) as error:
        await mcp.call_tool(name, arguments)
    return json.loads(str(error.value))["error"]


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "names.sqlite", start_worker=False)


def seed(app):
    """A job with a note and an application, a Career entry and a claim."""
    workspace, career = app.state.workspace, app.state.career
    with acting_as(OWNER):
        job = workspace.ingest_job({"title": "Synthetic engineer", "posting": "Build APIs."})
        application = workspace.create_application({"job_id": job["id"]})
        note = workspace.add_note(job["id"], {"body": "Synthetic note."})
        entry = career.create_knowledge(
            KnowledgeCreate(title="Synthetic project", narrative="Built it.")
        )
        claim = career.create_claim(ClaimCreate(knowledge_id=entry["id"], text="Built a thing."))
    return {"job": job, "application": application, "note": note, "entry": entry, "claim": claim}


def test_every_tool_is_named_from_its_declaration():
    """`<resource>_<verb>`, plural resources, no name given by hand."""
    operations, _, _ = catalog()
    names = [operation.canonical_name for operation in operations if operation.tool]
    assert len(names) == len(set(names))
    for operation in operations:
        assert operation.resource in SINGULAR or operation.resource.endswith("s"), operation.id
        assert not hasattr(operation.tool, "name"), operation.id
        assert not hasattr(operation, "aliases"), operation.id


async def test_the_earlier_names_are_gone_and_each_has_its_tool(app):
    tools = {tool.name for tool in await app.state.mcp.list_tools()}
    assert not set(REMOVED_NAMES) & tools
    assert set(REMOVED_NAMES.values()) <= tools
    for name in REMOVED_NAMES:
        with pytest.raises(ToolError, match=f"Unknown tool: {name}"):
            await app.state.mcp.call_tool(name, {})


async def test_filters_beside_value_are_refused_not_ignored(app):
    data = seed(app)
    mcp = app.state.mcp
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    for name, identifiers in FLAT_BEFORE.items():
        assert set(tools[name].input_schema["properties"]) == {"value", *identifiers}, name
    error = await refused(mcp, "knowledge_list", {"q": "Synthetic", "summary": False})
    assert error["code"] == "validation"
    assert sorted(item["field"] for item in error["details"]) == [["q"], ["summary"]]
    error = await refused(mcp, "documents_list", {"limit": 5, "value": {"limit": 5}})
    assert error["details"][0]["field"] == ["limit"]
    full = await call(mcp, "knowledge_list", {"value": {"q": "Synthetic", "summary": False}})
    assert full["items"][0]["narrative"] == "Built it."
    assert (await call(mcp, "claims_list", {"value": {"knowledge_id": data["entry"]["id"]}}))[
        "total"
    ] == 1


async def test_no_schema_or_description_marks_anything_deprecated(app):
    """What 0.19 to 0.22 deprecated is gone from REST and MCP, not merely marked."""
    pattern = re.compile(r"deprecat|removed in 0\.23|until 0\.23", re.IGNORECASE)
    for tool in await app.state.mcp.list_tools():
        assert not pattern.search(json.dumps(tool.input_schema)), tool.name
        assert not pattern.search(tool.description or ""), tool.name
    openapi = json.dumps(app.openapi())
    assert not pattern.search(openapi)
    for field in ('"availability"', '"preferences"', '"roles"'):
        assert field not in openapi, field


async def test_lists_return_summaries_by_default_with_limit_offset_and_total(app):
    mcp = app.state.mcp
    data = seed(app)
    lists = [tool.name for tool in await mcp.list_tools() if tool.name.endswith("_list")]
    # Bounded by one job, one application or the installation: every item and a total.
    bounded = {
        "notes_list": {"job_id": data["job"]["id"]},
        "responses_list": {"application_id": data["application"]["id"]},
        "providers_list": {},
        "skills_list": {},
        "tokens_list": {},
    }
    for name in lists:
        if name in bounded:
            assert "total" in await call(mcp, name, bounded[name]), name
            continue
        result = await call(mcp, name, {"value": {"limit": 7, "offset": 0}})
        assert (result["limit"], result["offset"]) == (7, 0), name
        assert "total" in result and "items" in result, name
    for name in ("knowledge_list", "claims_list", "templates_list", "contexts_list", "files_list"):
        schema = next(tool for tool in await mcp.list_tools() if tool.name == name).input_schema
        query = next(iter(schema["$defs"].values()))
        assert query["properties"]["summary"]["default"] is True, name
    assert "narrative" not in (await call(mcp, "knowledge_list"))["items"][0]


async def test_every_delete_requires_expected_version(app):
    operations, _, _ = catalog()
    tools = {tool.name: tool for tool in await app.state.mcp.list_tools()}
    paths = app.openapi()["paths"]
    deletes = [
        operation
        for operation in operations
        if any(route.method == "DELETE" and not route.custom for route in operation.rest)
    ]
    assert {operation.id for operation in deletes} >= {
        "notes.delete",
        "documents.delete",
        "files.delete",
    }
    for operation in deletes:
        if operation.id == "tokens.revoke":
            continue  # a token has no version: revoking is not a versioned delete
        schema = tools[operation.canonical_name].input_schema
        assert "expected_version" in schema.get("required", []), operation.id
        for route in operation.rest:
            if route.method == "DELETE":
                parameters = paths["/api/v1" + route.path]["delete"]["parameters"]
                version = next(p for p in parameters if p["name"] == "expected_version")
                assert version["required"] is True, operation.id


def test_notes_revisions_and_files_are_deleted_with_their_version(app):
    data = seed(app)
    documents = app.state.documents
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic owner token")["token"]
    with TestClient(app, base_url="http://localhost:8080") as client:
        client.headers["Authorization"] = "Bearer " + token
        note = data["note"]
        stale = client.delete(f"/api/v1/notes/{note['id']}?expected_version=9")
        assert stale.status_code == 409
        assert stale.json()["error"]["details"] == {"current_version": note["version"]}
        # Without a version: refused, and the note stays.
        missing = client.delete(f"/api/v1/notes/{note['id']}")
        assert missing.status_code == 422
        assert app.state.workspace.get_note(note["id"])["body"] == "Synthetic note."
        deleted = client.delete(f"/api/v1/notes/{note['id']}?expected_version={note['version']}")
        assert deleted.status_code == 200

        revision = documents.create_document(
            DocumentCreate(application_id=data["application"]["id"], kind="other", content={"a": 1})
        )
        assert client.delete(f"/api/v1/documents/{revision['id']}").status_code == 422
        assert (
            client.delete(f"/api/v1/documents/{revision['id']}?expected_version=2").json()["error"][
                "code"
            ]
            == "conflict"
        )
        assert (
            client.delete(
                f"/api/v1/documents/{revision['id']}?expected_version={revision['version']}"
            ).status_code
            == 200
        )

        content = b"Synthetic asset."
        grant = documents.reserve_upload(
            UploadReservation(
                owner_type="knowledge",
                owner_id=data["entry"]["id"],
                name="asset.txt",
                size=len(content),
                media_type="text/plain",
            )
        )
        stored = client.put(grant["url"], headers=grant["headers"], content=content).json()
        assert documents.get_file(stored["id"])["version"] == 1
        assert client.delete(f"/api/v1/files/{stored['id']}").status_code == 422
        assert client.delete(f"/api/v1/files/{stored['id']}?expected_version=2").status_code == 409
        assert client.delete(f"/api/v1/files/{stored['id']}?expected_version=1").status_code == 200


async def test_mcp_deletes_without_a_version_are_refused(app):
    data = seed(app)
    mcp = app.state.mcp
    revision = app.state.documents.create_document(
        DocumentCreate(application_id=data["application"]["id"], kind="other", content={"a": 1})
    )
    for name, arguments in (
        ("notes_delete", {"note_id": data["note"]["id"]}),
        ("documents_delete", {"document_id": revision["id"]}),
        ("files_delete", {"file_id": "missing"}),
    ):
        error = await refused(mcp, name, arguments)
        assert error["code"] == "validation", name
        assert error["details"][0]["field"] == ["expected_version"], name
    assert app.state.workspace.get_note(data["note"]["id"])["version"] == 1


async def test_removed_fields_are_refused_on_rest_and_mcp_and_never_returned(app):
    """The application note, the job's availability and the Profile's preferences and roles."""
    data = seed(app)
    mcp = app.state.mcp
    job, application = app.state.workspace.get_job(data["job"]["id"]), data["application"]
    app.state.auth.setup("synthetic-password")
    token = app.state.auth.create_token("Synthetic owner token")["token"]
    profile_version = app.state.career.get_profile()["version"]
    writes = (
        ("POST", "/applications", "applications_create", {}, {"job_id": job["id"], "note": "x"}),
        (
            "PATCH",
            f"/applications/{application['id']}",
            "applications_update",
            {"application_id": application["id"]},
            {"expected_version": application["version"], "note": "x"},
        ),
        (
            "PATCH",
            f"/jobs/{job['id']}",
            "jobs_update",
            {"job_id": job["id"]},
            {"expected_version": job["version"], "availability": "closed"},
        ),
        (
            "PATCH",
            "/career/profile",
            "profile_update",
            {},
            {"expected_version": profile_version, "roles": "Engineer"},
        ),
        (
            "PATCH",
            "/career/profile",
            "profile_update",
            {},
            {"expected_version": profile_version, "preferences": "Remote"},
        ),
    )
    with TestClient(app, base_url="http://localhost:8080") as client:
        client.headers["Authorization"] = "Bearer " + token
        for method, path, tool, identifiers, body in writes:
            response = client.request(method, "/api/v1" + path, json=body)
            assert response.status_code == 422, (path, body)
            error = await refused(mcp, tool, {**identifiers, "value": body})
            assert error["code"] == "validation", (tool, body)
        assert "note" not in client.get(f"/api/v1/applications/{application['id']}").json()
        assert "availability" not in client.get(f"/api/v1/jobs/{job['id']}").json()
        assert "availability" not in client.get("/api/v1/jobs").json()["items"][0]
        profile = client.get("/api/v1/career/profile").json()
        assert not {"preferences", "roles"} & set(profile)
        preview = client.post(
            "/api/v1/career/import/preview",
            json={"text": json.dumps({"profile": {"name": "Alex", "roles": "Engineer"}})},
        )
        assert preview.status_code == 422
        assert preview.json()["error"]["code"] == "import_validation"
    # Nothing was written.
    assert app.state.workspace.get_job(job["id"])["version"] == job["version"]
    assert app.state.career.get_profile()["version"] == profile_version
    assert app.state.workspace.list_applications()["total"] == 1


async def test_every_create_accepts_an_idempotency_key(app):
    operations, _, _ = catalog()
    tools = {tool.name: tool for tool in await app.state.mcp.list_tools()}
    creates = [
        operation
        for operation in operations
        if operation.verb in {"create", "add", "ask", "start"} and operation.tool
    ]
    assert len(creates) == 15
    for operation in creates:
        schema = tools[operation.canonical_name].input_schema
        body = schema["$defs"][schema["properties"]["value"]["$ref"].rsplit("/", 1)[1]]
        assert "idempotency_key" in body["properties"], operation.id


async def test_a_retried_create_returns_its_record_and_a_reused_key_is_refused(app):
    data = seed(app)
    mcp = app.state.mcp
    job_id, entry_id = data["job"]["id"], data["entry"]["id"]
    # Each create: its request, and a change to it that a reused key refuses.
    requests = {
        "jobs_create": ({"title": "Pasted role", "posting": "Pasted text."}, {"title": "Other"}),
        "notes_create": ({"body": "Retried note."}, {"body": "Other"}),
        "knowledge_create": ({"title": "Retried entry"}, {"title": "Other"}),
        "claims_create": ({"knowledge_id": entry_id, "text": "Retried claim."}, {"text": "Other"}),
        "templates_create": ({"name": "Retried template"}, {"name": "Other"}),
        "documents_create": (
            {"application_id": data["application"]["id"], "kind": "other"},
            {"title": "Other"},
        ),
        "sources_create": (
            {
                "name": "Retried search",
                "kind": "jobspy",
                "config": {"query": "engineer", "providers": ["linkedin"]},
            },
            {"name": "Other"},
        ),
        "tokens_create": ({"name": "Retried token", "kind": "agent"}, {"name": "Other"}),
    }
    for name, (body, change) in requests.items():
        arguments = {"job_id": job_id} if name == "notes_create" else {}

        async def create(fields, key, name=name, arguments=arguments):
            return await call(mcp, name, {**arguments, "value": {**fields, "idempotency_key": key}})

        first = await create(body, "k1")
        again = await create(body, "k1")
        assert again["id"] == first["id"], name
        # Another key creates another record (with other content: two revisions with
        # the same content are one revision even without a key).
        assert (await create({**body, **change}, "k2"))["id"] != first["id"], name
        error = await refused(
            mcp, name, {**arguments, "value": {**body, **change, "idempotency_key": "k1"}}
        )
        assert error["code"] == "conflict", name
        if name == "jobs_create":
            assert first["created"] is True and again["created"] is False
        if name == "tokens_create":
            assert first["token"] and again["token"] is None
    # A key whose record is gone is free again.
    note = await call(
        mcp, "notes_create", {"job_id": job_id, "value": {"body": "Gone.", "idempotency_key": "g"}}
    )
    await call(mcp, "notes_delete", {"note_id": note["id"], "expected_version": note["version"]})
    again = await call(
        mcp, "notes_create", {"job_id": job_id, "value": {"body": "Gone.", "idempotency_key": "g"}}
    )
    assert again["id"] != note["id"]


def shipped_text_files():
    """Every text the product ships or documents, by path from the repository root."""
    patterns = (
        "*.md",
        "skills/**/*",
        "docs/**/*.md",
        "docs/**/*.json",
        "examples/**/*",
        "frontend/src/**/*",
        "frontend/tests/**/*",
        "scripts/*",
        "backend/openings/**/*.json",
        "backend/tests/agent_roundtrip.py",
    )
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            name = str(path.relative_to(ROOT))
            if path.is_file() and name not in MAY_NAME_EARLIER and "node_modules" not in name:
                try:
                    yield name, path.read_text()
                except UnicodeDecodeError:
                    continue


async def test_no_earlier_name_remains_outside_the_upgrade_guides(app):
    pattern = re.compile(r"(?<![\w{.-])(" + "|".join(sorted(REMOVED_NAMES)) + r")(?!\w)")
    found = {name: sorted(set(pattern.findall(text))) for name, text in shipped_text_files()}
    assert not {name: names for name, names in found.items() if names}
    for tool in await app.state.mcp.list_tools():
        assert not pattern.findall(tool.description or ""), tool.name
        assert not pattern.findall(json.dumps(tool.input_schema)), tool.name
    for prompt in await app.state.mcp.list_prompts():
        assert not pattern.findall(prompt.description or ""), prompt.name


def test_the_upgrade_guide_maps_every_earlier_name_to_its_tool():
    guide = GUIDE.read_text()
    for old, new in REMOVED_NAMES.items():
        assert f"| `{old}` | `{new}` |" in guide, old
    for name in FLAT_BEFORE:
        assert f"| `{name}` |" in guide, name
